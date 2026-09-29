import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../../core/assets/app_assets.dart';
import '../../../../core/astrology/domain/transit.dart';
import '../../../../core/extensions/context_extensions.dart';
import '../../../../core/localization/astro_labels.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/typewriter_text.dart';
import '../../../../core/widgets/typing_dots.dart';
import '../../../../core/widgets/widgets.dart';
import '../../domain/chat_message.dart';
import '../../../../core/localization/b12_copy.dart';

/// User / Astro AI message bubble, with the influence strip under AI answers.
///
/// An answer that arrives while the person watches types itself out at a
/// steady pace, whatever the size of the network chunks; an answer that was
/// already there (an opened conversation) is shown whole.
class ChatBubble extends StatefulWidget {
  const ChatBubble({required this.message, super.key});

  final ChatMessage message;

  @override
  State<ChatBubble> createState() => _ChatBubbleState();
}

class _ChatBubbleState extends State<ChatBubble> {
  /// True when this bubble was first built while its answer was still coming.
  late final bool _arrivedLive =
      widget.message.status == ChatMessageStatus.streaming;

  @override
  Widget build(BuildContext context) {
    final ChatMessage message = widget.message;
    final bool isUser = message.isUser;
    final String time = DateFormat.Hm(
      context.languageCode,
    ).format(message.createdAt);

    final Widget bubble = Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.sizeOf(context).width * 0.78,
      ),
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        AppSpacing.md,
        AppSpacing.lg,
        AppSpacing.sm,
      ),
      decoration: BoxDecoration(
        color: isUser
            ? AppColors.navySoft.withValues(alpha: 0.92)
            : AppColors.surface.withValues(alpha: 0.92),
        borderRadius: BorderRadius.only(
          topLeft: const Radius.circular(AppRadius.lg),
          topRight: const Radius.circular(AppRadius.lg),
          bottomLeft: Radius.circular(isUser ? AppRadius.lg : AppRadius.xs),
          bottomRight: Radius.circular(isUser ? AppRadius.xs : AppRadius.lg),
        ),
        border: Border.all(
          color: isUser ? AppColors.hairline : AppColors.hairlineStrong,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          if (message.status == ChatMessageStatus.cancelled ||
              message.status == ChatMessageStatus.partial)
            Text(
              b12(context, message.status.name),
              style: AppTypography.bodySmall,
            ),
          if (message.text.isNotEmpty)
            if (isUser)
              Text(
                message.text,
                style: AppTypography.bodyLarge.copyWith(height: 1.55),
              )
            else
              TypewriterText(
                message.text,
                key: const ValueKey('ai-answer-text'),
                instant: !_arrivedLive,
                charactersPerSecond: 80,
                showCaret: message.status == ChatMessageStatus.streaming,
                style: AppTypography.bodyLarge.copyWith(height: 1.55),
              ),
          if (message.status == ChatMessageStatus.streaming &&
              message.text.isEmpty)
            const TypingDots(key: ValueKey('ai-typing-dots')),
          const SizedBox(height: AppSpacing.xs),
          Align(
            alignment: AlignmentDirectional.centerEnd,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Text(
                  time,
                  style: AppTypography.bodySmall.copyWith(fontSize: 12),
                ),
                if (isUser) ...<Widget>[
                  const SizedBox(width: AppSpacing.xs),
                  Icon(
                    message.status == ChatMessageStatus.failed
                        ? Icons.error_outline
                        : Icons.done_all,
                    size: 13,
                    color: message.status == ChatMessageStatus.failed
                        ? AppColors.danger
                        : AppColors.ivoryMuted,
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Column(
        crossAxisAlignment: isUser
            ? CrossAxisAlignment.end
            : CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            mainAxisAlignment: isUser
                ? MainAxisAlignment.end
                : MainAxisAlignment.start,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              if (!isUser) ...<Widget>[
                const AstroAvatar(
                  size: 40,
                  assetPath: AppAssets.astroAiAvatar,
                  glow: false,
                ),
                const SizedBox(width: AppSpacing.sm),
              ],
              Flexible(child: bubble),
              if (isUser) ...<Widget>[
                const SizedBox(width: AppSpacing.sm),
                Container(
                  width: 40,
                  height: 40,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppColors.surfaceMuted,
                  ),
                  child: const Icon(
                    Icons.person_outline,
                    size: 20,
                    color: AppColors.ivoryMuted,
                  ),
                ),
              ],
            ],
          ),
          if (!isUser && message.influences.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.lg),
              child: InfluenceStrip(influences: message.influences),
            ),
        ],
      ),
    );
  }
}

/// "Bu yorumu oluşturan etkiler" - what shaped the answer.
class InfluenceStrip extends StatelessWidget {
  const InfluenceStrip({required this.influences, super.key});

  final List<TransitSummary> influences;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        AstroGoldDivider(
          label: context.l10n.astroAiInfluencesTitle,
          labelStyle: AppTypography.labelSmall.copyWith(
            color: AppColors.ivory,
            fontSize: 12,
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xxs),
          child: Row(
            children: <Widget>[
              for (final TransitSummary influence in influences)
                Padding(
                  padding: const EdgeInsets.only(right: AppSpacing.sm),
                  child: AstroChip(
                    label: context.l10n.transitTitle(influence),
                    titleWidget: TransitTitle(
                      summary: influence,
                      glyphSize: 13,
                      maxLines: 1,
                      style: AppTypography.labelLarge.copyWith(fontSize: 13.5),
                    ),
                    subtitle: context.l10n.influenceNature(influence.nature),
                    leading: AstroImage(
                      influence.transitingPlanet.asset,
                      width: 26,
                      height: 26,
                    ),
                    semanticLabel:
                        '${context.l10n.transitTitle(influence)}, '
                        '${context.l10n.influenceNature(influence.nature)}',
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
