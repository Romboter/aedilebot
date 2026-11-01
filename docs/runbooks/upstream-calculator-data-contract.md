# AedileBot calculator input contract and asset-extraction priorities

## Provenance

Read-only inspection of original upstream repository `olted/aedilebot`, files `src/calculator.py`, `src/parse.py`, `src/bot.py`, `data/Weapons.json`, `data/Targets.json`, `data/Damage.json`, `data/Bunker_piece.json` and `data_manual/vehicle_targets.json`. This is a **requirements audit** only; no upstream code is pulled, merged, or modified. The target remains `Romboter/aedilebot`.

## Executed calculator behavior

- `/kill`: weapon base damage and `DamageType`; target `Health` and `Mitigation Type`; applied damage = ceil(base damage * (1 - damage mitigation)), optionally with scenario multiplier. Hits = ceil(target HP / applied damage). Selected ammo and mounted weapon variants must be explicit, rather than chosen by names.
- `/disable`: additionally reads `Disable Level`; current upstream uses remaining-health threshold `HP*(1.005 - Disable Level)`. Source of the 0.005 factor is **not** established by the extracted assets.
- `/dehusk`: reuses kill math against husk target catalog entries.
- `/custom_kill`: subtracts accumulated damage of weapon 1 then computes hits for weapon 2; type relationships and rounding apply separately.
- `/statsheet`: includes vehicle and aircraft armor HP, penetration bounds, disable chances, gun attributes, reload, structure repairs and decay. Not every displayed stat is consumed by the kill calculator.
- `/bunker_kill` and text bunker queries: read tiers, piece counts, component variants, red/green edges and wet hours. Bunker HP is a composite of per-piece `health[tier]` times multiplicative integrity `si[tier]`, with an additional topology term; bunker mitigation is tier-based. The wet multiplier is a scenario rule, not established to be a static class default. Additional bunker shelter mitigation is in code.

## Data files and field obligations

| Upstream input | Field obligations | Extraction hypothesis (NOT yet verified) |
|---|---|---|
| `data/Weapons.json` | key, `Name`, `Dev Name`, `Damage`, `DamageType`, `ObjectType`, `Additional Names` | `BPAmmoDynamicData`, weapon/mount class defaults, projectile instances, human aliases |
| `data/Targets.json` | `Name`, `Dev Name`, `Health`, `Mitigation Type`, `Disable Level`, `ObjectType`; secondary armor, penetration, repair and weapon slots | vehicle/structure defaults and components; target damage-class relation may be native |
| `data/Damage.json` | each `DamageType` against each mitigation category (e.g. tanks, garrison houses, structures, ships and aircraft) | inspect damage-type assets and native class constraints; do not assume DataTable alone contains matrix |
| `data/Bunker_piece.json` | per-tier piece `health`, `si`, `repair`; variants core, rg, mg, atg, hg, etc. | bunker piece classes, tier upgrades, integrity modifiers, repair and structural components; composition rules may be native |
| `data/Locations.csv` | player-friendly location aliases to target archetypes | human or map data; exact combat identity can stay separately indexed |
| `data_manual/vehicle_targets.json` | human-maintained vehicle values and labels | downstream comparison only, never an automatic production write |

## Priority-driven research backlog

1. **Damage matrix origin**: locate exact `DamageType` and target mitigation category declaration paths, original tags, native class boundaries and candidate rules. A resolvable ammo row **does not** establish mitigation. Separate serialized declaration, derived value and native/unknown.
2. **Target stats, especially structures**: systematically inventory `Health`, repair, decay, disable and mitigation category source properties in vehicles, buildings, defenses, emplacements and husks; verify exact class/owner and whether the field is a saved source default or runtime effective.
3. **Bunker piece variant/tier model**: find every piece class, upgrade and saved health/SI/repair candidate; explicitly report gaps where topology or wet multiplier are gameplay rules rather than asset properties. Do not infer piece integrity from a similarly named asset.
4. **Weapon/mount/ammo resolution**: continue exact class and DataTable relationships for multiple mounts and variants. Preserve existing `MultiAmmo` UE4.24 uncertainty in Issue #62. Report a weapon per actual mount and selected variant; never collapse to primary gun.
5. **Display stats and metadata**: armor, penetration, component disable chance, reload and ranges are required for stat sheets even when not directly used by the simple kill formula. Aliases and location spelling are a separate human-friendly mapping problem.
6. **Scenario/gameplay exceptions**: low-roll factors (upstream uses hard-coded 0.94 or 0.95 for different calculations), bunker shelter bonus, wet-concrete multiplier, penetration mechanics, special target cases and rounded damage need explicit independent validation or `manual_rule` provenance; they are NOT verified by source graph edges.

## Evidence and completeness schema

Every proposed derived field should eventually report:

- `source_build_id`, package or DataTable identity, SHA-256, exact export, field path and original property type (when inspected).
- `source_status`: explicitly serialized, exact indexed reference, exact target export verified, verified component owner, ancestor default candidate, or separately proven runtime effective.
- `runtime_effective`: true only with independent evidence; otherwise `not_established`.
- `gameplay_rule_source`: serialized field, validated engine rule, controlled game experiment, documented human rule, or unknown.
- `field_consumers`: `kill`, `disable`, `dehusk`, `statsheet`, `bunker_kill`, `custom_kill`.
- `criticality`: direct calculation requirement versus optional display attribute.
- `coverage`: total expected targets, exact matches, missing packages, native boundaries, ambiguous references, partial class defaults and human exceptions.

An export containing a numeric field is not proof that the calculator can safely use it. A damage calculation additionally requires verified specific weapon/ammunition selection, target damage-category semantics, modifiers, and rounding rules.

## Next private runner pass

Use the source-only domain inventory `scripts/audit_blueprint_domain_coverage.py` to locate candidate `Health`, `Mitigation`, `DamageType`, `Repair`, `Decay`, `SI` / structural integrity and tier field families. Print bounded summary frequencies, source owner types and normalized paths. Move from lexical candidates to exact typed links only after original serialized evidence. Prioritize gaps by whether they block `/kill` or `/bunker_kill`, not by raw ObjectPath frequency. No production catalog changes, upstream pulls, merges, raw PAK publication or Steam update.
