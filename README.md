# SYNAPSE

SYNAPSE is a pure-Python multi-paradigm Knowledge Representation and Reasoning demo for PC hardware validation, game compatibility evaluation, and bottleneck inference.

It implements:

- Frame-based hardware and game profiles with slot facets, defaults, and `:if-needed` demons.
- A semantic network with `is-a`, `part-of`, and associative links.
- Programmatic First-Order Logic and Description Logic report structures.
- Horn clauses, Most General Unification, forward chaining, backward chaining, and closed-world unplayable verdicts.
- Clean terminal reports showing user input, step-by-step chaining, output traces, and final conclusions.

## Setup

```bash
cd synapse_kr
python -m pip install -r requirements.txt
```

## Run

Run every demonstration:

```bash
python main.py --all
```

Run a single scenario:

```bash
python main.py --config DummyUser_1
python main.py --config DummyUser_2
python main.py --config DummyUser_3
```

Or start the numeric selector:

```bash
python main.py
```

Enter a live system on the CLI (menu option 5, or flag):

```bash
python main.py --interactive
```

After hardware entry, you can optionally test one game by ID/title, or press Enter / `s` to skip. Catalog lists are not printed in the prompt.

## Demo Scenarios

- `DummyUser_1`: incomplete user input resolved through catalog lookup demons and defaults; balanced SSD rig; includes backward proofs for `PlayableRecommended(DummyUser_1, G06)` and `PlayableRecommended(DummyUser_1, G01)`.
- `DummyUser_2`: CPU bottleneck with an HDD; shows `Severe_CPU_Bound` and SSD recommendation warnings for eligible games.
- `DummyUser_3`: structural hardware faults; Stage 0 fails for socket, RAM generation, and power sufficiency, so Stage 1-3 inference halts.

No external rule-engine libraries are used. The only runtime dependency is `rich`.
