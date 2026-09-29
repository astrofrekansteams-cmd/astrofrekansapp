import 'package:astrofrekans/core/network/api_exception.dart';
import 'package:astrofrekans/core/widgets/api_state_view.dart';
import 'package:astrofrekans/core/widgets/astro_skeleton.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

void main() {
  testWidgets(
    'loading, safe GET retry, empty and success remain readable at large text scale',
    (tester) async {
      var retries = 0;
      Future<void> show(AsyncValue<String> value) => tester.pumpWidget(
        MaterialApp(
          locale: const Locale('tr'),
          supportedLocales: const [Locale('tr'), Locale('en')],
          localizationsDelegates: GlobalMaterialLocalizations.delegates,
          home: MediaQuery(
            data: const MediaQueryData(textScaler: TextScaler.linear(1.6)),
            child: Scaffold(
              body: ApiStateView(
                value: value,
                onRetry: () => retries++,
                builder: (value) => FactSection(
                  title: 'sources',
                  lines: value.isEmpty ? [] : [value],
                ),
              ),
            ),
          ),
        ),
      );
      await show(const AsyncLoading<String>());
      expect(find.byType(AstroSkeletonPage), findsOneWidget);
      await show(
        const AsyncError<String>(
          ApiException(kind: ApiErrorKind.network),
          StackTrace.empty,
        ),
      );
      expect(find.textContaining('Bağlantı kurulamadı'), findsOneWidget);
      await tester.tap(find.text('Tekrar dene'));
      expect(retries, 1);
      await show(const AsyncData<String>(''));
      expect(find.text('Henüz kayıt yok.'), findsOneWidget);
      await show(const AsyncData<String>('transit:venus'));
      expect(find.text('transit:venus'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'backend stable codes are translated without raw exception text',
    (tester) async {
      late BuildContext captured;
      await tester.pumpWidget(
        MaterialApp(
          locale: const Locale('en'),
          home: Builder(
            builder: (context) {
              captured = context;
              return const SizedBox();
            },
          ),
        ),
      );
      for (final entry in <String, String>{
        'ai_not_configured': 'Astro AI is not configured',
        'firebase_not_configured': 'Firebase is not configured',
        'ai_rate_limited': 'Request limit reached',
        'provider_unavailable': 'temporarily unavailable',
      }.entries) {
        final copy = friendlyApiError(
          captured,
          ApiException(kind: ApiErrorKind.server, code: entry.key),
        );
        expect(copy, contains(entry.value));
        expect(copy, isNot(contains('ApiException')));
      }
    },
  );
}
