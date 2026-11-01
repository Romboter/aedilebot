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
