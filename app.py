import hashlib
import random
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="SkyBook", page_icon="✈️", layout="wide")

# ---------- Data ----------
CITIES = ["Kochi", "Delhi", "Mumbai", "Bengaluru", "Chennai", "Hyderabad",
          "Kolkata", "Goa", "Thiruvananthapuram", "Dubai", "Singapore"]
CODES = {"Kochi": "COK", "Delhi": "DEL", "Mumbai": "BOM", "Bengaluru": "BLR",
         "Chennai": "MAA", "Hyderabad": "HYD", "Kolkata": "CCU", "Goa": "GOI",
         "Thiruvananthapuram": "TRV", "Dubai": "DXB", "Singapore": "SIN"}
AIRLINES = [("Air India", "AI"), ("IndiGo", "6E"), ("Emirates", "EK"),
            ("Vistara", "UK"), ("SpiceJet", "SG"), ("Akasa Air", "QP")]
CLASS_MULT = {"Economy": 1.0, "Premium Economy": 1.4, "Business": 2.2}
MEALS = {"No meal": 0, "Veg meal": 250, "Non-veg meal": 300}
BAG_PRICE = 1200
STEPS = ["Search", "Flights", "Passengers", "Seats", "Payment", "Ticket"]
CABINS = [("Business", range(1, 4), "ACDF", "biz"),
          ("Premium Economy", range(4, 7), "ABCDEF", "prem"),
          ("Economy", range(7, 11), "ABCDEF", "eco")]
WINGS = {5: 45, 6: 85, 7: 125}


def cabin_seats(name):
    for n, rows, letters, _ in CABINS:
        if n == name:
            return [f"{r}{c}" for r in rows for c in letters]
    return []


def seat_type(seat):
    return "Window" if seat[-1] in "AF" else ("Aisle" if seat[-1] in "CD" else "Middle")


# cabin -> (legroom/seat pitch in inches, seat width in inches, recline in inches)
BASE = {"Business": (40, 21, 8), "Premium Economy": (36, 18.5, 6), "Economy": (31, 17.5, 3)}


def seat_info(seat, cabin):
    row = int(seat[:-1])
    pitch, width, recline = BASE[cabin]
    base_pitch = pitch
    notes = []
    if row == 6:
        pitch += 6
        notes += ["Emergency exit row: extra legroom, but passengers must be 15+ and able to "
                  "help in an emergency", "Close to the lavatory, so expect some foot traffic"]
    elif row in (1, 4, 7):
        pitch += 4
        notes.append("Bulkhead row: no seat in front of you, but bags must go overhead")
    if row == 5:
        recline = 2
        notes.append("Limited recline because of the exit row behind")
    if row == 3:
        notes.append("Next to the galley, so expect some noise")
    if row == 10:
        recline = 1
        notes.append("Wall behind you: limited recline, near the lavatories and galley")
    kind = seat_type(seat)
    if kind == "Window":
        if row <= 4:
            view = "Clear window view, ahead of the wing"
        elif row <= 7:
            view = "Window view partly blocked by the wing"
        else:
            view = "Clear window view behind the wing, great for landing"
    elif kind == "Aisle":
        view = "No window, but easy to get up and walk around"
    else:
        view = "No window, seated between two passengers"
    label, tone = (("Generous", "g") if pitch >= 38 else
                   ("Comfortable", "b") if pitch >= 34 else ("Standard", ""))
    return {"pitch": pitch, "width": width, "recline": recline, "view": view,
            "notes": notes, "kind": kind, "label": label, "tone": tone,
            "extra": pitch > base_pitch}


BREAKS = {"Business": "Galley", "Premium Economy": "Lavatory"}


def seat_layout(taken, ticket_class, names):
    """Everything the seat picker needs, as plain data that can be sent to the browser."""
    seats = {}
    for cabin, rows, letters, _ in CABINS:
        for r in rows:
            for c in letters:
                seats[f"{r}{c}"] = {**seat_info(f"{r}{c}", cabin),
                                    "cabin": cabin, "row": r, "letter": c}
    return {"cabins": [{"name": n, "rows": list(rows), "letters": letters, "css": css}
                       for n, rows, letters, css in CABINS],
            "seats": seats, "taken": sorted(taken),
            "wings": {str(k): v for k, v in WINGS.items()},
            "breaks": BREAKS, "ticket": ticket_class, "passengers": list(names)}


def clean_picks(picked, free, count):
    """Keep only valid, free, non-duplicate seats, keyed by passenger number."""
    out, used = {}, set()
    for i in range(count):
        seat = (picked or {}).get(str(i))
        if seat in free and seat not in used:
            out[str(i)] = seat
            used.add(seat)
    return out


# ---------- Seat picker component ----------
# A small web page (HTML + JavaScript) that Streamlit shows inside the Seats step.
# It draws the clickable seat map and the 3D cabin view (three.js, loaded from cdnjs,
# so the 3D view needs an internet connection), and sends the chosen seats back to Python.
SEAT_PICKER_HTML = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:transparent}
body{font-family:"Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif;color:#1b1650;font-size:14px}
#app{padding:2px 2px 6px}
.wrap{display:flex;flex-wrap:wrap;gap:18px;align-items:flex-start}
.left{flex:1 1 380px;min-width:300px}
.right{flex:1 1 400px;min-width:300px}
button{font-family:inherit}

/* passenger pills */
.pills{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px}
.pill{border:2px solid #d9d2ff;background:#f3efff;color:#3a1c8f;border-radius:999px;padding:4px 12px;
 font-size:.85rem;cursor:pointer}
.pill.on{border-color:#ff5f6d;background:#fff0f2}
.pill .pn{background:#6a5cff;color:#fff;border-radius:999px;padding:0 7px;font-size:.72rem;margin-right:4px}
.pill b{margin-left:6px;color:#ff5f6d}
.tip{font-size:.85rem;margin:2px 0 6px;color:#4b4a6a}

/* seat map */
.legend{display:flex;gap:8px;justify-content:center;margin-bottom:6px;flex-wrap:wrap}
.legend .seat{width:auto;padding:0 10px;height:24px;cursor:default}
.legend .seat:hover{transform:none}
.plane-wrap{overflow:hidden;padding:10px 0 6px}
.fuse{position:relative;z-index:0;width:340px;max-width:100%;margin:0 auto;padding-bottom:22px;
 background:linear-gradient(90deg,#e6ebf5,#fff 50%,#e6ebf5);border:3px solid #aab3c8;
 border-radius:170px 170px 90px 90px}
.cockpit{width:90px;height:26px;margin:36px auto 12px;border-radius:40px 40px 10px 10px;
 background:linear-gradient(#27325c,#4a5cb8)}
.cabin-name{text-align:center;font-size:.75rem;color:#6a5cff;font-weight:700;margin:8px 0 2px}
.galley{width:70%;margin:6px auto;padding:3px;border-radius:6px;background:#dfe4ef;
 color:#667;font-size:.7rem;text-align:center}
.prow{position:relative;display:flex;justify-content:center;align-items:center;gap:5px;padding:3px 20px}
.win{position:absolute;top:50%;width:6px;height:14px;margin-top:-7px;border-radius:4px;
 background:#8fd0ff;border:1px solid #6aa8d8}
.win.l{left:5px}.win.r{right:5px}
.wing{position:absolute;top:0;bottom:0;z-index:-1;background:linear-gradient(#c9d0de,#9ea8bd)}
.wing.l{right:100%}.wing.r{left:100%}
.wing.l.tip{border-radius:0 0 0 40px}.wing.r.tip{border-radius:0 0 40px 0}
.exit{position:absolute;top:-6px;background:#e53935;color:#fff;font-size:.55rem;padding:0 4px;border-radius:3px}
.exit.l{left:8px}.exit.r{right:8px}
.seat{width:34px;height:30px;border-radius:9px 9px 4px 4px;font-size:.68rem;display:flex;
 align-items:center;justify-content:center;color:#16306b;transition:transform .15s;padding:0;
 border:0;border-bottom:3px solid rgba(0,0,0,.18);cursor:pointer;font-weight:600}
.seat.eco{background:#bfe3ff}
.seat.prem{width:38px;height:32px;background:#ffd9b8;color:#7a3b00}
.seat.biz{width:46px;height:38px;background:#d9c9ff;color:#3a1c8f}
.seat:hover:not(:disabled){transform:translateY(-3px) scale(1.1)}
.seat:focus-visible{outline:3px solid #6a5cff;outline-offset:2px}
.seat.off{opacity:.35;cursor:not-allowed}
.seat.taken{background:#9aa0b4;color:#fff;opacity:.65;cursor:not-allowed}
.seat.xl{border-top:3px solid #2ecc71}
.seat.mine{background:linear-gradient(#ffb347,#ff5f6d);color:#fff;font-weight:700;opacity:1;
 animation:pulse 1.6s infinite}
.seat.focus{outline:3px solid #3a1c8f;outline-offset:2px;position:relative;z-index:2}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(255,95,109,.55)}50%{box-shadow:0 0 0 7px rgba(255,95,109,0)}}
.aisle{width:26px}.rownum{width:18px;font-size:.65rem;opacity:.6;text-align:center}

/* 3D view */
.view3d{position:relative;height:380px;border-radius:18px;overflow:hidden;
 background:linear-gradient(#2a6fd6,#bfe0ff);box-shadow:0 8px 22px rgba(58,28,143,.28)}
#cv{position:absolute;left:0;top:0;width:100%;height:100%;display:block;touch-action:pan-y;cursor:grab}
.badge{position:absolute;left:10px;top:10px;background:rgba(20,16,60,.72);color:#fff;border-radius:999px;
 padding:4px 12px;font-size:.8rem;font-weight:600;pointer-events:none}
.hint{position:absolute;right:10px;top:12px;color:#fff;font-size:.72rem;opacity:.85;pointer-events:none;
 text-shadow:0 1px 3px rgba(0,0,0,.6)}
.cap{position:absolute;left:10px;right:10px;bottom:52px;color:#fff;font-size:.78rem;pointer-events:none;
 text-shadow:0 1px 3px rgba(0,0,0,.75)}
.modes{position:absolute;left:0;right:0;bottom:10px;display:flex;gap:6px;justify-content:center}
.modes button{border:0;border-radius:999px;padding:6px 14px;font-size:.82rem;font-weight:700;cursor:pointer;
 background:rgba(255,255,255,.85);color:#3a1c8f}
.modes button.on{background:linear-gradient(90deg,#ff9a44,#ff5f6d);color:#fff}
.ph{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;
 text-align:center;padding:20px;color:#fff;background:linear-gradient(160deg,#35b6ff,#6a5cff 60%,#ff5fa2);
 font-size:1rem}
.ph .big{font-size:2.6rem;margin-bottom:6px}
.ph small{opacity:.9;margin-top:4px}
.nofx{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;
 padding:24px;background:#27325c;color:#fff;font-size:.9rem}
[hidden]{display:none!important}

/* seat info */
.infocard{border-left:5px solid #6a5cff;background:#f3efff;border-radius:12px;color:#1b1650;
 padding:10px 14px;margin:12px 0 4px;font-size:.9rem}
.infocard.muted{color:#4b4a6a}
.chip{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.78rem;margin:4px 6px 4px 0;
 background:#e3e8ff;color:#1b1650}
.chip.g{background:#c8f5e1;color:#0a6b46}.chip.b{background:#d6e8ff;color:#154a8a}
.chip.sel{background:#ffe2ee;color:#c2185b;margin-left:6px}
.infocard ul{margin:4px 0 0 1rem;padding:0;font-size:.82rem}
.infocard .small{font-size:.74rem;color:#6b6a8a;margin-top:6px}
.linkbtn{margin-top:8px;border:0;background:none;color:#c2185b;font-weight:700;cursor:pointer;padding:0;
 text-decoration:underline;font-size:.85rem}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style>
</head>
<body>
<div id="app">
 <div class="wrap">
  <div class="left">
   <div class="pills" id="pills"></div>
   <div class="tip" id="tip"></div>
   <div class="legend"><span class="seat eco">Free</span><span class="seat mine">Yours</span>
    <span class="seat taken">Taken</span><span class="seat eco xl">Extra legroom</span></div>
   <div id="map"></div>
  </div>
  <div class="right">
   <div class="view3d" id="view3d">
    <canvas id="cv"></canvas>
    <div class="badge" id="badge" hidden></div>
    <div class="hint" id="hint" hidden>Drag to look around</div>
    <div class="cap" id="cap"></div>
    <div class="modes" id="modes" hidden>
     <button type="button" data-mode="overview" class="on">Overview</button>
     <button type="button" data-mode="legroom">Legroom</button>
     <button type="button" data-mode="window">Window</button>
    </div>
    <div class="ph" id="ph"><div class="big">💺</div><div><b>Tap a seat on the map</b></div>
     <small>to pick it and see your legroom and window view in 3D</small></div>
    <div class="nofx" id="nofx" hidden>The 3D view could not start (it needs WebGL and an internet connection
     to load the 3D library). You can still pick seats, and the details are shown below.</div>
   </div>
   <div id="info"></div>
  </div>
 </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(function () {
"use strict";

var IN = 0.0254;                       // metres per inch
function $(id) { return document.getElementById(id); }
function esc(s) {
  return String(s).replace(/[&<>"]/g, function (c) {
    return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c];
  });
}

/* ---------- Streamlit component protocol ---------- */
function post(type, data) {
  var m = {isStreamlitMessage: true, type: type};
  for (var k in data) m[k] = data[k];
  window.parent.postMessage(m, "*");
}
function fit() {
  post("streamlit:setFrameHeight", {height: Math.ceil($("app").getBoundingClientRect().height) + 8});
}
function sendValue() {
  post("streamlit:setComponentValue", {value: Object.assign({}, S.sel), dataType: "json"});
}
window.addEventListener("message", function (ev) {
  var d = ev.data;
  if (d && d.type === "streamlit:render") onRender(d.args || {});
});

/* ---------- State ---------- */
var S = {active: 0, sel: {}, focus: null, mode: "overview"};
var L = null, inited = false, T = null;

function ownerOf(id) {
  for (var k in S.sel) if (S.sel[k] === id) return k;
  return null;
}
function cabinOf(name) { return L.cabins.filter(function (c) { return c.name === name; })[0]; }
function isExit(s) { return s.notes.some(function (n) { return n.indexOf("Emergency exit") === 0; }); }
// rough knee room for a 175 cm passenger: seat pitch - seat-back thickness - buttock-to-knee length
function kneeIn(s) {
  var wall = s.row === cabinOf(s.cabin).rows[0];
  return Math.max(0, s.pitch - 23.2 - (wall ? 0 : 3.9));
}

function onRender(args) {
  if (!inited) {
    L = args.layout;
    S.sel = Object.assign({}, args.selected || {});
    S.active = 0;
    for (var i = 0; i < L.passengers.length; i++) {
      if (!S.sel[i]) { S.active = i; break; }
    }
    var keys = Object.keys(S.sel).sort();
    if (keys.length) S.focus = S.sel[keys[0]];
    buildMap();
    initThree();
    inited = true;
    refresh(true);
  }
  fit();
}

/* ---------- Seat map ---------- */
function buildMap() {
  var taken = {};
  L.taken.forEach(function (t) { taken[t] = true; });
  var lastWing = Math.max.apply(null, Object.keys(L.wings).map(Number));
  var h = '<div class="plane-wrap"><div class="fuse"><div class="cockpit"></div>';
  L.cabins.forEach(function (cab) {
    h += '<div class="cabin-name">' + esc(cab.name) + ' cabin</div>';
    var letters = cab.letters.split(""), half = letters.length / 2;
    cab.rows.forEach(function (r) {
      h += '<div class="prow">';
      var wv = L.wings[String(r)];
      if (wv !== undefined) {
        var tip = r === lastWing ? " tip" : "";
        h += '<div class="wing l' + tip + '" style="width:' + wv + 'px"></div>' +
             '<div class="wing r' + tip + '" style="width:' + wv + 'px"></div>';
      }
      if (isExit(L.seats[r + letters[0]])) h += '<span class="exit l">Exit</span><span class="exit r">Exit</span>';
      h += '<span class="win l"></span><span class="win r"></span><div class="rownum">' + r + '</div>';
      letters.forEach(function (letter, j) {
        if (j === half) h += '<div class="aisle"></div>';
        var id = r + letter, s = L.seats[id], isTaken = !!taken[id], off = cab.name !== L.ticket;
        var cls = "seat " + cab.css + (isTaken ? " taken" : "") + (off ? " off" : "") +
                  (s.extra && !isTaken ? " xl" : "");
        var tipTxt = isTaken ? id + ": already taken"
                   : off ? id + ": not in the cabin on your ticket"
                   : id + ": " + s.kind + ", " + s.pitch + " in legroom. " + s.view;
        h += '<button type="button" class="' + cls + '" data-seat="' + id + '" title="' + esc(tipTxt) + '"' +
             (isTaken || off ? " disabled" : "") + ">" + (isTaken ? "✕" : id) + "</button>";
      });
      h += "</div>";
    });
    if (L.breaks[cab.name]) h += '<div class="galley">' + esc(L.breaks[cab.name]) + "</div>";
  });
  h += '<div class="galley">Lavatories and galley</div></div></div>';
  $("map").innerHTML = h;
}

function refreshMap() {
  var btns = document.querySelectorAll("#map .seat[data-seat]");
  for (var i = 0; i < btns.length; i++) {
    var b = btns[i];
    if (b.disabled) continue;
    var id = b.getAttribute("data-seat"), o = ownerOf(id);
    b.classList.toggle("mine", o !== null);
    b.classList.toggle("focus", S.focus === id);
    b.textContent = o !== null ? "P" + (+o + 1) : id;
  }
}

function refreshPills() {
  var h = "";
  L.passengers.forEach(function (nm, i) {
    var s = S.sel[i];
    h += '<button type="button" class="pill' + (S.active === i ? " on" : "") + '" data-i="' + i + '">' +
         '<span class="pn">P' + (i + 1) + "</span>" + esc(nm) + "<b>" + (s ? s : "choose a seat") + "</b></button>";
  });
  $("pills").innerHTML = h;
  var who = L.passengers[S.active];
  $("tip").innerHTML = "Tap a free seat to choose it for <b>" + esc(who) + "</b>. " +
    (L.passengers.length > 1 ? "Tap a name above to switch passenger." : "");
}

function refreshInfo() {
  var el = $("info");
  if (S.focus === null) {
    el.innerHTML = '<div class="infocard muted">Tap a free seat on the map. It is chosen straight away, ' +
      "and you can look at it in 3D: legroom, and the view from the window.</div>";
    return;
  }
  var id = S.focus, s = L.seats[id], o = ownerOf(id), k = Math.round(kneeIn(s));
  var h = '<div class="infocard"><b>Seat ' + id + " · " + s.kind + " · " + esc(s.cabin) + "</b>";
  if (o !== null) h += '<span class="chip sel">Chosen for ' + esc(L.passengers[+o]) + "</span>";
  h += '<div><span class="chip ' + s.tone + '">Legroom ' + s.pitch + " in (" + s.label + ")</span>" +
       '<span class="chip">Knee room about ' + k + " in</span>" +
       '<span class="chip">Seat width ' + s.width + " in</span>" +
       '<span class="chip">Recline ' + s.recline + " in</span></div>";
  h += "<div>🪟 " + esc(s.view) + "</div>";
  if (s.notes.length) h += "<ul>" + s.notes.map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("") + "</ul>";
  h += '<div class="small">Knee room is an estimate for a passenger about 5 ft 9 in tall.</div>';
  if (o !== null) h += '<button type="button" class="linkbtn" data-act="clear">Remove this seat</button>';
  el.innerHTML = h + "</div>";
}

function captionFor(s) {
  if (S.mode === "overview") return "Side view. The coloured block is the space for your knees; the white ruler is the seat pitch.";
  if (S.mode === "legroom") return "Looking down at your knees and the seat in front of you.";
  return s.kind === "Window" ? s.view + "." : "No window at this seat. This is the nearest window.";
}

function refreshView() {
  var has = S.focus !== null;
  $("ph").hidden = has;
  $("badge").hidden = !has;
  $("hint").hidden = !has || !T;
  $("modes").hidden = !has || !T;
  if (!has) { $("cap").textContent = ""; return; }
  var s = L.seats[S.focus];
  $("badge").textContent = "Seat " + S.focus + " · " + s.kind;
  $("cap").textContent = T ? captionFor(s) : "";
  var mb = document.querySelectorAll("#modes button");
  for (var i = 0; i < mb.length; i++) mb[i].classList.toggle("on", mb[i].getAttribute("data-mode") === S.mode);
}

function refresh(rebuild3d) {
  refreshPills();
  refreshMap();
  refreshInfo();
  refreshView();
  if (rebuild3d && S.focus !== null && T) buildSeatScene(S.focus);
  fit();
}

/* ---------- Interaction ---------- */
function showSeat(id) {
  S.focus = id;
  refresh(true);
  if (window.innerWidth < 760 && T) {
    try { $("view3d").scrollIntoView({behavior: "smooth", block: "nearest"}); } catch (e) {}
  }
}

function nextWithoutSeat(from) {
  var n = L.passengers.length;
  for (var step = 1; step < n; step++) {
    var i = (from + step) % n;
    if (!S.sel[i]) return i;
  }
  return from;
}

function onSeat(id) {
  var o = ownerOf(id);
  if (o !== null) {                         // a seat that is already chosen: just look at it
    S.active = +o;
    showSeat(id);
    return;
  }
  S.sel[S.active] = id;                     // choose it for the active passenger
  S.active = nextWithoutSeat(S.active);
  sendValue();
  showSeat(id);
}

function clearSeat() {
  if (S.focus === null) return;
  var o = ownerOf(S.focus);
  if (o === null) return;
  delete S.sel[o];
  S.active = +o;
  sendValue();
  refresh(false);
}

$("map").addEventListener("click", function (e) {
  var b = e.target.closest ? e.target.closest(".seat[data-seat]") : null;
  if (b && !b.disabled) onSeat(b.getAttribute("data-seat"));
});
$("pills").addEventListener("click", function (e) {
  var b = e.target.closest ? e.target.closest(".pill") : null;
  if (!b) return;
  S.active = +b.getAttribute("data-i");
  var mine = S.sel[S.active];
  if (mine) showSeat(mine); else refresh(false);
});
$("info").addEventListener("click", function (e) {
  if (e.target.getAttribute && e.target.getAttribute("data-act") === "clear") clearSeat();
});
$("modes").addEventListener("click", function (e) {
  var m = e.target.getAttribute ? e.target.getAttribute("data-mode") : null;
  if (m) setMode(m);
});

if (window.ResizeObserver) new ResizeObserver(function () { fit(); }).observe($("app"));
window.addEventListener("resize", function () { resizeRenderer(); fit(); });
post("streamlit:componentReady", {apiVersion: 1});

/* =====================================================================
   3D cabin view (three.js). 1 unit = 1 metre. Forward is -z, up is +y.
   Seat letters run left (x < 0) to right (x > 0).
   ===================================================================== */
function rng(seed) {
  return function () {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

function initThree() {
  if (!window.THREE) { $("nofx").hidden = false; return; }
  var renderer;
  try {
    renderer = new THREE.WebGLRenderer({canvas: $("cv"), antialias: true});
  } catch (e) { $("nofx").hidden = false; return; }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(60, 1, 0.03, 200000);
  var dyn = new THREE.Group();
  scene.add(dyn);
  T = {renderer: renderer, scene: scene, camera: camera, dyn: dyn, clouds: [], visible: true,
       goal: null, cur: null, yaw: 0, pitch: 0, ghost: null, ctx: null, sunTex: null};
  buildWorld();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x9aa0b8, 0.7));
  var lamp = new THREE.PointLight(0xfff1dc, 0.25, 12);
  lamp.position.set(0, 1.9, -0.4);
  scene.add(lamp);
  resizeRenderer();
  setupDrag();
  if (window.IntersectionObserver) {
    new IntersectionObserver(function (es) { T.visible = es[0].isIntersecting; }).observe($("view3d"));
  }
  requestAnimationFrame(loop);
}

function resizeRenderer() {
  if (!T) return;
  var v = $("view3d"), w = v.clientWidth, h = v.clientHeight;
  if (!w || !h) return;
  T.renderer.setSize(w, h, false);
  T.camera.aspect = w / h;
  T.camera.updateProjectionMatrix();
}

function canvasTex(w, h, draw) {
  var c = document.createElement("canvas");
  c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  var t = new THREE.CanvasTexture(c);
  t.skybookKeep = true;   // shared texture: never disposed
  return t;
}

/* Everything outside the plane: sky, ground far below, clouds. Built once. */
function buildWorld() {
  var scene = T.scene;
  scene.background = new THREE.Color(0xcfe6ff);
  scene.fog = new THREE.Fog(0xdcefff, 25000, 95000);

  var skyTex = canvasTex(4, 512, function (g, w, h) {
    var gr = g.createLinearGradient(0, 0, 0, h);
    gr.addColorStop(0, "#1c5fc4"); gr.addColorStop(0.28, "#4f9be8");
    gr.addColorStop(0.46, "#b9dcff"); gr.addColorStop(0.5, "#dcefff"); gr.addColorStop(1, "#dcefff");
    g.fillStyle = gr; g.fillRect(0, 0, w, h);
  });
  var sky = new THREE.Mesh(new THREE.SphereGeometry(100000, 24, 16),
    new THREE.MeshBasicMaterial({map: skyTex, side: THREE.BackSide, fog: false, depthWrite: false}));
  sky.renderOrder = -10;
  scene.add(sky);

  var rnd = rng(7);
  var groundTex = canvasTex(512, 512, function (g) {
    g.fillStyle = "#86a95d"; g.fillRect(0, 0, 512, 512);
    var pal = ["#8db562", "#a7b96a", "#c8b86b", "#6c9951", "#d5c68a", "#5d8d4d", "#b2a072", "#9fc27a"];
    for (var i = 0; i < 150; i++) {
      g.fillStyle = pal[(rnd() * pal.length) | 0];
      g.fillRect(rnd() * 512, rnd() * 512, 20 + rnd() * 90, 16 + rnd() * 70);
    }
    g.strokeStyle = "#cfc7b0"; g.lineWidth = 2;
    for (i = 0; i < 6; i++) { g.beginPath(); g.moveTo(rnd() * 512, 0); g.lineTo(rnd() * 512, 512); g.stroke(); }
    g.strokeStyle = "#6fa8d8"; g.lineWidth = 3; g.beginPath(); g.moveTo(0, rnd() * 512);
    g.bezierCurveTo(150, rnd() * 512, 300, rnd() * 512, 512, rnd() * 512); g.stroke();
  });
  groundTex.wrapS = groundTex.wrapT = THREE.RepeatWrapping;
  groundTex.repeat.set(36, 36);
  groundTex.anisotropy = T.renderer.capabilities.getMaxAnisotropy();
  var ground = new THREE.Mesh(new THREE.CircleGeometry(95000, 48), new THREE.MeshBasicMaterial({map: groundTex}));
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -9500;
  scene.add(ground);

  var puff = canvasTex(128, 128, function (g) {
    var r = g.createRadialGradient(64, 64, 4, 64, 64, 62);
    r.addColorStop(0, "rgba(255,255,255,0.95)"); r.addColorStop(0.5, "rgba(255,255,255,0.55)");
    r.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = r; g.fillRect(0, 0, 128, 128);
  });
  var cmat = new THREE.SpriteMaterial({map: puff, transparent: true, depthWrite: false, fog: false, opacity: 0.92});
  for (var c = 0; c < 16; c++) {
    var cx = (rnd() < 0.5 ? -1 : 1) * (600 + rnd() * 6500);
    var cy = rnd() < 0.8 ? -2600 + rnd() * 2300 : 50 + rnd() * 500;
    var cz = -7000 + rnd() * 10000;
    var n = 4 + ((rnd() * 3) | 0);
    for (var p = 0; p < n; p++) {
      var sp = new THREE.Sprite(cmat);
      var sz = 700 + rnd() * 1300;
      sp.scale.set(sz, sz * 0.55, 1);
      sp.position.set(cx + (rnd() - 0.5) * 900, cy + (rnd() - 0.5) * 160, cz + (rnd() - 0.5) * 900);
      scene.add(sp);
      T.clouds.push(sp);
    }
  }
  T.sunTex = canvasTex(128, 128, function (g) {
    var r = g.createRadialGradient(64, 64, 2, 64, 64, 62);
    r.addColorStop(0, "rgba(255,252,235,1)"); r.addColorStop(0.18, "rgba(255,240,190,0.9)");
    r.addColorStop(1, "rgba(255,220,150,0)");
    g.fillStyle = r; g.fillRect(0, 0, 128, 128);
  });
}

/* ----- small builders ----- */
function mk(color, o) {
  o = o || {};
  var p = {color: color};
  if (o.opacity !== undefined) { p.transparent = true; p.opacity = o.opacity; p.depthWrite = false; }
  if (o.side) p.side = o.side;
  if (o.emissive !== undefined) p.emissive = o.emissive;
  return new THREE.MeshLambertMaterial(p);
}
function box(w, h, d, color, x, y, z, parent, o) {
  var m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mk(color, o));
  m.position.set(x, y, z);
  (parent || T.dyn).add(m);
  return m;
}
function plane(w, h, color, x, y, z, rx, ry) {
  var m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mk(color, {side: THREE.DoubleSide}));
  m.position.set(x, y, z);
  m.rotation.set(rx || 0, ry || 0, 0);
  T.dyn.add(m);
  return m;
}
function roundedRect(cx, cy, w, h, r) {
  var pts = [], hw = w / 2 - r, hh = h / 2 - r;
  [[hw, hh, 0], [-hw, hh, Math.PI / 2], [-hw, -hh, Math.PI], [hw, -hh, 1.5 * Math.PI]].forEach(function (c) {
    for (var i = 0; i <= 6; i++) {
      var a = c[2] + (Math.PI / 2) * i / 6;
      pts.push(new THREE.Vector2(cx + c[0] + r * Math.cos(a), cy + c[1] + r * Math.sin(a)));
    }
  });
  return pts;
}
function label(text, bg, fg, width, x, y, z) {
  var c = document.createElement("canvas");
  c.width = 320; c.height = 80;
  var g = c.getContext("2d"), r = 22;
  g.fillStyle = bg;
  g.beginPath();
  g.moveTo(r, 4); g.arcTo(316, 4, 316, 76, r); g.arcTo(316, 76, 4, 76, r);
  g.arcTo(4, 76, 4, 4, r); g.arcTo(4, 4, 316, 4, r);
  g.fill();
  g.fillStyle = fg; g.font = "bold 34px Arial, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText(text, 160, 42);
  var s = new THREE.Sprite(new THREE.SpriteMaterial({map: new THREE.CanvasTexture(c), transparent: true, depthTest: false}));
  s.scale.set(width, width * 80 / 320, 1);
  s.position.set(x, y, z);
  s.renderOrder = 20;
  T.dyn.add(s);
  return s;
}

var CAB_COL = {biz: 0x6c55c4, prem: 0xe08a3a, eco: 0x3f7fd0};
var SKINS = [0xf2c9a5, 0xd9a47a, 0xb97c55, 0x8a5a3c, 0xf6d6b8];
var CLOTHES = [0x56627a, 0x7c8aa5, 0x8a6f8f, 0x5f8a7d, 0xa08a5a, 0x6b6f80, 0xb4655f];

/* Seat in its own coordinates: backrest front face at z = 0, knees point to -z. */
function makeSeat(css, w, recline) {
  var g = new THREE.Group(), col = CAB_COL[css];
  var light = new THREE.Color(col).offsetHSL(0, 0, 0.08).getHex();
  box(w, 0.12, 0.46, col, 0, 0.40, -0.23, g);                    // cushion
  box(w * 0.66, 0.32, 0.26, 0x2b3047, 0, 0.17, -0.2, g);          // base
  box(0.05, 0.05, 0.40, 0x2b3047, -(w / 2 + 0.02), 0.63, -0.2, g);  // armrests
  box(0.05, 0.05, 0.40, 0x2b3047, (w / 2 + 0.02), 0.63, -0.2, g);
  var back = new THREE.Group();
  back.position.set(0, 0.46, 0);
  back.rotation.x = 0.10 + recline * 0.012;                      // tilts the top backwards
  g.add(back);
  box(w, 0.66, 0.10, col, 0, 0.33, 0.05, back);                  // backrest, z from 0 to 0.10
  box(w * 0.7, 0.22, 0.12, light, 0, 0.77, 0.05, back);          // headrest
  box(w * 0.72, 0.22, 0.012, 0xe8e6df, 0, 0.17, 0.108, back);    // folded tray table
  box(w * 0.8, 0.12, 0.03, 0x2b3047, 0, 0.04, 0.115, back);      // seat-back pocket
  if (css !== "eco") box(0.26, 0.17, 0.012, 0x0c1330, 0, 0.47, 0.108, back, {emissive: 0x1a3b80});  // screen
  return g;
}

/* Seated person. Parts flagged "upper" are hidden when the camera is the person's head. */
function makePerson(cloth, skin, ghost) {
  var g = new THREE.Group(), o = ghost ? {opacity: 0.85} : undefined;
  function part(w, h, d, c, x, y, z, upper) {
    var m = box(w, h, d, c, x, y, z, g, o);
    if (upper) m.userData.upper = true;
  }
  part(0.38, 0.52, 0.20, cloth, 0, 0.80, -0.12, true);           // torso
  part(0.09, 0.34, 0.10, cloth, -0.24, 0.80, -0.14, true);       // arms
  part(0.09, 0.34, 0.10, cloth, 0.24, 0.80, -0.14, true);
  var head = new THREE.Mesh(new THREE.SphereGeometry(0.105, 16, 12), mk(skin, o));
  head.position.set(0, 1.26, -0.11);
  head.userData.upper = true;
  g.add(head);
  [-0.10, 0.10].forEach(function (sx) {
    part(0.14, 0.13, 0.47, cloth, sx, 0.53, -0.355, false);      // thigh, knee front at z = -0.59
    part(0.12, 0.46, 0.12, cloth, sx, 0.27, -0.53, false);       // shin
    part(0.12, 0.07, 0.26, 0x2a2d3a, sx, 0.04, -0.61, false);    // shoe
  });
  return g;
}

function globalRowZ() {            // distance of each row from row 1, in metres, growing towards the tail
  var z = {}, acc = 0, first = true;
  L.cabins.forEach(function (c) {
    c.rows.forEach(function (r) {
      if (!first) acc += L.seats[r + c.letters.charAt(0)].pitch * IN;
      z[r] = acc; first = false;
    });
  });
  return z;
}

function clearDyn() {
  var d = T.dyn;
  while (d.children.length) {
    var c = d.children[0];
    d.remove(c);
    c.traverse(function (o) {
      if (o.geometry) o.geometry.dispose();
      if (o.material) {
        if (o.material.map && !o.material.map.skybookKeep) o.material.map.dispose();
        o.material.dispose();
      }
    });
  }
}

function buildSeatScene(id) {
  clearDyn();
  var s = L.seats[id], cab = cabinOf(s.cabin), letters = cab.letters.split("");
  var n = letters.length, half = n / 2, w = s.width * IN, lat = w + 0.05, pitch = s.pitch * IN;
  var W = 1.9, edge = 0.1, DS = THREE.DoubleSide;
  var xs = letters.map(function (_, j) {
    return j < half ? -W + edge + lat * (j + 0.5) : W - edge - lat * (n - j - 0.5);
  });
  var j0 = letters.indexOf(s.letter), sx = xs[j0], sg = j0 < half ? -1 : 1;
  var first = cab.rows[0], last = cab.rows[cab.rows.length - 1];
  var ahead = [];
  for (var k = 1; k <= 2; k++) if (s.row - k >= first) ahead.push(k);
  var hasAhead = ahead.length > 0;
  var zWall = hasAhead ? -ahead.length * pitch - 0.8 : -(pitch - 0.05);   // bulkhead wall or end of preview
  var zBack = 1.9, zc = (zWall + zBack) / 2, Lz = zBack - zWall;
  var taken = {};
  L.taken.forEach(function (t) { taken[t] = true; });

  /* cabin shell */
  plane(2 * W, Lz, 0x4b5068, 0, 0, zc, -Math.PI / 2, 0);               // floor
  plane(0.30, Lz, 0x6c7390, 0, 0.004, zc, -Math.PI / 2, 0);            // aisle runner
  plane(2 * W, Lz, 0xf2f0ea, 0, 2.25, zc, Math.PI / 2, 0);             // ceiling
  box(0.62, 0.62, Lz, 0xe6e1d6, -(W - 0.31), 1.94, zc);                // overhead bins
  box(0.62, 0.62, Lz, 0xe6e1d6, (W - 0.31), 1.94, zc);
  plane(2 * W, 2.25, hasAhead ? 0xd4cfc4 : 0xcfc8ea, 0, 1.125, zWall, 0, 0);   // front wall / bulkhead
  plane(2 * W, 2.25, 0xcfcad8, 0, 1.125, zBack, 0, 0);                 // back wall

  var winZ = [];
  [-1, 0, 1, 2].forEach(function (kk) {
    var r = s.row - kk, z = -kk * pitch - 0.22;
    if (r >= first && r <= last && z > zWall + 0.25 && z < zBack - 0.25) winZ.push(z);
  });
  [-1, 1].forEach(function (sign) {
    var shape = new THREE.Shape([new THREE.Vector2(zWall, 0), new THREE.Vector2(zBack, 0),
                                 new THREE.Vector2(zBack, 1.63), new THREE.Vector2(zWall, 1.63)]);
    winZ.forEach(function (z) {
      shape.holes.push(new THREE.Path(roundedRect(z, 1.12, 0.27, 0.37, 0.1)));
    });
    var wall = new THREE.Mesh(new THREE.ShapeGeometry(shape), mk(0xdcd6ca, {side: DS}));
    wall.rotation.y = -Math.PI / 2;
    wall.position.x = sign * W;
    T.dyn.add(wall);
    winZ.forEach(function (z) {
      var bez = new THREE.Shape(roundedRect(z, 1.12, 0.35, 0.46, 0.12));
      bez.holes.push(new THREE.Path(roundedRect(z, 1.12, 0.27, 0.37, 0.1)));
      var m = new THREE.Mesh(new THREE.ShapeGeometry(bez), mk(0xf6f3ec, {side: DS}));
      m.rotation.y = -Math.PI / 2;
      m.position.x = sign * (W - 0.012);
      T.dyn.add(m);
    });
    if (isExit(s)) {                                                   // emergency exit door and sign
      box(0.06, 1.5, 0.72, 0xd9d4c8, sign * (W - 0.03), 0.78, -0.78);
      box(0.03, 0.04, 0.20, 0xb33a3a, sign * (W - 0.07), 0.85, -0.62);
      label("EXIT", "#d62828", "#ffffff", 0.34, sign * (W - 0.1), 1.55, -0.78);
    }
  });

  /* wings, engines and the sun, outside the windows */
  var gz = globalRowZ();
  var wrows = Object.keys(L.wings).map(Number);
  var zf = gz[Math.min.apply(null, wrows)] - gz[s.row] - 0.7;
  var zb = gz[Math.max.apply(null, wrows)] - gz[s.row] + 0.35;
  [-1, 1].forEach(function (sign) {
    var x0 = W + 0.08, span = 13;
    var pts = [[x0, zf], [x0 + span, zf + 6.2], [x0 + span, zf + 7.2], [x0, zb]].map(function (p) {
      return new THREE.Vector2(sign * p[0], -p[1]);
    });
    var wing = new THREE.Mesh(new THREE.ExtrudeGeometry(new THREE.Shape(pts), {depth: 0.25, bevelEnabled: false}),
                              mk(0xdfe5ee, {side: DS}));
    wing.rotation.x = -Math.PI / 2;
    wing.position.y = 0.17;
    T.dyn.add(wing);
    var ex = sign * (W + 4.8);
    var eng = new THREE.Mesh(new THREE.CylinderGeometry(0.78, 0.78, 3.4, 20), mk(0xc9d0db));
    eng.rotation.x = Math.PI / 2;
    eng.position.set(ex, -0.62, zf + 1.4);
    T.dyn.add(eng);
    var inlet = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.6, 0.12, 20), mk(0x2e3445));
    inlet.rotation.x = Math.PI / 2;
    inlet.position.set(ex, -0.62, zf - 0.3);
    T.dyn.add(inlet);
    box(0.28, 0.7, 1.8, 0xb8bfcc, ex, -0.05, zf + 2.2);
    var tipLight = new THREE.Mesh(new THREE.SphereGeometry(0.14, 8, 6),
      new THREE.MeshBasicMaterial({color: sign < 0 ? 0xff3b3b : 0x3bff6a}));
    tipLight.position.set(sign * (x0 + span), 0.5, zf + 6.7);
    T.dyn.add(tipLight);
  });
  var sd = new THREE.Vector3(sg * 0.85, 0.30, -0.35).normalize();
  var sun = new THREE.DirectionalLight(0xfff0d6, 0.45);
  sun.position.copy(sd).multiplyScalar(100);
  T.dyn.add(sun);
  var sunSprite = new THREE.Sprite(new THREE.SpriteMaterial({map: T.sunTex, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false, fog: false, opacity: 0.95}));
  sunSprite.position.copy(sd).multiplyScalar(60000);
  sunSprite.scale.set(14000, 14000, 1);
  T.dyn.add(sunSprite);

  /* seats: my row, and up to two rows in front */
  function seatAt(css, x, z, rowNo, letter) {
    var g = makeSeat(css, w, s.recline);
    g.position.set(x, 0, z);
    var sid = rowNo + letter, h = rowNo * 7 + letter.charCodeAt(0);
    if (taken[sid]) g.add(makePerson(CLOTHES[h % CLOTHES.length], SKINS[(h * 3) % SKINS.length], false));
    T.dyn.add(g);
    return g;
  }
  var ghost = null;
  letters.forEach(function (letter, j) {
    var g = seatAt(cab.css, xs[j], 0, s.row, letter);
    if (j === j0) { ghost = makePerson(0x7b6dff, 0xffd0b0, true); g.add(ghost); }
  });
  ahead.forEach(function (kk) {
    letters.forEach(function (letter, j) { seatAt(cab.css, xs[j], -kk * pitch, s.row - kk, letter); });
  });
  T.ghost = ghost;

  /* leg space: knee-room block and a seat-pitch ruler */
  var zKnee = -0.59, zAhead = hasAhead ? -(pitch - 0.10) : zWall;
  var gap = Math.max(0.02, zKnee - zAhead);
  var tone = s.tone === "g" ? 0x2ecc71 : s.tone === "b" ? 0x3b8ee8 : 0xffa23a;
  var gapBox = box(w * 0.85, 0.5, gap, tone, sx, 0.5, zKnee - gap / 2, null, {opacity: 0.4});
  var edges = new THREE.LineSegments(new THREE.EdgesGeometry(gapBox.geometry),
                                     new THREE.LineBasicMaterial({color: tone}));
  edges.position.copy(gapBox.position);
  T.dyn.add(edges);
  var rx = sx - sg * 0.30;
  box(0.025, 0.012, pitch, 0xffffff, rx, 0.02, -pitch / 2, null, {emissive: 0xffffff});
  box(0.16, 0.012, 0.025, 0xffffff, rx, 0.02, 0, null, {emissive: 0xffffff});
  box(0.16, 0.012, 0.025, 0xffffff, rx, 0.02, -pitch, null, {emissive: 0xffffff});
  label(s.pitch + " in legroom", "rgba(20,16,60,0.85)", "#ffffff", 0.62, rx, 0.22, -pitch / 2);
  label("about " + Math.round(kneeIn(s)) + " in knee room", "rgba(20,16,60,0.85)", "#ffffff", 0.78,
        sx, 0.98, zKnee - gap / 2);

  T.ctx = {sx: sx, sg: sg, W: W, pitch: pitch, isWindow: s.kind === "Window"};
  setGoals(true);
  showUpperBody();
}

/* ----- camera ----- */
function goalFor(mode) {
  var c = T.ctx, V = THREE.Vector3;
  if (mode === "overview") {
    var cx = Math.max(-(c.W - 0.75), Math.min(c.W - 0.75, c.sx - c.sg * 1.7));
    return {pos: new V(cx, 1.75, 0.45 + c.pitch * 0.4), tgt: new V(c.sx, 0.62, -c.pitch * 0.5), fov: 58};
  }
  if (mode === "legroom") return {pos: new V(c.sx, 1.24, -0.10), tgt: new V(c.sx, 0.40, -0.85), fov: 78};
  return {pos: new V(c.sx + c.sg * 0.02, 1.2, -0.12), tgt: new V(c.sg * (c.W + 40), 1.2 - 7.5, -0.12 - 6), fov: 62};
}

function setGoals(snap) {
  T.goal = goalFor(S.mode);
  if (snap || !T.cur) {
    T.cur = {pos: T.goal.pos.clone(), tgt: T.goal.tgt.clone(), fov: T.goal.fov};
  }
}

function showUpperBody() {
  if (!T || !T.ghost) return;
  T.ghost.traverse(function (o) { if (o.userData.upper) o.visible = S.mode === "overview"; });
}

function setMode(m) {
  S.mode = m;
  if (T) {
    T.yaw = 0; T.pitch = 0;
    if (T.ctx) { setGoals(false); showUpperBody(); }
  }
  refreshView();
}

function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

function applyCamera(dt) {
  var k = 1 - Math.exp(-dt * 5), cur = T.cur, g = T.goal, cam = T.camera;
  cur.pos.lerp(g.pos, k);
  cur.tgt.lerp(g.tgt, k);
  cur.fov += (g.fov - cur.fov) * k;
  cam.fov = cur.fov;
  cam.updateProjectionMatrix();
  if (S.mode === "overview") {                       // orbit around the seat
    var ox = cur.pos.x - cur.tgt.x, oy = cur.pos.y - cur.tgt.y, oz = cur.pos.z - cur.tgt.z;
    var yaw = clamp(T.yaw, -0.9, 0.9), ca = Math.cos(yaw), sa = Math.sin(yaw);
    cam.position.set(cur.tgt.x + ox * ca + oz * sa, cur.tgt.y + oy + clamp(T.pitch, -0.5, 0.5),
                     cur.tgt.z - ox * sa + oz * ca);
    cam.lookAt(cur.tgt);
  } else {                                           // look around from the seat
    var dx = cur.tgt.x - cur.pos.x, dy = cur.tgt.y - cur.pos.y, dz = cur.tgt.z - cur.pos.z;
    var yaw0 = Math.atan2(-dx, -dz), pitch0 = Math.atan2(dy, Math.sqrt(dx * dx + dz * dz));
    cam.position.copy(cur.pos);
    cam.rotation.set(clamp(pitch0 + T.pitch, -1.3, 1.3), yaw0 + clamp(T.yaw, -1.4, 1.4), 0, "YXZ");
  }
}

var lastT = 0;
function loop(t) {
  requestAnimationFrame(loop);
  if (!T || S.focus === null || !T.ctx || document.hidden || !T.visible) { lastT = t; return; }
  var dt = Math.min(0.05, Math.max(0, (t - lastT) / 1000));
  lastT = t;
  for (var i = 0; i < T.clouds.length; i++) {          // clouds drift past, as the plane flies on
    var c = T.clouds[i];
    c.position.z += 90 * dt;
    if (c.position.z > 4000) c.position.z -= 14000;
  }
  applyCamera(dt);
  T.renderer.render(T.scene, T.camera);
}

function setupDrag() {
  var cv = $("cv"), drag = null;
  cv.addEventListener("pointerdown", function (e) {
    drag = {x: e.clientX, y: e.clientY};
    try { cv.setPointerCapture(e.pointerId); } catch (err) {}
    cv.style.cursor = "grabbing";
  });
  cv.addEventListener("pointermove", function (e) {
    if (!drag || !T) return;
    T.yaw += (e.clientX - drag.x) * 0.005;
    T.pitch += (e.clientY - drag.y) * 0.004;
    T.pitch = clamp(T.pitch, -0.7, 0.7);
    drag.x = e.clientX; drag.y = e.clientY;
  });
  function end() { drag = null; cv.style.cursor = "grab"; }
  cv.addEventListener("pointerup", end);
  cv.addEventListener("pointercancel", end);
  cv.addEventListener("dblclick", function () { if (T) { T.yaw = 0; T.pitch = 0; } });
}
})();
</script>
</body>
</html>
"""


@st.cache_resource
def seat_picker_component():
    """Save the page to a temp folder once and register it as a Streamlit component."""
    digest = hashlib.sha1(SEAT_PICKER_HTML.encode("utf-8")).hexdigest()[:10]
    folder = Path(tempfile.gettempdir()) / f"skybook_seat_picker_{digest}"
    folder.mkdir(exist_ok=True)
    (folder / "index.html").write_text(SEAT_PICKER_HTML, encoding="utf-8")
    return components.declare_component("skybook_seat_picker", path=str(folder))


# ---------- State ----------
defaults = {"page": "Home", "bookings": [], "flight": None, "passengers": [],
            "booking": None, "seats": {}, "from_city": "Kochi",
            "to_city": "Delhi", "date": date.today(), "people": 1}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------- Styling ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;800&display=swap');
.stApp{background:linear-gradient(160deg,#35b6ff,#6a5cff,#ff5fa2,#ffb347);
 background-size:300% 300%;animation:sky 18s ease infinite}
@keyframes sky{0%,100%{background-position:0% 0%}50%{background-position:100% 100%}}
[data-testid="stHeader"]{background:transparent}
.block-container{position:relative;z-index:2;max-width:1100px;margin-top:1rem;
 background:rgba(255,255,255,.94);border-radius:26px;padding:1.5rem 2rem 2rem!important;
 box-shadow:0 20px 60px rgba(40,20,120,.35)}
h1,h2,h3{font-family:'Baloo 2',cursive!important;color:#3a1c8f}
.cloud{position:fixed;z-index:-1;pointer-events:none;background:rgba(255,255,255,.55);
 border-radius:100px;animation:drift linear infinite}
.cloud::before,.cloud::after{content:"";position:absolute;background:inherit;border-radius:50%}
.cloud::before{width:50%;height:160%;top:-70%;left:15%}
.cloud::after{width:35%;height:130%;top:-45%;right:15%}
.c1{width:160px;height:40px;top:12%;left:-200px;animation-duration:38s}
.c2{width:240px;height:55px;top:45%;left:-300px;animation-duration:55s;animation-delay:-20s}
.c3{width:120px;height:32px;top:75%;left:-200px;animation-duration:30s;animation-delay:-8s}
@keyframes drift{to{transform:translateX(calc(100vw + 400px))}}
.hero{position:relative;overflow:hidden;color:#fff;padding:1.4rem 2rem 2.6rem;border-radius:20px;
 margin-bottom:1rem;background:linear-gradient(120deg,#ff5f6d,#ff9a44 50%,#ffd36b);
 box-shadow:0 10px 24px rgba(255,95,109,.4)}
.hero h1{margin:0;padding:0;font-size:2.8rem!important;color:#fff!important;
 font-family:'Baloo 2',cursive;text-shadow:0 3px 0 rgba(0,0,0,.12)}
.hero p{margin:.2rem 0 0;color:#fff!important;font-size:1.1rem}
.hero::after{content:"";position:absolute;left:0;right:0;bottom:16px;
 border-top:3px dashed rgba(255,255,255,.6)}
.plane{position:absolute;bottom:2px;left:-80px;font-size:2.2rem;animation:fly 8s linear infinite}
@keyframes fly{0%{left:-80px;transform:translateY(0)}50%{transform:translateY(-10px)}
 100%{left:105%;transform:translateY(0)}}
.stButton>button,.stDownloadButton>button{border:0;border-radius:999px;font-weight:700;
 background:linear-gradient(90deg,#6a5cff,#ff5fa2);box-shadow:0 6px 16px rgba(106,92,255,.35);
 transition:transform .15s,box-shadow .15s}
.stButton>button *,.stDownloadButton>button *{color:#fff!important}
[data-testid="stBaseButton-primary"]{background:linear-gradient(90deg,#ff9a44,#ff5f6d)!important}
.stButton>button:hover,.stDownloadButton>button:hover{transform:translateY(-3px) scale(1.03);
 box-shadow:0 10px 22px rgba(255,95,162,.45)}
.stButton>button:active{transform:scale(.97)}
.steps{display:flex;gap:6px;margin:.5rem 0 1rem;flex-wrap:wrap}
.step{flex:1;min-width:80px;text-align:center;padding:7px 4px;border-radius:999px;
 font-size:.85rem;background:#ece8ff;color:#5b4bb8}
.step.done{background:linear-gradient(90deg,#00c9a7,#3ad6b5);color:#fff}
.step.now{background:linear-gradient(90deg,#ff9a44,#ff5f6d);color:#fff;font-weight:700;
 animation:pulse 1.6s infinite}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(255,95,109,.55)}50%{box-shadow:0 0 0 8px rgba(255,95,109,0)}}
.fcard{background:#fff;color:#1b1650;border-left:8px solid #ff5fa2;border-radius:16px;
 padding:14px 18px;margin-bottom:6px;box-shadow:0 6px 18px rgba(58,28,143,.18);
 animation:rise .5s ease both;transition:transform .2s}
.fcard:hover{transform:translateX(6px)}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
.fcard .air{font-weight:700;font-size:1.1rem}
.fcard .route{display:flex;align-items:center;gap:14px;margin:8px 0;font-size:1.3rem;font-weight:600}
.fcard .line{flex:1;position:relative;border-top:2px dashed #b7a8ff;text-align:center;
 font-size:.75rem;font-weight:400;padding-top:6px}
.fcard .line::after{content:"✈";position:absolute;left:0;top:-15px;font-size:1.1rem;
 color:#6a5cff;animation:along 3s linear infinite}
@keyframes along{to{left:calc(100% - 1rem)}}
.tag{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.78rem;
 background:#ffe2ee;color:#c2185b;margin-right:6px}
.price{font-size:1.4rem;font-weight:800;color:#ff5f6d}
.bp{background:#fff;color:#1b1650;border-radius:16px;margin:14px 0;overflow:hidden;
 box-shadow:0 10px 26px rgba(58,28,143,.25);display:flex;flex-wrap:wrap;
 animation:slide .7s cubic-bezier(.2,.9,.3,1.2) both}
@keyframes slide{from{opacity:0;transform:translateX(-60px)}to{opacity:1;transform:none}}
.bp .main{flex:3;min-width:260px;padding:0 0 18px}
.bp .stub{flex:1;min-width:170px;padding:18px;border-left:2px dashed #b7a8ff;background:#fff3d6}
.bp .head{background:linear-gradient(90deg,#6a5cff,#ff5fa2);color:#fff;padding:9px 22px;
 font-weight:700;letter-spacing:.5px}
.bp .big{font-size:2.2rem;font-weight:800;line-height:1;color:#3a1c8f}
.bp .small{font-size:.75rem;color:#6b7280}
.bp .row{display:flex;gap:22px;margin:14px 22px 0;flex-wrap:wrap;align-items:center}
.bp .bar{height:34px;margin-top:10px;background:repeating-linear-gradient(90deg,#3a1c8f 0 2px,
 transparent 2px 5px,#3a1c8f 5px 6px,transparent 6px 10px)}
.flyby{position:fixed;inset:0;z-index:9999;pointer-events:none;overflow:hidden;
 animation:fadeout 1.7s forwards}
.flyplane{position:absolute;top:42%;left:-150px;font-size:5rem;
 filter:drop-shadow(0 10px 8px rgba(0,0,0,.3));animation:flyacross 1.5s ease-in forwards}
.flyplane::before{content:"";position:absolute;right:85%;top:55%;width:320px;height:8px;
 border-radius:8px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.95))}
@keyframes flyacross{from{left:-150px;transform:translateY(60px)}
 to{left:105%;transform:translateY(-140px)}}
@keyframes fadeout{0%,85%{opacity:1}100%{opacity:0}}
@media(max-width:640px){.block-container{padding:1rem!important}.hero h1{font-size:2rem!important}}
@media(prefers-reduced-motion:reduce){.flyby{display:none}*{animation:none!important;transition:none!important}}
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="cloud c1"></div><div class="cloud c2"></div><div class="cloud c3"></div>'
    '<div class="hero"><h1>SkyBook</h1><p>Your Journey, Our Responsibility</p>'
    '<div class="plane">✈️</div></div>',
    unsafe_allow_html=True)

# ---------- Navigation ----------
a, b, c = st.columns(3)
for col, label, pg in [(a, "🏠 Home", "Home"), (b, "🔎 Search Flights", "Search"),
                       (c, "📚 My Bookings", "Bookings")]:
    if col.button(label, use_container_width=True, key="nav_" + pg):
        st.session_state.page = pg
        st.session_state.fly = True
        st.rerun()

page = st.session_state.page
if page != "Seats":
    st.session_state.pop("seat_seed", None)

# Plane flies across the screen after a page-changing button click
if st.session_state.pop("fly", False):
    st.markdown('<div class="flyby"><span class="flyplane">✈️</span></div>',
                unsafe_allow_html=True)


def go(p):
    st.session_state.page = p
    st.session_state.fly = True
    st.rerun()


def progress(current):
    html = '<div class="steps">'
    idx = STEPS.index(current)
    for i, s in enumerate(STEPS):
        cls = "now" if i == idx else ("done" if i < idx else "")
        html += f'<div class="step {cls}">{s}</div>'
    st.markdown(html + "</div>", unsafe_allow_html=True)


def make_flights(src, dst, d):
    rng = random.Random(f"{src}{dst}{d}".lower())
    base = rng.randint(3200, 6500)
    out = []
    for name, code in rng.sample(AIRLINES, 5):
        dep = datetime.combine(d, time(rng.choice([5, 7, 9, 12, 15, 18, 21]),
                                       rng.choice([0, 15, 30, 45])))
        stops = rng.choice([0, 0, 1])
        mins = rng.randint(100, 260) + (70 if stops else 0)
        cls = rng.choice(["Economy", "Economy", "Premium Economy", "Business"])
        price = int(base * CLASS_MULT[cls] * (0.9 if stops else 1) / 50) * 50
        out.append({"airline": name, "number": f"{code}-{rng.randint(100, 999)}",
                    "dep": dep.strftime("%I:%M %p"),
                    "arr": (dep + timedelta(minutes=mins)).strftime("%I:%M %p"),
                    "mins": mins, "stops": stops, "class": cls, "price": price})
    return out


def taken_seats(flight):
    rng = random.Random(flight["number"] + str(st.session_state.date))
    out = set()
    for name, *_ in CABINS:
        seats = cabin_seats(name)
        out |= set(rng.sample(seats, max(0, min(round(len(seats) * 0.3), len(seats) - 9))))
    return out


def boarding_pass(b, p):
    return (
        f'<div class="bp"><div class="main"><div class="head">SKYBOOK BOARDING PASS</div>'
        f'<div class="row"><div><div class="big">{CODES.get(b["from"], b["from"][:3].upper())}</div>'
        f'<div class="small">{b["from"]}</div></div><div class="big">✈</div>'
        f'<div><div class="big">{CODES.get(b["to"], b["to"][:3].upper())}</div>'
        f'<div class="small">{b["to"]}</div></div></div>'
        f'<div class="row"><div><div class="small">Passenger</div><b>{p["name"]}</b></div>'
        f'<div><div class="small">Flight</div><b>{b["flight"]}</b></div>'
        f'<div><div class="small">Date</div><b>{b["date"]}</b></div>'
        f'<div><div class="small">Time</div><b>{b["time"]}</b></div></div></div>'
        f'<div class="stub"><div class="small">Seat</div><div class="big">{p["seat"]}</div>'
        f'<div class="small" style="margin-top:8px">Class</div><b>{b["class"]}</b>'
        f'<div class="small" style="margin-top:8px">Booking</div><b>{b["id"]}</b>'
        f'<div class="bar"></div></div></div>')


# ---------- Home ----------
if page == "Home":
    st.header("Welcome to SkyBook! 👋")
    st.write("Search flights, pick your seat on a live seat map, and get a boarding pass.")
    x, y, z = st.columns(3)
    x.subheader("🔎 Search")
    x.write("Choose cities and compare 5 flights by price, speed or time.")
    y.subheader("💺 Pick Seats")
    y.write("Tap a seat on the map and look at it in 3D before you choose.")
    z.subheader("🎫 Boarding Pass")
    z.write("Add meals and baggage, apply a promo, and download your ticket.")
    st.info("Try the promo code **SKY10** at payment for 10% off the base fare.")
    if st.button("Start Booking", key="start", type="primary"):
        go("Search")

# ---------- Search ----------
elif page == "Search":
    progress("Search")
    st.header("🔎 Search Flights")
    x, y = st.columns(2)
    source = x.selectbox("From", CITIES, index=CITIES.index(st.session_state.from_city))
    destination = y.selectbox("To", CITIES, index=CITIES.index(st.session_state.to_city))
    d = st.date_input("Travel Date", value=max(st.session_state.date, date.today()),
                      min_value=date.today())
    people = st.number_input("Passengers", 1, 9, st.session_state.people)

    if st.button("Search Flights", key="submit_search", type="primary"):
        if source == destination:
            st.warning("Departure and destination must differ.")
        else:
            st.session_state.update(from_city=source, to_city=destination,
                                    date=d, people=int(people))
            go("Flights")

# ---------- Flights ----------
elif page == "Flights":
    progress("Flights")
    ss = st.session_state
    st.header(f"✈️ {ss.from_city} → {ss.to_city}")
    st.caption(f"{ss.date.strftime('%A, %d %B %Y')} · {ss.people} passenger(s)")

    x, y = st.columns(2)
    sort = x.radio("Sort by", ["Cheapest", "Fastest", "Earliest"], horizontal=True)
    cls_filter = y.multiselect("Class", list(CLASS_MULT), default=list(CLASS_MULT))

    flights = [f for f in make_flights(ss.from_city, ss.to_city, ss.date)
               if f["class"] in cls_filter]
    key = {"Cheapest": lambda f: f["price"], "Fastest": lambda f: f["mins"],
           "Earliest": lambda f: datetime.strptime(f["dep"], "%I:%M %p")}[sort]
    flights.sort(key=key)

    if not flights:
        st.info("No flights match these filters. Select more classes.")
    for i, f in enumerate(flights):
        stop_txt = "Non-stop" if f["stops"] == 0 else "1 stop"
        st.markdown(
            f'<div class="fcard"><div class="air">{f["airline"]} '
            f'<span style="font-weight:400">{f["number"]}</span></div>'
            f'<div class="route"><span>{f["dep"]}</span>'
            f'<span class="line">{f["mins"] // 60}h {f["mins"] % 60}m · {stop_txt}</span>'
            f'<span>{f["arr"]}</span></div>'
            f'<span class="tag">{f["class"]}</span>'
            f'<span class="price">₹{f["price"]:,}</span> per passenger</div>',
            unsafe_allow_html=True)
        if st.button("Select " + f["airline"], key=f"flight_{i}"):
            for k in [k for k in ss.keys() if k.startswith(("seat_", "meal_", "bag_"))]:
                del ss[k]
            ss.flight = {"airline": f["airline"], "number": f["number"],
                         "time": f"{f['dep']} - {f['arr']}", "class": f["class"],
                         "price": f["price"]}
            ss.passengers, ss.seats = [], {}
            go("Passengers")

    if st.button("← Change search"):
        go("Search")

# ---------- Passengers ----------
elif page == "Passengers":
    progress("Passengers")
    st.header("👤 Passenger Details")
    data = []
    for i in range(st.session_state.people):
        st.subheader(f"Passenger {i + 1}")
        name = st.text_input("Full Name", key=f"name_{i}")
        x, y = st.columns(2)
        age = x.number_input("Age", 1, 100, 18, key=f"age_{i}")
        kind = y.selectbox("Type", ["Adult", "Child"], key=f"type_{i}")
        phone = st.text_input("Phone (10 digits)", key=f"phone_{i}")
        email = st.text_input("Email", key=f"email_{i}")
        data.append({"name": name.strip(), "age": age, "type": kind,
                     "phone": phone.strip(), "email": email.strip()})

    if st.button("Continue to Seat Selection", type="primary"):
        bad_phone = any(not (p["phone"].isdigit() and len(p["phone"]) == 10) for p in data)
        if any(not p["name"] or "@" not in p["email"] for p in data) or bad_phone:
            st.warning("Fill in every name, a 10-digit phone number and a valid email.")
        else:
            st.session_state.passengers = data
            go("Seats")
    if st.button("Back to Flights"):
        go("Flights")

# ---------- Seats ----------
elif page == "Seats":
    progress("Seats")
    ss = st.session_state
    f = ss.flight
    st.header("💺 Seat Selection")
    st.caption(f"Your ticket is for the {f['class']} cabin, so only seats there can be chosen. "
               "Tap a seat to choose it, and see it in 3D: your legroom and the view from the window.")
    taken = taken_seats(f)
    free = {s for s in cabin_seats(f["class"]) if s not in taken}
    count = len(ss.passengers)
    if "seat_seed" not in ss:      # the picker starts from the seats chosen earlier, if any
        ss.seat_seed = clean_picks(ss.get("seat_pick"), free, count)
    picked = seat_picker_component()(
        layout=seat_layout(taken, f["class"], [p["name"] for p in ss.passengers]),
        selected=ss.seat_seed, default=ss.seat_seed, key="seat_picker")
    chosen = clean_picks(picked if picked is not None else ss.seat_seed, free, count)
    ss.seat_pick = chosen

    for i, p in enumerate(ss.passengers):
        seat = chosen.get(str(i))
        if seat:
            d = seat_info(seat, f["class"])
            st.write(f"👤 **{p['name']}**: seat **{seat}** ({d['kind'].lower()}, {d['pitch']} in legroom)")
        else:
            st.write(f"👤 **{p['name']}**: no seat chosen yet")
    with st.expander("Compare the cabins"):
        st.markdown(
            "| Cabin | Legroom | Seat width | Recline |\n|---|---|---|---|\n"
            + "\n".join(f"| {n} | {p} in | {w} in | {r} in |" for n, (p, w, r) in BASE.items())
            + "\n\nExit rows and bulkhead rows add 4 to 6 inches of legroom.")

    if st.button("Continue to Payment", type="primary"):
        if len(chosen) < count:
            st.error("Choose a seat for every passenger first. "
                     "Tap a name above the seat map to switch passenger.")
        else:
            ss.seats = chosen
            for i, p in enumerate(ss.passengers):
                p["seat"] = chosen[str(i)]
            go("Payment")
    if st.button("Back to Passenger Details"):
        go("Passengers")

# ---------- Payment ----------
elif page == "Payment":
    progress("Payment")
    ss = st.session_state
    f, passengers = ss.flight, ss.passengers

    st.header("💳 Payment")
    st.write(f"**{f['airline']} ({f['number']})** · {ss.from_city} → {ss.to_city} · {ss.date}")

    st.subheader("Extras")
    extras = 0
    for i, p in enumerate(passengers):
        x, y = st.columns(2)
        meal = x.selectbox(f"{p['name']} — Meal", list(MEALS), key=f"meal_{i}")
        bag = y.checkbox(f"Extra 15 kg baggage (+₹{BAG_PRICE:,})", key=f"bag_{i}")
        p["meal"] = meal
        p["bag"] = bag
        extras += MEALS[meal] + (BAG_PRICE if bag else 0)

    promo = st.text_input("Promo code").strip().upper()
    base = f["price"] * len(passengers)
    discount = base * 0.10 if promo == "SKY10" else 0
    if promo and not discount:
        st.warning("That promo code is not valid.")
    elif discount:
        st.success("SKY10 applied: 10% off the base fare.")
    gst = (base + extras - discount) * 0.05
    total = base + extras - discount + gst

    st.divider()
    st.write(f"Base Fare: ₹{base:,.2f}")
    st.write(f"Extras: ₹{extras:,.2f}")
    if discount:
        st.write(f"Discount: -₹{discount:,.2f}")
    st.write(f"GST (5%): ₹{gst:,.2f}")
    st.subheader(f"Total: ₹{total:,.2f}")

    method = st.radio("Payment Method", ["Credit / Debit Card", "UPI"])
    if method == "Credit / Debit Card":
        card = st.text_input("Card Number (16 digits)")
        x, y = st.columns(2)
        x.text_input("Expiry Date (MM/YY)")
        cvv = y.text_input("CVV", type="password")
        valid = card.replace(" ", "").isdigit() and len(card.replace(" ", "")) == 16 \
            and cvv.isdigit() and len(cvv) == 3
        problem = "Enter a 16-digit card number and a 3-digit CVV."
    else:
        upi = st.text_input("UPI ID", placeholder="example@upi")
        valid = "@" in upi
        problem = "Enter a valid UPI ID, like name@upi."

    if st.button("← Back to Seats"):
        go("Seats")

    if st.button("Confirm Payment", type="primary"):
        if not valid:
            st.error(problem)
        else:
            booking = {
                "id": "SB" + str(random.randint(10000, 99999)),
                "airline": f["airline"], "flight": f["number"], "time": f["time"],
                "class": f["class"], "from": ss.from_city, "to": ss.to_city,
                "date": str(ss.date), "passengers": [p.copy() for p in passengers],
                "base": base, "extras": extras, "discount": discount,
                "gst": gst, "total": total, "method": method}
            ss.bookings.append(booking)
            ss.booking = booking
            ss.celebrate = True
            go("Ticket")

# ---------- Ticket ----------
elif page == "Ticket":
    b = st.session_state.booking
    if b is None:
        st.warning("No booking found.")
    else:
        progress("Ticket")
        if st.session_state.pop("celebrate", False):
            st.balloons()
        st.header("🎫 Booking Confirmed!")
        st.success(f"Booking ID: {b['id']} (simulated booking)")

        for p in b["passengers"]:
            st.markdown(boarding_pass(b, p), unsafe_allow_html=True)

        st.subheader("💰 Payment Summary")
        st.write(f"Base Fare: ₹{b['base']:,.2f}")
        st.write(f"Extras: ₹{b['extras']:,.2f}")
        if b["discount"]:
            st.write(f"Discount: -₹{b['discount']:,.2f}")
        st.write(f"GST: ₹{b['gst']:,.2f}")
        st.write(f"**Total: ₹{b['total']:,.2f}** · {b['method']}")

        ticket = (f"SKYBOOK FLIGHT TICKET\nBooking ID: {b['id']}\n"
                  f"Airline: {b['airline']}\nFlight: {b['flight']}\n"
                  f"From: {b['from']}\nTo: {b['to']}\nDate: {b['date']}\n"
                  f"Time: {b['time']}\nClass: {b['class']}\n\n")
        for i, p in enumerate(b["passengers"]):
            ticket += (f"Passenger {i + 1}: {p['name']}\nAge: {p['age']} | Type: {p['type']}\n"
                       f"Seat: {p['seat']}\nMeal: {p['meal']}\n"
                       f"Extra baggage: {'Yes' if p['bag'] else 'No'}\n"
                       f"Phone: {p['phone']}\nEmail: {p['email']}\n\n")
        ticket += (f"Base Fare: Rs. {b['base']:.2f}\nExtras: Rs. {b['extras']:.2f}\n"
                   f"Discount: Rs. {b['discount']:.2f}\nGST: Rs. {b['gst']:.2f}\n"
                   f"Total: Rs. {b['total']:.2f}\nPayment Method: {b['method']}\n"
                   "Simulated school project booking.")

        st.download_button("📥 Download Ticket", ticket,
                           file_name=f"SkyBook_{b['id']}.txt", mime="text/plain")
        if st.button("View My Bookings"):
            go("Bookings")
        if st.button("Back to Home"):
            go("Home")

# ---------- My Bookings ----------
elif page == "Bookings":
    st.header("📚 My Bookings")
    bookings = st.session_state.bookings
    if not bookings:
        st.info("You don't have any bookings yet. Search for a flight to get started.")
    else:
        st.metric("Total spent", f"₹{sum(b['total'] for b in bookings):,.2f}",
                  f"{len(bookings)} booking(s)")
        for b in reversed(list(bookings)):
            with st.expander(f"🎫 {b['id']} · {b['from']} → {b['to']} · {b['date']}"):
                st.write(f"{b['airline']} ({b['flight']}) · {b['time']} · {b['class']}")
                st.write(f"Total: ₹{b['total']:,.2f}")
                for p in b["passengers"]:
                    st.write(f"👤 {p['name']} — Seat {p['seat']}")
                if st.button("Cancel this booking", key="cancel_" + b["id"]):
                    bookings.remove(b)
                    st.rerun()

    if st.button("✈️ Book Another Flight", type="primary"):
        go("Search")
