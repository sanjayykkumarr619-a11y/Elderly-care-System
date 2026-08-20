document.addEventListener("DOMContentLoaded", () => {
  CareCommon.renderSidebar("dashboard");
  document.getElementById("today-date").textContent = new Date().toLocaleDateString(undefined, {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  });
  loadDashboard();
  window.addEventListener("medication-updated", loadDashboard);
  initAlarmControls();
});

function initAlarmControls() {
  const statusEl = document.getElementById("alarm-status-text");
  const enableBtn = document.getElementById("enable-alarm-btn");
  if (!statusEl || !enableBtn) return; // hidden for non-Patient roles

  function refreshStatus() {
    const enabled = AlarmAudio.isEnabled();
    statusEl.textContent = enabled ? "Enabled" : "Not enabled - click below";
    enableBtn.textContent = enabled ? "🔔 Alarm Enabled" : "🔔 Enable Medication Alarm";
  }

  refreshStatus();

  enableBtn.addEventListener("click", async () => {
    const result = await AlarmAudio.enable();
    if (result.ok) {
      CareCommon.toast("Medication alarm enabled for this browser.", "success");
    } else {
      CareCommon.toast(
        "Could not enable the alarm sound: " + (result.error && result.error.message ? result.error.message : "playback was blocked"),
        "error"
      );
    }
    refreshStatus();
  });
}

async function loadDashboard() {
  try {
    const [todayData, stockData, notifData] = await Promise.all([
      Api.getToday(),
      Api.getStock(),
      Api.getNotifications(),
    ]);
    renderStats(todayData.records, stockData.stock);
    renderTodayTable(todayData.records);
    renderLowStock(stockData.stock);
    renderRecentNotifications(notifData.notifications);
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderStats(records, stock) {
  const taken = records.filter((r) => r.status === "TAKEN").length;
  const missed = records.filter((r) => r.status === "MISSED").length;
  const pending = records.filter((r) => r.status === "PENDING").length;
  const lowStock = stock.filter((m) => m.stock_status === "LOW_STOCK").length;
  const totalStock = stock.reduce((sum, m) => sum + m.current_stock, 0);

  const nextDose = records
    .filter((r) => r.status === "PENDING")
    .sort((a, b) => a.scheduled_time.localeCompare(b.scheduled_time))[0];

  const tiles = [
    { label: "Total Medicines", value: stock.length, cls: "primary" },
    { label: "Current Stock", value: CareCommon.formatNumber(totalStock), cls: "primary" },
    { label: "Today's Doses", value: records.length, cls: "primary" },
    { label: "Taken", value: taken, cls: "success" },
    { label: "Missed", value: missed, cls: "danger" },
    { label: "Pending", value: pending, cls: "warning" },
    { label: "Low Stock Alerts", value: lowStock, cls: "danger" },
    { label: "Next Medication", value: nextDose ? `${CareCommon.formatTime12(nextDose.scheduled_time)} - ${nextDose.medicine_name}` : "None", cls: "primary" },
  ];

  document.getElementById("stat-tiles").innerHTML = tiles
    .map(
      (t) => `<div class="stat-tile ${t.cls}">
        <div class="stat-label">${t.label}</div>
        <div class="stat-value" style="${t.label === "Next Medication" ? "font-size:20px;" : ""}">${t.value}</div>
      </div>`
    )
    .join("");
}

function renderTodayTable(records) {
  const body = document.getElementById("today-table-body");
  const empty = document.getElementById("today-empty");
  if (records.length === 0) {
    body.innerHTML = "";
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";
  const sorted = [...records].sort((a, b) => a.scheduled_time.localeCompare(b.scheduled_time));
  body.innerHTML = sorted
    .map(
      (r) => `<tr>
        <td>${CareCommon.formatTime12(r.scheduled_time)}</td>
        <td>${r.medicine_name}</td>
        <td>${CareCommon.formatNumber(r.dosage)}</td>
        <td>${CareCommon.statusBadge(r.status)}</td>
        <td>${r.status === "PENDING"
          ? `<button class="btn-success btn-sm role-patient-only" onclick="confirmTaken(${r.id})">Mark Taken</button>`
          : `<span class="text-muted">-</span>`}
        </td>
      </tr>`
    )
    .join("");
}

async function confirmTaken(recordId) {
  try {
    await Api.markTaken(recordId);
    CareCommon.toast("Medication marked as taken.", "success");
    window.dispatchEvent(new CustomEvent("medication-updated"));
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderLowStock(stock) {
  const low = stock.filter((m) => m.stock_status === "LOW_STOCK");
  const el = document.getElementById("low-stock-list");
  if (low.length === 0) {
    el.innerHTML = `<div class="empty-state">No low stock alerts.</div>`;
    return;
  }
  el.innerHTML = low
    .map(
      (m) => `<div class="notification-item">
        <div>
          <div class="n-title">${m.name}</div>
          <div class="n-meta">${CareCommon.formatNumber(m.current_stock)} left - threshold ${CareCommon.formatNumber(m.low_stock_threshold)}</div>
        </div>
      </div>`
    )
    .join("");
}

function renderRecentNotifications(notifications) {
  const el = document.getElementById("recent-notifications");
  const recent = notifications.slice(0, 5);
  if (recent.length === 0) {
    el.innerHTML = `<div class="empty-state">No notifications yet.</div>`;
    return;
  }
  el.innerHTML = recent
    .map(
      (n) => `<div class="notification-item ${n.is_read ? "" : "unread"}">
        <div>
          <div class="n-title">${n.title}</div>
          <div class="n-meta">${n.message}</div>
          <div class="n-meta">${CareCommon.formatDateTimeDisplay(n.created_at)}</div>
        </div>
      </div>`
    )
    .join("");
}
