import '../../../core/astrology/domain/natal_chart.dart';
import '../../../core/astrology/domain/transit.dart';
import '../../profile/domain/user_profile.dart';
import 'chat_message.dart';

/// Streamed pieces of an Astro AI answer.
sealed class AstroAIEvent {
  const AstroAIEvent();
}

/// Incremental text, so the UI can show a real "typing" state.
class AstroAITextDelta extends AstroAIEvent {
  const AstroAITextDelta(this.text);

  final String text;
}

/// These are available context factors, not a claim the answer cited all of them.
class AstroAIMetadata extends AstroAIEvent {
  const AstroAIMetadata({
    required this.warnings,
    required this.availableFactorIds,
    this.influenceLabels = const <String>[],
  });
  final List<String> warnings;
  final List<String> availableFactorIds;

  /// Localized lines from the engine ("Transit Satürn kare natal Güneş"):
  /// the astrological basis of the answer, readable.
  final List<String> influenceLabels;
}

/// Final event: the influences the engine says shaped this answer.
class AstroAICompleted extends AstroAIEvent {
  const AstroAICompleted({this.influences = const <TransitSummary>[]});

  final List<TransitSummary> influences;
}

/// The AI seam.
///
/// The app never calls an LLM provider directly and never embeds a provider
/// key: an implementation of this interface talks to our own backend, which
/// holds the keys and composes the prompt from the astrology context.
abstract interface class AstroAIRepository {
  Stream<AstroAIEvent> sendMessage({
    required String message,
    required UserProfile userProfile,
    required NatalChart natalChart,
    required List<Transit> activeTransits,
    List<ChatMessage> history,
  });
}

/// Voice input is planned; the architecture is here so the chat controller can
/// enter its `listening` state without another refactor.
abstract interface class VoiceInputService {
  bool get isAvailable;

  Stream<String> listen();

  Future<void> stop();
}

class UnavailableVoiceInputService implements VoiceInputService {
  const UnavailableVoiceInputService();

  @override
  bool get isAvailable => false;

  @override
  Stream<String> listen() =>
      Stream<String>.error(UnsupportedError('Voice input not configured'));

  @override
  Future<void> stop() async {}
}
