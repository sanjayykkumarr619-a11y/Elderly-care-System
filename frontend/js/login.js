document.addEventListener("DOMContentLoaded", () => {
  // Already logged in? Skip straight past the login screen.
  if (Api.getToken()) {
    Api.me()
      .then((data) => {
        location.href = data.user.setup_completed ? "index.html" : "setup.html";
      })
      .catch(() => Api.clearSession());
  }

  const tabLogin = document.getElementById("tab-login");
  const tabRegister = document.getElementById("tab-register");
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const errorBox = document.getElementById("auth-error");

  const roleSelect = document.getElementById("reg-role");
  const patientFields = document.getElementById("patient-fields");
  const linkedFields = document.getElementById("linked-fields");
  roleSelect.addEventListener("change", () => {
    const isPatient = roleSelect.value === "PATIENT";
    patientFields.style.display = isPatient ? "block" : "none";
    linkedFields.style.display = isPatient ? "none" : "block";
    document.getElementById("reg-caregiver-email").required = isPatient;
    document.getElementById("reg-invite-code").required = !isPatient;
  });

  function showTab(which) {
    hideError();
    const isLogin = which === "login";
    tabLogin.classList.toggle("active", isLogin);
    tabRegister.classList.toggle("active", !isLogin);
    loginForm.style.display = isLogin ? "block" : "none";
    registerForm.style.display = isLogin ? "none" : "block";
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.classList.add("visible");
  }

  function hideError() {
    errorBox.classList.remove("visible");
  }

  tabLogin.addEventListener("click", () => showTab("login"));
  tabRegister.addEventListener("click", () => showTab("register"));

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideError();
    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;
    try {
      const data = await Api.login({ username, password });
      Api.setSession(data.token, data.user);
      location.href = data.user.setup_completed ? "index.html" : "setup.html";
    } catch (err) {
      showError(err.message);
    }
  });

  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideError();
    const username = document.getElementById("reg-username").value.trim();
    const password = document.getElementById("reg-password").value;
    const role = roleSelect.value;

    const payload = { username, password, role };
    if (role === "PATIENT") {
      payload.caregiver_name = document.getElementById("reg-caregiver-name").value.trim();
      payload.caregiver_email = document.getElementById("reg-caregiver-email").value.trim();
    } else {
      payload.invite_code = document.getElementById("reg-invite-code").value.trim();
    }

    try {
      const data = await Api.register(payload);
      Api.setSession(data.token, data.user);
      location.href = role === "PATIENT" ? "setup.html" : "index.html";
    } catch (err) {
      showError(err.message);
    }
  });
});
