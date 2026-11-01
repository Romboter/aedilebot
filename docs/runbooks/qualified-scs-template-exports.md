# Qualified SCS component-template export references

**Scope:** pinned game-build **source evidence only**. No runtime component reconstruction, gun, ammunition or damage calculation.

Previous read-only [PR #73](https://github.com/Romboter/aedilebot/pull/73) found that every template ObjectName uses a class-qualified Unreal string such as `StaticMeshComponent'Grenade_C:GrenadeMesh_GEN_VARIABLE'`. A literal comparison between the whole `ObjectName` and export `Name` therefore found no matches, without demonstrating any missing component.

`scripts/resolve_qualified_scs_template_exports.py` parses this form only when it matches a strict, anchored syntax, then checks the **exact source package** for one `BlueprintGeneratedClass` with that owning class name and one export with both the exact component `Name` and component `Type`. It retains the original ObjectPath and both parent/child source package hashes and reports missing, unsupported and ambiguous identities separately. The object path's numeric `.N` suffix is **not interpreted as an export index**.

The input is the fail-closed component-template reference audit from PR #73 and its graph fingerprint. Every source package is checked against the indexed SHA-256. The source identity follows the parent SCS-node proof from PRs #70/#72; runtime-effective component values remain `not_established`.

The private runner validates the pinned game build and prints only derived counts and a bounded source example set. The complete game export corpus and reports remain in temporary restricted scratch.

**Future work:** independently verify export ownership via the `Outer` reference and determine the precise CUE4Parse package export index semantics before considering deeper export resolution. An explicit template object does not prove which properties survive UE4.24 CDO inheritance. Do not activate or publish calculated damage, perform game updates, or merge without human review.
