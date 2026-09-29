import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/assets/app_assets.dart';
import '../../../core/astrology/domain/zodiac_sign.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/localization/astro_labels.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/widgets.dart';
import '../../billing/application/entitlement_service.dart';
import '../../billing/presentation/coin_wallet_screen.dart';
import '../../production/application/core_providers.dart';
import '../domain/user_profile.dart';

/// Cover styles, in picker order. Codes match the server's list.
const coverThemes = <String, List<Color>>{
  'cosmic_night': [Color(0xFF111730), Color(0xFF05070F)],
  'golden_dawn': [Color(0xFF3A2A12), Color(0xFF0A0E1C)],
  'moonlit': [Color(0xFF1E2A44), Color(0xFF090F1A)],
  'nebula': [Color(0xFF2B1640), Color(0xFF0A0E1C)],
  'aurora': [Color(0xFF0F3A34), Color(0xFF05070F)],
};

/// The user's avatar: a chosen zodiac glyph, else their initials.
class ProfileAvatar extends StatelessWidget {
  const ProfileAvatar({super.key, required this.user, this.size = 88});
  final UserProfile? user;
  final double size;
  @override
  Widget build(BuildContext context) => AstroAvatar(
    size: size,
    assetPath: AppAssets.zodiac[user?.avatarPreset],
    initials: user?.initials,
  );
}

/// Profile header: cover, avatar, name, bio, plan, coins, big three.
class ProfileHeader extends ConsumerWidget {
  const ProfileHeader({super.key, required this.user});
  final UserProfile? user;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tier = ref.watch(subscriptionTierProvider);
    final colors =
        coverThemes[user?.coverTheme] ?? coverThemes['cosmic_night']!;
    final bio = user?.bio;
    return Container(
      key: const ValueKey('profile-header'),
      decoration: BoxDecoration(
        borderRadius: AppRadius.brLg,
        border: Border.all(color: AppColors.hairlineStrong),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: colors,
        ),
      ),
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ProfileAvatar(user: user),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      user?.name ?? context.l10n.profileTitle,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: AppTypography.displayMedium.copyWith(fontSize: 26),
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Wrap(
                      spacing: AppSpacing.sm,
                      runSpacing: AppSpacing.xs,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        AstroBadge(
                          key: const ValueKey('plan-badge'),
                          label: b12(context, 'tier_${tier.wire}'),
                          icon: tier.isPaid ? Icons.star : null,
                        ),
                        const CoinBalanceChip(),
                      ],
                    ),
                  ],
                ),
              ),
              IconButton(
                tooltip: b12(context, 'profile_customize'),
                onPressed: () => context.push(AppRoutes.profileCustomize),
                icon: const Icon(Icons.edit_outlined, color: AppColors.gold),
              ),
            ],
          ),
          if (bio != null && bio.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.md),
            Text(bio, style: AppTypography.bodyMedium),
          ],
          const SizedBox(height: AppSpacing.md),
          const _BigThree(),
        ],
      ),
    );
  }
}

class _BigThree extends ConsumerWidget {
  const _BigThree();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final chart = ref.watch(natalProvider).asData?.value;
    if (chart == null) return const SizedBox.shrink();
    final l10n = context.l10n;
    final labels = [
      b12(context, 'big3_sun'),
      b12(context, 'big3_moon'),
      b12(context, 'big3_rising'),
    ];
    return Row(
      children: [
        for (final (i, sign) in chart.bigThree.indexed)
          if (sign != null)
            Expanded(
              child: Column(
                children: [
                  Text(labels[i], style: AppTypography.labelSmall),
                  const SizedBox(height: 2),
                  Text(
                    l10n.sign(sign),
                    style: AppTypography.titleMedium.copyWith(
                      color: AppColors.goldBright,
                    ),
                  ),
                ],
              ),
            ),
      ],
    );
  }
}

/// Zodiac codes in order, for the avatar picker.
List<String> get avatarPresets =>
    ZodiacSign.values.map((s) => s.name).toList(growable: false);
