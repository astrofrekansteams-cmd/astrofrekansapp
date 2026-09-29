import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/astrology/data/api_contract_dto.dart';
import '../../../core/astrology/data/production_models.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../auth/application/session_controller.dart';

/// Inbox categories (server `InboxCategory`).
enum NotificationCategory {
  astroAi,
  appointment,
  expertMessage,
  payment,
  system,
  promotion,
}

extension NotificationCategoryWire on NotificationCategory {
  String get wire => switch (this) {
    NotificationCategory.astroAi => 'astro_ai',
    NotificationCategory.appointment => 'appointment',
    NotificationCategory.expertMessage => 'expert_message',
    NotificationCategory.payment => 'payment',
    NotificationCategory.system => 'system',
    NotificationCategory.promotion => 'promotion',
  };
}

NotificationCategory _category(String? raw) =>
    NotificationCategory.values.firstWhere(
      (c) => c.wire == raw,
      orElse: () => NotificationCategory.system,
    );

/// One notification: the same event that was (or would have been) pushed.
/// It carries ids to route on - never content - and the app writes the text.
class InboxNotification extends ContractRecord {
  InboxNotification(super.value) {
    text('id');
    text('event');
  }
  String get id => text('id');
  String get event => text('event');
  NotificationCategory get category => _category(optionalText('category'));
  DateTime get createdAt => ContractJson.date(json, 'created_at').toLocal();
  bool get read => json['read'] == true;
  Map<String, String> get data =>
      Map<String, String>.from(json['data'] as Map? ?? const {});
  InboxNotification withRead(bool value) =>
      InboxNotification({...json, 'read': value});
}

class InboxPage extends ContractRecord {
  InboxPage(super.value);
  List<InboxNotification> get items => ContractJson.maps(
    json['items'],
  ).map(InboxNotification.new).toList(growable: false);
  int get unreadCount => json['unread_count'] as int? ?? 0;
  String? get nextBefore => optionalText('next_before');
}

abstract interface class NotificationRepository {
  Future<InboxPage> list({String? before, NotificationCategory? category});
  Future<int> unreadCount();
  Future<InboxNotification> setRead(String id, {required bool read});
  Future<void> readAll();
}

class ApiNotificationRepository implements NotificationRepository {
  const ApiNotificationRepository(this.api);
  final ApiClient api;

  @override
  Future<InboxPage> list({
    String? before,
    NotificationCategory? category,
  }) async => InboxPage(
    await api.getMap(
      'notifications',
      queryParameters: {
        'limit': 30,
        'before': ?before,
        'category': ?category?.wire,
      },
    ),
  );

  @override
  Future<int> unreadCount() async =>
      (await api.getMap('notifications/unread-count'))['unread_count']
          as int? ??
      0;

  @override
  Future<InboxNotification> setRead(String id, {required bool read}) async =>
      InboxNotification(
        await api.patchMap(
          'notifications/${Uri.encodeComponent(id)}',
          data: {'read': read},
        ),
      );

  @override
  Future<void> readAll() async {
    await api.postMap('notifications/read-all', data: {});
  }
}

/// Demo builds have no server and no notifications - an empty inbox, never
/// invented ones.
class EmptyNotificationRepository implements NotificationRepository {
  const EmptyNotificationRepository();
  @override
  Future<InboxPage> list({
    String? before,
    NotificationCategory? category,
  }) async => InboxPage({'items': <Json>[], 'unread_count': 0});
  @override
  Future<int> unreadCount() async => 0;
  @override
  Future<InboxNotification> setRead(String id, {required bool read}) async =>
      throw StateError('No notifications in demo mode');
  @override
  Future<void> readAll() async {}
}

final notificationRepositoryProvider = Provider<NotificationRepository>((ref) {
  ref.watch(currentUserProvider)?.id;
  return ref.watch(appEnvironmentProvider).useMocks
      ? const EmptyNotificationRepository()
      : ApiNotificationRepository(ApiClient(ref.watch(dioProvider)));
});

/// The bell's number. Re-read when the inbox changes and when the app comes
/// back to the foreground.
final unreadNotificationsProvider = FutureProvider<int>((ref) async {
  if (ref.watch(currentUserProvider) == null) return 0;
  return ref.watch(notificationRepositoryProvider).unreadCount();
});
