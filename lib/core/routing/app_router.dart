import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/astro_ai/presentation/astro_ai_screen.dart';
import '../../features/auth/application/session_controller.dart';
import '../../features/auth/presentation/login_screen.dart';
import '../../features/auth/presentation/password_reset_screens.dart';
import '../../features/auth/presentation/register_screen.dart';
import '../../features/explore/presentation/explore_screen.dart';
import '../../features/home/presentation/home_screen.dart';
import '../../features/onboarding/presentation/onboarding_screen.dart';
import '../../features/placeholder/coming_soon_screen.dart';
import '../../features/guides/presentation/moon_guide_screen.dart';
import '../../features/guides/presentation/numerology_screen.dart';
import '../../features/guides/presentation/returns_screen.dart';
import '../../features/guides/presentation/stone_guide_screen.dart';
import '../../features/profile/presentation/profile_screen.dart';
import '../../features/shell/app_shell.dart';
import '../../features/sky/presentation/sky_screen.dart';
import '../../features/splash/presentation/splash_screen.dart';
import 'deep_links.dart';
import 'app_routes.dart';
import '../../features/production/presentation/sky_detail_screens.dart';
import '../../features/production/presentation/relationship_screens.dart';
import '../../features/production/presentation/divination_screen.dart';
import '../../features/production/presentation/forecast_screen.dart';
import '../../features/production/presentation/profile_data_screens.dart';
import '../../features/astro_ai/presentation/ai_library_screen.dart';
import '../../features/marketplace/presentation/marketplace_screens.dart';
import '../../features/marketplace/presentation/booking_screens.dart';
import '../../features/marketplace/presentation/expert_workspace_screen.dart';
import '../../features/consultation/presentation/consultation_screens.dart';
import '../../features/calls/presentation/call_screens.dart';
import '../../features/billing/presentation/coin_wallet_screen.dart';
import '../../features/billing/presentation/premium_screen.dart';
import '../../features/profile/presentation/profile_settings_screens.dart';
import '../../features/profile/presentation/account_center_screens.dart';
import '../../features/notifications/presentation/notification_center_screen.dart';
import '../astrology/data/production_models.dart';

final GlobalKey<NavigatorState> _rootNavigatorKey = GlobalKey<NavigatorState>(
  debugLabel: 'root',
);

/// Bridges Riverpod session changes into GoRouter's refresh mechanism.
class _SessionRefresh extends ChangeNotifier {
  _SessionRefresh(this._ref) {
    _ref.listen<SessionState>(sessionProvider, (
      SessionState? previous,
      SessionState next,
    ) {
      if (previous?.status != next.status ||
          previous?.onboardingSeen != next.onboardingSeen) {
        notifyListeners();
      }
    });
  }

  final Ref _ref;
}

final Provider<GoRouter> routerProvider = Provider<GoRouter>((Ref ref) {
  final _SessionRefresh refresh = _SessionRefresh(ref);
  ref.onDispose(refresh.dispose);

  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: AppRoutes.splash,
    refreshListenable: refresh,
    debugLogDiagnostics: false,
    redirect: (BuildContext context, GoRouterState state) {
      // An outside link (astrofrekans://app/...) is reduced to an allowed
      // in-app location first; the checks below then apply to it as usual.
      if (isExternalLink(state.uri)) return externalLinkTarget(state.uri);

      final SessionState session = ref.read(sessionProvider);
      final String location = state.matchedLocation;

      // A reset link opened from email needs no session, and the link's token
      // would be lost behind the splash redirect.
      final bool resetFlow =
          location == AppRoutes.forgotPassword ||
          location == AppRoutes.resetPassword;
      if (!session.isResolved && resetFlow) return null;

      // Until storage has been read, the splash screen owns the screen.
      if (!session.isResolved) {
        return location == AppRoutes.splash ? null : AppRoutes.splash;
      }

      if (!session.isAuthenticated) {
        // A reset link must open wherever the person is in the app's first
        // run - they may be on a new device that never saw onboarding.
        if (resetFlow) return null;
        if (!session.onboardingSeen) {
          return location == AppRoutes.onboarding ? null : AppRoutes.onboarding;
        }
        final bool onPublicScreen =
            location == AppRoutes.login ||
            location == AppRoutes.register ||
            location == AppRoutes.onboarding;
        return onPublicScreen ? null : AppRoutes.login;
      }

      // Signed in: never sit on an auth screen.
      if (AppRoutes.publicRoutes.contains(location)) return AppRoutes.home;
      return null;
    },
    routes: <RouteBase>[
      GoRoute(
        path: AppRoutes.splash,
        name: 'splash',
        builder: (BuildContext context, GoRouterState state) =>
            const SplashScreen(),
      ),
      GoRoute(
        path: AppRoutes.onboarding,
        name: 'onboarding',
        builder: (BuildContext context, GoRouterState state) =>
            const OnboardingScreen(),
      ),
      GoRoute(
        path: AppRoutes.login,
        name: 'login',
        builder: (BuildContext context, GoRouterState state) =>
            const LoginScreen(),
      ),
      GoRoute(
        path: AppRoutes.register,
        name: 'register',
        builder: (BuildContext context, GoRouterState state) =>
            const RegisterScreen(),
      ),
      GoRoute(
        path: AppRoutes.forgotPassword,
        name: 'forgot-password',
        builder: (BuildContext context, GoRouterState state) =>
            ForgotPasswordScreen(
              initialEmail: state.uri.queryParameters['email'],
            ),
      ),
      GoRoute(
        path: AppRoutes.resetPassword,
        name: 'reset-password',
        builder: (BuildContext context, GoRouterState state) =>
            // Keyed by token: a second link opened while this screen is up
            // must be checked afresh, not inherit the first link's state.
            ResetPasswordScreen(
              key: ValueKey<String?>(state.uri.queryParameters['token']),
              token: state.uri.queryParameters['token'],
            ),
      ),
      StatefulShellRoute.indexedStack(
        builder:
            (
              BuildContext context,
              GoRouterState state,
              StatefulNavigationShell navigationShell,
            ) => AppShell(navigationShell: navigationShell),
        branches: <StatefulShellBranch>[
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: AppRoutes.home,
                name: 'home',
                builder: (BuildContext context, GoRouterState state) =>
                    const HomeScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: AppRoutes.sky,
                name: 'sky',
                builder: (BuildContext context, GoRouterState state) =>
                    const SkyScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: AppRoutes.astroAi,
                name: 'astroAi',
                builder: (BuildContext context, GoRouterState state) =>
                    const AstroAiScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: AppRoutes.explore,
                name: 'explore',
                builder: (BuildContext context, GoRouterState state) =>
                    const ExploreScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: AppRoutes.profile,
                name: 'profile',
                builder: (BuildContext context, GoRouterState state) =>
                    const ProfileScreen(),
              ),
            ],
          ),
        ],
      ),
      // Feature screens live above the shell so they keep a back button and do
      // not disturb tab state. They are placeholders until their phase starts.
      ..._comingSoonRoutes,
      GoRoute(
        path: AppRoutes.marketplace,
        builder: (_, state) => MarketplaceScreen(
          specialty: state.uri.queryParameters['specialty'],
          deliveryType: state.uri.queryParameters['delivery'],
        ),
      ),
      GoRoute(
        path: '${AppRoutes.marketplace}/:id',
        builder: (_, state) =>
            ExpertDetailScreen(expertId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '${AppRoutes.marketplace}/:id/services/:serviceId/book',
        builder: (_, state) => BookingScreen(
          expertId: state.pathParameters['id']!,
          serviceId: state.pathParameters['serviceId']!,
        ),
      ),
      GoRoute(
        path: AppRoutes.favorites,
        builder: (_, _) => const FavoriteExpertsScreen(),
      ),
      GoRoute(path: AppRoutes.orders, builder: (_, _) => const OrdersScreen()),
      GoRoute(
        path: '${AppRoutes.orders}/:id',
        builder: (_, state) =>
            OrderDetailScreen(id: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '${AppRoutes.orders}/:id/consent',
        builder: (_, state) =>
            OrderConsentScreen(orderId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '${AppRoutes.orders}/:id/chat',
        builder: (_, state) =>
            OpenOrderChatScreen(orderId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '${AppRoutes.orders}/:id/call',
        builder: (_, state) =>
            OpenOrderCallScreen(orderId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: AppRoutes.callHistory,
        builder: (_, _) => const CallHistoryScreen(),
      ),
      GoRoute(
        path: '${AppRoutes.calls}/:id/incoming',
        builder: (_, state) => CallScreen(
          id: state.pathParameters['id']!,
          incoming: true,
          autoAnswer: state.uri.queryParameters['answer'] == '1',
        ),
      ),
      GoRoute(
        path: '${AppRoutes.calls}/:id',
        builder: (_, state) => CallScreen(id: state.pathParameters['id']!),
      ),
      GoRoute(
        path: AppRoutes.premium,
        builder: (_, state) =>
            PremiumScreen(initialTier: state.uri.queryParameters['tier']),
      ),
      GoRoute(
        path: AppRoutes.appointments,
        builder: (_, _) => const AppointmentsScreen(),
      ),
      GoRoute(
        path: '${AppRoutes.appointments}/:id',
        builder: (_, state) =>
            AppointmentDetailScreen(id: state.pathParameters['id']!),
      ),
      GoRoute(
        path: AppRoutes.consultations,
        builder: (_, _) => const ConsultationsScreen(),
      ),
      GoRoute(
        path: '${AppRoutes.consultations}/:id',
        builder: (_, state) =>
            ChatThreadScreen(id: state.pathParameters['id']!),
      ),
      GoRoute(
        path: AppRoutes.expertWorkspace,
        builder: (_, _) => const ExpertWorkspaceScreen(),
      ),
      GoRoute(
        path: '${AppRoutes.expertWorkspace}/orders',
        builder: (_, _) => const OrdersScreen(expert: true),
      ),
      GoRoute(
        path: '${AppRoutes.expertWorkspace}/orders/:id',
        builder: (_, state) =>
            OrderDetailScreen(id: state.pathParameters['id']!, expert: true),
      ),
      GoRoute(
        path: '${AppRoutes.expertWorkspace}/appointments',
        builder: (_, _) => const AppointmentsScreen(expert: true),
      ),
      GoRoute(
        path: '${AppRoutes.expertWorkspace}/appointments/:id',
        builder: (_, state) =>
            ExpertAppointmentDetailScreen(id: state.pathParameters['id']!),
      ),
      GoRoute(
        path: AppRoutes.natalChart,
        builder: (_, _) => const NatalScreen(),
      ),
      GoRoute(
        path: AppRoutes.transits,
        builder: (_, _) => const TransitsScreen(),
      ),
      GoRoute(
        path: AppRoutes.cosmicCalendar,
        builder: (_, _) => const CalendarScreen(),
      ),
      GoRoute(
        path: AppRoutes.frequency,
        builder: (_, _) => const FrequencyScreen(),
      ),
      GoRoute(
        path: AppRoutes.forecasts,
        builder: (_, state) => ForecastScreen(
          initialPeriod: switch (state.uri.queryParameters['period']) {
            'weekly' => 'weekly',
            'monthly' => 'monthly',
            'yearly' => 'yearly',
            _ => 'daily',
          },
        ),
      ),
      GoRoute(
        path: AppRoutes.moonGuide,
        builder: (_, _) => const MoonGuideScreen(),
      ),
      GoRoute(
        path: AppRoutes.numerology,
        builder: (_, _) => const NumerologyScreen(),
      ),
      GoRoute(
        path: AppRoutes.stoneGuide,
        builder: (_, _) => const StoneGuideScreen(),
      ),
      GoRoute(
        path: AppRoutes.solarReturn,
        builder: (_, _) => const ReturnsScreen(),
      ),
      GoRoute(
        path: AppRoutes.lunarReturn,
        builder: (_, _) => const ReturnsScreen(lunar: true),
      ),
      GoRoute(
        path: AppRoutes.accountCenter,
        builder: (_, _) => const AccountCenterScreen(),
      ),
      GoRoute(
        path: AppRoutes.accountInfo,
        builder: (_, _) => const AccountInfoScreen(),
      ),
      GoRoute(
        path: AppRoutes.changePassword,
        builder: (_, _) => const ChangePasswordScreen(),
      ),
      GoRoute(
        path: AppRoutes.accountSessions,
        builder: (_, _) => const SessionsScreen(),
      ),
      GoRoute(
        path: AppRoutes.deleteAccount,
        builder: (_, _) => const DeleteAccountScreen(),
      ),
      GoRoute(
        path: AppRoutes.settings,
        builder: (_, _) => const SettingsScreen(),
      ),
      GoRoute(
        path: AppRoutes.notifications,
        builder: (_, _) => const NotificationCenterScreen(),
      ),
      GoRoute(
        path: AppRoutes.profileEdit,
        builder: (_, _) => const ProfileEditScreen(),
      ),
      GoRoute(
        path: AppRoutes.profileCustomize,
        builder: (_, _) => const ProfileCustomizeScreen(),
      ),
      GoRoute(
        path: AppRoutes.notificationSettings,
        builder: (_, _) => const NotificationSettingsScreen(),
      ),
      GoRoute(
        path: AppRoutes.privacySettings,
        builder: (_, _) => const PrivacySettingsScreen(),
      ),
      GoRoute(
        path: AppRoutes.coins,
        builder: (_, _) => const CoinWalletScreen(),
      ),
      GoRoute(
        path: AppRoutes.savedPeople,
        builder: (_, _) => const SavedPeopleScreen(),
      ),
      GoRoute(
        path: AppRoutes.compatibility,
        builder: (_, state) => CompatibilityScreen(
          personId: state.uri.queryParameters['person'],
          initialKind: switch (state.uri.queryParameters['kind']) {
            'composite' => 'composite',
            'davison' => 'davison',
            _ => 'synastry',
          },
        ),
      ),
      GoRoute(path: AppRoutes.horary, builder: (_, _) => const HoraryScreen()),
      GoRoute(
        path: '${AppRoutes.horary}/:id',
        builder: (_, state) =>
            HoraryScreen(questionId: state.pathParameters['id']),
      ),
      GoRoute(
        path: AppRoutes.aiReports,
        builder: (_, state) =>
            AILibraryScreen(jobId: state.uri.queryParameters['job']),
      ),
      GoRoute(
        path: '${AppRoutes.aiReports}/:id',
        builder: (_, state) =>
            AILibraryScreen(reportId: state.pathParameters['id']),
      ),
      for (final entry in <String, DeckType>{
        AppRoutes.tarot: DeckType.tarot,
        AppRoutes.rune: DeckType.rune,
        AppRoutes.katina: DeckType.katina,
      }.entries) ...[
        GoRoute(
          path: entry.key,
          builder: (_, _) => DivinationScreen(deck: entry.value),
        ),
        GoRoute(
          path: '${entry.key}/:id',
          builder: (_, state) => DivinationScreen(
            deck: entry.value,
            readingId: state.pathParameters['id'],
          ),
        ),
      ],
    ],
    errorBuilder: (BuildContext context, GoRouterState state) =>
        const ComingSoonScreen(titleKey: ComingSoonTitle.generic),
  );
});

final List<GoRoute> _comingSoonRoutes = <GoRoute>[
  GoRoute(
    path: AppRoutes.consultants,
    redirect: (_, _) => AppRoutes.marketplace,
  ),
];
