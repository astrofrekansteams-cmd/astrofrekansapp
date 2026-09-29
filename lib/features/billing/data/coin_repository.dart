import 'dart:math' as math;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../core/network/api_config.dart';
import '../../auth/application/session_controller.dart';
import 'coin_models.dart';

/// AstroCoin API. There is no "add coins" call: coins arrive from verified
/// store purchases, verified rewarded ads, the monthly plan bonus or refunds.
class CoinRepository {
  const CoinRepository(this.api);
  final ApiClient api;

  Future<CoinWallet> wallet() async =>
      CoinWallet(await api.getMap('coins/wallet'));

  Future<List<CoinTransaction>> transactions({int limit = 50}) async =>
      (await api.getList(
        'coins/transactions',
        queryParameters: {'limit': limit},
      )).map(CoinTransaction.new).toList(growable: false);

  Future<CoinCatalog> catalog() async =>
      CoinCatalog(await api.getMap('coins/catalog'));

  /// Claims a completed rewarded ad. [token] is the ad network's reward id.
  Future<CoinWallet> rewardAd(String token) async {
    final body = await api.postMap('coins/ads/reward', data: {'token': token});
    return CoinWallet(Map<String, dynamic>.from(body['wallet'] as Map));
  }

  Future<DrawAllowance> drawAllowance() async =>
      DrawAllowance(await api.getMap('divination/allowance'));
}

final coinRepositoryProvider = Provider<CoinRepository?>((ref) {
  ref.watch(currentUserProvider)?.id;
  if (ref.watch(appEnvironmentProvider).useMocks) return null;
  return CoinRepository(ApiClient(ref.watch(dioProvider)));
});

final coinWalletProvider = FutureProvider.autoDispose<CoinWallet?>((ref) async {
  final repo = ref.watch(coinRepositoryProvider);
  return repo?.wallet();
});

final coinTransactionsProvider =
    FutureProvider.autoDispose<List<CoinTransaction>>((ref) async {
      final repo = ref.watch(coinRepositoryProvider);
      return await repo?.transactions() ?? const <CoinTransaction>[];
    });

final coinCatalogProvider = FutureProvider<CoinCatalog?>((ref) async {
  final repo = ref.watch(coinRepositoryProvider);
  return repo?.catalog();
});

final drawAllowanceProvider = FutureProvider.autoDispose<DrawAllowance?>((
  ref,
) async {
  final repo = ref.watch(coinRepositoryProvider);
  return repo?.drawAllowance();
});

// ---------------------------------------------------------- rewarded ads

/// Shows a rewarded ad and returns the network's reward token, or null when
/// the viewer closed it early. A real network (AdMob, AppLovin...) plugs in
/// here; the server verifies the token before paying.
abstract interface class RewardedAdService {
  bool get isDemo;
  Future<String?> show();
}

/// Placeholder until an ad network is integrated: the server only accepts
/// its tokens with the dev-only "mock" verifier, never in production.
class DemoRewardedAdService implements RewardedAdService {
  const DemoRewardedAdService();
  @override
  bool get isDemo => true;
  @override
  Future<String?> show() async {
    await Future<void>.delayed(const Duration(milliseconds: 600));
    final random = math.Random.secure();
    return 'demo-${List.generate(20, (_) => random.nextInt(16).toRadixString(16)).join()}';
  }
}

final rewardedAdServiceProvider = Provider<RewardedAdService>(
  (ref) => const DemoRewardedAdService(),
);
