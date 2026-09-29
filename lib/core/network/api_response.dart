/// Parsed payload with the backend correlation identifier when available.
class ApiResponse<T> {
  const ApiResponse({required this.data, this.requestId});

  final T data;
  final String? requestId;
}
