import 'package:flutter/material.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../../core/astrology/domain/daily_frequency.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/widgets.dart';
import '../../home/presentation/widgets/frequency_ring.dart';
import '../application/forecast_digest.dart';

/// A forecast as a reader sees it: score, the five life areas, dates, what
/// to watch, what helps - and, folded away, the influences behind it.
class ForecastReadingView extends StatelessWidget {
  const ForecastReadingView({
    super.key,
    required this.digest,
    required this.period,
  });

  final ForecastDigest digest;

  /// daily, weekly, monthly or yearly.
  final String period;

  static const _areaColors = <String, Color>{
    'general_energy': AppColors.energy,
    'love': AppColors.love,
    'career': AppColors.career,
    'money': AppColors.money,
    'mood': AppColors.mood,
  };

  static const _areaIcons = <String, IconData>{
    'general_energy': Icons.bolt_outlined,
    'love': Icons.favorite_border,
    'career': Icons.work_outline,
    'money': Icons.savings_outlined,
    'mood': Icons.spa_outlined,
  };

  /// The period's name. Its bounds are midnights in the chart's timezone,
  /// which fall on the previous day in UTC or on another device, so the name
  /// is read half a day inside them.
  String _range(String language) {
    const inset = Duration(hours: 12);
    final start = digest.startAt.add(inset);
    final end = digest.endAt.subtract(inset);
    final middle = digest.startAt.add(
      digest.endAt.difference(digest.startAt) ~/ 2,
    );
    return switch (period) {
      'daily' => DateFormat('d MMMM y, EEEE', language).format(middle),
      'weekly' =>
        '${DateFormat('d MMM', language).format(start)} – ${DateFormat('d MMM y', language).format(end)}',
      'monthly' => DateFormat('MMMM y', language).format(middle),
      _ => DateFormat('y', language).format(middle),
    };
  }

  @override
  Widget build(BuildContext context) {
    final language = Localizations.localeOf(context).languageCode;
    String t(String key) => b12(context, key);
    return Column(
      key: const ValueKey('forecast-reading'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _Header(
          score: digest.score,
          title: t('fc_title_$period'),
          range: _range(language),
          tone: digest.tone,
        ),
        if (digest.highlights.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          AstroCard(
            key: const ValueKey('forecast-highlights'),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final line in digest.highlights)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(
                          Icons.auto_awesome,
                          size: 16,
                          color: AppColors.gold,
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: Text(line, style: AppTypography.bodyMedium),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ],
        for (final area in digest.areas) ...[
          const SizedBox(height: AppSpacing.md),
          _AreaCard(
            area: area,
            color: _areaColors[area.key] ?? AppColors.gold,
            icon: _areaIcons[area.key] ?? Icons.circle_outlined,
          ),
        ],
        AstroSectionTitle(title: t('fc_sec_dates')),
        _DatesCard(dates: digest.dates, language: language),
        if (digest.cautions.isNotEmpty) ...[
          AstroSectionTitle(title: t('fc_sec_cautions')),
          _InfluenceCard(
            key: const ValueKey('forecast-cautions'),
            lines: digest.cautions,
            icon: Icons.error_outline,
            color: AppColors.warning,
          ),
        ],
        if (digest.supports.isNotEmpty) ...[
          AstroSectionTitle(title: t('fc_sec_supports')),
          _InfluenceCard(
            key: const ValueKey('forecast-supports'),
            lines: digest.supports,
            icon: Icons.wb_sunny_outlined,
            color: AppColors.success,
          ),
        ],
        if (digest.influences.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          AstroCard(
            padding: EdgeInsets.zero,
            child: ExpansionTile(
              key: const ValueKey('forecast-influences'),
              title: Text(
                t('fc_sec_influences'),
                style: AppTypography.titleMedium,
              ),
              childrenPadding: const EdgeInsets.fromLTRB(
                AppSpacing.lg,
                0,
                AppSpacing.lg,
                AppSpacing.md,
              ),
              children: [
                for (final line in digest.influences)
                  _InfluenceRow(
                    line: line,
                    icon: line.supportive
                        ? Icons.add_circle_outline
                        : Icons.remove_circle_outline,
                    color: line.supportive
                        ? AppColors.success
                        : AppColors.warning,
                    footer: [
                      t(line.supportive ? 'fc_supportive' : 'fc_challenging'),
                      if (line.weight > 0)
                        t('fc_weight').replaceAll('{n}', '${line.weight}'),
                      if (line.at case final at?)
                        DateFormat('d MMM', language).format(at.toLocal()),
                    ].join(' · '),
                  ),
              ],
            ),
          ),
        ],
        const SizedBox(height: AppSpacing.md),
        Text(
          t('fc_method_note'),
          textAlign: TextAlign.center,
          style: AppTypography.bodySmall,
        ),
      ],
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.score,
    required this.title,
    required this.range,
    required this.tone,
  });
  final int score;
  final String title;
  final String range;
  final ForecastTone tone;

  @override
  Widget build(BuildContext context) => AstroCard(
    key: const ValueKey('forecast-header'),
    borderColor: AppColors.hairlineStrong,
    gradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [
        AppColors.gold.withValues(alpha: 0.16),
        AppColors.surface.withValues(alpha: 0.94),
      ],
    ),
    child: Row(
      children: [
        FrequencyRing(
          score: score,
          caption: b12(context, 'fc_tone_label_${tone.name}'),
          size: 104,
        ),
        const SizedBox(width: AppSpacing.lg),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: AppTypography.headlineMedium.copyWith(
                  color: AppColors.goldBright,
                ),
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(range, style: AppTypography.labelLarge),
              const SizedBox(height: AppSpacing.sm),
              Text(
                b12(context, 'fc_tone_${tone.name}_general'),
                style: AppTypography.bodySmall,
              ),
            ],
          ),
        ),
      ],
    ),
  );
}

class _AreaCard extends StatelessWidget {
  const _AreaCard({
    required this.area,
    required this.color,
    required this.icon,
  });
  final AreaReading area;
  final Color color;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final trend = switch (area.trend) {
      ScoreTrend.rising => Icons.trending_up,
      ScoreTrend.falling => Icons.trending_down,
      _ => Icons.trending_flat,
    };
    return AstroCard(
      key: ValueKey('forecast-area-${area.key}'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 22),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text(
                  b12(context, 'fc_sec_${area.key}'),
                  style: AppTypography.titleLarge,
                ),
              ),
              Icon(trend, color: color, size: 20),
              const SizedBox(width: AppSpacing.xs),
              Text(
                '${area.score}',
                style: AppTypography.titleLarge.copyWith(color: color),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: (area.score / 100).clamp(0, 1).toDouble(),
              minHeight: 6,
              color: color,
              backgroundColor: AppColors.surfaceMuted,
              semanticsLabel: b12(context, 'fc_sec_${area.key}'),
              semanticsValue: '${area.score}',
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(area.summary, style: AppTypography.bodyMedium),
          if (area.support case final line?)
            _InfluenceRow(
              line: line,
              icon: Icons.add_circle_outline,
              color: AppColors.success,
              lead: b12(context, 'fc_support'),
            ),
          if (area.caution case final line?)
            _InfluenceRow(
              line: line,
              icon: Icons.remove_circle_outline,
              color: AppColors.warning,
              lead: b12(context, 'fc_caution'),
            ),
        ],
      ),
    );
  }
}

class _InfluenceCard extends StatelessWidget {
  const _InfluenceCard({
    super.key,
    required this.lines,
    required this.icon,
    required this.color,
  });
  final List<InfluenceLine> lines;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) => AstroCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final line in lines)
          _InfluenceRow(line: line, icon: icon, color: color),
      ],
    ),
  );
}

class _InfluenceRow extends StatelessWidget {
  const _InfluenceRow({
    required this.line,
    required this.icon,
    required this.color,
    this.lead,
    this.footer,
  });
  final InfluenceLine line;
  final IconData icon;
  final Color color;
  final String? lead;
  final String? footer;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: AppSpacing.sm),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 2),
          child: Icon(icon, size: 18, color: color),
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                lead == null ? line.title : '$lead: ${line.title}',
                style: AppTypography.labelLarge,
              ),
              if (line.meaning case final meaning?)
                Text(meaning, style: AppTypography.bodySmall),
              if (footer case final footer?)
                Text(
                  footer,
                  style: AppTypography.labelSmall.copyWith(color: color),
                ),
            ],
          ),
        ),
      ],
    ),
  );
}

class _DatesCard extends StatelessWidget {
  const _DatesCard({required this.dates, required this.language});
  final List<DatedLine> dates;
  final String language;

  @override
  Widget build(BuildContext context) {
    if (dates.isEmpty) {
      return AstroCard(child: Text(b12(context, 'fc_none_dates')));
    }
    final day = DateFormat('d MMM', language);
    final time = DateFormat('HH:mm', language);
    String when(DatedLine d) {
      final at = d.at.toLocal();
      final until = d.until?.toLocal();
      if (d.withTime) {
        return until == null
            ? time.format(at)
            : '${time.format(at)}–${time.format(until)}';
      }
      if (until == null || DateUtils.isSameDay(at, until)) {
        return day.format(at);
      }
      return '${day.format(at)} – ${day.format(until)}';
    }

    return AstroCard(
      key: const ValueKey('forecast-dates'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final (i, d) in dates.indexed) ...[
            if (i > 0) const Divider(color: AppColors.hairline, height: 20),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 86,
                  child: Text(
                    when(d),
                    style: AppTypography.labelLarge.copyWith(
                      color: AppColors.goldBright,
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(d.title, style: AppTypography.labelLarge),
                      if (d.note case final note?)
                        Text(note, style: AppTypography.bodySmall),
                    ],
                  ),
                ),
                if (d.supportive case final supportive?) ...[
                  const SizedBox(width: AppSpacing.xs),
                  AstroBadge(
                    label: b12(
                      context,
                      supportive
                          ? 'fc_badge_opportunity'
                          : 'fc_badge_challenge',
                    ),
                    color: supportive ? AppColors.success : AppColors.warning,
                  ),
                ],
              ],
            ),
          ],
        ],
      ),
    );
  }
}
