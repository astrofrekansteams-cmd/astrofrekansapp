import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/assets/app_assets.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../explore/presentation/widgets/hub_tile.dart';

/// "Gökyüzü" tab: the astrology hub. The individual screens land in the next
/// phases; this tile list is the navigation surface for them.
class SkyScreen extends StatelessWidget {
  const SkyScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;

    return ListView(
      padding: EdgeInsets.fromLTRB(
        context.gutter,
        AppSpacing.lg,
        context.gutter,
        AppSpacing.huge,
      ),
      children: <Widget>[
        Text(
          l10n.skyTitle,
          style: AppTypography.displayMedium.copyWith(fontSize: 30),
        ),
        Text(l10n.skySubtitle, style: AppTypography.bodyMedium),
        const SizedBox(height: AppSpacing.xl),
        HubTile(
          asset: AppAssets.natalZodiacWheel,
          title: l10n.skyNatalChart,
          subtitle: l10n.skyNatalChartSub,
          onTap: () => context.push(AppRoutes.natalChart),
        ),
        HubTile(
          asset: AppAssets.planets['saturn']!,
          title: l10n.skyTransits,
          subtitle: l10n.skyTransitsSub,
          onTap: () => context.push(AppRoutes.transits),
        ),
        HubTile(
          asset: AppAssets.moonPhases['full_moon']!,
          title: l10n.skyCosmicCalendar,
          subtitle: l10n.skyCosmicCalendarSub,
          onTap: () => context.push(AppRoutes.cosmicCalendar),
        ),
        HubTile(
          asset: AppAssets.dailyFrequency['love']!,
          title: l10n.skyCompatibility,
          subtitle: l10n.skyCompatibilitySub,
          onTap: () => context.push(AppRoutes.compatibility),
        ),
      ],
    );
  }
}
