# Blueprint ObjectPath reference-surface survey

The research-only scanner `scripts/audit_blueprint_reference_surface.py` checks every exported package against a build-pinned graph and inventories additional serialized `ObjectPath` field families. It verifies exact package hashes and reconciles all preexisting indexed edges. New paths are source candidates, not proven weapon connections.

Run the scanner with `--source-root`, `--index`, and `--output` on the same private export. Keep complete reports private. Do not infer runtime CDO defaults, gameplay damage, or ammunition from the presence of an `ObjectPath` alone. Only promote fields to graph edges after independently confirming owning class, original type and intended relationship.

The private validation workflow is in `Romboter/foxhole-lab` on branch `automation/reference-surface-inventory`. It runs on the pinned game build with a restricted runner and never publishes raw game exports. Deployment, automatic game updates, merges, and production data writes remain disabled.
