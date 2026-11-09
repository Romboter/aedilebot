# CUE4Parse extractor (spike)

Reads Foxhole paks via CUE4Parse and dumps asset data as JSON.

- `Extractor.csproj` / `Program.cs`: the .NET 10 extractor. It references the CUE4Parse submodule at
  `tools/CUE4Parse` (upstream FabianFG, pinned to 85495b5). Init it non-recursively:
  `git submodule update --init tools/CUE4Parse` (skips the native-code submodules).

Spike quality: not wired into CI or the bot.
