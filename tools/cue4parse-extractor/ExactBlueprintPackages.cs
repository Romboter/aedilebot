using System.Text.RegularExpressions;

// Strict, bounded manifest of exact Blueprint package paths supplied by the
// offline dependency scanner. This intentionally cannot export arbitrary paths.
internal static class ExactBlueprintPackages
{
    private const string Prefix = "War/Content/Blueprints/";
    private static readonly Regex Package = new(
        @"^[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*$",
        RegexOptions.CultureInvariant | RegexOptions.Compiled);

    public static IReadOnlyList<string> ReadManifest(string file)
    {
        var info = new FileInfo(file);
        if (!info.Exists || info.Length > 65536)
            throw new InvalidOperationException("Manifest missing or exceeds 64 KiB limit");

        var result = new SortedSet<string>(StringComparer.Ordinal);
        foreach (var sourceLine in File.ReadAllLines(file))
        {
            var entry = sourceLine.Trim();
            if (entry.Length == 0 || entry.StartsWith('#'))
                continue;

            if (!entry.StartsWith(Prefix, StringComparison.Ordinal) ||
                !Package.IsMatch(entry[Prefix.Length..]))
                throw new InvalidOperationException($"Invalid or non-Blueprint package path: {entry}");

            result.Add(entry + ".uasset");
            if (result.Count > 256)
                throw new InvalidOperationException("Too many distinct package requests (maximum 256)");
        }
        if (result.Count == 0)
            throw new InvalidOperationException("Manifest contains no Blueprint package requests");

        return result.ToArray();
    }
}
