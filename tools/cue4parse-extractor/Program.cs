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

var sw = Stopwatch.StartNew();
var provider = new DefaultFileProvider(args[0], SearchOption.TopDirectoryOnly,
    new VersionContainer(EGame.GAME_UE4_24), StringComparer.OrdinalIgnoreCase);
provider.Initialize();
provider.SubmitKey(new FGuid(), new FAesKey("0x" + new string('0', 64)));
provider.PostMount();
Console.WriteLine($"provider ready: {provider.Files.Count} files, {sw.Elapsed.TotalSeconds:F2}s");

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

if (args.Skip(2).FirstOrDefault() == "blueprints")   // every package under the folders the generators read, into dir args[1]
{
    string[] folders = ["Structures", "Vehicles", "ItemPickups", "Items", "DamageTypes", "Data"];
    int n = 0, failed = 0;
    foreach (var key in provider.Files.Keys.Where(k => k.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase)
        && folders.Any(f => k.StartsWith($"War/Content/Blueprints/{f}/", StringComparison.OrdinalIgnoreCase))))
    {
        if (!provider.TryLoadPackage(key, out var p)) { failed++; continue; }
        var o = Path.Combine(args[1], Path.ChangeExtension(key, ".json"));
        Directory.CreateDirectory(Path.GetDirectoryName(o)!);
        File.WriteAllText(o, Newtonsoft.Json.JsonConvert.SerializeObject(p.GetExports(), Newtonsoft.Json.Formatting.Indented));
        n++;
    }
    Console.WriteLine($"blueprints: {n} packages, {failed} failed, {sw.Elapsed.TotalSeconds:F1}s");
    return;
}

if (args.Skip(2).FirstOrDefault() == "names")   // list packages whose name table contains every given substring; output is one path per line into args[1]
{
    var wanted2 = args.Skip(3).ToArray();
    var found2 = new List<string>(); int scanned = 0, failed2 = 0;
    foreach (var key in provider.Files.Keys.Where(k => k.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase) || k.EndsWith(".umap", StringComparison.OrdinalIgnoreCase)))
    {
        scanned++;
        try
        {
            if (!provider.TryLoadPackage(key, out var p)) { failed2++; continue; }
            var names = ((CUE4Parse.UE4.Assets.Package)p).NameMap.Select(n => n.Name).ToList();
            if (wanted2.All(w => names.Any(n => n.Contains(w, StringComparison.OrdinalIgnoreCase)))) found2.Add(key);
        }
        catch { failed2++; }
    }
    File.WriteAllLines(args[1], found2.OrderBy(x => x));
    Console.WriteLine($"names: {found2.Count} of {scanned} packages match ({failed2} unreadable), {sw.Elapsed.TotalSeconds:F1}s");
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
