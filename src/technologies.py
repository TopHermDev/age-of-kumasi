"""Technology tree — researchable upgrades for the Age of Kumasi."""

from dataclasses import dataclass, field


@dataclass
class TechTemplate:
    name: str
    age_required: int  # 1-4
    cost: dict  # {"gold": 100, "food": 50}
    research_time: int  # turns to research
    effects: dict  # {"gold_income_mult": 0.15, "vision": 1}
    prerequisites: list[str] = field(default_factory=list)
    description: str = ""


TECHS = {
    # === AGE I — Settlement Era ===
    "irrigation": TechTemplate(
        name="Irrigation",
        age_required=1,
        cost={"wood": 50, "food": 30},
        research_time=2,
        effects={"food_income_mult": 0.15},
        description="Channel river water to farm fields. +15% food income.",
    ),

    # === AGE II — Gold Era ===
    "gold_weighting": TechTemplate(
        name="Gold Weighting",
        age_required=2,
        cost={"gold": 80, "food": 30},
        research_time=3,
        effects={"gold_income_mult": 0.15},
        description="Master the gold weight system for precise trade. +15% gold income.",
    ),
    "drum_communication": TechTemplate(
        name="Drum Communication",
        age_required=2,
        cost={"wood": 60, "gold": 40},
        research_time=2,
        effects={"vision": 1, "unit_speed_mult": 0.10},
        description="Long-range drum signals reveal more of the map. +1 vision, +10% speed.",
    ),
    "kola_trade_routes": TechTemplate(
        name="Kola Trade Routes",
        age_required=2,
        cost={"food": 50, "gold": 60},
        research_time=2,
        effects={"kola_income_mult": 0.25},
        description="Establish profitable kola nut trade routes. +25% kola income.",
    ),
    "iron_smelting": TechTemplate(
        name="Iron Smelting",
        age_required=2,
        cost={"gold": 70, "food": 40},
        research_time=3,
        effects={"melee_attack_mult": 0.10},
        description="Forge harder blades. +10% melee attack damage.",
    ),

    # === AGE III — Age of the Stool ===
    "golden_stool_unity": TechTemplate(
        name="Golden Stool Unity",
        age_required=3,
        cost={"gold": 150, "food": 80},
        research_time=3,
        effects={"unit_hp_mult": 0.10},
        prerequisites=["drum_communication"],
        description="The sacred Golden Stool inspires all warriors. +10% unit HP.",
    ),
    "gunpowder_trading": TechTemplate(
        name="Gunpowder Trading",
        age_required=3,
        cost={"gold": 200, "kola": 30},
        research_time=3,
        effects={"ranged_attack_mult": 0.20},
        prerequisites=["gold_weighting"],
        description="Acquire firearms through coastal trade. +20% ranged attack damage.",
    ),
    "fortification": TechTemplate(
        name="Fortification",
        age_required=3,
        cost={"wood": 100, "gold": 80, "kola": 20},
        research_time=2,
        effects={"building_hp_mult": 0.20},
        description="Reinforce walls and structures. +20% building HP.",
    ),
    "palm_wine_tactics": TechTemplate(
        name="Palm Wine Tactics",
        age_required=3,
        cost={"food": 60, "gold": 50},
        research_time=2,
        effects={"training_time_mult": -0.15},
        description="Boost worker morale with palm wine. -15% training time.",
    ),

    # === AGE IV — Age of Resistance ===
    "independence_resolve": TechTemplate(
        name="Independence Resolve",
        age_required=4,
        cost={"gold": 250, "food": 150, "kola": 50},
        research_time=4,
        effects={"unit_hp_mult": 0.15, "melee_attack_mult": 0.10},
        prerequisites=["golden_stool_unity"],
        description="The spirit of self-determination empowers all units. +15% HP, +10% melee attack.",
    ),
    "asante_confederacy": TechTemplate(
        name="Asante Confederacy",
        age_required=4,
        cost={"gold": 200, "kola": 80},
        research_time=3,
        effects={"building_hp_mult": 0.25, "gold_income_mult": 0.20},
        description="Unite allied states under one banner. +25% building HP, +20% gold income.",
    ),
    "guerrilla_warfare": TechTemplate(
        name="Guerrilla Warfare",
        age_required=4,
        cost={"food": 100, "gold": 120},
        research_time=3,
        effects={"unit_speed_mult": 0.20, "unit_hp_mult": 0.10},
        prerequisites=["palm_wine_tactics"],
        description="Fight from the forest. +20% speed, +10% HP for all units.",
    ),
    "master_weaver": TechTemplate(
        name="Master Weaver",
        age_required=4,
        cost={"wood": 150, "gold": 100},
        research_time=2,
        effects={"building_cost_mult": -0.15},
        description="Efficient building techniques from master artisans. -15% building costs.",
    ),
    "river_navigation": TechTemplate(
        name="River Navigation",
        age_required=4,
        cost={"wood": 120, "food": 80},
        research_time=3,
        effects={"naval_attack_mult": 0.25, "naval_hp_mult": 0.20},
        description="Master the rivers for swift naval assault. +25% naval attack, +20% naval HP.",
    ),
    "kente_diplomacy": TechTemplate(
        name="Kente Diplomacy",
        age_required=4,
        cost={"gold": 180, "kola": 60},
        research_time=2,
        effects={"kola_income_mult": 0.30, "food_income_mult": 0.20},
        description="Trade kente cloth across empires. +30% kola, +20% food income.",
    ),
}


def get_tech(name: str) -> TechTemplate:
    """Get a tech template by name (fuzzy match)."""
    key = name.lower().strip().replace(" ", "_")
    if key in TECHS:
        return TECHS[key]
    for tech_key, tech in TECHS.items():
        if key in tech_key or tech_key in key:
            return tech
    available = ", ".join(TECHS.keys())
    raise ValueError(f"Unknown technology: '{name}'. Available: {available}")


def techs_available_at_age(age: int) -> list[str]:
    """Return list of tech names available at a given age."""
    return [name for name, tech in TECHS.items() if tech.age_required <= age]


def format_tech_list(age: int) -> str:
    """Format available technologies as a readable string."""
    lines = []
    for name, tech in TECHS.items():
        if tech.age_required <= age:
            cost_str = ", ".join(f"{v} {k}" for k, v in tech.cost.items() if v > 0)
            prereqs = ", ".join(tech.prerequisites) if tech.prerequisites else "none"
            lines.append(
                f"  {tech.name:<26} Cost: {cost_str:<24} "
                f"Time: {tech.research_time} turns  Prereqs: {prereqs}"
            )
            lines.append(f"    {tech.description}")
    return "\n".join(lines) if lines else "  No technologies available at this age."
