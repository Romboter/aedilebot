# Type-gated case-only SCS component source identities

This research-only, build-pinned checker uses `scripts/resolve_scs_typed_case_identity.py`.
It consumes the existing source-only SCS matcher output, the checked Blueprint
graph index, and actual tagged property types from the private CUE4Parse
`inspect-scs-tags` command.

A child component-key name that differs only in ASCII casing from the unique
GUID-matching parent SCS node can be accepted as a **serialized source
identity** only after all five original tag checks agree:

- child `Records[i].ComponentKey.OwnerClass` = `ObjectProperty`
- child `Records[i].ComponentKey.SCSVariableName` = `NameProperty`
- child `Records[i].ComponentKey.AssociatedGuid` = `StructProperty`
- parent `SCS_Node.InternalVariableName` = `NameProperty`
- parent `SCS_Node.VariableGuid` = `StructProperty`

The report additionally requires the exact child record index, exact parent
node name and package, a unique GUID candidate, a case-only name match,
matching game build and graph relation digest, source package SHA-256 matches,
and a pinned inspector commit. Duplicate/absent or wrong-type evidence fails
closed. General fuzzy matching and global case-folding are forbidden.

The two pinned-build `BPScoutTankOffensiveW` exceptions are:
`exhaustR` vs `ExhaustR`, and `exhaustL` vs `ExhaustL`. They may be
upgraded from GUID-only diagnostics to typed `FName` source identities
**only if** the independent private run passes every gate. No effective
UE4.24 runtime CDO reconstruction, inferred firing mount, ammunition
selection, numeric damage or unattended publication is authorized.

To reproduce, use the private runner with the same pinned PAK, source
commit and extractor commit. Retain the full tagged output and raw exports
in restricted scratch; show only derived validated counts in job logs.
