import '../domain/astro_ai_repository.dart';
import '../domain/chat_message.dart';
import '../../../core/astrology/domain/natal_chart.dart';
import '../../../core/astrology/domain/transit.dart';
import '../../profile/domain/user_profile.dart';

/// B6 has no public AI contract yet. Fails explicitly if selected.
class AstroAIServiceUnavailable implements Exception {
  const AstroAIServiceUnavailable();
}

class DisabledApiAstroAIRepository implements AstroAIRepository {
  const DisabledApiAstroAIRepository();

  @override
  Stream<AstroAIEvent> sendMessage({
    required String message,
    required UserProfile userProfile,
    required NatalChart natalChart,
    required List<Transit> activeTransits,
    List<ChatMessage> history = const <ChatMessage>[],
  }) => Stream<AstroAIEvent>.error(const AstroAIServiceUnavailable());
}
