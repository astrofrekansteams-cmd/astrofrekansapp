# B12B backend/Flutter contract issues

Backend and Firebase rules are read-only for this phase. No backend, migration, rule or asset file was changed.

| BACKEND FIELD / PATH | FLUTTER FIELD / PATH | TYPE | SEVERITY | RECOMMENDED FIX |
| --- | --- | --- | --- | --- |
| `GET /experts`: no free-text `q`/`search` parameter | Discovery search box | Missing API capability | Medium | Add a server-side text search contract if global discovery is required. Flutter currently labels and limits search to the loaded page; it does not send an invented parameter. |
| Backend Admin SDK writes `presenceVisibility/{uid}/{conversationId}/{partnerUid}`; RTDB rule reads `presenceVisibility/{uid}/{partnerUid}` | `FirebaseConsultationPresence.watchPartner` reads `presence/{partnerUid}` after backend-scoped presence lookup | Projection/rule path mismatch | High | Align the backend projection and RTDB rule in a separately owned backend/Firebase rules phase, with emulator tests for active, closed and unrelated users. Current partner-presence reads may be denied even for members. Do not broaden reads in Flutter. |
| No `GET /expert/appointments/{id}`; only `GET /expert/appointments` list | Expert appointment detail route | Missing detail endpoint | Low | Add a member-scoped expert detail endpoint if needed. Flutter derives the current detail from the authorized expert list and refreshes that list after cancellation. |

Environment gaps (not invented API mismatches): backend `/auth/capabilities` currently reports `firebase_configured=false`; native Firebase config is absent. Firestore, RTDB, Storage and FCM real-project behavior is therefore not verified. Firebase CLI is present but its emulator requires Java 21+ while this host has Java 17.
