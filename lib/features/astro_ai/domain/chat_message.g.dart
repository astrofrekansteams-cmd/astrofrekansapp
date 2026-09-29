// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'chat_message.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_ChatMessage _$ChatMessageFromJson(Map<String, dynamic> json) => _ChatMessage(
  id: json['id'] as String,
  role: $enumDecode(_$ChatRoleEnumMap, json['role']),
  text: json['text'] as String,
  createdAt: DateTime.parse(json['created_at'] as String),
  influences:
      (json['influences'] as List<dynamic>?)
          ?.map((e) => TransitSummary.fromJson(e as Map<String, dynamic>))
          .toList() ??
      const <TransitSummary>[],
  status:
      $enumDecodeNullable(_$ChatMessageStatusEnumMap, json['status']) ??
      ChatMessageStatus.sent,
);

Map<String, dynamic> _$ChatMessageToJson(_ChatMessage instance) =>
    <String, dynamic>{
      'id': instance.id,
      'role': _$ChatRoleEnumMap[instance.role]!,
      'text': instance.text,
      'created_at': instance.createdAt.toIso8601String(),
      'influences': instance.influences.map((e) => e.toJson()).toList(),
      'status': _$ChatMessageStatusEnumMap[instance.status]!,
    };

const _$ChatRoleEnumMap = {ChatRole.user: 'user', ChatRole.astroAi: 'astroAi'};

const _$ChatMessageStatusEnumMap = {
  ChatMessageStatus.sending: 'sending',
  ChatMessageStatus.streaming: 'streaming',
  ChatMessageStatus.sent: 'sent',
  ChatMessageStatus.failed: 'failed',
  ChatMessageStatus.partial: 'partial',
  ChatMessageStatus.cancelled: 'cancelled',
};
