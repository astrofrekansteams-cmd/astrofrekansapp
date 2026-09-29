import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/astrology/astrology_providers.dart';
import '../../../core/astrology/domain/astro_ai_context.dart';
import '../../../core/astrology/domain/transit.dart';
import '../../../core/localization/locale_controller.dart';
import '../../../core/network/api_config.dart';
import '../../auth/application/session_controller.dart';
import '../../profile/domain/user_profile.dart';
import '../data/mock_astro_ai_repository.dart';
import '../data/api_astro_ai_repository.dart';
import '../../../core/network/api_client.dart';
import '../domain/astro_ai_repository.dart';
import '../domain/chat_message.dart';

final Provider<AstroAIRepository> astroAIRepositoryProvider =
    Provider<AstroAIRepository>((Ref ref) {
      ref.watch(currentUserProvider)?.id;
      if (!ref.watch(appEnvironmentProvider).useMocks) {
        return ApiAstroAIRepository(
          ApiClient(ref.watch(dioProvider)),
          locale: ref.watch(localeControllerProvider).languageCode,
        );
      }
      final String language = ref.watch(localeControllerProvider).languageCode;
      return MockAstroAIRepository(languageCode: language);
    });

final Provider<VoiceInputService> voiceInputServiceProvider =
    Provider<VoiceInputService>(
      (Ref ref) => const UnavailableVoiceInputService(),
    );

/// Conversation states from the spec: idle, listening, thinking, typing,
/// answering, error.
enum AstroAIStatus { idle, listening, thinking, typing, answering, error }

@immutable
class AstroAIState {
  const AstroAIState({
    this.messages = const <ChatMessage>[],
    this.status = AstroAIStatus.idle,
    this.errorKind,
    this.availableFactorIds = const [],
    this.warnings = const [],
    this.influenceLabels = const [],
  });

  final List<ChatMessage> messages;
  final AstroAIStatus status;
  final Object? errorKind;
  final List<String> availableFactorIds;
  final List<String> warnings;

  /// "Bu yorumu oluşturan etkiler" for the latest answer.
  final List<String> influenceLabels;

  bool get isBusy =>
      status == AstroAIStatus.thinking || status == AstroAIStatus.typing;

  bool get hasConversation => messages.isNotEmpty;

  AstroAIState copyWith({
    List<ChatMessage>? messages,
    AstroAIStatus? status,
    Object? errorKind,
    bool clearError = false,
    List<String>? availableFactorIds,
    List<String>? warnings,
    List<String>? influenceLabels,
  }) => AstroAIState(
    messages: messages ?? this.messages,
    status: status ?? this.status,
    errorKind: clearError ? null : (errorKind ?? this.errorKind),
    availableFactorIds: availableFactorIds ?? this.availableFactorIds,
    warnings: warnings ?? this.warnings,
    influenceLabels: influenceLabels ?? this.influenceLabels,
  );
}

/// Owns the Astro AI conversation.
///
/// It assembles the astrology context (chart + active transits) from the
/// engine, hands it to [AstroAIRepository] and folds the streamed answer into
/// the message list.
class AstroAIController extends Notifier<AstroAIState> {
  StreamSubscription<AstroAIEvent>? _subscription;
  Completer<void>? _done;
  int _generation = 0;

  @override
  AstroAIState build() {
    ref.onDispose(() {
      _generation++;
      _subscription?.cancel();
      if (_done?.isCompleted == false) _done!.complete();
    });
    ref.watch(astroAIRepositoryProvider);
    return const AstroAIState();
  }

  Future<void> send(String rawMessage) async {
    final String message = rawMessage.trim();
    if (message.isEmpty || state.isBusy) return;

    final int generation = ++_generation;

    final UserProfile? user = ref.read(currentUserProvider);
    if (user == null) return;

    final DateTime now = DateTime.now();
    final ChatMessage userMessage = ChatMessage(
      id: 'u-${now.microsecondsSinceEpoch}',
      role: ChatRole.user,
      text: message,
      createdAt: now,
    );
    final String replyId = 'a-${now.microsecondsSinceEpoch}';

    state = state.copyWith(
      messages: <ChatMessage>[...state.messages, userMessage],
      status: AstroAIStatus.thinking,
      clearError: true,
    );

    try {
      final repository = ref.read(astroAIRepositoryProvider);
      final AstroAIContext? context = repository is ApiAstroAIRepository
          ? null
          : await ref
                .read(astrologyServiceProvider)
                .getAstroAIContext(profile: user, at: now);

      final List<ChatMessage> history = List<ChatMessage>.unmodifiable(
        state.messages,
      );

      if (generation != _generation) return;
      final Stream<AstroAIEvent> stream = repository is ApiAstroAIRepository
          ? repository.streamChat(message)
          : repository.sendMessage(
              message: message,
              userProfile: user,
              natalChart: context!.natalChart,
              activeTransits: context.activeTransits,
              history: history,
            );

      final ChatMessage placeholder = ChatMessage(
        id: replyId,
        role: ChatRole.astroAi,
        text: '',
        createdAt: DateTime.now(),
        status: ChatMessageStatus.streaming,
      );
      state = state.copyWith(
        messages: <ChatMessage>[...state.messages, placeholder],
        status: AstroAIStatus.typing,
      );

      await _subscription?.cancel();
      final Completer<void> done = Completer<void>();
      _done = done;
      _subscription = stream.listen(
        (AstroAIEvent event) {
          switch (event) {
            case AstroAITextDelta(:final String text):
              _appendText(replyId, text);
            case AstroAICompleted(:final List<TransitSummary> influences):
              _complete(replyId, influences);
            case AstroAIMetadata(
              :final warnings,
              :final availableFactorIds,
              :final influenceLabels,
            ):
              state = state.copyWith(
                warnings: warnings,
                availableFactorIds: availableFactorIds,
                influenceLabels: influenceLabels,
              );
          }
        },
        onError: (Object error, StackTrace stackTrace) {
          _fail(replyId, error);
          if (!done.isCompleted) done.complete();
        },
        onDone: () {
          if (!done.isCompleted) done.complete();
        },
        cancelOnError: true,
      );
      await done.future;
    } on Object catch (error) {
      _fail(replyId, error);
    }
  }

  void _appendText(String id, String delta) {
    state = state.copyWith(
      status: AstroAIStatus.typing,
      messages: <ChatMessage>[
        for (final ChatMessage message in state.messages)
          if (message.id == id)
            message.copyWith(
              text: message.text + delta,
              status: ChatMessageStatus.streaming,
            )
          else
            message,
      ],
    );
  }

  void _complete(String id, List<TransitSummary> influences) {
    state = state.copyWith(
      status: AstroAIStatus.answering,
      messages: <ChatMessage>[
        for (final ChatMessage message in state.messages)
          if (message.id == id)
            message.copyWith(
              influences: influences,
              status: ChatMessageStatus.sent,
            )
          else
            message,
      ],
    );
  }

  void _fail(String id, Object error) {
    state = state.copyWith(
      status: AstroAIStatus.error,
      errorKind: error,
      messages: <ChatMessage>[
        for (final ChatMessage message in state.messages)
          if (message.id == id)
            message.copyWith(
              status: message.text.isEmpty
                  ? ChatMessageStatus.failed
                  : ChatMessageStatus.partial,
            )
          else
            message,
      ],
    );
  }

  /// Placeholder for the planned voice flow; keeps the state machine honest.
  Future<void> startListening() async {
    final VoiceInputService service = ref.read(voiceInputServiceProvider);
    if (!service.isAvailable) return;
    state = state.copyWith(status: AstroAIStatus.listening);
  }

  void clear() {
    cancel();
    final repository = ref.read(astroAIRepositoryProvider);
    if (repository is ApiAstroAIRepository) repository.conversationId = null;
    state = const AstroAIState();
  }

  void cancel() {
    _generation++;
    _subscription?.cancel();
    if (_done?.isCompleted == false) _done!.complete();
    state = state.copyWith(
      status: AstroAIStatus.idle,
      messages: [
        for (final message in state.messages)
          message.status == ChatMessageStatus.streaming
              ? message.copyWith(status: ChatMessageStatus.cancelled)
              : message,
      ],
    );
  }

  Future<void> openConversation(String id) async {
    cancel();
    final repository = ref.read(astroAIRepositoryProvider);
    if (repository is! ApiAstroAIRepository) return;
    final messages = await repository.messages(id);
    repository.conversationId = id;
    state = AstroAIState(
      messages: [
        for (final m in messages.where((m) => m.text('role') != 'system_note'))
          ChatMessage(
            id: m.text('id'),
            role: m.text('role') == 'user' ? ChatRole.user : ChatRole.astroAi,
            text: m.content,
            createdAt: DateTime.parse(m.text('created_at')),
            status: switch (m.completionStatus) {
              'completed' => ChatMessageStatus.sent,
              'cancelled' => ChatMessageStatus.cancelled,
              _ => ChatMessageStatus.partial,
            },
          ),
      ],
    );
  }
}

final NotifierProvider<AstroAIController, AstroAIState>
astroAIControllerProvider = NotifierProvider<AstroAIController, AstroAIState>(
  AstroAIController.new,
);
