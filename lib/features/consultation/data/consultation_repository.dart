import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_exception.dart';
import '../../auth/application/session_controller.dart';
import 'consultation_models.dart';

/// Registering this device's push token. The server scopes it to whoever
/// the request is authenticated as, so it needs no signed-in-user state.
abstract interface class PushDeviceApi {
  Future<PushDevice> registerDevice({
    required String token,
    required String platform,
    String? deviceId,
    String? appVersion,
  });
  Future<void> unregisterDevice(String id);
}

abstract interface class ConsultationRepository implements PushDeviceApi {
  Future<ChatPolicy> policy();
  Future<List<Conversation>> conversations();
  Future<Conversation> conversation(String id);
  Future<Conversation> openForOrder(String orderId);
  Future<MessagePage> history(String id, {String? before, int limit = 50});
  Future<ConsultationMessage> send(String id, OutgoingMessage message);
  Future<ConsultationMessage> deleteOwn(String id, String messageId);
  Future<AttachmentIntent> createAttachment(
    String id, {
    required String mime,
    required int size,
    String? filename,
  });
  Future<ChatAttachment> finalizeAttachment(String id);
  Future<List<ChatAttachment>> attachments(String conversationId);
  Future<List<Map<String, dynamic>>> presence(String conversationId);
  Future<List<PushDevice>> devices();
}

class ApiConsultationRepository implements ConsultationRepository {
  const ApiConsultationRepository(this.api);
  final ApiClient api;
  String _id(String value) => Uri.encodeComponent(value);
  @override
  Future<ChatPolicy> policy() async =>
      ChatPolicy(await api.getMap('chat/policy'));
  @override
  Future<List<Conversation>> conversations() async =>
      (await api.getList('conversations')).map(Conversation.new).toList();
  @override
  Future<Conversation> conversation(String id) async =>
      Conversation(await api.getMap('conversations/${_id(id)}'));
  @override
  Future<Conversation> openForOrder(String orderId) async => Conversation(
    await api.postMap('conversations', data: {'order_id': orderId}),
  );
  @override
  Future<MessagePage> history(
    String id, {
    String? before,
    int limit = 50,
  }) async {
    final query = <String, dynamic>{'limit': limit};
    if (before != null) {
      query['before'] = before;
    }
    return MessagePage(
      await api.getMap(
        'conversations/${_id(id)}/messages',
        queryParameters: query,
      ),
    );
  }

  @override
  Future<ConsultationMessage> send(String id, OutgoingMessage message) async =>
      ConsultationMessage(
        await api.postMap(
          'conversations/${_id(id)}/messages',
          data: message.payload,
        ),
      );
  @override
  Future<ConsultationMessage> deleteOwn(String id, String messageId) async =>
      ConsultationMessage(
        await api.deleteMap(
          'conversations/${_id(id)}/messages/${_id(messageId)}',
        ),
      );
  @override
  Future<AttachmentIntent> createAttachment(
    String id, {
    required String mime,
    required int size,
    String? filename,
  }) async => AttachmentIntent(
    await api.postMap(
      'conversations/${_id(id)}/attachments',
      data: {
        'mime_type': mime,
        'size_bytes': size,
        'original_filename': filename,
      },
    ),
  );
  @override
  Future<ChatAttachment> finalizeAttachment(String id) async =>
      ChatAttachment(await api.postMap('attachments/${_id(id)}/finalize'));
  @override
  Future<List<ChatAttachment>> attachments(String conversationId) async =>
      (await api.getList(
        'conversations/${_id(conversationId)}/attachments',
      )).map(ChatAttachment.new).toList();
  @override
  Future<List<Map<String, dynamic>>> presence(String conversationId) =>
      api.getList('conversations/${_id(conversationId)}/presence');
  @override
  Future<PushDevice> registerDevice({
    required String token,
    required String platform,
    String? deviceId,
    String? appVersion,
  }) async {
    final data = <String, dynamic>{'token': token, 'platform': platform};
    if (deviceId != null) {
      data['device_id'] = deviceId;
    }
    if (appVersion != null) {
      data['app_version'] = appVersion;
    }
    return PushDevice(await api.postMap('devices/push', data: data));
  }

  @override
  Future<List<PushDevice>> devices() async =>
      (await api.getList('devices/push')).map(PushDevice.new).toList();
  @override
  Future<void> unregisterDevice(String id) =>
      api.delete('devices/push/${_id(id)}');
}

class UnavailableConsultationRepository implements ConsultationRepository {
  const UnavailableConsultationRepository();
  ApiException get _unavailable => const ApiException(
    kind: ApiErrorKind.server,
    code: 'firebase_not_configured',
  );
  @override
  Future<ChatPolicy> policy() async => throw _unavailable;
  @override
  Future<List<Conversation>> conversations() async => [];
  @override
  Future<Conversation> conversation(String id) async => throw _unavailable;
  @override
  Future<Conversation> openForOrder(String id) async => throw _unavailable;
  @override
  Future<MessagePage> history(
    String id, {
    String? before,
    int limit = 50,
  }) async =>
      MessagePage({'items': <Map<String, dynamic>>[], 'has_more': false});
  @override
  Future<ConsultationMessage> send(String id, OutgoingMessage m) async =>
      throw _unavailable;
  @override
  Future<ConsultationMessage> deleteOwn(String id, String m) async =>
      throw _unavailable;
  @override
  Future<AttachmentIntent> createAttachment(
    String id, {
    required String mime,
    required int size,
    String? filename,
  }) async => throw _unavailable;
  @override
  Future<ChatAttachment> finalizeAttachment(String id) async =>
      throw _unavailable;
  @override
  Future<List<ChatAttachment>> attachments(String id) async => [];
  @override
  Future<List<Map<String, dynamic>>> presence(String id) async => [];
  @override
  Future<PushDevice> registerDevice({
    required String token,
    required String platform,
    String? deviceId,
    String? appVersion,
  }) async => throw _unavailable;
  @override
  Future<List<PushDevice>> devices() async => [];
  @override
  Future<void> unregisterDevice(String id) async => throw _unavailable;
}

final consultationRepositoryProvider = Provider<ConsultationRepository>((ref) {
  ref.watch(currentUserProvider)?.id;
  return ref.watch(appEnvironmentProvider).useMocks
      ? const UnavailableConsultationRepository()
      : ApiConsultationRepository(ApiClient(ref.watch(dioProvider)));
});

/// Push device registration, independent of the session.
///
/// The session controller registers the device after sign-in, so this must
/// not depend on anything derived from the session (such as
/// [currentUserProvider]): that would make `sessionProvider` depend on itself.
/// The bearer token is attached per request by [dioProvider].
final pushDeviceApiProvider = Provider<PushDeviceApi>(
  (ref) => ref.watch(appEnvironmentProvider).useMocks
      ? const UnavailableConsultationRepository()
      : ApiConsultationRepository(ApiClient(ref.watch(dioProvider))),
);
