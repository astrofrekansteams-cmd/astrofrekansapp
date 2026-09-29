import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../core/assets/app_assets.dart';
import '../../../core/astrology/data/production_models.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/widgets.dart';

/// The user's picks from a face-down deck, in pick order.
///
/// Client state until the reveal: the i-th pick fills the spread's i-th
/// position, so the order is never sorted. Once the reveal starts the
/// selection is locked and cannot change.
class DivinationSelection extends ChangeNotifier {
  DivinationSelection({
    required this.required,
    required this.deckSize,
    List<int> initial = const [],
    bool locked = false,
  }) {
    // A restored draft: keep valid, distinct picks in their original order.
    for (final slot in initial) {
      if (_picks.length >= required) break;
      if (slot >= 0 && slot < deckSize && !_picks.contains(slot)) {
        _picks.add(slot);
      }
    }
    _locked = locked;
  }

  final int required;
  final int deckSize;
  final List<int> _picks = [];
  bool _locked = false;

  List<int> get picks => List.unmodifiable(_picks);
  int get count => _picks.length;
  bool get isComplete => _picks.length == required;
  bool get locked => _locked;

  bool isSelected(int slot) => _picks.contains(slot);

  /// 1-based pick number of [slot], or null when it is not picked.
  int? orderOf(int slot) {
    final index = _picks.indexOf(slot);
    return index < 0 ? null : index + 1;
  }

  /// Picks or unpicks [slot]. Returns whether anything changed: a full
  /// selection ignores new slots, a locked one ignores everything.
  bool toggle(int slot) {
    if (_locked || slot < 0 || slot >= deckSize) return false;
    if (_picks.remove(slot)) {
      notifyListeners();
      return true;
    }
    if (_picks.length >= required) return false;
    _picks.add(slot);
    notifyListeners();
    return true;
  }

  /// Called when the reveal starts (or the session expired); the picks are
  /// final from here on.
  void lock() {
    if (_locked) return;
    _locked = true;
    notifyListeners();
  }
}

/// A fresh idempotency reference for one shuffle press.
String newConsumerRef() {
  final random = math.Random.secure();
  final hex = List.generate(
    24,
    (_) => random.nextInt(16).toRadixString(16),
  ).join();
  return 'shuffle-$hex';
}

String _fill(String template, Map<String, Object> values) {
  var out = template;
  values.forEach((k, v) => out = out.replaceAll('{$k}', '$v'));
  return out;
}

String _face(DeckType deck) => deck == DeckType.rune ? 'runes' : 'cards';

// ----------------------------------------------------------------- sizes

/// Every size an asset is shown at in this flow. Precaching must use the
/// same sizes as the widgets, because decodes are cached per size.
abstract final class DivinationSizes {
  static const fanCard = Size(58, 90);
  static const stone = Size(46, 69);

  /// Rune art is a standing stone on a 2:3 transparent canvas.
  static const readingStone = Size(150, 225);
  static const readingCard = Size(170, 255);

  /// Faces decode once, at the reading's size; the reveal shows that decode
  /// smaller. The face-down art in the reveal decodes at [revealBackDecode].
  static double faceDecode(DeckType deck) =>
      deck == DeckType.rune ? readingStone.width : readingCard.width;
  static const revealBackDecode = 88.0;

  static Size revealItem(DeckType deck, int count) {
    if (deck == DeckType.rune) return const Size(72, 108);
    final width = count > 5 ? 64.0 : 88.0;
    return Size(width, width * 1.55);
  }

  static String faceDownAsset(DeckType deck) => switch (deck) {
    DeckType.tarot => AppAssets.tarotBack,
    DeckType.katina => AppAssets.katinaBack,
    DeckType.rune => AppAssets.runeStoneBack,
  };
}

/// Decodes the face-down art and every revealed face at the sizes the reveal
/// and the reading will paint them, so neither shows an empty frame.
/// Bounded: a slow decode delays the reveal by at most [limit].
Future<void> precacheReveal(
  BuildContext context,
  DeckType deck,
  DivinationReading reading,
  String? Function(DrawnItem item) faceOf, {
  Duration limit = const Duration(milliseconds: 2500),
}) {
  final face = DivinationSizes.faceDecode(deck);
  final jobs = <Future<void>>[
    precacheDeck(context, deck),
    // A rune without stone art (the blank Odin rune) shows the plain stone.
    if (deck == DeckType.rune)
      AstroImage.precache(context, AppAssets.runeStoneBack, width: face),
    for (final item in reading.items)
      if (faceOf(item) case final String asset)
        AstroImage.precache(context, asset, width: face),
  ];
  return Future.wait(jobs).timeout(limit, onTimeout: () => const []);
}

/// Face-down art for the picker, decoded before the deck is shown.
Future<void> precacheDeck(BuildContext context, DeckType deck) {
  final size = deck == DeckType.rune
      ? DivinationSizes.stone
      : DivinationSizes.fanCard;
  final back = DivinationSizes.faceDownAsset(deck);
  return Future.wait([
    AstroImage.precache(context, back, width: size.width),
    AstroImage.precache(context, back, width: DivinationSizes.revealBackDecode),
  ]);
}

// ------------------------------------------------------------------ deck

/// Face-down slots 0..deckSize-1. Knows nothing about what lies beneath.
class HiddenDeck extends StatelessWidget {
  const HiddenDeck({super.key, required this.deck, required this.selection});

  final DeckType deck;
  final DivinationSelection selection;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: selection,
    builder: (context, _) => deck == DeckType.rune
        ? _RuneBag(selection: selection)
        : _CardFan(deck: deck, selection: selection),
  );
}

const _lift = 16.0;

/// Room above a lifted card for its order badge, inside the scroll view's
/// clip so the badge is never cut.
const _badgeRoom = 14.0;

/// Tarot and Katina: two overlapping rows that scroll sideways.
class _CardFan extends StatefulWidget {
  const _CardFan({required this.deck, required this.selection});
  final DeckType deck;
  final DivinationSelection selection;

  @override
  State<_CardFan> createState() => _CardFanState();
}

class _CardFanState extends State<_CardFan> {
  static const _step = 36.0;
  static const _fade = 28.0;
  final _scroll = ScrollController();
  bool _moreLeft = false;
  bool _moreRight = true;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) => _onScroll());
  }

  void _onScroll() {
    if (!mounted || !_scroll.hasClients) return;
    final p = _scroll.position;
    final left = p.pixels > 1;
    final right = p.pixels < p.maxScrollExtent - 1;
    if (left != _moreLeft || right != _moreRight) {
      setState(() {
        _moreLeft = left;
        _moreRight = right;
      });
    }
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final selection = widget.selection;
    const card = DivinationSizes.fanCard;
    final back = DivinationSizes.faceDownAsset(widget.deck);
    final size = selection.deckSize;
    final perRow = (size / 2).ceil();
    final rows = [
      for (var start = 0; start < size; start += perRow)
        [for (var i = start; i < math.min(start + perRow, size); i++) i],
    ];
    Widget row(List<int> slots) {
      // Picked cards paint (and take taps) above their neighbours; the
      // others keep deck order. Keys keep each slot's state when reordered.
      final ordered = [
        ...slots.where((s) => !selection.isSelected(s)),
        ...slots.where(selection.isSelected),
      ];
      return SizedBox(
        width: (slots.length - 1) * _step + card.width,
        height: _badgeRoom + _lift + card.height + AppSpacing.sm,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            for (final slot in ordered)
              Positioned(
                key: ValueKey('fan-$slot'),
                left: (slot - slots.first) * _step,
                top: _badgeRoom + _lift,
                child: _Slot(
                  slot: slot,
                  selection: selection,
                  deck: widget.deck,
                  child: _CardBack(
                    asset: back,
                    selected: selection.isSelected(slot),
                  ),
                ),
              ),
          ],
        ),
      );
    }

    final fan = SingleChildScrollView(
      controller: _scroll,
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [for (final r in rows) row(r)],
      ),
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Soft edge fade where more cards are hidden: a scroll cue that
        // adds nothing to the layout.
        ShaderMask(
          key: const ValueKey('fan-fade'),
          blendMode: BlendMode.dstIn,
          shaderCallback: (bounds) {
            final f = (_fade / bounds.width).clamp(0.0, 0.5);
            return LinearGradient(
              colors: [
                _moreLeft ? Colors.transparent : Colors.white,
                Colors.white,
                Colors.white,
                _moreRight ? Colors.transparent : Colors.white,
              ],
              stops: [0, f, 1 - f, 1],
            ).createShader(bounds);
          },
          child: fan,
        ),
        if (_moreLeft || _moreRight)
          ExcludeSemantics(
            child: Row(
              key: const ValueKey('scroll-hint'),
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  Icons.swipe_outlined,
                  size: 14,
                  color: AppColors.ivoryMuted.withValues(alpha: .8),
                ),
                const SizedBox(width: AppSpacing.xs),
                Flexible(
                  child: Text(
                    _fill(b12(context, 'scroll_hint'), {'n': size}),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTypography.labelSmall.copyWith(
                      color: AppColors.ivoryMuted.withValues(alpha: .8),
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

class _CardBack extends StatelessWidget {
  const _CardBack({required this.asset, required this.selected});
  final String asset;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    const card = DivinationSizes.fanCard;
    return AnimatedContainer(
      duration: context.reduceMotion
          ? Duration.zero
          : const Duration(milliseconds: 220),
      width: card.width,
      height: card.height,
      decoration: BoxDecoration(
        borderRadius: AppRadius.brSm,
        border: Border.all(
          color: selected ? AppColors.goldBright : AppColors.hairline,
          width: selected ? 2 : 1,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: .45),
            blurRadius: 8,
            offset: const Offset(-2, 2),
          ),
          if (selected)
            BoxShadow(
              color: AppColors.gold.withValues(alpha: .45),
              blurRadius: 18,
            ),
        ],
      ),
      child: ClipRRect(
        borderRadius: AppRadius.brSm,
        child: AstroImage(
          asset,
          width: card.width,
          height: card.height,
          fit: BoxFit.cover,
        ),
      ),
    );
  }
}

/// Rune: standing stones in a bag, symbols hidden. The stone art is a
/// transparent cut-out, so it is drawn whole - never clipped to a shape.
class _RuneBag extends StatelessWidget {
  const _RuneBag({required this.selection});
  final DivinationSelection selection;

  @override
  Widget build(BuildContext context) {
    const stone = DivinationSizes.stone;
    return Padding(
      padding: const EdgeInsets.only(top: _badgeRoom),
      child: Wrap(
        alignment: WrapAlignment.center,
        spacing: AppSpacing.sm,
        runSpacing: AppSpacing.sm,
        children: [
          for (var slot = 0; slot < selection.deckSize; slot++)
            _Slot(
              slot: slot,
              selection: selection,
              deck: DeckType.rune,
              child: _Stone(
                asset: AppAssets.runeStoneBack,
                size: stone,
                selected: selection.isSelected(slot),
              ),
            ),
        ],
      ),
    );
  }
}

/// A rune stone with a soft gold halo when chosen (no frame, no clip).
class _Stone extends StatelessWidget {
  const _Stone({
    required this.asset,
    required this.size,
    this.selected = false,
    this.scale = 1,
    this.decodeWidth,
  });
  final String asset;
  final Size size;
  final bool selected;

  /// Face art sits smaller on its canvas than the back; scale evens them.
  final double scale;

  /// See [AstroImage.decodeWidth].
  final double? decodeWidth;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: size.width,
    height: size.height,
    child: Stack(
      alignment: Alignment.center,
      clipBehavior: Clip.none,
      children: [
        AnimatedOpacity(
          opacity: selected ? 1 : 0,
          duration: context.reduceMotion
              ? Duration.zero
              : const Duration(milliseconds: 220),
          child: Container(
            width: size.width * 1.02,
            height: size.height * 0.98,
            decoration: BoxDecoration(
              shape: BoxShape.rectangle,
              borderRadius: BorderRadius.all(
                Radius.elliptical(size.width * .55, size.height * .5),
              ),
              border: Border.all(color: AppColors.goldBright, width: 2),
              boxShadow: [
                BoxShadow(
                  color: AppColors.gold.withValues(alpha: .5),
                  blurRadius: 18,
                ),
              ],
            ),
          ),
        ),
        Transform.scale(
          scale: scale,
          child: AstroImage(
            asset,
            width: size.width,
            height: size.height,
            decodeWidth: decodeWidth,
            fit: BoxFit.contain,
          ),
        ),
      ],
    ),
  );
}

/// One face-down slot: tap target, lift, order badge, semantics.
class _Slot extends StatelessWidget {
  const _Slot({
    required this.slot,
    required this.selection,
    required this.deck,
    required this.child,
  });
  final int slot;
  final DivinationSelection selection;
  final DeckType deck;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final order = selection.orderOf(slot);
    final selected = order != null;
    final enabled = !selection.locked && (selected || !selection.isComplete);
    final label = _fill(b12(context, 'face_down_${_face(deck)}'), {
      'n': slot + 1,
    });
    return Semantics(
      button: true,
      selected: selected,
      enabled: enabled,
      label: selected
          ? '$label, ${_fill(b12(context, 'picked_as'), {'n': order})}'
          : label,
      excludeSemantics: true,
      child: GestureDetector(
        key: ValueKey('slot-$slot'),
        behavior: HitTestBehavior.opaque,
        onTap: enabled ? () => selection.toggle(slot) : null,
        child: TweenAnimationBuilder<double>(
          tween: Tween(end: selected ? -_lift : 0),
          duration: context.reduceMotion
              ? Duration.zero
              : const Duration(milliseconds: 220),
          curve: Curves.easeOutCubic,
          builder: (context, dy, child) =>
              Transform.translate(offset: Offset(0, dy), child: child),
          child: Stack(
            clipBehavior: Clip.none,
            children: [
              Opacity(opacity: enabled || selected ? 1 : .55, child: child),
              if (order != null)
                Positioned(
                  top: -10,
                  right: -6,
                  child: _OrderBadge(order: order),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _OrderBadge extends StatelessWidget {
  const _OrderBadge({required this.order});
  final int order;

  @override
  Widget build(BuildContext context) => Container(
    key: ValueKey('order-$order'),
    width: 24,
    height: 24,
    alignment: Alignment.center,
    decoration: const BoxDecoration(
      shape: BoxShape.circle,
      color: AppColors.gold,
      boxShadow: [BoxShadow(color: AppColors.glow, blurRadius: 8)],
    ),
    child: Text(
      '$order',
      style: AppTypography.labelMedium.copyWith(
        color: AppColors.onGold,
        fontWeight: FontWeight.w700,
        height: 1,
      ),
    ),
  );
}

// -------------------------------------------------------------- progress

/// "2 / 3 kart seçildi", the positions with ✓ / waiting, and the reveal CTA.
///
/// Semantics: the progress line is its own live region, each position is one
/// node, and the CTA is a real button with an enabled state.
class SelectionPanel extends StatefulWidget {
  const SelectionPanel({
    super.key,
    required this.deck,
    required this.session,
    required this.selection,
    required this.revealing,
    required this.onReveal,
    this.expired = false,
  });

  final DeckType deck;
  final DrawSession session;
  final DivinationSelection selection;
  final bool revealing;
  final VoidCallback onReveal;

  /// The session can no longer be revealed: the CTA stays disabled.
  final bool expired;

  @override
  State<SelectionPanel> createState() => _SelectionPanelState();
}

class _SelectionPanelState extends State<SelectionPanel> {
  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.selection,
    builder: (context, _) {
      final selection = widget.selection;
      final face = _face(widget.deck);
      final positions = widget.session.positions;
      final count = _fill(b12(context, 'selected_count_$face'), {
        'x': selection.count,
        'n': selection.required,
      });
      final status = selection.isComplete
          ? b12(context, 'selection_complete')
          : count;
      final canReveal =
          selection.isComplete && !widget.revealing && !widget.expired;
      return AstroCard(
        borderColor: selection.isComplete
            ? AppColors.hairlineStrong
            : AppColors.hairline,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Semantics(
              key: const ValueKey('selection-progress'),
              container: true,
              liveRegion: true,
              label: selection.isComplete ? '$status, $count' : status,
              excludeSemantics: true,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    status,
                    key: const ValueKey('selection-status'),
                    style: AppTypography.titleMedium.copyWith(
                      color: selection.isComplete
                          ? AppColors.goldBright
                          : AppColors.ivory,
                    ),
                  ),
                  if (selection.isComplete)
                    Text(count, style: AppTypography.bodySmall),
                ],
              ),
            ),
            AppSpacing.gapSm,
            for (final (i, (title, _)) in positions.indexed)
              Semantics(
                container: true,
                label:
                    '${i + 1}. $title, ${b12(context, i < selection.count ? 'position_picked' : 'selection_waiting')}',
                excludeSemantics: true,
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.xxs),
                  child: Row(
                    key: ValueKey('position-$i'),
                    children: [
                      Expanded(
                        child: Text.rich(
                          TextSpan(
                            children: [
                              TextSpan(
                                text: '${i + 1}. ',
                                style: AppTypography.labelLarge.copyWith(
                                  color: AppColors.gold,
                                ),
                              ),
                              TextSpan(
                                text: title,
                                style: AppTypography.labelLarge,
                              ),
                              if (i >= selection.count)
                                TextSpan(
                                  text:
                                      ' — ${b12(context, 'selection_waiting')}',
                                  style: AppTypography.bodySmall,
                                ),
                            ],
                          ),
                        ),
                      ),
                      if (i < selection.count)
                        const Icon(
                          Icons.check,
                          size: 18,
                          color: AppColors.gold,
                        ),
                    ],
                  ),
                ),
              ),
            AppSpacing.gapMd,
            AstroButton(
              key: const ValueKey('reveal-button'),
              label: b12(context, 'reveal_$face'),
              icon: Icons.flip_outlined,
              isLoading: widget.revealing,
              onPressed: canReveal ? widget.onReveal : null,
            ),
          ],
        ),
      );
    },
  );
}

// ---------------------------------------------------------------- reveal

/// Turns the picks face up one by one, in position order (1 → 2 → 3).
/// A soft flip and fade; instant with reduced motion. Its images are
/// precached (see [precacheReveal]) before it is shown.
class RevealSequence extends StatefulWidget {
  const RevealSequence({
    super.key,
    required this.deck,
    required this.reading,
    required this.faceOf,
    required this.onDone,
  });

  final DeckType deck;
  final DivinationReading reading;

  /// Face asset for an item, or null when the artwork is missing.
  final String? Function(DrawnItem item) faceOf;
  final VoidCallback onDone;

  @override
  State<RevealSequence> createState() => _RevealSequenceState();
}

class _RevealSequenceState extends State<RevealSequence>
    with SingleTickerProviderStateMixin {
  static const _perItem = Duration(milliseconds: 650);
  late final int _count = widget.reading.items.length;
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: _perItem * _count + const Duration(milliseconds: 500),
  );
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    if (context.reduceMotion) {
      _controller.value = 1;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) widget.onDone();
      });
    } else {
      _controller.forward().whenComplete(() {
        if (mounted) widget.onDone();
      });
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  /// 0 → 1 flip progress of item [i].
  double _progress(int i) {
    final total = _controller.duration!.inMilliseconds;
    final start = _perItem.inMilliseconds * i / total;
    final end = start + _perItem.inMilliseconds / total;
    return Curves.easeInOutCubic.transform(
      ((_controller.value - start) / (end - start)).clamp(0.0, 1.0),
    );
  }

  @override
  Widget build(BuildContext context) {
    final items = widget.reading.items;
    final size = DivinationSizes.revealItem(widget.deck, items.length);
    return Semantics(
      liveRegion: true,
      label: b12(context, 'revealing'),
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) => Wrap(
          alignment: WrapAlignment.center,
          spacing: AppSpacing.md,
          runSpacing: AppSpacing.md,
          children: [
            for (final (i, item) in items.indexed)
              SizedBox(
                width: size.width + AppSpacing.sm,
                child: Column(
                  children: [
                    _Flip(
                      deck: widget.deck,
                      progress: _progress(i),
                      face: widget.faceOf(item),
                      reversed: item.reversed,
                      size: size,
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Opacity(
                      opacity: _progress(i),
                      child: Text(
                        '${i + 1}. ${item.position}',
                        textAlign: TextAlign.center,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: AppTypography.labelSmall.copyWith(
                          color: AppColors.gold,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _Flip extends StatelessWidget {
  const _Flip({
    required this.deck,
    required this.progress,
    required this.face,
    required this.reversed,
    required this.size,
  });
  final DeckType deck;
  final double progress;
  final String? face;
  final bool reversed;
  final Size size;

  @override
  Widget build(BuildContext context) {
    final showFace = progress >= .5;
    // Horizontal squash to the edge and back: a soft turn, no spin.
    final scaleX = (math.cos(progress * math.pi)).abs().clamp(0.02, 1.0);
    final back = DivinationSizes.faceDownAsset(deck);
    final Widget visual;
    if (deck == DeckType.rune) {
      // A stone turning over: no frame, the symbol on the stone's face.
      visual = RotatedBox(
        quarterTurns: showFace && reversed ? 2 : 0,
        child: _Stone(
          asset: showFace ? (face ?? back) : back,
          size: size,
          decodeWidth: showFace && face != null
              ? DivinationSizes.faceDecode(deck)
              : DivinationSizes.revealBackDecode,
          scale: showFace && face != null ? 1.15 : 1,
          selected: !showFace,
        ),
      );
    } else {
      visual = Container(
        width: size.width,
        height: size.height,
        decoration: BoxDecoration(
          borderRadius: AppRadius.brSm,
          border: Border.all(
            color: showFace ? AppColors.hairlineStrong : AppColors.goldBright,
            width: showFace ? 1 : 2,
          ),
          boxShadow: [
            BoxShadow(
              color: AppColors.gold.withValues(alpha: .18 * progress),
              blurRadius: 24,
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: AppRadius.brSm,
          child: showFace && face != null
              ? RotatedBox(
                  quarterTurns: reversed ? 2 : 0,
                  child: AstroImage(
                    face!,
                    width: size.width,
                    height: size.height,
                    decodeWidth: DivinationSizes.faceDecode(deck),
                    fit: BoxFit.cover,
                  ),
                )
              : AstroImage(
                  back,
                  width: size.width,
                  height: size.height,
                  decodeWidth: DivinationSizes.revealBackDecode,
                  fit: BoxFit.cover,
                ),
        ),
      );
    }
    return Transform(
      alignment: Alignment.center,
      transform: Matrix4.diagonal3Values(scaleX, 1, 1),
      child: visual,
    );
  }
}

/// The revealed item in the reading: a stone for runes, a card otherwise.
class RevealedArt extends StatelessWidget {
  const RevealedArt({
    super.key,
    required this.deck,
    required this.asset,
    required this.reversed,
    this.semanticLabel,
  });

  final DeckType deck;
  final String? asset;
  final bool reversed;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    if (deck == DeckType.rune) {
      const size = DivinationSizes.readingStone;
      return Semantics(
        image: true,
        label: semanticLabel,
        child: RotatedBox(
          quarterTurns: reversed ? 2 : 0,
          child: _Stone(
            asset: asset ?? AppAssets.runeStoneBack,
            size: size,
            scale: asset == null ? 1 : 1.15,
          ),
        ),
      );
    }
    if (asset == null) return const SizedBox.shrink();
    const size = DivinationSizes.readingCard;
    return RotatedBox(
      quarterTurns: reversed ? 2 : 0,
      child: AstroImage(
        asset!,
        width: size.width,
        height: size.height,
        fit: BoxFit.contain,
        semanticLabel: semanticLabel,
      ),
    );
  }
}
