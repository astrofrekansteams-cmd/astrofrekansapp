import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/astrology/data/api_contract_dto.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../../billing/application/coin_spend.dart';
import '../../billing/application/entitlement_service.dart';
import '../../production/presentation/chart_view.dart';
import '../application/guides_providers.dart';
import '../domain/guide_models.dart';
import 'guide_widgets.dart';

/// Solar return (per birthday year) and lunar return (next Moon return).
class ReturnsScreen extends ConsumerStatefulWidget {
  const ReturnsScreen({super.key, this.lunar = false});
  final bool lunar;
  @override
  ConsumerState<ReturnsScreen> createState() => _ReturnsState();
}

class _ReturnsState extends ConsumerState<ReturnsScreen> {
  late bool lunar = widget.lunar;
  int year = DateTime.now().year;
  DateTime after = DateUtils.dateOnly(DateTime.now());

  @override
  Widget build(BuildContext context) {
    final entitlements = ref.watch(entitlementServiceProvider);
    final feature = lunar
        ? PremiumFeature.lunarReturn
        : PremiumFeature.solarReturn;
    final unlockKey = lunar
        ? lunarReturnUnlockKey(after)
        : solarReturnUnlockKey(year);
    return CorePage(
      title: lunar ? 'lunar_return' : 'solar_return',
      children: [
        SegmentedButton<bool>(
          segments: [
            ButtonSegment(
              value: false,
              label: Text(b12(context, 'solar_return')),
              icon: const Icon(Icons.wb_sunny_outlined),
            ),
            ButtonSegment(
              value: true,
              label: Text(b12(context, 'lunar_return')),
              icon: const Icon(Icons.nightlight_outlined),
            ),
          ],
          selected: {lunar},
          onSelectionChanged: (value) => setState(() => lunar = value.first),
        ),
        Row(
          children: [
            IconButton.outlined(
              tooltip: b12(context, 'previous'),
              onPressed: () => setState(() {
                if (lunar) {
                  after = after.subtract(const Duration(days: 27));
                } else {
                  year--;
                }
              }),
              icon: const Icon(Icons.chevron_left),
            ),
            Expanded(
              child: Text(
                lunar
                    ? formatLocalMoment(
                        context,
                        after,
                      ).split(' ').take(2).join(' ')
                    : '$year',
                textAlign: TextAlign.center,
                style: AppTypography.titleLarge,
              ),
            ),
            IconButton.outlined(
              tooltip: b12(context, 'next'),
              onPressed: () => setState(() {
                if (lunar) {
                  after = after.add(const Duration(days: 27));
                } else {
                  year++;
                }
              }),
              icon: const Icon(Icons.chevron_right),
            ),
          ],
        ),
        if (!entitlements.canUse(feature) &&
            !ref.watch(coinUnlocksProvider).containsKey(unlockKey))
          CoinLockCard(unlockKey: unlockKey, feature: feature)
        else if (lunar)
          ApiStateView(
            value: ref.watch(lunarReturnProvider(after)),
            onRetry: () => ref.invalidate(lunarReturnProvider(after)),
            builder: (reading) => _ReturnView(reading: reading),
          )
        else
          ApiStateView(
            value: ref.watch(solarReturnProvider(year)),
            onRetry: () => ref.invalidate(solarReturnProvider(year)),
            builder: (reading) => _ReturnView(reading: reading),
          ),
      ],
    );
  }
}

class _ReturnView extends StatelessWidget {
  const _ReturnView({required this.reading});
  final ReturnReading reading;

  @override
  Widget build(BuildContext context) {
    final chart = NatalChartDto.fromJson(
      reading.chart.json,
    ).toDomain(event: true);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AstroCard(
          borderColor: AppColors.gold,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${b12(context, 'return_moment')}: ${formatLocalMoment(context, reading.moment)}',
                style: AppTypography.labelMedium.copyWith(
                  color: AppColors.gold,
                ),
              ),
              AppSpacing.gapSm,
              Text(reading.theme.headline, style: AppTypography.headlineMedium),
              AppSpacing.gapMd,
              for (final line in reading.theme.lines) BulletLine(line),
            ],
          ),
        ),
        AppSpacing.gapLg,
        ChartView(chart: chart),
      ],
    );
  }
}
