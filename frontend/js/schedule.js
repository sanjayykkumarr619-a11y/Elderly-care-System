let medicinesCache = [];

document.addEventListener("DOMContentLoaded", () => {
  CareCommon.renderSidebar("schedule");
  init();

  document.getElementById("add-schedule-btn").addEventListener("click", openForm);
  document.getElementById("cancel-form-btn").addEventListener("click", closeForm);
  document.getElementById("schedule-form").addEventListener("submit", submitForm);
});

async function init() {
  try {
    const medData = await Api.getMedicines();
    medicinesCache = medData.medicines;
    const select = document.getElementById("sch-medicine");
    if (medicinesCache.length === 0) {
      select.innerHTML = `<option value="">No medicines yet - add one first</option>`;
    } else {
      select.innerHTML = medicinesCache
        .map((m) => `<option value="${m.id}">${CareCommon.escapeHtml(m.name)}</option>`)
        .join("");
    }
    loadSchedules();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function loadSchedules() {
  try {
    const data = await Api.getSchedules();
    renderSchedules(data.schedules);
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderSchedules(schedules) {
  const body = document.getElementById("schedule-table-body");
  const empty = document.getElementById("schedule-empty");
  if (schedules.length === 0) {
    body.innerHTML = "";
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";
  const sorted = [...schedules].sort((a, b) => a.scheduled_time.localeCompare(b.scheduled_time));
  body.innerHTML = sorted
    .map(
      (s) => `<tr>
        <td data-label="Time"><strong style="font-size:15px;color:var(--color-primary);">${CareCommon.formatTime12(s.scheduled_time)}</strong></td>
        <td data-label="Medicine"><strong style="color:var(--color-text);">${CareCommon.escapeHtml(s.medicine_name)}</strong></td>
        <td data-label="Dosage">${CareCommon.formatNumber(s.dosage)} dose</td>
        <td data-label="Status">${s.active ? '<span class="badge badge-on">ACTIVE</span>' : '<span class="badge badge-off">DISABLED</span>'}</td>
        <td data-label="Actions">
          <div class="btn-row role-medication-write">
            <button class="btn-sm" onclick="toggleActive(${s.id}, ${!s.active})">${s.active ? "Disable" : "Enable"}</button>
            <button class="btn-sm btn-danger" onclick="deleteSchedule(${s.id})">Delete</button>
          </div>
        </td>
      </tr>`
    )
    .join("");
}

function openForm() {
  if (medicinesCache.length === 0) {
    CareCommon.toast("Add a medicine first before creating a schedule.", "error");
    return;
  }
  document.getElementById("sch-medicine").value = medicinesCache[0].id;
  document.getElementById("sch-time").value = "08:00";
  document.getElementById("sch-dosage").value = 1;
  document.getElementById("sch-active").checked = true;

  document.getElementById("schedule-form-card").style.display = "block";
  document.getElementById("schedule-form-card").scrollIntoView({ behavior: "smooth" });
}

function closeForm() {
  document.getElementById("schedule-form-card").style.display = "none";
}

async function submitForm(e) {
  e.preventDefault();
  const payload = {
    medicine_id: parseInt(document.getElementById("sch-medicine").value, 10),
    scheduled_time: document.getElementById("sch-time").value,
    dosage: document.getElementById("sch-dosage").value,
    active: document.getElementById("sch-active").checked,
  };
  try {
    await Api.createSchedule(payload);
    CareCommon.toast("Schedule created.", "success");
    closeForm();
    loadSchedules();
    window.dispatchEvent(new CustomEvent("medication-updated"));
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function toggleActive(id, newActive) {
  try {
    await Api.updateSchedule(id, { active: newActive });
    loadSchedules();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function deleteSchedule(id) {
  if (!confirm("Delete this schedule?")) return;
  try {
    await Api.deleteSchedule(id);
    CareCommon.toast("Schedule deleted.", "success");
    loadSchedules();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}
