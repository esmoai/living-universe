import { CHANNELS, hashText } from './universe-core.js';
export class UniverseField {
  constructor(runtime, onSelect, onNode) {
    this.runtime = runtime; this.e = runtime.experience; this.T = runtime.types; this.onSelect = onSelect; this.onNode = onNode; this.enabled = false; this.items = []; this.selected = null;
    const T = this.T; this.root = new T.Group(); this.root.name = 'Evidence objects (not decorative stars)'; this.e.scene.add(this.root);
    this.sphere = new T.SphereGeometry(.075, 10, 8); this.box = new T.BoxGeometry(.12, .12, .12);
    this.materials = CHANNELS.map(c => new T.MeshBasicMaterial({ color: c.id === 8 ? '#b8c4dc' : c.hex }));
    this.halo = new T.Mesh(new T.SphereGeometry(.18, 16, 12), new T.MeshBasicMaterial({ color: '#e9fff9', wireframe: true, transparent: true, opacity: .55, depthWrite: false })); this.halo.visible = false; this.root.add(this.halo);
    const e = this.e;
    const oldSelect = e.select.bind(e), oldHover = e.updateHover.bind(e), oldFrame = e.frame.bind(e), oldHome = e.home.bind(e), oldFinish = e.finishTravel.bind(e);
    e.select = ray => { if (e.transition) return; const hit = this.hit(ray); if (hit) { this.select(hit.userData.packet.id); onSelect(hit.userData.packet.id); } else oldSelect(ray); };
    e.updateHover = () => { if (!e.transition && !e.drag && !document.querySelector('dialog[open]') && e.pointer.x >= 0 && this.root.visible && !e.renderer.xr.isPresenting) { const hit = this.hit(e.cast(e.pointer.x, e.pointer.y)); if (hit) { e.renderer.domElement.style.cursor = 'pointer'; const p = hit.userData.packet; e.callbacks.onHover?.({ id: p.id, label: `${p.name} / ${p.quality}`, x: e.pointer.x, y: e.pointer.y }); return; } } oldHover(); };
    e.frame = time => { this.root.visible = this.enabled && !e.transition; if (this.halo.visible) this.halo.rotation.y = e.time * .4; if (this.label) { this.label.visible = Boolean(this.selected) && e.renderer.xr.isPresenting; this.label.quaternion.copy(e.camera.quaternion); } oldFrame(time); };
    e.home = () => { oldHome(); onNode('core'); };
    e.finishTravel = () => { const id = e.transition?.portal?.id; oldFinish(); onNode(({ 'rear-left': 'intelligence', 'rear-right': 'collaboration', bottom: 'tools' })[id] || 'core'); };
    // The original animation callback calls the instance's frame method dynamically.
    this.root.visible = false;
  }
  positionFor(p) {
    const h = parseInt(hashText(p.id), 16), phi = (h % 65536) / 65536 * Math.PI * 2, y = ((h >>> 16) / 65535) * 1.7 - .85, r = 2.55 + (p.channel % 4) * .15;
    return new this.T.Vector3(Math.sqrt(1 - y * y) * Math.cos(phi) * r, y * r, Math.sqrt(1 - y * y) * Math.sin(phi) * r);
  }
  setPackets(packets) {
    for (const item of this.items) this.root.remove(item); this.items = [];
    for (const p of packets) { const m = new this.T.Mesh(p.quality === 'imported' ? this.box : this.sphere, this.materials[p.channel - 1]); m.position.copy(this.positionFor(p)); if (p.pinned) m.scale.setScalar(1.5); m.userData.packet = p; this.root.add(m); this.items.push(m); }
    this.select(this.selected); this.root.updateMatrixWorld(true);
  }
  show(value) { this.enabled = value; this.root.visible = value && !this.e.transition; }
  hit(ray) { if (!this.root.visible) return null; this.root.updateMatrixWorld(true); const hit = ray.intersectObjects(this.items, false)[0]; return hit?.object || null; }
  select(id) { this.selected = id; const m = this.items.find(x => x.userData.packet.id === id); this.halo.visible = Boolean(m); if (m) this.halo.position.copy(m.position); }
  peer(id) {
    const m = this.items.find(x => x.userData.packet.id === id); if (!m) return;
    const e = this.e; if (e.transition) return;
    if (e.renderer.xr.isPresenting) { e.notice('Object selected. Detailed byte inspection is available in the desktop instruments.'); return; }
    e.activateFly(); e.flyCamera.position.copy(m.position.clone().multiplyScalar(1.6)); e.flyCamera.lookAt(m.position); e.keepInWorld();
  }
}
