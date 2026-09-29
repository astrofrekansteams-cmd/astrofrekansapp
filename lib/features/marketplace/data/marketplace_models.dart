import '../../../core/astrology/data/api_contract_dto.dart';
import '../../../core/astrology/data/production_models.dart';

enum ExpertStatus {
  draft,
  pendingReview,
  active,
  paused,
  suspended,
  inactive,
  unknown,
}

enum ExpertSpecialty {
  astrology,
  natalChart,
  transits,
  synastry,
  composite,
  davison,
  horary,
  monthlyForecast,
  annualForecast,
  tarot,
  rune,
  katina,
  unknown,
}

enum DeliveryType { chat, voice, video, writtenReport, unknown }

enum OrderStatus {
  draft,
  pendingPayment,
  paid,
  confirmed,
  pending,
  calculating,
  generating,
  awaitingExpert,
  inProgress,
  completed,
  cancelled,
  refunded,
  failed,
  unknown,
}

/// One answer to "where is my order?", derived by the server from the stored
/// order, payment, appointment and refund facts (never computed here).
enum OrderLifecycle {
  pending,
  paid,
  scheduled,
  awaitingCompletion,
  completed,
  cancelled,
  refundReview,
  refunded,
  unknown,
}

enum AppointmentStatus {
  pending,
  confirmed,
  completed,
  cancelled,
  noShow,
  unknown,
}

T wireEnum<T extends Enum>(List<T> values, String? raw, T fallback) =>
    ContractJson.bySnakeOr(values, raw ?? '', fallback);

class Money extends ContractRecord {
  Money(super.value) {
    number('amount_minor');
    text('currency');
  }
  int get minor => json['amount_minor'] as int;
  String get currency => text('currency');
  String get display => '${(minor / 100).toStringAsFixed(2)} $currency';
}

class Expert extends ContractRecord {
  Expert(super.value) {
    text('id');
    text('display_name');
  }
  String get id => text('id');
  String get name => text('display_name');
  String? get headline => optionalText('headline');
  String? get avatarKey => optionalText('avatar_key');
  String? get bio => optionalText('bio');
  String? get timezone => optionalText('timezone');
  ExpertStatus get status => wireEnum(
    ExpertStatus.values,
    optionalText('status'),
    ExpertStatus.unknown,
  );
  List<String> get languages => strings('languages');
  List<String> get specialties => strings('specialties');
  List<ExpertSpecialty> get typedSpecialties => specialties
      .map((s) => wireEnum(ExpertSpecialty.values, s, ExpertSpecialty.unknown))
      .toList(growable: false);
  int get experienceYears => json['experience_years'] as int;
  bool get verified => json['verified'] as bool;
  double get rating => number('rating_average');
  int get reviewCount => json['rating_count'] as int;
  bool get isFavorite => json['is_favorite'] == true;
  Money? get fromPrice => json['from_price'] == null
      ? null
      : Money(ContractJson.map(json['from_price']));
  List<ExpertService> get services => ContractJson.maps(
    json['services'] ?? [],
  ).map(ExpertService.new).toList(growable: false);
  Map<String, int> get ratingDistribution =>
      Map<String, int>.from(json['rating_distribution'] as Map? ?? {});
}

class ExpertPage extends ContractRecord {
  ExpertPage(super.value) {
    number('total');
  }
  int get total => json['total'] as int;
  int get limit => json['limit'] as int;
  int get offset => json['offset'] as int;
  List<Expert> get items =>
      ContractJson.maps(json['items']).map(Expert.new).toList(growable: false);
  bool get hasMore => offset + items.length < total;
}

class ExpertService extends ContractRecord {
  ExpertService(super.value) {
    text('id');
    text('service_code');
    text('title');
    record('price');
  }
  String get id => text('id');
  String get expertId => text('expert_id');
  String get serviceCode => text('service_code');
  String get title => text('title');
  String? get description => optionalText('description');
  DeliveryType get deliveryType => wireEnum(
    DeliveryType.values,
    optionalText('delivery_type'),
    DeliveryType.unknown,
  );
  int get durationMinutes => json['duration_minutes'] as int;
  Money get price => Money(ContractJson.map(json['price']));
  bool get supportsChat => json['supports_chat'] == true;
  bool get supportsVoice => json['supports_voice'] == true;
  bool get supportsVideo => json['supports_video'] == true;
  bool get supportsAppointment => json['supports_appointment'] == true;
  bool get requiresBirthData => json['requires_birth_data'] == true;
  bool get requiresPartnerData => json['requires_partner_data'] == true;
  bool get requiresQuestion => json['requires_question'] == true;
}

class ExpertSlot extends ContractRecord {
  ExpertSlot(super.value) {
    text('starts_at_utc');
    text('ends_at_utc');
  }
  DateTime get startsUtc => ContractJson.date(json, 'starts_at_utc').toUtc();
  DateTime get endsUtc => ContractJson.date(json, 'ends_at_utc').toUtc();
  DateTime get startsLocal => startsUtc.toLocal();
  DateTime get endsLocal => endsUtc.toLocal();
  String get displayTimezone => text('display_timezone');
}

class SlotPage extends ContractRecord {
  SlotPage(super.value) {
    text('expert_service_id');
  }
  List<ExpertSlot> get slots => ContractJson.maps(
    json['slots'],
  ).map(ExpertSlot.new).toList(growable: false);
  String get displayTimezone => text('display_timezone');
}

class Order extends ContractRecord {
  Order(super.value) {
    text('id');
    text('status');
    text('payment_status');
    record('total');
  }
  String get id => text('id');
  String get serviceCode => text('service_code');
  String? get title => optionalText('service_title');
  OrderStatus get status =>
      wireEnum(OrderStatus.values, text('status'), OrderStatus.unknown);
  String get paymentStatus => text('payment_status');
  DeliveryType get deliveryType => wireEnum(
    DeliveryType.values,
    optionalText('delivery_type'),
    DeliveryType.unknown,
  );
  Money get total => Money(ContractJson.map(json['total']));
  String? get expertId => optionalText('expert_id');
  String? get expertName => optionalText('expert_display_name');
  Appointment? get appointment => json['appointment'] == null
      ? null
      : Appointment(ContractJson.map(json['appointment']));
  DateTime? get appointmentStartsUtc =>
      ContractJson.optionalDate(json, 'appointment_starts_at_utc')?.toUtc();
  List<String> get grantedScopes => strings('granted_consent_scopes');
  OrderLifecycle get lifecycle => wireEnum(
    OrderLifecycle.values,
    optionalText('lifecycle'),
    OrderLifecycle.unknown,
  );
  OrderActions get actions =>
      OrderActions(ContractJson.map(json['actions'] ?? <String, dynamic>{}));
  String? get completionBlock => optionalText('completion_block');
  OrderRefund? get refund => json['refund'] == null
      ? null
      : OrderRefund(ContractJson.map(json['refund']));
  CancellationPreview? get cancellation => json['cancellation'] == null
      ? null
      : CancellationPreview(ContractJson.map(json['cancellation']));
  OrderDelivery? get delivery => json['delivery'] == null
      ? null
      : OrderDelivery(ContractJson.map(json['delivery']));
  List<OrderTimelineEvent> get timeline => ContractJson.maps(
    json['timeline'] ?? [],
  ).map(OrderTimelineEvent.new).toList(growable: false);
  bool get isLive =>
      deliveryType == DeliveryType.chat ||
      deliveryType == DeliveryType.voice ||
      deliveryType == DeliveryType.video;

  /// The server's answer when it gave one; older responses fall back to the
  /// status it is derived from.
  bool get reviewEligible => json['actions'] == null
      ? status == OrderStatus.completed && expertId != null
      : actions.reviewEligible;
}

/// What the caller may do now. The server refuses anything not offered here.
class OrderActions extends ContractRecord {
  OrderActions(super.value);
  bool get canCancel => json['can_cancel'] == true;
  bool get canComplete => json['can_complete'] == true;
  bool get canDeliver => json['can_deliver'] == true;
  bool get reviewEligible => json['review_eligible'] == true;
}

enum RefundState { review, refunded, denied, failed, unknown }

class OrderRefund extends ContractRecord {
  OrderRefund(super.value) {
    text('status');
  }
  String get rawStatus => text('status');
  RefundState get state => switch (rawStatus) {
    'requested' ||
    'manual_review' ||
    'approved' ||
    'processing' => RefundState.review,
    'refunded' => RefundState.refunded,
    'denied' => RefundState.denied,
    'failed' => RefundState.failed,
    _ => RefundState.unknown,
  };
  Money get amount => Money({
    'amount_minor': json['amount_minor'] as int,
    'currency': text('currency'),
  });
}

enum RefundOutcome { refundReview, notPaid, free, none, unknown }

/// What cancelling now would mean for money - shown before confirming.
class CancellationPreview extends ContractRecord {
  CancellationPreview(super.value);
  bool get allowed => json['allowed'] == true;
  RefundOutcome get outcome => wireEnum(
    RefundOutcome.values,
    optionalText('refund_outcome'),
    RefundOutcome.unknown,
  );
  Money get refundable => Money({
    'amount_minor': json['refundable_minor'] as int? ?? 0,
    'currency': optionalText('currency') ?? '',
  });
}

class OrderDelivery extends ContractRecord {
  OrderDelivery(super.value) {
    text('note');
  }
  String get note => text('note');
  DateTime? get deliveredAt =>
      ContractJson.optionalDate(json, 'delivered_at')?.toUtc();
}

class OrderTimelineEvent extends ContractRecord {
  OrderTimelineEvent(super.value) {
    text('event');
    text('at');
  }
  String get event => text('event');
  DateTime get at => ContractJson.date(json, 'at').toUtc();
}

class Appointment extends ContractRecord {
  Appointment(super.value) {
    text('id');
    text('starts_at_utc');
    text('status');
  }
  String get id => text('id');
  String get expertId => text('expert_id');
  String get serviceId => text('expert_service_id');
  String? get orderId => optionalText('service_order_id');
  DateTime get startsUtc => ContractJson.date(json, 'starts_at_utc').toUtc();
  DateTime get endsUtc => ContractJson.date(json, 'ends_at_utc').toUtc();
  DateTime get startsLocal => startsUtc.toLocal();
  String get timezone => text('timezone');
  bool get isLive =>
      status == AppointmentStatus.pending ||
      status == AppointmentStatus.confirmed;
  AppointmentStatus get status => wireEnum(
    AppointmentStatus.values,
    text('status'),
    AppointmentStatus.unknown,
  );
}

const consentScopes = <String>[
  'share_birth_profile',
  'share_natal_chart',
  'share_partner_profile',
  'share_synastry',
  'share_horary',
  'share_forecast',
  'share_divination_reading',
  'share_previous_readings',
];

class OrderConsent extends ContractRecord {
  OrderConsent(super.value) {
    text('scope');
  }
  String get scope => text('scope');
  bool get active => json['active'] == true;
}

class ExpertReview extends ContractRecord {
  ExpertReview(super.value) {
    text('id');
    number('rating');
  }
  String get id => text('id');
  String get orderId => text('order_id');
  int get rating => json['rating'] as int;
  String? get comment => optionalText('comment');
}

class ReviewPage extends ContractRecord {
  ReviewPage(super.value) {
    number('total');
  }
  List<ExpertReview> get items => ContractJson.maps(
    json['items'],
  ).map(ExpertReview.new).toList(growable: false);
  int get total => json['total'] as int;
  double get average => number('rating_average');
}

/// Weekly local wall-clock hours remain in the expert's IANA timezone.
class AvailabilityWindow extends ContractRecord {
  AvailabilityWindow(super.value) {
    text('id');
    number('weekday');
    text('start_local_time');
    text('end_local_time');
    text('timezone');
  }
  String get id => text('id');
  int get weekday => json['weekday'] as int;
  String get startLocalTime => text('start_local_time');
  String get endLocalTime => text('end_local_time');
  String get timezone => text('timezone');
  bool get active => json['active'] == true;
}

class AvailabilityException extends ContractRecord {
  AvailabilityException(super.value) {
    text('id');
    text('exception_type');
    text('starts_at_utc');
    text('ends_at_utc');
  }
  String get id => text('id');
  String get type => text('exception_type');
  DateTime get startsUtc => ContractJson.date(json, 'starts_at_utc').toUtc();
  DateTime get endsUtc => ContractJson.date(json, 'ends_at_utc').toUtc();
  String? get reason => optionalText('reason');
}
