"""Map engine — grid-based terrain system with fog of war and movement."""

import random
from dataclasses import dataclass, field


# Terrain definitions
TERRAIN_TYPES = {
    "savanna":     {"symbol": ".", "name": "Savanna",     "move_cost": 1, "buildable": True},
    "forest":      {"symbol": "T", "name": "Forest",      "move_cost": 2, "buildable": True},
    "coast":       {"symbol": "~", "name": "Coast",       "move_cost": 3, "buildable": True},
    "river":       {"symbol": "≈", "name": "River",       "move_cost": 99, "buildable": False},
    "gold_field":  {"symbol": "G", "name": "Gold Field",  "move_cost": 1, "buildable": True},
    "kola_grove":  {"symbol": "K", "name": "Kola Grove",  "move_cost": 2, "buildable": True},
    "village":     {"symbol": "V", "name": "Village",     "move_cost": 1, "buildable": True},
}

# Which terrains can be built on by default
BUILDABLE_TERRAINS = {t for t, info in TERRAIN_TYPES.items() if info["buildable"]}

# Special building placement rules (building key -> allowed terrains, or None for any buildable)
BUILDING_TERRAIN_RESTRICTIONS = {
    "fishing_village": {"coast"},
    "gold_mine": {"gold_field"},
    "kola_grove": {"kola_grove", "forest"},
    "farm": {"savanna", "village"},
}

# Visibility radius for fog of war
DEFAULT_VISIBILITY = 3

# Map size
MAP_WIDTH = 20
MAP_HEIGHT = 20


@dataclass
class MapCell:
    """A single cell on the game map."""
    terrain: str = "savanna"
    building: str = ""  # "player" or "enemy" or ""
    visible: bool = False  # fog of war: has the player seen this cell?
    revealed: bool = False  # permanently revealed (was visible at some point)


@dataclass
class GameMap:
    """20x20 grid-based game map with terrain and fog of war."""
    width: int = MAP_WIDTH
    height: int = MAP_HEIGHT
    cells: list = field(default_factory=list)
    player_spawn: tuple = (1, 18)
    ai_spawn: tuple = (18, 1)
    player_start_terrain: str = "village"
    ai_start_terrain: str = "village"

    def __post_init__(self):
        if not self.cells:
            self.cells = [
                [MapCell() for _ in range(self.width)]
                for _ in range(self.height)
            ]

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get_cell(self, x: int, y: int) -> MapCell | None:
        if self.in_bounds(x, y):
            return self.cells[y][x]
        return None

    def get_terrain(self, x: int, y: int) -> str:
        cell = self.get_cell(x, y)
        return cell.terrain if cell else "river"  # out of bounds = impassable

    def set_terrain(self, x: int, y: int, terrain: str):
        cell = self.get_cell(x, y)
        if cell and terrain in TERRAIN_TYPES:
            cell.terrain = terrain

    def get_move_cost(self, x: int, y: int) -> int:
        """Get movement cost for a terrain cell. Returns 99 if impassable."""
        terrain = self.get_terrain(x, y)
        return TERRAIN_TYPES.get(terrain, {}).get("move_cost", 99)

    def is_passable(self, x: int, y: int) -> bool:
        return self.get_move_cost(x, y) < 99

    def is_buildable(self, x: int, y: int, building_key: str = "") -> bool:
        """Check if a cell can have a building placed on it."""
        terrain = self.get_terrain(x, y)
        if terrain not in BUILDABLE_TERRAINS:
            return False
        # Check terrain-specific restrictions
        if building_key and building_key in BUILDING_TERRAIN_RESTRICTIONS:
            allowed = BUILDING_TERRAIN_RESTRICTIONS[building_key]
            if terrain not in allowed:
                return False
        cell = self.get_cell(x, y)
        if cell and cell.building:
            return False  # already has a building
        return True

    def place_building(self, x: int, y: int, owner: str):
        """Place a building marker on the map."""
        cell = self.get_cell(x, y)
        if cell:
            cell.building = owner

    def manhattan_distance(self, x1: int, y1: int, x2: int, y2: int) -> int:
        return abs(x1 - x2) + abs(y1 - y2)

    def chebyshev_distance(self, x1: int, y1: int, x2: int, y2: int) -> int:
        return max(abs(x1 - x2), abs(y1 - y2))

    def update_fog(self, sources: list[tuple[int, int]], visibility: int = DEFAULT_VISIBILITY):
        """Update fog of war based on positions of units and buildings."""
        # Reset visibility for this turn (but keep revealed)
        for row in self.cells:
            for cell in row:
                cell.visible = False

        # Mark tiles visible around each source
        for sx, sy in sources:
            for dy in range(-visibility, visibility + 1):
                for dx in range(-visibility, visibility + 1):
                    nx, ny = sx + dx, sy + dy
                    if self.in_bounds(nx, ny):
                        # Use Chebyshev distance (diagonal tiles count)
                        if self.chebyshev_distance(sx, sy, nx, ny) <= visibility:
                            cell = self.cells[ny][nx]
                            cell.visible = True
                            cell.revealed = True

    def get_player_sources(self, player_units: list, player_buildings: list) -> list[tuple[int, int]]:
        """Get all positions that provide visibility for the player."""
        sources = []
        for u in player_units:
            if hasattr(u, 'alive') and u.alive:
                sources.append((u.x, u.y))
            elif not hasattr(u, 'alive'):
                sources.append((u.x, u.y))
        for b in player_buildings:
            if hasattr(b, 'complete') and b.complete:
                sources.append((b.x, b.y))
            elif not hasattr(b, 'complete'):
                sources.append((b.x, b.y))
        return sources

    def render(self, player_units=None, player_buildings=None,
               enemy_units=None, enemy_buildings=None,
               show_full_map=False) -> str:
        """
        Render the map as ASCII art.

        Legend:
          ~  water/coast    .  savanna    T  forest
          G  gold field     K  kola grove V  village
          ≈  river          P  player unit/building
          E  enemy unit/building

        Fog of war: unseen tiles show as ' ' (black)
        Revealed but not currently visible show as '.' (dimmed)
        """
        if player_units is None:
            player_units = []
        if player_buildings is None:
            player_buildings = []
        if enemy_units is None:
            enemy_units = []
        if enemy_buildings is None:
            enemy_buildings = []

        # Update fog of war
        if not show_full_map:
            sources = self.get_player_sources(player_units, player_buildings)
            self.update_fog(sources)

        # Build position lookup for units and buildings
        unit_positions = {}
        for u in player_units:
            if hasattr(u, 'alive') and not u.alive:
                continue
            unit_positions[(u.x, u.y)] = "P"
        for u in enemy_units:
            if hasattr(u, 'alive') and not u.alive:
                continue
            # Only show enemies that are visible
            cell = self.get_cell(u.x, u.y)
            if cell and (cell.visible or show_full_map):
                unit_positions[(u.x, u.y)] = "E"

        building_positions = {}
        for b in player_buildings:
            if hasattr(b, 'complete') and not b.complete:
                continue
            building_positions[(b.x, b.y)] = "P"
        for b in enemy_buildings:
            if hasattr(b, 'complete') and not b.complete:
                continue
            cell = self.get_cell(b.x, b.y)
            if cell and (cell.visible or show_full_map):
                building_positions[(b.x, b.y)] = "E"

        lines = []
        # Header with column numbers
        header = "    " + " ".join(f"{i:>2}" for i in range(self.width))
        lines.append(header)
        lines.append("    " + "─" * (self.width * 3))

        for y in range(self.height):
            row_parts = [f"{y:>2} │"]
            for x in range(self.width):
                cell = self.cells[y][x]

                # Check fog of war
                if not show_full_map and not cell.revealed:
                    row_parts.append("  ")
                    continue
                elif not show_full_map and not cell.visible:
                    # Revealed but not currently visible — show terrain dimly
                    terrain_info = TERRAIN_TYPES.get(cell.terrain, {})
                    symbol = terrain_info.get("symbol", "?")
                    row_parts.append(f" {symbol}")
                    continue

                # Currently visible
                # Priority: unit > building > terrain
                if (x, y) in unit_positions:
                    row_parts.append(f" {unit_positions[(x, y)]}")
                elif (x, y) in building_positions:
                    row_parts.append(f" {building_positions[(x, y)]}")
                else:
                    terrain_info = TERRAIN_TYPES.get(cell.terrain, {})
                    symbol = terrain_info.get("symbol", "?")
                    row_parts.append(f" {symbol}")

            lines.append("".join(row_parts))

        # Legend
        lines.append("")
        lines.append("  Legend: ~ coast  . savanna  T forest  G gold  K kola  V village  ≈ river")
        lines.append("          P player  E enemy   ' ' unexplored")

        return "\n".join(lines)


def generate_map(seed: int | None = None) -> GameMap:
    """
    Generate a random map themed after the Gold Coast.

    Layout concept (roughly):
    - Bottom edge (y=18-19): Coast along the south (Gulf of Guinea)
    - Right edge (x=18-19): Coast along the east
    - River running roughly north-south through the center (x=9-11)
    - Forest clusters in the interior (left-center)
    - Gold fields in the Ashanti heartland (center-north)
    - Kola groves in the forest regions
    - Savanna in the far north
    - Scattered villages

    Player spawns at bottom-left (1, 18), AI at top-right (18, 1).
    """
    if seed is not None:
        random.seed(seed)

    game_map = GameMap()
    w, h = game_map.width, game_map.height

    # 1. Fill with savanna as base
    for y in range(h):
        for x in range(w):
            game_map.cells[y][x] = MapCell(terrain="savanna")

    # 2. Coast along the south edge (y = h-2, h-1)
    for y in range(h - 2, h):
        for x in range(w):
            game_map.cells[y][x].terrain = "coast"

    # 3. Coast along the east edge (x = w-2, w-1)
    for x in range(w - 2, w):
        for y in range(h):
            game_map.cells[y][x].terrain = "coast"

    # Make corner areas coast (where south and east coasts meet)
    # Already handled by the two loops above

    # 4. River running roughly north-south through center
    #    Winding path from top to bottom, centered around x=9-10
    river_x = 9
    for y in range(0, h - 2):  # Don't extend into coast
        # River meanders left and right
        offset = random.choice([-1, 0, 0, 0, 1])
        rx = max(1, min(w - 3, river_x + offset))
        game_map.cells[y][rx].terrain = "river"
        # River is 1-2 tiles wide
        if random.random() < 0.4:
            rx2 = rx + random.choice([-1, 1])
            if 0 <= rx2 < w and game_map.cells[y][rx2].terrain != "coast":
                game_map.cells[y][rx2].terrain = "river"
        river_x = rx

    # 5. Forest clusters in the interior
    #    Create 3-4 forest clusters using a scatter approach
    forest_centers = [
        (3, 5),   # western interior
        (5, 8),   # southwest interior
        (12, 6),  # eastern interior
        (7, 12),  # central
    ]
    for cx, cy in forest_centers:
        # Each cluster covers a random area
        cluster_size = random.randint(3, 6)
        for _ in range(cluster_size):
            dx = random.randint(-3, 3)
            dy = random.randint(-3, 3)
            nx, ny = cx + dx, cy + dy
            if game_map.in_bounds(nx, ny):
                cell = game_map.cells[ny][nx]
                if cell.terrain == "savanna":
                    cell.terrain = "forest"

    # 6. Gold fields in the Ashanti heartland (center-north)
    gold_centers = [
        (7, 3),   # northern gold
        (11, 2),  # northeastern gold
        (5, 1),   # far north gold
    ]
    for cx, cy in gold_centers:
        cluster_size = random.randint(2, 4)
        for _ in range(cluster_size):
            dx = random.randint(-2, 2)
            dy = random.randint(-2, 2)
            nx, ny = cx + dx, cy + dy
            if game_map.in_bounds(nx, ny):
                cell = game_map.cells[ny][nx]
                if cell.terrain == "savanna":
                    cell.terrain = "gold_field"

    # 7. Kola groves — place near forest clusters
    kola_centers = [
        (3, 5),   # in western forest
        (5, 8),   # in southwest forest
        (12, 6),  # in eastern forest
    ]
    for cx, cy in kola_centers:
        cluster_size = random.randint(2, 4)
        for _ in range(cluster_size):
            dx = random.randint(-2, 2)
            dy = random.randint(-2, 2)
            nx, ny = cx + dx, cy + dy
            if game_map.in_bounds(nx, ny):
                cell = game_map.cells[ny][nx]
                if cell.terrain in ("forest", "savanna"):
                    cell.terrain = "kola_grove"

    # 8. Scatter a few villages
    village_positions = [(2, 3), (14, 4), (8, 14), (16, 10)]
    for vx, vy in village_positions:
        if game_map.in_bounds(vx, vy):
            cell = game_map.cells[vy][vx]
            if cell.terrain not in ("river", "coast"):
                cell.terrain = "village"

    # 9. Place player and AI spawns
    # Player: bottom-left (1, 18) — near the coast
    # Make sure spawn is passable
    px, py = game_map.player_spawn
    game_map.cells[py][px].terrain = "village"
    game_map.player_start_terrain = "village"

    # AI: top-right (18, 1) — in the savanna
    ax, ay = game_map.ai_spawn
    game_map.cells[ay][ax].terrain = "village"
    game_map.ai_start_terrain = "village"

    # Ensure spawns aren't on rivers
    for sx, sy in [game_map.player_spawn, game_map.ai_spawn]:
        if game_map.get_terrain(sx, sy) == "river":
            game_map.cells[sy][sx].terrain = "savanna"

    # Clear a small area around spawns (make sure it's passable)
    for sx, sy in [game_map.player_spawn, game_map.ai_spawn]:
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                nx, ny = sx + dx, sy + dy
                if game_map.in_bounds(nx, ny):
                    cell = game_map.cells[ny][nx]
                    if cell.terrain == "river":
                        cell.terrain = "savanna"

    return game_map
