# B12A backend contract issues

Backend files were read only. The following frontend requirement cannot be completed without a backend contract change:

| Backend contract | Flutter requirement | Severity | B12A handling | Recommended follow-up |
|---|---|---|---|---|
| `GET|POST /saved-people`, `DELETE /saved-people/{id}`; no `GET /saved-people/{id}` | Read saved person by ID | Low | Read via the authenticated owner's list and match ID. Missing ID returns not-found. | Add owner-scoped detail endpoint if list pagination or size makes this unsuitable. |
| No `PATCH`/`PUT /saved-people/{id}` | Update saved person | Medium | Edit is explicitly unavailable; no delete-and-recreate workaround, which could invalidate references. | Add owner-scoped update endpoint with validation and authorization; then wire the form. |

Source: `docs/api_contracts.md`, Saved People section, and local B11 OpenAPI/route inspection. No backend contract or source file was changed.
