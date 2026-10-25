import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { ReferenceWorld } from './world.js';
import { XRNavigation } from './xr.js';
import { createJourney, canTypeTarget } from './navigation.js';
import { PORTALS, V } from './geometry.js';

export const DESTINATIONS = {
  'rear-left': { name: 'Intelligence', subtitle: 'The knowledge field', color: '#ac70ff' },
  'rear-right': { name: 'Collaboration', subtitle: 'The shared presence', color: '#ff53c6' },
  bottom: { name: 'Capabilities', subtitle: 'The action space', color: '#58ffe0' },
};
const UP = V(0, 1, 0), ease = t => t * t * (3 - 2 * t);
const blocked = () => !!document.querySelector('dialog[open]');

export class CubeExperience {
  constructor(container, callbacks = {}) {
    this.callbacks = callbacks;
    this.mode = 'orbit'; this.time = 0; this.last = 0; this.keys = new Set();
    this.reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.paused = this.reduced; this.comfort = true; this.speed = 1;
    this.node = { name: 'Shared reality', subtitle: 'Source / Destination', visit: 0 };
    this.transition = null; this.nextWorld = null; this.tunnel = null;
    this.pointer = { x: -100, y: -100, moved: false }; this.down = null; this.drag = null;
    this.touchMove = { x: 0, y: 0, vertical: 0 };
    this.ray = new THREE.Raycaster(); this.hovered = null; this.listeners = [];
    this.quality = innerWidth < 800 || devicePixelRatio > 2 ? 'medium' : 'high';
    this.scene = new THREE.Scene(); this.scene.background = new THREE.Color(0);
    this.orbitCamera = new THREE.OrthographicCamera(-6, 6, 6, -6, .02, 180);
    this.orbitCamera.position.set(12, 12, 12); this.orbitCamera.lookAt(0, 0, 0);
    this.flyCamera = new THREE.PerspectiveCamera(68, innerWidth / innerHeight, .018, 180);
    this.camera = this.orbitCamera;
    this.rig = new THREE.Group(); this.rig.add(this.flyCamera); this.scene.add(this.rig);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 1.65));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace; this.renderer.toneMapping = THREE.NoToneMapping;
    this.renderer.setClearColor(0x000000, 1); this.renderer.xr.enabled = true; this.renderer.xr.setFoveation(1);
    this.renderer.setSize(innerWidth, innerHeight); container.append(this.renderer.domElement);
    const canvas = this.renderer.domElement;
    canvas.tabIndex = 0;
    canvas.setAttribute('aria-label', 'Interactive open cube. Drag to orbit. Select the globe to enter or a funnel to travel. Press H for controls.');
    this.controls = new OrbitControls(this.orbitCamera, canvas);
    Object.assign(this.controls, { enableDamping: true, dampingFactor: .075, enablePan: false, minZoom: .55, maxZoom: 4, rotateSpeed: .5, zoomSpeed: .85 });
    this.controls.target.set(0, 0, 0);
    this.world = new ReferenceWorld({ quality: this.quality }); this.scene.add(this.world.root);
    this.xr = new XRNavigation({ renderer: this.renderer, rig: this.rig, camera: this.flyCamera,
      onSelect: ray => { if (!this.transition) this.select(ray); }, onHome: () => this.home(),
      onSessionChange: active => this.xrSession(active), onNotice: text => this.notice(text) });
    this.fade = new THREE.Mesh(new THREE.SphereGeometry(.09, 24, 16), new THREE.MeshBasicMaterial({ color: 0, side: THREE.BackSide, transparent: true, opacity: 0, depthTest: false, depthWrite: false }));
    this.fade.renderOrder = 10000; this.fade.frustumCulled = false; this.fade.visible = false; this.flyCamera.add(this.fade);
    this.setupInput(); this.resize(); this.renderer.setAnimationLoop(stamp => this.frame(stamp));
  }
  notice(text) { this.callbacks.onNotice?.(text); }
  listen(target, type, fn, options) { target.addEventListener(type, fn, options); this.listeners.push(() => target.removeEventListener(type, fn, options)); }
  setMode(mode) { this.mode = mode; this.controls.enabled = mode === 'orbit' && !this.renderer.xr.isPresenting; this.callbacks.onMode?.(mode); this.clearHover(); }
  clearHover() { this.hovered = null; this.world.setEmphasis(null); this.callbacks.onHover?.(null); this.renderer.domElement.style.cursor = this.mode === 'orbit' ? 'grab' : 'crosshair'; }

  activateFly() {
    if (this.camera === this.flyCamera) return;
    const direction = this.orbitCamera.position.clone().sub(this.controls.target).normalize();
    const fit = (this.viewHeight / 2) / Math.tan(THREE.MathUtils.degToRad(this.flyCamera.fov / 2)) / this.orbitCamera.zoom;
    this.flyCamera.position.copy(direction.multiplyScalar(fit)); this.flyCamera.quaternion.copy(this.orbitCamera.quaternion);
    this.rig.position.set(0, 0, 0); this.rig.quaternion.identity(); this.camera = this.flyCamera; this.setMode('inside');
  }
  enter() {
    if (this.transition) return;
    if (this.renderer.xr.isPresenting) { this.placeHead(V(1.3, .75, 1.3)); this.notice('Inside the coalescence. Point at a portal and trigger to travel.'); return; }
    this.activateFly();
    const direction = this.flyCamera.position.clone().normalize();
    if (!direction.lengthSq()) direction.set(1, .58, 1).normalize();
    const target = direction.multiplyScalar(1.98), temp = this.flyCamera.clone(false);
    temp.position.copy(target); temp.lookAt(0, 0, 0);
    this.transition = { kind: 'enter', elapsed: 0, duration: this.reduced ? .01 : 1.8,
      from: this.flyCamera.position.clone(), to: target, fromQ: this.flyCamera.quaternion.clone(), toQ: temp.quaternion.clone() };
    this.callbacks.onJourney?.({ active: true, name: 'Entering the coalescence', progress: 0 });
  }
  disposeJourney() {
    if (this.tunnel) { this.scene.remove(this.tunnel); this.tunnel.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); }); this.tunnel = null; }
    if (this.nextWorld) { this.scene.remove(this.nextWorld.root); this.nextWorld.dispose(); this.nextWorld = null; }
    this.transition = null; this.fade.visible = false; this.fade.material.opacity = 0; this.callbacks.onJourney?.({ active: false });
  }
  home() {
    this.disposeJourney(); this.keys.clear(); this.touchMove = { x: 0, y: 0, vertical: 0 };
    this.node = { name: 'Shared reality', subtitle: 'Source / Destination', visit: 0 }; this.callbacks.onNode?.(this.node);
    if (this.renderer.xr.isPresenting) {
      this.rig.quaternion.identity(); this.rig.position.set(0, 0, 0); this.placeHead(V(0, 1.1, 8.8)); this.setMode('inside'); this.notice('Returned to the source chamber.'); return;
    }
    this.rig.position.set(0, 0, 0); this.rig.quaternion.identity(); this.flyCamera.position.set(0, 0, 0); this.flyCamera.quaternion.identity();
    this.camera = this.orbitCamera; this.controls.reset(); this.orbitCamera.position.set(12, 12, 12); this.orbitCamera.zoom = 1;
    this.controls.target.set(0, 0, 0); this.controls.update(); this.orbitCamera.updateProjectionMatrix(); this.setMode('orbit');
  }
  travel(portalOrId) {
    if (this.transition) return;
    const portal = typeof portalOrId === 'string' ? PORTALS.find(p => p.id === portalOrId) : portalOrId;
    if (!portal) return;
    this.activateFly(); this.keys.clear();
    const journey = createJourney(portal, this.headPosition());
    this.nextWorld = new ReferenceWorld({ quality: this.quality === 'high' ? 'medium' : this.quality });
    this.nextWorld.root.position.copy(journey.end); this.scene.add(this.nextWorld.root);
    this.tunnel = this.makeTunnel(journey); this.scene.add(this.tunnel);
    const instant = this.reduced || (this.renderer.xr.isPresenting && this.comfort);
    this.transition = { ...journey, kind: 'travel', portal, elapsed: 0, duration: instant ? .6 : journey.duration, instant };
    this.setMode('travel'); this.callbacks.onJourney?.({ active: true, name: `To ${DESTINATIONS[portal.id].name}`, progress: 0 });
  }
  makeTunnel(journey) {
    const group = new THREE.Group(); group.name = 'Traversable continuation';
    const curve = new THREE.Curve();
    curve.getPoint = (t, target = V()) => journey.curve.getPointAt(journey.mouthProgress + (1 - journey.mouthProgress) * t, target);
    const geo = new THREE.TubeGeometry(curve, 210, 1.6, 48, false), p = geo.attributes.position, n = geo.attributes.normal, uv = geo.attributes.uv;
    for (let i = 0; i < p.count; i++) {
      const t = uv.getX(i), r = .19 * Math.exp(-t * 14) + .65 * Math.pow(t, 10);
      p.setXYZ(i, p.getX(i) + n.getX(i) * r, p.getY(i) + n.getY(i) * r, p.getZ(i) + n.getZ(i) * r);
    }
    geo.computeBoundingSphere();
    const material = new THREE.ShaderMaterial({ side: THREE.DoubleSide, transparent: true, depthWrite: false,
      uniforms: { uTime: { value: 0 } },
      vertexShader: 'varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
      fragmentShader: `varying vec2 vUv;uniform float uTime;
      vec3 hue(float h){vec3 p=abs(fract(vec3(h)+vec3(0.,2./3.,1./3.))*6.-3.);return clamp(p-1.,0.,1.);}
      void main(){
        vec2 grid=vec2(vUv.x*64.,vUv.y*32.);
        vec2 edge=abs(fract(grid-.5)-.5)/max(fwidth(grid),vec2(.001));
        float line=1.-min(min(edge.x,edge.y),1.);
        float signal=pow(.5+.5*cos((vUv.x*15.-uTime*.75)*6.283),16.);
        float fiber=pow(.5+.5*cos((vUv.y*8.+vUv.x*.6+uTime*.08)*6.283),18.);
        vec3 c=hue(vUv.y+vUv.x*.34-uTime*.025);
        gl_FragColor=vec4(mix(c,vec3(1.),signal*fiber*.52),.02+line*.79+signal*fiber*.46);
        #include <colorspace_fragment>
      }` });
    group.add(new THREE.Mesh(geo, material)); return group;
  }
  finishTravel() {
    const tr = this.transition; if (!tr || tr.kind !== 'travel') return;
    if (this.renderer.xr.isPresenting) this.placeHead(tr.arrivalOffset);
    else { this.flyCamera.position.copy(tr.arrivalOffset); this.flyCamera.lookAt(0, 0, 0); }
    // Rebase at a complete chamber; repeated crossings keep coordinates small.
    this.node = { ...DESTINATIONS[tr.portal.id], visit: this.node.visit + 1 };
    this.disposeJourney(); this.setMode('inside'); this.callbacks.onNode?.(this.node);
    this.notice(`${this.node.name} · chamber ${String(this.node.visit).padStart(2, '0')}. Explore, or choose another portal.`);
  }
  syncXR() { if (this.renderer.xr.isPresenting) { this.rig.updateMatrixWorld(true); this.renderer.xr.updateCamera(this.flyCamera); } }
  headPosition() { this.syncXR(); return this.flyCamera.getWorldPosition(V()); }
  placeHead(target) { const head = this.headPosition(); this.rig.position.add(target.clone().sub(head)); this.syncXR(); }
  xrSession(active) {
    this.disposeJourney(); this.keys.clear();
    if (active) {
      this.rig.position.set(0, 0, 0); this.rig.quaternion.identity(); this.flyCamera.position.set(0, 0, 0); this.flyCamera.quaternion.identity();
      this.camera = this.flyCamera; this.rig.position.set(0, this.xr.referenceSpaceType === 'local' ? 1.1 : -.5, 8.8); this.setMode('inside');
    } else {
      this.flyCamera.fov = 68; this.flyCamera.zoom = 1; this.flyCamera.aspect = innerWidth / innerHeight; this.flyCamera.updateProjectionMatrix();
      this.home();
    }
    this.callbacks.onXR?.(active);
  }
  async enterVR() { await this.xr.enter(); }
  setQuality(quality) {
    if (!['low', 'medium', 'high'].includes(quality) || quality === this.quality || this.transition) return;
    const next = new ReferenceWorld({ quality }); this.scene.remove(this.world.root); this.world.dispose(); this.world = next; this.scene.add(next.root); this.quality = quality;
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, quality === 'low' ? 1 : quality === 'medium' ? 1.4 : 1.8)); this.resize();
  }
  cast(x, y) {
    this.world.root.updateMatrixWorld(true); this.camera.updateMatrixWorld(true);
    this.ray.setFromCamera(new THREE.Vector2(x / innerWidth * 2 - 1, 1 - y / innerHeight * 2), this.camera); return this.ray;
  }
  targetFor(ray) {
    const hits = ray.intersectObjects([...this.world.portals.map(p => p.hit), this.world.globeHit], false);
    for (const hit of hits) {
      if (hit.object.userData.portal) return { id: hit.object.userData.portal.id, portal: hit.object.userData.portal };
      if (this.mode === 'orbit') return { id: 'globe' };
    }
    return null;
  }
  select(ray) { if (this.transition) return; const target = this.targetFor(ray); if (target?.portal) this.travel(target.portal); else if (target) this.enter(); }
  updateHover() {
    if (this.transition || this.drag || blocked() || this.pointer.x < 0 || this.renderer.xr.isPresenting) return this.clearHover();
    const target = this.targetFor(this.cast(this.pointer.x, this.pointer.y)), id = target?.id || null;
    if (id !== this.hovered) { this.hovered = id; this.world.setEmphasis(id); this.renderer.domElement.style.cursor = id ? 'pointer' : this.mode === 'orbit' ? 'grab' : 'crosshair'; }
    this.callbacks.onHover?.(id ? { id, label: id === 'globe' ? 'Enter the coalescence' : `Travel to ${DESTINATIONS[id].name}`, x: this.pointer.x, y: this.pointer.y } : null);
  }
  setupInput() {
    const canvas = this.renderer.domElement;
    this.listen(canvas, 'pointerdown', e => {
      if (this.transition || blocked()) return;
      this.down = { x: e.clientX, y: e.clientY, id: e.pointerId };
      if (this.mode !== 'orbit') { this.drag = { x: e.clientX, y: e.clientY }; canvas.setPointerCapture(e.pointerId); }
    });
    this.listen(canvas, 'pointermove', e => {
      this.pointer = { x: e.clientX, y: e.clientY, moved: true };
      if (this.drag && !this.transition && !this.renderer.xr.isPresenting) {
        const rot = new THREE.Euler().setFromQuaternion(this.flyCamera.quaternion, 'YXZ');
        rot.y -= (e.clientX - this.drag.x) * .0033; rot.x = THREE.MathUtils.clamp(rot.x - (e.clientY - this.drag.y) * .0033, -1.53, 1.53);
        this.flyCamera.quaternion.setFromEuler(rot); this.drag = { x: e.clientX, y: e.clientY };
      }
    });
    this.listen(canvas, 'pointerup', e => {
      const click = this.down && this.down.id === e.pointerId && Math.hypot(e.clientX - this.down.x, e.clientY - this.down.y) < 5;
      this.down = null; this.drag = null; if (click && !this.transition) this.select(this.cast(e.clientX, e.clientY));
    });
    this.listen(canvas, 'pointercancel', () => { this.down = null; this.drag = null; });
    this.listen(canvas, 'pointerleave', () => { this.pointer.x = -100; this.clearHover(); });
    this.listen(canvas, 'contextmenu', e => e.preventDefault());
    this.listen(canvas, 'wheel', e => { if (this.mode === 'inside' && !this.transition && !blocked()) { e.preventDefault(); this.flyCamera.position.addScaledVector(this.flyCamera.getWorldDirection(V()), -Math.sign(e.deltaY) * .27); this.keepInWorld(); } }, { passive: false });
    this.listen(window, 'keydown', e => {
      if (canTypeTarget(e.target) || blocked()) return;
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key) || (e.key === ' ' && !['BUTTON', 'SUMMARY'].includes(e.target.tagName))) e.preventDefault();
      this.keys.add(e.key.toLowerCase()); if (e.repeat) return;
      if (['1', '2', '3'].includes(e.key)) this.travel(PORTALS[Number(e.key) - 1]);
      if (e.key === 'Home') { e.preventDefault(); this.home(); }
      if (e.key === 'Escape' && this.transition) { this.home(); this.notice('Journey cancelled. Returned to the reference view.'); }
      if (e.key === 'Enter' && !['BUTTON', 'SUMMARY', 'A'].includes(e.target.tagName)) this.mode === 'orbit' ? this.enter() : this.home();
    });
    this.listen(window, 'keyup', e => this.keys.delete(e.key.toLowerCase()));
    this.listen(window, 'blur', () => { this.keys.clear(); this.drag = null; this.touchMove.x = 0; this.touchMove.y = 0; this.touchMove.vertical = 0; });
    this.listen(document, 'visibilitychange', () => { this.keys.clear(); this.last = 0; });
    this.listen(window, 'resize', () => this.resize());
    this.listen(canvas, 'webglcontextlost', e => { e.preventDefault(); this.contextLost = true; this.callbacks.onError?.('Graphics were interrupted. Reload this page to restore the field.'); });
  }
  keepInWorld() {
    const p = this.flyCamera.position, len = p.length();
    if (len < 1.38) { if (len < .0001) p.set(1.38, 0, 0); else p.setLength(1.38); }
    if (len > 35) p.setLength(35);
  }
  resize() {
    const aspect = innerWidth / innerHeight; this.viewHeight = aspect < 1 ? 10.8 / aspect : 13.5;
    const width = this.viewHeight * aspect;
    Object.assign(this.orbitCamera, { left: -width / 2, right: width / 2, top: this.viewHeight / 2, bottom: -this.viewHeight / 2 });
    this.orbitCamera.updateProjectionMatrix(); this.flyCamera.aspect = aspect; this.flyCamera.updateProjectionMatrix();
    this.renderer.setSize(innerWidth, innerHeight); this.pointScale = innerHeight / this.viewHeight;
  }
  frame(stamp) {
    const dt = Math.min((stamp - (this.last || stamp)) / 1000, .05); this.last = stamp;
    if (this.contextLost || (document.hidden && !this.renderer.xr.isPresenting)) return;
    this.syncXR();
    if (!this.paused) this.time += dt * this.speed;
    const params = { pixelRatio: this.renderer.getPixelRatio(), pointScale: this.pointScale * this.orbitCamera.zoom, perspective: this.camera.isPerspectiveCamera };
    this.world.update(this.time, params); this.nextWorld?.update(this.time, params);
    if (this.tunnel) this.tunnel.children[0].material.uniforms.uTime.value = this.time;
    if (this.transition) this.updateTransition(dt);
    else if (this.mode === 'orbit') this.controls.update();
    else if (!this.renderer.xr.isPresenting && !blocked()) this.updateFlight(dt);
    if (this.renderer.xr.isPresenting) {
      this.xr.update(dt, { blocked: !!this.transition });
      if (!this.transition) {
        const head = this.headPosition(), distance = head.length();
        if (distance < 1.38 || distance > 35) this.placeHead(distance < .0001 ? V(1.38, 0, 0) : head.clone().setLength(THREE.MathUtils.clamp(distance, 1.38, 35)));
        this.checkPortalCrossing(this.headPosition());
      }
    }
    if (!this.renderer.xr.isPresenting && (this.pointer.moved || !this.paused)) { this.updateHover(); this.pointer.moved = false; }
    this.renderer.render(this.scene, this.camera);
  }
  updateTransition(dt) {
    const tr = this.transition; tr.elapsed += dt;
    const p = Math.min(1, tr.elapsed / tr.duration), s = ease(p);
    if (tr.kind === 'enter') { this.flyCamera.position.lerpVectors(tr.from, tr.to, s); this.flyCamera.quaternion.slerpQuaternions(tr.fromQ, tr.toQ, s); }
    else if (tr.instant) {
      this.fade.visible = true; this.fade.material.opacity = Math.sin(Math.PI * p);
      if (p > .5 && !tr.placed) { const pos = tr.curve.getPointAt(1); if (this.renderer.xr.isPresenting) this.placeHead(pos); else { this.flyCamera.position.copy(pos); this.flyCamera.lookAt(tr.end); } tr.placed = true; }
    } else {
      const pos = tr.curve.getPointAt(s);
      if (this.renderer.xr.isPresenting) this.placeHead(pos);
      else {
        this.flyCamera.position.copy(pos);
        const look = tr.curve.getPointAt(Math.min(1, s + .018)).lerp(tr.end, THREE.MathUtils.smoothstep(p, .89, 1));
        if (look.distanceToSquared(pos) > .00001) { const q = this.flyCamera.quaternion.clone(); this.flyCamera.lookAt(look); const desired = this.flyCamera.quaternion.clone(); this.flyCamera.quaternion.copy(q).slerp(desired, Math.min(1, dt * 7)); }
      }
    }
    this.callbacks.onJourney?.({ active: true, name: tr.kind === 'enter' ? 'Entering the coalescence' : `To ${DESTINATIONS[tr.portal.id].name}`, progress: p });
    if (p >= 1) {
      if (tr.kind === 'travel') this.finishTravel();
      else { this.transition = null; this.callbacks.onJourney?.({ active: false }); this.notice('Inside the field · drag to look, W A S D to fly. Select a portal to continue.'); }
    }
  }
  updateFlight(dt) {
    const forward = this.flyCamera.getWorldDirection(V()), right = V().crossVectors(forward, UP).normalize(), input = V();
    const key = (...keys) => keys.some(k => this.keys.has(k));
    const f = Number(key('w', 'arrowup')) - Number(key('s', 'arrowdown')) + this.touchMove.y;
    const r = Number(key('d', 'arrowright')) - Number(key('a', 'arrowleft')) + this.touchMove.x;
    const u = Number(key('e')) - Number(key('q')) + this.touchMove.vertical;
    input.addScaledVector(forward, f).addScaledVector(right, r); input.y += u;
    if (input.lengthSq() > 1) input.normalize();
    this.flyCamera.position.addScaledVector(input, dt * (this.keys.has('shift') ? 4.5 : 1.8)); this.keepInWorld();
    if (input.lengthSq() > .05) this.checkPortalCrossing(this.flyCamera.position);
  }
  checkPortalCrossing(position) {
    for (const item of this.world.portals) {
      const offset = position.clone().sub(V(...item.portal.center));
      const normal = V(...item.portal.normal), depth = offset.dot(normal), radial = offset.clone().addScaledVector(normal, -depth).length();
      if (Math.abs(depth) < .19 && radial < 1.5) { this.travel(item.portal); break; }
    }
  }
  dispose() {
    this.renderer.setAnimationLoop(null); this.disposeJourney(); this.listeners.forEach(fn => fn());
    this.xr.dispose(); this.controls.dispose(); this.world.dispose(); this.fade.geometry.dispose(); this.fade.material.dispose(); this.renderer.dispose(); this.renderer.domElement.remove();
  }
}
