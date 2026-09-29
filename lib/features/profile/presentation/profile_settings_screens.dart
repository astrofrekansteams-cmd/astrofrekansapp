import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/assets/app_assets.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/localization/locale_controller.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../../../core/config/firebase_client.dart';
import '../../auth/application/session_controller.dart';
import '../../consultation/data/push_service.dart';
import '../../production/application/action_state.dart';
import 'profile_widgets.dart';

/// Avatar, display name, bio, cover style and language.
class ProfileCustomizeScreen extends ConsumerStatefulWidget {
  const ProfileCustomizeScreen({super.key});
  @override
  ConsumerState<ProfileCustomizeScreen> createState() => _CustomizeState();
}

class _CustomizeState extends ConsumerState<ProfileCustomizeScreen> {
  final action = ActionState<bool>();
  late final user = ref.read(currentUserProvider);
  late final name = TextEditingController(text: user?.name ?? '');
  late final bio = TextEditingController(text: user?.bio ?? '');
  late String? avatar = user?.avatarPreset;
  late String cover = user?.coverTheme ?? 'cosmic_night';
  late String language = const {'tr', 'en'}.contains(user?.language)
      ? user!.language
      : ref.read(localeControllerProvider).languageCode;

  @override
  void dispose() {
    action.dispose();
    name.dispose();
    bio.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final ok = await action.run(() async {
      await ref.read(sessionProvider.notifier).customizeProfile({
        if (name.text.trim().length >= 2) 'name': name.text.trim(),
        'bio': bio.text.trim(),
        'avatar_preset': avatar ?? '',
        'cover_theme': cover,
        'language': language,
      });
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
      title: 'profile_customize',
      children: [
        AstroSectionTitle(title: b12(context, 'profile_avatar')),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            _AvatarChoice(
              key: const ValueKey('avatar-none'),
              selected: avatar == null,
              onTap: () => setState(() => avatar = null),
              child: Text(
                ref.read(currentUserProvider)?.initials ?? '?',
                style: AppTypography.titleMedium,
              ),
            ),
            for (final code in avatarPresets)
              _AvatarChoice(
                key: ValueKey('avatar-$code'),
                selected: avatar == code,
                onTap: () => setState(() => avatar = code),
                child: AstroImage(
                  AppAssets.zodiac[code]!,
                  width: 36,
                  height: 36,
                ),
              ),
          ],
        ),
        TextField(
          key: const ValueKey('profile-name'),
          controller: name,
          maxLength: 120,
          decoration: InputDecoration(
            labelText: b12(context, 'profile_display_name'),
          ),
        ),
        TextField(
          key: const ValueKey('profile-bio'),
          controller: bio,
          maxLength: 280,
          minLines: 2,
          maxLines: 4,
          decoration: InputDecoration(
            labelText: b12(context, 'profile_bio'),
            hintText: b12(context, 'profile_bio_hint'),
          ),
        ),
        AstroSectionTitle(title: b12(context, 'profile_cover')),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            for (final entry in coverThemes.entries)
              Semantics(
                button: true,
                selected: cover == entry.key,
                label: b12(context, 'cover_${entry.key}'),
                child: InkWell(
                  key: ValueKey('cover-${entry.key}'),
                  borderRadius: AppRadius.brMd,
                  onTap: () => setState(() => cover = entry.key),
                  child: Container(
                    width: 96,
                    height: 56,
                    alignment: Alignment.bottomLeft,
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      borderRadius: AppRadius.brMd,
                      gradient: LinearGradient(colors: entry.value),
                      border: Border.all(
                        color: cover == entry.key
                            ? AppColors.goldBright
                            : AppColors.hairline,
                        width: cover == entry.key ? 2 : 1,
                      ),
                    ),
                    child: Text(
                      b12(context, 'cover_${entry.key}'),
                      style: AppTypography.labelSmall,
                    ),
                  ),
                ),
              ),
          ],
        ),
        AstroSectionTitle(title: b12(context, 'profile_language')),
        AstroSegmentedControl<String>(
          segments: const [
            // Only languages with a complete translation. Azerbaijani returns
            // here with its app_az.arb.
            AstroSegment(value: 'tr', label: 'Türkçe'),
            AstroSegment(value: 'en', label: 'English'),
          ],
          selected: language,
          onChanged: (v) => setState(() => language = v),
        ),
        AstroButton(
          key: const ValueKey('profile-save'),
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

class _AvatarChoice extends StatelessWidget {
  const _AvatarChoice({
    super.key,
    required this.selected,
    required this.onTap,
    required this.child,
  });
  final bool selected;
  final VoidCallback onTap;
  final Widget child;
  @override
  Widget build(BuildContext context) => Semantics(
    button: true,
    selected: selected,
    child: InkWell(
      customBorder: const CircleBorder(),
      onTap: onTap,
      child: Container(
        width: 52,
        height: 52,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: AppColors.surface.withValues(alpha: 0.7),
          border: Border.all(
            color: selected ? AppColors.goldBright : AppColors.hairline,
            width: selected ? 2 : 1,
          ),
        ),
        child: child,
      ),
    ),
  );
}

/// A list of on/off preferences saved as one map on the profile.
class _FlagsScreen extends ConsumerStatefulWidget {
  const _FlagsScreen({
    required this.title,
    required this.field,
    required this.keys,
    required this.defaults,
    this.intro,
    this.footer,
  });
  final String title;
  final String field;
  final List<String> keys;
  final Map<String, bool> defaults;
  final String? intro;
  final Widget? footer;
  @override
  ConsumerState<_FlagsScreen> createState() => _FlagsState();
}

class _FlagsState extends ConsumerState<_FlagsScreen> {
  final action = ActionState<bool>();
  late final Map<String, bool> values = {
    ...widget.defaults,
    ...(widget.field == 'privacy'
            ? ref.read(currentUserProvider)?.privacy
            : ref.read(currentUserProvider)?.notificationPrefs) ??
        const {},
  };

  @override
  void dispose() {
    action.dispose();
    super.dispose();
  }

  /// The change that failed to save, offered again by "Tekrar Dene".
  (String, bool)? _failed;

  /// Optimistic: the switch moves at once. If the server does not save it,
  /// it goes back to what is actually stored and the error offers a retry -
  /// a switch that shows "off" must mean the server has it off.
  Future<void> _toggle(String key, bool value) async {
    final bool previous = values[key] ?? widget.defaults[key] ?? false;
    setState(() {
      values[key] = value;
      _failed = null;
    });
    final ok = await action.run(() async {
      await ref.read(sessionProvider.notifier).customizeProfile({
        widget.field: Map<String, bool>.of(values),
      });
      return true;
    });
    if (ok != true && mounted) {
      setState(() {
        values[key] = previous;
        _failed = (key, value);
      });
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: action,
    builder: (context, _) => CorePage(
      title: widget.title,
      children: [
        if (widget.intro != null)
          Text(b12(context, widget.intro!), style: AppTypography.bodySmall),
        AstroCard(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
          child: Column(
            children: [
              for (final key in widget.keys)
                SwitchListTile.adaptive(
                  key: ValueKey('flag-$key'),
                  title: Text(b12(context, '${widget.field}_$key')),
                  value: values[key] ?? false,
                  activeThumbColor: AppColors.gold,
                  onChanged: action.busy ? null : (v) => _toggle(key, v),
                ),
            ],
          ),
        ),
        if (action.value case final AsyncValue<bool> v when v.hasError)
          ApiStateView(
            key: const ValueKey('flag-save-error'),
            value: v,
            onRetry: switch (_failed) {
              (final String key, final bool value) => () => _toggle(key, value),
              null => null,
            },
            builder: (_) => const SizedBox.shrink(),
          ),
        ?widget.footer,
      ],
    ),
  );
}

/// Asks the OS for notification permission (the preferences above only say
/// what the server may send).
class _DevicePermissionButton extends ConsumerWidget {
  const _DevicePermissionButton();
  @override
  Widget build(BuildContext context, WidgetRef ref) => AstroOutlineButton(
    key: const ValueKey('device-permission'),
    label: b12(context, 'notifications_device_permission'),
    icon: Icons.notifications_active_outlined,
    onPressed: () async {
      final messenger = ScaffoldMessenger.of(context);
      final ok = b12(context, 'saved');
      final unavailable = b12(context, 'chat_unavailable');
      final available = await ref.read(firebaseBootstrapProvider.future);
      final granted =
          available.ready &&
          await ref.read(pushServiceProvider).requestPermissionExplicit();
      messenger.showSnackBar(
        SnackBar(content: Text(granted ? ok : unavailable)),
      );
    },
  );
}

class NotificationSettingsScreen extends StatelessWidget {
  const NotificationSettingsScreen({super.key});
  @override
  Widget build(BuildContext context) => const _FlagsScreen(
    title: 'profile_notifications',
    field: 'notification_prefs',
    intro: 'notifications_intro',
    footer: _DevicePermissionButton(),
    // Only switches the server honours when it sends (see the backend's
    // notification preferences). Incoming calls are never switchable.
    keys: [
      'daily_horoscope',
      'ai_reports',
      'expert_messages',
      'appointment_reminders',
      'promotions',
    ],
    defaults: {
      'daily_horoscope': true,
      'ai_reports': true,
      'expert_messages': true,
      'appointment_reminders': true,
      'promotions': false,
    },
  );
}

class PrivacySettingsScreen extends StatelessWidget {
  const PrivacySettingsScreen({super.key});
  @override
  Widget build(BuildContext context) => const _FlagsScreen(
    title: 'profile_privacy',
    field: 'privacy',
    intro: 'privacy_intro',
    keys: [
      'show_sun_sign',
      'show_moon_sign',
      'show_rising_sign',
      'show_birth_date',
      'show_bio',
    ],
    defaults: {
      'show_sun_sign': true,
      'show_moon_sign': true,
      'show_rising_sign': true,
      'show_birth_date': false,
      'show_bio': true,
    },
  );
}

/// App settings: notification preferences and the language (saved to the
/// account, so it follows the person to another device).
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final locale = ref.watch(localeControllerProvider);
    return CorePage(
      title: 'menu_settings',
      children: [
        AstroCard(
          padding: EdgeInsets.zero,
          child: ListTile(
            key: const ValueKey('settings-notification-prefs'),
            leading: const Icon(Icons.tune, color: AppColors.gold),
            title: Text(b12(context, 'profile_notifications')),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.push(AppRoutes.notificationSettings),
          ),
        ),
        AstroSectionTitle(title: b12(context, 'profile_language')),
        AstroSegmentedControl<String>(
          key: const ValueKey('settings-language'),
          segments: const [
            AstroSegment(value: 'tr', label: 'Türkçe'),
            AstroSegment(value: 'en', label: 'English'),
          ],
          selected: locale.languageCode,
          onChanged: (code) async {
            try {
              await ref
                  .read(sessionProvider.notifier)
                  .setLanguage(Locale(code));
            } on Object catch (error) {
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(friendlyApiError(context, error))),
                );
              }
            }
          },
        ),
      ],
    );
  }
}
