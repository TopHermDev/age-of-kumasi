/* Age of Kumasi — browser client (plain ES module, no build step).
 * REST drives every action; one WebSocket per player keeps state in sync.
 * Sections: constants · state · utils · API · lobby · room · socket · render · timer · commands · boot.
 */

/* ------------------------------------------------------------- constants */
const MAX_HISTORY = 60, ROOM_POLL_MS = 5000, HEALTH_POLL_MS = 30000;
const PING_MS = 20000, RECONNECT_MAX_MS = 15000;
const SESSION_KEY = 'aok.session.v1', PREFS_KEY = 'aok.prefs.v1';
const TERRAIN = {
  '~': { key: 'coast', name: 'Coast' }, '.': { key: 'savanna', name: 'Savanna' },
  'T': { key: 'forest', name: 'Forest' }, 'G': { key: 'gold', name: 'Gold field' },
  'K': { key: 'kola', name: 'Kola grove' }, 'V': { key: 'village', name: 'Village' },
  '≈': { key: 'river', name: 'River' },
};
const OCCUPANT_GLYPH = { self: '@', ally: '+', enemy: '!' };
const OCCUPANT_LABEL = { self: 'your forces', ally: 'ally', enemy: 'enemy' };
const CIV_LABELS = new Map();

/* ----------------------------------------------------------------- state */
const state = {
  civs: [], pendingCiv: '', roomCode: null, playerId: null, snapshot: null, snapshotAt: 0,
  ws: null, conn: 'idle', reconnectAttempts: 0, reconnectTimer: null, pingTimer: null, watchdogTimer: null,
  mapSignature: '', logSignature: '', chatSignature: '', localEntries: [], chatExtra: [],
  history: [], historyIndex: -1, historyDraft: '',
  ticker: null, roomsTimer: null, healthTimer: null, toastTimer: null,
};
const els = {};

/* ----------------------------------------------------------------- utils */
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}
function add(parent, tag, className, text) {
  const node = el(tag, className, text);
  parent.appendChild(node);
  return node;
}
function civName(key) { return key ? (CIV_LABELS.get(key) || key.charAt(0).toUpperCase() + key.slice(1)) : '—'; }
function firstName(name) { return String(name || '').trim().split(/\s+/)[0] || ''; }
function formatClock(seconds) {
  const total = Math.max(0, Math.ceil(seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}
function setBusy(button, busy, label) {
  if (!button) return;
  if (busy) { button.dataset.idleLabel = button.textContent; button.textContent = label; button.disabled = true; }
  else { button.textContent = button.dataset.idleLabel || label; button.disabled = false; }
}

/* ------------------------------------------------------------------- API */
class ApiError extends Error {
  constructor(message, status) { super(message); this.name = 'ApiError'; this.status = status; }
}
function detailMessage(detail) {
  if (!detail) return ''; if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((item) => (item && (item.msg || item.message)) || '').filter(Boolean).join('; ');
  if (typeof detail === 'object') return detail.message || detail.msg || ''; return String(detail);
}
async function api(path, options = {}) {
  const init = { method: options.method || 'GET', headers: { Accept: 'application/json' } };
  if (options.body !== undefined) {
    init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(options.body);
  }
  let response;
  try { response = await fetch(path, init); } catch (_) { throw new ApiError('Cannot reach the server — check your connection.', 0); }
  const raw = await response.text(); let data = null;
  if (raw) { try { data = JSON.parse(raw); } catch (_) { data = null; } }
  if (!response.ok) {
    const message = detailMessage(data ? (data.detail ?? data.message) : null) || `Request failed (HTTP ${response.status}).`;
    throw new ApiError(message, response.status);
  }
  return data || {};
}

/* --------------------------------------------------------------- storage */
function saveSession() {
  if (!state.roomCode || !state.playerId) return;
  try { localStorage.setItem(SESSION_KEY, JSON.stringify({ code: state.roomCode, player_id: state.playerId })); } catch (_) { /* private mode */ }
}
function loadSession() {
  try {
    const data = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null');
    if (data && data.code && data.player_id) return data;
  } catch (_) { /* corrupt entry */ }
  return null;
}
function clearSession() { try { localStorage.removeItem(SESSION_KEY); } catch (_) { /* ignore */ } }
function savePrefs(name, civ) { try { localStorage.setItem(PREFS_KEY, JSON.stringify({ name: name || '', civ: civ || '' })); } catch (_) { /* ignore */ } }
function loadPrefs() { try { return JSON.parse(localStorage.getItem(PREFS_KEY) || '{}') || {}; } catch (_) { return {}; } }

/* --------------------------------------------------------------- notices */
function setLobbyNotice(message, kind = 'notice') {
  els.lobbyNotice.textContent = message || ''; els.lobbyNotice.className = `notice notice-${kind}`;
  els.lobbyNotice.hidden = !message;
}
function toast(message) {
  els.toast.textContent = message; els.toast.hidden = false; clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => { els.toast.hidden = true; }, 2200);
}
function setConn(mode) {
  const labels = { live: 'live', connecting: 'connecting', reconnecting: 'resyncing', offline: 'offline', idle: 'offline' };
  state.conn = mode; els.connStatus.textContent = labels[mode] || mode; els.connStatus.className = `conn conn-${mode}`;
}
function showReconnectBanner(delay) {
  els.reconnectBanner.hidden = false;
  els.reconnectBanner.textContent = `reconnecting in ${Math.max(1, Math.round(delay / 1000))}s…`;
}
function hideReconnectBanner() { els.reconnectBanner.hidden = true; }

/* ----------------------------------------------------------------- lobby */
async function loadCivs() {
  try {
    const data = await api('/api/civs'); state.civs = Array.isArray(data.civs) ? data.civs : [];
    if (!state.civs.length) throw new ApiError('the server returned no civilisations', 200);
    CIV_LABELS.clear(); els.civSelect.replaceChildren();
    for (const civ of state.civs) {
      CIV_LABELS.set(civ.key, civ.name); const option = el('option', null, civ.name);
      option.value = civ.key; els.civSelect.appendChild(option);
    }
    els.civSelect.disabled = false;
    if (state.pendingCiv && state.civs.some((civ) => civ.key === state.pendingCiv)) els.civSelect.value = state.pendingCiv;
    updateCivNote(); refreshCivLabels();
  } catch (err) {
    els.civNote.textContent = `civilisations unavailable — ${err.message}`;
    setLobbyNotice(`Could not load civilisations: ${err.message}`, 'warn');
  }
}
function updateCivNote() {
  const civ = state.civs.find((entry) => entry.key === els.civSelect.value);
  if (!civ) { els.civNote.textContent = 'choose a civilisation'; return; }
  els.civNote.textContent = `bonus: ${civ.bonus} · unique unit: ${civ.unique_unit}`;
  els.civNote.title = civ.description || '';
}
function refreshCivLabels() { if (state.snapshot) { renderWaiting(); renderPlayers(); renderDiplomacy(); renderStatus(); } }
async function refreshHealth() {
  try {
    const data = await api('/api/health'); const rooms = Number(data.rooms) || 0;
    els.healthText.textContent = `online · ${rooms} ${rooms === 1 ? 'room' : 'rooms'}`;
    els.healthLed.className = 'led led-ok';
  } catch (_) {
    els.healthText.textContent = 'server offline'; els.healthLed.className = 'led led-bad';
  }
}
async function refreshRooms(force = false) {
  if (!force && els.lobbyScreen.hidden) return; // no point polling mid-game
  try {
    const data = await api('/api/rooms'); renderRooms(Array.isArray(data.rooms) ? data.rooms : []);
    els.roomsUpdated.textContent = `updated ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
  } catch (err) {
    els.roomsUpdated.textContent = 'unavailable';
    els.roomsList.replaceChildren(el('p', 'empty', `Could not list rooms: ${err.message}`));
  }
}
function renderRooms(rooms) {
  els.roomsList.replaceChildren();
  if (!rooms.length) { els.roomsList.appendChild(el('p', 'empty', 'No open camps. Create one and share the code.')); return; }
  for (const room of rooms) {
    const row = el('div', 'room-row'), main = el('div', 'room-main');
    main.appendChild(el('span', 'room-code', room.code));
    const bits = [`${room.players}/${room.max_players} players`, room.state,
      room.turn_seconds ? `${room.turn_seconds}s turns` : 'no timer', room.host ? `host ${room.host}` : null];
    main.appendChild(el('span', 'room-meta-line', bits.filter(Boolean).join(' · '))); row.appendChild(main);
    if (room.spectators > 0) add(row, 'span', 'room-spec', `${room.spectators} watching`);
    const join = add(row, 'button', 'btn btn-small', room.state === 'lobby' ? 'Join' : 'Watch');
    join.type = 'button'; join.addEventListener('click', () => joinFromList(room)); els.roomsList.appendChild(row);
  }
}
function joinFromList(room) {
  if (!els.nameInput.value.trim()) {
    setLobbyNotice('Choose a commander name before joining a room.'); els.nameInput.focus(); return;
  }
  joinRoom(room.code, room.state !== 'lobby');
}
async function createRoom(event) {
  event.preventDefault(); const name = els.nameInput.value.trim();
  if (!name) { setLobbyNotice('Choose a commander name first.'); els.nameInput.focus(); return; }
  const civ = els.civSelect.value || 'ashanti';
  const body = { name, civ, max_players: Number(els.maxPlayers.value) || 4, turn_seconds: Number(els.turnSeconds.value) || 0, map_seed: null };
  setBusy(els.createBtn, true, 'Creating…');
  try {
    const data = await api('/api/rooms', { method: 'POST', body }); savePrefs(name, civ);
    enterRoom(data.room.code, data.player_id, data.snapshot);
  } catch (err) {
    setLobbyNotice(`Could not create room: ${err.message}`, 'warn');
  } finally {
    setBusy(els.createBtn, false, 'Create room');
  }
}
async function joinRoom(code, spectator) {
  const name = els.nameInput.value.trim(), civ = els.civSelect.value || 'ashanti';
  const roomCode = String(code || '').trim().toUpperCase();
  if (!name) { setLobbyNotice('Choose a commander name first.'); els.nameInput.focus(); return; }
  if (!roomCode) { setLobbyNotice('Enter a room code to join.'); els.codeInput.focus(); return; }
  setBusy(els.joinBtn, true, 'Joining…');
  try {
    const data = await api(`/api/rooms/${encodeURIComponent(roomCode)}/join`, { method: 'POST', body: { name, civ, spectator: Boolean(spectator) } });
    savePrefs(name, civ); enterRoom(data.room.code, data.player_id, data.snapshot);
  } catch (err) {
    setLobbyNotice(`Join failed: ${err.message}`, 'warn');
  } finally {
    setBusy(els.joinBtn, false, 'Join room');
  }
}

/* ---------------------------------------------------------- room lifecycle */
function enterRoom(code, playerId, snapshot) {
  state.roomCode = String(code || '').toUpperCase(); state.playerId = playerId; state.snapshot = null;
  state.localEntries = []; state.chatExtra = []; state.history = []; state.historyIndex = -1;
  state.mapSignature = ''; state.logSignature = ''; state.chatSignature = ''; saveSession();
  els.lobbyScreen.hidden = true; els.roomScreen.hidden = false;
  els.log.replaceChildren(); els.chat.replaceChildren(); els.map.replaceChildren();
  els.finishedBanner.hidden = true; els.turnHint.hidden = true; setLobbyNotice('');
  if (snapshot) applySnapshot(snapshot); connectSocket(); ensureTicker();
  document.title = `Room ${state.roomCode} — Age of Kumasi`;
}
function returnToLobby(message) {
  closeSocket(); clearTimeout(state.reconnectTimer); state.reconnectTimer = null;
  clearTimeout(state.watchdogTimer); state.watchdogTimer = null; hideReconnectBanner();
  clearSession(); state.roomCode = null; state.playerId = null; state.snapshot = null;
  state.localEntries = []; state.chatExtra = []; state.reconnectAttempts = 0;
  els.roomScreen.hidden = true; els.lobbyScreen.hidden = false;
  els.map.replaceChildren(); els.log.replaceChildren(); els.chat.replaceChildren();
  els.finishedBanner.hidden = true; els.startBtn.hidden = true; els.startHint.hidden = true;
  document.title = 'Age of Kumasi — Multiplayer'; setConn('idle'); if (message) setLobbyNotice(message);
  refreshRooms(true);
}
async function resumeSession() {
  const saved = loadSession(); if (!saved) return false;
  try {
    await api(`/api/rooms/${encodeURIComponent(saved.code)}`);
    const data = await api(`/api/rooms/${encodeURIComponent(saved.code)}/state?player_id=${encodeURIComponent(saved.player_id)}`);
    enterRoom(saved.code, saved.player_id, data.snapshot); return true;
  } catch (err) {
    if (err.status === 403 || err.status === 404) {
      clearSession();
      setLobbyNotice(`Room ${saved.code} is no longer available.`, 'warn');
    } else {
      // keep the saved seat so a reload can retry once the network returns
      setLobbyNotice(`Could not rejoin room ${saved.code}: ${err.message}`, 'warn');
    }
    return false;
  }
}

/* --------------------------------------------------------------- websocket */
function connectSocket() {
  if (!state.roomCode || !state.playerId) return;
  closeSocket(); clearTimeout(state.reconnectTimer); state.reconnectTimer = null;
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${proto}//${location.host}/ws/${encodeURIComponent(state.roomCode)}/${encodeURIComponent(state.playerId)}`;
  let ws;
  try { ws = new WebSocket(url); } catch (_) { scheduleReconnect(); return; }
  state.ws = ws; setConn(state.reconnectAttempts ? 'reconnecting' : 'connecting');
  ws.onopen = () => {
    state.reconnectAttempts = 0; hideReconnectBanner(); setConn('live'); startPing();
    armWatchdog();
  };
  ws.onmessage = (event) => {
    let message;
    try { message = JSON.parse(event.data); } catch (_) { return; }
    handleSocketMessage(message);
  };
  ws.onerror = () => { /* onclose drives the retry */ };
  ws.onclose = (event) => {
    if (state.ws !== ws) return; state.ws = null; stopPing();
    clearTimeout(state.watchdogTimer);
    if (event && event.code === 4404) { returnToLobby('That room is closed, or you are no longer seated in it.'); return; }
    setConn('offline'); scheduleReconnect();
  };
}
function closeSocket() {
  const ws = state.ws; state.ws = null; stopPing();
  if (ws) {
    ws.onopen = null; ws.onmessage = null; ws.onerror = null; ws.onclose = null;
    try { ws.close(); } catch (_) { /* already closing */ }
  }
}
function scheduleReconnect() {
  if (!state.roomCode || !state.playerId || state.reconnectTimer) return; state.reconnectAttempts += 1;
  const delay = Math.min(RECONNECT_MAX_MS, 1000 * 2 ** (state.reconnectAttempts - 1));
  showReconnectBanner(delay); setConn('offline');
  state.reconnectTimer = setTimeout(() => { state.reconnectTimer = null; connectSocket(); }, delay);
}
function startPing() {
  stopPing();
  state.pingTimer = setInterval(() => {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) state.ws.send(JSON.stringify({ type: 'ping' }));
  }, PING_MS);
}
function stopPing() { if (state.pingTimer) { clearInterval(state.pingTimer); state.pingTimer = null; } }
function armWatchdog() {
  clearTimeout(state.watchdogTimer); const before = state.snapshotAt;
  state.watchdogTimer = setTimeout(() => { if (state.roomCode && state.snapshotAt === before) refreshState(); }, 3000);
}
function handleSocketMessage(message) {
  if (!message || !message.type) return;
  switch (message.type) {
    case 'snapshot': applySnapshot(message.data); break;
    case 'chat':
      if (message.entry) {
        state.chatExtra.push(message.entry); if (state.chatExtra.length > 80) state.chatExtra.shift();
        renderChat();
      }
      break;
    case 'command_result': break; // entries arrive inside the snapshot's log
    case 'error': clientLog('notice', message.message || 'Server error.'); break;
    case 'turn_timeout': clientLog('system', 'Turn timer expired — the turn was auto-ended.'); break;
    case 'pong': break;
    default: break;
  }
}
async function refreshState() {
  if (!state.roomCode || !state.playerId) return;
  try {
    const data = await api(`/api/rooms/${encodeURIComponent(state.roomCode)}/state?player_id=${encodeURIComponent(state.playerId)}`);
    if (data && data.snapshot) applySnapshot(data.snapshot);
  } catch (err) {
    if (err.status === 403 || err.status === 404) returnToLobby('Your seat in this room is gone.');
    else clientLog('notice', `Could not refresh state: ${err.message}`);
  }
}

/* ---------------------------------------------------------------- render */
function applySnapshot(snapshot) {
  if (!snapshot || els.roomScreen.hidden) return;
  if (snapshot.code && state.roomCode && snapshot.code !== state.roomCode) return;
  if (snapshot.code) state.roomCode = snapshot.code; state.snapshot = snapshot; state.snapshotAt = Date.now();
  if (Array.isArray(snapshot.chat) && state.chatExtra.length) {
    const known = new Set(snapshot.chat.map((entry) => entry.seq));
    state.chatExtra = state.chatExtra.filter((entry) => !known.has(entry.seq));
  }
  renderHeader(); renderWaiting(); renderGame(); renderLog(); renderChat();
  renderBanner(); updateTurnUi(); updateTimer();
}
function renderHeader() {
  const snap = state.snapshot; if (!snap) return; els.roomCode.textContent = snap.code || state.roomCode || '----';
  els.statePill.textContent = snap.state; els.statePill.className = `state-pill state-${snap.state}`;
  const turn = snap.turn || {}, active = snap.state === 'active';
  els.turnNumber.textContent = snap.state === 'lobby' ? '—' : String(turn.number ?? '—');
  els.activePlayer.textContent = active ? (turn.active_player_name || '—') : '—';
  els.activePlayer.classList.toggle('is-you', Boolean(active && turn.active_player_id === state.playerId));
}
function renderWaiting() {
  const snap = state.snapshot; if (!snap) return;
  if (snap.state !== 'lobby') {
    els.waitingPanel.hidden = true; els.startBtn.hidden = true; els.startHint.hidden = true; return;
  }
  const players = snap.players || [], humans = players.filter((p) => !p.is_spectator);
  const spectators = players.length - humans.length, you = snap.you || {};
  const maxPlayers = (snap.settings && snap.settings.max_players) || 4; els.waitingPanel.hidden = false;
  els.waitingNote.textContent = `${humans.length}/${maxPlayers} commanders${spectators ? ` · ${spectators} watching` : ''}`;
  els.waitingPlayers.replaceChildren();
  for (const p of players) {
    const flags = `${p.id === state.playerId ? ' is-you' : ''}${p.eliminated ? ' is-eliminated' : ''}${p.connected ? '' : ' is-offline'}`;
    const card = el('li', `player-card${flags}`);
    const top = el('div', 'player-card-top'); add(top, 'span', 'player-name', p.name);
    if (p.id === state.playerId) add(top, 'span', 'tag tag-you', 'you');
    if (p.is_host) add(top, 'span', 'tag tag-host', 'host'); if (p.is_spectator) add(top, 'span', 'tag', 'spectator');
    if (!p.connected) add(top, 'span', 'tag tag-off', 'offline'); card.appendChild(top);
    add(card, 'span', 'player-civ', p.is_spectator ? 'observer' : civName(p.civ)); els.waitingPlayers.appendChild(card);
  }
  els.startBtn.hidden = !you.is_host; els.startBtn.disabled = !you.is_host || humans.length < 2;
  els.startHint.hidden = false;
  if (you.is_spectator) els.startHint.textContent = 'Spectating — the host starts the game.';
  else if (!you.is_host) els.startHint.textContent = `Waiting for ${(players.find((p) => p.is_host) || {}).name || 'the host'} to start the game.`;
  else if (humans.length < 2) els.startHint.textContent = `Need at least 2 commanders to start (${humans.length}/${maxPlayers} present).`;
  else els.startHint.textContent = 'Ready — start when your rivals are assembled.';
  els.waitingCopy.textContent = you.is_host
    ? 'Share the room code. You can start once at least two commanders have joined.'
    : 'Share the room code. The host starts the game once at least two commanders are present.';
}
function renderGame() {
  const snap = state.snapshot; if (!snap) return; const inGame = snap.state !== 'lobby'; els.gameView.hidden = !inGame;
  if (!inGame) return; renderMap(); renderStatus(); renderPlayers(); renderDiplomacy();
  const map = snap.map, seed = snap.settings ? snap.settings.map_seed : null;
  els.mapMeta.textContent = map ? `${map.width}×${map.height} · seed ${seed ?? 'random'}` : '—';
}
function renderMap() {
  const map = state.snapshot && state.snapshot.map; if (!map || !Array.isArray(map.rows)) return;
  let signature = `${map.width}x${map.height}:`;
  for (const row of map.rows) for (const cell of row) signature += (cell.g || ' ') + (cell.o || '') + (cell.f || '?').charAt(0);
  if (signature === state.mapSignature) return; state.mapSignature = signature;
  const frag = document.createDocumentFragment();
  map.rows.forEach((row, y) => {
    const line = el('span', 'map-row');
    row.forEach((cell, x) => {
      const spot = el('span', 'cell');
      if (cell.f === 'unseen' || !cell.g) {
        spot.classList.add('fog-unseen'); spot.textContent = '\u00a0';
      } else {
        const terrain = TERRAIN[cell.g] || { key: 'other', name: 'Unknown ground' };
        spot.classList.add(`fog-${cell.f}`, `t-${terrain.key}`); spot.textContent = OCCUPANT_GLYPH[cell.o] || cell.g;
        if (cell.o) spot.classList.add('occ', `occ-${cell.o}`);
        spot.title = `${terrain.name}${cell.o ? ` · ${OCCUPANT_LABEL[cell.o]}` : ''} @ ${x},${y}`;
      }
      line.appendChild(spot);
    });
    frag.appendChild(line);
  });
  els.map.replaceChildren(frag);
}
function listBlock(title, items, format) {
  const block = el('div', 'mini-block'); block.appendChild(el('h3', 'mini-title', title));
  if (!items || !items.length) { block.appendChild(el('p', 'muted tiny', 'none')); return block; }
  const list = el('ul', 'mini-list'); for (const item of items) list.appendChild(el('li', null, format(item)));
  block.appendChild(list); return block;
}
function renderStatus() {
  const you = state.snapshot && state.snapshot.you; els.statusBody.replaceChildren(); if (!you) return;
  els.statusAge.textContent = you.age_name || '—';
  if (you.is_spectator) { els.statusBody.appendChild(el('p', 'muted', 'Spectating — you have no domain to command.')); return; }
  const identity = el('div', 'identity'); add(identity, 'span', 'identity-name', you.name);
  add(identity, 'span', 'identity-civ', `${civName(you.civ)} · age ${you.age} · ${you.age_name || ''}`);
  els.statusBody.appendChild(identity); const resources = el('div', 'res-grid');
  for (const key of ['food', 'wood', 'gold', 'kola']) {
    const tile = el('div', `res res-${key}`); add(tile, 'span', 'res-label', key);
    add(tile, 'b', 'res-value', String((you.resources && you.resources[key]) ?? 0)); resources.appendChild(tile);
  }
  els.statusBody.appendChild(resources);
  const maxPop = Number(you.max_population) || 0, pop = Number(you.population) || 0;
  const popRow = el('div', 'pop-row'); add(popRow, 'span', 'pop-label', 'population');
  add(popRow, 'span', 'pop-value', `${pop}/${maxPop}`); els.statusBody.appendChild(popRow);
  const fill = el('div', 'pop-fill'), bar = el('div', 'pop-bar');
  fill.style.width = `${maxPop > 0 ? Math.min(100, Math.round((pop / maxPop) * 100)) : 0}%`;
  bar.appendChild(fill); els.statusBody.appendChild(bar);
  els.statusBody.appendChild(listBlock('units', you.units, (unit) => `${unit.name} ×${unit.count}`));
  els.statusBody.appendChild(listBlock('buildings', you.buildings, (b) => `${b.name} ×${b.count}`));
}
function renderPlayers() {
  const snap = state.snapshot; if (!snap) return; const players = snap.players || [];
  const activeId = snap.state === 'active' && snap.turn ? snap.turn.active_player_id : null;
  els.playersCount.textContent = `${players.filter((p) => !p.is_spectator).length}/${(snap.settings && snap.settings.max_players) || '?'}`;
  els.playersList.replaceChildren();
  for (const p of players) {
    const flags = `${p.id === activeId ? ' is-active' : ''}${p.id === state.playerId ? ' is-you' : ''}`
      + `${p.eliminated ? ' is-eliminated' : ''}${p.connected ? '' : ' is-offline'}`;
    const row = el('li', `player-row${flags}`);
    add(row, 'span', 'turn-marker', p.id === activeId ? '▶' : '·');
    const main = el('div', 'player-row-main'), top = el('div', 'player-row-top');
    add(top, 'span', 'player-row-name', p.name); if (p.is_host) add(top, 'span', 'tag tag-host', 'host');
    if (p.is_spectator) add(top, 'span', 'tag', 'spec'); main.appendChild(top);
    const bits = [civName(p.civ)]; if (!p.is_spectator) bits.push(`pop ${p.population ?? 0}`);
    if (!p.connected) bits.push('offline'); if (p.eliminated) bits.push('eliminated');
    add(main, 'span', 'player-row-sub', bits.join(' · ')); row.appendChild(main); els.playersList.appendChild(row);
  }
}
function renderDiplomacy() {
  const entries = (state.snapshot && state.snapshot.diplomacy) || []; els.diplomacyList.replaceChildren();
  if (!entries.length) { els.diplomacyList.appendChild(el('li', 'muted tiny', 'No rivals yet.')); return; }
  for (const entry of entries) {
    const row = el('li', 'diplo-row'); const head = el('div', 'diplo-head');
    add(head, 'span', 'diplo-name', entry.name); const relation = String(entry.relation || 'unknown');
    add(head, 'span', `rel rel-${relation.replace(/_/g, '-')}`, relation.replace(/_/g, ' ')); row.appendChild(head);
    const meta = el('div', 'diplo-meta'); add(meta, 'span', 'diplo-rep', `reputation ${entry.reputation ?? 0}`);
    if (entry.proposal === 'incoming') add(meta, 'span', 'diplo-prop', 'proposes an alliance');
    if (entry.proposal === 'outgoing') add(meta, 'span', 'diplo-prop is-dim', 'proposal sent'); row.appendChild(meta);
    if (entry.proposal === 'incoming') {
      const actions = el('div', 'diplo-actions'); const accept = add(actions, 'button', 'btn btn-small', 'Accept');
      const reject = add(actions, 'button', 'btn btn-small btn-ghost', 'Reject');
      accept.type = 'button'; reject.type = 'button';
      accept.addEventListener('click', () => sendCommand(`accept alliance ${firstName(entry.name)}`));
      reject.addEventListener('click', () => sendCommand(`reject alliance ${firstName(entry.name)}`));
      row.appendChild(actions);
    }
    els.diplomacyList.appendChild(row);
  }
}
function clientLog(kind, text, actor) {
  state.localEntries.push({
    kind: kind || 'notice', actor: actor || null, text: String(text ?? ''),
    turn: state.snapshot && state.snapshot.turn ? state.snapshot.turn.number : null,
    ts: Date.now() / 1000, local: true,
  });
  if (state.localEntries.length > 40) state.localEntries.shift(); renderLog(true);
}
function logRow(entry) {
  const row = el('div', `log-entry kind-${entry.kind || 'system'}`);
  add(row, 'span', 'log-turn', entry.turn ? `T${entry.turn}` : '—'); const body = el('span', 'log-body');
  if (entry.actor) add(body, 'span', 'log-actor', `${entry.actor}: `);
  add(body, 'span', 'log-text', entry.text ?? ''); row.appendChild(body); return row;
}
function renderLog(force = false) {
  const server = (state.snapshot && Array.isArray(state.snapshot.log)) ? state.snapshot.log : [];
  const items = [...server, ...state.localEntries].sort((a, b) => (a.ts ?? 0) - (b.ts ?? 0));
  const signature = items.map((e) => `${e.seq ?? 'local'}:${e.kind}:${(e.text || '').length}:${e.ts ?? 0}`).join('|');
  if (!force && signature === state.logSignature) return; state.logSignature = signature;
  const box = els.log, previous = box.scrollTop; const atBottom = box.scrollHeight - previous - box.clientHeight < 48;
  const frag = document.createDocumentFragment(); for (const entry of items) frag.appendChild(logRow(entry));
  box.replaceChildren(frag); els.logCount.textContent = `${items.length} ${items.length === 1 ? 'entry' : 'entries'}`;
  box.scrollTop = atBottom ? box.scrollHeight : previous;
}
function chatItems() {
  const seen = new Set(), items = [];
  for (const entry of (state.snapshot && Array.isArray(state.snapshot.chat)) ? state.snapshot.chat : []) {
    if (!seen.has(entry.seq)) { seen.add(entry.seq); items.push(entry); }
  }
  for (const entry of state.chatExtra) {
    if (!seen.has(entry.seq)) { seen.add(entry.seq); items.push(entry); }
  }
  return items.sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0));
}
function renderChat(force = false) {
  const items = chatItems(); const signature = items.map((entry) => entry.seq).join(',');
  if (!force && signature === state.chatSignature) return; state.chatSignature = signature;
  const box = els.chat, previous = box.scrollTop; const atBottom = box.scrollHeight - previous - box.clientHeight < 40;
  const frag = document.createDocumentFragment();
  if (!items.length) frag.appendChild(el('p', 'empty tiny', 'No messages yet.'));
  for (const entry of items) {
    const row = el('div', 'chat-entry'); add(row, 'span', 'chat-actor', `${entry.actor || 'system'}:`);
    add(row, 'span', 'chat-text', entry.text ?? ''); frag.appendChild(row);
  }
  box.replaceChildren(frag); box.scrollTop = atBottom ? box.scrollHeight : previous;
}
function renderBanner() {
  const snap = state.snapshot, banner = els.finishedBanner;
  if (!snap || snap.state !== 'finished') { banner.hidden = true; banner.replaceChildren(); return; }
  banner.hidden = false; banner.replaceChildren();
  if (snap.winner) {
    add(banner, 'span', 'banner-label', 'victory'); add(banner, 'strong', 'banner-name', snap.winner);
    add(banner, 'span', 'banner-tail', 'claims the stool.');
  } else {
    add(banner, 'span', 'banner-label', 'game over'); add(banner, 'strong', 'banner-name', 'No victor');
  }
}
function updateTurnUi() {
  const snap = state.snapshot, input = els.commandInput, you = snap && snap.you;
  const finished = !snap || snap.state === 'finished';
  const activeId = snap && snap.turn ? snap.turn.active_player_id : null;
  const isMyTurn = Boolean(snap && snap.state === 'active' && you && !you.is_spectator && activeId === state.playerId);
  input.disabled = finished; els.endTurnBtn.disabled = !isMyTurn;
  input.classList.toggle('is-waiting', Boolean(snap && snap.state === 'active' && !isMyTurn));
  els.roomScreen.classList.toggle('my-turn', isMyTurn); let hint = ''; if (!snap) input.placeholder = '—';
  else if (snap.state === 'lobby') input.placeholder = 'the game has not started yet';
  else if (finished) input.placeholder = 'game over';
  else if (you && you.is_spectator) {
    input.placeholder = 'spectator — map · status · players · diplomacy · help';
    hint = 'Spectators can use look commands only.';
  }
  else if (isMyTurn) input.placeholder = 'your move — try: build farm · train archer · help';
  else {
    input.placeholder = 'not your turn — map · status · players · diplomacy · help';
    hint = `Waiting on ${(snap.turn && snap.turn.active_player_name) || '—'}.`;
  }
  els.turnHint.textContent = hint; els.turnHint.hidden = !hint;
}

/* ------------------------------------------------------------------ timer */
function ensureTicker() { if (!state.ticker) state.ticker = setInterval(updateTimer, 250); }
function updateTimer() {
  const node = els.turnTimer, snap = state.snapshot;
  if (!snap || snap.state !== 'active') {
    node.textContent = snap && snap.state === 'lobby' ? '—' : 'off'; node.classList.remove('urgent'); return;
  }
  const turn = snap.turn || {}; let left = null;
  // anchor on the server's seconds_left so client clock skew cannot skew the countdown
  if (typeof turn.seconds_left === 'number' && Number.isFinite(turn.seconds_left)) left = turn.seconds_left - (Date.now() - state.snapshotAt) / 1000;
  else if (typeof turn.deadline === 'number' && Number.isFinite(turn.deadline)) left = turn.deadline - Date.now() / 1000;
  if (left === null) { node.textContent = 'off'; node.classList.remove('urgent'); return; }
  left = Math.max(0, left); node.textContent = formatClock(left); node.classList.toggle('urgent', left <= 10);
}

/* --------------------------------------------------------------- commands */
function rememberCommand(command) {
  if (!command) return;
  if (state.history[state.history.length - 1] !== command) {
    state.history.push(command); if (state.history.length > MAX_HISTORY) state.history.shift();
  }
  state.historyIndex = -1; state.historyDraft = '';
}
function submitCommand() {
  const command = els.commandInput.value.trim(); if (!command) return;
  els.commandInput.value = ''; sendCommand(command);
}
async function sendCommand(command) {
  const clean = String(command || '').trim(); if (!clean || !state.roomCode || !state.playerId) return;
  rememberCommand(clean);
  try {
    const data = await api(`/api/rooms/${encodeURIComponent(state.roomCode)}/command`, { method: 'POST', body: { player_id: state.playerId, command: clean } });
    if (data && data.snapshot) applySnapshot(data.snapshot); els.commandInput.focus();
  } catch (err) { clientLog('notice', err.message); }
}
function navigateHistory(direction) {
  const input = els.commandInput; if (!state.history.length) return;
  if (state.historyIndex === -1) { state.historyDraft = input.value; state.historyIndex = state.history.length; }
  let next = state.historyIndex + direction; if (next < 0) next = 0;
  if (next >= state.history.length) { state.historyIndex = -1; input.value = state.historyDraft; return; }
  state.historyIndex = next; input.value = state.history[next]; const end = input.value.length;
  requestAnimationFrame(() => { try { input.setSelectionRange(end, end); } catch (_) { /* not focusable */ } });
}
function onCommandKeyDown(event) {
  if (event.key === 'Enter') { event.preventDefault(); submitCommand(); return; }
  if (event.key === 'ArrowUp') { event.preventDefault(); navigateHistory(-1); return; }
  if (event.key === 'ArrowDown') { event.preventDefault(); navigateHistory(1); return; }
  if (event.key === 'Escape') { event.preventDefault(); els.commandInput.value = ''; state.historyIndex = -1; }
}
async function endTurn() {
  if (!state.roomCode || !state.playerId) return; els.endTurnBtn.disabled = true;
  try {
    const data = await api(`/api/rooms/${encodeURIComponent(state.roomCode)}/end-turn`, { method: 'POST', body: { player_id: state.playerId } });
    if (data && data.snapshot) applySnapshot(data.snapshot);
  } catch (err) { clientLog('notice', err.message); } finally { updateTurnUi(); }
}
async function sendChat(event) {
  if (event) event.preventDefault();
  const text = els.chatInput.value.trim(); if (!text || !state.roomCode || !state.playerId) return;
  els.chatInput.value = '';
  try {
    const data = await api(`/api/rooms/${encodeURIComponent(state.roomCode)}/chat`, { method: 'POST', body: { player_id: state.playerId, text } });
    if (data && data.entry) {
      state.chatExtra.push(data.entry); if (state.chatExtra.length > 80) state.chatExtra.shift(); renderChat();
    }
  } catch (err) { clientLog('notice', err.message); }
}
async function startGame() {
  if (!state.roomCode || !state.playerId) return; els.startBtn.disabled = true;
  try {
    const data = await api(`/api/rooms/${encodeURIComponent(state.roomCode)}/start`, { method: 'POST', body: { player_id: state.playerId } });
    if (data && data.snapshot) applySnapshot(data.snapshot);
  } catch (err) {
    clientLog('notice', err.message); renderWaiting();
    // the log panel is hidden in the lobby, so surface the failure in the room header
    if (state.snapshot && state.snapshot.state === 'lobby') {
      els.startHint.hidden = false; els.startHint.textContent = err.message;
    }
  }
}
async function leaveRoom() {
  const code = state.roomCode, playerId = state.playerId; els.leaveBtn.disabled = true;
  try {
    if (code && playerId) await api(`/api/rooms/${encodeURIComponent(code)}/leave?player_id=${encodeURIComponent(playerId)}`, { method: 'DELETE' });
  } catch (_) {
    /* the room may already be gone — leaving locally is enough */
  } finally {
    els.leaveBtn.disabled = false;
  }
  returnToLobby('You left the room.');
}
async function copyCode() {
  const code = String(state.roomCode || els.roomCode.textContent || '').trim(); if (!code) return;
  try {
    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(code);
    else {
      const area = document.createElement('textarea'); area.value = code;
      area.setAttribute('readonly', ''); area.style.position = 'fixed';
      area.style.opacity = '0'; document.body.appendChild(area); area.select(); document.execCommand('copy');
      area.remove();
    }
    toast(`Room code ${code} copied`);
  } catch (_) { toast('Copy failed — select the code manually.'); }
}

/* ------------------------------------------------------------------- boot */
function cacheEls() {
  const ids = {
    lobbyScreen: 'lobby-screen', roomScreen: 'room-screen', lobbyNotice: 'lobby-notice',
    createForm: 'create-form', nameInput: 'name-input', civSelect: 'civ-select', civNote: 'civ-note',
    maxPlayers: 'max-players', turnSeconds: 'turn-seconds', createBtn: 'create-btn',
    joinForm: 'join-form', codeInput: 'code-input', joinBtn: 'join-btn', spectatorCheck: 'spectator-check',
    roomsList: 'rooms-list', roomsUpdated: 'rooms-updated',
    roomCode: 'room-code', copyCode: 'copy-code', statePill: 'state-pill',
    turnNumber: 'turn-number', activePlayer: 'active-player', turnTimer: 'turn-timer', connStatus: 'conn-status',
    startBtn: 'start-btn', startHint: 'start-hint', leaveBtn: 'leave-btn',
    finishedBanner: 'finished-banner', reconnectBanner: 'reconnect-banner',
    waitingPanel: 'waiting-panel', waitingPlayers: 'waiting-players', waitingNote: 'waiting-note', waitingCopy: 'waiting-copy',
    gameView: 'game-view', map: 'map', mapMeta: 'map-meta',
    statusAge: 'status-age', statusBody: 'status-body', playersList: 'players-list', playersCount: 'players-count',
    diplomacyList: 'diplomacy-list', log: 'log', logCount: 'log-count',
    commandInput: 'command-input', endTurnBtn: 'end-turn-btn', turnHint: 'turn-hint',
    chat: 'chat', chatForm: 'chat-form', chatInput: 'chat-input',
    healthLed: 'health-led', healthText: 'health-text', toast: 'toast',
  };
  for (const [key, id] of Object.entries(ids)) els[key] = document.getElementById(id);
}
function restorePrefs() {
  const prefs = loadPrefs(); if (prefs.name) els.nameInput.value = prefs.name;
  if (prefs.civ) state.pendingCiv = prefs.civ;
}
function bindEvents() {
  els.createForm.addEventListener('submit', createRoom);
  els.joinForm.addEventListener('submit', (event) => { event.preventDefault(); joinRoom(els.codeInput.value, els.spectatorCheck.checked); });
  els.codeInput.addEventListener('input', () => { els.codeInput.value = els.codeInput.value.toUpperCase().replace(/[^A-Z0-9]/g, ''); });
  els.civSelect.addEventListener('change', () => { updateCivNote(); savePrefs(els.nameInput.value.trim(), els.civSelect.value); });
  els.nameInput.addEventListener('input', () => { if (!els.lobbyNotice.hidden) setLobbyNotice(''); });
  els.startBtn.addEventListener('click', startGame); els.leaveBtn.addEventListener('click', leaveRoom);
  els.copyCode.addEventListener('click', copyCode); els.endTurnBtn.addEventListener('click', endTurn);
  els.chatForm.addEventListener('submit', sendChat); els.commandInput.addEventListener('keydown', onCommandKeyDown);
}
async function boot() {
  cacheEls(); bindEvents(); ensureTicker(); restorePrefs();
  state.roomsTimer = setInterval(() => refreshRooms(), ROOM_POLL_MS);
  state.healthTimer = setInterval(refreshHealth, HEALTH_POLL_MS);
  const resumed = await resumeSession(); await loadCivs();
  await refreshHealth(); if (!resumed) await refreshRooms(true);
}
boot();
