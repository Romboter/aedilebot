# Asset-derived game data: evidence and generation contract

**Status:** Proposed Phase 4 contract, review-only. No Steam polling, scheduling,
automatic data writes, PR creation, production activation, or merges are enabled
by this document.

**Baseline:** Foxhole public depot build `26058282`, as reported from a licensed
Blueprint export. Store the corresponding PAK SHA-256 and exact export file/field
paths in the *private* audit workspace before independently signing off a mapping.

## Outcome

AedileBot is a **compiler of current game facts**, not a list of old numerical
answers. For every game-data field, try to produce a deterministic value from a
specific, pinned Foxhole build. Preserve hand-maintained display names and aliases.
Where game assets do not establish a value, retain an explicitly labelled manual
rule or a review-blocking unresolved state; never select an equal-valued, unrelated
row to make the arithmetic match.

Target files: `Weapons.json`, `Targets.json`, `Damage.json`,
`Bunker_piece.json`, and `Locations.csv`. This specification covers the
cross-cutting identity/provenance contract, not a claim that all five are ready
to regenerate.

## Source-of-truth rules

| Value | Preferred source | Fallback / gate |
|---|---|---|
| Ammunition direct damage and damage type | `BPAmmoDynamicData` row referenced by the *actual firing weapon* | Unresolved without a trustworthy ammo edge |
| Weapon/mount multiplier | Named `BPWeaponDynamicData` or `BPMountDynamicData` row reached through a Blueprint reference chain | Explicitly reviewed, build-scoped manual rule, never a numerical proxy |
| Seat / barrel identity | Vehicle Blueprint seat's `MountCodeName` → component class → inheritance/default ammo | Unresolved if missing, ambiguous or native-only; inspect each seat independently |
| Vehicle/structure HP | Matching developer identity → dynamic-data `MaxHealth` | Block on ambiguous joins and mismatched source identity |
| Structure armour, bunker tiers | Blueprint/inherited properties and appropriate DataTables when present | Some native runtime fields remain unresolvable from exports; curated overlay with provenance, review on drift |
| Mitigation | `DTDamageProfiles` | Explicit review for missing/manual columns |
| Map locations | Current game's actual map actors and stable coordinate transformations; static War API naming where needed | Ambiguous nearest names / changed actor counts flagged |
| Human-facing names/aliases | Curated sheet values | Preserve; do not replace with game asset names |

### Damage computation

For a resolved firing endpoint:

```text
damage = current_ammo_damage × validated_damage_type_rule × actual_mount_or_weapon_multiplier
```

The existing 1.25 kinetic factor and some game-observed damage behaviour have **not**
been proven to live in exportable game tables. Treat these as *versioned manual
rules* (separately reviewable and testable), not as automatically derived values.
A formula reproducing 98/98 existing sheet values is a numerical reconciliation,
**not** evidence that 98 asset identities were independently verified.

### Asset graph and evidence

Every successful resolution needs a chain of **explicit, typed edges**:

1. A concrete vehicle/weapon/structure Blueprint, not just a display name.
2. A specific gunner seat or weapon endpoint to an actual component via a named property.
3. The component and its parent class/default-property chain through to the
   ammunition development identifier.
4. The firing component's **own** dynamic-data row by name, including its multiplier.
5. The ammo row and all source rules needed to compute the number.

Record with each edge: game build, vanilla PAK SHA-256, exporter and
CUE4Parse revision, source asset path, exported JSON property path, explicit
value, inheritance step where relevant, and private export checksum.
The public repo may contain only safe derived identifiers, audit conclusions
and non-proprietary metadata; raw exports and Steam credentials remain private.

A matching number, same prefix, multiple identifiers in the same actor,
an HV/LV label, or an existing sheet value **must not** be used to create an edge.
No edge is inferred from a native implementation that is not actually exported.

### Concrete baseline: Colonial Destroyer machine gun

On build `26058282`, the user-reported exported Blueprint relationship is:

```text
BPLargeShipDestroyerC
  GunnerSeat4 / GunnerSeat5
    MountCodeName = LargeShipDestroyerCMachineGunner
      BPLargeShipDestroyerCMachineGunner
        inherits BPColVehicleMachineGunnerComponent
          ammo = MGAmmo
      BPMountDynamicData.LargeShipDestroyerCMachineGunner
        DamageMultiplier = 1.20
```

See `data_manual/weapon_asset_identity_candidates.json`. The build is pinned,
but source file/property paths, hashes, and independent review have not yet
been supplied to this repo. That metadata remains a **reported source-backed
candidate**, not a generator-approved identity.

The existing `Ship 12.7mm (+20% HV)` maps to the unrelated
`Weapon:AssaultRifleHeavyW`. Replace that *numerical proxy* only after
source sign-off **and a scope decision**. A generic `Ship 12.7mm` sheet row may
represent multiple vessels with different mounts; one Destroyer link is not
proof for every ship. A per-vehicle/mount key may be required.

A battleship MG seat-to-mount relationship was also reported, but **no exact
identifiers are available in this repo**. Do not fill them in by analogy.

## Per-field resolution states

- `asset_derived`: complete traced source chain from a pinned game build,
  with private proof and reviewed extraction rules.
- `rule_derived`: numerical value calculated with a disclosed manual rule
  (e.g., the currently observed kinetic 1.25); preserve rule version.
- `curated`: manually maintained alias/name or genuinely inaccessible numeric
  field, with provenance and validation against observable data.
- `unresolved`: missing asset edge, ambiguous candidate, native-only value,
  changed row/inheritance path, missing source table, or insufficient export.
- `not_applicable`: field intentionally absent for this kind of asset.

A value may include multiple provenance facets (e.g., asset-backed ammo with
a rule-derived kinetic adjustment). Never relabel such output `asset_derived`
end-to-end if any numeric factor is still a manual rule.

## Controlled processing stages (not enabled)

1. **Detect:** Compare Steam public-branch build ID (appid `505460`) with the
   last approved/processed build. Detection alone does not authorize download.
   Log detection attempts and failures; never overwrite a last-approved marker
   with a new *observed* ID before successful review.
2. **Acquire:** After the operator releases a controlled run, SteamCMD downloads
   the licensed Windows depot on the private runner into existing managed
   storage. Pin the build ID and SHA-256 of the exact vanilla PAK.
3. **Extract:** Export named DataTables and the *specific* Blueprint defaults,
   parent classes, weapon components, vehicle seats and relevant map actors.
   Pin extractor revision. Keep raw exports private.
4. **Resolve:** Build explicit identity graphs for infantry, vehicles, tanks,
   artillery, aircraft and large ships. Enumerate all firing endpoints; do not
   assume one vehicle = one gun. Missing/ambiguous references fail closed.
5. **Generate:** Compute from the current game build, preserve curated fields,
   record per-field provenance, and produce a machine-readable coverage report.
6. **Validate:** Check old/new assets, field-level diffs, known goldens, runtime
   loader schema, number sanity, missing joins and unexplained coverage loss.
   Compare the result against approved game-observation fixtures.
7. **Review PR:** A separate GitHub-hosted job with tightly scoped public-repo
   credentials may open a data PR with only approved derived outputs and a
   provenance/coverage summary. A human reviews and merges; never auto-merge.
8. **Activate:** The bot stages an approved immutable data bundle, validates
   schema and referential integrity, then atomically swaps snapshots. On any
   error it retains or rolls back to the previously approved snapshot without
   restarting. Notify admins and keep an audit trail.

**No automatic scheduling, unattended SteamCMD, production data writes,
GitHub PR creation or live swaps until independent audit backup and restore,
identity verification, controlled build detection and loader safeguards pass
their separate reviews.** See PR #50 for the audit-history backup gate.

## Immediate acceptance gates

- A synthetic equal-multiplier unrelated mount must never resolve a weapon.
- A changed named mount row or missing inherited-ammo edge must be unresolved.
- Baseline two-seat Destroyer chain independently reproducible from build
  `26058282`, with private evidence hashes.
- Enumerate and classify all current sheet entries: identity hints do not
  automatically become verified chains. Include tank, aircraft, ship,
  infantry and indirect weapons in the inventory.
- A build transition cannot silently reuse an old mapping or manual factor.
- Deterministic rerun of the same inputs yields byte-identical generated
  numeric data; a new build yields a reviewable delta, not a production update.
- Approved aliases remain byte-identical unless changed by a separately
  reviewed editorial update.
- Independent off-host audit-history restore drill and bot rollback drill pass.

Related: [weapon tracing](../../runbooks/weapon-asset-tracing.md),
[Phase 4 design](2026-10-31-phase4-automated-data-pipeline-design.md),
[Issue #44](https://github.com/Romboter/aedilebot/issues/44).
