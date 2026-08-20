document.addEventListener("DOMContentLoaded", () => {
  CareCommon.renderSidebar("stock");
  loadStock();
  document.getElementById("cancel-stock-btn").addEventListener("click", closeAddStock);
  document.getElementById("add-stock-form").addEventListener("submit", submitAddStock);
});

async function loadStock() {
  try {
    const data = await Api.getStock();
    renderStock(data.stock);
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderStock(stock) {
  const body = document.getElementById("stock-table-body");
  const empty = document.getElementById("stock-empty");
  if (stock.length === 0) {
    body.innerHTML = "";
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";
  body.innerHTML = stock
    .map(
      (m) => `<tr>
        <td data-label="Medicine"><strong style="font-size:16px;color:var(--color-primary-dark);">${CareCommon.escapeHtml(m.name)}</strong></td>
        <td data-label="Current Stock"><strong style="${m.stock_status === 'LOW_STOCK' ? 'color:var(--color-danger);font-size:18px;' : 'font-size:18px;'}">${CareCommon.formatNumber(m.current_stock)}</strong></td>
        <td data-label="Threshold">${CareCommon.formatNumber(m.low_stock_threshold)}</td>
        <td data-label="Status">${CareCommon.statusBadge(m.stock_status)}</td>
        <td data-label="Action"><button class="btn-sm btn-primary role-patient-only" onclick='openAddStock(${JSON.stringify({ id: m.id, name: m.name })})'>+ Add Stock</button></td>
      </tr>`
    )
    .join("");
}

function openAddStock(medicine) {
  document.getElementById("stock-medicine-id").value = medicine.id;
  document.getElementById("add-stock-title").textContent = `Add Stock - ${medicine.name}`;
  document.getElementById("stock-amount").value = "";
  document.getElementById("add-stock-card").style.display = "block";
  document.getElementById("add-stock-card").scrollIntoView({ behavior: "smooth" });
}

function closeAddStock() {
  document.getElementById("add-stock-card").style.display = "none";
}

async function submitAddStock(e) {
  e.preventDefault();
  const medicineId = document.getElementById("stock-medicine-id").value;
  const amount = document.getElementById("stock-amount").value;
  try {
    const result = await Api.addStock(medicineId, amount);
    CareCommon.toast(`Stock updated. New stock: ${CareCommon.formatNumber(result.medicine.current_stock)}.`, "success");
    closeAddStock();
    loadStock();
    window.dispatchEvent(new CustomEvent("medication-updated"));
  } catch (err) {
    CareCommon.errorToast(err);
  }
}
