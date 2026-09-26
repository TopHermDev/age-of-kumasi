#!/usr/bin/env python3
"""
AGE OF KUMASI
A text-based strategy game through Ghanaian civilizations.
Inspired by Age of Empires II.
"""

import sys
import os

# Add project root to path so 'from src.xxx' works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.civilizations import list_civs, get_civ, CIVILIZATIONS
from src.game import PlayerState, AGES
from src.commands import CommandParser
from src.ai import AIPlayer


def print_banner():
    print("""
    ╔══════════════════════════════════════════════════╗
    ║                                                  ║
    ║              AGE  OF  K U M A S I                ║
    ║                                                  ║
    ║    A Text-Based Strategy Game Through             ║
    ║    Ghanaian Civilizations                         ║
    ║                                                  ║
    ║    Inspired by Age of Empires II                  ║
    ║                                                  ║
    ╚══════════════════════════════════════════════════╝
    """)


def choose_civilization() -> str:
    """Let the player pick a civilization."""
    print("\nChoose your civilization:\n")
    print(list_civs())
    while True:
        choice = input("Enter civilization name (or number): ").strip().lower()
        civ_keys = list(CIVILIZATIONS.keys())
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(civ_keys):
                return civ_keys[idx]
        if choice in civ_keys:
            return choice
        print(f"Invalid choice. Enter one of: {', '.join(civ_keys)}")


def choose_ai_civ(exclude: str) -> str:
    """Pick a random AI civ different from the player's."""
    available = [k for k in CIVILIZATIONS.keys() if k != exclude]
    return __import__("random").choice(available)


def print_intro(player: PlayerState, ai: AIPlayer):
    """Print the game introduction."""
    print(f"\n{'═' * 50}")
    print(f"  The year is uncertain. The Gold Coast stirs.")
    print(f"  You lead the {player.civ.name} people of {player.civ.region}.")
    print(f"  Your rival, the {ai.state.civ.name} ({ai.personality}),")
    print(f"  seeks the same dominance.")
    print(f"{'═' * 50}")
    print(f"\n  Your civilization: {player.civ.description}")
    print(f"\n  Unique Unit: {player.civ.unique_unit}")
    print(f"  {player.civ.unique_unit_desc}")
    print(f"\n  Bonus: {player.civ.bonus}")
    print(f"{'═' * 50}")
    print(f"\n  Type 'help' for commands. Type 'status' to see your empire.")
    print(f"  Type 'end' to finish your turn.\n")


def game_loop(player: PlayerState, ai: AIPlayer):
    """Main game loop."""
    turn = 1
    max_turns = 100  # Game ends after this many turns

    while turn <= max_turns:
        print(f"\n{'━' * 50}")
        print(f"  TURN {turn}")
        print(f"{'━' * 50}")

        # Show player status
        print(player.status_report())

        # Player input loop
        parser = CommandParser(player)
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

        # Check win conditions
        if player.age >= 4 and ai.state.age < 4:
            print(f"\n{'═' * 50}")
            print(f"  VICTORY! Your civilization has reached the Age of Resistance")
            print(f"  while the {ai.state.civ.name} lag behind.")
            print(f"  Your people celebrate with drum and dance!")
            print(f"{'═' * 50}")
            return

        if ai.state.age >= 4 and player.age < 4:
            print(f"\n{'═' * 50}")
            print(f"  DEFEAT! The {ai.state.civ.name} have reached the Age of")
            print(f"  Resistance while your people struggle.")
            print(f"{'═' * 50}")
            return

        turn += 1

    # Game ends at max turns
    print(f"\n{'═' * 50}")
    print(f"  GAME OVER — {max_turns} turns have passed.")
    print(f"  Final Standings:")
    print(f"    You ({player.civ.name}): {player.age_name()}")
    print(f"    Enemy ({ai.state.civ.name}): {ai.state.age_name()}")
    if player.age > ai.state.age:
        print(f"  Your civilization stands supreme!")
    elif player.age < ai.state.age:
        print(f"  The enemy has outpaced you.")
    else:
        print(f"  The ages are equal. The struggle continues...")
    print(f"{'═' * 50}")


def main():
    print_banner()

    # Main menu
    print("  1. Free Play — Choose your civilization and fight an AI opponent")
    print("  2. Campaign — Play through historical scenarios\n")

    while True:
        try:
            choice = input("  Select mode (1 or 2): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nThe drums fall silent. Your people await your return.\n")
            return

        if choice == "1":
            free_play()
            break
        elif choice == "2":
            campaign_menu()
            break
        else:
            print("  Please enter 1 or 2.")

    print("\nThank you for playing Age of Kumasi!")
    print("The Gold Coast remembers.\n")


def free_play():
    """Standard free play mode."""
    from src.game import PlayerState

    # Choose civilization
    civ_name = choose_civilization()
    civ = get_civ(civ_name)
    print(f"\nYou have chosen the {civ.name}! {civ.bonus}")

    # Create player
    player = PlayerState(name="You", civ=civ)

    # Create AI opponent
    ai_civ_name = choose_ai_civ(civ_name)
    ai = AIPlayer(name="Enemy", civ_name=ai_civ_name)

    # Print intro
    print_intro(player, ai)

    # Start game
    game_loop(player, ai)


def campaign_menu():
    """Campaign mode menu and game runner."""
    from src.campaign import list_scenarios, get_scenario, setup_scenario, campaign_game_loop

    print(f"\n{'═' * 50}")
    print("  CAMPAIGN MODE")
    print("  Play through the history of Ghana, chapter by chapter.")
    print(f"{'═' * 50}\n")

    print(list_scenarios())

    while True:
        try:
            choice = input(f"  Select scenario (1-3): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nThe drums fall silent.\n")
            return

        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= 3:
                break
        print("  Please enter 1, 2, or 3.")

    scenario = get_scenario(idx)
    print(f"\n  Starting: {scenario.name}")
    print(f"{'─' * 50}")
    print(f"  {scenario.description}")
    print(f"{'─' * 50}\n")

    player, ai = setup_scenario(scenario)

    # Print scenario intro
    print(f"  You lead the {player.civ.name} people.")
    print(f"  Your rival: {ai.state.civ.name} ({ai.personality}).")
    print(f"  Turn limit: {scenario.turn_limit}")
    print(f"\n  Type 'help' for commands. Type 'end' to finish your turn.\n")

    campaign_game_loop(player, ai, scenario)


if __name__ == "__main__":
    main()
