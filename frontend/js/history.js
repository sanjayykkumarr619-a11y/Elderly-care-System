document.addEventListener("DOMContentLoaded", () => {
  CareCommon.renderSidebar("history");
  init();
  document.getElementById("apply-filters-btn").addEventListener("click", loadHistory);
  document.getElementById("clear-filters-btn").addEventListener("click", () => {
    document.getElementById("filter-date").value = "";
    document.getElementById("filter-medicine").value = "";
    document.getElementById("filter-status").value = "";
    loadHistory();
  });
});

async function init() {
  try {
    const medData = await Api.getMedicines();
    const select = document.getElementById("filter-medicine");
    select.innerHTML =
      `<option value="">All medicines</option>` +
      medData.medicines.map((m) => `<option value="${m.id}">${m.name}</option>`).join("");
  } catch (err) {
    CareCommon.errorToast(err);
  }
  loadHistory();
}

async function loadHistory() {
  const params = {};
  const date = document.getElementById("filter-date").value;
  const medicineId = document.getElementById("filter-medicine").value;
  const status = document.getElementById("filter-status").value;
  if (date) params.date = date;
  if (medicineId) params.medicine_id = medicineId;
  if (status) params.status = status;

  try {
    const data = await Api.getHistory(params);
    renderHistory(data.records);
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderHistory(records) {
  const body = document.getElementById("history-table-body");
  const empty = document.getElementById("history-empty");
  if (records.length === 0) {
    body.innerHTML = "";
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";
  body.innerHTML = records
    .map(
      (r) => `<tr>
        <td>${CareCommon.formatDateDisplay(r.scheduled_date)}</td>
        <td>${r.medicine_name}</td>
        <td>${CareCommon.formatTime12(r.scheduled_time)}</td>
        <td>${CareCommon.formatNumber(r.dosage)}</td>
        <td>${CareCommon.statusBadge(r.status)}</td>
        <td>${r.confirmed_at ? CareCommon.formatDateTimeDisplay(r.confirmed_at) : "-"}</td>
        <td>${r.stock_after !== null && r.stock_after !== undefined ? CareCommon.formatNumber(r.stock_after) : "-"}</td>
      </tr>`
    )
    .join("");
}
