"""Server-authoritative multiplayer sessions for Age of Kumasi.

The CLI game in ``src/`` is single-player: one ``PlayerState`` against one AI
player, with fog of war stored on the shared ``GameMap``. This module wraps that
engine for N human players in a room:

* one ``PlayerState`` per player, sharing a single terrain map,
* per-player fog of war (own explored set) instead of the map's global fog,
* sequential turns with an optional per-turn deadline,
* player-to-player diplomacy (alliance proposals, war, tribute),
* JSON (de)serialisation so rooms survive a server restart.

The engine's ``CommandParser`` is reused for every command so the browser speaks
exactly the same command language as the terminal; the only adaptation is an
adapter object exposing ``.state`` for the engine's combat code to target.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from src.civilizations import CIVILIZATIONS, get_civ
from src.combat import find_nearest_enemy, get_battle_summary, resolve_combat
from src.commands import HELP_TEXT, CommandParser
from src.diplomacy import RelationState
from src.game import PlayerState
from src.map_engine import TERRAIN_TYPES, generate_map
from src.save_load import deserialize_player, serialize_player

#: Visibility radius around each of a player's own units and buildings.
VISIBILITY = 4

#: Where players start, in join order (corners first, then edges).
SPAWNS: list[tuple[int, int]] = [
    (1, 18),
    (18, 1),
    (1, 1),
    (18, 18),
    (9, 1),
    (9, 18),
]

MAX_PLAYERS = 6
MIN_PLAYERS = 2

LOOK_COMMANDS = {"map", "m", "view", "status", "st", "s", "help", "h", "?",
                 "list", "diplomacy", "diplo", "diplomat", "players", "who"}

#: Commands that are conversational rather than "actions", so they are allowed
#: on another player's turn (you can always answer an alliance offer).
OFF_TURN_COMMANDS = {"propose", "accept", "reject", "decline", "declare",
                     "tribute", "offer", "demand"}

RESOURCE_KEYS = ("food", "wood", "gold", "kola")

ENEMY_OWNER = "__other__"


class SessionError(Exception):
    """A user-facing problem (bad command, wrong turn, room full, ...)."""


class _OpponentAdapter:
    """Gives the engine's combat code the ``.state`` shape it expects."""

    def __init__(self, slot: "PlayerSlot"):
        self.state = slot.state
        self.name = slot.name
        self.personality = "human"


@dataclass
class PlayerSlot:
    id: str
    name: str
    civ_key: str
    is_spectator: bool = False
    is_host: bool = False
    connected: bool = True
    eliminated: bool = False
    joined_at: float = field(default_factory=time.time)
    state: PlayerState | None = None

    @property
    def ps(self) -> PlayerState:
        """The slot's game state; spectators have none."""
        if self.state is None:
            raise SessionError(f"{self.name} has no game state (spectator).")
        return self.state

    def public(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "civ": self.civ_key,
            "is_spectator": self.is_spectator,
            "is_host": self.is_host,
            "connected": self.connected,
            "eliminated": self.eliminated,
            "age": self.state.age if self.state else 1,
            "population": self.state.population if self.state else 0,
        }


@dataclass
class Session:
    """One game room."""

    code: str
    max_players: int = 4
    turn_seconds: int = 60
    map_seed: int | None = None
    created_at: float = field(default_factory=time.time)

    state: str = "lobby"  # lobby | active | finished
    players: dict[str, PlayerSlot] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    turn_index: int = 0
    turn_number: int = 1
    turn_deadline: float | None = None
    winner: str | None = None

    log: list[dict] = field(default_factory=list)
    chat: list[dict] = field(default_factory=list)
    proposals: dict[str, dict] = field(default_factory=dict)  # "from>to" -> proposal
    relations: dict[str, dict] = field(default_factory=dict)  # "a|b" sorted -> {state, reputation}
    explored: dict[str, list[str]] = field(default_factory=dict)  # player_id -> ["x,y", ...]
    seq: int = 0
    last_activity: float = field(default_factory=time.time)

    game_map: Any = None

    # ------------------------------------------------------------------ setup

    def __post_init__(self) -> None:
        if self.game_map is None:
            self.game_map = generate_map(self.map_seed)

    # ---- players ---------------------------------------------------------

    def add_player(self, name: str, civ_key: str, spectator: bool = False) -> PlayerSlot:
        name = (name or "").strip()
        if not name:
            raise SessionError("Choose a player name.")
        if len(name) > 20:
            raise SessionError("Player name is too long (max 20 characters).")
        if any(p.name.lower() == name.lower() for p in self.players.values()):
            raise SessionError(f"The name '{name}' is already taken in this room.")
        if civ_key not in CIVILIZATIONS:
            raise SessionError(f"Unknown civilization '{civ_key}'.")
        if not spectator and self.state != "lobby":
            raise SessionError("This game has already started — join as a spectator instead.")
        humans = [p for p in self.players.values() if not p.is_spectator]
        if not spectator and len(humans) >= self.max_players:
            raise SessionError("This room is full.")

        slot = PlayerSlot(
            id=secrets.token_urlsafe(9),
            name=name,
            civ_key=civ_key,
            is_spectator=spectator,
            is_host=not any(p.is_host for p in self.players.values()),
        )
        if not spectator:
            sx, sy = SPAWNS[len(humans) % len(SPAWNS)]
            slot.state = PlayerState(name=name, civ=get_civ(civ_key), spawn_x=sx, spawn_y=sy)
            self.order.append(slot.id)
            self.explored[slot.id] = []
            self._refresh_fog(slot.id)
        self.players[slot.id] = slot
        self._log("system", None, f"{name} joined as {'spectator' if spectator else civ_key.title()}.")
        return slot

    def remove_player(self, player_id: str) -> None:
        slot = self.players.pop(player_id, None)
        if not slot:
            return
        if player_id in self.order:
            idx = self.order.index(player_id)
            self.order.remove(player_id)
            if idx < self.turn_index:
                self.turn_index -= 1
            self.turn_index = max(0, min(self.turn_index, len(self.order) - 1)) if self.order else 0
        self.explored.pop(player_id, None)
        self._log("system", None, f"{slot.name} left the room.")
        if self.state == "active":
            self._check_victory()

    def set_connected(self, player_id: str, connected: bool) -> None:
        slot = self.players.get(player_id)
        if slot and slot.connected != connected:
            slot.connected = connected
            self._log("system", slot.name, f"{slot.name} {'reconnected' if connected else 'disconnected'}.")

    def host(self) -> PlayerSlot | None:
        for slot in self.players.values():
            if slot.is_host:
                return slot
        return None

    # ---- lifecycle -------------------------------------------------------

    def start(self, player_id: str) -> None:
        slot = self.players.get(player_id)
        if not slot or not slot.is_host:
            raise SessionError("Only the host can start the game.")
        if self.state != "lobby":
            raise SessionError("The game has already started.")
        if len(self.order) < MIN_PLAYERS:
            raise SessionError(f"At least {MIN_PLAYERS} players are needed to start.")
        self.state = "active"
        self.turn_index = 0
        self.turn_number = 1
        for pid in self.order:
            self._refresh_fog(pid)
            for unit in self.players[pid].ps.units:
                unit.reset_moves()
        self._reset_deadline()
        active = self.players[self.order[0]]
        self._log("system", None, f"The game begins. {active.name} moves first.")

    def end_turn(self, player_id: str | None = None, reason: str = "ended turn") -> None:
        if self.state != "active":
            raise SessionError("The game is not active.")
        active_id = self.active_player_id
        if player_id is not None and player_id != active_id:
            raise SessionError("It is not your turn.")

        current = self.players[active_id]
        messages = current.ps.process_turn()
        for msg in messages:
            self._log("action", current.name, msg)

        self._check_victory()
        if self.state != "active":
            return

        self.turn_index = (self.turn_index + 1) % len(self.order)
        if self.turn_index == 0:
            self.turn_number += 1
            self._decay_diplomacy()

        nxt = self.players[self.order[self.turn_index]]
        for unit in nxt.ps.units:
            unit.reset_moves()
        self._refresh_fog(nxt.id)
        self._reset_deadline()
        self._log("system", None, f"{current.name} {reason}. {nxt.name}'s turn (turn {self.turn_number}).")

    def _reset_deadline(self) -> None:
        self.turn_deadline = (
            time.time() + self.turn_seconds if self.turn_seconds and self.turn_seconds > 0 else None
        )

    def seconds_left(self) -> float | None:
        if not self.turn_deadline:
            return None
        return max(0.0, round(self.turn_deadline - time.time(), 1))

    def expired(self) -> bool:
        return self.turn_deadline is not None and time.time() >= self.turn_deadline

    @property
    def active_player_id(self) -> str | None:
        if self.state != "active" or not self.order:
            return None
        return self.order[self.turn_index % len(self.order)]

    def _check_victory(self) -> None:
        survivors = []
        for pid in list(self.order):
            slot = self.players.get(pid)
            if not slot or not slot.state:
                continue
            alive = slot.state.get_alive_units() or slot.state.get_alive_buildings()
            if not alive and not slot.eliminated:
                slot.eliminated = True
                self._log("system", None, f"{slot.name} has been eliminated.")
            if not slot.eliminated:
                survivors.append(slot)
        if len(survivors) <= 1 and len(self.order) >= MIN_PLAYERS:
            self.state = "finished"
            self.turn_deadline = None
            if survivors:
                self.winner = survivors[0].id
                self._log("system", None, f"{survivors[0].name} wins the Gold Coast!")
            else:
                self._log("system", None, "Everyone has fallen. No winner.")

    # ---- diplomacy -------------------------------------------------------

    def _rel_key(self, a: str, b: str) -> str:
        return "|".join(sorted((a, b)))

    def relation(self, a: str, b: str) -> dict:
        key = self._rel_key(a, b)
        rel = self.relations.setdefault(key, {"state": RelationState.NEUTRAL.value, "reputation": 0})
        return rel

    def _set_relation(self, a: str, b: str, state: RelationState, delta_rep: int = 0) -> dict:
        rel = self.relation(a, b)
        rel["state"] = state.value
        rel["reputation"] = max(-100, min(100, rel["reputation"] + delta_rep))
        return rel

    def _decay_diplomacy(self) -> None:
        for rel in self.relations.values():
            if rel["state"] == RelationState.NEUTRAL.value and rel["reputation"] > 0:
                rel["reputation"] = max(0, rel["reputation"] - 1)

    def _resolve_target(self, actor_id: str, name: str | None) -> PlayerSlot:
        others = [
            p for p in self.players.values()
            if p.id != actor_id and not p.is_spectator and p.state and not p.eliminated
        ]
        if not others:
            raise SessionError("There are no other players to act against.")
        if name:
            wanted = name.lower()
            for slot in others:
                if slot.name.lower() == wanted or slot.name.lower().startswith(wanted):
                    return slot
            raise SessionError(f"No player named '{name}' in this game.")
        # Default: an opponent we are at war with, else the nearest one.
        actor = self.players[actor_id]
        for slot in others:
            if self.relation(actor_id, slot.id)["state"] == RelationState.AT_WAR.value:
                return slot
        units = actor.ps.get_alive_units()
        if not units:
            return others[0]
        anchor = units[0]

        def distance(slot: PlayerSlot) -> int:
            enemy_units = slot.ps.get_alive_units()
            if not enemy_units:
                return 999
            return min(
                abs(anchor.x - u.x) + abs(anchor.y - u.y) for u in enemy_units
            )

        return min(others, key=distance)

    # ---- commands --------------------------------------------------------

    def execute(self, player_id: str, raw: str) -> list[dict]:
        """Run one command for a player. Returns the log entries it produced."""
        slot = self.players.get(player_id)
        if not slot:
            raise SessionError("You are not in this room.")
        raw = (raw or "").strip()
        if not raw:
            return []
        if self.state == "lobby":
            raise SessionError("The game has not started yet.")
        if self.state == "finished":
            raise SessionError("This game is over.")

        before = len(self.log)
        cmd = raw.split()[0].lower()
        args = raw.split()[1:]

        is_look = cmd in LOOK_COMMANDS
        is_chat = cmd == "chat" or raw.startswith("/")
        # Diplomacy is conversational: proposals can be made, answered, and
        # tributes sent at any time, not only on your own turn.
        is_diplomacy = cmd in OFF_TURN_COMMANDS

        if (
            not slot.is_spectator
            and not (is_look or is_chat or is_diplomacy)
            and player_id != self.active_player_id
        ):
            raise SessionError("It is not your turn.")

        if slot.is_spectator and not (is_look or is_chat):
            raise SessionError("Spectators can only look: map, status, players, diplomacy, help — and chat.")

        if cmd.startswith("/") or cmd == "chat":
            text = raw[1:] if raw.startswith("/") else " ".join(args)
            self.send_chat(player_id, text, kind="chat")
            return self.log[before:]

        # --- session-level commands ---------------------------------------
        if cmd in {"players", "who"}:
            self._log("notice", slot.name, self._players_summary())
            return self.log[before:]

        if cmd in {"end", "next", "done", "turn", "e", "n"}:
            self.end_turn(player_id)
            return self.log[before:]

        if cmd in {"attack", "fight", "battle", "defend", "def"}:
            target = self._resolve_target(player_id, args[0] if args else None)
            self._require_not_allied(slot, target)
            self._log("action", slot.name, f"{slot.name} → {target.name}: {cmd}")
            parser = CommandParser(
                player=slot.ps,
                ai=_OpponentAdapter(target),
                diplomacy=None,
                turn=self.turn_number,
                game_map=self.game_map,
            )
            text, _ = parser.parse("attack" if cmd in {"attack", "fight", "battle"} else "defend")
            self._log("battle", slot.name, text)
            self._sync_after_combat(slot, target)
            self._check_victory()
            return self.log[before:]

        if cmd == "propose":
            target = self._resolve_target(player_id, args[1] if len(args) > 1 else (args[0] if args else None))
            self._propose_alliance(slot, target)
            return self.log[before:]

        if cmd in {"accept", "reject", "decline"}:
            target = self._resolve_target(player_id, args[1] if len(args) > 1 else (args[0] if args else None))
            self._answer_proposal(slot, target, accept=cmd == "accept")
            return self.log[before:]

        if cmd == "declare":
            target = self._resolve_target(player_id, args[1] if len(args) > 1 else (args[0] if args else None))
            self._declare_war(slot, target)
            return self.log[before:]

        if cmd in {"tribute", "offer", "demand"}:
            self._tribute(slot, args, demand=(cmd == "demand"))
            return self.log[before:]

        if cmd == "diplomacy" or cmd.startswith("diplo"):
            self._log("notice", slot.name, self._diplomacy_report(slot))
            return self.log[before:]

        if cmd in {"save", "load"}:
            self._log("notice", slot.name,
                      "Multiplayer games save automatically — the room survives restarts. "
                      "Continue with normal commands.")
            return self.log[before:]

        # --- engine commands ----------------------------------------------
        if cmd in {"map", "m", "view"}:
            self._log("notice", slot.name, self.render_ascii(player_id))
            return self.log[before:]

        try:
            target = self._resolve_target(player_id, None)
            ai = _OpponentAdapter(target)
        except SessionError:
            ai = None
        parser = CommandParser(
            player=slot.ps,
            ai=ai,
            diplomacy=None,
            turn=self.turn_number,
            game_map=self.game_map,
        )
        if cmd in {"status", "st", "s"}:
            text = self.status_text(player_id)
        elif cmd in {"help", "h", "?"}:
            text = HELP_TEXT + "\nMULTIPLAYER EXTRA COMMANDS:\n" \
                "  attack [player]           — Attack a player (default: nearest / at war)\n" \
                "  defend [player]           — Defend against a player's forces\n" \
                "  propose alliance <player> — Offer an alliance\n" \
                "  accept alliance <player>  — Accept an incoming proposal\n" \
                "  reject alliance <player>  — Decline an incoming proposal\n" \
                "  declare war <player>      — Declare war\n" \
                "  tribute <res> <n> <player>— Gift resources\n" \
                "  demand <res> <n> <player> — Demand resources (risky)\n" \
                "  /<message>                — Chat to the room\n" \
                "  players                   — List players and standings\n"
        else:
            text, _ = parser.parse(raw)
        self._log("action", slot.name, text)
        self._refresh_fog(player_id)
        return self.log[before:]

    def _require_not_allied(self, actor: PlayerSlot, target: PlayerSlot) -> None:
        if self.relation(actor.id, target.id)["state"] == RelationState.ALLIED.value:
            raise SessionError(
                f"You are allied with {target.name}. Declare war first if you want to break it."
            )

    def _sync_after_combat(self, actor: PlayerSlot, target: PlayerSlot) -> None:
        for slot in (actor, target):
            slot.ps.units = [u for u in slot.ps.units if u.alive]
            slot.ps._update_pop()
            self._refresh_fog(slot.id)
        self.relations.setdefault(self._rel_key(actor.id, target.id), {"reputation": 0})
        if self.relation(actor.id, target.id)["state"] == RelationState.NEUTRAL.value:
            self._set_relation(actor.id, target.id, RelationState.AT_WAR, -10)
            self._log("system", None, f"{actor.name} and {target.name} are now at war.")

    def _propose_alliance(self, actor: PlayerSlot, target: PlayerSlot) -> None:
        rel = self.relation(actor.id, target.id)
        if rel["state"] == RelationState.ALLIED.value:
            raise SessionError(f"You are already allied with {target.name}.")
        self.proposals[f"{actor.id}>{target.id}"] = {
            "from": actor.id,
            "to": target.id,
            "turn": self.turn_number,
        }
        self._log("system", actor.name,
                  f"{actor.name} proposes an alliance to {target.name}.")
        self._log("notice", target.name,
                  f"{actor.name} proposes an alliance. Type: accept alliance {actor.name}")

    def _answer_proposal(self, actor: PlayerSlot, other: PlayerSlot, accept: bool) -> None:
        key = f"{other.id}>{actor.id}"
        if key not in self.proposals:
            raise SessionError(f"{other.name} has not proposed an alliance to you.")
        self.proposals.pop(key, None)
        if accept:
            self._set_relation(actor.id, other.id, RelationState.ALLIED, 10)
            self._log("system", None, f"{actor.name} and {other.name} are now allied.")
        else:
            self._set_relation(actor.id, other.id, RelationState.HOSTILE, -5)
            self._log("system", None, f"{actor.name} rejected {other.name}'s alliance proposal.")

    def _declare_war(self, actor: PlayerSlot, target: PlayerSlot) -> None:
        rel = self.relation(actor.id, target.id)
        penalty = -40 if rel["state"] == RelationState.ALLIED.value else -20
        self.proposals.pop(f"{actor.id}>{target.id}", None)
        self.proposals.pop(f"{target.id}>{actor.id}", None)
        self._set_relation(actor.id, target.id, RelationState.AT_WAR, penalty)
        self._log("system", None, f"{actor.name} declares war on {target.name}.")

    def _tribute(self, actor: PlayerSlot, args: list[str], demand: bool = False) -> None:
        if len(args) < 3:
            raise SessionError("Usage: tribute <food|wood|gold|kola> <amount> <player>")
        resource, amount_raw, who = args[0].lower(), args[1], " ".join(args[2:])
        if resource not in RESOURCE_KEYS:
            raise SessionError(f"Unknown resource '{resource}'. Use food, wood, gold or kola.")
        try:
            amount = int(amount_raw)
        except ValueError:
            raise SessionError("The amount must be a whole number.")
        if amount <= 0:
            raise SessionError("The amount must be greater than zero.")
        target = self._resolve_target(actor.id, who)

        if demand:
            rel = self.relation(actor.id, target.id)
            if rel["state"] == RelationState.ALLIED.value:
                raise SessionError("You cannot demand tribute from an ally.")
            willing = rel["reputation"] <= -20 or target.ps.resources.__dict__[resource] < amount
            if not willing:
                self._set_relation(actor.id, target.id, RelationState.HOSTILE, -15)
                self._log("system", None,
                          f"{target.name} refuses {actor.name}'s demand for {amount} {resource}.")
                return
            taken = min(amount, target.ps.resources.__dict__[resource])
            target.ps.resources.spend({resource: taken})
            actor.ps.resources.earn({resource: taken})
            self._set_relation(actor.id, target.id, RelationState.AT_WAR, -15)
            self._log("system", None,
                      f"{actor.name} seizes {taken} {resource} from {target.name} — war!")
            return

        if not actor.ps.resources.spend({resource: amount}):
            raise SessionError(f"You cannot afford {amount} {resource}.")
        target.ps.resources.earn({resource: amount})
        self._set_relation(actor.id, target.id, RelationState.NEUTRAL, 8)
        self._log("system", None, f"{actor.name} gifts {amount} {resource} to {target.name}.")

    # ---- log / chat ------------------------------------------------------

    def _log(self, kind: str, actor: str | None, text: str) -> dict:
        self.seq += 1
        self.last_activity = time.time()
        entry = {
            "seq": self.seq,
            "kind": kind,
            "actor": actor,
            "text": text,
            "turn": self.turn_number,
            "ts": round(time.time(), 3),
        }
        self.log.append(entry)
        if len(self.log) > 500:
            self.log = self.log[-400:]
        return entry

    def send_chat(self, player_id: str, text: str, kind: str = "chat") -> dict:
        slot = self.players.get(player_id)
        if not slot:
            raise SessionError("You are not in this room.")
        text = (text or "").strip()
        if not text:
            raise SessionError("Say something first.")
        if len(text) > 500:
            text = text[:500] + "…"
        self.seq += 1
        entry = {
            "seq": self.seq,
            "kind": kind,
            "actor": slot.name,
            "text": text,
            "turn": self.turn_number,
            "ts": round(time.time(), 3),
        }
        self.chat.append(entry)
        if len(self.chat) > 300:
            self.chat = self.chat[-200:]
        return entry

    # ---- fog / map -------------------------------------------------------

    def _visible_cells(self, player_id: str) -> set[str]:
        slot = self.players.get(player_id)
        if not slot or not slot.state:
            return set()
        cells: set[str] = set()
        sources: list[tuple[int, int]] = []
        for unit in slot.state.get_alive_units():
            sources.append((unit.x, unit.y))
        for building in slot.state.get_alive_buildings():
            sources.append((building.x, building.y))
        for sx, sy in sources:
            for dx in range(-VISIBILITY, VISIBILITY + 1):
                for dy in range(-VISIBILITY, VISIBILITY + 1):
                    nx, ny = sx + dx, sy + dy
                    if self.game_map.in_bounds(nx, ny):
                        cells.add(f"{nx},{ny}")
        return cells

    def _refresh_fog(self, player_id: str) -> None:
        known = set(self.explored.get(player_id, []))
        known |= self._visible_cells(player_id)
        self.explored[player_id] = sorted(known)

    def occupancy(self) -> dict[str, dict]:
        """cell key -> {owner_id, kind, category} for every unit/building."""
        cells: dict[str, dict] = {}
        for slot in self.players.values():
            if not slot.state:
                continue
            for unit in slot.state.get_alive_units():
                cells[f"{unit.x},{unit.y}"] = {
                    "owner_id": slot.id,
                    "kind": "unit",
                    "category": getattr(unit.template, "category", ""),
                    "name": unit.name,
                }
            for building in slot.state.get_alive_buildings():
                cells[f"{building.x},{building.y}"] = {
                    "owner_id": slot.id,
                    "kind": "building",
                    "category": "building",
                    "name": building.name,
                }
        return cells

    def map_payload(self, viewer_id: str | None) -> dict:
        """Fog-aware grid for one viewer (``None`` = spectator sees everything)."""
        viewer = self.players.get(viewer_id) if viewer_id else None
        spectator = viewer is None or viewer.is_spectator
        explored = set(self.explored.get(viewer_id, [])) if viewer_id else set()
        visible = self._visible_cells(viewer_id) if viewer_id else set()
        occ = self.occupancy()
        allies = {
            self._rel_key(viewer_id, other.id)
            for other in self.players.values()
            if viewer_id and self.relation(viewer_id, other.id)["state"] == RelationState.ALLIED.value
        }

        rows = []
        for y in range(self.game_map.height):
            row = []
            for x in range(self.game_map.width):
                key = f"{x},{y}"
                cell = self.game_map.get_cell(x, y)
                symbol = TERRAIN_TYPES.get(cell.terrain, {}).get("symbol", "?") if cell else "?"
                if not spectator and key not in explored:
                    row.append({"g": None, "o": None, "f": "unseen"})
                    continue
                occupant = occ.get(key) if (spectator or key in visible) else None
                owner = None
                if occupant and viewer_id:
                    if occupant["owner_id"] == viewer_id:
                        owner = "self"
                    elif self._rel_key(viewer_id, occupant["owner_id"]) in allies:
                        owner = "ally"
                    else:
                        owner = "enemy"
                elif occupant:
                    owner = "enemy"
                fog = "visible" if (spectator or key in visible) else "explored"
                row.append({"g": symbol, "o": owner, "f": fog})
            rows.append(row)

        return {"width": self.game_map.width, "height": self.game_map.height, "rows": rows}

    def render_ascii(self, viewer_id: str | None, show_full: bool = False) -> str:
        payload = self.map_payload(viewer_id if not show_full else None)
        header = "    " + "".join(f"{x % 10}" for x in range(payload["width"]))
        lines = [header]
        for y, row in enumerate(payload["rows"]):
            cells = []
            for x, cell in enumerate(row):
                if cell["f"] == "unseen" and not show_full:
                    cells.append(" ")
                elif cell["o"] == "self":
                    cells.append("P")
                elif cell["o"] == "ally":
                    cells.append("A")
                elif cell["o"] == "enemy":
                    cells.append("E")
                else:
                    cells.append(cell["g"] or " ")
            lines.append(f"{y:>3} " + "".join(cells))
        lines.append("")
        lines.append("  Legend: P you  A ally  E enemy  · ~ coast  . savanna  T forest  G gold  K kola  V village")
        return "\n".join(lines)

    # ---- status ----------------------------------------------------------

    def status_text(self, viewer_id: str) -> str:
        slot = self.players[viewer_id]
        if slot.is_spectator:
            return self._players_summary()
        st = slot.ps
        units: dict[str, int] = {}
        for unit in st.get_alive_units():
            units[unit.name] = units.get(unit.name, 0) + 1
        buildings: dict[str, int] = {}
        for building in st.get_alive_buildings():
            buildings[building.name] = buildings.get(building.name, 0) + 1
        lines = [
            f"═══ {slot.name} — {st.civ.name} — {st.age_name} ═══",
            f"Population: {st.population}/{st.max_population}   Turn {self.turn_number}",
            f"Resources: {st.resources.format()}",
            f"Units: {', '.join(f'{k} x{v}' for k, v in units.items()) or 'none'}",
            f"Buildings: {', '.join(f'{k} x{v}' for k, v in buildings.items()) or 'none'}",
        ]
        active = self.players.get(self.active_player_id or "")
        lines.append(f"Active player: {active.name if active else '—'}")
        return "\n".join(lines)

    def _players_summary(self) -> str:
        lines = ["Players in this room:"]
        for slot in self.players.values():
            if slot.is_spectator:
                lines.append(f"  {slot.name} (spectator)")
                continue
            marker = "→" if slot.id == self.active_player_id else " "
            status = "eliminated" if slot.eliminated else f"pop {slot.ps.population}"
            lines.append(
                f" {marker} {slot.name} — {slot.civ_key.title()} — age {slot.state.age} — {status}"
                + ("" if slot.connected else " (offline)")
            )
        return "\n".join(lines)

    def _diplomacy_report(self, slot: PlayerSlot) -> str:
        lines = ["Diplomacy:"]
        for other in self.players.values():
            if other.id == slot.id or other.is_spectator:
                continue
            rel = self.relation(slot.id, other.id)
            proposal = " — alliance proposed by you" if f"{slot.id}>{other.id}" in self.proposals else ""
            if f"{other.id}>{slot.id}" in self.proposals:
                proposal = " — proposes an alliance to you"
            lines.append(
                f"  {other.name}: {rel['state'].replace('_', ' ')} (reputation {rel['reputation']}){proposal}"
            )
        return "\n".join(lines)

    # ---- snapshot --------------------------------------------------------

    def snapshot(self, viewer_id: str | None) -> dict:
        viewer = self.players.get(viewer_id) if viewer_id else None
        active = self.players.get(self.active_player_id or "")

        you = None
        if viewer:
            slots_units: dict[str, dict] = {}
            if viewer.state:
                for unit in viewer.state.get_alive_units():
                    entry = slots_units.setdefault(
                        unit.name, {"name": unit.name, "count": 0,
                                    "category": getattr(unit.template, "category", "")}
                    )
                    entry["count"] += 1
            buildings: dict[str, int] = {}
            if viewer.state:
                for building in viewer.state.get_alive_buildings():
                    buildings[building.name] = buildings.get(building.name, 0) + 1
            you = {
                "id": viewer.id,
                "name": viewer.name,
                "civ": viewer.civ_key,
                "is_host": viewer.is_host,
                "is_spectator": viewer.is_spectator,
                "eliminated": viewer.eliminated,
                "age": viewer.state.age if viewer.state else 1,
                "age_name": viewer.state.age_name() if viewer.state else "—",
                "resources": (
                    {
                        "food": viewer.state.resources.food,
                        "wood": viewer.state.resources.wood,
                        "gold": viewer.state.resources.gold,
                        "kola": viewer.state.resources.kola,
                    }
                    if viewer.state else {}
                ),
                "population": viewer.state.population if viewer.state else 0,
                "max_population": viewer.state.max_population if viewer.state else 0,
                "units": list(slots_units.values()),
                "buildings": [{"name": k, "count": v} for k, v in sorted(buildings.items())],
                "status_text": self.status_text(viewer.id) if viewer.state else "",
            }

        diplomacy = []
        if viewer:
            for other in self.players.values():
                if other.id == viewer.id:
                    continue
                rel = self.relation(viewer.id, other.id) if not viewer.is_spectator else {
                    "state": "unknown", "reputation": 0
                }
                proposal = None
                if f"{other.id}>{viewer.id}" in self.proposals:
                    proposal = "incoming"
                elif f"{viewer.id}>{other.id}" in self.proposals:
                    proposal = "outgoing"
                diplomacy.append({
                    "player_id": other.id,
                    "name": other.name,
                    "relation": rel["state"],
                    "reputation": rel["reputation"],
                    "proposal": proposal,
                })

        return {
            "code": self.code,
            "state": self.state,
            "settings": {
                "max_players": self.max_players,
                "turn_seconds": self.turn_seconds,
                "map_seed": self.map_seed,
            },
            "turn": {
                "number": self.turn_number,
                "active_player_id": self.active_player_id,
                "active_player_name": active.name if active else None,
                "seconds_left": self.seconds_left(),
                "deadline": self.turn_deadline,
                "order": [
                    {"id": self.players[pid].id, "name": self.players[pid].name}
                    for pid in self.order if pid in self.players
                ],
            },
            "you": you,
            "players": [slot.public() for slot in self.players.values()],
            "map": self.map_payload(viewer_id),
            "diplomacy": diplomacy,
            "log": self.log[-100:],
            "chat": self.chat[-100:],
            "winner": self.players[self.winner].name if self.winner and self.winner in self.players else None,
        }

    def summary(self) -> dict:
        humans = [p for p in self.players.values() if not p.is_spectator]
        return {
            "code": self.code,
            "state": self.state,
            "players": len(humans),
            "max_players": self.max_players,
            "spectators": len(self.players) - len(humans),
            "turn_seconds": self.turn_seconds,
            "created_at": self.created_at,
            "host": (self.host().name if self.host() else None),
        }

    # ---- persistence -----------------------------------------------------

    def to_dict(self) -> dict:
        terrain = [
            [self.game_map.cells[y][x].terrain for x in range(self.game_map.width)]
            for y in range(self.game_map.height)
        ]
        players = {}
        for pid, slot in self.players.items():
            players[pid] = {
                "id": slot.id,
                "name": slot.name,
                "civ_key": slot.civ_key,
                "is_spectator": slot.is_spectator,
                "is_host": slot.is_host,
                "connected": slot.connected,
                "eliminated": slot.eliminated,
                "joined_at": slot.joined_at,
                "state": serialize_player(slot.state) if slot.state else None,
            }
        return {
            "code": self.code,
            "max_players": self.max_players,
            "turn_seconds": self.turn_seconds,
            "map_seed": self.map_seed,
            "created_at": self.created_at,
            "state": self.state,
            "players": players,
            "order": list(self.order),
            "turn_index": self.turn_index,
            "turn_number": self.turn_number,
            "turn_deadline": self.turn_deadline,
            "winner": self.winner,
            "log": self.log[-200:],
            "chat": self.chat[-100:],
            "proposals": self.proposals,
            "relations": self.relations,
            "explored": self.explored,
            "seq": self.seq,
            "last_activity": self.last_activity,
            "terrain": terrain,
            "width": self.game_map.width,
            "height": self.game_map.height,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        session = cls(
            code=data["code"],
            max_players=data.get("max_players", 4),
            turn_seconds=data.get("turn_seconds", 60),
            map_seed=data.get("map_seed"),
            created_at=data.get("created_at", time.time()),
        )
        for y, row in enumerate(data.get("terrain", [])):
            for x, terrain in enumerate(row):
                session.game_map.set_terrain(x, y, terrain)
        for pid, pdata in data.get("players", {}).items():
            slot = PlayerSlot(
                id=pdata["id"],
                name=pdata["name"],
                civ_key=pdata["civ_key"],
                is_spectator=pdata.get("is_spectator", False),
                is_host=pdata.get("is_host", False),
                connected=pdata.get("connected", True),
                eliminated=pdata.get("eliminated", False),
                joined_at=pdata.get("joined_at", time.time()),
                state=deserialize_player(pdata["state"]) if pdata.get("state") else None,
            )
            session.players[pid] = slot
        session.state = data.get("state", "lobby")
        session.order = [pid for pid in data.get("order", []) if pid in session.players]
        session.turn_index = data.get("turn_index", 0)
        session.turn_number = data.get("turn_number", 1)
        session.turn_deadline = data.get("turn_deadline")
        session.winner = data.get("winner")
        session.log = data.get("log", [])
        session.chat = data.get("chat", [])
        session.proposals = data.get("proposals", {})
        session.relations = data.get("relations", {})
        session.explored = data.get("explored", {})
        session.seq = data.get("seq", 0)
        session.last_activity = data.get("last_activity", time.time())
        return session
