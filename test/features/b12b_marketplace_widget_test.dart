import 'package:astrofrekans/features/marketplace/data/marketplace_models.dart';
import 'package:astrofrekans/features/marketplace/data/marketplace_repository.dart';
import 'package:astrofrekans/features/marketplace/presentation/marketplace_screens.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class _Marketplace extends Fake implements MarketplaceRepository {
  final queries = <ExpertQuery>[];
  @override
  Future<ExpertPage> search(ExpertQuery query) async {
    queries.add(query);
    if (query.search != null) {
      // The server searched every expert and found none.
      return ExpertPage({
        'items': <Map<String, dynamic>>[],
        'total': 0,
        'limit': 20,
        'offset': 0,
      });
    }
    return ExpertPage({
      'items': [
        for (var i = 0; i < 20; i++)
          {
            'id': '$i',
            'display_name': i == 0 ? 'Ayşe Demir' : 'Uzman $i',
            'headline': 'Astroloji uzmanı',
            'languages': ['tr'],
            'specialties': ['astrology'],
            'experience_years': 7,
            'verified': true,
            'rating_average': 4.8,
            'rating_count': 12,
            'from_price': {'amount_minor': 1999, 'currency': 'TRY'},
          },
      ],
      'total': 20,
      'limit': 20,
      'offset': query.offset,
    });
  }
}

void main() {
  testWidgets('marketplace renders experts and searches on the server', (
    tester,
  ) async {
    final repo = _Marketplace();
    final watch = Stopwatch()..start();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [marketplaceRepositoryProvider.overrideWithValue(repo)],
        child: const MaterialApp(home: MarketplaceScreen()),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    watch.stop();
    // ignore: avoid_print
    print(
      'B12B_PERF marketplace_first_page_20_widget=${watch.elapsedMilliseconds}ms',
    );
    expect(find.text('Ayşe Demir'), findsOneWidget);
    expect(repo.queries.single.offset, 0);
    await tester.enterText(find.byType(TextField).first, 'Olmayan');
    await tester.pump();
    // Debounced: one keystroke burst, one request - after the pause.
    expect(repo.queries.length, 1);
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pump();
    expect(repo.queries.length, 2);
    expect(repo.queries.last.query['q'], 'Olmayan');
    expect(repo.queries.last.offset, 0);
    expect(find.text('Ayşe Demir'), findsNothing);
  });

  testWidgets('expert card remains usable with large text', (tester) async {
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final repo = _Marketplace();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [marketplaceRepositoryProvider.overrideWithValue(repo)],
        child: const MaterialApp(
          home: MediaQuery(
            data: MediaQueryData(textScaler: TextScaler.linear(1.6)),
            child: MarketplaceScreen(),
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    await tester.scrollUntilVisible(
      find.text('Ayşe Demir'),
      150,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Ayşe Demir'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
