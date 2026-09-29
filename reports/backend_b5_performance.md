# Backend B5 — Performance

Measured 23 September 2026. Every figure is an end-to-end HTTP request against
the running API: authentication, chart resolution, computation, persistence
and serialisation.

* **Cold** = every cache bypassed (`refresh: true`, or a freshly created
  question), full ephemeris work.
* **Warm** = the same request again, served from Redis or from the stored
  snapshot.

Reference pair: 14 May 1992 14:30 Istanbul and 21 August 1994 09:45 London,
both Placidus. Horary question cast for 23 September 2026 from Istanbul.

---

## Docker stack (api + postgres + redis)

| Endpoint | Cold | Warm | Speed-up |
| --- | --- | --- | --- |
| `POST /horary/questions` | 184 ms | – | first write |
| `POST /horary/questions/{id}/calculate` | 156 ms | – | chart cast + cached |
| `GET /horary/questions/{id}/analysis` | **1 186 ms** | **15 ms** | 79× |
| `GET /horary/questions` | 15 ms | – | listing |
| `POST /compatibility/synastry` | **49 ms** | **17 ms** | 3× |
| `POST /compatibility/composite` | **31 ms** | **28 ms** | – |
| `POST /compatibility/davison` | **121 ms** | **39 ms** | 3× |
| `GET /compatibility/reports` | 33 ms | – | listing |
| `GET /compatibility/reports/{id}` | 26 ms | – | stored snapshot |

## Local uvicorn (dev venv, busier CPU)

| Endpoint | Cold | Warm |
| --- | --- | --- |
| horary create | 158 ms | – |
| horary calculate | 203 ms | – |
| horary analysis | 1 662 ms | 37 ms |
| synastry | 163 ms | 69 ms |
| composite | 83 ms | 46 ms |
| davison | 136 ms | 52 ms |

## Engine-level (no HTTP)

| Operation | Time | Note |
| --- | --- | --- |
| Horary chart | ~100 ms | one chart cast |
| Horary structured analysis | **1.29 s** | was 4.19 s before the fix below |
| Synastry (aspects + overlays + themes) | **< 5 ms** | pure arithmetic on two charts |
| Composite | **< 5 ms** | midpoints, then the natal aspect engine |
| Davison | ~100 ms | one real chart cast at the midpoint instant |

## Where the horary second goes, and what was fixed

The analysis is the only expensive call in B5, because it searches forward for
perfections: for every candidate aspect it has to find *when* two moving bodies
reach an exact angle, and the Moon moves 13° a day.

1. **Both bodies move.** The first implementation searched the Moon against a
   *fixed* planet longitude. That is fast and wrong: it mis-times contacts and
   can mis-call void of course, which is a headline warning. Switching to a
   two-body search cost accuracy nothing and, with the step size tuned per
   body (2 h when the Moon is involved, 6 h otherwise), dropped the analysis
   from **4.19 s to 1.29 s** - the coarse scan now brackets contacts in far
   fewer samples before bisection.
2. **Snapshots, not recomputation.** A stored analysis is returned as it was
   produced (15 ms). That is also the correct behaviour: re-running a newer
   engine over an old question would change an answer the user already read.

Synastry, composite and their scoring touch no ephemeris at all once the two
natal charts exist - they are arithmetic over positions already computed and
cached - which is why they land in the tens of milliseconds. Davison pays for
one chart cast because it is a real chart.

## Cache and storage behaviour

* Compatibility results are cached in Redis for 7 days under a fingerprint of
  **both** people's birth data plus the engine and scoring versions, and
  persisted in `compatibility_reports`.
* Horary analyses are persisted in `horary_analyses`; the chart lives in
  `charts` like every other chart, never duplicated.
* Changing a saved person's birth data changes the fingerprint, so a new report
  is produced rather than an old one silently rewritten (tested).

## Assessment

Warm latency is comfortable everywhere (15-52 ms). Cold latency is fine for
synastry, composite and Davison. The horary analysis at ~1.2 s is acceptable
for a deliberate action the user just performed (they typed a question and
pressed a button) and is paid once per question, but it is the obvious
candidate for the background-job seam in B11 if the product later shows it
inline.

## Not measured

* Concurrency: all figures are single-request. The ephemeris work is CPU-bound
  and holds the GIL; behaviour under parallel load is untested.
* Multiple uvicorn workers sharing Redis.
* Horary analysis for charts where the significators are very slow planets
  (the forward search runs its full 30-day horizon more often).
