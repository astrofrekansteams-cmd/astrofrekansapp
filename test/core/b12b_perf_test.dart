import 'dart:typed_data';

import 'package:astrofrekans/features/consultation/data/attachment_service.dart';
import 'package:astrofrekans/features/consultation/data/consultation_models.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'B12B host-side DTO and local-byte benchmark, not device frame latency',
    () {
      int measure(String label, void Function() work) {
        final watch = Stopwatch()..start();
        work();
        watch.stop();
        // Only synthetic local processing. No network, Firebase or GPU included.
        // ignore: avoid_print
        print('B12B_PERF $label=${watch.elapsedMicroseconds}us');
        return watch.elapsedMicroseconds;
      }

      final expert = <String, dynamic>{
        'id': '11111111-1111-4111-8111-111111111111',
        'display_name': 'Synthetic Expert',
        'languages': ['tr'],
        'specialties': ['astrology'],
        'experience_years': 7,
        'verified': true,
        'rating_average': 4.8,
        'rating_count': 12,
      };
      measure('marketplace_20_dto', () {
        final page = ExpertPage({
          'items': [
            for (var i = 0; i < 20; i++) {...expert, 'id': '$i'},
          ],
          'total': 20,
          'limit': 20,
          'offset': 0,
        });
        expect(page.items.length, 20);
      });
      measure('expert_detail_dto', () {
        expect(
          Expert({...expert, 'services': <Map<String, dynamic>>[]}).name,
          'Synthetic Expert',
        );
      });
      measure('slot_30_day_dto', () {
        final now = DateTime.utc(2026, 10, 1);
        final page = SlotPage({
          'expert_service_id': 'service',
          'display_timezone': 'Europe/Istanbul',
          'slots': [
            for (var i = 0; i < 240; i++)
              {
                'starts_at_utc': now
                    .add(Duration(hours: i * 3))
                    .toIso8601String(),
                'ends_at_utc': now
                    .add(Duration(hours: i * 3 + 1))
                    .toIso8601String(),
                'display_timezone': 'Europe/Istanbul',
              },
          ],
        });
        expect(page.slots.length, 240);
      });
      measure('chat_50_dto', () {
        final page = MessagePage({
          'items': [
            for (var i = 0; i < 50; i++)
              {
                'message_id': 'm$i',
                'sender_role': 'user',
                'message_type': 'text',
                'created_at': '2026-09-24T10:00:00Z',
                'text': 'Synthetic',
              },
          ],
          'has_more': false,
        });
        expect(page.items.length, 50);
      });
      measure('chat_one_append_dedupe', () {
        final messages = <String, ConsultationMessage>{
          for (var i = 0; i < 50; i++)
            'm$i': ConsultationMessage({
              'message_id': 'm$i',
              'sender_role': 'user',
              'created_at': '2026-09-24T10:00:00Z',
            }),
        };
        messages['m50'] = ConsultationMessage({
          'message_id': 'm50',
          'sender_role': 'expert',
          'created_at': '2026-09-24T10:01:00Z',
        });
        expect(messages.length, 51);
      });
      measure('attachment_8mib_local_copy', () {
        final bytes = Uint8List(maxImageBytes);
        final copy = Uint8List.fromList(bytes);
        expect(copy.length, maxImageBytes);
      });
    },
  );
}
