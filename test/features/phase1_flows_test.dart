// Phase 1 critical user flows, client side: a stale slot can never be booked,
// cancelling says what happens to the money, refund states are visible, a
// payment refreshes the order around it, and password reset is honest.
import 'package:astrofrekans/core/theme/app_theme.dart';
import 'package:astrofrekans/features/auth/data/password_reset_service.dart';
import 'package:astrofrekans/features/auth/presentation/password_reset_screens.dart';
import 'package:astrofrekans/features/billing/application/entitlement_controller.dart';
import 'package:astrofrekans/features/billing/data/billing_models.dart';
import 'package:astrofrekans/features/billing/data/billing_repository.dart';
import 'package:astrofrekans/features/billing/data/billing_service.dart';
import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_models.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_repository.dart';
import 'package:astrofrekans/features/marketplace/presentation/booking_screens.dart';
import 'package:astrofrekans/l10n/generated/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/intl.dart';

import '../helpers/test_harness.dart' show disableAnimations;

Map<String, dynamic> orderJson({
  String id = 'order-1',
  String status = 'confirmed',
  String paymentStatus = 'paid',
  String lifecycle = 'scheduled',
  String delivery = 'video',
  Map<String, dynamic>? actions,
  Map<String, dynamic>? refund,
  Map<String, dynamic>? cancellation,
  DateTime? startsUtc,
  String appointmentStatus = 'confirmed',
}) {
  final starts =
      startsUtc ?? DateTime.now().toUtc().add(const Duration(days: 2));
  return {
    'id': id,
    'service_code': 'natal_consult',
    'service_title': 'Doğum haritası danışmanlığı',
    'status': status,
    'payment_status': paymentStatus,
    'delivery_type': delivery,
    'total': {'amount_minor': 99900, 'currency': 'TRY'},
    'expert_id': 'expert-1',
    'expert_display_name': 'Ayşe Demir',
    'lifecycle': lifecycle,
    'actions':
        actions ??
        {
          'can_cancel': true,
          'can_complete': false,
          'can_deliver': false,
          'review_eligible': false,
        },
    'refund': refund,
    'cancellation':
        cancellation ??
        {
          'allowed': true,
          'refund_outcome': 'refund_review',
          'refundable_minor': 99900,
          'currency': 'TRY',
        },
    'appointment': {
      'id': 'appt-1',
      'expert_id': 'expert-1',
      'expert_service_id': 'service-1',
      'service_order_id': id,
      'starts_at_utc': starts.toIso8601String(),
      'ends_at_utc': starts.add(const Duration(hours: 1)).toIso8601String(),
      'timezone': 'Europe/Istanbul',
      'status': appointmentStatus,
    },
    'timeline': [
      {'event': 'created', 'at': '2026-09-20T10:00:00Z'},
    ],
  };
}

class FakeMarketplace extends Fake implements MarketplaceRepository {
  FakeMarketplace({Map<String, dynamic>? order}) : current = order;
  final DateTime first = DateUtils.dateOnly(
    DateTime.now(),
  ).add(const Duration(hours: 12));
  Map<String, dynamic>? current;
  final List<BookingIntent> intents = [];
  int cancels = 0, orderReads = 0;
  Map<String, dynamic> Function()? afterCancel;
  ApiException? createError;

  @override
  Future<List<ExpertService>> services(String expertId) async => [
    ExpertService({
      'id': 'service',
      'expert_id': expertId,
      'service_code': 'natal',
      'title': 'Video danışmanlık',
      'delivery_type': 'video',
      'duration_minutes': 60,
      'price': {'amount_minor': 1000, 'currency': 'TRY'},
      'supports_appointment': true,
    }),
  ];

  @override
  Future<Expert> detail(String id) async => Expert({
    'id': id,
    'display_name': 'Ayşe Demir',
    'experience_years': 5,
    'verified': true,
    'rating_average': 4.9,
    'rating_count': 10,
  });

  @override
  Future<SlotPage> slots(
    String expertId,
    String serviceId,
    DateTime from,
    DateTime to,
  ) async => SlotPage({
    'expert_service_id': serviceId,
    'display_timezone': 'Europe/Istanbul',
    'slots': [
      for (final d in [first, first.add(const Duration(days: 1))])
        {
          'starts_at_utc': d.toUtc().toIso8601String(),
          'ends_at_utc': d
              .add(const Duration(hours: 1))
              .toUtc()
              .toIso8601String(),
          'display_timezone': 'Europe/Istanbul',
        },
    ],
  });

  @override
  Future<Order> createOrder(BookingIntent intent) async {
    intents.add(intent);
    if (createError case final error?) throw error;
    return Order(
      orderJson(status: 'pending_payment', paymentStatus: 'pending'),
    );
  }

  @override
  Future<Order> order(String id, {bool expert = false}) async {
    orderReads++;
    return Order(current!);
  }

  @override
  Future<Order> cancelOrder(String id) async {
    cancels++;
    current = afterCancel!();
    return Order(current!);
  }

  @override
  Future<Appointment> cancelAppointment(
    String id, {
    bool expert = false,
  }) async {
    cancels++;
    current = afterCancel!();
    return Appointment(current!['appointment'] as Map<String, dynamic>);
  }

  @override
  Future<Appointment> appointment(String id) async =>
      Appointment(current!['appointment'] as Map<String, dynamic>);

  @override
  Future<List<Appointment>> appointments({
    bool expert = false,
    bool upcoming = false,
  }) async => const [];
}

Future<void> pumpApp(
  WidgetTester tester,
  Widget home, {
  required MarketplaceRepository marketplace,
  BillingRepository? billing,
  EntitlementController? entitlements,
  PasswordResetService? reset,
}) async {
  disableAnimations(tester);
  tester.view.physicalSize = const Size(1000, 2400);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        marketplaceRepositoryProvider.overrideWithValue(marketplace),
        if (billing != null)
          billingRepositoryProvider.overrideWithValue(billing),
        if (entitlements != null)
          entitlementControllerProvider.overrideWithValue(entitlements),
        if (reset != null)
          passwordResetServiceProvider.overrideWithValue(reset),
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
        home: home,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> pickDate(WidgetTester tester, DateTime day) async {
  await tester.tap(find.byKey(const ValueKey('booking-date')));
  await tester.pumpAndSettle();
  await tester.tap(find.byIcon(Icons.edit_outlined));
  await tester.pumpAndSettle();
  final format = DateFormat.yMd('tr');
  await tester.enterText(find.byType(TextField).last, format.format(day));
  await tester.tap(find.text('Tamam'));
  await tester.pumpAndSettle();
}

FilledButton submitButton(WidgetTester tester) =>
    tester.widget<FilledButton>(find.byKey(const ValueKey('booking-submit')));

void main() {
  setUpAll(() async {
    // Date picker text entry is parsed in the app locale.
    Intl.defaultLocale = 'tr';
  });

  group('booking', () {
    testWidgets('changing the date clears the slot and disables booking', (
      tester,
    ) async {
      final repo = FakeMarketplace();
      await pumpApp(
        tester,
        const BookingScreen(expertId: 'expert', serviceId: 'service'),
        marketplace: repo,
      );
      expect(submitButton(tester).onPressed, isNull);
      await tester.tap(find.byType(ChoiceChip).first);
      await tester.pumpAndSettle();
      expect(submitButton(tester).onPressed, isNotNull);

      await pickDate(tester, repo.first.add(const Duration(days: 1)));

      expect(
        tester.widget<ChoiceChip>(find.byType(ChoiceChip)).selected,
        false,
      );
      expect(submitButton(tester).onPressed, isNull);
      // Nothing from the previous day can be sent.
      await tester.tap(
        find.byKey(const ValueKey('booking-submit')),
        warnIfMissed: false,
      );
      await tester.pumpAndSettle();
      expect(repo.intents, isEmpty);
      expect(
        find.byKey(const ValueKey('booking-confirm-dialog')),
        findsNothing,
      );
    });

    testWidgets('confirmation shows date, time, zone, expert and service; '
        'the request names the selected day', (tester) async {
      final repo = FakeMarketplace();
      await pumpApp(
        tester,
        const BookingScreen(expertId: 'expert', serviceId: 'service'),
        marketplace: repo,
      );
      await pickDate(tester, repo.first.add(const Duration(days: 1)));
      await tester.tap(find.byType(ChoiceChip).first);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('booking-submit')));
      await tester.pumpAndSettle();

      final dialog = find.byKey(const ValueKey('booking-confirm-dialog'));
      expect(dialog, findsOneWidget);
      final second = repo.first.add(const Duration(days: 1));
      for (final text in [
        'Tarih',
        'Saat',
        'Saat dilimi',
        'Uzman',
        'Hizmet',
        'Ayşe Demir',
        'Video danışmanlık',
        timezoneLabel(second),
      ]) {
        expect(
          find.descendant(of: dialog, matching: find.text(text)),
          findsOneWidget,
          reason: text,
        );
      }
      await tester.tap(find.byKey(const ValueKey('booking-confirm-yes')));
      await tester.pumpAndSettle();

      final sent = repo.intents.single;
      expect(sent.startsUtc, second.toUtc());
      expect(
        sent.payload['selected_local_date'],
        DateFormat('yyyy-MM-dd').format(second),
      );
      expect(
        sent.payload['selected_utc_offset_minutes'],
        second.timeZoneOffset.inMinutes,
      );
    });

    testWidgets('a server date mismatch clears the stale selection', (
      tester,
    ) async {
      final repo = FakeMarketplace()
        ..createError = const ApiException(
          kind: ApiErrorKind.validation,
          code: 'slot_date_mismatch',
        );
      await pumpApp(
        tester,
        const BookingScreen(expertId: 'expert', serviceId: 'service'),
        marketplace: repo,
      );
      await tester.tap(find.byType(ChoiceChip).first);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('booking-submit')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('booking-confirm-yes')));
      await tester.pumpAndSettle();
      expect(
        find.text(
          'Seçtiğin saat seçili güne ait değil. Lütfen saati yeniden seç.',
        ),
        findsOneWidget,
      );
      expect(submitButton(tester).onPressed, isNull);
    });
  });

  group('cancellation and refunds', () {
    testWidgets('cancel asks first, shows the refund outcome, then shows the '
        'refund under review', (tester) async {
      final repo = FakeMarketplace(order: orderJson())
        ..afterCancel = () => orderJson(
          status: 'cancelled',
          paymentStatus: 'refund_pending',
          lifecycle: 'refund_review',
          appointmentStatus: 'cancelled',
          actions: {'can_cancel': false},
          refund: {
            'id': 'r1',
            'status': 'manual_review',
            'amount_minor': 99900,
            'currency': 'TRY',
            'reason': 'user_cancellation',
          },
        );
      await pumpApp(
        tester,
        const OrderDetailScreen(id: 'order-1'),
        marketplace: repo,
      );
      await tester.ensureVisible(find.byKey(const ValueKey('cancel-order')));
      await tester.tap(find.byKey(const ValueKey('cancel-order')));
      await tester.pumpAndSettle();

      final outcome = tester.widget<Text>(
        find.byKey(const ValueKey('cancel-refund-outcome')),
      );
      expect(outcome.data, contains('999.00 TRY'));
      expect(outcome.data, contains('iade incelemesine'));
      expect(repo.cancels, 0);

      // Backing out changes nothing.
      await tester.tap(find.text('Vazgeç'));
      await tester.pumpAndSettle();
      expect(repo.cancels, 0);

      await tester.tap(find.byKey(const ValueKey('cancel-order')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('cancel-confirm-yes')));
      await tester.pumpAndSettle();

      expect(repo.cancels, 1);
      expect(find.byKey(const ValueKey('refund-card')), findsOneWidget);
      expect(find.textContaining('İade incelemesinde'), findsWidgets);
      expect(find.byKey(const ValueKey('cancel-order')), findsNothing);
    });

    testWidgets('unpaid cancel says nothing is owed', (tester) async {
      final repo = FakeMarketplace(
        order: orderJson(
          status: 'pending_payment',
          paymentStatus: 'pending',
          lifecycle: 'pending',
          cancellation: {
            'allowed': true,
            'refund_outcome': 'not_paid',
            'refundable_minor': 0,
            'currency': 'TRY',
          },
        ),
      );
      await pumpApp(
        tester,
        const AppointmentDetailScreen(id: 'appt-1'),
        marketplace: repo,
      );
      await tester.tap(find.byKey(const ValueKey('cancel-appointment')));
      await tester.pumpAndSettle();
      expect(find.text('Ödeme alınmadı; iade gerekmez.'), findsOneWidget);
    });

    for (final (status, label) in [
      ('manual_review', 'İade incelemesinde'),
      ('refunded', 'İade edildi'),
      ('denied', 'İade reddedildi'),
    ]) {
      testWidgets('refund $status is visible from the appointment', (
        tester,
      ) async {
        final repo = FakeMarketplace(
          order: orderJson(
            status: 'cancelled',
            paymentStatus: status == 'refunded' ? 'refunded' : 'paid',
            lifecycle: status == 'refunded' ? 'refunded' : 'cancelled',
            appointmentStatus: 'cancelled',
            refund: {
              'id': 'r1',
              'status': status,
              'amount_minor': 99900,
              'currency': 'TRY',
              'reason': 'expert_cancellation',
            },
          ),
        );
        await pumpApp(
          tester,
          const AppointmentDetailScreen(id: 'appt-1'),
          marketplace: repo,
        );
        expect(
          find.descendant(
            of: find.byKey(const ValueKey('refund-card')),
            matching: find.textContaining(label),
          ),
          findsOneWidget,
        );
        expect(find.byKey(const ValueKey('cancel-appointment')), findsNothing);
      });
    }
  });

  group('appointment center', () {
    test('filters split upcoming, past and cancelled', () {
      final now = DateTime.utc(2026, 9, 27, 12);
      Appointment a(String id, int hours, String status) => Appointment({
        'id': id,
        'expert_id': 'e',
        'expert_service_id': 's',
        'starts_at_utc': now.add(Duration(hours: hours)).toIso8601String(),
        'ends_at_utc': now.add(Duration(hours: hours + 1)).toIso8601String(),
        'timezone': 'UTC',
        'status': status,
      });
      final items = [
        a('later', 48, 'confirmed'),
        a('soon', 2, 'pending'),
        a('done', -48, 'completed'),
        a('missed', -24, 'confirmed'),
        a('off', 5, 'cancelled'),
      ];
      List<String> ids(AppointmentFilter f) =>
          filterAppointments(items, f, now: now).map((x) => x.id).toList();
      expect(ids(AppointmentFilter.upcoming), ['soon', 'later']);
      expect(ids(AppointmentFilter.past), ['missed', 'done']);
      expect(ids(AppointmentFilter.cancelled), ['off']);
    });
  });

  group('payment refresh', () {
    testWidgets('after payment the order stops saying "awaiting payment" and '
        'offers the next step', (tester) async {
      final repo = FakeMarketplace(
        order: orderJson(
          status: 'pending_payment',
          paymentStatus: 'pending',
          lifecycle: 'pending',
        ),
      );
      final billing = FakeBilling();
      final entitlements = EntitlementController(
        billing,
        const DisabledBillingService(),
      );
      await entitlements.start();
      addTearDown(entitlements.dispose);
      await pumpApp(
        tester,
        const OrderDetailScreen(id: 'order-1'),
        marketplace: repo,
        billing: billing,
        entitlements: entitlements,
      );
      expect(find.text('Bekliyor'), findsOneWidget);
      expect(find.byKey(const ValueKey('payment-confirmed')), findsNothing);
      final readsBefore = repo.orderReads;

      // The provider confirms the payment on the server.
      billing.paid = true;
      repo.current = orderJson();
      await tester.ensureVisible(find.text('Ödeme durumunu yenile'));
      await tester.tap(find.text('Ödeme durumunu yenile'));
      await tester.pumpAndSettle();

      expect(repo.orderReads, greaterThan(readsBefore));
      expect(billing.entitlementReads, greaterThan(1));
      expect(find.text('Bekliyor'), findsNothing);
      expect(find.text('Planlandı'), findsOneWidget);
      expect(find.byKey(const ValueKey('payment-confirmed')), findsOneWidget);
      expect(find.byKey(const ValueKey('go-to-call')), findsOneWidget);
    });
  });

  group('password reset', () {
    testWidgets('request shows one generic answer', (tester) async {
      final reset = FakeReset(PasswordResetRequestResult.requested);
      await pumpApp(
        tester,
        const ForgotPasswordScreen(),
        marketplace: FakeMarketplace(),
        reset: reset,
      );
      await tester.enterText(find.byType(TextFormField), 'a@example.com');
      await tester.tap(find.text('Bağlantı gönder'));
      await tester.pumpAndSettle();
      expect(reset.requested, ['a@example.com']);
      expect(find.byKey(const ValueKey('reset-requested')), findsOneWidget);
      expect(
        find.textContaining('Hesap uygunsa sıfırlama bağlantısı gönderildi'),
        findsOneWidget,
      );
    });

    testWidgets('no mail provider: says unavailable, never "sent"', (
      tester,
    ) async {
      await pumpApp(
        tester,
        const ForgotPasswordScreen(),
        marketplace: FakeMarketplace(),
        reset: FakeReset(PasswordResetRequestResult.unavailable),
      );
      await tester.enterText(find.byType(TextFormField), 'a@example.com');
      await tester.tap(find.text('Bağlantı gönder'));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('reset-unavailable')), findsOneWidget);
      expect(find.byKey(const ValueKey('reset-requested')), findsNothing);
    });

    for (final state in [ResetLinkState.expired, ResetLinkState.used]) {
      testWidgets('a ${state.name} link is said before any form', (
        tester,
      ) async {
        await pumpApp(
          tester,
          const ResetPasswordScreen(token: 'token-value-123'),
          marketplace: FakeMarketplace(),
          reset: FakeReset(PasswordResetRequestResult.requested, link: state),
        );
        expect(find.byKey(ValueKey('reset-${state.name}')), findsOneWidget);
        expect(find.byType(TextFormField), findsNothing);
        expect(find.text('Yeni bağlantı iste'), findsOneWidget);
      });
    }

    testWidgets('a valid link sets the password once', (tester) async {
      final reset = FakeReset(PasswordResetRequestResult.requested);
      await pumpApp(
        tester,
        const ResetPasswordScreen(token: 'token-value-123'),
        marketplace: FakeMarketplace(),
        reset: reset,
      );
      await tester.enterText(find.byType(TextFormField).at(0), 'NewPass12345');
      await tester.enterText(find.byType(TextFormField).at(1), 'NewPass12345');
      await tester.tap(find.text('Şifreyi güncelle'));
      await tester.pumpAndSettle();
      expect(reset.resets, ['token-value-123:NewPass12345']);
      expect(find.byKey(const ValueKey('reset-done')), findsOneWidget);
    });

    testWidgets('a link used meanwhile is reported on submit', (tester) async {
      final reset = FakeReset(PasswordResetRequestResult.requested)
        ..failOnReset = ResetLinkState.used;
      await pumpApp(
        tester,
        const ResetPasswordScreen(token: 'token-value-123'),
        marketplace: FakeMarketplace(),
        reset: reset,
      );
      await tester.enterText(find.byType(TextFormField).at(0), 'NewPass12345');
      await tester.enterText(find.byType(TextFormField).at(1), 'NewPass12345');
      await tester.tap(find.text('Şifreyi güncelle'));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('reset-used')), findsOneWidget);
    });

    testWidgets('a missing token is invalid', (tester) async {
      await pumpApp(
        tester,
        const ResetPasswordScreen(token: null),
        marketplace: FakeMarketplace(),
        reset: FakeReset(PasswordResetRequestResult.requested),
      );
      expect(find.byKey(const ValueKey('reset-invalid')), findsOneWidget);
    });
  });
}

class FakeBilling extends Fake implements BillingRepository {
  bool paid = false;
  int entitlementReads = 0;

  @override
  Future<EntitlementSummary> entitlements() async {
    entitlementReads++;
    return EntitlementSummary({
      'tier': 'free',
      'premium': false,
      'credits': <String, dynamic>{},
      'capabilities': <String, dynamic>{},
      'items': <dynamic>[],
    });
  }

  @override
  Future<ProductCatalog> products(StorePlatform platform) async =>
      ProductCatalog({'products': <dynamic>[]});

  @override
  Future<OrderPayment> orderPayment(String orderId) async => OrderPayment({
    'order_id': orderId,
    'payable_externally': !paid,
    'blocked_by_policy_review': false,
    'groups': [
      {
        'classification': 'live_person_to_person',
        'rail': 'external_marketplace',
        'status': paid ? 'satisfied' : 'required',
        'amount_minor': 99900,
        'currency': 'TRY',
      },
    ],
    'lines': <dynamic>[],
  });
}

class FakeReset implements PasswordResetService {
  FakeReset(this.result, {this.link = ResetLinkState.valid});
  final PasswordResetRequestResult result;
  final ResetLinkState link;
  ResetLinkState? failOnReset;
  final List<String> requested = [], resets = [];

  @override
  bool get completesInApp => true;

  @override
  Future<PasswordResetRequestResult> requestReset(String email) async {
    requested.add(email);
    return result;
  }

  @override
  Future<ResetLinkState> checkLink(String token) async => link;

  @override
  Future<void> resetPassword(String token, String newPassword) async {
    if (failOnReset case final state?) throw PasswordResetException(state);
    resets.add('$token:$newPassword');
  }
}
