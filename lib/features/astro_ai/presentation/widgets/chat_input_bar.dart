import 'package:flutter/material.dart';

import '../../../../core/extensions/context_extensions.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/widgets.dart';

/// Chat composer: attachment, text field, send.
///
/// A voice button appears automatically once a [VoiceInputService] reports
/// itself available; until then the affordance stays hidden rather than fake.
class ChatInputBar extends StatefulWidget {
  const ChatInputBar({
    required this.controller,
    required this.onSend,
    super.key,
    this.enabled = true,
    this.onAttachment,
    this.onVoice,
  });

  final TextEditingController controller;
  final ValueChanged<String> onSend;
  final bool enabled;
  final VoidCallback? onAttachment;
  final VoidCallback? onVoice;

  @override
  State<ChatInputBar> createState() => _ChatInputBarState();
}

class _ChatInputBarState extends State<ChatInputBar> {
  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onChanged);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onChanged);
    super.dispose();
  }

  void _onChanged() => setState(() {});

  void _submit() {
    final String text = widget.controller.text.trim();
    if (text.isEmpty || !widget.enabled) return;
    widget.onSend(text);
    widget.controller.clear();
  }

  @override
  Widget build(BuildContext context) {
    final bool canSend =
        widget.enabled && widget.controller.text.trim().isNotEmpty;

    return Container(
      padding: EdgeInsets.fromLTRB(
        context.gutter,
        AppSpacing.sm,
        context.gutter,
        AppSpacing.sm,
      ),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: AppColors.hairline)),
        color: AppColors.night,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: <Widget>[
          if (widget.onAttachment != null)
            AstroIconButton(
              icon: Icons.add,
              semanticLabel: context.l10n.astroAiAttachmentSoon,
              onPressed: widget.onAttachment,
              size: 42,
            ),
          const SizedBox(width: AppSpacing.xs),
          Expanded(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 132),
              child: TextField(
                controller: widget.controller,
                enabled: widget.enabled,
                minLines: 1,
                maxLines: 5,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _submit(),
                style: AppTypography.bodyLarge,
                decoration: InputDecoration(
                  hintText: context.l10n.astroAiInputHint,
                  isDense: true,
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.lg,
                    vertical: AppSpacing.md,
                  ),
                  border: const OutlineInputBorder(
                    borderRadius: AppRadius.brPill,
                    borderSide: BorderSide(color: AppColors.hairline),
                  ),
                  enabledBorder: const OutlineInputBorder(
                    borderRadius: AppRadius.brPill,
                    borderSide: BorderSide(color: AppColors.hairline),
                  ),
                  focusedBorder: const OutlineInputBorder(
                    borderRadius: AppRadius.brPill,
                    borderSide: BorderSide(color: AppColors.gold, width: 1.3),
                  ),
                ),
              ),
            ),
          ),
          if (widget.onVoice != null) ...<Widget>[
            const SizedBox(width: AppSpacing.xs),
            AstroIconButton(
              icon: Icons.mic_none,
              semanticLabel: context.l10n.astroAiVoiceSoon,
              onPressed: widget.onVoice,
              size: 42,
            ),
          ],
          const SizedBox(width: AppSpacing.xs),
          AstroIconButton(
            icon: Icons.send,
            semanticLabel: context.l10n.homeSend,
            onPressed: canSend ? _submit : null,
            filled: canSend,
            size: 44,
          ),
        ],
      ),
    );
  }
}
