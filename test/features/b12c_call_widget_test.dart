import 'package:astrofrekans/features/calls/data/call_media_service.dart';
import 'package:astrofrekans/features/calls/data/call_models.dart';
import 'package:astrofrekans/features/calls/data/call_repository.dart';
import 'package:astrofrekans/features/calls/presentation/call_screens.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_models.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_repository.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets(
    '2x audio call screen builds, joins and exposes semantic controls',
    (tester) async {
      final repository = _Calls();
      final media = _Media();
      final watch = Stopwatch()..start();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            callRepositoryProvider.overrideWithValue(repository),
            callMediaProvider.overrideWithValue(media),
            callPermissionProvider.overrideWithValue(_Permissions()),
            marketplaceRepositoryProvider.overrideWithValue(_Marketplace()),
          ],
          child: const MediaQuery(
            data: MediaQueryData(textScaler: TextScaler.linear(2)),
            child: MaterialApp(
              locale: Locale('tr'),
              supportedLocales: [Locale('tr'), Locale('en')],
              localizationsDelegates: GlobalMaterialLocalizations.delegates,
              home: CallScreen(id: 'test'),
            ),
          ),
        ),
      );
      await tester.pump();
      watch.stop();
      // ignore: avoid_print
      print(
        'B12C_HOST_PERF audio_call_initial_widget=${watch.elapsedMilliseconds}ms',
      );
      expect(find.text('Sesli Uzman Görüşmesi'), findsOneWidget);
      await tester.scrollUntilVisible(find.text('Görüşmeye katıl'), 240);
      await tester.tap(find.text('Görüşmeye katıl'));
      await tester.pump();
      expect(find.byTooltip('Mikrofonu kapat'), findsOneWidget);
      expect(find.byTooltip('Hoparlöre geç'), findsOneWidget);
      expect(find.byTooltip('Ses çıkışı seç'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      media.dispose();
    },
  );
}

class _Calls extends Fake implements CallRepository {
  @override
  Future<CallSession> get(String id) async => CallSession({
    'id': id,
    'order_id': 'order',
    'call_type': 'audio',
    'status': 'waiting',
    'my_role': 'customer',
    'participants': <Map<String, dynamic>>[],
    'created_at': '2026-09-25T10:00:00Z',
  });
  @override
  Future<CallJoinGrant> join(String id) async => CallJoinGrant({
    'call_id': id,
    'call_type': 'audio',
    'livekit_url': 'wss://example.invalid',
    'token': 'SANITIZED_TEST_ONLY',
  });
}

class _Permissions implements CallPermissionService {
  @override
  Future<MediaPermission> request(CallType type) async =>
      MediaPermission.granted;
  @override
  Future<bool> openSettings() async => false;
}

class _Media extends CallMediaService {
  MediaConnection _connection = MediaConnection.disconnected;
  @override
  MediaConnection get connection => _connection;
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
  @override
  Future<void> connect(CallJoinGrant grant) async {
    _connection = MediaConnection.connected;
    notifyListeners();
  }

  @override
  Future<void> setMuted(bool value) async {}
  @override
  Future<void> setCameraEnabled(bool value) async {}
  @override
  Future<void> switchCamera() async {}
  @override
  Future<void> setSpeakerEnabled(bool value) async {}
  @override
  Future<List<(String, String)>> audioOutputs() async => const [];
  @override
  Future<void> selectAudioOutput(String deviceId) async {}
  @override
  Future<void> disconnect() async {}
}

class _Marketplace extends Fake implements MarketplaceRepository {
  @override
  Future<Order> order(String id, {bool expert = false}) async => Order({
    'id': id,
    'service_code': 'voice',
    'status': 'confirmed',
    'payment_status': 'paid',
    'expert_display_name': 'Ayşe',
    'total': {'amount_minor': 100, 'currency': 'TRY'},
  });
}
