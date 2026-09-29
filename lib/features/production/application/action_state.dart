import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Mutations are explicit user commands, never retried automatically.
class ActionState<T> extends ChangeNotifier {
  AsyncValue<T>? value;
  bool _disposed = false;
  bool get busy => value?.isLoading ?? false;
  Future<T?> run(Future<T> Function() operation) async {
    if (busy) return null;
    value = const AsyncLoading();
    notifyListeners();
    final result = await AsyncValue.guard(operation);
    if (_disposed) return null;
    value = result;
    notifyListeners();
    return result.asData?.value;
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
