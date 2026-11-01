# SCS component-template export reference inventory

**Scope:** source-only exploration of pinned Foxhole build `26058282`. This does not reconstruct effective UE4.24 runtime components, weapon damage or ammunition.

`scripts/audit_scs_template_exports.py` consumes the hash-checked Blueprint graph, the 664 exact SCS key matches from PR #70, and the two independently typed FName case-only identities from PR #72. It then opens the checked parent and child packages and inspects the *serialized* `SCS_Node.Properties.ComponentTemplate` and `InheritableComponentHandler.Records[i].ComponentTemplate`.

The tool checks the original child handler record against its indexed ObjectPath, preserves both object references and records whether `ObjectName` exactly equals an exported object's `Name` in that source package. It does **not** assume numeric `.N` ObjectPath suffixes correspond to export indexes. Missing/ambiguous names and unusual shapes remain review findings. Cross-package child pointers, invalid indexed identities and changed source SHA-256 fail closed.

## Private reproducible run

Use the restricted self-hosted workflow `foxhole-lab/.github/workflows/scs-key-inspection.yml` pinned to exact extractor and aedilebot commit IDs, source build and PAK. It runs the prior SCS type and key validations first. Only derived status counts and a bounded sample are written to logs. Raw exports and complete reports remain in temporary private storage.

## Next independent checks

The source object path grammar must be established from CUE4Parse's actual resolved-object serializer, not inferred from visible numbers. Only after confirming the precise export identity, object type and same-record parent/child template pair should the resolver expose a source edge to the underlying component export. Keep runtime component default inheritance, `MultiAmmo` behavior and damage multipliers unresolved until independently verified. No automatic merges, asset publishing, game updates, production writes or bot activation.
