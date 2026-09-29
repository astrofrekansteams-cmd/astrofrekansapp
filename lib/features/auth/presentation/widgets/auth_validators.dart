import '../../../../l10n/generated/app_localizations.dart';

/// Form validation shared by login and register.
class AuthValidators {
  const AuthValidators(this.l10n);

  final AppLocalizations l10n;

  static final RegExp _email = RegExp(r'^[\w.+-]+@[\w-]+\.[\w.-]+$');

  String? name(String? value) {
    final String text = value?.trim() ?? '';
    if (text.isEmpty) return l10n.validationRequired;
    if (text.length < 2) return l10n.validationNameShort;
    return null;
  }

  String? email(String? value) {
    final String text = value?.trim() ?? '';
    if (text.isEmpty) return l10n.validationRequired;
    if (!_email.hasMatch(text)) return l10n.validationEmail;
    return null;
  }

  String? password(String? value) {
    final String text = value ?? '';
    if (text.isEmpty) return l10n.validationRequired;
    if (text.length < 8) return l10n.validationPasswordShort;
    return null;
  }

  String? passwordConfirm(String? value, String original) {
    if (value == null || value.isEmpty) return l10n.validationRequired;
    if (value != original) return l10n.validationPasswordMatch;
    return null;
  }

  String? birthPlace(String? value) {
    final String text = value?.trim() ?? '';
    if (text.isEmpty) return l10n.validationBirthPlace;
    return null;
  }
}
