// A dependency-free perspective bit microscope. Every voxel maps to one real bit.
// Software rendering avoids a second WebGL context and works with the offline bundle.
import { bitAt } from './universe-core.js';
export class BitLens {
  constructor(canvas, onSelect) {
    this.canvas = canvas; this.ctx = canvas.getContext('2d'); this.onSelect = onSelect; this.yaw = -.65; this.pitch = .48; this.bytes = new Uint8Array(); this.offset = 0; this.selected = -1; this.points = []; this.drag = null; this.dirty = true;
    this.down = e => { this.drag = { x: e.clientX, y: e.clientY, startX: e.clientX, startY: e.clientY }; canvas.setPointerCapture(e.pointerId); };
    this.move = e => { if (!this.drag) return; this.yaw += (e.clientX - this.drag.x) * .009; this.pitch = Math.max(-1.3, Math.min(1.3, this.pitch + (e.clientY - this.drag.y) * .009)); this.drag.x = e.clientX; this.drag.y = e.clientY; this.draw(); };
    this.up = e => { if (this.drag && Math.hypot(e.clientX - this.drag.startX, e.clientY - this.drag.startY) < 5) { const r = canvas.getBoundingClientRect(), x = (e.clientX - r.left) * canvas.width / r.width, y = (e.clientY - r.top) * canvas.height / r.height; const p = [...this.points].reverse().find(p => Math.abs(x - p.x) < p.s + 3 && Math.abs(y - p.y) < p.s + 3); if (p) { this.selected = p.index; this.onSelect(p.index); this.draw(); } } this.drag = null; };
    this.cancel = () => { this.drag = null; };
    canvas.addEventListener('pointerdown', this.down); canvas.addEventListener('pointermove', this.move); canvas.addEventListener('pointerup', this.up); canvas.addEventListener('pointercancel', this.cancel);
    this.resize = new ResizeObserver(() => this.draw()); this.resize.observe(canvas);
  }
  set(bytes, offset, selected) { this.bytes = bytes; this.offset = offset; this.selected = selected; this.draw(); }
  project(x, y, z, w, h) { const a = Math.cos(this.yaw), b = Math.sin(this.yaw), c = Math.cos(this.pitch), d = Math.sin(this.pitch); const xx = x * a + z * b, zz = z * a - x * b, yy = y * c - zz * d, depth = y * d + zz * c; const scale = Math.min(w / 12, h / 11) * 16 / (16 + depth); return { x: w / 2 + xx * scale, y: h / 2 + yy * scale, z: depth, s: scale * .23 }; }
  draw() {
    const rect = this.canvas.getBoundingClientRect(); const w = Math.max(250, Math.round(rect.width * Math.min(devicePixelRatio || 1, 2))), h = Math.round(w * .68); this.canvas.width = w; this.canvas.height = h;
    const c = this.ctx; if (!c) return; c.clearRect(0, 0, w, h); this.points = [];
    for (let i = 0; i < 512; i++) { const index = this.offset * 8 + i; if (index >= this.bytes.length * 8) break; const p = this.project((i % 8) - 3.5, (Math.floor(i / 8) % 8) - 3.5, Math.floor(i / 64) - 3.5, w, h); this.points.push({ ...p, index, bit: bitAt(this.bytes, index) }); }
    this.points.sort((a, b) => b.z - a.z);
    for (const p of this.points) { const sel = Math.floor(p.index / 8) === Math.floor(this.selected / 8), exact = p.index === this.selected; c.globalAlpha = exact ? 1 : sel ? .96 : p.bit ? .68 : .20; c.fillStyle = exact ? '#ffffff' : p.bit ? '#65ffe2' : '#ac87ff'; c.strokeStyle = sel ? '#f9e67e' : p.bit ? '#7bfff0' : '#b99aff'; const s = p.s * (exact ? 1.25 : 1); c.fillRect(p.x - s, p.y - s, s * 2, s * 2); c.strokeRect(p.x - s, p.y - s, s * 2, s * 2); }
    c.globalAlpha = 1;
  }
  dispose() { this.resize.disconnect(); for (const [type, fn] of [['pointerdown', this.down], ['pointermove', this.move], ['pointerup', this.up], ['pointercancel', this.cancel]]) this.canvas.removeEventListener(type, fn); }
}
