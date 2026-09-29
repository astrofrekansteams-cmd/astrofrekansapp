// Outside links open the same few screens on Android and iOS, and nothing
// else: both platforms deliver the full astrofrekans:// URL to the router.
import 'package:astrofrekans/core/routing/deep_links.dart';
import 'package:astrofrekans/features/auth/presentation/password_reset_screens.dart';
import 'package:astrofrekans/features/home/presentation/home_screen.dart';
import 'package:astrofrekans/features/notifications/presentation/notification_center_screen.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';

const _id = '66666666-6666-4666-8666-666666666666';

/// What the engine sends when the OS opens a link into the app.
Future<void> _openLink(WidgetTester tester, String url) async {
  final ByteData message = const JSONMethodCodec().encodeMethodCall(
    MethodCall('pushRouteInformation', <String, Object?>{
      'location': url,
      'state': null,
    }),
  );
  await tester.binding.defaultBinaryMessenger.handlePlatformMessage(
    'flutter/navigation',
    message,
    (_) {},
  );
  await tester.pumpAndSettle();
}

void main() {
  group('allowlist', () {
    test('allowed screens keep their path and query', () {
      expect(
        externalLinkTarget(
          Uri.parse('astrofrekans://app/reset-password?token=abc'),
        ),
        '/reset-password?token=abc',
      );
      expect(
        externalLinkTarget(Uri.parse('astrofrekans://app/notifications')),
        '/notifications',
      );
      for (final path in [
        '/appointments/$_id',
        '/orders/$_id',
        '/astro-ai/reports/$_id',
      ]) {
        expect(externalLinkTarget(Uri.parse('astrofrekans://app$path')), path);
      }
    });

    test('everything else goes home', () {
      for (final url in [
        'astrofrekans://app/profile/account/delete',
        'astrofrekans://app/orders/$_id/call',
        'astrofrekans://app/calls/$_id/incoming',
        'astrofrekans://app/orders/not-an-id',
        'astrofrekans://elsewhere/reset-password?token=abc',
        'https://evil.example/reset-password?token=abc',
      ]) {
        expect(externalLinkTarget(Uri.parse(url)), '/home', reason: url);
      }
      expect(isExternalLink(Uri.parse('/orders/$_id')), isFalse);
    });
  });

  testWidgets('a reset link opens the reset screen with its token', (
    tester,
  ) async {
    final TestEnv env = await TestEnv.create();
    await pumpApp(tester, env: env);
    await _openLink(tester, 'astrofrekans://app/reset-password?token=abc123');
    final screen = tester.widget<ResetPasswordScreen>(
      find.byType(ResetPasswordScreen),
    );
    expect(screen.token, 'abc123');
  });

  testWidgets('signed in: an allowed link opens, a disallowed one goes home', (
    tester,
  ) async {
    final TestEnv env = await TestEnv.create(user: testUser);
    await pumpApp(tester, env: env);
    await _openLink(tester, 'astrofrekans://app/notifications');
    expect(find.byType(NotificationCenterScreen), findsOneWidget);

    await _openLink(tester, 'astrofrekans://app/profile/account/delete');
    expect(find.byType(HomeScreen), findsOneWidget);
    expect(find.byType(NotificationCenterScreen), findsNothing);
  });
}
