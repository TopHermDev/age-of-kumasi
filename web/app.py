"""FastAPI web layer for Age of Kumasi — REST + WebSocket multiplayer.

Run it with::

    uvicorn web.app:app --host 0.0.0.0 --port 8000

The REST API drives everything (create/join/command/chat); the WebSocket is a
one-way push channel that sends every client a *personalised* snapshot, so fog
of war is enforced server-side (a client never receives data it has not scouted).

Identity is a bearer-style ``player_id`` returned by create/join — it is a
random token, not a guessable name. It is the only thing needed to act in a room.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.civilizations import CIVILIZATIONS

from .session import MAX_PLAYERS, MIN_PLAYERS, Session, SessionError

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
ROOM_DIR = Path(os.environ.get("AOK_ROOM_DIR", Path.cwd() / "var" / "rooms"))

#: Finished rooms are dropped after this many seconds (they are still resumable before that).
ROOM_TTL = 6 * 60 * 60


# ---------------------------------------------------------------- models


class CreateRoom(BaseModel):
    name: str
    civ: str = "ashanti"
    max_players: int = Field(default=4, ge=MIN_PLAYERS, le=MAX_PLAYERS)
    turn_seconds: int = Field(default=60, ge=0, le=600)
    map_seed: int | None = None


class JoinRoom(BaseModel):
    name: str
    civ: str = "ashanti"
    spectator: bool = False


class CommandBody(BaseModel):
    player_id: str
    command: str


class ChatBody(BaseModel):
    player_id: str
    text: str


class IdentityBody(BaseModel):
    player_id: str


# ---------------------------------------------------------------- state


class RoomManager:
    """In-process room registry with JSON persistence under ``var/rooms``."""

    def __init__(self, directory: Path = ROOM_DIR) -> None:
        self.directory = directory
        self.rooms: dict[str, Session] = {}
        self.directory.mkdir(parents=True, exist_ok=True)

    # ---- persistence --------------------------------------------------

    def _path(self, code: str) -> Path:
        return self.directory / f"{code}.json"

    def save(self, session: Session) -> None:
        self._path(session.code).write_text(
            json.dumps(session.to_dict(), separators=(",", ":")), encoding="utf-8"
        )

    def load_all(self) -> None:
        for path in sorted(self.directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                session = Session.from_dict(data)
            except Exception:  # a corrupt or old-format file must not stop the server
                continue
            self.rooms[session.code] = session

    # ---- lifecycle ----------------------------------------------------

    def new_code(self) -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        for _ in range(200):
            code = "".join(secrets.choice(alphabet) for _ in range(4))
            if code not in self.rooms:
                return code
        raise HTTPException(503, "Could not allocate a room code — try again.")

    def create(self, body: CreateRoom) -> tuple[Session, str]:
        session = Session(
            code=self.new_code(),
            max_players=body.max_players,
            turn_seconds=body.turn_seconds,
            map_seed=body.map_seed,
        )
        slot = session.add_player(body.name, body.civ)
        self.rooms[session.code] = session
        self.save(session)
        return session, slot.id

    def get(self, code: str) -> Session:
        session = self.rooms.get(code.upper())
        if not session:
            raise HTTPException(404, f"No room with code {code.upper()}.")
        return session

    def delete(self, code: str) -> None:
        self.rooms.pop(code, None)
        with contextlib.suppress(FileNotFoundError):
            self._path(code).unlink()

    def prune(self) -> None:
        now = time.time()
        for code, session in list(self.rooms.items()):
            if session.state == "finished" and now - session.created_at > ROOM_TTL:
                self.delete(code)

    def open_rooms(self) -> list[dict]:
        return [
            session.summary()
            for session in sorted(self.rooms.values(), key=lambda s: s.created_at, reverse=True)
            if session.state in {"lobby", "active"}
        ]


class ConnectionManager:
    """Tracks WebSockets per room so updates can be pushed per player."""

    def __init__(self) -> None:
        self.connections: dict[str, dict[str, set[WebSocket]]] = {}

    def register(self, code: str, player_id: str, ws: WebSocket) -> None:
        self.connections.setdefault(code, {}).setdefault(player_id, set()).add(ws)

    def unregister(self, code: str, player_id: str, ws: WebSocket) -> None:
        room = self.connections.get(code)
        if not room:
            return
        sockets = room.get(player_id)
        if sockets:
            sockets.discard(ws)
            if not sockets:
                room.pop(player_id, None)
        if not room:
            self.connections.pop(code, None)

    def recipients(self, code: str) -> list[tuple[str, WebSocket]]:
        return [
            (pid, ws)
            for pid, sockets in self.connections.get(code, {}).items()
            for ws in sockets
        ]


manager = RoomManager()
connections = ConnectionManager()


# ---------------------------------------------------------------- app


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    """Load persisted rooms and run the turn-expiry ticker for the app's lifetime."""
    manager.load_all()
    ticker = asyncio.create_task(_turn_ticker())
    try:
        yield
    finally:
        ticker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ticker


async def _broadcast(code: str, session: Session, event: dict | None = None) -> None:
    """Push a fresh snapshot to every connected client, fog-adjusted per player."""
    for pid, ws in connections.recipients(code):
        try:
            await ws.send_json({"type": "snapshot", "data": session.snapshot(pid)})
            if event:
                await ws.send_json(event)
        except Exception:
            connections.unregister(code, pid, ws)


async def _turn_ticker() -> None:
    """End expired turns once per second (server-side authority for the turn timer)."""
    while True:
        await asyncio.sleep(1)
        for code, session in list(manager.rooms.items()):
            if session.state != "active" or not session.expired():
                continue
            try:
                session.end_turn(reason="ran out of time")
                manager.save(session)
                await _broadcast(code, session, {"type": "turn_timeout"})
            except SessionError:
                continue


app = FastAPI(title="Age of Kumasi — Web", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- helpers


def _cmd_response(session: Session, client_id: str, entries: list[dict]) -> JSONResponse:
    return JSONResponse({
        "ok": True,
        "entries": entries,
        "snapshot": session.snapshot(client_id),
    })


def _session_view(session: Session, player_id: str) -> dict:
    return {
        "room": session.summary(),
        "player_id": player_id,
        "snapshot": session.snapshot(player_id),
    }


# ---------------------------------------------------------------- routes


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "rooms": len(manager.rooms), "time": round(time.time(), 3)}


@app.get("/api/civs")
async def civs() -> dict:
    return {
        "civs": [
            {
                "key": key,
                "name": civ.name,
                "region": civ.region,
                "bonus": civ.bonus,
                "unique_unit": civ.unique_unit,
                "description": civ.description,
            }
            for key, civ in CIVILIZATIONS.items()
        ]
    }


@app.get("/api/rooms")
async def list_rooms() -> dict:
    return {"rooms": manager.open_rooms()}


@app.post("/api/rooms", status_code=201)
async def create_room(body: CreateRoom) -> dict:
    try:
        session, player_id = manager.create(body)
    except SessionError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _session_view(session, player_id)


@app.get("/api/rooms/{code}")
async def room_info(code: str) -> dict:
    session = manager.get(code)
    return {"room": session.summary(), "players": [p.public() for p in session.players.values()]}


@app.post("/api/rooms/{code}/join", status_code=201)
async def join_room(code: str, body: JoinRoom) -> dict:
    session = manager.get(code)
    try:
        slot = session.add_player(body.name, body.civ, spectator=body.spectator)
    except SessionError as exc:
        raise HTTPException(400, str(exc)) from exc
    manager.save(session)
    await _broadcast(session.code, session)
    return _session_view(session, slot.id)


@app.post("/api/rooms/{code}/start")
async def start_game(code: str, body: IdentityBody) -> dict:
    session = manager.get(code)
    try:
        session.start(body.player_id)
    except SessionError as exc:
        raise HTTPException(400, str(exc)) from exc
    manager.save(session)
    await _broadcast(session.code, session)
    return {"ok": True, "snapshot": session.snapshot(body.player_id)}


@app.get("/api/rooms/{code}/state")
async def room_state(code: str, player_id: str = Query(...)) -> dict:
    session = manager.get(code)
    if player_id not in session.players:
        raise HTTPException(403, "You are not in this room.")
    return {"ok": True, "snapshot": session.snapshot(player_id)}


@app.post("/api/rooms/{code}/command")
async def run_command(code: str, body: CommandBody) -> Any:
    session = manager.get(code)
    try:
        entries = session.execute(body.player_id, body.command)
    except SessionError as exc:
        raise HTTPException(400, str(exc)) from exc
    manager.save(session)
    await _broadcast(session.code, session)
    return _cmd_response(session, body.player_id, entries)


@app.post("/api/rooms/{code}/end-turn")
async def end_turn(code: str, body: IdentityBody) -> Any:
    session = manager.get(code)
    try:
        session.end_turn(body.player_id)
    except SessionError as exc:
        raise HTTPException(400, str(exc)) from exc
    manager.save(session)
    await _broadcast(session.code, session)
    return {"ok": True, "snapshot": session.snapshot(body.player_id)}


@app.post("/api/rooms/{code}/chat")
async def chat(code: str, body: ChatBody) -> dict:
    session = manager.get(code)
    try:
        entry = session.send_chat(body.player_id, body.text)
    except SessionError as exc:
        raise HTTPException(400, str(exc)) from exc
    manager.save(session)
    await _broadcast(session.code, session, {"type": "chat", "entry": entry})
    return {"ok": True, "entry": entry}


@app.delete("/api/rooms/{code}/leave")
async def leave_room(code: str, player_id: str = Query(...)) -> dict:
    session = manager.get(code)
    if player_id not in session.players:
        raise HTTPException(403, "You are not in this room.")
    session.remove_player(player_id)
    if not session.players:
        manager.delete(code)
    else:
        manager.save(session)
        await _broadcast(session.code, session)
    return {"ok": True}


@app.websocket("/ws/{code}/{player_id}")
async def websocket_endpoint(ws: WebSocket, code: str, player_id: str) -> None:
    code = code.upper()
    session = manager.rooms.get(code)
    if not session or player_id not in session.players:
        await ws.close(code=4404)
        return

    await ws.accept()
    connections.register(code, player_id, ws)
    session.set_connected(player_id, True)
    await ws.send_json({"type": "snapshot", "data": session.snapshot(player_id)})
    await _broadcast(code, session)  # let everyone else see the presence change

    try:
        while True:
            message = await ws.receive_json()
            kind = (message or {}).get("type")
            if kind == "ping":
                await ws.send_json({"type": "pong", "ts": round(time.time(), 3)})
            elif kind == "command":
                try:
                    entries = session.execute(player_id, message.get("command", ""))
                    manager.save(session)
                    await _broadcast(code, session)
                    await ws.send_json({"type": "command_result", "entries": entries})
                except SessionError as exc:
                    await ws.send_json({"type": "error", "message": str(exc)})
            elif kind == "chat":
                try:
                    entry = session.send_chat(player_id, message.get("text", ""))
                    manager.save(session)
                    await _broadcast(code, session, {"type": "chat", "entry": entry})
                except SessionError as exc:
                    await ws.send_json({"type": "error", "message": str(exc)})
            else:
                await ws.send_json({"type": "error", "message": f"Unknown message type: {kind}"})
    except WebSocketDisconnect:
        pass
    finally:
        connections.unregister(code, player_id, ws)
        if not connections.connections.get(code):
            session.set_connected(player_id, False)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main() -> None:  # pragma: no cover - convenience entry point
    import uvicorn

    uvicorn.run(
        "web.app:app",
        host=os.environ.get("AOK_HOST", "0.0.0.0"),
        port=int(os.environ.get("AOK_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
