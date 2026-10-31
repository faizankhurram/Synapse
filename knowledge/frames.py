"""Frame system with slots, facets, defaults, and if-needed demons."""

from dataclasses import dataclass, field
from typing import Any, Callable

from .catalog_db import CPUS, GAMES, GPUS, MOTHERBOARDS, game_profile
from .matcher import resolve_catalog_key


class FrameError(ValueError):
    pass


@dataclass
class SlotDefinition:
    name: str
    data_type: type | tuple[type, ...] | None = None
    valid_range: tuple[float, float] | None = None
    enum: set[Any] | None = None
    default_value: Any = None
    if_needed_demon: Callable[["FrameInstance", str], Any] | None = None


@dataclass
class FrameClass:
    name: str
    superclass: "FrameClass | None" = None
    slots: dict[str, SlotDefinition] = field(default_factory=dict)

    def all_slots(self) -> dict[str, SlotDefinition]:
        inherited = self.superclass.all_slots() if self.superclass else {}
        return {**inherited, **self.slots}


@dataclass
class FrameInstance:
    frame_class: FrameClass
    instance_id: str
    values: dict[str, Any]
    resolution_log: list[dict[str, Any]] = field(default_factory=list)

    def get(self, slot_name: str) -> Any:
        slots = self.frame_class.all_slots()
        if slot_name not in slots:
            raise FrameError(f"{self.frame_class.name} has no slot {slot_name}")
        if slot_name not in self.values or self.values[slot_name] is None:
            slot = slots[slot_name]
            if slot.if_needed_demon:
                value = slot.if_needed_demon(self, slot_name)
                if value is not None:
                    self.values[slot_name] = value
                    self.resolution_log.append({"slot": slot_name, "method": ":if-needed", "source": slot.if_needed_demon.__name__, "value": value})
            if (slot_name not in self.values or self.values[slot_name] is None) and slot.default_value is not None:
                self.values[slot_name] = slot.default_value
                self.resolution_log.append({"slot": slot_name, "method": ":default", "source": "slot default", "value": slot.default_value})
        value = self.values.get(slot_name)
        self._validate(slot_name, value)
        return value

    def materialize(self) -> dict[str, Any]:
        return {name: self.get(name) for name in self.frame_class.all_slots()}

    def _validate(self, slot_name: str, value: Any) -> None:
        slot = self.frame_class.all_slots()[slot_name]
        if value is None:
            return
        if slot.data_type and not isinstance(value, slot.data_type):
            raise FrameError(f"{self.instance_id}.{slot_name} expected {slot.data_type}, got {type(value)}")
        if slot.valid_range:
            lo, hi = slot.valid_range
            if not lo <= value <= hi:
                raise FrameError(f"{self.instance_id}.{slot_name}={value} outside [{lo}, {hi}]")
        if slot.enum and value not in slot.enum:
            raise FrameError(f"{self.instance_id}.{slot_name}={value} not in {sorted(slot.enum)}")


def _catalog_lookup(instance: FrameInstance, slot_name: str, catalog: dict[str, dict[str, Any]]) -> Any:
    model = instance.values.get("model_name")
    if not model:
        return None
    if model not in catalog:
        matched = resolve_catalog_key(str(model), catalog)
        if matched is None:
            return None
        instance.values["model_name"] = matched
        instance.resolution_log.append({
            "slot": "model_name",
            "method": ":if-needed",
            "source": "longest_match",
            "value": matched,
        })
        model = matched
    return catalog[model].get(slot_name)


def lookup_cpu_spec(instance: FrameInstance, slot_name: str) -> Any:
    return _catalog_lookup(instance, slot_name, CPUS)


def lookup_gpu_spec(instance: FrameInstance, slot_name: str) -> Any:
    return _catalog_lookup(instance, slot_name, GPUS)


def lookup_mobo_spec(instance: FrameInstance, slot_name: str) -> Any:
    return _catalog_lookup(instance, slot_name, MOTHERBOARDS)


def lookup_cpu_tier(instance: FrameInstance, slot_name: str) -> int:
    catalog_value = lookup_cpu_spec(instance, slot_name)
    if catalog_value is not None:
        return catalog_value
    cores = instance.get("cores") or 2
    clock = instance.get("clock_speed_ghz") or 2.0
    return max(1, min(10, round((cores * clock) / 5)))


def lookup_gpu_tier(instance: FrameInstance, slot_name: str) -> int:
    catalog_value = lookup_gpu_spec(instance, slot_name)
    if catalog_value is not None:
        return catalog_value
    vram = instance.get("vram_gb") or 1
    dx_bonus = 1 if instance.get("directx_version") >= 12 else 0
    return max(1, min(10, round(vram / 2) + dx_bonus))


def compute_total_power(instance: FrameInstance, slot_name: str) -> int:
    cpu = instance.values.get("cpu")
    gpu = instance.values.get("gpu")
    if isinstance(cpu, FrameInstance) and isinstance(gpu, FrameInstance):
        return cpu.get("tdp_watts") + gpu.get("tdp_watts") + 100
    return None


def check_physical_compatibility(instance: FrameInstance, slot_name: str) -> bool:
    cpu = instance.get("cpu")
    gpu = instance.get("gpu")
    ram = instance.get("ram")
    motherboard = instance.get("motherboard")
    psu = instance.get("psu")
    storage = instance.get("storage")
    required_power = int((cpu.get("tdp_watts") + gpu.get("tdp_watts") + 100) * 1.15)
    return (
        cpu.get("socket") == motherboard.get("supported_socket")
        and ram.get("generation") == motherboard.get("supported_ram_gen")
        and psu.get("wattage") >= required_power
        and storage.get("free_space_gb") > 0
    )


Component = FrameClass("Component")
CPU = FrameClass("CPU", Component, {
    "model_name": SlotDefinition("model_name", str),
    "socket": SlotDefinition("socket", str, if_needed_demon=lookup_cpu_spec),
    "cores": SlotDefinition("cores", int, (2, 64), if_needed_demon=lookup_cpu_spec),
    "clock_speed_ghz": SlotDefinition("clock_speed_ghz", float, (1.0, 6.0), if_needed_demon=lookup_cpu_spec),
    "tier": SlotDefinition("tier", int, (1, 10), if_needed_demon=lookup_cpu_tier),
    "tdp_watts": SlotDefinition("tdp_watts", int, (15, 300), default_value=65, if_needed_demon=lookup_cpu_spec),
})
GPU = FrameClass("GPU", Component, {
    "model_name": SlotDefinition("model_name", str),
    "vram_gb": SlotDefinition("vram_gb", int, (1, 32), if_needed_demon=lookup_gpu_spec),
    "directx_version": SlotDefinition("directx_version", int, enum={11, 12}, default_value=12, if_needed_demon=lookup_gpu_spec),
    "tier": SlotDefinition("tier", int, (1, 10), if_needed_demon=lookup_gpu_tier),
    "tdp_watts": SlotDefinition("tdp_watts", int, (30, 500), default_value=150, if_needed_demon=lookup_gpu_spec),
})
RAM = FrameClass("RAM", Component, {
    "capacity_gb": SlotDefinition("capacity_gb", int, (4, 128)),
    "generation": SlotDefinition("generation", str, enum={"DDR3", "DDR4", "DDR5"}, default_value="DDR4"),
})
Motherboard = FrameClass("Motherboard", Component, {
    "model_name": SlotDefinition("model_name", str),
    "supported_socket": SlotDefinition("supported_socket", str, if_needed_demon=lookup_mobo_spec),
    "supported_ram_gen": SlotDefinition("supported_ram_gen", str, enum={"DDR3", "DDR4", "DDR5"}, if_needed_demon=lookup_mobo_spec),
})
Storage = FrameClass("Storage", Component, {
    "drive_type": SlotDefinition("drive_type", str, enum={"HDD", "SSD"}, default_value="SSD"),
    "free_space_gb": SlotDefinition("free_space_gb", (int, float), (0.0, 10000.0)),
})
PowerSupply = FrameClass("PowerSupply", Component, {
    "wattage": SlotDefinition("wattage", int, (200, 1600)),
    "total_system_draw": SlotDefinition("total_system_draw", int, if_needed_demon=compute_total_power),
})
SystemConfiguration = FrameClass("SystemConfiguration", slots={
    "config_id": SlotDefinition("config_id", str),
    "cpu": SlotDefinition("cpu", FrameInstance),
    "gpu": SlotDefinition("gpu", FrameInstance),
    "ram": SlotDefinition("ram", FrameInstance),
    "motherboard": SlotDefinition("motherboard", FrameInstance),
    "storage": SlotDefinition("storage", FrameInstance),
    "psu": SlotDefinition("psu", FrameInstance),
    "physical_valid": SlotDefinition("physical_valid", bool, if_needed_demon=check_physical_compatibility),
})
RequirementProfile = FrameClass("RequirementProfile", slots={
    "profile_type": SlotDefinition("profile_type", str, enum={"Min", "Rec"}),
    "required_cpu_tier": SlotDefinition("required_cpu_tier", int, (1, 10)),
    "required_gpu_tier": SlotDefinition("required_gpu_tier", int, (1, 10)),
    "required_ram_gb": SlotDefinition("required_ram_gb", int),
    "required_vram_gb": SlotDefinition("required_vram_gb", int),
    "required_storage": SlotDefinition("required_storage", (int, float)),
    "storage_type": SlotDefinition("storage_type", str, enum={"HDD", "SSD"}),
    "directx_version": SlotDefinition("directx_version", int, enum={11, 12}),
})
GameTitle = FrameClass("GameTitle", slots={
    "game_id": SlotDefinition("game_id", str),
    "title_name": SlotDefinition("title_name", str),
    "min_profile": SlotDefinition("min_profile", FrameInstance),
    "rec_profile": SlotDefinition("rec_profile", FrameInstance),
})


def instantiate_system(config_id: str, raw: dict[str, dict[str, Any]]) -> FrameInstance:
    cpu = FrameInstance(CPU, f"{config_id}_CPU", dict(raw["cpu"]))
    gpu = FrameInstance(GPU, f"{config_id}_GPU", dict(raw["gpu"]))
    ram = FrameInstance(RAM, f"{config_id}_RAM", dict(raw["ram"]))
    motherboard = FrameInstance(Motherboard, f"{config_id}_Motherboard", dict(raw["motherboard"]))
    storage = FrameInstance(Storage, f"{config_id}_Storage", dict(raw["storage"]))
    psu = FrameInstance(PowerSupply, f"{config_id}_PSU", dict(raw["psu"]))
    psu.values["cpu"] = cpu
    psu.values["gpu"] = gpu
    system = FrameInstance(SystemConfiguration, config_id, {
        "config_id": config_id,
        "cpu": cpu,
        "gpu": gpu,
        "ram": ram,
        "motherboard": motherboard,
        "storage": storage,
        "psu": psu,
    })
    for instance in (cpu, gpu, ram, motherboard, storage, psu, system):
        instance.materialize()
    return system


def instantiate_games() -> dict[str, FrameInstance]:
    games = {}
    for game_id, data in GAMES.items():
        min_profile = FrameInstance(RequirementProfile, f"{game_id}_Min", {"profile_type": "Min", **game_profile(game_id, "Min")})
        rec_profile = FrameInstance(RequirementProfile, f"{game_id}_Rec", {"profile_type": "Rec", **game_profile(game_id, "Rec")})
        games[game_id] = FrameInstance(GameTitle, game_id, {
            "game_id": game_id,
            "title_name": data["title_name"],
            "min_profile": min_profile,
            "rec_profile": rec_profile,
        })
    return games


def collect_resolution_log(system: FrameInstance) -> list[dict[str, Any]]:
    rows = []
    for component_slot in ("cpu", "gpu", "ram", "motherboard", "storage", "psu", "physical_valid"):
        target = system.values.get(component_slot)
        if isinstance(target, FrameInstance):
            for event in target.resolution_log:
                rows.append({"component": component_slot, **event})
        elif component_slot == "physical_valid":
            for event in system.resolution_log:
                rows.append({"component": "system", **event})
    return rows
