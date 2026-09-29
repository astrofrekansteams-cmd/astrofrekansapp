import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/localization/b12_copy.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/widgets.dart';
import '../../marketplace/data/marketplace_repository.dart';
import '../application/call_controller.dart';
import '../application/incoming_call_presentation.dart';
import '../data/call_media_service.dart';
import '../data/call_models.dart';
import '../data/call_repository.dart';

const _callErrorCodes = {
  'call_too_early',
  'call_window_closed',
  'call_not_allowed',
  'call_provider_not_configured',
  'call_already_ended',
  'call_type_not_supported',
  'call_provider_unavailable',
  'duplicate_identity',
};

String callErrorText(String? code, {String language = 'tr'}) => b12In(
  language,
  _callErrorCodes.contains(code) ? 'call_err_$code' : 'call_err_generic',
);

String _lang(BuildContext context) =>
    Localizations.localeOf(context).languageCode;

String _callStatus(BuildContext context, CallStatus status) =>
    b12(context, 'call_status_${status.name}');

String _duration(int seconds) =>
    '${(seconds ~/ 60).toString().padLeft(2, '0')}:${(seconds % 60).toString().padLeft(2, '0')}';

final callHistoryProvider = FutureProvider.autoDispose<CallPage>(
  (ref) => ref.watch(callRepositoryProvider).history(),
);
final callExpertNameProvider = FutureProvider.autoDispose
    .family<String?, (String, bool)>((ref, key) async {
      try {
        return (await ref
                .watch(marketplaceRepositoryProvider)
                .order(key.$1, expert: key.$2))
            .expertName;
      } on Object {
        return null;
      }
    });

class CallHistoryScreen extends ConsumerWidget {
  const CallHistoryScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(callHistoryProvider);
    return AstroScaffold(
      appBar: AppBar(title: Text(b12(context, 'call_history'))),
      body: history.when(
        loading: () => ListView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          children: const [
            AstroSkeletonCard(media: true, lines: 1),
            SizedBox(height: AppSpacing.cardGap),
            AstroSkeletonCard(media: true, lines: 1),
          ],
        ),
        error: (_, _) => Center(
          child: FilledButton(
            onPressed: () => ref.invalidate(callHistoryProvider),
            child: Text(b12(context, 'retry')),
          ),
        ),
        data: (page) => ListView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          children: [
            if (page.items.isEmpty)
              AstroCard(child: Text(b12(context, 'call_history_empty'))),
            for (final call in page.items)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.md),
                child: AstroCard(
                  onTap: () => context.push(AppRoutes.callDetail(call.id)),
                  child: ListTile(
                    leading: Icon(
                      call.type == CallType.video
                          ? Icons.videocam_outlined
                          : Icons.call_outlined,
                      color: AppColors.gold,
                    ),
                    title: Text(
                      '${b12(context, call.type == CallType.video ? 'call_video' : 'call_audio')} · ${ref.watch(callExpertNameProvider((call.orderId, call.myRole == 'expert'))).value ?? b12(context, 'booking_expert')}',
                    ),
                    subtitle: Text(
                      '${DateFormat.yMMMd(_lang(context)).add_Hm().format(call.createdAt.toLocal())} · ${_callStatus(context, call.status)}\n${call.durationSeconds == null ? b12(context, 'call_duration_pending') : _duration(call.durationSeconds!)}',
                    ),
                    isThreeLine: true,
                    trailing: const Icon(Icons.chevron_right),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class OpenOrderCallScreen extends ConsumerStatefulWidget {
  const OpenOrderCallScreen({
    super.key,
    required this.orderId,
    this.appointmentId,
  });
  final String orderId;
  final String? appointmentId;
  @override
  ConsumerState<OpenOrderCallScreen> createState() =>
      _OpenOrderCallScreenState();
}

class _OpenOrderCallScreenState extends ConsumerState<OpenOrderCallScreen> {
  bool busy = false;
  String? error;

  Future<void> open(CallType type) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final available = await ref.read(callRepositoryProvider).availability();
      if (!available.configured) {
        throw StateError('call_provider_not_configured');
      }
      final call = await ref
          .read(callRepositoryProvider)
          .create(
            orderId: widget.orderId,
            appointmentId: widget.appointmentId,
            type: type,
          );
      if (mounted) context.replace(AppRoutes.callDetail(call.id));
    } on Object catch (e) {
      if (mounted) {
        setState(() {
          error = e is ApiException
              ? e.code
              : e is StateError
              ? 'call_provider_not_configured'
              : 'call_unavailable';
        });
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AstroScaffold(
    appBar: AppBar(title: Text(b12(context, 'call_live'))),
    body: ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        AstroCard(child: Text(b12(context, 'call_server_checks'))),
        const SizedBox(height: AppSpacing.lg),
        if (error != null)
          AstroCard(
            child: Text(callErrorText(error, language: _lang(context))),
          ),
        FilledButton.icon(
          onPressed: busy ? null : () => open(CallType.audio),
          icon: const Icon(Icons.call),
          label: Text(b12(context, 'call_audio')),
        ),
        const SizedBox(height: AppSpacing.md),
        OutlinedButton.icon(
          onPressed: busy ? null : () => open(CallType.video),
          icon: const Icon(Icons.videocam),
          label: Text(b12(context, 'call_video')),
        ),
      ],
    ),
  );
}

class CallScreen extends ConsumerStatefulWidget {
  const CallScreen({
    super.key,
    required this.id,
    this.incoming = false,
    this.autoAnswer = false,
  });
  final String id;
  final bool incoming;
  final bool autoAnswer;

  @override
  ConsumerState<CallScreen> createState() => _CallScreenState();
}

class _CallScreenState extends ConsumerState<CallScreen> {
  bool _answerTriggered = false;

  Future<void> _join(CallController controller) async {
    final presentation = ref.read(incomingCallPresentationProvider);
    var callKit = false;
    if (presentation is IOSCallPresentationService) {
      callKit = await presentation.prepareAudio(widget.id);
    }
    await controller.join();
    if (presentation is IOSCallPresentationService && callKit) {
      if (controller.phase == CallUiPhase.inCall) {
        await presentation.markConnected(widget.id);
      } else {
        await presentation.dismiss(widget.id);
        await presentation.releaseAudio();
      }
    }
  }

  Future<void> _end(CallController controller) async {
    await controller.end();
    final presentation = ref.read(incomingCallPresentationProvider);
    await presentation.dismiss(widget.id);
    if (presentation is IOSCallPresentationService) {
      await presentation.releaseAudio();
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = ref.watch(callControllerProvider(widget.id));
    if (widget.autoAnswer &&
        !_answerTriggered &&
        controller.phase == CallUiPhase.ready &&
        controller.session != null) {
      _answerTriggered = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(_join(controller));
      });
    }
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final session = controller.session;
        final media = controller.media;
        return AstroScaffold(
          appBar: AppBar(
            title: Text(
              b12(context, widget.incoming ? 'call_incoming' : 'call_live'),
            ),
          ),
          body: session == null
              ? Center(
                  child: controller.phase == CallUiPhase.loading
                      ? const AstroLoading()
                      : FilledButton(
                          onPressed: controller.refresh,
                          child: Text(
                            callErrorText(
                              controller.errorCode,
                              language: _lang(context),
                            ),
                          ),
                        ),
                )
              : ListView(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  children: [
                    _CallHeader(session: session, controller: controller),
                    const SizedBox(height: AppSpacing.lg),
                    if (session.type == CallType.video)
                      _VideoStage(media: media)
                    else
                      _AudioStage(controller: controller),
                    const SizedBox(height: AppSpacing.lg),
                    if (media.connection == MediaConnection.reconnecting)
                      AstroCard(child: Text(b12(context, 'call_reconnecting'))),
                    if (media.connection == MediaConnection.replaced)
                      AstroCard(
                        child: Text(
                          callErrorText(
                            'duplicate_identity',
                            language: _lang(context),
                          ),
                        ),
                      ),
                    if (controller.permissionError != null &&
                        controller.permissionError != MediaPermission.granted)
                      AstroCard(
                        child: Column(
                          children: [
                            Text(
                              controller.permissionError ==
                                      MediaPermission.permanentlyDenied
                                  ? b12(context, 'call_permission_settings')
                                  : b12(context, 'call_permission_denied'),
                            ),
                            if (controller.permissionError ==
                                MediaPermission.permanentlyDenied)
                              TextButton(
                                onPressed: () =>
                                    controller.permissions.openSettings(),
                                child: Text(b12(context, 'call_open_settings')),
                              ),
                          ],
                        ),
                      ),
                    if (controller.errorCode != null &&
                        media.connection != MediaConnection.replaced)
                      AstroCard(
                        child: Text(
                          callErrorText(
                            controller.errorCode,
                            language: _lang(context),
                          ),
                        ),
                      ),
                    const SizedBox(height: AppSpacing.lg),
                    if (!session.isTerminal &&
                        controller.phase != CallUiPhase.inCall &&
                        media.connection != MediaConnection.replaced)
                      FilledButton.icon(
                        onPressed: controller.phase == CallUiPhase.joining
                            ? null
                            : () => unawaited(_join(controller)),
                        icon: const Icon(Icons.call),
                        label: Text(
                          b12(
                            context,
                            widget.incoming ? 'call_accept' : 'call_join',
                          ),
                        ),
                      ),
                    if (controller.phase == CallUiPhase.inCall)
                      _CallControls(controller: controller),
                    const SizedBox(height: AppSpacing.md),
                    if (!session.isTerminal)
                      OutlinedButton.icon(
                        onPressed: controller.phase == CallUiPhase.ending
                            ? null
                            : () => unawaited(_end(controller)),
                        icon: const Icon(Icons.call_end),
                        label: Text(b12(context, 'call_end')),
                      ),
                    if (session.isTerminal)
                      // Ending a call never completes the order (a dropped
                      // call is not a finished consultation). It leads back
                      // to the order, where completion is a separate action.
                      AstroCard(
                        child: Column(
                          children: [
                            Text(b12(context, 'call_ended')),
                            Text(b12(context, 'call_ended_next_step')),
                            TextButton(
                              key: const ValueKey('call-open-order'),
                              onPressed: () => context.push(
                                session.myRole == 'expert'
                                    ? '${AppRoutes.expertWorkspace}/orders/${session.orderId}'
                                    : AppRoutes.orderDetail(session.orderId),
                              ),
                              child: Text(b12(context, 'open_order')),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
        );
      },
    );
  }
}

class _CallHeader extends ConsumerWidget {
  const _CallHeader({required this.session, required this.controller});
  final CallSession session;
  final CallController controller;
  @override
  Widget build(BuildContext context, WidgetRef ref) => AstroCard(
    child: Column(
      children: [
        Text(
          b12(
            context,
            session.type == CallType.video
                ? 'call_video_title'
                : 'call_audio_title',
          ),
          style: AppTypography.titleLarge,
        ),
        const SizedBox(height: 8),
        Text(
          ref
                  .watch(
                    callExpertNameProvider((
                      session.orderId,
                      session.myRole == 'expert',
                    )),
                  )
                  .value ??
              b12(context, 'booking_expert'),
          style: AppTypography.bodyMedium,
        ),
        Text(
          '${b12(context, 'call_state')}: ${_callStatus(context, session.status)} · '
          '${b12(context, 'call_connection')}: ${b12(context, 'call_conn_${controller.media.connection.name}')}',
          textAlign: TextAlign.center,
        ),
        Text(
          _duration(controller.elapsedSeconds),
          style: AppTypography.displayMedium.copyWith(color: AppColors.gold),
        ),
      ],
    ),
  );
}

class _AudioStage extends StatelessWidget {
  const _AudioStage({required this.controller});
  final CallController controller;
  @override
  Widget build(BuildContext context) => Center(
    child: Container(
      width: 210,
      height: 210,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: AppColors.cardGradient,
        border: Border.all(color: AppColors.gold, width: 2),
        boxShadow: const [BoxShadow(color: AppColors.glow, blurRadius: 38)],
      ),
      child: const Icon(
        Icons.graphic_eq,
        size: 85,
        color: AppColors.goldBright,
      ),
    ),
  );
}

class _VideoStage extends StatelessWidget {
  const _VideoStage({required this.media});
  final CallMediaService media;
  @override
  Widget build(BuildContext context) => SizedBox(
    height: MediaQuery.sizeOf(context).height * .43,
    child: ClipRRect(
      borderRadius: BorderRadius.circular(24),
      child: Stack(
        children: [
          Positioned.fill(
            child: ColoredBox(
              color: AppColors.surface,
              child: media.remoteVideo(),
            ),
          ),
          Positioned(
            right: 14,
            bottom: 14,
            width: 108,
            height: 150,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: ColoredBox(
                color: AppColors.navy,
                child: media.localVideo(),
              ),
            ),
          ),
        ],
      ),
    ),
  );
}

class _CallControls extends StatelessWidget {
  const _CallControls({required this.controller});
  final CallController controller;
  @override
  Widget build(BuildContext context) {
    final media = controller.media;
    return Wrap(
      alignment: WrapAlignment.center,
      spacing: 12,
      runSpacing: 12,
      children: [
        _control(
          icon: media.muted ? Icons.mic_off : Icons.mic,
          label: b12(context, media.muted ? 'call_mic_on' : 'call_mic_off'),
          onTap: () => controller.setMuted(!media.muted),
        ),
        _control(
          icon: media.speakerEnabled ? Icons.volume_up : Icons.hearing,
          label: b12(
            context,
            media.speakerEnabled ? 'call_to_earpiece' : 'call_to_speaker',
          ),
          onTap: () => controller.setSpeakerEnabled(!media.speakerEnabled),
        ),
        if (controller.session?.type == CallType.video) ...[
          _control(
            icon: media.cameraEnabled ? Icons.videocam : Icons.videocam_off,
            label: b12(
              context,
              media.cameraEnabled ? 'call_camera_off' : 'call_camera_on',
            ),
            onTap: () => controller.setCameraEnabled(!media.cameraEnabled),
          ),
          _control(
            icon: Icons.cameraswitch_outlined,
            label: b12(context, 'call_camera_switch'),
            onTap: controller.switchCamera,
          ),
        ],
        FutureBuilder<List<(String, String)>>(
          future: media.audioOutputs(),
          builder: (context, snapshot) =>
              snapshot.hasData && snapshot.data!.length > 1
              ? PopupMenuButton<String>(
                  tooltip: b12(context, 'call_audio_output'),
                  icon: const Icon(
                    Icons.bluetooth_audio,
                    color: AppColors.gold,
                  ),
                  onSelected: controller.selectAudioOutput,
                  itemBuilder: (_) => [
                    for (final output in snapshot.data!)
                      PopupMenuItem(value: output.$1, child: Text(output.$2)),
                  ],
                )
              : const SizedBox.shrink(),
        ),
      ],
    );
  }

  Widget _control({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) => Semantics(
    label: label,
    button: true,
    child: IconButton.filledTonal(
      onPressed: onTap,
      tooltip: label,
      icon: Icon(icon),
    ),
  );
}
