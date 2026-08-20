/* Shared UI plumbing used by every page: sidebar nav, mobile header,
   mobile bottom bar, mobile drawer, toasts, formatting helpers,
   and the browser-side medication reminder engine. */

const CareCommon = (() => {
  const NAV_ITEMS = [
    { id: "dashboard", label: "Dashboard", href: "index.html", icon: "🏠", shortLabel: "Home" },
    { id: "medication", label: "Medicines", href: "medication.html", icon: "💊", shortLabel: "Meds" },
    { id: "schedule", label: "Schedule", href: "schedule.html", icon: "⏰", shortLabel: "Schedule" },
    { id: "history", label: "History", href: "history.html", icon: "📋", shortLabel: "History" },
    { id: "stock", label: "Stock", href: "stock.html", icon: "📦", shortLabel: "Stock" },
    { id: "cameras", label: "Cameras", href: "cameras.html", icon: "📹", shortLabel: "Cameras" },
    { id: "smart-home", label: "Smart Home", href: "smart-home.html", icon: "⚡", shortLabel: "Smart" },
    { id: "notifications", label: "Notifications", href: "notifications.html", icon: "🔔", shortLabel: "Alerts" },
    { id: "settings", label: "Settings", href: "settings.html", icon: "⚙️", shortLabel: "Settings" },
  ];

  const BOTTOM_NAV_IDS = ["dashboard", "medication", "schedule", "notifications"];

  function renderSidebar(activeId) {
    const placeholder = document.getElementById("sidebar-placeholder");
    if (!placeholder) return;

    // 1. Desktop Sidebar
    const desktopLinks = NAV_ITEMS.map(
      (item) => `<a href="${item.href}" data-nav-id="${item.id}" class="${item.id === activeId ? "active" : ""}">
        <span class="nav-icon">${item.icon}</span>
        <span>${item.label}</span>
        ${item.id === "notifications" ? '<span class="unread-badge unread-badge-desktop" style="display:none;"></span>' : ""}
      </a>`
    ).join("");

    // 2. Mobile Bottom Navigation Tabs
    const bottomTabs = BOTTOM_NAV_IDS.map((id) => {
      const item = NAV_ITEMS.find((n) => n.id === id);
      if (!item) return "";
      const isActive = item.id === activeId;
      return `<a href="${item.href}" data-nav-id="${item.id}" class="mobile-nav-tab ${isActive ? "active" : ""}">
        <span class="tab-icon">
          ${item.icon}
          ${item.id === "notifications" ? '<span class="tab-badge unread-badge-bottom" style="display:none;"></span>' : ""}
        </span>
        <span>${item.shortLabel}</span>
      </a>`;
    }).join("") + `
      <button type="button" class="mobile-nav-tab" id="mobile-menu-tab-btn" aria-label="Open navigation menu">
        <span class="tab-icon">☰</span>
        <span>More</span>
      </button>`;

    // 3. Mobile Slide-out Drawer Navigation Links
    const drawerLinks = NAV_ITEMS.map(
      (item) => `<a href="${item.href}" data-nav-id="${item.id}" class="${item.id === activeId ? "active" : ""}">
        <span class="nav-icon">${item.icon}</span>
        <span>${item.label}</span>
        ${item.id === "notifications" ? '<span class="unread-badge unread-badge-drawer" style="display:none;"></span>' : ""}
      </a>`
    ).join("");

    placeholder.outerHTML = `
      <!-- Desktop Sidebar Navigation -->
      <aside class="sidebar">
        <div class="brand">
          <span class="brand-icon">✚</span>
          <span>Elderly Care</span>
        </div>
        <nav>${desktopLinks}</nav>
      </aside>

      <!-- Mobile Top Navigation Header -->
      <header class="mobile-topbar">
        <div class="mobile-topbar-left">
          <a href="index.html" class="mobile-topbar-brand">
            <span class="brand-icon">✚</span>
            <span>Elderly Care</span>
          </a>
        </div>
        <div class="mobile-topbar-actions">
          <a href="notifications.html" class="mobile-icon-btn" aria-label="Notifications">
            <span>🔔</span>
            <span class="unread-badge unread-badge-top" style="display:none;"></span>
          </a>
          <button type="button" class="mobile-icon-btn" id="mobile-drawer-toggle-btn" aria-label="Toggle menu">
            <span>☰</span>
          </button>
        </div>
      </header>

      <!-- Mobile Slide-out Drawer -->
      <div class="mobile-drawer-overlay" id="mobile-drawer-overlay"></div>
      <div class="mobile-drawer" id="mobile-drawer">
        <div class="mobile-drawer-header">
          <div class="mobile-drawer-title">Navigation Menu</div>
          <button type="button" class="mobile-drawer-close" id="mobile-drawer-close-btn" aria-label="Close menu">&times;</button>
        </div>
        <div class="mobile-drawer-user" id="mobile-drawer-user-info">
          <!-- Populated by attachSidebarFooter -->
        </div>
        <nav class="mobile-drawer-nav">
          ${drawerLinks}
        </nav>
        <div class="mobile-drawer-footer">
          <button id="mobile-logout-btn" class="btn-danger btn-block">Log Out</button>
        </div>
      </div>

      <!-- Mobile Fixed Bottom Navigation Bar -->
      <nav class="mobile-bottom-nav">
        ${bottomTabs}
      </nav>
    `;

    initMobileDrawer();
  }

  function initMobileDrawer() {
    const drawer = document.getElementById("mobile-drawer");
    const overlay = document.getElementById("mobile-drawer-overlay");
    const toggleBtn = document.getElementById("mobile-drawer-toggle-btn");
    const closeBtn = document.getElementById("mobile-drawer-close-btn");
    const moreTabBtn = document.getElementById("mobile-menu-tab-btn");

    function openDrawer() {
      if (drawer && overlay) {
        drawer.classList.add("open");
        overlay.classList.add("open");
        document.body.style.overflow = "hidden";
      }
    }

    function closeDrawer() {
      if (drawer && overlay) {
        drawer.classList.remove("open");
        overlay.classList.remove("open");
        document.body.style.overflow = "";
      }
    }

    if (toggleBtn) toggleBtn.addEventListener("click", openDrawer);
    if (moreTabBtn) moreTabBtn.addEventListener("click", openDrawer);
    if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
    if (overlay) overlay.addEventListener("click", closeDrawer);
  }

  async function refreshUnreadBadge() {
    const badges = document.querySelectorAll(".unread-badge-desktop, .unread-badge-top, .unread-badge-bottom, .unread-badge-drawer");
    if (badges.length === 0) return;
    try {
      const data = await Api.getNotifications(false);
      const count = data.notifications.length;
      badges.forEach((b) => {
        if (count > 0) {
          b.textContent = count > 99 ? "99+" : String(count);
          b.style.display = "inline-flex";
        } else {
          b.style.display = "none";
        }
      });
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

  const NO_ACCESS_NAV = {
    DOCTOR: ["cameras", "smart-home"],
    CARETAKER: ["cameras", "smart-home"],
  };

  function attachSidebarFooter(user) {
    const sidebar = document.querySelector(".sidebar");
    const mobileUserInfo = document.getElementById("mobile-drawer-user-info");
    const subtitle =
      user.role === "PATIENT"
        ? `Caregiver: ${escapeHtml(user.caregiver_email || "not set")}`
        : "Linked account";

    // 1. Desktop Footer
    if (sidebar && !sidebar.querySelector(".sidebar-footer")) {
      const footer = document.createElement("div");
      footer.className = "sidebar-footer";
      footer.innerHTML = `
        <div class="sidebar-user">
          <div class="sidebar-user-name">${escapeHtml(user.username)} <span class="role-badge">${escapeHtml(ROLE_LABELS[user.role] || user.role)}</span></div>
          <div class="sidebar-user-caregiver">${subtitle}</div>
        </div>
        <button id="logout-btn" class="btn-sm btn-block">Log Out</button>`;
      sidebar.appendChild(footer);

      document.getElementById("logout-btn").addEventListener("click", handleLogout);
    }

    // 2. Mobile Drawer User Info
    if (mobileUserInfo) {
      mobileUserInfo.innerHTML = `
        <div class="sidebar-user-name">${escapeHtml(user.username)} <span class="role-badge">${escapeHtml(ROLE_LABELS[user.role] || user.role)}</span></div>
        <div class="sidebar-user-caregiver">${subtitle}</div>
      `;
      const mobileLogoutBtn = document.getElementById("mobile-logout-btn");
      if (mobileLogoutBtn) {
        mobileLogoutBtn.addEventListener("click", handleLogout);
      }
    }
  }

  async function handleLogout() {
    try {
      await Api.logout();
    } catch (err) {
      // ignore
    }
    Api.clearSession();
    location.href = "login.html";
  }

  function applyRolePermissions(user) {
    document.body.dataset.role = user.role;
    const hiddenNavIds = NO_ACCESS_NAV[user.role] || [];
    hiddenNavIds.forEach((navId) => {
      const links = document.querySelectorAll(`[data-nav-id="${navId}"]`);
      links.forEach((l) => l.remove());
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
    el.innerHTML = `<span>${type === "error" ? "⚠️" : type === "success" ? "✓" : "ℹ️"}</span> <span>${escapeHtml(message)}</span>`;
    container.appendChild(el);
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transform = "translateY(-10px)";
      el.style.transition = "all 0.2s ease";
      setTimeout(() => el.remove(), 200);
    }, 4500);
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
   HTMLAudioElement - no external audio library.
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
    overlay.innerHTML = `
      <div class="reminder-modal">
        <div class="reminder-kicker">🔔 Medicine Reminder</div>
        <h2>${CareCommon.escapeHtml(record.medicine_name)}</h2>
        <div class="reminder-dose">Take ${CareCommon.formatNumber(record.dosage)} dose</div>
        <div class="reminder-time">Scheduled for ${CareCommon.formatTime12(record.scheduled_time)}</div>
        <div class="btn-row">
          <button class="btn-success btn-large" id="reminder-taken-btn">✓ MEDICINE TAKEN</button>
          <button class="btn-danger btn-large" id="reminder-stop-alarm-btn">STOP ALARM SOUND</button>
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
    if (modalEl) return;
    activeRecord = record;
    modalEl = buildModal(record);

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
      if (activeRecord) {
        const current = data.records.find((r) => r.id === activeRecord.id);
        if (!current || current.status !== "PENDING") {
          closeModal(current && current.status === "MISSED" ? "expired" : undefined);
          window.dispatchEvent(new CustomEvent("medication-updated"));
        }
      }

      const due = data.records.filter(isDue);
      if (!modalEl && due.length > 0) {
        openModal(due[0]);
      }
    } catch (err) {
      // Silent
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
  if (document.body.dataset.public === "true") return;

  const user = await CareCommon.guardAuth();
  if (!user) return;

  CareCommon.attachSidebarFooter(user);
  CareCommon.applyRolePermissions(user);
  document.dispatchEvent(new CustomEvent("auth-ready", { detail: user }));

  CareCommon.refreshUnreadBadge();
  window.addEventListener("medication-updated", CareCommon.refreshUnreadBadge);

  const canConfirmDoses = user.role === "PATIENT";
  if (document.body.dataset.page !== "setup" && canConfirmDoses) {
    ReminderEngine.start();
  }
});
