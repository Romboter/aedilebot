# Aedile answerability case study: 75mm against Silverhand Mk. IV

**Purpose:** Source-trace one real Discord question, not merely index game assets.  
**Question:** `/kill target:Silverhand weapon:75mm`  
**Game:** pinned, read-only Foxhole Steam build `26058282`.  
**Status:** source-backed **legacy 3-hit calculation under explicitly stated assumptions**. Native runtime penetration and armor/damage mechanics remain unverified. **Not a guaranteed in-game shot count.**

## Aedile human baseline (existing catalogs, unchanged)

| Input | Existing value / identity |
|---|---|
| Attacker display key | `75mm` |
| Ammo Dev Name | `BattleTankAmmo` |
| Base damage | 1750 |
| Damage type | `Explosive` |
| Defender display key | `Silverhand - Mk. IV (SvH)` |
| Defender Dev Name | `MediumTankW` |
| Max health | 3100 |
| Mitigation type | `Tier2Tank` |
| `Explosive` × `Tier2Tank` mitigation fraction | 0.15 |

The actual legacy Python calculator in `src/calculator.py` computes per-hit damage as `ceil(1750 * (1 - 0.15)) = 1488`, and then health-limited hit count as `ceil(3100 / 1488) = 3`. Treat this as the **conditional baseline**: every projectile hits, its damage is not defeated by penetration checks, no additional modifier applies, and the target is at full listed health. The target Silverhand itself mounts 40mm and 68mm; the 75mm is **incoming** ammunition.

## Verified saved-source chain

| Stage | Evidence | Status |
|---|---|---|
| Ammo source | Exact `Data/BPAmmoDynamicData` row key `BattleTankAmmo` | Present; source base damage matches human 1750 |
| Ammo damage type | Saved `DamageType` object reference pointing to a unique exported `DamageTypes/` generated-class/default candidate | Resolved, source-only |
| Class → mitigation row | Saved DamageType `Type` enum value identifies `Explosive`; exact `DTDamageProfiles` row | Exact saved value → exact row |
| Mitigation | `DTDamageProfiles.Explosive.Tier2Tank` | Matches human 0.15 |
| Defender source | Exact `Data/BPVehicleDynamicData` row key `MediumTankW`; `MaxHealth` | Source value agrees with human 3100 |
| Defender Blueprint | `Vehicles/MediumTank/BPMediumTankW` saves original `CodeName=MediumTankW` | One local saved CodeName candidate |
| Defender classification | Saved parent chain `BPMediumTankW` → `MediumTankBaseW` → `BPMediumTankBase`; ancestor explicitly saves `ArmourType=EArmourType::Tier2Tank` | Exact saved parent references, original ancestor `EnumProperty` tag verified |
| Gameplay engine | Unreal effective inherited defaults / native `/Script/War` damage and armor penetration / random mechanics | **Not established by saved exports** |
| Shot count | Existing Aedile Python calculation | **3 assuming the stated model**, not an independent in-game proof |

This cleanly illustrates why inspecting only the Silverhand leaf Blueprint is insufficient: `BPMediumTankW` itself does **not** save an `ArmourType` value. The category is explicitly saved in a referenced ancestor. The chain is serialized-source evidence; we still cannot equate that with verified native runtime-effective inheritance.

## Evidence and reproducibility

- Initial passing source audit: private [run #41360772806](https://github.com/Romboter/foxhole-lab/actions/runs/41360772806) — exact four relevant DataTables, damage-class candidates and selected MediumTank Blueprints; eight synthetic tests, no direct game mutations.
- Narrow parent-chain survey: private [run #41360892255](https://github.com/Romboter/foxhole-lab/actions/runs/41360892255) — identified the exact named parent chain and ancestor `EArmourType::Tier2Tank` declaration.
- Original type-tag-gated saved-ancestor audit: private [run #41361107624](https://github.com/Romboter/foxhole-lab/actions/runs/41361107624) — **passed** 13 synthetic tests, original saved ancestor `ArmourType: EnumProperty`, exact parent chain; classified `native_effective_inheritance: unverified`.
- Final pinned validation after testing the actual historical calculator, not merely a clone: see private `automation/93-75mm-silverhand-answerability` latest successful run (confirm final completion before updating counts).
- Code: `scripts/audit_75mm_silverhand_answerability.py`, `scripts/trace_silverhand_saved_armour_ancestry.py`, `test/test_audit_75mm_silverhand_answerability.py`, `test/test_trace_silverhand_saved_armour_ancestry.py`; branch `research/93-75mm-silverhand-answerability`.

All jobs check dedicated `foxrunner`, pinned Steam build and unchanged PAK file identity before completion. Files are extracted into permission-restricted `mktemp` scratch, used only for source comparisons, and scrubbed on exit. No raw game assets, numbers from private exports, PAK bytes, or private reports are published.

## Actionable remaining work

1. **Native damage/penetration path:** distinguish hits that penetrate from impacts that are deflected; determine whether 75mm `Explosive` damage vs `Tier2Tank` class has additional tank-armor, angle, subsystem, impact and attenuation rules. Need native-source/gameplay/fixture evidence, not more DataTable row comparisons.
2. **Exact player semantics:** distinguish **three damaging full-strength hits** from shots fired, hits that bounce, expected outcomes, and guarantees; do not expose a false unconditional count in the Discord response.
3. **Automated regression coverage:** make this a case in a versioned query-to-evidence matrix; reproduce the **actual** historical Python calculation and eventually the Node rewrite's tested equivalent, then expand to one structure and one bunker fixture.
4. **Repeatable asset-data regeneration:** derive attacker/defender/profile facts from verified game-source paths. Keep aliases/manual exceptions review-only, and require immutable build/source-hash provenance before modifying any generated bot catalog.

**Acceptance status:** The game-serialized source path for **base damage, class, mitigation and health is proven**. The standalone arithmetic has a verified legacy implementation. A claim of native game-runtime shot-count parity requires further damage/penetration testing. Do not silently update `data/`, `data_manual/`, or live Discord output from this research PR.
