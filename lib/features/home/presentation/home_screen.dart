import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/assets/app_assets.dart';
import '../../../core/astrology/domain/daily_frequency.dart';
import '../../../core/astrology/domain/moon_phase.dart';
import '../../../core/astrology/domain/transit.dart';
import '../../../core/astrology/domain/zodiac_sign.dart';
import '../../../core/astrology/astrology_providers.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/localization/astro_labels.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/localization/locale_controller.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/utils/text_case.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../astro_ai/application/astro_ai_controller.dart';
import '../../auth/application/session_controller.dart';
import '../../notifications/data/notification_repository.dart';
import '../../profile/domain/user_profile.dart';
import '../application/home_providers.dart';
import 'widgets/frequency_card.dart';
import 'widgets/transit_card.dart';

/// "Bugünün Frekansı" - the personalised daily entry point.
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final TextEditingController _quickAsk = TextEditingController();

  @override
  void dispose() {
    _quickAsk.dispose();
    super.dispose();
  }

  void _ask(String text) {
    final String question = text.trim();
    if (question.isEmpty) return;
    _quickAsk.clear();
    FocusScope.of(context).unfocus();
    ref.read(astroAIControllerProvider.notifier).send(question);
    context.go(AppRoutes.astroAi);
  }

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;
    final UserProfile? user = ref.watch(currentUserProvider);
    final AsyncValue<DailyFrequency> frequency = ref.watch(
      dailyFrequencyProvider,
    );

    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(dailyFrequencyProvider),
      color: AppColors.gold,
      backgroundColor: AppColors.surface,
      child: ListView(
        // Bottom padding keeps the last card and the footer clear of the
        // navigation bar when scrolled to the end.
        padding: EdgeInsets.fromLTRB(
          context.gutter,
          AppSpacing.sm,
          context.gutter,
          AppSpacing.sectionGap + AppSpacing.huge,
        ),
        children: <Widget>[
          AstroReveal(child: _Header(user: user)),
          const SizedBox(height: AppSpacing.lg),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final action in [
                ('home_draw_action', Icons.style_outlined, AppRoutes.tarot),
                (
                  'home_forecast_action',
                  Icons.today_outlined,
                  '${AppRoutes.forecasts}?period=daily',
                ),
                (
                  'home_expert_action',
                  Icons.support_agent,
                  AppRoutes.marketplace,
                ),
              ])
                ActionChip(
                  label: Text(b12(context, action.$1)),
                  avatar: Icon(action.$2, size: 18),
                  onPressed: () => context.push(action.$3),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          frequency.when(
            loading: () => const _HomeSkeleton(),
            error: (Object error, StackTrace stack) => AstroEmptyState(
              kind: AstroEmptyStateKind.noData,
              title: l10n.emptyNoData,
              message: l10n.errorGeneric,
              actionLabel: l10n.commonRetry,
              onAction: () => ref.invalidate(dailyFrequencyProvider),
            ),
            data: (DailyFrequency data) => Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                AstroReveal(
                  order: 1,
                  child: FrequencyCard(
                    frequency: data,
                    onDetails: () => context.go(AppRoutes.sky),
                  ),
                ),
                const SizedBox(height: AppSpacing.sectionGap),
                AstroSectionTitle(
                  title: l10n.homeTodayAffecting,
                  actionLabel: l10n.commonSeeAll,
                  onAction: () => context.push(AppRoutes.transits),
                ),
                const SizedBox(height: AppSpacing.md),
                AstroReveal(
                  order: 2,
                  child: _TransitRow(transits: data.transits),
                ),
                const SizedBox(height: AppSpacing.sectionGap),
                AstroReveal(
                  order: 3,
                  child: _QuickAskCard(
                    controller: _quickAsk,
                    prompts: data.suggestedPrompts,
                    onAsk: _ask,
                  ),
                ),
                const SizedBox(height: AppSpacing.cardGap),
                AstroReveal(
                  order: 4,
                  child: _CalendarAndGuidance(moon: data.moon),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.sectionGap),
          AstroBrandFooter(motto: l10n.brandMotto),
        ],
      ),
    );
  }
}

class _Header extends ConsumerWidget {
  const _Header({required this.user});

  final UserProfile? user;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppLocalizations l10n = context.l10n;
    final DateTime today = ref.watch(todayProvider);

    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: <Widget>[
        AstroAvatar(
          size: 56,
          initials: user?.initials,
          semanticLabel: user?.name,
        ),
        const SizedBox(width: AppSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Text(l10n.homeGreeting, style: AppTypography.bodyMedium),
              Text(
                user?.firstName ?? l10n.appName,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTypography.displayMedium.copyWith(fontSize: 26),
              ),
              _HeaderDate(date: today),
            ],
          ),
        ),
        const _NotificationBell(),
        const SizedBox(width: AppSpacing.xs),
        const _LanguageButton(),
      ],
    );
  }
}

/// One-line date: the longest format that fits the column wins, so narrow
/// phones get "26 EYL 2026, CMT" instead of a wrapped line. Never below the
/// 12 px floor; ellipsis only as a last resort.
class _HeaderDate extends StatelessWidget {
  const _HeaderDate({required this.date});

  final DateTime date;

  static const List<String> _patterns = <String>[
    'd MMMM y, EEEE',
    'd MMMM, EEEE',
    'd MMM y, EEE',
    'd MMM, EEE',
  ];

  @override
  Widget build(BuildContext context) {
    final String language = context.languageCode;
    final TextStyle style = AppTypography.labelSmall.copyWith(
      color: AppColors.ivoryMuted,
    );
    final TextScaler scaler = MediaQuery.textScalerOf(context);
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        String pick = '';
        for (final String pattern in _patterns) {
          pick = DateFormat(
            pattern,
            language,
          ).format(date).toUpperCaseFor(language);
          final TextPainter painter = TextPainter(
            text: TextSpan(text: pick, style: style),
            textDirection: Directionality.of(context),
            textScaler: scaler,
            maxLines: 1,
          )..layout();
          if (painter.width <= constraints.maxWidth) break;
        }
        return Text(
          pick,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          semanticsLabel: DateFormat.yMMMMEEEEd(language).format(date),
          style: style,
        );
      },
    );
  }
}

class _LanguageButton extends ConsumerWidget {
  const _LanguageButton();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final Locale locale = ref.watch(localeControllerProvider);
    final AppLocalizations l10n = context.l10n;

    return Semantics(
      button: true,
      label: l10n.homeLanguage,
      child: Material(
        color: AppColors.surface.withValues(alpha: 0.55),
        shape: const StadiumBorder(
          side: BorderSide(color: AppColors.hairlineStrong),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () async {
            final Locale? selected = await showModalBottomSheet<Locale>(
              context: context,
              builder: (BuildContext context) => SafeArea(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    ListTile(
                      title: Text(l10n.languageTurkish),
                      trailing: locale.languageCode == 'tr'
                          ? const Icon(Icons.check, color: AppColors.gold)
                          : null,
                      onTap: () =>
                          Navigator.of(context).pop(AppLocales.turkish),
                    ),
                    ListTile(
                      title: Text(l10n.languageEnglish),
                      trailing: locale.languageCode == 'en'
                          ? const Icon(Icons.check, color: AppColors.gold)
                          : null,
                      onTap: () =>
                          Navigator.of(context).pop(AppLocales.english),
                    ),
                  ],
                ),
              ),
            );
            if (selected != null) {
              // App and account language move together.
              try {
                await ref.read(sessionProvider.notifier).setLanguage(selected);
              } on Object catch (error) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(friendlyApiError(context, error))),
                  );
                }
              }
            }
          },
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: AppSpacing.md,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Text(
                  locale.languageCode.toUpperCase(),
                  style: AppTypography.labelMedium.copyWith(
                    color: AppColors.ivory,
                  ),
                ),
                const Icon(
                  Icons.keyboard_arrow_down,
                  size: 18,
                  color: AppColors.ivoryMuted,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _TransitRow extends StatelessWidget {
  const _TransitRow({required this.transits});

  final List<TransitSummary> transits;

  @override
  Widget build(BuildContext context) {
    if (transits.isEmpty) {
      return AstroCard(
        child: Text(context.l10n.emptyNoData, style: AppTypography.bodyMedium),
      );
    }

    final double cardWidth = (MediaQuery.sizeOf(context).width * 0.56).clamp(
      180.0,
      240.0,
    );

    // IntrinsicHeight keeps every card as tall as the tallest one without
    // hardcoding a height that large text scales would overflow.
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      clipBehavior: Clip.none,
      child: Row(
        // Natural height per card: no forced equal heights.
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          for (final TransitSummary transit in transits)
            Padding(
              padding: const EdgeInsets.only(right: AppSpacing.md),
              child: SizedBox(
                width: cardWidth,
                child: TransitCard(
                  summary: transit,
                  onTap: () => context.push(AppRoutes.transits),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _QuickAskCard extends StatelessWidget {
  const _QuickAskCard({
    required this.controller,
    required this.prompts,
    required this.onAsk,
  });

  final TextEditingController controller;
  final List<String> prompts;
  final ValueChanged<String> onAsk;

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;

    return AstroCard(
      child: Stack(
        children: <Widget>[
          const PositionedDirectional(
            end: -18,
            top: -10,
            child: IgnorePointer(
              child: AstroImage(
                AppAssets.astroAiAvatar,
                width: 104,
                height: 104,
                opacity: 0.35,
              ),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  const AstroImage(
                    AppAssets.premiumStar,
                    width: 26,
                    height: 26,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      l10n.homeAskAstroAi,
                      style: AppTypography.titleLarge.copyWith(fontSize: 20),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(l10n.homeAskAstroAiSub, style: AppTypography.bodySmall),
              const SizedBox(height: AppSpacing.md),
              Row(
                children: <Widget>[
                  Expanded(
                    child: TextField(
                      controller: controller,
                      textInputAction: TextInputAction.send,
                      onSubmitted: onAsk,
                      style: AppTypography.bodyMedium.copyWith(
                        color: AppColors.ivory,
                      ),
                      decoration: InputDecoration(
                        hintText: l10n.homeAskHint,
                        isDense: true,
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.lg,
                          vertical: AppSpacing.md,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  AstroIconButton(
                    icon: Icons.send,
                    semanticLabel: l10n.homeSend,
                    filled: true,
                    onPressed: () => onAsk(controller.text),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.md),
              Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.sm,
                children: <Widget>[
                  for (final String prompt in prompts)
                    AstroChip(label: prompt, onTap: () => onAsk(prompt)),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _CalendarAndGuidance extends ConsumerWidget {
  const _CalendarAndGuidance({required this.moon});

  final MoonPhaseSummary? moon;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppLocalizations l10n = context.l10n;
    // The daily payload may omit the phase; fall back to the moon-phase call.
    final MoonPhase? live = moon == null
        ? ref.watch(homeMoonProvider).asData?.value
        : null;
    final MoonPhaseType? phase = moon?.type ?? live?.type;
    final ZodiacSign? sign = moon?.sign ?? live?.sign;

    final Widget calendar = AstroCard(
      onTap: () => context.push(AppRoutes.cosmicCalendar),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Row(
            children: <Widget>[
              const Icon(
                Icons.calendar_month_outlined,
                size: 18,
                color: AppColors.gold,
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text(
                  l10n.homeCosmicCalendar,
                  style: AppTypography.titleLarge.copyWith(fontSize: 18),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              AstroImage(
                (phase ?? MoonPhaseType.fullMoon).asset,
                width: 56,
                height: 56,
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Text(
                      l10n.commonToday.toUpperCaseFor(context.languageCode),
                      style: AppTypography.overline.copyWith(
                        color: AppColors.gold,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xxs),
                    if (phase != null)
                      Text(
                        l10n.moonPhase(phase),
                        style: AppTypography.titleMedium,
                      ),
                    if (sign != null)
                      Text(
                        l10n.moonInSign(l10n.sign(sign)),
                        style: AppTypography.bodyMedium,
                      ),
                    if (moon?.message != null)
                      Padding(
                        padding: const EdgeInsets.only(top: AppSpacing.xs),
                        child: Text(
                          moon!.message!,
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                          style: AppTypography.bodySmall,
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );

    final Widget guidance = AstroCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text(
            l10n.homeInnerGuidance,
            style: AppTypography.titleLarge.copyWith(fontSize: 18),
          ),
          Text(l10n.homeInnerGuidanceSub, style: AppTypography.bodySmall),
          const SizedBox(height: AppSpacing.lg),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: <Widget>[
              Expanded(
                child: _GuidanceItem(
                  asset: AppAssets.tarotBack,
                  label: l10n.exploreTarot,
                  caption: l10n.pillarTarotSub,
                  onTap: () => context.push(AppRoutes.tarot),
                ),
              ),
              Expanded(
                child: _GuidanceItem(
                  asset: AppAssets.runeStone('raidho'),
                  label: l10n.exploreRune,
                  caption: l10n.pillarRuneSub,
                  onTap: () => context.push(AppRoutes.rune),
                ),
              ),
              Expanded(
                child: _GuidanceItem(
                  asset: AppAssets.katinaBack,
                  label: l10n.exploreKatina,
                  caption: l10n.pillarKatinaSub,
                  onTap: () => context.push(AppRoutes.katina),
                ),
              ),
            ],
          ),
        ],
      ),
    );

    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        if (constraints.maxWidth >= 520) {
          return IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                Expanded(child: calendar),
                const SizedBox(width: AppSpacing.cardGap),
                Expanded(child: guidance),
              ],
            ),
          );
        }
        return Column(
          children: <Widget>[
            calendar,
            const SizedBox(height: AppSpacing.cardGap),
            guidance,
          ],
        );
      },
    );
  }
}

class _GuidanceItem extends StatelessWidget {
  const _GuidanceItem({
    required this.asset,
    required this.label,
    required this.caption,
    required this.onTap,
  });

  final String asset;
  final String label;
  final String caption;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: '$label, $caption',
      excludeSemantics: true,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.xs,
            vertical: AppSpacing.sm,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.hairlineStrong),
                ),
                clipBehavior: Clip.antiAlias,
                child: AstroImage(
                  asset,
                  width: 56,
                  height: 56,
                  fit: BoxFit.cover,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTypography.titleMedium.copyWith(fontSize: 14),
              ),
              Text(
                caption,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: AppTypography.bodySmall.copyWith(
                  fontSize: AppTypography.minFontSize,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Home loading shape: frequency card, a row of transit cards, the Ask card.
class _HomeSkeleton extends StatelessWidget {
  const _HomeSkeleton();

  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    label: b12(context, 'loading'),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        AstroCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              const AstroSkeleton(width: 200, height: 28),
              const SizedBox(height: AppSpacing.xl),
              Row(
                children: <Widget>[
                  const AstroSkeleton.circle(size: 112),
                  const SizedBox(width: AppSpacing.lg),
                  Expanded(
                    child: Column(
                      children: <Widget>[
                        for (int i = 0; i < 4; i++) ...<Widget>[
                          if (i > 0) const SizedBox(height: AppSpacing.md),
                          const AstroSkeleton(height: 12),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.sectionGap),
        const AstroSkeleton(width: 180, height: 22),
        const SizedBox(height: AppSpacing.md),
        const Row(
          children: <Widget>[
            Expanded(child: AstroSkeletonCard(lines: 2)),
            SizedBox(width: AppSpacing.md),
            Expanded(child: AstroSkeletonCard(lines: 2)),
          ],
        ),
      ],
    ),
  );
}

/// The bell: unread count from the notification centre, re-read when the
/// app comes back to the foreground and after the centre is closed.
class _NotificationBell extends ConsumerStatefulWidget {
  const _NotificationBell();
  @override
  ConsumerState<_NotificationBell> createState() => _NotificationBellState();
}

class _NotificationBellState extends ConsumerState<_NotificationBell> {
  late final AppLifecycleListener _lifecycle = AppLifecycleListener(
    onResume: () => ref.invalidate(unreadNotificationsProvider),
  );

  @override
  void initState() {
    super.initState();
    _lifecycle;
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;
    final int unread =
        ref.watch(unreadNotificationsProvider).asData?.value ?? 0;
    return AstroIconButton(
      key: const ValueKey('home-bell'),
      icon: Icons.notifications_none,
      semanticLabel: unread > 0
          ? '${l10n.homeNotifications} ($unread)'
          : l10n.homeNotifications,
      badgeCount: unread,
      onPressed: () async {
        await context.push(AppRoutes.notifications);
        ref.invalidate(unreadNotificationsProvider);
      },
    );
  }
}
