import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart' show DateFormat;
import '../../../core/assets/app_assets.dart';
import '../../../core/astrology/domain/natal_chart.dart';
import '../../../core/astrology/domain/transit.dart';
import '../../../core/astrology/domain/daily_frequency.dart';
import '../../../core/astrology/data/production_repository.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/localization/astro_labels.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/utils/text_case.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../home/application/home_providers.dart';
import '../application/core_providers.dart';
import 'chart_view.dart';
import '../../../core/localization/transit_meaning.dart';
import '../../billing/application/coin_spend.dart';
import '../../billing/application/entitlement_service.dart';

String instant(DateTime? value) => value == null
    ? '—'
    : '${DateFormat('yyyy-MM-dd HH:mm').format(value.toUtc())} UTC';

class NatalScreen extends ConsumerWidget {
  const NatalScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) => CorePage(
    title: 'natal',
    children: [
      ApiStateView(
        value: ref.watch(natalProvider),
        onRetry: () => ref.invalidate(natalProvider),
        builder: (chart) => NatalDetails(chart: chart),
      ),
    ],
  );
}

class NatalDetails extends StatelessWidget {
  const NatalDetails({super.key, required this.chart});
  final NatalChart chart;
  @override
  Widget build(BuildContext context) => ChartView(chart: chart);
}

class TransitsScreen extends ConsumerStatefulWidget {
  const TransitsScreen({super.key});
  @override
  ConsumerState<TransitsScreen> createState() => _TransitsState();
}

/// Today / tomorrow / this week / this month, or any picked day. The server
/// computes every window; this screen only chooses which one to ask for.
class _TransitsState extends ConsumerState<TransitsScreen> {
  DateTime date = DateUtils.dateOnly(DateTime.now());
  String range = 'day';
  bool picked = false;

  static const _ranges = [
    ('day', 'today'),
    ('tomorrow', 'tomorrow'),
    ('week', 'this_week'),
    ('month', 'this_month'),
  ];

  Future<void> _pickDate() async {
    final selected = await showDatePicker(
      context: context,
      initialDate: date,
      firstDate: DateTime(1900),
      lastDate: DateTime(2100),
    );
    if (selected != null && mounted) {
      setState(() {
        date = selected;
        range = 'day';
        picked = true;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final entitlements = ref.watch(entitlementServiceProvider);
    final locked =
        !entitlements.canUseTransitRange(range) &&
        !ref
            .watch(coinUnlocksProvider)
            .containsKey(transitUnlockKey(date, range));
    final provider = transitWindowProvider((date, range));
    final language = Localizations.localeOf(context).languageCode;
    final dateFormat = DateFormat.yMMMd(context.languageCode);
    return CorePage(
      title: 'transits',
      children: [
        Row(
          children: [
            Expanded(
              child: AstroSegmentedControl<String>(
                selected: picked ? null : range,
                segments: [
                  for (final choice in _ranges)
                    AstroSegment(
                      value: choice.$1,
                      label: b12(context, choice.$2),
                      icon: entitlements.canUseTransitRange(choice.$1)
                          ? null
                          : Icons.lock_outline,
                    ),
                ],
                onChanged: (value) => setState(() {
                  range = value;
                  picked = false;
                  date = DateUtils.dateOnly(DateTime.now());
                }),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            AstroIconButton(
              icon: Icons.calendar_month_outlined,
              semanticLabel: b12(context, 'pick_date'),
              filled: picked,
              onPressed: _pickDate,
            ),
          ],
        ),
        if (locked)
          CoinLockCard(
            unlockKey: transitUnlockKey(date, range),
            feature: PremiumFeature.advancedTransits,
          )
        else
          ApiStateView(
            value: ref.watch(provider),
            onRetry: () => ref.invalidate(provider),
            loading: const _TransitsSkeleton(),
            builder: (window) => Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  picked
                      ? dateFormat.format(date)
                      : '${dateFormat.format(window.startAt.toLocal())}'
                            ' — ${dateFormat.format(window.endAt.toLocal())}',
                  textAlign: TextAlign.center,
                  style: AppTypography.labelMedium,
                ),
                // Said once for the whole list instead of on every card.
                if (window.all.any((t) => t.windowClipped))
                  Padding(
                    padding: const EdgeInsets.only(top: AppSpacing.sm),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.info_outline,
                          size: 16,
                          color: AppColors.textSubtle,
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: Text(
                            b12(context, 'clipped'),
                            style: AppTypography.bodySmall,
                          ),
                        ),
                      ],
                    ),
                  ),
                if (window.all.isEmpty)
                  AstroEmptyState(
                    kind: AstroEmptyStateKind.noResults,
                    title: b12(context, 'no_transits'),
                  ),
                for (final (title, items) in [
                  ('transits_active', window.active),
                  ('transits_approaching', window.approaching),
                  ('transits_upcoming', window.upcoming),
                ])
                  if (items.isNotEmpty) ...[
                    const SizedBox(height: AppSpacing.sectionGap),
                    AstroSectionTitle(title: b12(context, title)),
                    const SizedBox(height: AppSpacing.md),
                    for (var i = 0; i < items.length; i++) ...[
                      if (i > 0) const SizedBox(height: AppSpacing.cardGap),
                      TransitDetails(transit: items[i], language: language),
                    ],
                  ],
                if (window.ingresses.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.sectionGap),
                  AstroSectionTitle(title: b12(context, 'ingresses')),
                  const SizedBox(height: AppSpacing.md),
                  AstroCard(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.cardPadding,
                      vertical: AppSpacing.xs,
                    ),
                    child: Column(
                      children: [
                        for (final i in window.ingresses)
                          Padding(
                            padding: const EdgeInsets.symmetric(
                              vertical: AppSpacing.md,
                            ),
                            child: Row(
                              children: [
                                AstroImage(
                                  i.planet.asset,
                                  width: 32,
                                  height: 32,
                                ),
                                const SizedBox(width: AppSpacing.md),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        '${context.l10n.planet(i.planet)} → '
                                        '${i.toHouse}. ${b12(context, 'house')}',
                                        style: AppTypography.titleMedium,
                                      ),
                                      Text(
                                        '${_fmt(context, i.enteredAt)} — '
                                        '${_fmt(context, i.estimatedExitAt)}',
                                        style: AppTypography.bodySmall,
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
      ],
    );
  }
}

class _TransitsSkeleton extends StatelessWidget {
  const _TransitsSkeleton();
  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    label: b12(context, 'loading'),
    child: const Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AstroSkeleton(width: 180, height: 14),
        SizedBox(height: AppSpacing.sectionGap),
        AstroSkeleton(width: 140, height: 22),
        SizedBox(height: AppSpacing.md),
        AstroSkeletonCard(media: true, mediaSize: 40, lines: 3),
        SizedBox(height: AppSpacing.cardGap),
        AstroSkeletonCard(media: true, mediaSize: 40, lines: 3),
      ],
    ),
  );
}

String _fmt(BuildContext context, DateTime? value) => value == null
    ? '—'
    : DateFormat.yMMMd(context.languageCode).format(value.toLocal());

/// One transit. Primary: who touches what, how (aspect), what it means and
/// its status. Secondary, but always present: orb, start / peak / end and
/// the affected houses.
class TransitDetails extends StatelessWidget {
  const TransitDetails({super.key, required this.transit, this.language});
  final Transit transit;
  final String? language;

  String _target(BuildContext context) {
    final l10n = context.l10n;
    if (transit.targetPlanet case final planet?) {
      return '${b12(context, 'natal_prefix')} ${planetTableName(context, planet)}';
    }
    if (transit.targetAngle case final angle?) {
      return '${b12(context, 'natal_prefix')} ${angle.name.toUpperCase()}';
    }
    if (transit.targetHouse case final house?) {
      return '$house. ${b12(context, 'house')}';
    }
    return l10n.transitTitle(transit.summary);
  }

  @override
  Widget build(BuildContext context) {
    final t = transit;
    final lang = language ?? Localizations.localeOf(context).languageCode;
    final (String? statusKey, Color statusColor) = switch (t.status) {
      TransitStatus.approaching => ('status_approaching', AppColors.gold),
      TransitStatus.exact ||
      TransitStatus.active => ('status_active', AppColors.success),
      TransitStatus.separating => ('status_separating', AppColors.ivoryMuted),
      TransitStatus.unknown => (null, AppColors.gold),
    };
    final aspect = t.aspectType;
    final secondary = [
      'orb ${t.orb.toStringAsFixed(2)}°',
      if (t.applying != null)
        b12(context, t.applying! ? 'applying' : 'separating_short'),
      if (t.affectedHouses.isNotEmpty)
        '${b12(context, 'affected_houses')}: ${t.affectedHouses.join(', ')}',
    ].join(' · ');
    return AstroCard(
      semanticLabel:
          '${context.l10n.planet(t.transitingPlanet)} ${_target(context)}',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AstroImage(
                AppAssets.planets[t.transitingPlanet.assetKey] ??
                    AppAssets.astroAiOrb,
                width: 44,
                height: 44,
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${context.l10n.planet(t.transitingPlanet)} → '
                      '${_target(context)}',
                      style: AppTypography.titleLarge.copyWith(fontSize: 19),
                    ),
                    if (aspect != null) ...[
                      const SizedBox(height: AppSpacing.xs),
                      Row(
                        children: [
                          AspectGlyph(type: aspect, size: 18, strokeWidth: 1.6),
                          const SizedBox(width: AppSpacing.sm),
                          Flexible(
                            child: Text(
                              _capitalized(context.l10n.aspect(aspect), lang),
                              style: AppTypography.labelLarge.copyWith(
                                color: AppColors.goldBright,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
              if (statusKey != null) ...[
                const SizedBox(width: AppSpacing.sm),
                AstroBadge(label: b12(context, statusKey), color: statusColor),
              ],
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Text(
            transitMeaning(t, lang),
            style: AppTypography.bodyLarge.copyWith(height: 1.5),
          ),
          const SizedBox(height: AppSpacing.lg),
          const AstroGoldDivider(),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              _DateCell(
                label: b12(context, 'start'),
                value: _fmt(context, t.startAt),
              ),
              _DateCell(
                label: b12(context, 'peak'),
                value: _fmt(context, t.exactAt),
                highlight: true,
              ),
              _DateCell(
                label: b12(context, 'end'),
                value: _fmt(context, t.endAt),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Text(secondary, style: AppTypography.bodySmall),
          if (t.passes.length > 1)
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.xs),
              child: Text(
                '${b12(context, 'passes')}: ${t.passes.map((p) => _fmt(context, p.exactAt) + (p.direction == TransitPassDirection.retrograde ? ' ℞' : '')).join(' · ')}',
                style: AppTypography.bodySmall,
              ),
            ),
        ],
      ),
    );
  }
}

String _capitalized(String text, String language) => text.isEmpty
    ? text
    : text.substring(0, 1).toUpperCaseFor(language) + text.substring(1);

class _DateCell extends StatelessWidget {
  const _DateCell({
    required this.label,
    required this.value,
    this.highlight = false,
  });
  final String label;
  final String value;
  final bool highlight;
  @override
  Widget build(BuildContext context) => Expanded(
    child: Column(
      children: [
        Text(label, style: AppTypography.labelSmall),
        const SizedBox(height: AppSpacing.xxs),
        Text(
          value,
          textAlign: TextAlign.center,
          style: AppTypography.bodyMedium.copyWith(
            color: highlight ? AppColors.goldBright : AppColors.ivory,
            fontWeight: highlight ? FontWeight.w600 : FontWeight.w400,
          ),
        ),
      ],
    ),
  );
}

class CalendarScreen extends ConsumerStatefulWidget {
  const CalendarScreen({super.key});
  @override
  ConsumerState<CalendarScreen> createState() => _CalendarState();
}

class _CalendarState extends ConsumerState<CalendarScreen> {
  DateTime month = DateTime(DateTime.now().year, DateTime.now().month);
  int? selectedDay;
  @override
  Widget build(BuildContext context) {
    final provider = calendarProvider(month);
    return CorePage(
      title: 'calendar',
      children: [
        Row(
          children: [
            IconButton(
              tooltip: MaterialLocalizations.of(context).previousMonthTooltip,
              onPressed: () => setState(() {
                month = DateTime(month.year, month.month - 1);
                selectedDay = null;
              }),
              icon: const Icon(Icons.chevron_left),
            ),
            Expanded(
              child: Text(
                DateFormat.yMMMM(context.languageCode).format(month),
                textAlign: TextAlign.center,
              ),
            ),
            IconButton(
              tooltip: MaterialLocalizations.of(context).nextMonthTooltip,
              onPressed: () => setState(() {
                month = DateTime(month.year, month.month + 1);
                selectedDay = null;
              }),
              icon: const Icon(Icons.chevron_right),
            ),
          ],
        ),
        ApiStateView(
          value: ref.watch(provider),
          onRetry: () => ref.invalidate(provider),
          builder: (events) => Column(
            children: [
              AstroCard(
                child: Column(
                  children: [
                    Row(
                      children: [
                        for (var weekday = 0; weekday < 7; weekday++)
                          Expanded(
                            child: Text(
                              DateFormat.E(
                                context.languageCode,
                              ).format(DateTime(2024, 1, 1 + weekday)),
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                color: AppColors.ivoryMuted,
                                fontSize: 12,
                              ),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    GridView.builder(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      gridDelegate:
                          const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 7,
                            mainAxisExtent: 48,
                          ),
                      itemCount:
                          ((month.weekday -
                                      1 +
                                      DateTime(
                                        month.year,
                                        month.month + 1,
                                        0,
                                      ).day) /
                                  7)
                              .ceil() *
                          7,
                      itemBuilder: (context, index) {
                        final day = index - month.weekday + 2;
                        if (day < 1 ||
                            day >
                                DateTime(month.year, month.month + 1, 0).day) {
                          return const SizedBox.shrink();
                        }
                        final marked = events.any(
                          (e) =>
                              e.exactAt.year == month.year &&
                              e.exactAt.month == month.month &&
                              e.exactAt.day == day,
                        );
                        final selected = selectedDay == day;
                        return Semantics(
                          selected: selected,
                          label: DateFormat.yMMMMd(
                            context.languageCode,
                          ).format(DateTime(month.year, month.month, day)),
                          child: InkWell(
                            customBorder: const CircleBorder(),
                            onTap: () => setState(
                              () => selectedDay = selected ? null : day,
                            ),
                            child: Container(
                              margin: const EdgeInsets.all(3),
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: selected
                                    ? AppColors.gold
                                    : Colors.transparent,
                              ),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Text(
                                    '$day',
                                    style: TextStyle(
                                      color: selected
                                          ? AppColors.night
                                          : AppColors.ivory,
                                    ),
                                  ),
                                  Container(
                                    width: 4,
                                    height: 4,
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      color: marked
                                          ? (selected
                                                ? AppColors.night
                                                : AppColors.gold)
                                          : Colors.transparent,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              if (selectedDay != null &&
                  !events.any(
                    (e) =>
                        e.exactAt.year == month.year &&
                        e.exactAt.month == month.month &&
                        e.exactAt.day == selectedDay,
                  ))
                Text(b12(context, 'empty')),
              if (events.isEmpty && selectedDay == null)
                Text(b12(context, 'empty')),
              for (final e in events)
                if (selectedDay == null ||
                    (e.exactAt.year == month.year &&
                        e.exactAt.month == month.month &&
                        e.exactAt.day == selectedDay))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: FactSection(
                      title: e.rawType ?? e.type.name,
                      lines: [
                        instant(e.exactAt),
                        if (e.planet != null) context.l10n.planet(e.planet!),
                        if (e.sign != null) context.l10n.sign(e.sign!),
                        if (e.eclipseSubtype != null) e.eclipseSubtype!,
                      ],
                    ),
                  ),
            ],
          ),
        ),
        if (ref.watch(productionRepositoryProvider) != null)
          ApiStateView(
            value: ref.watch(personalCalendarProvider(month)),
            onRetry: () => ref.invalidate(personalCalendarProvider(month)),
            builder: (items) => FactSection(
              title: 'sources',
              lines: [
                for (final item in items)
                  '${item.record('event').text('type')} · ${item.json['affected_house'] ?? '—'} · ${item.strings('source_factors').join(', ')}',
              ],
            ),
          ),
      ],
    );
  }
}

class FrequencyScreen extends ConsumerWidget {
  const FrequencyScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) => CorePage(
    title: 'frequency',
    children: [
      ApiStateView<DailyFrequency>(
        value: ref.watch(dailyFrequencyProvider),
        onRetry: () => ref.invalidate(dailyFrequencyProvider),
        builder: (d) => Column(
          children: [
            FactSection(
              title: 'frequency',
              lines: [
                '${d.overallScore}/100',
                for (final score in d.scores)
                  '${score.rawArea ?? score.area.name}: ${score.score} · ${score.trend.name}',
              ],
            ),
            FactSection(
              title: 'hours',
              lines: [
                for (final h in d.importantHours)
                  '${instant(h.start)} — ${instant(h.end)} · ${h.reason} · ${h.factorIds.join(', ')}',
              ],
            ),
            SourceFactors(
              factors: {for (final f in d.influences) f.id: f.label},
            ),
          ],
        ),
      ),
    ],
  );
}
