import '../../../core/astrology/data/api_contract_dto.dart';
import '../../../core/astrology/data/production_models.dart';
import '../../marketplace/data/marketplace_models.dart' show wireEnum;

enum CallType { audio, video, unknown }

enum CallStatus {
  scheduled,
  waiting,
  ringing,
  active,
  ended,
  missed,
  cancelled,
  failed,
  unknown,
}

enum CallEndReason {
  userEnded,
  expertEnded,
  missed,
  timeout,
  providerError,
  networkDisconnect,
  appointmentCancelled,
  orderCancelled,
  expertSuspended,
  noShow,
  system,
  unknown,
}

class CallParticipant extends ContractRecord {
  CallParticipant(super.value);
  String get role => optionalText('role') ?? 'unknown';
  String get status => optionalText('status') ?? 'unknown';
  bool get isMe => json['is_me'] == true;
}

class CallSession extends ContractRecord {
  CallSession(super.value) {
    text('id');
    text('order_id');
    if (json.containsKey('token') || json.containsKey('livekit_url')) {
      throw const FormatException('Call GET must not contain join credentials');
    }
  }

  String get id => text('id');
  String get orderId => text('order_id');
  String get myRole => optionalText('my_role') ?? 'unknown';
  String? get appointmentId => optionalText('appointment_id');
  String? get conversationId => optionalText('conversation_id');
  CallType get type =>
      wireEnum(CallType.values, optionalText('call_type'), CallType.unknown);
  CallStatus get status =>
      wireEnum(CallStatus.values, optionalText('status'), CallStatus.unknown);
  CallEndReason? get endReason => optionalText('end_reason') == null
      ? null
      : wireEnum(
          CallEndReason.values,
          optionalText('end_reason'),
          CallEndReason.unknown,
        );
  DateTime? get startedAt => ContractJson.optionalDate(json, 'started_at');
  DateTime? get endedAt => ContractJson.optionalDate(json, 'ended_at');
  DateTime get createdAt => ContractJson.date(json, 'created_at');
  DateTime? get joinOpensAt => ContractJson.optionalDate(json, 'join_opens_at');
  DateTime? get joinClosesAt =>
      ContractJson.optionalDate(json, 'join_closes_at');
  int? get durationSeconds =>
      json['duration_seconds'] is int ? json['duration_seconds'] as int : null;
  List<CallParticipant> get participants => ContractJson.maps(
    json['participants'] ?? [],
  ).map(CallParticipant.new).toList(growable: false);
  bool get isTerminal => const {
    CallStatus.ended,
    CallStatus.missed,
    CallStatus.cancelled,
    CallStatus.failed,
  }.contains(status);
}

class CallSummary extends ContractRecord {
  CallSummary(super.value);
  String get id => text('id');
  String get orderId => text('order_id');
  String get myRole => optionalText('my_role') ?? 'unknown';
  CallType get type =>
      wireEnum(CallType.values, optionalText('call_type'), CallType.unknown);
  CallStatus get status =>
      wireEnum(CallStatus.values, optionalText('status'), CallStatus.unknown);
  DateTime get createdAt => ContractJson.date(json, 'created_at');
  int? get durationSeconds =>
      json['duration_seconds'] is int ? json['duration_seconds'] as int : null;
}

class CallPage extends ContractRecord {
  CallPage(super.value);
  List<CallSummary> get items => ContractJson.maps(
    json['items'],
  ).map(CallSummary.new).toList(growable: false);
  DateTime? get nextCursor => ContractJson.optionalDate(json, 'next_cursor');
}

/// Credentials exist only in the join call's in-memory return value.
class CallJoinGrant {
  CallJoinGrant(Map<String, dynamic> json)
    : callId = json['call_id'] as String,
      type = wireEnum(
        CallType.values,
        json['call_type'] as String?,
        CallType.unknown,
      ),
      livekitUrl = json['livekit_url'] as String,
      token = json['token'] as String;

  final String callId;
  final CallType type;
  final String livekitUrl;
  final String token;

  @override
  String toString() => 'CallJoinGrant(redacted)';
}

class CallAvailability extends ContractRecord {
  CallAvailability(super.value);
  bool get configured => json['configured'] == true;
  String get provider => optionalText('provider') ?? 'unknown';
}
