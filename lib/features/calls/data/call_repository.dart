import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_exception.dart';
import '../../auth/application/session_controller.dart';
import 'call_models.dart';

abstract interface class CallRepository {
  Future<CallAvailability> availability();
  Future<CallPage> history({int limit = 50, DateTime? before});
  Future<CallSession> create({
    required String orderId,
    required CallType type,
    String? appointmentId,
  });
  Future<CallSession> get(String id);
  Future<CallJoinGrant> join(String id);
  Future<CallSession> end(String id);
}

class ApiCallRepository implements CallRepository {
  const ApiCallRepository(this.api);
  final ApiClient api;
  String _id(String value) => Uri.encodeComponent(value);

  @override
  Future<CallAvailability> availability() async =>
      CallAvailability(await api.getMap('calls/status'));
  @override
  Future<CallPage> history({int limit = 50, DateTime? before}) async =>
      CallPage(
        await api.getMap(
          'calls',
          queryParameters: {
            'limit': limit,
            if (before != null) 'before': before.toUtc().toIso8601String(),
          },
        ),
      );
  @override
  Future<CallSession> create({
    required String orderId,
    required CallType type,
    String? appointmentId,
  }) async {
    if (type == CallType.unknown) {
      throw const ApiException(
        kind: ApiErrorKind.validation,
        code: 'call_type_not_supported',
      );
    }
    return CallSession(
      await api.postMap(
        'calls',
        data: {
          'order_id': orderId,
          'call_type': type.name,
          'appointment_id': ?appointmentId,
        },
      ),
    );
  }

  @override
  Future<CallSession> get(String id) async =>
      CallSession(await api.getMap('calls/${_id(id)}'));
  @override
  Future<CallJoinGrant> join(String id) async =>
      CallJoinGrant(await api.postMap('calls/${_id(id)}/join'));
  @override
  Future<CallSession> end(String id) async =>
      CallSession(await api.postMap('calls/${_id(id)}/end'));
}

class UnavailableCallRepository implements CallRepository {
  const UnavailableCallRepository();
  ApiException get _error => const ApiException(
    kind: ApiErrorKind.server,
    code: 'call_provider_not_configured',
  );
  @override
  Future<CallAvailability> availability() async =>
      CallAvailability({'configured': false, 'provider': 'disabled'});
  @override
  Future<CallPage> history({int limit = 50, DateTime? before}) async =>
      CallPage({'items': <Map<String, dynamic>>[]});
  @override
  Future<CallSession> create({
    required String orderId,
    required CallType type,
    String? appointmentId,
  }) async => throw _error;
  @override
  Future<CallSession> get(String id) async => throw _error;
  @override
  Future<CallJoinGrant> join(String id) async => throw _error;
  @override
  Future<CallSession> end(String id) async => throw _error;
}

final callRepositoryProvider = Provider<CallRepository>((ref) {
  ref.watch(currentUserProvider)?.id;
  return ref.watch(appEnvironmentProvider).useMocks
      ? const UnavailableCallRepository()
      : ApiCallRepository(ApiClient(ref.watch(dioProvider)));
});
