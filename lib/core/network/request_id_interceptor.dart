import 'dart:math';

import 'package:dio/dio.dart';

class RequestIdInterceptor extends Interceptor {
  final Random _random = Random.secure();

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    options.headers.putIfAbsent('X-Request-Id', () {
      final String micros = DateTime.now()
          .toUtc()
          .microsecondsSinceEpoch
          .toRadixString(16);
      final String suffix = List<int>.generate(
        4,
        (_) => _random.nextInt(256),
      ).map((int byte) => byte.toRadixString(16).padLeft(2, '0')).join();
      return '$micros$suffix';
    });
    handler.next(options);
  }
}
