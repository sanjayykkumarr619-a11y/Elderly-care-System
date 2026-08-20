document.addEventListener("DOMContentLoaded", () => {
  CareCommon.renderSidebar("notifications");
  loadNotifications();
  document.getElementById("refresh-btn").addEventListener("click", loadNotifications);
});

async function loadNotifications() {
  try {
    const data = await Api.getNotifications();
    renderNotifications(data.notifications);
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderNotifications(notifications) {
  const list = document.getElementById("notification-list");
  const empty = document.getElementById("notification-empty");
  if (notifications.length === 0) {
    list.innerHTML = "";
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";
  list.innerHTML = notifications
    .map(
      (n) => `<div class="notification-item ${n.is_read ? "" : "unread"}">
        <div style="flex:1;">
          <div class="n-title">${n.title} <span class="text-muted" style="font-weight:400;">(${n.type})</span></div>
          <div class="n-meta">${n.message}</div>
          <div class="n-meta">${CareCommon.formatDateTimeDisplay(n.created_at)} - for ${n.recipient_type}</div>
          ${emailStatusLine(n)}
        </div>
        ${n.is_read ? "" : `<button class="btn-sm" onclick="markRead(${n.id})">Mark Read</button>`}
      </div>`
    )
    .join("");
}

function emailStatusLine(n) {
  if (!n.email_to) return "";
  const labels = { SENT: "Emailed", FAILED: "Email failed", SKIPPED: "Not emailed (no caregiver address)" };
  const label = labels[n.email_status] || n.email_status;
  const cls = n.email_status === "SENT" ? "badge-normal" : n.email_status === "FAILED" ? "badge-low" : "badge-pending";
  return `<div class="n-meta"><span class="badge ${cls}" style="font-size:11px;">${label}</span> ${CareCommon.escapeHtml(n.email_to)}</div>`;
}

async function markRead(id) {
  try {
    await Api.markNotificationRead(id);
    loadNotifications();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}
