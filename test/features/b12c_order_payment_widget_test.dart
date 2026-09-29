import 'dart:convert';
import 'dart:io';

import 'package:astrofrekans/features/billing/application/entitlement_controller.dart';
import 'package:astrofrekans/features/billing/data/billing_models.dart';
import 'package:astrofrekans/features/billing/data/billing_repository.dart';
import 'package:astrofrekans/features/billing/data/billing_service.dart';
import 'package:astrofrekans/features/billing/presentation/order_payment_section.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets(
    'hybrid rails are separate and REVIEW_REQUIRED never opens another rail',
    (tester) async {
      final fixture =
          jsonDecode(
                File(
                  'test/fixtures/b12c_contract_samples.json',
                ).readAsStringSync(),
              )
              as Map<String, dynamic>;
      final repo = _PaymentBilling(fixture);
      final controller = EntitlementController(
        repo,
        const DisabledBillingService(),
      );
      await controller.start();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            billingRepositoryProvider.overrideWithValue(repo),
            entitlementControllerProvider.overrideWithValue(controller),
          ],
          child: const MaterialApp(
            locale: Locale('tr'),
            supportedLocales: [Locale('tr'), Locale('en')],
            localizationsDelegates: GlobalMaterialLocalizations.delegates,
            home: Scaffold(body: OrderPaymentSection(orderId: 'order-test')),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Dijital ürün · uygulama mağazası'), findsOneWidget);
      expect(
        find.text('Canlı uzman hizmeti · harici sağlayıcı'),
        findsOneWidget,
      );
      expect(find.text('Ödeme yöntemi inceleme bekliyor'), findsOneWidget);
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Uzman ödemesine geç'),
            )
            .onPressed,
        isNull,
      );
      expect(repo.paymentStarts, 0);
      await tester.pumpWidget(const SizedBox.shrink());
      controller.dispose();
    },
  );
}

class _PaymentBilling extends Fake implements BillingRepository {
  _PaymentBilling(this.fixture);
  final Map<String, dynamic> fixture;
  int paymentStarts = 0;
  @override
  Future<EntitlementSummary> entitlements() async =>
      EntitlementSummary(fixture['entitlements_free'] as Map<String, dynamic>);
  @override
  Future<OrderPayment> orderPayment(String orderId) async =>
      OrderPayment(fixture['payment_groups'] as Map<String, dynamic>);
  @override
  Future<OrderPaymentStart> payOrder(
    String orderId, {
    required String method,
    required String idempotencyKey,
  }) async {
    paymentStarts++;
    throw StateError('Blocked');
  }
}
