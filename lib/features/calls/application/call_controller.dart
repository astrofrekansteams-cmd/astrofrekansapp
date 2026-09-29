import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_exception.dart';
import '../data/call_media_service.dart';
import '../data/call_models.dart';
import '../data/call_repository.dart';

enum CallUiPhase {
  loading,
  ready,
  requestingPermission,
  joining,
  inCall,
  ending,
  error,
}

class CallController extends ChangeNotifier {
  CallController(this.id, this.repository, this.media, this.permissions) {
    media.addListener(_onMedia);
  }
  final String id;
  final CallRepository repository;
  final CallMediaService media;
  final CallPermissionService permissions;
  CallSession? session;
  CallUiPhase phase = CallUiPhase.loading;
  MediaPermission? permissionError;
  String? errorCode;
  bool _disposed = false;
  Future<void>? _loading;
  Timer? _elapsedTimer;
  int elapsedSeconds = 0;

  void _emit() {
    if (!_disposed) notifyListeners();
  }

  void _onMedia() {
    if (media.connection == MediaConnection.replaced) {
      errorCode = 'duplicate_identity';
    } else if (media.connection == MediaConnection.connected &&
        phase == CallUiPhase.joining) {
      phase = CallUiPhase.inCall;
    }
    _emit();
  }

  Future<void> load() => _loading ??= _load();
  Future<void> _load() async {
    try {
      session = await repository.get(id);
      phase = CallUiPhase.ready;
      _startElapsed();
    } on Object catch (error) {
      phase = CallUiPhase.error;
      errorCode = error is ApiException ? error.code : 'call_unavailable';
    }
    _emit();
  }

  Future<void> refresh() async {
    try {
      session = await repository.get(id);
      phase = CallUiPhase.ready;
      errorCode = null;
      _startElapsed();
    } on Object catch (error) {
      phase = CallUiPhase.error;
      errorCode = error is ApiException ? error.code : 'call_unavailable';
    }
    _emit();
  }

  void _startElapsed() {
    _elapsedTimer?.cancel();
    final started = session?.startedAt;
    if (started == null) return;
    void update() {
      elapsedSeconds = DateTime.now()
          .toUtc()
          .difference(started.toUtc())
          .inSeconds
          .clamp(0, 86400);
      _emit();
    }

    update();
    _elapsedTimer = Timer.periodic(const Duration(seconds: 1), (_) => update());
  }

  Future<void> join() async {
    if (phase == CallUiPhase.joining ||
        phase == CallUiPhase.inCall ||
        session?.isTerminal != false) {
      return;
    }
    // A push or an already-open screen is never authorization. Recheck the
    // server immediately before permission and the token-issuing join call.
    try {
      session = await repository.get(id);
      if (session!.isTerminal) {
        errorCode = 'call_already_ended';
        phase = CallUiPhase.ready;
        _emit();
        return;
      }
    } on Object catch (error) {
      errorCode = error is ApiException ? error.code : 'call_unavailable';
      phase = CallUiPhase.ready;
      _emit();
      return;
    }
    phase = CallUiPhase.requestingPermission;
    errorCode = null;
    permissionError = await permissions.request(session!.type);
    if (permissionError != MediaPermission.granted) {
      phase = CallUiPhase.ready;
      _emit();
      return;
    }
    phase = CallUiPhase.joining;
    _emit();
    try {
      final grant = await repository.join(
        id,
      ); // Only this endpoint issues a token.
      await media.connect(grant); // Token stays in memory; never persisted.
      phase = CallUiPhase.inCall;
    } on Object catch (error) {
      phase = CallUiPhase.ready;
      errorCode = error is ApiException
          ? error.code
          : 'call_provider_unavailable';
    }
    _emit();
  }

  Future<void> setMuted(bool value) async {
    try {
      await media.setMuted(value);
    } on Object {
      errorCode = 'call_unavailable';
      _emit();
    }
  }

  Future<void> setCameraEnabled(bool value) async {
    try {
      await media.setCameraEnabled(value);
    } on Object {
      errorCode = 'call_unavailable';
      _emit();
    }
  }

  Future<void> switchCamera() async {
    try {
      await media.switchCamera();
    } on Object {
      errorCode = 'call_unavailable';
      _emit();
    }
  }

  Future<void> setSpeakerEnabled(bool value) async {
    try {
      await media.setSpeakerEnabled(value);
    } on Object {
      errorCode = 'call_unavailable';
      _emit();
    }
  }

  Future<void> selectAudioOutput(String deviceId) async {
    try {
      await media.selectAudioOutput(deviceId);
    } on Object {
      errorCode = 'call_unavailable';
      _emit();
    }
  }

  Future<void> end() async {
    if (phase == CallUiPhase.ending) return;
    phase = CallUiPhase.ending;
    _emit();
    try {
      session = await repository.end(id);
      phase = CallUiPhase.ready;
      _elapsedTimer?.cancel();
    } on Object catch (error) {
      phase = CallUiPhase.error;
      errorCode = error is ApiException ? error.code : 'call_unavailable';
    } finally {
      // A failed backend request must not leave the local microphone/camera
      // publishing after the user tapped End. Backend state is refreshed later.
      try {
        await media.disconnect();
      } on Object {
        errorCode ??= 'call_provider_unavailable';
      }
    }
    _emit();
  }

  @override
  void dispose() {
    _disposed = true;
    _elapsedTimer?.cancel();
    media.removeListener(_onMedia);
    super.dispose();
  }
}

final callControllerProvider = Provider.autoDispose
    .family<CallController, String>((ref, id) {
      final controller = CallController(
        id,
        ref.watch(callRepositoryProvider),
        ref.watch(callMediaProvider),
        ref.watch(callPermissionProvider),
      );
      ref.onDispose(controller.dispose);
      unawaited(controller.load());
      return controller;
    });
