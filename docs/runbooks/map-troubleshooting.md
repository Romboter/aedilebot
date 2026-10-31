# Runbook: Missing relics, wrong names, and map-data anomalies

**Status:** Troubleshooting guidance for **prototype/unverified production pipeline**. The raw UnrealExporter examples are recovered research; the current CUE4Parse extractor JSON schema is different. **Use for:** relic count zero, unexpected names, duplicate Town Bases or changed map.

## Identify the failing gate

1. **Download:** Does SteamCMD confirm AppID 505460 Windows depot? Does expected PAK exist and have reasonable size?
2. **Export:** Does the pinned C# exporter exit successfully and produce nonempty per-hex _json/*.json files? Which exporter SHA, source format and game build were recorded?
3. **Coverage:** Does a known map contain known structures? The recovered Lykos Isle raw UnrealExporter sample contained **five** distinct BPDestroyedRelicBase actors and **three** BPTownBase actor entries; two town entries shared coordinates. These figures are **historical fixture evidence**, not guaranteed for future patches. Preserve duplicates for inspection until actor identity is understood.
4. **Schema:** Raw export records include ArrowComponents and Outer/RelativeLocation; processed CUE4Parse geometry uses blueprints/symbols/groups/splines and may omit meshless Blueprint actors. Do **not** feed processed JSON into a parser expecting raw records without an explicit adapter.
5. **Coordinate space:** Verify world transforms versus component-relative coordinates, parent transforms and map normalization. Historical converter used common X [-109200,+109200] and Y [-94500,+94500]; treat as an empirical assumption, not all-map truth.
6. **Naming:** The old batch script mistakenly reused Basin Sionnach's 11 hardcoded markers for every hex. This caused grossly false Acrithia associations (e.g., 10k–25k units from supposed matches). Require **per-hex** static War API markers and a confidence/distance gate; ambiguous, far or unmatched results stay unapproved.
7. **Tier:** Relic class/mesh names have not been proven to map reliably to Small/Medium/Large tiers. Do not assign size based solely on iconType or guessed suffix.
8. **Static vs dynamic:** A destroyed/unbuilt live-war structure does not imply a patch removed that static map location. Never automatically delete from Locations.csv based on /dynamic/public absence.

## Procedure

- Keep the last successful archive and full raw input unchanged.
- Export one known hex and record its SHA. Inspect actor classes, transforms and count before applying any matching.
- Compare with historical actor positions and War API static markers **from that same hex**. Log candidate label, distance, source and confidence.
- If any known relic disappears in the new format, stop and pursue full actor/property exporter coverage (#40). Do not mark the scan as zero valid relics.
- Escalate unknown IDs, duplicate locations, map misalignment and inconsistent tiers to manual review; do not publish CSV automatically.

## Success criteria

Every known fixture survives extraction, transforms are coherent, unmatched/ambiguous cases are explicit, and a human reviewer can trace each proposal back to game build + map + actor + marker. Full coverage remains #40; automated location matching remains #17.

**Sources:** [map source decision #13](https://github.com/Romboter/aedilebot/issues/13), [recovered tools #14](https://github.com/Romboter/aedilebot/issues/14), [location matcher #17](https://github.com/Romboter/aedilebot/issues/17), [raw fidelity #40](https://github.com/Romboter/aedilebot/issues/40).
