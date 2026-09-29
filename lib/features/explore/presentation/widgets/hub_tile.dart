import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/widgets.dart';

/// Row used by the Sky and Explore hubs.
class HubTile extends StatelessWidget {
  const HubTile({
    required this.asset,
    required this.title,
    required this.subtitle,
    required this.onTap,
    super.key,
    this.trailing,
  });

  final String asset;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: AstroCard(
        onTap: onTap,
        semanticLabel: '$title, $subtitle',
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Row(
          children: <Widget>[
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: AppColors.hairline),
              ),
              clipBehavior: Clip.antiAlias,
              child: AstroImage(
                asset,
                width: 52,
                height: 52,
                fit: BoxFit.cover,
              ),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Text(
                    title,
                    style: AppTypography.titleLarge.copyWith(fontSize: 18),
                  ),
                  Text(subtitle, style: AppTypography.bodySmall),
                ],
              ),
            ),
            trailing ??
                const Icon(Icons.chevron_right, color: AppColors.ivoryMuted),
          ],
        ),
      ),
    );
  }
}
