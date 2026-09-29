import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/core/astrology/data/api_contract_dto.dart';
import 'package:astrofrekans/core/astrology/data/production_repository.dart';
import 'package:astrofrekans/core/astrology/data/production_models.dart';
import 'package:astrofrekans/features/auth/data/api_auth_repository.dart';
import 'package:astrofrekans/features/auth/domain/auth_repository.dart';
import 'package:astrofrekans/features/astro_ai/data/api_astro_ai_repository.dart';

/// Explicit loopback-only smoke. Random credentials stay in process memory.
/// Generated fixtures contain only this disposable account's synthetic data.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'B12A local contracts and safe disposable-account cleanup',
    () async {
      HttpOverrides.global = null;
      const origin = 'http://127.0.0.1:8000';
      final probe = Dio(
        BaseOptions(
          baseUrl: origin,
          connectTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 10),
        ),
      );
      final health = await probe.get<Json>('/health');
      expect(health.data?['environment'], 'local');
      final openapi = (await probe.get<Json>('/api/v1/openapi.json')).data!;
      final paths = (openapi['paths'] as Map).keys.cast<String>().toList();
      expect(paths, contains('/api/v1/ai/chat/stream'));
      probe.close();
      final random = Random.secure();
      String randomString() =>
          List.generate(24, (_) => random.nextInt(16).toRadixString(16)).join();
      final email = 'codex-b12a-${randomString()}@example.com',
          password = '${randomString()}Aa9!';
      final store = InMemorySecureStore();
      final transport = buildDio(store: store, baseUrl: origin)
        ..options.receiveTimeout = const Duration(seconds: 90);
      final api = ApiClient(transport),
          repo = ProductionRepository(ApiClient(transport));
      final auth = ApiAuthRepository(api, store);
      final samples = <String, Object?>{};
      final timing = <String, int>{};
      bool registered = false;
      Future<T> measure<T>(String name, Future<T> Function() run) async {
        final watch = Stopwatch()..start();
        final result = await run();
        timing[name] = watch.elapsedMilliseconds;
        stdout.writeln('PASS $name ${timing[name]}ms');
        return result;
      }

      try {
        await auth.register(
          RegistrationRequest(
            name: 'B12A Synthetic',
            email: email,
            password: password,
            birthDate: DateTime(1992, 5, 14),
            birthTime: '14:30',
          ),
        );
        registered = true;
        await auth.signOut();
        await auth.signIn(email: email, password: password);
        await api.putMap(
          'birth-profiles/me',
          data: {
            'birth_date': '1992-05-14',
            'birth_time': '14:30:00',
            'latitude': 41.0082,
            'longitude': 28.9784,
            'timezone': 'Europe/Istanbul',
            'birth_place': 'Synthetic Istanbul',
          },
        );
        NatalChartDto.fromJson(
          await measure(
            'natal_remote',
            () => api.getMap('astrology/natal-chart/me'),
          ),
        ).toDomain();
        TransitListDto.fromJson(
          await measure(
            'transits_remote',
            () => api.getMap(
              'astrology/transits',
              queryParameters: {'date': '2026-09-24', 'range': 'day'},
            ),
          ),
        ).toWindow();
        DailyFrequencyDto.fromJson(
          await measure(
            'daily_remote',
            () => api.getMap(
              'astrology/daily-frequency',
              queryParameters: {'date': '2026-09-24'},
            ),
          ),
        ).toDomain();
        samples['calendar_personal'] = await measure(
          'calendar_personal',
          () => api.getMap(
            'calendar/personal',
            queryParameters: {'start': '2026-09-01', 'end': '2026-10-01'},
          ),
        );
        final saved = await repo.createPerson({
          'name': 'Synthetic Partner',
          'relation': 'friend',
          'birth_date': '1990-11-02',
          'birth_time': '09:15:00',
          'latitude': 40.4093,
          'longitude': 49.8671,
          'timezone': 'Asia/Baku',
        });
        expect((await repo.person(saved.id)).id, saved.id);
        samples['saved_person'] = (await api.getList(
          'saved-people',
        )).firstWhere((p) => p['id'] == saved.id);
        final q = await measure(
          'horary_create',
          () => repo.createQuestion({
            'question': 'Will this synthetic project finish?',
            'category': 'career',
            'asked_at': '2026-09-24T10:00:00Z',
            'latitude': 41.0082,
            'longitude': 28.9784,
            'timezone': 'Europe/Istanbul',
          }),
        );
        samples['horary_question'] = q.json;
        await repo.calculate(q.id);
        samples['horary_analysis'] = (await measure(
          'horary_analysis',
          () => repo.analysis(q.id),
        )).json;
        final person = <String, dynamic>{
          'birth_date': '1990-11-02',
          'birth_time': '09:15:00',
          'latitude': 40.4093,
          'longitude': 49.8671,
          'timezone': 'Asia/Baku',
          'label': 'Synthetic Partner',
        };
        samples['synastry'] = (await measure(
          'synastry',
          () => repo.synastry(person),
        )).json;
        expect(
          (await repo.synastry({'saved_person_id': saved.id})).overallIndex,
          inInclusiveRange(0, 100),
        );
        samples['composite'] = (await measure(
          'composite',
          () => repo.relationshipChart('composite', person),
        )).json;
        samples['davison'] = (await measure(
          'davison',
          () => repo.relationshipChart('davison', person),
        )).json;
        await repo.deletePerson(saved.id);
        expect(
          (await repo.savedPeople()).where((p) => p.id == saved.id),
          isEmpty,
        );
        samples['decks'] = (await repo.decks()).map((d) => d.json).toList();
        for (final deck in DeckType.values) {
          final spreads = await repo.spreads(deck, 'tr');
          samples['${deck.name}_spreads'] = spreads.map((s) => s.json).toList();
          final reading = await measure(
            '${deck.name}_draw',
            () => repo.draw(deck, spreads.first.code),
          );
          expect((await repo.reading(reading.id)).json, reading.json);
          samples['${deck.name}_reading'] = reading.json;
        }
        final ai = ApiAstroAIRepository(api);
        samples['ai_status'] = await ai.status();
        samples['ai_conversation'] = (await ai.createConversation(
          title: 'Synthetic contract test',
        )).json;
        expect(await ai.messages(ai.conversationId!), isEmpty);
        expect((await ai.conversations()).length, 1);
        final expert = await api.getMap(
          'experts',
          queryParameters: {'limit': 1},
        );
        samples['expert_search'] = expert;
        if ((samples['ai_status'] as Json)['configured'] == false) {
          try {
            await ai.chat('Merhaba');
            fail('Expected AI unavailable');
          } on ApiException catch (e) {
            expect(e.code, 'ai_not_configured');
            samples['ai_unavailable'] = {
              'code': e.code,
              'status': e.statusCode,
            };
          }
        }
        // No provider generation is requested by this smoke when configured.
        final idMap = <String, String>{};
        Object? sanitize(Object? value) {
          if (value is Map) {
            return <String, Object?>{
              for (final e in value.entries)
                if (!RegExp(
                  r'email|token|password|secret|authorization',
                  caseSensitive: false,
                ).hasMatch(e.key as String))
                  e.key as String: sanitize(e.value),
            };
          }
          if (value is List) return value.map(sanitize).toList();
          if (value is String &&
              RegExp(r'^[0-9a-f]{8}-[0-9a-f-]{27}$').hasMatch(value)) {
            return idMap.putIfAbsent(
              value,
              () =>
                  '00000000-0000-4000-8000-${(idMap.length + 1).toString().padLeft(12, '0')}',
            );
          }
          return value;
        }

        await File(
          'test/fixtures/live_b5_b11_contract_samples.json',
        ).writeAsString(
          const JsonEncoder.withIndent('  ').convert({
            'provenance': 'loopback B1-B11 API, synthetic disposable account',
            'captured_at': DateTime.now().toUtc().toIso8601String(),
            'sanitized': true,
            'responses': sanitize(samples),
          }),
        );
        await File('reports/b12a_live_timings.json').writeAsString(
          const JsonEncoder.withIndent('  ').convert({
            'kind':
                'remote HTTP durations from Flutter test runtime, NOT device startup/frame measurements',
            'milliseconds': timing,
          }),
        );
      } finally {
        if (registered) {
          await api.delete('users/me');
          stdout.writeln('PASS disposable account soft-deleted');
        }
        transport.close(force: true);
      }
    },
    timeout: const Timeout(Duration(minutes: 12)),
  );
}
