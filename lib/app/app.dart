import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/constants/app_config.dart';
import '../core/localization/locale_controller.dart';
import '../core/routing/app_router.dart';
import '../core/routing/notification_routes.dart';
import '../core/routing/pending_deep_links.dart';
import '../core/theme/app_theme.dart';
import '../l10n/generated/app_localizations.dart';
import '../features/consultation/data/push_service.dart';
import '../features/notifications/data/notification_repository.dart';
import '../features/calls/application/incoming_call_presentation.dart';
import '../features/calls/data/call_media_service.dart';
import '../core/routing/app_routes.dart';
import '../features/auth/application/session_controller.dart';
import '../features/billing/application/entitlement_controller.dart';
import '../features/calls/data/call_repository.dart';
import '../features/calls/presentation/call_screens.dart' show callErrorText;

class AstrofrekansApp extends ConsumerStatefulWidget {
  const AstrofrekansApp({super.key});

  @override
  ConsumerState<AstrofrekansApp> createState() => _AstrofrekansAppState();
}

class _AstrofrekansAppState extends ConsumerState<AstrofrekansApp> {
  PushService? _observedPush;
  StreamSubscription<String>? _pushRoutes;
  StreamSubscription<Map<String, dynamic>>? _foregroundCalls;
  StreamSubscription<String>? _openedNotifications;
  StreamSubscription<IncomingCallAction>? _nativeActions;
  StreamSubscription<String>? _iosIncoming;
  IncomingCallPresentationService? _observedPresentation;
  bool _initialActionConsumed = false;
  final _handledNativeActions = <String>{};
  final _queuedNativeActions = <IncomingCallAction>[];
  final _reconciliationTimers = <String, Timer>{};
  final PendingDeepLinks _pendingLinks = PendingDeepLinks();
  GoRouter? _activeRouter;
  bool _navigationScheduled = false;
  final _messengerKey = GlobalKey<ScaffoldMessengerState>();

  void _callError(String? code) {
    _messengerKey.currentState?.showSnackBar(
      SnackBar(
        content: Text(
          callErrorText(
            code,
            language: ref.read(localeControllerProvider).languageCode,
          ),
        ),
      ),
    );
  }

  void _drainPendingLinks(bool authenticated) {
    if (!authenticated || !_pendingLinks.hasPending || _navigationScheduled) {
      return;
    }
    _navigationScheduled = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _navigationScheduled = false;
      if (!mounted) return;
      final route = _pendingLinks.takeIfReady(
        authenticated: ref.read(sessionProvider).isAuthenticated,
      );
      if (route != null) _activeRouter?.push(route);
      if (_pendingLinks.hasPending) {
        _drainPendingLinks(ref.read(sessionProvider).isAuthenticated);
      }
    });
  }

  @override
  void dispose() {
    _pushRoutes?.cancel();
    _foregroundCalls?.cancel();
    _openedNotifications?.cancel();
    _nativeActions?.cancel();
    _iosIncoming?.cancel();
    for (final timer in _reconciliationTimers.values) {
      timer.cancel();
    }
    super.dispose();
  }

  /// The push that was opened is the same record as in the notification
  /// centre: mark it read there too. Idempotent on the server.
  Future<void> _markOpened(String id) async {
    if (!mounted || !ref.read(sessionProvider).isAuthenticated) return;
    try {
      await ref.read(notificationRepositoryProvider).setRead(id, read: true);
    } on Object {
      // Best effort: the record stays unread and can be read in the centre.
    }
    if (mounted) ref.invalidate(unreadNotificationsProvider);
  }

  void _route(String route) {
    _pendingLinks.enqueue(route);
    if (mounted) _drainPendingLinks(ref.read(sessionProvider).isAuthenticated);
  }

  Future<void> _handleNativeAction(IncomingCallAction action) async {
    if (!mounted) return;
    if (!ref.read(sessionProvider).isAuthenticated) {
      _queuedNativeActions.add(action);
      return;
    }
    if (action.isExpired) {
      await ref.read(incomingCallPresentationProvider).dismiss(action.callId);
      return;
    }
    if (!_handledNativeActions.add('${action.callId}:${action.type.name}')) {
      return;
    }
    final coordinator = ref.read(incomingCallCoordinatorProvider);
    if (action.type == IncomingCallActionType.end) {
      final ended = await coordinator.end(action.callId);
      if (!ended && coordinator.lastErrorCode != null) {
        _callError(coordinator.lastErrorCode);
      }
      await ref.read(callMediaProvider).disconnect();
      _stopReconciliation(action.callId);
      return;
    }
    if (action.type == IncomingCallActionType.decline) {
      final declined = await coordinator.decline(action.callId);
      if (!declined && coordinator.lastErrorCode != null) {
        _callError(coordinator.lastErrorCode);
      }
      _stopReconciliation(action.callId);
      return;
    }
    if (await coordinator.accept(action.callId)) {
      _route(
        '${AppRoutes.incomingCall(action.callId)}${action.type == IncomingCallActionType.answer ? '?answer=1' : ''}',
      );
    } else {
      _route(AppRoutes.callDetail(action.callId));
    }
  }

  void _stopReconciliation(String id) {
    _reconciliationTimers.remove(id)?.cancel();
  }

  void _startReconciliation(String id) {
    if (_reconciliationTimers.containsKey(id)) return;
    var remaining = 6;
    Future<void> check() async {
      if (!mounted || !ref.read(sessionProvider).isAuthenticated) {
        _stopReconciliation(id);
        return;
      }
      try {
        final call = await ref.read(callRepositoryProvider).get(id);
        final presentation = _observedPresentation;
        if (presentation is IOSCallPresentationService) {
          await presentation.reconcile(id, call.status);
        }
        if (call.isTerminal || call.status.name == 'active') {
          _stopReconciliation(id);
          return;
        }
      } on Object {
        // PushKit's expiry timer remains the native backstop while offline.
      }
      if (--remaining <= 0) _stopReconciliation(id);
    }

    unawaited(check());
    _reconciliationTimers[id] = Timer.periodic(
      const Duration(seconds: 10),
      (_) => unawaited(check()),
    );
  }

  Future<void> _handleForegroundCall(Map<String, dynamic> data) async {
    if (_observedPresentation is AndroidCallPresentationService) return;
    final id = data['call_id'];
    if (id is! String || !RegExp(r'^[0-9a-fA-F-]{36}$').hasMatch(id)) return;
    if (!mounted || !ref.read(sessionProvider).isAuthenticated) return;
    final coordinator = ref.read(incomingCallCoordinatorProvider);
    if (data['event'] == 'incoming_call') {
      final shown = await coordinator.incoming(id);
      if (shown && _observedPresentation is IOSCallPresentationService) {
        _route(AppRoutes.incomingCall(id));
      }
    } else if (data['event'] == 'call_answered' ||
        data['event'] == 'call_cancelled' ||
        data['event'] == 'call_missed') {
      await coordinator.cancelled(id);
    }
  }

  @override
  Widget build(BuildContext context) {
    final GoRouter router = ref.watch(routerProvider);
    _activeRouter = router;
    final session = ref.watch(sessionProvider);
    if (session.isAuthenticated) {
      ref.watch(entitlementControllerProvider);
      _drainPendingLinks(true);
      if (_queuedNativeActions.isNotEmpty) {
        final queued = List<IncomingCallAction>.of(_queuedNativeActions);
        _queuedNativeActions.clear();
        WidgetsBinding.instance.addPostFrameCallback((_) {
          for (final action in queued) {
            unawaited(_handleNativeAction(action));
          }
        });
      }
    } else {
      _initialActionConsumed = false;
      _handledNativeActions.clear();
    }
    final Locale locale = ref.watch(localeControllerProvider);
    final push = ref.watch(pushServiceProvider);
    final presentation = ref.watch(incomingCallPresentationProvider);
    if (!identical(presentation, _observedPresentation)) {
      _nativeActions?.cancel();
      _iosIncoming?.cancel();
      _observedPresentation = presentation;
      _initialActionConsumed = false;
      _nativeActions = presentation.actions.listen((action) {
        unawaited(_handleNativeAction(action));
      });
      if (presentation is IOSCallPresentationService) {
        _iosIncoming = presentation.incoming.listen(_startReconciliation);
      }
    }
    if (session.isAuthenticated && !_initialActionConsumed) {
      _initialActionConsumed = true;
      unawaited(
        presentation
            .consumeInitialAction()
            .then((action) {
              if (action != null) return _handleNativeAction(action);
            })
            .catchError((Object _) {}),
      );
    }
    if (!identical(push, _observedPush)) {
      _pushRoutes?.cancel();
      _foregroundCalls?.cancel();
      _openedNotifications?.cancel();
      _observedPush = push;
      _pushRoutes = push.routes.listen((route) {
        _route(route);
      });
      _foregroundCalls = push.foregroundEvents.listen((data) {
        unawaited(_handleForegroundCall(data));
        // A notification arrived while the app is open: it is already an
        // inbox record, so the bell's count moves now.
        if (notificationIdOf(data) != null) {
          ref.invalidate(unreadNotificationsProvider);
        }
      });
      _openedNotifications = push.openedNotificationIds.listen((id) {
        unawaited(_markOpened(id));
      });
    }

    return MaterialApp.router(
      scaffoldMessengerKey: _messengerKey,
      title: AppConfig.appName,
      debugShowCheckedModeBanner: false,
      routerConfig: router,
      theme: AppTheme.dark,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.dark,
      locale: locale,
      supportedLocales: AppLocales.supported,
      localizationsDelegates: const <LocalizationsDelegate<Object>>[
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      builder: (BuildContext context, Widget? child) {
        // Keep the layout readable without ignoring the user's font size:
        // clamp rather than lock.
        final MediaQueryData data = MediaQuery.of(context);
        return MediaQuery(
          data: data.copyWith(
            textScaler: data.textScaler.clamp(
              minScaleFactor: 0.9,
              maxScaleFactor: 2.0,
            ),
          ),
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}
