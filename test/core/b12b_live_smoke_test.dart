import 'dart:io';
import 'dart:math';

import 'package:astrofrekans/core/network/api_client.dart';
import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/core/storage/secure_storage.dart';
import 'package:astrofrekans/features/auth/data/api_auth_repository.dart';
import 'package:astrofrekans/features/auth/domain/auth_repository.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_repository.dart';
import 'package:astrofrekans/features/consultation/data/consultation_repository.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'B12B loopback smoke with disposable local account',
    () async {
      HttpOverrides.global = null;
      const origin = 'http://127.0.0.1:8000';
      final probe = Dio(
        BaseOptions(
          baseUrl: origin,
          connectTimeout: const Duration(seconds: 5),
        ),
      );
      expect(
        (await probe.get<Map<String, dynamic>>('/health')).data?['environment'],
        'local',
      );
      probe.close();
      final random = Random.secure();
      String randomPart() =>
          List.generate(24, (_) => random.nextInt(16).toRadixString(16)).join();
      final email = 'codex-b12b-${randomPart()}@example.com';
      final password = '${randomPart()}Aa9!';
      final store = InMemorySecureStore();
      final transport = buildDio(store: store, baseUrl: origin);
      final api = ApiClient(transport);
      final auth = ApiAuthRepository(api, store);
      final market = ApiMarketplaceRepository(api);
      final chat = ApiConsultationRepository(api);
      var registered = false;
      try {
        await auth.register(
          RegistrationRequest(
            name: 'B12B Synthetic',
            email: email,
            password: password,
            birthDate: DateTime(1992, 5, 14),
          ),
        );
        registered = true;
        final capabilities = await api.getMap('auth/capabilities');
        stdout.writeln(
          'B12B firebase_configured=${capabilities['firebase_configured']}',
        );
        final page = await market.search(const ExpertQuery(limit: 10));
        stdout.writeln('B12B experts=${page.total}');
        expect(page.items.length, lessThanOrEqualTo(10));
        stdout.writeln('B12B GET favorites');
        expect(await market.favorites(), isEmpty);
        stdout.writeln('B12B GET orders');
        expect(await market.orders(), isEmpty);
        stdout.writeln('B12B GET appointments');
        expect(await market.appointments(), isEmpty);
        stdout.writeln('B12B GET conversations');
        if (capabilities['firebase_configured'] == true) {
          expect(await chat.conversations(), isEmpty);
        } else {
          try {
            expect(await chat.conversations(), isEmpty);
          } on ApiException catch (error) {
            expect(error.statusCode, 503);
            stdout.writeln(
              'B12B conversations controlled unavailable code=${error.code}',
            );
          }
        }
        final policy = await chat.policy();
        expect(policy.maxMessageLength, greaterThan(0));
        if (page.items.isNotEmpty) {
          final expert = await market.detail(page.items.first.id);
          final services = await market.services(expert.id);
          final reviews = await market.reviews(expert.id);
          stdout.writeln(
            'B12B services=${services.length} reviews=${reviews.total}',
          );
          await market.setFavorite(expert.id, true);
          expect(
            (await market.favorites()).any((x) => x.id == expert.id),
            isTrue,
          );
          await market.setFavorite(expert.id, false);
          expect(
            (await market.favorites()).any((x) => x.id == expert.id),
            isFalse,
          );
          for (final service in services.take(1)) {
            final from = DateTime.now().toUtc();
            final slots = await market.slots(
              expert.id,
              service.id,
              from,
              from.add(const Duration(days: 7)),
            );
            stdout.writeln('B12B slots=${slots.slots.length}');
            if (!service.supportsAppointment || slots.slots.isNotEmpty) {
              final intent = BookingIntent(
                serviceId: service.id,
                startsUtc: service.supportsAppointment
                    ? slots.slots.first.startsUtc
                    : null,
              );
              final order = await market.createOrder(intent);
              try {
                final detail = await market.order(order.id);
                stdout.writeln(
                  'B12B order=${detail.status.name} payment=${detail.paymentStatus}',
                );
                expect(detail.id, order.id);
                expect(detail.reviewEligible, isFalse);
                expect(await market.consents(order.id), isEmpty);
                final granted = await market.setConsents(order.id, {
                  'share_birth_profile',
                });
                expect(granted.any((c) => c.active), isTrue);
                final revoked = await market.setConsents(order.id, {});
                expect(revoked.any((c) => c.active), isFalse);
              } finally {
                await market.cancelOrder(order.id);
                stdout.writeln('B12B synthetic order cancelled');
              }
            }
          }
        }
      } finally {
        if (registered) {
          await api.delete('users/me');
          stdout.writeln('B12B disposable account soft-deleted');
        }
        transport.close(force: true);
      }
    },
    skip: Platform.environment['B12B_LIVE'] != '1',
    timeout: const Timeout(Duration(minutes: 3)),
  );
}
