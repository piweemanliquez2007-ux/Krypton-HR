/* QR login on the login screen */
(function () {
  const tabs = document.querySelectorAll(".login-tab");
  const creds = document.getElementById("loginCreds");
  const qrBox = document.getElementById("loginQr");
  const readerEl = document.getElementById("loginQrReader");
  const stopBtn = document.getElementById("loginQrStop");
  const qrError = document.getElementById("loginQrError");
  const loginError = document.getElementById("loginError");
  let scanner = null;
  let scanning = false;
  let scanStatusEl = null;

  function ensureStatus() {
    if (!qrBox) return;
    if (!scanStatusEl) {
      scanStatusEl = document.createElement("div");
      scanStatusEl.id = "loginQrStatus";
      scanStatusEl.style.cssText = "margin-top:10px;padding:10px 12px;border-radius:10px;font-size:13px;display:flex;align-items:center;gap:10px;";
      qrBox.appendChild(scanStatusEl);
    }
    return scanStatusEl;
  }

  function setStatus(state, msg) {
    const el = ensureStatus();
    if (!el) return;
    if (state === "scanning") {
      el.style.background = "rgba(59,130,246,0.18)";
      el.style.border = "1px solid rgba(96,165,250,0.6)";
      el.style.color = "#bfdbfe";
      el.innerHTML = `<span style="width:10px;height:10px;border-radius:50%;background:#60a5fa;box-shadow:0 0 0 6px rgba(96,165,250,0.18);"></span><span>${msg || "Scanning... Align QR within the frame."}</span>`;
      el.style.display = "flex";
    } else if (state === "success") {
      el.style.background = "rgba(34,197,94,0.22)";
      el.style.border = "1px solid rgba(74,222,128,0.7)";
      el.style.color = "#bbf7d0";
      el.innerHTML = `<span style="width:10px;height:10px;border-radius:50%;background:#22c55e;"></span><span>${msg || "QR scanned successfully. Logging in..."}</span>`;
      el.style.display = "flex";
    } else if (state === "error") {
      el.style.background = "rgba(248,113,113,0.24)";
      el.style.border = "1px solid rgba(252,165,165,0.7)";
      el.style.color = "#fecaca";
      el.innerHTML = `<span style="width:10px;height:10px;border-radius:50%;background:#f87171;"></span><span>${msg || "Fix the position of the QR to scan properly."}</span>`;
      el.style.display = "flex";
    } else {
      el.style.display = "none";
    }
  }

  function setError(el, msg) {
    if (!el) return;
    el.textContent = msg || "";
    el.style.display = msg ? "block" : "none";
  }

  async function startScanner() {
    if (scanning || !window.Html5Qrcode || !readerEl) return;
    try {
      setError(qrError, "");
      setError(loginError, "");
      readerEl.innerHTML = "";
      scanner = new Html5Qrcode("loginQrReader");
      await scanner.start(
        { facingMode: "environment" },
        { fps: 12, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
        onScanSuccess,
        () => {}
      );
      scanning = true;
      setStatus("scanning", "Scanning... Align QR within the frame.");
    } catch (e) {
      setError(qrError, "Camera access failed or not available.");
      setStatus("error", "Fix the position of the QR to scan properly.");
    }
  }

  async function stopScanner() {
    if (!scanner || !scanning) return;
    try {
      await scanner.stop();
      scanner.clear();
    } catch {}
    scanning = false;
    setStatus("none");
  }

  async function onScanSuccess(decodedText) {
    setStatus("success", "QR scanned successfully. Logging in...");
    await stopScanner();
    try {
      const res = await fetch((typeof Auth !== "undefined" && Auth.API_BASE ? Auth.API_BASE : "https://localhost:8000") + "/auth/qr-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ qr_payload: decodedText }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(qrError, data.detail || "QR login failed");
        setStatus("error", "Fix the position of the QR to scan properly.");
        await startScanner();
        return;
      }
      if (data.access_token) {
        try {
          let part = data.access_token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
          while (part.length % 4) part += "=";
          const payload = JSON.parse(atob(part));
          sessionStorage.setItem("hr_session", JSON.stringify({
            token: data.access_token,
            userId: payload.sub,
            username: payload.username,
            role: payload.role,
            employeeId: payload.emp || payload.employee_id,
          }));
        } catch {}
        document.body.classList.add("authenticated");
        const loginScreen = document.getElementById("loginScreen");
        if (loginScreen) loginScreen.style.display = "none";
        window.location.reload();
      } else {
        setError(qrError, "Invalid login response");
        setStatus("error", "Fix the position of the QR to scan properly.");
        await startScanner();
      }
    } catch (e) {
      setError(qrError, e.message || "Network error");
      setStatus("error", "Fix the position of the QR to scan properly.");
      await startScanner();
    }
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", async () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const mode = tab.dataset.loginTab;
      if (mode === "creds") {
        creds.hidden = false;
        qrBox.hidden = true;
        await stopScanner();
        setStatus("none");
      } else {
        creds.hidden = true;
        qrBox.hidden = false;
        await startScanner();
      }
    });
  });

  if (stopBtn) {
    stopBtn.addEventListener("click", async () => {
      await stopScanner();
      setError(qrError, "Scanner stopped.");
      setStatus("error", "Fix the position of the QR to scan properly.");
    });
  }
})();
