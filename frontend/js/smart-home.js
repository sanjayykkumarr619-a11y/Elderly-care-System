document.addEventListener("DOMContentLoaded", () => {
  CareCommon.renderSidebar("smart-home");
  document.getElementById("add-device-btn").addEventListener("click", () => {
    document.getElementById("device-form-card").style.display = "block";
  });
  document.getElementById("cancel-device-btn").addEventListener("click", () => {
    document.getElementById("device-form-card").style.display = "none";
  });
  document.getElementById("device-form").addEventListener("submit", submitDevice);
});

document.addEventListener("auth-ready", (e) => {
  if (!["PATIENT", "FAMILY"].includes(e.detail.role)) {
    document.getElementById("smart-home-content").style.display = "none";
    document.getElementById("smart-home-no-access").style.display = "block";
    return;
  }
  loadDevices();
  loadSensors();
  loadRobot();
});

async function submitDevice(e) {
  e.preventDefault();
  const name = document.getElementById("d-name").value.trim();
  const device_type = document.getElementById("d-type").value;
  const location = document.getElementById("d-location").value.trim();
  try {
    await Api.createDevice({ name, device_type, location });
    document.getElementById("device-form-card").style.display = "none";
    document.getElementById("device-form").reset();
    CareCommon.toast("Device added.", "success");
    loadDevices();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function removeDevice(id) {
  if (!confirm("Remove this device?")) return;
  try {
    await Api.deleteDevice(id);
    loadDevices();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function loadDevices() {
  try {
    const data = await Api.getDevices();
    renderDevices(data.devices);
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderDevices(devices) {
  const grid = document.getElementById("device-grid");
  if (devices.length === 0) {
    grid.innerHTML = `<div class="empty-state">No devices configured.</div>`;
    return;
  }
  grid.innerHTML = devices
    .map((d) => {
      const isOn = d.state === "ON";
      return `<div class="device-tile">
        <div class="device-header">
          <div>
            <h3 style="margin:0 0 4px 0;">${d.name}</h3>
            <div class="text-muted">${d.location || ""}</div>
          </div>
          ${CareCommon.statusBadge(d.state)}
        </div>
        <div class="btn-row role-camera-control" style="margin-top:16px;">
          <button class="btn-success btn-block" ${isOn ? "disabled" : ""} onclick="sendCommand(${d.id}, 'ON')">ON</button>
          <button class="btn-danger btn-block" ${!isOn ? "disabled" : ""} onclick="sendCommand(${d.id}, 'OFF')">OFF</button>
        </div>
        <button class="btn-sm role-camera-control" style="margin-top:8px;width:100%;" onclick="removeDevice(${d.id})">Remove</button>
      </div>`;
    })
    .join("");
}

async function sendCommand(id, command) {
  try {
    await Api.sendDeviceCommand(id, command);
    loadDevices();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function loadSensors() {
  try {
    const data = await Api.getSensors();
    renderSensors(data.sensors);
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderSensors(sensors) {
  const grid = document.getElementById("sensor-grid");
  if (sensors.length === 0) {
    grid.innerHTML = `<div class="empty-state">No sensors configured.</div>`;
    return;
  }
  grid.innerHTML = sensors
    .map(
      (s) => `<div class="sensor-tile">
        <h3 style="margin:0 0 4px 0;">${s.name}</h3>
        <div class="text-muted">${s.location || ""}</div>
        <div style="margin-top:10px;font-size:22px;font-weight:700;">${s.last_value ?? "-"} ${s.unit || ""}</div>
        <div class="text-muted" style="font-size:13px;margin-top:4px;">Updated ${CareCommon.formatDateTimeDisplay(s.updated_at)}</div>
      </div>`
    )
    .join("");
}

async function loadRobot() {
  try {
    const data = await Api.getRobotStatus();
    updateRobotUI(data.robot);
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function updateRobotUI(robot) {
  const statusEl = document.getElementById("robot-status");
  statusEl.textContent = robot.status;
  statusEl.className = "badge " + (robot.status === "ALARM" ? "badge-missed" : robot.status === "IDLE" ? "badge-off" : "badge-on");
  document.getElementById("robot-event").textContent = robot.last_event || "No events yet.";
}

async function dispense() {
  try {
    const data = await Api.robotDispense({});
    updateRobotUI(data.robot);
    CareCommon.toast("Simulated dispense triggered.", "success");
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function alarm() {
  try {
    const data = await Api.robotAlarm();
    updateRobotUI(data.robot);
    CareCommon.toast("Alarm triggered.", "success");
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function stopRobot() {
  try {
    const data = await Api.robotStop();
    updateRobotUI(data.robot);
  } catch (err) {
    CareCommon.errorToast(err);
  }
}
