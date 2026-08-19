import { describe, expect, it } from "vitest";
import {
  buildLocationNameIndex,
  getAllNames,
  getHuskNames,
  getVehicleNames,
  isLocationName,
} from "../../src/data/aliasIndex.js";
import { defaultDataDir, loadDataSnapshot } from "../../src/data/loader.js";
import { loadFixtures } from "../fixtures.js";

interface AliasIndexFixtures {
  targets_dictionary: Record<string, string>;
  weapons_dictionary: Record<string, string>;
  all_dictionary: Record<string, string>;
  husk_dictionary: Record<string, string>;
  vehicle_dictionary: Record<string, string>;
}

function toObject(map: Map<string, string>): Record<string, string> {
  return Object.fromEntries(map);
}

describe("data/aliasIndex full-dictionary parity with Python parse.py", () => {
  const snapshot = loadDataSnapshot(defaultDataDir());
  const fixtures = loadFixtures<AliasIndexFixtures>("alias-index-fixtures.json");

  const targetsDictionary = getAllNames(snapshot.targets);
  const weaponsDictionary = getAllNames(snapshot.weapons);
  const allDictionary = getAllNames(snapshot.all);
  const huskDictionary = getHuskNames(targetsDictionary);
  const vehicleDictionary = getVehicleNames(snapshot.targets);

  it("targets_dictionary matches exactly, key-for-key", () => {
    expect(toObject(targetsDictionary)).toEqual(fixtures.targets_dictionary);
  });

  it("weapons_dictionary matches exactly, key-for-key", () => {
    expect(toObject(weaponsDictionary)).toEqual(fixtures.weapons_dictionary);
  });

  it("all_dictionary matches exactly, key-for-key (collision resolution + iteration order)", () => {
    expect(toObject(allDictionary)).toEqual(fixtures.all_dictionary);
  });

  it("husk_dictionary matches exactly, key-for-key", () => {
    expect(toObject(huskDictionary)).toEqual(fixtures.husk_dictionary);
  });

  it("vehicle_dictionary matches exactly, key-for-key", () => {
    expect(toObject(vehicleDictionary)).toEqual(fixtures.vehicle_dictionary);
  });

  it("isLocationName matches Python's check_if_location_name", () => {
    const index = buildLocationNameIndex(snapshot.locations);
    expect(isLocationName("finis", index)).toBe(true);
    expect(isLocationName("not a place", index)).toBe(false);
  });
});
