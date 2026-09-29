import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../astro_ai/application/astro_ai_controller.dart';

import '../../core/extensions/context_extensions.dart';
import '../../core/widgets/widgets.dart';

/// Bottom-navigation shell. [StatefulShellRoute.indexedStack] keeps each tab's
/// navigation state and scroll position alive across switches.
class AppShell extends ConsumerWidget {
  const AppShell({required this.navigationShell, super.key});

  final StatefulNavigationShell navigationShell;

  void _goBranch(int index) {
    navigationShell.goBranch(
      index,
      // Tapping the active tab returns it to its root.
      initialLocation: index == navigationShell.currentIndex,
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final List<AstroNavItem> items = <AstroNavItem>[
      AstroNavItem(label: context.l10n.navToday, icon: Icons.home_outlined),
      AstroNavItem(
        label: context.l10n.navSky,
        icon: Icons.brightness_3_outlined,
      ),
      AstroNavItem(
        label: context.l10n.navAstroAi,
        icon: Icons.auto_awesome,
        isCenter: true,
      ),
      AstroNavItem(
        label: context.l10n.navExplore,
        icon: Icons.explore_outlined,
      ),
      AstroNavItem(label: context.l10n.navProfile, icon: Icons.person_outline),
    ];

    return PopScope(
      // Android back on a secondary tab returns to Today instead of leaving.
      canPop: navigationShell.currentIndex == 0,
      onPopInvokedWithResult: (bool didPop, Object? result) {
        if (!didPop) _goBranch(0);
      },
      child: AstroScaffold(
        safeAreaBottom: false,
        body: navigationShell,
        bottomNavigationBar: AstroBottomNavigation(
          items: items,
          currentIndex: navigationShell.currentIndex,
          onSelected: (index) {
            if (navigationShell.currentIndex == 2 && index != 2) {
              ref.read(astroAIControllerProvider.notifier).cancel();
            }
            _goBranch(index);
          },
        ),
      ),
    );
  }
}
