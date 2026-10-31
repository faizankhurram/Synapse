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


def _fact_str(fact) -> str:
    name, args = fact
    return f"{name}{args}"


def render_forward_trace(console: Console, result) -> None:
    section(console, "3. FORWARD CHAINING TRACE (step by step)")
    counts = " -> ".join(str(c) for c in result.iteration_counts)
    console.print(f"Working memory size by iteration: {counts}")
    console.print(f"Total fired rule applications  : {len(result.fired)}")
    console.print()

    by_rule: dict[str, list] = {}
    for event in result.fired:
        by_rule.setdefault(event.rule_name, []).append(event)

    for rule_name, events in by_rule.items():
        console.print(f"[bold]{rule_name}[/bold]  ({len(events)} derivation(s))")
        show = events if len(events) <= 8 else events[:5]
        for event in show:
            console.print(f"  iter {event.iteration}: {_fact_str(event.derived_fact)}")
            console.print(f"           theta = {event.theta}")
        if len(events) > 8:
            console.print(f"  ... and {len(events) - 5} more for this rule")
        console.print()


def render_backward_proof(console: Console, proof, depth: int = 0) -> None:
    indent = "  " * depth
    style = "green" if proof.status else "red"
    console.print(f"{indent}[{style}]{escape(proof.label)}[/{style}]")
    if proof.theta and proof.theta != "{}":
        console.print(f"{indent}  theta = {proof.theta}")
    for child in proof.children:
        render_backward_proof(console, child, depth + 1)


def render_proofs(console: Console, proofs, section_title: str = "4. BACKWARD CHAINING PROOFS (step by step)") -> None:
    section(console, section_title)
    if not proofs:
        console.print("  (no backward goals requested for this config)")
        return
    for i, proof in enumerate(proofs, start=1):
        console.print(f"[bold]Goal {i}[/bold]")
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
