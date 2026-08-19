// Port of parse.py's get_all_names/get_husk_names/get_vehicle_names/
// check_if_location_name: builds alias(normalized) -> canonical-name lookup
// maps from the "Name" + ";"-split "Additional Names" fields. Straight
// behavior-preserving port, including the exact (asymmetric) collision rule
// below — not a redesign.
import { normalize } from "../domain/normalize.js";
import { moveStringToRear } from "../domain/textParsing/moveStringToRear.js";
import type { Entity, TargetEntry } from "./schema.js";

/** Every current entity type carries this field (optionally); the Python
 * original supports an arbitrary field_name but never actually calls with
 * anything else, so it's fixed here rather than kept generic over a field
 * that's always the same string in practice. */
function collectAliasCandidates(key: string, value: Entity): string[] {
  const names: string[] = [value.Name];
  const extra = value["Additional Names"];
  if (extra !== undefined) {
    names.push(...extra.split(";"));
  }
  if (!names.includes(key)) {
    names.push(key);
  }
  return names;
}

/** alias -> canonical key, built from Name + Additional Names + the dict key
 * itself. Collision rule (preserved exactly): a Weapons entry never
 * overwrites an existing alias; any non-Weapons entry always overwrites,
 * even another target's alias — this depends on iteration order, so callers
 * must pass `dictionary` in the same merge order Python would have produced
 * (see data/loader.ts's `all` construction via object spread). */
export function getAllNames(dictionary: Record<string, Entity>): Map<string, string> {
  const namesDictionary = new Map<string, string>();
  for (const [key, value] of Object.entries(dictionary)) {
    for (const rawName of collectAliasCandidates(key, value)) {
      const name = normalize(moveStringToRear(rawName));
      if (name === "") {
        continue;
      }
      if (namesDictionary.has(name) && value.ObjectType === "Weapons") {
        continue;
      }
      namesDictionary.set(name, key);
    }
  }
  return namesDictionary;
}

/** Husk-name derivation is inconsistent with the other alias builders by
 * design (see parse.py's own comment) — kept as-is, not cleaned up here. */
export function getHuskNames(namesDictionary: Map<string, string>): Map<string, string> {
  const huskNamesDictionary = new Map<string, string>();
  for (const [key, value] of namesDictionary) {
    if (key.toLowerCase().includes("husk")) {
      huskNamesDictionary.set(key, value);
      huskNamesDictionary.set(key.replaceAll("husk", ""), value);
    }
  }
  return huskNamesDictionary;
}

/** Vehicles/Aircraft_Parts only, first-write-wins (no overwrite) — distinct
 * collision rule from getAllNames, and doesn't add the dict key itself as an
 * alias. Both differences are preserved as-is from parse.get_vehicle_names. */
export function getVehicleNames(targets: Record<string, TargetEntry>): Map<string, string> {
  const namesDictionary = new Map<string, string>();
  for (const [key, value] of Object.entries(targets)) {
    if (value.ObjectType !== "Vehicles" && value.ObjectType !== "Aircraft_Parts") {
      continue;
    }
    const candidates: string[] = [value.Name];
    const extra = value["Additional Names"];
    if (extra !== undefined) {
      candidates.push(...extra.split(";"));
    }
    for (const rawName of candidates) {
      const name = normalize(moveStringToRear(rawName));
      if (name === "" || namesDictionary.has(name)) {
        continue;
      }
      namesDictionary.set(name, key);
    }
  }
  return namesDictionary;
}

/** O(1) membership check via a precomputed normalized set — parse.py's
 * check_if_location_name re-scans + re-normalizes every location name on
 * every call (an O(n) linear scan), which this replaces with an equivalent,
 * behavior-identical Set lookup built once. */
export function buildLocationNameIndex(locations: Map<string, string>): Set<string> {
  const index = new Set<string>();
  for (const locationName of locations.keys()) {
    index.add(normalize(locationName));
  }
  return index;
}

export function isLocationName(name: string, locationNameIndex: Set<string>): boolean {
  return locationNameIndex.has(normalize(name));
}
