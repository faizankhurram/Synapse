# SYNAPSE

**A Hardware–Game Compatibility Reasoning System**

SYNAPSE answers a question PC builders ask all the time:

*"Will this build actually run the games I care about — and if not, what is holding it back?"*

It is a pure-Python Knowledge Representation & Reasoning  project. You describe a PC, and SYNAPSE checks whether the parts fit together safely, then judges game compatibility using formal rules — not a black-box recommendation API.

No external Prolog engine. No third-party rule library. Frames, logic, unification, and chaining are implemented in this repo.


## What it does

1. **Validates the hardware first**  
   Socket match, RAM generation match, PSU headroom, and free storage. If the build is physically wrong, game checks stop early.

2. **Scores games against your system**  
   Compares CPU tier, GPU tier, VRAM, RAM, storage space, drive type, and DirectX against each game’s minimum and recommended profiles.

3. **Produces clear verdicts**  
   - **Recommended** — comfortable for recommended settings  
   - **Minimum only** — playable, but not at recommended targets  
   - **Unplayable** — at least one hard requirement fails  

4. **Explains balance issues**  
   Detects CPU or GPU bottlenecks, well-balanced builds, and SSD upgrade warnings when a game is playable on HDD but prefers SSD.


## Features of SYNAPSE

| Capability | Why it matters |
|---|---|
| **Frames with auto-fill** | Pick a CPU/GPU model and specs (socket, TDP, tier, VRAM…) are filled from a curated catalog via `:if-needed` demons |
| **Semantic network** | Hardware and games are linked with `is-a`, `part-of`, fit/match, and evaluation relations |
| **Horn-clause rule base** | Stage 0–3 rules drive every decision; same rules power both chaining modes |
| **Forward chaining** | Scan the whole game catalog in one pass and derive every playability / diagnostic fact |
| **Backward chaining** | Ask about one game and get a goal-driven proof for minimum and recommended play |
| **Closed-world unplayable** | If minimum play cannot be proven, the game is marked unplayable with missing checks listed |
| **Dual interface** | Full step-by-step CLI traces, plus a styled Flask UI for demos and quick experiments |

Catalog highlights today:

- Broad CPU / GPU / motherboard coverage across older and modern platforms  
- **12 curated games** from low-demand titles (e.g. Valorant) to high-end stress cases (e.g. Alan Wake 2, S.T.A.L.K.E.R. 2)


## Flask frontend — what you can do

Start the web UI and you get a focused control panel for the same reasoning engine:

- **Build a PC from dropdowns** — CPU, GPU, motherboard from the live catalog; RAM, storage, and PSU as typed inputs with range checks  
- **Choose a reasoning mode**  
  - *Find All Compatible Games* → forward chaining across the full catalog  
  - *Already have a game? Test Compatibility* → search a title and run backward chaining  
- **Smart game search** — type a name, pick from ranked suggestions (no need to memorize IDs)  
- **Readable results**  
  - Stage 0 failures shown as plain-language cards (not raw CLI dumps)  
  - System diagnostics (bottleneck / balance / warnings)  
  - Game table with **Game Name · Verdict · Notes**  
  - Focused game card with verdict, notes, warnings, and performance outlook  
- **Reset after a run** — clear the page and try another configuration quickly  

The frontend still runs the real CLI pipeline under the hood (subprocess → `main.py`), then filters and styles the output for the browser.


## CLI mode — what you get in the terminal

Running `main.py` gives the full academic / debugging view:

1. User input  
2. Stage 0 pre-checks, step by step  
3. Forward chaining with **every** derived fact (rule numbers included), or backward proofs for one game  
4. Final conclusions — diagnostics plus an aligned **ID · Verdict · Title · Notes** table  

Useful when you need screenshots, viva demos, or a complete inference trace.


## Project layout (mental map)

```
synapse_kr/
├── main.py                 # Interactive CLI entry
├── frontend_app.py         # Flask server
├── frontend_bridge.py      # Subprocess bridge + output parsing
├── knowledge/              # Frames, catalog, matcher, semantic net
├── logic/                  # Horn clauses, FOL / DL helpers
├── engine/                 # Stage 0, unifier, forward & backward chaining
├── traces/                 # Rich terminal rendering
├── templates/ + static/    # Web UI
└── rules_description.txt   # Plain-English rule guide
```


## Setup

```bash
cd synapse_kr
python -m pip install -r requirements.txt
```

Runtime dependencies: **rich** (CLI) and **Flask** (web UI).


## Run

### CLI Mode

```bash
python main.py
```

Enter hardware specs interactively. After that you can:

- Press Enter / `s` to skip a single-game check → **forward chaining** over all games  
- Enter a game ID or title → **backward chaining** for that title’s minimum and recommended goals  

Typo-tolerant matching helps resolve catalog names when input is close but not exact.

### Frontend Mode

```bash
python frontend_app.py
```

Open the local URL printed in the terminal (usually `http://127.0.0.1:5000`).

Configure the system, pick a mode, run SYNAPSE, and inspect the styled results.


## Rules reference

Every Stage 0–3 rule is explained in [`rules_description.txt`](rules_description.txt).

