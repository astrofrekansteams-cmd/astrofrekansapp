// LiveKit 2.13 exposes CallKit audio coordination as experimental. Keep its
// use isolated here so an SDK upgrade has one explicit review point.
// ignore_for_file: experimental_member_use

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:livekit_client/livekit_client.dart' as lk;

import '../data/call_models.dart';
import '../data/call_repository.dart';
import '../../../core/network/api_exception.dart';

enum IncomingCallActionType { open, answer, decline, end }

class IncomingCallAction {
  const IncomingCallAction(
    this.callId,
    this.type, {
    this.eventVersion = 0,
    this.expiresAt,
  });
  final String callId;
  final IncomingCallActionType type;
  final int eventVersion;
  final DateTime? expiresAt;

  bool get isExpired =>
      expiresAt != null && !expiresAt!.isAfter(DateTime.now().toUtc());
}

abstract interface class IncomingCallPresentationService {
  Stream<IncomingCallAction> get actions;
  Future<IncomingCallAction?> consumeInitialAction();
  Future<void> show(String callId);
  Future<void> dismiss(String callId);
  Future<void> clearPending();
  void dispose();
}

/// Native PushKit reports promptly to CallKit; Dart only handles authenticated
/// actions and business-state reconciliation after the app engine is ready.
class IOSCallPresentationService implements IncomingCallPresentationService {
  IOSCallPresentationService() {
    _channel.setMethodCallHandler((call) async {
      if (call.method == 'action') {
        final action = await consumeInitialAction();
        if (action != null) _actions.add(action);
      } else if (call.method == 'incoming') {
        final args = call.arguments;
        if (args is Map && args['callId'] is String) {
          _incoming.add(args['callId'] as String);
        }
      } else if (call.method == 'audioActivated') {
        await lk.AudioManager.instance.setEngineAvailability(
          lk.AudioEngineAvailability.defaultAvailability,
        );
      } else if (call.method == 'audioDeactivated') {
        await lk.AudioManager.instance.setEngineAvailability(
          lk.AudioEngineAvailability.none,
        );
      }
    });
  }

  static const _channel = MethodChannel('astrofrekans/ios_calls');
  final _actions = StreamController<IncomingCallAction>.broadcast();
  final _incoming = StreamController<String>.broadcast();
  Stream<String> get incoming => _incoming.stream;
  @override
  Stream<IncomingCallAction> get actions => _actions.stream;
  @override
  Future<IncomingCallAction?> consumeInitialAction() async =>
      _decodeAction(await _channel.invokeMethod<Object?>('consumeAction'));
  @override
  Future<void> show(String callId) async {} // PushKit owns CallKit reporting.
  @override
  Future<void> dismiss(String callId) =>
      _channel.invokeMethod<void>('dismiss', {'callId': callId});
  @override
  Future<void> clearPending() => _channel.invokeMethod<void>('clearPending');

  Future<bool> prepareAudio(String id) async {
    final hasCall =
        await _channel.invokeMethod<bool>('hasCall', {'callId': id}) ?? false;
    if (!hasCall) return false;
    await lk.AudioManager.instance.setAudioSessionManagementMode(
      lk.AudioSessionManagementMode.externalCallSystem,
    );
    final active = await _channel.invokeMethod<bool>('audioState') ?? false;
    await lk.AudioManager.instance.setEngineAvailability(
      active
          ? lk.AudioEngineAvailability.defaultAvailability
          : lk.AudioEngineAvailability.none,
    );
    return true;
  }

  Future<void> markConnected(String id) =>
      _channel.invokeMethod<void>('markConnected', {'callId': id});

  Future<void> reconcile(String id, CallStatus status) => _channel
      .invokeMethod<void>('reconcile', {'callId': id, 'status': status.name});

  Future<void> releaseAudio() async {
    await lk.AudioManager.instance.setEngineAvailability(
      lk.AudioEngineAvailability.defaultAvailability,
    );
    await lk.AudioManager.instance.setAudioSessionManagementMode(
      lk.AudioSessionManagementMode.automatic,
    );
  }

  @override
  void dispose() {
    _channel.setMethodCallHandler(null);
    _actions.close();
    _incoming.close();
  }
}

IncomingCallAction? _decodeAction(Object? raw) {
  if (raw is! Map) return null;
  final id = raw['callId'];
  final value = raw['action'];
  if (id is! String ||
      !RegExp(r'^[0-9a-fA-F-]{36}$').hasMatch(id) ||
      value is! String) {
    return null;
  }
  final type = IncomingCallActionType.values
      .where((item) => item.name == value)
      .firstOrNull;
  if (type == null) return null;
  final version = raw['eventVersion'];
  final expiry = raw['expiresAt'];
  return IncomingCallAction(
    id,
    type,
    eventVersion: version is int ? version : 0,
    expiresAt: expiry is int
        ? DateTime.fromMillisecondsSinceEpoch(expiry * 1000, isUtc: true)
        : null,
  );
}

class InAppCallPresentationService implements IncomingCallPresentationService {
  @override
  Stream<IncomingCallAction> get actions => const Stream.empty();
  @override
  Future<IncomingCallAction?> consumeInitialAction() async => null;
  @override
  Future<void> show(String callId) async {}
  @override
  Future<void> dismiss(String callId) async {}
  @override
  Future<void> clearPending() async {}
  @override
  void dispose() {}
}

class AndroidCallPresentationService
    implements IncomingCallPresentationService {
  AndroidCallPresentationService() {
    _channel.setMethodCallHandler((call) async {
      if (call.method == 'action') {
        final action = await consumeInitialAction();
        if (action != null) _actions.add(action);
      }
    });
  }

  static const _channel = MethodChannel('astrofrekans/incoming_calls');
  final _actions = StreamController<IncomingCallAction>.broadcast();

  @override
  Stream<IncomingCallAction> get actions => _actions.stream;
  @override
  Future<IncomingCallAction?> consumeInitialAction() async =>
      _decodeAction(await _channel.invokeMethod<Object?>('consumeAction'));
  @override
  Future<void> show(String callId) =>
      _channel.invokeMethod<void>('show', {'callId': callId});
  @override
  Future<void> dismiss(String callId) =>
      _channel.invokeMethod<void>('dismiss', {'callId': callId});
  @override
  Future<void> clearPending() => _channel.invokeMethod<void>('clearPending');
  @override
  void dispose() {
    _channel.setMethodCallHandler(null);
    _actions.close();
  }
}

class FakeIncomingCallPresentationService
    implements IncomingCallPresentationService {
  final shown = <String>[];
  final dismissed = <String>[];
  final _actions = StreamController<IncomingCallAction>.broadcast();
  IncomingCallAction? initialAction;

  void emit(IncomingCallAction action) => _actions.add(action);
  @override
  Stream<IncomingCallAction> get actions => _actions.stream;
  @override
  Future<IncomingCallAction?> consumeInitialAction() async {
    final result = initialAction;
    initialAction = null;
    return result;
  }

  @override
  Future<void> show(String callId) async => shown.add(callId);
  @override
  Future<void> dismiss(String callId) async => dismissed.add(callId);
  @override
  Future<void> clearPending() async {
    initialAction = null;
  }

  @override
  void dispose() => _actions.close();
}

/// Push IDs are hints only. Every display and native action is gated by GET.
class IncomingCallCoordinator {
  IncomingCallCoordinator(this.repository, this.presentation);
  final CallRepository repository;
  final IncomingCallPresentationService presentation;
  final _visible = <String>{};
  final _processing = <String>{};
  final _cancelled = <String>{};
  String? lastErrorCode;

  Future<bool> incoming(String callId) async {
    if (_cancelled.contains(callId)) return false;
    if (_visible.contains(callId)) return true;
    if (!_processing.add(callId)) return false;
    try {
      final call = await repository.get(callId);
      if (!_joinable(call) || _cancelled.contains(callId)) return false;
      await presentation.show(callId);
      _visible.add(callId);
      return true;
    } on Object {
      // Auth/network failure must not create a native ringing UI.
      return false;
    } finally {
      _processing.remove(callId);
    }
  }

  Future<void> cancelled(String callId) async {
    _cancelled.add(callId);
    _visible.remove(callId);
    await presentation.dismiss(callId);
  }

  Future<bool> accept(String callId) async {
    try {
      final call = await repository.get(callId);
      if (!_joinable(call) || _cancelled.contains(callId)) {
        await cancelled(callId);
        return false;
      }
      // Keep CallKit alive through the join/audio handoff. Android has already
      // dismissed its notification when the native action was consumed.
      _cancelled.add(callId);
      _visible.remove(callId);
      return true; // CallScreen refreshes again before /join and LiveKit.
    } on Object {
      await cancelled(callId);
      return false;
    }
  }

  Future<bool> decline(String callId) async {
    lastErrorCode = null;
    try {
      final call = await repository.get(callId);
      if (!_joinable(call) || _cancelled.contains(callId)) return false;
      await repository.end(callId); // Backend CANCELLED semantics for ringing.
      return true;
    } on Object catch (error) {
      lastErrorCode = error is ApiException ? error.code : 'call_unavailable';
      return false;
    } finally {
      await cancelled(callId);
    }
  }

  Future<bool> end(String callId) async {
    lastErrorCode = null;
    try {
      final call = await repository.get(callId);
      if (call.isTerminal) return false;
      await repository.end(callId);
      return true;
    } on Object catch (error) {
      lastErrorCode = error is ApiException ? error.code : 'call_unavailable';
      return false;
    } finally {
      await cancelled(callId);
    }
  }

  bool _joinable(CallSession call) =>
      !call.isTerminal &&
      (call.status == CallStatus.waiting || call.status == CallStatus.ringing);
}

final incomingCallPresentationProvider =
    Provider<IncomingCallPresentationService>((ref) {
      final IncomingCallPresentationService service =
          switch (defaultTargetPlatform) {
            TargetPlatform.android => AndroidCallPresentationService(),
            TargetPlatform.iOS => IOSCallPresentationService(),
            _ => InAppCallPresentationService(),
          };
      ref.onDispose(service.dispose);
      return service;
    });

final incomingCallCoordinatorProvider = Provider<IncomingCallCoordinator>(
  (ref) => IncomingCallCoordinator(
    ref.watch(callRepositoryProvider),
    ref.watch(incomingCallPresentationProvider),
  ),
);
