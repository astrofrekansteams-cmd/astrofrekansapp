import 'package:astrofrekans/features/astro_ai/presentation/astro_ai_screen.dart';
import 'package:astrofrekans/features/astro_ai/presentation/widgets/chat_bubble.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('hero and prompt suggestions render before any question', (
    WidgetTester tester,
  ) async {
    final TestEnv env = await TestEnv.create(user: testUser);
    await pumpScreen(tester, const AstroAiScreen(), env: env);

    expect(find.text('Astro AI'), findsWidgets);
    expect(find.text('Doğum haritanı okur.'), findsOneWidget);
    expect(find.text('İlk sorunu sor'), findsOneWidget);
    expect(find.text('Bir şey sor...'), findsOneWidget);
  });

  testWidgets('asking a question shows the answer and its influences', (
    WidgetTester tester,
  ) async {
    final TestEnv env = await TestEnv.create(user: testUser);
    await pumpScreen(tester, const AstroAiScreen(), env: env);

    await tester.enterText(
      find.byType(TextField).last,
      'Bu dönemde ilişkilerimde nelere dikkat etmeliyim?',
    );
    await tester.pump();

    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();

    // The answer pushes the question above the viewport, and the chat list is
    // lazy, so scroll back up before asserting on it.
    await tester.drag(find.byType(ListView), const Offset(0, 600));
    await tester.pumpAndSettle();

    expect(
      find.text('Bu dönemde ilişkilerimde nelere dikkat etmeliyim?'),
      findsOneWidget,
    );
    expect(find.byType(ChatBubble), findsWidgets);
    expect(find.text('Bu yorumu oluşturan etkiler'), findsOneWidget);
    expect(find.byType(InfluenceStrip), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
