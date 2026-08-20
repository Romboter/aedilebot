# Phase 4: Admin Data Pipeline — Design Spec

**Status:** Approved for planning
**Date:** 2026-08-20
**Branch:** `rewrite/node-ts`
**Depends on:** Phase 3 hot-swap (`PluginHost<DataSnapshot>`, `data/dataStore.ts`) — done.
**Supersedes:** the "Admin Data Pipeline" and location-parser sections of
`C:\Users\Jason\.claude\plans\ok-i-have-more-iterative-ladybug.md` for the
locations portion specifically (weapons/vehicles parsing is still out of
scope and still stubbed, unchanged from that plan).

## Goal

Let an admin update `data/Locations.csv` (and eventually weapon/vehicle
data) after a Foxhole patch, through a Discord-native review flow, without
hand-editing files or restarting the bot — reusing Phase 3's `PluginHost`
for the final swap. Automate detection and data-gathering as much as
possible; a human always makes the final approve/reject call.

## Why this differs from the original plan

The original plan assumed a `WORKFLOW.md` (Unreal Engine map-export
tooling) already proven in this repo. It isn't in this repo — it lives at
`D:\SteamLibrary\steamapps\common\Foxhole\Modding\Tools\UnrealExporter-1.1.2\output\full\War\Content\Maps\Master\`
(`WORKFLOW.md`, `extract_relicbase_locations.py`, `convert_coordinates.py`,
`batch_analyze_relics.py`). That tooling only proves extraction for one
location type (Relic Bases), not the Town Center/Post Office/School TH
majority of today's 428-row `Locations.csv`.

During design, we found Foxhole's public War API
(`war-service-live.foxholeservices.com`) exposes live map data that covers
the Town Base types directly with no local export step:

- `GET /api/worldconquest/maps` — list of hex names (confirmed "OriginHex"
  present, matching the "ORIGIN" hex value already in `Locations.csv`).
- `GET /api/worldconquest/maps/{hex}/static` → `mapTextItems`: named
  locations (`text`, `x`, `y`, `mapMarkerType`). Confirmed live: OriginHex
  contains `{"text": "Arise", "x": 0.446..., "y": 0.423...}`, which matches
  the existing row `ORIGIN,Arise,Medium Relic` in `Locations.csv` — the
  location name comes straight from this field.
- `GET /api/worldconquest/maps/{hex}/dynamic/public` → `mapItems`:
  structure icons (`iconType`, `x`, `y`, `teamId`, `flags`). Per community
  documentation (clapfoot War API docs), `iconType` 56/57/58 = Town Base
  tiers 1–3, and 45/46/47 = Relic Base tiers 1–3.

This means Town Base rows (School/Post Office/Town Center TH) can be
derived entirely from the live API: no manual export, no attachment
upload, fully pollable. **Confirmed with the user**, Relic Base rows still
need the UE map export for accurate world-space x/y of the ruin itself —
the live API's relic-related `mapItems` entries aren't reliable/complete
enough to source position from directly — so relic ingestion stays a
hybrid: UE export gives position, the live API's `mapTextItems` gives the
name via nearest-marker matching (porting the same algorithm
`convert_coordinates.py`/`batch_analyze_relics.py` already use, just
against live marker data instead of a hardcoded list).

## Scope (v1)

**In scope:**
- Town Base locations (School TH, Post Office TH, Town Center TH) — fully
  live-API-derived.
- Relic Base locations (Small/Medium/Large Relic) — hybrid: admin-uploaded
  UE export + live API naming.
- Generic diff → review → approve/reject → swap pipeline, reusable for any
  future data type.
- A background Steam-patch watcher that *nudges* an admin channel to run a
  poll; it never applies data itself.

**Explicitly out of scope for v1** (unchanged from the original plan):
- Weapon/vehicle stat extraction — no proven source, `admin/gameFileParser/`
  stays a generic interface so this slots in later without a redesign.
- Fully automatic apply — a human always runs `/admin-data-approve`.
- A CLI equivalent (`scripts/admin-cli.ts`) — same open gap Phase 3 already
  flagged for `/admin_swap`; not attempted here either.

## Architecture & data flow

```
Town Bases (School/Post Office/Town Center):
  War API (live poll) → mapItems[iconType 56/57/58] + mapTextItems (nearest-name match)
                       → LocationEntity[]  ──┐
                                              ├→ diffEngine (vs current Locations.csv)
Relic Bases (Small/Medium/Large):             │      → ChangeSet → reviewStore (pending, id)
  UE map export (admin uploads, per WORKFLOW.md) │       → admin review/approve in Discord
    → relic x/y (world coords)                │       → Locations.csv rewrite + dataHost.swap()
    → War API mapTextItems (live, nearest-name match)
                       → LocationEntity[]  ──┘

Steam PICS watcher (background) → "Foxhole's Steam depot changed" signal
                                 → posts to admin channel: "run /admin-data-poll?"
                                 (a nudge, not an automatic trigger — approval still required)
```

Both sources normalize to the same shape — `LocationRow` (`schema.ts`
already has this: `{hexName, locationName, locationType}`) — before
hitting the diff engine, so `diffEngine`/`reviewStore`/the approve command
never need to know which source produced a row.

## Components

### `admin/warApi.ts`
Thin typed fetch wrapper for the live War API. No SDK dependency — plain
JSON over HTTPS, Node 22's native `fetch` covers it.

```ts
listHexes(): Promise<string[]>
getStaticMarkers(hex: string): Promise<MapTextItem[]>   // { text, x, y, mapMarkerType }
getDynamicMapItems(hex: string): Promise<MapItem[]>     // { iconType, x, y, teamId, flags }
```
Timeout + single retry on failure; a failed hex fails that hex's slice of
the poll cleanly (reported in the summary), never partially written.

### `admin/gameFileParser/locations.ts`
Implements the plan's generic parser interface:

```ts
interface GameFileParser<T> {
  dataType: 'locations' | 'weapons' | 'vehicles' | ...;
  parse(rawFiles: RawFileBundle): IntermediateEntity<T>[];
}
```

Two entry points feeding it:

- **`parseTownBases(hexes: HexMapData[]): LocationRow[]`** — pure function
  over already-fetched API data (fetching is `warApi.ts`'s job, this stays
  testable without network). For each hex: filter `mapItems` to iconType
  ∈ {56, 57, 58}, nearest-neighbor match each to that hex's
  `mapTextItems` (reuse the same Euclidean nearest-marker algorithm as
  `convert_coordinates.py`/`batch_analyze_relics.py` — Z ignored, 2D only),
  map iconType → locationType via a small constant table.
  - **iconType→locationType mapping needs one empirical confirmation
    pass** before this ships: poll a hex we already have ground truth for
    from the current `Locations.csv` (e.g. OriginHex) and check which of
    56/57/58 lines up with School vs Post Office vs Town Center. Flagged
    here rather than guessed — do this as the first step of
    implementation, not blocked on it now.
- **`parseRelicBases(mapName: string, relicJson: RelicExport[], liveMarkers: MapTextItem[]): LocationRow[]`**
  — takes the small JSON an admin exports locally via
  `extract_relicbase_locations.py` (portable ~80-line script; port to TS
  directly rather than shelling out to Python, keeping the pipeline
  dependency-free) and the live `mapTextItems` for that map. Converts
  world→API coordinates with a ported pure function:

  ```ts
  // world bounds are a per-map constant, confirmed identical across the
  // 3 sampled hexes in batch_analyze_relics.py — hardcode as config,
  // not auto-detected (WORKFLOW.md itself lists that as a "future
  // enhancement", not proven)
  function worldToApi(worldX: number, worldY: number, bounds: WorldBounds): { x: number; y: number }
  ```

  then matches each relic's converted position to the nearest *live*
  `mapTextItems` entry (not a hardcoded marker list) for both name and
  sanity-checking size tier.

### `admin/diffEngine.ts`
Generic: `IntermediateEntity<T>[]` in, `ChangeSet` out (added / removed /
modified vs. the currently-loaded `Locations.csv` rows). No dependency on
what produced the entities — same module serves town-base polls, relic
imports, and any future data type.

```ts
interface ChangeSet {
  id: string;
  createdAt: string;
  source: 'town-poll' | 'relic-import';
  added: LocationRow[];
  removed: LocationRow[];
  modified: Array<{ before: LocationRow; after: LocationRow }>;
}
```

### `admin/reviewStore.ts`
Pending `ChangeSet`s persisted as one JSON file per id under
`bot-ts/data/pending/<id>.json`. No database in this project and this
doesn't need one — matches the existing plain-file storage pattern
`data/dataStore.ts` already uses. `approve()` deletes the pending file
after a successful `Locations.csv` rewrite + swap; `reject()` deletes it
without writing anything.

### `admin/steamWatcher.ts`
Uses the `steam-user` npm package (anonymous Steam login, subscribes to
PICS changelist notifications) filtered to Foxhole's Steam AppID (to be
supplied). On a changelist hit for that app, posts a message to a
configured admin channel suggesting `/admin-data-poll`. New dependency —
no stdlib/native path exists for Steam's PICS protocol; this is the same
mechanism SteamDB itself uses. Never applies data itself — a notifier
only, so its failure mode is "no nudge," never data corruption. Smoke-
tested manually like `/admin_swap` was, not fixture-tested.

### Commands (all admin-only via `setDefaultMemberPermissions(Administrator)`, matching `/admin_swap`)

- `/admin-data-poll` — runs `parseTownBases()` against all hexes from the
  live API, diffs, stores a pending `ChangeSet`, replies with a summary
  embed (added/removed/modified counts + top changes) and the full diff as
  an attached file.
- `/admin-data-import <attachment>` — accepts the small relic-export JSON,
  runs `parseRelicBases()`, diffs, stores pending, same summary reply
  shape as above.
- `/admin-data-review <id> [locationtype]` — paginated drill-down into a
  pending `ChangeSet`.
- `/admin-data-edit <id> <entity> <field> <value>` — manual field-level
  correction to a pending `ChangeSet` before approval (parsers won't get
  every case right, especially the relic-matching heuristics).
- `/admin-data-approve <id>` — re-validates (including manual edits),
  rewrites `Locations.csv`, calls `dataHost.swap()` (reuses Phase 3's
  `PluginHost<DataSnapshot>` — this is the only step that mutates live
  data), records who/when.
- `/admin-data-reject <id>` — discards the pending `ChangeSet`.

## Error handling

- War API calls: timeout + retry-once per hex; a hex that still fails is
  excluded from that poll's results and called out by name in the summary
  reply — never silently dropped, never partially written into a
  `ChangeSet`.
- `Locations.csv` rewrite + `dataHost.swap()` in `/admin-data-approve`
  follows the same atomicity guarantee Phase 3's `PluginHost` already
  proved: a failed `validate()` leaves the live snapshot untouched and the
  command replies with the failure instead of silently discarding the
  pending `ChangeSet` (so the admin can retry approval without redoing the
  poll/import).
- Manual relic-JSON import: malformed/empty upload replies with a clear
  error and does not create a pending `ChangeSet`.

## Testing

- `parseTownBases`/`parseRelicBases` are pure functions over
  already-fetched/uploaded JSON → unit-testable with recorded fixtures,
  same golden-fixture discipline as the rest of this branch (snapshot a
  real API response once per hex used in tests, assert against that —
  not hand-derived expected output).
- `worldToApi`/nearest-marker-matching get targeted unit tests against the
  known-good example from `WORKFLOW.md` itself (API (0.71431875,
  0.58150333) ↔ World (46807.21, 15404.13)).
- `diffEngine` gets deterministic unit tests (added/removed/modified
  cases) with hand-built `LocationRow[]` fixtures — no network or game
  data dependency.
- `reviewStore` gets tests for the persist/load/delete cycle, same shape
  as testing any other file-backed store in this codebase.
- `steamWatcher` and the live `warApi.ts` calls themselves: manual smoke
  test only (like `/admin_swap`'s live verification in Phase 3) — no
  fixture suite for live network calls.
- Out of scope for automated testing (per the original plan's own
  carve-out, still holds): full gateway/e2e testing of the new commands
  beyond a manual click-through.

## Open items to resolve during implementation, not blocking this spec

1. **iconType→locationType mapping** needs one empirical confirmation pass
   against a hex with known ground truth before `parseTownBases` ships.
2. **Foxhole's Steam AppID** — user will supply.
3. **Admin channel ID** for `steamWatcher`'s nudge — needs a config value
   (env var, matching `TEST_GUILD_ID`'s pattern in `config/env.ts`).
4. Whether `extract_relicbase_locations.py`'s line-by-line brace-counting
   JSON parser needs any behavior changes when ported to TS, or is a
   direct line-for-line port — decide when writing that file, it's a
   small self-contained algorithm either way.

## Non-goals (explicit, so they don't creep back in)

- Auto-detecting per-map world bounds (WORKFLOW.md itself lists this as a
  future enhancement, not proven — stays hardcoded config).
- Fetching map markers from anywhere other than the live War API once
  this ships (no more hardcoded `API_MARKERS` list like the Python
  tooling used).
- Weapon/vehicle parsing (unchanged from the original plan's scope split).
- Any automatic apply-without-approval path.
