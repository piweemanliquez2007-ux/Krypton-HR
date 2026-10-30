/* ==========================================================================
   Attendance page, connected to the backend API (PostgreSQL), not localStorage.
   Loaded AFTER script.js. It replaces script.js's old renderAttendance() and
   recordAttendance() (see the two small functions at the very bottom).

   Employee  : clock in / clock out, sees only their own records.
   Admin/HR  : sees everyone, can filter, add, edit and delete records.
   ========================================================================== */
const AttendanceModule = (() => {
  const STATUS_LABEL = { present: "Present", late: "Late", absent: "Absent", half_day: "Half day" };
  const STATUS_CLASS = { present: "active", late: "late", absent: "absent", half_day: "leave" };

  let rows = [];            // records currently shown in the table
  let myToday = null;       // my own record for today (or null)
  let editingId = null;     // null = adding, number = editing that record
  let messageTimer = null;

  // ----------------------------------------------------------------- helpers
  const el = (id) => document.getElementById(id);

  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }

  function ymd(date) {
    const p = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}`;
  }

  function fmtTime(t) {                         // "08:02:00" -> "8:02 AM"
    if (!t) return "--";
    const [h, m] = String(t).split(":");
    const hour = Number(h);
    return `${hour % 12 || 12}:${m} ${hour >= 12 ? "PM" : "AM"}`;
  }

  function initials(name) {
    return String(name || "?").trim().split(/\s+/).map(n => n[0]).join("").slice(0, 2).toUpperCase();
  }

  function showMessage(text, type) {
    const box = el("attMessage");
    if (!box) return;
    clearTimeout(messageTimer);
    if (!text) { box.hidden = true; return; }
    box.textContent = text;
    box.className = `msg ${type || "success"}`;
    box.hidden = false;
    messageTimer = setTimeout(() => { box.hidden = true; }, 7000);
  }

  function mySession() { return Auth.getSession(); }

  // -------------------------------------------------------------------- data
  let autoRefreshTimer = null;
  let autoRefreshEnabled = true;

  function setAutoRefreshStatus(active) {
    autoRefreshEnabled = active;
    const dot = el("autoRefreshDot");
    const text = el("autoRefreshText");
    if (dot) {
      dot.style.background = active ? "#16a34a" : "#94a3b8";
      dot.style.animation = active ? "pulse 2s infinite" : "none";
    }
    if (text) {
      text.textContent = active ? "Auto-refresh active (every 30s)" : "Auto-refresh paused";
    }
  }

  async function loadEmployeeOptions() {
    if (!Auth.isStaff()) return;
    try {
      const employees = await Auth.apiFetch("/employees?limit=200");
      const options = employees.map(e =>
        `<option value="${e.employee_id}">${esc(e.employee_no)} - ${esc(e.first_name)} ${esc(e.last_name)}</option>`
      ).join("");
      el("attEmployeeFilter").innerHTML = `<option value="">All employees</option>${options}`;
      el("attEmployee").innerHTML = options;
    } catch (e) {
      showMessage(e.message, "error");
    }
  }

  async function loadMyToday() {
    const session = mySession();
    myToday = null;
    if (session && session.employeeId) {
      const today = ymd(new Date());
      try {
        const found = await Auth.apiFetch(
          `/attendance?employee_id=${session.employeeId}&date_from=${today}&date_to=${today}&limit=1`
        );
        myToday = found[0] || null;
      } catch (e) { /* the table load reports errors */ }
    }
    updateTodayPanel();
  }

  async function load() {
    if (!mySession()) return;
    const params = new URLSearchParams({ limit: "200" });
    if (el("attDateFrom").value) params.set("date_from", el("attDateFrom").value);
    if (el("attDateTo").value) params.set("date_to", el("attDateTo").value);
    if (Auth.isStaff() && el("attEmployeeFilter").value) {
      params.set("employee_id", el("attEmployeeFilter").value);
    }
    try {
      rows = await Auth.apiFetch(`/attendance?${params}`);
      syncDashboardData();
      updateLastRefresh();
      render();
    } catch (e) {
      showMessage(e.message, "error");
    }
  }

  async function refreshAll() {
    await Promise.all([load(), loadMyToday()]);
  }

  // Real-time auto-refresh every 30 seconds when on attendance page
  function startAutoRefresh() {
    stopAutoRefresh();
    setAutoRefreshStatus(true);
    autoRefreshTimer = setInterval(() => {
      if (autoRefreshEnabled && document.querySelector('.nav[data-page="attendance"].active')) {
        refreshAll();
      }
    }, 30000); // 30 seconds
  }

  function stopAutoRefresh() {
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer);
      autoRefreshTimer = null;
    }
    setAutoRefreshStatus(false);
  }

  function updateLastRefresh() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const info = el("attTodayStatus");
    if (info) {
      info.setAttribute("data-last-refresh", timeStr);
    }
  }

  // Keep the dashboard's "clocked-in today" counter (script.js) in step with the database
  function syncDashboardData() {
    try {
      attendance = rows.map(r => ({
        empId: r.employee_id, name: r.employee_name, date: r.work_date,
        timeIn: fmtTime(r.time_in), timeOut: fmtTime(r.time_out),
        status: STATUS_LABEL[r.status] || r.status
      }));
      // Also update the dashboard stats in real-time
      if (typeof renderAll === 'function') {
        renderAll();
      }
    } catch (e) { /* dashboard counter is optional */ }
  }

  // ------------------------------------------------------------------ render
  function updateTodayPanel() {
    const info = el("attTodayStatus");
    const inBtn = el("timeInBtn");
    const outBtn = el("timeOutBtn");
    if (!info) return;
    const session = mySession();

    if (!session) {
      info.textContent = "Log in to view attendance.";
      inBtn.disabled = outBtn.disabled = true;
      return;
    }
    if (!session.employeeId) {
      info.textContent = "This account is not linked to an employee record, so clock-in is not available. HR can add records manually.";
      inBtn.disabled = outBtn.disabled = true;
      return;
    }
    if (!myToday) {
      info.textContent = "You have not clocked in today.";
      inBtn.disabled = false;
      outBtn.disabled = true;
    } else if (!myToday.time_out) {
      info.textContent = `Clocked in today at ${fmtTime(myToday.time_in)} (${STATUS_LABEL[myToday.status] || myToday.status}).`;
      inBtn.disabled = true;
      outBtn.disabled = false;
    } else {
      info.textContent = `Today: ${fmtTime(myToday.time_in)} to ${fmtTime(myToday.time_out)}, ${Number(myToday.hours_worked).toFixed(2)} hours.`;
      inBtn.disabled = outBtn.disabled = true;
    }
    // Show last refresh time
    const lastRefresh = info.getAttribute("data-last-refresh");
    if (lastRefresh) {
      const refreshSpan = document.createElement("small");
      refreshSpan.style.cssText = "display:block; color:#94a3b8; font-size:11px; margin-top:4px;";
      refreshSpan.textContent = `↻ Auto-refreshed at ${lastRefresh}`;
      if (!info.querySelector("small")) info.appendChild(refreshSpan);
    }
  }

  function render() {
    const tbody = el("attendanceTable");
    if (!tbody) return;

    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="8" class="empty-row">No attendance records for this period.</td></tr>`;
      return;
    }

    tbody.innerHTML = rows.map(r => `
      <tr>
        <td>
          <div class="user-cell">
            <div class="avatar sm">${esc(initials(r.employee_name))}</div>
            <strong>${esc(r.employee_name)}</strong>
          </div>
        </td>
        <td>${esc(r.work_date)}</td>
        <td>${fmtTime(r.time_in)}</td>
        <td>${fmtTime(r.time_out)}</td>
        <td>${Number(r.hours_worked).toFixed(2)}</td>
        <td>${Number(r.overtime_hours).toFixed(2)}</td>
        <td><span class="status-badge ${STATUS_CLASS[r.status] || "active"}">${esc(STATUS_LABEL[r.status] || r.status)}</span></td>
        <td class="staff-only">
          <button class="secondary small-btn" data-act="edit" data-id="${r.attendance_id}">Edit</button>
          <button class="danger small-btn" data-act="delete" data-id="${r.attendance_id}">Delete</button>
        </td>
      </tr>
    `).join("");
  }

  // ------------------------------------------------------- clock in / clock out
  async function clock(type) {
    const inBtn = el("timeInBtn");
    const outBtn = el("timeOutBtn");
    inBtn.disabled = outBtn.disabled = true;
    try {
      const path = type === "Out" ? "/attendance/clock-out" : "/attendance/clock-in";
      const record = await Auth.apiFetch(path, { method: "POST" });
      showMessage(
        type === "Out"
          ? `Clocked out at ${fmtTime(record.time_out)}. Hours worked: ${Number(record.hours_worked).toFixed(2)}.`
          : `Clocked in at ${fmtTime(record.time_in)} (${STATUS_LABEL[record.status] || record.status}).`,
        "success"
      );
    } catch (e) {
      showMessage(e.message, "error");
    }
    await refreshAll();       // also re-enables the correct buttons
  }

  // ------------------------------------------- add / edit / delete (Admin & HR)
  function openModal(record) {
    editingId = record ? record.attendance_id : null;
    el("attModalTitle").textContent = record ? "Edit Attendance Record" : "Add Attendance Record";
    el("attFormError").textContent = "";

    el("attEmployee").disabled = !!record;     // the API only lets you change times and status
    el("attDate").disabled = !!record;
    if (record) {
      el("attEmployee").value = String(record.employee_id);
      el("attDate").value = record.work_date;
      el("attTimeIn").value = record.time_in ? record.time_in.slice(0, 5) : "";
      el("attTimeOut").value = record.time_out ? record.time_out.slice(0, 5) : "";
      el("attStatus").value = record.status;
    } else {
      el("attForm").reset();
      el("attDate").value = ymd(new Date());
      el("attStatus").value = "present";
    }
    el("attModal").classList.add("active");
  }

  function closeModal() {
    el("attModal").classList.remove("active");
  }

  async function saveRecord(event) {
    event.preventDefault();
    const errorBox = el("attFormError");
    errorBox.textContent = "";
    const timeIn = el("attTimeIn").value || null;
    const timeOut = el("attTimeOut").value || null;

    if (timeIn && timeOut && timeOut < timeIn) {
      errorBox.textContent = "Time out must be after time in.";
      return;
    }
    try {
      if (editingId === null) {
        await Auth.apiFetch("/attendance", {
          method: "POST",
          body: {
            employee_id: Number(el("attEmployee").value),
            work_date: el("attDate").value,
            time_in: timeIn, time_out: timeOut, status: el("attStatus").value
          }
        });
        showMessage("Attendance record added.", "success");
      } else {
        await Auth.apiFetch(`/attendance/${editingId}`, {
          method: "PUT",
          body: { time_in: timeIn, time_out: timeOut, status: el("attStatus").value }
        });
        showMessage("Attendance record updated.", "success");
      }
      closeModal();
      await refreshAll();
    } catch (e) {
      errorBox.textContent = e.message;
    }
  }

  async function onTableClick(event) {
    const btn = event.target.closest("button[data-act]");
    if (!btn) return;
    const id = Number(btn.dataset.id);
    if (btn.dataset.act === "edit") {
      const record = rows.find(r => r.attendance_id === id);
      if (record) openModal(record);
    } else if (btn.dataset.act === "delete") {
      if (!confirm("Delete this attendance record? This cannot be undone.")) return;
      try {
        await Auth.apiFetch(`/attendance/${id}`, { method: "DELETE" });
        showMessage("Attendance record deleted.", "success");
        await refreshAll();
      } catch (e) {
        showMessage(e.message, "error");
      }
    }
  }

  // -------------------------------------------------------------------- init
  function resetFilters() {
    const now = new Date();
    el("attDateFrom").value = ymd(new Date(now.getFullYear(), now.getMonth(), 1));
    el("attDateTo").value = ymd(now);
    el("attEmployeeFilter").value = "";
  }

  function init() {
    resetFilters();
    el("attApplyBtn").addEventListener("click", load);
    el("attResetBtn").addEventListener("click", () => { resetFilters(); load(); });
    el("attAddBtn").addEventListener("click", () => openModal(null));
    el("attCancel").addEventListener("click", closeModal);
    el("attForm").addEventListener("submit", saveRecord);
    el("attendanceTable").addEventListener("click", onTableClick);
    el("refreshBtn").addEventListener("click", refreshAll);

    const navBtn = document.querySelector('.nav[data-page="attendance"]');
    if (navBtn) navBtn.addEventListener("click", () => {
      refreshAll();
      startAutoRefresh();
    });

    // Stop auto-refresh when leaving the attendance page
    document.addEventListener("hr:pagechange", (e) => {
      if (e.detail.page !== "attendance") {
        stopAutoRefresh();
      }
    });

    document.addEventListener("hr:login", async () => {
      resetFilters();
      await loadEmployeeOptions();
      await refreshAll();
      startAutoRefresh();
    });
    document.addEventListener("hr:logout", () => {
      rows = [];
      myToday = null;
      stopAutoRefresh();
      try { attendance = []; } catch (e) { /* ignore */ }
      render();
      updateTodayPanel();
    });

    // Initial auto-refresh start
    startAutoRefresh();

    render();
    updateTodayPanel();
  }

  document.addEventListener("DOMContentLoaded", init);

  return { render, clock };
})();

// These two replace the old localStorage versions defined in script.js
function renderAttendance() { AttendanceModule.render(); }
function recordAttendance(type) { AttendanceModule.clock(type); }
