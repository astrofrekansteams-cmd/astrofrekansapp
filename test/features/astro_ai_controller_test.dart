import 'package:astrofrekans/features/astro_ai/application/astro_ai_controller.dart';
import 'package:astrofrekans/features/astro_ai/domain/chat_message.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/test_harness.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late ProviderContainer container;

  setUp(() async {
    container = containerFor(await TestEnv.create(user: testUser));
  });

  test('send() produces a user message and a streamed AI answer', () async {
    final AstroAIController controller = container.read(
      astroAIControllerProvider.notifier,
    );

    expect(
      container.read(astroAIControllerProvider).status,
      AstroAIStatus.idle,
    );

    await controller.send('Aşk hayatım nasıl?');

    final AstroAIState state = container.read(astroAIControllerProvider);
    expect(state.messages, hasLength(2));

    final ChatMessage question = state.messages.first;
    expect(question.isUser, isTrue);
    expect(question.text, 'Aşk hayatım nasıl?');

    final ChatMessage answer = state.messages.last;
    expect(answer.role, ChatRole.astroAi);
    expect(answer.text, isNotEmpty);
    expect(answer.status, ChatMessageStatus.sent);

    // The answer must carry the sky factors that shaped it.
    expect(answer.influences, isNotEmpty);
    expect(state.status, AstroAIStatus.answering);
  });

  test('status passes through thinking and typing', () async {
    final List<AstroAIStatus> seen = <AstroAIStatus>[];
    container.listen<AstroAIState>(astroAIControllerProvider, (
      AstroAIState? _,
      AstroAIState next,
    ) {
      if (seen.isEmpty || seen.last != next.status) seen.add(next.status);
    }, fireImmediately: true);

    await container
        .read(astroAIControllerProvider.notifier)
        .send('Kariyerimde ne görünüyor?');

    expect(
      seen,
      containsAllInOrder(<AstroAIStatus>[
        AstroAIStatus.thinking,
        AstroAIStatus.typing,
        AstroAIStatus.answering,
      ]),
    );
  });

  test('empty input is ignored', () async {
    await container.read(astroAIControllerProvider.notifier).send('   ');
    expect(container.read(astroAIControllerProvider).messages, isEmpty);
  });

  test('clear() resets the conversation', () async {
    final AstroAIController controller = container.read(
      astroAIControllerProvider.notifier,
    );
    await controller.send('Bugünün enerjisi ne?');
    expect(container.read(astroAIControllerProvider).messages, isNotEmpty);

    controller.clear();
    final AstroAIState state = container.read(astroAIControllerProvider);
    expect(state.messages, isEmpty);
    expect(state.status, AstroAIStatus.idle);
  });
}
