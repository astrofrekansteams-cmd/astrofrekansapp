import '../../../core/astrology/data/api_contract_dto.dart';
import '../../../core/astrology/data/production_models.dart';
import '../../marketplace/data/marketplace_models.dart' show wireEnum;

enum ConversationStatus { active, readOnly, closed, suspended, unknown }

enum MessageType { text, image, file, system, unknown }

enum MessageDelivery { sending, sent, failed, deleted }

class Conversation extends ContractRecord {
  Conversation(super.value) {
    text('id');
    text('order_id');
    text('status');
  }
  String get id => text('id');
  String get orderId => text('order_id');
  String? get firebaseId => optionalText('firebase_conversation_id');
  String? get expertId => optionalText('expert_id');
  String? get counterpart => optionalText('counterpart_display_name');
  String get myRole => text('my_role');
  ConversationStatus get status => wireEnum(
    ConversationStatus.values,
    text('status'),
    ConversationStatus.unknown,
  );
  String? get provisioningStatus => optionalText('provisioning_status');
  bool get canRead => (json['permission'] as Map?)?['can_read'] == true;
  bool get canWrite =>
      status == ConversationStatus.active &&
      (json['permission'] as Map?)?['can_write'] == true;
  String? get permissionReason =>
      (json['permission'] as Map?)?['reason'] as String?;
  int get messageCount => json['message_count'] as int;
  DateTime? get lastMessageAt =>
      ContractJson.optionalDate(json, 'last_message_at');
}

class ConsultationMessage extends ContractRecord {
  ConsultationMessage(super.value) {
    text('message_id');
    text('sender_role');
  }
  String get id => text('message_id');
  String get senderRole => text('sender_role');
  String? get senderUid => optionalText('sender_uid');
  String? get textBody => optionalText('text');
  String? get attachmentId => optionalText('attachment_id');
  String? get clientMessageId => optionalText('client_message_id');
  MessageType get type => wireEnum(
    MessageType.values,
    optionalText('message_type'),
    MessageType.unknown,
  );
  DateTime get createdAt => ContractJson.date(json, 'created_at').toUtc();
  bool get deleted => json['deleted_at'] != null;
  bool isMine(String myRole) => senderRole == myRole;
}

class MessagePage extends ContractRecord {
  MessagePage(super.value) {
    records('items');
  }
  List<ConsultationMessage> get items => ContractJson.maps(
    json['items'],
  ).map(ConsultationMessage.new).toList(growable: false);
  String? get nextCursor => optionalText('next_cursor');
  bool get hasMore => json['has_more'] == true;
}

class ChatPolicy extends ContractRecord {
  ChatPolicy(super.value) {
    number('message_max_length');
    number('attachment_max_bytes');
  }
  int get maxMessageLength => json['message_max_length'] as int;
  int get attachmentMaxBytes => json['attachment_max_bytes'] as int;
  List<String> get allowedMimeTypes => strings('attachment_allowed_mime_types');
}

class AttachmentIntent extends ContractRecord {
  AttachmentIntent(super.value) {
    record('attachment');
    record('upload');
  }
  String get id => (json['attachment'] as Map)['id'] as String;
  String get storageKey => (json['upload'] as Map)['storage_key'] as String;
  String get bucket => (json['upload'] as Map)['bucket'] as String;
  int get maxBytes => (json['upload'] as Map)['max_bytes'] as int;
  List<String> get allowedMimes =>
      List<String>.from((json['upload'] as Map)['allowed_mime_types'] as List);
}

class ChatAttachment extends ContractRecord {
  ChatAttachment(super.value) {
    text('id');
    text('status');
  }
  String get id => text('id');
  String get status => text('status');
  bool get ready => status == 'ready';
  String get storageKey => text('storage_key');
  String get mimeType => text('mime_type');
}

class PushDevice extends ContractRecord {
  PushDevice(super.value) {
    text('id');
    text('token_fingerprint');
  }
  String get id => text('id');
  String get fingerprint => text('token_fingerprint');
}

/// Retrying keeps the same ID and exact text/attachment payload.
class OutgoingMessage {
  const OutgoingMessage({
    required this.clientMessageId,
    this.text,
    this.attachmentId,
  });
  final String clientMessageId;
  final String? text, attachmentId;
  Json get payload => {
    'client_message_id': clientMessageId,
    if (text != null) 'text': text,
    if (attachmentId != null) 'attachment_id': attachmentId,
  };
}
