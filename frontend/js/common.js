/* Shared UI plumbing used by every page: sidebar nav, toasts, formatting
   helpers, and the browser-side medication reminder engine. */

const CareCommon = (() => {
  const NAV_ITEMS = [
    { id: "dashboard", label: "Dashboard", href: "index.html", icon: "⌂" },
    { id: "medication", label: "Medicines", href: "medication.html", icon: "⚕" },
    { id: "schedule", label: "Schedule", href: "schedule.html", icon: "⏰" },
    { id: "history", label: "History", href: "history.html", icon: "☰" },
    { id: "stock", label: "Stock", href: "stock.html", icon: "▤" },
    { id: "cameras", label: "Cameras", href: "cameras.html", icon: "◉" },
    { id: "smart-home", label: "Smart Home", href: "smart-home.html", icon: "⚙" },
    { id: "notifications", label: "Notifications", href: "notifications.html", icon: "✉" },
    { id: "settings", label: "Settings", href: "settings.html", icon: "⚙" },
  ];

  function renderSidebar(activeId) {
    const placeholder = document.getElementById("sidebar-placeholder");
    if (!placeholder) return;
    const links = NAV_ITEMS.map(
      (item) => `<a href="${item.href}" data-nav-id="${item.id}" class="${item.id === activeId ? "active" : ""}">
        <span class="nav-icon">${item.icon}</span>${item.label}
        ${item.id === "notifications" ? '<span class="unread-badge" id="unread-badge" style="display:none;"></span>' : ""}
      </a>`
    ).join("");
    placeholder.outerHTML = `
      <div class="sidebar">
        <div class="brand">Elderly Care System</div>
        <nav>${links}</nav>
      </div>`;
  }

  async function refreshUnreadBadge() {
    const badge = document.getElementById("unread-badge");
    if (!badge) return;
    try {
      const data = await Api.getNotifications(false);
      const count = data.notifications.length;
      if (count > 0) {
        badge.textContent = count > 99 ? "99+" : String(count);
        badge.style.display = "inline-block";
      } else {
        badge.style.display = "none";
      }
    } catch (err) {
      // Silent - the badge is a nice-to-have, not worth surfacing errors for.
    }
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  function redirectToLogin() {
    Api.clearSession();
    if (!location.pathname.endsWith("login.html")) {
      location.href = "login.html";
    }
  }

  async function guardAuth() {
    const token = Api.getToken();
    if (!token) {
      redirectToLogin();
      return null;
    }
    let data;
    try {
      data = await Api.me();
    } catch (err) {
      redirectToLogin();
      return null;
    }
    Api.setSession(token, data.user);

    const onSetupPage = document.body.dataset.page === "setup";
    if (!data.user.setup_completed && !onSetupPage) {
      location.href = "setup.html";
      return null;
    }
    return data.user;
  }

  const ROLE_LABELS = {
    PATIENT: "Patient",
    CARETAKER: "Caretaker",
    FAMILY: "Family Member",
    DOCTOR: "Doctor",
  };

  // Roles with no camera/smart-home access at all (not even read-only) -
  // their nav links are removed entirely rather than just disabled.
  // Cameras/smart-home are a Patient + Family Member thing; Caretaker and
  // Doctor get neither.
  const NO_ACCESS_NAV = {
    DOCTOR: ["cameras", "smart-home"],
    CARETAKER: ["cameras", "smart-home"],
  };

  function attachSidebarFooter(user) {
    const sidebar = document.querySelector(".sidebar");
    if (!sidebar || sidebar.querySelector(".sidebar-footer")) return;
    const footer = document.createElement("div");
    footer.className = "sidebar-footer";
    const subtitle =
      user.role === "PATIENT"
        ? `Caregiver: ${escapeHtml(user.caregiver_email || "not set")}`
        : "Linked account";
    footer.innerHTML = `
      <div class="sidebar-user">
        <div class="sidebar-user-name">${escapeHtml(user.username)} <span class="role-badge">${escapeHtml(ROLE_LABELS[user.role] || user.role)}</span></div>
        <div class="sidebar-user-caregiver">${subtitle}</div>
      </div>
      <button id="logout-btn" class="btn-sm btn-block">Log Out</button>`;
    sidebar.appendChild(footer);
    document.getElementById("logout-btn").addEventListener("click", async () => {
      try {
        await Api.logout();
      } catch (err) {
        // ignore - we're logging out either way
      }
      Api.clearSession();
      location.href = "login.html";
    });
  }

  function applyRolePermissions(user) {
    document.body.dataset.role = user.role;
    const hiddenNavIds = NO_ACCESS_NAV[user.role] || [];
    hiddenNavIds.forEach((navId) => {
      const link = document.querySelector(`.sidebar nav a[data-nav-id="${navId}"]`);
      if (link) link.remove();
    });
  }

  function ensureToastContainer() {
    let el = document.getElementById("toast-container");
    if (!el) {
      el = document.createElement("div");
      el.id = "toast-container";
      document.body.appendChild(el);
    }
    return el;
  }

  function toast(message, type) {
    const container = ensureToastContainer();
    const el = document.createElement("div");
    el.className = "toast" + (type ? " " + type : "");
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => el.remove(), 4500);
  }

  function errorToast(err) {
    toast(err && err.message ? err.message : "Something went wrong", "error");
  }

  // ---- formatting helpers ----

  function formatTime12(hhmm) {
    if (!hhmm) return "-";
    const [hStr, mStr] = hhmm.split(":");
    let h = parseInt(hStr, 10);
    const suffix = h >= 12 ? "PM" : "AM";
    h = h % 12;
    if (h === 0) h = 12;
    return `${h}:${mStr} ${suffix}`;
  }

  function formatDateTimeDisplay(ts) {
    if (!ts) return "-";
    const [datePart, timePart] = ts.split(" ");
    if (!timePart) return ts;
    return `${formatDateDisplay(datePart)} ${formatTime12(timePart.slice(0, 5))}`;
  }

  function formatDateDisplay(iso) {
    if (!iso) return "-";
    const d = new Date(iso + "T00:00:00");
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
  }

  function formatNumber(n) {
    if (n === null || n === undefined) return "-";
    const num = Number(n);
    return Number.isInteger(num) ? String(num) : num.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
  }

  function statusBadge(status) {
    const map = {
      TAKEN: "badge-taken",
      MISSED: "badge-missed",
      PENDING: "badge-pending",
      LOW_STOCK: "badge-low",
      NORMAL: "badge-normal",
      ON: "badge-on",
      OFF: "badge-off",
      ONLINE: "badge-online",
      OFFLINE: "badge-offline",
      STREAMING: "badge-streaming",
    };
    const cls = map[status] || "badge-pending";
    return `<span class="badge ${cls}">${status.replace("_", " ")}</span>`;
  }

  // ---- browser notifications ----

  function requestNotificationPermission() {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  }

  function showBrowserNotification(title, body) {
    if ("Notification" in window && Notification.permission === "granted") {
      try {
        new Notification(title, { body });
      } catch (err) {
        // ignore - in-app modal is the fallback of record
      }
    }
  }

  return {
    NAV_ITEMS,
    renderSidebar,
    refreshUnreadBadge,
    toast,
    errorToast,
    formatTime12,
    formatDateDisplay,
    formatDateTimeDisplay,
    formatNumber,
    statusBadge,
    requestNotificationPermission,
    showBrowserNotification,
    escapeHtml,
    guardAuth,
    redirectToLogin,
    attachSidebarFooter,
    applyRolePermissions,
    ROLE_LABELS,
  };
})();

/* ---------------------------------------------------------------------
   Alarm Audio
   Plays frontend/assets/medication-alarm.mp3 via a single, reused
   HTMLAudioElement - no external audio library. Browsers block unmuted
   autoplay until the page has real user interaction with audio, so the
   Dashboard's "Enable Medication Alarm" button exists specifically to
   produce that first genuine play() call from a click. Once that has
   happened, the same <audio> element keeps working for automatic
   (no-click) playback for the rest of the browsing session.
   ------------------------------------------------------------------- */

const AlarmAudio = (() => {
  const ALARM_SRC = "/assets/medication-alarm.mp3";
  const STORAGE_KEY = "ecs_alarm_enabled";
  let audio = null;

  function getAudio() {
    if (!audio) {
      audio = new Audio(ALARM_SRC);
      audio.loop = true;
    }
    return audio;
  }

  function isEnabled() {
    return localStorage.getItem(STORAGE_KEY) === "true";
  }

  function isPlaying() {
    return !!audio && !audio.paused;
  }

  async function play() {
    const el = getAudio();
    try {
      el.currentTime = 0;
      el.loop = true;
      await el.play();
      return { ok: true };
    } catch (err) {
      return { ok: false, error: err };
    }
  }

  function stop() {
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
  }

  // Called directly from a click handler (a genuine user gesture) so the
  // browser's autoplay policy allows it - this is what "enables" the
  // alarm for automatic playback later.
  async function enable() {
    const result = await play();
    if (result.ok) {
      stop();
      localStorage.setItem(STORAGE_KEY, "true");
    }
    return result;
  }

  return { play, stop, enable, isEnabled, isPlaying };
})();

/* ---------------------------------------------------------------------
   Medication Reminder Engine
   Polls the backend (the source of truth) for today's records and pops a
   prominent modal + independent audible alarm + browser notification the
   moment a dose's scheduled time arrives, until the user confirms it as
   taken, stops the alarm, or the grace period expires.
   ------------------------------------------------------------------- */

const ReminderEngine = (() => {
  const POLL_MS = 15000;
  let activeRecord = null;
  let modalEl = null;
  let timer = null;

  function currentHHMM() {
    const now = new Date();
    return String(now.getHours()).padStart(2, "0") + ":" + String(now.getMinutes()).padStart(2, "0");
  }

  function isDue(record) {
    return record.status === "PENDING" && record.scheduled_time <= currentHHMM();
  }

  function buildModal(record) {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    // Deliberately no "dismiss" / "remind me later" control here: per spec
    // the reminder must stay active until the user confirms it or the
    // backend grace period expires (poll() below detects that and closes
    // it) - not until the user just clicks it away. STOP ALARM only
    // silences the audible alarm; it does not dismiss the reminder.
    overlay.innerHTML = `
      <div class="reminder-modal">
        <div class="reminder-kicker">Medicine Time</div>
        <h2>${record.medicine_name}</h2>
        <div class="reminder-dose">Take ${CareCommon.formatNumber(record.dosage)}</div>
        <div class="reminder-time">Scheduled: ${CareCommon.formatTime12(record.scheduled_time)}</div>
        <div class="btn-row" style="justify-content:center;">
          <button class="btn-success btn-large" id="reminder-taken-btn">MEDICINE TAKEN</button>
          <button class="btn-danger btn-large" id="reminder-stop-alarm-btn">STOP ALARM</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    overlay.querySelector("#reminder-taken-btn").addEventListener("click", async () => {
      try {
        await Api.markTaken(record.id);
        CareCommon.toast(`${record.medicine_name} marked as taken.`, "success");
        closeModal();
        window.dispatchEvent(new CustomEvent("medication-updated"));
      } catch (err) {
        CareCommon.errorToast(err);
        closeModal();
      }
    });

    overlay.querySelector("#reminder-stop-alarm-btn").addEventListener("click", () => {
      AlarmAudio.stop();
    });

    return overlay;
  }

  function closeModal(reason) {
    AlarmAudio.stop();
    if (modalEl) {
      modalEl.remove();
      modalEl = null;
    }
    if (reason === "expired" && activeRecord) {
      CareCommon.toast(
        `${activeRecord.medicine_name}'s ${CareCommon.formatTime12(activeRecord.scheduled_time)} dose was not confirmed in time and is now marked MISSED.`,
        "error"
      );
    }
    activeRecord = null;
  }

  function openModal(record) {
    if (modalEl) return; // one at a time
    activeRecord = record;
    modalEl = buildModal(record);

    // Three independent triggers off the same scheduled time - the alarm
    // sound never depends on (or is gated by) the Notification API, and
    // vice versa. Either can fail on its own without affecting the other.
    AlarmAudio.play().then((result) => {
      if (!result.ok) {
        CareCommon.toast(
          "Browser blocked the alarm sound. Click \"Enable Medication Alarm\" on the Dashboard.",
          "error"
        );
      }
    });
    CareCommon.showBrowserNotification(
      `Medicine Time: ${record.medicine_name}`,
      `Take ${CareCommon.formatNumber(record.dosage)} - scheduled ${CareCommon.formatTime12(record.scheduled_time)}`
    );
  }

  async function poll() {
    try {
      const data = await Api.getToday();

      // If the record currently shown got confirmed/expired elsewhere (e.g.
      // the backend's own grace-period sweep, or another tab), close it -
      // this is the "grace period expires" half of "active until confirmed
      // or grace period expires."
      if (activeRecord) {
        const current = data.records.find((r) => r.id === activeRecord.id);
        if (!current || current.status !== "PENDING") {
          closeModal(current && current.status === "MISSED" ? "expired" : undefined);
          // Status changed underneath us (grace period expired, or resolved
          // from another tab) - let any open dashboard/history/stock view
          // refresh instead of showing stale PENDING data.
          window.dispatchEvent(new CustomEvent("medication-updated"));
        }
      }

      const due = data.records.filter(isDue);
      if (!modalEl && due.length > 0) {
        openModal(due[0]);
      }
    } catch (err) {
      // Silent: reminder polling should not spam errors if the server is
      // briefly unavailable.
    }
  }

  function start() {
    CareCommon.requestNotificationPermission();
    poll();
    timer = setInterval(poll, POLL_MS);
    window.addEventListener("medication-updated", poll);
  }

  return { start };
})();

document.addEventListener("DOMContentLoaded", async () => {
  if (document.body.dataset.public === "true") return; // login.html handles its own flow

  const user = await CareCommon.guardAuth();
  if (!user) return; // guardAuth is already redirecting

  CareCommon.attachSidebarFooter(user);
  CareCommon.applyRolePermissions(user);
  document.dispatchEvent(new CustomEvent("auth-ready", { detail: user }));

  CareCommon.refreshUnreadBadge();
  window.addEventListener("medication-updated", CareCommon.refreshUnreadBadge);

  // Family Member / Doctor accounts are read-only, so a "confirm taken"
  // reminder popup would just be a dead end for them - only the Patient
  // (the only role that can actually confirm a dose) gets the reminder engine.
  const canConfirmDoses = user.role === "PATIENT";
  if (document.body.dataset.page !== "setup" && canConfirmDoses) {
    ReminderEngine.start();
  }
});
