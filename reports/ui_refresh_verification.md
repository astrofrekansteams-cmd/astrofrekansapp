# Reference UI refresh — 2026-09-26

## Implemented

- Supplied `assets/logo/1logo.png` is bundled and used intact on welcome, splash and login.
- Welcome is now a single reference-inspired composition with language selection, four pillars and working register/login actions.
- Existing cosmic backdrop, darker translucent cards, serif page headings, rounded navigation and profile hierarchy are shared across the app.
- Finite staggered entrance animations, press/hover feedback and navigation selection motion honor reduced motion.
- Calendar shows actual event markers and a selectable month grid; changing month resets selection. Natal wheel includes zodiac symbols without changing calculations.
- Divination uses existing deck-back artwork before a reading, without fabricating results.
- Minimal web bootstrap added because the repository had no `web/` directory and profile web compilation failed without it.

## Verification

- Full Flutter suite: 145 passed, 2 skipped (`reports/ui_test_run.log`).
- Additional explicit visual capture run: 6 passed; each screen now uses its own test scope to avoid provider lifecycle leakage.
- Static analysis: clean on the checked Dart changes.
- Profile web build passed and is served at http://localhost:7357. Chrome at 430x932 verified welcome-to-login navigation; loaded captures are `reports/ui_after_welcome.png` and `reports/ui_after_login.png`.
- New tests: supplied logo, 320/430/1280 viewport layouts at 1.5 text scale, immediate reduced-motion content.
- Existing auth, navigation, logout, marketplace large-text and premium large-text checks pass. Offscreen controls are scrolled into view rather than assumed visible.
- Captures under `test/preview/` are widget previews; home/profile omit the shell and are not full-device acceptance evidence.

## Boundaries

This is a reference-inspired UI pass, not pixel-identical acceptance of all ten designs. Relationship results, consultant details, transit detail density and the complete tarot result composition still differ from the references. Backend-dependent screens retain their actual data and unavailable states; no sample score, expert availability or AI result was invented.

Native device performance and store readiness are not established by these local checks. Preview remains development/mock, not production integration.

Backend files modified: 0. Existing image assets modified/regenerated: 0. Git commit: no.
