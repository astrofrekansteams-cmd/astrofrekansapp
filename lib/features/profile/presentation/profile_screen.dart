import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'profile_widgets.dart';
import '../../billing/presentation/subscription_actions.dart';

import '../../../core/assets/app_assets.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/utils/text_case.dart';
import '../../../core/widgets/widgets.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../auth/application/session_controller.dart';
import '../domain/user_profile.dart';
import '../../marketplace/data/marketplace_repository.dart';
import '../../../core/localization/b12_copy.dart';

/// Minimal profile for this phase: identity, plan, and the settings rows that
/// the later phases will fill in. Sign-out is real so the auth flow can be
/// exercised end to end.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppLocalizations l10n = context.l10n;
    final UserProfile? user = ref.watch(currentUserProvider);

    Future<void> confirmSignOut() async {
      final bool? confirmed = await showDialog<bool>(
        context: context,
        builder: (BuildContext context) => AlertDialog(
          content: Text(l10n.profileSignOutConfirm),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: Text(l10n.commonCancel),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: Text(
                l10n.authSignOut,
                style: const TextStyle(color: AppColors.danger),
              ),
            ),
          ],
        ),
      );
      if (confirmed ?? false) {
        await ref.read(sessionProvider.notifier).signOut();
      }
    }

    return ListView(
      padding: EdgeInsets.fromLTRB(
        context.gutter,
        AppSpacing.lg,
        context.gutter,
        AppSpacing.huge + 96,
      ),
      children: <Widget>[
        Text(
          l10n.appName,
          textAlign: TextAlign.center,
          style: AppTypography.displayLarge,
        ),
        const SizedBox(height: 28),
        AstroReveal(child: ProfileHeader(user: user)),
        const SizedBox(height: AppSpacing.xl),
        AstroCard(
          key: const ValueKey('menu-plan'),
          onTap: () => context.push(AppRoutes.premium),
          child: Row(
            children: <Widget>[
              const AstroImage(AppAssets.premiumCrown, width: 40, height: 40),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Text(
                      b12(context, 'hub_plans_title'),
                      style: AppTypography.titleLarge.copyWith(fontSize: 18),
                    ),
                    Text(
                      b12(context, 'hub_plans_sub'),
                      style: AppTypography.bodySmall,
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, color: AppColors.ivoryMuted),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        _MenuGroup(
          title: b12(context, 'menu_account'),
          rows: [
            _SettingsRow(
              key: const ValueKey('menu-profile'),
              icon: Icons.palette_outlined,
              label: b12(context, 'menu_profile'),
              route: AppRoutes.profileCustomize,
            ),
            _SettingsRow(
              key: const ValueKey('menu-account-center'),
              icon: Icons.manage_accounts_outlined,
              label: b12(context, 'account_center'),
              route: AppRoutes.accountCenter,
            ),
            _SettingsRow(
              key: const ValueKey('menu-birth'),
              icon: Icons.nightlight_outlined,
              label: l10n.profileBirthData,
              route: AppRoutes.profileEdit,
            ),
            _SettingsRow(
              key: const ValueKey('menu-saved-people'),
              icon: Icons.group_outlined,
              label: l10n.profileSavedPeople,
              route: AppRoutes.savedPeople,
            ),
            _SettingsRow(
              key: const ValueKey('menu-privacy'),
              icon: Icons.shield_outlined,
              label: l10n.profilePrivacy,
              route: AppRoutes.privacySettings,
            ),
          ],
        ),
        _MenuGroup(
          title: b12(context, 'menu_services'),
          rows: [
            _SettingsRow(
              key: const ValueKey('menu-appointments'),
              icon: Icons.event_available_outlined,
              label: b12(context, 'appointments'),
              route: AppRoutes.appointments,
            ),
            _SettingsRow(
              key: const ValueKey('menu-orders'),
              icon: Icons.receipt_long_outlined,
              label: b12(context, 'orders'),
              route: AppRoutes.orders,
            ),
            _SettingsRow(
              key: const ValueKey('menu-messages'),
              icon: Icons.chat_bubble_outline,
              label: b12(context, 'menu_messages'),
              route: AppRoutes.consultations,
            ),
            _SettingsRow(
              key: const ValueKey('menu-reports'),
              icon: Icons.auto_awesome_outlined,
              label: b12(context, 'menu_reports'),
              route: AppRoutes.aiReports,
            ),
            _SettingsRow(
              icon: Icons.favorite_border,
              label: b12(context, 'favorites'),
              route: AppRoutes.favorites,
            ),
            _SettingsRow(
              icon: Icons.call_outlined,
              label: b12(context, 'call_history'),
              route: AppRoutes.callHistory,
            ),
          ],
        ),
        _MenuGroup(
          title: l10n.appName,
          rows: [
            _SettingsRow(
              key: const ValueKey('menu-coins'),
              icon: Icons.account_balance_wallet_outlined,
              label: b12(context, 'coin_wallet'),
              route: AppRoutes.coins,
            ),
            _SettingsRow(
              key: const ValueKey('menu-notifications'),
              icon: Icons.notifications_none,
              label: b12(context, 'notifications_title'),
              route: AppRoutes.notifications,
            ),
            _SettingsRow(
              key: const ValueKey('menu-settings'),
              icon: Icons.settings_outlined,
              label: b12(context, 'menu_settings'),
              route: AppRoutes.settings,
            ),
          ],
        ),
        // Role-based: only an expert sees their workspace.
        if (ref.watch(isExpertProvider).asData?.value ?? false)
          _MenuGroup(
            title: b12(context, 'menu_expert'),
            rows: [
              _SettingsRow(
                key: const ValueKey('menu-expert'),
                icon: Icons.work_outline,
                label: b12(context, 'expert_workspace'),
                route: AppRoutes.expertWorkspace,
              ),
            ],
          ),
        const SizedBox(height: AppSpacing.md),
        const SubscriptionLegalLinks(),
        // Destructive, alone, last.
        OutlinedButton.icon(
          key: const ValueKey('menu-sign-out'),
          style: OutlinedButton.styleFrom(
            foregroundColor: AppColors.danger,
            side: const BorderSide(color: AppColors.danger),
            minimumSize: const Size.fromHeight(AppSpacing.minTapTarget + 4),
          ),
          icon: const Icon(Icons.logout),
          label: Text(l10n.authSignOut),
          onPressed: confirmSignOut,
        ),
      ],
    );
  }
}

class _MenuGroup extends StatelessWidget {
  const _MenuGroup({required this.title, required this.rows});
  final String title;
  final List<Widget> rows;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.lg),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: AppSpacing.sm),
          child: Text(
            title.toUpperCaseFor(context.languageCode),
            style: AppTypography.labelSmall.copyWith(color: AppColors.gold),
          ),
        ),
        AstroCard(
          padding: EdgeInsets.zero,
          child: Column(children: rows),
        ),
      ],
    ),
  );
}

/// Whether the signed-in user has an expert profile. A 404 is simply "no".
final isExpertProvider = FutureProvider.autoDispose<bool>((ref) async {
  if (ref.watch(currentUserProvider) == null) return false;
  try {
    await ref.watch(marketplaceRepositoryProvider).ownProfile();
    return true;
  } on Object {
    return false;
  }
});

class _SettingsRow extends StatelessWidget {
  const _SettingsRow({
    super.key,
    required this.icon,
    required this.label,
    this.route,
  });

  final IconData icon;
  final String label;
  final String? route;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      minTileHeight: AppSpacing.minTapTarget + 20,
      shape: const Border(
        bottom: BorderSide(color: AppColors.hairline, width: .5),
      ),
      leading: Icon(icon, color: AppColors.gold, size: 25),
      title: Text(label, style: AppTypography.titleMedium),
      trailing: const Icon(Icons.chevron_right, color: AppColors.ivoryMuted),
      onTap: () {
        if (route != null) {
          context.push(route!);
          return;
        }
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(SnackBar(content: Text(context.l10n.commonSoon)));
      },
    );
  }
}
