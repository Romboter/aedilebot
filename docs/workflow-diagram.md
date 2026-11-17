# End-to-end workflow: from a player's question to the game data behind it

Solid boxes are built. Dashed boxes are planned (Phase 4 spec, `docs/superpowers/specs/2026-10-31-phase4-automated-data-pipeline-design.md`).
Status as of 2026-11-08, branch `rewrite/node-ts`.

```mermaid
flowchart TB
    subgraph QUERY["1. Player query (live bot, bot-ts)"]
        U([Discord user]) -->|"/kill /disable /dehusk /bunkerkill /how /statsheet or free text"| GW["gateway/<br/>commandRouter + freeTextDispatch<br/>(MESSAGE_CONTENT intent)"]
        GW --> AC["autocompleteHandlers<br/>aliasIndex + fuzzy match"]
        GW --> CMD["commands/*<br/>parse target, weapon, structure names"]
        CMD --> CALC["domain/calculator<br/>damage x mitigation x shelter bonus"]
        CMD --> SS["statsheet<br/>weapon/vehicle/structure text"]
        CALC --> REPLY([Reply in Discord])
        SS --> REPLY
    end

    subgraph STORE["2. Bot data layer (bot-ts/src/data)"]
        DS["dataStore.ts<br/>PluginHost snapshot, hot-swappable"]
        LOAD{"DATA_LAYOUT"}
        OLD["loader.ts<br/>hand-kept sheet<br/>(default today)"]
        NEW["newLoader.ts<br/>legacy-shape adapter<br/>(DATA_LAYOUT=new)"]
        CMD -. reads .-> DS
        CALC -. reads .-> DS
        AC -. reads .-> DS
        DS --> LOAD
        LOAD -->|unset| OLD
        LOAD -->|new| NEW
    end

    subgraph DATA["3. Repo data (data/ on main)"]
        SHEET["Sheet files<br/>Targets.json Weapons.json Damage.json ...<br/>(frozen, not edited)"]
        GEN["Generated<br/>vehicles structures materials<br/>aircraft_parts emplacements tripods<br/>bunker_pieces weapons.gen damage.gen<br/>locations.gen.csv"]
        OVL["data/overlay/<br/>hand-kept: names, aliases, armour types,<br/>multitier, tripod_excluded, bunker_pieces ..."]
    end
    OLD --> SHEET
    NEW --> GEN
    NEW --> OVL

    subgraph BUILD["4. Data build (scripts/, Python, run by hand today)"]
        GENS["gen_vehicles, gen_structures, gen_weapons_layout,<br/>gen_damage, gen_bunker_pieces, gen_aircraft_parts,<br/>gen_emplacements, gen_tripods, gen_locations<br/>+ parity checkers"]
        BP[("Blueprint JSON export<br/>Structures Vehicles ItemPickups<br/>Items DamageTypes Data<br/>3780 packages")]
        ST[("Map actors per hex<br/>relics + towns")]
        WAPI["War API<br/>/worldconquest/maps/HEX/static<br/>marker names"]
        BP --> GENS
        ST --> GENS
        WAPI --> GENS
    end
    GENS -->|"--write"| GEN

    subgraph EXTRACT["5. Extraction (tools/cue4parse-extractor, .NET 10)"]
        EX["Extractor<br/>modes: blueprints, stats, find, dump, hex names / all"]
        CUE["CUE4Parse<br/>tools/vendor submodule @ 85495b5"]
        PAK[("War-WindowsNoEditor.pak<br/>vanilla only, read-only<br/>pinned build 26058282")]
        PAK --> CUE --> EX
    end
    EX --> BP
    EX --> ST

    subgraph RUNNER["6. Where it runs"]
        WIN["Windows dev box<br/>manual runs today"]
        LAB["Private repo Romboter/foxhole-lab<br/>self-hosted Linux runner foxhole-lab01<br/>branch-triggered automation/* workflows<br/>(audits, Linux build proven)"]
        STEAM["SteamCMD / Steam<br/>game install, no auto-update"]
        STEAM --> PAK
        WIN -. runs .-> EX
        LAB -. runs .-> EX
    end

    subgraph AUTO["7. Planned automation (Phase 4, not built)"]
        CRON["GitHub cron, 5 min<br/>detect new Steam buildid"]:::plan
        ONE["One-command runner<br/>extract + War API + generators<br/>+ parity tests + diff report"]:::plan
        PR["Open PR against public repo<br/>(bot token / GitHub App)"]:::plan
        REV{{"Human reviews and merges"}}:::plan
        POLL["Bot polls data/ on main<br/>validate, stage, hot-swap"]:::plan
        CRON --> LAB
        LAB --> ONE --> PR --> REV --> POLL
    end
    POLL -.-> DS

    classDef plan stroke-dasharray: 5 5,fill:#f6f6f6,color:#333
```

## Reading it

1. **Query path (top):** a Discord message or slash command goes through the gateway to a command, which reads the current data snapshot, runs the calculator or statsheet, and replies.
2. **Data layer:** the snapshot comes from one of two loaders. The hand-kept sheet is still the default; `DATA_LAYOUT=new` loads the generated files through the adapter, so the calculator and statsheet code is the same either way.
3. **Build path (bottom):** the PAK is read by CUE4Parse through our extractor, which writes the Blueprint JSON and map actors. Python generators turn those, plus War API marker names and hand overlays, into the `data/` files.
4. **Still manual:** every arrow from the extractor to `data/` is run by hand. The planned part is detection, a one-command runner, the PR, human review, and the bot picking up merged data without a restart.
