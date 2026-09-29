import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/auth/domain/auth_repository.dart';
import '../network/api_client.dart';
import '../network/api_config.dart';
import '../network/api_exception.dart';

/// No generated or fake project settings. Native config or explicitly supplied
/// public FlutterFire options are required before SDK access.
class FirebaseClient {
  FirebaseClient({this.options});
  final FirebaseOptions? options;
  Future<FirebaseAuth>? _initializing;
  Future<FirebaseAuth> auth() => _initializing ??= _initialize();

  Future<FirebaseAuth> _initialize() async {
    try {
      if (Firebase.apps.isEmpty) await Firebase.initializeApp(options: options);
      return FirebaseAuth.instance;
    } on Object {
      _initializing = null;
      throw const AuthException(AuthFailureKind.notConfigured);
    }
  }

  Future<String?> token(bool forceRefresh) async =>
      (await auth()).currentUser?.getIdToken(forceRefresh);

  Future<void> signOut() async {
    if (Firebase.apps.isNotEmpty) await FirebaseAuth.instance.signOut();
  }
}

final firebaseClientProvider = Provider<FirebaseClient>(
  (ref) => FirebaseClient(),
);

enum FirebaseBootstrapStatus { unconfigured, initializing, ready, error }

class FirebaseAvailability {
  const FirebaseAvailability(this.status, {this.reason});
  final FirebaseBootstrapStatus status;
  final String? reason;
  bool get ready => status == FirebaseBootstrapStatus.ready;
}

/// Started from the splash. In mock mode this never initializes a Firebase
/// project, and an absent native config cannot disable astrology features.
final firebaseBootstrapProvider = FutureProvider<FirebaseAvailability>((
  ref,
) async {
  if (ref.watch(appEnvironmentProvider).useMocks) {
    return const FirebaseAvailability(FirebaseBootstrapStatus.unconfigured);
  }
  try {
    final capabilities = await ApiClient(
      ref.watch(dioProvider),
    ).getMap('auth/capabilities');
    if (capabilities['firebase_configured'] != true ||
        capabilities['accepts_firebase_token'] != true) {
      return const FirebaseAvailability(
        FirebaseBootstrapStatus.unconfigured,
        reason: 'firebase_not_configured',
      );
    }
    final auth = await ref.watch(firebaseClientProvider).auth();
    final String projectId = auth.app.options.projectId;
    // A production binary must never carry a staging/dev Firebase config
    // (google-services.json / GoogleService-Info.plist): it would sign people
    // in to the wrong user base. Fail closed.
    if (ref.watch(appEnvironmentProvider).isProduction &&
        looksLikeDevFirebaseProject(projectId)) {
      return const FirebaseAvailability(
        FirebaseBootstrapStatus.error,
        reason: 'firebase_dev_project_in_production',
      );
    }
    if (projectId != capabilities['firebase_project_id']) {
      return const FirebaseAvailability(
        FirebaseBootstrapStatus.error,
        reason: 'firebase_project_mismatch',
      );
    }
    return const FirebaseAvailability(FirebaseBootstrapStatus.ready);
  } on AuthException {
    return const FirebaseAvailability(
      FirebaseBootstrapStatus.unconfigured,
      reason: 'firebase_not_configured',
    );
  } on ApiException catch (error) {
    return FirebaseAvailability(
      FirebaseBootstrapStatus.error,
      reason: error.code ?? 'capability_check_failed',
    );
  } on Object {
    return const FirebaseAvailability(
      FirebaseBootstrapStatus.error,
      reason: 'firebase_initialization_failed',
    );
  }
});

/// Staging, dev, test or emulator (`demo-`) project ids. Same rule as the
/// backend's production check and the Android release build.
bool looksLikeDevFirebaseProject(String projectId) => RegExp(
  r'(^demo-|staging|(^|[-_])(dev|test|local)([-_]|$))',
  caseSensitive: false,
).hasMatch(projectId);

/// Synchronous view for UI: loading is an explicit initializing capability.
final firebaseAvailabilityProvider = Provider<FirebaseAvailability>((ref) {
  final state = ref.watch(firebaseBootstrapProvider);
  return state.when(
    data: (availability) => availability,
    loading: () =>
        const FirebaseAvailability(FirebaseBootstrapStatus.initializing),
    error: (_, _) => const FirebaseAvailability(FirebaseBootstrapStatus.error),
  );
});
