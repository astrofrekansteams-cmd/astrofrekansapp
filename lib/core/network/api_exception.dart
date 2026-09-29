/// Transport-agnostic failure kinds surfaced to the UI layer.
enum ApiErrorKind {
  unauthorized,
  forbidden,
  validation,
  notFound,
  rateLimited,
  server,
  network,
  timeout,
  cancelled,
  unknown,
}

class ApiException implements Exception {
  const ApiException({
    required this.kind,
    this.statusCode,
    this.code,
    this.fieldErrors = const <ApiFieldError>[],
    this.debugMessage,
    this.retryAfterSeconds,
  });

  final ApiErrorKind kind;
  final int? statusCode;
  final String? code;
  final List<ApiFieldError> fieldErrors;

  /// Developer-facing only. Never contains tokens or personal data and is not
  /// rendered in the UI; screens map [kind] to a localized message.
  final String? debugMessage;
  final int? retryAfterSeconds;

  @override
  String toString() => 'ApiException(${kind.name}, status: $statusCode)';
}

class ApiFieldError {
  const ApiFieldError({required this.path, required this.message});

  final String path;
  final String message;
}
