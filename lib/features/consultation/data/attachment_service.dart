import 'dart:async';
import 'dart:typed_data';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/config/firebase_client.dart';
import '../../../core/network/api_exception.dart';
import 'consultation_models.dart';
import 'consultation_repository.dart';

const allowedImageMime = <String>{'image/jpeg', 'image/png', 'image/webp'};
const maxImageBytes = 8 * 1024 * 1024;

class PickedChatImage {
  const PickedChatImage({
    required this.bytes,
    required this.mimeType,
    required this.filename,
  });
  final Uint8List bytes;
  final String mimeType, filename;
}

abstract interface class ChatImagePicker {
  Future<PickedChatImage?> pick();
}

class GalleryChatImagePicker implements ChatImagePicker {
  GalleryChatImagePicker({ImagePicker? picker})
    : _picker = picker ?? ImagePicker();
  final ImagePicker _picker;
  @override
  Future<PickedChatImage?> pick() async {
    final image = await _picker.pickImage(source: ImageSource.gallery);
    if (image == null) return null;
    final filename = image.name;
    final extension = filename.split('.').last.toLowerCase();
    final mime = switch (extension) {
      'jpg' || 'jpeg' => 'image/jpeg',
      'png' => 'image/png',
      'webp' => 'image/webp',
      _ => null,
    };
    final size = await image.length();
    if (mime == null || size < 1 || size > maxImageBytes) {
      throw const ApiException(
        kind: ApiErrorKind.validation,
        code: 'attachment_invalid',
      );
    }
    return PickedChatImage(
      bytes: await image.readAsBytes(),
      mimeType: mime,
      filename: filename,
    );
  }
}

abstract interface class AttachmentUpload {
  Stream<double> get progress;
  Future<void> get completed;
  Future<void> cancel();
}

abstract interface class AttachmentStorageService {
  Future<AttachmentUpload> upload(
    AttachmentIntent intent,
    PickedChatImage image, {
    required String conversationId,
  });
  Future<Uint8List?> readReady(ChatAttachment attachment);
}

class _FirebaseUpload implements AttachmentUpload {
  _FirebaseUpload(this.task);
  final UploadTask task;
  @override
  Stream<double> get progress => task.snapshotEvents.map(
    (s) => s.totalBytes == 0 ? 0 : s.bytesTransferred / s.totalBytes,
  );
  @override
  Future<void> get completed async {
    await task;
  }

  @override
  Future<void> cancel() async {
    await task.cancel();
  }
}

class FirebaseAttachmentStorage implements AttachmentStorageService {
  FirebaseAttachmentStorage(this.availability);
  final Future<FirebaseAvailability> availability;
  Future<void> _ensureReady() async {
    if (!(await availability).ready) {
      throw const ApiException(
        kind: ApiErrorKind.server,
        code: 'firebase_not_configured',
      );
    }
  }

  @override
  Future<AttachmentUpload> upload(
    AttachmentIntent intent,
    PickedChatImage image, {
    required String conversationId,
  }) async {
    await _ensureReady();
    if (image.bytes.isEmpty ||
        image.bytes.length > maxImageBytes ||
        image.bytes.length > intent.maxBytes ||
        !allowedImageMime.contains(image.mimeType) ||
        !intent.allowedMimes.contains(image.mimeType) ||
        !intent.storageKey.startsWith('chat/$conversationId/${intent.id}/') ||
        intent.storageKey.contains('..')) {
      throw const ApiException(
        kind: ApiErrorKind.validation,
        code: 'attachment_invalid',
      );
    }
    final storage = FirebaseStorage.instanceFor(bucket: intent.bucket);
    final task = storage
        .ref(intent.storageKey)
        .putData(image.bytes, SettableMetadata(contentType: image.mimeType));
    return _FirebaseUpload(task);
  }

  @override
  Future<Uint8List?> readReady(ChatAttachment attachment) async {
    await _ensureReady();
    if (!attachment.ready ||
        !attachment.storageKey.startsWith('chat/') ||
        attachment.storageKey.contains('..')) {
      throw const ApiException(
        kind: ApiErrorKind.forbidden,
        code: 'attachment_not_ready',
      );
    }
    // No permanent/public download URL is minted. Storage rules still check
    // the signed-in user's conversation membership on every read.
    return FirebaseStorage.instance
        .ref(attachment.storageKey)
        .getData(maxImageBytes);
  }
}

class UnavailableAttachmentStorage implements AttachmentStorageService {
  const UnavailableAttachmentStorage();
  @override
  Future<AttachmentUpload> upload(
    AttachmentIntent i,
    PickedChatImage f, {
    required String conversationId,
  }) async => throw const ApiException(
    kind: ApiErrorKind.server,
    code: 'firebase_not_configured',
  );
  @override
  Future<Uint8List?> readReady(ChatAttachment a) async =>
      throw const ApiException(
        kind: ApiErrorKind.server,
        code: 'firebase_not_configured',
      );
}

/// Intent -> authorised Storage upload -> backend finalise -> message. A
/// failed finalise never sends a message; the backend cleans orphan objects.
class AttachmentCoordinator {
  const AttachmentCoordinator(this.api, this.storage);
  final ConsultationRepository api;
  final AttachmentStorageService storage;
  Future<ChatAttachment> uploadReady(
    String conversationId,
    PickedChatImage image, {
    void Function(double)? onProgress,
    void Function(AttachmentUpload)? onStarted,
  }) async {
    if (!allowedImageMime.contains(image.mimeType) ||
        image.bytes.isEmpty ||
        image.bytes.length > maxImageBytes) {
      throw const ApiException(
        kind: ApiErrorKind.validation,
        code: 'attachment_invalid',
      );
    }
    final intent = await api.createAttachment(
      conversationId,
      mime: image.mimeType,
      size: image.bytes.length,
      filename: image.filename,
    );
    final operation = await storage.upload(
      intent,
      image,
      conversationId: conversationId,
    );
    onStarted?.call(operation);
    final subscription = operation.progress.listen(
      (value) => onProgress?.call(value),
    );
    try {
      await operation.completed;
      final ready = await api.finalizeAttachment(intent.id);
      if (!ready.ready) {
        throw const ApiException(
          kind: ApiErrorKind.server,
          code: 'attachment_not_ready',
        );
      }
      return ready;
    } finally {
      await subscription.cancel();
    }
  }
}

final chatImagePickerProvider = Provider<ChatImagePicker>(
  (ref) => GalleryChatImagePicker(),
);
final attachmentStorageProvider = Provider<AttachmentStorageService>(
  (ref) =>
      FirebaseAttachmentStorage(ref.watch(firebaseBootstrapProvider.future)),
);
final attachmentCoordinatorProvider = Provider<AttachmentCoordinator>(
  (ref) => AttachmentCoordinator(
    ref.watch(consultationRepositoryProvider),
    ref.watch(attachmentStorageProvider),
  ),
);
