# Astrofrekans Asset Rename Map

This mapping was prepared before any source move. All paths are relative to `C:/astrofrekans`.

## Folder moves

| Source | Destination | Reason |
|---|---|---|
| `assets/tarrot/` | `assets/tarot/` | Correct spelling. |
| `assets/backgraunds/` | `assets/backgrounds/` | Correct spelling. |
| `assets/tas-rune/` | `assets/rune/stones/` | Place rune stones under the rune domain. |
| `assets/app-thema/` | `assets/references/ui_screens/` | These files are visual specifications, not runtime screens. |
| `assets/dogumharitasi/` | `assets/natal_chart/` | Normalize the feature name. |

## Known filename corrections

| Source | Destination | Reason |
|---|---|---|
| `assets/gezegen/puluto.png` | `assets/gezegen/pluto.png` | Correct planet name. |
| `assets/gezegen/saturun.png` | `assets/gezegen/saturn.png` | Correct planet name. |
| `assets/tas-rune/lngwaz.png` | `assets/rune/stones/ingwaz.png` | Correct rune name. |
| `assets/dogumharitasi/aspect-line.png` | `assets/natal_chart/aspect_line.png` | Enforce lowercase_snake_case. |

## UI screenshot semantic names

| Source | Destination | Visual identification |
|---|---|---|
| `assets/app-thema/04bdc8c6-3497-4bcd-9f8b-f5e5a877ac56.png` | `assets/references/ui_screens/cosmic_calendar.png` | Kozmik Takvim screen. |
| `assets/app-thema/07cc11d7-18f7-4203-988e-8f99c81c4849.png` | `assets/references/ui_screens/natal_chart.png` | Doğum Haritam screen. |
| `assets/app-thema/16e6a90e-b355-4ef5-ab8e-3dc2dbdb8fbf.png` | `assets/references/ui_screens/profile.png` | Astrofrekans profile screen. |
| `assets/app-thema/755e9d0f-3c5f-45b0-b952-a1599cdb620a.png` | `assets/references/ui_screens/transits.png` | Transitler screen. |
| `assets/app-thema/81da2f94-6e26-47fa-b96e-5eeedd5de16a.png` | `assets/references/ui_screens/compatibility.png` | Uyum Analizi screen. |
| `assets/app-thema/9bf23e5d-713e-4f06-8b0c-52e64225856e.png` | `assets/references/ui_screens/consultants.png` | Canlı Danışmanlık screen. |
| `assets/app-thema/c4dc11cc-d22c-490c-96a5-6acf1e1e4021.png` | `assets/references/ui_screens/home.png` | Bugünün Frekansı/home screen. |
| `assets/app-thema/d6b71bc7-7950-44d1-834d-3871f8e16420.png` | `assets/references/ui_screens/astro_ai.png` | Astro AI conversation screen. |
| `assets/app-thema/e57798f5-1714-438e-a611-9b7643db35cc.png` | `assets/references/ui_screens/tarot.png` | Tarot screen. |
| `assets/app-thema/login_register.png` | `assets/references/ui_screens/login_register.png` | Login/register screen; name already semantic. |

## Daily-frequency semantic names

| Source | Destination | Visual identification |
|---|---|---|
| `assets/kategori/116b61bb-4123-45d2-b6b8-66467896db0f.png` | `assets/kategori/love.png` | Heart with orbital ring. |
| `assets/kategori/3e34eb61-b400-46f6-a41c-0425808dfe66.png` | `assets/kategori/health_balance.png` | Lotus/meditation emblem. |
| `assets/kategori/46e809ba-d6cc-45f5-a830-c10f7a5902eb.png` | `assets/kategori/general_energy.png` | Radiant sun emblem. |
| `assets/kategori/93ee8630-2111-4ba8-8a6f-a725d013a633.png` | `assets/kategori/career.png` | Briefcase emblem. |
| `assets/kategori/f06eaffc-0a89-4fad-b0ba-bffa643fa17c.png` | `assets/kategori/important_hours.png` | Hourglass emblem. |
| `assets/kategori/f171b089-7f1f-4b2f-95d4-c535a1555a72.png` | `assets/kategori/money.png` | Gold fortune sphere/coin-like emblem. |
| `assets/kategori/f6e8d555-a5c3-4bb9-b74b-3a6c1568333e.png` | `assets/kategori/luck.png` | Four-leaf clover emblem. |

## Safety procedure

1. Record all original relative paths, byte sizes, and SHA-256 hashes.
2. Copy the untouched originals to `assets/masters/original_2026_09_22/`.
3. Verify the master copy by SHA-256 before any move.
4. Apply the mapping only when every destination is absent.
5. Verify the post-move inventory and retain the original hash manifest.
