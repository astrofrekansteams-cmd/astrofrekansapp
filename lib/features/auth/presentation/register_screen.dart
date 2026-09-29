import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/assets/app_assets.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/network/api_config.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/utils/text_case.dart';
import '../../../core/widgets/widgets.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../application/session_controller.dart';
import '../domain/auth_repository.dart';
import 'widgets/astro_text_field.dart';
import 'widgets/auth_validators.dart';
import 'widgets/social_auth_row.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _name = TextEditingController();
  final TextEditingController _email = TextEditingController();
  final TextEditingController _password = TextEditingController();
  final TextEditingController _passwordConfirm = TextEditingController();
  final TextEditingController _birthPlace = TextEditingController();

  final ScrollController _scroll = ScrollController();
  int _step = 0;

  void _changeStep(int step) {
    FocusScope.of(context).unfocus();
    setState(() {
      _step = step;
      _error = null;
    });
    if (_scroll.hasClients) _scroll.jumpTo(0);
  }

  DateTime? _birthDate;
  TimeOfDay? _birthTime;
  bool _birthTimeUnknown = false;
  bool _busy = false;
  bool _obscure = true;
  String? _error;
  String? _birthDateError;

  @override
  void dispose() {
    _scroll.dispose();
    _name.dispose();
    _email.dispose();
    _password.dispose();
    _passwordConfirm.dispose();
    _birthPlace.dispose();
    super.dispose();
  }

  Future<void> _pickBirthDate() async {
    final DateTime now = DateTime.now();
    final DateTime? picked = await showDatePicker(
      context: context,
      initialDate: _birthDate ?? DateTime(now.year - 28, now.month, now.day),
      firstDate: DateTime(1920),
      lastDate: now,
      helpText: context.l10n.authBirthDate,
    );
    if (picked != null) {
      setState(() {
        _birthDate = picked;
        _birthDateError = null;
      });
    }
  }

  Future<void> _pickBirthTime() async {
    final TimeOfDay? picked = await showTimePicker(
      context: context,
      initialTime: _birthTime ?? const TimeOfDay(hour: 9, minute: 41),
      helpText: context.l10n.authBirthTime,
    );
    if (picked != null) setState(() => _birthTime = picked);
  }

  String? _formattedTime() {
    if (_birthTimeUnknown || _birthTime == null) return null;
    final String hh = _birthTime!.hour.toString().padLeft(2, '0');
    final String mm = _birthTime!.minute.toString().padLeft(2, '0');
    return '$hh:$mm';
  }

  Future<void> _submit() async {
    if (_step == 0) {
      if (_formKey.currentState?.validate() ?? false) _changeStep(1);
      return;
    }
    final bool formValid = _formKey.currentState?.validate() ?? false;
    if (_birthDate == null) {
      setState(() => _birthDateError = context.l10n.validationBirthDate);
    }
    if (!formValid || _birthDate == null) return;

    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref
          .read(sessionProvider.notifier)
          .register(
            RegistrationRequest(
              name: _name.text,
              email: _email.text,
              password: _password.text,
              birthDate: _birthDate!,
              birthTime: _formattedTime(),
              birthPlace: _birthPlace.text.trim(),
            ),
          );
    } on AuthException catch (error) {
      if (!mounted) return;
      setState(
        () => _error = error.kind == AuthFailureKind.emailInUse
            ? context.l10n.authEmailInUse
            : context.l10n.errorGeneric,
      );
    } on Object {
      if (!mounted) return;
      setState(() => _error = context.l10n.errorGeneric);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;
    final AuthValidators validators = AuthValidators(l10n);
    final DateFormat dateFormat = DateFormat.yMMMMd(context.languageCode);

    return AstroScaffold(
      backgroundAsset: AppAssets.loginBackground,
      backgroundAspectRatio: 941 / 1672,
      scrimOpacity: 0.74,
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: AppSpacing.contentMaxWidth,
          ),
          child: SingleChildScrollView(
            controller: _scroll,
            padding: EdgeInsets.fromLTRB(
              context.gutter + AppSpacing.sm,
              AppSpacing.lg,
              context.gutter + AppSpacing.sm,
              AppSpacing.xxl,
            ),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      AstroIconButton(
                        icon: Icons.arrow_back,
                        semanticLabel: l10n.commonBack,
                        onPressed: _busy
                            ? null
                            : () => _step == 1
                                  ? _changeStep(0)
                                  : context.go(AppRoutes.onboarding),
                      ),
                      const Spacer(),
                      if (ref.watch(showDemoNoticeProvider))
                        AstroBadge(label: l10n.commonDemoMode),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.xl),
                  Text(
                    l10n.authRegisterTitle,
                    textAlign: TextAlign.center,
                    style: AppTypography.displayMedium.copyWith(fontSize: 29),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    l10n.authRegisterSubtitle,
                    textAlign: TextAlign.center,
                    style: AppTypography.bodyMedium,
                  ),
                  const SizedBox(height: AppSpacing.xxl),

                  Text(
                    b12(
                      context,
                      _step == 0
                          ? 'register_step_account'
                          : 'register_step_birth',
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  if (_step == 0) ...[
                    _SectionLabel(
                      text: l10n.authAccountSection.toUpperCaseFor(
                        context.languageCode,
                      ),
                    ),
                    AstroTextField(
                      controller: _name,
                      label: l10n.authName.toUpperCaseFor(context.languageCode),
                      keyboardType: TextInputType.name,
                      autofillHints: const <String>[AutofillHints.name],
                      validator: validators.name,
                    ),
                    AstroTextField(
                      controller: _email,
                      label: l10n.authEmail.toUpperCaseFor(
                        context.languageCode,
                      ),
                      keyboardType: TextInputType.emailAddress,
                      autofillHints: const <String>[AutofillHints.email],
                      validator: validators.email,
                    ),
                    AstroTextField(
                      controller: _password,
                      label: l10n.authPassword.toUpperCaseFor(
                        context.languageCode,
                      ),
                      obscureText: _obscure,
                      validator: validators.password,
                      suffix: IconButton(
                        onPressed: () => setState(() => _obscure = !_obscure),
                        icon: Icon(
                          _obscure
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined,
                          size: 20,
                        ),
                        tooltip: l10n.authPassword,
                      ),
                    ),
                    AstroTextField(
                      controller: _passwordConfirm,
                      label: l10n.authPasswordConfirm.toUpperCaseFor(
                        context.languageCode,
                      ),
                      obscureText: _obscure,
                      validator: (String? value) =>
                          validators.passwordConfirm(value, _password.text),
                    ),
                  ],
                  if (_step == 1) ...[
                    const SizedBox(height: AppSpacing.md),
                    _SectionLabel(
                      text: l10n.authBirthSection.toUpperCaseFor(
                        context.languageCode,
                      ),
                    ),
                    _PickerField(
                      label: l10n.authBirthDate.toUpperCaseFor(
                        context.languageCode,
                      ),
                      value: _birthDate == null
                          ? l10n.commonSelect
                          : dateFormat.format(_birthDate!),
                      icon: Icons.calendar_today_outlined,
                      onTap: _pickBirthDate,
                      isPlaceholder: _birthDate == null,
                      errorText: _birthDateError,
                    ),
                    _PickerField(
                      label: l10n.authBirthTime.toUpperCaseFor(
                        context.languageCode,
                      ),
                      value: _birthTimeUnknown
                          ? l10n.authBirthTimeUnknown
                          : _birthTime?.format(context) ?? l10n.commonSelect,
                      icon: Icons.schedule_outlined,
                      onTap: _birthTimeUnknown ? null : _pickBirthTime,
                      isPlaceholder: _birthTimeUnknown || _birthTime == null,
                    ),
                    Row(
                      children: <Widget>[
                        Checkbox(
                          value: _birthTimeUnknown,
                          onChanged: (bool? value) => setState(() {
                            _birthTimeUnknown = value ?? false;
                            if (_birthTimeUnknown) _birthTime = null;
                          }),
                        ),
                        Expanded(
                          child: GestureDetector(
                            onTap: () => setState(
                              () => _birthTimeUnknown = !_birthTimeUnknown,
                            ),
                            child: Text(
                              l10n.authBirthTimeUnknown,
                              style: AppTypography.bodySmall.copyWith(
                                color: AppColors.ivoryMuted,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.md),
                    AstroTextField(
                      controller: _birthPlace,
                      label: l10n.authBirthPlace.toUpperCaseFor(
                        context.languageCode,
                      ),
                      hint: l10n.authBirthPlaceHint,
                      textInputAction: TextInputAction.done,
                      validator: validators.birthPlace,
                    ),
                    Text(
                      l10n.authBirthDataWhy,
                      style: AppTypography.bodySmall.copyWith(fontSize: 12),
                    ),
                  ],
                  if (_error != null) ...<Widget>[
                    const SizedBox(height: AppSpacing.md),
                    Text(
                      _error!,
                      style: AppTypography.bodySmall.copyWith(
                        color: AppColors.danger,
                      ),
                    ),
                  ],
                  const SizedBox(height: AppSpacing.xl),
                  AstroButton(
                    key: ValueKey(
                      _step == 0 ? 'register-next' : 'register-submit',
                    ),
                    label: _step == 0
                        ? b12(context, 'register_next')
                        : l10n.authRegister,
                    isLoading: _busy,
                    onPressed: _submit,
                  ),
                  const SizedBox(height: AppSpacing.xl),
                  if (_step == 0) const SocialAuthRow(),
                  const SizedBox(height: AppSpacing.lg),
                  Wrap(
                    alignment: WrapAlignment.center,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: <Widget>[
                      Text(l10n.authHasAccount, style: AppTypography.bodySmall),
                      TextButton(
                        onPressed: () => context.go(AppRoutes.login),
                        style: TextButton.styleFrom(
                          foregroundColor: AppColors.gold,
                          minimumSize: const Size(0, AppSpacing.minTapTarget),
                        ),
                        child: Text(
                          l10n.authLogin,
                          style: AppTypography.labelMedium.copyWith(
                            color: AppColors.gold,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.md),
    child: Row(
      children: <Widget>[
        Text(
          text,
          style: AppTypography.labelSmall.copyWith(color: AppColors.gold),
        ),
        const SizedBox(width: AppSpacing.md),
        const Expanded(child: AstroGoldDivider()),
      ],
    ),
  );
}

class _PickerField extends StatelessWidget {
  const _PickerField({
    required this.label,
    required this.value,
    required this.icon,
    required this.onTap,
    required this.isPlaceholder,
    this.errorText,
  });

  final String label;
  final String value;
  final IconData icon;
  final VoidCallback? onTap;
  final bool isPlaceholder;
  final String? errorText;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.only(
              left: AppSpacing.xs,
              bottom: AppSpacing.xs + 2,
            ),
            child: Text(
              label,
              style: AppTypography.labelSmall.copyWith(
                color: AppColors.ivoryMuted,
                letterSpacing: 1.1,
              ),
            ),
          ),
          Semantics(
            button: onTap != null,
            label: '$label: $value',
            child: Material(
              color: AppColors.surfaceMuted.withValues(alpha: 0.72),
              borderRadius: BorderRadius.circular(16),
              clipBehavior: Clip.antiAlias,
              child: InkWell(
                onTap: onTap,
                child: Container(
                  constraints: const BoxConstraints(
                    minHeight: AppSpacing.minTapTarget + 8,
                  ),
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.lg,
                    vertical: AppSpacing.md,
                  ),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: errorText != null
                          ? AppColors.danger
                          : AppColors.hairline,
                    ),
                  ),
                  child: Row(
                    children: <Widget>[
                      Expanded(
                        child: Text(
                          value,
                          overflow: TextOverflow.ellipsis,
                          style: AppTypography.bodyLarge.copyWith(
                            color: isPlaceholder
                                ? AppColors.textSubtle
                                : AppColors.ivory,
                          ),
                        ),
                      ),
                      Icon(icon, size: 18, color: AppColors.ivoryMuted),
                    ],
                  ),
                ),
              ),
            ),
          ),
          if (errorText != null)
            Padding(
              padding: const EdgeInsets.only(
                top: AppSpacing.xs,
                left: AppSpacing.md,
              ),
              child: Text(
                errorText!,
                style: AppTypography.bodySmall.copyWith(
                  color: AppColors.danger,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
