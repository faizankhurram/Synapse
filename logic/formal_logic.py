"""Programmatic FOL and Description Logic report objects and checks."""

from dataclasses import dataclass


FOL_FORMULAS = [
    {
        "name": "Socket Constraint Invariant",
        "formula": "forall s,c,m: SystemCPU(s,c) and SystemMobo(s,m) -> (SocketCompatible(s) iff CPUSocket(c)=MoboSocket(m))",
    },
    {
        "name": "DirectX API Capability Constraint",
        "formula": "forall s,g,p: DirectXMeetsAPI(s,g,p) <- SystemDX(s,d1) and GameReqDX(g,p,d2) and d1 >= d2",
    },
    {
        "name": "Architectural Bottleneck Inference",
        "formula": "forall s: Bottleneck(s,Severe_CPU_Bound) <- SystemGPUTier(s,g) and SystemCPUTier(s,c) and g-c >= 3",
    },
]

DL_AXIOMS = [
    "ModernDirectX12GPU equivalent GPU and exists supportsAPI.DirectX12",
    "BalancedGamingRig equivalent SystemConfiguration and hasBalance.Well_Balanced",
    "PlayableMinimum and Unplayable subclass Bottom",
    "SevereCPUBound and SevereGPUBound subclass Bottom",
]


@dataclass
class DLConsistencyResult:
    consistent: bool
    violations: list[str]


def validate_dl_disjointness(facts: set) -> DLConsistencyResult:
    violations = []
    playable_pairs = {(args[0], args[1]) for pred, args in facts if pred == "PlayableMinimum"}
    unplayable_pairs = {(args[0], args[1]) for pred, args in facts if pred == "Unplayable"}
    for pair in sorted(playable_pairs & unplayable_pairs):
        violations.append(f"PlayableMinimum{pair} conflicts with Unplayable{pair}")
    severe_cpu = {args[0] for pred, args in facts if pred == "Bottleneck" and args[1] == "Severe_CPU_Bound"}
    severe_gpu = {args[0] for pred, args in facts if pred == "Bottleneck" and args[1] == "Severe_GPU_Bound"}
    for system_id in sorted(severe_cpu & severe_gpu):
        violations.append(f"{system_id} is both SevereCPUBound and SevereGPUBound")
    return DLConsistencyResult(not violations, violations)
