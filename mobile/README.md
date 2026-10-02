# Mobile Companion App (section 34) — not built yet

The spec calls for an optional Flutter companion app (live map, sensor
status, occupancy, tracking, session control, alerts, historical sessions,
basic configuration) that talks to the same backend as the CLI and web
dashboard, without duplicating backend logic.

**This directory is a placeholder.** Given the scope of the rest of the
platform, the mobile app was not built in this pass — building it honestly
(rather than a stub screen) is a multi-day Flutter project on its own.

## What's already in place to support it

Nothing mobile-specific needs to change on the backend — `mobile/` would be
a thin Flutter client of the exact same REST + WebSocket API documented in
[../docs/api.md](../docs/api.md):

- `GET /api/status`, `/ws/map` → live map / sensor status / occupancy
- `/ws/tracking` → tracking
- `/api/sessions/*` → session control / historical sessions
- `/api/system/config` → basic configuration

## Suggested starting point

```bash
flutter create am_map_mobile
cd am_map_mobile
flutter pub add web_socket_channel http provider
```

Mirror the web dashboard's data flow (`frontend/src/state/store.ts` and
`frontend/src/api/`) — same endpoints, same `MapSnapshot` shape
(`frontend/src/types.ts`), different rendering layer (e.g. `flutter_map` for
a 2D top-down view rather than a full Three.js 3D scene, which is a
reasonable first cut for mobile).

## Note on phone CSI

Stock iOS/Android WiFi stacks do not expose Channel State Information to apps. A mobile companion would visualize maps from the backend or talk to a nearby ESP32/Raspberry Pi CSI node — it cannot turn a normal phone into a CSI sensor.
