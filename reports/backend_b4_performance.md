# Backend B4 — Performance

Measured 23 September 2026 on the development machine (Windows 11, Docker
Desktop). Every figure is an end-to-end HTTP request against the running API:
authentication, chart lookup, computation, serialisation.

* **Cold** = `?refresh=true`, every cache bypassed, full ephemeris work.
* **Warm** = the next identical request, served from Redis.

Reference chart: 14 May 1992, 14:30, Istanbul (Placidus).

---

## API latency

### Docker stack (`docker compose`, api + postgres + redis)

| Endpoint | Cold | Warm | Speed-up |
| --- | --- | --- | --- |
| `GET /astrology/transits?range=day` | 1 137 ms | 14 ms | 81× |
| `GET /astrology/transits?range=week` | 1 141 ms | 19 ms | 60× |
| `GET /astrology/transits?range=month` | 1 163 ms | 15 ms | 77× |
| `GET /astrology/transits?range=year` | 3 144 ms | 38 ms | 83× |
| `GET /astrology/daily-frequency` | 1 862 ms | 16 ms | 119× |
| `GET /horoscope/daily` | 1 320 ms | 25 ms | 53× |
| `GET /horoscope/weekly` | 1 375 ms | 29 ms | 48× |
| `GET /calendar/events` (30 days) | 591 ms | 21 ms | 28× |
| `GET /calendar/personal` (30 days) | 503 ms | 36 ms | 14× |
| `GET /forecasts/monthly` | 2 589 ms | 16 ms | 167× |
| `GET /forecasts/yearly` | 7 180 ms | 43 ms | 167× |

### Local uvicorn (same machine, dev venv, busier CPU)

| Endpoint | Cold | Warm |
| --- | --- | --- |
| transits day | 1 570 ms | 41 ms |
| transits year | 4 667 ms | 31 ms |
| daily-frequency | 3 735 ms | 31 ms |
| horoscope weekly | 2 026 ms | 48 ms |
| forecast monthly | 5 272 ms | 52 ms |
| forecast yearly | 21 686 ms → **11 500 ms** after the batching work below | 53 ms |

## Engine-level scans (no HTTP, cold sampler each time)

| Scan | Before batching | After batching |
| --- | --- | --- |
| 1 day of transits | 6.36 s | **2.45 s** |
| 1 week | 11.30 s | **3.14 s** |
| 1 month | 30.04 s | **3.48 s** |
| 1 year (no Moon) | 89.79 s | **5.58 s** |
| Moon phases, full year | 3.0 s | **0.3 s** |
| Eclipse detection, full year | 8.0 s | **1.0 s** |
| Annual forecast (everything) | 24.3 s | **11.5 s** |

## What made the difference

1. **Vectorised sampling.** A scalar Skyfield call costs ~2.4 ms; 8 760
   instants in one call cost ~0.08 ms each (30× cheaper per point). Each body
   is now sampled once per scan instead of per target and aspect.
2. **Batched bisection.** Window edges, exact passes, stations, moon phases and
   mundane aspects are refined *together*: one vectorised call per round rather
   than one per bracket per round. The year scan went from ~3 900 scalar calls
   to a few dozen batched ones.
3. **Eclipse gate.** A syzygy further than 18.6° (solar) / 12.5° (lunar) from a
   node cannot be an eclipse, so the expensive geometry runs on ~4 lunations a
   year instead of 25. 8× faster, identical results.
4. **Station cache.** `events()` and `retrograde_periods()` no longer compute
   the same stations twice.
5. **Fewer, better-targeted iterations.** Window edges to 5 minutes, stations
   to 30 minutes, exact contacts to 20 seconds - each dropped halving is a
   saved ephemeris round trip, and none of it is visible in the product.

## Cache behaviour

* Warm responses are 14-53 ms end to end, i.e. cache lookup plus
  serialisation; the ephemeris is not touched.
* Cache keys carry `engine_version : orb_policy_version : scoring_version` and
  the chart fingerprint, so editing birth data or bumping a weight retires the
  affected entries automatically (verified by tests).
* Monthly and annual results are additionally written to
  `forecast_snapshots`, so a cold Redis after a deploy does not recompute a
  year per user.

## Assessment

Warm latency is where it needs to be for the mobile client (sub-50 ms for
every screen). Cold latency is acceptable for everything except the annual
forecast:

* daily / weekly / monthly: **1-3 s cold**, and only the first caller pays it.
* **annual: 7 s in Docker, 11.5 s locally.** Cached for 14 days and persisted,
  so it is paid once per user per year - but it is still a long request. The
  `ForecastJob` seam exists for moving it to a background worker in B11, which
  is the right fix; a premium annual report should be generated ahead of time
  and pushed, not waited for.

## Not measured

* Concurrency: all figures are single-request. Behaviour under parallel load
  (the ephemeris is CPU-bound and holds the GIL) has not been tested.
* Multiple uvicorn workers, or a shared Redis across workers.
* Memory under sustained load; the sampler's grid cache is per instance and
  unbounded within a request, which is fine for a request but not for a
  long-lived worker processing many charts.
