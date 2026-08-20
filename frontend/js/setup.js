let addedMedicines = [];

document.addEventListener("auth-ready", () => {
  loadExisting();
});

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("medicine-form").addEventListener("submit", addMedicine);
  document.getElementById("schedule-form").addEventListener("submit", addSchedule);
  document.getElementById("camera-form").addEventListener("submit", addCamera);
  document.getElementById("device-form").addEventListener("submit", addDevice);

  document.getElementById("step1-next").addEventListener("click", () => goToStep(2));
  document.getElementById("step2-back").addEventListener("click", () => goToStep(1));
  document.getElementById("step2-next").addEventListener("click", () => goToStep(3));
  document.getElementById("step3-back").addEventListener("click", () => goToStep(2));
  document.getElementById("step3-next").addEventListener("click", () => goToStep(4));
  document.getElementById("step4-back").addEventListener("click", () => goToStep(3));
  document.getElementById("finish-setup").addEventListener("click", finishSetup);
});

// If the user already added things (e.g. came back after a refresh
// mid-setup), reflect that instead of starting from a blank slate. Only
// applies if nothing has been added *this* page load yet - otherwise this
// fetch (started at page load) could resolve after a fast user has
// already added a medicine and wipe that out from under them.
async function loadExisting() {
  if (addedMedicines.length > 0) return;
  try {
    const [medData, schedData, camData, devData] = await Promise.all([
      Api.getMedicines(), Api.getSchedules(), Api.getCameras(), Api.getDevices(),
    ]);
    if (addedMedicines.length > 0) return; // lost the race - don't clobber
    addedMedicines = medData.medicines;
    renderMedicineList(medData.medicines);
    renderScheduleList(schedData.schedules);
    renderCameraList(camData.cameras);
    renderDeviceList(devData.devices);
    populateMedicineSelect();
    document.getElementById("step1-next").disabled = addedMedicines.length === 0;
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function goToStep(n) {
  for (let i = 1; i <= 4; i++) {
    document.getElementById(`step-${i}`).style.display = i === n ? "block" : "none";
    document.querySelector(`.setup-step-dot[data-step="${i}"]`).classList.toggle("active", i === n);
    document.querySelector(`.setup-step-dot[data-step="${i}"]`).classList.toggle("done", i < n);
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function addMedicine(e) {
  e.preventDefault();
  const name = document.getElementById("m-name").value.trim();
  const initial_stock = document.getElementById("m-stock").value;
  const low_stock_threshold = document.getElementById("m-threshold").value;
  try {
    const res = await Api.createMedicine({ name, initial_stock, low_stock_threshold });
    addedMedicines.push(res.medicine);
    renderMedicineList(addedMedicines);
    populateMedicineSelect();
    document.getElementById("medicine-form").reset();
    document.getElementById("m-threshold").value = 5;
    document.getElementById("step1-next").disabled = false;
    CareCommon.toast("Medicine added.", "success");
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderMedicineList(medicines) {
  document.getElementById("medicine-list").innerHTML = medicines
    .map(
      (m) => `<div class="setup-list-item">
        <div><strong>${CareCommon.escapeHtml(m.name)}</strong> - ${CareCommon.formatNumber(m.current_stock)} in stock, threshold ${CareCommon.formatNumber(m.low_stock_threshold)}</div>
      </div>`
    )
    .join("") || `<div class="text-muted">No medicines added yet.</div>`;
}

function populateMedicineSelect() {
  const select = document.getElementById("s-medicine");
  select.innerHTML = addedMedicines.map((m) => `<option value="${m.id}">${CareCommon.escapeHtml(m.name)}</option>`).join("");
}

async function addSchedule(e) {
  e.preventDefault();
  const medicine_id = parseInt(document.getElementById("s-medicine").value, 10);
  const scheduled_time = document.getElementById("s-time").value;
  const dosage = document.getElementById("s-dosage").value;
  if (!medicine_id) {
    CareCommon.toast("Add a medicine first.", "error");
    return;
  }
  try {
    await Api.createSchedule({ medicine_id, scheduled_time, dosage });
    const data = await Api.getSchedules();
    renderScheduleList(data.schedules);
    CareCommon.toast("Schedule added.", "success");
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderScheduleList(schedules) {
  document.getElementById("schedule-list").innerHTML = schedules
    .map(
      (s) => `<div class="setup-list-item">
        <div>${CareCommon.formatTime12(s.scheduled_time)} - <strong>${CareCommon.escapeHtml(s.medicine_name)}</strong> (${CareCommon.formatNumber(s.dosage)})</div>
      </div>`
    )
    .join("") || `<div class="text-muted">No schedules added yet.</div>`;
}

async function addCamera(e) {
  e.preventDefault();
  const name = document.getElementById("c-name").value.trim();
  const location = document.getElementById("c-location").value.trim();
  try {
    await Api.createCamera({ name, location });
    const data = await Api.getCameras();
    renderCameraList(data.cameras);
    document.getElementById("camera-form").reset();
    CareCommon.toast("Camera added.", "success");
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderCameraList(cameras) {
  document.getElementById("camera-list").innerHTML = cameras
    .map((c) => `<div class="setup-list-item"><div><strong>${CareCommon.escapeHtml(c.name)}</strong> - ${CareCommon.escapeHtml(c.location || "")}</div></div>`)
    .join("") || `<div class="text-muted">No cameras added yet.</div>`;
}

async function addDevice(e) {
  e.preventDefault();
  const name = document.getElementById("d-name").value.trim();
  const device_type = document.getElementById("d-type").value;
  const location = document.getElementById("d-location").value.trim();
  try {
    await Api.createDevice({ name, device_type, location });
    const data = await Api.getDevices();
    renderDeviceList(data.devices);
    document.getElementById("device-form").reset();
    CareCommon.toast("Device added.", "success");
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderDeviceList(devices) {
  document.getElementById("device-list").innerHTML = devices
    .map((d) => `<div class="setup-list-item"><div><strong>${CareCommon.escapeHtml(d.name)}</strong> - ${CareCommon.escapeHtml(d.location || "")}</div></div>`)
    .join("") || `<div class="text-muted">No devices added yet.</div>`;
}

async function finishSetup() {
  try {
    await Api.updateMe({ setup_completed: true });
    CareCommon.toast("Setup complete!", "success");
    location.href = "index.html";
  } catch (err) {
    CareCommon.errorToast(err);
  }
}
