/* Thin wrapper around every backend REST endpoint. Nothing in here knows
   about the DOM (aside from the localStorage session + 401 redirect) - it
   mostly just talks JSON over HTTP to the Python backend. */

const Api = (() => {
  const TOKEN_KEY = "ecs_token";
  const USER_KEY = "ecs_user";

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function getCachedUser() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || "null");
    } catch (err) {
      return null;
    }
  }

  function setSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  async function request(method, path, body) {
    const options = { method, headers: {} };
    const token = getToken();
    if (token) options.headers["Authorization"] = "Bearer " + token;
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }

    let response;
    try {
      response = await fetch(path, options);
    } catch (err) {
      throw new Error("Could not reach the server. Is server.py running?");
    }

    let data = null;
    try {
      data = await response.json();
    } catch (err) {
      data = null;
    }

    const isAuthEndpoint = path.startsWith("/api/auth/login") || path.startsWith("/api/auth/register");
    if (response.status === 401 && !isAuthEndpoint) {
      clearSession();
      if (!location.pathname.endsWith("login.html")) {
        location.href = "login.html";
      }
    }

    if (!response.ok) {
      const message = (data && data.error) || `Request failed (${response.status})`;
      const err = new Error(message);
      err.status = response.status;
      throw err;
    }
    return data;
  }

  const get = (path) => request("GET", path);
  const post = (path, body) => request("POST", path, body || {});
  const put = (path, body) => request("PUT", path, body || {});
  const del = (path) => request("DELETE", path);

  return {
    getToken,
    getCachedUser,
    setSession,
    clearSession,

    // Auth
    register: (data) => post("/api/auth/register", data),
    login: (data) => post("/api/auth/login", data),
    logout: () => post("/api/auth/logout"),
    me: () => get("/api/auth/me"),
    updateMe: (data) => put("/api/auth/me", data),
    regenerateInviteCode: () => post("/api/auth/invite-code/regenerate"),
    getLinkedAccounts: () => get("/api/auth/linked-accounts"),
    revokeLinkedAccount: (id) => post(`/api/auth/linked-accounts/${id}/revoke`),

    // Caregiver / family recipients
    getCaregivers: () => get("/api/caregivers"),
    createCaregiver: (data) => post("/api/caregivers", data),
    updateCaregiver: (id, data) => put(`/api/caregivers/${id}`, data),
    deleteCaregiver: (id) => del(`/api/caregivers/${id}`),

    // Medicines
    getMedicines: () => get("/api/medicines"),
    getMedicine: (id) => get(`/api/medicines/${id}`),
    createMedicine: (data) => post("/api/medicines", data),
    updateMedicine: (id, data) => put(`/api/medicines/${id}`, data),
    deleteMedicine: (id) => del(`/api/medicines/${id}`),

    // Stock
    getStock: () => get("/api/stock"),
    getStockAlerts: () => get("/api/stock/alerts"),
    addStock: (medicineId, amount) => post(`/api/stock/${medicineId}/add`, { amount }),
    setStock: (medicineId, currentStock) => put(`/api/stock/${medicineId}`, { current_stock: currentStock }),

    // Schedules
    getSchedules: (medicineId) => get(medicineId ? `/api/schedules?medicine_id=${medicineId}` : "/api/schedules"),
    createSchedule: (data) => post("/api/schedules", data),
    updateSchedule: (id, data) => put(`/api/schedules/${id}`, data),
    deleteSchedule: (id) => del(`/api/schedules/${id}`),

    // Medication records
    getToday: () => get("/api/medications/today"),
    getHistory: (params) => {
      const qs = new URLSearchParams(params || {}).toString();
      return get(`/api/medication-history${qs ? "?" + qs : ""}`);
    },
    markTaken: (recordId) => post(`/api/medications/${recordId}/taken`),
    markMissed: (recordId) => post(`/api/medications/${recordId}/missed`),

    // Notifications
    getNotifications: (isRead) => get(`/api/notifications${isRead === undefined ? "" : `?is_read=${isRead ? 1 : 0}`}`),
    markNotificationRead: (id) => post(`/api/notifications/${id}/read`),

    // Cameras
    getCameras: () => get("/api/cameras"),
    createCamera: (data) => post("/api/cameras", data),
    updateCamera: (id, data) => put(`/api/cameras/${id}`, data),
    deleteCamera: (id) => del(`/api/cameras/${id}`),
    connectCamera: (id) => post(`/api/cameras/${id}/connect`),
    disconnectCamera: (id) => post(`/api/cameras/${id}/disconnect`),
    getCameraStream: (id) => get(`/api/cameras/${id}/stream`),

    // Smart home devices
    getDevices: () => get("/api/devices"),
    getDevice: (id) => get(`/api/devices/${id}`),
    createDevice: (data) => post("/api/devices", data),
    deleteDevice: (id) => del(`/api/devices/${id}`),
    sendDeviceCommand: (id, command) => post(`/api/devices/${id}/command`, { command }),

    // Robot (hardware-ready)
    getRobotStatus: () => get("/api/robot/status"),
    robotDispense: (data) => post("/api/robot/dispense", data || {}),
    robotAlarm: () => post("/api/robot/alarm"),
    robotStop: () => post("/api/robot/stop"),

    // Sensors (hardware-ready)
    getSensors: () => get("/api/sensors"),
    getSensorStatus: (id) => get(`/api/sensors/${id}/status`),
    pushSensorData: (id, value) => post(`/api/sensors/${id}/data`, { value }),
  };
})();
