import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/astrology/data/production_models.dart';
import '../../../core/astrology/data/production_repository.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../../auth/application/session_controller.dart';
import '../application/action_state.dart';
import '../application/core_providers.dart';
import 'birth_form.dart';

/// The account's own birth data - and only that. The account name and the
/// zone the person lives in are edited in Account Information; changing a
/// birth place here never moves where the person lives, and vice versa.
class ProfileEditScreen extends ConsumerStatefulWidget {
  const ProfileEditScreen({super.key});
  @override
  ConsumerState<ProfileEditScreen> createState() => _ProfileEditState();
}

class _ProfileEditState extends ConsumerState<ProfileEditScreen> {
  final action = ActionState<bool>();
  @override
  void dispose() {
    action.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    return ListenableBuilder(
      listenable: action,
      builder: (context, _) => CorePage(
        title: 'birth_data_title',
        children: [
          Text(b12(context, 'birth_data_intro')),
          if (user != null)
            BirthForm(
              key: const ValueKey('birth-data-form'),
              busy: action.busy,
              showName: false,
              initial: {
                'birth_date': user.birthDate?.toIso8601String().substring(
                  0,
                  10,
                ),
                'birth_time': user.birthTime,
                'birth_place': user.birthPlace,
                'latitude': user.latitude,
                'longitude': user.longitude,
                // The birth place's zone - not where the person lives now.
                'timezone': user.birthTimezone,
              },
              onSubmit: (data) => action.run(() async {
                await ref
                    .read(sessionProvider.notifier)
                    .updateBirthData(
                      user.copyWith(
                        birthDate: DateTime.parse(data['birth_date'] as String),
                        birthTime: data['birth_time'] as String?,
                        birthPlace: data['birth_place'] as String?,
                        latitude: data['latitude'] as double?,
                        longitude: data['longitude'] as double?,
                        birthTimezone: data['timezone'] as String?,
                      ),
                    );
                return true;
              }),
            ),
          if (action.value != null)
            ApiStateView(
              value: action.value!,
              builder: (_) => Text(b12(context, 'saved')),
            ),
        ],
      ),
    );
  }
}

class SavedPeopleScreen extends ConsumerStatefulWidget {
  const SavedPeopleScreen({super.key});
  @override
  ConsumerState<SavedPeopleScreen> createState() => _SavedPeopleState();
}

class _SavedPeopleState extends ConsumerState<SavedPeopleScreen> {
  final action = ActionState<bool>();
  bool adding = false;

  /// The person being edited, if any. Past reports are unaffected: they keep
  /// the birth data they were made from.
  String? editing;
  @override
  void dispose() {
    action.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final repo = ref.watch(productionRepositoryProvider);
    return ListenableBuilder(
      listenable: action,
      builder: (context, _) => CorePage(
        title: 'saved_people',
        children: [
          if (repo == null)
            Text(b12(context, 'demo_unavailable'))
          else ...[
            FilledButton(
              onPressed: action.busy
                  ? null
                  : () => setState(() {
                      adding = !adding;
                      editing = null;
                    }),
              child: Text(b12(context, adding ? 'cancel' : 'create')),
            ),
            if (adding)
              BirthForm(
                busy: action.busy,
                onSubmit: (Json data) async {
                  final result = await action.run(() async {
                    await repo.createPerson({...data, 'relation': 'other'});
                    return true;
                  });
                  if (result == true && mounted) {
                    setState(() => adding = false);
                    ref.invalidate(savedPeopleProvider);
                  }
                },
              ),
            if (action.value != null)
              ApiStateView(
                value: action.value!,
                builder: (_) => const SizedBox.shrink(),
              ),
            ApiStateView(
              value: ref.watch(savedPeopleProvider),
              onRetry: () => ref.invalidate(savedPeopleProvider),
              builder: (people) => Column(
                children: [
                  if (people.isEmpty) Text(b12(context, 'empty')),
                  for (final person in people)
                    if (editing == person.id)
                      AstroCard(
                        key: ValueKey('edit-person-${person.id}'),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Text(b12(context, 'person_edit_note')),
                            BirthForm(
                              busy: action.busy,
                              initial: {
                                'name': person.name,
                                'birth_date': person.birthDate
                                    .toIso8601String()
                                    .substring(0, 10),
                                'birth_time': person.birthTimeKnown
                                    ? person.birthTime
                                    : null,
                                'birth_place': person.birthPlace,
                                'latitude': person.latitude,
                                'longitude': person.longitude,
                                'timezone': person.timezone,
                              },
                              onSubmit: (Json data) async {
                                final result = await action.run(() async {
                                  await repo.updatePerson(person.id, {
                                    ...data,
                                    // An empty name keeps the current one.
                                    if (data['name'] == null)
                                      'name': person.name,
                                  });
                                  return true;
                                });
                                if (result == true && mounted) {
                                  setState(() => editing = null);
                                  ref.invalidate(savedPeopleProvider);
                                }
                              },
                            ),
                            TextButton(
                              onPressed: action.busy
                                  ? null
                                  : () => setState(() => editing = null),
                              child: Text(b12(context, 'cancel')),
                            ),
                          ],
                        ),
                      )
                    else
                      ListTile(
                        title: Text(person.name),
                        subtitle: Text(
                          '${person.birthDate.toIso8601String().substring(0, 10)} · ${person.birthTime ?? '—'} · ${person.birthPlace ?? '—'}',
                        ),
                        onTap: () => context.push(
                          '${AppRoutes.compatibility}?person=${Uri.encodeComponent(person.id)}',
                        ),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            IconButton(
                              key: ValueKey('edit-${person.id}'),
                              tooltip: b12(context, 'edit'),
                              onPressed: action.busy
                                  ? null
                                  : () => setState(() {
                                      editing = person.id;
                                      adding = false;
                                    }),
                              icon: const Icon(Icons.edit_outlined),
                            ),
                            IconButton(
                              tooltip: b12(context, 'delete'),
                              onPressed: action.busy
                                  ? null
                                  : () async {
                                      final confirm = await showDialog<bool>(
                                        context: context,
                                        builder: (context) => AlertDialog(
                                          content: Text(
                                            b12(context, 'confirm_delete'),
                                          ),
                                          actions: [
                                            TextButton(
                                              onPressed: () =>
                                                  Navigator.pop(context, false),
                                              child: Text(
                                                b12(context, 'cancel'),
                                              ),
                                            ),
                                            TextButton(
                                              onPressed: () =>
                                                  Navigator.pop(context, true),
                                              child: Text(
                                                b12(context, 'delete'),
                                              ),
                                            ),
                                          ],
                                        ),
                                      );
                                      if (confirm == true) {
                                        await action.run(() async {
                                          await repo.deletePerson(person.id);
                                          return true;
                                        });
                                        ref.invalidate(savedPeopleProvider);
                                      }
                                    },
                              icon: const Icon(Icons.delete_outline),
                            ),
                          ],
                        ),
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
