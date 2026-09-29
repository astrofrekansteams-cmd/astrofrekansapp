import 'dart:async';

import 'package:flutter/material.dart';

import '../extensions/context_extensions.dart';
import '../localization/b12_copy.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';

/// "Astro AI is writing": three dots that rise in turn, and a short label.
/// Still (three quiet dots) with Reduce Motion, and it pauses when its screen
/// is not the one being looked at.
class TypingDots extends StatefulWidget {
  const TypingDots({super.key, this.labelKey = 'ai_writing'});
  final String labelKey;

  @override
  State<TypingDots> createState() => _TypingDotsState();
}

class _TypingDotsState extends State<TypingDots> {
  Timer? _timer;
  int _step = 0;
  bool _run = true;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _run = !context.reduceMotion && TickerMode.valuesOf(context).enabled;
    _timer?.cancel();
    _timer = null;
    if (_run) {
      _timer = Timer.periodic(const Duration(milliseconds: 260), (_) {
        if (mounted) setState(() => _step = (_step + 1) % 4);
      });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    label: b12(context, widget.labelKey),
    excludeSemantics: true,
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < 3; i++)
          AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            margin: EdgeInsets.only(
              right: 5,
              bottom: _run && _step == i + 1 ? 5 : 0,
            ),
            width: 7,
            height: 7,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppColors.gold.withValues(
                alpha: !_run || _step == i + 1 ? 0.95 : 0.4,
              ),
            ),
          ),
        const SizedBox(width: 6),
        Text(
          b12(context, widget.labelKey),
          style: AppTypography.bodySmall.copyWith(fontStyle: FontStyle.italic),
        ),
      ],
    ),
  );
}
