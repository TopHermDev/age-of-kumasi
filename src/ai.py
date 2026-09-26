"""AI opponent — rule-based opponent with personality archetypes."""

import random
from .game import PlayerState, Resources, Unit, BUILDINGS, UNITS, AGES


class AIPersonality:
    AGGRESSIVE = "aggressive"
    DEFENSIVE = "defensive"
    TRADER = "trader"
    DIPLOMAT = "diplomat"


class AIPlayer:
    """Simple rule-based AI opponent."""

    def __init__(self, name: str, civ_name: str, personality: str = ""):
        from .civilizations import get_civ
        self.personality = personality or random.choice([
            AIPersonality.AGGRESSIVE,
            AIPersonality.DEFENSIVE,
            AIPersonality.TRADER,
        ])
        self.state = PlayerState(
            name=name,
            civ=get_civ(civ_name),
            resources=Resources(food=200, wood=200, gold=100, kola=0),
        )

    def take_turn(self) -> list[str]:
        """AI takes a turn — returns events/actions taken."""
        events = []
        state = self.state

        # Priority-based decision making
        actions_taken = 0
        max_actions = 3  # AI gets 3 actions per turn

        # 1. Always train villagers early
        if state.age == 1 and state.population < 10:
            result = state.train_unit("villager")
            if "Training" in result:
                events.append(f"AI trains a villager.")

        # 2. Build economic buildings
        has_mine = any(b.template.name == "Gold Mine" and b.complete for b in state.buildings)
        has_farm = any(b.template.name == "Farm" and b.complete for b in state.buildings)

        if not has_mine and actions_taken < max_actions:
            result = state.build_structure("gold_mine")
            if "Building" in result:
                events.append("AI builds a Gold Mine.")
                actions_taken += 1

        if not has_farm and actions_taken < max_actions:
            result = state.build_structure("farm")
            if "Building" in result:
                events.append("AI builds a Farm.")
                actions_taken += 1

        # 3. Age advancement
        can_advance, msg = state.can_advance_age()
        if can_advance and actions_taken < max_actions:
            result = state.advance_age()
            events.append(f"AI advances to {state.age_name()}!")
            actions_taken += 1

        # 4. Military based on personality
        if state.age >= 2 and actions_taken < max_actions:
            if self.personality == AIPersonality.AGGRESSIVE:
                # Train military units
                military_options = ["spearman", "archer"]
                if state.age >= 3:
                    military_options.extend(["cavalry_rider", "musketman"])
                unit = random.choice(military_options)
                result = state.train_unit(unit)
                if "Training" in result:
                    events.append(f"AI trains a {unit}.")
                    actions_taken += 1

            elif self.personality == AIPersonality.DEFENSIVE:
                # Build walls and shrine
                has_wall = any(
                    b.template.name in ("Palisade Wall", "Stone Wall") and b.complete
                    for b in state.buildings
                )
                if not has_wall:
                    result = state.build_structure("wall")
                    if "Building" in result:
                        events.append("AI builds a defensive wall.")
                        actions_taken += 1

            elif self.personality == AIPersonality.TRADER:
                # Build market
                has_market = any(
                    b.template.name == "Market" and b.complete for b in state.buildings
                )
                if not has_market:
                    result = state.build_structure("market")
                    if "Building" in result:
                        events.append("AI builds a Market.")
                        actions_taken += 1

        # 5. Process turn (income, completion)
        turn_events = state.process_turn()
        events.extend(turn_events)

        return events

    def status_short(self) -> str:
        """Brief status for the AI."""
        s = self.state
        return (
            f"  {s.civ.name} ({self.personality}) — {s.age_name()}\n"
            f"  Pop: {s.population}/{s.max_population}  "
            f"F:{s.resources.food} W:{s.resources.wood} "
            f"G:{s.resources.gold} K:{s.resources.kola}"
        )
