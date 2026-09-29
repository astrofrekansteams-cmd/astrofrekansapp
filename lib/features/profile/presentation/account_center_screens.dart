import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/astrology/data/production_models.dart';
import '../../../core/astrology/data/production_repository.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../../auth/application/session_controller.dart';
import '../../production/application/action_state.dart';
import '../data/account_repository.dart';

final passwordCapabilityProvider =
    FutureProvider.autoDispose<PasswordCapability>(
      (ref) => ref.watch(accountRepositoryProvider).passwordCapability(),
    );

/// "Google ile giriş yapıyorsun; şifren Google hesabında yönetilir."
String providerPasswordNote(BuildContext context, String? provider) =>
    b12(context, 'password_external_note').replaceAll(
      '{provider}',
      switch (provider) {
        'google.com' => 'Google',
        'apple.com' => 'Apple',
        _ => b12(context, 'password_external_provider'),
      },
    );

/// One row of a settings list.
class AccountRow extends StatelessWidget {
  const AccountRow({
    super.key,
    required this.icon,
    required this.label,
    required this.onTap,
    this.subtitle,
    this.destructive = false,
  });
  final IconData icon;
  final String label;
  final String? subtitle;
  final VoidCallback onTap;
  final bool destructive;
  @override
  Widget build(BuildContext context) => ListTile(
    minTileHeight: AppSpacing.minTapTarget + 16,
    shape: const Border(
      bottom: BorderSide(color: AppColors.hairline, width: .5),
    ),
    leading: Icon(
      icon,
      color: destructive ? AppColors.danger : AppColors.gold,
      size: 24,
    ),
    title: Text(
      label,
      style: AppTypography.titleMedium.copyWith(
        color: destructive ? AppColors.danger : null,
      ),
    ),
    subtitle: subtitle == null
        ? null
        : Text(subtitle!, style: AppTypography.bodySmall),
    trailing: const Icon(Icons.chevron_right, color: AppColors.ivoryMuted),
    onTap: onTap,
  );
}

/// Everything about the account itself, in one place.
class AccountCenterScreen extends ConsumerWidget {
  const AccountCenterScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    return CorePage(
      title: 'account_center',
      children: [
        if (user != null) Text(user.email, style: AppTypography.bodySmall),
        AstroCard(
          padding: EdgeInsets.zero,
          child: Column(
            children: [
              AccountRow(
                key: const ValueKey('account-info'),
                icon: Icons.person_outline,
                label: b12(context, 'account_info'),
                subtitle: b12(context, 'account_info_sub'),
                onTap: () => context.push(AppRoutes.accountInfo),
              ),
              AccountRow(
                key: const ValueKey('account-birth'),
                icon: Icons.nightlight_outlined,
                label: b12(context, 'birth_data_title'),
                subtitle: b12(context, 'birth_data_sub'),
                onTap: () => context.push(AppRoutes.profileEdit),
              ),
              // Only where there is a password to change; a Google/Apple
              // account is told where its sign-in is managed instead.
              switch (ref.watch(passwordCapabilityProvider).asData?.value) {
                PasswordCapability(canChange: false, :final provider) =>
                  AccountRow(
                    key: const ValueKey('account-password'),
                    icon: Icons.lock_outline,
                    label: b12(context, 'change_password'),
                    subtitle: providerPasswordNote(context, provider),
                    onTap: () => showDialog<void>(
                      context: context,
                      builder: (dialogContext) => AlertDialog(
                        content: Text(
                          providerPasswordNote(dialogContext, provider),
                        ),
                        actions: [
                          TextButton(
                            onPressed: () => Navigator.pop(dialogContext),
                            child: Text(b12(dialogContext, 'ok')),
                          ),
                        ],
                      ),
                    ),
                  ),
                _ => AccountRow(
                  key: const ValueKey('account-password'),
                  icon: Icons.lock_outline,
                  label: b12(context, 'change_password'),
                  onTap: () => context.push(AppRoutes.changePassword),
                ),
              },
              AccountRow(
                key: const ValueKey('account-sessions'),
                icon: Icons.devices_outlined,
                label: b12(context, 'sessions_title'),
                onTap: () => context.push(AppRoutes.accountSessions),
              ),
              AccountRow(
                key: const ValueKey('account-privacy'),
                icon: Icons.shield_outlined,
                label: b12(context, 'privacy_security'),
                onTap: () => context.push(AppRoutes.privacySettings),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        AstroCard(
          padding: EdgeInsets.zero,
          child: AccountRow(
            key: const ValueKey('account-delete'),
            icon: Icons.delete_forever_outlined,
            label: b12(context, 'delete_account'),
            destructive: true,
            onTap: () => context.push(AppRoutes.deleteAccount),
          ),
        ),
      ],
    );
  }
}

// ============================================================ account info

/// Name, language and where the person lives now. The birth chart is not
/// affected by any of these.
class AccountInfoScreen extends ConsumerStatefulWidget {
  const AccountInfoScreen({super.key});
  @override
  ConsumerState<AccountInfoScreen> createState() => _AccountInfoState();
}

class _AccountInfoState extends ConsumerState<AccountInfoScreen> {
  final action = ActionState<bool>();
  late final user = ref.read(currentUserProvider);
  late final name = TextEditingController(text: user?.name ?? '');
  final place = TextEditingController();
  late String? timezone = user?.timezone;
  late String language = const {'tr', 'en'}.contains(user?.language)
      ? user!.language
      : 'tr';
  Timer? _debounce;
  int _seq = 0;
  List<GeoPlace> results = const [];
  bool searching = false;

  @override
  void dispose() {
    _debounce?.cancel();
    action.dispose();
    name.dispose();
    place.dispose();
    super.dispose();
  }

  void _search(String text) {
    _debounce?.cancel();
    if (text.trim().length < 2) {
      setState(() => results = const []);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 400), () async {
      final repo = ref.read(productionRepositoryProvider);
      if (repo == null) return;
      final seq = ++_seq;
      setState(() => searching = true);
      try {
        final found = await repo.geocode(text.trim());
        if (mounted && seq == _seq) {
          setState(
            () => results = found.where((p) => p.timezone != null).toList(),
          );
        }
      } on Object {
        if (mounted && seq == _seq) setState(() => results = const []);
      } finally {
        if (mounted && seq == _seq) setState(() => searching = false);
      }
    });
  }

  Future<void> _save() async {
    final ok = await action.run(() async {
      final session = ref.read(sessionProvider.notifier);
      await session.customizeProfile({
        if (name.text.trim().length >= 2) 'name': name.text.trim(),
        'timezone': ?timezone,
      });
      await session.setLanguage(Locale(language));
      return true;
    });
    if (ok == true && mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(b12(context, 'saved'))));
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: action,
    builder: (context, _) => CorePage(
      title: 'account_info',
      children: [
        TextField(
          key: const ValueKey('account-name'),
          controller: name,
          maxLength: 120,
          decoration: InputDecoration(
            labelText: b12(context, 'profile_display_name'),
          ),
        ),
        Text(
          '${b12(context, 'email')}: ${user?.email ?? '—'}',
          style: AppTypography.bodySmall,
        ),
        const SizedBox(height: AppSpacing.md),
        AstroSectionTitle(title: b12(context, 'current_timezone')),
        Text(
          timezone ?? '—',
          key: const ValueKey('current-timezone'),
          style: AppTypography.titleMedium,
        ),
        Text(
          b12(context, 'current_timezone_note'),
          style: AppTypography.bodySmall,
        ),
        TextField(
          key: const ValueKey('timezone-search'),
          controller: place,
          onChanged: _search,
          decoration: InputDecoration(
            prefixIcon: const Icon(Icons.location_city_outlined),
            labelText: b12(context, 'current_city_search'),
            suffixIcon: searching ? const AstroLoading(size: 20) : null,
          ),
        ),
        for (final result in results)
          ListTile(
            key: ValueKey('tz-${result.displayName}'),
            dense: true,
            title: Text(result.displayName),
            subtitle: Text(result.timezone!),
            onTap: () => setState(() {
              timezone = result.timezone;
              results = const [];
              place.text = result.displayName;
            }),
          ),
        const SizedBox(height: AppSpacing.md),
        AstroSectionTitle(title: b12(context, 'profile_language')),
        AstroSegmentedControl<String>(
          segments: const [
            AstroSegment(value: 'tr', label: 'Türkçe'),
            AstroSegment(value: 'en', label: 'English'),
          ],
          selected: language,
          onChanged: (v) => setState(() => language = v),
        ),
        const SizedBox(height: AppSpacing.lg),
        AstroButton(
          key: const ValueKey('account-info-save'),
          label: b12(context, 'save'),
          isLoading: action.busy,
          onPressed: action.busy ? null : _save,
        ),
        if (action.value case final AsyncValue<bool> v when v.hasError)
          ApiStateView(value: v, builder: (_) => const SizedBox.shrink()),
      ],
    ),
  );
}

// ======================================================== change password

class ChangePasswordScreen extends ConsumerStatefulWidget {
  const ChangePasswordScreen({super.key});
  @override
  ConsumerState<ChangePasswordScreen> createState() => _ChangePasswordState();
}

class _ChangePasswordState extends ConsumerState<ChangePasswordScreen> {
  final _form = GlobalKey<FormState>();
  final current = TextEditingController();
  final next = TextEditingController();
  final confirm = TextEditingController();
  bool busy = false, obscure = true, done = false;
  String? error;

  @override
  void dispose() {
    current.dispose();
    next.dispose();
    confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_form.currentState?.validate() ?? false)) return;
    FocusScope.of(context).unfocus();
    final user = ref.read(currentUserProvider);
    if (user == null) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final revoked = await ref
          .read(accountRepositoryProvider)
          .changePassword(
            current: current.text,
            next: next.text,
            email: user.email,
          );
      await ref
          .read(sessionProvider.notifier)
          .afterPasswordChange(
            sessionsRevoked: revoked,
            newPassword: next.text,
          );
      if (mounted) setState(() => done = true);
    } on PasswordChangeException catch (e) {
      if (mounted) {
        setState(
          () => error = b12(context, switch (e.reason) {
            PasswordChangeFailure.wrongCurrent => 'password_wrong_current',
            PasswordChangeFailure.weak => 'password_weak',
            PasswordChangeFailure.rateLimited => 'rate_limited',
            PasswordChangeFailure.needsRecentLogin => 'password_recent_login',
            PasswordChangeFailure.network => 'network',
            PasswordChangeFailure.unsupported => 'password_change_unsupported',
          }),
        );
      }
    } on Object catch (e) {
      if (mounted) setState(() => error = friendlyApiError(context, e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    InputDecoration field(String key) => InputDecoration(
      labelText: b12(context, key),
      suffixIcon: IconButton(
        onPressed: () => setState(() => obscure = !obscure),
        icon: Icon(
          obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined,
        ),
      ),
    );
    return CorePage(
      title: 'change_password',
      children: [
        if (ref.watch(passwordCapabilityProvider).asData?.value
            case PasswordCapability(canChange: false, :final provider))
          AstroCard(
            key: const ValueKey('password-external'),
            child: Text(providerPasswordNote(context, provider)),
          )
        else if (done)
          AstroCard(
            key: const ValueKey('password-changed'),
            child: Text(b12(context, 'password_changed')),
          )
        else
          Form(
            key: _form,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  b12(context, 'password_change_note'),
                  style: AppTypography.bodySmall,
                ),
                TextFormField(
                  key: const ValueKey('password-current'),
                  controller: current,
                  obscureText: obscure,
                  autofillHints: const [AutofillHints.password],
                  decoration: field('password_current'),
                  validator: (v) =>
                      (v ?? '').isEmpty ? b12(context, 'validation') : null,
                ),
                TextFormField(
                  key: const ValueKey('password-new'),
                  controller: next,
                  obscureText: obscure,
                  autofillHints: const [AutofillHints.newPassword],
                  decoration: field('password_new'),
                  validator: (v) {
                    final text = v ?? '';
                    if (text.length < 8) return b12(context, 'password_min');
                    if (text.trim() != text) {
                      return b12(context, 'password_spaces');
                    }
                    if (text == current.text) {
                      return b12(context, 'password_same');
                    }
                    return null;
                  },
                ),
                TextFormField(
                  key: const ValueKey('password-confirm'),
                  controller: confirm,
                  obscureText: obscure,
                  decoration: field('password_repeat'),
                  validator: (v) =>
                      v != next.text ? b12(context, 'password_mismatch') : null,
                  onFieldSubmitted: (_) => _submit(),
                ),
                if (error != null)
                  Padding(
                    padding: const EdgeInsets.only(top: AppSpacing.sm),
                    child: Text(
                      error!,
                      key: const ValueKey('password-error'),
                      style: const TextStyle(color: AppColors.danger),
                    ),
                  ),
                const SizedBox(height: AppSpacing.md),
                AstroButton(
                  key: const ValueKey('password-submit'),
                  label: b12(context, 'change_password'),
                  isLoading: busy,
                  onPressed: busy ? null : _submit,
                ),
              ],
            ),
          ),
      ],
    );
  }
}

// ============================================================== sessions

final _sessionsProvider = FutureProvider.autoDispose<List<AccountSession>>(
  (ref) => ref.watch(accountRepositoryProvider).sessions(),
);
final _devicesProvider = FutureProvider.autoDispose<List<AccountDevice>>(
  (ref) => ref.watch(accountRepositoryProvider).devices(),
);

String _providerName(BuildContext context, String? provider) =>
    switch (provider) {
      'password' => b12(context, 'sessions_provider_password'),
      'google.com' => 'Google',
      'apple.com' => 'Apple',
      _ => provider ?? '',
    };

String _agent(BuildContext context, String? raw) {
  if (raw == null || raw.isEmpty) return '—';
  // The app's own HTTP client identifies itself as Dart's.
  if (raw.contains('dart:io') || raw.startsWith('Dart/')) {
    return b12(context, 'session_this_app');
  }
  final paren = RegExp(r'\(([^)]+)\)').firstMatch(raw)?.group(1);
  return paren ?? (raw.length > 48 ? '${raw.substring(0, 48)}…' : raw);
}

class SessionsScreen extends ConsumerWidget {
  const SessionsScreen({super.key});

  Future<void> _run(
    BuildContext context,
    WidgetRef ref,
    Future<void> Function() action,
  ) async {
    try {
      await action();
      ref
        ..invalidate(_sessionsProvider)
        ..invalidate(_devicesProvider);
    } on Object catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(friendlyApiError(context, e))));
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final language = Localizations.localeOf(context).toLanguageTag();
    String when(DateTime? t) =>
        t == null ? '—' : DateFormat('d MMM y, HH:mm', language).format(t);
    final repo = ref.read(accountRepositoryProvider);
    return CorePage(
      title: 'sessions_title',
      children: [
        AstroSectionTitle(title: b12(context, 'sessions_signed_in')),
        ApiStateView(
          value: ref.watch(_sessionsProvider),
          onRetry: () => ref.invalidate(_sessionsProvider),
          builder: (sessions) => Column(
            children: [
              if (sessions.isEmpty) Text(b12(context, 'sessions_none')),
              if (sessions.any((s) => s.isFirebase))
                Padding(
                  key: const ValueKey('sessions-firebase-note'),
                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                  child: Text(
                    b12(context, 'sessions_firebase_note'),
                    style: AppTypography.bodySmall,
                  ),
                ),
              for (final s in sessions)
                AstroCard(
                  key: ValueKey('session-${s.id}'),
                  child: ListTile(
                    leading: Icon(
                      s.isFirebase
                          ? Icons.verified_user_outlined
                          : Icons.phone_iphone,
                      color: AppColors.gold,
                    ),
                    title: Text(
                      s.isFirebase
                          ? '${b12(context, 'sessions_firebase')}'
                                '${s.signInProvider == null ? '' : ' · ${_providerName(context, s.signInProvider)}'}'
                          : _agent(context, s.userAgent),
                    ),
                    subtitle: Text(
                      '${s.current ? '${b12(context, 'sessions_this_device')} · ' : ''}'
                      '${s.isFirebase ? '${b12(context, 'sessions_firebase_managed')} · ' : ''}'
                      '${b12(context, s.isFirebase ? 'sessions_signed_in_at' : 'sessions_last_used')}: '
                      '${when(s.isFirebase ? s.createdAt : s.lastUsedAt)}'
                      '${s.ipHint == null ? '' : ' · ${s.ipHint}'}',
                    ),
                    trailing: s.current || !s.revocable
                        ? null
                        : TextButton(
                            key: ValueKey('revoke-${s.id}'),
                            onPressed: () => _run(
                              context,
                              ref,
                              () => repo.revokeSession(s.id),
                            ),
                            child: Text(b12(context, 'sessions_sign_out')),
                          ),
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        AstroSectionTitle(title: b12(context, 'devices_title')),
        ApiStateView(
          value: ref.watch(_devicesProvider),
          onRetry: () => ref.invalidate(_devicesProvider),
          builder: (devices) => Column(
            children: [
              if (devices.where((d) => d.enabled).isEmpty)
                Text(b12(context, 'devices_none')),
              for (final d in devices.where((d) => d.enabled))
                AstroCard(
                  key: ValueKey('device-${d.id}'),
                  child: ListTile(
                    leading: Icon(
                      d.platform == 'ios'
                          ? Icons.phone_iphone
                          : Icons.phone_android,
                      color: AppColors.gold,
                    ),
                    title: Text(
                      '${d.platform.toUpperCase()}${d.appVersion == null ? '' : ' · ${d.appVersion}'}',
                    ),
                    subtitle: Text(
                      '${b12(context, 'sessions_last_used')}: ${when(d.lastSeenAt)}',
                    ),
                    trailing: TextButton(
                      onPressed: () =>
                          _run(context, ref, () => repo.removeDevice(d.id)),
                      child: Text(b12(context, 'devices_remove')),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

// ========================================================= delete account

final _deletionCheckProvider = FutureProvider.autoDispose<DeletionCheck>(
  (ref) => ref.watch(accountRepositoryProvider).deletionCheck(),
);

class DeleteAccountScreen extends ConsumerStatefulWidget {
  const DeleteAccountScreen({super.key});
  @override
  ConsumerState<DeleteAccountScreen> createState() => _DeleteAccountState();
}

class _DeleteAccountState extends ConsumerState<DeleteAccountScreen> {
  final secret = TextEditingController();
  bool understood = false, busy = false;
  String? error;

  @override
  void dispose() {
    secret.dispose();
    super.dispose();
  }

  Future<void> _delete(DeletionCheck check) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        key: const ValueKey('delete-confirm-dialog'),
        title: Text(b12(dialogContext, 'delete_account')),
        content: Text(b12(dialogContext, 'delete_account_final')),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: Text(b12(dialogContext, 'cancel_keep')),
          ),
          FilledButton(
            key: const ValueKey('delete-confirm-yes'),
            style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () => Navigator.pop(dialogContext, true),
            child: Text(b12(dialogContext, 'delete_account')),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await ref
          .read(accountRepositoryProvider)
          .deleteAccount(
            password: check.requiresPassword ? secret.text : null,
            confirmEmail: check.requiresPassword ? null : secret.text.trim(),
          );
      await ref.read(sessionProvider.notifier).afterAccountDeleted();
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        error = switch (e.code) {
          'current_password_incorrect' ||
          'invalid_credentials' => b12(context, 'password_wrong_current'),
          'deletion_confirmation_required' => b12(
            context,
            'delete_email_mismatch',
          ),
          'account_has_active_services' => b12(context, 'delete_blocked'),
          _ => friendlyApiError(context, e),
        };
      });
      ref.invalidate(_deletionCheckProvider);
    } on Object catch (e) {
      if (mounted) setState(() => error = friendlyApiError(context, e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => CorePage(
    title: 'delete_account',
    children: [
      ApiStateView(
        value: ref.watch(_deletionCheckProvider),
        onRetry: () => ref.invalidate(_deletionCheckProvider),
        builder: (check) {
          if (!check.allowed) {
            return AstroCard(
              key: const ValueKey('delete-blocked'),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(b12(context, 'delete_blocked')),
                  const SizedBox(height: AppSpacing.sm),
                  if (check.liveAppointments > 0)
                    Text(
                      '• ${b12(context, 'delete_blocked_appointments').replaceAll('{n}', '${check.liveAppointments}')}',
                    ),
                  if (check.openOrders > 0)
                    Text(
                      '• ${b12(context, 'delete_blocked_orders').replaceAll('{n}', '${check.openOrders}')}',
                    ),
                  if (check.openRefunds > 0)
                    Text(
                      '• ${b12(context, 'delete_blocked_refunds').replaceAll('{n}', '${check.openRefunds}')}',
                    ),
                  if (check.expertOpenOrders > 0)
                    Text(
                      '• ${b12(context, 'delete_blocked_expert').replaceAll('{n}', '${check.expertOpenOrders}')}',
                    ),
                  const SizedBox(height: AppSpacing.sm),
                  Wrap(
                    spacing: AppSpacing.sm,
                    children: [
                      OutlinedButton(
                        onPressed: () => context.push(AppRoutes.appointments),
                        child: Text(b12(context, 'appointments')),
                      ),
                      OutlinedButton(
                        onPressed: () => context.push(AppRoutes.orders),
                        child: Text(b12(context, 'orders')),
                      ),
                    ],
                  ),
                ],
              ),
            );
          }
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(b12(context, 'delete_account_intro')),
              const SizedBox(height: AppSpacing.md),
              TextField(
                key: const ValueKey('delete-secret'),
                controller: secret,
                obscureText: check.requiresPassword,
                keyboardType: check.requiresPassword
                    ? TextInputType.visiblePassword
                    : TextInputType.emailAddress,
                onChanged: (_) => setState(() {}),
                decoration: InputDecoration(
                  labelText: b12(
                    context,
                    check.requiresPassword
                        ? 'password_current'
                        : 'delete_type_email',
                  ),
                ),
              ),
              CheckboxListTile(
                key: const ValueKey('delete-understood'),
                value: understood,
                onChanged: (v) => setState(() => understood = v ?? false),
                title: Text(b12(context, 'delete_understood')),
                controlAffinity: ListTileControlAffinity.leading,
              ),
              if (error != null)
                Text(
                  error!,
                  key: const ValueKey('delete-error'),
                  style: const TextStyle(color: AppColors.danger),
                ),
              const SizedBox(height: AppSpacing.md),
              FilledButton(
                key: const ValueKey('delete-submit'),
                style: FilledButton.styleFrom(
                  backgroundColor: AppColors.danger,
                ),
                onPressed: busy || !understood || secret.text.trim().isEmpty
                    ? null
                    : () => _delete(check),
                child: Text(b12(context, 'delete_account')),
              ),
            ],
          );
        },
      ),
    ],
  );
}
