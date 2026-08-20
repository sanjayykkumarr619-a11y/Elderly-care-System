document.addEventListener("DOMContentLoaded", () => {
  CareCommon.renderSidebar("settings");

  const permEl = document.getElementById("perm-status");
  function refreshPerm() {
    permEl.textContent = "Notification" in window ? Notification.permission : "unsupported";
  }
  refreshPerm();
  document.getElementById("request-perm-btn").addEventListener("click", async () => {
    if (!("Notification" in window)) {
      CareCommon.toast("Browser notifications are not supported here. In-app alerts will still work.", "error");
      return;
    }
    await Notification.requestPermission();
    refreshPerm();
  });

  document.getElementById("add-caregiver-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("new-caregiver-name").value.trim();
    const email = document.getElementById("new-caregiver-email").value.trim();
    try {
      await Api.createCaregiver({ name, email, active: true });
      document.getElementById("add-caregiver-form").reset();
      CareCommon.toast("Recipient added.", "success");
      loadCaregivers();
    } catch (err) {
      CareCommon.errorToast(err);
    }
  });

  document.getElementById("regenerate-invite-btn").addEventListener("click", async () => {
    if (!confirm("Regenerate the invite code? The old code will stop working for new sign-ups (accounts already linked keep their access).")) return;
    try {
      const data = await Api.regenerateInviteCode();
      document.getElementById("invite-code-display").textContent = data.user.invite_code;
      CareCommon.toast("Invite code regenerated.", "success");
    } catch (err) {
      CareCommon.errorToast(err);
    }
  });
});

document.addEventListener("auth-ready", (e) => {
  const user = e.detail;
  document.getElementById("account-username").textContent = user.username;
  document.getElementById("account-role-badge").textContent = CareCommon.ROLE_LABELS[user.role] || user.role;

  if (user.role === "PATIENT") {
    document.getElementById("invite-code-display").textContent = user.invite_code || "-";
    loadLinkedAccounts();
    loadCaregivers();
  } else {
    const note = document.getElementById("linked-patient-note");
    note.textContent = user.linked_patient_id
      ? "This account is linked to a patient's data and permissions."
      : "This account is not yet linked to a patient. Ask the patient for their invite code.";
    note.style.display = "block";
  }
});

async function loadLinkedAccounts() {
  try {
    const data = await Api.getLinkedAccounts();
    renderLinkedAccounts(data.accounts);
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderLinkedAccounts(accounts) {
  const el = document.getElementById("linked-accounts-list");
  if (accounts.length === 0) {
    el.innerHTML = `<div class="empty-state">No linked accounts yet. Share your invite code above.</div>`;
    return;
  }
  el.innerHTML = accounts
    .map(
      (a) => `<div class="setup-list-item">
        <div><strong>${CareCommon.escapeHtml(a.username)}</strong> <span class="role-badge">${CareCommon.escapeHtml(CareCommon.ROLE_LABELS[a.role] || a.role)}</span></div>
        <button class="btn-sm btn-danger" onclick="revokeAccount(${a.id}, '${a.username.replace(/'/g, "\\'")}')">Revoke</button>
      </div>`
    )
    .join("");
}

async function revokeAccount(id, username) {
  if (!confirm(`Revoke access for "${username}"? They will be logged out immediately.`)) return;
  try {
    await Api.revokeLinkedAccount(id);
    CareCommon.toast("Access revoked.", "success");
    loadLinkedAccounts();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function loadCaregivers() {
  try {
    const data = await Api.getCaregivers();
    renderCaregivers(data.caregivers);
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

function renderCaregivers(caregivers) {
  const el = document.getElementById("caregiver-list");
  if (caregivers.length === 0) {
    el.innerHTML = `<div class="empty-state">No recipients yet - add one below.</div>`;
    return;
  }
  el.innerHTML = caregivers
    .map(
      (c) => `<div class="setup-list-item">
        <div>
          <strong>${CareCommon.escapeHtml(c.name)}</strong>
          <span class="badge ${c.active ? "badge-on" : "badge-off"}">${c.active ? "Active" : "Inactive"}</span>
          <div class="text-muted" style="font-size:13px;">${CareCommon.escapeHtml(c.email)}</div>
        </div>
        <div class="btn-row">
          <button class="btn-sm" onclick="editCaregiver(${c.id}, '${CareCommon.escapeHtml(c.name).replace(/'/g, "\\'")}', '${CareCommon.escapeHtml(c.email).replace(/'/g, "\\'")}')">Edit</button>
          <button class="btn-sm" onclick="toggleCaregiverActive(${c.id}, ${!c.active})">${c.active ? "Deactivate" : "Activate"}</button>
          <button class="btn-sm btn-danger" onclick="deleteCaregiver(${c.id})">Delete</button>
        </div>
      </div>`
    )
    .join("");
}

async function toggleCaregiverActive(id, newActive) {
  try {
    await Api.updateCaregiver(id, { active: newActive });
    loadCaregivers();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function editCaregiver(id, currentName, currentEmail) {
  const name = prompt("Recipient name:", currentName);
  if (name === null) return;
  const email = prompt("Recipient email:", currentEmail);
  if (email === null) return;
  try {
    await Api.updateCaregiver(id, { name: name.trim(), email: email.trim() });
    CareCommon.toast("Recipient updated.", "success");
    loadCaregivers();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}

async function deleteCaregiver(id) {
  if (!confirm("Remove this recipient? They will stop receiving alert emails.")) return;
  try {
    await Api.deleteCaregiver(id);
    loadCaregivers();
  } catch (err) {
    CareCommon.errorToast(err);
  }
}
