// THROWAWAY SPIKE: read relic/town base positions straight from hex .umap files via CUE4Parse.
// usage: Extractor <pakDir> <outJson> <HexName> [HexName...]   (HexName like AcrithiaHex; "all" = every Master/*Hex)
using System.Diagnostics;
using System.Text.Json;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Objects.Core.Math;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Assets.Exports.Engine;
using CUE4Parse.UE4.Assets.Objects;
using CUE4Parse.UE4.Versions;

var wanted = new Dictionary<string, string>
{
    ["BPDestroyedRelicBase1_C"] = "Small Relic",
    ["BPDestroyedRelicBase2_C"] = "Medium Relic",
    ["BPDestroyedRelicBase3_C"] = "Large Relic",
    ["BPTownBase1_C"] = "Post Office",
    ["BPTownBase2_C"] = "School",
    ["BPTownBase3_C"] = "Town Center",
};

// Exact package extraction uses fully named Blueprint paths, never substring
// filters. Check-list can be tested without mounting or reading a game PAK.
if (args.Length >= 3 && (args[2] == "check-list" || args[2] == "dump-list" || args[2] == "inspect-types" || args[2] == "inspect-scs-tags") && args.Length != 4)
    throw new ArgumentException("Usage: Extractor <pakDir> <outputDir> check-list|dump-list|inspect-types|inspect-scs-tags <manifestFile>");

IReadOnlyList<string>? exactPackages = null;
if (args.Length == 4 && (args[2] == "check-list" || args[2] == "dump-list" || args[2] == "inspect-types" || args[2] == "inspect-scs-tags"))
{
    exactPackages = ExactBlueprintPackages.ReadManifest(args[3]);
    if (args[2] == "check-list")
    {
        foreach (var package in exactPackages)
            Console.WriteLine(package);
        Console.WriteLine($"validated: {exactPackages.Count} exact Blueprint packages");
        return;
    }
}

var sw = Stopwatch.StartNew();
var provider = new DefaultFileProvider(args[0], SearchOption.TopDirectoryOnly,
    new VersionContainer(EGame.GAME_UE4_24), StringComparer.OrdinalIgnoreCase);
provider.Initialize();
provider.SubmitKey(new FGuid(), new FAesKey("0x" + new string('0', 64)));
provider.PostMount();
Console.WriteLine($"provider ready: {provider.Files.Count} files, {sw.Elapsed.TotalSeconds:F2}s");

if (exactPackages != null)
{
    // Preflight *all* requested names before writing any exports. A package
    // not present in the PAK is an error, not a reason to guess a similar key.
    var absent = exactPackages.Where(k => !provider.Files.ContainsKey(k)).ToArray();
    if (absent.Length > 0)
        throw new InvalidOperationException("Missing exact Blueprint packages: " + string.Join(", ", absent));

    var inspected = 0;
    var typeFields = new HashSet<string>(StringComparer.Ordinal)
    {
        "CodeName", "UpgradeStructureCodeName", "AmmoName", "MountCodeName", "CompatibleAmmoCodeName", "ExplosiveCodeName", "DamageType", "ArmourType", "Type"
    };
    foreach (var key in exactPackages)
    {
        if (!provider.TryLoadPackage(key, out var pkg))
            throw new InvalidOperationException("Could not parse exact package: " + key);
        if (args[2] == "inspect-scs-tags")
        {
            // Report *original tagged* UE property types, not JSON value shapes.
            // This is strictly read-only and never reconstructs CDO defaults.
            foreach (var obj in pkg.GetExports())
            {
                if (obj.ExportType == "SCS_Node")
                {
                    foreach (var prop in obj.Properties.Where(p =>
                         p.Name.Text is "InternalVariableName" or "VariableGuid"))
                    {
                        Console.WriteLine($"SCSNODETYPE\t{key}\t{obj.Name}\t{prop.Name.Text}\t{prop.PropertyType.Text}");
                        inspected++;
                    }
                }
                if (obj.ExportType != "InheritableComponentHandler")
                    continue;
                foreach (var property in obj.Properties.Where(p => p.Name.Text == "Records"))
                {
                    Console.WriteLine($"SCSARRAYTYPE\t{key}\t{obj.Name}\tRecords\t{property.PropertyType.Text}");
                    if (property.Tag?.GenericValue is not UScriptArray entries ||
                        entries.InnerType != "StructProperty")
                    {
                        Console.WriteLine($"UNRESOLVED\t{key}\t{obj.Name}\tRecords\tarray_struct_not_inspectable");
                        continue;
                    }
                    for (var i = 0; i < entries.Properties.Count; i++)
                    {
                        if (entries.Properties[i].GenericValue is not FScriptStruct recordStruct ||
                            recordStruct.StructType is not FStructFallback recordFields)
                        {
                            Console.WriteLine($"UNRESOLVED\t{key}\t{obj.Name}\tRecords[{i}]\tstruct_not_inspectable");
                            continue;
                        }
                        var keys = recordFields.Properties
                            .Where(p => p.Name.Text == "ComponentKey").ToArray();
                        if (keys.Length != 1 ||
                            keys[0].Tag?.GenericValue is not FScriptStruct componentKey ||
                            componentKey.StructType is not FStructFallback keyFields)
                        {
                            Console.WriteLine($"UNRESOLVED\t{key}\t{obj.Name}\tRecords[{i}].ComponentKey\tkey_struct_not_inspectable");
                            continue;
                        }
                        foreach (var field in keyFields.Properties.Where(p =>
                             p.Name.Text is "OwnerClass" or "SCSVariableName" or "AssociatedGuid"))
                        {
                            Console.WriteLine($"SCSKEYTYPE\t{key}\t{obj.Name}\tRecords[{i}].ComponentKey.{field.Name.Text}\t{field.PropertyType.Text}");
                            inspected++;
                        }
                    }
                }
            }
            continue;
        }
        if (args[2] == "inspect-types")
        {
            // Report original tagged UE property types, never raw property
            // values or a flattened/inferred game-data relationship.
            foreach (var obj in pkg.GetExports())
            {
                // UDataTable's RowMap key type is FName in the underlying UE
                // export, not merely a JSON dictionary string key.
                if (obj is UDataTable)
                {
                    var keyType = typeof(UDataTable).GetProperty(nameof(UDataTable.RowMap))!
                        .PropertyType.GetGenericArguments()[0].Name;
                    Console.WriteLine($"TABLE\t{key}\t{obj.Name}\t{keyType}");
                }
                foreach (var prop in obj.Properties)
                {
                    if (typeFields.Contains(prop.Name.Text))
                    {
                        Console.WriteLine($"TYPE\t{key}\t{obj.Name}\t{prop.Name.Text}\t{prop.PropertyType.Text}");
                        inspected++;
                    }
                    // Never infer a nested field's type from JSON or from the
                    // enclosing struct. Only report it when the parsed UE
                    // structure explicitly contains a typed array of names.
                    if (prop.Name.Text is not ("MultiAmmo" or "GrenadeMultiAmmo"))
                        continue;
                    if (prop.Tag?.GenericValue is not FScriptStruct structValue ||
                        structValue.StructType is not FStructFallback fields)
                    {
                        Console.WriteLine($"UNRESOLVED\t{key}\t{obj.Name}\t{prop.Name.Text}.CompatibleAmmoNames\tstruct_not_inspectable");
                        continue;
                    }
                    // Expose only original nested property tag types, not
                    // values or assumptions about inherited CDO defaults.
                    foreach (var fieldTag in fields.Properties)
                    {
                        Console.WriteLine($"STRUCTFIELD\t{key}\t{obj.Name}\t{prop.Name.Text}.{fieldTag.Name.Text}\t{fieldTag.PropertyType.Text}");
                        if (fieldTag.Tag?.GenericValue is UScriptArray nestedArray)
                            Console.WriteLine($"ARRAYINNER\t{key}\t{obj.Name}\t{prop.Name.Text}.{fieldTag.Name.Text}\t{nestedArray.InnerType}");
                    }
                    var nested = fields.Properties
                        .Where(p => p.Name.Text == "CompatibleAmmoNames").ToArray();
                    if (nested.Length != 1 || nested[0].Tag?.GenericValue is not UScriptArray array)
                    {
                        Console.WriteLine($"UNRESOLVED\t{key}\t{obj.Name}\t{prop.Name.Text}.CompatibleAmmoNames\tnested_array_not_inspectable");
                        continue;
                    }
                    if (array.InnerType != "NameProperty")
                    {
                        Console.WriteLine($"UNRESOLVED\t{key}\t{obj.Name}\t{prop.Name.Text}.CompatibleAmmoNames\tunexpected_inner_type_{array.InnerType}");
                        continue;
                    }
                    for (var i = 0; i < array.Properties.Count; i++)
                    {
                        Console.WriteLine($"TYPE\t{key}\t{obj.Name}\t{prop.Name.Text}.CompatibleAmmoNames[{i}]\tNameProperty");
                        inspected++;
                    }
                }
            }
            continue;
        }
        var destination = Path.Combine(args[1], Path.ChangeExtension(key, ".json"));
        Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
        File.WriteAllText(destination, Newtonsoft.Json.JsonConvert.SerializeObject(
            pkg.GetExports(), Newtonsoft.Json.Formatting.Indented));
    }
    if (args[2] == "inspect-types")
    {
        if (inspected == 0) throw new InvalidOperationException("No requested tagged property types were found");
        Console.WriteLine($"inspect-types: {inspected} tagged identity properties in {exactPackages.Count} packages");
    }
    else if (args[2] == "inspect-scs-tags")
    {
        if (inspected == 0) throw new InvalidOperationException("No SCS property tags were found");
        Console.WriteLine($"inspect-scs-tags: {inspected} original tagged fields in {exactPackages.Count} packages");
    }
    else Console.WriteLine($"dump-list: {exactPackages.Count} exact Blueprint packages in {sw.Elapsed.TotalSeconds:F2}s");
    return;
}


if (args.Skip(2).FirstOrDefault() == "find")   // list pak paths containing every given substring
{
    foreach (var k in provider.Files.Keys.Where(k => args.Skip(3).All(s => k.Contains(s, StringComparison.OrdinalIgnoreCase))).OrderBy(k => k).Take(int.TryParse(Environment.GetEnvironmentVariable("FINDMAX"), out var fm) ? fm : 60))
        Console.WriteLine(k);
    return;
}

if (args.Skip(2).FirstOrDefault() == "dump")   // dump packages whose path contains every substring into dir args[1]
{
    foreach (var key in provider.Files.Keys.Where(k => k.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase) && args.Skip(3).All(s => k.Contains(s, StringComparison.OrdinalIgnoreCase))))
    {
        if (!provider.TryLoadPackage(key, out var p)) continue;
        var o = Path.Combine(args[1], Path.ChangeExtension(key, ".json"));
        Directory.CreateDirectory(Path.GetDirectoryName(o)!);
        File.WriteAllText(o, Newtonsoft.Json.JsonConvert.SerializeObject(p.GetExports(), Newtonsoft.Json.Formatting.Indented));
    }
    return;
}

if (args.Skip(2).FirstOrDefault() == "stats")
{
    // dump every DataTable-ish asset under Blueprints/Data as JSON into <outJson> (a directory)
    var n = 0;
    foreach (var key in provider.Files.Keys.Where(k => k.StartsWith("War/Content/Blueprints/Data/", StringComparison.OrdinalIgnoreCase)
                                                     && k.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase)))
    {
        if (!provider.TryLoadPackage(key, out var p)) continue;
        var outPath = Path.Combine(args[1], Path.ChangeExtension(key, ".json"));
        Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
        File.WriteAllText(outPath, Newtonsoft.Json.JsonConvert.SerializeObject(p.GetExports(), Newtonsoft.Json.Formatting.Indented));
        n++;
    }
    Console.WriteLine($"stats: {n} assets in {sw.Elapsed.TotalSeconds:F2}s");
    return;
}

var hexes = args.Skip(2).ToList();
if (hexes is ["all"])
    hexes = provider.Files.Keys
        .Where(k => k.StartsWith("War/Content/Maps/Master/", StringComparison.OrdinalIgnoreCase)
                 && k.EndsWith(".umap", StringComparison.OrdinalIgnoreCase)
                 && k.Count(c => c == '/') == 4)
        .Select(k => Path.GetFileNameWithoutExtension(k)).OrderBy(x => x).ToList();

var result = new SortedDictionary<string, List<object>>();
foreach (var hex in hexes)
{
    var t0 = sw.Elapsed;
    if (!provider.TryLoadPackage($"War/Content/Maps/Master/{hex}", out var pkg)) { Console.WriteLine($"{hex}: load failed"); continue; }
    var found = new Dictionary<(string, long, long), object>();
    foreach (var e in pkg.GetExports())
    {
        if (!wanted.TryGetValue(e.ExportType, out var kind)) continue;
        var rc = e.GetOrDefault<FPackageIndex>("RootComponent");
        if (rc == null || rc.IsNull) continue;
        var comp = rc.Load<UObject>();
        if (comp == null) continue;
        var loc = comp.GetOrDefault("RelativeLocation", FVector.ZeroVector);
        found[(kind, (long)Math.Round(loc.X), (long)Math.Round(loc.Y))] = new { kind, e.ExportType, x = Math.Round(loc.X, 2), y = Math.Round(loc.Y, 2), z = Math.Round(loc.Z, 2) };
    }
    result[hex] = found.Values.ToList();
    Console.WriteLine($"{hex}: {found.Count} structures in {(sw.Elapsed - t0).TotalSeconds:F2}s");
}
File.WriteAllText(args[1], JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"done: {hexes.Count} maps, total {sw.Elapsed.TotalSeconds:F2}s");
