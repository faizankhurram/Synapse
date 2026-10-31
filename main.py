"""SYNAPSE entry point."""

import argparse

from rich.console import Console

from engine.backward_chainer import BackwardChainer
from engine.forward_chainer import forward_chain, system_and_game_facts
from engine.pre_checks import evaluate_pre_checks
from knowledge.catalog_db import CPUS, GAMES, GPUS, MOTHERBOARDS
from knowledge.frames import collect_resolution_log, instantiate_games, instantiate_system
from knowledge.matcher import longest_match, resolve_catalog_key
from knowledge.semantic_net import build_semantic_network
from logic.formal_logic import validate_dl_disjointness
from logic.horn_clause import P
from traces.cli_renderer import (
    render_conclusions,
    render_focused_game_conclusion,
    render_forward_trace,
    render_halt_conclusion,
    render_header,
    render_pre_checks,
    render_proofs,
    render_user_input,
)


DUMMY_USERS = {
    "DummyUser_1": {
        "description": "Incomplete user knowledge plus balanced mid-range rig on SSD",
        "raw": {
            "cpu": {"model_name": "AMD Ryzen 5 5600"},
            "gpu": {"model_name": "NVIDIA GeForce RTX 3060 12GB"},
            "motherboard": {"model_name": "MSI B550-A PRO"},
            "ram": {"capacity_gb": 16},
            "storage": {"drive_type": "SSD", "free_space_gb": 120.0},
            "psu": {"wattage": 650},
        },
        "proofs": [
            P("PlayableRecommended", "DummyUser_1", "G06"),
            P("PlayableRecommended", "DummyUser_1", "G01"),
        ],
    },
    "DummyUser_2": {
        "description": "Bottlenecked rig with HDD streaming warning",
        "raw": {
            "cpu": {"model_name": "AMD Ryzen 3 1200"},
            "gpu": {"model_name": "NVIDIA GeForce RTX 3070"},
            "motherboard": {"model_name": "MSI B550-A PRO"},
            "ram": {"capacity_gb": 16, "generation": "DDR4"},
            "storage": {"drive_type": "HDD", "free_space_gb": 250.0},
            "psu": {"wattage": 650},
        },
        "proofs": [P("PlayableMinimum", "DummyUser_2", "G08")],
    },
    "DummyUser_3": {
        "description": "Physical hardware fault rig",
        "raw": {
            "cpu": {"model_name": "Intel Core i5-12400F"},
            "gpu": {"model_name": "NVIDIA GeForce RTX 4090"},
            "motherboard": {"model_name": "MSI B550-A PRO"},
            "ram": {"capacity_gb": 16, "generation": "DDR5"},
            "storage": {"drive_type": "SSD", "free_space_gb": 500.0},
            "psu": {"wattage": 500},
        },
        "proofs": [],
    },
}


def _ask(prompt: str, required: bool = True) -> str:
    while True:
        value = input(prompt).strip()
        if value or not required:
            return value
        print("  This field is required.")


def _ask_int_in_range(prompt: str, lo: int, hi: int) -> int:
    while True:
        raw = _ask(prompt, required=True)
        try:
            value = int(raw)
        except ValueError:
            print(f"  Invalid input. Enter an integer between {lo} and {hi}.")
            continue
        if lo <= value <= hi:
            return value
        print(f"  Out of range. Enter an integer between {lo} and {hi}.")


def _ask_float_in_range(prompt: str, lo: float, hi: float) -> float:
    while True:
        raw = _ask(prompt, required=True)
        try:
            value = float(raw)
        except ValueError:
            print(f"  Invalid input. Enter a number between {lo} and {hi}.")
            continue
        if lo <= value <= hi:
            return value
        print(f"  Out of range. Enter a number between {lo} and {hi}.")


def _ask_optional_choice(prompt: str, allowed: set[str]) -> str | None:
    allowed_display = "/".join(sorted(allowed))
    while True:
        raw = _ask(prompt, required=False)
        if not raw:
            return None
        value = raw.upper()
        if value in allowed:
            return value
        print(f"  Invalid input. Enter one of {allowed_display}, or leave blank.")


def _ask_catalog_model(prompt: str, catalog: dict, kind: str) -> str:
    while True:
        raw = _ask(prompt, required=True)
        matched = resolve_catalog_key(raw, catalog)
        if matched is None:
            print(f"  Could not interpret that {kind} name. Try again.")
            continue
        if matched.casefold() != raw.casefold():
            print(f"  Interpreted as: {matched}")
        return matched


def collect_interactive_raw() -> dict:
    print()
    print("Interactive system entry")
    print("Leave optional fields blank to let catalog lookup / defaults fill them.")
    print()

    cpu_model = _ask_catalog_model("CPU model name: ", CPUS, "CPU")
    gpu_model = _ask_catalog_model("GPU model name: ", GPUS, "GPU")
    mobo_model = _ask_catalog_model("Motherboard model name: ", MOTHERBOARDS, "motherboard")
    ram_capacity = _ask_int_in_range("RAM capacity (GB): ", 4, 128)
    ram_gen = _ask_optional_choice(
        "RAM generation (DDR3/DDR4/DDR5, blank for default DDR4): ",
        {"DDR3", "DDR4", "DDR5"},
    )
    drive_type = _ask_optional_choice(
        "Storage drive type (HDD/SSD, blank for default SSD): ",
        {"HDD", "SSD"},
    )
    free_space = _ask_float_in_range("Storage free space (GB): ", 0.0, 10000.0)
    psu_wattage = _ask_int_in_range("PSU wattage (W): ", 200, 1600)

    raw = {
        "cpu": {"model_name": cpu_model},
        "gpu": {"model_name": gpu_model},
        "motherboard": {"model_name": mobo_model},
        "ram": {"capacity_gb": ram_capacity},
        "storage": {"free_space_gb": free_space, "drive_type": drive_type or "SSD"},
        "psu": {"wattage": psu_wattage},
    }
    if ram_gen:
        raw["ram"]["generation"] = ram_gen
    return raw


def resolve_game_query(query: str) -> str | None:
    text = query.strip()
    if not text:
        return None

    upper = text.upper()
    if upper in GAMES:
        return upper

    # Match against game IDs and titles with the same longest-match scorer.
    labels = []
    label_to_id = {}
    for game_id, data in GAMES.items():
        labels.append(game_id)
        label_to_id[game_id] = game_id
        labels.append(data["title_name"])
        label_to_id[data["title_name"]] = game_id
        combo = f"{game_id} {data['title_name']}"
        labels.append(combo)
        label_to_id[combo] = game_id

    matched_label = longest_match(text, labels)
    if matched_label is None:
        return None
    return label_to_id[matched_label]


def ask_optional_game() -> str | None:
    print()
    print("Optional game compatibility check")
    print("Enter a game ID (e.g. G01) or title. Press Enter or type s to skip.")
    while True:
        query = input("Game to test (or Enter/s to skip): ").strip()
        if not query or query.lower() == "s":
            return None
        game_id = resolve_game_query(query)
        if game_id is None:
            print("  Could not interpret that game entry. Try again, or press Enter/s to skip.")
            continue
        title = GAMES[game_id]["title_name"]
        if query.casefold() not in {game_id.casefold(), title.casefold()}:
            print(f"  Interpreted as: {game_id} - {title}")
        else:
            print(f"  Selected: {game_id} - {title}")
        return game_id


def _build_kr_artifacts(system, facts: set):
    """Keep frames / semantic net / DL artifacts alive in the backend (not printed)."""
    games = instantiate_games()
    resolution_log = collect_resolution_log(system)
    diagnostics = [
        args[1]
        for pred, args in facts
        if pred in {"Bottleneck", "SystemBalance"} and args[0] == system.instance_id
    ]
    if not diagnostics and not facts:
        diagnostics = ["StructuralHardwareFault"]
    semantic_net = build_semantic_network(system, games, diagnostics)
    dl_result = validate_dl_disjointness(facts)
    return {
        "games": games,
        "resolution_log": resolution_log,
        "semantic_net": semantic_net,
        "dl_result": dl_result,
    }


def run_pipeline(
    config_id: str,
    description: str,
    raw: dict,
    proofs: list,
    console: Console,
    focus_game_id: str | None = None,
) -> None:
    system = instantiate_system(config_id, raw)

    render_header(console, f"SYNAPSE: {config_id} - {description}")
    render_user_input(console, config_id, raw)

    pre_results = evaluate_pre_checks(system)
    ok = render_pre_checks(console, pre_results)
    if not ok:
        # Structural KR still computed for the knowledge layer; omitted from CLI output.
        _build_kr_artifacts(system, set())
        render_halt_conclusion(console, pre_results, raw, system)
        return

    # Forward closure still runs for diagnostics; focused game mode does not print it.
    forward = forward_chain(system)
    # Frames, semantic network, and DL consistency remain part of the engine path.
    _build_kr_artifacts(system, forward.facts)

    if focus_game_id is None:
        render_forward_trace(console, forward)
        prover = BackwardChainer(forward.facts)
        proof_nodes = [prover.prove(goal) for goal in proofs]
        render_proofs(console, proof_nodes)
        render_conclusions(console, config_id, forward.facts, forward.limiting, raw, system)
        return

    # Prove from ground facts so the backward tree expands step by step for the requested game.
    prover = BackwardChainer(system_and_game_facts(system))
    proof_nodes = [prover.prove(goal) for goal in proofs]
    render_proofs(console, proof_nodes, section_title="3. BACKWARD CHAINING PROOFS (step by step)")
    render_focused_game_conclusion(
        console, config_id, focus_game_id, forward.facts, forward.limiting, raw, system
    )


def run_demo(config_id: str, console: Console) -> None:
    entry = DUMMY_USERS[config_id]
    run_pipeline(config_id, entry["description"], entry["raw"], entry["proofs"], console)


def run_interactive(console: Console) -> None:
    raw = collect_interactive_raw()
    game_id = ask_optional_game()
    proofs = []
    if game_id:
        proofs = [
            P("PlayableMinimum", "InteractiveUser", game_id),
            P("PlayableRecommended", "InteractiveUser", game_id),
        ]
    run_pipeline(
        "InteractiveUser",
        "CLI-entered live system configuration",
        raw,
        proofs,
        console,
        focus_game_id=game_id,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SYNAPSE multi-paradigm KRR expert system demo")
    parser.add_argument("--all", action="store_true", help="Run all dummy user configurations")
    parser.add_argument("--config", choices=sorted(DUMMY_USERS), help="Run one dummy user configuration")
    parser.add_argument("--interactive", action="store_true", help="Enter a live system configuration on the CLI")
    return parser.parse_args()


def select_mode(args: argparse.Namespace):
    if args.interactive:
        return ("interactive", None)
    if args.all:
        return ("demos", list(DUMMY_USERS))
    if args.config:
        return ("demos", [args.config])

    print("SYNAPSE demo selector")
    print("1. DummyUser_1 - incomplete balanced SSD rig")
    print("2. DummyUser_2 - CPU bottleneck HDD rig")
    print("3. DummyUser_3 - physical fault rig")
    print("4. All demos")
    print("5. Enter my own system specs (interactive)")
    choice = input("Select 1/2/3/4/5: ").strip()
    if choice == "5":
        return ("interactive", None)
    return (
        "demos",
        {
            "1": ["DummyUser_1"],
            "2": ["DummyUser_2"],
            "3": ["DummyUser_3"],
            "4": list(DUMMY_USERS),
        }.get(choice, ["DummyUser_1"]),
    )


def main() -> None:
    console = Console()
    mode, configs = select_mode(parse_args())
    if mode == "interactive":
        run_interactive(console)
        console.print()
        return
    for config_id in configs:
        run_demo(config_id, console)
        console.print()


if __name__ == "__main__":
    main()
