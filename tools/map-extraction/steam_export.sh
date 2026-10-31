#!/usr/bin/env bash
# Linux SteamCMD + pinned CUE4Parse exporter. Requires persistent, preauthenticated
# SteamCMD and a dedicated self-hosted Linux runner. Do not run with sudo.
set -Eeuo pipefail
exporter_sha='db11ab571a6c95fb63c53d7c3bdec44d9f7966d1'
: "${FOXHOLE_WORK_ROOT:?Must configure FOXHOLE_WORK_ROOT to a persistent directory}"
: "${FOXHOLE_STEAM_USER:?Must configure FOXHOLE_STEAM_USER, preauthenticated under runner user}"
: "${GITHUB_WORKSPACE:?Must run within a GitHub Actions workspace}"
steamcmd_bin="${FOXHOLE_STEAMCMD_PATH:-/usr/games/steamcmd}"
[[ -x "$steamcmd_bin" ]] || { echo 'SteamCMD binary missing. Install steamcmd:i386 on Ubuntu.' >&2; exit 1; }
for bin in git dotnet python3 timeout; do command -v "$bin" >/dev/null || { echo "Missing $bin" >&2; exit 1; }; done
root="$(realpath -m "$FOXHOLE_WORK_ROOT")"
mkdir -p "$root"
game="$root/game"
pak="$game/War/Content/Paks/War-WindowsNoEditor.pak"
export_dir="$root/export"
out_dir="$root/outputs"
state_dir="$root/state"
source_dir="$root/tools/fh_map_exporter"
publish_dir="$root/tools/published-linux"
mkdir -p "$game" "$state_dir" "$out_dir"
available_kib="$(df -Pk "$root" | awk 'NR==2 {print $4}')"
required_kib=$((40 * 1024 * 1024))
[[ -f "$pak" ]] && required_kib=$((10 * 1024 * 1024))
if (( available_kib < required_kib )); then
  echo "Not enough free space for Foxhole: need at least $(( required_kib / 1024 / 1024 )) GiB free" >&2; exit 1
fi

# Force SteamCMD on Linux to download the *Windows* game content.
# Steam Guard/bootstrap must have been completed interactively beforehand.
# Never pass or log Steam passwords or Steam Guard tokens.
echo 'SteamCMD: update Foxhole (505460), Windows content on Linux.'
steam_log="$(mktemp)"
trap 'rm -f "$steam_log"' EXIT
set +e
timeout 100m "$steamcmd_bin" +@sSteamCmdForcePlatformType windows +force_install_dir "$game" +login "$FOXHOLE_STEAM_USER" +app_update 505460 +quit >"$steam_log" 2>&1
steam_status=$?
set -e
if (( steam_status != 0 )) || ! grep -Fq "Success! App '505460' fully installed" "$steam_log"; then
  echo "SteamCMD failed or did not confirm fresh installation (exit $steam_status). Reauthorize Steam Guard under the runner user if needed." >&2
  # Do not dump potentially sensitive SteamCMD output into GitHub job logs.
  exit 1
fi
[[ -s "$pak" ]] || { echo "Expected game PAK missing: $pak" >&2; exit 1; }
(( $(stat -c %s "$pak") > 1073741824 )) || { echo 'PAK is suspiciously small.' >&2; exit 1; }

echo "Building pinned CUE4Parse exporter: $exporter_sha"
mkdir -p "$(dirname "$source_dir")" "$publish_dir"
if [[ ! -d "$source_dir/.git" ]]; then
  git clone https://github.com/Tsekho/fh_map_exporter.git "$source_dir"
else
  git -C "$source_dir" fetch origin
fi
git -C "$source_dir" checkout --force --detach "$exporter_sha"
git -C "$source_dir" submodule update --init --recursive --force
[[ "$(git -C "$source_dir" rev-parse HEAD)" == "$exporter_sha" ]] || { echo 'Exporter revision mismatch.' >&2; exit 1; }
dotnet publish "$source_dir/Exporter/Exporter.csproj" -c Release -r linux-x64 --self-contained true -o "$publish_dir" -p:RuntimeIdentifier=linux-x64 -p:NuGetAudit=false
exporter_bin="$publish_dir/Exporter"
[[ -x "$exporter_bin" ]] || { echo 'Linux exporter executable missing.' >&2; exit 1; }

# Avoid stale/incomplete exports being included in subsequent reports.
rm -rf "$export_dir"
mkdir -p "$export_dir"
"$exporter_bin" -i "$pak" -o "$export_dir"
json_dir="$export_dir/_json"
[[ -d "$json_dir" ]] || { echo 'Exporter did not produce _json directory.' >&2; exit 1; }
count="$(find "$json_dir" -maxdepth 1 -type f -name '*.json' | wc -l)"
(( count >= 2 )) || { echo "Only $count map JSON files: refusing to publish." >&2; exit 1; }
python3 "$GITHUB_WORKSPACE/tools/map-extraction/inventory.py" --input "$json_dir" --output "$out_dir" --state "$state_dir" --exporter-sha "$exporter_sha" --pak "$pak"
echo "PASS: $count map files exported on Linux. Locations.csv remains unchanged."
