/* ==========================================================================
   QR Attendance: self-service badge + kiosk scanner.
   Loaded after attendance.js. Uses Auth.apiFetch against /api/attendance/*.
   ========================================================================== */
const QRAttendance = (() => {
  const el = (id) => document.getElementById(id);
  let kioskTimer = null;
  let kioskPayload = "";

  function msg(text, type = "success") {
    const box = el("qrMsg");
    if (!box) return;
    box.textContent = text || "";
    box.hidden = !text;
    box.className = `msg ${type}`;
  }

  function session() { return Auth.getSession(); }

  async function loadMyQR() {
    if (!session() || !session().employeeId) {
      el("qrPanel").hidden = true;
      el("qrNotLinked").hidden = false;
      return;
    }
    el("qrNotLinked").hidden = true;
    el("qrPanel").hidden = false;
    try {
      const data = await Auth.apiFetch("/api/attendance/qr/my-qr?mode=static");
      el("qrEmployee").textContent = data.employee_name;
      el("qrMode").textContent = data.mode === "dynamic" ? "Dynamic (refreshes)" : "Static badge";
      el("qrPayload").value = data.qr_payload || "";
      el("qrMeta").textContent = `Credential: ${data.credential_id} • Seq: ${data.seq} • Require PIN: ${data.require_pin ? "Yes" : "No"}`;
      el("qrWrap").hidden = !data.qr_payload;
    } catch (e) {
      msg(e.message, "error");
    }
  }

  function showQRText() {
    el("qrTextBox").hidden = false;
    el("qrPayload").focus();
    el("qrPayload").select();
  }

  async function copyQR() {
    try {
      await navigator.clipboard.writeText(el("qrPayload").value);
      msg("QR payload copied to clipboard.", "success");
    } catch {
      showQRText();
      msg("Select and copy the payload below.", "success");
    }
  }

  async function loadKiosks() {
    if (!Auth.isStaff()) {
      el("kioskAdmin").hidden = true;
      return;
    }
    el("kioskAdmin").hidden = false;
    try {
      const list = await Auth.apiFetch("/api/attendance/kiosks");
      const tbody = el("kioskTable");
      if (!tbody) return;
      if (!list.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty-row">No kiosks enrolled.</td></tr>`;
        return;
      }
      tbody.innerHTML = list.map(k => `
        <tr>
          <td>${esc(k.device_id)}</td>
          <td>${esc(k.label)}</td>
          <td>${esc(k.location || "-")}</td>
          <td>${esc(k.status)}</td>
          <td>${k.last_seen_at ? esc(k.last_seen_at) : "-"}</td>
          <td>${k.scan_count || 0}</td>
        </tr>
      `).join("");
    } catch (e) {
      msg(e.message, "error");
    }
  }

  async function enrollKiosk(e) {
    e.preventDefault();
    const err = el("kioskErr");
    err.textContent = "";
    try {
      const body = {
        device_id: el("kioskId").value.trim(),
        label: el("kioskLabel").value.trim(),
        location: el("kioskLoc").value.trim() || null,
      };
      const res = await Auth.apiFetch("/api/attendance/kiosks", { method: "POST", body });
      el("kioskKeyBox").hidden = false;
      el("kioskKey").value = res.api_key || "";
      el("kioskKeyMsg").textContent = "Save this key now: it is only shown once.";
      document.getElementById("kioskForm").reset();
      await loadKiosks();
      msg("Kiosk enrolled. Copy the device secret below.", "success");
    } catch (ex) {
      err.textContent = ex.message;
    }
  }

  function copyKey() {
    navigator.clipboard.writeText(el("kioskKey").value).catch(() => {});
    msg("Device secret copied.", "success");
  }

  function esc(v) {
    return String(v ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  async function startScan() {
    const payload = el("kioskScanInput").value.trim();
    if (!payload) { msg("Paste or scan a QR payload first.", "error"); return; }
    kioskPayload = payload;
    const hid = el("kioskDeviceId").value.trim();
    const hsec = el("kioskSecret").value.trim();
    if (!hid || !hsec) { msg("Set the kiosk device id and secret in the scanner panel.", "error"); return; }
    const headers = {"X-Device-Id": hid, "X-Device-Secret": hsec};
    try {
      const res = await Auth.apiFetch("/api/attendance/scan", { method: "POST", body: { qr_payload: payload }, headers });
      if (res.status === "pin_required") {
        el("kioskStep1").hidden = true;
        el("kioskStep2").hidden = false;
        el("kioskChallenge").value = res.challenge_id;
        el("kioskPin").value = "";
        el("kioskPin").focus();
        el("kioskScanMsg").textContent = res.message || "Enter your PIN.";
        el("kioskScanMsg").className = "msg success";
        el("kioskScanMsg").hidden = false;
      } else if (res.status === "punched") {
        el("kioskScanMsg").textContent = res.message || `${res.event_type} recorded for ${res.employee_name}.`;
        el("kioskScanMsg").className = "msg success";
        el("kioskScanMsg").hidden = false;
        el("kioskScanInput").value = "";
      }
    } catch (e) {
      el("kioskScanMsg").textContent = e.message;
      el("kioskScanMsg").className = "msg error";
      el("kioskScanMsg").hidden = false;
    }
  }

  async function confirmScan(e) {
    e.preventDefault();
    try {
      const res = await Auth.apiFetch("/api/attendance/scan/confirm", { method: "POST", body: { challenge_id: el("kioskChallenge").value, pin: el("kioskPin").value } });
      el("kioskStep2").hidden = true;
      el("kioskStep1").hidden = false;
      el("kioskScanMsg").textContent = res.message || `${res.event_type} recorded for ${res.employee_name}.`;
      el("kioskScanMsg").className = "msg success";
      el("kioskScanMsg").hidden = false;
      el("kioskScanInput").value = "";
    } catch (e) {
      el("kioskScanMsg").textContent = e.message;
      el("kioskScanMsg").className = "msg error";
      el("kioskScanMsg").hidden = false;
    }
  }

  function cancelPin() {
    el("kioskStep2").hidden = true;
    el("kioskStep1").hidden = false;
    el("kioskScanMsg").textContent = "";
    el("kioskScanMsg").hidden = true;
  }

  function init() {
    if (el("qrRefresh")) el("qrRefresh").addEventListener("click", loadMyQR);
    if (el("qrShowText")) el("qrShowText").addEventListener("click", showQRText);
    if (el("qrCopy")) el("qrCopy").addEventListener("click", copyQR);
    if (el("kioskEnrollForm")) el("kioskEnrollForm").addEventListener("submit", enrollKiosk);
    if (el("kioskKeyCopy")) el("kioskKeyCopy").addEventListener("click", copyKey);
    if (el("kioskScanBtn")) el("kioskScanBtn").addEventListener("click", startScan);
    if (el("kioskPinForm")) el("kioskPinForm").addEventListener("submit", confirmScan);
    if (el("kioskPinCancel")) el("kioskPinCancel").addEventListener("click", cancelPin);

    document.addEventListener("hr:login", () => {
      loadMyQR();
      loadKiosks();
    });
    document.addEventListener("hr:pagechange", (e) => {
      if (e.detail.page === "qr-attendance") loadMyQR();
      if (e.detail.page === "kiosk-admin") loadKiosks();
    });

    loadMyQR();
    loadKiosks();
  }

  document.addEventListener("DOMContentLoaded", init);
  return { loadMyQR, loadKiosks };
})();
