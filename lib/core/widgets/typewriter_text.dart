import 'dart:async';

import 'package:flutter/material.dart';

import '../extensions/context_extensions.dart';

/// Text that types itself.
///
/// A streamed or freshly finished answer reads best when it appears at a
/// steady, human pace instead of in bursts (network chunks) or all at once.
/// The pace adapts: normally about [charactersPerSecond]; when much more text
/// is waiting than the pace could show in a couple of seconds, it speeds up
/// so the reader never falls far behind the source.
///
/// [text] may grow (streaming). Set [instant] for text that was already there
/// (a saved conversation, Reduce Motion): it is shown whole. Nothing is ever
/// hidden from screen readers: the semantics label always carries the full
/// text.
class TypewriterText extends StatefulWidget {
  const TypewriterText(
    this.text, {
    super.key,
    this.style,
    this.textAlign,
    this.instant = false,
    this.charactersPerSecond = 70,
    this.showCaret = true,
    this.onFinished,
  });

  final String text;
  final TextStyle? style;
  final TextAlign? textAlign;
  final bool instant;
  final double charactersPerSecond;
  final bool showCaret;

  /// Called once when everything that was given has been typed.
  final VoidCallback? onFinished;

  @override
  State<TypewriterText> createState() => _TypewriterTextState();
}

class _TypewriterTextState extends State<TypewriterText> {
  static const Duration _tick = Duration(milliseconds: 33);

  Timer? _timer;
  double _shown = 0;
  bool _reduceMotion = false;
  bool _finishedReported = false;

  int get _target => widget.text.characters.length;

  @override
  void initState() {
    super.initState();
    if (widget.instant) _shown = _target.toDouble();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _reduceMotion = context.reduceMotion;
    _sync();
  }

  @override
  void didUpdateWidget(TypewriterText oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.text.length < oldWidget.text.length) {
      // A different text: start over (never types backwards).
      _shown = widget.instant ? _target.toDouble() : 0;
      _finishedReported = false;
    }
    _sync();
  }

  void _sync() {
    if (widget.instant || _reduceMotion) {
      _timer?.cancel();
      _timer = null;
      _shown = _target.toDouble();
      _report();
      return;
    }
    if (_shown < _target) {
      _timer ??= Timer.periodic(_tick, _advance);
    }
  }

  void _advance(Timer timer) {
    final backlog = _target - _shown;
    if (backlog <= 0) {
      timer.cancel();
      _timer = null;
      _report();
      return;
    }
    // Catch up if more than ~2.5 s of typing is waiting.
    final perSecond = backlog / 2.5 > widget.charactersPerSecond
        ? backlog / 2.5
        : widget.charactersPerSecond;
    setState(() {
      _shown = (_shown + perSecond * _tick.inMilliseconds / 1000).clamp(
        0,
        _target.toDouble(),
      );
    });
    if (_shown >= _target) _report();
  }

  void _report() {
    if (_finishedReported || _shown < _target || _target == 0) return;
    _finishedReported = true;
    widget.onFinished?.call();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final characters = widget.text.characters;
    final visible = _shown >= _target
        ? widget.text
        : characters.take(_shown.floor()).toString();
    final typing = _shown < _target;
    return Semantics(
      label: widget.text,
      excludeSemantics: true,
      child: Text.rich(
        TextSpan(
          text: visible,
          children: [
            if (widget.showCaret && typing)
              WidgetSpan(
                alignment: PlaceholderAlignment.middle,
                child: _Caret(
                  color: (widget.style?.color ?? const Color(0xFFD9B979)),
                  height: (widget.style?.fontSize ?? 16) * 1.05,
                ),
              ),
          ],
        ),
        style: widget.style,
        textAlign: widget.textAlign,
      ),
    );
  }
}

class _Caret extends StatelessWidget {
  const _Caret({required this.color, required this.height});
  final Color color;
  final double height;

  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsetsDirectional.only(start: 2),
    width: 2,
    height: height,
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.85),
      borderRadius: BorderRadius.circular(1),
    ),
  );
}
