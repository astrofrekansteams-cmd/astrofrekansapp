import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../assets/app_assets.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';
import 'astro_image.dart';
import '../extensions/context_extensions.dart';

/// One destination of [AstroBottomNavigation].
class AstroNavItem {
  const AstroNavItem({
    required this.label,
    required this.icon,
    this.isCenter = false,
  });

  final String label;
  final IconData icon;

  /// The Astro AI tab is the visual anchor of the bar, exactly as in the
  /// reference: a gold compass star inside a ring.
  final bool isCenter;
}

class AstroBottomNavigation extends StatelessWidget {
  const AstroBottomNavigation({
    required this.items,
    required this.currentIndex,
    required this.onSelected,
    super.key,
  });

  final List<AstroNavItem> items;
  final int currentIndex;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    final double bottomInset = MediaQuery.paddingOf(context).bottom;
    final TextScaler scaler = MediaQuery.textScalerOf(context);
    final double labelHeight = scaler
        .scale(AppTypography.minFontSize * 1.25)
        .clamp(15, 22);

    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.night.withValues(alpha: 0.94),
        border: const Border(top: BorderSide(color: AppColors.hairline)),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 60 + labelHeight + (bottomInset > 0 ? 0 : AppSpacing.sm),
          child: Row(
            children: <Widget>[
              for (int i = 0; i < items.length; i++)
                Expanded(
                  child: _NavButton(
                    item: items[i],
                    selected: i == currentIndex,
                    onTap: () => onSelected(i),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({
    required this.item,
    required this.selected,
    required this.onTap,
  });

  final AstroNavItem item;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final Color color = selected ? AppColors.goldBright : AppColors.ivoryMuted;

    return Semantics(
      button: true,
      selected: selected,
      label: item.label,
      child: InkWell(
        onTap: onTap,
        customBorder: const StadiumBorder(),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              if (!item.isCenter)
                // Active marker: a short champagne bar above the icon.
                AnimatedContainer(
                  duration: Duration(
                    milliseconds: context.reduceMotion ? 0 : 220,
                  ),
                  width: selected ? 22 : 0,
                  height: 2,
                  margin: const EdgeInsets.only(bottom: AppSpacing.xs + 2),
                  decoration: BoxDecoration(
                    color: AppColors.gold,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              if (item.isCenter)
                _CenterStar(selected: selected)
              else
                AnimatedScale(
                  scale: selected ? 1.12 : 1,
                  duration: Duration(
                    milliseconds: context.reduceMotion ? 0 : 220,
                  ),
                  curve: Curves.easeOutCubic,
                  child: Icon(item.icon, size: 23, color: color),
                ),
              const SizedBox(height: AppSpacing.xs),
              Flexible(
                child: Text(
                  item.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.center,
                  style: AppTypography.labelSmall.copyWith(
                    letterSpacing: 0.2,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                    color: color,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CenterStar extends StatelessWidget {
  const _CenterStar({required this.selected});

  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 46,
      height: 46,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: <Color>[
            AppColors.navySoft.withValues(alpha: selected ? 0.95 : 0.7),
            AppColors.night,
          ],
        ),
        border: Border.all(
          color: selected ? AppColors.gold : AppColors.hairlineStrong,
          width: selected ? 1.4 : 1,
        ),
        boxShadow: selected
            ? <BoxShadow>[
                BoxShadow(
                  color: AppColors.gold.withValues(alpha: 0.28),
                  blurRadius: 18,
                ),
              ]
            : null,
      ),
      child: Center(
        child: Transform.rotate(
          angle: selected ? 0 : math.pi / 90,
          child: AstroImage(
            AppAssets.premiumStar,
            width: 26,
            height: 26,
            opacity: selected ? 1 : 0.62,
          ),
        ),
      ),
    );
  }
}
