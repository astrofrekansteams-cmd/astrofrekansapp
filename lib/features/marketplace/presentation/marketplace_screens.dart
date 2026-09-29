import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../../core/localization/b12_copy.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/widgets/widgets.dart';
import '../data/marketplace_models.dart';
import '../data/marketplace_repository.dart';

/// The expert directory: categories, quick filters, sorting and favourites,
/// over the public search (`GET /experts`).
class MarketplaceScreen extends ConsumerStatefulWidget {
  const MarketplaceScreen({super.key, this.specialty, this.deliveryType});

  /// Optional pre-filters, e.g. from the Explore expert shortcuts.
  final String? specialty;
  final String? deliveryType;
  @override
  ConsumerState<MarketplaceScreen> createState() => _MarketplaceState();
}

/// The directory's categories (server `ExpertSpecialty` codes).
const expertCategories = [
  'astrology',
  'natal_chart',
  'synastry',
  'transits',
  'horary',
  'tarot',
  'rune',
  'katina',
];

class _MarketplaceState extends ConsumerState<MarketplaceScreen> {
  late ExpertQuery query = ExpertQuery(
    specialty: widget.specialty,
    deliveryType: widget.deliveryType,
  );
  List<Expert> items = [];
  int total = 0;
  bool loading = false;
  bool favoritesOnly = false;
  Object? error;
  final search = TextEditingController();
  Timer? _searchDebounce;
  final minPrice = TextEditingController(), maxPrice = TextEditingController();
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load(reset: true));
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    search.dispose();
    minPrice.dispose();
    maxPrice.dispose();
    super.dispose();
  }

  Future<void> _load({bool reset = false}) async {
    if (loading) return;
    setState(() {
      loading = true;
      error = null;
      if (reset) {
        items = [];
        total = 0;
      }
    });
    try {
      final repo = ref.read(marketplaceRepositoryProvider);
      if (favoritesOnly) {
        final favorites = await repo.favorites();
        if (!mounted) return;
        setState(() {
          items = favorites;
          total = favorites.length;
        });
        return;
      }
      final page = await repo.search(query.at(reset ? 0 : items.length));
      if (!mounted) return;
      setState(() {
        items = [
          ...{
            for (final item in [...items, ...page.items]) item.id: item,
          }.values,
        ];
        total = page.total;
      });
    } on Object catch (e) {
      if (mounted) setState(() => error = e);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  /// Typing searches the server (all experts, paged), after a short pause
  /// so each keystroke is not a request.
  void _onSearchChanged(String text) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 350), () {
      if (!mounted) return;
      final value = text.trim();
      if ((query.search ?? '') == value) return;
      _filter(query.copy(search: value.isEmpty ? null : value));
    });
  }

  void _filter(ExpertQuery updated) {
    setState(() => query = updated.at(0));
    _load(reset: true);
  }

  Future<void> _toggleFavorite(Expert expert) async {
    try {
      await ref
          .read(marketplaceRepositoryProvider)
          .setFavorite(expert.id, !expert.isFavorite);
      if (!mounted) return;
      setState(() {
        items = [
          for (final e in items)
            if (e.id != expert.id)
              e
            else if (!favoritesOnly || !expert.isFavorite)
              Expert({...e.json, 'is_favorite': !expert.isFavorite}),
        ];
        if (favoritesOnly) total = items.length;
      });
    } on Object catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(friendlyApiError(context, e))));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // Favourites are one complete list (not paged), so a search over them is
    // local; the directory itself is searched on the server.
    final needle = (query.search ?? '').toLowerCase();
    final visible = favoritesOnly && needle.isNotEmpty
        ? items
              .where(
                (e) =>
                    e.name.toLowerCase().contains(needle) ||
                    (e.headline?.toLowerCase().contains(needle) ?? false),
              )
              .toList()
        : items;
    Widget chip(
      String label, {
      required bool selected,
      required ValueChanged<bool> onSelected,
      IconData? icon,
      Key? key,
    }) => Padding(
      padding: const EdgeInsets.only(right: AppSpacing.sm),
      child: FilterChip(
        key: key,
        avatar: icon == null ? null : Icon(icon, size: 16),
        label: Text(label),
        selected: selected,
        onSelected: onSelected,
      ),
    );
    return CorePage(
      title: 'marketplace',
      children: [
        TextField(
          key: const ValueKey('expert-search'),
          controller: search,
          onChanged: _onSearchChanged,
          textInputAction: TextInputAction.search,
          onSubmitted: (text) {
            _searchDebounce?.cancel();
            final value = text.trim();
            _filter(query.copy(search: value.isEmpty ? null : value));
          },
          decoration: InputDecoration(
            prefixIcon: const Icon(Icons.search),
            labelText: b12(context, 'search_experts'),
          ),
        ),
        SingleChildScrollView(
          key: const ValueKey('expert-categories'),
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              chip(
                b12(context, 'all_categories'),
                selected: query.specialty == null,
                onSelected: (_) => _filter(query.copy(specialty: null)),
              ),
              for (final category in expertCategories)
                chip(
                  b12(context, 'specialty_$category'),
                  key: ValueKey('category-$category'),
                  selected: query.specialty == category,
                  onSelected: (on) =>
                      _filter(query.copy(specialty: on ? category : null)),
                ),
            ],
          ),
        ),
        SingleChildScrollView(
          key: const ValueKey('expert-quick-filters'),
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              chip(
                b12(context, 'available_today'),
                key: const ValueKey('filter-available-today'),
                icon: Icons.schedule,
                selected: query.availableToday,
                onSelected: (on) => _filter(query.copy(availableToday: on)),
              ),
              chip(
                b12(context, 'favorites_only'),
                key: const ValueKey('filter-favorites'),
                icon: Icons.favorite_border,
                selected: favoritesOnly,
                onSelected: (on) {
                  setState(() => favoritesOnly = on);
                  _load(reset: true);
                },
              ),
              chip(
                '★ 4.5+',
                key: const ValueKey('filter-rating'),
                selected: query.ratingMin == 4.5,
                onSelected: (on) =>
                    _filter(query.copy(ratingMin: on ? 4.5 : null)),
              ),
              chip(
                b12(context, 'verified_short'),
                icon: Icons.verified_outlined,
                selected: query.verified,
                onSelected: (on) => _filter(query.copy(verified: on)),
              ),
            ],
          ),
        ),
        Row(
          children: [
            Expanded(
              child: Text(
                b12(context, 'experts_count').replaceAll('{n}', '$total'),
                style: AppTypography.labelMedium,
              ),
            ),
            Flexible(
              child: DropdownButton<String>(
                key: const ValueKey('expert-sort'),
                value: query.sort,
                isExpanded: true,
                underline: const SizedBox.shrink(),
                items: [
                  for (final sort in const [
                    'rating',
                    'review_count',
                    'price',
                    'experience',
                    'newest',
                  ])
                    DropdownMenuItem(
                      value: sort,
                      child: Text(b12(context, 'sort_$sort')),
                    ),
                ],
                onChanged: favoritesOnly
                    ? null
                    : (v) {
                        if (v != null) _filter(query.copy(sort: v));
                      },
              ),
            ),
          ],
        ),
        ExpansionTile(
          title: Text(b12(context, 'filters')),
          children: [
            _FilterRow(
              title: b12(context, 'language'),
              values: const ['tr', 'en', 'az'],
              labelOf: (v) => b12(context, 'lang_$v'),
              selected: query.language,
              onSelect: (v) => _filter(query.copy(language: v)),
            ),
            _FilterRow(
              title: b12(context, 'delivery'),
              values: const ['chat', 'voice', 'video', 'written_report'],
              labelOf: (v) => b12(context, 'delivery_$v'),
              selected: query.deliveryType,
              onSelect: (v) => _filter(query.copy(deliveryType: v)),
            ),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: minPrice,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(
                      labelText: '${b12(context, 'price_range')} min',
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: maxPrice,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'max'),
                  ),
                ),
                IconButton(
                  tooltip: b12(context, 'filters'),
                  icon: const Icon(Icons.check),
                  onPressed: () {
                    final min = double.tryParse(minPrice.text);
                    final max = double.tryParse(maxPrice.text);
                    _filter(
                      query.copy(
                        currency: 'TRY',
                        minPriceMinor: min == null ? null : (min * 100).round(),
                        maxPriceMinor: max == null ? null : (max * 100).round(),
                      ),
                    );
                  },
                ),
              ],
            ),
          ],
        ),
        if (error != null)
          AstroCard(
            child: Column(
              children: [
                Text(friendlyApiError(context, error!)),
                TextButton(
                  onPressed: () => _load(reset: items.isEmpty),
                  child: Text(b12(context, 'retry')),
                ),
              ],
            ),
          ),
        if (loading && items.isEmpty)
          const Column(
            children: [
              AstroSkeletonCard(media: true, lines: 2),
              SizedBox(height: AppSpacing.cardGap),
              AstroSkeletonCard(media: true, lines: 2),
            ],
          ),
        if (!loading && error == null && visible.isEmpty)
          AstroEmptyState(
            kind: AstroEmptyStateKind.noData,
            title: b12(context, 'experts_empty'),
          ),
        for (final expert in visible)
          ExpertTile(
            expert: expert,
            onTap: () => context.push(AppRoutes.expertDetail(expert.id)),
            onFavorite: () => _toggleFavorite(expert),
          ),
        if (!favoritesOnly && items.length < total && !loading)
          OutlinedButton(
            onPressed: () => _load(),
            child: Text(b12(context, 'load_more')),
          ),
        if (loading && items.isNotEmpty)
          const AstroSkeletonCard(media: true, lines: 1),
      ],
    );
  }
}

class _FilterRow extends StatelessWidget {
  const _FilterRow({
    required this.title,
    required this.values,
    required this.labelOf,
    required this.selected,
    required this.onSelect,
  });
  final String title;
  final List<String> values;
  final String Function(String) labelOf;
  final String? selected;
  final ValueChanged<String?> onSelect;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(title, style: AppTypography.titleMedium),
      Wrap(
        spacing: 8,
        children: [
          for (final value in values)
            ChoiceChip(
              label: Text(labelOf(value)),
              selected: value == selected,
              onSelected: (_) => onSelect(value == selected ? null : value),
            ),
        ],
      ),
    ],
  );
}

String _specialties(BuildContext context, List<String> codes, [int? take]) =>
    (take == null ? codes : codes.take(take))
        .map((s) => b12(context, 'specialty_$s'))
        .join(' · ');

class ExpertTile extends StatelessWidget {
  const ExpertTile({
    super.key,
    required this.expert,
    required this.onTap,
    this.onFavorite,
  });
  final Expert expert;
  final VoidCallback onTap;
  final VoidCallback? onFavorite;
  @override
  Widget build(BuildContext context) => AstroCard(
    key: ValueKey('expert-tile-${expert.id}'),
    onTap: onTap,
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AstroAvatar(
          size: 60,
          initials: expert.name.isEmpty ? '✦' : expert.name.substring(0, 1),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Flexible(
                    child: Text(
                      expert.name,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: AppTypography.titleLarge,
                    ),
                  ),
                  if (expert.verified)
                    Padding(
                      padding: const EdgeInsets.only(left: 6),
                      child: Semantics(
                        label: b12(context, 'verified'),
                        child: const Icon(
                          Icons.verified,
                          color: AppColors.gold,
                          size: 18,
                        ),
                      ),
                    ),
                ],
              ),
              Text(
                _specialties(context, expert.specialties, 3),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTypography.labelSmall.copyWith(
                  color: AppColors.goldBright,
                ),
              ),
              if (expert.headline != null)
                Text(
                  expert.headline!,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: AppTypography.bodySmall,
                ),
              const SizedBox(height: 4),
              Semantics(
                label:
                    '${b12(context, 'rating')} ${expert.rating.toStringAsFixed(1)}, ${expert.reviewCount} ${b12(context, 'reviews')}',
                child: Wrap(
                  spacing: AppSpacing.sm,
                  children: [
                    Text(
                      '★ ${expert.rating.toStringAsFixed(1)} (${expert.reviewCount})',
                      style: AppTypography.labelMedium,
                    ),
                    Text(
                      expert.languages.map((l) => l.toUpperCase()).join(' · '),
                      style: AppTypography.labelMedium,
                    ),
                    if (expert.fromPrice case final Money price)
                      Text(
                        b12(
                          context,
                          'from_price',
                        ).replaceAll('{price}', price.display),
                        style: AppTypography.labelMedium.copyWith(
                          color: AppColors.goldBright,
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (onFavorite != null)
          IconButton(
            key: ValueKey('favorite-${expert.id}'),
            tooltip: b12(context, 'favorite_toggle'),
            onPressed: onFavorite,
            icon: Icon(
              expert.isFavorite ? Icons.favorite : Icons.favorite_border,
              color: AppColors.gold,
            ),
          )
        else
          const Icon(Icons.chevron_right, color: AppColors.gold),
      ],
    ),
  );
}

/// Open times for one service over the next week.
final _upcomingSlotsProvider = FutureProvider.autoDispose
    .family<SlotPage, (String, String)>((ref, key) {
      final now = DateTime.now();
      return ref
          .watch(marketplaceRepositoryProvider)
          .slots(key.$1, key.$2, now, now.add(const Duration(days: 7)));
    });

class ExpertDetailScreen extends ConsumerStatefulWidget {
  const ExpertDetailScreen({super.key, required this.expertId});
  final String expertId;
  @override
  ConsumerState<ExpertDetailScreen> createState() => _ExpertDetailState();
}

class _ExpertDetailState extends ConsumerState<ExpertDetailScreen> {
  late Future<Expert> detail;
  late Future<ReviewPage> reviews;
  bool? favorite;
  bool changing = false;
  String? serviceId;
  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    detail = ref.read(marketplaceRepositoryProvider).detail(widget.expertId);
    reviews = ref.read(marketplaceRepositoryProvider).reviews(widget.expertId);
  }

  Future<void> _favorite(Expert expert) async {
    final previous = favorite ?? expert.isFavorite;
    setState(() {
      favorite = !previous;
      changing = true;
    });
    try {
      await ref
          .read(marketplaceRepositoryProvider)
          .setFavorite(expert.id, !previous);
    } on Object catch (e) {
      if (mounted) {
        setState(() => favorite = previous);
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(friendlyApiError(context, e))));
      }
    } finally {
      if (mounted) setState(() => changing = false);
    }
  }

  void _book(Expert expert, ExpertService service) => context.push(
    '${AppRoutes.expertDetail(expert.id)}/services/${service.id}/book',
  );

  @override
  Widget build(BuildContext context) => CorePage(
    title: 'expert_detail',
    children: [
      FutureBuilder<Expert>(
        future: detail,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const AstroSkeletonPage();
          }
          if (snapshot.hasError) {
            return AstroCard(
              child: Column(
                children: [
                  Text(friendlyApiError(context, snapshot.error!)),
                  TextButton(
                    onPressed: () => setState(_reload),
                    child: Text(b12(context, 'retry')),
                  ),
                ],
              ),
            );
          }
          final expert = snapshot.requireData;
          final services = expert.services;
          final selected =
              services.where((s) => s.id == serviceId).firstOrNull ??
              services.firstOrNull;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _ExpertHeader(
                expert: expert,
                favorite: favorite ?? expert.isFavorite,
                onFavorite: changing ? null : () => _favorite(expert),
              ),
              if (expert.bio case final String bio when bio.isNotEmpty) ...[
                AstroSectionTitle(title: b12(context, 'about_expert')),
                AstroCard(child: Text(bio, style: AppTypography.bodyMedium)),
              ],
              AstroSectionTitle(title: b12(context, 'specialty')),
              Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.xs,
                children: [
                  for (final s in expert.specialties)
                    AstroBadge(label: b12(context, 'specialty_$s')),
                ],
              ),
              AstroSectionTitle(title: b12(context, 'languages')),
              Wrap(
                spacing: AppSpacing.sm,
                children: [
                  for (final l in expert.languages)
                    AstroBadge(
                      label: b12(context, 'lang_$l'),
                      icon: Icons.translate,
                    ),
                ],
              ),
              AstroSectionTitle(title: b12(context, 'services')),
              if (services.isEmpty)
                AstroCard(child: Text(b12(context, 'expert_no_services')))
              else
                for (final service in services)
                  _ServiceCard(
                    service: service,
                    selected: service.id == selected?.id,
                    onSelect: () => setState(() => serviceId = service.id),
                    onBook: () => _book(expert, service),
                  ),
              if (selected != null) ...[
                AstroSectionTitle(title: b12(context, 'slots')),
                _UpcomingSlots(
                  expertId: expert.id,
                  service: selected,
                  onPick: () => _book(expert, selected),
                ),
                const SizedBox(height: AppSpacing.md),
                AstroButton(
                  key: const ValueKey('book-appointment'),
                  label: b12(context, 'book_appointment'),
                  icon: Icons.event_available,
                  onPressed: () => _book(expert, selected),
                ),
              ],
            ],
          );
        },
      ),
      FutureBuilder<ReviewPage>(
        future: reviews,
        builder: (context, snapshot) {
          if (!snapshot.hasData) return const SizedBox.shrink();
          final page = snapshot.requireData;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              AstroSectionTitle(
                title:
                    '${b12(context, 'reviews')} · ★ ${page.average.toStringAsFixed(1)} (${page.total})',
              ),
              if (page.items.isEmpty)
                AstroCard(child: Text(b12(context, 'reviews_empty')))
              else
                for (final r in page.items)
                  AstroCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '★' * r.rating + '☆' * (5 - r.rating),
                          style: AppTypography.labelLarge.copyWith(
                            color: AppColors.gold,
                          ),
                        ),
                        if (r.comment case final String comment
                            when comment.isNotEmpty)
                          Text(comment, style: AppTypography.bodyMedium),
                      ],
                    ),
                  ),
            ],
          );
        },
      ),
    ],
  );
}

class _ExpertHeader extends StatelessWidget {
  const _ExpertHeader({
    required this.expert,
    required this.favorite,
    required this.onFavorite,
  });
  final Expert expert;
  final bool favorite;
  final VoidCallback? onFavorite;

  @override
  Widget build(BuildContext context) => AstroCard(
    key: const ValueKey('expert-header'),
    borderColor: AppColors.hairlineStrong,
    child: Column(
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            AstroAvatar(
              size: 84,
              initials: expert.name.isEmpty ? '✦' : expert.name.substring(0, 1),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          expert.name,
                          style: AppTypography.headlineMedium,
                        ),
                      ),
                      if (expert.verified)
                        Padding(
                          padding: const EdgeInsets.only(left: 6),
                          child: Semantics(
                            label: b12(context, 'verified'),
                            child: const Icon(
                              Icons.verified,
                              color: AppColors.gold,
                              size: 20,
                            ),
                          ),
                        ),
                    ],
                  ),
                  if (expert.headline != null)
                    Text(expert.headline!, style: AppTypography.bodySmall),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    '★ ${expert.rating.toStringAsFixed(1)} · ${expert.reviewCount} ${b12(context, 'reviews_word')}',
                    style: AppTypography.labelLarge.copyWith(
                      color: AppColors.goldBright,
                    ),
                  ),
                  Text(
                    b12(
                      context,
                      'experience_years',
                    ).replaceAll('{n}', '${expert.experienceYears}'),
                    style: AppTypography.bodySmall,
                  ),
                ],
              ),
            ),
            IconButton(
              key: const ValueKey('expert-favorite'),
              tooltip: b12(context, 'favorite_toggle'),
              onPressed: onFavorite,
              icon: Icon(
                favorite ? Icons.favorite : Icons.favorite_border,
                color: AppColors.gold,
              ),
            ),
          ],
        ),
      ],
    ),
  );
}

class _ServiceCard extends StatelessWidget {
  const _ServiceCard({
    required this.service,
    required this.selected,
    required this.onSelect,
    required this.onBook,
  });
  final ExpertService service;
  final bool selected;
  final VoidCallback onSelect;
  final VoidCallback onBook;

  @override
  Widget build(BuildContext context) => AstroCard(
    key: ValueKey('service-${service.id}'),
    onTap: onSelect,
    borderColor: selected ? AppColors.gold : AppColors.hairline,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(service.title, style: AppTypography.titleMedium),
            ),
            Text(
              service.price.minor == 0
                  ? b12(context, 'free_price')
                  : service.price.display,
              style: AppTypography.titleMedium.copyWith(
                color: AppColors.goldBright,
              ),
            ),
          ],
        ),
        const SizedBox(height: 2),
        Text(
          '${b12(context, 'delivery_${_deliveryWire(service.deliveryType)}')} · ${b12(context, 'minutes').replaceAll('{n}', '${service.durationMinutes}')}',
          style: AppTypography.labelMedium,
        ),
        if (service.description case final String d when d.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: AppSpacing.xs),
            child: Text(d, style: AppTypography.bodySmall),
          ),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton.icon(
            onPressed: onBook,
            icon: const Icon(Icons.event_available, size: 18),
            label: Text(b12(context, 'book_appointment')),
          ),
        ),
      ],
    ),
  );
}

String _deliveryWire(DeliveryType type) => switch (type) {
  DeliveryType.writtenReport => 'written_report',
  DeliveryType.unknown => 'chat',
  _ => type.name,
};

class _UpcomingSlots extends ConsumerWidget {
  const _UpcomingSlots({
    required this.expertId,
    required this.service,
    required this.onPick,
  });
  final String expertId;
  final ExpertService service;
  final VoidCallback onPick;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final key = (expertId, service.id);
    final language = Localizations.localeOf(context).languageCode;
    return ApiStateView<SlotPage>(
      value: ref.watch(_upcomingSlotsProvider(key)),
      onRetry: () => ref.invalidate(_upcomingSlotsProvider(key)),
      loading: const AstroSkeletonCard(lines: 1),
      builder: (page) {
        final slots = page.slots.take(8).toList();
        if (slots.isEmpty) {
          return AstroCard(child: Text(b12(context, 'no_slots_week')));
        }
        final format = DateFormat('EEE d MMM · HH:mm', language);
        return Wrap(
          key: const ValueKey('upcoming-slots'),
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            for (final slot in slots)
              ActionChip(
                avatar: const Icon(Icons.schedule, size: 16),
                label: Text(format.format(slot.startsLocal)),
                onPressed: onPick,
              ),
          ],
        );
      },
    );
  }
}

class FavoriteExpertsScreen extends ConsumerWidget {
  const FavoriteExpertsScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final future = ref.watch(_favoritesProvider);
    return CorePage(
      title: 'favorites',
      children: [
        ApiStateView(
          value: future,
          onRetry: () => ref.invalidate(_favoritesProvider),
          builder: (items) => Column(
            children: [
              if (items.isEmpty) Text(b12(context, 'empty')),
              for (final item in items)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: ExpertTile(
                    expert: item,
                    onTap: () => context.push(AppRoutes.expertDetail(item.id)),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

final _favoritesProvider = FutureProvider.autoDispose(
  (ref) => ref.watch(marketplaceRepositoryProvider).favorites(),
);
