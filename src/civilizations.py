"""Civilization definitions — each with unique units, bonuses, and history."""

from dataclasses import dataclass, field


@dataclass
class Civilization:
    name: str
    region: str
    description: str
    unique_unit: str
    unique_unit_desc: str
    bonus: str
    bonus_effect: dict  # e.g. {"gold_mining": 1.2}
    team_bonus: str = ""
    team_bonus_effect: dict = field(default_factory=dict)


CIVILIZATIONS = {
    "ashanti": Civilization(
        name="Ashanti",
        region="Kumasi, Gold Coast Interior",
        description=(
            "The great Ashanti Empire, centered at Kumasi, dominated the "
            "Gold Coast from the 17th century. Known for elaborate gold work, "
            "military discipline, and the Golden Stool — the soul of the nation."
        ),
        unique_unit="Odwira Priest",
        unique_unit_desc=(
            "Heals nearby units and boosts morale. The Odwira festival "
            "purifies the nation — in battle, it purifies the spirit."
        ),
        bonus="+20% gold mining efficiency",
        bonus_effect={"gold_mining": 1.2},
        team_bonus="Allied gold trade +10%",
        team_bonus_effect={"gold_trade": 1.1},
    ),
    "dagbon": Civilization(
        name="Dagbon",
        region="Yendi, Northern Ghana",
        description=(
            "The Dagbon Kingdom, one of the oldest in West Africa, "
            "preserved its history through the Lunsi drummers. Their "
            "mud-brick architecture and oral traditions span centuries."
        ),
        unique_unit="Lunsi Drummer",
        unique_unit_desc=(
            "Reveals enemy positions through drum language. "
            "The beat carries news across the savanna."
        ),
        bonus="Buildings cost 15% less wood",
        bonus_effect={"building_wood_cost": 0.85},
        team_bonus="Map visibility +1 tile",
        team_bonus_effect={"vision_range": 1},
    ),
    "ga": Civilization(
        name="Ga",
        region="Accra Plains, Coast",
        description=(
            "The Ga people founded Accra. Their Homowo festival celebrates "
            "overcoming famine — they turn hunger into triumph. Coastal "
            "fishers and traders with deep spiritual traditions."
        ),
        unique_unit="Homowo Dancer",
        unique_unit_desc=(
            "Boosts nearby unit morale and terrifies enemies. "
            "The dance that mocked famine now mocks the enemy."
        ),
        bonus="Fishing efficiency +25%",
        bonus_effect={"fishing": 1.25},
        team_bonus="Coastal buildings +10% HP",
        team_bonus_effect={"coastal_hp": 1.1},
    ),
    "ewe": Civilization(
        name="Ewe",
        region="Volta Region",
        description=(
            "The Ewe people of the Volta Region are known for the complex "
            "Agbadza dance, textile arts, and fierce defense of their "
            "autonomy against Ashanti and colonial expansion."
        ),
        unique_unit="Agbadza Dancer",
        unique_unit_desc=(
            "Area-of-effect attack that confuses enemy formations. "
            "The rhythm disrupts the enemy's will."
        ),
        bonus="All units move 10% faster",
        bonus_effect={"unit_speed": 1.1},
        team_bonus="Textile trade +15%",
        team_bonus_effect={"textile_trade": 1.15},
    ),
    "mamprusi": Civilization(
        name="Mamprusi",
        region="Nalerigu, Northeast",
        description=(
            "The Kingdom of Mamprugu founded Dagbon, Mossi, and other "
            "northern kingdoms. The 'mother' kingdom of the north — "
            "their kings were kingmakers."
        ),
        unique_unit="Gatekeeper",
        unique_unit_desc=(
            "Powerful defensive unit that guards Age advancement. "
            "The gatekeeper decides who passes into the next age."
        ),
        bonus="Advance to next age 15% faster",
        bonus_effect={"age_advance": 0.85},
        team_bonus="Defensive structures +15% HP",
        team_bonus_effect={"defense_hp": 1.15},
    ),
    "fante": Civilization(
        name="Fante",
        region="Cape Coast, Central Coast",
        description=(
            "The Fante Confederacy controlled the central coast. Their Asafo "
            "companies were feared military organizations with elaborate "
            "flags, rituals, and naval prowess."
        ),
        unique_unit="Asafo Captain",
        unique_unit_desc=(
            "Inspires troops and coordinates amphibious landings. "
            "The flag bearer leads from the front."
        ),
        bonus="Naval units +20% attack",
        bonus_effect={"naval_attack": 1.2},
        team_bonus="Trade route income +10%",
        team_bonus_effect={"trade_income": 1.1},
    ),
}


def get_civ(name: str) -> Civilization:
    """Get a civilization by name (case-insensitive)."""
    key = name.lower().strip()
    if key not in CIVILIZATIONS:
        available = ", ".join(CIVILIZATIONS.keys())
        raise ValueError(f"Unknown civilization: '{name}'. Available: {available}")
    return CIVILIZATIONS[key]


def list_civs() -> str:
    """Return a formatted list of all civilizations."""
    lines = []
    for key, civ in CIVILIZATIONS.items():
        lines.append(f"  {civ.name} ({key})")
        lines.append(f"    Region: {civ.region}")
        lines.append(f"    Unique Unit: {civ.unique_unit}")
        lines.append(f"    Bonus: {civ.bonus}")
        lines.append(f"    {civ.description}")
        lines.append("")
    return "\n".join(lines)
