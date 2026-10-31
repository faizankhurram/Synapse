"""Stage 0 physical hardware sanity invariants."""

from dataclasses import dataclass

from logic.horn_clause import ComparisonGuard, HornClause, P, V
from engine.unifier import evaluate_guard


@dataclass
class PreCheckResult:
    rule: str
    formula: str
    values: str
    passed: bool
    detail: str


STAGE0_RULES = [
    HornClause("Rule 0.1 SocketCompatible", 0, P("SocketCompatible", V("s")), (
        P("SystemCPU", V("s"), V("cpu")),
        P("CPUSocket", V("cpu"), V("s_cpu")),
        P("SystemMobo", V("s"), V("mobo")),
        P("MoboSocket", V("mobo"), V("s_mobo")),
        ComparisonGuard("Equal", V("s_cpu"), V("s_mobo")),
    )),
    HornClause("Rule 0.2 RAMGenCompatible", 0, P("RAMGenCompatible", V("s")), (
        P("SystemRAMGen", V("s"), V("g_ram")),
        P("SystemMobo", V("s"), V("mobo")),
        P("MoboRAMGen", V("mobo"), V("g_mobo")),
        ComparisonGuard("Equal", V("g_ram"), V("g_mobo")),
    )),
    HornClause("Rule 0.3 PowerSufficient", 0, P("PowerSufficient", V("s")), (
        P("SystemPSUWattage", V("s"), V("w_psu")),
        P("SystemCPUTDP", V("s"), V("t_cpu")),
        P("SystemGPUTDP", V("s"), V("t_gpu")),
        ComparisonGuard("GreaterOrEqual", V("w_psu"), ("mul", ("add", ("add", V("t_cpu"), V("t_gpu")), 100), 1.15)),
    )),
    HornClause("Rule 0.4 StorageValid", 0, P("StorageValid", V("s")), (
        P("SystemStorageFree", V("s"), V("free")),
        ComparisonGuard("GreaterThan", V("free"), 0),
    )),
]


def evaluate_pre_checks(system) -> list[PreCheckResult]:
    sid = system.instance_id
    cpu = system.values["cpu"]
    gpu = system.values["gpu"]
    ram = system.values["ram"]
    mobo = system.values["motherboard"]
    storage = system.values["storage"]
    psu = system.values["psu"]
    cases = [
        (
            STAGE0_RULES[0],
            {"s": sid, "cpu": cpu.instance_id, "s_cpu": cpu.get("socket"), "mobo": mobo.instance_id, "s_mobo": mobo.get("supported_socket")},
        ),
        (
            STAGE0_RULES[1],
            {"s": sid, "g_ram": ram.get("generation"), "mobo": mobo.instance_id, "g_mobo": mobo.get("supported_ram_gen")},
        ),
        (
            STAGE0_RULES[2],
            {"s": sid, "w_psu": psu.get("wattage"), "t_cpu": cpu.get("tdp_watts"), "t_gpu": gpu.get("tdp_watts")},
        ),
        (
            STAGE0_RULES[3],
            {"s": sid, "free": storage.get("free_space_gb")},
        ),
    ]
    results = []
    for rule, theta in cases:
        guard = next(item for item in rule.body if isinstance(item, ComparisonGuard))
        passed, detail = evaluate_guard(guard, theta)
        results.append(PreCheckResult(rule.name, str(rule), ", ".join(f"?{k}={v!r}" for k, v in theta.items()), passed, detail))
    return results
