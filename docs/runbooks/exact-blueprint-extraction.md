# Exact Blueprint extraction and dependency closure (read-only)

**Status:** Research-only extractor interface. Does not monitor Steam, install
game updates, write bot data, open PRs, or activate production snapshots.

## Motivation

CUE4Parse previously offered a `dump <substring>` command. That is useful
for manual exploration, but it is not an auditable extraction protocol:
substring matches can include unrelated assets and miss inherited parent
Blueprints or referenced projectile components.

The new `dump-list` takes a **bounded list of exact Blueprint packages**
and refuses to silently substitute similarly named assets.

## Manifest contract

One exact package *without extension* per line:

~~~text
War/Content/Blueprints/ItemPickups/BPRifleHeavyWPickup
War/Content/Blueprints/Data/BPAmmoDynamicData
War/Content/Blueprints/Data/BPWeaponDynamicData
~~~

The parser accepts only paths under `War/Content/Blueprints/` consisting
of directory and base-name characters `[A-Za-z0-9_-]`. It rejects traversal,
extensions, whitespace within paths, non-Blueprint assets, missing/empty
files, manifests above 64 KiB and requests of more than **256 unique**
packages. It deduplicates and sorts requests deterministically.
Empty lines and comment lines starting with `#` are permitted.

Two modes:

~~~bash
# Validate the requested names without mounting a PAK:
dotnet run --project tools/cue4parse-extractor/Extractor.csproj -- \
  unused unused check-list /PRIVATE/pending-blueprints.txt

# Extract exactly the named packages from a pinned, authorized local PAK:
dotnet run --project tools/cue4parse-extractor/Extractor.csproj -- \
  /PRIVATE/vanilla-pak-dir /PRIVATE/transient-output \
  dump-list /PRIVATE/pending-blueprints.txt
~~~

The PAK is mounted read-only by the existing extractor. `dump-list`
preflights that **every exact package** exists before writing any JSON;
a parsing failure aborts the run. Output paths correspond to exact game
package paths beneath the specified private output directory. A failed run
may leave partial temporary JSON in that directory, so run only in a
restricted, uniquely named scratch directory and discard it after failure.

## Close the *explicit* graph

The separate research branch
`research/55-infantry-firing-mode-graph` contains
`scripts/find_blueprint_dependencies.py`, which inspects exports for
exact, typed references:

- `BlueprintGeneratedClass.SuperStruct.ObjectPath` (inheritance)
- `VehicleSeatComponent.MountComponent.ObjectPath` (gunner components)
- `Default__*.ItemComponentClass.ObjectPath` (inventory item components)
- `Default__*.ProjectileClass/ObjectPath` and
  `Default__*.ProjectileClasses[]` (projectiles)
- `Default__*.GrenadeClasses[]` and
  `Default__*.ExplosionTemplate` (grenades and explosion assets)

The dependency scanner emits `missing_packages[].pak_path`. Write those
to a new manifest and run `dump-list`; repeat until the scan finds no
missing supported references. Bound each pass, total passes and requested
package count. Any missing exact PAK package, unsafe path, dependency
cycle, export error, or cap exhaustion **fails the audit**, never substituting
another class.

The private workflow on
`Romboter/foxhole-lab` branch
`automation/exact-blueprint-closure-validation` tests this sequence on
build `26058282` beginning with the rifle pickup and the two numeric
DataTables. It then validates both primary ammunition and the three
grenade options without guessing per-mode damage multipliers.

## Limits and future work

This is closure for the **supported, explicit fields only**, not proof
that every gameplay dependency is exported. Unreal bytecode, native
`/Script/War` class behavior, dynamic spawns, implicit data-table lookups,
display-name joins, damage rules and any unknown Blueprint property type
remain out of scope. New source relationship types require reviewed
scanner support and synthetic/real-fixture tests, not broad recursive
crawling of arbitrary `ObjectPath` values.

Before enabling an update scheduler: prove off-host audit-history backup
and restore, deterministic outputs on a full game build, complete coverage
reports, human-reviewed PR promotion, and atomic bot snapshot rollback.

No raw game JSON is committed to the public repository. Extraction happens
only on the private runner with transient output.
