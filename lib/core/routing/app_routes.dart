/// Route paths and names. Screens never hardcode path strings.
abstract final class AppRoutes {
  static const String splash = '/splash';
  static const String onboarding = '/onboarding';
  static const String login = '/login';
  static const String register = '/register';
  static const String forgotPassword = '/forgot-password';
  static const String resetPassword = '/reset-password';

  // Shell branches
  static const String home = '/home';
  static const String sky = '/sky';
  static const String astroAi = '/astro-ai';
  static const String explore = '/explore';
  static const String profile = '/profile';

  // Feature routes pushed over the shell
  static const String natalChart = '/natal-chart';
  static const String transits = '/transits';
  static const String compatibility = '/compatibility';
  static const String tarot = '/tarot';
  static const String rune = '/rune';
  static const String katina = '/katina';
  static const String cosmicCalendar = '/cosmic-calendar';
  static const String consultants = '/consultants';
  static const String premium = '/premium';
  static const String savedPeople = '/saved-people';
  static const String profileEdit = '/profile/edit';
  static const String horary = '/horary';
  static const String forecasts = '/forecasts';
  static const String frequency = '/frequency';
  static const String moonGuide = '/moon-guide';
  static const String numerology = '/numerology';
  static const String stoneGuide = '/stones';
  static const String solarReturn = '/solar-return';
  static const String lunarReturn = '/lunar-return';
  static const String aiReports = '/astro-ai/reports';
  static const String marketplace = '/experts';
  static const String orders = '/orders';
  static const String appointments = '/appointments';
  static const String favorites = '/favorites';
  static const String consultations = '/consultations';
  static const String calls = '/calls';
  static const String callHistory = '/calls/history';
  static const String expertWorkspace = '/expert-workspace';
  static const String coins = '/coins';
  static const String profileCustomize = '/profile/customize';
  static const String notificationSettings = '/profile/notifications';
  static const String privacySettings = '/profile/privacy';
  static const String accountCenter = '/profile/account';
  static const String accountInfo = '/profile/account/info';
  static const String changePassword = '/profile/account/password';
  static const String accountSessions = '/profile/account/sessions';
  static const String deleteAccount = '/profile/account/delete';
  static const String settings = '/profile/settings';
  static const String notifications = '/notifications';
  static String expertDetail(String id) =>
      '$marketplace/${Uri.encodeComponent(id)}';
  static String orderDetail(String id) => '$orders/${Uri.encodeComponent(id)}';
  static String appointmentDetail(String id) =>
      '$appointments/${Uri.encodeComponent(id)}';
  static String chatThread(String id) =>
      '$consultations/${Uri.encodeComponent(id)}';
  static String callDetail(String id) => '$calls/${Uri.encodeComponent(id)}';
  static String incomingCall(String id) => '${callDetail(id)}/incoming';
  static String orderCall(String id) => '${orderDetail(id)}/call';
  static String reading(String deck, String id) =>
      '/$deck/${Uri.encodeComponent(id)}';

  static const Set<String> publicRoutes = <String>{
    splash,
    onboarding,
    login,
    register,
    forgotPassword,
    resetPassword,
  };
}
