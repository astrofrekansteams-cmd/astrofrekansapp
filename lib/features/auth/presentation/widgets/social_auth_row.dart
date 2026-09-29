import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/extensions/context_extensions.dart';
import '../../../../core/network/api_config.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/widgets.dart';
import '../../application/session_controller.dart';
import '../../domain/auth_repository.dart';
import '../../../../core/widgets/api_state_view.dart';

/// Google / Apple entry points.
///
/// No credentials exist yet, so the buttons show a "coming soon" hint instead
/// of faking a successful social login. The wiring (interface + provider) is
/// already in place: implementing [SocialAuthService] enables them.
class SocialAuthRow extends ConsumerWidget {
  const SocialAuthRow({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final SocialAuthService service = ref.watch(socialAuthServiceProvider);
    final AppEnvironment environment = ref.watch(appEnvironmentProvider);
    // Production shows only what works: no "coming soon" buttons, and no
    // Google sign-in in the first release at all.
    final bool showGoogle =
        environment.googleSignInEnabled &&
        (!environment.isProduction ||
            service.isAvailable(SocialProvider.google));
    final bool showApple =
        (defaultTargetPlatform == TargetPlatform.iOS ||
            defaultTargetPlatform == TargetPlatform.macOS) &&
        environment.appleSignInEnabled &&
        (!environment.isProduction ||
            service.isAvailable(SocialProvider.apple));
    if (!showGoogle && !showApple) return const SizedBox.shrink();

    void notAvailable() {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(context.l10n.authSocialSoon)));
    }

    Future<void> authenticate(SocialProvider provider) async {
      try {
        await ref.read(sessionProvider.notifier).signInWithSocial(provider);
      } on Object catch (error) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(friendlyApiError(context, error))),
          );
        }
      }
    }

    VoidCallback handlerFor(SocialProvider provider) =>
        service.isAvailable(provider)
        ? () => authenticate(provider)
        : notAvailable;

    return Column(
      children: <Widget>[
        Row(
          children: <Widget>[
            const Expanded(child: AstroGoldDivider()),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
              child: Text(
                context.l10n.authOr,
                style: AppTypography.bodySmall.copyWith(
                  color: AppColors.textSubtle,
                ),
              ),
            ),
            const Expanded(child: AstroGoldDivider()),
          ],
        ),
        const SizedBox(height: AppSpacing.lg),
        if (showGoogle)
          Opacity(
            key: const ValueKey('social-google'),
            opacity: service.isAvailable(SocialProvider.google) ? 1 : 0.55,
            child: AstroOutlineButton(
              label: context.l10n.authContinueWithGoogle,
              icon: Icons.g_mobiledata,
              onPressed: handlerFor(SocialProvider.google),
            ),
          ),
        if (showApple) ...<Widget>[
          if (showGoogle) const SizedBox(height: AppSpacing.md),
          Opacity(
            opacity: service.isAvailable(SocialProvider.apple) ? 1 : 0.55,
            child: AstroOutlineButton(
              label: context.l10n.authContinueWithApple,
              icon: Icons.apple,
              onPressed: handlerFor(SocialProvider.apple),
            ),
          ),
        ],
      ],
    );
  }
}
