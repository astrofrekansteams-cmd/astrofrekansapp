/// Locale-aware casing helpers.
///
/// `String.toUpperCase()` in Dart is not locale aware: in Turkish it turns
/// `i` into `I` instead of `İ`, and `ı` into `I` only by accident. The UI uses
/// wide-tracked uppercase labels a lot, so this matters.
extension AstroTextCase on String {
  String toUpperCaseFor(String languageCode) {
    if (languageCode == 'tr' || languageCode == 'az') {
      return replaceAll('i', 'İ').replaceAll('ı', 'I').toUpperCase();
    }
    return toUpperCase();
  }

  String toLowerCaseFor(String languageCode) {
    if (languageCode == 'tr' || languageCode == 'az') {
      return replaceAll('I', 'ı').replaceAll('İ', 'i').toLowerCase();
    }
    return toLowerCase();
  }
}
