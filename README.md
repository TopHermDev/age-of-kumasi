# Age of Kumasi

A text-based strategy game inspired by Age of Empires II, reimagined through
Ghanaian civilizations. Build your empire, gather resources, advance through
historical ages, and conquer the Gold Coast.

## Screenshot

```
╔══════════════════════════════════════════════════╗
║              AGE  OF  K U M A S I                ║
║    A Text-Based Strategy Game Through             ║
║    Ghanaian Civilizations                         ║
╚══════════════════════════════════════════════════╝

══════════════════════════════════════════════════
  Ashanti Empire — Age of Gold
  Population: 18/20
  Food: 340  Wood: 120  Gold: 580  Kola: 25
══════════════════════════════════════════════════
  Military:
    Villager: 10    Archer: 4    Spearman: 3
    Scout: 1
  Buildings:
    Town Center: 1    Barracks: 1    Gold Mine: 2
    Farm: 3    Archery Range: 1    Shrine: 1
  Training:
    Archer: 2 turns
══════════════════════════════════════════════════
  Diplomacy: Neutral with Ewe (Rep: 0)
```

## Features

- **6 Ghanaian Civilizations** — Ashanti, Dagbon, Ga, Ewe, Mamprusi, Fante
- **4 Historical Ages** — Age of Settlement, Age of Gold, Age of the Stool, Age of Resistance
- **13 Unit Types** — From Club Warriors to Siege Rams
- **12 Building Types** — Town Center, Barracks, Gold Mine, Palace, and more
- **15 Technologies** — Gold Weighting, Drum Communication, Golden Stool Unity, and more
- **Combat System** — AoE2-style counter bonuses (cavalry > infantry > archers > cavalry)
- **Diplomacy** — Alliances, tribute, war declarations with AI personality-based responses
- **Map Engine** — 20x20 grid with 7 terrain types, fog of war, movement
- **Campaign Mode** — 3 historical scenarios (Founding of Kumasi, Golden Stool, Anglo-Ashanti Wars)
- **Save/Load** — JSON game state persistence
- **AI Opponent** — Rule-based with aggressive, defensive, and trader personalities

## Requirements

- **Python 3.10+** (developed on 3.14)
- No external dependencies — uses only Python standard library

## Setup

### Quick Start

```bash
# Clone the repository
git clone https://github.com/TopHermDev/age-of-kumasi.git
cd age-of-kumasi

# Run the game
python3 src/main.py
```

### Verify Installation

```bash
# Quick smoke test (non-interactive)
echo -e "ashanti\nstatus\nhelp\nquit" | python3 src/main.py
```

### Project Structure

```
age-of-kumasi/
├── src/
│   ├── main.py              # Entry point, game loop, menus
│   ├── game.py              # Player state, resources, age progression
│   ├── civilizations.py     # 6 civilizations with unique bonuses
│   ├── units.py             # 13 unit definitions across 4 ages
│   ├── buildings.py         # 12 building definitions
│   ├── technologies.py      # 15 researchable technologies
│   ├── commands.py          # Text command parser
│   ├── combat.py            # Combat resolution with counter bonuses
│   ├── diplomacy.py         # Alliances, tribute, reputation
│   ├── map_engine.py        # 20x20 grid map with terrain
│   ├── ai.py                # AI opponent with 3 personalities
│   ├── campaign.py          # 3 historical campaign scenarios
│   └── save_load.py         # JSON save/load serialization
├── DESIGN.md                # Game design concept document
├── LICENSE                  # MIT License
└── README.md                # This file
```

## How to Play

### Starting the Game

```bash
python3 src/main.py
```

Choose a civilization, then enter commands at the prompt.

### Basic Commands

| Command | Description |
|---------|-------------|
| `status` | Show full empire status |
| `help` | List all available commands |
| `build <building>` | Construct a building |
| `train <unit> [n]` | Train n units (default: 1) |
| `gather <resource>` | Gather food/wood/gold/kola |
| `advance` | Advance to the next age |
| `map` | Show the ASCII game map |
| `move <unit> <direction>` | Move a unit (north/south/east/west) |
| `attack` | Attack nearest enemy |
| `defend` | Defend against enemy attack |
| `diplomacy` | Show diplomacy options |
| `propose alliance` | Seek peace with AI |
| `offer tribute <res> <n>` | Gift resources to improve relations |
| `declare war` | Open hostilities |
| `research <tech>` | Research a technology (requires Library) |
| `list units` | Show available units |
| `list buildings` | Show available buildings |
| `list techs` | Show available technologies |
| `save` | Save game to file |
| `load` | Load saved game |
| `end` | End your turn |

### Tips

- Type partial names: `train arch` trains archers, `build barr` builds a Barracks
- Advance through ages to unlock better units and buildings
- Build a Library to research technologies
- Build a Palace before advancing to Age III
- Use diplomacy wisely — alliances prevent attacks, tribute improves relations
- The AI has personalities: aggressive civs attack faster, traders love tribute

### Resources

| Resource | Source | Uses |
|----------|--------|------|
| **Food** | Farms, Fishing Villages | Training units, age advancement |
| **Wood** | Forests | Building construction |
| **Gold** | Gold Mines | Units, upgrades, age advancement |
| **Kola** | Kola Groves | Defensive structures, special tech |

### Ages

1. **Age of Settlement** — Basic units, economy foundation
2. **Age of Gold** — Archers, cavalry, trade
3. **Age of the Stool** — Palace, gunpowder, elite infantry
4. **Age of Resistance** — Siege, war drums, final conflict

## Roadmap

- [x] Core game engine (civilizations, units, buildings)
- [x] Combat system with AoE2-style counters
- [x] Technology tree (15 techs)
- [x] Diplomacy system (alliances, tribute, war)
- [x] Map engine with terrain and fog of war
- [x] Campaign mode (3 scenarios)
- [x] Save/load game state
- [ ] Multi-user web browser playable ([Issue #1](https://github.com/TopHermDev/age-of-kumasi/issues/1))
- [ ] Sound effects and music
- [ ] More campaign scenarios
- [ ] Unit animations in terminal
- [ ] Tournament/leaderboard system

## Contributing

Contributions are welcome! Fork the repo, create a feature branch, and submit a PR.

```bash
# Create a feature branch
git checkout -b feat/my-feature

# Make changes, then commit
git add .
git commit -m "feat: add my feature"

# Push and create PR
git push -u origin feat/my-feature
gh pr create
```

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by [Age of Empires II](https://www.ageofempires.com/) by Ensemble Studios
- Built with respect for Ghanaian history and cultures
- The Ashanti proverb: *"If you want to go fast, go alone. If you want to go far, go together."*
