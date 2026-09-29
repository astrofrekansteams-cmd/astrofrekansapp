import 'dart:math';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/astrology/data/production_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../../core/network/api_exception.dart';
import '../../auth/application/session_controller.dart';
import 'marketplace_models.dart';

class ExpertQuery {
  const ExpertQuery({
    this.search,
    this.specialty,
    this.language,
    this.serviceCode,
    this.deliveryType,
    this.minPriceMinor,
    this.maxPriceMinor,
    this.currency,
    this.verified = false,
    this.ratingMin,
    this.availableToday = false,
    this.sort = 'rating',
    this.limit = 20,
    this.offset = 0,
  });

  /// Free text (`q`): name, headline, bio and specialty names, searched by
  /// the server across every expert - not just the loaded page.
  final String? search,
      specialty,
      language,
      serviceCode,
      deliveryType,
      currency,
      sort;
  final int? minPriceMinor, maxPriceMinor;
  final double? ratingMin;
  final bool verified;

  /// Has open hours today (the server's `available_today`). Live presence is
  /// private to a conversation, so the directory filters on the schedule.
  final bool availableToday;
  final int limit, offset;
  Map<String, dynamic> get query => {
    if (search != null && search!.trim().isNotEmpty) 'q': search!.trim(),
    if (specialty != null && specialty!.isNotEmpty) 'specialty': specialty,
    if (language != null && language!.isNotEmpty) 'language': language,
    if (serviceCode != null && serviceCode!.isNotEmpty)
      'service_code': serviceCode,
    if (deliveryType != null && deliveryType!.isNotEmpty)
      'delivery_type': deliveryType,
    if (minPriceMinor != null) 'min_price_minor': minPriceMinor,
    if (maxPriceMinor != null) 'max_price_minor': maxPriceMinor,
    if (currency != null && currency!.isNotEmpty) 'currency': currency,
    if (verified) 'verified': true,
    if (ratingMin != null) 'rating_min': ratingMin,
    if (availableToday) 'available_today': true,
    'sort': sort,
    'limit': limit,
    'offset': offset,
  };
  static const Object _keep = Object();

  /// A copy with some filters changed; pass `null` to clear one.
  ExpertQuery copy({
    Object? specialty = _keep,
    Object? language = _keep,
    Object? deliveryType = _keep,
    Object? currency = _keep,
    Object? minPriceMinor = _keep,
    Object? maxPriceMinor = _keep,
    Object? ratingMin = _keep,
    bool? verified,
    bool? availableToday,
    String? sort,
    Object? search = _keep,
  }) => ExpertQuery(
    search: identical(search, _keep) ? this.search : search as String?,
    specialty: identical(specialty, _keep)
        ? this.specialty
        : specialty as String?,
    language: identical(language, _keep) ? this.language : language as String?,
    serviceCode: serviceCode,
    deliveryType: identical(deliveryType, _keep)
        ? this.deliveryType
        : deliveryType as String?,
    minPriceMinor: identical(minPriceMinor, _keep)
        ? this.minPriceMinor
        : minPriceMinor as int?,
    maxPriceMinor: identical(maxPriceMinor, _keep)
        ? this.maxPriceMinor
        : maxPriceMinor as int?,
    currency: identical(currency, _keep) ? this.currency : currency as String?,
    verified: verified ?? this.verified,
    ratingMin: identical(ratingMin, _keep)
        ? this.ratingMin
        : ratingMin as double?,
    availableToday: availableToday ?? this.availableToday,
    sort: sort ?? this.sort,
    limit: limit,
    offset: offset,
  );

  ExpertQuery at(int newOffset) => ExpertQuery(
    search: search,
    specialty: specialty,
    language: language,
    serviceCode: serviceCode,
    deliveryType: deliveryType,
    minPriceMinor: minPriceMinor,
    maxPriceMinor: maxPriceMinor,
    currency: currency,
    verified: verified,
    ratingMin: ratingMin,
    availableToday: availableToday,
    sort: sort,
    limit: limit,
    offset: newOffset,
  );
}

/// Immutable intentional booking. Retry retains both payload and idempotency key.
class BookingIntent {
  BookingIntent({
    required this.serviceId,
    this.startsUtc,
    this.displayTimezone,
    this.notes,
    this.selectedLocalDate,
    List<Json> sources = const [],
    String? idempotencyKey,
  }) : sources = List<Json>.unmodifiable(sources),
       idempotencyKey = idempotencyKey ?? newClientId();
  final String serviceId, idempotencyKey;
  final DateTime? startsUtc;
  final String? displayTimezone, notes;
  final List<Json> sources;

  /// The calendar day the person was looking at when they chose the slot.
  /// Sent with the slot's UTC offset so the server refuses a slot that is
  /// not on that day (`slot_date_mismatch`) instead of booking it.
  final DateTime? selectedLocalDate;

  Json get payload => {
    'expert_service_id': serviceId,
    if (startsUtc != null)
      'starts_at_utc': startsUtc!.toUtc().toIso8601String(),
    if (displayTimezone != null) 'display_timezone': displayTimezone,
    'sources': sources,
    if (notes != null) 'notes': notes,
    if (startsUtc != null && selectedLocalDate != null) ...{
      'selected_local_date': _day(selectedLocalDate!),
      'selected_utc_offset_minutes': startsUtc!
          .toLocal()
          .timeZoneOffset
          .inMinutes,
    },
  };
  static String _day(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-'
      '${d.month.toString().padLeft(2, '0')}-'
      '${d.day.toString().padLeft(2, '0')}';
}

String newClientId() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  final hex = bytes.map((v) => v.toRadixString(16).padLeft(2, '0')).join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}

abstract interface class MarketplaceRepository {
  Future<ExpertPage> search(ExpertQuery query);
  Future<Expert> detail(String id);
  Future<List<ExpertService>> services(String id);
  Future<ReviewPage> reviews(String id, {int limit = 20, int offset = 0});
  Future<List<Expert>> favorites();
  Future<void> setFavorite(String id, bool value);
  Future<SlotPage> slots(
    String expertId,
    String serviceId,
    DateTime from,
    DateTime to,
  );
  Future<Order> createOrder(BookingIntent intent);
  Future<List<Order>> orders({bool expert = false});
  Future<Order> order(String id, {bool expert = false});
  Future<Order> cancelOrder(String id);

  /// A live session that has begun: either party confirms it took place.
  Future<Order> completeOrder(String id, {bool expert = false});

  /// The expert hands over a written analysis; that completes the order.
  Future<Order> deliverOrder(String id, String note);
  Future<List<Appointment>> appointments({
    bool expert = false,
    bool upcoming = false,
  });
  Future<Appointment> appointment(String id);
  Future<Appointment> cancelAppointment(String id, {bool expert = false});
  Future<List<OrderConsent>> consents(String orderId);
  Future<List<OrderConsent>> setConsents(String orderId, Set<String> scopes);
  Future<ExpertReview> createReview(
    String orderId,
    int rating,
    String? comment,
  );
  Future<ExpertReview> updateReview(
    String reviewId,
    int rating,
    String? comment,
  );
  Future<void> deleteReview(String reviewId);
  Future<Expert> ownProfile();
  Future<Expert> updateOwnProfile(Json patch);
  Future<ExpertService> createOwnService(Json data);
  Future<ExpertService> updateOwnService(String id, Json data);
  Future<ExpertService> deactivateOwnService(String id);
  Future<List<AvailabilityWindow>> ownAvailability();
  Future<AvailabilityWindow> addOwnAvailability(Json data);
  Future<void> removeOwnAvailability(String id);
  Future<List<AvailabilityException>> ownExceptions();
  Future<AvailabilityException> addOwnException(Json data);
  Future<void> removeOwnException(String id);
}

class ApiMarketplaceRepository implements MarketplaceRepository {
  const ApiMarketplaceRepository(this.api);
  final ApiClient api;
  String _id(String id) => Uri.encodeComponent(id);
  @override
  Future<ExpertPage> search(ExpertQuery query) async =>
      ExpertPage(await api.getMap('experts', queryParameters: query.query));
  @override
  Future<Expert> detail(String id) async =>
      Expert(await api.getMap('experts/${_id(id)}'));
  @override
  Future<List<ExpertService>> services(String id) async => (await api.getList(
    'experts/${_id(id)}/services',
  )).map(ExpertService.new).toList();
  @override
  Future<ReviewPage> reviews(
    String id, {
    int limit = 20,
    int offset = 0,
  }) async => ReviewPage(
    await api.getMap(
      'experts/${_id(id)}/reviews',
      queryParameters: {'limit': limit, 'offset': offset},
    ),
  );
  @override
  Future<List<Expert>> favorites() async =>
      (await api.getList('favorites/experts')).map(Expert.new).toList();
  @override
  Future<void> setFavorite(String id, bool value) async {
    if (value) {
      await api.postMap('experts/${_id(id)}/favorite');
    } else {
      await api.delete('experts/${_id(id)}/favorite');
    }
  }

  @override
  Future<SlotPage> slots(
    String expertId,
    String serviceId,
    DateTime from,
    DateTime to,
  ) async => SlotPage(
    await api.getMap(
      'experts/${_id(expertId)}/slots',
      queryParameters: {
        'service_id': serviceId,
        'from': from.toUtc().toIso8601String(),
        'to': to.toUtc().toIso8601String(),
      },
    ),
  );
  @override
  Future<Order> createOrder(BookingIntent intent) async => Order(
    await api.postMap(
      'orders',
      data: intent.payload,
      headers: {'Idempotency-Key': intent.idempotencyKey},
    ),
  );
  @override
  Future<List<Order>> orders({bool expert = false}) async => (await api.getList(
    expert ? 'expert/orders' : 'orders',
  )).map(Order.new).toList();
  @override
  Future<Order> order(String id, {bool expert = false}) async => Order(
    await api.getMap('${expert ? 'expert/orders' : 'orders'}/${_id(id)}'),
  );
  @override
  Future<Order> cancelOrder(String id) async =>
      Order(await api.postMap('orders/${_id(id)}/cancel', data: {}));
  @override
  Future<Order> completeOrder(String id, {bool expert = false}) async => Order(
    await api.postMap(
      '${expert ? 'expert/orders' : 'orders'}/${_id(id)}/complete',
      data: {},
    ),
  );
  @override
  Future<Order> deliverOrder(String id, String note) async => Order(
    await api.postMap('expert/orders/${_id(id)}/deliver', data: {'note': note}),
  );
  @override
  Future<List<Appointment>> appointments({
    bool expert = false,
    bool upcoming = false,
  }) async => (await api.getList(
    expert ? 'expert/appointments' : 'appointments',
    queryParameters: {'upcoming': upcoming},
  )).map(Appointment.new).toList();
  @override
  Future<Appointment> appointment(String id) async =>
      Appointment(await api.getMap('appointments/${_id(id)}'));
  @override
  Future<Appointment> cancelAppointment(
    String id, {
    bool expert = false,
  }) async => Appointment(
    await api.postMap(
      '${expert ? 'expert/appointments' : 'appointments'}/${_id(id)}/cancel',
      data: {},
    ),
  );
  @override
  Future<List<OrderConsent>> consents(String orderId) async =>
      (await api.getList(
        'orders/${_id(orderId)}/consents',
      )).map(OrderConsent.new).toList();
  @override
  Future<List<OrderConsent>> setConsents(
    String orderId,
    Set<String> scopes,
  ) async {
    if (!consentScopes.toSet().containsAll(scopes)) {
      throw ArgumentError.value(scopes, 'scopes');
    }
    final response = await api.putList(
      'orders/${_id(orderId)}/consents',
      data: {'scopes': scopes.toList()},
    );
    return response.map(OrderConsent.new).toList();
  }

  @override
  Future<ExpertReview> createReview(
    String orderId,
    int rating,
    String? comment,
  ) async => ExpertReview(
    await api.postMap(
      'orders/${_id(orderId)}/review',
      data: {'rating': rating, 'comment': comment},
    ),
  );
  @override
  Future<ExpertReview> updateReview(
    String reviewId,
    int rating,
    String? comment,
  ) async => ExpertReview(
    await api.patchMap(
      'reviews/${_id(reviewId)}',
      data: {'rating': rating, 'comment': comment},
    ),
  );
  @override
  Future<void> deleteReview(String reviewId) =>
      api.delete('reviews/${_id(reviewId)}');
  @override
  Future<Expert> ownProfile() async => Expert(await api.getMap('experts/me'));
  @override
  Future<Expert> updateOwnProfile(Json patch) async =>
      Expert(await api.patchMap('experts/me', data: patch));
  @override
  Future<ExpertService> createOwnService(Json data) async =>
      ExpertService(await api.postMap('experts/me/services', data: data));
  @override
  Future<ExpertService> updateOwnService(String id, Json data) async =>
      ExpertService(
        await api.patchMap('experts/me/services/${_id(id)}', data: data),
      );
  @override
  Future<ExpertService> deactivateOwnService(String id) async =>
      ExpertService(await api.deleteMap('experts/me/services/${_id(id)}'));
  @override
  Future<List<AvailabilityWindow>> ownAvailability() async =>
      (await api.getList(
        'experts/me/availability',
      )).map(AvailabilityWindow.new).toList();
  @override
  Future<AvailabilityWindow> addOwnAvailability(Json data) async =>
      AvailabilityWindow(
        await api.postMap('experts/me/availability', data: data),
      );
  @override
  Future<void> removeOwnAvailability(String id) =>
      api.delete('experts/me/availability/${_id(id)}');
  @override
  Future<List<AvailabilityException>> ownExceptions() async =>
      (await api.getList(
        'experts/me/availability/exceptions',
      )).map(AvailabilityException.new).toList();
  @override
  Future<AvailabilityException> addOwnException(Json data) async =>
      AvailabilityException(
        await api.postMap('experts/me/availability/exceptions', data: data),
      );
  @override
  Future<void> removeOwnException(String id) =>
      api.delete('experts/me/availability/exceptions/${_id(id)}');
}

class UnavailableMarketplaceRepository implements MarketplaceRepository {
  const UnavailableMarketplaceRepository();
  ApiException get _unavailable =>
      const ApiException(kind: ApiErrorKind.server, code: 'demo_unavailable');
  @override
  Future<ExpertPage> search(ExpertQuery q) async => ExpertPage({
    'items': <Json>[],
    'total': 0,
    'limit': q.limit,
    'offset': q.offset,
  });
  @override
  Future<Expert> detail(String id) async => throw _unavailable;
  @override
  Future<List<ExpertService>> services(String id) async => [];
  @override
  Future<ReviewPage> reviews(
    String id, {
    int limit = 20,
    int offset = 0,
  }) async => ReviewPage({
    'items': <Json>[],
    'total': 0,
    'rating_average': 0,
    'rating_count': 0,
  });
  @override
  Future<List<Expert>> favorites() async => [];
  @override
  Future<void> setFavorite(String id, bool value) async => throw _unavailable;
  @override
  Future<SlotPage> slots(String e, String s, DateTime f, DateTime t) async =>
      SlotPage({
        'expert_service_id': s,
        'display_timezone': 'UTC',
        'slots': <Json>[],
      });
  @override
  Future<Order> createOrder(BookingIntent i) async => throw _unavailable;
  @override
  Future<List<Order>> orders({bool expert = false}) async => [];
  @override
  Future<Order> order(String id, {bool expert = false}) async =>
      throw _unavailable;
  @override
  Future<Order> cancelOrder(String id) async => throw _unavailable;
  @override
  Future<Order> completeOrder(String id, {bool expert = false}) async =>
      throw _unavailable;
  @override
  Future<Order> deliverOrder(String id, String note) async =>
      throw _unavailable;
  @override
  Future<List<Appointment>> appointments({
    bool expert = false,
    bool upcoming = false,
  }) async => [];
  @override
  Future<Appointment> appointment(String id) async => throw _unavailable;
  @override
  Future<Appointment> cancelAppointment(
    String id, {
    bool expert = false,
  }) async => throw _unavailable;
  @override
  Future<List<OrderConsent>> consents(String id) async => [];
  @override
  Future<List<OrderConsent>> setConsents(String id, Set<String> scopes) async =>
      throw _unavailable;
  @override
  Future<ExpertReview> createReview(
    String id,
    int rating,
    String? comment,
  ) async => throw _unavailable;
  @override
  Future<ExpertReview> updateReview(
    String id,
    int rating,
    String? comment,
  ) async => throw _unavailable;
  @override
  Future<void> deleteReview(String id) async => throw _unavailable;
  @override
  Future<Expert> ownProfile() async => throw _unavailable;
  @override
  Future<Expert> updateOwnProfile(Json patch) async => throw _unavailable;
  @override
  Future<ExpertService> createOwnService(Json data) async => throw _unavailable;
  @override
  Future<ExpertService> updateOwnService(String id, Json data) async =>
      throw _unavailable;
  @override
  Future<ExpertService> deactivateOwnService(String id) async =>
      throw _unavailable;
  @override
  Future<List<AvailabilityWindow>> ownAvailability() async => [];
  @override
  Future<AvailabilityWindow> addOwnAvailability(Json data) async =>
      throw _unavailable;
  @override
  Future<void> removeOwnAvailability(String id) async => throw _unavailable;
  @override
  Future<List<AvailabilityException>> ownExceptions() async => [];
  @override
  Future<AvailabilityException> addOwnException(Json data) async =>
      throw _unavailable;
  @override
  Future<void> removeOwnException(String id) async => throw _unavailable;
}

final marketplaceRepositoryProvider = Provider<MarketplaceRepository>((ref) {
  ref.watch(currentUserProvider)?.id;
  return ref.watch(appEnvironmentProvider).useMocks
      ? const UnavailableMarketplaceRepository()
      : ApiMarketplaceRepository(ApiClient(ref.watch(dioProvider)));
});
