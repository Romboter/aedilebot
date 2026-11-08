# Data layout redesign (draft)

Date: 2026-11-08
Status: draft, not implemented. Implement after the data-mapping work in `docs/data-parity-scope.md` is finished; the generators should emit this layout directly.

## Why

The current files keep the original sheet's shape. The rewrite loader consumes them unchanged, which was a deliberate constraint for the port and no longer holds.

- `Targets.json` is keyed by display string (`"00MS “Stinger” (MG bike)"`, curly quotes included). The Dev Name, the game's stable key, is only a field.
- Every value is a string: numbers, booleans (`"TRUE"`), blanks (`""`, `" "`). The bot parses at use.
- Column names are display text (`"Main Weapon (damage bonus)(max range, reach)(artillery range)"`). Vehicle weapon and reload cells are hand-formatted text, while the pipeline yields structured values.
- One file holds six `ObjectType`s with different fields, so `schema.ts` needs a discriminated union plus an index signature for sparse fields.
- Costs are seven fixed columns, which cannot hold facility, rocket or multi-material costs.

## Principles

1. Key by Dev Name (the game's key). Display name and aliases are fields.
2. One file per kind, one shape per file.
3. Typed values: JSON numbers and booleans, `null` for "not applicable", no empty-string sentinels.
4. Structured fields in the data; the bot builds display strings.
5. Generated files are pure pipeline output. Hand-maintained values live in `overlay/` and are merged at load time.
6. Sheet disagreements are reported in a generated `reports/` file, not stored in the data.

## Files

```
data/
  vehicles.json          Dev Name -> vehicle
  structures.json        Dev Name -> structure
  (multi-tier: no file; see below)
  emplacements.json      Dev Name -> emplacement (gun, with emplaced variant derived)
  tripods.json           Dev Name -> tripod
  aircraft_parts.json    Dev Name -> aircraft part
  weapons.json           Dev Name -> weapon
  materials.json         code -> display name
  damage.json            damage type -> mitigation type -> multiplier
  bunker_pieces.json     unchanged shape, typed numbers
  locations.csv          unchanged until generated
  overlay/
    armour_types.json    Dev Name -> armour type (native-class structures)
    notes.json           Dev Name -> free text
  reports/
    sheet_errors.json    generated: every place the export beat the sheet
```

`Damage.json`, `Bunker_piece.json` and `Locations.csv` keep their shape for now (typed numbers aside) and are revisited once their generators exist.

## Example rows

### vehicles.json

```json
"MotorcycleOffensiveC": {
  "name": "00MS “Stinger”",
  "aliases": ["MG Bike"],
  "armourType": "LightVehicle",
  "health": 300,
  "armourHealth": 0,
  "penetration": { "min": 1, "max": 1 },
  "disableLevel": 0.5,
  "disableChance": { "tracks": 0, "engine": 0, "mainGun": 0, "secondaryGun": 0 },
  "repairCost": 110,
  "slots": 1,
  "mainWeapon": {
    "weapon": "7.92mm",
    "count": 1,
    "range": 27, "reach": 40,
    "firingTime": null, "reload": null, "magazine": 30
  },
  "secondaryWeapon": null,
  "cost": [{ "code": "Cloth", "qty": 110 }]
}
```

`mainWeapon.weapon` is a key into `weapons.json`. Ranges are metres, times are seconds. `reload: null` means the export has no value; `0` means zero.

### structures.json

```json
"ATPillbox": {
  "name": "Anti-Tank Rifle Pillbox",
  "aliases": ["at pillbox"],
  "armourType": "Tier2Structure",
  "health": 800,
  "repairCost": 75,
  "decay": { "startHours": 48, "durationHours": 32 },
  "structuralIntegrity": 1,
  "storedItemCapacity": 0,
  "ramDamageFlags": 0,
  "harvestable": true,
  "vaultable": true,
  "damagedWhenDrivenOver": false,
  "cost": [{ "code": "Cloth", "qty": 75 }],
  "altCost": []
}
```

`cost` is `ResourceAmounts` (primary plus `OtherResources`). `altCost` is `AltResourceAmounts`, the facility (assembly station) production cost; the rocket parts and large emplacements have only that. Omit it when it equals `cost`. The bot reads neither today.

### Multi-tier structures (no separate file)

Superseded: the 7 rows are ordinary `structures.json` entries (health, repair cost, capacity and cost all match the sheet, generated). Multi-tier is a bot classification: `overlay/multitier.json` lists the Dev Names, and the bot evaluates one health value against the `Tier1/2/3GarrisonHouse` damage profiles (`multitier.ts`), so there is no per-tier health. The `tiers` array below is not backed by the data; the old example is kept for reference only.

#### Old example

```json
"GarrisonStation": {
  "name": "Safe House",
  "aliases": ["sh", "safehouse"],
  "tiers": [
    { "health": 2000, "repairCost": 250, "cost": [{ "code": "Cloth", "qty": 250 }] }
  ],
  "storedItemCapacity": 15
}
```

Moving per-tier data into a `tiers` array replaces the current parallel-string approach and is what the bunker and multi-tier calculation already iterates over.

### emplacements.json

```json
"EmplacedLightArtilleryW": {
  "name": "Lariat",
  "aliases": [],
  "armourType": "Tier1Structure",
  "health": 750,
  "emplaced": { "healthMultiplier": 4, "trackingMultiplier": 2 },
  "repairCost": 100,
  "weapon": { "weapon": "…", "range": 0, "reach": 0, "firingTime": 0, "reload": 0, "magazine": 0 }
}
```

The sheet's 24 rows (12 guns x unemplaced/emplaced) become 12 rows. Emplaced health is `health / EmplacedIncomingDamageModifier`, stored as `healthMultiplier` (1 for Zeal and Bolas). The bot derives both variants; its alias index still registers "<name> (Emplaced)".

### tripods.json, aircraft_parts.json

Same fields as vehicles where they apply (`name`, `armourType`, `health`, `repairCost`, `disableLevel` for aircraft parts, `weapon` for tripods), and nothing else. No empty-string placeholders for fields a kind never has.

### weapons.json

```json
"BattleTankAmmo": {
  "name": "75mm",
  "aliases": ["bt", "collie bt", "warden bt"],
  "damage": 1750,
  "damageType": "Explosive",
  "shelterBonus": false
}
```

`shelterBonus` is a boolean from the game's per-damage-type flag. The bot reads it instead of inferring from the type name. Weapons that have no ammo row (9 hand-entered garrison and AI shells) carry `"source": "overlay"`.

### materials.json

```json
{
  "Cloth": "Basic Materials",
  "Concrete": "Concrete",
  "Excavation": "Shovel dig",
  "FacilityMaterials9": "Rare Alloys",
  "FacilityMaterials11": "Thermal Shielding"
}
```

Display names come from each material's pickup blueprint (`DisplayName`). Codes for the legacy sheet columns map as: `Cloth` to Bmat, `Wood` to Rmat, `Excavation` to shovel digs, `Concrete`, `MetalBeamMaterials`, `SandbagMaterials`, `BarbedWireMaterials` to their own columns.

### overlay/armour_types.json

```json
{ "Hospital": "Tier2Structure", "Keep": "Tier3Structure" }
```

Hand-maintained. Seeded from the current sheet for the 39 native-class structures (plus Garage, OilWell and WoodBridge, which have no blueprint). The loader applies it only where the generated armour type is `null`.

### reports/sheet_errors.json

Generated, not read by the bot. One entry per disagreement: file, Dev Name, field, sheet value, export value. The rocket costs, the Zeal and Bolas health, the penetration differences and the 8 Dev Name fixes go here.

## Loader and bot impact

- `loader.ts`, `schema.ts` and `aliasIndex.ts` are rewritten against typed rows. The discriminated union is replaced by one interface per file.
- The calculator and statsheet stop parsing strings. The statsheet builds the reload and weapon text from the structured fields.
- Parity check: keep a small adapter that flattens the new files back into the old sheet shape so the old calculator tests and the old-vs-new diff still run. Delete it when the old files are removed.
- The "Repair Cost" that the statsheet shows for structures (really decay start hours) is a preserved bug. In the new layout, the statsheet maps it explicitly to `decay.startHours` and the preserved bug is stated in one place.

## Open questions

- Should the data files live under `bot-ts/` or stay at `data/`? The extractor and generators write to `data/`.
- `altCost` is the facility production cost (confirmed for vehicles against the wiki's Flood Mk. I). Concrete Mixer's 5 Construction Materials is unverified, and Mass Production Factory costs are not in the structure table.
- Alias source: aliases are hand-maintained and must survive regeneration. Keep them in `overlay/aliases.json` keyed by Dev Name rather than inside the generated files?
- Display name source: the sheet's `Name` is hand-written. If the export has a usable `DisplayName`, generated names may differ from what players type today; aliases cover this.
