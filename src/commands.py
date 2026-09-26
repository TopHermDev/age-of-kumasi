"""Command parser — translates text input into game actions."""

import re
from .game import PlayerState


HELP_TEXT = """
COMMANDS:
  status                    — Show full status report
  help                      — Show this help
  gather <resource> [n]     — Assign villagers (food/wood/gold/kola)
  build <building>          — Construct a building
  train <unit> [n]          — Train n units (default: 1)
  advance                   — Advance to the next age
  list units                — Show available units
  list buildings            — Show available buildings
  list techs                — Show available technologies
  end / next                — End your turn
  attack <target>           — Attack an enemy
  move <unit> <x> <y>       — Move a unit
  diplomacy                 — Show diplomacy options
  save                      — Save the game
  load                      — Load a saved game
  quit                      — Exit the game

TIPS:
  - Type partial names: "train arch" trains archers
  - "build barr" builds a Barracks
  - Resources: food, wood, gold, kola
"""


class CommandParser:
    """Parses text commands and dispatches to game state."""

    def __init__(self, player: PlayerState):
        self.player = player

    def parse(self, raw_input: str) -> tuple[str, bool]:
        """
        Parse a command string and execute it.
        Returns (response_text, should_end_turn).
        """
        raw = raw_input.strip()
        if not raw:
            return "No command entered. Type 'help' for available commands.", False

        parts = raw.lower().split()
        cmd = parts[0]
        args = parts[1:]

        # === Navigation commands ===
        if cmd in ("help", "h", "?"):
            return HELP_TEXT, False

        if cmd in ("status", "st", "s"):
            return self.player.status_report(), False

        if cmd in ("end", "next", "done", "turn", "e", "n"):
            return self._end_turn()

        # === Resource commands ===
        if cmd == "gather":
            return self._cmd_gather(args)

        # === Build commands ===
        if cmd in ("build", "construct", "make"):
            return self._cmd_build(args)

        # === Train commands ===
        if cmd in ("train", "recruit", "create"):
            return self._cmd_train(args)

        # === Age advancement ===
        if cmd in ("advance", "age", "nextage"):
            return self._cmd_advance()

        # === List commands ===
        if cmd == "list":
            return self._cmd_list(args)

        # === Attack ===
        if cmd in ("attack", "fight", "battle"):
            return self._cmd_attack(args)

        # === Move ===
        if cmd in ("move", "go"):
            return self._cmd_move(args)

        # === Diplomacy ===
        if cmd in ("diplomacy", "diplomat", "ally"):
            return "Diplomacy system coming soon. For now, focus on building your empire.", False

        # === Save/Load ===
        if cmd == "save":
            return "Save system coming soon. For now, your progress persists this session.", False
        if cmd == "load":
            return "Load system coming soon.", False

        # === Quit ===
        if cmd in ("quit", "exit", "q"):
            return "QUIT", True

        return (
            f"Unknown command: '{cmd}'. Type 'help' for available commands.",
            False,
        )

    def _cmd_gather(self, args: list[str]) -> tuple[str, bool]:
        if not args:
            return "Usage: gather <resource> [amount]\nResources: food, wood, gold, kola", False
        resource = args[0]
        if resource not in ("food", "wood", "gold", "kola"):
            return f"Unknown resource: '{resource}'. Use food, wood, gold, or kola.", False
        amount = int(args[1]) if len(args) > 1 else 10
        setattr(self.player.resources, resource, getattr(self.player.resources, resource) + amount)
        return f"Gathered {amount} {resource}.", False

    def _cmd_build(self, args: list[str]) -> tuple[str, bool]:
        if not args:
            from .buildings import format_building_list
            return f"Usage: build <building>\n\nAvailable:\n{format_building_list(self.player.age)}", False
        building_name = " ".join(args)
        result = self.player.build_structure(building_name)
        return result, False

    def _cmd_train(self, args: list[str]) -> tuple[str, bool]:
        if not args:
            from .units import format_unit_list
            return f"Usage: train <unit> [count]\n\nAvailable:\n{format_unit_list(self.player.age)}", False
        count = 1
        unit_name = args[0]
        if len(args) > 1 and args[-1].isdigit():
            count = int(args[-1])
            unit_name = " ".join(args[:-1])
        result = self.player.train_unit(unit_name, count)
        return result, False

    def _cmd_advance(self) -> tuple[str, bool]:
        result = self.player.advance_age()
        return result, False

    def _cmd_list(self, args: list[str]) -> tuple[str, bool]:
        if not args:
            return "Usage: list <units|buildings|techs>", False
        what = args[0]
        if what in ("unit", "units", "u"):
            from .units import format_unit_list
            return f"Available Units:\n{format_unit_list(self.player.age)}", False
        if what in ("building", "buildings", "b"):
            from .buildings import format_building_list
            return f"Available Buildings:\n{format_building_list(self.player.age)}", False
        if what in ("tech", "techs", "t"):
            return "Technology tree coming soon.", False
        return f"Unknown list type: '{what}'. Use units, buildings, or techs.", False

    def _cmd_attack(self, args: list[str]) -> tuple[str, bool]:
        alive_military = [
            u for u in self.player.units
            if u.alive and u.template.category != "civilian"
        ]
        if not alive_military:
            return "You have no military units to attack with. Train some first.", False
        if not args:
            unit_list = ", ".join(u.name for u in alive_military)
            return (
                f"Your military units: {unit_list}\n"
                f"Usage: attack <unit_name>\n"
                f"(Target selection coming soon — for now, units march forward.)"
            ), False
        # Basic attack: send first matching unit
        target = " ".join(args)
        for unit in alive_military:
            if target.lower() in unit.name.lower():
                return (
                    f"Your {unit.name} charges into battle!\n"
                    f"(Full combat system coming soon — for now, the attack echoes across the savanna.)"
                ), False
        return f"No military unit matching '{target}' found.", False

    def _cmd_move(self, args: list[str]) -> tuple[str, bool]:
        return (
            "Movement system coming soon.\n"
            "Currently all units are at your settlement center."
        ), False

    def _end_turn(self) -> tuple[str, bool]:
        events = self.player.process_turn()
        if events:
            event_text = "\n".join(f"  • {e}" for e in events)
            return f"\n--- TURN ENDS ---\n{event_text}\n", True
        return "\n--- TURN ENDS ---\n  Nothing notable happens.\n", True
