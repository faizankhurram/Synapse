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

Start the interactive system entry:

```bash
python main.py
```

Enter your hardware specs on the CLI. After hardware entry, you can optionally test one game by ID/title, or press Enter / `s` to skip. Catalog lists are not printed in the prompt.

- If you skip the game check, the system runs forward chaining across the full game set and prints the compatibility conclusions.
- If you choose a game, the system shows backward chaining proofs for that game's minimum and recommended requirements, plus a focused final diagnostic.

See `rules_description.txt` for a plain-English explanation of every rule.

No external rule-engine libraries are used. The only runtime dependency is `rich`.
