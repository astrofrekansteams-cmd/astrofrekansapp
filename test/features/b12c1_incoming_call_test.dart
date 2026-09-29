import 'dart:async';

import 'package:astrofrekans/features/calls/application/incoming_call_presentation.dart';
import 'package:astrofrekans/features/calls/data/call_models.dart';
import 'package:astrofrekans/features/calls/data/call_repository.dart';
import 'package:flutter_test/flutter_test.dart';

const id = '11111111-1111-4111-8111-111111111111';

CallSession session(String status) => CallSession({
  'id': id,
  'order_id': '22222222-2222-4222-8222-222222222222',
  'call_type': 'audio',
  'status': status,
  'created_at': '2025-01-01T00:00:00Z',
});

class Calls extends Fake implements CallRepository {
  CallSession current = session('ringing');
  int reads = 0;
  int ends = 0;
  bool failRead = false;
  bool failEnd = false;
  Completer<void>? gate;

  @override
  Future<CallSession> get(String id) async {
    reads++;
    if (gate != null) await gate!.future;
    if (failRead) throw StateError('unauthorized');
    return current;
  }

  @override
  Future<CallSession> end(String id) async {
    ends++;
    if (failEnd) throw StateError('end failure');
    current = session('cancelled');
    return current;
  }
}

void main() {
  test('incoming GET, duplicate push and cancelled dismissal', () async {
    final calls = Calls();
    final presentation = FakeIncomingCallPresentationService();
    final coordinator = IncomingCallCoordinator(calls, presentation);
    expect(await coordinator.incoming(id), isTrue);
    expect(await coordinator.incoming(id), isTrue);
    expect(calls.reads, 1);
    expect(presentation.shown, [id]);
    await coordinator.cancelled(id);
    expect(presentation.dismissed, [id]);
    expect(await coordinator.incoming(id), isFalse);
    presentation.dispose();
  });

  test('missed/ended or unauthorized push never rings', () async {
    for (final status in ['missed', 'ended', 'cancelled', 'failed']) {
      final calls = Calls()..current = session(status);
      final presentation = FakeIncomingCallPresentationService();
      expect(
        await IncomingCallCoordinator(calls, presentation).incoming(id),
        isFalse,
      );
      expect(presentation.shown, isEmpty);
      presentation.dispose();
    }
    final calls = Calls()..failRead = true;
    final presentation = FakeIncomingCallPresentationService();
    expect(
      await IncomingCallCoordinator(calls, presentation).incoming(id),
      isFalse,
    );
    expect(presentation.shown, isEmpty);
    presentation.dispose();
  });

  test('cancel during validation suppresses late ringing', () async {
    final calls = Calls()..gate = Completer<void>();
    final presentation = FakeIncomingCallPresentationService();
    final coordinator = IncomingCallCoordinator(calls, presentation);
    final pending = coordinator.incoming(id);
    await coordinator.cancelled(id);
    calls.gate!.complete();
    expect(await pending, isFalse);
    expect(presentation.shown, isEmpty);
    presentation.dispose();
  });

  test('answer revalidates and stale answer cannot join', () async {
    final calls = Calls();
    final presentation = FakeIncomingCallPresentationService();
    final coordinator = IncomingCallCoordinator(calls, presentation);
    await coordinator.incoming(id);
    expect(await coordinator.accept(id), isTrue);
    expect(calls.reads, 2);
    expect(presentation.dismissed, isEmpty);
    calls.current = session('ended');
    expect(await coordinator.accept(id), isFalse);
    presentation.dispose();
  });

  test('decline uses backend end; failure does not fabricate state', () async {
    final calls = Calls();
    final presentation = FakeIncomingCallPresentationService();
    final coordinator = IncomingCallCoordinator(calls, presentation);
    expect(await coordinator.decline(id), isTrue);
    expect(calls.ends, 1);
    expect(calls.current.status, CallStatus.cancelled);
    final failed = Calls()..failEnd = true;
    final failedCoordinator = IncomingCallCoordinator(failed, presentation);
    expect(await failedCoordinator.decline(id), isFalse);
    expect(failedCoordinator.lastErrorCode, 'call_unavailable');
    expect(failed.current.status, CallStatus.ringing);
    presentation.dispose();
  });

  test('CallKit end uses backend end and action expiry is enforced', () async {
    final calls = Calls()..current = session('active');
    final presentation = FakeIncomingCallPresentationService();
    final coordinator = IncomingCallCoordinator(calls, presentation);
    expect(await coordinator.end(id), isTrue);
    expect(calls.ends, 1);
    expect(presentation.dismissed, [id]);
    expect(
      IncomingCallAction(
        id,
        IncomingCallActionType.answer,
        expiresAt: DateTime.now().toUtc().subtract(const Duration(seconds: 1)),
      ).isExpired,
      isTrue,
    );
    presentation.dispose();
  });

  test(
    'cold-start action is consumed once; action listener disposes',
    () async {
      final presentation = FakeIncomingCallPresentationService()
        ..initialAction = const IncomingCallAction(
          id,
          IncomingCallActionType.answer,
        );
      expect(
        (await presentation.consumeInitialAction())?.type,
        IncomingCallActionType.answer,
      );
      expect(await presentation.consumeInitialAction(), isNull);
      final events = <IncomingCallAction>[];
      final subscription = presentation.actions.listen(events.add);
      presentation.emit(
        const IncomingCallAction(id, IncomingCallActionType.decline),
      );
      await Future<void>.delayed(Duration.zero);
      expect(events.single.type, IncomingCallActionType.decline);
      await subscription.cancel();
      presentation.dispose();
    },
  );
}
