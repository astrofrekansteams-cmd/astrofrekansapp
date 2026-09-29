import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/localization/b12_copy.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../application/guides_providers.dart';
import '../domain/guide_models.dart';

/// Pythagorean numerology from the profile's birth name and date. The full
/// birth name can differ from the display name, so it can be overridden.
class NumerologyScreen extends ConsumerStatefulWidget {
  const NumerologyScreen({super.key});
  @override
  ConsumerState<NumerologyScreen> createState() => _NumerologyState();
}

class _NumerologyState extends ConsumerState<NumerologyScreen> {
  final _name = TextEditingController();
  String? _override;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  void _apply() {
    final value = _name.text.trim();
    setState(() => _override = value.length >= 2 ? value : null);
  }

  @override
  Widget build(BuildContext context) {
    final provider = numerologyProvider(_override);
    return CorePage(
      title: 'numerology',
      children: [
        AstroCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                b12(context, 'numerology_intro'),
                style: AppTypography.bodyMedium,
              ),
              AppSpacing.gapMd,
              TextField(
                controller: _name,
                textCapitalization: TextCapitalization.words,
                onSubmitted: (_) => _apply(),
                decoration: InputDecoration(
                  labelText: b12(context, 'full_birth_name'),
                  hintText: b12(context, 'full_birth_name_hint'),
                  suffixIcon: IconButton(
                    tooltip: b12(context, 'calculate'),
                    onPressed: _apply,
                    icon: const Icon(Icons.calculate_outlined),
                  ),
                ),
              ),
            ],
          ),
        ),
        ApiStateView(
          value: ref.watch(provider),
          onRetry: () => ref.invalidate(provider),
          builder: (profile) => _NumbersView(profile: profile),
        ),
      ],
    );
  }
}

class _NumbersView extends StatelessWidget {
  const _NumbersView({required this.profile});
  final NumerologyProfile profile;

  @override
  Widget build(BuildContext context) {
    final lifePath = profile.numbers['life_path']!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          profile.nameUsed,
          textAlign: TextAlign.center,
          style: AppTypography.titleMedium.copyWith(
            color: AppColors.goldBright,
          ),
        ),
        AppSpacing.gapMd,
        _NumberCard(
          label: b12(context, 'num_life_path'),
          meaning: lifePath,
          hero: true,
        ),
        for (final key in NumerologyProfile.keys.skip(1))
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.md),
            child: _NumberCard(
              label: b12(context, 'num_$key'),
              meaning: profile.numbers[key]!,
            ),
          ),
        AppSpacing.gapMd,
        Text(
          b12(context, 'numerology_method'),
          textAlign: TextAlign.center,
          style: AppTypography.labelSmall,
        ),
      ],
    );
  }
}

class _NumberCard extends StatelessWidget {
  const _NumberCard({
    required this.label,
    required this.meaning,
    this.hero = false,
  });
  final String label;
  final NumberMeaning meaning;
  final bool hero;

  @override
  Widget build(BuildContext context) => AstroCard(
    borderColor: hero ? AppColors.gold : AppColors.hairline,
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: hero ? 72 : 56,
          height: hero ? 72 : 56,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: hero ? AppColors.goldGradient : null,
            border: Border.all(color: AppColors.gold),
          ),
          child: Text(
            '${meaning.number}',
            style: AppTypography.score.copyWith(
              fontSize: hero ? 34 : 26,
              color: hero ? AppColors.onGold : AppColors.goldBright,
            ),
          ),
        ),
        AppSpacing.gapLg,
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label.toUpperCase(),
                style: AppTypography.overline.copyWith(color: AppColors.gold),
              ),
              const SizedBox(height: AppSpacing.xxs),
              Row(
                children: [
                  Flexible(
                    child: Text(meaning.title, style: AppTypography.titleLarge),
                  ),
                  if (meaning.isMaster) ...[
                    AppSpacing.gapSm,
                    AstroBadge(label: b12(context, 'master_number')),
                  ],
                ],
              ),
              const SizedBox(height: AppSpacing.xxs),
              Text(meaning.keywords, style: AppTypography.bodySmall),
              AppSpacing.gapSm,
              Text(meaning.meaning, style: AppTypography.bodyMedium),
            ],
          ),
        ),
      ],
    ),
  );
}
