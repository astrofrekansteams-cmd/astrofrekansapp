import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/extensions/context_extensions.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/widgets/widgets.dart';
import '../../l10n/generated/app_localizations.dart';

/// Which feature the placeholder stands in for. These screens are built in
/// later phases; the routes exist now so navigation is real.
enum ComingSoonTitle {
  generic,
  natalChart,
  transits,
  compatibility,
  tarot,
  rune,
  katina,
  cosmicCalendar,
  consultants,
  premium,
}

class ComingSoonScreen extends StatelessWidget {
  const ComingSoonScreen({required this.titleKey, super.key});

  final ComingSoonTitle titleKey;

  String _title(AppLocalizations l10n) => switch (titleKey) {
    ComingSoonTitle.natalChart => l10n.skyNatalChart,
    ComingSoonTitle.transits => l10n.skyTransits,
    ComingSoonTitle.compatibility => l10n.skyCompatibility,
    ComingSoonTitle.tarot => l10n.exploreTarot,
    ComingSoonTitle.rune => l10n.exploreRune,
    ComingSoonTitle.katina => l10n.exploreKatina,
    ComingSoonTitle.cosmicCalendar => l10n.skyCosmicCalendar,
    ComingSoonTitle.consultants => l10n.exploreConsultants,
    ComingSoonTitle.premium => l10n.explorePremium,
    ComingSoonTitle.generic => l10n.comingSoonTitle,
  };

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;

    return AstroScaffold(
      body: Column(
        children: <Widget>[
          Padding(
            padding: EdgeInsets.symmetric(horizontal: context.gutter),
            child: Row(
              children: <Widget>[
                AstroIconButton(
                  icon: Icons.arrow_back,
                  semanticLabel: l10n.commonBack,
                  onPressed: () =>
                      context.canPop() ? context.pop() : context.go('/home'),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(_title(l10n), style: AppTypography.titleLarge),
                ),
              ],
            ),
          ),
          Expanded(
            child: AstroEmptyState(
              kind: AstroEmptyStateKind.noData,
              title: l10n.comingSoonTitle,
              message: l10n.comingSoonBody,
            ),
          ),
        ],
      ),
    );
  }
}
