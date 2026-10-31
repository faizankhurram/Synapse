"""Terminal rendering for SYNAPSE inference traces.

Default CLI output uses only the operational sections (input, chaining, conclusions).
Structural KR views (frames, semantic network, FOL/DL) remain available here for
report documentation and code screenshots; they are not printed by main.py.
"""

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from engine.forward_chainer import recommended_limiters
from knowledge.catalog_db import GAMES
from logic.formal_logic import DL_AXIOMS, FOL_FORMULAS

PASS = "[bold green][PASS][/bold green]"
FAIL = "[bold red][FAIL][/bold red]"
WARN = "[bold yellow][WARN][/bold yellow]"

RULE = "-" * 72


def section(console: Console, title: str) -> None:
    console.print()
    console.print(f"[bold cyan]{title}[/bold cyan]")
    console.print(RULE)


def render_header(console: Console, title: str) -> None:
    console.print()
    console.print("=" * 72)
    console.print(f"[bold]{escape(title)}[/bold]")
    console.print("=" * 72)


def render_user_input(console: Console, config_id: str, raw: dict) -> None:
    section(console, "1. USER INPUT")
    console.print(f"Config ID : {config_id}")
    for key in ("cpu", "gpu", "motherboard", "ram", "storage", "psu"):
        console.print(f"  {key:12s}: {raw[key]}")


def render_specs_summary(console: Console, raw: dict, system=None) -> None:
    console.print("[bold]Entered system specs[/bold]")
    for key in ("cpu", "gpu", "motherboard", "ram", "storage", "psu"):
        console.print(f"  {key:12s}: {raw[key]}")
    if system is not None:
        console.print()
        console.print("[bold]Resolved system details[/bold]")
        for key in ("cpu", "gpu", "motherboard", "ram", "storage", "psu"):
            instance = system.values[key]
            resolved = {slot: instance.get(slot) for slot in instance.frame_class.all_slots()}
            console.print(f"  {key:12s}: {resolved}")
    console.print()


def render_pre_checks(console: Console, results) -> bool:
    section(console, "2. STAGE 0 PRE-CHECKS (step by step)")
    all_ok = True
    for row in results:
        status = PASS if row.passed else FAIL
        all_ok = all_ok and row.passed
        console.print(f"  {row.rule}")
        console.print(f"    check  : {row.detail}")
        console.print(f"    status : {status}")
        console.print()
    if not all_ok:
        console.print(f"{FAIL} Physical fault detected. Stage 1-3 inference halted.")
    return all_ok


def _game_title(game_id: str) -> str:
    data = GAMES.get(game_id)
    return data["title_name"] if data else game_id


def _profile_word(profile: str) -> str:
    return "minimum" if profile == "Min" else "recommended"


RULE_PLAIN = {
    "Rule 1.1 CPUMeetsTier": "CPU power check",
    "Rule 1.2 GPUMeetsTier": "GPU power check",
    "Rule 1.3 VRAMMeetsCapacity": "GPU memory (VRAM) check",
    "Rule 1.4 RAMMeetsCapacity": "System RAM check",
    "Rule 1.5 StorageMeetsCapacity": "Free storage space check",
    "Rule 1.6a StorageMeetsMedium_HDD": "Storage type check (HDD allowed)",
    "Rule 1.6b StorageMeetsMedium_SSD": "Storage type check (SSD required)",
    "Rule 1.7 DirectXMeetsAPI": "DirectX version check",
    "Rule 2.1 PlayableMinimum": "Can run at minimum settings",
    "Rule 2.2 PlayableRecommended": "Can run at recommended settings",
    "Rule 3.1 Severe_CPU_Bound": "CPU is holding the GPU back",
    "Rule 3.2 Severe_GPU_Bound": "GPU is holding the CPU back",
    "Rule 3.3 Well_Balanced": "CPU and GPU are well matched",
    "Rule 3.4 SSD_Recommended_Warning": "SSD upgrade recommended",
}


def _plain_forward_line(event) -> str:
    name, args = event.derived_fact
    if name in {"CPUMeetsTier", "GPUMeetsTier", "VRAMMeetsCapacity", "RAMMeetsCapacity", "StorageMeetsCapacity", "StorageMeetsMedium", "DirectXMeetsAPI"}:
        label = {
            "CPUMeetsTier": "CPU",
            "GPUMeetsTier": "GPU",
            "VRAMMeetsCapacity": "VRAM",
            "RAMMeetsCapacity": "RAM",
            "StorageMeetsCapacity": "storage space",
            "StorageMeetsMedium": "storage type",
            "DirectXMeetsAPI": "DirectX",
        }[name]
        system_id, game_id, profile = args
        return f"{label} is enough for {_profile_word(profile)} settings of {_game_title(game_id)} ({game_id})"
    if name == "PlayableMinimum":
        return f"{_game_title(args[1])} ({args[1]}) is playable at minimum settings"
    if name == "PlayableRecommended":
        return f"{_game_title(args[1])} ({args[1]}) is playable at recommended settings"
    if name == "Bottleneck":
        kind = "CPU bottleneck" if args[1] == "Severe_CPU_Bound" else "GPU bottleneck"
        return f"System shows a severe {kind}"
    if name == "SystemBalance":
        return "System CPU and GPU tiers are well balanced"
    if name == "Warning":
        return f"Warning for {_game_title(args[1])} ({args[1]}): an SSD is recommended"
    return f"Derived: {name} {args}"


def _stage_of_rule(rule_name: str) -> int:
    if "Rule 3." in rule_name:
        return 3
    if "Rule 2." in rule_name:
        return 2
    return 1


def render_forward_trace(console: Console, result) -> None:
    section(console, "3. FORWARD CHAINING TRACE (step by step)")
    console.print(f"Facts known at start -> end: {' -> '.join(str(c) for c in result.iteration_counts)}")
    console.print(f"Total new conclusions made: {len(result.fired)}")
    console.print()

    by_rule: dict[str, list] = {}
    for event in result.fired:
        by_rule.setdefault(event.rule_name, []).append(event)

    for stage, stage_title in (
        (1, "Stage 1 - Part-by-part checks against each game"),
        (2, "Stage 2 - Overall playability decisions"),
        (3, "Stage 3 - Bottleneck and warning diagnostics"),
    ):
        stage_rules = [(name, events) for name, events in by_rule.items() if _stage_of_rule(name) == stage]
        if not stage_rules:
            continue
        console.print(f"[bold]{stage_title}[/bold]")
        for rule_name, events in stage_rules:
            plain = RULE_PLAIN.get(rule_name, rule_name)
            console.print(f"  {plain}  [{len(events)} conclusion(s)]")
            show = events if len(events) <= 6 else events[:4]
            for event in show:
                console.print(f"    - {_plain_forward_line(event)}")
            if len(events) > 6:
                console.print(f"    - ... and {len(events) - 4} more similar conclusions")
        console.print()


def _humanize_proof_label(label: str) -> str:
    text = label
    # Longer phrases first so rule titles are not partially rewritten.
    replacements = [
        ("Apply Rule 1.1 CPUMeetsTier", "Using CPU power rule"),
        ("Apply Rule 1.2 GPUMeetsTier", "Using GPU power rule"),
        ("Apply Rule 1.3 VRAMMeetsCapacity", "Using VRAM capacity rule"),
        ("Apply Rule 1.4 RAMMeetsCapacity", "Using RAM capacity rule"),
        ("Apply Rule 1.5 StorageMeetsCapacity", "Using storage space rule"),
        ("Apply Rule 1.6a StorageMeetsMedium_HDD", "Using HDD storage-type rule"),
        ("Apply Rule 1.6b StorageMeetsMedium_SSD", "Using SSD storage-type rule"),
        ("Apply Rule 1.7 DirectXMeetsAPI", "Using DirectX rule"),
        ("Apply Rule 2.1 PlayableMinimum", "Using minimum playability rule"),
        ("Apply Rule 2.2 PlayableRecommended", "Using recommended playability rule"),
        ("Apply Rule 3.1 Severe_CPU_Bound", "Using CPU bottleneck rule"),
        ("Apply Rule 3.2 Severe_GPU_Bound", "Using GPU bottleneck rule"),
        ("Apply Rule 3.3 Well_Balanced", "Using balance rule"),
        ("Apply Rule 3.4 SSD_Recommended_Warning", "Using SSD warning rule"),
        ("PlayableRecommended", "Recommended playability"),
        ("PlayableMinimum", "Minimum playability"),
        ("CPUMeetsTier", "CPU tier check"),
        ("GPUMeetsTier", "GPU tier check"),
        ("VRAMMeetsCapacity", "VRAM capacity check"),
        ("RAMMeetsCapacity", "RAM capacity check"),
        ("StorageMeetsCapacity", "Storage space check"),
        ("StorageMeetsMedium", "Storage type check"),
        ("DirectXMeetsAPI", "DirectX check"),
        ("SystemCPUTier", "System CPU tier"),
        ("SystemGPUTier", "System GPU tier"),
        ("SystemVRAM", "System VRAM"),
        ("SystemRAM", "System RAM"),
        ("SystemStorageFree", "Free storage"),
        ("SystemDriveType", "Drive type"),
        ("SystemDX", "System DirectX"),
        ("SystemConfig", "System configuration"),
        ("GameReqCPUTier", "Game required CPU tier"),
        ("GameReqGPUTier", "Game required GPU tier"),
        ("GameReqVRAM", "Game required VRAM"),
        ("GameReqRAM", "Game required RAM"),
        ("GameReqStorage", "Game required storage"),
        ("GameReqMedium", "Game required storage type"),
        ("GameReqDX", "Game required DirectX"),
        (" -> PROVEN", " -> YES, proven"),
        (" -> DISPROVEN", " -> NO, not proven"),
        ("Fact ", "Known fact: "),
        ("Goal ", "Need to prove: "),
        ("Compare ", "Number check: "),
        ("No proof for ", "Could not prove: "),
        ("Cycle blocked at ", "Stopped repeating check for: "),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    text = text.replace("('", " for ").replace("', '", ", ").replace("')", "")
    text = text.replace("(", " ").replace(")", "").replace("'", "")
    return " ".join(text.split())


def render_backward_proof(console: Console, proof, depth: int = 0) -> None:
    indent = "  " * depth
    style = "green" if proof.status else "red"
    mark = "OK" if proof.status else "X"
    console.print(f"{indent}[{style}][{mark}] {_humanize_proof_label(proof.label)}[/{style}]")
    for child in proof.children:
        render_backward_proof(console, child, depth + 1)


def _proof_test_heading(proof) -> str:
    label = proof.label
    if "PlayableRecommended" in label:
        return "Recommended requirements test"
    if "PlayableMinimum" in label:
        return "Minimum requirements test"
    return "Requirements test"


def render_proofs(console: Console, proofs, section_title: str = "4. BACKWARD CHAINING PROOFS (step by step)") -> None:
    section(console, section_title)
    if not proofs:
        console.print("  (no game-specific proof was requested)")
        return
    for proof in proofs:
        outcome = "PROVEN" if proof.status else "NOT PROVEN"
        color = "green" if proof.status else "red"
        console.print(
            f"[bold]{_proof_test_heading(proof)}[/bold]  "
            f"final answer: [bold {color}]{outcome}[/bold {color}]"
        )
        render_backward_proof(console, proof, depth=1)
        console.print()


def _system_diagnostic_lines(system_id: str, facts: set) -> tuple[list[str], list[str], list[str]]:
    bottlenecks = sorted(args[1] for pred, args in facts if pred == "Bottleneck" and args[0] == system_id)
    balances = sorted(args[1] for pred, args in facts if pred == "SystemBalance" and args[0] == system_id)
    warnings = sorted(
        f"{args[1]} -> {args[2]}"
        for pred, args in facts
        if pred == "Warning" and args[0] == system_id
    )
    return bottlenecks, balances, warnings


def _game_verdict(system_id: str, game_id: str, facts: set, limiting: dict[str, list[str]]) -> tuple[str, str, str]:
    if ("PlayableRecommended", (system_id, game_id)) in facts:
        verdict, color, notes = "RECOMMENDED", "green", ""
    elif ("PlayableMinimum", (system_id, game_id)) in facts:
        verdict, color = "MINIMUM ONLY", "yellow"
        notes = ", ".join(recommended_limiters(system_id, game_id, facts))
    else:
        verdict, color = "UNPLAYABLE", "red"
        notes = ", ".join(limiting.get(game_id, []))

    warn = [
        args[2]
        for pred, args in facts
        if pred == "Warning" and args[0] == system_id and args[1] == game_id
    ]
    if warn:
        notes = (notes + "; " if notes else "") + f"{WARN} {', '.join(warn)}"
    return verdict, color, notes


def render_conclusions(console: Console, system_id: str, facts: set, limiting: dict[str, list[str]], raw: dict, system=None) -> None:
    section(console, "5. FINAL CONCLUSIONS")
    render_specs_summary(console, raw, system)

    bottlenecks, balances, warnings = _system_diagnostic_lines(system_id, facts)
    console.print("[bold]System diagnostics[/bold]")
    console.print(f"  Bottleneck : {', '.join(bottlenecks) if bottlenecks else 'None'}")
    console.print(f"  Balance    : {', '.join(balances) if balances else 'Not classified'}")
    console.print(f"  Warnings   : {', '.join(warnings) if warnings else 'None'}")
    console.print()

    console.print("[bold]Game compatibility verdicts[/bold]")
    console.print(f"  {'ID':<5} {'Verdict':<14} Title / Notes")
    console.print(f"  {'-'*5} {'-'*14} {'-'*48}")

    recommended = minimum = unplayable = 0
    for game_id, data in GAMES.items():
        verdict, color, notes = _game_verdict(system_id, game_id, facts, limiting)
        if verdict == "RECOMMENDED":
            recommended += 1
        elif verdict == "MINIMUM ONLY":
            minimum += 1
        else:
            unplayable += 1
        line_notes = f"  {notes}" if notes else ""
        console.print(
            f"  {game_id:<5} [bold {color}]{verdict:<14}[/bold {color}] "
            f"{data['title_name']}{line_notes}"
        )

    console.print()
    console.print(
        f"  Summary: {recommended} recommended, {minimum} minimum-only, {unplayable} unplayable"
    )


def render_focused_game_conclusion(
    console: Console,
    system_id: str,
    game_id: str,
    facts: set,
    limiting: dict[str, list[str]],
    raw: dict,
    system=None,
) -> None:
    section(console, "4. FINAL CONCLUSIONS")
    render_specs_summary(console, raw, system)

    bottlenecks, balances, warnings = _system_diagnostic_lines(system_id, facts)
    game_warnings = [
        args[2]
        for pred, args in facts
        if pred == "Warning" and args[0] == system_id and args[1] == game_id
    ]
    console.print("[bold]System diagnostics[/bold]")
    console.print(f"  Bottleneck : {', '.join(bottlenecks) if bottlenecks else 'None'}")
    console.print(f"  Balance    : {', '.join(balances) if balances else 'Not classified'}")
    console.print(f"  Warnings   : {', '.join(warnings) if warnings else 'None'}")
    console.print()

    title = GAMES[game_id]["title_name"]
    verdict, color, notes = _game_verdict(system_id, game_id, facts, limiting)
    console.print(f"[bold]Requested game evaluation[/bold]: {game_id} - {title}")
    console.print(f"  Verdict : [bold {color}]{verdict}[/bold {color}]")
    console.print(f"  Notes   : {notes if notes else 'None'}")
    if game_warnings:
        console.print(f"  Game warnings: {', '.join(game_warnings)}")
    console.print()
    if ("PlayableRecommended", (system_id, game_id)) in facts:
        console.print("  Performance outlook: meets recommended requirements.")
    elif ("PlayableMinimum", (system_id, game_id)) in facts:
        console.print("  Performance outlook: playable at minimum settings; recommended target not met.")
    else:
        console.print("  Performance outlook: not playable under current system constraints.")


def render_halt_conclusion(console: Console, results, raw: dict, system=None) -> None:
    section(console, "5. FINAL CONCLUSIONS")
    render_specs_summary(console, raw, system)
    failed = [row.rule for row in results if not row.passed]
    console.print(f"{FAIL} Hardware configuration is physically invalid.")
    console.print("  Failed Stage 0 checks:")
    for name in failed:
        console.print(f"    - {name}")
    console.print("  Compatibility and bottleneck inference were not run.")


# ---------------------------------------------------------------------------
# Structural KR views retained for report screenshots / documentation.
# These are intentionally not invoked by main.py CLI output.
# ---------------------------------------------------------------------------


def render_frame_resolution(console: Console, config_id: str, raw: dict, system, resolution_log: list[dict]) -> None:
    table = Table(title=f"Frame and Demon Resolution: {config_id}", show_lines=True)
    table.add_column("Component", overflow="fold")
    table.add_column("Raw Partial User Input", overflow="fold")
    table.add_column("Resolved Frame Slots", overflow="fold")
    for slot in ("cpu", "gpu", "motherboard", "ram", "storage", "psu"):
        instance = system.values[slot]
        table.add_row(slot, str(raw[slot]), str(instance.materialize()))
    console.print(table)

    demon_table = Table(title="Activated Facets")
    demon_table.add_column("Component", overflow="fold")
    demon_table.add_column("Slot", overflow="fold")
    demon_table.add_column("Facet", overflow="fold")
    demon_table.add_column("Source", overflow="fold")
    demon_table.add_column("Value", overflow="fold")
    if resolution_log:
        for event in resolution_log:
            demon_table.add_row(
                event["component"],
                event["slot"],
                event["method"],
                event["source"],
                repr(event["value"]),
            )
    else:
        demon_table.add_row("-", "-", "-", "All supplied explicitly", "-")
    console.print(demon_table)


def render_diagnostics(console: Console, system_id: str, facts: set) -> None:
    bottlenecks, balances, warnings = _system_diagnostic_lines(system_id, facts)
    text = [
        f"Bottlenecks: {', '.join(bottlenecks) if bottlenecks else 'None'}",
        f"Balance: {', '.join(balances) if balances else 'Not classified'}",
        f"Warnings: {', '.join(warnings) if warnings else 'None'}",
    ]
    console.print(Panel("\n".join(text), title="Stage 3 Diagnostics"))


def render_semantic_net(console: Console, net, dl_result) -> None:
    root = Tree("[bold]Semantic Network[/bold]")
    by_source: dict[str, list] = {}
    for edge in net.edges:
        by_source.setdefault(edge.source, []).append(edge)
    for source in sorted(by_source):
        branch = root.add(f"[cyan]{source}[/cyan]")
        for edge in sorted(by_source[source], key=lambda e: (e.relation, e.target)):
            branch.add(f"{edge.relation} -> {edge.target}")
    console.print(root)

    status = PASS if dl_result.consistent else FAIL
    axiom_text = "\n".join(f"- {axiom}" for axiom in DL_AXIOMS)
    violation_text = "No disjointness violations." if dl_result.consistent else "\n".join(dl_result.violations)
    console.print(
        Panel(
            f"{status} DL Consistency\n\n[bold]ALCN Axioms[/bold]\n{axiom_text}\n\n"
            f"[bold]Result[/bold]\n{violation_text}",
            title="Description Logic",
        )
    )
    fol_text = "\n".join(f"[bold]{item['name']}[/bold]\n{item['formula']}" for item in FOL_FORMULAS)
    console.print(Panel(fol_text, title="First-Order Logic Formulas"))


def render_proof(console: Console, proof) -> None:
    """Single-proof tree helper retained for documentation screenshots."""
    root = Tree("[bold]Backward Chaining Goal Proof Tree[/bold]")

    def _attach(parent: Tree, node) -> None:
        style = "green" if node.status else "red"
        branch = parent.add(f"[{style}]{node.label}[/{style}] theta={node.theta}")
        for child in node.children:
            _attach(branch, child)

    _attach(root, proof)
    console.print(root)
