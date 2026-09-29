import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/localization/b12_copy.dart';

import '../../../core/network/api_config.dart';
import '../../../core/extensions/context_extensions.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/widgets.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../application/astro_ai_controller.dart';
import '../domain/chat_message.dart';
import 'widgets/astro_ai_hero.dart';
import 'widgets/chat_bubble.dart';
import 'widgets/chat_input_bar.dart';

/// Astro AI: the conversation with your own chart.
class AstroAiScreen extends ConsumerStatefulWidget {
  const AstroAiScreen({super.key});

  @override
  ConsumerState<AstroAiScreen> createState() => _AstroAiScreenState();
}

class _AstroAiScreenState extends ConsumerState<AstroAiScreen> {
  final TextEditingController _input = TextEditingController();
  final ScrollController _scroll = ScrollController();
  late final AstroAIController _controller;

  @override
  void initState() {
    super.initState();
    _controller = ref.read(astroAIControllerProvider.notifier);
  }

  @override
  void dispose() {
    _controller.cancel();
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _scrollToEnd() {
    if (!_scroll.hasClients) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      final double target = _scroll.position.maxScrollExtent;
      if (context.reduceMotion) {
        _scroll.jumpTo(target);
      } else {
        _scroll.animateTo(
          target,
          duration: const Duration(milliseconds: 260),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _send(String text) {
    ref.read(astroAIControllerProvider.notifier).send(text);
    _scrollToEnd();
  }

  void _soon(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;
    final AstroAIState state = ref.watch(astroAIControllerProvider);
    final bool voiceAvailable = ref
        .watch(voiceInputServiceProvider)
        .isAvailable;

    ref.listen<AstroAIState>(astroAIControllerProvider, (
      AstroAIState? previous,
      AstroAIState next,
    ) {
      if (previous?.messages.length != next.messages.length) _scrollToEnd();
    });

    return Column(
      children: <Widget>[
        _Header(status: state.status),
        Expanded(
          child: ListView(
            controller: _scroll,
            padding: EdgeInsets.fromLTRB(
              context.gutter,
              AppSpacing.sm,
              context.gutter,
              AppSpacing.lg,
            ),
            children: <Widget>[
              const AstroAiHero(),
              TextButton(
                onPressed: () => context.push(AppRoutes.aiReports),
                child: Text(b12(context, 'reports')),
              ),
              if (state.isBusy)
                TextButton(
                  onPressed: _controller.cancel,
                  child: Text(b12(context, 'stop')),
                ),
              const SizedBox(height: AppSpacing.lg),
              if (!state.hasConversation)
                _EmptyConversation(onPrompt: _send, enabled: !state.isBusy)
              else
                for (final ChatMessage message in state.messages)
                  ChatBubble(message: message),
              if (state.status == AstroAIStatus.error)
                Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.md),
                  child: Text(
                    friendlyApiError(
                      context,
                      state.errorKind ?? StateError('unknown'),
                    ),
                    textAlign: TextAlign.center,
                    style: AppTypography.bodySmall.copyWith(
                      color: AppColors.danger,
                    ),
                  ),
                ),
              if (ref.watch(showDemoNoticeProvider)) ...<Widget>[
                const SizedBox(height: AppSpacing.lg),
                Text(
                  l10n.commonDemoNotice,
                  textAlign: TextAlign.center,
                  style: AppTypography.bodySmall.copyWith(fontSize: 12),
                ),
              ],
              if (state.influenceLabels.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.md),
                  child: FactSection(
                    title: 'influences_title',
                    lines: [
                      for (final label in state.influenceLabels) '✦ $label',
                    ],
                  ),
                ),
              if (state.warnings.isNotEmpty)
                FactSection(title: 'warnings', lines: state.warnings),
            ],
          ),
        ),
        ChatInputBar(
          controller: _input,
          enabled: !state.isBusy,
          onSend: _send,
          onAttachment: () => _soon(l10n.astroAiAttachmentSoon),
          onVoice: voiceAvailable
              ? () => ref
                    .read(astroAIControllerProvider.notifier)
                    .startListening()
              : null,
        ),
      ],
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.status});

  final AstroAIStatus status;

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;
    final String? liveLabel = switch (status) {
      AstroAIStatus.thinking => l10n.astroAiThinking,
      AstroAIStatus.typing => l10n.astroAiTyping,
      AstroAIStatus.listening => l10n.astroAiVoiceSoon,
      _ => null,
    };

    return Padding(
      padding: EdgeInsets.fromLTRB(
        context.gutter,
        AppSpacing.sm,
        context.gutter,
        AppSpacing.sm,
      ),
      child: Column(
        children: <Widget>[
          Text(
            l10n.astroAiTitle,
            style: AppTypography.displayMedium.copyWith(fontSize: 30),
          ),
          const SizedBox(height: AppSpacing.xxs),
          Text(l10n.astroAiKicker, style: AppTypography.overline),
          if (liveLabel != null) ...<Widget>[
            const SizedBox(height: AppSpacing.sm),
            Semantics(
              liveRegion: true,
              child: Text(
                liveLabel,
                style: AppTypography.bodySmall.copyWith(color: AppColors.gold),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _EmptyConversation extends StatelessWidget {
  const _EmptyConversation({required this.onPrompt, required this.enabled});

  final ValueChanged<String> onPrompt;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    final AppLocalizations l10n = context.l10n;
    final List<String> prompts = <String>[
      l10n.astroAiPromptLove,
      l10n.astroAiPromptCareer,
      l10n.astroAiPromptEnergy,
      l10n.astroAiPromptTransits,
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        const SizedBox(height: AppSpacing.lg),
        Text(
          l10n.astroAiEmptyTitle,
          textAlign: TextAlign.center,
          style: AppTypography.headlineMedium.copyWith(fontSize: 22),
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          l10n.astroAiEmptyBody,
          textAlign: TextAlign.center,
          style: AppTypography.bodyMedium,
        ),
        const SizedBox(height: AppSpacing.lg),
        Wrap(
          alignment: WrapAlignment.center,
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: <Widget>[
            for (final String prompt in prompts)
              AstroChip(
                label: prompt,
                onTap: enabled ? () => onPrompt(prompt) : null,
              ),
          ],
        ),
      ],
    );
  }
}
