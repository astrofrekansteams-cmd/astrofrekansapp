import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/localization/b12_copy.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../data/marketplace_models.dart';
import '../data/marketplace_repository.dart';

final _ownExpertProvider = FutureProvider.autoDispose<Expert>(
  (ref) => ref.watch(marketplaceRepositoryProvider).ownProfile(),
);
final _ownHoursProvider = FutureProvider.autoDispose<List<AvailabilityWindow>>(
  (ref) => ref.watch(marketplaceRepositoryProvider).ownAvailability(),
);

class ExpertWorkspaceScreen extends ConsumerWidget {
  const ExpertWorkspaceScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) => CorePage(
    title: 'expert_workspace',
    children: [
      ApiStateView(
        value: ref.watch(_ownExpertProvider),
        onRetry: () => ref.invalidate(_ownExpertProvider),
        builder: (expert) => Column(
          children: [
            AstroCard(
              child: ListTile(
                title: Text(expert.name),
                subtitle: Text(
                  '${expert.status.name} · ${expert.timezone ?? '—'}',
                ),
              ),
            ),
            AstroCard(
              onTap: () => context.push('${AppRoutes.expertWorkspace}/orders'),
              child: ListTile(
                title: Text(b12(context, 'orders')),
                trailing: const Icon(Icons.chevron_right),
              ),
            ),
            AstroCard(
              onTap: () =>
                  context.push('${AppRoutes.expertWorkspace}/appointments'),
              child: ListTile(
                title: Text(b12(context, 'appointments')),
                trailing: const Icon(Icons.chevron_right),
              ),
            ),
            AstroCard(
              onTap: () => context.push(AppRoutes.consultations),
              child: ListTile(
                title: Text(b12(context, 'consultations')),
                trailing: const Icon(Icons.chevron_right),
              ),
            ),
            FactSection(
              title: 'services',
              lines: [
                for (final service in expert.services)
                  '${service.title} · ${service.deliveryType.name} · ${service.price.display}',
              ],
            ),
          ],
        ),
      ),
      ApiStateView(
        value: ref.watch(_ownHoursProvider),
        onRetry: () => ref.invalidate(_ownHoursProvider),
        builder: (hours) => FactSection(
          title: 'slots',
          lines: [
            for (final window in hours)
              '${window.weekday} · ${window.startLocalTime}–${window.endLocalTime} · ${window.timezone}',
          ],
        ),
      ),
    ],
  );
}
