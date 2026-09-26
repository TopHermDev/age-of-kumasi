"""Diplomacy system — alliances, tribute, and reputation for Age of Kumasi."""

import random
from dataclasses import dataclass, field
from enum import Enum


class RelationState(Enum):
    NEUTRAL = "neutral"
    ALLIED = "allied"
    HOSTILE = "hostile"
    AT_WAR = "at_war"


# Reputation thresholds for state changes
REP_ALLY_ACCEPT_MIN = 30
REP_WAR_DECALARATION_COST = -20
REP_ALLIANCE_BREAK_PENALTY = -40
REP_TRIBUTE_GIFT_BASE = 10
REP_TRIBUTE_DEMAND_BASE = -15
REP_WAR_REDUCTION = -50


@dataclass
class DiplomacyState:
    """Tracks the diplomatic relationship between player and AI."""
    state: RelationState = RelationState.NEUTRAL
    reputation: int = 0  # -100 to 100, 0 is neutral
    tribute_sent: int = 0  # total tribute given
    tribute_received: int = 0  # total tribute demanded/received
    alliance_turns: int = 0  # how many turns allied
    war_turns: int = 0  # how many turns at war
    broken_alliances: int = 0  # times alliance was broken

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "reputation": self.reputation,
            "tribute_sent": self.tribute_sent,
            "tribute_received": self.tribute_received,
            "alliance_turns": self.alliance_turns,
            "war_turns": self.war_turns,
            "broken_alliances": self.broken_alliances,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DiplomacyState":
        return cls(
            state=RelationState(d.get("state", "neutral")),
            reputation=d.get("reputation", 0),
            tribute_sent=d.get("tribute_sent", 0),
            tribute_received=d.get("tribute_received", 0),
            alliance_turns=d.get("alliance_turns", 0),
            war_turns=d.get("war_turns", 0),
            broken_alliances=d.get("broken_alliances", 0),
        )

    def clamp_reputation(self):
        self.reputation = max(-100, min(100, self.reputation))


class DiplomacyManager:
    """Manages diplomatic relations between the player and AI."""

    def __init__(self):
        self.relations: dict[str, DiplomacyState] = {}

    def get_relation(self, entity_key: str) -> DiplomacyState:
        if entity_key not in self.relations:
            self.relations[entity_key] = DiplomacyState()
        return self.relations[entity_key]

    def propose_alliance(self, entity_key: str, player_resources, personality: str) -> str:
        """Player proposes an alliance with the AI."""
        rel = self.get_relation(entity_key)

        if rel.state == RelationState.ALLIED:
            return "You are already allied. No need to renew the bond."
        if rel.state == RelationState.AT_WAR:
            return (
                "The drums of war still echo. The enemy refuses your overtures.\n"
                "End the war first, or wait for the fires to cool."
            )
        if rel.state == RelationState.HOSTILE:
            return (
                "Relations are hostile. Send tribute to mend the bridge\n"
                "before proposing alliance."
            )

        # AI acceptance depends on personality and reputation
        acceptance_chance = 0.5  # base 50%
        if personality == "defensive":
            acceptance_chance = 0.75  # defensive AI likes alliances
        elif personality == "aggressive":
            acceptance_chance = 0.25  # aggressive AI resists
        elif personality == "trader":
            acceptance_chance = 0.6  # trader is moderate

        # Reputation modifier
        acceptance_chance += rel.reputation / 200.0

        # Player has military strength? Helps
        if hasattr(player_resources, 'units'):
            military_count = sum(
                1 for u in player_resources.units
                if u.alive and u.template.category != "civilian"
            )
            if military_count > 3:
                acceptance_chance += 0.1

        if random.random() < acceptance_chance:
            rel.state = RelationState.ALLIED
            rel.reputation += 10
            rel.clamp_reputation()
            rel.alliance_turns = 0
            personality_response = _alliance_accept_text(personality)
            return (
                f"The {entity_key.title()} accept your alliance!\n"
                f"{personality_response}\n"
                f"A shared drum beats for peace."
            )
        else:
            personality_response = _alliance_reject_text(personality)
            return (
                f"The {entity_key.title()} decline your proposal.\n"
                f"{personality_response}"
            )

    def declare_war(self, entity_key: str, player_resources) -> str:
        """Player declares war on the AI."""
        rel = self.get_relation(entity_key)

        if rel.state == RelationState.AT_WAR:
            return "You are already at war with the enemy!"
        if rel.state == RelationState.ALLIED:
            # Breaking alliance has consequences
            rel.broken_alliances += 1
            rel.reputation += REP_ALLIANCE_BREAK_PENALTY
            rel.clamp_reputation()

        rel.state = RelationState.AT_WAR
        rel.reputation += REP_WAR_DECALARATION_COST
        rel.clamp_reputation()
        rel.war_turns = 0

        if rel.broken_alliances > 0:
            return (
                "You break the alliance and declare war!\n"
                f"Your reputation suffers. (-{abs(REP_ALLIANCE_BREAK_PENALTY)} reputation)\n"
                "The drums beat war. The {entity_key} prepare for battle."
            )
        return (
            f"War drums echo across the Gold Coast!\n"
            f"You declare war on the {entity_key.title()}!\n"
            "The enemy mobilizes for battle."
        )

    def offer_tribute(
        self, entity_key: str, resource: str, amount: int, player_resources
    ) -> str:
        """Player offers tribute (gifts) to improve relations."""
        rel = self.get_relation(entity_key)

        if rel.state == RelationState.AT_WAR:
            return (
                "The enemy refuses tribute during war.\n"
                "They want blood, not kola nuts."
            )

        # Check player has enough
        current = getattr(player_resources, resource, 0)
        if current < amount:
            return (
                f"You lack the resources. You have {current} {resource}, "
                f"need {amount}."
            )

        # Spend the resources
        player_resources.spend({resource: amount})

        # Calculate reputation gain
        rep_gain = REP_TRIBUTE_GIFT_BASE + (amount // 50)
        if resource == "kola":
            rep_gain += 5  # kola is special — the peace nut

        rel.reputation += rep_gain
        rel.clamp_reputation()
        rel.tribute_sent += amount

        if rel.state == RelationState.HOSTILE:
            rel.state = RelationState.NEUTRAL

        # AI personality response
        if random.random() < 0.3 and rel.reputation > REP_ALLY_ACCEPT_MIN:
            rel.state = RelationState.ALLIED
            return (
                f"You send {amount} {resource} as tribute.\n"
                f"Reputation +{rep_gain}. Relations warm.\n"
                f"The {entity_key.title()} accept your gift and extend their hand!\n"
                f"Alliance formed! The shared drum beats for peace."
            )

        personality_response = _tribute_response(personality="", entity_key=entity_key, amount=amount, resource=resource)
        return (
            f"You send {amount} {resource} as tribute to the {entity_key.title()}.\n"
            f"Reputation +{rep_gain}. Relations improve.\n"
            f"{personality_response}"
        )

    def demand_tribute(
        self, entity_key: str, resource: str, amount: int, player_resources, personality: str
    ) -> str:
        """Player demands tribute from the AI. Risky — could provoke war."""
        rel = self.get_relation(entity_key)

        if rel.state == RelationState.AT_WAR:
            return "You are already at war! Negotiation is off the table."
        if rel.state == RelationState.ALLIED:
            return "You cannot demand tribute from an ally. That would break the bond."

        # Reputation hit
        rel.reputation += REP_TRIBUTE_DEMAND_BASE
        rel.clamp_reputation()

        # AI response depends on personality
        accept_chance = 0.4
        if personality == "trader":
            accept_chance = 0.65  # trader might pay to keep peace
        elif personality == "aggressive":
            accept_chance = 0.15  # aggressive AI fights back
        elif personality == "defensive":
            accept_chance = 0.5  # defensive AI might comply

        if random.random() < accept_chance:
            # AI pays up
            rel.tribute_received += amount
            rel.reputation += 5
            rel.clamp_reputation()

            if hasattr(player_resources, 'resources'):
                player_resources.resources.earn({resource: amount})

            return (
                f"The {entity_key.title()} reluctantly pay {amount} {resource}.\n"
                f"Your coffers grow, but trust erodes."
            )
        else:
            # AI refuses — might escalate to war
            if rel.reputation < -30 or personality == "aggressive":
                rel.state = RelationState.AT_WAR
                rel.war_turns = 0
                return (
                    f"The {entity_key.title()} refuse your demand!\n"
                    "War drums sound in response. You have provoked the enemy!"
                )
            rel.state = RelationState.HOSTILE
            return (
                f"The {entity_key.title()} refuse your demand.\n"
                "Relations turn hostile. Choose your next move wisely."
            )

    def end_turn_update(self, personality: str) -> list[str]:
        """Process end-of-turn diplomacy effects. Returns events."""
        events = []
        for key, rel in self.relations.items():
            if rel.state == RelationState.ALLIED:
                rel.alliance_turns += 1
                # Alliance slowly improves reputation
                rel.reputation += 2
                rel.clamp_reputation()
                if rel.alliance_turns > 0 and rel.alliance_turns % 5 == 0:
                    events.append(
                        f"Alliance with {key.title()} endures. "
                        f"Shared drums beat in harmony."
                    )
            elif rel.state == RelationState.AT_WAR:
                rel.war_turns += 1
                rel.reputation -= 5
                rel.clamp_reputation()
                # War slowly cools
                if rel.war_turns >= 10:
                    events.append(
                        f"The war with {key.title()} grows tired. "
                        f"Peace may be possible."
                    )
            elif rel.state == RelationState.HOSTILE:
                # Hostile can degrade to war if very negative
                if rel.reputation < -50 and random.random() < 0.3:
                    rel.state = RelationState.AT_WAR
                    rel.war_turns = 0
                    events.append(
                        f"The {key.title()} declare war! "
                        f"Relations have reached the breaking point."
                    )

        return events

    def status_report(self, entity_key: str, personality: str) -> str:
        """Diplomacy status report."""
        rel = self.get_relation(entity_key)

        state_display = {
            RelationState.NEUTRAL: "⚖️  Neutral",
            RelationState.ALLIED: "🤝 Allied",
            RelationState.HOSTILE: "⚠️  Hostile",
            RelationState.AT_WAR: "⚔️  AT WAR",
        }

        rep_bar = _rep_bar(rel.reputation)

        lines = [
            f"{'═' * 50}",
            f"  DIPLOMACY — {entity_key.title()} ({personality})",
            f"{'═' * 50}",
            f"  Status: {state_display[rel.state]}",
            f"  Reputation: {rep_bar} ({rel.reputation})",
            f"  Tribute given: {rel.tribute_sent}  |  Tribute received: {rel.tribute_received}",
        ]

        if rel.state == RelationState.ALLIED:
            lines.append(f"  Alliance turns: {rel.alliance_turns}")
        if rel.state == RelationState.AT_WAR:
            lines.append(f"  War turns: {rel.war_turns}")
        if rel.broken_alliances > 0:
            lines.append(f"  Broken alliances: {rel.broken_alliances} (reputation cost!)")

        lines.append(f"{'═' * 50}")
        lines.append(f"  Actions:")
        lines.append(f"    propose alliance — Seek peace (costs reputation if rejected)")
        lines.append(f"    declare war      — Open hostilities")
        lines.append(f"    offer tribute <resource> <amount> — Gift resources")
        lines.append(f"    demand tribute <resource> <amount> — Risky demand")
        lines.append(f"{'═' * 50}")

        return "\n".join(lines)


def _rep_bar(rep: int) -> str:
    """Visual reputation bar."""
    normalized = (rep + 100) // 10  # 0-20 scale
    filled = "█" * normalized
    empty = "░" * (20 - normalized)
    return f"[{filled}{empty}]"


def _alliance_accept_text(personality: str) -> str:
    texts = {
        "aggressive": (
            "The warlord grins. 'Your strength earns my respect. "
            "Together we shall crush all who oppose us!'"
        ),
        "defensive": (
            "The elder nods slowly. 'Peace is wise. Let our peoples "
            "share the warmth of the fire together.'"
        ),
        "trader": (
            "The merchant smiles. 'Alliance means trade routes are safe. "
            "A profitable arrangement for all!'"
        ),
    }
    return texts.get(personality, "They accept your alliance.")


def _alliance_reject_text(personality: str) -> str:
    texts = {
        "aggressive": (
            "The warlord laughs. 'I do not need allies — I need conquest!'"
        ),
        "defensive": (
            "The elder shakes their head. 'Trust must be earned over many moons.'"
        ),
        "trader": (
            "The merchant considers, then declines. "
            "'What profit is there in this alliance?'"
        ),
    }
    return texts.get(personality, "They politely decline.")


def _tribute_response(personality: str, entity_key: str, amount: int, resource: str) -> str:
    texts = {
        "aggressive": (
            f"The {entity_key} accept the tribute, but their eyes "
            "gleam with hunger for more."
        ),
        "defensive": (
            f"The {entity_key} accept your gift with quiet gratitude. "
            "Trust grows slowly."
        ),
        "trader": (
            f"The {entity_key} merchant's eyes light up. "
            "'This is most generous! Perhaps we can do business.'"
        ),
    }
    return texts.get(
        personality,
        f"The {entity_key} accept your tribute with measured thanks."
    )
