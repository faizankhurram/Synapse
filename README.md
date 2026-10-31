# SYNAPSE

SYNAPSE is a pure-Python multi-paradigm Knowledge Representation and Reasoning system for PC hardware validation, game compatibility evaluation, and bottleneck inference.

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

### CLI Mode

Start the original interactive CLI system entry:

```bash
python main.py
```

Enter your hardware specs on the CLI. After hardware entry, you can optionally test one game by ID/title, or press Enter / `s` to skip. Catalog lists are not printed in the prompt.

- If you skip the game check, the system runs forward chaining across the full game set and prints the compatibility conclusions.
- If you choose a game, the system shows backward chaining proofs for that game's minimum and recommended requirements, plus a focused final diagnostic.

### Frontend Mode

Start the Flask frontend:

```bash
python frontend_app.py
```

Then open the local URL shown in the terminal. The frontend collects the same inputs as the CLI and sends them to `main.py` through a Python subprocess. The CLI output is still generated completely; the frontend filters it for a cleaner display.

See `rules_description.txt` for a plain-English explanation of every rule.

No external rule-engine libraries are used. Runtime dependencies are `rich` and `Flask`.
