# Serialized parent SCS component-key matching

Read-only research on pinned Foxhole build `26058282`, tracking [Issue #68](https://github.com/Romboter/aedilebot/issues/68).

Earlier private extraction showed that child `InheritableComponentHandler.Records[i].ComponentKey` contains `OwnerClass`, `SCSVariableName`, and `AssociatedGuid`. Parent class `SCS_Node.Properties` uses `InternalVariableName` and `VariableGuid` (not `VariableName`).

`scripts/resolve_scs_component_keys.py` validates the full graph's build fingerprint and every inspected source package SHA-256. It checks that the child source record matches its indexed `OwnerClass` and `ComponentTemplate` object paths. It then looks only in the explicit owner class's saved SCS nodes and requires exact equality on **both** variable name and GUID. A unique candidate produces a parent source node identity, owning package SHA, and source key hash. Name-only and GUID-only matches do not qualify.

The report distinguishes `unique_serialized_key_match`, `ambiguous_exact_key`, `name_guid_disagreement`, `no_parent_scs_match`, invalid keys and missing exports. Negative tests cover same-name/different-GUID nodes, conflicts, duplicates, missing fields, and changed source hashes.

**This remains a serialized-source identity matcher, not a UE4.24 runtime component resolver.** Original Unreal property types have not been independently verified by the nested type inspector. No merged CDO, selected ammunition, gameplay multiplier, or damage value is inferred. Continue to require the private restricted runner, raw export privacy, human review and no production activation.

## Pinned Foxhole findings

The restricted runner [#41327072222](https://github.com/Romboter/foxhole-lab/actions/runs/41327072222) passed and showed 664 unique exact name-plus-GUID matches from 666 component handler records. The remaining two records, indices 1 and 2 under `Vehicles/ScoutTank/BPScoutTankOffensiveW`, point to owner class `Vehicles/ScoutTank/ScoutTankWBase`. Each GUID matches one saved parent SCS node, but neither saved child variable name matches that parent node's `InternalVariableName`.

The resolver leaves these cases `name_guid_disagreement`, reports a separately labeled `unverified_guid_only_candidate` for investigation, and explicitly sets `accepted_as_exact_match=false`. A GUID-only candidate must never be silently published as a runtime component relationship. The original Unreal property tag types and UE4.24 runtime behavior still require independent validation.

## Engine API context (not pinned-version tag proof)

Epic's Unreal Engine API documents `FComponentKey.SCSVariableName` as
`FName`, `FComponentKey.AssociatedGuid` as `FGuid`, and
`USCS_Node.InternalVariableName` / `USCS_Node.VariableGuid` as
`FName` / `FGuid` respectively:
- https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/FComponentKey
- https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/USCS_Node

These references describe the current public API and independently support
the proposed identity grammar, but do **not** verify the original tagged
property types or effective component behavior in the pinned Foxhole
UE4.24 build. Do not conflate a GUID-only candidate with a verified runtime
override; use read-only original-tag inspection if further promotion is needed.
