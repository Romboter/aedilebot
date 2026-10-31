#Requires -Version 7
param(
  [string] $WorkRoot = $env:FOXHOLE_WORK_ROOT,
  [string] $SteamCmdPath = $env:FOXHOLE_STEAMCMD_PATH,
  [string] $SteamUser = $env:FOXHOLE_STEAM_USER
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$exporterSha = 'db11ab571a6c95fb63c53d7c3bdec44d9f7966d1'
$exporterUrl = 'https://github.com/Tsekho/fh_map_exporter.git'
if ([string]::IsNullOrWhiteSpace($WorkRoot)) { throw 'FOXHOLE_WORK_ROOT is required (persistent volume with 80+ GiB free).' }
if ([string]::IsNullOrWhiteSpace($SteamCmdPath) -or !(Test-Path -LiteralPath $SteamCmdPath -PathType Leaf)) { throw 'FOXHOLE_STEAMCMD_PATH must point to steamcmd.exe.' }
if ([string]::IsNullOrWhiteSpace($SteamUser)) { throw 'FOXHOLE_STEAM_USER is missing; bootstrap the login with Steam Guard on the runner first.' }
foreach ($tool in @('git','dotnet','python')) { if (!(Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Missing executable: $tool" } }
$root = [IO.Path]::GetFullPath($WorkRoot)
$game = Join-Path $root 'game'
$tools = Join-Path $root 'tools/fh_map_exporter'
$published = Join-Path $root 'tools/published'
$export = Join-Path $root 'export'
$outputs = Join-Path $root 'outputs'
$state = Join-Path $root 'state'
$pak = Join-Path $game 'War/Content/Paks/War-WindowsNoEditor.pak'
$drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($root))
$minimum = if (Test-Path -LiteralPath $pak) { 10GB } else { 40GB }
if ($drive.AvailableFreeSpace -lt $minimum) { throw "Insufficient free disk space for Foxhole on $($drive.Name)" }
foreach ($dir in @($game,$outputs,$state)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

# No Steam password is accepted or emitted by this workflow. SteamCMD must
# reuse a previously authorized login belonging to the runner service user.
Write-Host 'SteamCMD: updating Foxhole app 505460 using stored account authentication.'
$steamResult = @(& $SteamCmdPath +force_install_dir $game +login $SteamUser +app_update 505460 +quit 2>&1 | ForEach-Object { $_.ToString() })
foreach ($line in $steamResult) { if ($line -notmatch '(?i)password|steam guard|authentication code') { Write-Host $line } }
if ($LASTEXITCODE -ne 0) { throw "SteamCMD failed with exit code $LASTEXITCODE. Reauthorize Steam Guard locally under the runner identity." }
if (!(($steamResult -join [Environment]::NewLine) -match "Success! App '505460' fully installed")) { throw 'SteamCMD did not confirm a successful install; refusing to reuse stale assets.' }
if (!(Test-Path -LiteralPath $pak -PathType Leaf) -or (Get-Item -LiteralPath $pak).Length -lt 1GB) { throw 'Expected valid game PAK was not downloaded.' }

# Pin and build the third-party extractor from SOURCE. No unverified binaries.
if (!(Test-Path -LiteralPath (Join-Path $tools '.git'))) {
  New-Item -ItemType Directory -Path (Split-Path $tools) -Force | Out-Null
  & git clone --recurse-submodules $exporterUrl $tools
  if ($LASTEXITCODE -ne 0) { throw 'Unable to clone map exporter.' }
} else {
  & git -C $tools fetch origin
  if ($LASTEXITCODE -ne 0) { throw 'Unable to fetch map exporter.' }
}
& git -C $tools checkout --force --detach $exporterSha
if ($LASTEXITCODE -ne 0) { throw 'Pinned map exporter checkout failed.' }
& git -C $tools submodule update --init --recursive --force
if ($LASTEXITCODE -ne 0) { throw 'Pinned exporter submodule checkout failed.' }
if ((& git -C $tools rev-parse HEAD).Trim() -ne $exporterSha) { throw 'Exporter source SHA mismatch.' }
New-Item -ItemType Directory -Path $published -Force | Out-Null
& dotnet publish (Join-Path $tools 'Exporter/Exporter.csproj') -c Release -r win-x64 --self-contained true -o $published -p:NuGetAudit=false
if ($LASTEXITCODE -ne 0) { throw 'Map exporter compilation failed.' }
$exe = Join-Path $published 'Exporter.exe'
if (!(Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Exporter.exe not produced.' }

if (Test-Path -LiteralPath $export) { Remove-Item -LiteralPath $export -Recurse -Force }
New-Item -ItemType Directory -Path $export -Force | Out-Null
Write-Host 'Exporting all map JSON, without optional terrain textures.'
& $exe -i $pak -o $export
if ($LASTEXITCODE -ne 0) { throw 'Unreal map exporter failed.' }
$jsonDir = Join-Path $export '_json'
$maps = @(Get-ChildItem -LiteralPath $jsonDir -Filter '*.json' -File -ErrorAction SilentlyContinue)
if ($maps.Count -lt 2) { throw 'Exporter produced fewer than 2 map JSON files.' }
if ([string]::IsNullOrWhiteSpace($env:GITHUB_WORKSPACE)) { throw 'GITHUB_WORKSPACE is missing.' }
& python (Join-Path $env:GITHUB_WORKSPACE 'tools/map-extraction/inventory.py') --input $jsonDir --output $outputs --state $state --exporter-sha $exporterSha --pak $pak
if ($LASTEXITCODE -ne 0) { throw 'Map inventory generation failed.' }
Write-Host "Exported $($maps.Count) maps. Relic/Town Base classification is NOT yet validated."
