import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../../billing/presentation/order_payment_section.dart';
import '../data/marketplace_models.dart';
import '../data/marketplace_repository.dart';

String localInstant(DateTime utc) =>
    DateFormat('dd.MM.yyyy HH:mm').format(utc.toLocal());

/// "UTC+03:00 (+03)": the offset the times on screen are shown in.
String timezoneLabel(DateTime local) {
  final offset = local.timeZoneOffset;
  final sign = offset.isNegative ? '-' : '+';
  final hours = offset.inHours.abs().toString().padLeft(2, '0');
  final minutes = (offset.inMinutes.abs() % 60).toString().padLeft(2, '0');
  final name = local.timeZoneName;
  return name.isEmpty
      ? 'UTC$sign$hours:$minutes'
      : 'UTC$sign$hours:$minutes ($name)';
}

String lifecycleLabel(BuildContext context, OrderLifecycle lifecycle) =>
    b12(context, switch (lifecycle) {
      OrderLifecycle.pending => 'lifecycle_pending',
      OrderLifecycle.paid => 'lifecycle_paid',
      OrderLifecycle.scheduled => 'lifecycle_scheduled',
      OrderLifecycle.awaitingCompletion => 'lifecycle_awaiting_completion',
      OrderLifecycle.completed => 'lifecycle_completed',
      OrderLifecycle.cancelled => 'lifecycle_cancelled',
      OrderLifecycle.refundReview => 'lifecycle_refund_review',
      OrderLifecycle.refunded => 'lifecycle_refunded',
      OrderLifecycle.unknown => 'lifecycle_unknown',
    });

String paymentStatusLabel(BuildContext context, String status) {
  const known = {
    'not_required',
    'pending',
    'authorized',
    'paid',
    'failed',
    'refund_pending',
    'refunded',
    'partially_refunded',
  };
  return known.contains(status)
      ? b12(context, 'payment_status_$status')
      : b12(context, 'lifecycle_unknown');
}

String appointmentStatusLabel(BuildContext context, AppointmentStatus status) =>
    b12(context, switch (status) {
      AppointmentStatus.pending => 'appointment_status_pending',
      AppointmentStatus.confirmed => 'appointment_status_confirmed',
      AppointmentStatus.completed => 'appointment_status_completed',
      AppointmentStatus.cancelled => 'appointment_status_cancelled',
      AppointmentStatus.noShow => 'appointment_status_no_show',
      AppointmentStatus.unknown => 'lifecycle_unknown',
    });

String refundLabel(BuildContext context, OrderRefund refund) =>
    b12(context, switch (refund.state) {
      RefundState.review => 'refund_status_review',
      RefundState.refunded => 'refund_status_refunded',
      RefundState.denied => 'refund_status_denied',
      RefundState.failed => 'refund_status_failed',
      RefundState.unknown => 'lifecycle_unknown',
    });

// Shared read models. Every screen that shows an order or an appointment reads
// these, so one refresh after a payment, cancellation or completion updates
// them all together.
final ordersListProvider = FutureProvider.autoDispose.family<List<Order>, bool>(
  (ref, expert) =>
      ref.watch(marketplaceRepositoryProvider).orders(expert: expert),
);
final appointmentsListProvider = FutureProvider.autoDispose
    .family<List<Appointment>, bool>(
      (ref, expert) =>
          ref.watch(marketplaceRepositoryProvider).appointments(expert: expert),
    );
final orderDetailProvider = FutureProvider.autoDispose
    .family<Order, (String, bool)>(
      (ref, key) => ref
          .watch(marketplaceRepositoryProvider)
          .order(key.$1, expert: key.$2),
    );
final appointmentDetailProvider = FutureProvider.autoDispose
    .family<Appointment, String>(
      (ref, id) => ref.watch(marketplaceRepositoryProvider).appointment(id),
    );

/// Re-read orders, appointments and payment together. A payment, a
/// cancellation or a completion changes all of them at once on the server.
void refreshServiceViews(WidgetRef ref) {
  ref.invalidate(orderDetailProvider);
  ref.invalidate(ordersListProvider);
  ref.invalidate(appointmentsListProvider);
  ref.invalidate(appointmentDetailProvider);
  ref.invalidate(orderPaymentProvider);
}

class _Row extends StatelessWidget {
  const _Row(this.label, this.value);
  final String label, value;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 110,
          child: Text(
            label,
            style: const TextStyle(color: AppColors.ivoryMuted),
          ),
        ),
        Expanded(child: Text(value)),
      ],
    ),
  );
}

/// Last look before a booking is placed: the exact day, time and zone.
Future<bool> confirmBooking(
  BuildContext context, {
  required DateTime startsUtc,
  required DateTime endsUtc,
  required String service,
  required String? expert,
}) async {
  final local = startsUtc.toLocal();
  final result = await showDialog<bool>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      key: const ValueKey('booking-confirm-dialog'),
      title: Text(b12(dialogContext, 'booking_confirm_title')),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _Row(
            b12(dialogContext, 'booking_date'),
            DateFormat(
              'dd.MM.yyyy · EEEE',
              Localizations.localeOf(dialogContext).toLanguageTag(),
            ).format(local),
          ),
          _Row(
            b12(dialogContext, 'booking_time'),
            '${DateFormat.Hm().format(local)}–'
            '${DateFormat.Hm().format(endsUtc.toLocal())}',
          ),
          _Row(b12(dialogContext, 'booking_timezone'), timezoneLabel(local)),
          _Row(b12(dialogContext, 'booking_expert'), expert ?? '—'),
          _Row(b12(dialogContext, 'booking_service'), service),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(dialogContext, false),
          child: Text(b12(dialogContext, 'cancel_keep')),
        ),
        FilledButton(
          key: const ValueKey('booking-confirm-yes'),
          onPressed: () => Navigator.pop(dialogContext, true),
          child: Text(b12(dialogContext, 'booking_confirm')),
        ),
      ],
    ),
  );
  return result == true;
}

String cancellationOutcomeText(
  BuildContext context,
  CancellationPreview? preview,
) {
  if (preview == null) return b12(context, 'cancel_not_paid');
  return switch (preview.outcome) {
    RefundOutcome.refundReview => b12(
      context,
      'cancel_refund_review',
    ).replaceAll('{amount}', preview.refundable.display),
    RefundOutcome.free => b12(context, 'cancel_free'),
    _ => b12(context, 'cancel_not_paid'),
  };
}

/// Before any cancellation: what is cancelled, when, and what happens to the
/// money - as the server previewed it.
Future<bool> confirmCancellation(
  BuildContext context, {
  required String service,
  DateTime? startsUtc,
  CancellationPreview? preview,
}) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      key: const ValueKey('cancel-confirm-dialog'),
      title: Text(b12(dialogContext, 'cancel_confirm_title')),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _Row(b12(dialogContext, 'booking_service'), service),
          if (startsUtc != null) ...[
            _Row(b12(dialogContext, 'booking_date'), localInstant(startsUtc)),
            _Row(
              b12(dialogContext, 'booking_timezone'),
              timezoneLabel(startsUtc.toLocal()),
            ),
          ],
          const SizedBox(height: 8),
          Text(
            cancellationOutcomeText(dialogContext, preview),
            key: const ValueKey('cancel-refund-outcome'),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(dialogContext, false),
          child: Text(b12(dialogContext, 'cancel_keep')),
        ),
        FilledButton(
          key: const ValueKey('cancel-confirm-yes'),
          style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
          onPressed: () => Navigator.pop(dialogContext, true),
          child: Text(b12(dialogContext, 'cancel_confirm')),
        ),
      ],
    ),
  );
  return result == true;
}

void _showError(BuildContext context, Object error) {
  if (!context.mounted) return;
  ScaffoldMessenger.of(
    context,
  ).showSnackBar(SnackBar(content: Text(friendlyApiError(context, error))));
}

class BookingScreen extends ConsumerStatefulWidget {
  const BookingScreen({
    super.key,
    required this.expertId,
    required this.serviceId,
  });
  final String expertId, serviceId;
  @override
  ConsumerState<BookingScreen> createState() => _BookingState();
}

class _BookingState extends ConsumerState<BookingScreen> {
  late Future<ExpertService> service;
  late final Future<String?> expertName = _expertName();
  Future<SlotPage>? slots;
  DateTime date = DateUtils.dateOnly(DateTime.now());
  ExpertSlot? selected;
  BookingIntent? intent;
  Order? created;
  Object? error;
  bool busy = false;
  @override
  void initState() {
    super.initState();
    service = _service();
    _reloadSlots();
  }

  Future<ExpertService> _service() async =>
      (await ref.read(marketplaceRepositoryProvider).services(widget.expertId))
          .firstWhere((s) => s.id == widget.serviceId);

  Future<String?> _expertName() async {
    try {
      return (await ref
              .read(marketplaceRepositoryProvider)
              .detail(widget.expertId))
          .name;
    } on Object {
      return null; // The confirmation still shows day, time and zone.
    }
  }

  void _reloadSlots() {
    final from = DateTime.now().toUtc();
    slots = ref
        .read(marketplaceRepositoryProvider)
        .slots(
          widget.expertId,
          widget.serviceId,
          from,
          from.add(const Duration(days: 14)),
        );
  }

  /// A new day is a new choice: the old slot and its pending request go, so
  /// nothing from the previous day can be submitted.
  void _changeDate(DateTime day) => setState(() {
    date = DateUtils.dateOnly(day);
    selected = null;
    intent = null;
    error = null;
  });

  bool get _selectionOnDate =>
      selected != null && DateUtils.isSameDay(selected!.startsLocal, date);

  Future<void> _book(ExpertService offering) async {
    if (offering.supportsAppointment) {
      final slot = selected;
      if (slot == null || !_selectionOnDate) {
        // Defence in depth: the button is disabled in this state.
        setState(() {
          selected = null;
          intent = null;
        });
        return;
      }
      final expert = await expertName;
      if (!mounted) return;
      final confirmed = await confirmBooking(
        context,
        startsUtc: slot.startsUtc,
        endsUtc: slot.endsUtc,
        service: offering.title,
        expert: expert,
      );
      if (!confirmed || !mounted) return;
    }
    final current = intent ??= BookingIntent(
      serviceId: offering.id,
      startsUtc: selected?.startsUtc,
      selectedLocalDate: offering.supportsAppointment ? date : null,
    );
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final order = await ref
          .read(marketplaceRepositoryProvider)
          .createOrder(current);
      if (mounted) {
        setState(() => created = order);
        refreshServiceViews(ref);
      }
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => error = e);
        if (const {
          'slot_unavailable',
          'slot_not_offered',
          'slot_date_mismatch',
        }.contains(e.code)) {
          setState(() {
            selected = null;
            intent = null;
            _reloadSlots();
          });
        }
      }
    } on Object catch (e) {
      if (mounted) setState(() => error = e);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => CorePage(
    title: 'booking',
    children: [
      FutureBuilder<ExpertService>(
        future: service,
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            return snapshot.hasError
                ? Text(friendlyApiError(context, snapshot.error!))
                : const AstroSkeletonPage();
          }
          final offering = snapshot.requireData;
          return Column(
            children: [
              AstroCard(
                child: ListTile(
                  title: Text(offering.title),
                  subtitle: Text(
                    '${offering.price.display} · ${offering.durationMinutes} min · ${offering.deliveryType.name}\n${offering.description ?? ''}',
                  ),
                ),
              ),
              if (offering.supportsAppointment) ...[
                TextButton.icon(
                  key: const ValueKey('booking-date'),
                  onPressed: () =>
                      showDatePicker(
                        context: context,
                        initialDate: date,
                        firstDate: DateUtils.dateOnly(DateTime.now()),
                        lastDate: DateUtils.dateOnly(
                          DateTime.now().add(const Duration(days: 14)),
                        ),
                      ).then((d) {
                        if (d != null && mounted) _changeDate(d);
                      }),
                  icon: const Icon(Icons.calendar_month),
                  label: Text(
                    DateFormat.yMMMd(
                      Localizations.localeOf(context).toLanguageTag(),
                    ).format(date),
                  ),
                ),
                FutureBuilder<SlotPage>(
                  future: slots,
                  builder: (context, slotSnapshot) {
                    if (slotSnapshot.connectionState != ConnectionState.done) {
                      return const AstroSkeletonCard(lines: 2);
                    }
                    if (slotSnapshot.hasError) {
                      return Text(
                        friendlyApiError(context, slotSnapshot.error!),
                      );
                    }
                    final available = slotSnapshot.requireData.slots
                        .where((s) => DateUtils.isSameDay(s.startsLocal, date))
                        .toList();
                    return Column(
                      children: [
                        Text(
                          '${b12(context, 'slots')} · ${timezoneLabel(date)}',
                        ),
                        if (available.isEmpty) Text(b12(context, 'empty')),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            for (final slot in available)
                              ChoiceChip(
                                label: Text(
                                  DateFormat.Hm().format(slot.startsLocal),
                                ),
                                selected: selected?.startsUtc == slot.startsUtc,
                                onSelected: (_) => setState(() {
                                  selected = slot;
                                  intent = null;
                                }),
                              ),
                          ],
                        ),
                        if (available.isNotEmpty && !_selectionOnDate)
                          Text(b12(context, 'booking_pick_time')),
                      ],
                    );
                  },
                ),
              ],
              if (error != null)
                AstroCard(child: Text(friendlyApiError(context, error!))),
              if (created == null)
                FilledButton(
                  key: const ValueKey('booking-submit'),
                  onPressed:
                      busy ||
                          (offering.supportsAppointment && !_selectionOnDate)
                      ? null
                      : () => _book(offering),
                  child: Text(b12(context, 'booking')),
                ),
              if (created != null)
                AstroCard(
                  child: Column(
                    children: [
                      Text(lifecycleLabel(context, created!.lifecycle)),
                      if (created!.status == OrderStatus.pendingPayment)
                        Text(b12(context, 'payment_required')),
                      TextButton(
                        onPressed: () =>
                            context.push(AppRoutes.orderDetail(created!.id)),
                        child: Text(b12(context, 'order_detail')),
                      ),
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

class OrdersScreen extends ConsumerWidget {
  const OrdersScreen({super.key, this.expert = false});
  final bool expert;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final provider = ordersListProvider(expert);
    return CorePage(
      title: expert ? 'expert_workspace' : 'orders',
      children: [
        ApiStateView(
          value: ref.watch(provider),
          onRetry: () => ref.invalidate(provider),
          builder: (orders) => Column(
            children: [
              if (orders.isEmpty) Text(b12(context, 'empty')),
              for (final o in orders)
                AstroCard(
                  onTap: () => context.push(
                    expert
                        ? '${AppRoutes.expertWorkspace}/orders/${o.id}'
                        : AppRoutes.orderDetail(o.id),
                  ),
                  child: ListTile(
                    title: Text(o.title ?? o.serviceCode),
                    subtitle: Text(
                      '${o.expertName ?? ''} · ${o.total.display}',
                    ),
                    trailing: Chip(
                      label: Text(lifecycleLabel(context, o.lifecycle)),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class OrderDetailScreen extends ConsumerWidget {
  const OrderDetailScreen({super.key, required this.id, this.expert = false});
  final String id;
  final bool expert;

  Future<void> _cancel(BuildContext context, WidgetRef ref, Order order) async {
    final appointment = order.appointment;
    final confirmed = await confirmCancellation(
      context,
      service: order.title ?? order.serviceCode,
      startsUtc: appointment?.startsUtc,
      preview: order.cancellation,
    );
    if (!confirmed) return;
    try {
      final repository = ref.read(marketplaceRepositoryProvider);
      if (expert) {
        // An expert cancels the session; the server cancels the order with it.
        await repository.cancelAppointment(appointment!.id, expert: true);
      } else {
        await repository.cancelOrder(order.id);
      }
      refreshServiceViews(ref);
    } on Object catch (e) {
      if (context.mounted) _showError(context, e);
    }
  }

  Future<void> _complete(
    BuildContext context,
    WidgetRef ref,
    Order order,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        content: Text(b12(dialogContext, 'complete_confirm')),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: Text(b12(dialogContext, 'cancel_keep')),
          ),
          FilledButton(
            key: const ValueKey('complete-confirm-yes'),
            onPressed: () => Navigator.pop(dialogContext, true),
            child: Text(b12(dialogContext, 'complete_action')),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref
          .read(marketplaceRepositoryProvider)
          .completeOrder(order.id, expert: expert);
      refreshServiceViews(ref);
    } on Object catch (e) {
      if (context.mounted) _showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final provider = orderDetailProvider((id, expert));
    return CorePage(
      title: 'order_detail',
      children: [
        ApiStateView(
          value: ref.watch(provider),
          onRetry: () => ref.invalidate(provider),
          builder: (order) {
            final appointment = order.appointment;
            final call =
                order.expertId != null &&
                (order.deliveryType == DeliveryType.voice ||
                    order.deliveryType == DeliveryType.video) &&
                !const [
                  OrderStatus.pendingPayment,
                  OrderStatus.completed,
                  OrderStatus.cancelled,
                  OrderStatus.refunded,
                  OrderStatus.failed,
                ].contains(order.status);
            final justPaid =
                !expert &&
                order.paymentStatus == 'paid' &&
                const [
                  OrderLifecycle.paid,
                  OrderLifecycle.scheduled,
                  OrderLifecycle.awaitingCompletion,
                ].contains(order.lifecycle);
            return Column(
              children: [
                AstroCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(order.title ?? order.serviceCode),
                      const SizedBox(height: 8),
                      Chip(
                        key: const ValueKey('order-lifecycle'),
                        label: Text(lifecycleLabel(context, order.lifecycle)),
                      ),
                      _Row(
                        b12(context, 'order_payment'),
                        paymentStatusLabel(context, order.paymentStatus),
                      ),
                      _Row(b12(context, 'order_total'), order.total.display),
                      if (order.expertName != null)
                        _Row(b12(context, 'booking_expert'), order.expertName!),
                      if (appointment != null) ...[
                        _Row(
                          b12(context, 'booking_date'),
                          localInstant(appointment.startsUtc),
                        ),
                        _Row(
                          b12(context, 'booking_timezone'),
                          timezoneLabel(appointment.startsUtc.toLocal()),
                        ),
                      ],
                    ],
                  ),
                ),
                if (!expert && order.status == OrderStatus.pendingPayment)
                  OrderPaymentSection(
                    orderId: id,
                    onRefresh: () => refreshServiceViews(ref),
                  ),
                if (justPaid)
                  AstroCard(
                    key: const ValueKey('payment-confirmed'),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(b12(context, 'payment_confirmed')),
                        if (call)
                          FilledButton.icon(
                            key: const ValueKey('go-to-call'),
                            onPressed: () =>
                                context.push(AppRoutes.orderCall(id)),
                            icon: const Icon(Icons.call_outlined),
                            label: Text(b12(context, 'go_to_call')),
                          )
                        else if (appointment != null)
                          FilledButton(
                            key: const ValueKey('view-appointment'),
                            onPressed: () => context.push(
                              AppRoutes.appointmentDetail(appointment.id),
                            ),
                            child: Text(b12(context, 'view_appointment')),
                          ),
                      ],
                    ),
                  ),
                if (order.refund case final refund?)
                  AstroCard(
                    key: const ValueKey('refund-card'),
                    child: ListTile(
                      title: Text(b12(context, 'refund_title')),
                      subtitle: Text(
                        '${refundLabel(context, refund)} · ${refund.amount.display}',
                      ),
                    ),
                  ),
                if (order.delivery case final delivery?)
                  AstroCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(b12(context, 'delivery_title')),
                        const SizedBox(height: 8),
                        SelectableText(delivery.note),
                      ],
                    ),
                  ),
                if (expert && order.actions.canDeliver)
                  _DeliverForm(orderId: id),
                if (order.actions.canComplete)
                  FilledButton(
                    key: const ValueKey('complete-order'),
                    onPressed: () => _complete(context, ref, order),
                    child: Text(b12(context, 'complete_action')),
                  )
                else if (order.completionBlock == 'session_not_started')
                  Text(b12(context, 'complete_waiting')),
                if (!expert && order.expertId != null)
                  OutlinedButton(
                    onPressed: () =>
                        context.push('${AppRoutes.orderDetail(id)}/consent'),
                    child: Text(b12(context, 'consent')),
                  ),
                if (!expert &&
                    order.expertId != null &&
                    order.status != OrderStatus.pendingPayment)
                  OutlinedButton(
                    onPressed: () =>
                        context.push('${AppRoutes.orderDetail(id)}/chat'),
                    child: Text(b12(context, 'consultations')),
                  ),
                if (call && !justPaid)
                  OutlinedButton.icon(
                    onPressed: () => context.push(AppRoutes.orderCall(id)),
                    icon: const Icon(Icons.call_outlined),
                    label: Text(b12(context, 'go_to_call')),
                  ),
                if (!expert && order.reviewEligible && order.expertId != null)
                  ReviewForm(orderId: id, expertId: order.expertId!),
                if (order.timeline.isNotEmpty) _Timeline(order.timeline),
                if (order.actions.canCancel && (!expert || appointment != null))
                  OutlinedButton(
                    key: const ValueKey('cancel-order'),
                    onPressed: () => _cancel(context, ref, order),
                    child: Text(b12(context, 'cancel_booking')),
                  ),
              ],
            );
          },
        ),
      ],
    );
  }
}

class _Timeline extends StatelessWidget {
  const _Timeline(this.events);
  final List<OrderTimelineEvent> events;
  @override
  Widget build(BuildContext context) => AstroCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(b12(context, 'timeline')),
        for (final event in events)
          _Row(localInstant(event.at), b12(context, 'timeline_${event.event}')),
      ],
    ),
  );
}

/// Expert only: hand over a written analysis. Delivering completes the order.
class _DeliverForm extends ConsumerStatefulWidget {
  const _DeliverForm({required this.orderId});
  final String orderId;
  @override
  ConsumerState<_DeliverForm> createState() => _DeliverFormState();
}

class _DeliverFormState extends ConsumerState<_DeliverForm> {
  final note = TextEditingController();
  bool busy = false;

  @override
  void dispose() {
    note.dispose();
    super.dispose();
  }

  Future<void> _deliver() async {
    final text = note.text.trim();
    if (text.isEmpty) return;
    setState(() => busy = true);
    try {
      await ref
          .read(marketplaceRepositoryProvider)
          .deliverOrder(widget.orderId, text);
      refreshServiceViews(ref);
    } on Object catch (e) {
      if (mounted) _showError(context, e);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AstroCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(b12(context, 'deliver_title')),
        TextField(
          key: const ValueKey('deliver-note'),
          controller: note,
          maxLines: 8,
          maxLength: 20000,
          decoration: InputDecoration(labelText: b12(context, 'deliver_hint')),
        ),
        FilledButton(
          key: const ValueKey('deliver-submit'),
          onPressed: busy ? null : _deliver,
          child: Text(b12(context, 'deliver_action')),
        ),
      ],
    ),
  );
}

class ReviewForm extends ConsumerStatefulWidget {
  const ReviewForm({super.key, required this.orderId, required this.expertId});
  final String orderId, expertId;
  @override
  ConsumerState<ReviewForm> createState() => _ReviewFormState();
}

class _ReviewFormState extends ConsumerState<ReviewForm> {
  int rating = 5;
  bool busy = false, submitted = false, initialized = false;
  ExpertReview? existing;
  late final Future<ExpertReview?> initial;
  final comment = TextEditingController();
  @override
  void initState() {
    super.initState();
    initial = _findReview();
  }

  Future<ExpertReview?> _findReview() async {
    final repository = ref.read(marketplaceRepositoryProvider);
    var offset = 0;
    while (true) {
      final page = await repository.reviews(
        widget.expertId,
        limit: 100,
        offset: offset,
      );
      for (final review in page.items) {
        if (review.orderId == widget.orderId) return review;
      }
      offset += page.items.length;
      if (page.items.isEmpty || offset >= page.total) return null;
    }
  }

  Future<void> _save() async {
    setState(() => busy = true);
    try {
      final repository = ref.read(marketplaceRepositoryProvider);
      final value = comment.text.trim().isEmpty ? null : comment.text.trim();
      final saved = existing == null
          ? await repository.createReview(widget.orderId, rating, value)
          : await repository.updateReview(existing!.id, rating, value);
      if (mounted) {
        setState(() {
          existing = saved;
          submitted = true;
        });
      }
    } on Object catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(friendlyApiError(context, e))));
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _delete() async {
    final review = existing;
    if (review == null) return;
    setState(() => busy = true);
    try {
      await ref.read(marketplaceRepositoryProvider).deleteReview(review.id);
      if (mounted) {
        setState(() {
          existing = null;
          submitted = true;
        });
      }
    } on Object catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(friendlyApiError(context, e))));
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    comment.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<ExpertReview?>(
    future: initial,
    builder: (context, snapshot) {
      if (snapshot.connectionState != ConnectionState.done) {
        return const AstroSkeletonCard(lines: 2);
      }
      if (snapshot.hasError) {
        return Text(friendlyApiError(context, snapshot.error!));
      }
      if (!initialized) {
        existing = snapshot.data;
        rating = existing?.rating ?? 5;
        comment.text = existing?.comment ?? '';
        initialized = true;
      }
      return AstroCard(
        child: Column(
          children: [
            Text(b12(context, 'review_eligible')),
            if (submitted) Text(b12(context, 'saved')),
            Wrap(
              children: [
                for (var i = 1; i <= 5; i++)
                  IconButton(
                    tooltip: '$i ${b12(context, 'rating')}',
                    onPressed: () => setState(() => rating = i),
                    icon: Icon(
                      i <= rating ? Icons.star : Icons.star_border,
                      color: AppColors.gold,
                    ),
                  ),
              ],
            ),
            TextField(
              controller: comment,
              maxLength: 2000,
              maxLines: 3,
              decoration: InputDecoration(labelText: b12(context, 'message')),
            ),
            FilledButton(
              onPressed: busy ? null : _save,
              child: Text(b12(context, 'save')),
            ),
            if (existing != null)
              TextButton(
                onPressed: busy ? null : _delete,
                child: Text(b12(context, 'delete')),
              ),
          ],
        ),
      );
    },
  );
}

enum AppointmentFilter { upcoming, past, cancelled }

/// Upcoming: still live and not yet over, soonest first. Past: over or
/// delivered, latest first. Cancelled: cancelled, latest first.
List<Appointment> filterAppointments(
  List<Appointment> items,
  AppointmentFilter filter, {
  DateTime? now,
}) {
  final moment = (now ?? DateTime.now()).toUtc();
  bool upcoming(Appointment a) => a.isLive && a.endsUtc.isAfter(moment);
  final result = items
      .where(
        (a) => switch (filter) {
          AppointmentFilter.upcoming => upcoming(a),
          AppointmentFilter.cancelled =>
            a.status == AppointmentStatus.cancelled,
          AppointmentFilter.past =>
            a.status != AppointmentStatus.cancelled && !upcoming(a),
        },
      )
      .toList();
  result.sort(
    (a, b) => filter == AppointmentFilter.upcoming
        ? a.startsUtc.compareTo(b.startsUtc)
        : b.startsUtc.compareTo(a.startsUtc),
  );
  return result;
}

class AppointmentsScreen extends ConsumerStatefulWidget {
  const AppointmentsScreen({super.key, this.expert = false});
  final bool expert;
  @override
  ConsumerState<AppointmentsScreen> createState() => _AppointmentsState();
}

class _AppointmentsState extends ConsumerState<AppointmentsScreen> {
  AppointmentFilter filter = AppointmentFilter.upcoming;

  @override
  Widget build(BuildContext context) {
    final provider = appointmentsListProvider(widget.expert);
    return CorePage(
      title: 'appointments',
      children: [
        SegmentedButton<AppointmentFilter>(
          showSelectedIcon: false,
          segments: [
            ButtonSegment(
              value: AppointmentFilter.upcoming,
              label: Text(
                b12(context, 'filter_upcoming'),
                key: const ValueKey('filter-upcoming'),
              ),
            ),
            ButtonSegment(
              value: AppointmentFilter.past,
              label: Text(
                b12(context, 'filter_past'),
                key: const ValueKey('filter-past'),
              ),
            ),
            ButtonSegment(
              value: AppointmentFilter.cancelled,
              label: Text(
                b12(context, 'filter_cancelled'),
                key: const ValueKey('filter-cancelled'),
              ),
            ),
          ],
          selected: {filter},
          onSelectionChanged: (value) => setState(() => filter = value.single),
        ),
        const SizedBox(height: 12),
        ApiStateView(
          value: ref.watch(provider),
          onRetry: () => ref.invalidate(provider),
          builder: (all) {
            final items = filterAppointments(all, filter);
            return Column(
              children: [
                if (items.isEmpty) Text(b12(context, 'empty')),
                for (final a in items)
                  AstroCard(
                    onTap: () => context.push(
                      widget.expert
                          ? '${AppRoutes.expertWorkspace}/appointments/${a.id}'
                          : AppRoutes.appointmentDetail(a.id),
                    ),
                    child: ListTile(
                      title: Text(localInstant(a.startsUtc)),
                      subtitle: Text(
                        '${timezoneLabel(a.startsUtc.toLocal())} · '
                        '${appointmentStatusLabel(context, a.status)}',
                      ),
                      trailing: const Icon(Icons.chevron_right),
                    ),
                  ),
              ],
            );
          },
        ),
      ],
    );
  }
}

/// Appointment facts plus, when it belongs to an order, that order's state:
/// what cancelling would mean for money, and any refund in progress.
class _AppointmentPanel extends ConsumerWidget {
  const _AppointmentPanel({required this.appointment, required this.expert});
  final Appointment appointment;
  final bool expert;

  Future<void> _cancel(
    BuildContext context,
    WidgetRef ref,
    Order? order,
  ) async {
    final confirmed = await confirmCancellation(
      context,
      service:
          order?.title ??
          order?.serviceCode ??
          b12(context, 'appointment_detail'),
      startsUtc: appointment.startsUtc,
      preview: order?.cancellation,
    );
    if (!confirmed) return;
    try {
      await ref
          .read(marketplaceRepositoryProvider)
          .cancelAppointment(appointment.id, expert: expert);
      refreshServiceViews(ref);
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(b12(context, 'cancel_done'))));
      }
    } on Object catch (e) {
      if (context.mounted) _showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final orderId = appointment.orderId;
    final orderValue = orderId == null
        ? null
        : ref.watch(orderDetailProvider((orderId, expert)));
    final order = orderValue?.asData?.value;
    return Column(
      children: [
        AstroCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (order != null) Text(order.title ?? order.serviceCode),
              _Row(
                b12(context, 'booking_date'),
                localInstant(appointment.startsUtc),
              ),
              _Row(
                b12(context, 'booking_time'),
                '${DateFormat.Hm().format(appointment.startsUtc.toLocal())}–'
                '${DateFormat.Hm().format(appointment.endsUtc.toLocal())}',
              ),
              _Row(
                b12(context, 'booking_timezone'),
                timezoneLabel(appointment.startsUtc.toLocal()),
              ),
              Chip(
                key: const ValueKey('appointment-status'),
                label: Text(
                  order != null
                      ? lifecycleLabel(context, order.lifecycle)
                      : appointmentStatusLabel(context, appointment.status),
                ),
              ),
            ],
          ),
        ),
        if (order?.refund case final refund?)
          AstroCard(
            key: const ValueKey('refund-card'),
            child: ListTile(
              title: Text(b12(context, 'refund_title')),
              subtitle: Text(
                '${refundLabel(context, refund)} · ${refund.amount.display}',
              ),
            ),
          ),
        if (orderId != null)
          TextButton(
            onPressed: () => context.push(
              expert
                  ? '${AppRoutes.expertWorkspace}/orders/$orderId'
                  : AppRoutes.orderDetail(orderId),
            ),
            child: Text(b12(context, 'open_order')),
          ),
        if (appointment.isLive)
          OutlinedButton(
            key: const ValueKey('cancel-appointment'),
            // Wait for the order's preview before offering the action, so the
            // confirmation always says what happens to the money.
            onPressed: orderValue != null && orderValue.isLoading
                ? null
                : () => _cancel(context, ref, order),
            child: Text(b12(context, 'cancel_booking')),
          ),
      ],
    );
  }
}

class AppointmentDetailScreen extends ConsumerWidget {
  const AppointmentDetailScreen({super.key, required this.id});
  final String id;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final provider = appointmentDetailProvider(id);
    return CorePage(
      title: 'appointment_detail',
      children: [
        ApiStateView(
          value: ref.watch(provider),
          onRetry: () => ref.invalidate(provider),
          builder: (a) => _AppointmentPanel(appointment: a, expert: false),
        ),
      ],
    );
  }
}

class ExpertAppointmentDetailScreen extends ConsumerWidget {
  const ExpertAppointmentDetailScreen({super.key, required this.id});
  final String id;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final provider = appointmentsListProvider(true);
    return CorePage(
      title: 'appointment_detail',
      children: [
        ApiStateView(
          value: ref.watch(provider),
          onRetry: () => ref.invalidate(provider),
          builder: (items) {
            final matching = items.where((item) => item.id == id);
            if (matching.isEmpty) return Text(b12(context, 'empty'));
            return _AppointmentPanel(
              appointment: matching.single,
              expert: true,
            );
          },
        ),
      ],
    );
  }
}

class OrderConsentScreen extends ConsumerStatefulWidget {
  const OrderConsentScreen({super.key, required this.orderId});
  final String orderId;
  @override
  ConsumerState<OrderConsentScreen> createState() => _ConsentState();
}

class _ConsentState extends ConsumerState<OrderConsentScreen> {
  late Future<List<OrderConsent>> initial;
  Set<String>? selected;
  bool saving = false;
  @override
  void initState() {
    super.initState();
    initial = ref.read(marketplaceRepositoryProvider).consents(widget.orderId);
  }

  @override
  Widget build(BuildContext context) => CorePage(
    title: 'consent',
    children: [
      Text(b12(context, 'consent_note')),
      FutureBuilder<List<OrderConsent>>(
        future: initial,
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            return snapshot.hasError
                ? Text(friendlyApiError(context, snapshot.error!))
                : const AstroSkeletonCard(lines: 3);
          }
          selected ??= {
            for (final c in snapshot.requireData)
              if (c.active) c.scope,
          };
          return Column(
            children: [
              for (final scope in consentScopes)
                CheckboxListTile(
                  title: Text(
                    scope.replaceFirst('share_', '').replaceAll('_', ' '),
                  ),
                  value: selected!.contains(scope),
                  onChanged: saving
                      ? null
                      : (value) => setState(() {
                          if (value == true) {
                            selected!.add(scope);
                          } else {
                            selected!.remove(scope);
                          }
                        }),
                ),
              FilledButton(
                onPressed: saving
                    ? null
                    : () async {
                        setState(() => saving = true);
                        try {
                          final saved = await ref
                              .read(marketplaceRepositoryProvider)
                              .setConsents(widget.orderId, selected!);
                          if (mounted) {
                            setState(
                              () => selected = {
                                for (final c in saved)
                                  if (c.active) c.scope,
                              },
                            );
                          }
                        } on Object catch (e) {
                          if (context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(friendlyApiError(context, e)),
                              ),
                            );
                          }
                        } finally {
                          if (mounted) setState(() => saving = false);
                        }
                      },
                child: Text(b12(context, 'save')),
              ),
            ],
          );
        },
      ),
    ],
  );
}
