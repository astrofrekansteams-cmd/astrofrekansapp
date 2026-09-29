import 'package:freezed_annotation/freezed_annotation.dart';

import '../../../core/astrology/domain/transit.dart';

part 'chat_message.freezed.dart';
part 'chat_message.g.dart';

enum ChatRole { user, astroAi }

enum ChatMessageStatus { sending, streaming, sent, failed, partial, cancelled }

/// One line of the Astro AI conversation.
///
/// [influences] are the structured sky factors behind an answer; the UI renders
/// them under the bubble as "Bu yorumu oluşturan etkiler".
@freezed
abstract class ChatMessage with _$ChatMessage {
  const factory ChatMessage({
    required String id,
    required ChatRole role,
    required String text,
    required DateTime createdAt,
    @Default(<TransitSummary>[]) List<TransitSummary> influences,
    @Default(ChatMessageStatus.sent) ChatMessageStatus status,
  }) = _ChatMessage;

  const ChatMessage._();

  factory ChatMessage.fromJson(Map<String, dynamic> json) =>
      _$ChatMessageFromJson(json);

  bool get isUser => role == ChatRole.user;
}
