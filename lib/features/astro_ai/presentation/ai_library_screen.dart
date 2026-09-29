import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/localization/b12_copy.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../production/application/action_state.dart';
import '../application/astro_ai_controller.dart';
import '../data/api_astro_ai_repository.dart';
import '../data/ai_models.dart';
import '../../billing/presentation/paid_reports_section.dart';

final aiReportsProvider = FutureProvider.autoDispose<List<AIReport>>((
  ref,
) async {
  final repo = ref.watch(astroAIRepositoryProvider);
  return repo is ApiAstroAIRepository ? repo.reports() : <AIReport>[];
});
final aiConversationsProvider =
    FutureProvider.autoDispose<List<AIConversation>>((ref) async {
      final repo = ref.watch(astroAIRepositoryProvider);
      return repo is ApiAstroAIRepository
          ? repo.conversations()
          : <AIConversation>[];
    });
final aiReportProvider = FutureProvider.autoDispose.family(
  (ref, String id) =>
      (ref.watch(astroAIRepositoryProvider) as ApiAstroAIRepository).report(id),
);

class AILibraryScreen extends ConsumerStatefulWidget {
  const AILibraryScreen({super.key, this.jobId, this.reportId});
  final String? jobId;
  final String? reportId;
  @override
  ConsumerState<AILibraryScreen> createState() => _AILibraryState();
}

class _AILibraryState extends ConsumerState<AILibraryScreen> {
  final action = ActionState<AIReportJob>();
  StreamSubscription<AIReportJob>? polling;
  AsyncValue<AIReportJob>? job;
  String type = 'transit';
  @override
  void initState() {
    super.initState();
    if (widget.jobId != null) Future.microtask(() => watchJob(widget.jobId!));
  }

  void watchJob(String id) {
    final repo = ref.read(astroAIRepositoryProvider);
    if (repo is! ApiAstroAIRepository) return;
    polling?.cancel();
    setState(() => job = const AsyncLoading());
    polling = repo
        .pollJob(id)
        .listen(
          (value) {
            if (mounted) setState(() => job = AsyncData(value));
            if (value.terminal) ref.invalidate(aiReportsProvider);
          },
          onError: (Object e, StackTrace s) {
            if (mounted) setState(() => job = AsyncError(e, s));
          },
        );
  }

  @override
  void dispose() {
    polling?.cancel();
    action.dispose();
    super.dispose();
  }

  Widget reportView(AIReport report) => Column(
    children: [
      FactSection(
        title: report.optionalText('title') ?? 'reports',
        lines: [
          if (report.optionalText('summary') != null) report.text('summary'),
        ],
      ),
      // Factor ids are the grounding audit trail and `warnings` are the
      // model's instructions (English, internal): neither is reader copy.
      for (final s in report.sections)
        FactSection(title: s.text('title'), lines: [s.text('body')]),
      if (report.optionalText('safety_note') case final String note
          when note.isNotEmpty)
        FactSection(title: 'warnings', lines: [note]),
    ],
  );
  @override
  Widget build(BuildContext context) {
    final repo = ref.watch(astroAIRepositoryProvider);
    return ListenableBuilder(
      listenable: action,
      builder: (context, _) => CorePage(
        title: 'reports',
        children: [
          if (repo is! ApiAstroAIRepository)
            Text(b12(context, 'demo_unavailable'))
          else ...[
            if (widget.reportId != null)
              ApiStateView(
                value: ref.watch(aiReportProvider(widget.reportId!)),
                onRetry: () =>
                    ref.invalidate(aiReportProvider(widget.reportId!)),
                builder: reportView,
              )
            else ...[
              PaidReportsSection(reports: repo),
              ExpansionTile(
                title: Text(b12(context, 'conversations')),
                children: [
                  ApiStateView(
                    value: ref.watch(aiConversationsProvider),
                    onRetry: () => ref.invalidate(aiConversationsProvider),
                    builder: (items) => Column(
                      children: [
                        if (items.isEmpty) Text(b12(context, 'empty')),
                        for (final item in items)
                          ListTile(
                            title: Text(
                              item.title ?? b12(context, 'conversations'),
                            ),
                            onTap: () async {
                              try {
                                await ref
                                    .read(astroAIControllerProvider.notifier)
                                    .openConversation(item.id);
                                if (context.mounted) Navigator.pop(context);
                              } on Object catch (e) {
                                if (context.mounted) {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(
                                      content: Text(
                                        friendlyApiError(context, e),
                                      ),
                                    ),
                                  );
                                }
                              }
                            },
                          ),
                      ],
                    ),
                  ),
                ],
              ),
              Wrap(
                spacing: 8,
                children: [
                  for (final t in ['transit', 'daily', 'weekly', 'monthly'])
                    ChoiceChip(
                      label: Text(b12(context, t)),
                      selected: type == t,
                      onSelected: action.busy
                          ? null
                          : (_) => setState(() => type = t),
                    ),
                ],
              ),
              FilledButton(
                onPressed: action.busy
                    ? null
                    : () async {
                        final result = await action.run(
                          () => repo.createJob(type),
                        );
                        if (result != null && mounted) watchJob(result.id);
                      },
                child: Text(b12(context, 'create')),
              ),
              if (action.value != null)
                ApiStateView(
                  value: action.value!,
                  builder: (_) => const SizedBox.shrink(),
                ),
              if (job != null)
                ApiStateView(
                  value: job!,
                  builder: (j) => Column(
                    children: [
                      Text(b12(context, j.status.name)),
                      if (j.status == ReportJobStatus.failed)
                        Text(switch (j.optionalText('error_code')) {
                          'report_credit_unavailable' =>
                            'Rapor kredisi artık kullanılamıyor; bakiye ve satın alma durumunu kontrol edin.',
                          _ =>
                            'Rapor oluşturulamadı. Aynı istekle yeniden deneyebilirsiniz.',
                        }),
                      if (!j.terminal)
                        TextButton(
                          onPressed: () async {
                            final result = await action.run(
                              () => repo.cancelJob(j.id),
                            );
                            if (result != null && mounted) {
                              await polling?.cancel();
                              setState(() => job = AsyncData(result));
                            }
                          },
                          child: Text(b12(context, 'cancel')),
                        ),
                      if (j.reportId != null)
                        ApiStateView(
                          value: ref.watch(aiReportProvider(j.reportId!)),
                          onRetry: () =>
                              ref.invalidate(aiReportProvider(j.reportId!)),
                          builder: reportView,
                        ),
                    ],
                  ),
                ),
              ApiStateView(
                value: ref.watch(aiReportsProvider),
                onRetry: () => ref.invalidate(aiReportsProvider),
                builder: (items) => Column(
                  children: [
                    if (items.isEmpty) Text(b12(context, 'empty')),
                    for (final item in items)
                      ExpansionTile(
                        title: Text(
                          item.optionalText('title') ??
                              item.text('report_type'),
                        ),
                        children: [
                          ApiStateView(
                            value: ref.watch(aiReportProvider(item.id)),
                            onRetry: () =>
                                ref.invalidate(aiReportProvider(item.id)),
                            builder: reportView,
                          ),
                        ],
                      ),
                  ],
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }
}
