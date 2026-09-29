import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/assets/app_assets.dart';
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
import '../../../core/widgets/api_state_view.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _email = TextEditingController();
  final TextEditingController _password = TextEditingController();

  bool _busy = false;
  bool _obscure = true;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
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
          .read(sessionProvider.notifier)
          .signIn(email: _email.text, password: _password.text);
      // Routing redirect takes over once the session flips to authenticated.
    } on AuthException catch (error) {
      if (!mounted) return;
      setState(
        () => _error = error.kind == AuthFailureKind.notConfigured
            ? friendlyApiError(context, error)
            : _messageFor(error.kind, context.l10n),
      );
    } on Object {
      if (!mounted) return;
      setState(() => _error = context.l10n.errorGeneric);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  static String _messageFor(AuthFailureKind kind, AppLocalizations l10n) =>
      switch (kind) {
        AuthFailureKind.invalidCredentials => l10n.authInvalidCredentials,
        AuthFailureKind.emailInUse => l10n.authEmailInUse,
        AuthFailureKind.network => l10n.errorNetwork,
        AuthFailureKind.notConfigured => l10n.authSocialSoon,
        AuthFailureKind.unknown => l10n.errorGeneric,
      };

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;
    final AuthValidators validators = AuthValidators(l10n);

    return AstroScaffold(
      backgroundAsset: AppAssets.loginBackground,
      backgroundAspectRatio: 941 / 1672,
      scrimOpacity: 0.44,
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: AppSpacing.contentMaxWidth,
          ),
          child: SingleChildScrollView(
            padding: EdgeInsets.fromLTRB(
              context.gutter + AppSpacing.sm,
              AppSpacing.lg,
              context.gutter + AppSpacing.sm,
              AppSpacing.xxl,
            ),
            child: Form(
              key: _formKey,
              child: AutofillGroup(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    Row(
                      children: <Widget>[
                        AstroIconButton(
                          icon: Icons.arrow_back,
                          semanticLabel: l10n.commonBack,
                          onPressed: () => context.go(AppRoutes.onboarding),
                        ),
                        const Spacer(),
                        if (ref.watch(showDemoNoticeProvider))
                          AstroBadge(label: l10n.commonDemoMode),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.xxl),
                    const Center(
                      child: AstroReveal(child: AstroBrandLogo(width: 190)),
                    ),
                    const SizedBox(height: AppSpacing.xl),
                    Text(
                      l10n.authLoginTitle,
                      textAlign: TextAlign.center,
                      style: AppTypography.displayMedium.copyWith(fontSize: 30),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Text(
                      l10n.authLoginSubtitle,
                      textAlign: TextAlign.center,
                      style: AppTypography.bodyMedium,
                    ),
                    const SizedBox(height: AppSpacing.xxl),
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
                      textInputAction: TextInputAction.done,
                      autofillHints: const <String>[AutofillHints.password],
                      validator: validators.password,
                      onFieldSubmitted: (_) => _submit(),
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
                    if (_error != null)
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.md),
                        child: Text(
                          _error!,
                          style: AppTypography.bodySmall.copyWith(
                            color: AppColors.danger,
                          ),
                        ),
                      ),
                    Align(
                      alignment: AlignmentDirectional.centerEnd,
                      child: TextButton(
                        onPressed: () => context.push(AppRoutes.forgotPassword),
                        style: TextButton.styleFrom(
                          foregroundColor: AppColors.ivoryMuted,
                          minimumSize: const Size(0, AppSpacing.minTapTarget),
                        ),
                        child: Text(
                          l10n.authForgotPassword,
                          style: AppTypography.labelMedium,
                        ),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    AstroButton(
                      label: l10n.authLogin,
                      isLoading: _busy,
                      onPressed: _submit,
                    ),
                    const SizedBox(height: AppSpacing.xl),
                    const SocialAuthRow(),
                    const SizedBox(height: AppSpacing.xl),
                    Wrap(
                      alignment: WrapAlignment.center,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: <Widget>[
                        Text(
                          l10n.authNoAccount,
                          style: AppTypography.bodySmall,
                        ),
                        TextButton(
                          onPressed: () => context.go(AppRoutes.register),
                          style: TextButton.styleFrom(
                            foregroundColor: AppColors.gold,
                            minimumSize: const Size(0, AppSpacing.minTapTarget),
                          ),
                          child: Text(
                            l10n.authRegister,
                            style: AppTypography.labelMedium.copyWith(
                              color: AppColors.gold,
                            ),
                          ),
                        ),
                      ],
                    ),
                    if (ref.watch(showDemoNoticeProvider)) ...<Widget>[
                      const SizedBox(height: AppSpacing.sm),
                      Text(
                        l10n.commonDemoNotice,
                        textAlign: TextAlign.center,
                        style: AppTypography.bodySmall.copyWith(fontSize: 12),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
