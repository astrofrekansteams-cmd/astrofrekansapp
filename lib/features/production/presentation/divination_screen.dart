import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../../core/assets/app_assets.dart';
import '../../../core/assets/divination_asset_resolver.dart';
import '../../../core/astrology/data/production_models.dart';
import '../../../core/astrology/data/production_repository.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/localization/locale_controller.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../../billing/application/coin_spend.dart';
import '../../billing/application/entitlement_service.dart';
import '../application/action_state.dart';
import '../application/divination_draft.dart';
import '../../billing/data/coin_repository.dart';
import 'divination_picker.dart';

final _spreadsProvider = FutureProvider.autoDispose.family(
  (ref, DeckType deck) async =>
      await ref
          .watch(productionRepositoryProvider)
          ?.spreads(deck, ref.watch(localeControllerProvider).languageCode) ??
      <DivinationSpread>[],
);
final _assetsProvider = FutureProvider((ref) => DivinationAssetResolver.load());

/// Warms the reveal's images before the flip starts (overridable in tests).
typedef RevealPrecache =
    Future<void> Function(
      BuildContext context,
      DeckType deck,
      DivinationReading reading,
      String? Function(DrawnItem item) faceOf,
    );
final revealPrecacheProvider = Provider<RevealPrecache>(
  (ref) => precacheReveal,
);

/// Face art for a drawn item. Runes are always shown as stones.
String? _faceOf(
  DivinationAssetResolver? resolver,
  DeckType deck,
  DrawnItem item,
) => resolver?.resolve(deck.name, item.assetKey, stone: deck == DeckType.rune);
final readingProvider = FutureProvider.autoDispose.family(
  (ref, String id) => ref.watch(productionRepositoryProvider)!.reading(id),
);
final readingsProvider = FutureProvider.autoDispose(
  (ref) async =>
      await ref.watch(productionRepositoryProvider)?.readings() ??
      <ContractRecord>[],
);

/// Theme groups in display order. Spreads arrive with a server-side theme.
const _themeOrder = [
  'general',
  'love',
  'relationship',
  'career',
  'money',
  'spiritual',
];

/// Tarot, rune and Katina: pick a spread, ask, shuffle, pick, reveal, read.
///
/// "Shuffle" asks the server for a face-down session: it shuffles the whole
/// deck (OS entropy) and fixes every slot's orientation, but only tells the
/// app how many slots there are. The user picks slots in order (local state),
/// and the reveal resolves exactly those slots - the i-th pick fills the i-th
/// position. This screen never decides or sees a card before the reveal.
class DivinationScreen extends ConsumerStatefulWidget {
  const DivinationScreen({super.key, required this.deck, this.readingId});
  final DeckType deck;
  final String? readingId;
  @override
  ConsumerState<DivinationScreen> createState() => _DivinationState();
}

class _DivinationState extends ConsumerState<DivinationScreen> {
  final session = ActionState<DrawSession>();
  final reveal = ActionState<DivinationReading>();
  final interpretation = ActionState<Json>();
  final question = TextEditingController();
  String theme = 'general';
  DivinationSpread? spread;
  bool optional = false;
  bool _questionError = false;

  /// Picks for the current face-down session, mirrored into the draft store
  /// so leaving the screen does not lose them.
  DivinationSelection? selection;

  /// Idempotency ref of the current shuffle; reused when retrying it.
  String? _consumerRef;

  /// The sequential flip has finished; show the full reading.
  bool _revealDone = false;

  /// The session can no longer be revealed (server said so, or its time ran
  /// out): the reveal CTA is disabled and "shuffle again" is the action.
  bool _expired = false;

  late final DivinationDrafts _drafts = ref.read(
    divinationDraftsProvider.notifier,
  );

  @override
  void initState() {
    super.initState();
    if (widget.readingId == null) _restore();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // The face-down art is ready before the deck is ever shown.
    unawaited(precacheDeck(context, widget.deck));
  }

  @override
  void dispose() {
    selection?.removeListener(_syncPicks);
    session.dispose();
    reveal.dispose();
    interpretation.dispose();
    question.dispose();
    selection?.dispose();
    super.dispose();
  }

  String get _deckKey => widget.deck.name;
  String get _face => widget.deck == DeckType.rune ? 'runes' : 'cards';

  // ------------------------------------------------------------ restore

  /// Resumes an open draft for this deck: same session, same picks in the
  /// same order, same setup. A finished draft shows its reading; an expired
  /// one shows the expired state. Nothing new is created.
  void _restore() {
    final draft = _drafts.of(widget.deck);
    if (draft == null) return;
    spread = draft.spread;
    theme = draft.spread.theme;
    question.text = draft.question;
    optional = draft.optional;
    session.value = AsyncData(draft.session);
    if (draft.reading case final DivinationReading reading) {
      reveal.value = AsyncData(reading);
      _revealDone = true; // already seen: no second flip
      return;
    }
    _expired = draft.expired || _pastExpiry(draft.session);
    _setSelection(
      DivinationSelection(
        required: draft.session.requiredSelections,
        deckSize: draft.session.deckSize,
        initial: draft.picks,
        locked: draft.revealing || _expired,
      ),
    );
    WidgetsBinding.instance.addPostFrameCallback((_) => _verify(draft));
  }

  bool _pastExpiry(DrawSession s) =>
      s.expiresAt != null && !s.expiresAt!.isAfter(DateTime.now());

  /// Confirms a restored draft with the server (public state only).
  Future<void> _verify(DivinationDraft draft) async {
    final repo = ref.read(productionRepositoryProvider);
    if (repo == null || !mounted) return;
    final id = draft.session.id;
    try {
      final fresh = await repo.drawSession(id);
      if (!mounted || session.value?.asData?.value.id != id) return;
      switch (fresh.status) {
        case 'expired':
          _markExpired(id);
        case 'completed' when fresh.readingId != null:
          // Revealed while away: show that reading, never the picker again.
          final reading = await repo.reading(fresh.readingId!);
          _drafts.update(widget.deck, id, (d) => d.copyWith(reading: reading));
          if (!mounted || session.value?.asData?.value.id != id) return;
          setState(() {
            reveal.value = AsyncData(reading);
            _revealDone = true;
          });
        default:
          // A reveal that was in flight when the screen closed: resend the
          // same picks; the server answers with the same reading.
          if (draft.revealing && selection?.isComplete == true) {
            await _reveal(repo);
          }
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.kind == ApiErrorKind.notFound) {
        _drafts.clear(widget.deck);
        _changeSpread();
      }
    }
  }

  void _setSelection(DivinationSelection? next) {
    selection?.removeListener(_syncPicks);
    selection?.dispose();
    selection = next?..addListener(_syncPicks);
  }

  void _syncPicks() {
    final current = session.value?.asData?.value;
    final picks = selection;
    if (current == null || picks == null) return;
    _drafts.update(
      widget.deck,
      current.id,
      (d) =>
          d.copyWith(picks: picks.picks, revealing: picks.locked && !_expired),
    );
  }

  void _markExpired(String sessionId) {
    _drafts.update(widget.deck, sessionId, (d) => d.copyWith(expired: true));
    if (!mounted) return;
    setState(() {
      _expired = true;
      selection?.lock();
    });
  }

  // ------------------------------------------------------------ actions

  void _clearPicks() {
    _setSelection(null);
    reveal.value = null;
    interpretation.value = null;
    _revealDone = false;
    _expired = false;
  }

  /// Shuffle face down. [fresh] = a new shuffle (new ref); otherwise a retry
  /// of the failed one, which the server answers idempotently.
  Future<void> _shuffle(
    ProductionRepository repo, {
    bool fresh = true,
    bool payWithCoins = false,
  }) async {
    final selected = spread;
    if (selected == null) return;
    final text = question.text.trim();
    if (selected.isQuestionSpread && text.length < 3) {
      setState(() => _questionError = true);
      return;
    }
    if (fresh || _consumerRef == null) _consumerRef = newConsumerRef();
    final consumerRef = _consumerRef!;
    final locale = context.languageCode;
    final includeOptional = optional;
    // The shuffle is felt, not waited on: 0.8-1.5 s, none with reduced motion.
    final minimum = context.reduceMotion
        ? Duration.zero
        : const Duration(milliseconds: 1100);
    setState(() {
      _questionError = false;
      _clearPicks();
    });
    _drafts.clear(widget.deck);
    final created = await session.run(() async {
      final results = await Future.wait<Object?>([
        repo.createDrawSession(
          widget.deck,
          selected.code,
          consumerRef: consumerRef,
          locale: locale,
          question: text.isEmpty ? null : text,
          includeOptional: includeOptional,
          payWithCoins: payWithCoins,
        ),
        Future<void>.delayed(minimum),
      ]);
      return results.first! as DrawSession;
    });
    if (created == null) {
      if (mounted) await _offerCoins(repo);
      return;
    }
    if (created.coinsSpent > 0) {
      ref
        ..invalidate(coinWalletProvider)
        ..invalidate(drawAllowanceProvider);
    }
    ref.invalidate(drawAllowanceProvider);
    // Stored even if the screen closed meanwhile: coming back resumes it.
    _drafts.put(
      widget.deck,
      DivinationDraft(
        session: created,
        spread: selected,
        question: text,
        optional: includeOptional,
      ),
    );
    if (!mounted) return;
    setState(
      () => _setSelection(
        DivinationSelection(
          required: created.requiredSelections,
          deckSize: created.deckSize,
        ),
      ),
    );
  }

  /// When the plan does not cover this draw (today's allowance used up, or
  /// a spread outside the plan), offer to pay with AstroCoins instead.
  Future<void> _offerCoins(ProductionRepository repo) async {
    final error = session.value?.error;
    if (error is! ApiException) return;
    final reason = switch (error.code) {
      'daily_draw_limit_reached' => 'extra_draw',
      'premium_required' => 'advanced_spread',
      _ => null,
    };
    if (reason == null || ref.read(coinRepositoryProvider) == null) return;
    final catalog = await ref.read(coinCatalogProvider.future);
    final wallet = await ref.read(coinWalletProvider.future);
    if (!mounted || catalog == null || wallet == null) return;
    final price = catalog.priceOf(reason);
    final choice = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        key: const ValueKey('coin-offer'),
        title: Text(b12(context, 'coin_offer_title_$reason')),
        content: Text(
          b12(context, 'coin_offer_body')
              .replaceAll('{price}', '$price')
              .replaceAll('{balance}', '${wallet.balance}'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, 'plans'),
            child: Text(b12(context, 'coin_offer_plans')),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, 'wallet'),
            child: Text(b12(context, 'coin_offer_earn')),
          ),
          if (wallet.balance >= price)
            FilledButton(
              key: const ValueKey('coin-offer-pay'),
              onPressed: () => Navigator.pop(context, 'pay'),
              child: Text(
                b12(context, 'coin_offer_pay').replaceAll('{price}', '$price'),
              ),
            ),
        ],
      ),
    );
    if (!mounted) return;
    switch (choice) {
      case 'pay':
        await _shuffle(repo, fresh: false, payWithCoins: true);
      case 'plans':
        await context.push(AppRoutes.premium);
      case 'wallet':
        await context.push(AppRoutes.coins);
    }
  }

  Future<void> _reveal(ProductionRepository repo) async {
    final current = session.value?.asData?.value;
    final picks = selection;
    if (current == null || picks == null || !picks.isComplete || _expired) {
      return;
    }
    if (_pastExpiry(current)) {
      _markExpired(current.id);
      return;
    }
    picks.lock(); // immutable from here on, even if the request fails
    final resolver = await ref.read(_assetsProvider.future);
    final reading = await reveal.run(() async {
      final result = await repo.revealDrawSession(current.id, picks.picks);
      // The flip starts only once its art is decoded: no empty frames.
      if (mounted) {
        await ref
            .read(revealPrecacheProvider)
            .call(
              context,
              widget.deck,
              result,
              (item) => _faceOf(resolver, widget.deck, item),
            );
      }
      return result;
    });
    if (reading != null) {
      _drafts.update(
        widget.deck,
        current.id,
        (d) => d.copyWith(reading: reading, revealing: false),
      );
      ref.invalidate(readingsProvider);
    } else if (reveal.value?.error case ApiException(
      code: 'divination_session_expired',
    )) {
      _markExpired(current.id);
    }
  }

  /// Back to the spread setup; the open session is simply abandoned.
  void _changeSpread() {
    _drafts.clear(widget.deck);
    setState(() {
      session.value = null;
      _consumerRef = null;
      _clearPicks();
    });
  }

  /// The AstroCoin purchase of one "Derinleştir" press, reused on every
  /// retry of it until the server has answered; the server charges it once.
  String? _deepenRef;
  String? _deepenReadingId;

  /// Readings interpreted in this visit: pressing again opens the same
  /// report at no cost, so no price is shown or asked.
  final _interpreted = <String>{};

  bool _isInterpreted(DivinationReading reading) =>
      reading.hasInterpretation || _interpreted.contains(reading.id);

  Future<void> _deepen(DivinationReading reading) async {
    final repo = ref.read(productionRepositoryProvider);
    if (repo == null) return;
    final paid =
        !_isInterpreted(reading) &&
        !ref.read(entitlementServiceProvider).canUse(PremiumFeature.advancedAi);
    if (_deepenReadingId != reading.id) {
      _deepenReadingId = reading.id;
      _deepenRef = null;
    }
    if (paid && _deepenRef == null) {
      if (!await confirmCoinSpend(context, ref, CoinItem.aiDeepReading)) {
        return;
      }
      _deepenRef = newCoinRef('deep');
    }
    if (!mounted) return;
    final consumerRef = paid ? _deepenRef : null;
    final locale = context.languageCode;
    final result = await interpretation.run(
      () =>
          repo.interpret(reading.id, locale: locale, consumerRef: consumerRef),
    );
    if (consumerRef != null) {
      ref.invalidate(coinWalletProvider);
      final error = interpretation.value?.error;
      final retryable =
          error is ApiException &&
          (error.kind == ApiErrorKind.network ||
              error.kind == ApiErrorKind.timeout);
      if (!retryable) _deepenRef = null;
      if (isInsufficientCoins(error) && mounted) {
        // The balance changed since the price was confirmed: offer the
        // wallet; nothing was charged.
        if (await confirmCoinSpend(context, ref, CoinItem.aiDeepReading)) {
          _deepenRef = newCoinRef('deep');
          if (mounted) await _deepen(reading);
        }
        return;
      }
    }
    if (result != null) _interpreted.add(reading.id);
    if (result != null && mounted) {
      final id = Uri.encodeComponent(result['id'] as String);
      // 200 is the finished report (already interpreted); 202 is its job.
      await context.push<void>(
        result.containsKey('sections')
            ? '${AppRoutes.aiReports}/$id'
            : '${AppRoutes.aiReports}?job=$id',
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final repo = ref.watch(productionRepositoryProvider);
    return ListenableBuilder(
      listenable: Listenable.merge([session, reveal, interpretation]),
      builder: (context, _) {
        final created = session.value?.asData?.value;
        final revealed = reveal.value?.asData?.value;
        return CorePage(
          title: _deckKey,
          children: [
            if (repo == null)
              AstroCard(child: Text(b12(context, 'demo_unavailable')))
            else if (widget.readingId != null)
              ApiStateView(
                value: ref.watch(readingProvider(widget.readingId!)),
                onRetry: () =>
                    ref.invalidate(readingProvider(widget.readingId!)),
                builder: (reading) => _ReadingView(
                  reading: reading,
                  deepening: interpretation,
                  interpreted: _isInterpreted(reading),
                  onDeepen: () => _deepen(reading),
                ),
              )
            else if (revealed != null)
              _revealed(repo, revealed)
            else if (created != null && selection != null)
              ..._picking(repo, created, selection!)
            else ...[
              _DeckHero(deck: widget.deck, shuffling: session.busy),
              if (session.value case final AsyncValue<DrawSession> v
                  when v.hasError)
                ApiStateView(
                  value: v,
                  onRetry: () => _shuffle(repo, fresh: false),
                  builder: (_) => const SizedBox.shrink(),
                ),
              if (!session.busy) ..._setup(repo),
            ],
            if (widget.readingId == null) _history(),
          ],
        );
      },
    );
  }

  List<Widget> _picking(
    ProductionRepository repo,
    DrawSession created,
    DivinationSelection picks,
  ) {
    final failure = switch (reveal.value) {
      final AsyncValue<DivinationReading> v when v.hasError && !_expired => v,
      _ => null,
    };
    return [
      Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            created.spreadName,
            textAlign: TextAlign.center,
            style: AppTypography.headlineMedium,
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            b12(context, 'pick_intro_$_face'),
            textAlign: TextAlign.center,
            style: AppTypography.bodySmall,
          ),
        ],
      ),
      HiddenDeck(deck: widget.deck, selection: picks),
      if (_expired) ...[
        AstroErrorCard(
          key: const ValueKey('session-expired'),
          message: b12(context, 'divination_session_expired'),
        ),
        AstroButton(
          key: const ValueKey('reshuffle-button'),
          label: b12(context, 'reshuffle'),
          icon: Icons.auto_awesome,
          onPressed: () => _shuffle(repo),
        ),
      ],
      SelectionPanel(
        deck: widget.deck,
        session: created,
        selection: picks,
        revealing: reveal.busy,
        expired: _expired,
        onReveal: () => _reveal(repo),
      ),
      if (failure != null)
        ApiStateView(
          value: failure,
          onRetry: () => _reveal(repo),
          builder: (_) => const SizedBox.shrink(),
        ),
      if (!reveal.busy)
        AstroOutlineButton(
          label: b12(context, 'change_spread'),
          onPressed: _changeSpread,
        ),
    ];
  }

  Widget _revealed(ProductionRepository repo, DivinationReading reading) {
    if (!_revealDone) {
      final resolver = ref.watch(_assetsProvider).asData?.value;
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            reading.spreadName,
            textAlign: TextAlign.center,
            style: AppTypography.headlineLarge,
          ),
          AppSpacing.gapLg,
          RevealSequence(
            deck: widget.deck,
            reading: reading,
            faceOf: (item) => _faceOf(resolver, widget.deck, item),
            onDone: () => setState(() => _revealDone = true),
          ),
        ],
      );
    }
    return _ReadingView(
      reading: reading,
      deepening: interpretation,
      interpreted: _isInterpreted(reading),
      onDeepen: () => _deepen(reading),
      onNewReading: () => _shuffle(repo),
      onChangeSpread: _changeSpread,
    );
  }

  List<Widget> _setup(ProductionRepository repo) => [
    ApiStateView(
      value: ref.watch(_spreadsProvider(widget.deck)),
      onRetry: () => ref.invalidate(_spreadsProvider(widget.deck)),
      builder: (spreads) {
        if (spreads.isEmpty) {
          return AstroEmptyState(
            kind: AstroEmptyStateKind.noData,
            title: b12(context, 'empty'),
          );
        }
        final themes = [
          for (final t in _themeOrder)
            if (spreads.any((s) => s.theme == t)) t,
        ];
        final visible = spreads.where((s) => s.theme == theme).toList();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            AstroSectionTitle(title: b12(context, 'choose_spread')),
            AppSpacing.gapSm,
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  for (final t in themes)
                    Padding(
                      padding: const EdgeInsets.only(right: AppSpacing.sm),
                      child: AstroChip(
                        label: b12(context, 'spread_theme_$t'),
                        selected: theme == t,
                        onTap: () => setState(() {
                          theme = t;
                          spread = null;
                        }),
                      ),
                    ),
                ],
              ),
            ),
            AppSpacing.gapMd,
            for (final s in visible)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.cardGap),
                child: _SpreadTile(
                  spread: s,
                  selected: spread?.code == s.code,
                  locked: !ref
                      .watch(entitlementServiceProvider)
                      .canUseSpread(widget.deck, s),
                  onTap: () => setState(() => spread = s),
                ),
              ),
          ],
        );
      },
    ),
    TextField(
      controller: question,
      maxLength: 500,
      minLines: 1,
      maxLines: 3,
      onChanged: (_) {
        if (_questionError) setState(() => _questionError = false);
      },
      decoration: InputDecoration(
        labelText: b12(
          context,
          spread?.isQuestionSpread ?? false ? 'question_required' : 'question',
        ),
        hintText: b12(context, 'question_hint'),
        errorText: _questionError ? b12(context, 'question_too_short') : null,
        prefixIcon: const Icon(Icons.help_outline),
      ),
    ),
    if (widget.deck == DeckType.rune)
      AstroCard(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
        child: CheckboxListTile(
          title: Text(b12(context, 'optional_rune')),
          value: optional,
          onChanged: (v) => setState(() => optional = v ?? false),
        ),
      ),
    _DrawButton(
      deck: widget.deck,
      spread: spread,
      locked:
          spread != null &&
          !ref
              .watch(entitlementServiceProvider)
              .canUseSpread(widget.deck, spread!),
      onDraw: () => _shuffle(repo),
      coinPrice: ref
          .watch(coinCatalogProvider)
          .asData
          ?.value
          ?.priceOf('advanced_spread'),
      onCoins: () => _shuffle(repo, payWithCoins: true),
    ),
    const _AllowanceNote(),
  ];

  Widget _history() => AstroCard(
    padding: EdgeInsets.zero,
    child: ExpansionTile(
      title: Text(b12(context, 'history'), style: AppTypography.titleMedium),
      children: [
        ApiStateView(
          value: ref.watch(readingsProvider),
          onRetry: () => ref.invalidate(readingsProvider),
          builder: (items) {
            final mine = items
                .where((i) => i.text('deck_type') == widget.deck.name)
                .toList();
            if (mine.isEmpty) {
              return Padding(
                padding: const EdgeInsets.all(AppSpacing.lg),
                child: Text(b12(context, 'empty')),
              );
            }
            return Column(
              children: [
                for (final item in mine)
                  ListTile(
                    leading: const Icon(
                      Icons.auto_awesome_outlined,
                      color: AppColors.gold,
                    ),
                    title: Text(item.text('spread_name')),
                    subtitle: Text(
                      [
                        _formatDate(
                          context,
                          DateTime.tryParse(item.text('drawn_at')),
                        ),
                        if (item.optionalText('question') case final String q
                            when q.isNotEmpty)
                          q,
                      ].join(' · '),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    onTap: () => context.push(
                      AppRoutes.reading(widget.deck.name, item.text('id')),
                    ),
                  ),
              ],
            );
          },
        ),
      ],
    ),
  );
}

String _formatDate(BuildContext context, DateTime? value) => value == null
    ? '—'
    : DateFormat.yMMMd(
        Localizations.localeOf(context).toLanguageTag(),
      ).add_Hm().format(value.toLocal());

class _DeckHero extends StatefulWidget {
  const _DeckHero({required this.deck, required this.shuffling});
  final DeckType deck;
  final bool shuffling;
  @override
  State<_DeckHero> createState() => _DeckHeroState();
}

class _DeckHeroState extends State<_DeckHero>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  );

  @override
  void didUpdateWidget(covariant _DeckHero oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.shuffling && !_controller.isAnimating) {
      _controller.repeat();
    } else if (!widget.shuffling) {
      _controller.stop();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  String get _shufflingKey =>
      widget.deck == DeckType.rune ? 'shuffling_runes' : 'shuffling';

  @override
  Widget build(BuildContext context) {
    final back = switch (widget.deck) {
      DeckType.tarot => AppAssets.tarotBack,
      DeckType.rune => AppAssets.runeBack,
      DeckType.katina => AppAssets.katinaBack,
    };
    return Semantics(
      liveRegion: widget.shuffling,
      label: widget.shuffling ? b12(context, _shufflingKey) : null,
      child: SizedBox(
        height: 260,
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            final t = _controller.value * 2 * math.pi;
            return Stack(
              alignment: Alignment.center,
              children: [
                for (var i = 2; i >= 0; i--)
                  Transform.translate(
                    offset: widget.shuffling
                        ? Offset(math.sin(t + i * 2.1) * 34, 0)
                        : Offset((i - 1) * 10.0, 0),
                    child: Transform.rotate(
                      angle: widget.shuffling
                          ? math.sin(t + i) * .12
                          : (i - 1) * .06,
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          borderRadius: AppRadius.brMd,
                          boxShadow: [
                            BoxShadow(
                              color: AppColors.gold.withValues(alpha: .12),
                              blurRadius: 40,
                            ),
                          ],
                        ),
                        child: AstroImage(back, width: 160, height: 240),
                      ),
                    ),
                  ),
                if (widget.shuffling)
                  Positioned(
                    bottom: 0,
                    child: Text(
                      b12(context, _shufflingKey),
                      style: AppTypography.labelLarge.copyWith(
                        color: AppColors.goldBright,
                      ),
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _SpreadTile extends StatelessWidget {
  const _SpreadTile({
    required this.spread,
    required this.selected,
    required this.locked,
    required this.onTap,
  });
  final DivinationSpread spread;
  final bool selected;
  final bool locked;
  final VoidCallback onTap;

  /// The position list only adds information when the name does not already
  /// spell it out ("Geçmiş - Şimdi - Gidişat").
  bool get _positionsRedundant {
    final name = spread.name.toLowerCase();
    return spread.positionTitles.every(
      (title) => name.contains(title.toLowerCase()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final positions = spread.records('positions');
    return AstroCard(
      onTap: onTap,
      semanticLabel:
          '${spread.name}, ${spread.cardCount} ${b12(context, 'cards_unit')}',
      borderColor: selected ? AppColors.gold : AppColors.hairline,
      gradient: selected
          ? LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                AppColors.gold.withValues(alpha: 0.14),
                AppColors.surface.withValues(alpha: 0.9),
              ],
            )
          : AppColors.cardGradient,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              // Card count in the UI sans: serif old-style "1" reads as "ı".
              Container(
                width: 52,
                height: 52,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: selected ? AppColors.gold : Colors.transparent,
                  border: Border.all(
                    color: selected ? AppColors.gold : AppColors.hairlineStrong,
                  ),
                ),
                padding: const EdgeInsets.all(AppSpacing.sm),
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        '${spread.cardCount}',
                        style: AppTypography.labelLarge.copyWith(
                          fontSize: 18,
                          height: 1,
                          fontWeight: FontWeight.w600,
                          color: selected
                              ? AppColors.onGold
                              : AppColors.goldBright,
                        ),
                      ),
                      Text(
                        b12(context, 'cards_unit'),
                        style: AppTypography.labelSmall.copyWith(
                          height: 1.1,
                          letterSpacing: 0.2,
                          color: selected
                              ? AppColors.onGold.withValues(alpha: 0.8)
                              : AppColors.ivoryMuted,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              AppSpacing.gapMd,
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(spread.name, style: AppTypography.titleMedium),
                    if (!_positionsRedundant && !selected) ...[
                      const SizedBox(height: AppSpacing.xxs),
                      Text(
                        spread.positionTitles.join(' · '),
                        style: AppTypography.bodySmall,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ],
                ),
              ),
              if (locked)
                AstroBadge(
                  label: b12(context, 'premium'),
                  icon: Icons.lock_outline,
                )
              else if (selected)
                const Icon(Icons.check_circle, color: AppColors.gold),
            ],
          ),
          // The chosen spread explains every position before the draw.
          if (selected && positions.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.md),
            const AstroGoldDivider(),
            const SizedBox(height: AppSpacing.sm),
            for (final (i, p) in positions.indexed)
              Padding(
                padding: const EdgeInsets.symmetric(
                  vertical: AppSpacing.xs + 2,
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: 28,
                      child: Text(
                        '${i + 1}.',
                        style: AppTypography.labelLarge.copyWith(
                          color: AppColors.gold,
                        ),
                      ),
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            p.text('title'),
                            style: AppTypography.labelLarge,
                          ),
                          if (p.optionalText('description') case final String d
                              when d.isNotEmpty)
                            Text(d, style: AppTypography.bodySmall),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ],
      ),
    );
  }
}

class _DrawButton extends StatelessWidget {
  const _DrawButton({
    required this.deck,
    required this.spread,
    required this.locked,
    required this.onDraw,
    this.coinPrice,
    this.onCoins,
  });
  final DeckType deck;
  final DivinationSpread? spread;
  final bool locked;
  final VoidCallback onDraw;

  /// Price of this spread in AstroCoins, when coins can open it.
  final int? coinPrice;
  final VoidCallback? onCoins;

  @override
  Widget build(BuildContext context) {
    if (locked) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          AstroOutlineButton(
            label: b12(context, 'unlock_premium'),
            onPressed: () => context.push(AppRoutes.premium),
          ),
          if (coinPrice != null && coinPrice! > 0 && onCoins != null) ...[
            const SizedBox(height: AppSpacing.sm),
            AstroButton(
              key: const ValueKey('spread-coins'),
              label: b12(
                context,
                'coin_open_spread',
              ).replaceAll('{price}', '$coinPrice'),
              icon: Icons.toll_outlined,
              onPressed: onCoins,
            ),
          ],
        ],
      );
    }
    return AstroButton(
      label: b12(
        context,
        deck == DeckType.rune ? 'shuffle_runes' : 'shuffle_cards',
      ),
      icon: Icons.auto_awesome,
      onPressed: spread == null ? null : onDraw,
    );
  }
}

/// "Bugün kalan: 2 / 3" under the shuffle button, when the plan limits it.
class _AllowanceNote extends ConsumerWidget {
  const _AllowanceNote();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final allowance = ref.watch(drawAllowanceProvider).asData?.value;
    if (allowance == null || !allowance.enforced) {
      return const SizedBox.shrink();
    }
    return Text(
      allowance.remaining > 0
          ? b12(context, 'draws_left')
                .replaceAll('{left}', '${allowance.remaining}')
                .replaceAll('{limit}', '${allowance.dailyLimit}')
          : b12(
              context,
              'draws_none_left',
            ).replaceAll('{price}', '${allowance.extraDrawPrice}'),
      key: const ValueKey('allowance-note'),
      textAlign: TextAlign.center,
      style: AppTypography.bodySmall,
    );
  }
}

class _ReadingView extends ConsumerWidget {
  const _ReadingView({
    required this.reading,
    required this.deepening,
    required this.onDeepen,
    this.interpreted = false,
    this.onNewReading,
    this.onChangeSpread,
  });
  final DivinationReading reading;
  final ActionState<Json> deepening;
  final VoidCallback onDeepen;

  /// Already has its AI interpretation: opening it again is free.
  final bool interpreted;
  final VoidCallback? onNewReading;
  final VoidCallback? onChangeSpread;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final resolver = ref.watch(_assetsProvider).asData?.value;
    final synthesis = reading.synthesis;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          reading.spreadName,
          textAlign: TextAlign.center,
          style: AppTypography.headlineLarge,
        ),
        Text(
          _formatDate(context, reading.drawnAt),
          textAlign: TextAlign.center,
          style: AppTypography.bodySmall,
        ),
        if (reading.question case final String q when q.isNotEmpty) ...[
          AppSpacing.gapMd,
          AstroCard(
            child: Row(
              children: [
                const Icon(Icons.format_quote, color: AppColors.gold),
                AppSpacing.gapSm,
                Expanded(
                  child: Text(
                    q,
                    style: AppTypography.bodyLarge.copyWith(
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
        AppSpacing.gapLg,
        for (final item in reading.items)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.lg),
            child: _DrawnCard(
              item: item,
              deck: DeckType.values.byName(reading.deckType),
              theme: reading.spreadTheme,
              asset: _faceOf(
                resolver,
                DeckType.values.byName(reading.deckType),
                item,
              ),
            ),
          ),
        if (synthesis != null)
          AstroCard(
            borderColor: AppColors.hairlineStrong,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  b12(context, 'combined_reading'),
                  style: AppTypography.headlineMedium,
                ),
                AppSpacing.gapSm,
                Text(synthesis.headline, style: AppTypography.bodyLarge),
                for (final line in synthesis.lines)
                  Padding(
                    padding: const EdgeInsets.only(top: AppSpacing.sm),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Padding(
                          padding: EdgeInsets.only(top: 3),
                          child: Icon(
                            Icons.auto_awesome,
                            size: 14,
                            color: AppColors.gold,
                          ),
                        ),
                        AppSpacing.gapSm,
                        Expanded(
                          child: Text(line, style: AppTypography.bodyMedium),
                        ),
                      ],
                    ),
                  ),
                if (synthesis.flow.length > 1) ...[
                  AppSpacing.gapMd,
                  const AstroGoldDivider(),
                  AppSpacing.gapMd,
                  for (final step in synthesis.flow)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                      child: Text('→ $step', style: AppTypography.bodySmall),
                    ),
                ],
              ],
            ),
          ),
        AppSpacing.gapLg,
        AstroButton(
          key: const ValueKey('deepen-button'),
          label:
              interpreted ||
                  ref
                      .watch(entitlementServiceProvider)
                      .canUse(PremiumFeature.advancedAi)
              ? b12(context, 'deepen_with_ai')
              : withCoinPrice(
                  context,
                  ref,
                  b12(context, 'deepen_with_ai'),
                  CoinItem.aiDeepReading,
                ),
          icon: Icons.auto_awesome,
          isLoading: deepening.busy,
          onPressed: deepening.busy ? null : onDeepen,
        ),
        if (deepening.value case final AsyncValue<Json> value
            when value.hasError)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.sm),
            child: ApiStateView(
              value: value,
              builder: (_) => const SizedBox.shrink(),
            ),
          ),
        Padding(
          padding: const EdgeInsets.only(top: AppSpacing.sm),
          child: Text(
            b12(context, 'deepen_note'),
            textAlign: TextAlign.center,
            style: AppTypography.bodySmall,
          ),
        ),
        if (onNewReading != null) ...[
          AppSpacing.gapMd,
          AstroOutlineButton(
            label: b12(context, 'new_reading'),
            icon: Icons.refresh,
            onPressed: onNewReading,
          ),
        ],
        if (onChangeSpread != null) ...[
          AppSpacing.gapSm,
          TextButton(
            onPressed: onChangeSpread,
            child: Text(b12(context, 'change_spread')),
          ),
        ],
      ],
    );
  }
}

class _DrawnCard extends StatelessWidget {
  const _DrawnCard({
    required this.item,
    required this.deck,
    required this.theme,
    required this.asset,
  });
  final DrawnItem item;
  final DeckType deck;
  final String theme;
  final String? asset;

  @override
  Widget build(BuildContext context) {
    final contextual = item.contextualMeaning;
    final showContextual =
        theme != 'general' &&
        contextual.isNotEmpty &&
        contextual != item.meaning;
    return AstroCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  item.position,
                  style: AppTypography.overline.copyWith(color: AppColors.gold),
                ),
              ),
              AstroBadge(
                label: b12(context, item.reversed ? 'reversed' : 'upright'),
                icon: item.reversed ? Icons.south : Icons.north,
              ),
            ],
          ),
          if (item.positionDescription.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.xs),
              child: Text(
                item.positionDescription,
                style: AppTypography.bodySmall,
              ),
            ),
          AppSpacing.gapMd,
          if (asset != null || deck == DeckType.rune)
            Center(
              child: RevealedArt(
                deck: deck,
                asset: asset,
                reversed: item.reversed,
                semanticLabel: item.name,
              ),
            ),
          AppSpacing.gapMd,
          Text(
            item.name,
            textAlign: TextAlign.center,
            style: AppTypography.headlineMedium,
          ),
          if (item.keywords.isNotEmpty) ...[
            AppSpacing.gapSm,
            Wrap(
              alignment: WrapAlignment.center,
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children: [
                for (final keyword in item.keywords.take(5))
                  AstroBadge(label: keyword),
              ],
            ),
          ],
          AppSpacing.gapMd,
          _Labeled(label: b12(context, 'card_meaning'), text: item.meaning),
          if (showContextual)
            _Labeled(
              label: b12(context, 'spread_meaning_$theme'),
              text: contextual,
            ),
          if (item.shadowMeaning.isNotEmpty)
            _Labeled(
              label: b12(context, 'shadow_side'),
              text: item.shadowMeaning,
            ),
          if (item.symbolism.isNotEmpty)
            _Labeled(label: b12(context, 'symbolism'), text: item.symbolism),
        ],
      ),
    );
  }
}

class _Labeled extends StatelessWidget {
  const _Labeled({required this.label, required this.text});
  final String label;
  final String text;
  @override
  Widget build(BuildContext context) => text.isEmpty
      ? const SizedBox.shrink()
      : Padding(
          padding: const EdgeInsets.only(bottom: AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: AppTypography.labelMedium.copyWith(
                  color: AppColors.goldBright,
                ),
              ),
              const SizedBox(height: AppSpacing.xxs),
              Text(text, style: AppTypography.bodyMedium),
            ],
          ),
        );
}
