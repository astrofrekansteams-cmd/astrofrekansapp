import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/astrology/data/production_repository.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../../core/extensions/context_extensions.dart';
import '../../../core/localization/astro_labels.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../../billing/application/coin_spend.dart';
import '../../billing/application/entitlement_service.dart';
import '../application/forecast_digest.dart';
import 'forecast_reading_view.dart';

/// What a forecast opened with AstroCoins is remembered as.
String forecastUnlockKey(String period, DateTime date) => period == 'monthly'
    ? 'monthly_forecast:${date.year}-${date.month}'
    : 'yearly_forecast:${date.year}';

final _forecastProvider = FutureProvider.autoDispose
    .family<Object?, (String, DateTime)>((ref, q) async {
      final repo = ref.watch(productionRepositoryProvider);
      if (repo == null) return null;
      return switch (q.$1) {
        'daily' || 'weekly' => repo.horoscope(q.$1, q.$2),
        'monthly' => loadWithCoins(
          ref,
          forecastUnlockKey('monthly', q.$2),
          (coinRef) => repo.monthly(q.$2, coinRef: coinRef),
        ),
        _ => loadWithCoins(
          ref,
          forecastUnlockKey('yearly', q.$2),
          (coinRef) => repo.yearly(q.$2.year, coinRef: coinRef),
        ),
      };
    });

class ForecastScreen extends ConsumerStatefulWidget {
  const ForecastScreen({super.key, this.initialPeriod = 'daily'});

  /// daily, weekly, monthly or yearly.
  final String initialPeriod;
  @override
  ConsumerState<ForecastScreen> createState() => _ForecastState();
}

class _ForecastState extends ConsumerState<ForecastScreen> {
  late String period = widget.initialPeriod;
  DateTime date = DateUtils.dateOnly(DateTime.now());
  @override
  Widget build(BuildContext context) {
    final provider = _forecastProvider((period, date));
    final entitlements = ref.watch(entitlementServiceProvider);
    final lockedFeature = switch (period) {
      'monthly' => PremiumFeature.monthlyForecast,
      'yearly' => PremiumFeature.yearlyForecast,
      _ => null,
    };
    final unlockKey = forecastUnlockKey(period, date);
    final language = Localizations.localeOf(context).languageCode;
    final l10n = context.l10n;
    final words = ForecastWords(
      language: language,
      copy: (key) => b12(context, key),
      planet: l10n.planet,
      sign: l10n.sign,
      aspect: l10n.aspect,
    );
    return CorePage(
      title: 'forecasts',
      children: [
        Text(
          b12(context, 'fc_intro'),
          textAlign: TextAlign.center,
          style: AppTypography.bodySmall,
        ),
        AstroSegmentedControl<String>(
          key: const ValueKey('forecast-periods'),
          selected: period,
          segments: [
            for (final p in const ['daily', 'weekly', 'monthly', 'yearly'])
              AstroSegment(value: p, label: b12(context, p)),
          ],
          onChanged: (value) => setState(() => period = value),
        ),
        Center(
          child: TextButton.icon(
            key: const ValueKey('forecast-date'),
            icon: const Icon(Icons.calendar_month_outlined, size: 18),
            onPressed: () async {
              final d = await showDatePicker(
                context: context,
                initialDate: date,
                firstDate: DateTime(1900),
                lastDate: DateTime(2100),
              );
              if (d != null && mounted) setState(() => date = d);
            },
            label: Text(DateFormat('d MMMM y', language).format(date)),
          ),
        ),
        if (lockedFeature != null &&
            !entitlements.canUse(lockedFeature) &&
            !ref.watch(coinUnlocksProvider).containsKey(unlockKey))
          CoinLockCard(unlockKey: unlockKey, feature: lockedFeature)
        else
          ApiStateView(
            value: ref.watch(provider),
            onRetry: () => ref.invalidate(provider),
            builder: (forecast) {
              if (forecast == null) {
                return Text(b12(context, 'demo_unavailable'));
              }
              final digest = ForecastDigest.of(forecast, words);
              if (digest == null) return Text(b12(context, 'empty'));
              return ForecastReadingView(digest: digest, period: period);
            },
          ),
      ],
    );
  }
}
