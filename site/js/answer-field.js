/* "Answer field" hero — the product metaphor in 3D:
   a wireframe globe + tilted orbit ring where green nodes (you got cited)
   pulse against muted red nodes (competitors got cited).
   three.js r0.160.1, vendored tree-shaken build (site/js/vendor/).
   Rules from design-language.md: DPR ≤1.5, ~30fps, pauses when the tab is
   hidden or the canvas is offscreen, pointer-events none (CSS), fixed-height
   hero, theme-aware colors, reduced-motion kills it (the loader gates it too). */
import * as THREE from "./vendor/three.module.min.js";

export function initField() {
  const canvas = document.getElementById("field-canvas");
  const holder = canvas && canvas.parentElement;
  if (!canvas || !holder) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const cssVar = (name, fb) => {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fb;
  };
  let pal = {
    structure: cssVar("--accent", "#8ab4ff"),
    good: cssVar("--good", "#34d399"),
    bad: cssVar("--bad", "#f87171"),
  };

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: "low-power" });
  } catch (e) {
    return; // no WebGL → SVG fallback stays
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 50);
  camera.position.set(0, 0.3, 4.4);
  camera.lookAt(0, 0, 0);

  const field = new THREE.Group();
  scene.add(field);

  // wireframe globe
  const globeMat = new THREE.LineBasicMaterial({ color: pal.structure, transparent: true, opacity: 0.22 });
  const globe = new THREE.LineSegments(
    new THREE.WireframeGeometry(new THREE.SphereGeometry(1.35, 20, 12)),
    globeMat
  );
  field.add(globe);

  // tilted orbit ring — circle of line segments in the XZ plane
  const R = 1.8, SEG = 96, pos = [];
  for (let i = 0; i < SEG; i++) {
    const a0 = (i / SEG) * Math.PI * 2, a1 = ((i + 1) / SEG) * Math.PI * 2;
    pos.push(Math.cos(a0) * R, 0, Math.sin(a0) * R, Math.cos(a1) * R, 0, Math.sin(a1) * R);
  }
  const ringGeo = new THREE.BufferGeometry();
  ringGeo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  const ringMat = new THREE.LineBasicMaterial({ color: pal.structure, transparent: true, opacity: 0.38 });
  const ring = new THREE.LineSegments(ringGeo, ringMat);
  ring.rotation.set(0.46, 0, -0.3);
  field.add(ring);

  // nodes on the sphere surface: 5 green (cited) vs 9 red (competitors own the answers)
  const sphereNodes = (n, r) => {
    const pts = [];
    for (let i = 0; i < n; i++) {
      const u = Math.random() * 2 - 1, th = Math.random() * Math.PI * 2;
      const s = Math.sqrt(1 - u * u);
      pts.push(s * Math.cos(th) * r, u * r, s * Math.sin(th) * r);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    return g;
  };
  const goodMat = new THREE.PointsMaterial({ color: pal.good, size: 0.1, transparent: true, opacity: 0.9, depthWrite: false });
  const badMat = new THREE.PointsMaterial({ color: pal.bad, size: 0.072, transparent: true, opacity: 0.6, depthWrite: false });
  field.add(new THREE.Points(sphereNodes(5, 1.37), goodMat));
  field.add(new THREE.Points(sphereNodes(9, 1.37), badMat));
  field.rotation.z = 0.12;

  function resize() {
    const w = holder.clientWidth || 1, h = holder.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    /* Fit the whole orbit ring: the ring sweeps ~2.1 world-units (with
     * perspective) horizontally, so pull the camera back on narrow columns.
     * Without this the ring clips at the canvas edges while it spins. */
    const halfTan = Math.tan((camera.fov * Math.PI) / 360);
    camera.position.z = Math.max(5.0, 2.15 / (halfTan * Math.max(camera.aspect, 0.6)));
    camera.updateProjectionMatrix();
  }
  resize();
  if ("ResizeObserver" in window) new ResizeObserver(resize).observe(holder);
  else window.addEventListener("resize", resize);

  // theme-aware colors — re-read the CSS variables when data-theme flips
  new MutationObserver(() => {
    pal = {
      structure: cssVar("--accent", "#8ab4ff"),
      good: cssVar("--good", "#34d399"),
      bad: cssVar("--bad", "#f87171"),
    };
    globeMat.color.set(pal.structure);
    ringMat.color.set(pal.structure);
    goodMat.color.set(pal.good);
    badMat.color.set(pal.bad);
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  // pause when the tab is hidden or the hero is scrolled offscreen
  let visible = true, onscreen = true;
  document.addEventListener("visibilitychange", () => { visible = document.visibilityState === "visible"; });
  if ("IntersectionObserver" in window) {
    new IntersectionObserver((es) => { onscreen = es[0].isIntersecting; }, { threshold: 0 }).observe(canvas);
  }

  holder.classList.add("has3d"); // hides the SVG fallback (CSS)

  // verification hook
  const state = { frames: 0, get running() { return visible && onscreen; } };
  window.__answerField = state;

  let last = 0;
  function loop(ts) {
    requestAnimationFrame(loop);
    if (!state.running) return;
    if (ts - last < 33) return; // ~30fps cap
    last = ts;
    const t = ts / 1000;
    field.rotation.y = t * 0.12;      // slow, calm
    ring.rotation.y = -t * 0.05;
    goodMat.opacity = 0.65 + 0.3 * Math.sin(t * 2.1);            // cited nodes breathe
    goodMat.size = 0.09 + 0.022 * (0.5 + 0.5 * Math.sin(t * 2.1));
    state.frames++;
    renderer.render(scene, camera);
  }
  requestAnimationFrame(loop);
}
