import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/localization/b12_copy.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/routing/app_routes.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/widgets/api_state_view.dart';
import '../../../core/widgets/widgets.dart';
import '../application/chat_controller.dart';
import '../data/attachment_service.dart';
import '../data/consultation_models.dart';
import '../data/consultation_repository.dart';
import '../data/realtime_services.dart';

final conversationsProvider = FutureProvider.autoDispose<List<Conversation>>(
  (ref) => ref.watch(consultationRepositoryProvider).conversations(),
);

class ConsultationsScreen extends ConsumerWidget {
  const ConsultationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) => CorePage(
    title: 'consultations',
    children: [
      ApiStateView(
        value: ref.watch(conversationsProvider),
        onRetry: () => ref.invalidate(conversationsProvider),
        builder: (items) => Column(
          children: [
            if (items.isEmpty) AstroCard(child: Text(b12(context, 'empty'))),
            for (final item in items)
              AstroCard(
                onTap: () => context.push(AppRoutes.chatThread(item.id)),
                child: ListTile(
                  title: Text(
                    item.counterpart ?? b12(context, 'consultations'),
                  ),
                  subtitle: Text('${item.status.name} · ${item.orderId}'),
                  trailing: const Icon(Icons.chevron_right),
                ),
              ),
          ],
        ),
      ),
    ],
  );
}

class OpenOrderChatScreen extends ConsumerStatefulWidget {
  const OpenOrderChatScreen({super.key, required this.orderId});
  final String orderId;

  @override
  ConsumerState<OpenOrderChatScreen> createState() => _OpenOrderChatState();
}

class _OpenOrderChatState extends ConsumerState<OpenOrderChatScreen> {
  Object? error;
  bool busy = false;
  int cooldown = 0;
  Timer? retryTimer;

  @override
  void dispose() {
    retryTimer?.cancel();
    super.dispose();
  }

  Future<void> open() async {
    if (busy || cooldown > 0) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      // The backend alone determines order, delivery, and capability eligibility.
      final conversation = await ref
          .read(consultationRepositoryProvider)
          .openForOrder(widget.orderId);
      if (mounted) context.replace(AppRoutes.chatThread(conversation.id));
    } on Object catch (e) {
      if (mounted) {
        setState(() {
          error = e;
          cooldown = e is ApiException ? e.retryAfterSeconds ?? 0 : 0;
        });
        retryTimer?.cancel();
        if (cooldown > 0) {
          retryTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
            if (!mounted) {
              timer.cancel();
              return;
            }
            setState(() => cooldown--);
            if (cooldown <= 0) timer.cancel();
          });
        }
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => CorePage(
    title: 'consultations',
    children: [
      AstroCard(child: Text(b12(context, 'chat_open_note'))),
      if (error != null)
        AstroCard(child: Text(friendlyApiError(context, error!))),
      if (cooldown > 0) Text('$cooldown s'),
      FilledButton(
        onPressed: busy || cooldown > 0 ? null : open,
        child: Text(b12(context, 'open_chat')),
      ),
    ],
  );
}

class ChatThreadScreen extends ConsumerStatefulWidget {
  const ChatThreadScreen({super.key, required this.id});
  final String id;

  @override
  ConsumerState<ChatThreadScreen> createState() => _ChatThreadState();
}

class _ChatThreadState extends ConsumerState<ChatThreadScreen>
    with WidgetsBindingObserver {
  late final ChatController controller;
  final composer = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    controller = ChatController(
      api: ref.read(consultationRepositoryProvider),
      realtime: ref.read(realtimeMessageServiceProvider),
      presence: ref.read(consultationPresenceProvider),
      attachments: ref.read(attachmentCoordinatorProvider),
      picker: ref.read(chatImagePickerProvider),
    );
    unawaited(controller.load(widget.id));
    unawaited(
      ref
          .read(consultationPresenceProvider)
          .setOnline()
          .catchError((Object _) {}),
    );
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final presence = ref.read(consultationPresenceProvider);
    if (state == AppLifecycleState.resumed) {
      unawaited(presence.setOnline().catchError((Object _) {}));
    } else if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      unawaited(presence.setOffline().catchError((Object _) {}));
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    unawaited(
      ref
          .read(consultationPresenceProvider)
          .setOffline()
          .catchError((Object _) {}),
    );
    controller.dispose();
    composer.dispose();
    super.dispose();
  }

  Future<void> send() async {
    final text = composer.text.trim();
    if (text.isEmpty) return;
    composer.clear();
    await controller.sendText(text);
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: controller,
    builder: (context, _) {
      final c = controller.conversation;
      final sendingAllowed =
          c?.canWrite == true &&
          controller.pending == null &&
          (controller.retryAfterSeconds ?? 0) <= 0 &&
          controller.status != ChatViewStatus.uploading &&
          controller.status != ChatViewStatus.sending;
      return CorePage(
        title: 'consultations',
        children: [
          if (controller.status == ChatViewStatus.loadingHistory)
            const Center(child: CircularProgressIndicator()),
          if (c != null)
            AstroCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(c.counterpart ?? b12(context, 'consultations')),
                  Semantics(
                    label: controller.partnerPresence.online
                        ? b12(context, 'online')
                        : b12(context, 'offline'),
                    child: Text(
                      controller.partnerPresence.available
                          ? (controller.partnerPresence.online
                                ? b12(context, 'online')
                                : b12(context, 'offline'))
                          : b12(context, 'chat_unavailable'),
                    ),
                  ),
                  if (controller.partnerTyping) Text(b12(context, 'typing')),
                ],
              ),
            ),
          if (controller.error != null)
            AstroCard(
              child: Column(
                children: [
                  Text(friendlyApiError(context, controller.error!)),
                  if (controller.retryAfterSeconds case final seconds?)
                    Text('$seconds s'),
                  if (controller.pending != null)
                    TextButton(
                      onPressed: (controller.retryAfterSeconds ?? 0) > 0
                          ? null
                          : controller.retryPending,
                      child: Text(b12(context, 'retry')),
                    ),
                  if (controller.canRetryImage)
                    TextButton(
                      onPressed: (controller.retryAfterSeconds ?? 0) > 0
                          ? null
                          : controller.retryImage,
                      child: Text(b12(context, 'retry')),
                    ),
                  if (controller.status == ChatViewStatus.error)
                    TextButton(
                      onPressed: () => controller.load(widget.id),
                      child: Text(b12(context, 'retry')),
                    ),
                ],
              ),
            ),
          if (controller.hasMore)
            OutlinedButton(
              onPressed: controller.loadMore,
              child: Text(b12(context, 'load_more')),
            ),
          if (c != null && controller.messages.isEmpty)
            AstroCard(child: Text(b12(context, 'empty'))),
          for (final message in controller.messages)
            _MessageTile(
              key: ValueKey(message.id),
              message: message,
              mine: message.isMine(c?.myRole ?? ''),
              attachment: controller.attachmentById[message.attachmentId],
              storage: ref.read(attachmentStorageProvider),
              onDelete: () => controller.deleteOwn(message),
            ),
          if (controller.status == ChatViewStatus.uploading)
            AstroCard(
              child: Column(
                children: [
                  Semantics(
                    label: b12(context, 'uploading'),
                    value: '${(controller.uploadProgress * 100).round()}%',
                    child: LinearProgressIndicator(
                      value: controller.uploadProgress,
                    ),
                  ),
                  TextButton(
                    onPressed: controller.cancelUpload,
                    child: Text(b12(context, 'cancel')),
                  ),
                ],
              ),
            ),
          if (controller.status == ChatViewStatus.readOnly ||
              controller.status == ChatViewStatus.closed)
            AstroCard(
              child: Text(
                b12(
                  context,
                  controller.status == ChatViewStatus.closed
                      ? 'closed'
                      : 'chat_read_only',
                ),
              ),
            ),
          if (c != null && c.canWrite)
            Row(
              children: [
                IconButton(
                  tooltip: b12(context, 'uploading'),
                  onPressed: sendingAllowed
                      ? controller.pickAndSendImage
                      : null,
                  icon: const Icon(
                    Icons.add_photo_alternate_outlined,
                    color: AppColors.gold,
                  ),
                ),
                Expanded(
                  child: TextField(
                    controller: composer,
                    enabled: sendingAllowed,
                    maxLength: controller.policy?.maxMessageLength ?? 4000,
                    maxLines: 3,
                    minLines: 1,
                    onChanged: controller.composerChanged,
                    decoration: InputDecoration(
                      labelText: b12(context, 'message'),
                    ),
                  ),
                ),
                IconButton(
                  tooltip: b12(context, 'send'),
                  onPressed: sendingAllowed ? send : null,
                  icon: const Icon(Icons.send, color: AppColors.gold),
                ),
              ],
            ),
        ],
      );
    },
  );
}

class _MessageTile extends StatelessWidget {
  const _MessageTile({
    super.key,
    required this.message,
    required this.mine,
    required this.attachment,
    required this.storage,
    required this.onDelete,
  });
  final ConsultationMessage message;
  final bool mine;
  final ChatAttachment? attachment;
  final AttachmentStorageService storage;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) => Align(
    alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 520),
      child: AstroCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Semantics(
              label: mine ? 'Ben' : message.senderRole,
              child: Text(mine ? 'Ben' : message.senderRole),
            ),
            if (message.deleted)
              Text(b12(context, 'message_deleted'))
            else if (message.type == MessageType.image &&
                attachment?.ready == true)
              _AttachmentPreview(attachment: attachment!, storage: storage)
            else if (message.type == MessageType.image)
              Text(b12(context, 'image_attachment'))
            else if (message.type == MessageType.file)
              Text(b12(context, 'file_attachment'))
            else
              Text(message.textBody ?? ''),
            if (mine && !message.deleted && message.type != MessageType.system)
              TextButton(
                onPressed: onDelete,
                child: Text(b12(context, 'delete')),
              ),
          ],
        ),
      ),
    ),
  );
}

class _AttachmentPreview extends StatefulWidget {
  const _AttachmentPreview({required this.attachment, required this.storage});
  final ChatAttachment attachment;
  final AttachmentStorageService storage;
  @override
  State<_AttachmentPreview> createState() => _AttachmentPreviewState();
}

class _AttachmentPreviewState extends State<_AttachmentPreview> {
  late Future<Uint8List?> image;
  @override
  void initState() {
    super.initState();
    image = widget.storage.readReady(widget.attachment);
  }

  @override
  void didUpdateWidget(covariant _AttachmentPreview oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.attachment.id != widget.attachment.id) {
      image = widget.storage.readReady(widget.attachment);
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Uint8List?>(
    future: image,
    builder: (context, snapshot) {
      if (!snapshot.hasData || snapshot.data == null) {
        return Text(b12(context, 'image_attachment'));
      }
      return Semantics(
        label: b12(context, 'image_attachment'),
        image: true,
        child: Image.memory(
          snapshot.data!,
          fit: BoxFit.contain,
          height: 240,
          errorBuilder: (_, _, _) => Text(b12(context, 'image_attachment')),
        ),
      );
    },
  );
}
