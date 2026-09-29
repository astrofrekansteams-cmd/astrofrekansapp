import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:astrofrekans/core/assets/divination_asset_resolver.dart';
import 'package:astrofrekans/core/astrology/data/production_models.dart';
import 'package:astrofrekans/features/astro_ai/data/ai_models.dart';

void main() {
  final live =
      jsonDecode(
            File(
              'test/fixtures/live_b5_b11_contract_samples.json',
            ).readAsStringSync(),
          )
          as Json;
  final samples = live['responses'] as Json;
  final schema =
      jsonDecode(
            File('test/fixtures/b12a_schema_samples.json').readAsStringSync(),
          )
          as Json;
  test(
    'B5 horary retains signifiers Moon dignity reception perfection obstruction warnings',
    () {
      final question = HoraryQuestion(samples['horary_question'] as Json);
      final a = HoraryAnalysis(samples['horary_analysis'] as Json);
      expect(a.text('question_id'), question.id);
      expect(a.querent.planet, isNotEmpty);
      expect(a.quesited.planet, isNotEmpty);
      expect(a.moon.text('phase'), isNotEmpty);
      expect(a.querent.essential, isNotNull);
      expect(a.querent.accidental, isNotNull);
      expect(a.receptions, isA<List<ContractRecord>>());
      expect(a.dignities, isA<List<ContractRecord>>());
      expect(a.perfection, isA<List<ContractRecord>>());
      expect(a.obstructions, isA<List<ContractRecord>>());
      expect(a.warnings, isA<List<ContractRecord>>());
      expect(a.json.containsKey('verdict'), isFalse);
      expect(() => a.json['question'] = 'changed', throwsUnsupportedError);
    },
  );
  test(
    'synastry is an index; cross-chart angles nodes and directional overlays retained',
    () {
      final s = SynastryReport(samples['synastry'] as Json);
      expect(s.overallIndex, inInclusiveRange(0, 100));
      expect(s.scoreSemantics, isNotEmpty);
      expect(s.themes, isNotEmpty);
      expect(s.aspects, isNotEmpty);
      expect(s.overlaysAInB, isNotEmpty);
      expect(s.overlaysBInA, isNotEmpty);
      expect(
        s.aspects.any(
          (a) =>
              a.optionalText('person_a_angle') != null ||
              a.optionalText('person_b_angle') != null,
        ),
        isTrue,
      );
      expect(
        s.aspects.any(
          (a) => [
            a.optionalText('person_a_body'),
            a.optionalText('person_b_body'),
          ].any((v) => v == 'north_node' || v == 'south_node'),
        ),
        isTrue,
      );
    },
  );
  test(
    'composite and Davison charts preserve server geometry and warnings',
    () {
      final composite = RelationshipChart(samples['composite'] as Json),
          davison = RelationshipChart(samples['davison'] as Json);
      expect(composite.chart.planets.length, 12);
      expect(composite.ambiguousMidpoints, isA<List<String>>());
      expect(davison.chart.planets.length, 12);
      expect(davison.midpointUtc, isNotNull);
      expect(davison.warnings, isA<List<String>>());
    },
  );
  test('all three server draws resolve into the existing bundled assets', () {
    final assets = Directory('assets')
        .listSync(recursive: true)
        .whereType<File>()
        .map((f) => f.path.replaceAll('\\', '/'));
    final resolver = DivinationAssetResolver(assets);
    for (final type in DeckType.values) {
      final reading = DivinationReading(
        samples['${type.name}_reading'] as Json,
      );
      expect(reading.items, isNotEmpty);
      for (final item in reading.items) {
        expect(resolver.resolve(type.name, item.assetKey), isNotNull);
        expect(item.position, isNotEmpty);
      }
      expect(
        () => (reading.json['items'] as List<dynamic>).add(<String, dynamic>{}),
        throwsUnsupportedError,
      );
    }
    expect(resolver.resolve('tarot', '../../secret'), isNull);
    expect(resolver.resolve('rune', 'C:/secret'), isNull);
    expect(resolver.resolve('tarot', 'unknown_key'), isNull);
  });
  test(
    'AI live conversation and schema report/message preserve provenance',
    () {
      expect(AIConversation(samples['ai_conversation'] as Json).id, isNotEmpty);
      final report = AIReport(schema['ai_report'] as Json),
          message = AIMessage(schema['ai_message'] as Json);
      expect(report.sections.single.strings('factor_ids'), [
        'natal:planet:sun',
      ]);
      expect(message.completionStatus, 'partial');
      expect(message.factorIds, ['natal:planet:sun']);
      for (final status in [
        'queued',
        'running',
        'completed',
        'failed',
        'cancelled',
        'future_status',
      ]) {
        final job = AIReportJob({'id': 'job', 'status': status});
        expect(job.terminal, !['queued', 'running'].contains(status));
      }
    },
  );
  test(
    'B8 public expert money remains integer minor units, no identity PII',
    () {
      final expert = PublicExpert(schema['expert'] as Json);
      expect(expert.fromPriceMinor, 1999);
      expect(expert.currency, 'TRY');
      expect(expert.json.containsKey('email'), isFalse);
    },
  );
}
