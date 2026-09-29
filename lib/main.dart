import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app/app.dart';
import 'core/network/retry_policy.dart';
import 'core/storage/app_preferences.dart';
import 'core/theme/app_theme.dart';
import 'core/widgets/api_state_view.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Users never see Flutter's crash screen; the error itself is still
  // reported (FlutterError.onError) with its stack. Debug keeps the red
  // screen so developers notice.
  if (!kDebugMode) {
    ErrorWidget.builder = (_) => const SectionFailedFallback();
  }

  // Edge to edge on Android; the cosmic ground paints behind both system bars.
  await SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  SystemChrome.setSystemUIOverlayStyle(AppTheme.overlayStyle);

  final SharedPreferences prefs = await SharedPreferences.getInstance();

  runApp(
    ProviderScope(
      retry: apiRetry,
      overrides: [
        appPreferencesProvider.overrideWithValue(AppPreferences(prefs)),
      ],
      child: const AstrofrekansApp(),
    ),
  );
}
