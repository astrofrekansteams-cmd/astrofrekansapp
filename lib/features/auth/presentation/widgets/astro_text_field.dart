import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';

/// Themed form field used by every auth form.
class AstroTextField extends StatelessWidget {
  const AstroTextField({
    required this.controller,
    required this.label,
    super.key,
    this.hint,
    this.keyboardType,
    this.obscureText = false,
    this.validator,
    this.textInputAction = TextInputAction.next,
    this.autofillHints,
    this.suffix,
    this.onTap,
    this.readOnly = false,
    this.maxLength,
    this.onFieldSubmitted,
  });

  final TextEditingController controller;
  final String label;
  final String? hint;
  final TextInputType? keyboardType;
  final bool obscureText;
  final String? Function(String?)? validator;
  final TextInputAction textInputAction;
  final Iterable<String>? autofillHints;
  final Widget? suffix;
  final VoidCallback? onTap;
  final bool readOnly;
  final int? maxLength;
  final ValueChanged<String>? onFieldSubmitted;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.only(
              left: AppSpacing.xs,
              bottom: AppSpacing.xs + 2,
            ),
            child: Text(
              label,
              style: AppTypography.labelSmall.copyWith(
                color: AppColors.ivoryMuted,
                letterSpacing: 1.1,
              ),
            ),
          ),
          TextFormField(
            controller: controller,
            keyboardType: keyboardType,
            obscureText: obscureText,
            validator: validator,
            textInputAction: textInputAction,
            autofillHints: autofillHints,
            readOnly: readOnly,
            maxLength: maxLength,
            onTap: onTap,
            onFieldSubmitted: onFieldSubmitted,
            style: AppTypography.bodyLarge,
            cursorColor: AppColors.gold,
            decoration: InputDecoration(
              hintText: hint,
              counterText: '',
              suffixIcon: suffix,
            ),
          ),
        ],
      ),
    );
  }
}
