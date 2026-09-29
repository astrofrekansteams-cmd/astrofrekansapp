@Tags(<String>['preview'])
library;

import 'dart:io';

import 'package:astrofrekans/features/astro_ai/presentation/astro_ai_screen.dart';
import 'package:astrofrekans/features/auth/presentation/login_screen.dart';
import 'package:astrofrekans/features/home/presentation/home_screen.dart';
import 'package:astrofrekans/features/onboarding/presentation/onboarding_screen.dart';
import 'package:astrofrekans/features/profile/presentation/profile_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'helpers/test_harness.dart';

/// Renders the main screens to PNG so the design can be reviewed without a
/// device. Run with: flutter test test/preview_capture_test.dart --update-goldens
Future<void> loadFonts() async {
  for (final MapEntry<String, List<String>> family in <String, List<String>>{
    'CormorantGaramond': <String>[
      'assets/fonts/CormorantGaramond-500.ttf',
      'assets/fonts/CormorantGaramond-600.ttf',
      'assets/fonts/CormorantGaramond-700.ttf',
    ],
    'Jost': <String>[
      'assets/fonts/Jost-300.ttf',
      'assets/fonts/Jost-400.ttf',
      'assets/fonts/Jost-500.ttf',
      'assets/fonts/Jost-600.ttf',
    ],
    'MaterialIcons': <String>[
      'C:/flutter/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf',
    ],
  }.entries) {
    final FontLoader loader = FontLoader(family.key);
    for (final String path in family.value) {
      loader.addFont(
        File(path).readAsBytes().then(
          (List<int> bytes) => ByteData.view(Uint8List.fromList(bytes).buffer),
        ),
      );
    }
    await loader.load();
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(loadFonts);

  void shoot(String name, Widget screen, {bool ai = false}) {
    testWidgets('capture $name', (WidgetTester tester) async {
      final TestEnv env = await TestEnv.create(user: testUser);
      await pumpScreen(tester, screen, env: env, size: const Size(390, 844));
      if (ai) {
        await tester.enterText(
          find.byType(TextField).last,
          'Bu dönemde ilişkilerimde nelere dikkat etmeliyim?',
        );
        await tester.pump();
        await tester.tap(find.byIcon(Icons.send));
        await tester.pumpAndSettle();
      }
      // Images decode asynchronously: load them before capturing.
      await tester.runAsync(() async {
        for (final Element element in find.byType(Image).evaluate()) {
          final Image image = element.widget as Image;
          await precacheImage(image.image, element);
        }
      });
      await tester.pumpAndSettle();

      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile('preview/$name.png'),
      );
    });
  }

  shoot('home', const HomeScreen());
  shoot('astro_ai', const AstroAiScreen());
  shoot('astro_ai_chat', const AstroAiScreen(), ai: true);
  shoot('login', const LoginScreen());
  shoot('onboarding', const OnboardingScreen());
  shoot('profile', const ProfileScreen());
}
