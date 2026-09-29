import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:livekit_client/livekit_client.dart' as lk;
import 'package:permission_handler/permission_handler.dart';

import '../../../core/network/api_config.dart';
import '../../../core/theme/app_colors.dart';
import 'call_models.dart';

enum MediaConnection {
  connecting,
  connected,
  reconnecting,
  disconnected,
  failed,
  replaced,
}

enum MediaPermission { granted, denied, permanentlyDenied }

abstract interface class CallPermissionService {
  Future<MediaPermission> request(CallType type);
  Future<bool> openSettings();
}

class DeviceCallPermissionService implements CallPermissionService {
  const DeviceCallPermissionService();

  @override
  Future<MediaPermission> request(CallType type) async {
    final microphone = await Permission.microphone.request();
    if (microphone.isPermanentlyDenied || microphone.isRestricted) {
      return MediaPermission.permanentlyDenied;
    }
    if (!microphone.isGranted) return MediaPermission.denied;
    // Audio calls never ask for camera access.
    if (type == CallType.video) {
      final camera = await Permission.camera.request();
      if (camera.isPermanentlyDenied || camera.isRestricted) {
        return MediaPermission.permanentlyDenied;
      }
      if (!camera.isGranted) return MediaPermission.denied;
    }
    return MediaPermission.granted;
  }

  @override
  Future<bool> openSettings() => openAppSettings();
}

abstract class CallMediaService extends ChangeNotifier {
  MediaConnection get connection;
  bool get muted;
  bool get cameraEnabled;
  bool get speakerEnabled;
  bool get hasRemoteVideo;
  Widget remoteVideo();
  Widget localVideo();
  Future<void> connect(CallJoinGrant grant);
  Future<void> setMuted(bool value);
  Future<void> setCameraEnabled(bool value);
  Future<void> switchCamera();
  Future<void> setSpeakerEnabled(bool value);
  Future<List<(String, String)>> audioOutputs();
  Future<void> selectAudioOutput(String deviceId);
  Future<void> disconnect();
}

class LiveKitCallMediaService extends CallMediaService {
  lk.Room? _room;
  lk.EventsListener<lk.RoomEvent>? _listener;
  MediaConnection _connection = MediaConnection.disconnected;
  bool _muted = false, _cameraEnabled = false, _speakerEnabled = false;
  lk.CameraPosition _cameraPosition = lk.CameraPosition.front;
  bool _disposed = false;

  @override
  MediaConnection get connection => _connection;
  @override
  bool get muted => _muted;
  @override
  bool get cameraEnabled => _cameraEnabled;
  @override
  bool get speakerEnabled => _speakerEnabled;
  @override
  bool get hasRemoteVideo => _remoteTrack != null;

  lk.VideoTrack? get _remoteTrack {
    for (final participant
        in _room?.remoteParticipants.values ?? <lk.RemoteParticipant>[]) {
      for (final publication in participant.videoTrackPublications) {
        if (!publication.muted && publication.track != null) {
          return publication.track;
        }
      }
    }
    return null;
  }

  lk.LocalVideoTrack? get _localTrack =>
      _room?.localParticipant?.videoTrackPublications.firstOrNull?.track;

  @override
  Widget remoteVideo() {
    final track = _remoteTrack;
    return track == null
        ? const Center(
            child: Icon(Icons.person_outline, size: 86, color: AppColors.gold),
          )
        : lk.VideoTrackRenderer(track);
  }

  @override
  Widget localVideo() {
    final track = _localTrack;
    return track == null
        ? const Center(
            child: Icon(
              Icons.videocam_off_outlined,
              color: AppColors.ivoryMuted,
            ),
          )
        : lk.VideoTrackRenderer(track);
  }

  void _setConnection(MediaConnection value) {
    if (_disposed) return;
    _connection = value;
    notifyListeners();
  }

  @override
  Future<void> connect(CallJoinGrant grant) async {
    if (_room != null) throw StateError('A media room is already active');
    if (grant.type == CallType.unknown) {
      throw StateError('Unsupported call type');
    }
    _setConnection(MediaConnection.connecting);
    final room = lk.Room(
      roomOptions: const lk.RoomOptions(adaptiveStream: true, dynacast: true),
    );
    _room = room;
    room.addListener(_onRoomChanged);
    final listener = room.createListener();
    _listener = listener;
    listener.on<lk.ReconnectingEvent>(
      (_) => _setConnection(MediaConnection.reconnecting),
    );
    listener.on<lk.RoomReconnectedEvent>(
      (_) => _setConnection(MediaConnection.connected),
    );
    listener.on<lk.RoomDisconnectedEvent>(
      (event) => _setConnection(
        event.reason == lk.DisconnectReason.duplicateIdentity
            ? MediaConnection.replaced
            : MediaConnection.disconnected,
      ),
    );
    try {
      // The grant is used once and never stored by this service.
      await room.connect(grant.livekitUrl, grant.token);
      await room.localParticipant?.setMicrophoneEnabled(true);
      if (grant.type == CallType.video) {
        await room.localParticipant?.setCameraEnabled(true);
        _cameraEnabled = true;
      }
      _setConnection(MediaConnection.connected);
    } on Object {
      _setConnection(MediaConnection.failed);
      await disconnect();
      rethrow;
    }
  }

  void _onRoomChanged() {
    if (!_disposed) notifyListeners();
  }

  @override
  Future<void> setMuted(bool value) async {
    await _room?.localParticipant?.setMicrophoneEnabled(!value);
    _muted = value;
    notifyListeners();
  }

  @override
  Future<void> setCameraEnabled(bool value) async {
    await _room?.localParticipant?.setCameraEnabled(value);
    _cameraEnabled = value;
    notifyListeners();
  }

  @override
  Future<void> switchCamera() async {
    final track = _localTrack;
    if (track == null) return;
    _cameraPosition = _cameraPosition.switched();
    await track.setCameraPosition(_cameraPosition);
    notifyListeners();
  }

  @override
  Future<void> setSpeakerEnabled(bool value) async {
    await lk.AudioManager.instance.setSpeakerOutputPreferred(
      value,
      force: false,
    );
    _speakerEnabled = value;
    notifyListeners();
  }

  @override
  Future<List<(String, String)>> audioOutputs() async =>
      (await lk.Hardware.instance.audioOutputs())
          .map((device) => (device.deviceId, device.label))
          .toList(growable: false);

  @override
  Future<void> selectAudioOutput(String deviceId) async {
    final room = _room;
    if (room == null) return;
    for (final device in await lk.Hardware.instance.audioOutputs()) {
      if (device.deviceId == deviceId) {
        await room.setAudioOutputDevice(device);
        notifyListeners();
        return;
      }
    }
  }

  @override
  Future<void> disconnect() async {
    final room = _room;
    _room = null;
    final listener = _listener;
    _listener = null;
    await listener?.dispose();
    room?.removeListener(_onRoomChanged);
    if (room != null) {
      await room.disconnect();
      await room.dispose();
    }
    if (_connection != MediaConnection.failed &&
        _connection != MediaConnection.replaced) {
      _setConnection(MediaConnection.disconnected);
    }
  }

  @override
  void dispose() {
    _disposed = true;
    // A route disposal must release tracks; the async cleanup owns its errors.
    disconnect().catchError((Object _) {});
    super.dispose();
  }
}

class DisabledCallMediaService extends CallMediaService {
  @override
  MediaConnection get connection => MediaConnection.disconnected;
  @override
  bool get muted => false;
  @override
  bool get cameraEnabled => false;
  @override
  bool get speakerEnabled => false;
  @override
  bool get hasRemoteVideo => false;
  @override
  Widget remoteVideo() => const SizedBox.shrink();
  @override
  Widget localVideo() => const SizedBox.shrink();
  Never get _unavailable => throw StateError('Media is disabled in mock mode');
  @override
  Future<void> connect(CallJoinGrant grant) async => _unavailable;
  @override
  Future<void> setMuted(bool value) async => _unavailable;
  @override
  Future<void> setCameraEnabled(bool value) async => _unavailable;
  @override
  Future<void> switchCamera() async => _unavailable;
  @override
  Future<void> setSpeakerEnabled(bool value) async => _unavailable;
  @override
  Future<List<(String, String)>> audioOutputs() async => _unavailable;
  @override
  Future<void> selectAudioOutput(String deviceId) async => _unavailable;
  @override
  Future<void> disconnect() async {}
}

final callPermissionProvider = Provider<CallPermissionService>(
  (ref) => const DeviceCallPermissionService(),
);
final callMediaProvider = Provider.autoDispose<CallMediaService>((ref) {
  final environment = ref.watch(appEnvironmentProvider);
  if (environment.environment == AppEnvironmentName.production &&
      environment.useMocks) {
    throw StateError('Production calls require APP_DATA_SOURCE=api');
  }
  final media = environment.useMocks
      ? DisabledCallMediaService()
      : LiveKitCallMediaService();
  ref.onDispose(media.dispose);
  return media;
});
