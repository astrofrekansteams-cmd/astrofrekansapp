import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/assets/app_assets.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/widgets.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../billing/application/entitlement_service.dart';
import 'widgets/marketplace_hub.dart';

/// One destination on the Explore hub.
class _Entry {
  const _Entry(
    this.titleKey,
    this.asset,
    this.route, {
    this.subtitleKey,
    this.feature,
  });
  final String titleKey;
  final String? subtitleKey;
  final String asset;
  final String route;
  final PremiumFeature? feature;
}

/// "Keşfet": three featured areas up front, then grouped secondary tools.
/// Astro AI is not repeated here - it lives in the centre of the tab bar.
class ExploreScreen extends ConsumerStatefulWidget {
  const ExploreScreen({super.key});
  @override
  ConsumerState<ExploreScreen> createState() => _ExploreScreenState();
}

class _ExploreScreenState extends ConsumerState<ExploreScreen> {
  String _category = 'all';
  String _query = '';

  static const List<_Entry> _featured = [
    _Entry(
      'natal',
      AppAssets.natalZodiacWheel,
      AppRoutes.natalChart,
      subtitleKey: 'explore_natal_sub',
    ),
    _Entry(
      'transits',
      'assets/planets/saturn/saturn.png',
      AppRoutes.transits,
      subtitleKey: 'explore_transits_sub',
    ),
    _Entry(
      'relationship_analysis',
      'assets/daily_frequency/love/love.png',
      '${AppRoutes.compatibility}?kind=synastry',
      subtitleKey: 'explore_relationship_sub',
      feature: PremiumFeature.synastry,
    ),
  ];

  static const List<(String, List<_Entry>)> _groups = [
    (
      'explore_relationships',
      [
        _Entry(
          'synastry',
          'assets/planets/venus/venus.png',
          '${AppRoutes.compatibility}?kind=synastry',
          subtitleKey: 'explore_synastry_sub',
          feature: PremiumFeature.synastry,
        ),
        _Entry(
          'composite',
          'assets/planets/mars/mars.png',
          '${AppRoutes.compatibility}?kind=composite',
          subtitleKey: 'explore_composite_sub',
          feature: PremiumFeature.composite,
        ),
        _Entry(
          'davison',
          'assets/planets/moon/moon.png',
          '${AppRoutes.compatibility}?kind=davison',
          subtitleKey: 'explore_davison_sub',
          feature: PremiumFeature.davison,
        ),
      ],
    ),
    (
      'explore_forecasts',
      [
        _Entry(
          'forecast_daily',
          'assets/planets/sun/sun.png',
          '${AppRoutes.forecasts}?period=daily',
          subtitleKey: 'explore_daily_sub',
        ),
        _Entry(
          'forecast_monthly',
          'assets/planets/jupiter/jupiter.png',
          '${AppRoutes.forecasts}?period=monthly',
          subtitleKey: 'explore_monthly_sub',
          feature: PremiumFeature.monthlyForecast,
        ),
        _Entry(
          'forecast_yearly',
          'assets/planets/saturn/saturn.png',
          '${AppRoutes.forecasts}?period=yearly',
          subtitleKey: 'explore_yearly_sub',
          feature: PremiumFeature.yearlyForecast,
        ),
      ],
    ),
    (
      'explore_returns',
      [
        _Entry(
          'solar_return',
          'assets/planets/sun/sun.png',
          AppRoutes.solarReturn,
          subtitleKey: 'explore_solar_sub',
          feature: PremiumFeature.solarReturn,
        ),
        _Entry(
          'lunar_return',
          'assets/planets/moon/moon.png',
          AppRoutes.lunarReturn,
          subtitleKey: 'explore_lunar_sub',
          feature: PremiumFeature.lunarReturn,
        ),
      ],
    ),
    (
      'explore_personal',
      [
        _Entry(
          'moon_guide',
          'assets/moon_phases/full_moon/full_moon.png',
          AppRoutes.moonGuide,
          subtitleKey: 'explore_moon_sub',
        ),
        _Entry(
          'stone_guide',
          AppAssets.premiumCrystal,
          AppRoutes.stoneGuide,
          subtitleKey: 'explore_stone_sub',
        ),
        _Entry(
          'numerology',
          AppAssets.natalZodiacWheel,
          AppRoutes.numerology,
          subtitleKey: 'explore_numerology_sub',
        ),
        _Entry(
          'calendar',
          'assets/moon_phases/new_moon/new_moon.png',
          AppRoutes.cosmicCalendar,
          subtitleKey: 'explore_calendar_sub',
        ),
        _Entry(
          'horary',
          'assets/planets/mercury/mercury.png',
          AppRoutes.horary,
          subtitleKey: 'explore_horary_sub',
        ),
      ],
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;
    final entitlements = ref.watch(entitlementServiceProvider);
    bool locked(_Entry e) =>
        e.feature != null && !entitlements.canUse(e.feature!);

    bool matches(_Entry e) =>
        ('${b12(context, e.titleKey)} ${e.subtitleKey == null ? '' : b12(context, e.subtitleKey!)}')
            .toLowerCase()
            .contains(_query.trim().toLowerCase());
    final featured = _featured
        .where(
          (e) =>
              (_category == 'all' ||
                  (_category == 'relationships'
                      ? e.feature == PremiumFeature.synastry
                      : _category == 'astrology' &&
                            e.feature != PremiumFeature.synastry)) &&
              matches(e),
        )
        .toList();
    final groups = [
      for (final (title, entries) in _groups)
        if (_category == 'all' ||
            (_category == 'relationships'
                ? title == 'explore_relationships'
                : _category == 'astrology' && title != 'explore_relationships'))
          (title, entries.where(matches).toList()),
    ].where((g) => g.$2.isNotEmpty).toList();
    bool sectionMatches(String key) =>
        b12(context, key).toLowerCase().contains(_query.trim().toLowerCase());
    final showSpreads =
        (_category == 'all' || _category == 'spreads') &&
        (_query.trim().isEmpty ||
            [
              'explore_category_spreads',
              'tarot',
              'rune',
              'katina',
            ].any(sectionMatches));
    final showConsultants =
        (_category == 'all' || _category == 'consultants') &&
        (_query.trim().isEmpty ||
            sectionMatches('explore_category_consultants'));
    return ListView(
      padding: EdgeInsets.fromLTRB(
        context.gutter,
        AppSpacing.lg,
        context.gutter,
        AppSpacing.sectionGap + AppSpacing.huge,
      ),
      children: <Widget>[
        Text(
          l10n.exploreTitle,
          style: AppTypography.displayMedium.copyWith(fontSize: 30),
        ),
        const SizedBox(height: AppSpacing.xxs),
        Text(l10n.exploreSubtitle, style: AppTypography.bodyMedium),
        const SizedBox(height: AppSpacing.xl),

        TextField(
          key: const ValueKey('explore-search'),
          decoration: InputDecoration(
            prefixIcon: const Icon(Icons.search),
            hintText: b12(context, 'explore_search_hint'),
          ),
          onChanged: (value) => setState(() => _query = value),
        ),
        const SizedBox(height: AppSpacing.md),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final category in [
              'all',
              'astrology',
              'relationships',
              'spreads',
              'consultants',
            ])
              ChoiceChip(
                key: ValueKey('explore-category-$category'),
                label: Text(b12(context, 'explore_category_$category')),
                selected: _category == category,
                onSelected: (_) => setState(() => _category = category),
              ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        if (featured.isEmpty &&
            groups.isEmpty &&
            !showSpreads &&
            !showConsultants)
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(b12(context, 'explore_no_results')),
          ),
        // Featured: the three primary astrology areas.
        for (final (i, entry) in featured.indexed) ...[
          if (i > 0) const SizedBox(height: AppSpacing.md),
          _FeatureCard(entry: entry, locked: locked(entry)),
        ],

        for (final (title, entries) in groups) ...[
          const SizedBox(height: AppSpacing.sectionGap),
          _GroupHeader(title: b12(context, title)),
          const SizedBox(height: AppSpacing.md),
          _GroupCard(entries: entries, isLocked: locked),
        ],

        // Spreads, then the consultant marketplace as its own area.
        const SizedBox(height: AppSpacing.sectionGap),
        if (showSpreads) const SpreadsSection(),
        const SizedBox(height: AppSpacing.sectionGap),
        if (showConsultants) const ConsultantsSection(),
        const SizedBox(height: AppSpacing.sectionGap),
        if (showConsultants) const ServiceTypesSection(),
        const SizedBox(height: AppSpacing.lg),
        if (showConsultants) const AppointmentsEntry(),

        const SizedBox(height: AppSpacing.sectionGap),
        AstroCard(
          onTap: () => context.push(AppRoutes.premium),
          semanticLabel: l10n.explorePremium,
          child: Row(
            children: [
              const AstroImage(AppAssets.premiumCrown, width: 44, height: 44),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      b12(context, 'hub_plans_title'),
                      style: AppTypography.titleMedium,
                    ),
                    Text(
                      b12(context, 'hub_plans_sub'),
                      style: AppTypography.bodySmall,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              const Icon(Icons.chevron_right, color: AppColors.gold),
            ],
          ),
        ),
      ],
    );
  }
}

class _GroupHeader extends StatelessWidget {
  const _GroupHeader({required this.title});
  final String title;
  @override
  Widget build(BuildContext context) => Row(
    children: [
      Flexible(
        child: Text(
          title,
          style: AppTypography.titleLarge.copyWith(fontSize: 21),
        ),
      ),
      const SizedBox(width: AppSpacing.md),
      const Expanded(child: AstroGoldDivider()),
    ],
  );
}

class _LockOrChevron extends StatelessWidget {
  const _LockOrChevron({required this.locked, required this.label});
  final String label;
  final bool locked;
  @override
  Widget build(BuildContext context) => locked
      ? AstroBadge(label: label, icon: Icons.lock_outline)
      : const Icon(Icons.chevron_right, color: AppColors.gold);
}

/// Primary area: large artwork, title, one-line purpose.
class _FeatureCard extends ConsumerWidget {
  const _FeatureCard({required this.entry, required this.locked});
  final _Entry entry;
  final bool locked;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final title = b12(context, entry.titleKey);
    final tier = entry.feature == null
        ? null
        : ref.watch(entitlementServiceProvider).requiredTier(entry.feature!);
    final planLabel = tier == null ? '' : b12(context, 'tier_${tier.wire}');
    return AstroCard(
      onTap: () => context.push(entry.route),
      semanticLabel: locked ? '$title, $planLabel' : title,
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Row(
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: AppColors.hairlineStrong),
            ),
            padding: const EdgeInsets.all(AppSpacing.xs),
            child: AstroImage(entry.asset, width: 56, height: 56),
          ),
          const SizedBox(width: AppSpacing.lg),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: AppTypography.titleLarge),
                if (locked)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: _LockOrChevron(locked: true, label: planLabel),
                  ),
                if (entry.subtitleKey != null) ...[
                  const SizedBox(height: AppSpacing.xxs),
                  Text(
                    b12(context, entry.subtitleKey!),
                    style: AppTypography.bodyMedium,
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          if (!locked) _LockOrChevron(locked: false, label: planLabel),
        ],
      ),
    );
  }
}

/// Secondary tools grouped in one card as rows, not as equal boxes.
class _GroupCard extends StatelessWidget {
  const _GroupCard({required this.entries, required this.isLocked});
  final List<_Entry> entries;
  final bool Function(_Entry) isLocked;

  @override
  Widget build(BuildContext context) => AstroCard(
    padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
    child: Column(
      children: [
        for (final (i, entry) in entries.indexed) ...[
          if (i > 0)
            const Divider(
              height: 1,
              indent: AppSpacing.lg,
              endIndent: AppSpacing.lg,
              color: AppColors.hairline,
            ),
          _GroupRow(entry: entry, locked: isLocked(entry)),
        ],
      ],
    ),
  );
}

class _GroupRow extends ConsumerWidget {
  const _GroupRow({required this.entry, required this.locked});
  final _Entry entry;
  final bool locked;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final title = b12(context, entry.titleKey);
    final tier = entry.feature == null
        ? null
        : ref.watch(entitlementServiceProvider).requiredTier(entry.feature!);
    final planLabel = tier == null ? '' : b12(context, 'tier_${tier.wire}');
    return Semantics(
      button: true,
      label: locked ? '$title, $planLabel' : title,
      excludeSemantics: true,
      child: InkWell(
        onTap: () => context.push(entry.route),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 60),
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.lg,
              vertical: AppSpacing.md,
            ),
            child: Row(
              children: [
                AstroImage(entry.asset, width: 32, height: 32),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title, style: AppTypography.titleMedium),
                      if (locked)
                        Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: _LockOrChevron(locked: true, label: planLabel),
                        ),
                      if (entry.subtitleKey != null)
                        Text(
                          b12(context, entry.subtitleKey!),
                          style: AppTypography.bodySmall,
                        ),
                    ],
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                if (!locked) _LockOrChevron(locked: false, label: planLabel),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Readings keep their deck artwork as the visual anchor.
