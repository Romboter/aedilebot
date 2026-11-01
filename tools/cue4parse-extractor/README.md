# CUE4Parse extractor (experimental)

This is the committed C# / .NET 10 Foxhole extractor spike. It is **not** yet an automated production data pipeline and has **not** been verified for full actor/property fidelity.

## Portable dependency

CUE4Parse is a pinned Git submodule at `tools/vendor/CUE4Parse`, not a Windows-specific path. Checked commit: `85495b5e126203d68ae3bf84e37fe31abd56a0e5` of `FabianFG/CUE4Parse`.

```bash
git submodule update --init tools/vendor/CUE4Parse
dotnet build tools/cue4parse-extractor/Extractor.csproj -c Release
```

Builds on the private Linux `foxhole-lab01` runner without root. The extractor itself reads only game PAK content; keep the PAK out of the public repository and CI logs.

## Invocation (from Linux)

```bash
# PAK_DIR must be a directory containing ONLY the vanilla War-WindowsNoEditor.pak.
# Access to this directory must be explicitly authorized for the process identity.
dotnet run --project tools/cue4parse-extractor -- PAK_DIR /private/output/stats stats

dotnet run --project tools/cue4parse-extractor -- PAK_DIR /private/output/hexes.json all

dotnet run --project tools/cue4parse-extractor -- PAK_DIR /private/output/unused find BPAmmoDynamicData

dotnet run --project tools/cue4parse-extractor -- PAK_DIR /private/output/dump dump BPAmmoDynamicData
```

Modes: `stats` writes DataTable assets under the requested output directory; `all` scans master map packages for relic/town-base positions; `find` prints selected asset names; `dump` exports selected packages to a folder. Some modes are an exploratory spike, not a stable CLI. Audit the parser/output and verify counts before using it to update any bot data.

**Safety:** Do not use an unrestricted directory containing mod PAKs or credentials. Do not publish raw game assets. The `assetextract` / `steamfetch` / `foxrunner` VM accounts are intentionally separate.

## Research scripts

The companion Python `*.py` files are one-off research scripts and still have hardcoded `D:/` paths from Claude's original Windows spike. They are not incorporated in Linux CI and must be made portable before reuse.

## Linux test against actual licensed Foxhole data

On November 1, 2026, the isolated Ubuntu 24.04 VM successfully ran this exact extractor revision against a licensed vanilla Foxhole Windows PAK:

| Test | Observed result |
|---|---|
| Pinned source and dependency build | Passed on .NET 10 |
| `stats` | 53 DataTable JSON assets in ~0.61 seconds |
| `all` | 53 master maps in ~68.85 seconds |
| Selected relic/town-base detections | 431 total across 53 maps; no zero-result maps |

This validates **Linux compatibility and narrow extraction**, not class completeness, world-space transform fidelity, bot data accuracy, or full Unreal actor coverage. Raw outputs remained inside private temporary storage and were not committed or uploaded. Automated comparisons against the bot data files are still to be built.

A read-only input arrangement avoids broad access to the Steam installation: give the worker permission to read the vanilla PAK alone, then create a worker-owned temporary directory with a symlink named `War-WindowsNoEditor.pak` pointing at the file. Pass the temporary directory as the extractor's first argument. CUE4Parse enumerates the supplied directory; merely giving the worker `--x` on the original PAK parent directory is insufficient.
