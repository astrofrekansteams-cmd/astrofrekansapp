import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/assets/app_assets.dart';
import '../../../../core/localization/b12_copy.dart';
import '../../../../core/routing/app_routes.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/widgets.dart';
import '../../../marketplace/data/marketplace_models.dart';
import '../../../marketplace/data/marketplace_repository.dart';

/// The best-rated active consultants, for the Explore hub.
final featuredExpertsProvider = FutureProvider.autoDispose<List<Expert>>((
  ref,
) async {
  final page = await ref
      .watch(marketplaceRepositoryProvider)
      .search(const ExpertQuery(sort: 'rating', limit: 6));
  return page.items;
});

/// The user's upcoming appointments, soonest first.
final upcomingAppointmentsProvider =
    FutureProvider.autoDispose<List<Appointment>>((ref) async {
      final items = await ref
          .watch(marketplaceRepositoryProvider)
          .appointments(upcoming: true);
      return [...items]..sort((a, b) => a.startsUtc.compareTo(b.startsUtc));
    });

/// A section title with an optional trailing action.
class HubHeader extends StatelessWidget {
  const HubHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.action,
    this.onAction,
  });
  final String title;
  final String? subtitle;
  final String? action;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.end,
    children: [
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Semantics(
              header: true,
              child: Text(title, style: AppTypography.headlineMedium),
            ),
            if (subtitle != null)
              Text(subtitle!, style: AppTypography.bodySmall),
          ],
        ),
      ),
      if (action != null)
        TextButton(
          onPressed: onAction,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(action!),
              const SizedBox(width: 2),
              const Icon(Icons.chevron_right, size: 18),
            ],
          ),
        ),
    ],
  );
}

// ---------------------------------------------------------------- spreads

class SpreadsSection extends StatelessWidget {
  const SpreadsSection({super.key});

  static const _decks = [
    ('tarot', AppAssets.tarotBack, AppRoutes.tarot),
    ('rune', AppAssets.runeBack, AppRoutes.rune),
    ('katina', AppAssets.katinaBack, AppRoutes.katina),
  ];

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      HubHeader(
        title: b12(context, 'explore_spreads'),
        subtitle: b12(context, 'hub_spreads_sub'),
      ),
      const SizedBox(height: AppSpacing.md),
      Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final (i, (key, asset, route)) in _decks.indexed) ...[
            if (i > 0) const SizedBox(width: AppSpacing.md),
            Expanded(
              child: _DeckTile(titleKey: key, asset: asset, route: route),
            ),
          ],
        ],
      ),
    ],
  );
}

class _DeckTile extends StatelessWidget {
  const _DeckTile({
    required this.titleKey,
    required this.asset,
    required this.route,
  });
  final String titleKey;
  final String asset;
  final String route;

  @override
  Widget build(BuildContext context) {
    final title = b12(context, titleKey);
    return AstroCard(
      key: ValueKey('deck-$titleKey'),
      onTap: () => context.push(route),
      semanticLabel: title,
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.sm,
        AppSpacing.sm,
        AppSpacing.sm,
        AppSpacing.md,
      ),
      child: Column(
        children: [
          AspectRatio(
            aspectRatio: 2 / 3,
            child: DecoratedBox(
              decoration: BoxDecoration(
                borderRadius: AppRadius.brSm,
                boxShadow: [
                  BoxShadow(
                    color: AppColors.gold.withValues(alpha: 0.18),
                    blurRadius: 16,
                  ),
                ],
              ),
              child: ClipRRect(
                borderRadius: AppRadius.brSm,
                child: LayoutBuilder(
                  builder: (context, c) => AstroImage(
                    asset,
                    width: c.maxWidth,
                    height: c.maxHeight,
                    fit: BoxFit.cover,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppTypography.titleMedium,
          ),
          Text(
            b12(context, 'hub_${titleKey}_sub'),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.center,
            style: AppTypography.labelSmall.copyWith(
              color: AppColors.ivoryMuted,
            ),
          ),
        ],
      ),
    );
  }
}

// ------------------------------------------------------------ consultants

class ConsultantsSection extends ConsumerWidget {
  const ConsultantsSection({super.key});

  static const _categories = [
    ('experts_astrologers', 'astrology', Icons.auto_awesome),
    ('experts_tarot', 'tarot', Icons.style_outlined),
    ('experts_rune', 'rune', Icons.hexagon_outlined),
    ('experts_katina', 'katina', Icons.filter_vintage_outlined),
  ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final experts = ref.watch(featuredExpertsProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        HubHeader(
          title: b12(context, 'hub_consultants'),
          subtitle: b12(context, 'hub_consultants_sub'),
          action: b12(context, 'hub_see_all'),
          onAction: () => context.push(AppRoutes.marketplace),
        ),
        const SizedBox(height: AppSpacing.md),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final (key, specialty, icon) in _categories)
                Padding(
                  padding: const EdgeInsets.only(right: AppSpacing.sm),
                  child: AstroChip(
                    label: b12(context, key),
                    leading: Icon(icon, size: 16, color: AppColors.gold),
                    onTap: () => context.push(
                      '${AppRoutes.marketplace}?specialty=$specialty',
                    ),
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        SizedBox(
          height: 232,
          child: experts.when(
            loading: () => ListView(
              scrollDirection: Axis.horizontal,
              children: const [
                SizedBox(width: 220, child: AstroSkeletonCard(lines: 4)),
                SizedBox(width: AppSpacing.md),
                SizedBox(width: 220, child: AstroSkeletonCard(lines: 4)),
              ],
            ),
            error: (_, _) =>
                _EmptyExperts(message: b12(context, 'hub_consultants_error')),
            data: (items) => items.isEmpty
                ? _EmptyExperts(message: b12(context, 'hub_consultants_empty'))
                : ListView.separated(
                    key: const ValueKey('featured-experts'),
                    scrollDirection: Axis.horizontal,
                    itemCount: items.length,
                    separatorBuilder: (_, _) =>
                        const SizedBox(width: AppSpacing.md),
                    itemBuilder: (context, i) =>
                        ConsultantCard(expert: items[i]),
                  ),
          ),
        ),
      ],
    );
  }
}

class _EmptyExperts extends StatelessWidget {
  const _EmptyExperts({required this.message});
  final String message;
  @override
  Widget build(BuildContext context) => AstroCard(
    child: Center(
      child: Text(
        message,
        textAlign: TextAlign.center,
        style: AppTypography.bodySmall,
      ),
    ),
  );
}

/// A featured consultant: avatar, name, speciality, short bio, rating and
/// starting price.
class ConsultantCard extends StatelessWidget {
  const ConsultantCard({super.key, required this.expert});
  final Expert expert;

  @override
  Widget build(BuildContext context) {
    final specialties = expert.specialties
        .take(2)
        .map((s) => b12(context, 'specialty_$s'))
        .join(' · ');
    final about = expert.headline ?? expert.bio ?? '';
    return SizedBox(
      width: 220,
      child: AstroCard(
        key: ValueKey('expert-${expert.id}'),
        onTap: () => context.push('${AppRoutes.marketplace}/${expert.id}'),
        semanticLabel: expert.name,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                AstroAvatar(
                  size: 48,
                  initials: expert.name.isEmpty
                      ? '✦'
                      : expert.name.substring(0, 1),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              expert.name,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTypography.titleMedium,
                            ),
                          ),
                          if (expert.verified) ...[
                            const SizedBox(width: 4),
                            const Icon(
                              Icons.verified,
                              size: 14,
                              color: AppColors.gold,
                            ),
                          ],
                        ],
                      ),
                      Text(
                        specialties,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTypography.labelSmall.copyWith(
                          color: AppColors.goldBright,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            Expanded(
              child: Text(
                about,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: AppTypography.bodySmall,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            Row(
              children: [
                const Icon(Icons.star_rounded, size: 16, color: AppColors.gold),
                const SizedBox(width: 2),
                Text(
                  expert.reviewCount == 0
                      ? b12(context, 'hub_new_expert')
                      : '${expert.rating.toStringAsFixed(1)} (${expert.reviewCount})',
                  style: AppTypography.labelMedium,
                ),
                const SizedBox(width: AppSpacing.sm),
                if (expert.fromPrice case final Money price)
                  Expanded(
                    child: Text(
                      b12(
                        context,
                        'hub_from_price',
                      ).replaceAll('{price}', price.display),
                      maxLines: 1,
                      textAlign: TextAlign.end,
                      overflow: TextOverflow.ellipsis,
                      style: AppTypography.labelMedium.copyWith(
                        color: AppColors.goldBright,
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------- service types

class ServiceTypesSection extends StatelessWidget {
  const ServiceTypesSection({super.key});

  static const _types = [
    ('chat', Icons.chat_bubble_outline),
    ('voice', Icons.call_outlined),
    ('video', Icons.videocam_outlined),
    ('written_report', Icons.description_outlined),
  ];

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      HubHeader(
        title: b12(context, 'hub_services'),
        subtitle: b12(context, 'hub_services_sub'),
      ),
      const SizedBox(height: AppSpacing.md),
      LayoutBuilder(
        builder: (context, c) {
          final width = (c.maxWidth - AppSpacing.md) / 2;
          return Wrap(
            spacing: AppSpacing.md,
            runSpacing: AppSpacing.md,
            children: [
              for (final (type, icon) in _types)
                SizedBox(
                  width: width,
                  child: _ServiceTile(type: type, icon: icon),
                ),
            ],
          );
        },
      ),
    ],
  );
}

class _ServiceTile extends StatelessWidget {
  const _ServiceTile({required this.type, required this.icon});
  final String type;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final title = b12(context, 'hub_service_$type');
    return AstroCard(
      key: ValueKey('service-$type'),
      onTap: () => context.push('${AppRoutes.marketplace}?delivery=$type'),
      semanticLabel: title,
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppColors.gold.withValues(alpha: 0.12),
              border: Border.all(color: AppColors.hairlineStrong),
            ),
            child: Icon(icon, color: AppColors.gold, size: 20),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppTypography.titleMedium,
          ),
          Text(
            b12(context, 'hub_service_${type}_sub'),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: AppTypography.bodySmall,
          ),
        ],
      ),
    );
  }
}

// ----------------------------------------------------------- appointments

class AppointmentsEntry extends ConsumerWidget {
  const AppointmentsEntry({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final upcoming = ref.watch(upcomingAppointmentsProvider).asData?.value;
    final next = upcoming == null || upcoming.isEmpty ? null : upcoming.first;
    final locale = Localizations.localeOf(context).toLanguageTag();
    return AstroCard(
      key: const ValueKey('appointments-entry'),
      onTap: () => context.push(AppRoutes.appointments),
      semanticLabel: b12(context, 'hub_appointments'),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              borderRadius: AppRadius.brMd,
              color: AppColors.gold.withValues(alpha: 0.12),
              border: Border.all(color: AppColors.hairlineStrong),
            ),
            child: const Icon(
              Icons.event_available_outlined,
              color: AppColors.gold,
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  b12(context, 'hub_appointments'),
                  style: AppTypography.titleMedium,
                ),
                Text(
                  next == null
                      ? b12(context, 'hub_appointments_none')
                      : b12(context, 'hub_appointments_next')
                            .replaceAll(
                              '{when}',
                              _when(next.startsLocal, locale),
                            )
                            .replaceAll('{count}', '${upcoming!.length}'),
                  style: AppTypography.bodySmall,
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right, color: AppColors.gold),
        ],
      ),
    );
  }

  static String _when(DateTime local, String locale) {
    String two(int v) => v.toString().padLeft(2, '0');
    return '${two(local.day)}.${two(local.month)} ${two(local.hour)}:${two(local.minute)}';
  }
}
