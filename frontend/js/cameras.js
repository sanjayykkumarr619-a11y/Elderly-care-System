document.addEventListener("DOMContentLoaded", () => {
  CareCommon.renderSidebar("cameras");
  document.getElementById("add-camera-btn").addEventListener("click", () => {
    document.getElementById("camera-form-card").style.display = "block";
  });
  document.getElementById("cancel-camera-btn").addEventListener("click", () => {
    document.getElementById("camera-form-card").style.display = "none";
  });
  document.getElementById("camera-form").addEventListener("submit", submitCamera);
});

document.addEventListener("auth-ready", (e) => {
  if (!["PATIENT", "FAMILY"].includes(e.detail.role)) {
    document.getElementById("camera-content").style.display = "none";
    document.getElementById("camera-no-access").style.display = "block";
    return;
  }
  loadCameras();
});

async function loadCameras() {
  try {
    const data = await Api.getCameras();
    renderCameras(data.cameras);
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderCameras(cameras) {
  const grid = document.getElementById("camera-grid");
  const empty = document.getElementById("camera-empty");
  if (cameras.length === 0) {
    grid.innerHTML = "";
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";
  grid.innerHTML = cameras
    .map((c) => {
      const isLive = c.status === "STREAMING";
      return `<div class="camera-tile">
        <div class="device-header">
          <div>
            <h3 style="margin:0 0 4px 0;">${c.name}</h3>
            <div class="text-muted">${c.location || ""}</div>
          </div>
          ${CareCommon.statusBadge(c.status)}
        </div>
        <div class="camera-feed ${isLive ? "" : "offline"}">
          ${isLive ? "● Simulated live feed" : "Camera offline"}
        </div>
        <div class="btn-row role-camera-control" style="margin-top:14px;">
          ${isLive
            ? `<button class="btn-sm btn-danger" onclick="disconnect(${c.id})">Stop Stream</button>`
            : `<button class="btn-sm btn-success" onclick="connect(${c.id})">Start Stream</button>`}
          <button class="btn-sm" onclick="removeCamera(${c.id})">Remove</button>
        </div>
      </div>`;
    })
    .join("");
}

async function connect(id) {
  try {
    await Api.connectCamera(id);
    loadCameras();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function disconnect(id) {
  try {
    await Api.disconnectCamera(id);
    loadCameras();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function removeCamera(id) {
  if (!confirm("Remove this camera?")) return;
  try {
    await Api.deleteCamera(id);
    loadCameras();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function submitCamera(e) {
  e.preventDefault();
  const name = document.getElementById("cam-name").value.trim();
  const location = document.getElementById("cam-location").value.trim();
  try {
    await Api.createCamera({ name, location });
    document.getElementById("camera-form-card").style.display = "none";
    document.getElementById("camera-form").reset();
    loadCameras();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}
