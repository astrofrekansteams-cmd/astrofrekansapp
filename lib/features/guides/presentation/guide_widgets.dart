import 'package:flutter/material.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../../core/astrology/data/api_contract_dto.dart';
import '../../../core/astrology/domain/aspect.dart';
import '../../../core/astrology/domain/planet.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/localization/astro_labels.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/widgets.dart';

/// Shared pieces for the guide screens, built on the design-system widgets.

String formatLocalMoment(BuildContext context, DateTime? value) => value == null
    ? '—'
    : DateFormat.MMMMd(
        Localizations.localeOf(context).toLanguageTag(),
      ).add_Hm().format(value.toLocal());

class GuideSection extends StatelessWidget {
  const GuideSection({
    super.key,
    required this.title,
    required this.children,
    this.icon,
    this.accent = AppColors.gold,
  });
  final String title;
  final List<Widget> children;
  final IconData? icon;
  final Color accent;

  @override
  Widget build(BuildContext context) => AstroCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            if (icon != null) ...[
              Icon(icon, size: 18, color: accent),
              AppSpacing.gapSm,
            ],
            Expanded(
              child: Semantics(
                header: true,
                child: Text(title, style: AppTypography.headlineMedium),
              ),
            ),
          ],
        ),
        AppSpacing.gapMd,
        ...children,
      ],
    ),
  );
}

class BulletLine extends StatelessWidget {
  const BulletLine(this.text, {super.key, this.color = AppColors.gold});
  final String text;
  final Color color;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.sm),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(top: 7),
          child: Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
        ),
        AppSpacing.gapSm,
        Expanded(child: Text(text, style: AppTypography.bodyMedium)),
      ],
    ),
  );
}

/// "☽ △ Venüs · orb 1.2° · yaklaşıyor" row for a Moon (or any) aspect.
class AspectLine extends StatelessWidget {
  const AspectLine({
    super.key,
    required this.first,
    required this.aspect,
    required this.second,
    required this.orb,
    this.applying,
    this.prefix,
  });
  final Planet first;
  final String aspect;
  final Planet second;
  final double orb;
  final bool? applying;
  final String? prefix;

  @override
  Widget build(BuildContext context) {
    final type = ContractJson.bySnakeOr(
      AspectType.values,
      aspect,
      AspectType.conjunction,
    );
    final l10n = context.l10n;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Row(
        children: [
          AstroImage(first.asset, width: 22, height: 22),
          AppSpacing.gapSm,
          AspectGlyph(type: type, size: 18),
          AppSpacing.gapSm,
          AstroImage(second.asset, width: 22, height: 22),
          AppSpacing.gapSm,
          Expanded(
            child: Text(
              '${prefix ?? ''}${l10n.planet(first)} ${l10n.aspect(type)} '
              '${l10n.planet(second)}',
              style: AppTypography.bodyMedium,
            ),
          ),
          SizedBox(
            width: 52,
            child: Text(
              '${orb.toStringAsFixed(1)}°',
              textAlign: TextAlign.end,
              style: AppTypography.labelMedium,
            ),
          ),
          if (applying != null) ...[
            AppSpacing.gapXs,
            Icon(
              applying! ? Icons.trending_up : Icons.trending_down,
              size: 14,
              color: applying! ? AppColors.success : AppColors.textSubtle,
            ),
          ],
        ],
      ),
    );
  }
}

class KeyValueRow extends StatelessWidget {
  const KeyValueRow({super.key, required this.label, required this.value});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
    child: Row(
      children: [
        Expanded(child: Text(label, style: AppTypography.bodySmall)),
        Text(value, style: AppTypography.titleMedium),
      ],
    ),
  );
}
