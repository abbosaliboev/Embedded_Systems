/* ── Smart Safety Guard — Dashboard JS ──────────────────────────────────── */

const ALERT_LABELS = {
  MOTION:          "Motion Detected",
  GAS:             "Gas / Smoke",
  PROXIMITY:       "Proximity Breach",
  OVERHEAT:        "Overheating",
  PERSON_DETECTED: "Person in Danger Zone",
};

// ── Clock ────────────────────────────────────────────────────────────────────

function tickClock() {
  document.getElementById("clock").textContent =
    new Date().toLocaleTimeString("en-US", { hour12: false });
}
tickClock();
setInterval(tickClock, 1000);

// ── Charts ───────────────────────────────────────────────────────────────────

const CHART_GRID = "#0f2d18";

const tempChart = new Chart(
  document.getElementById("temp-chart").getContext("2d"),
  {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Temp (°C)",
          data: [],
          borderColor: "#ff1744",
          backgroundColor: "rgba(248,113,113,0.07)",
          tension: 0.3,
          pointRadius: 2,
          yAxisID: "y",
        },
        {
          label: "Humidity (%)",
          data: [],
          borderColor: "#00b0ff",
          backgroundColor: "rgba(56,189,248,0.07)",
          tension: 0.3,
          pointRadius: 2,
          yAxisID: "y1",
        },
      ],
    },
    options: chartOpts("left", "#ff1744", "right", "#00b0ff"),
  }
);

const distChart = new Chart(
  document.getElementById("dist-chart").getContext("2d"),
  {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Distance (cm)",
          data: [],
          borderColor: "#00e676",
          backgroundColor: "rgba(74,222,128,0.07)",
          tension: 0.3,
          pointRadius: 2,
        },
      ],
    },
    options: chartOpts("left", "#00e676"),
  }
);

function chartOpts(pos1, col1, pos2, col2) {
  const scales = {
    x:  { ticks: { color: "#1a4025", maxTicksLimit: 8, font: { size: 10 } }, grid: { color: CHART_GRID } },
    y:  { position: pos1, ticks: { color: col1, font: { size: 10 } }, grid: { color: CHART_GRID } },
  };
  if (pos2) {
    scales.y1 = { position: pos2, ticks: { color: col2, font: { size: 10 } }, grid: { drawOnChartArea: false } };
  }
  return {
    responsive: true,
    interaction: { mode: "index", intersect: false },
    plugins: { legend: { labels: { color: "#3d7a52", font: { size: 11 } } } },
    scales,
  };
}

function pushChart(chart, label, ...values) {
  const MAX = 60;
  chart.data.labels.push(label);
  values.forEach((v, i) => chart.data.datasets[i].data.push(v ?? null));
  if (chart.data.labels.length > MAX) {
    chart.data.labels.shift();
    chart.data.datasets.forEach(ds => ds.data.shift());
  }
  chart.update("none");
}

// ── Load initial history ─────────────────────────────────────────────────────

fetch("/api/history")
  .then(r => r.json())
  .then(rows => {
    rows.reverse().forEach(row => {
      const ts = row.timestamp ? row.timestamp.slice(11, 19) : "";
      pushChart(tempChart, ts, row.temp, row.humidity);
      pushChart(distChart, ts, row.distance);
    });
  });

fetch("/api/events").then(r => r.json()).then(renderEvents);
fetch("/api/latest_analysis").then(r => r.json()).then(renderAIAnalysis);

// ── SSE live updates ─────────────────────────────────────────────────────────

const evtSource = new EventSource("/stream");

evtSource.onmessage = (e) => {
  const data = JSON.parse(e.data);

  if (data.ai_analysis) {
    renderAIAnalysis(data.ai_analysis);
    return;
  }

  const ts = new Date().toLocaleTimeString("en-US", { hour12: false });
  updateSensorCards(data); updateBars(data);
  updateActuators(data);
  updateAlertBanner(data.alerts || []);
  pushChart(tempChart, ts, data.temp, data.humidity);
  pushChart(distChart, ts, data.distance);
  document.getElementById("last-ts").textContent = ts;
};

evtSource.onerror = () => {
  const b = document.getElementById("status-badge");
  b.textContent = "OFFLINE";
  b.className = "badge offline";
};

// ── Refresh event log every 10s ──────────────────────────────────────────────

setInterval(() => {
  fetch("/api/events").then(r => r.json()).then(renderEvents);
}, 10_000);

// ── Camera frame refresh ─────────────────────────────────────────────────────

let _cameraAvailable = false;

function refreshCamera() {
  fetch("/api/frame_info")
    .then(r => r.json())
    .then(info => {
      const offline = document.getElementById("cam-offline");
      const img = document.getElementById("cam-img");
      const ts = document.getElementById("cam-ts");
      const conf = document.getElementById("cam-conf");

      if (info.available) {
        if (!_cameraAvailable) {
          _cameraAvailable = true;
          offline.classList.add("hidden");
        }
        img.src = "/api/latest_frame?t=" + Date.now();
        ts.textContent = info.timestamp || "Live";

        const v = info.vision || {};
        if (v.person_detected) {
          conf.textContent = `Person ${(v.confidence * 100).toFixed(0)}% conf` +
                             (v.in_danger_zone ? " ⚠️ IN ZONE" : "");
          conf.style.color = v.in_danger_zone ? "#ff1744" : "#00e676";
        } else {
          conf.textContent = "";
        }

        // Update YOLO sensor card from frame_info
        setCard("person",
          v.person_detected ? "YES" : "NO",
          !!v.in_danger_zone
        );
        if (v.person_detected) {
          document.getElementById("val-conf").textContent =
            `${(v.confidence * 100).toFixed(0)}% conf`;
        }
      } else {
        _cameraAvailable = false;
        offline.classList.remove("hidden");
        ts.textContent = "No frame received";
        conf.textContent = "";
      }
    })
    .catch(() => {});
}

refreshCamera();
setInterval(refreshCamera, 500);

// ── Poll AI analysis every 5s ────────────────────────────────────────────────

let _lastAITimestamp = "";

setInterval(() => {
  fetch("/api/latest_analysis")
    .then(r => r.json())
    .then(result => {
      if (result && result.timestamp && result.timestamp !== _lastAITimestamp) {
        renderAIAnalysis(result);
      }
    });
}, 5_000);

// ── AI Analyze button ────────────────────────────────────────────────────────

function analyze() {
  const btn = document.getElementById("analyze-btn");
  btn.textContent = "⏳ Analyzing...";
  btn.disabled = true;
  fetch("/api/analyze", { method: "POST" })
    .then(r => r.json())
    .then(() => { setTimeout(() => { btn.textContent = "🤖 Analyze Now"; btn.disabled = false; }, 8000); })
    .catch(() => { btn.textContent = "🤖 Analyze Now"; btn.disabled = false; });
}

// ── Sensor card updates ──────────────────────────────────────────────────────

function updateSensorCards(d) {
  setCard("distance", d.distance != null ? d.distance : "—",
          d.distance != null && d.distance < 50);
  setCard("gas",      d.gas != null ? (d.gas ? "YES" : "NO") : "—", !!d.gas);
  setCard("temp",     d.temp != null ? d.temp : "—",
          d.temp != null && d.temp > 40);
  setCard("humidity", d.humidity != null ? d.humidity : "—", false);
  setCard("pir",      d.pir != null ? (d.pir ? "YES" : "NO") : "—", !!d.pir);

  const hasAlert = !!d.gas
    || (d.distance != null && d.distance < 50)
    || (d.temp != null && d.temp > 40)
    || !!d.pir
    || (d.alerts && d.alerts.includes("PERSON_DETECTED"));

  const badge = document.getElementById("status-badge");
  badge.textContent = hasAlert ? "DANGER" : "SAFE";
  badge.className   = "badge " + (hasAlert ? "danger" : "safe");
}

function setCard(id, value, isAlert) {
  const card = document.getElementById("card-" + id);
  const val  = document.getElementById("val-" + id);
  if (!card || !val) return;
  val.textContent = value;
  card.classList.toggle("alert", !!isAlert);
  card.classList.toggle("ok",    !isAlert);
  // support both .card and .scard class names
  card.classList.toggle("alert", !!isAlert);
}

// ── Actuator status ──────────────────────────────────────────────────────────

function updateActuators(d) {
  setActuator("led",    d.led_on);
  setActuator("buzzer", d.buzzer_on);
  setActuator("fan",    d.fan_on);
}

function setActuator(name, on) {
  const card  = document.getElementById("act-" + name);
  const ind   = document.getElementById("ind-" + name);
  const state = document.getElementById("state-" + name);
  if (!card) return;
  card.classList.toggle("act-on",  !!on);
  card.classList.toggle("act-off", !on);
  ind.classList.toggle("ind-on",   !!on);
  ind.classList.toggle("ind-off",  !on);
  state.textContent = on ? "ON" : "OFF";
}

// ── Alert banner ─────────────────────────────────────────────────────────────

function updateAlertBanner(alerts) {
  const banner = document.getElementById("alert-banner");
  const list   = document.getElementById("alert-list");
  if (!alerts.length) { banner.classList.add("hidden"); return; }
  banner.classList.remove("hidden");
  list.textContent = " " + alerts.map(a => ALERT_LABELS[a] || a).join(" · ");
}

// ── Manual controls ──────────────────────────────────────────────────────────

function control(action) {
  fetch("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  }).catch(console.error);
}

// ── Event log ────────────────────────────────────────────────────────────────

function renderEvents(events) {
  const container = document.getElementById("event-log");
  if (!events.length) {
    container.innerHTML = '<p class="elog-empty">No events yet.</p>';
    return;
  }
  container.innerHTML = events.map(ev => `
    <div class="elog-item">
      <span class="elog-time">${ev.timestamp || ""}</span>
      <span class="elog-type ${ev.event_type}">${ev.event_type}</span>
      <span class="elog-det">${ev.details || ""}</span>
    </div>
  `).join("");
}

// ── AI Analysis panel ────────────────────────────────────────────────────────

function renderAIAnalysis(result) {
  if (!result || !result.threat_level) return;

  _lastAITimestamp = result.timestamp || "";

  document.getElementById("ai-empty").classList.add("hidden");
  const panel = document.getElementById("ai-result");
  panel.classList.remove("hidden");

  const threat = document.getElementById("ai-threat");
  threat.textContent = result.threat_level || "—";
  threat.className = "threat-badge threat-" + (result.threat_level || "LOW");

  document.getElementById("ai-scene").textContent   = result.scene_description || result.scene_desc || "—";
  document.getElementById("ai-action").textContent  = result.immediate_action   || result.action     || "—";
  document.getElementById("ai-summary").textContent = result.incident_summary   || result.summary    || "—";
  document.getElementById("ai-time").textContent    = result.timestamp || "";
}

function updateBars(d) {
  var b, pct;
  b = document.getElementById("fill-distance");
  if (b) b.style.width = (d.distance != null ? Math.min(100, (d.distance / 200) * 100) : 0) + "%";
  b = document.getElementById("fill-gas");
  if (b) b.style.width = (d.gas ? 100 : 0) + "%";
  b = document.getElementById("fill-temp");
  if (b) b.style.width = (d.temp != null ? Math.min(100, ((d.temp - 10) / 40) * 100) : 0) + "%";
  b = document.getElementById("fill-humidity");
  if (b) b.style.width = (d.humidity != null ? Math.min(100, d.humidity) : 0) + "%";
  var ac = document.getElementById("alert-count");
  if (ac) ac.textContent = (d.alerts || []).length + " ALERTS";
}
