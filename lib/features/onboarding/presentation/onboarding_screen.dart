import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/assets/app_assets.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/localization/locale_controller.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/widgets.dart';
import '../../auth/application/session_controller.dart';

class OnboardingScreen extends ConsumerWidget {
  const OnboardingScreen({super.key});

  Future<void> _finish(
    BuildContext context,
    WidgetRef ref,
    String route,
  ) async {
    await ref.read(sessionProvider.notifier).completeOnboarding();
    if (context.mounted) context.go(route);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final tr = context.languageCode == 'tr';
    return AstroScaffold(
      backgroundAsset: AppAssets.splashBackground,
      backgroundAspectRatio: 1080 / 1920,
      scrimOpacity: .16,
      body: LayoutBuilder(
        builder: (context, constraints) {
          final logoWidth = (constraints.maxWidth * .78).clamp(220.0, 330.0);
          return SingleChildScrollView(
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: constraints.maxHeight),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Align(
                      alignment: Alignment.centerRight,
                      child: PopupMenuButton<Locale>(
                        tooltip: l10n.homeLanguage,
                        onSelected: (locale) => ref
                            .read(localeControllerProvider.notifier)
                            .setLocale(locale),
                        itemBuilder: (_) => [
                          PopupMenuItem(
                            value: const Locale('tr'),
                            child: Text(l10n.languageTurkish),
                          ),
                          PopupMenuItem(
                            value: const Locale('en'),
                            child: Text(l10n.languageEnglish),
                          ),
                        ],
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 12,
                          ),
                          decoration: BoxDecoration(
                            color: AppColors.night.withValues(alpha: .72),
                            borderRadius: BorderRadius.circular(30),
                            border: Border.all(color: AppColors.hairlineStrong),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                context.languageCode.toUpperCase(),
                                style: AppTypography.labelLarge.copyWith(
                                  color: AppColors.goldBright,
                                ),
                              ),
                              const SizedBox(width: 8),
                              const Icon(
                                Icons.keyboard_arrow_down,
                                size: 18,
                                color: AppColors.goldBright,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                    AstroReveal(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 18),
                        child: AstroBrandLogo(width: logoWidth),
                      ),
                    ),
                    AstroReveal(
                      order: 1,
                      child: Text(
                        tr
                            ? 'EVREN HER ZAMAN KONUŞUR.\nSEN SADECE DİNLE.'
                            : 'THE UNIVERSE IS ALWAYS SPEAKING.\nJUST LISTEN.',
                        textAlign: TextAlign.center,
                        style: AppTypography.overline.copyWith(
                          color: AppColors.ivory,
                          letterSpacing: 2.5,
                          height: 1.8,
                        ),
                      ),
                    ),
                    const SizedBox(height: 36),
                    AstroReveal(
                      order: 2,
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _Pillar(
                            icon: Icons.auto_awesome_outlined,
                            title: tr ? 'Astroloji' : 'Astrology',
                            caption: tr ? 'Kendini tanı' : 'Know yourself',
                          ),
                          _Pillar(
                            icon: Icons.style_outlined,
                            title: l10n.exploreTarot,
                            caption: l10n.pillarTarotSub,
                          ),
                          _Pillar(
                            icon: Icons.bolt_outlined,
                            title: l10n.exploreRune,
                            caption: l10n.pillarRuneSub,
                          ),
                          _Pillar(
                            icon: Icons.spa_outlined,
                            title: l10n.exploreKatina,
                            caption: l10n.pillarKatinaSub,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 28),
                    AstroReveal(
                      order: 3,
                      child: Column(
                        children: [
                          AstroPress(
                            child: AstroButton(
                              label: l10n.onboardingStart,
                              trailingArrow: true,
                              onPressed: () =>
                                  _finish(context, ref, AppRoutes.register),
                            ),
                          ),
                          const SizedBox(height: 12),
                          AstroPress(
                            child: AstroOutlineButton(
                              label: l10n.onboardingHaveAccount,
                              trailingArrow: true,
                              onPressed: () =>
                                  _finish(context, ref, AppRoutes.login),
                            ),
                          ),
                          const SizedBox(height: 26),
                          AstroBrandFooter(motto: l10n.brandMotto),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _Pillar extends StatelessWidget {
  const _Pillar({
    required this.icon,
    required this.title,
    required this.caption,
  });
  final IconData icon;
  final String title, caption;
  @override
  Widget build(BuildContext context) => Expanded(
    child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 3),
      child: Column(
        children: [
          Container(
            width: 54,
            height: 54,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppColors.night.withValues(alpha: .7),
              border: Border.all(color: AppColors.gold.withValues(alpha: .8)),
            ),
            child: Icon(icon, size: 28, color: AppColors.goldBright),
          ),
          const SizedBox(height: 12),
          Text(
            title,
            textAlign: TextAlign.center,
            style: AppTypography.labelMedium.copyWith(color: AppColors.ivory),
          ),
          const SizedBox(height: 4),
          Text(
            caption,
            textAlign: TextAlign.center,
            style: AppTypography.bodySmall.copyWith(
              fontSize: 12,
              color: AppColors.ivoryMuted,
            ),
          ),
        ],
      ),
    ),
  );
}
