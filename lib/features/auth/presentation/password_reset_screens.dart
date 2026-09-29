import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/localization/b12_copy.dart';
import '../../../core/assets/app_assets.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/utils/text_case.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../data/password_reset_service.dart';
import 'widgets/astro_text_field.dart';
import 'widgets/auth_validators.dart';

/// Shared frame for the two reset screens: same background and width as login.
class _ResetFrame extends StatelessWidget {
  const _ResetFrame({required this.title, required this.children});
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => AstroScaffold(
    backgroundAsset: AppAssets.loginBackground,
    backgroundAspectRatio: 941 / 1672,
    scrimOpacity: 0.5,
    // Top-aligned: these screens are short, and a centred column would float
    // the back button in the middle of the screen.
    body: Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: AppSpacing.contentMaxWidth),
        child: SingleChildScrollView(
          padding: EdgeInsets.fromLTRB(
            context.gutter + AppSpacing.sm,
            AppSpacing.lg,
            context.gutter + AppSpacing.sm,
            AppSpacing.xxl,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Row(
                children: <Widget>[
                  AstroIconButton(
                    icon: Icons.arrow_back,
                    semanticLabel: context.l10n.commonBack,
                    onPressed: () => context.go(AppRoutes.login),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.xl),
              Text(
                title,
                textAlign: TextAlign.center,
                style: AppTypography.displayMedium.copyWith(fontSize: 28),
              ),
              const SizedBox(height: AppSpacing.lg),
              ...children,
            ],
          ),
        ),
      ),
    ),
  );
}

class _Notice extends StatelessWidget {
  const _Notice(this.text, {this.danger = false, super.key});
  final String text;
  final bool danger;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.md),
    child: Text(
      text,
      textAlign: TextAlign.center,
      style: AppTypography.bodyMedium.copyWith(
        color: danger ? AppColors.danger : null,
      ),
    ),
  );
}

/// "Şifremi unuttum": one field, one generic answer. The screen never says
/// whether the address has an account, and never claims a link was sent when
/// the server cannot send one.
class ForgotPasswordScreen extends ConsumerStatefulWidget {
  const ForgotPasswordScreen({super.key, this.initialEmail});
  final String? initialEmail;

  @override
  ConsumerState<ForgotPasswordScreen> createState() =>
      _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends ConsumerState<ForgotPasswordScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  late final TextEditingController _email = TextEditingController(
    text: widget.initialEmail,
  );
  bool _busy = false;
  PasswordResetRequestResult? _result;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final PasswordResetRequestResult result = await ref
          .read(passwordResetServiceProvider)
          .requestReset(_email.text);
      if (mounted) setState(() => _result = result);
    } on Object catch (error) {
      if (mounted) setState(() => _error = friendlyApiError(context, error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;
    final AuthValidators validators = AuthValidators(l10n);
    final PasswordResetRequestResult? result = _result;
    return _ResetFrame(
      title: l10n.authForgotTitle,
      children: <Widget>[
        if (result == PasswordResetRequestResult.requested) ...<Widget>[
          _Notice(
            l10n.authForgotRequested,
            key: const ValueKey<String>('reset-requested'),
          ),
          _Notice(l10n.authForgotCheckSpam),
        ] else if (result ==
            PasswordResetRequestResult.requestedFirebaseOnly) ...<Widget>[
          _Notice(
            b12(context, 'reset_requested_firebase_only'),
            key: const ValueKey<String>('reset-requested-firebase-only'),
          ),
          _Notice(l10n.authForgotCheckSpam),
        ] else ...<Widget>[
          _Notice(l10n.authForgotSubtitle),
          if (result == PasswordResetRequestResult.unavailable)
            _Notice(
              l10n.authForgotUnavailable,
              danger: true,
              key: const ValueKey<String>('reset-unavailable'),
            ),
          if (_error != null) _Notice(_error!, danger: true),
          Form(
            key: _formKey,
            child: AstroTextField(
              controller: _email,
              label: l10n.authEmail.toUpperCaseFor(context.languageCode),
              keyboardType: TextInputType.emailAddress,
              autofillHints: const <String>[AutofillHints.email],
              textInputAction: TextInputAction.done,
              validator: validators.email,
              onFieldSubmitted: (_) => _submit(),
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          AstroButton(
            label: l10n.authForgotSubmit,
            isLoading: _busy,
            onPressed: _submit,
          ),
        ],
        const SizedBox(height: AppSpacing.lg),
        TextButton(
          onPressed: () => context.go(AppRoutes.login),
          child: Text(l10n.authBackToLogin),
        ),
      ],
    );
  }
}

/// Opened from the emailed link (`astrofrekans://app/reset-password?token=`).
/// Checks the link first, so an expired or used one is said before a new
/// password is typed; the link works once.
class ResetPasswordScreen extends ConsumerStatefulWidget {
  const ResetPasswordScreen({super.key, required this.token});
  final String? token;

  @override
  ConsumerState<ResetPasswordScreen> createState() =>
      _ResetPasswordScreenState();
}

class _ResetPasswordScreenState extends ConsumerState<ResetPasswordScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _password = TextEditingController();
  final TextEditingController _confirm = TextEditingController();
  late Future<ResetLinkState> _check;
  bool _busy = false, _done = false, _obscure = true;
  ResetLinkState? _failed;
  String? _error;

  @override
  void initState() {
    super.initState();
    final String token = widget.token ?? '';
    _check = token.isEmpty
        ? Future<ResetLinkState>.value(ResetLinkState.invalid)
        : ref.read(passwordResetServiceProvider).checkLink(token);
  }

  @override
  void dispose() {
    _password.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref
          .read(passwordResetServiceProvider)
          .resetPassword(widget.token!, _password.text);
      if (mounted) setState(() => _done = true);
    } on PasswordResetException catch (error) {
      if (mounted) setState(() => _failed = error.state);
    } on Object catch (error) {
      if (mounted) setState(() => _error = friendlyApiError(context, error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  static String _stateText(AppLocalizations l10n, ResetLinkState state) =>
      switch (state) {
        ResetLinkState.expired => l10n.authResetExpired,
        ResetLinkState.used => l10n.authResetUsed,
        _ => l10n.authResetInvalid,
      };

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;
    final AuthValidators validators = AuthValidators(l10n);
    return _ResetFrame(
      title: l10n.authResetTitle,
      children: <Widget>[
        FutureBuilder<ResetLinkState>(
          future: _check,
          builder: (BuildContext context, AsyncSnapshot<ResetLinkState> snap) {
            if (snap.connectionState != ConnectionState.done) {
              return _Notice(l10n.authResetChecking);
            }
            if (snap.hasError) {
              return _Notice(
                friendlyApiError(context, snap.error!),
                danger: true,
              );
            }
            if (_done) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  _Notice(
                    l10n.authResetDone,
                    key: const ValueKey<String>('reset-done'),
                  ),
                  AstroButton(
                    label: l10n.authLogin,
                    onPressed: () => context.go(AppRoutes.login),
                  ),
                ],
              );
            }
            final ResetLinkState state = _failed ?? snap.requireData;
            if (state != ResetLinkState.valid) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  _Notice(
                    _stateText(l10n, state),
                    danger: true,
                    key: ValueKey<String>('reset-${state.name}'),
                  ),
                  AstroButton(
                    label: l10n.authResetRequestNew,
                    onPressed: () => context.go(AppRoutes.forgotPassword),
                  ),
                ],
              );
            }
            return Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: <Widget>[
                  if (_error != null) _Notice(_error!, danger: true),
                  AstroTextField(
                    controller: _password,
                    label: l10n.authResetNewPassword.toUpperCaseFor(
                      context.languageCode,
                    ),
                    obscureText: _obscure,
                    autofillHints: const <String>[AutofillHints.newPassword],
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
                    controller: _confirm,
                    label: l10n.authPasswordConfirm.toUpperCaseFor(
                      context.languageCode,
                    ),
                    obscureText: _obscure,
                    textInputAction: TextInputAction.done,
                    validator: (String? value) =>
                        validators.passwordConfirm(value, _password.text),
                    onFieldSubmitted: (_) => _submit(),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  AstroButton(
                    label: l10n.authResetSubmit,
                    isLoading: _busy,
                    onPressed: _submit,
                  ),
                ],
              ),
            );
          },
        ),
      ],
    );
  }
}
