// Dashboard — connects to the SSE /stream endpoint for live updates
// and renders a Chart.js temperature history graph.

const ALERT_LABELS = {
  MOTION:    "Motion Detected",
  GAS:       "Gas / Smoke",
  PROXIMITY: "Proximity Breach",
  OVERHEAT:  "Overheating",
};

// ---- Chart setup ----
const chartCtx = document.getElementById("temp-chart").getContext("2d");
const tempHistory = { labels: [], temps: [], humidities: [] };

const tempChart = new Chart(chartCtx, {
  type: "line",
  data: {
    labels: tempHistory.labels,
    datasets: [
      {
        label: "Temperature (°C)",
        data: tempHistory.temps,
        borderColor: "#fc8181",
        backgroundColor: "rgba(252,129,129,0.08)",
        tension: 0.3,
        pointRadius: 2,
        yAxisID: "y",
      },
      {
        label: "Humidity (%)",
        data: tempHistory.humidities,
        borderColor: "#63b3ed",
        backgroundColor: "rgba(99,179,237,0.08)",
        tension: 0.3,
        pointRadius: 2,
        yAxisID: "y1",
      },
    ],
  },
  options: {
    responsive: true,
    interaction: { mode: "index", intersect: false },
    plugins: { legend: { labels: { color: "#a0aec0", font: { size: 11 } } } },
    scales: {
      x:  { ticks: { color: "#4a5568", maxTicksLimit: 8, font: { size: 10 } }, grid: { color: "#2d3748" } },
      y:  { position: "left",  ticks: { color: "#fc8181", font: { size: 10 } }, grid: { color: "#2d3748" } },
      y1: { position: "right", ticks: { color: "#63b3ed", font: { size: 10 } }, grid: { drawOnChartArea: false } },
    },
  },
});

// ---- Load initial history from REST API ----
fetch("/api/history")
  .then(r => r.json())
  .then(rows => {
    // rows are newest-first; reverse for chronological display
    rows.reverse().forEach(row => pushToChart(row.timestamp, row.temp, row.humidity));
    tempChart.update("none");
  })
  .catch(console.error);

fetch("/api/events")
  .then(r => r.json())
  .then(events => {
    if (events.length) renderEvents(events);
  })
  .catch(console.error);

// ---- SSE live updates ----
const evtSource = new EventSource("/stream");

evtSource.onmessage = (e) => {
  const data = JSON.parse(e.data);
  updateCards(data);
  updateAlertBanner(data.alerts || []);
  pushToChart(new Date().toLocaleTimeString(), data.temp, data.humidity);
  tempChart.update("none");
  document.getElementById("last-ts").textContent = new Date().toLocaleTimeString();
};

evtSource.onerror = () => {
  document.getElementById("status-badge").textContent = "OFFLINE";
  document.getElementById("status-badge").className = "badge warning";
};

// ---- SSE event log updates (poll every 10s — avoids a second stream) ----
setInterval(() => {
  fetch("/api/events?limit=50")
    .then(r => r.json())
    .then(renderEvents)
    .catch(console.error);
}, 10_000);

// ---- Helpers ----

function updateCards(d) {
  setCard("pir",      d.pir ? "YES" : "NO",         d.pir);
  setCard("gas",      d.gas ? "YES" : "NO",          d.gas);
  setCard("distance", d.distance != null ? d.distance : "—", d.distance != null && d.distance < 50);
  setCard("temp",     d.temp     != null ? d.temp     : "—", d.temp != null && d.temp > 40);
  setCard("humidity", d.humidity != null ? d.humidity : "—", false);

  const hasAlert = d.pir || d.gas ||
    (d.distance != null && d.distance < 50) ||
    (d.temp     != null && d.temp     > 40);

  const badge = document.getElementById("status-badge");
  if (hasAlert) {
    badge.textContent = "DANGER";
    badge.className = "badge danger";
  } else {
    badge.textContent = "SAFE";
    badge.className = "badge safe";
  }
}

function setCard(id, value, isAlert) {
  const card = document.getElementById("card-" + id);
  const val  = document.getElementById("val-"  + id);
  if (!card || !val) return;
  val.textContent = value;
  card.classList.toggle("alert", !!isAlert);
  card.classList.toggle("ok",    !isAlert);
}

function updateAlertBanner(alerts) {
  const banner = document.getElementById("alert-banner");
  const list   = document.getElementById("alert-list");
  if (!alerts.length) {
    banner.classList.add("hidden");
    return;
  }
  banner.classList.remove("hidden");
  list.textContent = " " + alerts.map(a => ALERT_LABELS[a] || a).join(" · ");
}

function pushToChart(label, temp, humidity) {
  const MAX = 60;
  tempHistory.labels.push(label);
  tempHistory.temps.push(temp ?? null);
  tempHistory.humidities.push(humidity ?? null);
  if (tempHistory.labels.length > MAX) {
    tempHistory.labels.shift();
    tempHistory.temps.shift();
    tempHistory.humidities.shift();
  }
}

function renderEvents(events) {
  const container = document.getElementById("event-log");
  if (!events.length) {
    container.innerHTML = '<p class="no-events">No events yet.</p>';
    return;
  }
  container.innerHTML = events.map(ev => `
    <div class="event-item">
      <span class="event-time">${ev.timestamp}</span>
      <span class="event-type ${ev.event_type}">${ev.event_type}</span>
      <span class="event-details">${ev.details || ""}</span>
    </div>
  `).join("");
}
