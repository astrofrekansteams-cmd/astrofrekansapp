import 'app_routes.dart';

final RegExp _uuid = RegExp(r'^[0-9a-fA-F-]{36}$');

/// Where a notification leads - one answer for the push that is tapped and
/// the notification-centre row that is opened, so both reach the same
/// screen. Ids only (validated as UUIDs): the screen fetches the detail after
/// the person has signed in.
String? routeForNotification(String? event, Map<String, dynamic> data) {
  String? id(String key) {
    final value = data[key];
    return value is String && _uuid.hasMatch(value) ? value : null;
  }

  final call = id('call_id');
  final conversation = id('conversation_id');
  final appointment = id('appointment_id');
  final order = id('order_id');
  final report = id('report_id');

  switch (event) {
    case 'incoming_call' when call != null:
      return AppRoutes.incomingCall(call);
    case 'call_cancelled' || 'call_missed' when call != null:
      return AppRoutes.callDetail(call);
    case 'new_chat_message' when conversation != null:
      return AppRoutes.chatThread(conversation);
    case 'appointment_booked' ||
            'appointment_cancelled' ||
            'appointment_reminder'
        when appointment != null:
      return AppRoutes.appointmentDetail(appointment);
    case 'order_status_changed' ||
            'payment_succeeded' ||
            'payment_failed' ||
            'refund_processed'
        when order != null:
      return AppRoutes.orderDetail(order);
    case 'ai_report_ready' when report != null:
      return '${AppRoutes.aiReports}/$report';
    case 'subscription_renewed' || 'subscription_expired':
      return AppRoutes.premium;
  }
  // Allowlisted: an event this build does not know leads nowhere, whatever
  // ids it carries.
  return null;
}

/// The inbox record a push is (`notification_id`, added by the server when it
/// sends). Opening the push marks that same record read.
String? notificationIdOf(Map<String, dynamic> data) {
  final value = data['notification_id'];
  return value is String && _uuid.hasMatch(value) ? value : null;
}
