"""Unit definitions — military and civilian units for all ages."""

from dataclasses import dataclass, field


@dataclass
class UnitTemplate:
    name: str
    age_required: int  # 1-4
    category: str  # infantry, ranged, cavalry, support, naval, siege
    hp: int
    attack: int
    defense: int
    speed: float
    cost: dict  # {"food": 50, "gold": 20, "wood": 0}
    train_time: int  # turns
    description: str = ""
    special: str = ""  # special ability text


# === AGE I — Settlement Era ===
UNITS = {
    "villager": UnitTemplate(
        name="Villager",
        age_required=1,
        category="civilian",
        hp=25,
        attack=3,
        defense=0,
        speed=1.0,
        cost={"food": 50},
        train_time=1,
        description="Gathers resources and builds structures. The backbone of your civilization.",
        special="gather, build",
    ),
    "club_warrior": UnitTemplate(
        name="Club Warrior",
        age_required=1,
        category="infantry",
        hp=40,
        attack=6,
        defense=1,
        speed=1.0,
        cost={"food": 60},
        train_time=1,
        description="Basic melee fighter armed with a wooden club.",
    ),
    "scout": UnitTemplate(
        name="Scout",
        age_required=1,
        category="infantry",
        hp=30,
        attack=3,
        defense=0,
        speed=2.0,
        cost={"food": 40},
        train_time=1,
        description="Fast explorer. Reveals the map and reports enemy movements.",
        special="scout",
    ),

    # === AGE II — Gold Era ===
    "spearman": UnitTemplate(
        name="Spearman",
        age_required=2,
        category="infantry",
        hp=55,
        attack=8,
        defense=3,
        speed=1.0,
        cost={"food": 35, "wood": 25},
        train_time=2,
        description="Armed with a long spear. Effective against cavalry.",
        special="bonus_vs_cavalry",
    ),
    "archer": UnitTemplate(
        name="Archer",
        age_required=2,
        category="ranged",
        hp=35,
        attack=7,
        defense=0,
        speed=1.0,
        cost={"wood": 25, "gold": 45},
        train_time=2,
        description="Ranged attacker with a bow. Strong at distance, weak in melee.",
        special="ranged",
    ),
    "canoe_warrior": UnitTemplate(
        name="Canoe Warrior",
        age_required=2,
        category="naval",
        hp=50,
        attack=6,
        defense=2,
        speed=1.5,
        cost={"wood": 80, "food": 20},
        train_time=2,
        description="Coastal naval fighter. Only builds near water.",
        special="naval",
    ),

    # === AGE III — Age of the Stool ===
    "cavalry_rider": UnitTemplate(
        name="Cavalry Rider",
        age_required=3,
        category="cavalry",
        hp=100,
        attack=12,
        defense=4,
        speed=2.0,
        cost={"food": 80, "gold": 75},
        train_time=3,
        description="Mounted warrior. Fast and devastating in open terrain.",
    ),
    "musketman": UnitTemplate(
        name="Musketman",
        age_required=3,
        category="ranged",
        hp=45,
        attack=16,
        defense=2,
        speed=0.8,
        cost={"gold": 75, "food": 25},
        train_time=3,
        description="Armed with traded firearms. Devastating but slow to reload.",
        special="gunpowder",
    ),
    "asafo_company": UnitTemplate(
        name="Asafo Company",
        age_required=3,
        category="infantry",
        hp=80,
        attack=10,
        defense=5,
        speed=1.0,
        cost={"food": 60, "gold": 40},
        train_time=3,
        description="Elite infantry unit with morale-boosting abilities.",
        special="morale_aura",
    ),

    # === AGE IV — Age of Resistance ===
    "war_drummer": UnitTemplate(
        name="War Drummer",
        age_required=4,
        category="support",
        hp=50,
        attack=4,
        defense=1,
        speed=1.0,
        cost={"food": 30, "gold": 50},
        train_time=2,
        description="Buffs nearby units, debuffs enemies. The heartbeat of the army.",
        special="drum_battle",
    ),
    "siege_ram": UnitTemplate(
        name="Siege Ram",
        age_required=4,
        category="siege",
        hp=150,
        attack=20,
        defense=5,
        speed=0.5,
        cost={"wood": 160, "gold": 75},
        train_time=4,
        description="Destroys fortifications. Slow but relentless.",
        special="siege",
    ),
}


def get_unit(name: str) -> UnitTemplate:
    """Get a unit template by name (fuzzy match)."""
    key = name.lower().strip().replace(" ", "_")
    # Direct match
    if key in UNITS:
        return UNITS[key]
    # Partial match
    for unit_key, unit in UNITS.items():
        if key in unit_key or unit_key in key:
            return unit
    available = ", ".join(UNITS.keys())
    raise ValueError(f"Unknown unit: '{name}'. Available: {available}")


def units_available_at_age(age: int) -> list[str]:
    """Return list of unit names available at a given age."""
    return [name for name, unit in UNITS.items() if unit.age_required <= age]


def format_unit_list(age: int) -> str:
    """Format available units as a readable string."""
    lines = []
    for name, unit in UNITS.items():
        if unit.age_required <= age:
            cost_str = ", ".join(f"{v} {k}" for k, v in unit.cost.items() if v > 0)
            lines.append(
                f"  {unit.name:<20} HP:{unit.hp:<4} ATK:{unit.attack:<4} "
                f"DEF:{unit.defense:<4} SPD:{unit.speed}  Cost: {cost_str}  "
                f"Time: {unit.train_time} turns"
            )
    return "\n".join(lines)
