import 'dart:async';

/// Provider-neutral contracts for the planned Firebase and LiveKit adapters.
/// No credentials or network SDKs are needed until those integrations land.
class IdentitySession {
  const IdentitySession({required this.userId, required this.idToken});

  final String userId;
  final String idToken;
}

abstract interface class IdentityProvider {
  Stream<IdentitySession?> watchSession();
  Future<String?> freshIdToken();
  Future<void> signOut();
}

class ChatMessageRecord {
  const ChatMessageRecord({
    required this.id,
    required this.senderId,
    required this.body,
    required this.sentAt,
  });

  final String id;
  final String senderId;
  final String body;
  final DateTime sentAt;
}

abstract interface class RealtimeChatService {
  Stream<List<ChatMessageRecord>> watchConversation(String conversationId);
  Future<void> sendMessage(String conversationId, String body);
}

enum PresenceState { offline, online, busy }

abstract interface class PresenceService {
  Future<void> setOnline();
  Future<void> setOffline();
  Stream<PresenceState> watchUser(String userId);
}

abstract interface class MediaUploadService {
  Future<Uri> uploadAttachment({
    required String conversationId,
    required String fileName,
    required List<int> bytes,
  });
}

abstract interface class PushNotificationService {
  Future<void> registerDeviceToken(String token);
  Future<void> unregisterDeviceToken();
}

abstract interface class CallService {
  Future<void> joinAudio({required String roomId, required String token});
  Future<void> joinVideo({required String roomId, required String token});
  Future<void> leave();
}

/// Explicitly unavailable until project credentials and rules are approved.
class DisabledRealtimeServices
    implements
        IdentityProvider,
        RealtimeChatService,
        PresenceService,
        MediaUploadService,
        PushNotificationService,
        CallService {
  const DisabledRealtimeServices();

  Never _disabled() =>
      throw StateError('Realtime integration is not configured.');

  @override
  Stream<IdentitySession?> watchSession() =>
      Stream<IdentitySession?>.value(null);

  @override
  Future<String?> freshIdToken() async => null;

  @override
  Future<void> signOut() async => _disabled();

  @override
  Stream<List<ChatMessageRecord>> watchConversation(String conversationId) =>
      Stream<List<ChatMessageRecord>>.error(
        StateError('Realtime integration is not configured.'),
      );

  @override
  Future<void> sendMessage(String conversationId, String body) async =>
      _disabled();

  @override
  Future<void> setOnline() async => _disabled();

  @override
  Future<void> setOffline() async => _disabled();

  @override
  Stream<PresenceState> watchUser(String userId) => Stream<PresenceState>.error(
    StateError('Realtime integration is not configured.'),
  );

  @override
  Future<Uri> uploadAttachment({
    required String conversationId,
    required String fileName,
    required List<int> bytes,
  }) async => _disabled();

  @override
  Future<void> registerDeviceToken(String token) async => _disabled();

  @override
  Future<void> unregisterDeviceToken() async => _disabled();

  @override
  Future<void> joinAudio({
    required String roomId,
    required String token,
  }) async => _disabled();

  @override
  Future<void> joinVideo({
    required String roomId,
    required String token,
  }) async => _disabled();

  @override
  Future<void> leave() async => _disabled();
}
