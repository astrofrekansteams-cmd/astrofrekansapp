// The transit copy moved from transit_meaning.dart into the copy catalogue.
// The golden file was written by the implementation before the move, over
// every planet, aspect, natal planet, chart angle and house, in TR and EN:
// the astrology a person reads must not have changed by a single character.
import 'dart:convert';
import 'dart:io';

import 'package:astrofrekans/core/astrology/domain/aspect.dart';
import 'package:astrofrekans/core/astrology/domain/planet.dart';
import 'package:astrofrekans/core/astrology/domain/transit.dart';
import 'package:astrofrekans/core/localization/transit_meaning.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('every transit meaning reads exactly as before the move', () {
    final golden =
        (jsonDecode(
                  File(
                    'test/fixtures/transit_meaning_golden.json',
                  ).readAsStringSync(),
                )
                as Map<String, dynamic>)
            .cast<String, String?>();
    final actual = <String, String?>{};
    for (final language in ['tr', 'en']) {
      for (final moving in Planet.values) {
        actual['theme|${moving.name}|$language'] = planetTheme(
          moving,
          language,
        );
        for (final aspect in AspectType.values) {
          for (final natal in Planet.values) {
            actual['aspect|${moving.name}|${aspect.name}|${natal.name}|$language'] =
                transitMeaning(
                  Transit(
                    summary: TransitSummary(
                      id: 't',
                      transitingPlanet: moving,
                      aspect: aspect,
                      natalPlanet: natal,
                    ),
                  ),
                  language,
                );
          }
          for (final angle in ['asc', 'mc', 'dsc', 'ic', 'xx']) {
            actual['angle|${moving.name}|${aspect.name}|$angle|$language'] =
                influenceMeaning(
                  moving: moving,
                  aspect: aspect,
                  targetAngle: angle,
                  language: language,
                );
          }
        }
        for (var house = 0; house <= 13; house++) {
          actual['house|${moving.name}|$house|$language'] = transitMeaning(
            Transit(
              summary: TransitSummary(
                id: 't',
                transitingPlanet: moving,
                house: house,
              ),
            ),
            language,
          );
        }
        actual['plain|${moving.name}|$language'] = transitMeaning(
          Transit(
            summary: TransitSummary(id: 't', transitingPlanet: moving),
          ),
          language,
        );
      }
      for (var house = 0; house <= 13; house++) {
        actual['topic|$house|$language'] = houseTopic(house, language);
      }
    }
    expect(actual.length, golden.length);
    for (final entry in golden.entries) {
      expect(actual[entry.key], entry.value, reason: entry.key);
    }
  });
}
