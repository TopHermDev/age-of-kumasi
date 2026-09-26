"""Game state — player resources, units, buildings, age progression."""

from dataclasses import dataclass, field
from .civilizations import Civilization, get_civ
from .units import UNITS, UnitTemplate
from .buildings import BUILDINGS, BuildingTemplate
from .technologies import TECHS, TechTemplate, get_tech


AGES = {
    1: "Age of Settlement",
    2: "Age of Gold",
    3: "Age of the Stool",
    4: "Age of Resistance",
}

AGE_COSTS = {
    2: {"food": 500, "gold": 200},
    3: {"food": 800, "gold": 400, "kola": 50},
    4: {"food": 1200, "gold": 800, "kola": 150},
}


@dataclass
class Unit:
    template: UnitTemplate
    hp: int = 0
    x: int = 0
    y: int = 0
    owner: str = "player"
    moves_remaining: int = 0  # movement points left this turn

    def __post_init__(self):
        if self.hp == 0:
            self.hp = self.template.hp
        if self.moves_remaining == 0:
            self.moves_remaining = max(1, int(self.template.speed))

    @property
    def name(self):
        return self.template.name

    @property
    def alive(self):
        return self.hp > 0

    def reset_moves(self):
        """Reset movement points at start of turn."""
        self.moves_remaining = max(1, int(self.template.speed))


@dataclass
class BuildingInstance:
    template: BuildingTemplate
    hp: int = 0
    x: int = 0
    y: int = 0
    owner: str = "player"
    turns_remaining: int = 0  # 0 = complete

    def __post_init__(self):
        if self.hp == 0:
            self.hp = self.template.hp
        if self.turns_remaining == 0 and self.template.build_time > 0:
            self.turns_remaining = self.template.build_time

    @property
    def name(self):
        return self.template.name

    @property
    def complete(self):
        return self.turns_remaining <= 0


@dataclass
class TrainOrder:
    """A unit currently being trained."""
    template: UnitTemplate
    turns_remaining: int
    owner: str = "player"


@dataclass
class BuildOrder:
    """A building currently under construction."""
    template: BuildingTemplate
    x: int
    y: int
    turns_remaining: int
    owner: str = "player"


@dataclass
class TechResearchOrder:
    """A technology currently being researched."""
    template: TechTemplate
    turns_remaining: int
    owner: str = "player"


@dataclass
class Resources:
    food: int = 200
    wood: int = 200
    gold: int = 100
    kola: int = 0

    def can_afford(self, cost: dict) -> bool:
        for resource, amount in cost.items():
            if getattr(self, resource, 0) < amount:
                return False
        return True

    def spend(self, cost: dict) -> bool:
        """Spend resources. Returns False if can't afford."""
        if not self.can_afford(cost):
            return False
        for resource, amount in cost.items():
            setattr(self, resource, getattr(self, resource) - amount)
        return True

    def earn(self, income: dict):
        for resource, amount in income.items():
            setattr(self, resource, getattr(self, resource) + amount)

    def format(self) -> str:
        return (
            f"Food: {self.food}  Wood: {self.wood}  "
            f"Gold: {self.gold}  Kola: {self.kola}"
        )


@dataclass
class PlayerState:
    name: str
    civ: Civilization
    age: int = 1
    resources: Resources = field(default_factory=Resources)
    units: list[Unit] = field(default_factory=list)
    buildings: list[BuildingInstance] = field(default_factory=list)
    train_queue: list[TrainOrder] = field(default_factory=list)
    build_queue: list[BuildOrder] = field(default_factory=list)
    population: int = 0
    max_population: int = 0
    combat_log: list[str] = field(default_factory=list)
    last_battle: str = ""
    researched_techs: set = field(default_factory=set)
    research_queue: list = field(default_factory=list)
    spawn_x: int = 10
    spawn_y: int = 10

    def __post_init__(self):
        # Start with a Town Center and some villagers at spawn position
        if not self.buildings:
            tc = BuildingInstance(
                template=BUILDINGS["town_center"],
                x=self.spawn_x, y=self.spawn_y,
                owner=self.name,
                turns_remaining=0,
            )
            self.buildings.append(tc)
        if not self.units:
            for i in range(3):
                v = Unit(
                    template=UNITS["villager"],
                    x=self.spawn_x, y=self.spawn_y,
                    owner=self.name,
                )
                self.units.append(v)
        self._update_pop()

    def get_alive_units(self) -> list[Unit]:
        return [u for u in self.units if u.alive]

    def get_alive_buildings(self) -> list[BuildingInstance]:
        return [b for b in self.buildings if b.complete]

    def get_nearest_friendly_building(self, x: int, y: int) -> BuildingInstance | None:
        """Find the nearest complete friendly building to a position."""
        alive = self.get_alive_buildings()
        if not alive:
            return None
        return min(alive, key=lambda b: abs(b.x - x) + abs(b.y - y))

    def _update_pop(self):
        alive_units = [u for u in self.units if u.alive]
        self.population = len(alive_units)
        houses = sum(
            1 for b in self.buildings
            if b.complete and b.template.name == "Farm"
        )
        self.max_population = 5 + houses * 2

    def age_name(self) -> str:
        return AGES.get(self.age, "Unknown")

    def can_advance_age(self) -> tuple[bool, str]:
        next_age = self.age + 1
        if next_age > 4:
            return False, "You are already at the maximum age."
        cost = AGE_COSTS[next_age]
        if not self.resources.can_afford(cost):
            needed = []
            for res, amt in cost.items():
                current = getattr(self.resources, res, 0)
                if current < amt:
                    needed.append(f"{res}: need {amt - current} more")
            return False, f"Insufficient resources: {', '.join(needed)}"
        if next_age >= 3:
            has_palace = any(
                b.template.name == "Palace" and b.complete
                for b in self.buildings
            )
            if not has_palace:
                return False, "You must build a Palace before advancing to Age III."
        return True, "Ready to advance."

    def advance_age(self) -> str:
        ok, msg = self.can_advance_age()
        if not ok:
            return msg
        next_age = self.age + 1
        cost = AGE_COSTS[next_age]
        advance_cost_multiplier = self.civ.bonus_effect.get("age_advance", 1.0)
        adjusted_cost = {k: int(v * advance_cost_multiplier) for k, v in cost.items()}
        self.resources.spend(adjusted_cost)
        self.age = next_age
        return (
            f"Your civilization advances to the {AGES[next_age]}!\n"
            f"The drums beat across the land. Your people celebrate."
        )

    def get_training_cost(self, unit_name: str) -> tuple[dict | None, str]:
        """Get adjusted training cost for a unit."""
        template = UNITS.get(unit_name)
        if not template:
            return None, f"Unknown unit: {unit_name}"
        if template.age_required > self.age:
            return None, f"{template.name} requires {AGES[template.age_required]}."
        if self.population >= self.max_population:
            return None, "Population limit reached. Build more farms or houses."
        cost = dict(template.cost)
        return cost, "OK"

    def train_unit(self, unit_name: str, count: int = 1) -> str:
        """Queue units for training."""
        template = UNITS.get(unit_name)
        if not template:
            return f"Unknown unit: {unit_name}"
        if template.age_required > self.age:
            return f"{template.name} requires {AGES[template.age_required]}."
        if self.population + count > self.max_population:
            return f"Not enough population space. Have {self.max_population - self.population} slots."

        total_cost = {}
        for res, amt in template.cost.items():
            total_cost[res] = amt * count

        if not self.resources.can_afford(total_cost):
            needed = []
            for res, amt in total_cost.items():
                current = getattr(self.resources, res, 0)
                if current < amt:
                    needed.append(f"{res}: need {amt - current} more")
            return f"Insufficient resources: {', '.join(needed)}"

        self.resources.spend(total_cost)
        for _ in range(count):
            self.train_queue.append(TrainOrder(
                template=template,
                turns_remaining=template.train_time,
                owner=self.name,
            ))

        cost_str = ", ".join(f"{v} {k}" for k, v in total_cost.items() if v > 0)
        return f"Training {count}x {template.name}. Cost: {cost_str}. ETA: {template.train_time} turns."

    def build_structure(self, building_name: str, x: int = 10, y: int = 10) -> str:
        """Queue a building for construction."""
        template = BUILDINGS.get(building_name)
        if not template:
            return f"Unknown building: {building_name}"
        if template.age_required > self.age:
            return f"{template.name} requires {AGES[template.age_required]}."
        cost = dict(template.cost)
        if "wood" in cost and self.civ.bonus_effect.get("building_wood_cost"):
            cost["wood"] = int(cost["wood"] * self.civ.bonus_effect["building_wood_cost"])

        if not self.resources.can_afford(cost):
            needed = []
            for res, amt in cost.items():
                current = getattr(self.resources, res, 0)
                if current < amt:
                    needed.append(f"{res}: need {amt - current} more")
            return f"Insufficient resources: {', '.join(needed)}"

        self.resources.spend(cost)
        self.build_queue.append(BuildOrder(
            template=template,
            x=x, y=y,
            turns_remaining=template.build_time,
            owner=self.name,
        ))

        cost_str = ", ".join(f"{v} {k}" for k, v in cost.items() if v > 0)
        return f"Building {template.name}. Cost: {cost_str}. ETA: {template.build_time} turns."

    # === Technology methods ===

    def get_tech_multiplier(self, effect_key: str) -> float:
        """Get the cumulative multiplier for a tech effect key (additive stacking)."""
        total = 0.0
        for tech_name in self.researched_techs:
            if tech_name in TECHS:
                total += TECHS[tech_name].effects.get(effect_key, 0.0)
        return 1.0 + total

    def get_tech_multipliers(self) -> dict:
        """Get all tech multipliers as a dict for combat/other systems."""
        return {
            "melee_attack_mult": self.get_tech_multiplier("melee_attack_mult"),
            "ranged_attack_mult": self.get_tech_multiplier("ranged_attack_mult"),
            "naval_attack_mult": self.get_tech_multiplier("naval_attack_mult"),
            "unit_hp_mult": self.get_tech_multiplier("unit_hp_mult"),
            "unit_speed_mult": self.get_tech_multiplier("unit_speed_mult"),
            "building_hp_mult": self.get_tech_multiplier("building_hp_mult"),
            "gold_income_mult": self.get_tech_multiplier("gold_income_mult"),
            "food_income_mult": self.get_tech_multiplier("food_income_mult"),
            "kola_income_mult": self.get_tech_multiplier("kola_income_mult"),
        }

    def start_research(self, tech_name: str) -> str:
        """Start researching a technology. Requires a Library building."""
        template = get_tech(tech_name)
        if template.age_required > self.age:
            return f"{template.name} requires {AGES[template.age_required]}."
        if template.name in self.researched_techs:
            return f"You have already researched {template.name}."
        for prereq in template.prerequisites:
            if prereq not in self.researched_techs:
                prereq_tech = TECHS.get(prereq)
                pname = prereq_tech.name if prereq_tech else prereq
                return f"{template.name} requires '{pname}' first."
        has_library = any(
            b.template.special == "research" and b.complete
            for b in self.buildings
        )
        if not has_library:
            return "You must build a Library before researching technologies."
        for order in self.research_queue:
            if order.template.name == template.name:
                return f"{template.name} is already being researched."
        if not self.resources.can_afford(template.cost):
            needed = []
            for res, amt in template.cost.items():
                current = getattr(self.resources, res, 0)
                if current < amt:
                    needed.append(f"{res}: need {amt - current} more")
            return f"Insufficient resources: {', '.join(needed)}"
        self.resources.spend(template.cost)
        self.research_queue.append(TechResearchOrder(
            template=template,
            turns_remaining=template.research_time,
            owner=self.name,
        ))
        cost_str = ", ".join(f"{v} {k}" for k, v in template.cost.items() if v > 0)
        return f"Researching {template.name}. Cost: {cost_str}. ETA: {template.research_time} turns."

    # === Turn processing ===

    def process_turn(self) -> list[str]:
        """Process one turn: complete training, construction, research, income, reset movement."""
        events = []

        # Reset unit movement
        for u in self.units:
            if u.alive:
                u.reset_moves()

        # Process train queue
        completed_units = []
        remaining_train = []
        for order in self.train_queue:
            order.turns_remaining -= 1
            if order.turns_remaining <= 0:
                unit = Unit(
                    template=order.template,
                    x=self.spawn_x, y=self.spawn_y,
                    owner=order.owner,
                )
                self.units.append(unit)
                completed_units.append(order.template.name)
            else:
                remaining_train.append(order)
        self.train_queue = remaining_train

        # Process build queue
        completed_buildings = []
        remaining_build = []
        for order in self.build_queue:
            order.turns_remaining -= 1
            if order.turns_remaining <= 0:
                bld = BuildingInstance(
                    template=order.template,
                    x=order.x, y=order.y,
                    owner=order.owner,
                    turns_remaining=0,
                )
                self.buildings.append(bld)
                completed_buildings.append(order.template.name)
            else:
                remaining_build.append(order)
        self.build_queue = remaining_build

        # Process research queue
        completed_techs = []
        remaining_research = []
        for order in self.research_queue:
            order.turns_remaining -= 1
            if order.turns_remaining <= 0:
                self.researched_techs.add(order.template.name)
                completed_techs.append(order.template.name)
            else:
                remaining_research.append(order)
        self.research_queue = remaining_research

        # Generate income from buildings
        income = {"food": 0, "wood": 0, "gold": 0, "kola": 0}
        for bld in self.buildings:
            if not bld.complete:
                continue
            if bld.template.special == "gold_income":
                gold_rate = int(20 * self.civ.bonus_effect.get("gold_mining", 1.0))
                income["gold"] += gold_rate
            elif bld.template.special == "food_income":
                income["food"] += 15
            elif bld.template.special == "fishing_income":
                fish_rate = int(18 * self.civ.bonus_effect.get("fishing", 1.0))
                income["food"] += fish_rate
            elif bld.template.special == "kola_income":
                income["kola"] += 10
            elif bld.template.special == "trade":
                income["gold"] += 8

        # Apply tech income multipliers
        gold_mult = self.get_tech_multiplier("gold_income_mult")
        food_mult = self.get_tech_multiplier("food_income_mult")
        kola_mult = self.get_tech_multiplier("kola_income_mult")
        income["gold"] = int(income["gold"] * gold_mult)
        income["food"] = int(income["food"] * food_mult)
        income["kola"] = int(income["kola"] * kola_mult)

        self.resources.earn(income)

        # Update population
        self._update_pop()

        # Build event messages
        for name in completed_units:
            events.append(f"A {name} has joined your forces.")
        for name in completed_buildings:
            events.append(f"Construction of {name} is complete.")
        for name in completed_techs:
            events.append(f"Research complete: {name}!")
        if any(v > 0 for v in income.values()):
            income_str = ", ".join(f"+{v} {k}" for k, v in income.items() if v > 0)
            events.append(f"Income: {income_str}")

        return events

    def status_report(self) -> str:
        """Full status report."""
        alive_units = [u for u in self.units if u.alive]
        lines = [
            f"{'═' * 50}",
            f"  {self.civ.name} Empire — {self.age_name()}",
            f"  Population: {self.population}/{self.max_population}",
            f"  {self.resources.format()}",
            f"{'═' * 50}",
        ]

        # Unit counts
        unit_counts = {}
        for u in alive_units:
            unit_counts[u.name] = unit_counts.get(u.name, 0) + 1
        if unit_counts:
            lines.append("  Military:")
            for name, count in unit_counts.items():
                lines.append(f"    {name}: {count}")

        # Buildings
        complete_buildings = [b for b in self.buildings if b.complete]
        if complete_buildings:
            bld_counts = {}
            for b in complete_buildings:
                bld_counts[b.name] = bld_counts.get(b.name, 0) + 1
            lines.append("  Buildings:")
            for name, count in bld_counts.items():
                lines.append(f"    {name}: {count}")

        # Queues
        if self.train_queue:
            lines.append("  Training:")
            for order in self.train_queue:
                lines.append(f"    {order.template.name}: {order.turns_remaining} turns")

        if self.build_queue:
            lines.append("  Construction:")
            for order in self.build_queue:
                lines.append(f"    {order.template.name}: {order.turns_remaining} turns")

        if self.research_queue:
            lines.append("  Research:")
            for order in self.research_queue:
                lines.append(f"    {order.template.name}: {order.turns_remaining} turns")

        if self.researched_techs:
            lines.append("  Technologies:")
            for tech_name in sorted(self.researched_techs):
                lines.append(f"    ✓ {tech_name}")

        # Combat results
        if self.last_battle:
            # Strip trailing border to avoid double-border
            battle = self.last_battle.rstrip('═').rstrip()
            lines.append(f"\n  {battle}")

        lines.append(f"{'═' * 50}")
        return "\n".join(lines)
