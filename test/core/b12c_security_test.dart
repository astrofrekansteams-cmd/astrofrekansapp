import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('join/store proof paths do not persist or log sensitive material', () {
    for (final path in [
      'lib/features/calls/application/call_controller.dart',
      'lib/features/calls/data/call_media_service.dart',
      'lib/features/calls/data/call_repository.dart',
      'lib/features/billing/application/entitlement_controller.dart',
      'lib/features/billing/data/billing_repository.dart',
      'lib/features/billing/data/billing_service.dart',
    ]) {
      final source = File(path).readAsStringSync();
      expect(source, isNot(contains('SecureStore(')), reason: path);
      expect(source, isNot(contains('SecureTokenStorage(')), reason: path);
      expect(source, isNot(contains('debugPrint(')), reason: path);
      expect(source, isNot(contains('LogInterceptor(')), reason: path);
    }
    final join = File(
      'lib/features/calls/data/call_models.dart',
    ).readAsStringSync();
    final purchase = File(
      'lib/features/billing/data/billing_models.dart',
    ).readAsStringSync();
    expect(join, contains('CallJoinGrant(redacted)'));
    expect(purchase, contains('StorePurchaseEvent(redacted)'));
  });
}
