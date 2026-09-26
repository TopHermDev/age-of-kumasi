"""Campaign mode — scenario definitions and campaign game loop."""

from dataclasses import dataclass, field
from .game import PlayerState, Resources, Unit, BuildingInstance, AGES
from .ai import AIPlayer
from .units import UNITS
from .buildings import BUILDINGS
from .civilizations import get_civ


@dataclass
class Scenario:
    """A single campaign scenario with narrative and conditions."""
    name: str
    description: str
    player_civ: str
    ai_civ: str
    starting_resources: dict  # {"food": N, "wood": N, "gold": N, "kola": N}
    starting_units: list[dict]  # [{"unit": "villager", "count": 5}]
    starting_buildings: list[dict]  # [{"building": "town_center", "turns_remaining": 0}]
    win_condition: dict  # {"type": "destroy_all_ai"}
    lose_condition: dict  # {"type": "player_lose_all"}
    turn_limit: int
    narrative_events: dict[int, str] = field(default_factory=dict)  # turn -> text


CAMPAIGN_SCENARIOS: list[Scenario] = [
    Scenario(
        name="The Founding of Kumasi",
        description=(
            "c. 1670 — In the heart of the Gold Coast interior, you lead a small "
            "band of settlers seeking a new home. The forests are thick with "
            "danger. You must build a settlement from nothing and defend it "
            "against raiders who would take what you've built.\n\n"
            "OBJECTIVE: Build a thriving settlement and defeat the raiding "
            "party within 30 turns."
        ),
        player_civ="ashanti",
        ai_civ="fante",
        starting_resources={"food": 200, "wood": 300, "gold": 50, "kola": 0},
        starting_units=[
            {"unit": "villager", "count": 5},
        ],
        starting_buildings=[
            {"building": "town_center", "turns_remaining": 0},
        ],
        win_condition={"type": "destroy_all_ai"},
        lose_condition={"type": "player_lose_all"},
        turn_limit=30,
        narrative_events={
            1: (
                "The drums sound at dawn. Your scouts report open savanna to the "
                "north and dense forest to the south. A wise choice of location "
                "could mean the difference between triumph and ruin.\n"
                "Build wisely. The land provides — if you know where to look."
            ),
            5: (
                "Smoke rises on the horizon. Scouts return with word of "
                "neighboring settlements — friendly eyes watch your progress. "
                "But there are also those who would rather see you fail."
            ),
            10: (
                "The first harvest is in. Your people feast on yam and "
                "plantain. The elders speak of a golden stool that will "
                "one day unite all the Ashanti."
            ),
            20: (
                "Raiders have been spotted gathering in the east. "
                "Arm your warriors. The time for battle draws near."
            ),
            28: (
                "Final warning: the enemy masses. All must fight. "
                "The future of your settlement hangs in the balance."
            ),
        },
    ),
    Scenario(
        name="The Rise of the Golden Stool",
        description=(
            "c. 1701 — The Ashanti Empire grows stronger under the Golden Stool, "
            "the sacred symbol of national unity. But two powerful kingdoms "
            "refuse to join the confederacy. You must bring them together — "
            "through diplomacy or conquest — to forge the greatest empire "
            "the Gold Coast has ever known.\n\n"
            "OBJECTIVE: Unite 2 rival civilizations by defeating them, within "
            "50 turns."
        ),
        player_civ="ashanti",
        ai_civ="dagbon",
        starting_resources={"food": 300, "wood": 250, "gold": 150, "kola": 10},
        starting_units=[
            {"unit": "villager", "count": 5},
            {"unit": "club_warrior", "count": 3},
        ],
        starting_buildings=[
            {"building": "town_center", "turns_remaining": 0},
            {"building": "barracks", "turns_remaining": 0},
        ],
        win_condition={"type": "destroy_all_ai"},
        lose_condition={"type": "player_lose_all"},
        turn_limit=50,
        narrative_events={
            1: (
                "The Golden Stool sits before you — a symbol of Ashanti "
                "destiny. The Okomfo Anokye spoke it into being, and with "
                "it comes the mandate to unite all Ashanti people.\n"
                "Two kingdoms stand in your path. The choice is yours: "
                "iron or words."
            ),
            8: (
                "Your first scouts report the enemy has built walls. "
                "Their defensive posture suggests they know your ambitions."
            ),
            15: (
                "The Odwira festival approaches. A time of purification "
                "and renewal. Your warriors seek the blessing of the ancestors "
                "before battle."
            ),
            25: (
                "Half your time has passed. The enemy has grown in strength. "
                "Hesitation will cost you."
            ),
            40: (
                "Ten turns remain. The Golden Stool demands unity. "
                "Every warrior must be ready."
            ),
        },
    ),
    Scenario(
        name="The Anglo-Ashanti Wars",
        description=(
            "1824 — The British Empire sets its sights on the Gold Coast. "
            "Governor Charles MacCarthy leads a coalition force against "
            "the Ashanti heartland. You command a modernized Ashanti army, "
            "armed with muskets and hardened by generations of warfare.\n\n"
            "OBJECTIVE: Defeat the European-allied invasion force within "
            "40 turns."
        ),
        player_civ="ashanti",
        ai_civ="ga",
        starting_resources={"food": 400, "wood": 300, "gold": 300, "kola": 50},
        starting_units=[
            {"unit": "villager", "count": 3},
            {"unit": "musketman", "count": 5},
            {"unit": "archer", "count": 4},
            {"unit": "spearman", "count": 4},
            {"unit": "cavalry_rider", "count": 2},
            {"unit": "asafo_company", "count": 3},
        ],
        starting_buildings=[
            {"building": "town_center", "turns_remaining": 0},
            {"building": "barracks", "turns_remaining": 0},
            {"building": "archery_range", "turns_remaining": 0},
            {"building": "stable", "turns_remaining": 0},
            {"building": "gold_mine", "turns_remaining": 0},
            {"building": "farm", "turns_remaining": 0},
            {"building": "palace", "turns_remaining": 0},
        ],
        win_condition={"type": "destroy_all_ai"},
        lose_condition={"type": "player_lose_all"},
        turn_limit=40,
        narrative_events={
            1: (
                "The drums of war beat across the Gold Coast. Governor "
                "MacCarthy has rallied British soldiers, Dutch mercenaries, "
                "and allied coastal tribes against you.\n"
                "Your army stands ready at Kumasi. The Golden Stool "
                "must not fall. The empire must not break."
            ),
            10: (
                "The enemy has fortified Cape Coast Castle. Ships bring "
                "reinforcements from across the sea. You must act before "
                "their numbers grow."
            ),
            20: (
                "Battle has been joined. The musket smoke chokes the air "
                "around Kumasi. Both sides have taken heavy losses.\n"
                "The ancestors watch. Do not fail them."
            ),
            35: (
                "Five turns remain. The enemy is weakened but not broken. "
                "One final push could end this war. For the Golden Stool!"
            ),
        },
    ),
]


def list_scenarios() -> str:
    """Format all available scenarios as a readable menu."""
    lines = []
    for i, s in enumerate(CAMPAIGN_SCENARIOS, 1):
        lines.append(f"  {i}. {s.name}")
        lines.append(f"     {s.description.split(chr(10))[0]}")
        lines.append(f"     Civilization: {s.player_civ.title()} | Enemy: {s.ai_civ.title()} | Turns: {s.turn_limit}")
        lines.append("")
    return "\n".join(lines)


def get_scenario(index: int) -> Scenario:
    """Get a scenario by 1-based index."""
    if 1 <= index <= len(CAMPAIGN_SCENARIOS):
        return CAMPAIGN_SCENARIOS[index - 1]
    raise ValueError(f"Invalid scenario number: {index}. Choose 1-{len(CAMPAIGN_SCENARIOS)}")


def setup_scenario(scenario: Scenario) -> tuple[PlayerState, AIPlayer]:
    """Create player and AI states from a scenario definition."""
    from .civilizations import get_civ

    civ = get_civ(scenario.player_civ)
    res = scenario.starting_resources
    player = PlayerState(
        name="You",
        civ=civ,
        resources=Resources(
            food=res.get("food", 200),
            wood=res.get("wood", 200),
            gold=res.get("gold", 100),
            kola=res.get("kola", 0),
        ),
    )

    # Override starting units if provided
    player.units = []
    for unit_spec in scenario.starting_units:
        unit_name = unit_spec["unit"]
        count = unit_spec.get("count", 1)
        template = UNITS.get(unit_name)
        if template:
            for _ in range(count):
                u = Unit(template=template, x=10, y=10, owner="player")
                player.units.append(u)

    # Override starting buildings if provided
    player.buildings = []
    for bld_spec in scenario.starting_buildings:
        bld_name = bld_spec["building"]
        turns_remaining = bld_spec.get("turns_remaining", 0)
        template = BUILDINGS.get(bld_name)
        if template:
            b = BuildingInstance(
                template=template,
                x=10, y=10,
                owner="player",
                turns_remaining=turns_remaining,
            )
            player.buildings.append(b)

    player._update_pop()

    # Create AI with bonus resources for harder scenarios
    ai_civ = scenario.ai_civ
    ai = AIPlayer(name="Enemy", civ_name=ai_civ, personality="aggressive")

    # Give AI extra resources based on scenario difficulty
    if scenario.turn_limit >= 40:
        ai.state.resources.food += 300
        ai.state.resources.wood += 200
        ai.state.resources.gold += 200
    elif scenario.turn_limit >= 30:
        ai.state.resources.food += 100
        ai.state.resources.wood += 100

    return player, ai


def check_win_condition(player: PlayerState, ai: AIPlayer, scenario: Scenario) -> str | None:
    """Check if the win condition is met. Returns victory message or None."""
    wc = scenario.win_condition
    if wc["type"] == "destroy_all_ai":
        alive_ai_units = [u for u in ai.state.units if u.alive]
        if not alive_ai_units and not ai.state.train_queue:
            return (
                f"The {ai.state.civ.name} forces have been vanquished!\n"
                f"The {player.civ.name} stand victorious!"
            )
    return None


def check_lose_condition(player: PlayerState, ai: AIPlayer, scenario: Scenario) -> str | None:
    """Check if the lose condition is met. Returns defeat message or None."""
    lc = scenario.lose_condition
    if lc["type"] == "player_lose_all":
        alive_player_units = [u for u in player.units if u.alive]
        if not alive_player_units and not player.train_queue:
            return (
                f"Your last warrior has fallen. The {player.civ.name} "
                f"are no more. The {ai.state.civ.name} claim dominion "
                f"over the land."
            )
    return None


def get_narrative(scenario: Scenario, turn: int) -> str | None:
    """Get narrative text for a given turn, if any."""
    return scenario.narrative_events.get(turn)


def campaign_game_loop(player: PlayerState, ai: AIPlayer, scenario: Scenario, game_map=None):
    """Main game loop for campaign mode with narrative events and win/lose checks."""
    from src.commands import CommandParser

    turn = 1
    max_turns = scenario.turn_limit

    while turn <= max_turns:
        # Print turn header
        print(f"\n{'━' * 50}")
        print(f"  TURN {turn} / {max_turns}")
        print(f"{'━' * 50}")

        # Show narrative event if any
        narrative = get_narrative(scenario, turn)
        if narrative:
            print(f"\n  {'─' * 46}")
            for line in narrative.strip().split("\n"):
                print(f"  {line}")
            print(f"  {'─' * 46}")

        # Show player status
        print(player.status_report())

        # Player input loop
        parser = CommandParser(player, game_map=game_map)
        turn_ended = False

        while not turn_ended:
            try:
                user_input = input(f"\n[{player.age_name()}] > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nThe drums fall silent. Your people await your return.")
                return

            response, should_end = parser.parse(user_input)
            if response == "QUIT":
                print("\nThe drums fall silent. Your people await your return.")
                return

            print(f"\n{response}")

            if should_end:
                turn_ended = True

        # AI takes its turn
        print(f"\n  The {ai.state.civ.name} act...")
        ai_events = ai.take_turn()
        for event in ai_events:
            print(f"    • {event}")

        # Check win condition
        win_msg = check_win_condition(player, ai, scenario)
        if win_msg:
            print(f"\n{'═' * 50}")
            print(f"  VICTORY!")
            print(f"  {win_msg}")
            print(f"{'═' * 50}")
            return

        # Check lose condition
        lose_msg = check_lose_condition(player, ai, scenario)
        if lose_msg:
            print(f"\n{'═' * 50}")
            print(f"  DEFEAT!")
            print(f"  {lose_msg}")
            print(f"{'═' * 50}")
            return

        turn += 1

    # Turn limit reached
    print(f"\n{'═' * 50}")
    print(f"  TIME'S UP — {max_turns} turns have passed.")
    print(f"  The {scenario.name} remains unresolved.")

    alive_ai = sum(1 for u in ai.state.units if u.alive)
    alive_player = sum(1 for u in player.units if u.alive)

    if alive_player > alive_ai:
        print(f"  But your forces outnumber the enemy. The {player.civ.name} prevail!")
    elif alive_ai > alive_player:
        print(f"  The {ai.state.civ.name} outnumber you. They claim victory.")
    else:
        print(f"  Both sides are battered. The struggle continues...")

    print(f"  Final Standings:")
    print(f"    You ({player.civ.name}): {player.age_name()}, {alive_player} units")
    print(f"    Enemy ({ai.state.civ.name}): {ai.state.age_name()}, {alive_ai} units")
    print(f"{'═' * 50}")
