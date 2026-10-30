/* ==========================================================================
   Authentication + session handling: login screen, JWT token, roles, logout.
   Loaded BEFORE script.js so that script.js can use Auth.*
   ========================================================================== */
const Auth = (() => {
  // IMPORTANT: change this to your live backend URL when you deploy.
  const API_BASE = "https://krypton-hr.onrender.com";

  const SESSION_KEY = "hr_session";            // sessionStorage: cleared when the tab closes
  const STAFF_ROLES = ["Admin", "HR"];
  // Pages an Employee can open. Everything else is hidden. (The API enforces the real rules.)
  const EMPLOYEE_PAGES = ["attendance", "qr-attendance", "mysalary"];

  let session = null;

  // ----------------------------------------------------------------- helpers
  function readStoredSession() {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY)); } catch (e) { return null; }
  }

  function saveSession() {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }

  function decodeJwtPayload(token) {
    try {
      let part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
      while (part.length % 4) part += "=";
      return JSON.parse(atob(part));
    } catch (e) {
      return null;
    }
  }

  function isExpired(token) {
    const payload = decodeJwtPayload(token);
    return !payload || !payload.exp || payload.exp * 1000 <= Date.now();
  }

  function formatDetail(detail) {
    if (!detail) return "";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {          // FastAPI validation errors (422)
      return detail.map(d => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
    }
    return JSON.stringify(detail);
  }

  function initials(name) {
    return String(name || "?").trim().split(/\s+/).map(n => n[0]).join("").slice(0, 2).toUpperCase();
  }

  // --------------------------------------------------------------------- API
  async function apiFetch(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (session) headers.set("Authorization", `Bearer ${session.token}`);

    let body = options.body;
    if (body && !(body instanceof FormData) && typeof body !== "string") {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(body);
    }

    let res;
    try {
      res = await fetch(`${API_BASE}${path}`, { ...options, headers, body });
    } catch (e) {
      throw new Error(`Cannot reach the server at ${API_BASE}. Make sure the backend is running.`);
    }

    if (res.status === 401 && session) {
      logout("Your session expired. Please log in again.");
      throw new Error("Session expired");
    }

    let data = null;
    const text = await res.text();
    if (text) {
      try { data = JSON.parse(text); } catch (e) { data = text; }
    }
    if (!res.ok) {
      const detail = data && typeof data === "object" ? data.detail : data;
      throw new Error(formatDetail(detail) || `Request failed (${res.status})`);
    }
    return data;
  }

  // ------------------------------------------------------------------- login
  async function login(username, password) {
    let res;
    try {
      res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
    } catch (e) {
      throw new Error(`Cannot reach the server at ${API_BASE}. Is the backend running?`);
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(formatDetail(data.detail) || "Login failed");

    session = {
      token: data.access_token,
      userId: data.user_id,
      username: data.username,
      role: data.role,
      employeeId: data.employee_id,
      displayName: data.username,
      subtitle: data.role
    };
    saveSession();
  }

  // Use the employee's real name and position in the sidebar when the account is linked to one
  async function loadProfileName() {
    if (!session || !session.employeeId) return;
    try {
      const me = await apiFetch("/employees/me");
      session.displayName = `${me.first_name} ${me.last_name}`;
      session.subtitle = `${me.position} (${session.role})`;
      saveSession();
    } catch (e) { /* keep the username */ }
  }

  // ------------------------------------------------------------------- views
  function showLogin(message) {
    document.body.classList.remove("authenticated");
    delete document.body.dataset.role;
    const err = document.getElementById("loginError");
    if (err) err.textContent = message || "";
    const pass = document.getElementById("loginPassword");
    if (pass) pass.value = "";
    const tu = document.getElementById("topbarUser");
    if (tu) tu.textContent = "Not signed in";
    const loader = document.getElementById("loginLoader");
    if (loader) {
      loader.hidden = true;
      loader.classList.remove("active", "success");
    }
    const loginScreen = document.getElementById("loginScreen");
    if (loginScreen) {
      loginScreen.classList.remove("fade-out");
    }
    const btn = document.getElementById("loginBtn");
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Sign In";
    }
  }

  function applySession() {
    document.body.classList.add("authenticated");
    document.body.dataset.role = session.role;

    document.getElementById("profileAvatar").textContent = initials(session.displayName);
    document.getElementById("profileName").textContent = session.displayName;
    document.getElementById("topbarUser").textContent = session.displayName;
    document.getElementById("profileRole").textContent = session.subtitle;

    // Show change password button for logged-in users
    const pwdBtn = document.getElementById("changePasswordBtn");
    if (pwdBtn) pwdBtn.style.display = "block";

    // Hide menu items this role may not use
    document.querySelectorAll(".nav").forEach(btn => {
      const page = btn.getAttribute("data-page");
      const allowed = session.role !== "Employee" || EMPLOYEE_PAGES.includes(page);
      btn.style.display = allowed ? "" : "none";
    });

    // Let script.js finish starting up first, then open the right landing page
    setTimeout(() => {
      if (typeof switchPage === "function") {
        switchPage(session.role === "Employee" ? "attendance" : "dashboard");
      }
      document.dispatchEvent(new CustomEvent("hr:login"));
    }, 0);
  }

  function logout(message) {
    sessionStorage.removeItem(SESSION_KEY);
    session = null;
    document.dispatchEvent(new CustomEvent("hr:logout"));
    showLogin(message);
  }

  // -------------------------------------------------------------------- init
  function init() {
    const form = document.getElementById("loginForm");
  const loginPassword = document.getElementById("loginPassword");
  const loginPasswordToggle = document.getElementById("loginPasswordToggle");

  if (loginPasswordToggle && loginPassword) {
    loginPasswordToggle.addEventListener("click", () => {
      const isPwd = loginPassword.type === "password";
      loginPassword.type = isPwd ? "text" : "password";
      loginPasswordToggle.setAttribute("aria-label", isPwd ? "Hide password" : "Show password");
      loginPasswordToggle.innerHTML = isPwd
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>';
    });
  }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const btn = document.getElementById("loginBtn");
      const err = document.getElementById("loginError");
      err.textContent = "";
      btn.disabled = true;
      btn.textContent = "Signing in...";

      const loader = document.getElementById("loginLoader");
      const loaderText = document.getElementById("loginLoaderText");
      const loginScreen = document.getElementById("loginScreen");
      if (loader) {
        loader.hidden = false;
        loader.classList.add("active");
        loader.classList.remove("success");
        if (loaderText) loaderText.textContent = "Authenticating credentials...";
      }

      await new Promise((r) => setTimeout(r, 1200));
      if (loader) {
        loader.classList.add("success");
        if (loaderText) loaderText.textContent = "Access granted. Securing session...";
      }
      await new Promise((r) => setTimeout(r, 900));
      if (loginScreen) {
        loginScreen.classList.add("fade-out");
      }
      await new Promise((r) => setTimeout(r, 600));

      try {
        await login(document.getElementById("loginUsername").value.trim(),
                    document.getElementById("loginPassword").value);
        await loadProfileName();
        applySession();
        if (loginScreen) loginScreen.classList.remove("fade-out");
        if (loader) {
          loader.classList.remove("active", "success");
          loader.hidden = true;
        }
        btn.disabled = false;
        btn.textContent = "Sign In";
      } catch (e) {
        if (loginScreen) loginScreen.classList.remove("fade-out");
        if (loader) {
          loader.classList.remove("active", "success");
          loader.hidden = true;
        }
        err.textContent = e.message;
        btn.disabled = false;
        btn.textContent = "Sign In";
        document.getElementById("loginPassword").value = "";
      }
    });

    document.getElementById("logoutBtn").addEventListener("click", () => logout());

    // Change password button
    const pwdBtn = document.getElementById("changePasswordBtn");
    if (pwdBtn) {
      pwdBtn.addEventListener("click", () => {
        document.getElementById("pwdModal").classList.add("active");
        document.getElementById("pwdError").textContent = "";
        document.getElementById("pwdForm").reset();
      });
    }

    // Change password form
    const pwdForm = document.getElementById("pwdForm");
    if (pwdForm) {
      pwdForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const current = document.getElementById("pwdCurrent").value;
        const newPass = document.getElementById("pwdNew").value;
        const confirm = document.getElementById("pwdConfirm").value;
        const errBox = document.getElementById("pwdError");

        if (newPass !== confirm) {
          errBox.textContent = "New passwords do not match.";
          return;
        }

        const submitBtn = pwdForm.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.textContent = "Updating...";

        try {
          await apiFetch("/auth/change-password", {
            method: "POST",
            body: { old_password: current, new_password: newPass }
          });
          document.getElementById("pwdModal").classList.remove("active");
          alert("Password changed successfully!");
        } catch (e) {
          errBox.textContent = e.message;
        } finally {
          submitBtn.disabled = false;
          submitBtn.textContent = "Update Password";
        }
      });
    }

    // Close password modal
    const pwdCancel = document.getElementById("pwdCancel");
    if (pwdCancel) {
      pwdCancel.addEventListener("click", () => {
        document.getElementById("pwdModal").classList.remove("active");
      });
    }

    const stored = readStoredSession();
    if (stored && stored.token && !isExpired(stored.token)) {
      session = stored;
      applySession();
    } else {
      sessionStorage.removeItem(SESSION_KEY);
      showLogin();
    }

    // Log out automatically when the token expires
    setInterval(() => {
      if (session && isExpired(session.token)) logout("Your session expired. Please log in again.");
    }, 30000);
  }

  document.addEventListener("DOMContentLoaded", init);

  return {
    API_BASE,
    apiFetch,
    logout,
    getToken: () => (session ? session.token : null),
    getSession: () => session,
    isStaff: () => !!session && STAFF_ROLES.includes(session.role)
  };
})();
