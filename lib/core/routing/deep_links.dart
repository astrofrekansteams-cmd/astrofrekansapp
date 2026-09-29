import 'app_routes.dart';

/// Links from outside the app - an email, a web page, another app - arrive as
/// `astrofrekans://app/<path>`. Both platforms hand the router the full URL
/// (Android `Intent.getData().toString()`, iOS `NSURL.absoluteString`), so
/// the scheme is what tells an outside link from the app's own navigation,
/// and this one list decides for Android and iOS alike.
///
/// Only these screens may be opened from outside. Signing in still applies,
/// and the detail screens load by id from the server, which checks
/// ownership. Anything else - an unknown path, another host, a route that
/// starts a call or a payment - lands on the home screen.
final List<RegExp> _openableFromOutside = <RegExp>[
  RegExp('^${RegExp.escape(AppRoutes.resetPassword)}\$'),
  RegExp('^${RegExp.escape(AppRoutes.notifications)}\$'),
  RegExp('^${RegExp.escape(AppRoutes.appointments)}/$_uuid\$'),
  RegExp('^${RegExp.escape(AppRoutes.orders)}/$_uuid\$'),
  RegExp('^${RegExp.escape(AppRoutes.aiReports)}/$_uuid\$'),
];

const String _uuid =
    '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
    '[0-9a-fA-F]{4}-[0-9a-fA-F]{12}';

const String appLinkScheme = 'astrofrekans';
const String appLinkHost = 'app';

/// True for a location that came from outside the app.
bool isExternalLink(Uri uri) => uri.hasScheme;

/// Where an outside link may go: its path (and query, e.g. the reset token)
/// when allowed, otherwise home.
String externalLinkTarget(Uri uri) {
  final bool ours =
      uri.scheme.toLowerCase() == appLinkScheme &&
      uri.host.toLowerCase() == appLinkHost;
  final String path = uri.path.length > 1 && uri.path.endsWith('/')
      ? uri.path.substring(0, uri.path.length - 1)
      : uri.path;
  if (!ours || !_openableFromOutside.any((r) => r.hasMatch(path))) {
    return AppRoutes.home;
  }
  return Uri(path: path, query: uri.hasQuery ? uri.query : null).toString();
}
