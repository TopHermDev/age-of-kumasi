"""Command parser — translates text input into game actions."""

import re
from .game import PlayerState
from .combat import resolve_combat, resolve_battle_round, get_battle_summary

HELP_TEXT = """
COMMANDS:
  map / m                   — Show the game map
  status                    — Show full status report
  help                      — Show this help
  gather <resource> [n]     — Assign villagers (food/wood/gold/kola)
  build <building>          — Construct a building
  train <unit> [n]          — Train n units (default: 1)
  advance                   — Advance to the next age
  list units                — Show available units
  list buildings            — Show available buildings
  list techs                — Show available technologies
  research <tech>           — Research a technology (requires Library)
  end / next                — End your turn
  move <unit> <direction>   — Move a unit (north/south/east/west)
  attack                    — Attack nearest enemy with your military
  defend                    — Defend against enemy attack
  diplomacy                 — Show diplomacy status and options
  propose alliance          — Propose alliance with AI
  declare war               — Declare war on AI
  offer tribute <res> <n>   — Gift resources to improve relations
  demand tribute <res> <n>  — Demand tribute (risky!)
  save                      — Save the game
  load                      — Load a saved game
  quit                      — Exit the game

MAP LEGEND:
  ~ coast    . savanna    T forest    G gold field
  K kola     V village    ≈ river     P player
  E enemy    (blank) unexplored

TIPS:
  - Type partial names: "train arch" trains archers
  - "build barr" builds a Barracks
  - Move north decreases y, south increases y
  - Terrain affects movement: forest costs 2, rivers impassable
"""


class CommandParser:
    """Parses text commands and dispatches to game state."""

    def __init__(self, player: PlayerState, ai=None, diplomacy=None, turn: int = 1, game_map=None):
        self.player = player
        self.ai = ai
        self.diplomacy = diplomacy
        self.turn = turn
        self.game_map = game_map

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

        # === Map ===
        if cmd in ("map", "m", "view"):
            return self._cmd_map(args)

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

        # === Research commands ===
        if cmd in ("research", "study", "discover"):
            return self._cmd_research(args)

        # === Attack ===
        if cmd in ("attack", "fight", "battle"):
            return self._cmd_attack(args)
        
        # === Defend ===
        if cmd in ("defend", "def"):
            return self._cmd_defend(args)

        # === Move ===
        if cmd in ("move", "go"):
            return self._cmd_move(args)

        # === Diplomacy commands ===
        if cmd in ("diplomacy", "diplomat", "diplo"):
            return self._cmd_diplomacy(args)

        if cmd in ("propose", "propose_alliance"):
            return self._cmd_propose_alliance(args)

        if cmd in ("declare", "declare_war"):
            return self._cmd_declare_war(args)

        if cmd in ("offer", "offer_tribute", "tribute"):
            return self._cmd_offer_tribute(args)

        if cmd in ("demand", "demand_tribute"):
            return self._cmd_demand_tribute(args)

        # === Save/Load ===
        if cmd == "save":
            return self._cmd_save(args)

        if cmd == "load":
            return self._cmd_load(args)

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
            from .technologies import format_tech_list
            return f"Available Technologies:\n{format_tech_list(self.player.age)}", False
        return f"Unknown list type: '{what}'. Use units, buildings, or techs.", False

    def _cmd_research(self, args: list[str]) -> tuple[str, bool]:
        """Research a technology. Requires a Library building."""
        if not args:
            from .technologies import format_tech_list
            return f"Usage: research <technology>\n\nAvailable:\n{format_tech_list(self.player.age)}", False
        tech_name = " ".join(args)
        result = self.player.start_research(tech_name)
        return result, False

    def _cmd_attack(self, args: list[str]) -> tuple[str, bool]:
        """Attack the nearest enemy military unit with your forces."""
        alive_military = [
            u for u in self.player.units
            if u.alive and u.template.category != "civilian"
        ]
        if not alive_military:
            return "You have no military units to attack with. Train some first.", False
        
        # Find AI enemy units
        if not self.ai:
            return "No enemy to attack.", False
        
        enemy_military = [
            u for u in self.ai.state.units
            if u.alive and u.template.category != "civilian"
        ]
        if not enemy_military:
            return "The enemy has no military units to fight.", False
        
        # Each player unit attacks nearest enemy
        results = []
        for unit in alive_military:
            if not unit.alive:
                continue
            from .combat import find_nearest_enemy
            target = find_nearest_enemy(unit, enemy_military)
            if target:
                result = resolve_combat(unit, target)
                results.append(result)
        
        # Remove dead units from both sides
        self.player.units = [u for u in self.player.units if u.alive]
        self.ai.state.units = [u for u in self.ai.state.units if u.alive]
        
        # Generate battle report
        battle_summary = get_battle_summary(results)
        self.player.last_battle = battle_summary
        
        return battle_summary, False
    
    def _cmd_defend(self, args: list[str]) -> tuple[str, bool]:
        """Defend against enemy attack — enemy units attack your forces."""
        if not self.ai:
            return "No enemy to defend against.", False
        
        alive_military = [
            u for u in self.player.units
            if u.alive and u.template.category != "civilian"
        ]
        enemy_military = [
            u for u in self.ai.state.units
            if u.alive and u.template.category != "civilian"
        ]
        
        if not alive_military:
            return "You have no military units to defend with. Train some first.", False
        if not enemy_military:
            return "The enemy has no military units attacking.", False
        
        # Enemy attacks first (they initiated)
        results = []
        for unit in enemy_military:
            if not unit.alive:
                continue
            from .combat import find_nearest_enemy
            target = find_nearest_enemy(unit, alive_military)
            if target:
                result = resolve_combat(unit, target)
                results.append(result)
        
        # Player units counter-attack
        for unit in alive_military:
            if not unit.alive:
                continue
            from .combat import find_nearest_enemy
            target = find_nearest_enemy(unit, enemy_military)
            if target:
                result = resolve_combat(unit, target)
                results.append(result)
        
        # Remove dead units
        self.player.units = [u for u in self.player.units if u.alive]
        self.ai.state.units = [u for u in self.ai.state.units if u.alive]
        
        battle_summary = get_battle_summary(results)
        self.player.last_battle = battle_summary
        
        return battle_summary, False

    def _cmd_map(self, args: list[str]) -> tuple[str, bool]:
        """Render the game map as ASCII art."""
        if not self.game_map:
            return "No map available.", False
        show_all = "full" in args or "all" in args
        rendering = self.game_map.render(
            player_units=self.player.units,
            player_buildings=self.player.buildings,
            enemy_units=self.ai.state.units if self.ai else [],
            enemy_buildings=self.ai.state.buildings if self.ai else [],
            show_full_map=show_all,
        )
        return rendering, False

    def _cmd_move(self, args: list[str]) -> tuple[str, bool]:
        """Move a unit in a direction: move <unit> <direction>

        Directions: north/south/east/west (or n/s/e/w)
        """
        if not args:
            return (
                "Usage: move <unit> <direction>\n"
                "Directions: north, south, east, west (or n, s, e, w)"
            ), False
        if not self.game_map:
            return "No map available. Movement requires a map.", False

        # Find the unit name and direction
        direction_map = {
            "north": (0, -1), "n": (0, -1),
            "south": (0, 1), "s": (0, 1),
            "east": (1, 0), "e": (1, 0),
            "west": (-1, 0), "w": (-1, 0),
        }

        # Parse: "move scout north" → unit="scout", direction="north"
        # Also handle: "move club_warrior north"
        direction = None
        unit_name_parts = []
        for part in args:
            if part.lower() in direction_map:
                direction = part.lower()
            else:
                unit_name_parts.append(part)

        if not direction:
            return (
                "Which direction? Use: north, south, east, west (or n, s, e, w)"
            ), False

        if not unit_name_parts:
            return "Move which unit? Usage: move <unit> <direction>", False

        unit_name = " ".join(unit_name_parts)
        dx, dy = direction_map[direction]

        # Find a matching alive unit owned by the player
        target_unit = None
        for u in self.player.units:
            if u.alive and unit_name.lower() in u.name.lower():
                target_unit = u
                break

        if not target_unit:
            alive_names = [u.name for u in self.player.units if u.alive]
            if alive_names:
                return f"No unit matching '{unit_name}'. You have: {', '.join(alive_names)}", False
            return "You have no units to move.", False

        # Check movement points
        if target_unit.moves_remaining <= 0:
            return f"{target_unit.name} has no movement points left this turn.", False

        # Calculate new position
        new_x = target_unit.x + dx
        new_y = target_unit.y + dy

        # Check bounds
        if not self.game_map.in_bounds(new_x, new_y):
            return f"Can't move {direction} — edge of the map.", False

        # Check terrain passability
        move_cost = self.game_map.get_move_cost(new_x, new_y)
        if move_cost >= 99:
            terrain_name = self.game_map.get_terrain(new_x, new_y)
            return f"Can't move {direction} — {terrain_name} is impassable.", False

        # Check for friendly unit collision
        for u in self.player.units:
            if u.alive and u is not target_unit and u.x == new_x and u.y == new_y:
                return f"Can't move {direction} — your {u.name} is blocking the way.", False

        # Move the unit
        terrain = self.game_map.get_terrain(new_x, new_y)
        target_unit.x = new_x
        target_unit.y = new_y
        target_unit.moves_remaining = max(0, target_unit.moves_remaining - move_cost)

        terrain_names = {
            "savanna": "savanna", "forest": "forest", "coast": "coast",
            "river": "river", "gold_field": "gold field", "kola_grove": "kola grove",
            "village": "village",
        }
        terrain_label = terrain_names.get(terrain, terrain)

        msg = f"{target_unit.name} moves {direction} to ({new_x},{new_y}) — {terrain_label}"
        msg += f" [moves left: {target_unit.moves_remaining}]"
        return msg, False

    # === Diplomacy commands ===

    def _cmd_diplomacy(self, args: list[str]) -> tuple[str, bool]:
        """Show diplomacy status."""
        if not self.ai or not self.diplomacy:
            return "Diplomacy system not available.", False
        entity_key = self.ai.state.civ.name.lower()
        report = self.diplomacy.status_report(entity_key, self.ai.personality)
        return report, False

    def _cmd_propose_alliance(self, args: list[str]) -> tuple[str, bool]:
        """Propose alliance with the AI."""
        if not self.ai or not self.diplomacy:
            return "Diplomacy system not available.", False
        entity_key = self.ai.state.civ.name.lower()
        result = self.diplomacy.propose_alliance(
            entity_key, self.player, self.ai.personality
        )
        return result, False

    def _cmd_declare_war(self, args: list[str]) -> tuple[str, bool]:
        """Declare war on the AI."""
        if not self.ai or not self.diplomacy:
            return "Diplomacy system not available.", False
        entity_key = self.ai.state.civ.name.lower()
        result = self.diplomacy.declare_war(entity_key, self.player)
        return result, False

    def _cmd_offer_tribute(self, args: list[str]) -> tuple[str, bool]:
        """Offer tribute to the AI."""
        if not self.ai or not self.diplomacy:
            return "Diplomacy system not available.", False
        # Skip "tribute" keyword if present
        if args and args[0] == "tribute":
            args = args[1:]
        if len(args) < 2:
            return (
                "Usage: offer tribute <resource> <amount>\n"
                "Resources: food, wood, gold, kola"
            ), False

        resource = args[0]
        if resource not in ("food", "wood", "gold", "kola"):
            return f"Unknown resource: '{resource}'. Use food, wood, gold, or kola.", False
        try:
            amount = int(args[1])
        except ValueError:
            return "Amount must be a number.", False
        if amount <= 0:
            return "Amount must be positive.", False

        entity_key = self.ai.state.civ.name.lower()
        result = self.diplomacy.offer_tribute(
            entity_key, resource, amount, self.player.resources
        )
        return result, False

    def _cmd_demand_tribute(self, args: list[str]) -> tuple[str, bool]:
        """Demand tribute from the AI."""
        if not self.ai or not self.diplomacy:
            return "Diplomacy system not available.", False
        # Skip "tribute" keyword if present
        if args and args[0] == "tribute":
            args = args[1:]
        if len(args) < 2:
            return (
                "Usage: demand tribute <resource> <amount>\n"
                "Resources: food, wood, gold, kola\n"
                "WARNING: Demanding tribute can provoke war!"
            ), False

        resource = args[0]
        if resource not in ("food", "wood", "gold", "kola"):
            return f"Unknown resource: '{resource}'. Use food, wood, gold, or kola.", False
        try:
            amount = int(args[1])
        except ValueError:
            return "Amount must be a number.", False
        if amount <= 0:
            return "Amount must be positive.", False

        entity_key = self.ai.state.civ.name.lower()
        result = self.diplomacy.demand_tribute(
            entity_key, resource, amount, self.player.resources, self.ai.personality
        )
        return result, False

    def _cmd_save(self, args: list[str] = None) -> tuple[str, bool]:
        """Save the game to a file."""
        filepath = (args or [])[0] if args else "savegame.json"
        try:
            from .save_load import save_game
            msg = save_game(self.player, self.ai, self.diplomacy, filepath)
            return msg, False
        except Exception as e:
            return f"Error saving game: {e}", False

    def _cmd_load(self, args: list[str] = None) -> tuple[str, bool]:
        """Load the game from a file.
        
        Returns a special __LOAD__<filepath> marker that the game loop detects
        to swap state.
        """
        filepath = (args or [])[0] if args else "savegame.json"
        import os
        if not os.path.exists(filepath):
            return f"Save file not found: {filepath}", False
        return f"__LOAD__{filepath}", False

    def _end_turn(self) -> tuple[str, bool]:
        events = self.player.process_turn()
        if events:
            event_text = "\n".join(f"  • {e}" for e in events)
            return f"\n--- TURN ENDS ---\n{event_text}\n", True
        return "\n--- TURN ENDS ---\n  Nothing notable happens.\n", True
