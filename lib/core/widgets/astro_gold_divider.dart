import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

/// Hairline that fades out at both ends; optionally carries a centred label
/// such as "Bu yorumu oluşturan etkiler".
class AstroGoldDivider extends StatelessWidget {
  const AstroGoldDivider({super.key, this.label, this.labelStyle});

  final String? label;
  final TextStyle? labelStyle;

  @override
  Widget build(BuildContext context) {
    final Widget line = Container(
      height: 1,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: <Color>[
            Colors.transparent,
            AppColors.hairlineStrong,
            Colors.transparent,
          ],
        ),
      ),
    );

    if (label == null) return line;

    return Row(
      children: <Widget>[
        Expanded(child: line),
        Flexible(
          flex: 4,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
            child: Text(
              label!,
              textAlign: TextAlign.center,
              style:
                  labelStyle ??
                  AppTypography.labelMedium.copyWith(color: AppColors.ivory),
            ),
          ),
        ),
        Expanded(child: line),
      ],
    );
  }
}

/// The brand footer line: DAHA BİLİNÇLİ • DAHA DENGELİ • DAHA SEN
class AstroBrandFooter extends StatelessWidget {
  const AstroBrandFooter({required this.motto, super.key});

  final String motto;

  @override
  Widget build(BuildContext context) => Row(
    children: <Widget>[
      const Expanded(child: AstroGoldDivider()),
      Flexible(
        flex: 6,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
          child: FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              motto,
              textAlign: TextAlign.center,
              maxLines: 1,
              style: AppTypography.labelSmall.copyWith(
                color: AppColors.gold,
                letterSpacing: 1.6,
              ),
            ),
          ),
        ),
      ),
      const Expanded(child: AstroGoldDivider()),
    ],
  );
}
