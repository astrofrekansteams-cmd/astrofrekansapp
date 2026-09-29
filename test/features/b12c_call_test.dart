import 'dart:convert';
import 'dart:io';

import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/core/routing/app_routes.dart';
import 'package:astrofrekans/core/routing/pending_deep_links.dart';
import 'package:astrofrekans/features/calls/application/call_controller.dart';
import 'package:astrofrekans/features/calls/data/call_media_service.dart';
import 'package:astrofrekans/features/calls/data/call_models.dart';
import 'package:astrofrekans/features/calls/data/call_repository.dart';
import 'package:astrofrekans/features/consultation/data/push_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final fixture =
      jsonDecode(
            File('test/fixtures/b12c_contract_samples.json').readAsStringSync(),
          )
          as Map<String, dynamic>;
  final callJson = fixture['call_session'] as Map<String, dynamic>;
  final grantJson = fixture['join_response'] as Map<String, dynamic>;

  test(
    'typed call contract rejects leaked join token and tolerates unknown status',
    () {
      final call = CallSession(callJson);
      expect(call.type, CallType.audio);
      expect(call.status, CallStatus.ringing);
      expect(
        CallSession({...callJson, 'status': 'new_status'}).status,
        CallStatus.unknown,
      );
      expect(
        () => CallSession({...callJson, 'token': 'forbidden'}),
        throwsFormatException,
      );
      final grant = CallJoinGrant(grantJson);
      expect(grant.toString(), isNot(contains('SANITIZED_TEST_ONLY')));
    },
  );

  test(
    'audio joins without camera; media controls, reconnect and replacement do not end backend call',
    () async {
      final repo = _Calls(callJson, grantJson);
      final media = _Media();
      final permission = _Permission();
      final controller = CallController('test', repo, media, permission);
      await controller.load();
      await controller.join();
      expect(permission.requested, [CallType.audio]);
      expect(repo.joinCount, 1);
      expect(media.grant?.token, 'SANITIZED_TEST_ONLY');
      expect(controller.phase, CallUiPhase.inCall);
      await controller.setMuted(true);
      await controller.setSpeakerEnabled(true);
      expect(media.muted, isTrue);
      expect(media.speakerEnabled, isTrue);
      media.setConnection(MediaConnection.reconnecting);
      expect(repo.endCount, 0);
      media.setConnection(MediaConnection.connected);
      media.setConnection(MediaConnection.replaced);
      expect(controller.errorCode, 'duplicate_identity');
      expect(repo.joinCount, 1);
      await controller.end();
      expect(repo.endCount, 1);
      controller.dispose();
      media.dispose();
    },
  );

  test('video requests camera, controls camera and switch', () async {
    final repo = _Calls(
      {...callJson, 'call_type': 'video'},
      {...grantJson, 'call_type': 'video'},
    );
    final media = _Media();
    final permission = _Permission();
    final controller = CallController('test', repo, media, permission);
    await controller.load();
    await controller.join();
    expect(permission.requested, [CallType.video]);
    await controller.setCameraEnabled(true);
    await controller.switchCamera();
    expect(media.cameraEnabled, isTrue);
    expect(media.switches, 1);
    controller.dispose();
    media.dispose();
  });

  test('denied permission does not request join token', () async {
    final repo = _Calls(callJson, grantJson);
    final media = _Media();
    final controller = CallController(
      'test',
      repo,
      media,
      _Permission(MediaPermission.permanentlyDenied),
    );
    await controller.load();
    await controller.join();
    expect(controller.permissionError, MediaPermission.permanentlyDenied);
    expect(repo.joinCount, 0);
    controller.dispose();
    media.dispose();
  });

  test(
    'terminal server refresh blocks stale in-app answer before token',
    () async {
      final repo = _Calls({...callJson}, grantJson);
      final media = _Media();
      final permission = _Permission();
      final controller = CallController('test', repo, media, permission);
      await controller.load();
      repo.callJson['status'] = 'ended';
      await controller.join();
      expect(repo.joinCount, 0);
      expect(permission.requested, isEmpty);
      expect(media.grant, isNull);
      controller.dispose();
      media.dispose();
    },
  );

  for (final code in [
    'call_too_early',
    'call_window_closed',
    'call_provider_unavailable',
  ]) {
    test('backend $code blocks media connect', () async {
      final repo = _Calls(callJson, grantJson)..joinError = code;
      final media = _Media();
      final controller = CallController('test', repo, media, _Permission());
      await controller.load();
      await controller.join();
      expect(controller.errorCode, code);
      expect(media.grant, isNull);
      controller.dispose();
      media.dispose();
    });
  }

  test('manual end releases local media even when backend end fails', () async {
    final repo = _Calls(callJson, grantJson)
      ..endError = 'call_provider_unavailable';
    final media = _Media();
    final controller = CallController('test', repo, media, _Permission());
    await controller.load();
    await controller.join();
    await controller.end();
    expect(media.disconnectCount, 1);
    expect(controller.phase, CallUiPhase.error);
    controller.dispose();
    media.dispose();
  });

  test(
    'incoming, cancelled and missed push routes wait for authenticated router',
    () {
      const id = '11111111-1111-4111-8111-111111111111';
      final incoming = routeForPush({'event': 'incoming_call', 'call_id': id});
      expect(incoming, AppRoutes.incomingCall(id));
      expect(
        routeForPush({'event': 'call_cancelled', 'call_id': id}),
        AppRoutes.callDetail(id),
      );
      expect(
        routeForPush({'event': 'call_missed', 'call_id': id}),
        AppRoutes.callDetail(id),
      );
      final pending = PendingDeepLinks()
        ..enqueue(incoming!)
        ..enqueue(incoming);
      expect(pending.takeIfReady(authenticated: false), isNull);
      expect(pending.takeIfReady(authenticated: true), incoming);
      expect(pending.takeIfReady(authenticated: true), isNull);
    },
  );
}

class _Calls implements CallRepository {
  _Calls(this.callJson, this.grantJson);
  final Map<String, dynamic> callJson, grantJson;
  int joinCount = 0, endCount = 0;
  String? joinError, endError;
  @override
  Future<CallAvailability> availability() async =>
      CallAvailability({'configured': true, 'provider': 'livekit'});
  @override
  Future<CallPage> history({int limit = 50, DateTime? before}) async =>
      CallPage({
        'items': [callJson],
      });
  @override
  Future<CallSession> create({
    required String orderId,
    required CallType type,
    String? appointmentId,
  }) async => CallSession(callJson);
  @override
  Future<CallSession> get(String id) async => CallSession(callJson);
  @override
  Future<CallJoinGrant> join(String id) async {
    joinCount++;
    if (joinError case final code?) {
      throw ApiException(kind: ApiErrorKind.server, code: code);
    }
    return CallJoinGrant(grantJson);
  }

  @override
  Future<CallSession> end(String id) async {
    endCount++;
    if (endError case final code?) {
      throw ApiException(kind: ApiErrorKind.server, code: code);
    }
    return CallSession({...callJson, 'status': 'ended'});
  }
}

class _Permission implements CallPermissionService {
  _Permission([this.result = MediaPermission.granted]);
  final MediaPermission result;
  final List<CallType> requested = [];
  @override
  Future<MediaPermission> request(CallType type) async {
    requested.add(type);
    return result;
  }

  @override
  Future<bool> openSettings() async => true;
}

class _Media extends CallMediaService {
  CallJoinGrant? grant;
  MediaConnection _connection = MediaConnection.disconnected;
  bool _muted = false, _camera = false, _speaker = false;
  int switches = 0, disconnectCount = 0;
  @override
  MediaConnection get connection => _connection;
  @override
  bool get muted => _muted;
  @override
  bool get cameraEnabled => _camera;
  @override
  bool get speakerEnabled => _speaker;
  @override
  bool get hasRemoteVideo => false;
  @override
  Widget remoteVideo() => const SizedBox.shrink();
  @override
  Widget localVideo() => const SizedBox.shrink();
  void setConnection(MediaConnection value) {
    _connection = value;
    notifyListeners();
  }

  @override
  Future<void> connect(CallJoinGrant value) async {
    grant = value;
    setConnection(MediaConnection.connected);
  }

  @override
  Future<void> setMuted(bool value) async {
    _muted = value;
    notifyListeners();
  }

  @override
  Future<void> setCameraEnabled(bool value) async {
    _camera = value;
    notifyListeners();
  }

  @override
  Future<void> switchCamera() async {
    switches++;
  }

  @override
  Future<void> setSpeakerEnabled(bool value) async {
    _speaker = value;
    notifyListeners();
  }

  @override
  Future<List<(String, String)>> audioOutputs() async => const [
    ('speaker', 'Speaker'),
  ];
  @override
  Future<void> selectAudioOutput(String deviceId) async {}
  @override
  Future<void> disconnect() async {
    disconnectCount++;
    setConnection(MediaConnection.disconnected);
  }
}
