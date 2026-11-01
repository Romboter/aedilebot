# Serialized parent SCS component-key matching

Read-only research on pinned Foxhole build `26058282`, tracking [Issue #68](https://github.com/Romboter/aedilebot/issues/68).

Earlier private extraction showed that child `InheritableComponentHandler.Records[i].ComponentKey` contains `OwnerClass`, `SCSVariableName`, and `AssociatedGuid`. Parent class `SCS_Node.Properties` uses `InternalVariableName` and `VariableGuid` (not `VariableName`).

`scripts/resolve_scs_component_keys.py` validates the full graph's build fingerprint and every inspected source package SHA-256. It checks that the child source record matches its indexed `OwnerClass` and `ComponentTemplate` object paths. It then looks only in the explicit owner class's saved SCS nodes and requires exact equality on **both** variable name and GUID. A unique candidate produces a parent source node identity, owning package SHA, and source key hash. Name-only and GUID-only matches do not qualify.

The report distinguishes `unique_serialized_key_match`, `ambiguous_exact_key`, `name_guid_disagreement`, `no_parent_scs_match`, invalid keys and missing exports. Negative tests cover same-name/different-GUID nodes, conflicts, duplicates, missing fields, and changed source hashes.

**This remains a serialized-source identity matcher, not a UE4.24 runtime component resolver.** Original Unreal property types have not been independently verified by the nested type inspector. No merged CDO, selected ammunition, gameplay multiplier, or damage value is inferred. Continue to require the private restricted runner, raw export privacy, human review and no production activation.
