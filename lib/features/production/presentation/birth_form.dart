import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../../core/astrology/data/production_models.dart';
import '../../../core/astrology/data/production_repository.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';

/// Birth data entry: date and time pickers plus a place search.
///
/// Local wall date/time are sent as entered. Picking a search result fills
/// latitude, longitude and the IANA timezone from the server's `/geocode`;
/// without a pick the server geocodes the typed place itself. Manual
/// coordinates stay available for places the search cannot find.
///
/// Output keys: name, birth_date (YYYY-MM-DD), birth_time (HH:mm or null),
/// birth_place, latitude, longitude, timezone.
class BirthForm extends ConsumerStatefulWidget {
  const BirthForm({
    super.key,
    required this.onSubmit,
    this.initial = const {},
    this.busy = false,
    this.showName = true,
  });
  final Json initial;
  final Future<void> Function(Json) onSubmit;
  final bool busy;

  /// False on the account's own birth data: the name belongs to the account,
  /// not to the birth record.
  final bool showName;
  @override
  ConsumerState<BirthForm> createState() => _BirthFormState();
}

class _BirthFormState extends ConsumerState<BirthForm> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(
    text: widget.initial['name']?.toString() ?? '',
  );
  late final _place = TextEditingController(
    text: widget.initial['birth_place']?.toString() ?? '',
  );
  late final _latitude = TextEditingController(
    text: widget.initial['latitude']?.toString() ?? '',
  );
  late final _longitude = TextEditingController(
    text: widget.initial['longitude']?.toString() ?? '',
  );
  late final _timezone = TextEditingController(
    text: widget.initial['timezone']?.toString() ?? '',
  );
  late DateTime? _date = DateTime.tryParse(
    widget.initial['birth_date']?.toString() ?? '',
  );
  late TimeOfDay? _time = parseBirthTime(widget.initial['birth_time']);
  late bool _timeUnknown =
      widget.initial.isNotEmpty && widget.initial['birth_time'] == null;
  bool _manual = false;
  bool _dateError = false;

  Timer? _debounce;
  int _searchSeq = 0;
  bool _searching = false;
  Object? _searchError;
  List<GeoPlace> _results = const [];

  @override
  void dispose() {
    _debounce?.cancel();
    for (final c in [_name, _place, _latitude, _longitude, _timezone]) {
      c.dispose();
    }
    super.dispose();
  }

  bool get _hasCoordinates =>
      double.tryParse(_latitude.text) != null &&
      double.tryParse(_longitude.text) != null;

  void _onPlaceChanged(String value) {
    // A new text invalidates coordinates picked for the previous text.
    if (!_manual) {
      _latitude.clear();
      _longitude.clear();
      _timezone.clear();
    }
    _debounce?.cancel();
    final repo = ref.read(productionRepositoryProvider);
    final query = value.trim();
    if (repo == null || query.length < 2) {
      setState(() {
        _results = const [];
        _searching = false;
        _searchError = null;
      });
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 450), () async {
      final seq = ++_searchSeq;
      setState(() {
        _searching = true;
        _searchError = null;
      });
      try {
        final results = await repo.geocode(query);
        if (!mounted || seq != _searchSeq) return;
        setState(() => _results = results);
      } catch (error) {
        if (!mounted || seq != _searchSeq) return;
        setState(() => _searchError = error);
      } finally {
        if (mounted && seq == _searchSeq) setState(() => _searching = false);
      }
    });
  }

  void _pick(GeoPlace place) {
    _debounce?.cancel();
    _searchSeq++;
    setState(() {
      _place.text = place.displayName;
      _latitude.text = place.latitude.toStringAsFixed(4);
      _longitude.text = place.longitude.toStringAsFixed(4);
      _timezone.text = place.timezone ?? '';
      _results = const [];
      _searching = false;
    });
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _date ?? DateTime(now.year - 25, 1, 1),
      firstDate: DateTime(1900),
      lastDate: now,
      initialEntryMode: DatePickerEntryMode.calendar,
    );
    if (picked != null) {
      setState(() {
        _date = picked;
        _dateError = false;
      });
    }
  }

  Future<void> _pickTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _time ?? const TimeOfDay(hour: 12, minute: 0),
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(alwaysUse24HourFormat: true),
        child: child!,
      ),
    );
    if (picked != null) setState(() => _time = picked);
  }

  String? _coordinate(String? raw, double limit) {
    final value = raw?.trim() ?? '';
    if (value.isEmpty) return null;
    final number = double.tryParse(value);
    if (number == null || !number.isFinite || number.abs() > limit) {
      return b12(context, 'validation');
    }
    return null;
  }

  Future<void> _submit() async {
    final valid = _form.currentState!.validate();
    setState(() => _dateError = _date == null);
    if (!valid || _date == null) return;
    String? text(TextEditingController c) =>
        c.text.trim().isEmpty ? null : c.text.trim();
    await widget.onSubmit(<String, dynamic>{
      'name': text(_name),
      'birth_date': formatBirthDate(_date!),
      'birth_time': _timeUnknown || _time == null
          ? null
          : formatBirthTime(_time!),
      'birth_place': text(_place),
      'latitude': double.tryParse(_latitude.text.trim()),
      'longitude': double.tryParse(_longitude.text.trim()),
      'timezone': text(_timezone),
    });
  }

  @override
  Widget build(BuildContext context) {
    final locale = Localizations.localeOf(context).toLanguageTag();
    final canSearch = ref.watch(productionRepositoryProvider) != null;
    return Form(
      key: _form,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (widget.showName) ...[
            TextFormField(
              controller: _name,
              enabled: !widget.busy,
              textCapitalization: TextCapitalization.words,
              decoration: InputDecoration(labelText: b12(context, 'name')),
              validator: (v) => (v?.trim().length ?? 0) < 2
                  ? b12(context, 'validation')
                  : null,
            ),
            AppSpacing.gapMd,
          ],
          _PickerField(
            icon: Icons.calendar_month_outlined,
            label: b12(context, 'birth_date_label'),
            value: _date == null
                ? null
                : DateFormat.yMMMMd(locale).format(_date!),
            error: _dateError ? b12(context, 'birth_date_required') : null,
            onTap: widget.busy ? null : _pickDate,
          ),
          AppSpacing.gapMd,
          _PickerField(
            icon: Icons.schedule_outlined,
            label: b12(context, 'birth_time_label'),
            value: _timeUnknown
                ? b12(context, 'birth_time_unknown')
                : _time == null
                ? null
                : formatBirthTime(_time!),
            onTap: widget.busy || _timeUnknown ? null : _pickTime,
          ),
          SwitchListTile.adaptive(
            contentPadding: EdgeInsets.zero,
            value: _timeUnknown,
            activeThumbColor: AppColors.gold,
            onChanged: widget.busy
                ? null
                : (v) => setState(() => _timeUnknown = v),
            title: Text(
              b12(context, 'birth_time_unknown_toggle'),
              style: AppTypography.bodyMedium,
            ),
            subtitle: _timeUnknown
                ? Text(
                    b12(context, 'birth_time_unknown_note'),
                    style: AppTypography.bodySmall,
                  )
                : null,
          ),
          AppSpacing.gapSm,
          TextFormField(
            controller: _place,
            enabled: !widget.busy,
            onChanged: _onPlaceChanged,
            decoration: InputDecoration(
              labelText: b12(context, 'birth_place_label'),
              hintText: b12(context, 'birth_place_hint'),
              prefixIcon: const Icon(Icons.place_outlined),
              suffixIcon: _searching
                  ? const Padding(
                      padding: EdgeInsets.all(14),
                      child: SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    )
                  : null,
            ),
            validator: (v) => (v?.trim().isEmpty ?? true) && !_hasCoordinates
                ? b12(context, 'birth_place_required')
                : null,
          ),
          if (_searchError != null)
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.sm),
              child: Text(
                friendlyApiError(context, _searchError!),
                style: AppTypography.bodySmall.copyWith(
                  color: AppColors.danger,
                ),
              ),
            ),
          if (_results.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.sm),
              child: AstroCard(
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    for (final place in _results)
                      ListTile(
                        dense: true,
                        leading: const Icon(
                          Icons.location_on_outlined,
                          color: AppColors.gold,
                        ),
                        title: Text(
                          place.displayName,
                          style: AppTypography.bodyMedium,
                        ),
                        subtitle: place.timezone == null
                            ? null
                            : Text(
                                place.timezone!,
                                style: AppTypography.bodySmall,
                              ),
                        onTap: () => _pick(place),
                      ),
                  ],
                ),
              ),
            ),
          if (_hasCoordinates && !_manual)
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.sm),
              child: Row(
                children: [
                  const Icon(
                    Icons.check_circle_outline,
                    size: 16,
                    color: AppColors.success,
                  ),
                  AppSpacing.gapSm,
                  Expanded(
                    child: Text(
                      describeCoordinates(
                        double.parse(_latitude.text),
                        double.parse(_longitude.text),
                        _timezone.text,
                      ),
                      style: AppTypography.bodySmall,
                    ),
                  ),
                ],
              ),
            ),
          if (!canSearch || _manual || _hasCoordinates)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: widget.busy
                    ? null
                    : () => setState(() => _manual = !_manual),
                icon: Icon(_manual ? Icons.expand_less : Icons.tune, size: 18),
                label: Text(b12(context, 'manual_coordinates')),
              ),
            ),
          if (_manual || !canSearch) ...[
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _latitude,
                    enabled: !widget.busy,
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                      signed: true,
                    ),
                    decoration: InputDecoration(
                      labelText: b12(context, 'latitude'),
                    ),
                    validator: (v) => _coordinate(v, 90),
                  ),
                ),
                AppSpacing.gapMd,
                Expanded(
                  child: TextFormField(
                    controller: _longitude,
                    enabled: !widget.busy,
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                      signed: true,
                    ),
                    decoration: InputDecoration(
                      labelText: b12(context, 'longitude'),
                    ),
                    validator: (v) => _coordinate(v, 180),
                  ),
                ),
              ],
            ),
            AppSpacing.gapMd,
            TextFormField(
              controller: _timezone,
              enabled: !widget.busy,
              decoration: InputDecoration(labelText: b12(context, 'timezone')),
            ),
          ],
          AppSpacing.gapXl,
          AstroButton(
            label: b12(context, 'save'),
            isLoading: widget.busy,
            onPressed: widget.busy ? null : _submit,
          ),
        ],
      ),
    );
  }
}

class _PickerField extends StatelessWidget {
  const _PickerField({
    required this.icon,
    required this.label,
    required this.value,
    required this.onTap,
    this.error,
  });
  final IconData icon;
  final String label;
  final String? value;
  final VoidCallback? onTap;
  final String? error;

  @override
  Widget build(BuildContext context) => Semantics(
    button: true,
    label: '$label ${value ?? ''}',
    child: InkWell(
      onTap: onTap,
      borderRadius: AppRadius.brMd,
      child: InputDecorator(
        isEmpty: value == null,
        decoration: InputDecoration(
          labelText: label,
          prefixIcon: Icon(icon),
          suffixIcon: const Icon(Icons.expand_more),
          errorText: error,
          enabled: onTap != null,
        ),
        child: value == null
            ? null
            : Text(value!, style: AppTypography.bodyLarge),
      ),
    ),
  );
}

String formatBirthDate(DateTime date) =>
    '${date.year.toString().padLeft(4, '0')}-'
    '${date.month.toString().padLeft(2, '0')}-'
    '${date.day.toString().padLeft(2, '0')}';

String formatBirthTime(TimeOfDay time) =>
    '${time.hour.toString().padLeft(2, '0')}:'
    '${time.minute.toString().padLeft(2, '0')}';

/// Accepts "HH:mm" or "HH:mm:ss"; anything else is treated as unknown.
TimeOfDay? parseBirthTime(Object? raw) {
  final match = RegExp(
    r'^([01]\d|2[0-3]):([0-5]\d)(:[0-5]\d)?$',
  ).firstMatch(raw?.toString() ?? '');
  if (match == null) return null;
  return TimeOfDay(
    hour: int.parse(match.group(1)!),
    minute: int.parse(match.group(2)!),
  );
}

String describeCoordinates(double latitude, double longitude, String tz) {
  final lat =
      '${latitude.abs().toStringAsFixed(2)}° ${latitude >= 0 ? 'N' : 'S'}';
  final lon =
      '${longitude.abs().toStringAsFixed(2)}° ${longitude >= 0 ? 'E' : 'W'}';
  return tz.isEmpty ? '$lat, $lon' : '$lat, $lon · $tz';
}
