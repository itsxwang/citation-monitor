/* Citation Monitor — interactions: theme toggle, scroll reveal, count-up
   counters, lazy three.js loader. Design-language v2: calm confidence,
   60ms stagger, 250ms theme transition, reduced-motion kills everything. */
(function () {
  "use strict";
  var docEl = document.documentElement;
  window.__cmApp = true; // lets the pre-paint counter script know we made it
  var reduceMq = window.matchMedia("(prefers-reduced-motion: reduce)");

  /* ---- theme toggle (same pattern as the store: localStorage "cr.theme") ---- */
  var toggle = document.getElementById("theme-toggle");
  function syncToggle() {
    if (toggle) toggle.textContent = (docEl.getAttribute("data-theme") || "light") === "dark" ? "☀️" : "🌙";
  }
  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = (docEl.getAttribute("data-theme") || "light") === "dark" ? "light" : "dark";
      docEl.setAttribute("data-theme", next);
      try { localStorage.setItem("cr.theme", next); } catch (e) {}
      syncToggle();
    });
    syncToggle();
  }

  /* ---- scroll reveal: fade + rise 12px, 500ms, 60ms stagger within each group ---- */
  var revealEls = Array.prototype.slice.call(document.querySelectorAll(".reveal"));
  revealEls.forEach(function (el) {
    var parent = el.parentElement;
    var peers = parent ? Array.prototype.slice.call(parent.children).filter(function (c) {
      return c.classList && c.classList.contains("reveal");
    }) : [el];
    var i = peers.indexOf(el);
    el.style.setProperty("--d", (i > 0 ? i * 60 : 0) + "ms");
  });
  if (reduceMq.matches || !("IntersectionObserver" in window)) {
    revealEls.forEach(function (el) { el.classList.add("in"); });
  } else {
    var revealIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); revealIO.unobserve(en.target); }
      });
    }, { rootMargin: "0px 0px -40px 0px", threshold: 0.12 });
    revealEls.forEach(function (el) { revealIO.observe(el); });
  }

  /* ---- count-up counters ----
     HTML ships the final values (no-JS/no-CLS safe); an inline pre-paint script
     in index.html resets [data-count] to the start value and stores the final in
     dataset.final. Here we animate once, when scrolled into view. */
  var counters = Array.prototype.slice.call(document.querySelectorAll("[data-count]"));
  function finalize(el) {
    if (el.dataset.final) el.textContent = el.dataset.final;
    el.dataset.done = "1";
  }
  function easeOut(t) { return 1 - Math.pow(1 - t, 3); }
  function animate(el) {
    var fin = el.dataset.final || "";
    var frac = fin.match(/^(\d+)\/(\d+)$/); // "0/72" → prefix stays "0/", denominator counts
    var t0 = null, dur = 900;
    function frame(ts) {
      if (t0 === null) t0 = ts;
      var p = Math.min(1, (ts - t0) / dur);
      var k = easeOut(p);
      el.textContent = frac
        ? frac[1] + "/" + Math.round(k * (+frac[2]))
        : String(Math.round(k * (+fin)));
      if (p < 1) requestAnimationFrame(frame);
      else el.dataset.done = "1";
    }
    requestAnimationFrame(frame);
  }
  if (reduceMq.matches || !("IntersectionObserver" in window) || !counters.length) {
    counters.forEach(finalize);
  } else {
    var countIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting || en.target.dataset.done === "1") return;
        countIO.unobserve(en.target);
        animate(en.target);
      });
    }, { threshold: 0.4 });
    counters.forEach(function (el) {
      if (el.dataset.final) countIO.observe(el); // only the ones the pre-paint script reset
      else el.dataset.done = "1";
    });
  }

  /* ---- lazy 3D "answer field" — after first paint, on idle.
     Gates: reduced-motion, saveData/slow connection, <768px (SVG fallback). ---- */
  function want3D() {
    if (reduceMq.matches) return false;
    if (window.innerWidth < 768) return false;
    var conn = navigator.connection;
    if (conn && (conn.saveData || /2g/.test(conn.effectiveType || ""))) return false;
    if (!document.getElementById("field-canvas")) return false;
    try {
      var probe = document.createElement("canvas");
      return !!(probe.getContext("webgl") || probe.getContext("experimental-webgl"));
    } catch (e) { return false; }
  }
  if (want3D()) {
    var started = false;
    var kick = function () {
      if (started) return;
      started = true;
      import("./answer-field.js")
        .then(function (mod) { mod.initField(); })
        .catch(function () { /* SVG fallback stays */ });
    };
    if ("requestIdleCallback" in window) requestIdleCallback(kick, { timeout: 600 });
    else setTimeout(kick, 150);
  }
})();
