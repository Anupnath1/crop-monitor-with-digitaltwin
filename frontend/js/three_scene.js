const ThreeScene = (() => {

  let scene, camera, renderer;
  let modelRoot  = null;
  let wheatMats  = [];
  let waterParticles = [];
  let waterActive    = false;
  let waterTimer     = null;
  let sprayHeads     = [];
  let t = 0;
  let cameraAngle = 0;

  const COLOR_HEALTHY  = new THREE.Color(0.30, 0.75, 0.20);
  const COLOR_MODERATE = new THREE.Color(0.70, 0.60, 0.12);
  const COLOR_CRITICAL = new THREE.Color(0.62, 0.25, 0.12);
  const WATER_COLOR    = new THREE.Color(0.48, 0.78, 1.00);

  let colorTarget  = new THREE.Color().copy(COLOR_HEALTHY);
  let colorCurrent = new THREE.Color().copy(COLOR_HEALTHY);

  function init() {
    const wrap   = document.getElementById('three-canvas-wrap');
    const canvas = document.getElementById('three-canvas');
    if (!wrap || !canvas) return;

    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type    = THREE.PCFSoftShadowMap;
    renderer.setClearColor(0x000000, 0);
    renderer.toneMapping         = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    renderer.outputEncoding      = THREE.sRGBEncoding;

    scene = new THREE.Scene();

    camera = new THREE.PerspectiveCamera(38, 1, 0.1, 300);
    camera.position.set(0, 8, 14);
    camera.lookAt(0, 1, 0);

    _setupLighting();
    _buildSpraySystem();
    _loadModel();

    new ResizeObserver(_onResize).observe(wrap);
    _onResize();
    _animate();
  }

  function _setupLighting() {
    scene.add(new THREE.AmbientLight(0xfff8ee, 0.70));

    const sun = new THREE.DirectionalLight(0xfffaf0, 2.2);
    sun.position.set(-5, 14, 8);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.left   = -10;
    sun.shadow.camera.right  =  10;
    sun.shadow.camera.top    =  10;
    sun.shadow.camera.bottom = -10;
    sun.shadow.bias = -0.001;
    scene.add(sun);

    const fill = new THREE.DirectionalLight(0xc8e8ff, 0.55);
    fill.position.set(8, 5, 3);
    scene.add(fill);

    const back = new THREE.DirectionalLight(0xffe0aa, 0.30);
    back.position.set(0, 3, -10);
    scene.add(back);

    scene.add(new THREE.HemisphereLight(0xb0d8ff, 0x5a7a40, 0.35));

    const soil = new THREE.PointLight(0x60a050, 0.40, 12);
    soil.position.set(0, 0.2, 0);
    scene.add(soil);
  }

  function _buildSpraySystem() {
    const positions = [
      new THREE.Vector3(-3.5, 0, -2.5),
      new THREE.Vector3( 3.5, 0, -2.5),
      new THREE.Vector3(-3.5, 0,  2.5),
      new THREE.Vector3( 3.5, 0,  2.5),
      new THREE.Vector3( 0,   0, -4.0),
      new THREE.Vector3( 0,   0,  4.0),
    ];

    const pipeMat   = new THREE.MeshStandardMaterial({ color: 0x2a5858, roughness: 0.4, metalness: 0.65 });
    const nozzleMat = new THREE.MeshStandardMaterial({ color: 0x1a4848, roughness: 0.35, metalness: 0.7 });

    positions.forEach(pos => {
      const group = new THREE.Group();
      group.position.copy(pos);

      const pipe = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.07, 0.50, 10), pipeMat);
      pipe.position.y = -0.10;
      pipe.castShadow = true;
      group.add(pipe);

      const nozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.10, 0.06, 0.14, 12), nozzleMat);
      nozzle.position.y = 0.17;
      group.add(nozzle);

      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(0.08, 0.015, 6, 14),
        new THREE.MeshStandardMaterial({ color: 0x3a7070, roughness: 0.3, metalness: 0.7 })
      );
      ring.rotation.x = Math.PI / 2;
      ring.position.y = 0.245;
      group.add(ring);

      const mount = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.028, 14), nozzleMat);
      mount.position.y = 0.0;
      group.add(mount);

      group.userData.restY   = pos.y;
      group.userData.activeY = pos.y + 0.35;
      scene.add(group);
      sprayHeads.push({ group, pos: new THREE.Vector3(pos.x, 0.26, pos.z) });
    });
  }

  function _loadModel() {
    const overlay = document.getElementById('canvas-overlay');

    if (typeof THREE.GLTFLoader === 'undefined') {
      if (overlay) overlay.textContent = 'Add GLTFLoader script to index.html';
      return;
    }

    const loader = new THREE.GLTFLoader();
    if (overlay) overlay.textContent = 'Loading farm model…';

    loader.load(
      'assets/farm.glb',

      (gltf) => {
        modelRoot = gltf.scene;
        _setupFarmModel(modelRoot);
        scene.add(modelRoot);
        if (overlay) { overlay.textContent = ''; overlay.style.opacity = '0'; }
        console.log('[Scene] farm.glb loaded ✓  wheat meshes:', wheatMats.length);
      },

      (xhr) => {
        if (overlay && xhr.total > 0)
          overlay.textContent = `Loading… ${Math.round(xhr.loaded / xhr.total * 100)}%`;
      },

      (err) => {
        console.error('[Scene] GLB load failed:', err.message);
        if (overlay) overlay.textContent = 'Farm model failed to load';
      }
    );
  }

  function _setupFarmModel(root) {
    const box    = new THREE.Box3().setFromObject(root);
    const size   = new THREE.Vector3();
    const center = new THREE.Vector3();
    box.getSize(size);
    box.getCenter(center);

    const maxDim = Math.max(size.x, size.z);
    const scale  = 14.0 / maxDim;
    root.scale.setScalar(scale);

    root.position.x = -center.x * scale;
    root.position.y = -box.min.y * scale;
    root.position.z = -center.z * scale;

    wheatMats = [];

    root.traverse(child => {
      if (!child.isMesh) return;
      child.castShadow    = true;
      child.receiveShadow = true;

      const nodeName = (child.parent?.name || child.name || '').toLowerCase();
      const matName  = (child.material?.name || '').toLowerCase();

      const isWheat = nodeName.includes('wheat') || matName.includes('wheat');

      if (isWheat) {
        const mats = Array.isArray(child.material) ? child.material : [child.material];
        mats.forEach(mat => {
          if (!mat) return;
          mat.userData.baseColor = mat.color ? mat.color.clone() : new THREE.Color(0.3, 0.7, 0.2);
          if (!mat.color) mat.color = new THREE.Color(0.3, 0.7, 0.2);
          wheatMats.push(mat);
        });
      }
    });

    root.userData.baseY = root.position.y;
    console.log(`[Scene] Farm scaled ×${scale.toFixed(2)}, wheat mats: ${wheatMats.length}`);
  }

  const GRAVITY = -0.0040;
  let dropTick  = 0;

  function _spawnSpray(nozzlePos) {
    for (let i = 0; i < 2; i++) {
      const geo = new THREE.SphereGeometry(0.055 + Math.random() * 0.030, 5, 4);
      const mat = new THREE.MeshStandardMaterial({
        color: WATER_COLOR, transparent: true, opacity: 0.88,
        roughness: 0.05, metalness: 0.1,
        emissive: new THREE.Color(0.05, 0.18, 0.48), emissiveIntensity: 0.35,
      });
      const mesh  = new THREE.Mesh(geo, mat);
      const angle = Math.random() * Math.PI * 2;
      const spread = 0.025 + Math.random() * 0.060;

      mesh.position.set(
        nozzlePos.x + (Math.random() - 0.5) * 0.10,
        nozzlePos.y,
        nozzlePos.z + (Math.random() - 0.5) * 0.10
      );
      mesh.userData.vel = new THREE.Vector3(
        Math.cos(angle) * spread,
        0.095 + Math.random() * 0.065,
        Math.sin(angle) * spread
      );
      mesh.userData.life  = 1.0;
      mesh.userData.decay = 0.007 + Math.random() * 0.005;
      mesh.userData.type  = 'drop';
      scene.add(mesh);
      waterParticles.push(mesh);
    }
  }

  function _spawnMist(pos) {
    const geo = new THREE.SphereGeometry(0.18, 6, 5);
    const mat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(0.85, 0.93, 1.0), transparent: true, opacity: 0.16, roughness: 1.0
    });
    const mist = new THREE.Mesh(geo, mat);
    mist.position.set(pos.x, pos.y + 0.12, pos.z);
    mist.userData = { life: 1.0, decay: 0.038, type: 'mist' };
    scene.add(mist);
    waterParticles.push(mist);
  }

  function _spawnSplash(x, z) {
    const geo = new THREE.RingGeometry(0.03, 0.09, 10);
    const mat = new THREE.MeshBasicMaterial({
      color: WATER_COLOR, transparent: true, opacity: 0.50, side: THREE.DoubleSide
    });
    const ring = new THREE.Mesh(geo, mat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(x, 0.08, z);
    ring.userData = { life: 1.0, decay: 0.055, type: 'splash' };
    scene.add(ring);
    waterParticles.push(ring);
  }

  function _updateWater() {
    if (waterActive) {
      dropTick++;
      if (dropTick % 4 === 0) {
        sprayHeads.forEach(({ group, pos }) => {
          const wp = new THREE.Vector3(group.position.x, group.position.y + 0.26, group.position.z);
          _spawnSpray(wp);
          if (Math.random() < 0.20) _spawnMist(wp);
        });
      }
    }

    for (let i = waterParticles.length - 1; i >= 0; i--) {
      const p = waterParticles[i];

      if (p.userData.type === 'mist') {
        p.userData.life -= p.userData.decay;
        p.material.opacity = Math.max(0, p.userData.life * 0.16);
        p.scale.setScalar(1 + (1 - p.userData.life) * 1.8);
        if (p.userData.life <= 0) { _remove(p, i); }
        continue;
      }

      if (p.userData.type === 'splash') {
        p.userData.life -= p.userData.decay;
        p.material.opacity = Math.max(0, p.userData.life * 0.50);
        const s = 1 + (1 - p.userData.life) * 5;
        p.scale.set(s, s, s);
        if (p.userData.life <= 0) { _remove(p, i); }
        continue;
      }

      p.userData.vel.y += GRAVITY;
      p.position.addScaledVector(p.userData.vel, 1);
      p.userData.life -= p.userData.decay;
      p.material.opacity = Math.max(0, Math.min(0.88, p.userData.life * 1.1));

      if (p.position.y <= 0.06 || p.userData.life <= 0) {
        if (p.position.y <= 0.06 && Math.random() < 0.28)
          _spawnSplash(p.position.x, p.position.z);
        _remove(p, i);
      }
    }
  }

  function _remove(p, i) {
    scene.remove(p);
    p.geometry.dispose();
    p.material.dispose();
    waterParticles.splice(i, 1);
  }

  function _animateSprayHeads() {
    sprayHeads.forEach(({ group }) => {
      const target = waterActive ? group.userData.activeY : group.userData.restY;
      group.position.y += (target - group.position.y) * 0.10;
    });
  }

  function _animate() {
    requestAnimationFrame(_animate);
    t += 0.006;

    cameraAngle += 0.0008;
    camera.position.set(
      Math.sin(cameraAngle) * 14,
      8.0 + Math.sin(t * 0.28) * 0.4,
      Math.cos(cameraAngle) * 14
    );
    camera.lookAt(0, 1.2, 0);

    if (modelRoot) {
      const baseY = modelRoot.userData.baseY || 0;
      modelRoot.position.y = baseY + Math.sin(t * 0.45) * 0.006;
    }

    colorCurrent.lerp(colorTarget, 0.018);
    wheatMats.forEach(mat => {
      const base = mat.userData.baseColor;
      if (base) {
        mat.color.setRGB(
          base.r * colorCurrent.r,
          base.g * colorCurrent.g,
          base.b * colorCurrent.b
        );
      }
    });

    _animateSprayHeads();
    _updateWater();
    renderer.render(scene, camera);
  }

  function _onResize() {
    const wrap = document.getElementById('three-canvas-wrap');
    if (!wrap || !renderer) return;
    const w = wrap.clientWidth, h = wrap.clientHeight;
    renderer.setSize(w, h, false);
    if (camera) { camera.aspect = w / h; camera.updateProjectionMatrix(); }
  }

  function updateHealth(score) {
    if      (score >= 75) { colorTarget.copy(COLOR_HEALTHY);  _setGlow('healthy');  }
    else if (score >= 50) { colorTarget.copy(COLOR_MODERATE); _setGlow('moderate'); }
    else                  { colorTarget.copy(COLOR_CRITICAL); _setGlow('critical'); }

    const badge = document.getElementById('twin-health-badge');
    if (badge) {
      badge.textContent   = `Health ${score.toFixed(0)}/100`;
      badge.style.color   = score >= 75 ? 'var(--ok)' : score >= 50 ? 'var(--warn)' : 'var(--crit)';
      badge.style.borderColor = score >= 75 ? 'var(--sage-dim)'
        : score >= 50 ? 'rgba(184,154,78,0.35)' : 'rgba(168,80,80,0.35)';
    }
  }

  function triggerWater(durationSeconds = 8) {
    if (waterActive) return;
    waterActive = true;
    dropTick    = 0;
    clearTimeout(waterTimer);
    waterTimer = setTimeout(() => { waterActive = false; }, durationSeconds * 1000);
  }

  function _setGlow(state) {
    const el = document.getElementById('plant-glow');
    if (el) el.className = `plant-glow ${state}`;
  }

  document.addEventListener('DOMContentLoaded', init);
  return { init, updateHealth, triggerWater };

})();
