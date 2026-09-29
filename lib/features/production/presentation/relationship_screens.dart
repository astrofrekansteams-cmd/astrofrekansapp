import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/astrology/data/production_models.dart';
import '../../../core/astrology/data/production_repository.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/astro_card.dart';
import '../application/action_state.dart';
import '../application/core_providers.dart';
import '../../billing/application/coin_spend.dart';
import '../../billing/application/entitlement_service.dart';
import '../../billing/data/coin_repository.dart';
import 'birth_form.dart';
import 'compatibility_reading.dart';

class CompatibilityScreen extends ConsumerStatefulWidget {
  const CompatibilityScreen({
    super.key,
    this.personId,
    this.initialKind = 'synastry',
  });

  /// synastry, composite or davison.
  final String initialKind;
  final String? personId;
  @override
  ConsumerState<CompatibilityScreen> createState() => _CompatibilityState();
}

class _CompatibilityState extends ConsumerState<CompatibilityScreen> {
  late String kind = widget.initialKind;
  final action = ActionState<ContractRecord>();
  Json? inline;
  String? selected;
  @override
  void initState() {
    super.initState();
    selected = widget.personId;
  }

  @override
  void dispose() {
    action.dispose();
    super.dispose();
  }

  /// A coin purchase for a typed-in person: reused on every retry of it.
  String? _inlineCoinRef;

  PremiumFeature get _feature => switch (kind) {
    'composite' => PremiumFeature.composite,
    'davison' => PremiumFeature.davison,
    _ => PremiumFeature.synastry,
  };

  /// A saved person's paid calculation is remembered: opening it again is free.
  String? get _unlockKey => selected == null ? null : '$kind:$selected';

  bool get _needsCoins =>
      !ref.read(entitlementServiceProvider).canUse(_feature) &&
      !(_unlockKey != null &&
          ref.read(coinUnlocksProvider).containsKey(_unlockKey));

  Future<void> _calculate(ProductionRepository repo) async {
    final person = selected == null
        ? inline!
        : <String, dynamic>{'saved_person_id': selected};
    final key = _unlockKey;
    String? coinRef;
    if (!ref.read(entitlementServiceProvider).canUse(_feature)) {
      coinRef = key == null
          ? _inlineCoinRef
          : ref.read(coinUnlocksProvider)[key];
      if (coinRef == null) {
        if (!await confirmCoinSpend(
          context,
          ref,
          CoinItem.singlePremiumContent,
        )) {
          return;
        }
        coinRef = key == null
            ? (_inlineCoinRef = newCoinRef('compat'))
            : ref.read(coinUnlocksProvider.notifier).unlock(key);
      }
    }
    final result = await action.run(
      () async => kind == 'synastry'
          ? repo.synastry(person, coinRef: coinRef)
          : repo.relationshipChart(kind, person, coinRef: coinRef),
    );
    if (coinRef == null) return;
    if (result != null) {
      ref.invalidate(coinWalletProvider);
    } else if (isInsufficientCoins(action.value?.error)) {
      // Nothing was charged: the next press asks again.
      if (key != null) ref.read(coinUnlocksProvider.notifier).forget(key);
      _inlineCoinRef = null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final repo = ref.watch(productionRepositoryProvider);
    ref
      ..watch(entitlementServiceProvider)
      ..watch(coinUnlocksProvider);
    return ListenableBuilder(
      listenable: action,
      builder: (context, _) => CorePage(
        title: 'compatibility',
        children: [
          Text(b12(context, 'index_note')),
          if (repo == null)
            Text(b12(context, 'demo_unavailable'))
          else ...[
            Wrap(
              spacing: 8,
              children: [
                for (final mode in ['synastry', 'composite', 'davison'])
                  ChoiceChip(
                    label: Text(b12(context, mode)),
                    selected: kind == mode,
                    onSelected: action.busy
                        ? null
                        : (_) => setState(() {
                            kind = mode;
                            action.value = null;
                          }),
                  ),
              ],
            ),
            ApiStateView(
              value: ref.watch(savedPeopleProvider),
              onRetry: () => ref.invalidate(savedPeopleProvider),
              builder: (people) => Wrap(
                spacing: 8,
                children: [
                  for (final p in people)
                    ChoiceChip(
                      label: Text(p.name),
                      selected: selected == p.id,
                      onSelected: action.busy
                          ? null
                          : (_) => setState(() {
                              selected = p.id;
                              inline = null;
                            }),
                    ),
                ],
              ),
            ),
            ExpansionTile(
              title: Text(b12(context, 'profile_edit')),
              children: [
                BirthForm(
                  busy: action.busy,
                  onSubmit: (data) async {
                    setState(() {
                      inline = {...data, 'label': data['name']}..remove('name');
                      selected = null;
                      _inlineCoinRef = null;
                    });
                  },
                ),
              ],
            ),
            FilledButton(
              key: const ValueKey('compatibility-calculate'),
              onPressed: action.busy || (selected == null && inline == null)
                  ? null
                  : () => _calculate(repo),
              child: Text(
                _needsCoins
                    ? withCoinPrice(
                        context,
                        ref,
                        b12(context, 'calculate'),
                        CoinItem.singlePremiumContent,
                      )
                    : b12(context, 'calculate'),
              ),
            ),
            if (action.value != null)
              ApiStateView(
                value: action.value!,
                builder: (result) => _CompatibilityResult(result: result),
              ),
          ],
        ],
      ),
    );
  }
}

/// The result: the AI reading first, the calculation folded underneath. The
/// calculation never waits for, or depends on, the reading.
class _CompatibilityResult extends ConsumerWidget {
  const _CompatibilityResult({required this.result});
  final ContractRecord result;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final kind =
        result.optionalText('kind') ??
        (result is SynastryReport ? 'synastry' : 'composite');
    final reportId = result.optionalText('report_id');
    final readingFailed =
        reportId != null &&
        ref
            .watch(
              compatibilityReadingProvider((
                reportId,
                Localizations.localeOf(context).languageCode,
              )),
            )
            .hasError;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        CompatibilityReadingView(kind: kind, result: result),
        const SizedBox(height: 24),
        CompatibilityTechnicalDetails(
          // A failed reading opens the calculation so it is not hidden.
          key: ValueKey('tech-$readingFailed'),
          result: result,
          initiallyExpanded: readingFailed || reportId == null,
        ),
      ],
    );
  }
}

class HoraryScreen extends ConsumerStatefulWidget {
  const HoraryScreen({super.key, this.questionId});
  final String? questionId;
  @override
  ConsumerState<HoraryScreen> createState() => _HoraryState();
}

class _HoraryState extends ConsumerState<HoraryScreen> {
  final action = ActionState<HoraryQuestion>();
  final form = GlobalKey<FormState>();
  final fields = <String, TextEditingController>{
    for (final k in [
      'question',
      'latitude',
      'longitude',
      'timezone',
      'location_name',
    ])
      k: TextEditingController(),
  };
  @override
  void dispose() {
    action.dispose();
    for (final f in fields.values) {
      f.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final repo = ref.watch(productionRepositoryProvider);
    return ListenableBuilder(
      listenable: action,
      builder: (context, _) => CorePage(
        title: 'horary',
        children: [
          Text(b12(context, 'no_verdict')),
          if (repo == null)
            Text(b12(context, 'demo_unavailable'))
          else if (widget.questionId != null) ...[
            FilledButton(
              onPressed: action.busy
                  ? null
                  : () async {
                      await action.run(
                        () => repo.calculate(widget.questionId!),
                      );
                      ref.invalidate(
                        horaryAnalysisProvider(widget.questionId!),
                      );
                    },
              child: Text(b12(context, 'calculate')),
            ),
            if (action.value != null)
              ApiStateView(
                value: action.value!,
                builder: (_) => const SizedBox.shrink(),
              ),
            ApiStateView(
              value: ref.watch(horaryAnalysisProvider(widget.questionId!)),
              onRetry: () =>
                  ref.invalidate(horaryAnalysisProvider(widget.questionId!)),
              builder: (a) => Column(
                children: [
                  FactSection(
                    title: 'significators',
                    lines: [
                      for (final s in [
                        a.querent,
                        a.quesited,
                        if (a.coSignificator != null) a.coSignificator!,
                      ])
                        '${s.role}: ${s.planet} · ${s.house} · ${s.text('sign')}',
                    ],
                  ),
                  FactSection(
                    title: 'moon',
                    lines: [
                      '${a.moon.text('sign')} · ${a.moon.number('degree')}°',
                      '${a.moon.text('phase')} · void of course: ${a.moon.json['void_of_course']}',
                      a.moon.text('void_definition'),
                    ],
                  ),
                  for (final entry in <String, List<ContractRecord>>{
                    'receptions': a.receptions,
                    'dignities': a.dignities,
                    'perfection': a.perfection,
                    'obstructions': a.obstructions,
                  }.entries)
                    FactSection(
                      title: entry.key,
                      lines: [
                        for (final f in entry.value)
                          [
                            f.optionalText('id'),
                            f.optionalText('kind'),
                            f.optionalText('planet'),
                            f.optionalText('from_planet'),
                            f.optionalText('to_planet'),
                            f.optionalText('note'),
                            f.json['kinds']?.toString(),
                            f.json['exact_at']?.toString(),
                          ].whereType<String>().join(' · '),
                      ],
                    ),
                  FactSection(
                    title: 'warnings',
                    lines: [for (final w in a.warnings) w.text('message')],
                  ),
                  FactSection(
                    title: 'not_implemented',
                    lines: a.notImplemented,
                  ),
                  SourceFactors(
                    factors: {for (final id in a.sourceFactors) id: ''},
                  ),
                ],
              ),
            ),
          ] else ...[
            AstroCard(
              child: Form(
                key: form,
                child: Column(
                  children: [
                    for (final e in fields.entries)
                      TextFormField(
                        controller: e.value,
                        enabled: !action.busy,
                        decoration: InputDecoration(
                          labelText: b12(
                            context,
                            e.key == 'location_name' ? 'location' : e.key,
                          ),
                        ),
                        validator: (raw) {
                          final value = raw?.trim() ?? '';
                          if (e.key == 'question' &&
                              (value.length < 3 || value.length > 500)) {
                            return b12(context, 'validation');
                          }
                          if (e.key == 'latitude' || e.key == 'longitude') {
                            final n = double.tryParse(value);
                            if (n == null ||
                                !n.isFinite ||
                                n.abs() > (e.key == 'latitude' ? 90 : 180)) {
                              return b12(context, 'validation');
                            }
                          }
                          if (e.key == 'timezone' && value.isEmpty) {
                            return b12(context, 'validation');
                          }
                          return null;
                        },
                      ),
                    FilledButton(
                      onPressed: action.busy
                          ? null
                          : () async {
                              if (!form.currentState!.validate()) return;
                              final q = await action.run(
                                () => repo.createQuestion({
                                  'question': fields['question']!.text.trim(),
                                  'latitude': double.parse(
                                    fields['latitude']!.text,
                                  ),
                                  'longitude': double.parse(
                                    fields['longitude']!.text,
                                  ),
                                  'timezone': fields['timezone']!.text.trim(),
                                  'location_name': fields['location_name']!.text
                                      .trim(),
                                }),
                              );
                              if (q != null && context.mounted) {
                                ref.invalidate(horaryQuestionsProvider);
                                await context.push<void>(
                                  '${AppRoutes.horary}/${q.id}',
                                );
                              }
                            },
                      child: Text(b12(context, 'create')),
                    ),
                  ],
                ),
              ),
            ),
            if (action.value != null)
              ApiStateView(
                value: action.value!,
                builder: (_) => const SizedBox.shrink(),
              ),
            ApiStateView(
              value: ref.watch(horaryQuestionsProvider),
              onRetry: () => ref.invalidate(horaryQuestionsProvider),
              builder: (items) => Column(
                children: [
                  if (items.isEmpty) Text(b12(context, 'empty')),
                  for (final q in items)
                    ListTile(
                      title: Text(q.question),
                      subtitle: Text(q.status),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => context.push('${AppRoutes.horary}/${q.id}'),
                    ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
