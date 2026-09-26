"""Save and load game state using JSON serialization."""

import json
import os
from .game import (
    PlayerState, Resources, Unit, BuildingInstance,
    TrainOrder, BuildOrder, TechResearchOrder,
)
from .ai import AIPlayer
from .units import UNITS, UnitTemplate
from .buildings import BUILDINGS, BuildingTemplate
from .civilizations import CIVILIZATIONS, Civilization
from .technologies import TECHS, TechTemplate


def _find_key(d, obj):
    """Find the key in dict `d` whose value is `obj` (identity match, then name fallback)."""
    for key, val in d.items():
        if val is obj:
            return key
    for key, val in d.items():
        if hasattr(val, "name") and val.name == obj.name:
            return key
    return None


def _serialize_unit(unit: Unit) -> dict:
    return {
        "template_key": _find_key(UNITS, unit.template),
        "hp": unit.hp,
        "x": unit.x,
        "y": unit.y,
        "owner": unit.owner,
    }


def _deserialize_unit(data: dict) -> Unit:
    template_key = data["template_key"]
    if template_key not in UNITS:
        raise ValueError(f"Unknown unit template: {template_key}")
    return Unit(
        template=UNITS[template_key],
        hp=data["hp"],
        x=data["x"],
        y=data["y"],
        owner=data["owner"],
    )


def _serialize_building_instance(bld: BuildingInstance) -> dict:
    return {
        "template_key": _find_key(BUILDINGS, bld.template),
        "hp": bld.hp,
        "x": bld.x,
        "y": bld.y,
        "owner": bld.owner,
        "turns_remaining": bld.turns_remaining,
    }


def _deserialize_building_instance(data: dict) -> BuildingInstance:
    template_key = data["template_key"]
    if template_key not in BUILDINGS:
        raise ValueError(f"Unknown building template: {template_key}")
    return BuildingInstance(
        template=BUILDINGS[template_key],
        hp=data["hp"],
        x=data["x"],
        y=data["y"],
        owner=data["owner"],
        turns_remaining=data["turns_remaining"],
    )


def _serialize_train_order(order: TrainOrder) -> dict:
    return {
        "template_key": _find_key(UNITS, order.template),
        "turns_remaining": order.turns_remaining,
        "owner": order.owner,
    }


def _deserialize_train_order(data: dict) -> TrainOrder:
    template_key = data["template_key"]
    if template_key not in UNITS:
        raise ValueError(f"Unknown unit template: {template_key}")
    return TrainOrder(
        template=UNITS[template_key],
        turns_remaining=data["turns_remaining"],
        owner=data["owner"],
    )


def _serialize_build_order(order: BuildOrder) -> dict:
    return {
        "template_key": _find_key(BUILDINGS, order.template),
        "x": order.x,
        "y": order.y,
        "turns_remaining": order.turns_remaining,
        "owner": order.owner,
    }


def _deserialize_build_order(data: dict) -> BuildOrder:
    template_key = data["template_key"]
    if template_key not in BUILDINGS:
        raise ValueError(f"Unknown building template: {template_key}")
    return BuildOrder(
        template=BUILDINGS[template_key],
        x=data["x"],
        y=data["y"],
        turns_remaining=data["turns_remaining"],
        owner=data["owner"],
    )


def _serialize_tech_order(order: TechResearchOrder) -> dict:
    return {
        "template_key": _find_key(TECHS, order.template),
        "turns_remaining": order.turns_remaining,
        "owner": order.owner,
    }


def _deserialize_tech_order(data: dict) -> TechResearchOrder:
    template_key = data["template_key"]
    if template_key not in TECHS:
        raise ValueError(f"Unknown tech template: {template_key}")
    return TechResearchOrder(
        template=TECHS[template_key],
        turns_remaining=data["turns_remaining"],
        owner=data["owner"],
    )


def _serialize_resources(res: Resources) -> dict:
    return {
        "food": res.food,
        "wood": res.wood,
        "gold": res.gold,
        "kola": res.kola,
    }


def _deserialize_resources(data: dict) -> Resources:
    return Resources(
        food=data["food"],
        wood=data["wood"],
        gold=data["gold"],
        kola=data["kola"],
    )


def _serialize_civ(civ: Civilization) -> str:
    for key, c in CIVILIZATIONS.items():
        if c is civ:
            return key
    return civ.name.lower()


def _deserialize_civ(civ_key: str) -> Civilization:
    if civ_key not in CIVILIZATIONS:
        raise ValueError(f"Unknown civilization: {civ_key}")
    return CIVILIZATIONS[civ_key]


def serialize_player(player: PlayerState) -> dict:
    """Serialize a full PlayerState to a JSON-friendly dict."""
    return {
        "name": player.name,
        "civ_key": _serialize_civ(player.civ),
        "age": player.age,
        "resources": _serialize_resources(player.resources),
        "units": [_serialize_unit(u) for u in player.units],
        "buildings": [_serialize_building_instance(b) for b in player.buildings],
        "train_queue": [_serialize_train_order(o) for o in player.train_queue],
        "build_queue": [_serialize_build_order(o) for o in player.build_queue],
        "population": player.population,
        "max_population": player.max_population,
        "combat_log": list(player.combat_log) if hasattr(player, "combat_log") else [],
        "last_battle": getattr(player, "last_battle", ""),
        "researched_techs": list(player.researched_techs) if hasattr(player, "researched_techs") else [],
        "research_queue": [_serialize_tech_order(o) for o in getattr(player, "research_queue", [])],
    }


def deserialize_player(data: dict) -> PlayerState:
    """Reconstruct a PlayerState from a serialized dict."""
    civ = _deserialize_civ(data["civ_key"])
    resources = _deserialize_resources(data["resources"])
    units = [_deserialize_unit(u) for u in data["units"]]
    buildings = [_deserialize_building_instance(b) for b in data["buildings"]]
    train_queue = [_deserialize_train_order(o) for o in data["train_queue"]]
    build_queue = [_deserialize_build_order(o) for o in data["build_queue"]]
    research_queue = [_deserialize_tech_order(o) for o in data.get("research_queue", [])]

    player = PlayerState(
        name=data["name"],
        civ=civ,
        age=data["age"],
        resources=resources,
        units=units,
        buildings=buildings,
        train_queue=train_queue,
        build_queue=build_queue,
        population=data["population"],
        max_population=data["max_population"],
        combat_log=data.get("combat_log", []),
        last_battle=data.get("last_battle", ""),
        researched_techs=set(data.get("researched_techs", [])),
        research_queue=research_queue,
    )
    # Force correct pop values (don't let __post_init__ recalculate)
    player.population = data["population"]
    player.max_population = data["max_population"]
    return player


def serialize_ai(ai: AIPlayer) -> dict:
    return {
        "personality": ai.personality,
        "state": serialize_player(ai.state),
    }


def deserialize_ai(data: dict) -> AIPlayer:
    state_data = data["state"]
    civ_key = state_data["civ_key"]
    ai = AIPlayer(
        name=state_data["name"],
        civ_name=civ_key,
        personality=data["personality"],
    )
    ai.state = deserialize_player(state_data)
    return ai


def save_game(player: PlayerState, ai: AIPlayer, turn: int = 1, filepath: str = "savegame.json", diplomacy=None) -> str:
    """Save the complete game state to a JSON file."""
    save_data = {
        "version": 1,
        "turn": turn,
        "player": serialize_player(player),
        "ai": serialize_ai(ai),
    }

    # Save diplomacy state
    if diplomacy:
        save_data["diplomacy"] = {
            key: rel.to_dict() for key, rel in diplomacy.relations.items()
        }

    with open(filepath, "w") as f:
        json.dump(save_data, f, indent=2)

    return f"Game saved to {filepath}."


def load_game(filepath: str = "savegame.json") -> tuple[PlayerState, AIPlayer, int, str]:
    """Load a complete game state from a JSON file.
    
    Returns (player, ai, turn, message).
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Save file not found: {filepath}")

    with open(filepath, "r") as f:
        save_data = json.load(f)

    if save_data.get("version") != 1:
        raise ValueError("Unsupported save file version.")

    player = deserialize_player(save_data["player"])
    ai = deserialize_ai(save_data["ai"])
    turn = save_data.get("turn", 1)

    return player, ai, turn, f"Game loaded from {filepath}. Welcome back, {player.name}!"


def load_game_with_diplomacy(filepath: str = "savegame.json"):
    """Load game state including diplomacy. Returns (player, ai, turn, diplomacy, message)."""
    from .diplomacy import DiplomacyManager, DiplomacyState
    
    player, ai, turn, msg = load_game(filepath)
    
    diplomacy = DiplomacyManager()
    if "diplomacy" in json.load(open(filepath)):
        data = json.load(open(filepath))
        for key, rel_dict in data.get("diplomacy", {}).items():
            diplomacy.relations[key] = DiplomacyState.from_dict(rel_dict)
    
    return player, ai, turn, diplomacy, msg
