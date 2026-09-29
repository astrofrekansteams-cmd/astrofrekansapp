import 'dart:convert';
import 'dart:io';

import 'package:astrofrekans/core/astrology/data/production_models.dart';
import 'package:astrofrekans/core/astrology/data/production_repository.dart';
import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/core/storage/app_preferences.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/core/widgets/api_state_view.dart';
import 'package:astrofrekans/features/billing/application/entitlement_service.dart';
import 'package:astrofrekans/features/production/application/core_providers.dart';
import 'package:astrofrekans/features/production/presentation/relationship_screens.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';

/// Real response shapes captured from the local API (seed test user +
/// synthetic person B). "unknown_time" = person B without a birth time.
final Map<String, dynamic> _samples =
    (jsonDecode(
              File(
                'test/fixtures/relationship_contract_samples.json',
              ).readAsStringSync(),
            )
            as Map<String, dynamic>)['responses']
        as Map<String, dynamic>;

Json _body(String name) => Map<String, dynamic>.from(
  (_samples[name] as Map<String, dynamic>)['body'] as Map,
);

typedef _Interpret = Future<Json> Function(String reportId);

Future<Json> _aiOff(String _) async => throw const ApiException(
  kind: ApiErrorKind.server,
  statusCode: 503,
  code: 'ai_not_configured',
);

class _FakeRepo extends ProductionRepository {
  _FakeRepo(this.respond, {this.onInterpret = _aiOff, this.jobs = const []})
    : super(ApiClient(Dio()));
  final Future<ContractRecord> Function(String kind) respond;
  final _Interpret onInterpret;
  final List<Json> jobs;
  int jobPolls = 0;
  final interpreted = <String>[];

  @override
  Future<Json> interpretCompatibility(
    String reportId, {
    String locale = 'tr',
    bool refresh = false,
  }) {
    interpreted.add(reportId);
    return onInterpret(reportId);
  }

  @override
  Future<Json> reportJob(String id) async => jobs[jobPolls++];

  @override
  Future<Json> aiReport(String id) async => _readingFor('composite', id);

  @override
  Future<SynastryReport> synastry(
    Json personB, {
    Json personA = const {'me': true},
    String? coinRef,
  }) async => await respond('synastry') as SynastryReport;

  @override
  Future<RelationshipChart> relationshipChart(
    String kind,
    Json personB, {
    Json personA = const {'me': true},
    String? coinRef,
  }) async => await respond(kind) as RelationshipChart;
}

/// A report shaped like `/ai/reports/{id}`, citing real factor ids of the
/// calculation the screen holds.
Json _readingFor(String kind, String id) {
  final ids = switch (kind) {
    'synastry' => [
      for (final a in (_body('synastry_full')['aspects'] as List).take(2))
        (a as Map)['id'] as String,
    ],
    _ => ['$kind:planet:sun', '$kind:aspect:moon:mercury:conjunction'],
  };
  return {
    'id': id,
    'report_type': '${kind}_reading',
    'source_type': 'compatibility_report',
    'status': 'completed',
    'title': 'Başlık',
    'summary': 'Özet',
    'sections': [
      for (final key in [
        'overview',
        'love',
        'communication',
        'emotional',
        'passion',
        'challenges',
        'strengths',
        'long_term',
        'summary',
      ])
        {
          'key': key,
          'title': 'model title $key',
          'body': 'Gövde $key',
          'factor_ids': key == 'summary' ? <String>[] : ids,
          'general_summary': key == 'summary',
        },
    ],
    'warnings': <String>[],
    'interpretation_scope': 'Yansıtma içindir, kehanet değildir.',
    'prompt_version': '${kind}_reading_v1',
    'context_version': 'v1',
    'engine_version': 'e',
    'provider': 'fake',
    'model': 'fake',
    'cached': false,
    'created_at': '2026-09-27T00:00:00Z',
  };
}

Future<_FakeRepo> _pumpScreen(
  WidgetTester tester,
  String kind,
  Future<ContractRecord> Function(String kind) respond, {
  _Interpret interpret = _aiOff,
  List<Json> jobs = const [],
}) async {
  final repo = _FakeRepo(respond, onInterpret: interpret, jobs: jobs);
  tester.view.physicalSize =
      const Size(390, 6000) * tester.view.devicePixelRatio;
  addTearDown(tester.view.reset);
  disableAnimations(tester);
  final env = await TestEnv.create();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        appPreferencesProvider.overrideWithValue(env.preferences),
        secureStoreProvider.overrideWithValue(env.store),
        productionRepositoryProvider.overrideWithValue(repo),
        savedPeopleProvider.overrideWith((ref) async => []),
        entitlementServiceProvider.overrideWithValue(
          const EntitlementService(catalogue: null, premium: true),
        ),
      ],
      child: MaterialApp(
        theme: AppTheme.dark,
        locale: const Locale('tr'),
        supportedLocales: AppLocalizations.supportedLocales,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        home: CompatibilityScreen(personId: 'p1', initialKind: kind),
      ),
    ),
  );
  await tester.pumpAndSettle();
  await tester.tap(find.text('Hesapla'));
  await tester.pumpAndSettle();
  return repo;
}

void main() {
  group('relationship DTOs parse the real response shapes', () {
    test('composite with unknown birth time: angles is null', () {
      final chart = RelationshipChart(_body('composite_unknown_time'));
      expect(chart.chart.json['birth_data'], isNull);
      expect(chart.chart.angles, isNull);
      expect(chart.chart.planets, isNotEmpty);
      expect(chart.midpointUtc, isNull);
      expect(chart.warnings, isA<List<String>>());
    });

    test('composite and davison with full data keep their angles', () {
      final composite = RelationshipChart(_body('composite_full'));
      expect(composite.chart.angles, isNotNull);
      expect(composite.chart.houses, hasLength(12));
      final davison = RelationshipChart(_body('davison_full'));
      expect(davison.chart.angles, isNotNull);
      expect(davison.midpointUtc, isNotNull);
      expect(davison.chart.subject.text('moment_utc'), isNotEmpty);
    });

    test('synastry with nullable bodies/angles and null labels', () {
      final report = SynastryReport(_body('synastry_unknown_time'));
      expect(report.aspects, isNotEmpty);
      final aspect = report.aspects.first;
      expect(aspect.optionalText('person_a_angle'), isNull);
      expect(aspect.text('label'), isNotEmpty);
      expect(report.themes, isNotEmpty);
      // Labels are nullable in the contract.
      final unlabeled = SynastryReport({
        ..._body('synastry_unknown_time'),
        'person_a_label': null,
        'person_b_label': null,
      });
      expect(unlabeled.optionalText('person_a_label'), isNull);
      expect(unlabeled.overallIndex, report.overallIndex);
    });

    test('missing optional keys and empty lists do not crash', () {
      final body = _body('composite_unknown_time')
        ..remove('warnings')
        ..remove('ambiguous_midpoints')
        ..remove('aspects');
      final chartJson = Map<String, dynamic>.from(body['chart'] as Map)
        ..['houses'] = <dynamic>[]
        ..remove('aspects')
        ..remove('warnings');
      body['chart'] = chartJson;
      final chart = RelationshipChart(body);
      expect(chart.warnings, isEmpty);
      expect(chart.ambiguousMidpoints, isEmpty);
      expect(chart.chart.houses, isEmpty);
      expect(chart.chart.aspects, isEmpty);
      expect(chart.chart.warnings, isEmpty);
      expect(chart.chart.angles, isNull);
    });

    test('davison without a birth time is a typed 422, not a 500', () {
      final sample = _samples['davison_unknown_time'] as Map<String, dynamic>;
      expect(sample['status'], 422);
      expect(
        ((sample['body'] as Map)['error'] as Map)['code'],
        'missing_birth_data',
      );
    });
  });

  group('compatibility screen', () {
    testWidgets('composite with null angles renders without an error', (
      tester,
    ) async {
      await _pumpScreen(
        tester,
        'composite',
        (_) async => RelationshipChart(_body('composite_unknown_time')),
      );
      expect(tester.takeException(), isNull);
      expect(find.byType(ErrorWidget), findsNothing);
      expect(
        find.text(
          'Doğum saati veya yeri bilinmediği için yükselen, MC ve evler hesaplanamadı.',
        ),
        findsWidgets,
      );
    });

    testWidgets('davison 422 shows the missing-birth-data message', (
      tester,
    ) async {
      await _pumpScreen(
        tester,
        'davison',
        (_) async => throw const ApiException(
          kind: ApiErrorKind.validation,
          statusCode: 422,
          code: 'missing_birth_data',
        ),
      );
      expect(tester.takeException(), isNull);
      expect(
        find.text('Bu hesaplama için doğum tarihi, saati ve yeri gerekli.'),
        findsOneWidget,
      );
    });

    testWidgets('synastry with nullable aspect fields renders', (tester) async {
      await _pumpScreen(
        tester,
        'synastry',
        (_) async => SynastryReport({
          ..._body('synastry_unknown_time'),
          'person_a_label': null,
          'person_b_label': null,
        }),
      );
      expect(tester.takeException(), isNull);
      expect(find.byType(ErrorWidget), findsNothing);
    });
  });

  testWidgets('a contract violation in ApiStateView is reported, not shown '
      'as a crash screen', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        locale: const Locale('tr'),
        supportedLocales: AppLocalizations.supportedLocales,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        home: Scaffold(
          body: ApiStateView<Json>(
            value: const AsyncData({'angles': null}),
            onRetry: () {},
            builder: (json) =>
                Text(ContractRecord(json).record('angles').text('x')),
          ),
        ),
      ),
    );
    // The real exception still reaches FlutterError (logs / crash reporting).
    expect(tester.takeException(), isA<TypeError>());
    expect(find.text('Bu bölüm yüklenemedi.'), findsOneWidget);
    expect(find.text('Tekrar dene'), findsOneWidget);
    expect(find.byType(ErrorWidget), findsNothing);
  });

  group('AI compatibility reading', () {
    testWidgets('reading cards come first; technical details are folded', (
      tester,
    ) async {
      final repo = await _pumpScreen(
        tester,
        'composite',
        (_) async => RelationshipChart({
          ..._body('composite_unknown_time'),
          'report_id': 'rep-1',
        }),
        interpret: (id) async => _readingFor('composite', id),
      );
      expect(tester.takeException(), isNull);
      expect(repo.interpreted, ['rep-1']);
      expect(find.text('AI Uyum Yorumu'), findsOneWidget);
      // Our own section titles (the model's titles are not trusted for UI).
      for (final title in [
        'İlişkinizin Genel Dinamiği',
        'Aşk ve Çekim',
        'İletişim',
        'Duygusal Bağ',
        'Tutku ve Fiziksel Çekim',
        'Zorlayıcı Alanlar',
        'İlişkinin Güçlü Tarafları',
        'Uzun Vadeli Dinamik',
        'Astro AI Özeti',
      ]) {
        expect(find.text(title), findsOneWidget, reason: title);
      }
      expect(find.textContaining('model title'), findsNothing);
      // Reading above the calculation.
      expect(
        tester.getTopLeft(find.text('AI Uyum Yorumu')).dy,
        lessThan(tester.getTopLeft(find.text('Teknik Astroloji Detayları')).dy),
      );
      // Calculation folded: planets not on screen until opened.
      expect(find.textContaining('Güneş · '), findsNothing);

      // "Bu yorumu oluşturan etkiler" names the cited factors in Turkish.
      await tester.tap(find.text('Bu yorumu oluşturan etkiler').first);
      await tester.pumpAndSettle();
      expect(find.textContaining('Güneş · '), findsOneWidget);
      expect(find.text('Ay · Kavuşum · Merkür'), findsOneWidget);

      // Technical details: localized, no raw engine words.
      await tester.tap(find.text('Teknik Astroloji Detayları'));
      await tester.pumpAndSettle();
      expect(find.text('Gezegenler'), findsOneWidget);
      expect(find.textContaining('Kavuşum'), findsWidgets);
      for (final raw in [
        'sun ·',
        'moon ·',
        ' conjunction ',
        ' sextile ',
        ' square ',
      ]) {
        expect(find.textContaining(raw), findsNothing, reason: raw);
      }
    });

    testWidgets('a queued reading is polled until it completes', (
      tester,
    ) async {
      final repo = await _pumpScreen(
        tester,
        'davison',
        (_) async =>
            RelationshipChart({..._body('davison_full'), 'report_id': 'rep-2'}),
        interpret: (id) async => {'id': 'job-1', 'status': 'queued'},
        jobs: [
          {'id': 'job-1', 'status': 'running'},
          {'id': 'job-1', 'status': 'completed', 'report_id': 'ai-9'},
        ],
      );
      await tester.pump(const Duration(seconds: 5));
      await tester.pumpAndSettle();
      expect(repo.jobPolls, 2);
      expect(find.text('Astro AI Özeti'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('an AI failure keeps the calculation, opened', (tester) async {
      await _pumpScreen(
        tester,
        'composite',
        (_) async => RelationshipChart({
          ..._body('composite_full'),
          'report_id': 'rep-3',
        }),
        interpret: (_) async => throw const ApiException(
          kind: ApiErrorKind.server,
          statusCode: 502,
          code: 'ai_provider_unavailable',
        ),
      );
      expect(tester.takeException(), isNull);
      expect(
        find.text('Yorum şu an oluşturulamadı. Astrolojik hesaplama aşağıda.'),
        findsOneWidget,
      );
      expect(find.text('Tekrar dene'), findsOneWidget);
      // Opened automatically: the calculation is visible without a tap.
      expect(find.text('Gezegenler'), findsOneWidget);
      expect(find.textContaining('Güneş · '), findsWidgets);
    });

    testWidgets('AI switched off: a plain note, no retry, calculation shown', (
      tester,
    ) async {
      await _pumpScreen(
        tester,
        'synastry',
        (_) async =>
            SynastryReport({..._body('synastry_full'), 'report_id': 'rep-4'}),
      );
      expect(
        find.text('Astro AI bu sunucuda kapalı. Astrolojik hesaplama aşağıda.'),
        findsOneWidget,
      );
      expect(find.text('Tekrar dene'), findsNothing);
      expect(find.text('Açılar'), findsOneWidget);
    });

    testWidgets('synastry factors name both people and the contact', (
      tester,
    ) async {
      await _pumpScreen(
        tester,
        'synastry',
        (_) async => SynastryReport({
          ..._body('synastry_full'),
          'report_id': 'rep-5',
          'person_a_label': 'Ece',
          'person_b_label': 'Can',
        }),
        interpret: (id) async => _readingFor('synastry', id),
      );
      await tester.tap(find.text('Bu yorumu oluşturan etkiler').first);
      await tester.pumpAndSettle();
      // First fixture contact: a_moon conjunction b_mc.
      expect(find.text('Ece Ay · Kavuşum · Can MC'), findsOneWidget);
    });
  });
}
