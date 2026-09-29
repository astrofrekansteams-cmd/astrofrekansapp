import 'package:astrofrekans/features/marketplace/data/marketplace_models.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_repository.dart';
import 'package:astrofrekans/features/marketplace/presentation/booking_screens.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/intl.dart';
import '../test/helpers/test_harness.dart' show disableAnimations;

// Asserts the observed defect, not the desired corrected behavior.
class ReviewMarketplace extends Fake implements MarketplaceRepository {
  final DateTime first = DateUtils.dateOnly(
    DateTime.now(),
  ).add(const Duration(hours: 12));
  BookingIntent? received;

  @override
  Future<List<ExpertService>> services(String expertId) async => [
    ExpertService({
      'id': 'service',
      'expert_id': expertId,
      'service_code': 'natal',
      'title': 'Review service',
      'delivery_type': 'video',
      'duration_minutes': 60,
      'price': {'amount_minor': 1000, 'currency': 'TRY'},
      'supports_appointment': true,
    }),
  ];

  @override
  Future<SlotPage> slots(
    String expertId,
    String serviceId,
    DateTime from,
    DateTime to,
  ) async => SlotPage({
    'expert_service_id': serviceId,
    'display_timezone': 'UTC',
    'slots': [
      for (final d in [first, first.add(const Duration(days: 1))])
        {
          'starts_at_utc': d.toUtc().toIso8601String(),
          'ends_at_utc': d
              .add(const Duration(hours: 1))
              .toUtc()
              .toIso8601String(),
          'display_timezone': 'UTC',
        },
    ],
  });

  @override
  Future<Order> createOrder(BookingIntent intent) async {
    received = intent;
    return Order({
      'id': 'review-order',
      'status': 'pending_payment',
      'payment_status': 'pending',
      'total': {'amount_minor': 1000, 'currency': 'TRY'},
    });
  }
}

void main() {
  testWidgets('changing booking date retains old selected slot', (
    tester,
  ) async {
    disableAnimations(tester);
    tester.view.physicalSize = const Size(1000, 1500);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final repo = ReviewMarketplace();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [marketplaceRepositoryProvider.overrideWithValue(repo)],
        child: const MaterialApp(
          home: BookingScreen(expertId: 'expert', serviceId: 'service'),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byType(ChoiceChip).first);
    await tester.pumpAndSettle();
    await tester.tap(find.byIcon(Icons.calendar_month));
    await tester.pumpAndSettle();
    await tester.tap(find.byIcon(Icons.edit_outlined));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byType(TextField).last,
      DateFormat('MM/dd/yyyy').format(repo.first.add(const Duration(days: 1))),
    );
    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();
    expect(
      tester.widget<ChoiceChip>(find.byType(ChoiceChip)).selected,
      isFalse,
    );
    final button = find.byType(FilledButton).first;
    expect(tester.widget<FilledButton>(button).onPressed, isNotNull);
    await tester.tap(button);
    await tester.pumpAndSettle();
    expect(repo.received?.startsUtc, repo.first.toUtc());
    expect(tester.takeException(), isNull);
  });
}
