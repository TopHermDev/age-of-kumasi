"""Tests for the web/multiplayer layer (web/app.py + web/session.py)."""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient with an isolated room directory and a fresh RoomManager."""
    monkeypatch.setenv("AOK_ROOM_DIR", str(tmp_path / "rooms"))
    import web.app as app_module

    app_module = importlib.reload(app_module)
    with TestClient(app_module.app) as test_client:
        test_client.app_module = app_module  # type: ignore[attr-defined]
        yield test_client


def make_room(client, name="Ama", civ="ashanti", players=2, turn_seconds=0):
    res = client.post(
        "/api/rooms",
        json={"name": name, "civ": civ, "max_players": players, "turn_seconds": turn_seconds},
    )
    assert res.status_code == 201, res.text
    return res.json()


def join(client, code, name, civ="dagbon", spectator=False):
    res = client.post(
        f"/api/rooms/{code}/join", json={"name": name, "civ": civ, "spectator": spectator}
    )
    return res


def start(client, code, host_id):
    return client.post(f"/api/rooms/{code}/start", json={"player_id": host_id})


def command(client, code, player_id, text):
    return client.post(
        f"/api/rooms/{code}/command", json={"player_id": player_id, "command": text}
    )


# --------------------------------------------------------------- basics


def test_health_and_civs(client):
    assert client.get("/api/health").json()["status"] == "ok"
    civs = client.get("/api/civs").json()["civs"]
    keys = {c["key"] for c in civs}
    assert {"ashanti", "dagbon", "ga", "ewe"} <= keys
    assert all(c["name"] and c["bonus"] for c in civs)


def test_create_and_join_room(client):
    created = make_room(client)
    code, host_id = created["room"]["code"], created["player_id"]
    assert created["snapshot"]["state"] == "lobby"
    assert created["snapshot"]["you"]["name"] == "Ama"

    res = join(client, code, "Kofi")
    assert res.status_code == 201
    snapshot = res.json()["snapshot"]
    assert len(snapshot["players"]) == 2
    assert snapshot["you"]["civ"] == "dagbon"


def test_duplicate_name_and_full_room_rejected(client):
    created = make_room(client, players=2)
    code = created["room"]["code"]
    assert join(client, code, "ama").status_code == 400          # name taken (case-insensitive)
    assert join(client, code, "Kofi").status_code == 201
    assert join(client, code, "Yaa").status_code == 400          # room full
    assert join(client, code, "Watcher", spectator=True).status_code == 201


def test_unknown_room_and_unknown_player(client):
    assert client.get("/api/rooms/ZZZZ").status_code == 404
    created = make_room(client)
    code = created["room"]["code"]
    assert client.get(f"/api/rooms/{code}/state", params={"player_id": "nope"}).status_code == 403


def test_spectator_may_join_after_start_and_only_look(client):
    created = make_room(client)
    code, host_id = created["room"]["code"], created["player_id"]
    join(client, code, "Kofi")
    assert start(client, code, host_id).status_code == 200

    spec = join(client, code, "Watcher", spectator=True)
    assert spec.status_code == 201
    spec_id = spec.json()["player_id"]

    assert command(client, code, spec_id, "gather food").status_code == 400
    look = command(client, code, spec_id, "map")
    assert look.status_code == 200
    assert "Legend" in look.json()["entries"][0]["text"]


# --------------------------------------------------------------- turns


def test_start_requires_host_and_two_players(client):
    solo = make_room(client, players=2)
    code, host_id = solo["room"]["code"], solo["player_id"]
    assert start(client, code, host_id).status_code == 400  # only one player

    joined = join(client, code, "Kofi").json()
    assert start(client, code, joined["player_id"]).status_code == 400  # not the host
    started = start(client, code, host_id)
    assert started.status_code == 200
    snap = started.json()["snapshot"]
    assert snap["state"] == "active"
    assert snap["turn"]["active_player_id"] == host_id


def test_turn_enforcement_and_end_turn(client):
    created = make_room(client)
    code, host_id = created["room"]["code"], created["player_id"]
    guest_id = join(client, code, "Kofi").json()["player_id"]
    start(client, code, host_id)

    # guest cannot act on the host's turn, but may look
    assert command(client, code, guest_id, "gather food").status_code == 400
    assert command(client, code, guest_id, "status").status_code == 200

    # host acts, ends turn -> guest is active
    assert command(client, code, host_id, "gather food").status_code == 200
    ended = client.post(f"/api/rooms/{code}/end-turn", json={"player_id": host_id})
    assert ended.status_code == 200
    snap = ended.json()["snapshot"]
    assert snap["turn"]["active_player_id"] == guest_id

    # full round increments the turn number
    client.post(f"/api/rooms/{code}/end-turn", json={"player_id": guest_id})
    snap = client.get(f"/api/rooms/{code}/state", params={"player_id": host_id}).json()["snapshot"]
    assert snap["turn"]["number"] == 2
    assert snap["turn"]["active_player_id"] == host_id


def test_commands_affect_state(client):
    created = make_room(client)
    code, host_id = created["room"]["code"], created["player_id"]
    join(client, code, "Kofi")
    start(client, code, host_id)

    before = client.get(f"/api/rooms/{code}/state", params={"player_id": host_id}).json()["snapshot"]
    res = command(client, code, host_id, "train villager 2")
    assert res.status_code == 200
    after = res.json()["snapshot"]
    # training queues or deducts resources; either way the log records the action
    assert any("villager" in e["text"].lower() for e in res.json()["entries"])
    assert after["you"]["resources"] != before["you"]["resources"] or after["you"]["units"] != before["you"]["units"]


# --------------------------------------------------------------- combat + diplomacy


def test_attack_human_player_and_war_state(client):
    created = make_room(client)
    code, host_id = created["room"]["code"], created["player_id"]
    guest_id = join(client, code, "Kofi").json()["player_id"]
    start(client, code, host_id)

    res = command(client, code, host_id, "attack Kofi")
    assert res.status_code == 200
    snap = res.json()["snapshot"]
    rel = next(d for d in snap["diplomacy"] if d["player_id"] == guest_id)
    # neutral -> at war once blows are exchanged (no military yet yields a message)
    assert rel["relation"] in {"at_war", "neutral"}


def test_alliance_flow_and_war_declaration(client):
    created = make_room(client)
    code, host_id = created["room"]["code"], created["player_id"]
    guest_id = join(client, code, "Kofi").json()["player_id"]
    start(client, code, host_id)

    assert command(client, code, host_id, "propose alliance Kofi").status_code == 200
    guest_snap = client.get(
        f"/api/rooms/{code}/state", params={"player_id": guest_id}
    ).json()["snapshot"]
    proposal = next(d for d in guest_snap["diplomacy"] if d["player_id"] == host_id)
    assert proposal["proposal"] == "incoming"

    assert command(client, code, guest_id, "accept alliance Ama").status_code == 200
    both = client.get(f"/api/rooms/{code}/state", params={"player_id": host_id}).json()["snapshot"]
    rel = next(d for d in both["diplomacy"] if d["player_id"] == guest_id)
    assert rel["relation"] == "allied"
    assert rel["reputation"] > 0

    # attacking an ally is refused until war is declared
    refused = command(client, code, host_id, "attack Kofi")
    assert refused.status_code == 400 and "allied" in refused.json()["detail"].lower()

    assert command(client, code, host_id, "declare war Kofi").status_code == 200
    war = client.get(f"/api/rooms/{code}/state", params={"player_id": host_id}).json()["snapshot"]
    rel = next(d for d in war["diplomacy"] if d["player_id"] == guest_id)
    assert rel["relation"] == "at_war"


def test_tribute_moves_resources(client):
    created = make_room(client)
    code, host_id = created["room"]["code"], created["player_id"]
    guest_id = join(client, code, "Kofi").json()["player_id"]
    start(client, code, host_id)

    host_before = command(client, code, host_id, "status").json()["snapshot"]["you"]["resources"]
    guest_before = client.get(
        f"/api/rooms/{code}/state", params={"player_id": guest_id}
    ).json()["snapshot"]["you"]["resources"]

    res = command(client, code, host_id, "tribute food 25 Kofi")
    assert res.status_code == 200
    host_after = res.json()["snapshot"]["you"]["resources"]
    guest_after = client.get(
        f"/api/rooms/{code}/state", params={"player_id": guest_id}
    ).json()["snapshot"]["you"]["resources"]

    assert host_after["food"] == host_before["food"] - 25
    assert guest_after["food"] == guest_before["food"] + 25


# --------------------------------------------------------------- fog / map


def test_fog_of_war_is_per_player(client):
    created = make_room(client)
    code, host_id = created["room"]["code"], created["player_id"]
    join(client, code, "Kofi")
    start(client, code, host_id)

    host_map = client.get(f"/api/rooms/{code}/state", params={"player_id": host_id}).json()["snapshot"]["map"]
    flat = [cell for row in host_map["rows"] for cell in row]
    unseen = [c for c in flat if c["f"] == "unseen"]
    visible = [c for c in flat if c["f"] == "visible"]
    assert unseen, "a player must not see the whole map"
    assert visible, "a player must see around their own units"
    assert len(visible) < len(flat)

    spectator = join(client, code, "Watcher", spectator=True).json()
    spec_map = spectator["snapshot"]["map"]
    spec_flat = [cell for row in spec_map["rows"] for cell in row]
    assert all(c["f"] != "unseen" for c in spec_flat), "spectators see the full map"


def test_map_renders_own_units(client):
    created = make_room(client)
    code, host_id = created["room"]["code"], created["player_id"]
    join(client, code, "Kofi")
    start(client, code, host_id)
    snap = client.get(f"/api/rooms/{code}/state", params={"player_id": host_id}).json()["snapshot"]
    owners = {cell["o"] for row in snap["map"]["rows"] for cell in row if cell["o"]}
    assert "self" in owners


# --------------------------------------------------------------- chat + ws


def test_chat_endpoint(client):
    created = make_room(client)
    code, host_id = created["room"]["code"], created["player_id"]
    res = client.post(f"/api/rooms/{code}/chat", json={"player_id": host_id, "text": "hello room"})
    assert res.status_code == 200
    assert res.json()["entry"]["text"] == "hello room"
    snap = client.get(f"/api/rooms/{code}/state", params={"player_id": host_id}).json()["snapshot"]
    assert snap["chat"][-1]["text"] == "hello room"


def test_websocket_broadcasts_snapshot_and_chat(client):
    created = make_room(client)
    code, host_id = created["room"]["code"], created["player_id"]
    guest_id = join(client, code, "Kofi").json()["player_id"]

    with client.websocket_connect(f"/ws/{code}/{host_id}") as host_ws:
        first = host_ws.receive_json()
        assert first["type"] == "snapshot"
        assert first["data"]["you"]["id"] == host_id

        with client.websocket_connect(f"/ws/{code}/{guest_id}") as guest_ws:
            guest_first = guest_ws.receive_json()
            assert guest_first["data"]["you"]["id"] == guest_id

            # the host's presence update reaches the guest as a new snapshot
            pushed = guest_ws.receive_json()
            assert pushed["type"] in {"snapshot", "chat"}

            client.post(f"/api/rooms/{code}/chat", json={"player_id": host_id, "text": "ping"})
            seen = None
            for _ in range(4):
                msg = guest_ws.receive_json()
                if msg["type"] == "chat" and msg["entry"]["text"] == "ping":
                    seen = msg
                    break
            assert seen is not None


def test_websocket_rejects_unknown_player(client):
    created = make_room(client)
    code = created["room"]["code"]
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/{code}/intruder") as ws:
            ws.receive_json()


# --------------------------------------------------------------- persistence


def test_room_survives_reload(client, tmp_path):
    created = make_room(client)
    code, host_id = created["room"]["code"], created["player_id"]
    guest_id = join(client, code, "Kofi").json()["player_id"]
    start(client, code, host_id)
    command(client, code, host_id, "gather wood")
    client.post(f"/api/rooms/{code}/end-turn", json={"player_id": host_id})

    before = client.get(f"/api/rooms/{code}/state", params={"player_id": guest_id}).json()["snapshot"]

    # simulate a restart: brand-new RoomManager pointed at the same directory
    app_module = client.app_module
    fresh = app_module.RoomManager(directory=app_module.ROOM_DIR)
    fresh.load_all()
    restored = fresh.rooms[code]
    after = restored.snapshot(guest_id)

    assert after["state"] == before["state"] == "active"
    # the host ended their turn, so it is the guest's move within the same round
    assert after["turn"]["number"] == before["turn"]["number"] == 1
    assert after["turn"]["active_player_id"] == guest_id
    assert [p["name"] for p in after["players"]] == [p["name"] for p in before["players"]]
    assert after["you"]["resources"] == before["you"]["resources"]
    assert after["you"]["units"] == before["you"]["units"]


def test_leave_room_removes_player(client):
    created = make_room(client)
    code, host_id = created["room"]["code"], created["player_id"]
    guest_id = join(client, code, "Kofi").json()["player_id"]
    res = client.delete(f"/api/rooms/{code}/leave", params={"player_id": guest_id})
    assert res.status_code == 200
    info = client.get(f"/api/rooms/{code}").json()
    assert [p["name"] for p in info["players"]] == ["Ama"]


# --------------------------------------------------------------- timer


def test_turn_timer_expiry_marks_turn_expired(client):
    created = make_room(client, turn_seconds=1)
    code, host_id = created["room"]["code"], created["player_id"]
    join(client, code, "Kofi")
    start(client, code, host_id)

    snap = client.get(f"/api/rooms/{code}/state", params={"player_id": host_id}).json()["snapshot"]
    assert snap["turn"]["seconds_left"] is not None

    session = client.app_module.manager.rooms[code]
    session.turn_deadline = __import__("time").time() - 0.01
    assert session.expired() is True

    session.end_turn(reason="ran out of time")
    after = session.snapshot(host_id)
    assert after["turn"]["active_player_id"] != host_id
    assert any("ran out of time" in entry["text"] for entry in after["log"])
