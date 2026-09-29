import '../../features/profile/domain/user_profile.dart';
import 'domain/astro_ai_context.dart';
import 'domain/birth_data.dart';
import 'domain/cosmic_event.dart';
import 'domain/daily_frequency.dart';
import 'domain/moon_phase.dart';
import 'domain/natal_chart.dart';
import 'domain/synastry_result.dart';
import 'domain/transit.dart';

/// The astrology engine seam.
///
/// Every astrological number in the app comes from an implementation of this
/// interface - never from the AI layer and never from the widgets. Today the
/// app runs on [MockAstrologyService]; a backend-backed implementation can be
/// swapped in by overriding `astrologyServiceProvider` only.
abstract interface class AstrologyService {
  Future<NatalChart> getNatalChart(BirthData birthData);

  Future<List<Transit>> getTransits({
    required NatalChart natalChart,
    required DateTime from,
    DateTime? to,
  });

  Future<DailyFrequency> getDailyFrequency({
    required UserProfile profile,
    required DateTime date,
  });

  Future<SynastryResult> getSynastry({
    required BirthData personA,
    required BirthData personB,
    CompatibilityMode mode,
  });

  Future<MoonPhase> getMoonPhase({
    required DateTime date,
    NatalChart? natalChart,
  });

  Future<List<CosmicEvent>> getCosmicCalendar({
    required DateTime from,
    required DateTime to,
    NatalChart? natalChart,
  });

  Future<AstroAIContext> getAstroAIContext({
    required UserProfile profile,
    DateTime? at,
  });
}
