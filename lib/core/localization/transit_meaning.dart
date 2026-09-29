import '../astrology/domain/aspect.dart';
import '../astrology/domain/planet.dart';
import '../astrology/domain/transit.dart';
import '../utils/text_case.dart';
import 'b12_copy.dart';

/// Fixed TR/EN meaning for a transit, built from the planets' themes and the
/// aspect's nature. Deterministic: the same transit always reads the same.
/// Mirrors `PLANET_THEMES` in the backend guide content.
///
/// The words live in the app's copy catalogue (`b12_copy.dart`, keys
/// `transit_*`); this file only assembles them. The astrology is unchanged:
/// the same planet themes, house topics and aspect natures as before.

const _angles = {'asc', 'mc', 'dsc', 'ic'};

String _theme(Planet planet, String language) =>
    b12In(language, 'transit_theme_${planet.name}');

String? _house(int house, String language) =>
    house >= 1 && house <= 12 ? b12In(language, 'transit_house_$house') : null;

String? _angle(String? angle, String language) =>
    _angles.contains(angle) ? b12In(language, 'transit_angle_$angle') : null;

String _sentence(String text, String language) => text.isEmpty
    ? text
    : text.substring(0, 1).toUpperCaseFor(language) + text.substring(1);

/// Sentence-cased meaning: the themes are lower-case table entries, so the
/// first letter is raised with the language's own casing (i -> İ in Turkish).
String transitMeaning(Transit transit, String language) =>
    _sentence(_rawMeaning(transit, language), language);

String _rawMeaning(Transit transit, String language) {
  final target = transit.targetPlanet;
  final aspect = transit.aspectType;
  final moving = _theme(transit.transitingPlanet, language);
  if (target != null && aspect != null) {
    return _aspectMeaning(moving, _theme(target, language), aspect, language);
  }
  final house = transit.targetHouse;
  final topic = house == null ? null : _house(house, language);
  if (house != null && topic != null) {
    return b12In(language, 'transit_in_house')
        .replaceAll('{moving}', moving)
        .replaceAll('{house}', '$house')
        .replaceAll('{topic}', topic);
  }
  return b12In(language, 'transit_prominent').replaceAll('{moving}', moving);
}

String _aspectMeaning(
  String moving,
  String natal,
  AspectType aspect,
  String language,
) => b12In(language, switch (aspect.nature) {
  AspectNature.harmonious => 'transit_aspect_harmonious',
  AspectNature.hard => 'transit_aspect_hard',
  AspectNature.neutral => 'transit_aspect_neutral',
}).replaceAll('{moving}', moving).replaceAll('{natal}', natal);

/// The same fixed meaning for an influence given by its parts: a moving
/// planet in [aspect] to a natal planet or chart angle (`asc`, `mc`, `dsc`,
/// `ic`). Null when the parts are not known.
String? influenceMeaning({
  required Planet moving,
  required AspectType aspect,
  Planet? targetPlanet,
  String? targetAngle,
  required String language,
}) {
  final natal = targetPlanet != null
      ? _theme(targetPlanet, language)
      : _angle(targetAngle, language);
  if (natal == null) return null;
  return _sentence(
    _aspectMeaning(_theme(moving, language), natal, aspect, language),
    language,
  );
}

/// The fixed theme of a planet ("duygular ve ihtiyaçlar").
String planetTheme(Planet planet, String language) => _theme(planet, language);

/// The fixed topic of a natal house ("kariyer ve hedefler").
String? houseTopic(int house, String language) => _house(house, language);
