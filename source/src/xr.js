import * as THREE from 'three';

const UP = new THREE.Vector3(0, 1, 0);
const FORWARD = new THREE.Vector3(0, 0, -1);
const SNAP_ANGLE = Math.PI / 6;
const MOVE_SPEED = 1.9;
const LIFT_SPEED = 1.35;
const DEAD_ZONE = 0.2;

function axis(value) {
  if (!Number.isFinite(value) || Math.abs(value) <= DEAD_ZONE) return 0;
  return Math.sign(value) * Math.min(1, (Math.abs(value) - DEAD_ZONE) / (1 - DEAD_ZONE));
}

function sessionError(error) {
  if (error?.name === 'NotAllowedError' || error?.name === 'SecurityError') {
    return 'VR permission was not granted. Allow immersive VR in your headset browser, then try again.';
  }
  if (error?.name === 'NotSupportedError') {
    return 'This browser could not start immersive VR. Open the page directly in a compatible headset browser.';
  }
  if (error?.name === 'InvalidStateError') {
    return 'Another immersive session is already running. Exit that session, then try VR again.';
  }
  return error?.message || 'The VR session could not start. Desktop and touch exploration are still available.';
}

/**
 * Native WebXR navigation for the same world used by desktop exploration.
 * The owner places the rig on session start and owns scene selection/travel.
 * Headset pose is always owned by WebXR; this class only moves the parent rig.
 */
export class XRNavigation {
  constructor({ renderer, rig, camera, onSelect, onHome, onSessionChange, onNotice }) {
    this.renderer = renderer;
    this.rig = rig;
    this.camera = camera;
    this.onSelect = onSelect || (() => {});
    this.onHome = onHome || (() => {});
    this.onSessionChange = onSessionChange || (() => {});
    this.onNotice = onNotice || (() => {});
    this.controllers = [];
    this.referenceSpaceType = 'local-floor';
    this.support = null;
    this.blocked = false;
    this._records = [];
    this._resources = new Set();
    this._listeners = [];
    this._entering = false;
    this._disposed = false;
    this._head = new THREE.Vector3();
    this._forward = new THREE.Vector3();
    this._right = new THREE.Vector3();
    this._move = new THREE.Vector3();
    this._worldRig = new THREE.Vector3();
    this._pivotOffset = new THREE.Vector3();
    this._rotation = new THREE.Quaternion();
    this._worldRotation = new THREE.Quaternion();
    this._parentRotation = new THREE.Quaternion();
    this._lastForward = new THREE.Vector3(0, 0, -1);

    renderer.xr.enabled = true;
    renderer.xr.setReferenceSpaceType(this.referenceSpaceType);

    this._listen(renderer.xr, 'sessionstart', () => {
      this.blocked = false;
      this._resetInput();
      this.onSessionChange(true);
    });
    this._listen(renderer.xr, 'sessionend', () => {
      this.blocked = false;
      this._resetInput();
      this.onSessionChange(false);
    });

    const dotGeometry = this._own(new THREE.SphereGeometry(0.007, 8, 6));
    const gripGeometry = this._own(new THREE.CapsuleGeometry(0.016, 0.06, 3, 6));
    const beamGeometry = this._own(new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0, -0.02), new THREE.Vector3(0, 0, -1),
    ]));

    for (let i = 0; i < 2; i++) {
      const color = i === 0 ? 0x4cffe3 : 0xff60d6;
      const controller = renderer.xr.getController(i);
      const grip = renderer.xr.getControllerGrip(i);
      const hand = renderer.xr.getHand(i);
      const material = this._own(new THREE.MeshBasicMaterial({ color }));
      const beamMaterial = this._own(new THREE.LineBasicMaterial({
        color, transparent: true, opacity: 0.42, depthWrite: false,
      }));
      const beam = new THREE.Line(beamGeometry, beamMaterial);
      beam.name = 'XR selection ray';
      beam.scale.z = 7;
      const tip = new THREE.Mesh(dotGeometry, material);
      tip.position.z = -7;
      tip.scale.setScalar(0.7);
      const handle = new THREE.Mesh(gripGeometry, material);
      handle.rotation.x = Math.PI / 2;
      handle.position.z = -0.015;
      handle.name = 'XR controller grip';
      controller.add(beam, tip);
      grip.add(handle);
      rig.add(controller, grip, hand);
      this.controllers.push(controller);

      const record = {
        controller, grip, hand, beam, tip, handle, material, beamMaterial,
        source: null, raycaster: new THREE.Raycaster(), dots: [],
        snapped: false, homeDown: false, lastSelection: -Infinity,
      };
      record.raycaster.far = 35;
      this._records.push(record);

      this._listen(controller, 'connected', event => {
        record.source = event.data;
        controller.userData.xrInputSource = event.data;
        record.snapped = false;
        record.homeDown = false;
        handle.visible = !event.data?.hand;
        this._attachHandDots(record, dotGeometry, material);
      });
      this._listen(controller, 'disconnected', () => {
        record.source = null;
        delete controller.userData.xrInputSource;
        record.snapped = false;
        record.homeDown = false;
        beam.visible = false;
        tip.visible = false;
      });
      this._listen(controller, 'selectstart', () => this._select(record));
      // Three.js also emits pinchstart for tracked hands. Dedupe it against
      // runtimes that emit the native selectstart event for the same pinch.
      this._listen(controller, 'pinchstart', () => this._select(record));
    }
  }

  _own(resource) {
    this._resources.add(resource);
    return resource;
  }

  _listen(target, type, handler) {
    target.addEventListener(type, handler);
    this._listeners.push({ target, type, handler });
  }

  _attachHandDots(record, geometry, material) {
    if (!record.source?.hand || record.dots.length) return;
    for (const name of ['index-finger-tip', 'thumb-tip']) {
      const joint = record.hand.joints?.[name];
      if (!joint) continue;
      const dot = new THREE.Mesh(geometry, material);
      dot.name = name;
      joint.add(dot);
      record.dots.push(dot);
    }
  }

  _resetInput() {
    for (const record of this._records) {
      record.snapped = false;
      record.homeDown = false;
      record.lastSelection = -Infinity;
      record.beam.visible = !!record.source;
      record.tip.visible = !!record.source;
      record.beamMaterial.opacity = 0.42;
    }
  }

  _select(record) {
    if (this._disposed || this.blocked || !this.renderer.xr.isPresenting || !record.controller.visible) return;
    const now = performance.now();
    if (now - record.lastSelection < 180) return;
    record.lastSelection = now;
    record.controller.updateWorldMatrix(true, false);
    record.raycaster.ray.origin.setFromMatrixPosition(record.controller.matrixWorld);
    record.raycaster.ray.direction.copy(FORWARD).transformDirection(record.controller.matrixWorld);
    try {
      this.onSelect(record.raycaster, record.controller);
    } catch (error) {
      this.onNotice(error?.message || 'That destination is not available.');
    }
  }

  async checkSupport() {
    if (!globalThis.isSecureContext) {
      this.support = { supported: false, reason: 'VR needs HTTPS or localhost. Desktop exploration is available here.' };
    } else if (!globalThis.navigator?.xr) {
      this.support = { supported: false, reason: 'Open this page in a compatible WebXR headset browser to enter VR.' };
    } else {
      try {
        const supported = await navigator.xr.isSessionSupported('immersive-vr');
        this.support = {
          supported,
          reason: supported ? 'Ready for immersive VR.' : 'No immersive VR headset is available in this browser. Desktop and touch exploration work here.',
        };
      } catch {
        this.support = { supported: false, reason: 'This browser could not check VR support. Open the page directly in a headset browser.' };
      }
    }
    return this.support;
  }

  async enter() {
    if (this._disposed) throw new Error('The VR view has been closed. Reload the page to start again.');
    const current = this.renderer.xr.getSession();
    if (current) {
      await current.end();
      return;
    }
    if (this._entering) return;
    this._entering = true;
    let session;
    try {
      const support = this.support?.supported ? this.support : await this.checkSupport();
      if (!support.supported) throw new Error(support.reason);
      session = await navigator.xr.requestSession('immersive-vr', {
        optionalFeatures: ['local-floor', 'bounded-floor', 'hand-tracking'],
      });
      // Some headsets support immersive VR without a floor reference space.
      // Probe before handing the session to Three.js, which requires the
      // configured reference-space request to succeed.
      try {
        await session.requestReferenceSpace('local-floor');
        this.referenceSpaceType = 'local-floor';
      } catch {
        await session.requestReferenceSpace('local');
        this.referenceSpaceType = 'local';
      }
      this.renderer.xr.setReferenceSpaceType(this.referenceSpaceType);
      this.renderer.xr.setFramebufferScaleFactor(1);
      await this.renderer.xr.setSession(session);
      this.renderer.xr.setFoveation(0.65);
    } catch (error) {
      if (session) {
        try { await session.end(); } catch { /* Session may already have ended. */ }
      }
      throw new Error(sessionError(error));
    } finally {
      this._entering = false;
    }
  }

  /** Move by a world-space vector even if the rig has a transformed parent. */
  _translateWorld(vector) {
    this.rig.getWorldPosition(this._worldRig).add(vector);
    if (this.rig.parent) this.rig.parent.worldToLocal(this._worldRig);
    this.rig.position.copy(this._worldRig);
    this.rig.updateMatrixWorld(true);
  }

  /** Snap around the tracked head, never around the parent rig's origin. */
  _snap(angle, head) {
    this._rotation.setFromAxisAngle(UP, angle);
    this.rig.getWorldPosition(this._worldRig);
    this._pivotOffset.copy(this._worldRig).sub(head).applyQuaternion(this._rotation).add(head);
    this.rig.getWorldQuaternion(this._worldRotation).premultiply(this._rotation);
    if (this.rig.parent) {
      this.rig.parent.worldToLocal(this._pivotOffset);
      this.rig.parent.getWorldQuaternion(this._parentRotation).invert();
      this._worldRotation.premultiply(this._parentRotation);
    }
    this.rig.position.copy(this._pivotOffset);
    this.rig.quaternion.copy(this._worldRotation);
    this.rig.updateMatrixWorld(true);
  }

  _syncCameraPose() {
    this.rig.updateMatrixWorld(true);
    this.renderer.xr.updateCamera(this.camera);
  }

  update(dt, { blocked = false } = {}) {
    this.blocked = blocked;
    if (this._disposed || !this.renderer.xr.isPresenting) return;
    const session = this.renderer.xr.getSession();
    if (!session || session.visibilityState === 'hidden' || session.visibilityState === 'visible-blurred') return;
    const delta = THREE.MathUtils.clamp(Number.isFinite(dt) ? dt : 0, 0, 0.05);
    // r180 resets the parentless XR ArrayCamera to reference-space pose before
    // the application animation callback. Its getWorldPosition() getter would
    // rebuild matrixWorld without the rig. Synchronize Three's user camera and
    // read that attached camera instead, so navigation includes rig transforms.
    this._syncCameraPose();
    this.camera.getWorldPosition(this._head);
    this.camera.getWorldDirection(this._forward);
    this._forward.y = 0;
    if (this._forward.lengthSq() > 0.0001) {
      this._forward.normalize();
      this._lastForward.copy(this._forward);
    } else {
      this._forward.copy(this._lastForward);
    }
    this._right.crossVectors(this._forward, UP).normalize();
    this._move.set(0, 0, 0);

    for (const record of this._records) {
      const source = record.source;
      record.beam.visible = !!source;
      record.tip.visible = !!source;
      record.beamMaterial.opacity = blocked ? 0.16 : 0.42;
      if (!source?.gamepad) continue;
      const axes = source.gamepad.axes;
      const offset = axes.length >= 4 ? 2 : 0;
      const x = axes[offset] || 0;
      const y = axes[offset + 1] || 0;
      // In the xr-standard mapping, button 5 is B (right) / Y (left).
      const homeDown = !!source.gamepad.buttons[5]?.pressed;
      if (homeDown && !record.homeDown) {
        record.homeDown = true;
        this.onHome();
        this._syncCameraPose();
        return;
      }
      record.homeDown = homeDown;

      if (blocked) {
        record.snapped = Math.abs(x) > 0.7;
        continue;
      }
      if (source.handedness === 'left') {
        const dx = axis(x), dy = axis(y);
        const length = Math.max(1, Math.hypot(dx, dy));
        this._move.addScaledVector(this._forward, -dy / length * MOVE_SPEED * delta);
        this._move.addScaledVector(this._right, dx / length * MOVE_SPEED * delta);
      } else if (source.handedness === 'right') {
        if (Math.abs(x) > 0.7 && !record.snapped) {
          this._snap(-Math.sign(x) * SNAP_ANGLE, this._head);
          record.snapped = true;
        } else if (Math.abs(x) < 0.3) {
          record.snapped = false;
        }
        this._move.y -= axis(y) * LIFT_SPEED * delta;
      }
    }
    if (this._move.lengthSq()) this._translateWorld(this._move);
    // Keep the attached camera current for owner code that reads the head
    // after locomotion or snap-turning and before renderer.render().
    this._syncCameraPose();
  }

  dispose() {
    if (this._disposed) return;
    this._disposed = true;
    const session = this.renderer.xr.getSession();
    if (session) session.end().catch(() => {});
    for (const { target, type, handler } of this._listeners) target.removeEventListener(type, handler);
    for (const record of this._records) {
      record.controller.remove(record.beam, record.tip);
      record.grip.remove(record.handle);
      for (const dot of record.dots) dot.removeFromParent();
      record.controller.removeFromParent();
      record.grip.removeFromParent();
      record.hand.removeFromParent();
      delete record.controller.userData.xrInputSource;
    }
    for (const resource of this._resources) resource.dispose();
    this._resources.clear();
    this._listeners.length = 0;
    this.controllers.length = 0;
  }
}
