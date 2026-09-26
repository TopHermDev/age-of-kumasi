"""Building definitions — structures players can construct."""

from dataclasses import dataclass, field


@dataclass
class BuildingTemplate:
    name: str
    age_required: int
    hp: int
    cost: dict  # {"wood": 100, "gold": 0}
    build_time: int  # turns
    description: str = ""
    produces: list[str] = field(default_factory=list)  # unit names this building can train
    techs: list[str] = field(default_factory=list)  # technologies available here
    special: str = ""


BUILDINGS = {
    "town_center": BuildingTemplate(
        name="Town Center",
        age_required=1,
        hp=2400,
        cost={},  # Starting building — free
        build_time=0,
        description="The heart of your settlement. Trains villagers and serves as a resource drop-off.",
        produces=["villager"],
    ),
    "barracks": BuildingTemplate(
        name="Barracks",
        age_required=1,
        hp=1200,
        cost={"wood": 175},
        build_time=3,
        description="Trains infantry units. The foundation of your army.",
        produces=["club_warrior", "spearman", "asafo_company"],
    ),
    "archery_range": BuildingTemplate(
        name="Archery Range",
        age_required=2,
        hp=900,
        cost={"wood": 175},
        build_time=3,
        description="Trains ranged units. Archers and gunmen hone their craft here.",
        produces=["archer", "musketman"],
    ),
    "stable": BuildingTemplate(
        name="Stable",
        age_required=2,
        hp=1000,
        cost={"wood": 175},
        build_time=3,
        description="Trains cavalry. Horses are housed and warriors mounted.",
        produces=["cavalry_rider"],
    ),
    "gold_mine": BuildingTemplate(
        name="Gold Mine",
        age_required=1,
        hp=600,
        cost={"wood": 100},
        build_time=2,
        description="Extracts gold from the earth. The Gold Coast's namesake.",
        special="gold_income",
    ),
    "kola_grove": BuildingTemplate(
        name="Kola Grove",
        age_required=2,
        hp=400,
        cost={"wood": 120},
        build_time=2,
        description="Harvests kola nuts from the forest. Traded across the Sahara.",
        special="kola_income",
    ),
    "farm": BuildingTemplate(
        name="Farm",
        age_required=1,
        hp=200,
        cost={"wood": 60},
        build_time=1,
        description="Grows yam, plantain, and cocoyam. Feeds your people.",
        special="food_income",
    ),
    "fishing_village": BuildingTemplate(
        name="Fishing Village",
        age_required=1,
        hp=300,
        cost={"wood": 100},
        build_time=2,
        description="Harvests food from coastal waters. Must be built on coast.",
        special="fishing_income",
    ),
    "shrine": BuildingTemplate(
        name="Shrine",
        age_required=1,
        hp=500,
        cost={"wood": 120},
        build_time=2,
        description="Heals nearby units and provides morale. A place of spiritual power.",
        special="healing",
    ),
    "wall": BuildingTemplate(
        name="Palisade Wall",
        age_required=2,
        hp=800,
        cost={"wood": 50},
        build_time=1,
        description="Wooden defensive perimeter. Cheap but effective.",
        special="defensive",
    ),
    "stone_wall": BuildingTemplate(
        name="Stone Wall",
        age_required=3,
        hp=1800,
        cost={"wood": 100, "kola": 25},
        build_time=2,
        description="Fortified stone wall. Much stronger than palisade.",
        special="defensive",
    ),
    "market": BuildingTemplate(
        name="Market",
        age_required=2,
        hp=600,
        cost={"wood": 150},
        build_time=2,
        description="Trade resources with other civilizations. Generates passive income.",
        special="trade",
    ),
    "library": BuildingTemplate(
        name="Library of Knowledge",
        age_required=2,
        hp=700,
        cost={"wood": 200, "gold": 100},
        build_time=3,
        description="Researches technologies that advance your civilization.",
        special="research",
    ),
    "palace": BuildingTemplate(
        name="Palace",
        age_required=3,
        hp=4800,
        cost={"wood": 650, "gold": 400, "kola": 100},
        build_time=5,
        description="The seat of power. Trains unique units and unlocks unique technologies.",
        produces=["unique"],
        special="unique_units",
    ),
}


def get_building(name: str) -> BuildingTemplate:
    """Get a building template by name (fuzzy match)."""
    key = name.lower().strip().replace(" ", "_")
    if key in BUILDINGS:
        return BUILDINGS[key]
    for bld_key, bld in BUILDINGS.items():
        if key in bld_key or bld_key in key:
            return bld
    available = ", ".join(BUILDINGS.keys())
    raise ValueError(f"Unknown building: '{name}'. Available: {available}")


def buildings_available_at_age(age: int) -> list[str]:
    """Return list of building names available at a given age."""
    return [name for name, bld in BUILDINGS.items() if bld.age_required <= age]


def format_building_list(age: int) -> str:
    """Format available buildings as a readable string."""
    lines = []
    for name, bld in BUILDINGS.items():
        if bld.age_required <= age:
            if not bld.cost:
                cost_str = "FREE"
            else:
                cost_str = ", ".join(f"{v} {k}" for k, v in bld.cost.items() if v > 0)
            lines.append(
                f"  {bld.name:<24} HP:{bld.hp:<6} "
                f"Cost: {cost_str:<20} Time: {bld.build_time} turns"
            )
    return "\n".join(lines)
