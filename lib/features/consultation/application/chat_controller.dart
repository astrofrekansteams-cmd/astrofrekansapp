import 'dart:async';
import 'package:flutter/foundation.dart';

import '../../../core/network/api_exception.dart';
import '../../marketplace/data/marketplace_repository.dart' show newClientId;
import '../data/attachment_service.dart';
import '../data/consultation_models.dart';
import '../data/consultation_repository.dart';
import '../data/realtime_services.dart';

enum ChatViewStatus {
  loadingHistory,
  ready,
  sending,
  uploading,
  readOnly,
  closed,
  error,
}

class ChatController extends ChangeNotifier {
  ChatController({
    required this.api,
    required this.realtime,
    required this.presence,
    required this.attachments,
    required this.picker,
  });
  final ConsultationRepository api;
  final RealtimeMessageService realtime;
  final ConsultationPresenceService presence;
  final AttachmentCoordinator attachments;
  final ChatImagePicker picker;
  ChatViewStatus status = ChatViewStatus.loadingHistory;
  Conversation? conversation;
  ChatPolicy? policy;
  List<ConsultationMessage> messages = [];
  Map<String, ChatAttachment> attachmentById = {};
  bool hasMore = false, partnerTyping = false;
  PartnerPresence partnerPresence = const PartnerPresence(
    online: false,
    available: false,
  );
  Object? error;
  OutgoingMessage? pending;
  int? retryAfterSeconds;
  double uploadProgress = 0;
  AttachmentUpload? _upload;
  PickedChatImage? _retryImage;
  String? _cursor;
  StreamSubscription<List<ConsultationMessage>>? _messagesSub;
  StreamSubscription<PartnerPresence>? _presenceSub;
  StreamSubscription<bool>? _typingSub;
  Timer? _typingDebounce, _typingExpiry;
  Timer? _retryTimer;
  bool _disposed = false, _typing = false;
  int get activeListeners =>
      [_messagesSub, _presenceSub, _typingSub].where((s) => s != null).length;
  bool get canRetryImage => _retryImage != null;

  Future<void> load(String conversationId) async {
    await _messagesSub?.cancel();
    await _presenceSub?.cancel();
    await _typingSub?.cancel();
    _messagesSub = null;
    _presenceSub = null;
    _typingSub = null;
    attachmentById = {};
    status = ChatViewStatus.loadingHistory;
    error = null;
    notifyListeners();
    try {
      final c = await api.conversation(conversationId);
      if (_disposed) return;
      conversation = c;
      if (!c.canRead) {
        throw const ApiException(
          kind: ApiErrorKind.forbidden,
          code: 'conversation_not_allowed',
        );
      }
      policy = await api.policy();
      if (_disposed) return;
      final page = await api.history(c.id);
      if (_disposed) return;
      messages = page.items;
      hasMore = page.hasMore;
      _cursor = page.nextCursor;
      status = _status(c);
      notifyListeners();
      unawaited(_loadAttachmentMetadata(c.id));
      _messagesSub = realtime
          .watchRecent(c)
          .listen(
            _merge,
            onError: (Object e) {
              if (_disposed) return;
              error = e;
              notifyListeners();
            },
          );
      _presenceSub = presence
          .watchPartner(c)
          .listen(
            (p) {
              if (_disposed) return;
              partnerPresence = p;
              notifyListeners();
            },
            onError: (Object _) {
              if (_disposed) return;
              partnerPresence = const PartnerPresence(
                online: false,
                available: false,
              );
              notifyListeners();
            },
          );
      _typingSub = presence
          .watchPartnerTyping(c)
          .listen(
            (v) {
              if (_disposed) return;
              partnerTyping = v;
              notifyListeners();
            },
            onError: (Object _) {
              if (_disposed) return;
              partnerTyping = false;
              notifyListeners();
            },
          );
    } on Object catch (e) {
      if (!_disposed) {
        error = e;
        status = ChatViewStatus.error;
        notifyListeners();
      }
    }
  }

  Future<void> _loadAttachmentMetadata(String conversationId) async {
    try {
      final rows = await api.attachments(conversationId);
      if (_disposed || conversation?.id != conversationId) return;
      attachmentById = {for (final row in rows) row.id: row};
      notifyListeners();
    } on Object {
      // Text messages remain readable if the attachment projection is offline.
    }
  }

  ChatViewStatus _status(Conversation c) => switch (c.status) {
    ConversationStatus.active when c.canWrite => ChatViewStatus.ready,
    ConversationStatus.closed ||
    ConversationStatus.suspended => ChatViewStatus.closed,
    _ => ChatViewStatus.readOnly,
  };
  void _merge(List<ConsultationMessage> incoming) {
    if (_disposed) return;
    final byId = {for (final m in messages) m.id: m};
    for (final m in incoming) {
      byId[m.id] = m;
    }
    messages = byId.values.toList()
      ..sort((a, b) => a.createdAt.compareTo(b.createdAt));
    notifyListeners();
  }

  Future<void> loadMore() async {
    final c = conversation;
    if (c == null || !hasMore || _cursor == null) return;
    try {
      final page = await api.history(c.id, before: _cursor);
      if (_disposed) return;
      _merge(page.items);
      hasMore = page.hasMore;
      _cursor = page.nextCursor;
      notifyListeners();
    } on Object catch (e) {
      if (!_disposed) {
        error = e;
        notifyListeners();
      }
    }
  }

  Future<void> sendText(String value) async {
    final text = value.trim();
    if (text.isEmpty) return;
    if (conversation?.canWrite != true) {
      throw const ApiException(
        kind: ApiErrorKind.forbidden,
        code: 'chat_read_only',
      );
    }
    if (pending != null) {
      throw const ApiException(
        kind: ApiErrorKind.validation,
        code: 'idempotency_conflict',
      );
    }
    if (text.length > (policy?.maxMessageLength ?? 4000)) {
      throw const ApiException(
        kind: ApiErrorKind.validation,
        code: 'message_rejected',
      );
    }
    pending = OutgoingMessage(clientMessageId: newClientId(), text: text);
    await _sendPending();
  }

  Future<void> retryPending() async {
    if ((retryAfterSeconds ?? 0) > 0) return;
    await _sendPending();
  }

  Future<void> _sendPending() async {
    final c = conversation, m = pending;
    if (c == null || m == null) return;
    if (!c.canWrite) {
      throw const ApiException(
        kind: ApiErrorKind.forbidden,
        code: 'chat_read_only',
      );
    }
    status = ChatViewStatus.sending;
    error = null;
    notifyListeners();
    await setTyping(false);
    try {
      final sent = await api.send(c.id, m);
      if (_disposed) return;
      _merge([sent]);
      pending = null;
      retryAfterSeconds = null;
      _retryTimer?.cancel();
    } on ApiException catch (e) {
      if (!_disposed) {
        error = e;
        _setCooldown(e.retryAfterSeconds);
      }
    } on Object catch (e) {
      if (!_disposed) error = e;
    } finally {
      if (!_disposed) {
        status = _status(c);
        notifyListeners();
      }
    }
  }

  void _setCooldown(int? seconds) {
    _retryTimer?.cancel();
    retryAfterSeconds = seconds;
    if (seconds == null || seconds <= 0) return;
    _retryTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_disposed) {
        timer.cancel();
        return;
      }
      retryAfterSeconds = (retryAfterSeconds ?? 1) - 1;
      if (retryAfterSeconds! <= 0) timer.cancel();
      notifyListeners();
    });
  }

  Future<void> deleteOwn(ConsultationMessage message) async {
    final c = conversation;
    if (c == null || !message.isMine(c.myRole) || message.deleted) return;
    try {
      final deleted = await api.deleteOwn(c.id, message.id);
      _merge([deleted]);
    } on Object catch (e) {
      error = e;
      notifyListeners();
    }
  }

  Future<void> pickAndSendImage() async {
    if ((retryAfterSeconds ?? 0) > 0) return;
    try {
      final image = await picker.pick();
      if (image == null) return;
      _retryImage = image;
      await _uploadImage(image);
    } on Object catch (e) {
      if (!_disposed) {
        error = e;
        notifyListeners();
      }
    }
  }

  Future<void> retryImage() async {
    if ((retryAfterSeconds ?? 0) > 0) return;
    final image = _retryImage;
    if (image != null) await _uploadImage(image);
  }

  Future<void> _uploadImage(PickedChatImage image) async {
    final c = conversation;
    if (c == null || !c.canWrite) return;
    status = ChatViewStatus.uploading;
    uploadProgress = 0;
    error = null;
    notifyListeners();
    try {
      final ready = await attachments.uploadReady(
        c.id,
        image,
        onProgress: (v) {
          uploadProgress = v;
          notifyListeners();
        },
        onStarted: (operation) => _upload = operation,
      );
      if (_disposed) return;
      attachmentById = {...attachmentById, ready.id: ready};
      pending = OutgoingMessage(
        clientMessageId: newClientId(),
        attachmentId: ready.id,
      );
      _retryImage = null;
      await _sendPending();
    } on Object catch (e) {
      if (!_disposed) {
        error = e;
        if (e is ApiException) _setCooldown(e.retryAfterSeconds);
        status = _status(c);
        notifyListeners();
      }
    } finally {
      _upload = null;
    }
  }

  Future<void> cancelUpload() async {
    await _upload?.cancel();
    _upload = null;
    _retryImage = null;
    if (conversation case final c?) {
      status = _status(c);
      notifyListeners();
    }
  }

  void composerChanged(String text) {
    final c = conversation;
    if (c == null || !c.canWrite) return;
    _typingDebounce?.cancel();
    _typingExpiry?.cancel();
    if (text.trim().isEmpty) {
      unawaited(setTyping(false));
      return;
    }
    _typingDebounce = Timer(
      const Duration(milliseconds: 350),
      () => unawaited(setTyping(true)),
    );
    _typingExpiry = Timer(
      const Duration(seconds: 4),
      () => unawaited(setTyping(false)),
    );
  }

  Future<void> setTyping(bool value) async {
    if (_typing == value) return;
    final c = conversation;
    if (c == null) return;
    _typing = value;
    try {
      await presence.setTyping(c, value);
    } on Object {
      _typing = false;
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _typingDebounce?.cancel();
    _typingExpiry?.cancel();
    _retryTimer?.cancel();
    _messagesSub?.cancel();
    _presenceSub?.cancel();
    _typingSub?.cancel();
    _upload?.cancel();
    final c = conversation;
    if (c != null) {
      unawaited(presence.setTyping(c, false).catchError((Object _) {}));
    }
    super.dispose();
  }
}
