import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_exception.dart';

/// Answers a retry cannot change: the record is gone, access is refused, the
/// request is invalid, or the server asked us to slow down.
const _settled = {
  ApiErrorKind.unauthorized,
  ApiErrorKind.forbidden,
  ApiErrorKind.validation,
  ApiErrorKind.notFound,
  ApiErrorKind.rateLimited,
};

/// Riverpod's automatic retry for failed providers, without retrying settled
/// API answers. Otherwise a notification that opens a deleted record keeps
/// the screen "loading" for about a minute while the same 404 is fetched ten
/// times; it now shows the not-found state at once. Network and server
/// failures keep Riverpod's default backoff.
Duration? apiRetry(int retryCount, Object error) {
  if (error is ApiException && _settled.contains(error.kind)) return null;
  return ProviderContainer.defaultRetry(retryCount, error);
}
