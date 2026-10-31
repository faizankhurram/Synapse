"""Forward chaining inference to deductive closure."""

from dataclasses import dataclass, field

from knowledge.catalog_db import GAMES, game_profile
from logic.horn_clause import ComparisonGuard, Fact, HornClause, P, Predicate, V
from engine.unifier import evaluate_guard, predicate_to_fact, theta_repr, unify_predicate_with_fact


@dataclass
class FiredRule:
    iteration: int
    rule_name: str
    theta: str
    derived_fact: Fact


@dataclass
class ForwardResult:
    facts: set[Fact]
    fired: list[FiredRule] = field(default_factory=list)
    iteration_counts: list[int] = field(default_factory=list)
    limiting: dict[str, list[str]] = field(default_factory=dict)


def build_rule_base() -> list[HornClause]:
    s, g, p = V("s"), V("g"), V("p")
    return [
        HornClause("Rule 1.1 CPUMeetsTier", 1, P("CPUMeetsTier", s, g, p), (
            P("SystemCPUTier", s, V("t_sys")), P("GameReqCPUTier", g, p, V("t_req")), ComparisonGuard("GreaterOrEqual", V("t_sys"), V("t_req")),
        )),
        HornClause("Rule 1.2 GPUMeetsTier", 1, P("GPUMeetsTier", s, g, p), (
            P("SystemGPUTier", s, V("t_sys")), P("GameReqGPUTier", g, p, V("t_req")), ComparisonGuard("GreaterOrEqual", V("t_sys"), V("t_req")),
        )),
        HornClause("Rule 1.3 VRAMMeetsCapacity", 1, P("VRAMMeetsCapacity", s, g, p), (
            P("SystemVRAM", s, V("v_sys")), P("GameReqVRAM", g, p, V("v_req")), ComparisonGuard("GreaterOrEqual", V("v_sys"), V("v_req")),
        )),
        HornClause("Rule 1.4 RAMMeetsCapacity", 1, P("RAMMeetsCapacity", s, g, p), (
            P("SystemRAM", s, V("r_sys")), P("GameReqRAM", g, p, V("r_req")), ComparisonGuard("GreaterOrEqual", V("r_sys"), V("r_req")),
        )),
        HornClause("Rule 1.5 StorageMeetsCapacity", 1, P("StorageMeetsCapacity", s, g, p), (
            P("SystemStorageFree", s, V("s_sys")), P("GameReqStorage", g, p, V("s_req")), ComparisonGuard("GreaterOrEqual", V("s_sys"), V("s_req")),
        )),
        HornClause("Rule 1.6a StorageMeetsMedium_HDD", 1, P("StorageMeetsMedium", s, g, p), (
            P("SystemConfig", s), P("GameReqMedium", g, p, "HDD"),
        )),
        HornClause("Rule 1.6b StorageMeetsMedium_SSD", 1, P("StorageMeetsMedium", s, g, p), (
            P("GameReqMedium", g, p, "SSD"), P("SystemDriveType", s, "SSD"),
        )),
        HornClause("Rule 1.7 DirectXMeetsAPI", 1, P("DirectXMeetsAPI", s, g, p), (
            P("SystemDX", s, V("d_sys")), P("GameReqDX", g, p, V("d_req")), ComparisonGuard("GreaterOrEqual", V("d_sys"), V("d_req")),
        )),
        HornClause("Rule 2.1 PlayableMinimum", 2, P("PlayableMinimum", s, g), (
            P("CPUMeetsTier", s, g, "Min"), P("GPUMeetsTier", s, g, "Min"), P("VRAMMeetsCapacity", s, g, "Min"),
            P("RAMMeetsCapacity", s, g, "Min"), P("StorageMeetsCapacity", s, g, "Min"), P("StorageMeetsMedium", s, g, "Min"), P("DirectXMeetsAPI", s, g, "Min"),
        )),
        HornClause("Rule 2.2 PlayableRecommended", 2, P("PlayableRecommended", s, g), (
            P("PlayableMinimum", s, g), P("CPUMeetsTier", s, g, "Rec"), P("GPUMeetsTier", s, g, "Rec"), P("VRAMMeetsCapacity", s, g, "Rec"),
            P("RAMMeetsCapacity", s, g, "Rec"), P("StorageMeetsCapacity", s, g, "Rec"), P("StorageMeetsMedium", s, g, "Rec"), P("DirectXMeetsAPI", s, g, "Rec"),
        )),
        HornClause("Rule 3.1 Severe_CPU_Bound", 3, P("Bottleneck", s, "Severe_CPU_Bound"), (
            P("SystemGPUTier", s, V("t_gpu")), P("SystemCPUTier", s, V("t_cpu")), ComparisonGuard("GreaterOrEqual", ("sub", V("t_gpu"), V("t_cpu")), 3),
        )),
        HornClause("Rule 3.2 Severe_GPU_Bound", 3, P("Bottleneck", s, "Severe_GPU_Bound"), (
            P("SystemCPUTier", s, V("t_cpu")), P("SystemGPUTier", s, V("t_gpu")), ComparisonGuard("GreaterOrEqual", ("sub", V("t_cpu"), V("t_gpu")), 3),
        )),
        HornClause("Rule 3.3 Well_Balanced", 3, P("SystemBalance", s, "Well_Balanced"), (
            P("SystemCPUTier", s, V("t_cpu")), P("SystemGPUTier", s, V("t_gpu")), ComparisonGuard("LessOrEqual", ("abs", ("sub", V("t_cpu"), V("t_gpu"))), 1),
        )),
        HornClause("Rule 3.4 SSD_Recommended_Warning", 3, P("Warning", s, g, "SSD_Recommended"), (
            P("PlayableMinimum", s, g), P("GameReqMedium", g, "Rec", "SSD"), P("SystemDriveType", s, "HDD"),
        )),
    ]


def system_and_game_facts(system) -> set[Fact]:
    sid = system.instance_id
    cpu = system.values["cpu"]
    gpu = system.values["gpu"]
    ram = system.values["ram"]
    mobo = system.values["motherboard"]
    storage = system.values["storage"]
    psu = system.values["psu"]
    facts: set[Fact] = {
        ("SystemConfig", (sid,)),
        ("SystemCPU", (sid, cpu.instance_id)),
        ("SystemMobo", (sid, mobo.instance_id)),
        ("CPUSocket", (cpu.instance_id, cpu.get("socket"))),
        ("MoboSocket", (mobo.instance_id, mobo.get("supported_socket"))),
        ("SystemRAMGen", (sid, ram.get("generation"))),
        ("MoboRAMGen", (mobo.instance_id, mobo.get("supported_ram_gen"))),
        ("SystemPSUWattage", (sid, psu.get("wattage"))),
        ("SystemCPUTDP", (sid, cpu.get("tdp_watts"))),
        ("SystemGPUTDP", (sid, gpu.get("tdp_watts"))),
        ("SystemStorageFree", (sid, storage.get("free_space_gb"))),
        ("SystemCPUTier", (sid, cpu.get("tier"))),
        ("SystemGPUTier", (sid, gpu.get("tier"))),
        ("SystemVRAM", (sid, gpu.get("vram_gb"))),
        ("SystemRAM", (sid, ram.get("capacity_gb"))),
        ("SystemDriveType", (sid, storage.get("drive_type"))),
        ("SystemDX", (sid, gpu.get("directx_version"))),
    }
    for game_id in GAMES:
        for profile in ("Min", "Rec"):
            req = game_profile(game_id, profile)
            facts.update({
                ("GameReqCPUTier", (game_id, profile, req["required_cpu_tier"])),
                ("GameReqGPUTier", (game_id, profile, req["required_gpu_tier"])),
                ("GameReqRAM", (game_id, profile, req["required_ram_gb"])),
                ("GameReqVRAM", (game_id, profile, req["required_vram_gb"])),
                ("GameReqStorage", (game_id, profile, req["required_storage"])),
                ("GameReqMedium", (game_id, profile, req["storage_type"])),
                ("GameReqDX", (game_id, profile, req["directx_version"])),
            })
    return facts


def _match_body(body: tuple, facts: set[Fact], theta: dict | None = None):
    theta = {} if theta is None else theta
    if not body:
        yield theta
        return
    first, rest = body[0], body[1:]
    if isinstance(first, Predicate):
        for fact in list(facts):
            new_theta = unify_predicate_with_fact(first, fact, theta)
            if new_theta is not None:
                yield from _match_body(rest, facts, new_theta)
    elif isinstance(first, ComparisonGuard):
        passed, _ = evaluate_guard(first, theta)
        if passed:
            yield from _match_body(rest, facts, theta)


def forward_chain(system) -> ForwardResult:
    facts = system_and_game_facts(system)
    fired: list[FiredRule] = []
    counts = [len(facts)]
    rules = build_rule_base()
    iteration = 0
    changed = True
    while changed:
        changed = False
        iteration += 1
        for rule in rules:
            for theta in _match_body(rule.body, facts):
                fact = predicate_to_fact(rule.head, theta)
                if fact and fact not in facts:
                    facts.add(fact)
                    fired.append(FiredRule(iteration, rule.name, theta_repr(theta), fact))
                    changed = True
        counts.append(len(facts))
    limiting = derive_unplayable(system.instance_id, facts)
    for game_id, missing in limiting.items():
        facts.add(("Unplayable", (system.instance_id, game_id)))
    return ForwardResult(facts, fired, counts, limiting)


MINIMUM_ATOMS = [
    ("CPUMeetsTier", "CPU tier"),
    ("GPUMeetsTier", "GPU tier"),
    ("VRAMMeetsCapacity", "VRAM"),
    ("RAMMeetsCapacity", "RAM"),
    ("StorageMeetsCapacity", "Storage capacity"),
    ("StorageMeetsMedium", "Storage medium"),
    ("DirectXMeetsAPI", "DirectX"),
]


def derive_unplayable(system_id: str, facts: set[Fact]) -> dict[str, list[str]]:
    missing_by_game = {}
    for game_id in GAMES:
        if ("PlayableMinimum", (system_id, game_id)) in facts:
            continue
        missing = [label for predicate, label in MINIMUM_ATOMS if (predicate, (system_id, game_id, "Min")) not in facts]
        missing_by_game[game_id] = missing
    return missing_by_game


def recommended_limiters(system_id: str, game_id: str, facts: set[Fact]) -> list[str]:
    if ("PlayableRecommended", (system_id, game_id)) in facts:
        return []
    return [label for predicate, label in MINIMUM_ATOMS if (predicate, (system_id, game_id, "Rec")) not in facts]
