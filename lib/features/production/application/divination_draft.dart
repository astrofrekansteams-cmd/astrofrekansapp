import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/astrology/data/production_models.dart';
import '../../auth/application/session_controller.dart';

/// An in-progress user-pick draw, kept for the app's lifetime so leaving the
/// screen and coming back resumes the same face-down session.
///
/// Holds only what the client already knows: the public session, the picked
/// slot indices (in pick order) and the setup. The hidden deck never reaches
/// the client, so nothing here can reveal a card.
class DivinationDraft {
  const DivinationDraft({
    required this.session,
    required this.spread,
    this.picks = const [],
    this.question = '',
    this.optional = false,
    this.revealing = false,
    this.expired = false,
    this.reading,
  });

  final DrawSession session;
  final DivinationSpread spread;
  final List<int> picks;
  final String question;
  final bool optional;

  /// The reveal was sent; the picks are final.
  final bool revealing;
  final bool expired;
  final DivinationReading? reading;

  DivinationDraft copyWith({
    List<int>? picks,
    bool? revealing,
    bool? expired,
    DivinationReading? reading,
  }) => DivinationDraft(
    session: session,
    spread: spread,
    picks: picks ?? this.picks,
    question: question,
    optional: optional,
    revealing: revealing ?? this.revealing,
    expired: expired ?? this.expired,
    reading: reading ?? this.reading,
  );
}

/// One draft per deck. Not auto-disposed: it must outlive the route.
class DivinationDrafts extends Notifier<Map<DeckType, DivinationDraft>> {
  @override
  Map<DeckType, DivinationDraft> build() {
    // A different (or no) account never sees another account's draft.
    ref.watch(sessionProvider.select((s) => s.user?.id));
    return const {};
  }

  DivinationDraft? of(DeckType deck) => state[deck];

  void put(DeckType deck, DivinationDraft draft) =>
      state = {...state, deck: draft};

  /// Updates the draft only while it still belongs to [sessionId], so a late
  /// response for an abandoned shuffle cannot overwrite a newer one.
  void update(
    DeckType deck,
    String sessionId,
    DivinationDraft Function(DivinationDraft) change,
  ) {
    final current = state[deck];
    if (current == null || current.session.id != sessionId) return;
    state = {...state, deck: change(current)};
  }

  void clear(DeckType deck) {
    if (!state.containsKey(deck)) return;
    state = {...state}..remove(deck);
  }
}

final divinationDraftsProvider =
    NotifierProvider<DivinationDrafts, Map<DeckType, DivinationDraft>>(
      DivinationDrafts.new,
    );
