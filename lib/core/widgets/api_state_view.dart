import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../localization/b12_copy.dart';
import '../network/api_exception.dart';
import '../routing/app_routes.dart';
import '../../features/auth/domain/auth_repository.dart';
import '../theme/app_typography.dart';
import 'astro_buttons.dart';
import 'astro_card.dart';
import 'astro_scaffold.dart';
import 'astro_motion.dart';
import 'astro_skeleton.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';

String friendlyApiError(BuildContext context, Object error) {
  if (error is AuthException && error.kind == AuthFailureKind.notConfigured) {
    return b12(context, 'firebase_not_configured');
  }
  if (error is ApiException) {
    final key = switch (error.code) {
      'ai_not_configured' ||
      'firebase_not_configured' ||
      'birth_profile_missing' ||
      'missing_birth_data' ||
      'premium_required' ||
      'insufficient_coins' ||
      'demo_unavailable' => error.code!,
      'ai_rate_limited' || 'rate_limited' => 'rate_limited',
      'ai_provider_unavailable' ||
      'provider_unavailable' => 'provider_unavailable',
      'chat_not_available' ||
      'conversation_not_allowed' ||
      'firebase_identity_required' => 'chat_unavailable',
      'chat_read_only' => 'chat_read_only',
      'slot_unavailable' || 'slot_not_offered' => 'slot_unavailable',
      'slot_date_mismatch' => 'slot_date_mismatch',
      'idempotency_conflict' ||
      'message_conflict' ||
      'consumer_ref_conflict' => 'idempotency_conflict',
      'divination_session_expired' ||
      'session_already_completed' => error.code!,
      'attachment_too_large' ||
      'mime_type_not_allowed' ||
      'mime_type_forbidden' => 'attachment_invalid',
      'attachment_not_ready' || 'attachment_missing' => 'attachment_not_ready',
      _ => switch (error.kind) {
        ApiErrorKind.network => 'network',
        ApiErrorKind.timeout => 'timeout',
        ApiErrorKind.unauthorized => 'unauthorized',
        ApiErrorKind.notFound || ApiErrorKind.forbidden => 'not_found',
        ApiErrorKind.validation => 'validation',
        ApiErrorKind.rateLimited => 'rate_limited',
        _ => 'error',
      },
    };
    return b12(context, key);
  }
  return b12(context, 'error');
}

/// Loading / error / data for one async value, in the app's visual language.
///
/// Loading shows a branded skeleton (the screen may pass its own [loading]
/// shape); error shows an icon, a plain-language reason and "Tekrar dene".
/// Empty data is the builder's job, via [AstroEmptyState].
class ApiStateView<T> extends StatelessWidget {
  const ApiStateView({
    super.key,
    required this.value,
    required this.builder,
    this.onRetry,
    this.loading,
  });
  final AsyncValue<T> value;
  final Widget Function(T) builder;
  final VoidCallback? onRetry;
  final Widget? loading;
  @override
  Widget build(BuildContext context) => value.when(
    loading: () => loading ?? AstroSkeletonPage(label: b12(context, 'loading')),
    error: (e, s) => Semantics(
      liveRegion: true,
      child: needsBirthData(e)
          ? MissingBirthDataCard(
              message: friendlyApiError(context, e),
              onDone: onRetry,
            )
          : AstroErrorCard(
              message: friendlyApiError(context, e),
              onRetry: onRetry,
            ),
    ),
    data: (data) => _render(context, data),
  );

  /// A response that does not match what its screen reads is a contract
  /// bug: it is reported with its stack (never swallowed), and the section
  /// shows a calm error with a retry instead of a crash screen.
  Widget _render(BuildContext context, T data) {
    try {
      return builder(data);
    } catch (error, stack) {
      FlutterError.reportError(
        FlutterErrorDetails(
          exception: error,
          stack: stack,
          library: 'api_state_view',
          context: ErrorDescription('while rendering API data of type $T'),
        ),
      );
      return AstroErrorCard(
        message: b12(context, 'section_failed'),
        onRetry: onRetry,
      );
    }
  }
}

/// Stands in for a widget whose build threw, outside debug builds (see
/// `main`). Debug keeps Flutter's red screen for developers; the error is
/// still reported through [FlutterError.onError] either way.
class SectionFailedFallback extends StatelessWidget {
  const SectionFailedFallback({super.key});

  @override
  Widget build(BuildContext context) {
    final hasLocale = Localizations.maybeLocaleOf(context) != null;
    return Padding(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Center(
        child: Text(
          hasLocale ? b12(context, 'section_failed') : 'Bu bölüm yüklenemedi',
          textAlign: TextAlign.center,
          textDirection: TextDirection.ltr,
          style: AppTypography.bodyMedium.copyWith(color: AppColors.ivoryMuted),
        ),
      ),
    );
  }
}

/// The calculation needs birth data the account does not have (or not the
/// time of birth). Not a failure to retry: something the person can fill in.
bool needsBirthData(Object error) =>
    error is ApiException &&
    (error.code == 'missing_birth_data' ||
        error.code == 'birth_profile_missing');

/// Says what is missing and opens the birth-data form; when the person comes
/// back, the screen tries again.
class MissingBirthDataCard extends StatelessWidget {
  const MissingBirthDataCard({super.key, required this.message, this.onDone});
  final String message;
  final VoidCallback? onDone;

  @override
  Widget build(BuildContext context) => AstroCard(
    key: const ValueKey('missing-birth-data'),
    padding: const EdgeInsets.all(AppSpacing.xl),
    child: Column(
      children: [
        Container(
          width: 52,
          height: 52,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: AppColors.hairlineStrong),
          ),
          child: const Icon(
            Icons.schedule_outlined,
            color: AppColors.gold,
            size: 24,
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        Text(
          message,
          textAlign: TextAlign.center,
          style: AppTypography.bodyLarge.copyWith(color: AppColors.ivory),
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          b12(context, 'birth_data_needed_hint'),
          textAlign: TextAlign.center,
          style: AppTypography.bodySmall,
        ),
        const SizedBox(height: AppSpacing.lg),
        AstroButton(
          key: const ValueKey('complete-birth-data'),
          label: b12(context, 'complete_birth_data'),
          onPressed: () async {
            await context.push(AppRoutes.profileEdit);
            onDone?.call();
          },
        ),
      ],
    ),
  );
}

/// Error presentation shared by every API screen.
class AstroErrorCard extends StatelessWidget {
  const AstroErrorCard({super.key, required this.message, this.onRetry});
  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) => AstroCard(
    padding: const EdgeInsets.all(AppSpacing.xl),
    child: Column(
      children: [
        Container(
          width: 52,
          height: 52,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: AppColors.hairlineStrong),
          ),
          child: const Icon(
            Icons.cloud_off_outlined,
            color: AppColors.gold,
            size: 24,
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        Text(
          message,
          textAlign: TextAlign.center,
          style: AppTypography.bodyLarge.copyWith(color: AppColors.ivory),
        ),
        if (onRetry != null) ...[
          const SizedBox(height: AppSpacing.lg),
          AstroOutlineButton(
            label: b12(context, 'retry'),
            onPressed: onRetry,
            expand: false,
          ),
        ],
      ],
    ),
  );
}

class CorePage extends StatelessWidget {
  const CorePage({super.key, required this.title, required this.children});
  final String title;
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => AstroScaffold(
    body: ListView(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.pageGutter(MediaQuery.sizeOf(context).width) + 4,
        AppSpacing.md,
        AppSpacing.pageGutter(MediaQuery.sizeOf(context).width) + 4,
        AppSpacing.huge + MediaQuery.paddingOf(context).bottom,
      ),
      children: [
        Row(
          children: [
            IconButton.outlined(
              tooltip: b12(context, 'back'),
              onPressed: () => Navigator.maybePop(context),
              icon: const Icon(Icons.arrow_back),
            ),
            Expanded(
              child: Semantics(
                header: true,
                child: Text(
                  b12(context, title),
                  textAlign: TextAlign.center,
                  style: AppTypography.headlineLarge,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
            const SizedBox(width: 48),
          ],
        ),
        const Padding(
          padding: EdgeInsets.symmetric(vertical: AppSpacing.lg),
          child: Row(
            children: [
              Expanded(child: Divider(color: AppColors.hairline)),
              Padding(
                padding: EdgeInsets.symmetric(horizontal: 16),
                child: Icon(
                  Icons.auto_awesome,
                  size: 18,
                  color: AppColors.gold,
                ),
              ),
              Expanded(child: Divider(color: AppColors.hairline)),
            ],
          ),
        ),
        for (int i = 0; i < children.length; i++)
          AstroReveal(
            order: i,
            child: Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.cardGap),
              child: children[i],
            ),
          ),
      ],
    ),
  );
}

class FactSection extends StatelessWidget {
  const FactSection({super.key, required this.title, required this.lines});
  final String title;
  final List<String> lines;
  @override
  Widget build(BuildContext context) => AstroCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(
          header: true,
          child: Text(b12(context, title), style: AppTypography.headlineMedium),
        ),
        const SizedBox(height: 10),
        for (final line in lines)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Text(line, style: AppTypography.bodyMedium),
          ),
        if (lines.isEmpty) Text(b12(context, 'empty')),
      ],
    ),
  );
}

class SourceFactors extends StatelessWidget {
  const SourceFactors({
    super.key,
    required this.factors,
    this.availableOnly = false,
  });
  final Map<String, String> factors;
  final bool availableOnly;
  @override
  Widget build(BuildContext context) => FactSection(
    title: availableOnly ? 'available_sources' : 'sources',
    lines: factors.entries
        .map((e) => e.value.isEmpty ? e.key : '${e.value} · ${e.key}')
        .toList(),
  );
}
