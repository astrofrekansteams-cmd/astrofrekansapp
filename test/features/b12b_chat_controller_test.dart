import 'dart:async';
import 'dart:typed_data';

import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/features/consultation/application/chat_controller.dart';
import 'package:astrofrekans/features/consultation/data/attachment_service.dart';
import 'package:astrofrekans/features/consultation/data/consultation_models.dart';
import 'package:astrofrekans/features/consultation/data/consultation_repository.dart';
import 'package:astrofrekans/features/consultation/data/realtime_services.dart';
import 'package:flutter_test/flutter_test.dart';

const _id = '66666666-6666-4666-8666-666666666666';
const _attachmentId = '88888888-8888-4888-8888-888888888888';

Conversation _conversation({String status = 'active', bool write = true}) =>
    Conversation({
      'id': _id,
      'order_id': '33333333-3333-4333-8333-333333333333',
      'status': status,
      'my_role': 'user',
      'message_count': 0,
      'permission': {'can_read': true, 'can_write': write, 'reason': 'active'},
    });

ConsultationMessage _message(String id, {String role = 'user'}) =>
    ConsultationMessage({
      'message_id': id,
      'sender_role': role,
      'message_type': 'text',
      'text': 'hello',
      'created_at': '2026-09-24T10:00:00Z',
    });

class _Repository extends Fake implements ConsultationRepository {
  Conversation current = _conversation();
  final sends = <OutgoingMessage>[];
  final deleted = <String>[];
  bool failSend = false;
  bool failFinalize = false;
  int finalizeCalls = 0;
  int createAttachmentCalls = 0;
  int historyCalls = 0;

  @override
  Future<Conversation> conversation(String id) async => current;
  @override
  Future<ChatPolicy> policy() async => ChatPolicy({
    'message_max_length': 4000,
    'attachment_max_bytes': 8388608,
    'attachment_allowed_mime_types': ['image/png'],
  });
  @override
  Future<MessagePage> history(
    String id, {
    String? before,
    int limit = 50,
  }) async {
    historyCalls++;
    return MessagePage({
      'items': before == null
          ? [_message('first').json]
          : [_message('older').json],
      'has_more': before == null,
      'next_cursor': before == null ? '2026-09-24T10:00:00Z' : null,
    });
  }

  @override
  Future<ConsultationMessage> send(String id, OutgoingMessage outgoing) async {
    sends.add(outgoing);
    if (failSend) {
      throw const ApiException(
        kind: ApiErrorKind.rateLimited,
        code: 'rate_limited',
        retryAfterSeconds: 1,
      );
    }
    return _message('sent-${outgoing.clientMessageId}');
  }

  @override
  Future<ConsultationMessage> deleteOwn(String id, String messageId) async {
    deleted.add(messageId);
    return ConsultationMessage({
      ..._message(messageId).json,
      'deleted_at': '2026-09-24T10:05:00Z',
      'text': null,
    });
  }

  @override
  Future<AttachmentIntent> createAttachment(
    String id, {
    required String mime,
    required int size,
    String? filename,
  }) async {
    createAttachmentCalls++;
    return AttachmentIntent({
      'attachment': {'id': _attachmentId},
      'upload': {
        'storage_key': 'chat/$_id/$_attachmentId/file.png',
        'bucket': 'example.invalid',
        'max_bytes': 8388608,
        'allowed_mime_types': ['image/png'],
      },
    });
  }

  @override
  Future<ChatAttachment> finalizeAttachment(String id) async {
    finalizeCalls++;
    if (failFinalize) {
      throw const ApiException(
        kind: ApiErrorKind.server,
        code: 'attachment_not_ready',
      );
    }
    return ChatAttachment({
      'id': id,
      'status': 'ready',
      'storage_key': 'chat/$_id/$_attachmentId/file.png',
      'mime_type': 'image/png',
    });
  }
}

class _Realtime implements RealtimeMessageService {
  int active = 0;
  late final stream = StreamController<List<ConsultationMessage>>.broadcast(
    onListen: () => active++,
    onCancel: () => active--,
  );
  @override
  Stream<List<ConsultationMessage>> watchRecent(
    Conversation c, {
    int limit = 50,
  }) => stream.stream;
  Future<void> close() => stream.close();
}

class _Presence implements ConsultationPresenceService {
  int active = 0;
  final paths = <String>[];
  late final partners = StreamController<PartnerPresence>.broadcast(
    onListen: () => active++,
    onCancel: () => active--,
  );
  late final typing = StreamController<bool>.broadcast(
    onListen: () => active++,
    onCancel: () => active--,
  );
  @override
  Stream<PartnerPresence> watchPartner(Conversation c) {
    paths.add(c.id);
    return partners.stream;
  }

  @override
  Stream<bool> watchPartnerTyping(Conversation c) {
    paths.add(c.id);
    return typing.stream;
  }

  @override
  Future<void> setTyping(Conversation c, bool value) async {}
  @override
  Future<void> setOnline() async {}
  @override
  Future<void> setOffline() async {}
  Future<void> close() async {
    await partners.close();
    await typing.close();
  }
}

class _Picker implements ChatImagePicker {
  PickedChatImage? image;
  @override
  Future<PickedChatImage?> pick() async => image;
}

class _Upload implements AttachmentUpload {
  bool cancelled = false;
  @override
  Stream<double> get progress => Stream.value(0.5);
  @override
  Future<void> get completed async {}
  @override
  Future<void> cancel() async {
    cancelled = true;
  }
}

class _Storage extends Fake implements AttachmentStorageService {
  final uploadResult = _Upload();
  @override
  Future<AttachmentUpload> upload(
    AttachmentIntent intent,
    PickedChatImage image, {
    required String conversationId,
  }) async => uploadResult;
}

void main() {
  late _Repository api;
  late _Realtime realtime;
  late _Presence presence;
  late _Storage storage;
  late _Picker picker;
  late ChatController chat;

  setUp(() {
    api = _Repository();
    realtime = _Realtime();
    presence = _Presence();
    storage = _Storage();
    picker = _Picker();
    chat = ChatController(
      api: api,
      realtime: realtime,
      presence: presence,
      attachments: AttachmentCoordinator(api, storage),
      picker: picker,
    );
  });
  tearDown(() async {
    chat.dispose();
    await realtime.close();
    await presence.close();
  });

  test(
    'history, realtime append, duplicate suppression, pagination and disposal',
    () async {
      await chat.load(_id);
      expect(chat.messages.map((m) => m.id), ['first']);
      realtime.stream.add([_message('first'), _message('new')]);
      await Future<void>.delayed(Duration.zero);
      expect(chat.messages.map((m) => m.id), ['first', 'new']);
      await chat.loadMore();
      expect(chat.messages.map((m) => m.id), ['first', 'new', 'older']);
      expect(api.historyCalls, 2);
      expect(realtime.active, 1);
      expect(presence.active, 2);
      expect(presence.paths, everyElement(_id));
      chat.dispose();
      await Future<void>.delayed(Duration.zero);
      expect(realtime.active, 0);
      expect(presence.active, 0);
      // Prevent tearDown from disposing twice.
      chat = ChatController(
        api: api,
        realtime: realtime,
        presence: presence,
        attachments: AttachmentCoordinator(api, storage),
        picker: picker,
      );
    },
  );

  test('reopening chat replaces rather than accumulates listeners', () async {
    await chat.load(_id);
    expect(realtime.active, 1);
    expect(presence.active, 2);
    await chat.load(_id);
    expect(realtime.active, 1);
    expect(presence.active, 2);
  });

  test(
    'failed send keeps the same client message id for retry and exposes cooldown',
    () async {
      await chat.load(_id);
      api.failSend = true;
      await chat.sendText('  Merhaba  ');
      expect(chat.pending!.text, 'Merhaba');
      expect(chat.retryAfterSeconds, 1);
      await chat.retryPending();
      expect(api.sends.length, 1);
      await Future<void>.delayed(const Duration(milliseconds: 1100));
      api.failSend = false;
      await chat.retryPending();
      expect(api.sends.length, 2);
      expect(api.sends[0].clientMessageId, api.sends[1].clientMessageId);
      expect(api.sends[0].payload, api.sends[1].payload);
      expect(chat.pending, isNull);
    },
  );

  test('closed/read-only conversations cannot send', () async {
    api.current = _conversation(status: 'closed', write: false);
    await chat.load(_id);
    expect(chat.status, ChatViewStatus.closed);
    await expectLater(chat.sendText('hello'), throwsA(isA<ApiException>()));
    expect(api.sends, isEmpty);
  });

  test('only own message can be soft-deleted', () async {
    await chat.load(_id);
    await chat.deleteOwn(_message('expert', role: 'expert'));
    expect(api.deleted, isEmpty);
    await chat.deleteOwn(_message('mine'));
    expect(api.deleted, ['mine']);
  });

  test(
    'attachment finalizes before image message and failed finalize sends nothing',
    () async {
      await chat.load(_id);
      picker.image = PickedChatImage(
        bytes: Uint8List.fromList([137, 80, 78, 71]),
        mimeType: 'image/png',
        filename: 'image.png',
      );
      api.failFinalize = true;
      await chat.pickAndSendImage();
      expect(api.sends, isEmpty);
      expect(api.finalizeCalls, 1);
      api.failFinalize = false;
      await chat.retryImage();
      expect(api.sends.single.attachmentId, _attachmentId);
      expect(api.createAttachmentCalls, 2);
    },
  );

  test('invalid attachment is rejected before intent', () async {
    await chat.load(_id);
    picker.image = PickedChatImage(
      bytes: Uint8List.fromList([1]),
      mimeType: 'image/svg+xml',
      filename: 'unsafe.svg',
    );
    await chat.pickAndSendImage();
    expect(api.createAttachmentCalls, 0);
    expect(api.sends, isEmpty);
  });
}
