import 'dart:convert';
import 'dart:io';

import 'package:astrofrekans/features/billing/data/billing_models.dart';
import 'package:astrofrekans/features/calls/data/call_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('B12C host-side DTO mapping benchmark (not device frame timing)', () {
    final fixture =
        jsonDecode(
              File(
                'test/fixtures/b12c_contract_samples.json',
              ).readAsStringSync(),
            )
            as Map<String, dynamic>;
    final call = fixture['call_session'] as Map<String, dynamic>;
    final product =
        (fixture['products'] as Map<String, dynamic>)['items'] as List<dynamic>;
    final timer = Stopwatch()..start();
    final calls = [
      for (var i = 0; i < 50; i++) CallSession({...call, 'id': '$i'}),
    ];
    final callMicros = timer.elapsedMicroseconds;
    timer.reset();
    final products = [
      for (var i = 0; i < 20; i++)
        CatalogProduct({
          ...product.single as Map<String, dynamic>,
          'code': 'p$i',
        }),
    ];
    final productMicros = timer.elapsedMicroseconds;
    timer.reset();
    final entitlements = [
      for (var i = 0; i < 100; i++)
        EntitlementSummary(
          fixture['entitlements_active'] as Map<String, dynamic>,
        ),
    ];
    final entitlementMicros = timer.elapsedMicroseconds;
    timer.stop();
    expect(calls, hasLength(50));
    expect(products, hasLength(20));
    expect(entitlements.every((value) => value.premium), isTrue);
    // ignore: avoid_print
    print(
      'B12C_HOST_PERF call_50_dto=${callMicros}us product_20_dto=${productMicros}us entitlement_100_dto=${entitlementMicros}us',
    );
  });
}
