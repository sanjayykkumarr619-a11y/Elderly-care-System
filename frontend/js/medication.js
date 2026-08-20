let editingId = null;

document.addEventListener("DOMContentLoaded", () => {
  CareCommon.renderSidebar("medication");
  loadMedicines();

  document.getElementById("add-medicine-btn").addEventListener("click", () => openForm(null));
  document.getElementById("cancel-form-btn").addEventListener("click", closeForm);
  document.getElementById("medicine-form").addEventListener("submit", submitForm);
});

async function loadMedicines() {
  try {
    const data = await Api.getMedicines();
    renderMedicines(data.medicines);
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderMedicines(medicines) {
  const body = document.getElementById("medicine-table-body");
  const empty = document.getElementById("medicine-empty");
  if (medicines.length === 0) {
    body.innerHTML = "";
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";
  body.innerHTML = medicines
    .map(
      (m) => `<tr>
        <td>${m.name}</td>
        <td>${CareCommon.formatNumber(m.initial_stock)}</td>
        <td>${CareCommon.formatNumber(m.current_stock)}</td>
        <td>${CareCommon.formatNumber(m.low_stock_threshold)}</td>
        <td>${CareCommon.statusBadge(m.stock_status)}</td>
        <td>
          <div class="btn-row role-medication-write">
            <button class="btn-sm" onclick='openForm(${JSON.stringify(m)})'>Edit</button>
            <button class="btn-sm" onclick="location.href='stock.html'">Adjust Stock</button>
            <button class="btn-sm btn-danger" onclick="deleteMedicine(${m.id}, '${m.name.replace(/'/g, "\\'")}')">Delete</button>
          </div>
        </td>
      </tr>`
    )
    .join("");
}

function openForm(medicine) {
  editingId = medicine ? medicine.id : null;
  document.getElementById("form-title").textContent = medicine ? "Edit Medicine" : "Add Medicine";
  document.getElementById("medicine-id").value = medicine ? medicine.id : "";
  document.getElementById("med-name").value = medicine ? medicine.name : "";
  document.getElementById("med-threshold").value = medicine ? medicine.low_stock_threshold : 5;

  const stockField = document.getElementById("med-initial-stock");
  const stockLabel = document.getElementById("initial-stock-label");
  if (medicine) {
    stockField.value = medicine.initial_stock;
    stockField.disabled = true;
    stockLabel.textContent = "Initial Physical Quantity (set at creation)";
  } else {
    stockField.value = "";
    stockField.disabled = false;
    stockLabel.textContent = "Initial Physical Quantity";
  }

  document.getElementById("medicine-form-card").style.display = "block";
  document.getElementById("medicine-form-card").scrollIntoView({ behavior: "smooth" });
}

function closeForm() {
  document.getElementById("medicine-form-card").style.display = "none";
  editingId = null;
}

async function submitForm(e) {
  e.preventDefault();
  const name = document.getElementById("med-name").value.trim();
  const threshold = document.getElementById("med-threshold").value;

  try {
    if (editingId) {
      await Api.updateMedicine(editingId, {
        name,
        low_stock_threshold: threshold,
      });
      CareCommon.toast("Medicine updated.", "success");
    } else {
      const initialStock = document.getElementById("med-initial-stock").value;
      await Api.createMedicine({
        name,
        initial_stock: initialStock,
        low_stock_threshold: threshold,
      });
      CareCommon.toast("Medicine added.", "success");
    }
    closeForm();
    loadMedicines();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function deleteMedicine(id, name) {
  if (!confirm(`Delete "${name}"? This also removes its schedules and history.`)) return;
  try {
    await Api.deleteMedicine(id);
    CareCommon.toast("Medicine deleted.", "success");
    loadMedicines();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}
