import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/astrology/data/api_contract_dto.dart';
import '../../../core/astrology/data/production_models.dart';
import '../../../core/astrology/data/production_repository.dart';
import '../../../core/astrology/domain/aspect.dart';
import '../../../core/astrology/domain/planet.dart';
import '../../../core/astrology/domain/zodiac_sign.dart';
import '../../../core/localization/astro_labels.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/astro_card.dart';
import '../../../core/widgets/astro_skeleton.dart';
import '../../../l10n/generated/app_localizations.dart';

/// How often and how long a queued reading is polled.
const readingPollInterval = Duration(seconds: 2);
const readingPollLimit = Duration(minutes: 2);

/// The AI reading of one stored compatibility calculation, per locale.
///
/// The server caches readings per calculation + locale + prompt version, so
/// asking again never pays for a second model call; this provider only adds
/// the polling of a queued job.
final compatibilityReadingProvider = FutureProvider.autoDispose
    .family<ContractRecord, (String, String)>(
      // No automatic retry: a failed reading is shown at once (with its own
      // retry button) and never delays the calculation below it.
      retry: (_, _) => null,
      (ref, key) async {
        final (reportId, locale) = key;
        final repo = ref.watch(productionRepositoryProvider);
        if (repo == null) {
          throw const ApiException(
            kind: ApiErrorKind.unknown,
            code: 'demo_unavailable',
          );
        }
        return loadCompatibilityReading(repo, reportId, locale: locale);
      },
    );

/// Asks for the reading and waits for a queued job to finish.
Future<ContractRecord> loadCompatibilityReading(
  ProductionRepository repo,
  String reportId, {
  required String locale,
  Duration interval = readingPollInterval,
  Duration limit = readingPollLimit,
}) async {
  var answer = await repo.interpretCompatibility(reportId, locale: locale);
  if (answer.containsKey('prompt_version')) return ContractRecord(answer);

  final deadline = DateTime.now().add(limit);
  final jobId = answer['id'] as String;
  while (true) {
    final status = answer['status'] as String?;
    if (status == 'completed' && answer['report_id'] is String) {
      return ContractRecord(await repo.aiReport(answer['report_id'] as String));
    }
    if (status == 'failed' || status == 'cancelled') {
      throw ApiException(
        kind: ApiErrorKind.server,
        code: answer['error_code'] as String? ?? 'ai_provider_unavailable',
      );
    }
    if (DateTime.now().isAfter(deadline)) {
      throw const ApiException(kind: ApiErrorKind.timeout);
    }
    await Future<void>.delayed(interval);
    answer = await repo.reportJob(jobId);
  }
}

// ------------------------------------------------------------ labels

/// Turkish/English names for the engine's canonical values. Presentation
/// only: the wire values never change.
class RelationshipLabels {
  RelationshipLabels(this.context) : l10n = AppLocalizations.of(context);

  final BuildContext context;
  final AppLocalizations l10n;

  String body(String? wire) {
    if (wire == null) return '';
    if (const {'asc', 'dsc', 'mc', 'ic'}.contains(wire)) {
      return b12(context, 'angle_$wire');
    }
    final planet = _planet(wire);
    return planet == null ? wire : l10n.planet(planet);
  }

  String aspect(String? wire) {
    for (final type in AspectType.values) {
      if (type.name == wire) return _capitalized(l10n.aspect(type));
    }
    return wire ?? '';
  }

  /// "kavuşum" -> "Kavuşum", Turkish-aware (i -> İ).
  String _capitalized(String value) {
    if (value.isEmpty) return value;
    final first = value[0];
    final upper = l10n.localeName.startsWith('tr') && first == 'i'
        ? 'İ'
        : first.toUpperCase();
    return '$upper${value.substring(1)}';
  }

  String sign(String? wire) {
    for (final sign in ZodiacSign.values) {
      if (sign.name == wire) return l10n.sign(sign);
    }
    return wire ?? '';
  }

  String theme(String wire) => b12(context, 'rel_theme_$wire');

  String house(num? number) => number == null
      ? ''
      : b12(context, 'house_n').replaceAll('{n}', '${number.round()}');

  String degree(num degree, [num? minute]) => minute == null
      ? '${degree.toStringAsFixed(2)}°'
      : '${degree.round()}°${minute.round().toString().padLeft(2, '0')}′';

  Planet? _planet(String wire) {
    for (final planet in Planet.values) {
      if (ContractJson.snake(planet.name) == wire) return planet;
    }
    return null;
  }

  /// "Ay · Kavuşum · MC" for a composite/Davison aspect record.
  String chartAspect(ContractRecord a) =>
      '${body(a.optionalText('first'))} · ${aspect(a.optionalText('aspect'))} · ${body(a.optionalText('second'))}';

  /// "A Ay · Kavuşum · B MC" for a synastry contact.
  String synastryAspect(ContractRecord a, String nameA, String nameB) {
    final left = body(
      a.optionalText('person_a_body') ?? a.optionalText('person_a_angle'),
    );
    final right = body(
      a.optionalText('person_b_body') ?? a.optionalText('person_b_angle'),
    );
    return '$nameA $left · ${aspect(a.optionalText('aspect'))} · $nameB $right';
  }

  /// "A Güneş → B 1. ev" for a directional house overlay.
  String overlay(ContractRecord o, String nameA, String nameB) {
    final aToB = o.optionalText('direction') == 'a_to_b';
    final (from, to) = aToB ? (nameA, nameB) : (nameB, nameA);
    return '$from ${body(o.optionalText('planet'))} → $to ${house(o.json['house'] as num?)}';
  }

  String chartPlanet(ContractRecord p) {
    final parts = [
      body(p.optionalText('planet')),
      '${sign(p.optionalText('sign'))} ${degree(p.json['degree'] as num? ?? 0, p.json['minute'] as num?)}',
      if (p.json['house'] != null) house(p.json['house'] as num?),
      if (p.json['retrograde'] == true) 'R',
    ];
    return parts.join(' · ');
  }
}

/// Plain-language names for the factor ids a reading cites, taken from the
/// calculation the app already holds (nothing is fetched or invented).
class FactorNames {
  FactorNames(this.labels, this.result);

  final RelationshipLabels labels;
  final ContractRecord result;

  String _person(String key, String fallback) =>
      result.optionalText(key)?.trim().isNotEmpty == true
      ? result.optionalText(key)!.trim()
      : fallback;

  String? of(String id) {
    if (result is SynastryReport) {
      final report = result as SynastryReport;
      final a = _person('person_a_label', 'A');
      final b = _person('person_b_label', 'B');
      if (id == 'synastry:scores') {
        return b12(labels.context, 'factor_theme_scores');
      }
      for (final aspect in report.aspects) {
        if (aspect.optionalText('id') == id) {
          return labels.synastryAspect(aspect, a, b);
        }
      }
      for (final o in [...report.overlaysAInB, ...report.overlaysBInA]) {
        if (o.optionalText('id') == id) return labels.overlay(o, a, b);
      }
      return null;
    }
    final chart = (result as RelationshipChart).chart;
    final parts = id.split(':');
    if (parts.length == 2 && parts[1] == 'summary') {
      return b12(labels.context, 'factor_chart_summary');
    }
    if (parts.length == 3 && parts[1] == 'planet') {
      for (final p in chart.planets) {
        if (p.optionalText('planet') == parts[2]) return labels.chartPlanet(p);
      }
    }
    if (parts.length == 5 && parts[1] == 'aspect') {
      return '${labels.body(parts[2])} · ${labels.aspect(parts[4])} · ${labels.body(parts[3])}';
    }
    return null;
  }
}

// -------------------------------------------------------------- reading

const _sectionEmoji = {
  'overview': '✨',
  'love': '❤️',
  'communication': '💬',
  'emotional': '🌙',
  'passion': '🔥',
  'challenges': '🧱',
  'strengths': '🌱',
  'long_term': '🔮',
  'summary': '✨',
};

/// "AI Uyum Yorumu": loading skeleton, the reading cards, or a calm error
/// that leaves the calculation (below it) untouched.
class CompatibilityReadingView extends ConsumerWidget {
  const CompatibilityReadingView({
    super.key,
    required this.kind,
    required this.result,
  });

  final String kind;
  final ContractRecord result;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final reportId = result.optionalText('report_id');
    final header = _Header(kind: kind);
    if (reportId == null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          header,
          _Unavailable(message: b12(context, 'reading_unavailable')),
        ],
      );
    }
    final key = (reportId, Localizations.localeOf(context).languageCode);
    final value = ref.watch(compatibilityReadingProvider(key));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        header,
        AppSpacing.gapMd,
        value.when(
          loading: () => Semantics(
            liveRegion: true,
            label: b12(context, 'reading_loading'),
            child: Column(
              key: const ValueKey('reading-loading'),
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  b12(context, 'reading_loading'),
                  style: AppTypography.bodySmall.copyWith(
                    color: AppColors.goldBright,
                  ),
                ),
                AppSpacing.gapSm,
                const AstroSkeletonCard(lines: 4),
                AppSpacing.gapMd,
                const AstroSkeletonCard(lines: 3),
                AppSpacing.gapMd,
                const AstroSkeletonCard(lines: 3),
              ],
            ),
          ),
          error: (error, _) => _Unavailable(
            message: switch (error) {
              ApiException(code: 'ai_not_configured') => b12(
                context,
                'reading_ai_off',
              ),
              _ => b12(context, 'reading_failed'),
            },
            onRetry: switch (error) {
              ApiException(code: 'ai_not_configured') => null,
              _ => () => ref.invalidate(compatibilityReadingProvider(key)),
            },
          ),
          data: (report) => _Reading(report: report, result: result),
        ),
      ],
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.kind});
  final String kind;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Semantics(
        header: true,
        child: Text(
          b12(context, 'reading_title'),
          style: AppTypography.headlineMedium,
        ),
      ),
      const SizedBox(height: AppSpacing.xxs),
      Text(b12(context, 'reading_kind_$kind'), style: AppTypography.bodySmall),
    ],
  );
}

class _Unavailable extends StatelessWidget {
  const _Unavailable({required this.message, this.onRetry});
  final String message;
  final VoidCallback? onRetry;
  @override
  Widget build(BuildContext context) => AstroErrorCard(
    key: const ValueKey('reading-unavailable'),
    message: message,
    onRetry: onRetry,
  );
}

class _Reading extends StatelessWidget {
  const _Reading({required this.report, required this.result});
  final ContractRecord report;
  final ContractRecord result;

  @override
  Widget build(BuildContext context) {
    final names = FactorNames(RelationshipLabels(context), result);
    final sections = report.records('sections');
    final scope = report.optionalText('interpretation_scope');
    final safety = report.optionalText('safety_note');
    return Column(
      key: const ValueKey('reading-cards'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final section in sections) ...[
          _SectionCard(section: section, names: names),
          AppSpacing.gapMd,
        ],
        if (safety != null && safety.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: Text(safety, style: AppTypography.bodySmall),
          ),
        if (scope != null && scope.isNotEmpty)
          Text(
            scope,
            style: AppTypography.bodySmall.copyWith(
              color: AppColors.ivoryMuted,
              fontStyle: FontStyle.italic,
            ),
          ),
      ],
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.section, required this.names});
  final ContractRecord section;
  final FactorNames names;

  @override
  Widget build(BuildContext context) {
    final key = section.optionalText('key') ?? '';
    final known = _sectionEmoji.containsKey(key);
    final title = known
        ? b12(context, 'reading_section_$key')
        : (section.optionalText('title') ?? '');
    final factors = [
      for (final id in section.strings('factor_ids'))
        if (names.of(id) case final String label) label,
    ];
    return AstroCard(
      key: ValueKey('reading-section-$key'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (known)
                Padding(
                  padding: const EdgeInsets.only(right: AppSpacing.sm),
                  child: ExcludeSemantics(
                    child: Text(
                      _sectionEmoji[key]!,
                      style: const TextStyle(fontSize: 20),
                    ),
                  ),
                ),
              Expanded(
                child: Semantics(
                  header: true,
                  child: Text(title, style: AppTypography.titleMedium),
                ),
              ),
            ],
          ),
          AppSpacing.gapSm,
          Text(
            section.optionalText('body') ?? '',
            style: AppTypography.bodyMedium,
          ),
          if (factors.isNotEmpty)
            Theme(
              data: Theme.of(
                context,
              ).copyWith(dividerColor: Colors.transparent),
              child: ExpansionTile(
                tilePadding: EdgeInsets.zero,
                childrenPadding: const EdgeInsets.only(bottom: AppSpacing.xs),
                expandedCrossAxisAlignment: CrossAxisAlignment.start,
                iconColor: AppColors.gold,
                collapsedIconColor: AppColors.ivoryMuted,
                title: Text(
                  b12(context, 'reading_factors'),
                  style: AppTypography.labelMedium.copyWith(
                    color: AppColors.goldBright,
                  ),
                ),
                children: [
                  for (final label in factors)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 3),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Padding(
                            padding: EdgeInsets.only(top: 6, right: 8),
                            child: Icon(
                              Icons.circle,
                              size: 5,
                              color: AppColors.gold,
                            ),
                          ),
                          Expanded(
                            child: Text(label, style: AppTypography.bodySmall),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------- technical details

/// The raw calculation, localized, folded under the reading.
class CompatibilityTechnicalDetails extends StatelessWidget {
  const CompatibilityTechnicalDetails({
    super.key,
    required this.result,
    this.initiallyExpanded = false,
  });

  final ContractRecord result;
  final bool initiallyExpanded;

  @override
  Widget build(BuildContext context) {
    final labels = RelationshipLabels(context);
    final blocks = result is SynastryReport
        ? _synastry(context, labels, result as SynastryReport)
        : _chart(context, labels, result as RelationshipChart);
    return AstroCard(
      padding: EdgeInsets.zero,
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          key: const ValueKey('technical-details'),
          initiallyExpanded: initiallyExpanded,
          tilePadding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
          childrenPadding: const EdgeInsets.fromLTRB(
            AppSpacing.lg,
            0,
            AppSpacing.lg,
            AppSpacing.lg,
          ),
          expandedCrossAxisAlignment: CrossAxisAlignment.stretch,
          iconColor: AppColors.gold,
          collapsedIconColor: AppColors.ivoryMuted,
          title: Text(
            b12(context, 'technical_details'),
            style: AppTypography.titleMedium,
          ),
          children: blocks,
        ),
      ),
    );
  }

  List<Widget> _synastry(
    BuildContext context,
    RelationshipLabels labels,
    SynastryReport report,
  ) {
    final a = report.optionalText('person_a_label') ?? 'A';
    final b = report.optionalText('person_b_label') ?? 'B';
    return [
      _Block(
        title: b12(context, 'tech_index'),
        lines: ['${report.overallIndex} / 100', b12(context, 'index_note')],
      ),
      _Block(
        title: b12(context, 'tech_themes'),
        lines: [
          for (final t in report.themes)
            '${labels.theme(t.text('theme'))} · ${t.number('score').round()}',
        ],
      ),
      _Block(
        title: b12(context, 'tech_aspects'),
        lines: [
          for (final x in report.aspects)
            '${labels.synastryAspect(x, a, b)} · orb ${x.number('orb').toStringAsFixed(2)}°',
        ],
      ),
      _Block(
        title: b12(context, 'tech_overlays'),
        lines: [
          for (final o in [...report.overlaysAInB, ...report.overlaysBInA])
            labels.overlay(o, a, b),
        ],
      ),
      if (report.warnings.isNotEmpty)
        _Block(title: b12(context, 'warnings'), lines: report.warnings),
    ];
  }

  List<Widget> _chart(
    BuildContext context,
    RelationshipLabels labels,
    RelationshipChart result,
  ) {
    final chart = result.chart;
    final angles = chart.angles;
    return [
      if (result.warnings.isNotEmpty || chart.warnings.isNotEmpty)
        _Block(
          title: b12(context, 'warnings'),
          lines: [...result.warnings, ...chart.warnings],
        ),
      _Block(
        title: b12(context, 'tech_planets'),
        lines: [for (final p in chart.planets) labels.chartPlanet(p)],
      ),
      _Block(
        title: b12(context, 'tech_houses'),
        lines: chart.houses.isEmpty
            ? [b12(context, 'angles_unavailable')]
            : [
                for (final h in chart.houses)
                  '${labels.house(h.json['number'] as num?)} · ${labels.sign(h.optionalText('sign'))} ${labels.degree(h.json['degree'] as num? ?? 0, h.json['minute'] as num?)}',
              ],
      ),
      _Block(
        title: b12(context, 'tech_angles'),
        lines: angles == null
            ? [b12(context, 'angles_unavailable')]
            : [
                for (final (key, wire) in const [
                  ('ascendant', 'asc'),
                  ('midheaven', 'mc'),
                  ('descendant', 'dsc'),
                  ('imum_coeli', 'ic'),
                ])
                  if (angles.json[key] is num)
                    '${labels.body(wire)} · ${labels.sign(angles.optionalText('${key}_sign'))} · ${(angles.json[key] as num).toStringAsFixed(2)}°',
              ],
      ),
      _Block(
        title: b12(context, 'tech_aspects'),
        lines: [
          for (final x in chart.aspects)
            '${labels.chartAspect(x)} · orb ${x.number('orb').toStringAsFixed(2)}°',
        ],
      ),
      if (result.midpointUtc != null)
        _Block(
          title: b12(context, 'tech_midpoint'),
          lines: [instantLabel(result.midpointUtc!)],
        ),
      _Block(
        title: b12(context, 'tech_engine'),
        lines: [chart.text('engine_version'), chart.subject.text('moment_utc')],
      ),
    ];
  }
}

String instantLabel(DateTime value) => value.toUtc().toIso8601String();

class _Block extends StatelessWidget {
  const _Block({required this.title, required this.lines});
  final String title;
  final List<String> lines;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: AppSpacing.md),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: AppTypography.labelLarge.copyWith(color: AppColors.goldBright),
        ),
        const SizedBox(height: AppSpacing.xs),
        for (final line in lines)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: Text(line, style: AppTypography.bodySmall),
          ),
      ],
    ),
  );
}
