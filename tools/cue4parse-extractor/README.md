# CUE4Parse extractor (spike)

Reads Foxhole paks via CUE4Parse and dumps asset data as JSON.

- `Extractor.csproj` / `Program.cs`: the .NET 10 extractor. It references a local CUE4Parse checkout at
  `..\fh_map_exporter_spike\src_up\CUE4Parse\CUE4Parse\CUE4Parse.csproj`; adjust the path for your machine.
- `*.py`: one-off analysis scripts run against the exported JSON. They have hardcoded `D:/` paths (Steam
  install and `D:/work/extractor_spike/stats_out`), so edit them before use.

Spike quality: not wired into CI or the bot.
