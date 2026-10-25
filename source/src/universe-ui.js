import { SoftwareField } from './software-field.js';
import { UniverseStore, CHANNELS, NODES, LIMITS, atomsOf, readPointer, kernelRecords, uid, stamp, permissionFor, utf8 } from './universe-core.js';
import { BitLens } from './bit-lens.js';
import { UniverseField } from './universe-field.js';

const LAYOUT = `
<div class="lu-tools"><button id="lu-reveal" class="lu-button" aria-pressed="false" title="Reveal inspectable records in the field">Reveal data</button><button id="lu-open" class="lu-button primary" aria-expanded="false" aria-controls="lu-field-panel">Instruments <span aria-hidden="true"> / I</span></button></div>
<button id="lu-state" class="lu-state" title="Open workspace instruments">LOCAL WORKSPACE</button>
<div id="lu-recall-ribbon" class="lu-recall-ribbon" hidden>RECORDED STATE / read-only <button id="lu-return" class="lu-button small">Return to present</button></div>
<aside id="lu-welcome" class="lu-welcome"><strong>A field you can understand.</strong><p>Peer into a record. Follow its history. Hold its actual bits. Your source stays local.</p><div class="lu-row"><button id="lu-begin" class="lu-button small primary">Open instruments</button><button id="lu-dismiss" class="lu-button small">Just explore</button></div><small>Sample objects are explicitly simulated.</small></aside>
<section id="lu-field-panel" class="lu-panel" aria-label="Universe instruments" hidden>
 <header class="lu-panel-head"><button class="lu-drag" aria-label="Move instruments card; use arrow keys">::</button><div class="lu-panel-title"><span class="lu-kicker">Living Universe / 0.3</span><strong>Observation instruments</strong></div><button class="lu-close" data-close="lu-field-panel" aria-label="Close instruments">&times;</button></header>
 <div class="lu-tabs" role="tablist" aria-label="Instrument modes"><button class="lu-tab" id="lu-tab-field" data-pane="field" role="tab" aria-selected="true" aria-controls="lu-pane-field">Field</button><button class="lu-tab" id="lu-tab-recall" data-pane="recall" role="tab" aria-selected="false" aria-controls="lu-pane-recall">Recall</button><button class="lu-tab" id="lu-tab-connect" data-pane="connect" role="tab" aria-selected="false" aria-controls="lu-pane-connect">Connect</button><button class="lu-tab" id="lu-tab-care" data-pane="care" role="tab" aria-selected="false" aria-controls="lu-pane-care">Nourish</button></div>
 <div id="lu-pane-field" class="lu-scroll" role="tabpanel" aria-labelledby="lu-tab-field">
  <p>Colored objects are inspectable records. The surrounding star field is decorative, not hidden telemetry.</p>
  <input id="lu-search" type="search" aria-label="Find objects" placeholder="Find a name, identity, or note..." autocomplete="off">
  <label for="lu-chamber">Chamber</label><select id="lu-chamber"><option value="core">Shared reality / source</option><option value="intelligence">Intelligence</option><option value="collaboration">Collaboration</option><option value="tools">Capabilities</option><option value="all">All chambers</option></select>
  <div id="lu-channels" class="lu-channels" role="group" aria-label="Filter the 12 information channels"></div>
  <div class="lu-row"><button id="lu-clear-filter" class="lu-button small">All channels</button><button id="lu-import" class="lu-button small primary">Import file</button></div>
  <div class="lu-count"><span id="lu-count"></span><span id="lu-filter-label">12 channels</span></div><div id="lu-objects" role="group" aria-label="Inspectable objects"></div>
 </div>
 <div id="lu-pane-recall" class="lu-scroll" role="tabpanel" aria-labelledby="lu-tab-recall" hidden>
  <h2>Remember what was recorded.</h2><p>Snapshots preserve workspace records, not unrecorded history or the entire machine. The newest 64 states are retained.</p>
  <div id="lu-recall-state" class="lu-callout">Present / editable workspace</div><label for="lu-timeline">Recorded state</label><input id="lu-timeline" class="lu-range" type="range" min="0" max="0" value="0">
  <div class="lu-row"><button id="lu-snapshot" class="lu-button small">Bookmark now</button><button id="lu-present" class="lu-button small primary">Present</button></div>
  <div class="lu-row"><button id="lu-undo" class="lu-button small">Undo edit</button><button id="lu-redo" class="lu-button small">Redo edit</button></div>
  <div id="lu-events"></div>
 </div>
 <div id="lu-pane-connect" class="lu-scroll" role="tabpanel" aria-labelledby="lu-tab-connect" hidden>
  <h2>Connect with evidence.</h2><p>Nothing is scanned, uploaded, or executed. Connections are opt-in and read-only.</p>
  <h3>01 / This visual application</h3><p>Measure this renderer: frame timing and available WebGL statistics, or software-renderer counts. These are not system-wide CPU or memory readings.</p><button id="lu-observe" class="lu-button" aria-pressed="false">Start browser observations</button>
  <h3>02 / Native C observer</h3><p>Launch the included C bridge, then open the local address it prints. Its random session key stays in memory, never in a workspace export.</p><div id="lu-bridge-status" class="lu-callout">No native bridge attached.</div><button id="lu-connect" class="lu-button" aria-pressed="false">Connect read-only bridge</button>
  <h3>03 / Kernel reports</h3><p>Import a QEMU serial log containing <code>@LU1</code> records. The dual-architecture Stage 0 patch emits these after firmware handoff. Reports are not proof of isolation.</p><button id="lu-import-log" class="lu-button small">Import a serial log</button>
  <h3>Workspace ownership</h3><p>Session-only by default. Save explicitly to this browser, or export a portable archive with retained history and original imported bytes.</p>
  <div class="lu-row"><button id="lu-save" class="lu-button small">Save locally</button><button id="lu-restore" class="lu-button small">Restore local</button></div><div class="lu-row"><button id="lu-export" class="lu-button small primary">Export workspace</button><button id="lu-forget" class="lu-button small danger">Forget saved</button></div>
  <div class="lu-callout warn">Exports may contain private data you imported. Store and share them deliberately. They are not encrypted.</div>
 </div>
 <div id="lu-pane-care" class="lu-scroll" role="tabpanel" aria-labelledby="lu-tab-care" hidden><h2>Nourish, without pretending.</h2><p>Inspect the health of this workspace. No automatic repairs or privileged system changes are performed.</p><div id="lu-diagnostics"></div><div class="lu-row"><button id="lu-light" class="lu-button small">Use lighter graphics</button><button id="lu-layout-reset" class="lu-button small">Reset card layout</button></div><h3>The seven instruments</h3><p><b>Peer</b> moves the camera to a record. <b>Inspect</b> reveals values and provenance. <b>Observe</b> records measured data. <b>Recall</b> visits recorded states. <b>Handle</b> moves local records. <b>Curate</b> pins, annotates, and extracts fragments. <b>Nourish</b> checks the workspace.</p><p>Touch, pointer, and keyboard operate the cards. The inherited VR scene supports traversal and record selection; detailed inspector cards currently require the desktop view.</p></div>
</section>
<section id="lu-inspector" class="lu-panel" aria-label="Object inspector" hidden>
 <header class="lu-panel-head"><button class="lu-drag" aria-label="Move inspector card; use arrow keys">::</button><div class="lu-panel-title"><span class="lu-kicker" id="lu-inspector-kicker">Object / inspect</span><strong id="lu-inspector-name">Select a record</strong></div><button class="lu-close" data-close="lu-inspector" aria-label="Close inspector">&times;</button></header>
 <div class="lu-tabs" role="tablist" aria-label="Object instruments"><button class="lu-tab" data-inspect="inspect" role="tab" aria-selected="true">Inspect</button><button class="lu-tab" data-inspect="bits" role="tab" aria-selected="false">Bits</button><button class="lu-tab" data-inspect="handle" role="tab" aria-selected="false">Handle</button><button class="lu-tab" data-inspect="history" role="tab" aria-selected="false">History</button></div>
 <div id="lu-detail" class="lu-scroll"></div>
</section><input id="lu-file" type="file" hidden>
`;

export function mountUniverse(runtime) {
  const root = document.createElement('div'); root.id = 'living-universe'; root.innerHTML = LAYOUT; document.body.append(root);
  const $ = selector => root.querySelector(selector), $$ = selector => [...root.querySelectorAll(selector)];
  const store = new UniverseStore(); const notice = runtime.notice || (text => { $('#lu-state').textContent = text; });
  let selected = null, chamber = 'core', channel = 0, query = '', inspectorTab = 'inspect', pointer = null, atomScope = false, bytePage = 0, byteSelected = 0, bitSelected = 0, lens = null;
  let observed = false, connected = false, bridgeBusy = false, observerTimer = null, bridgeTimer = null, atomLimit = 100, pending = false, lastPacket = null, lastRecall = null, busyImport = false;
  let frameTimes = [], previousFrame = 0;
  let bridgeKey = new URLSearchParams(location.hash.slice(1)).get('key') || '';
  if (!/^[a-f0-9]{64}$/.test(bridgeKey)) bridgeKey = '';
  if (bridgeKey && location.protocol !== 'file:') { try { history.replaceState(null, '', location.pathname + location.search); } catch {} }
  const element = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
  const action = (label, fn, cls = '') => { const b = element('button', `lu-button ${cls}`, label); b.addEventListener('click', () => safely(fn)); return b; };
  const safely = async fn => { try { await fn(); } catch (e) { notice(e.message || String(e)); } };
  const bind = (id, fn) => $(id).addEventListener('click', () => safely(fn));
  const show = id => { $(id).hidden = false; if (id === '#lu-field-panel') { $('#lu-open').setAttribute('aria-expanded', 'true'); $('#lu-welcome').hidden = true; } };
  const open = () => { show('#lu-field-panel'); $('#lu-search').focus({ preventScroll: true }); };
  const nodeChanged = node => { chamber = node; $('#lu-chamber').value = chamber; render(); };
  const field = runtime.experience ? new UniverseField(runtime, id => select(id), nodeChanged) : new SoftwareField({ onSelect: id => select(id), onNode: nodeChanged, notice });
  function filtered() { return store.view.filter(p => (chamber === 'all' || p.node === chamber) && (!channel || p.channel === channel) && (!query || `${p.name} ${p.id} ${p.note} ${p.quality}`.toLowerCase().includes(query))); }
  function reveal(value) { field?.show(value); $('#lu-reveal').setAttribute('aria-pressed', String(value)); $('#lu-reveal').textContent = value ? 'Hide data' : 'Reveal data'; if (!field && value) notice('Graphics unavailable. All data remains accessible in the instruments.'); }
  function select(id) { selected = id; pointer = null; atomLimit = 100; bytePage = byteSelected = bitSelected = 0; lastPacket = null; field?.select(id); show('#lu-inspector'); render(); const p = store.get(id); if (runtime.experience?.renderer.xr.isPresenting && p) notice(`${p.name} / ${p.quality}. Desktop instruments contain its detailed data.`); }
  function pane(name) { $$('[data-pane]').forEach(b => b.setAttribute('aria-selected', String(b.dataset.pane === name))); ['field', 'recall', 'connect', 'care'].forEach(n => $(`#lu-pane-${n}`).hidden = n !== name); }
  function badge(p) { const tag = element('span', 'lu-tag', p.provenance.recorded && p.quality === 'observed' ? 'recorded observation' : p.quality); tag.dataset.quality = p.quality; return tag; }
  function shortTime(value) { const d = new Date(value); return Number.isNaN(d.getTime()) ? 'Timestamp not verified' : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  function render() {
    pending = false; const list = filtered(); const frag = document.createDocumentFragment();
    for (const p of list) { const b = element('button', 'lu-object'); b.dataset.id = p.id; b.setAttribute('aria-pressed', String(selected === p.id)); b.style.setProperty('--channel', p.channel === 8 ? '#c8d1df' : CHANNELS[p.channel - 1].hex); const dot = element('span', 'lu-object-dot'); dot.setAttribute('aria-hidden', 'true'); const text = element('span', 'lu-object-copy'); text.append(element('strong', '', `${p.pinned ? '* ' : ''}${p.name}`), element('small', '', `${CHANNELS[p.channel - 1].role} / ${p.quality}`)); b.append(dot, text); b.addEventListener('click', () => select(p.id)); frag.append(b); }
    if (!list.length) frag.append(element('p', '', 'No records match. Clear the channel or search filter.'));
    $('#lu-objects').replaceChildren(frag); $('#lu-count').textContent = `${list.length} / ${store.view.length} records`;
    $('#lu-filter-label').textContent = channel ? CHANNELS[channel - 1].role : '12 channels';
    const simulated = store.view.filter(p => p.quality === 'simulated').length;
    $('#lu-state').textContent = `${store.isRecall ? 'RECALL / READ-ONLY' : 'LOCAL WORKSPACE'} / ${store.view.length} OBJECTS / ${simulated} SAMPLE`;
    $('#lu-state').dataset.recall = String(store.isRecall); $('#lu-recall-ribbon').hidden = !store.isRecall;
    field?.setPackets(list);
    const slider = $('#lu-timeline'); slider.max = String(Math.max(0, store.frames.length - 1)); slider.value = String(store.cursor ?? store.frames.length - 1);
    $('#lu-recall-state').textContent = store.isRecall ? `Recorded ${shortTime(store.frames[store.cursor].time)} / read-only` : 'Present / editable local workspace';
    $('#lu-undo').disabled = store.isRecall || !store.undoStack.length; $('#lu-redo').disabled = store.isRecall || !store.redoStack.length; $('#lu-snapshot').disabled = store.isRecall;
    const events = document.createDocumentFragment(); store.frames.map((f, index) => ({ f, index })).reverse().forEach(({ f, index }) => { const b = element('button', 'lu-event'); b.setAttribute('aria-current', String(index === store.cursor)); b.append(element('small', '', `${shortTime(f.time)} / ${f.kind} / ${f.packets.length} objects`), element('span', '', f.label)); b.addEventListener('click', () => safely(() => store.recall(index))); events.append(b); }); $('#lu-events').replaceChildren(events);
    const diagnostics = document.createDocumentFragment(); for (const d of store.diagnose()) { const item = element('div', 'lu-diagnostic'); item.dataset.ok = String(d.ok); item.append(element('strong', '', d.title), element('p', '', d.value)); diagnostics.append(item); } $('#lu-diagnostics').replaceChildren(diagnostics);
    const p = selected && store.get(selected); if (!p && selected) { $('#lu-detail').replaceChildren(element('p', '', 'This record did not exist in the selected state. Return to the present or select another record.')); lastPacket = null; }
    if (p && !$('#lu-inspector').hidden && (p !== lastPacket || store.isRecall !== lastRecall)) { if (!$('#lu-detail').contains(document.activeElement) || !document.activeElement.matches('textarea')) renderDetail(p); }
  }
  store.addEventListener('change', () => { if (!pending) { pending = true; requestAnimationFrame(render); } });
  function renderDetail(p) {
    lens?.dispose(); lens = null; lastPacket = p; lastRecall = store.isRecall;
    $('#lu-inspector-name').textContent = p.name; $('#lu-inspector-kicker').textContent = `${CHANNELS[p.channel - 1].role} / ${p.quality}`;
    const detail = $('#lu-detail'); detail.replaceChildren();
    const identity = element('div', 'lu-row'); identity.append(badge(p), element('span', 'lu-meta', `${NODES[p.node].name} / rev ${p.revision}`)); detail.append(identity);
    if (store.isRecall) detail.append(element('div', 'lu-callout warn', 'Recorded state. Changes are blocked until you return to the present.'));
    if (inspectorTab === 'inspect') renderInspect(detail, p);
    if (inspectorTab === 'bits') renderBits(detail, p);
    if (inspectorTab === 'handle') renderHandle(detail, p);
    if (inspectorTab === 'history') renderHistory(detail, p);
  }
  function refreshDetail() { const p = store.get(selected); if (p) renderDetail(p); }
  function renderInspect(detail, p) {
    detail.append(element('p', '', p.provenance.description), element('div', 'lu-id', `ID ${p.id}`));
    if (p.provenance.digest) detail.append(element('div', 'lu-id', `SHA-256 ${p.provenance.digest}`));
    if (p.provenance.parentId) detail.append(element('div', 'lu-id', `Parent ${p.provenance.parentId} / ${p.provenance.pointer || '(root)'}`));
    const row = element('div', 'lu-row'); row.append(action('Peer closer', () => { chamber = p.node; channel = 0; query = ''; $('#lu-chamber').value = chamber; $('#lu-search').value = ''; render(); reveal(true); field?.peer(p.id); }, 'small'), action('Inspect bits', () => { inspectorTab = 'bits'; syncInspectorTabs(); refreshDetail(); }, 'small primary')); detail.append(row);
    detail.append(element('h3', '', 'Payload / select a property'));
    const rootButton = element('button', 'lu-atom'); rootButton.textContent = '(root) / full payload'; rootButton.setAttribute('aria-pressed', String(pointer === '')); rootButton.addEventListener('click', () => { pointer = ''; refreshDetail(); }); detail.append(rootButton);
    const atoms = atomsOf(p.payload); const tree = element('div', 'lu-tree');
    for (const atom of atoms.slice(0, atomLimit)) { const b = element('button', 'lu-atom'); b.dataset.pointer = atom.path; b.setAttribute('aria-pressed', String(pointer === atom.path)); b.append(element('span', 'lu-path', atom.path || '(root)'), element('span', 'lu-value', JSON.stringify(atom.value))); b.addEventListener('click', () => { pointer = atom.path; refreshDetail(); }); tree.append(b); }
    detail.append(tree);
    if (atoms.length > atomLimit) detail.append(action(`Show more (${atoms.length - atomLimit} remaining)`, () => { atomLimit += 100; refreshDetail(); }, 'small'));
    if (pointer !== null) { detail.append(element('div', 'lu-callout', `Selected ${pointer || '(root)'}. Bits can inspect its UTF-8 JSON representation. Handle can extract its exact value.`)); }
  }
  function renderBits(detail, p) {
    const checkRow = element('label', 'lu-row'); const check = element('input'); check.type = 'checkbox'; check.checked = atomScope; check.addEventListener('change', () => { atomScope = check.checked; bytePage = byteSelected = bitSelected = 0; refreshDetail(); }); checkRow.append(check, document.createTextNode('Use selected property (JSON representation)')); detail.append(checkRow);
    const result = store.bytesFor(p, atomScope ? pointer || '' : null), bytes = result.bytes;
    if (!bytes.length) { detail.append(element('p', '', 'This file contains zero bytes. There are no bits to inspect.')); return; }
    bytePage = Math.min(bytePage, Math.max(0, Math.ceil(bytes.length / 64) - 1)); byteSelected = Math.min(byteSelected, bytes.length - 1);
    const offset = bytePage * 64;
    detail.append(element('p', '', result.label), element('div', 'lu-meta', `${bytes.length.toLocaleString()} bytes / ${(bytes.length * 8).toLocaleString()} bits / MSB first`));
    const canvas = element('canvas', 'lu-lens'); canvas.setAttribute('aria-label', 'Perspective voxel microscope: 8 bits per byte, 8 bytes per row, 8 rows. Drag to rotate. Use byte and bit buttons for keyboard access.'); detail.append(canvas);
    const hint = element('p', '', 'Drag the cube to rotate. Select a voxel or use the exact byte/bit controls below. Mint = 1. Violet = 0.'); detail.append(hint);
    const selectedInfo = element('div', 'lu-callout'); selectedInfo.id = 'lu-bit-readout'; detail.append(selectedInfo);
    const bits = element('div', 'lu-bits'); detail.append(bits);
    const rangeRow = element('div', 'lu-row'); rangeRow.append(action('Previous 64', () => { bytePage = Math.max(0, bytePage - 1); byteSelected = bytePage * 64; bitSelected = byteSelected * 8; refreshDetail(); }, 'small'), element('span', 'lu-meta', `${offset} - ${Math.min(offset + 63, bytes.length - 1)}`), action('Next 64', () => { bytePage = Math.min(Math.ceil(bytes.length / 64) - 1, bytePage + 1); byteSelected = bytePage * 64; bitSelected = byteSelected * 8; refreshDetail(); }, 'small')); detail.append(rangeRow);
    const hex = element('div', 'lu-hex');
    for (let i = offset; i < Math.min(offset + 64, bytes.length); i++) { const b = element('button', 'lu-byte', bytes[i].toString(16).padStart(2, '0').toUpperCase()); b.dataset.offset = String(i); b.setAttribute('aria-label', `Byte ${i}: ${bytes[i]} decimal`); b.addEventListener('click', () => chooseBit(i * 8)); hex.append(b); } detail.append(hex);
    const jumpLabel = element('label', '', 'Jump to byte offset'); jumpLabel.htmlFor = 'lu-byte-offset'; const jump = element('input'); jump.id = 'lu-byte-offset'; jump.type = 'number'; jump.min = '0'; jump.max = String(bytes.length - 1); jump.value = String(byteSelected); detail.append(jumpLabel, jump, action('Go to byte', () => { const n = Number(jump.value); if (!Number.isInteger(n) || n < 0 || n >= bytes.length) throw Error('Byte offset is outside this record.'); byteSelected = n; bitSelected = n * 8; bytePage = Math.floor(n / 64); refreshDetail(); }, 'small'));
    const chooseBit = index => {
      bitSelected = index; byteSelected = Math.floor(index / 8); const value = bytes[byteSelected], bit = 7 - index % 8;
      selectedInfo.textContent = `Byte ${byteSelected} (0x${byteSelected.toString(16).padStart(4, '0')}) = ${value} / 0x${value.toString(16).padStart(2, '0').toUpperCase()} / bit ${bit} = ${(value >> bit) & 1}`;
      bits.replaceChildren(); for (let b = 7; b >= 0; b--) { const button = element('button', 'lu-bit', String((value >> b) & 1)); button.dataset.value = String((value >> b) & 1); button.setAttribute('aria-label', `Bit ${b}: ${(value >> b) & 1}`); button.setAttribute('aria-pressed', String(bit === b)); button.addEventListener('click', () => chooseBit(byteSelected * 8 + 7 - b)); bits.append(button); }
      hex.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.offset) === byteSelected))); jump.value = String(byteSelected); lens?.set(bytes, offset, index);
    };
    lens = new BitLens(canvas, chooseBit); chooseBit(Math.min(bitSelected, bytes.length * 8 - 1));
  }
  function renderHandle(detail, p) {
    detail.append(element('p', '', 'These actions affect only records in this workspace. Moving a record does not move a host file, execute a tool, or grant a capability.'));
    const noteLabel = element('label', '', 'Annotation'); noteLabel.htmlFor = 'lu-note'; const note = element('textarea'); note.id = 'lu-note'; note.maxLength = LIMITS.note; note.value = p.note; detail.append(noteLabel, note);
    const row = element('div', 'lu-row'); row.append(action('Save note', () => store.annotate(p.id, note.value), 'small primary'), action(p.pinned ? 'Unpin' : 'Pin object', () => store.pin(p.id), 'small')); detail.append(row);
    const label = element('label', '', 'Destination'); label.htmlFor = 'lu-destination'; const dest = element('select'); dest.id = 'lu-destination'; for (const node of Object.values(NODES)) { const o = element('option', '', node.name); o.value = node.id; dest.append(o); } dest.value = p.node; detail.append(label, dest);
    detail.append(action('Move local record', () => { if (confirm(`Move "${p.name}" to ${NODES[dest.value].name}? This changes only your workspace.`)) store.route(p.id, dest.value); }, 'small'));
    detail.append(element('h3', '', 'Curate a fragment'), element('p', '', `Copy the exact value at ${pointer || '(root)'} into a new record, retaining parent identity and JSON pointer.`));
    detail.append(action('Extract selected value', () => { const fragment = store.cloneAtom(p.id, pointer || '', dest.value); select(fragment.id); notice('Created a derived record with parent provenance.'); }, 'small'));
    detail.append(element('h3', '', 'External permissions'), element('div', 'lu-callout warn', permissionFor('native.execute').boundary), element('p', '', 'Native execution, filesystem writes, network tools, and device control remain unavailable. Browser-side labels are not a security sandbox.'));
    if (store.isRecall) detail.querySelectorAll('button,textarea,select').forEach(e => e.disabled = true);
  }
  function renderHistory(detail, p) {
    detail.append(element('p', '', 'Only states retained in this workspace can be recalled. Evidence imported from another workspace is recorded, not live.'));
    let previous = null; const frames = []; store.frames.forEach((frame, index) => { const value = frame.packets.find(x => x.id === p.id); if (value && value !== previous) frames.push({ frame, index }); previous = value; });
    for (const { frame, index } of frames.reverse()) { const b = element('button', 'lu-event'); b.append(element('small', '', shortTime(frame.time)), element('span', '', frame.label)); b.addEventListener('click', () => store.recall(index)); detail.append(b); }
  }
  function syncInspectorTabs() { $$('[data-inspect]').forEach(b => b.setAttribute('aria-selected', String(b.dataset.inspect === inspectorTab))); }
  for (const c of CHANNELS) { const b = element('button', 'lu-channel'); b.style.setProperty('--channel', c.id === 8 ? '#c8d1df' : c.hex); b.append(element('span'), document.createTextNode(String(c.id).padStart(2, '0'))); b.title = c.role; b.setAttribute('aria-label', `${c.id}: ${c.role}`); b.setAttribute('aria-pressed', 'false'); b.dataset.channel = c.id; b.addEventListener('click', () => { channel = channel === c.id ? 0 : c.id; updateChannelButtons(); render(); }); $('#lu-channels').append(b); }
  function updateChannelButtons() { $$('.lu-channel').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.channel) === channel))); }
  bind('#lu-open', () => { if ($('#lu-field-panel').hidden) open(); else { $('#lu-field-panel').hidden = true; $('#lu-open').setAttribute('aria-expanded', 'false'); } });
  bind('#lu-begin', open); bind('#lu-state', open); bind('#lu-dismiss', () => { $('#lu-welcome').hidden = true; });
  bind('#lu-reveal', () => reveal(!field?.enabled));
  $$('[data-close]').forEach(b => b.addEventListener('click', () => { $(`#${b.dataset.close}`).hidden = true; if (b.dataset.close === 'lu-field-panel') $('#lu-open').setAttribute('aria-expanded', 'false'); if (b.dataset.close === 'lu-inspector') { lens?.dispose(); lens = null; lastPacket = null; } }));
  $$('[data-pane]').forEach(b => b.addEventListener('click', () => pane(b.dataset.pane)));
  $$('[data-inspect]').forEach(b => b.addEventListener('click', () => { inspectorTab = b.dataset.inspect; syncInspectorTabs(); refreshDetail(); }));
  // Standard arrow-key navigation for both tab strips.
  $$('.lu-tabs').forEach(strip => strip.addEventListener('keydown', e => { if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return; const tabs = [...strip.querySelectorAll('[role=tab]')]; let index = tabs.indexOf(document.activeElement); if (index < 0) return; e.preventDefault(); e.stopPropagation(); index = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : (index + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length; tabs[index].click(); tabs[index].focus(); }));
  $('#lu-search').addEventListener('input', e => { query = e.target.value.toLowerCase().trim(); render(); });
  $('#lu-chamber').addEventListener('change', e => { chamber = e.target.value; render(); });
  bind('#lu-clear-filter', () => { channel = 0; updateChannelButtons(); render(); });
  $('#lu-timeline').addEventListener('input', e => safely(() => store.recall(Number(e.target.value))));
  bind('#lu-snapshot', () => store.snapshot()); bind('#lu-present', () => store.present()); bind('#lu-return', () => store.present()); bind('#lu-undo', () => store.undo()); bind('#lu-redo', () => store.redo());
  bind('#lu-light', () => { runtime.experience?.setQuality('low'); if (!runtime.experience) field.quality = 'low'; const selector = document.querySelector('#quality'); if (selector) selector.value = 'low'; notice('Light detail selected. Original bytes and records are unchanged.'); });
  function resetLayout() { $$('.lu-panel').forEach(p => { p.style.removeProperty('left'); p.style.removeProperty('right'); p.style.removeProperty('top'); p.style.removeProperty('width'); p.style.removeProperty('height'); }); }
  bind('#lu-layout-reset', resetLayout);
  bind('#lu-save', () => { localStorage.setItem('living-universe.workspace.v1', store.exportText()); notice('Workspace and retained history saved in this browser. Export is the portable backup.'); });
  bind('#lu-restore', () => { const saved = localStorage.getItem('living-universe.workspace.v1'); if (!saved) throw Error('No explicitly saved workspace in this browser.'); if (confirm('Replace this session with your saved workspace? Export unsaved work first.')) { store.importWorkspace(saved); selected = null; $('#lu-inspector').hidden = true; notice('Restored recorded workspace. Live connections were not imported.'); } });
  bind('#lu-forget', () => { if (confirm('Delete only the saved Living Universe workspace from this browser? The current session is unchanged.')) { localStorage.removeItem('living-universe.workspace.v1'); notice('Saved copy removed. Current session remains in memory.'); } });
  const download = (text, name, type = 'application/json') => { const u = URL.createObjectURL(new Blob([text], { type })); const a = element('a'); a.href = u; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(u), 1000); };
  bind('#lu-export', () => { download(store.exportText(), `LivingUniverse-${new Date().toISOString().replaceAll(':', '-')}.lu.json`); notice('Exported records, original byte attachments, and retained history. No native permissions or session keys included.'); });
  bind('#lu-import', () => $('#lu-file').click()); bind('#lu-import-log', () => $('#lu-file').click());
  $('#lu-file').addEventListener('change', () => safely(async () => {
    const file = $('#lu-file').files[0]; $('#lu-file').value = ''; if (!file || busyImport) return; busyImport = true;
    try {
      const workspace = /\.lu\.json$/i.test(file.name); if (file.size > (workspace ? LIMITS.workspaceBytes : LIMITS.fileBytes)) throw Error(workspace ? 'Workspace limit: 8 MiB.' : 'Selected file limit: 256 KiB.');
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (workspace) { if (confirm('Replace this workspace with the imported archive? Export unsaved work first.')) { store.importWorkspace(new TextDecoder().decode(bytes)); selected = null; $('#lu-inspector').hidden = true; notice('Imported recorded workspace. No permissions were imported.'); } return; }
      const p = await store.importBytes(file.name, bytes, chamber === 'all' ? 'core' : chamber, channel || 6); select(p.id);
      if (/\.(log|jsonl|txt)$/i.test(file.name)) { const result = kernelRecords(new TextDecoder().decode(bytes)); for (const record of result.records) store.upsertObservation(record, `Imported ${record.payload.arch} serial report`); if (result.records.length || result.errors.length) notice(`${result.records.length} valid Stage 0 reports / ${result.errors.length} rejected records. Raw file bytes retained.`); else notice('Imported locally. No @LU1 kernel records found.'); }
      else notice('Imported locally. Original selected-file bytes are available in Bits.');
    } finally { busyImport = false; }
  }));
  // Measurements come from the actual renderer, never invented machine telemetry.
  if (runtime.experience) { const e = runtime.experience, frame = e.frame.bind(e); e.frame = t => { if (observed && !document.hidden) { if (previousFrame && t > previousFrame) { frameTimes.push(t - previousFrame); if (frameTimes.length > 360) frameTimes.shift(); } previousFrame = t; } frame(t); }; }
  function browserObservation() {
    if (!observed || store.isRecall || document.hidden) return;
    if (!runtime.experience) { store.upsertObservation({id:'observed-software-renderer',name:'Software renderer / observation',channel:9,node:'core',quality:'observed',source:'software-renderer',payload:{...field.stats,sampledAt:stamp(),scope:'this Canvas2D renderer only'},provenance:{description:'Actual counters from the software fallback. No GPU or system-wide metrics are claimed.'}},'Recorded software renderer counters'); return; }
    const e = runtime.experience, count = frameTimes.length, mean = count ? frameTimes.reduce((a, b) => a + b, 0) / count : null; frameTimes = [];
    store.upsertObservation({ id: 'observed-browser-renderer', name: 'Browser / renderer observation', channel: 9, node: 'core', quality: 'observed', source: 'browser-renderer', payload: { sampledAt: stamp(), frameMeanMs: mean === null ? null : Number(mean.toFixed(2)), frameSamples: count, drawCalls: e.renderer.info.render.calls, triangles: e.renderer.info.render.triangles, geometryCount: e.renderer.info.memory.geometries, viewport: { width: innerWidth, height: innerHeight }, detail: e.quality, scope: 'this browser renderer only' }, provenance: { description: 'Measured from this application. Timing under emulation or background throttling is not a hardware performance benchmark.' } }, 'Recorded browser renderer measurements');
  }
  bind('#lu-observe', () => { observed = !observed; $('#lu-observe').setAttribute('aria-pressed', String(observed)); $('#lu-observe').textContent = observed ? 'Stop browser observations' : 'Start browser observations'; clearInterval(observerTimer); frameTimes = []; previousFrame = 0; if (observed) { observerTimer = setInterval(() => safely(browserObservation), 5000); browserObservation(); notice('Recording browser measurements every 5 seconds. Pauses during recall or when hidden.'); } });
  async function bridgeObservation() {
    if (!connected || bridgeBusy || store.isRecall || document.hidden) return;
    bridgeBusy = true;
    try {
      const response = await fetch('/api/snapshot', { method: 'GET', headers: { 'X-Universe-Key': bridgeKey }, credentials: 'omit', mode: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(4000) });
      if (!response.ok) throw Error(`Bridge refused the request (${response.status}).`);
      const text = await response.text(); if (text.length > 524288) throw Error('Bridge response exceeds limits.'); const data = JSON.parse(text);
      if (data.schema !== 'living-universe.bridge' || data.version !== 1 || data.read_only !== true) throw Error('Unsupported native bridge contract.');
      if (store.isRecall || !connected) return;
      const serial = typeof data.serial_log === 'string' ? data.serial_log : ''; delete data.serial_log;
      store.upsertObservation({ id: 'observed-native-bridge', name: 'Native C / observer process', channel: 9, node: 'core', quality: 'observed', source: 'same-origin-c-bridge', payload: data, provenance: { description: 'Read-only measurements reported by the local C bridge process. It is a hosted observer, not the bare-metal kernel.' } }, 'Recorded native C observer measurement');
      if (serial) { const result = kernelRecords(serial); for (const p of result.records) if (!store.packets.some(x => x.id === p.id)) store.upsertObservation(p, 'Received kernel serial report through read-only bridge'); }
      $('#lu-bridge-status').textContent = `Connected / read-only / ${data.architecture || 'native'} / ${shortTime(stamp())}`;
    } catch (e) { connected = false; clearInterval(bridgeTimer); $('#lu-connect').textContent = 'Connect read-only bridge'; $('#lu-connect').setAttribute('aria-pressed', 'false'); $('#lu-bridge-status').textContent = e.message; notice(e.message); }
    finally { bridgeBusy = false; }
  }
  bind('#lu-connect', async () => {
    if (!bridgeKey || !['http:', 'https:'].includes(location.protocol) || !['127.0.0.1', 'localhost'].includes(location.hostname)) throw Error('Open the local URL printed by Launch-LivingUniverse-Native. Portable HTML can import logs without a server.');
    connected = !connected; $('#lu-connect').setAttribute('aria-pressed', String(connected)); $('#lu-connect').textContent = connected ? 'Disconnect bridge' : 'Connect read-only bridge'; clearInterval(bridgeTimer);
    if (connected) { await bridgeObservation(); if (connected) bridgeTimer = setInterval(bridgeObservation, 5000); } else $('#lu-bridge-status').textContent = 'Disconnected. Previously recorded measurements remain available.';
  });
  if (bridgeKey) $('#lu-bridge-status').textContent = 'Native session key received. Select Connect to begin read-only observation.';
  // Movable cards. Keyboard users can focus the grip and move in 10 px steps.
  $$('.lu-panel').forEach(panel => {
    const grip = panel.querySelector('.lu-drag'); let drag = null;
    function move(x, y) { const r = panel.getBoundingClientRect(); panel.style.right = 'auto'; panel.style.left = `${Math.max(0, Math.min(innerWidth - Math.min(r.width, innerWidth), x))}px`; panel.style.top = `${Math.max(0, Math.min(innerHeight - 64, y))}px`; }
    grip.addEventListener('pointerdown', e => { const r = panel.getBoundingClientRect(); drag = { x: e.clientX - r.left, y: e.clientY - r.top }; grip.setPointerCapture(e.pointerId); e.preventDefault(); });
    grip.addEventListener('pointermove', e => { if (drag) move(e.clientX - drag.x, e.clientY - drag.y); });
    for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) grip.addEventListener(type, () => { drag = null; });
    grip.addEventListener('keydown', e => { const delta = { ArrowLeft: [-10, 0], ArrowRight: [10, 0], ArrowUp: [0, -10], ArrowDown: [0, 10] }[e.key]; if (!delta) return; e.preventDefault(); e.stopPropagation(); const r = panel.getBoundingClientRect(); move(r.left + delta[0], r.top + delta[1]); });
  });
  window.addEventListener('resize', resetLayout);
  // Stop flight shortcuts inside cards without trapping normal form navigation.
  root.addEventListener('keydown', e => { e.stopPropagation(); if (e.key === 'Escape') { if (!$('#lu-inspector').hidden) { $('#lu-inspector').hidden = true; lens?.dispose(); lens = null; lastPacket = null; } else { $('#lu-field-panel').hidden = true; $('#lu-open').setAttribute('aria-expanded', 'false'); } } });
  window.addEventListener('keydown', e => { if (e.repeat || e.ctrlKey || e.metaKey || e.altKey || e.target.matches('input,textarea,select,[contenteditable]')) return; if (e.key.toLowerCase() === 'i') { e.preventDefault(); $('#lu-open').click(); } });
  document.addEventListener('visibilitychange', () => { frameTimes = []; previousFrame = 0; });
  document.querySelector('.wordmark small').textContent = 'The Living Universe';
  document.querySelector('.menu-footer').textContent = 'Spatial prototype / local records / opt-in read-only observations. No native executor.';
  window.livingUniverse = Object.freeze({ store, field, select, open, exportWorkspace: () => store.exportText(), version: '0.3.0' });
  render();
  return window.livingUniverse;
}
