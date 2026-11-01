# Inherited component-key source inspection

Pinned Foxhole build `26058282`, read-only private workflow: https://github.com/Romboter/foxhole-lab/actions/runs/41326710600

`scripts/audit_scs_component_keys.py` reads each hash-checked handler source package and its exact referenced owner class. It inventories serialized fields without deriving runtime CDO data.

## Findings

Across 666 paired child handler records, every `ComponentKey` has serialized `OwnerClass` (object reference), `SCSVariableName` (string), and `AssociatedGuid` (string). The 7,799 inspected parent `SCS_Node` records use `InternalVariableName` (string) and `VariableGuid` (string). They do not export a property called `VariableName`. The prior exploratory comparison against `VariableName` therefore produced zero candidates; it is not proof that any parent component is missing.

The next exact candidate join is: child `OwnerClass` target package, `SCSVariableName` ↔ owner node `InternalVariableName`, and `AssociatedGuid` ↔ owner node `VariableGuid`. Require uniqueness and hash provenance; do not guess when names or GUIDs differ. Serialized JSON shapes alone do not establish original UE property tag types or effective runtime default construction.

No raw game exports, auto-merge, downloads, scheduling, or production writes are permitted. See Issue #68 and the next staged research PR.
