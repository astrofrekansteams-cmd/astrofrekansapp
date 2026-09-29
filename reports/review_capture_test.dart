@Tags(<String>['preview'])
library;

import 'dart:io';
import 'package:astrofrekans/features/home/presentation/home_screen.dart';
import 'package:astrofrekans/features/profile/presentation/profile_screen.dart';
import 'package:astrofrekans/features/auth/presentation/login_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import '../test/helpers/test_harness.dart';
import '../test/preview_capture_test.dart' as preview;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(preview.loadFonts);
  for (final entry in <String, Widget>{
    'home': const HomeScreen(),
    'profile': const ProfileScreen(),
    'login': const LoginScreen(),
  }.entries) {
    testWidgets('current review capture ${entry.key}', (tester) async {
      final env = await TestEnv.create(user: testUser);
      await pumpScreen(
        tester,
        entry.value,
        env: env,
        size: const Size(390, 844),
      );
      await tester.runAsync(() async {
        for (final element in find.byType(Image).evaluate()) {
          final widget = element.widget as Image;
          await precacheImage(widget.image, element);
        }
      });
      await tester.pumpAndSettle();
      Directory('reports/review_preview').createSync(recursive: true);
      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile('review_preview/${entry.key}.png'),
      );
    });
  }
}
