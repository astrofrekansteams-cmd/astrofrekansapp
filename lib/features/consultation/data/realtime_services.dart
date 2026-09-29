import 'dart:async';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_database/firebase_database.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/firebase_client.dart';
import '../../../core/network/api_exception.dart';
import 'consultation_models.dart';
import 'consultation_repository.dart';

abstract interface class RealtimeMessageService {
  Stream<List<ConsultationMessage>> watchRecent(
    Conversation conversation, {
    int limit = 50,
  });
}

class FirebaseMessageReader implements RealtimeMessageService {
  FirebaseMessageReader(this.availability);
  final Future<FirebaseAvailability> availability;
  @override
  Stream<List<ConsultationMessage>> watchRecent(
    Conversation conversation, {
    int limit = 50,
  }) async* {
    if (!(await availability).ready ||
        FirebaseAuth.instance.currentUser == null ||
        !conversation.canRead ||
        conversation.firebaseId == null) {
      throw const ApiException(
        kind: ApiErrorKind.server,
        code: 'firebase_not_configured',
      );
    }
    yield* FirebaseFirestore.instance
        .collection('conversations')
        .doc(conversation.firebaseId)
        .collection('messages')
        .orderBy('createdAt', descending: true)
        .limit(limit)
        .snapshots()
        .map(
          (snapshot) => snapshot.docs
              .where((d) => d.data()['createdAt'] is Timestamp)
              .map((d) {
                final data = d.data();
                return ConsultationMessage({
                  'message_id': d.id,
                  'sender_role': data['senderRole'] as String? ?? 'unknown',
                  'sender_uid': data['senderUid'],
                  'message_type': data['type'] as String? ?? 'unknown',
                  'text': data['text'],
                  'attachment_id': data['attachmentId'],
                  'client_message_id': data['clientMessageId'],
                  'created_at': (data['createdAt'] as Timestamp)
                      .toDate()
                      .toUtc()
                      .toIso8601String(),
                  'deleted_at': (data['deletedAt'] as Timestamp?)
                      ?.toDate()
                      .toUtc()
                      .toIso8601String(),
                });
              })
              .toList(growable: false),
        );
  }
}

class UnavailableMessageReader implements RealtimeMessageService {
  const UnavailableMessageReader();
  @override
  Stream<List<ConsultationMessage>> watchRecent(
    Conversation conversation, {
    int limit = 50,
  }) => Stream.error(
    const ApiException(
      kind: ApiErrorKind.server,
      code: 'firebase_not_configured',
    ),
  );
}

final realtimeMessageServiceProvider = Provider<RealtimeMessageService>(
  (ref) => FirebaseMessageReader(ref.watch(firebaseBootstrapProvider.future)),
);

class PartnerPresence {
  const PartnerPresence({
    required this.online,
    this.lastChanged,
    this.available = true,
  });
  final bool online, available;
  final DateTime? lastChanged;
}

abstract interface class ConsultationPresenceService {
  Stream<PartnerPresence> watchPartner(Conversation conversation);
  Stream<bool> watchPartnerTyping(Conversation conversation);
  Future<void> setTyping(Conversation conversation, bool typing);
  Future<void> setOnline();
  Future<void> setOffline();
}

class FirebaseConsultationPresence implements ConsultationPresenceService {
  FirebaseConsultationPresence(this.availability, this.api);
  final Future<FirebaseAvailability> availability;
  final ConsultationRepository api;
  FirebaseDatabase get _db => FirebaseDatabase.instance;
  Future<String> _ownUid() async {
    if (!(await availability).ready) {
      throw const ApiException(
        kind: ApiErrorKind.server,
        code: 'firebase_not_configured',
      );
    }
    final uid = FirebaseAuth.instance.currentUser?.uid;
    if (uid == null) {
      throw const ApiException(
        kind: ApiErrorKind.server,
        code: 'firebase_identity_required',
      );
    }
    return uid;
  }

  @override
  Stream<PartnerPresence> watchPartner(Conversation conversation) async* {
    final uid = await _ownUid();
    if (!conversation.canRead) {
      throw const ApiException(
        kind: ApiErrorKind.forbidden,
        code: 'conversation_not_allowed',
      );
    }
    // The backend checks membership and returns only this conversation's uids.
    final allowed = await api.presence(conversation.id);
    final partner = allowed
        .where((row) => row['firebase_uid'] != uid)
        .firstOrNull;
    if (partner == null) {
      yield const PartnerPresence(online: false, available: false);
      return;
    }
    final partnerUid = partner['firebase_uid'] as String;
    yield* _db.ref('presence/$partnerUid').onValue.map((event) {
      final raw = event.snapshot.value;
      final data = raw is Map ? raw : const <String, dynamic>{};
      final changed = data['lastChanged'];
      return PartnerPresence(
        online: data['state'] == 'online',
        lastChanged: changed is int
            ? DateTime.fromMillisecondsSinceEpoch(changed, isUtc: true)
            : DateTime.tryParse('$changed'),
      );
    });
  }

  @override
  Stream<bool> watchPartnerTyping(Conversation conversation) async* {
    final uid = await _ownUid();
    if (!conversation.canRead) {
      throw const ApiException(
        kind: ApiErrorKind.forbidden,
        code: 'conversation_not_allowed',
      );
    }
    yield* _db.ref('typing/${conversation.id}').onValue.map((event) {
      final raw = event.snapshot.value;
      if (raw is! Map) return false;
      return raw.entries.any(
        (entry) =>
            entry.key != uid &&
            entry.value is Map &&
            (entry.value as Map)['typing'] == true &&
            _recentTyping((entry.value as Map)['updatedAt']),
      );
    });
  }

  bool _recentTyping(Object? timestamp) =>
      timestamp is int &&
      DateTime.now().millisecondsSinceEpoch - timestamp < 10000;
  @override
  Future<void> setTyping(Conversation conversation, bool typing) async {
    final uid = await _ownUid();
    final ref = _db.ref('typing/${conversation.id}/$uid');
    if (!typing) {
      await ref.remove();
      return;
    }
    if (!conversation.canWrite) {
      throw const ApiException(
        kind: ApiErrorKind.forbidden,
        code: 'chat_read_only',
      );
    }
    await ref.onDisconnect().remove();
    await ref.set({'typing': true, 'updatedAt': ServerValue.timestamp});
  }

  @override
  Future<void> setOnline() async {
    final uid = await _ownUid();
    final ref = _db.ref('presence/$uid');
    await ref.onDisconnect().set({
      'state': 'offline',
      'lastChanged': ServerValue.timestamp,
    });
    await ref.set({'state': 'online', 'lastChanged': ServerValue.timestamp});
  }

  @override
  Future<void> setOffline() async {
    final uid = await _ownUid();
    await _db.ref('presence/$uid').set({
      'state': 'offline',
      'lastChanged': ServerValue.timestamp,
    });
  }
}

class UnavailableConsultationPresence implements ConsultationPresenceService {
  const UnavailableConsultationPresence();
  @override
  Stream<PartnerPresence> watchPartner(Conversation c) =>
      Stream.value(const PartnerPresence(online: false, available: false));
  @override
  Stream<bool> watchPartnerTyping(Conversation c) => Stream.value(false);
  @override
  Future<void> setTyping(Conversation c, bool value) async {}
  @override
  Future<void> setOnline() async {}
  @override
  Future<void> setOffline() async {}
}

final consultationPresenceProvider = Provider<ConsultationPresenceService>(
  (ref) => FirebaseConsultationPresence(
    ref.watch(firebaseBootstrapProvider.future),
    ref.watch(consultationRepositoryProvider),
  ),
);
