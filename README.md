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
- The terminal game uses **only the Python standard library**
- The web/multiplayer server additionally needs FastAPI + Uvicorn (`requirements.txt`)

## Setup

### Quick Start — terminal

```bash
# Clone the repository
git clone https://github.com/TopHermDev/age-of-kumasi.git
cd age-of-kumasi

# Run the game
python3 src/main.py
```

### Quick Start — browser multiplayer

```bash
python3 -m pip install -r requirements.txt
uvicorn web.app:app --host 0.0.0.0 --port 8000
# then open http://localhost:8000
```

One player creates a room and shares the 4-character code; everyone else joins
with it (2–6 players, plus spectators). The browser speaks exactly the same
commands as the terminal.

### Verify Installation

```bash
# Quick smoke test (non-interactive)
echo -e "ashanti\nstatus\nhelp\nquit" | python3 src/main.py

# Web layer: unit + API + WebSocket tests
python3 -m pytest tests/ -q
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
├── web/
│   ├── app.py               # FastAPI server: REST + WebSocket, room registry, turn timer
│   ├── session.py           # Server-authoritative multiplayer session (turns, fog, diplomacy)
│   └── static/              # Browser client (terminal-style UI, no build step)
├── tests/
│   └── test_web.py          # API, WebSocket, fog-of-war, diplomacy and persistence tests
├── requirements.txt         # Web server + test dependencies
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

## Multiplayer (browser)

The web layer wraps the *existing* engine — same civilisations, units, techs, combat
and map — in a server-authoritative multiplayer service.

### How it works

- **Server-authoritative.** The browser never simulates the game; it sends commands
  and renders snapshots. Turn order, resources, combat and fog are computed on the
  server, so a modified client cannot cheat.
- **Per-player snapshots.** Every connected client receives its *own* snapshot, with
  fog of war applied server-side: unexplored cells arrive with `g: null` and enemies
  only appear while inside your vision radius (4 tiles). An un-hacked client cannot
  see what it has not scouted.
- **Rooms** are created from the browser and joined with a 4-character code
  (2–6 players, unlimited spectators). Rooms are persisted as JSON under
  `var/rooms/<CODE>.json`, so a server restart resumes sessions mid-game.
- **Turns** are sequential. Each player's `end` runs the engine's `process_turn()`
  (income, training, construction, research) and passes the move on. With a turn
  timer configured, the server ends the turn automatically when it expires.
- **Diplomacy is conversational**, so it is *not* turn-gated: you can answer an
  alliance offer while another player is thinking.

### Multiplayer commands

Everything from the terminal works unchanged (`gather`, `build`, `train`, `advance`,
`research`, `move`, `list`, `status`, `map`, `help`, `end`), plus:

| Command | Effect |
|---|---|
| `attack [player]` | Attack that player's forces (default: an opponent you are at war with, else the nearest) |
| `defend [player]` | Let that player's forces attack first, then counter-attack |
| `propose alliance <player>` | Offer an alliance (they get a notice and an Accept/Reject button) |
| `accept alliance <player>` / `reject alliance <player>` | Answer an offer |
| `declare war <player>` | Declare war (breaking an alliance costs more reputation) |
| `tribute <res> <n> <player>` | Gift resources to improve relations |
| `demand <res> <n> <player>` | Demand resources — refused (and it costs reputation) unless they fear you |
| `players` | List players, ages and who is on turn |
| `/<message>` or `chat <message>` | Talk to the room |

### HTTP + WebSocket API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Liveness + room count |
| `GET` | `/api/civs` | Civilisation list for the lobby |
| `GET` | `/api/rooms` | Open rooms (lobby + in progress) |
| `POST` | `/api/rooms` | Create a room — returns `room`, `player_id`, `snapshot` |
| `POST` | `/api/rooms/{code}/join` | Join (or spectate) |
| `POST` | `/api/rooms/{code}/start` | Host starts the game (≥ 2 players) |
| `GET` | `/api/rooms/{code}/state` | Fog-adjusted snapshot for one player |
| `POST` | `/api/rooms/{code}/command` | Run a command |
| `POST` | `/api/rooms/{code}/end-turn` | End your turn |
| `POST` | `/api/rooms/{code}/chat` | Send a chat message |
| `DELETE` | `/api/rooms/{code}/leave` | Leave the room |
| `WS` | `/ws/{code}/{player_id}` | Push channel: snapshots, chat, timeouts |

`player_id` is a random token returned at create/join — it is the only credential
needed to act in a room (no accounts, no cookies).

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `AOK_HOST` / `AOK_PORT` | `0.0.0.0` / `8000` | Bind address for `python -m web.app` |
| `AOK_ROOM_DIR` | `./var/rooms` | Where persisted rooms are stored |

## Roadmap

- [x] Core game engine (civilizations, units, buildings)
- [x] Combat system with AoE2-style counters
- [x] Technology tree (15 techs)
- [x] Diplomacy system (alliances, tribute, war)
- [x] Map engine with terrain and fog of war
- [x] Campaign mode (3 scenarios)
- [x] Save/load game state
- [x] Multi-user web browser playable ([Issue #1](https://github.com/TopHermDev/age-of-kumasi/issues/1))
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
