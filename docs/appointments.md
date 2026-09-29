# Availability, Slots and Appointments

Two hard problems live here: daylight saving time, and two people clicking the
same slot at the same moment.

## Availability is stored in local time

An expert says "Mondays, 09:00 to 12:00, Europe/Istanbul". That is a statement
about *local* time and it stays true across a DST change — they still start at
nine. So the schedule is stored as **local time plus a zone**:

```
weekday, start_local_time, end_local_time, timezone
```

Converting to UTC at write time would silently move their morning by an hour
twice a year. Storing the zone also means an expert moving countries changes
their future availability without touching appointments that already exist.

A window that crosses midnight is entered as one window per local day. The
check constraint `start_local_time < end_local_time` makes that explicit
rather than letting a wrapped window produce a negative duration.

## Exceptions

Stored in **UTC**, because they are absolute instants rather than recurring
local statements.

| Type | Effect |
| --- | --- |
| `vacation` | removes time |
| `busy` | removes time |
| `manual_block` | removes time |
| `extra_availability` | **adds** time |

Extra availability is applied first, then every blocking exception is
subtracted. A block in the middle of a window splits it into two, which is
what a two-hour meeting in the middle of a working day should do.

## DST, precisely

Two things go wrong at a transition, and both are handled explicitly rather
than left to the library.

**Spring forward — the time does not exist.** On 2027-03-28 in Berlin, 02:30
never happens. Python will happily *construct* it, so the check is a round
trip: convert to UTC and back, and see whether the clock agrees with itself.
A window whose start falls in the gap is **skipped**, not shifted — silently
moving it to 03:30 would put an expert in a meeting they did not agree to.

**Autumn back — the time happens twice.** On 2027-10-31 in Berlin, 02:30
occurs at 00:30 UTC and again at 01:30 UTC. **Both slots are generated.** They
are different instants an hour apart, and discarding one would lose an hour of
genuine availability. `fold=0` and `fold=1` produce them; if the two agree,
there was only one.

```python
utc_instants(date(2027, 3, 28), time(2, 30), BERLIN)   # []  - skipped
utc_instants(date(2027, 10, 31), time(2, 30), BERLIN)  # two instants
utc_instants(date(2027, 3, 28), time(9, 0), ISTANBUL)  # one - no DST since 2016
```

Tested against `Europe/Istanbul` (the control — permanently UTC+3),
`Europe/Berlin` (EU transitions) and `America/New_York` (US transitions, on
different dates). The tests assert the slot list is **non-empty** before
checking its contents, because a vacuous loop over an empty list proves
nothing.

## Slot generation

`GET /experts/{id}/slots?service_id=&from=&to=` combines:

1. the weekly schedule, resolved per local day against that day's offset
2. exceptions (extra added, blocks subtracted)
3. existing appointments and live holds, **padded by the buffers**
4. the service duration and the configured granularity
5. minimum notice and the booking horizon

UTC is canonical. The display timezone travels alongside so a client can
render what the user will see, but nothing is ever scheduled against a local
string.

Buffers are applied during generation rather than at booking time, so the slot
list and a booking attempt agree about what is free. If they disagreed, a user
would be shown a slot the booking then refused.

Generation walks a day either side of the requested range: a window late in an
expert's local evening can land inside the requested UTC range while belonging
to the previous or next local day.

| Setting | Default | Meaning |
| --- | --- | --- |
| `APPOINTMENT_SLOT_GRANULARITY_MINUTES` | 15 | Step between candidate starts |
| `APPOINTMENT_BUFFER_BEFORE_MINUTES` | 5 | Padding before a booking |
| `APPOINTMENT_BUFFER_AFTER_MINUTES` | 5 | Padding after |
| `APPOINTMENT_MINIMUM_NOTICE_MINUTES` | 120 | How soon is too soon |
| `APPOINTMENT_MAX_HORIZON_DAYS` | 90 | How far ahead bookings open |
| `APPOINTMENT_MAX_SLOT_QUERY_DAYS` | 92 | Largest single query |

Booking re-checks through the **same generator**, so a hand-crafted request
for 03:00 on a Sunday is refused even though the row would fit. Anything that
was never offered cannot be booked.

## Double booking

This is the invariant the phase exists to protect.

"SELECT to check, then INSERT" does not achieve it. Two requests can both run
the SELECT before either runs the INSERT, and both find the slot free. The
window is milliseconds wide and it is exactly the window a popular expert's
10:00 slot lives in.

So Postgres enforces it:

```sql
ALTER TABLE appointments
ADD CONSTRAINT ex_appointments_no_overlap
EXCLUDE USING gist (
    expert_id WITH =,
    tstzrange(starts_at_utc, ends_at_utc, '[)') WITH &&
)
WHERE (status IN ('pending', 'confirmed'));
```

Two overlapping live appointments for one expert cannot exist, whatever the
application does. `btree_gist` is required because `expert_id` is a uuid and
gist does not handle equality on uuid without it. The same shape guards active
slot holds.

The application-level check is still there — it produces a readable `409`
instead of an integrity violation and catches the common case before any work
— but it is the *second* line of defence. When both run, the database wins and
the loser gets a clean `slot_unavailable`.

An `IntegrityError` rolls the session back before the domain error is raised.
Leaving that to the caller surfaced as a `PendingRollbackError` from the next
statement anybody ran, which is how the defect was found.

**Verified, not assumed.** `python -m scripts.booking_concurrency_check` runs
10 concurrent attempts on the same slot against real Postgres. Last run:
1 booked, 9 `slot_unavailable`, no unmapped errors; and 1 held, 9 refused for
the hold path.

SQLite has no exclusion constraints, so the unit tests prove the state machine
and the script proves the locking. Both are needed.

## Slot holds

A hold is a short-lived claim while an order is being placed. Without one,
two people filling in a booking form both believe they have the slot and one
finds out at the very end.

```
active ──consume──► consumed      (the booking succeeded)
   │
   ├──release──► cancelled        (abandoned deliberately)
   └──expiry───► expired          (walked away)
```

`SLOT_HOLD_TTL_SECONDS` (default 600) is long enough to finish a checkout and
short enough that an abandoned form does not hold a popular slot hostage.
Expired holds are retired before any availability decision, so an abandoned
hold never blocks the slot beyond its TTL.

A user's **own** hold is consumed *before* the availability and overlap checks
run — both treat a live hold as busy, so without that ordering a user would be
refused their own booking. A later failure rolls the transaction back, hold
included.

## Appointment lifecycle

```
pending ──confirm──► confirmed ──complete──► completed
   │                     │
   ├──cancel──► cancelled ◄──cancel
   └──no_show──► no_show ◄──no_show
```

`pending` and `confirmed` are the **live** states: they occupy a slot, they
appear in the exclusion constraint's predicate, and they are what blocks
generation. `cancelled`, `completed` and `no_show` release the slot.

`complete` and `mark_no_show` exist as service methods with no routes yet —
the surface that drives them belongs to the consultation phase. They are here
so an order can be completed and reviewed without inventing state later.

Cancellation records **who** and **why**:

| Actor | Meaning |
| --- | --- |
| `user` | the client cancelled |
| `expert` | the practitioner cancelled |
| `admin` | moderation |
| `system` | automated (e.g. an unpaid order expiring) |
| `technical_failure` | the platform's fault |

No refund is computed in this phase. The actor is captured because refund
policy will depend on it and it is only knowable at the time.

## Timezones and stored appointments

Appointment times are UTC. `timezone` records what the user saw when they
booked, for display only.

Consequently an expert changing their profile timezone **does not move
existing appointments** — tested explicitly. Their future availability
changes; their commitments do not.

## Known limitations

- Slot generation is computed per request with no caching. At 40 experts a
  90-day query takes ~44 ms against real Postgres; a caching layer becomes
  worthwhile when the horizon or the population grows, and it is not there
  yet.
- Granularity is global rather than per service. A 15-minute step for a
  90-minute service produces overlapping candidate starts, which is intended
  (it offers more choice), but an expert cannot ask for "on the hour only".
- Recurring exceptions are not modelled. A weekly lunch break is either seven
  narrower windows or a series of one-off blocks.
- No waiting list and no "notify me when this frees up".
- Holds are not surfaced to the expert. They see a slot vanish and reappear.
