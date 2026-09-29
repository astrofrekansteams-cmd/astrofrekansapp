import '../../../core/astrology/domain/natal_chart.dart';
import '../../../core/astrology/domain/transit.dart';
import '../../profile/domain/user_profile.dart';
import '../domain/astro_ai_repository.dart';
import '../domain/chat_message.dart';

/// Offline stand-in for the Astro AI backend.
///
/// It streams a canned answer word by word so the chat UI (thinking -> typing
/// -> answering) can be built and tested for real. The copy is template based
/// and openly demo content; it is never presented as a live reading.
class MockAstroAIRepository implements AstroAIRepository {
  MockAstroAIRepository({
    this.wordDelay = const Duration(milliseconds: 45),
    this.thinkingDelay = const Duration(milliseconds: 650),
    String languageCode = 'tr',
  }) : _templates = languageCode == 'en' ? _en : _tr;

  final Duration wordDelay;
  final Duration thinkingDelay;
  final _Templates _templates;

  @override
  Stream<AstroAIEvent> sendMessage({
    required String message,
    required UserProfile userProfile,
    required NatalChart natalChart,
    required List<Transit> activeTransits,
    List<ChatMessage> history = const <ChatMessage>[],
  }) async* {
    if (thinkingDelay > Duration.zero) {
      await Future<void>.delayed(thinkingDelay);
    }

    final String answer = _templates.answerFor(
      message: message,
      firstName: userProfile.firstName,
      transitHeadline: activeTransits.isEmpty
          ? null
          : activeTransits.first.summary.headline,
    );

    final List<String> words = answer.split(' ');
    final StringBuffer buffer = StringBuffer();
    for (int i = 0; i < words.length; i++) {
      buffer.write(i == 0 ? words[i] : ' ${words[i]}');
      if (wordDelay > Duration.zero) {
        await Future<void>.delayed(wordDelay);
      }
      yield AstroAITextDelta(i == 0 ? words[i] : ' ${words[i]}');
    }

    yield AstroAICompleted(
      influences: <TransitSummary>[
        for (final Transit transit in activeTransits.take(3)) transit.summary,
      ],
    );
  }

  static const _Templates _tr = _Templates(
    love:
        'İlişkilerinde şu dönemde daha derin bağlar kurma isteği öne çıkıyor. '
        'Duygusal hassasiyetin yükselebilir; ani tepkilerden kaçınman faydalı '
        'olur. Karşılıklı anlayış ve açık iletişim, bu dönemin anahtarı.',
    career:
        'Kariyerinde yapı kurma ve sorumluluk temaları belirgin. Acele etmek '
        'yerine sağlam adımlar atmak, uzun vadede çok daha iyi sonuç verecek. '
        'Görünürlüğünü artıracak fırsatlara açık ol.',
    money:
        'Maddi konularda dengeyi korumak önemli. Kısa vadeli heveslerden çok, '
        'düzenli ve planlı ilerleyiş destek buluyor. Bütçeni gözden geçirmek '
        'için iyi bir zaman.',
    general:
        'Bu dönemde farkındalığını artıran bir gökyüzü var. İçsel ritmini '
        'dinlediğinde, dışarıdaki akışın da yumuşadığını göreceksin. Küçük ama '
        'net adımlar bugünün enerjisine uygun.',
    suffix:
        'Not: bu yanıt demo içeriktir; gerçek yorum motoru bağlandığında '
        'doğum haritanın tamamı kullanılacak.',
    loveKeys: <String>['aşk', 'ilişki', 'sevgili', 'partner', 'evlilik'],
    careerKeys: <String>['kariyer', 'iş', 'terfi', 'meslek', 'proje'],
    moneyKeys: <String>['para', 'maddi', 'bütçe', 'kazanç', 'finans'],
  );

  static const _Templates _en = _Templates(
    love:
        'In your relationships the wish for deeper bonds is coming forward. '
        'Emotional sensitivity may rise, so it helps to avoid sudden '
        'reactions. Mutual understanding and open communication are the key.',
    career:
        'Structure and responsibility are the themes in your career right '
        'now. Solid steps will serve you far better than rushing. Stay open '
        'to what increases your visibility.',
    money:
        'Keeping balance around money matters. Steady, planned progress finds '
        'more support than short-term impulses. A good time to review your '
        'budget.',
    general:
        'The current sky supports awareness. When you listen to your own '
        'rhythm, the flow outside softens too. Small but clear steps suit '
        "today's energy.",
    suffix:
        'Note: this answer is demo content; once the interpretation engine is '
        'connected your full birth chart will be used.',
    loveKeys: <String>['love', 'relationship', 'partner', 'marriage'],
    careerKeys: <String>['career', 'job', 'work', 'promotion', 'project'],
    moneyKeys: <String>['money', 'finance', 'budget', 'income'],
  );
}

class _Templates {
  const _Templates({
    required this.love,
    required this.career,
    required this.money,
    required this.general,
    required this.suffix,
    required this.loveKeys,
    required this.careerKeys,
    required this.moneyKeys,
  });

  final String love;
  final String career;
  final String money;
  final String general;
  final String suffix;
  final List<String> loveKeys;
  final List<String> careerKeys;
  final List<String> moneyKeys;

  String answerFor({
    required String message,
    required String firstName,
    String? transitHeadline,
  }) {
    final String lower = message.toLowerCase();
    bool matches(List<String> keys) =>
        keys.any((String key) => lower.contains(key));

    final String body = matches(loveKeys)
        ? love
        : matches(careerKeys)
        ? career
        : matches(moneyKeys)
        ? money
        : general;

    return <String>['$firstName,', body, ?transitHeadline, suffix].join(' ');
  }
}
