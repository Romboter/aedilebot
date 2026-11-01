# FoxBunker public bunker-model source review and AedileBot integration map

Reviewed: 2026-11-01. **Research-only**, not a game-runtime assertion or a proposal to copy FoxBunker's implementation.

## Source provenance

Target is **FoxBunker**, Tsekho's public browser calculator: https://foxbunker.com/bunker/ , not the unrelated open-source Foxhole Planner. The normal search reader exposes only the rendered page; the existing restricted `foxrunner` retrieved publicly served **same-origin JavaScript** as read-only HTTP GETs, without executing JavaScript or uploading copies.

- Private source discovery: https://github.com/Romboter/foxhole-lab/actions/runs/41348953519
- Bounded formula/relationship inspection: https://github.com/Romboter/foxhole-lab/actions/runs/41349081904
- FoxBunker https://foxbunker.com/bunker/js/utils.js: SHA-256 `9f781ca6f7f1d523c4a22f51dd380f0bc2ff38436d829098199de4209f9e69de`.
- FoxBunker https://foxbunker.com/bunker/js/bunker.js: SHA-256 `62ba5c377ab9a5e48970e6291e994a943c623ce2ba7889bcd234ba337081320c`.
- FoxBunker https://foxbunker.com/bunker/js/share.js: SHA-256 `5dcf64f5e7b0282045a777a57f4f7018cd0d45600dc17c0637e7d1b1125f098a`.
- Source comparison: read-only `olted/aedilebot/data/Bunker_piece.json` and `src/calculator.py` via the GitHub connector (upstream untouched). These files represent the upstream **bot's own model**, not authoritative game-engine source.

These are reproducible fingerprints of public browser code **as served on the inspection date**; the website can change independently. No source code was copied into the research fork.

## FoxBunker's actual data model

`utils.js` contains 22 per-piece structure definitions. Each defines a display label, short label, minimum tier and per-tier six-value tuple. The tuple is read by `Bunker.recalc()` in this order:

| Position | Interpretation from use |
|---|---|
| 0 | Piece structural-integrity multiplier |
| 1 | Piece health contribution |
| 2 | Piece repair-cost contribution |
| 3 | Dig/build contribution |
| 4 | Basic-material contribution |
| 5 | Concrete-material contribution |

`Tile` stores geometry (start coordinate, shape and orientation), a separate tier and a structure type. Its `Wall` objects have endpoints, wall type, a reciprocal `socket` for physical attachment, and a classification of the socket. `Bunker` owns a network of connected tiles rather than one single static class. The site tests *matching wall endpoints and opposite directions* to attach adjoining pieces; this is a geometry-derived relationship independent of any UE Blueprint parent path.

`OVERS` identifies types whose face-to-face contact does **not** count as a qualifying green edge (the site includes certain garrison types). This distinct red/green classification explains why counting connected bunker tiles alone is insufficient for compactness.

`share.js` serializes a bunker as a versioned set of spatial tile records: lattice coordinates, shape and direction, tier, type and rotation. Those records capture **layout geometry** missing from a simple piece-count-based calculator. The shareable URL schema belongs to FoxBunker, not an in-game object identity.

`TURRET_PROFILES` separately encodes sight/arc information for some garrisons and changes with tier. Line-of-sight geometry belongs to a different layer than incoming damage or ammo/mount class identity.

## FoxBunker network mathematics (observed browser implementation)

For pieces `i`, each with explicit tuple `si_i, hp_i, repair_i`:

1. Sum raw piece health and repair costs separately: `raw_HP = sum(hp_i)`, `repair = sum(repair_i)`.
2. For multiple pieces, compute baseline integrity `I0 = product(si_i)`. For one piece, the site uses `I0=1` for effective integrity, despite retaining its own raw component multiplier as metadata.
3. Derive `green` and `red` connection counts by inspecting qualifying walls once, not estimating them from total bunker size. Green means a qualifying internal socket, red means external or a nonqualifying joint.
4. If at least one eligible edge is counted, compute compactness candidate `B = 0.15 * green/(green + red)`. Limit the awarded bonus by **both** available room to 100% and the baseline integrity: `B_eff = max(0, min(B, 1-I0, I0))`.
5. Final integrity is `I = min(1, I0 + B_eff)`. The displayed HP is `round(raw_HP * I)`; breachable percentage is `100*(1-I)`. The UI's "after N HP" threshold is `round(displayed_HP * I)` in remaining HP, not independently proven effective runtime breach code.
6. Repair efficiency is `displayed_HP / total_repair`. The site keeps dig/bmat/concrete construction totals separate from those two combat values.

The old upstream bot independently multiplies structural values and applies a similar compactness term from *user-supplied or estimated* red/green dots, but it lacks FoxBunker's `min(1-I0,...)` cap. It can therefore return `I > 1` in artificially eligible cases. Its public `calculate_breachable_health()` helper computes `raw_HP*(1-I)`; this result is currently assigned but not otherwise used in `src/calculator.py`, so do **not** call that an active damage-calculation defect without further tests. The bot calculates a wet-concrete multiplier separately; FoxBunker's `Bunker.recalc()` does not model that same input in the inspected path.

Neither model is the actual compiled game runtime. Even close agreement does not prove exact gameplay results, rounding stages, or that every named tier is buildable.

## Reference-table comparison (read-only; exact values, not game verification)

The publicly served FoxBunker `STRUCTURES` table contains **22** named types. A deliberately explicit alias crosswalk was used to compare against the upstream bot's **17** `data/Bunker_piece.json` keys:

| Bot key | FoxBunker label |
|---|---|
| core | Base |
| piece | Blank |
| ramp | Ramp |
| med | Med Bunker |
| shelter | Artillery Shelter |
| rg | Rifle Garrison |
| mg | Machine Gun Garrison |
| obs | Observation Bunker |
| eng | Engine Room |
| atg | Anti-Tank Garrison |
| hg | Howitzer Garrison |
| ammo | Ammo Room |
| ic | Intelligence Center |
| sc | Storm Cannon |
| ws | Weather Station |
| fortress | Underground Fortress |
| radar | Interceptor Array |

Of the per-tier source rows allowed by these type definitions, **39 of 39** exactly matched between FoxBunker and the upstream bot for the three comparable fields (integrity, HP, repair). Missing T1/T2 tier tuples were only treated as unsupported when the upstream counterpart was zero/absent; absent tiers were not counted as positive matches. No unexpected numeric differences occurred in the 39 supported cases.

Five other FoxBunker types do not have their own dedicated upstream `Bunker_piece.json` key: **Corner, Fire Station, Hearth, Foundation and Radar**. Crucial naming trap: the bot key `radar` matches FoxBunker's **Interceptor Array** large structure constants, *not* FoxBunker's separately named **Radar** type. Do not fuzzy-match these and silently replace game data. Some missing types may be deliberately represented by generic `piece` values, but that requires independent verification.

## Where this joins our pinned Foxhole asset work

Our own restricted game asset run https://github.com/Romboter/foxhole-lab/actions/runs/41347602989 separately established **507** exact original `NameProperty` → `FName` structure class-default `CodeName` to `BPStructureDynamicData` row source identities, covering **506 distinct** rows out of the table's 592 rows. These rows expose serialized `MaxHealth`, `StructuralIntegrity`, `RepairCost`, `DecayStartHours`, `DecayDurationHours` fields and others. **This is source identity, not engine proof that a runtime structure consumes that row as its effective value.**

The architecture should retain four independently sourced layers:

1. **Game identities:** `BlueprintGeneratedClass`, saved `Default__*.CodeName`, exact dynamic row key, SHA-256 and original property type; no inferred runtime CDO inheritance.
2. **Piece type/tier stats:** explicit row-backed health/repair/SI candidates; manual normalized aliases for `rg`, `atg`, `radar`, etc., with status/provenance and version.
3. **Layout topology:** placed piece instances, shape/rotation, reciprocal wall connections, qualified green/red edges and actual network membership. Not derivable from item classes or a DataTable alone.
4. **Combat/scenario rules:** damage type × target mitigation, breach checks, curing/wetness and sheltered effects, plus any native `/Script/War` behavior; keep unverified mechanics separate.

Do not promote `TURRET_PROFILES` to mount/ammo/damage relationships. For operational AedileBot calculation, compare FoxBunker's geometry to the bot's `estimate_red_green()` approximation using independent, preferably in-game, layout fixtures.

## Next acceptance criteria

- Resolve the game-sourced exact rows representing bunker bases, blank pieces, corner, garrisons, rooms and large structures, with source-only class and type evidence.
- Record `structuralIntegrity`/`MaxHealth`/`RepairCost` row field value **presence and per-row provenance**, keeping source exports private; check actual numbers against FoxBunker and bot catalogs only as independently reviewed candidate values.
- Implement a separately tested topology component that counts green and red eligible wall joints by actual geometry and distinguishes absent layout from approximate counts.
- Test compactness clipping at 100%, zero-edge cases, one-piece integrity and qualifying/nonqualifying garrison adjacency; do not apply a bug fix to upstream production calculator without review.
- Keep wet concrete, shelter mitigation, and damage matrix outside the geometry model. Preserve Issue #62 CDO uncertainty and Issue #86 missing/inherited structure CodeName statuses.
- No upstream pulls/merges, production bot writes, Steam updates, or raw public game exports.
