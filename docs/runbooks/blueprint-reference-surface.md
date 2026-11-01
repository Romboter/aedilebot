# Blueprint ObjectPath reference-surface survey

The research-only scanner `scripts/audit_blueprint_reference_surface.py` checks every exported package against a build-pinned graph and inventories additional serialized `ObjectPath` field families. It verifies exact package hashes and reconciles all preexisting indexed edges. New paths are source candidates, not proven weapon connections.

Run the scanner with `--source-root`, `--index`, and `--output` on the same private export. Keep complete reports private. Do not infer runtime CDO defaults, gameplay damage, or ammunition from the presence of an `ObjectPath` alone. Only promote fields to graph edges after independently confirming owning class, original type and intended relationship.

The private validation workflow is in `Romboter/foxhole-lab` on branch `automation/reference-surface-inventory`. It runs on the pinned game build with a restricted runner and never publishes raw game exports. Deployment, automatic game updates, merges, and production data writes remain disabled.

## InheritableComponentHandler record references

The initial full-build inventory identified two frequent serialized Blueprint
reference fields on `InheritableComponentHandler` records:

- `Records[i].ComponentKey.OwnerClass` identifies the class recorded as the
  component key's owner, not necessarily the effective runtime parent.
- `Records[i].ComponentTemplate` identifies a component template record.
  The target may be in the same package; it is not necessarily a new weapon.

The exact field locations are now included as source references by
`find_blueprint_dependencies.direct_edges` and indexed normally in
`index_blueprint_graph`. This preserves the record index and actual
`ObjectPath`, while leaving gameplay interpretation unresolved. Malformed
record arrays and keys fail closed. Explicit native-only references are
not rewritten into guessed Blueprint links.

Before interpreting these as effective component overrides, independently
verify the target UE4 class-template construction and parent/child behavior.
In particular, these serialized edges do not prove effective `MultiAmmo`
values or associate a firing mount with a damage multiplier.

## Paired inherited-component records

`scripts/pair_inheritable_component_records.py` uses checked graph edges
for `Records[i].ComponentKey.OwnerClass` and
`Records[i].ComponentTemplate`. It pairs fields only when they occur
on the same source package, export record and array index, retaining
both `ObjectPath` strings and the defining source SHA-256. It never
constructs effective runtime values from these pairs.

On pinned Foxhole build `26058282`, private runner
[validation #41325767200](https://github.com/Romboter/foxhole-lab/actions/runs/41325767200)
found exactly **666 paired records**, all with cross-package owner-class
Blueprint references and same-package component-template references.
All 666 pairs have both fields and all targets were among the previously
indexed exports. This is a source-only structural observation, not
proof that every pair describes a live or spawnable component.

Next: inspect `ComponentKey.SCSVariableName` and `AssociatedGuid`
and match them to the actual parent `SCS_Node`. Without that specific
component key and UE4.24 template construction evidence, a class-level
owner/template association cannot establish effective mount properties,
ammunition, firing mode, or damage. See Issue #68.
