"""Combat system — unit vs unit resolution with AoE2-style counters."""

import random
from dataclasses import dataclass
from .game import Unit


# Counter relationships (AoE2-style)
# cavalry > infantry, spears > cavalry, archers > infantry at range
COUNTER_BONUSES = {
    # (attacker_category, defender_category): damage multiplier
    ("cavalry", "infantry"): 1.5,    # Cavalry charges infantry
    ("infantry", "cavalry"): 1.4,    # Spears beat cavalry (via special)
    ("ranged", "infantry"): 1.3,     # Archers pick off infantry
}

SPECIAL_BONUSES = {
    "bonus_vs_cavalry": 1.6,  # Spearman's bonus vs cavalry
    "ranged": 1.1,            # Ranged units get slight edge
    "gunpowder": 1.2,         # Muskets extra damage
}


@dataclass
class CombatResult:
    """Result of a combat encounter."""
    attacker_name: str
    defender_name: str
    damage_dealt: int
    damage_received: int
    attacker_killed: bool
    defender_killed: bool
    narrative: str
    bonus_applied: str = ""


def resolve_combat(attacker: Unit, defender: Unit,
                   attacker_tech: dict | None = None,
                   defender_tech: dict | None = None) -> CombatResult:
    """
    Resolve combat between attacker and defender.
    
    Damage formula: attack * (1 - defense/(defense + 10)) * multiplier + randomness
    
    Counter bonuses:
    - Cavalry beats infantry: +50%
    - Spears beat cavalry: +60% (via special)
    - Archers beat infantry: +30%
    
    attacker_tech/defender_tech: optional dict of multipliers from researched techs.
    """
    atk_template = attacker.template
    def_template = defender.template
    
    # Base stats
    atk_power = atk_template.attack
    def_power = def_template.defense
    
    # Apply tech multipliers
    if attacker_tech:
        atk_power = int(atk_power * attacker_tech.get("melee_attack_mult", 1.0))
        atk_power = int(atk_power * attacker_tech.get("ranged_attack_mult", 1.0))
        atk_power = int(atk_power * attacker_tech.get("naval_attack_mult", 1.0))
    if defender_tech:
        def_power = int(def_power * defender_tech.get("melee_attack_mult", 1.0))
        def_power = int(def_power * defender_tech.get("naval_attack_mult", 1.0))
    
    defense_reduction = def_power / (def_power + 10)
    
    # Calculate multiplier from category counters
    multiplier = 1.0
    bonus_applied = ""
    
    # Check category-based counter
    counter_key = (atk_template.category, def_template.category)
    if counter_key in COUNTER_BONUSES:
        multiplier *= COUNTER_BONUSES[counter_key]
        bonus_applied = f"{atk_template.category} vs {def_template.category}"
    
    # Check special abilities
    if atk_template.special in SPECIAL_BONUSES:
        if atk_template.special == "bonus_vs_cavalry" and def_template.category == "cavalry":
            multiplier *= SPECIAL_BONUSES[atk_template.special]
            bonus_applied = f"{atk_template.name} special bonus vs cavalry"
        elif atk_template.special in ("ranged", "gunpowder"):
            if def_template.category == "infantry":
                multiplier *= SPECIAL_BONUSES[atk_template.special]
                bonus_applied = f"{atk_template.special} bonus vs infantry"
    
    # Add randomness (±20%)
    randomness = random.uniform(0.8, 1.2)
    
    # Final damage to defender
    damage_dealt = int(atk_power * (1 - defense_reduction) * multiplier * randomness)
    damage_dealt = max(1, damage_dealt)  # Minimum 1 damage
    
    # Defender counter-attacks (reduced since they're defending)
    def_multiplier = 1.0
    def_counter_key = (def_template.category, atk_template.category)
    if def_counter_key in COUNTER_BONUSES:
        def_multiplier *= COUNTER_BONUSES[def_counter_key]
    
    def_randomness = random.uniform(0.8, 1.2)
    damage_received = int(def_template.attack * (1 - atk_power / (atk_power + 10)) * def_multiplier * def_randomness * 0.7)  # Defender deals 70%
    damage_received = max(0, damage_received)
    
    # Apply damage
    defender.hp -= damage_dealt
    attacker.hp -= damage_received
    
    # Check kills
    defender_killed = defender.hp <= 0
    attacker_killed = attacker.hp <= 0
    
    # Generate narrative
    narrative_parts = []
    narrative_parts.append(f"{attacker.name} engages {defender.name}!")
    
    if bonus_applied:
        narrative_parts.append(f"  ⚔ {bonus_applied} bonus applies!")
    
    narrative_parts.append(f"  → {attacker.name} deals {damage_dealt} damage")
    narrative_parts.append(f"  → {defender.name} counters for {damage_received} damage")
    
    if defender_killed:
        narrative_parts.append(f"  ☠ {defender.name} is destroyed!")
    else:
        narrative_parts.append(f"  ♥ {defender.name} survives with {defender.hp} HP")
    
    if attacker_killed:
        narrative_parts.append(f"  ☠ {attacker.name} falls in battle!")
    else:
        narrative_parts.append(f"  ♥ {attacker.name} survives with {attacker.hp} HP")
    
    return CombatResult(
        attacker_name=attacker.name,
        defender_name=defender.name,
        damage_dealt=damage_dealt,
        damage_received=damage_received,
        attacker_killed=attacker_killed,
        defender_killed=defender_killed,
        narrative="\n".join(narrative_parts),
        bonus_applied=bonus_applied,
    )


def find_nearest_enemy(attacker: Unit, enemies: list[Unit]) -> Unit | None:
    """Find the nearest alive enemy military unit."""
    alive_enemies = [e for e in enemies if e.alive and e.template.category != "civilian"]
    if not alive_enemies:
        return None
    # Simple distance-based selection (manhattan distance)
    return min(alive_enemies, key=lambda e: abs(attacker.x - e.x) + abs(attacker.y - e.y))


def resolve_battle_round(player_units: list[Unit], enemy_units: list[Unit]) -> list[CombatResult]:
    """
    Resolve one round of battle between two armies.
    Each unit attacks once, targeting nearest enemy.
    """
    results = []
    
    # Player units attack first
    for unit in player_units:
        if not unit.alive:
            continue
        target = find_nearest_enemy(unit, enemy_units)
        if target:
            result = resolve_combat(unit, target)
            results.append(result)
    
    # Enemy units counter-attack
    for unit in enemy_units:
        if not unit.alive:
            continue
        target = find_nearest_enemy(unit, player_units)
        if target:
            result = resolve_combat(unit, target)
            results.append(result)
    
    return results


def get_battle_summary(results: list[CombatResult]) -> str:
    """Generate a summary of battle results."""
    if not results:
        return "No combat occurred."
    
    lines = ["═══════════════════════════════════════════════════",
             "  BATTLE REPORT",
             "═══════════════════════════════════════════════════"]
    
    for result in results:
        lines.append(f"\n{result.narrative}")
    
    lines.append("\n═══════════════════════════════════════════════════")
    return "\n".join(lines)
