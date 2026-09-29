import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/localization/b12_copy.dart';
import '../../../core/routing/notification_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../data/notification_repository.dart';

IconData _icon(NotificationCategory category) => switch (category) {
  NotificationCategory.astroAi => Icons.auto_awesome_outlined,
  NotificationCategory.appointment => Icons.event_available_outlined,
  NotificationCategory.expertMessage => Icons.chat_bubble_outline,
  NotificationCategory.payment => Icons.receipt_long_outlined,
  NotificationCategory.system => Icons.info_outline,
  NotificationCategory.promotion => Icons.local_offer_outlined,
};

const _knownEvents = {
  'appointment_booked',
  'appointment_cancelled',
  'appointment_reminder',
  'order_status_changed',
  'call_missed',
  'new_chat_message',
  'payment_succeeded',
  'payment_failed',
  'refund_processed',
  'subscription_renewed',
  'subscription_expired',
  'ai_report_ready',
  'daily_content',
  'promotion',
};

String notificationTitle(BuildContext context, InboxNotification item) {
  if (!_knownEvents.contains(item.event)) {
    return b12(context, 'notif_title_generic');
  }
  final title = b12(context, 'notif_title_${item.event}');
  final minutes = int.tryParse(item.data['minutes_before'] ?? '');
  if (item.event != 'appointment_reminder' || minutes == null) return title;
  // 1440 -> "24 saat", 60 -> "1 saat", 15 -> "15 dk".
  final left = minutes >= 60 && minutes % 60 == 0
      ? b12(context, 'notif_hours_before').replaceAll('{n}', '${minutes ~/ 60}')
      : b12(context, 'notif_minutes_before').replaceAll('{n}', '$minutes');
  return '$title · $left';
}

/// Where a notification leads: the same answer as a tapped push.
String? notificationRoute(InboxNotification item) =>
    routeForNotification(item.event, item.data);

class NotificationCenterScreen extends ConsumerStatefulWidget {
  const NotificationCenterScreen({super.key});
  @override
  ConsumerState<NotificationCenterScreen> createState() =>
      _NotificationCenterState();
}

class _NotificationCenterState extends ConsumerState<NotificationCenterScreen> {
  final List<InboxNotification> items = [];
  NotificationCategory? category;
  String? nextBefore;
  bool loading = false;
  Object? error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load(reset: true));
  }

  Future<void> _load({bool reset = false}) async {
    if (loading) return;
    setState(() {
      loading = true;
      error = null;
      if (reset) {
        items.clear();
        nextBefore = null;
      }
    });
    try {
      final page = await ref
          .read(notificationRepositoryProvider)
          .list(before: reset ? null : nextBefore, category: category);
      if (!mounted) return;
      setState(() {
        items.addAll(page.items);
        nextBefore = page.nextBefore;
      });
    } on Object catch (e) {
      if (mounted) setState(() => error = e);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void _replace(InboxNotification updated) {
    final index = items.indexWhere((item) => item.id == updated.id);
    if (index >= 0) setState(() => items[index] = updated);
    ref.invalidate(unreadNotificationsProvider);
  }

  Future<void> _setRead(InboxNotification item, bool read) async {
    // Moves at once; goes back if the server does not save it.
    _replace(item.withRead(read));
    try {
      _replace(
        await ref
            .read(notificationRepositoryProvider)
            .setRead(item.id, read: read),
      );
    } on Object catch (e) {
      _replace(item);
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(friendlyApiError(context, e))));
      }
    }
  }

  Future<void> _open(InboxNotification item) async {
    if (!item.read) await _setRead(item, true);
    final route = notificationRoute(item);
    if (route != null && mounted) await context.push(route);
  }

  Future<void> _readAll() async {
    try {
      await ref.read(notificationRepositoryProvider).readAll();
      if (!mounted) return;
      setState(() {
        for (var i = 0; i < items.length; i++) {
          items[i] = items[i].withRead(true);
        }
      });
      ref.invalidate(unreadNotificationsProvider);
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
    final language = Localizations.localeOf(context).toLanguageTag();
    final anyUnread = items.any((item) => !item.read);
    return CorePage(
      title: 'notifications_title',
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                b12(context, 'inbox_intro'),
                style: AppTypography.bodySmall,
              ),
            ),
            TextButton.icon(
              key: const ValueKey('notifications-read-all'),
              onPressed: anyUnread ? _readAll : null,
              icon: const Icon(Icons.done_all, size: 18),
              label: Text(b12(context, 'notifications_read_all')),
            ),
          ],
        ),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final option in <NotificationCategory?>[
                null,
                ...NotificationCategory.values,
              ])
                Padding(
                  padding: const EdgeInsets.only(right: AppSpacing.sm),
                  child: ChoiceChip(
                    key: ValueKey('notif-filter-${option?.wire ?? 'all'}'),
                    label: Text(
                      option == null
                          ? b12(context, 'all_categories')
                          : b12(context, 'notif_cat_${option.wire}'),
                    ),
                    selected: category == option,
                    onSelected: (_) {
                      setState(() => category = option);
                      _load(reset: true);
                    },
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        if (error != null && items.isEmpty)
          AstroErrorCard(
            message: friendlyApiError(context, error!),
            onRetry: () => _load(reset: true),
          )
        else if (loading && items.isEmpty)
          const AstroSkeletonCard(lines: 3)
        else if (items.isEmpty)
          AstroCard(
            key: const ValueKey('notifications-empty'),
            child: Text(b12(context, 'notifications_empty')),
          ),
        for (final item in items)
          AstroCard(
            key: ValueKey('notification-${item.id}'),
            onTap: () => _open(item),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(_icon(item.category), color: AppColors.gold),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        notificationTitle(context, item),
                        style: AppTypography.titleMedium.copyWith(
                          fontWeight: item.read
                              ? FontWeight.w400
                              : FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '${b12(context, 'notif_cat_${item.category.wire}')} · '
                        '${DateFormat('d MMM y, HH:mm', language).format(item.createdAt)}',
                        style: AppTypography.bodySmall,
                      ),
                    ],
                  ),
                ),
                if (!item.read)
                  Container(
                    key: ValueKey('unread-${item.id}'),
                    width: 9,
                    height: 9,
                    margin: const EdgeInsets.only(top: 6, right: 4),
                    decoration: const BoxDecoration(
                      color: AppColors.goldBright,
                      shape: BoxShape.circle,
                    ),
                  ),
                IconButton(
                  key: ValueKey('toggle-read-${item.id}'),
                  tooltip: b12(
                    context,
                    item.read
                        ? 'notifications_mark_unread'
                        : 'notifications_mark_read',
                  ),
                  icon: Icon(
                    item.read
                        ? Icons.mark_email_unread_outlined
                        : Icons.mark_email_read_outlined,
                    size: 20,
                  ),
                  onPressed: () => _setRead(item, !item.read),
                ),
              ],
            ),
          ),
        if (nextBefore != null)
          TextButton(
            onPressed: loading ? null : () => _load(),
            child: Text(b12(context, 'load_more')),
          ),
      ],
    );
  }
}
