/// Holds a validated push route until authentication and the router are ready.
class PendingDeepLinks {
  final _pending = <String>[];
  String? _lastDelivered;

  bool get hasPending => _pending.isNotEmpty;

  void enqueue(String route) {
    if (route.isEmpty || route == _lastDelivered || _pending.contains(route)) {
      return;
    }
    _pending.add(route);
  }

  String? takeIfReady({required bool authenticated}) {
    if (!authenticated || _pending.isEmpty) return null;
    final route = _pending.removeAt(0);
    _lastDelivered = route;
    return route;
  }

  void clear() {
    _pending.clear();
    _lastDelivered = null;
  }
}
