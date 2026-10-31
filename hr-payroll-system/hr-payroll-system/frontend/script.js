const DEFAULT_EMPLOYEES = [
  { id: "EMP-001", name: "Maria Clara Santos", dept: "Engineering", pos: "Senior Software Engineer", salary: 75000, status: "Active", tin: "234-567-890-000", sss: "34-5678901-2", phic: "12-345678901-2", hdmf: "1234-5678-9012" },
  { id: "EMP-002", name: "Juan Dela Cruz", dept: "Human Resources", pos: "HR & Payroll Specialist", salary: 38000, status: "Active", tin: "112-334-556-000", sss: "03-9876543-2", phic: "98-765432109-1", hdmf: "9876-5432-1098" },
  { id: "EMP-003", name: "Ana Maria Reyes", dept: "Finance", pos: "Senior Tax Accountant", salary: 48000, status: "Active", tin: "445-667-889-000", sss: "04-1122334-5", phic: "55-667788990-1", hdmf: "5566-7788-9900" },
  { id: "EMP-004", name: "Mark Antonio Torralba", dept: "Marketing", pos: "Digital Marketing Manager", salary: 52000, status: "On Leave", tin: "998-776-554-000", sss: "09-8877665-4", phic: "33-221100998-7", hdmf: "3322-1100-9987" },
  { id: "EMP-005", name: "Elena Bonifacio-Ramos", dept: "Engineering", pos: "QA Lead Engineer", salary: 62000, status: "Active", tin: "776-554-332-000", sss: "33-4455667-8", phic: "44-556677889-0", hdmf: "4455-6677-8899" },
  { id: "EMP-006", name: "Carlos Jose Mendoza", dept: "Engineering", pos: "Full Stack Developer", salary: 55000, status: "Active", tin: "887-665-443-000", sss: "12-3412341-2", phic: "66-778899001-2", hdmf: "6677-8899-0012" },
  { id: "EMP-007", name: "Beatriz Liza Gomez", dept: "Human Resources", pos: "HR Director", salary: 95000, status: "Active", tin: "334-221-556-000", sss: "01-9988776-5", phic: "11-223344556-7", hdmf: "1122-3344-5566" },
  { id: "EMP-008", name: "David Gabriel Lim", dept: "Finance", pos: "Financial Analyst", salary: 42000, status: "Active", tin: "556-443-221-000", sss: "02-8877665-1", phic: "88-990011223-4", hdmf: "8899-0011-2233" }
];

const DEFAULT_ATTENDANCE = [
  { empId: "EMP-001", name: "Maria Clara Santos", date: new Date().toISOString().slice(0, 10), timeIn: "08:02 AM", timeOut: "05:00 PM", status: "Present" },
  { empId: "EMP-002", name: "Juan Dela Cruz", date: new Date().toISOString().slice(0, 10), timeIn: "08:15 AM", timeOut: "05:03 PM", status: "Present" },
  { empId: "EMP-003", name: "Ana Maria Reyes", date: new Date().toISOString().slice(0, 10), timeIn: "07:55 AM", timeOut: "--", status: "Present" }
];

let employees = JSON.parse(localStorage.getItem("ph_hr_employees")) || DEFAULT_EMPLOYEES;
let attendance = JSON.parse(localStorage.getItem("ph_hr_attendance")) || DEFAULT_ATTENDANCE;

let payrollChartInstance = null;
let deptChartInstance = null;

// STATUTORY COMPUTATION ENGINES (PHILIPPINES)
function computeSSS(salary) {
  // SSS 2025/2026: 4.5% Employee share, MSC capped at ?35,000
  const msc = Math.min(Math.max(salary, 5000), 35000);
  const eeShare = msc * 0.045;
  const erShare = msc * 0.105;
  return { eeShare, erShare, msc };
}

function computePhilHealth(salary) {
  // PhilHealth 2025/2026: 5.0% split equally (2.5% EE share). Floor ?10,000; Cap ?100,000
  const base = Math.min(Math.max(salary, 10000), 100000);
  const eeShare = base * 0.025;
  const erShare = base * 0.025;
  return { eeShare, erShare };
}

function computePagIBIG(salary) {
  // Pag-IBIG: 2% capped at ?200 EE share
  const eeShare = Math.min(salary * 0.02, 200);
  const erShare = Math.min(salary * 0.02, 200);
  return { eeShare, erShare };
}

function computeBIRWithholdingTax(monthlyTaxableIncome) {
  // BIR TRAIN Law Progressive Monthly Tax Table
  if (monthlyTaxableIncome <= 20833.33) return 0;
  if (monthlyTaxableIncome <= 33333.33) return (monthlyTaxableIncome - 20833.33) * 0.15;
  if (monthlyTaxableIncome <= 66666.67) return 1875 + (monthlyTaxableIncome - 33333.33) * 0.20;
  if (monthlyTaxableIncome <= 166666.67) return 8541.67 + (monthlyTaxableIncome - 66666.67) * 0.25;
  if (monthlyTaxableIncome <= 666666.67) return 33541.67 + (monthlyTaxableIncome - 166666.67) * 0.30;
  return 183541.67 + (monthlyTaxableIncome - 666666.67) * 0.35;
}

function calculateEmployeePayroll(salary) {
  const sss = computeSSS(salary);
  const phic = computePhilHealth(salary);
  const hdmf = computePagIBIG(salary);

  const totalStatutoryNonTax = sss.eeShare + phic.eeShare + hdmf.eeShare;
  const taxableIncome = salary - totalStatutoryNonTax;
  const withholdingTax = computeBIRWithholdingTax(taxableIncome);

  const totalDeductions = totalStatutoryNonTax + withholdingTax;
  const netPay = salary - totalDeductions;

  return {
    gross: salary,
    sss: sss.eeShare,
    phic: phic.eeShare,
    hdmf: hdmf.eeShare,
    tax: withholdingTax,
    totalDeductions,
    netPay,
    sssEr: sss.erShare,
    phicEr: phic.erShare,
    hdmfEr: hdmf.erShare
  };
}

// DOM INITIALIZATION
const navBtns = document.querySelectorAll(".nav");
const pages = document.querySelectorAll(".page");
const pageTitle = document.getElementById("pageTitle");
const breadcrumb = document.getElementById("breadcrumb");

document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  setupEventListeners();
  setupRecruitmentAI();
  renderAll();
});

function setupNavigation() {
  navBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const pageId = btn.getAttribute("data-page");
      switchPage(pageId);
    });
  });
}

function switchPage(pageId) {
  navBtns.forEach(b => b.classList.remove("active"));
  pages.forEach(p => p.classList.remove("active"));

  if (pageId === "recruitment") {
    loadApplicantsFromDatabase();
  }

  const targetBtn = document.querySelector(`.nav[data-page="${pageId}"]`);
  const targetPage = document.getElementById(pageId);

  if (targetBtn) targetBtn.classList.add("active");
  if (targetPage) targetPage.classList.add("active");

  const titleText = targetBtn ? targetBtn.textContent.trim().replace(/^[^a-zA-Z]+/, '') : pageId;
  pageTitle.textContent = titleText;
  breadcrumb.textContent = `ENTERPRISE HR / ${titleText.toUpperCase()}`;

  renderAll();
}

function setupEventListeners() {
  document.querySelectorAll(".dashAddBtn").forEach(btn => {
    btn.addEventListener("click", () => openEmpModal());
  });

  document.getElementById("closeEmpModal").addEventListener("click", closeEmpModal);
  document.getElementById("empForm").addEventListener("submit", handleEmpSubmit);

  document.getElementById("closePersonnelModal").addEventListener("click", () => {
    document.getElementById("personnelModal").classList.remove("active");
  });

  document.getElementById("search").addEventListener("input", renderEmployeesTable);
  document.getElementById("clearSearch").addEventListener("click", () => {
    document.getElementById("search").value = "";
    renderEmployeesTable();
  });

  document.querySelectorAll(".viewAllBtn").forEach(btn => {
    btn.addEventListener("click", () => switchPage(btn.getAttribute("data-target")));
  });

  document.getElementById("refreshBtn").addEventListener("click", () => renderAll());
  document.getElementById("calcPayrollBtn").addEventListener("click", () => {
    alert("Philippine payroll recalculated with updated SSS, PhilHealth, Pag-IBIG, and TRAIN Law Tax tables.");
    renderPayroll();
  });
  document.getElementById("generateSlipBtn").addEventListener("click", generatePayslip);
  document.getElementById("printReportBtn").addEventListener("click", () => window.print());

  document.getElementById("timeInBtn").addEventListener("click", () => recordAttendance("Present"));
  document.getElementById("timeOutBtn").addEventListener("click", () => recordAttendance("Out"));
}

function getInitials(name) {
  return name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase();
}

function formatMoney(amount) {
  return "?" + Number(amount).toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function saveData() {
  localStorage.setItem("ph_hr_employees", JSON.stringify(employees));
  localStorage.setItem("ph_hr_attendance", JSON.stringify(attendance));
}

function renderAll() {
  saveData();
  renderStats();
  renderCharts();
  renderRecentTable();
  renderEmployeesTable();
  renderDepartments();
  renderPositions();
  renderAttendance();
  renderPayroll();
  renderSalary();
  renderThirteenthMonth();
  renderPayslipOptions();
  renderReports();
}

function renderStats() {
  const total = employees.length;
  const present = attendance.filter(a => a.date === new Date().toISOString().slice(0, 10)).length;
  const gross = employees.reduce((sum, e) => sum + Number(e.salary), 0);

  let totalStatutory = 0;
  employees.forEach(e => {
    const p = calculateEmployeePayroll(e.salary);
    totalStatutory += p.totalDeductions;
  });

  document.getElementById("sEmployees").textContent = total;
  document.getElementById("sPresent").textContent = present;
  document.getElementById("sPayroll").textContent = formatMoney(gross);
  document.getElementById("sStatutory").textContent = formatMoney(totalStatutory);
}

function renderCharts() {
  let totalNet = 0;
  let totalDeductions = 0;

  employees.forEach(e => {
    const p = calculateEmployeePayroll(e.salary);
    totalNet += p.netPay;
    totalDeductions += p.totalDeductions;
  });

  const ctx1 = document.getElementById("payrollChart").getContext("2d");
  if (payrollChartInstance) payrollChartInstance.destroy();

  payrollChartInstance = new Chart(ctx1, {
    type: "doughnut",
    data: {
      labels: ["Net Payout to Employees", "Statutory Deductions & Tax"],
      datasets: [{
        data: [totalNet, totalDeductions],
        backgroundColor: ["#0284c7", "#03203c"]
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" } }
    }
  });

  const deptCounts = {};
  employees.forEach(e => deptCounts[e.dept] = (deptCounts[e.dept] || 0) + 1);

  const ctx2 = document.getElementById("deptChartCanvas").getContext("2d");
  if (deptChartInstance) deptChartInstance.destroy();

  deptChartInstance = new Chart(ctx2, {
    type: "bar",
    data: {
      labels: Object.keys(deptCounts),
      datasets: [{
        label: "Headcount",
        data: Object.values(deptCounts),
        backgroundColor: "#0284c7"
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
    }
  });
}

function renderRecentTable() {
  const tbody = document.getElementById("recent");
  tbody.innerHTML = employees.slice(0, 4).map(e => `
    <tr>
      <td>
        <div class="user-cell">
          <div class="avatar sm">${getInitials(e.name)}</div>
          <strong>${e.name}</strong>
        </div>
      </td>
      <td>${e.dept}</td>
      <td>${e.pos}</td>
      <td>${formatMoney(e.salary)}</td>
      <th>Salary Basis</th>
      <td>${e.salary_basis || '-'}</td>
      <td><span class="status-badge ${e.status.toLowerCase().replace(' ', '')}">${e.status}</span></td>
    </tr>
  `).join("");
}

function renderEmployeesTable() {
  const query = document.getElementById("search").value.toLowerCase();
  const filtered = employees.filter(e => 
    e.name.toLowerCase().includes(query) || 
    e.dept.toLowerCase().includes(query) || 
    e.pos.toLowerCase().includes(query) ||
    (e.tin && e.tin.includes(query)) ||
    (e.sss && e.sss.includes(query))
  );

  const tbody = document.getElementById("employeesTable");
  tbody.innerHTML = filtered.map(e => `
    <tr>
      <td>${e.id}</td>
      <td>
        <div class="user-cell">
          <div class="avatar sm">${getInitials(e.name)}</div>
          <div>
            <strong>${e.name}</strong><br>
            <small style="color:#64748b;">TIN: ${e.tin || 'N/A'}</small>
          </div>
        </div>
      </td>
      <td>${e.dept}</td>
      <td>${e.pos}</td>
      <td>${formatMoney(e.salary)}</td>
      <th>Salary Basis</th>
      <td>${e.salary_basis || '-'}</td>
      <td><span class="status-badge ${e.status.toLowerCase().replace(' ', '')}">${e.status}</span></td>
      <td>
        <button class="link" onclick="editEmployee('${e.id}')">Edit</button> | 
        <button class="link" style="color:#ef4444;" onclick="deleteEmployee('${e.id}')">Delete</button>
      </td>
    </tr>
  `).join("");
}

function renderDepartments() {
  const grid = document.getElementById("departmentsList");
  const depts = {};
  employees.forEach(e => depts[e.dept] = (depts[e.dept] || 0) + 1);

  grid.innerHTML = Object.keys(depts).map(d => `
    <div class="info-card clickable" onclick="openPersonnelModal('Department', '${d}')">
      <span>DEPARTMENT</span>
      <strong>${d}</strong>
      <small>${depts[d]} Member(s) � View Personnel ?</small>
    </div>
  `).join("");
}

function renderPositions() {
  const tbody = document.getElementById("positionsTable");
  const posMap = {};
  employees.forEach(e => {
    if (!posMap[e.pos]) posMap[e.pos] = { dept: e.dept, count: 0 };
    posMap[e.pos].count++;
  });

  tbody.innerHTML = Object.keys(posMap).map(p => `
    <tr>
      <td><strong>${p}</strong></td>
      <td>${posMap[p].dept}</td>
      <td>${posMap[p].count} Member(s)</td>
      <td><button class="link" onclick="openPersonnelModal('Position', '${p}')">View Employees ?</button></td>
    </tr>
  `).join("");
}

window.openPersonnelModal = function(type, name) {
  const modal = document.getElementById("personnelModal");
  const eyebrow = document.getElementById("personnelModalEyebrow");
  const title = document.getElementById("personnelModalTitle");
  const tbody = document.getElementById("personnelModalBody");

  eyebrow.textContent = `${type.toUpperCase()} MEMBERS`;
  title.textContent = name;

  const filtered = employees.filter(e => type === "Department" ? e.dept === name : e.pos === name);

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#64748b;">No employees registered under this category.</td></tr>`;
  } else {
    tbody.innerHTML = filtered.map(e => `
      <tr>
        <td>
          <div class="user-cell">
            <div class="avatar sm">${getInitials(e.name)}</div>
            <strong>${e.name}</strong>
          </div>
        </td>
        <td>${e.id}</td>
        <td>${e.dept}</td>
        <td>${e.pos}</td>
        <td>${formatMoney(e.salary)}</td>
      <th>Salary Basis</th>
      <td>${e.salary_basis || '-'}</td>
        <td><span class="status-badge ${e.status.toLowerCase().replace(' ', '')}">${e.status}</span></td>
      </tr>
    `).join("");
  }

  modal.classList.add("active");
};

function renderAttendance() {
  const tbody = document.getElementById("attendanceTable");
  tbody.innerHTML = attendance.map(a => `
    <tr>
      <td>
        <div class="user-cell">
          <div class="avatar sm">${getInitials(a.name)}</div>
          <strong>${a.name}</strong>
        </div>
      </td>
      <td>${a.date}</td>
      <td>${a.timeIn}</td>
      <td>${a.timeOut}</td>
      <td><span class="status-badge active">${a.status}</span></td>
    </tr>
  `).join("");
}

function renderPayroll() {
  const isSemi = document.getElementById("payrollCycle").value === "semi";
  const factor = isSemi ? 0.5 : 1.0;

  let grossTotal = 0;
  let deductTotal = 0;

  const tbody = document.getElementById("payrollTable");
  tbody.innerHTML = employees.map(e => {
    const baseSalary = e.salary * factor;
    const p = calculateEmployeePayroll(baseSalary);

    grossTotal += p.gross;
    deductTotal += p.totalDeductions;

    return `
      <tr>
        <td>
          <div class="user-cell">
            <div class="avatar sm">${getInitials(e.name)}</div>
            <strong>${e.name}</strong>
          </div>
        </td>
        <td>${formatMoney(p.gross)}</td>
        <td style="color:#ef4444;">-${formatMoney(p.sss)}</td>
        <td style="color:#ef4444;">-${formatMoney(p.phic)}</td>
        <td style="color:#ef4444;">-${formatMoney(p.hdmf)}</td>
        <td style="color:#ef4444;">-${formatMoney(p.tax)}</td>
        <td><strong>${formatMoney(p.netPay)}</strong></td>
      </tr>
    `;
  }).join("");

  document.getElementById("gross").textContent = formatMoney(grossTotal);
  document.getElementById("deduct").textContent = formatMoney(deductTotal);
  document.getElementById("net").textContent = formatMoney(grossTotal - deductTotal);
}

function renderSalary() {
  const tbody = document.getElementById("salaryTable");
  tbody.innerHTML = employees.map(e => {
    const daily = e.salary / 26;
    const semi = e.salary / 2;
    return `
      <tr>
        <td>
          <div class="user-cell">
            <div class="avatar sm">${getInitials(e.name)}</div>
            <strong>${e.name}</strong>
          </div>
        </td>
        <td>${e.dept}</td>
        <td>${e.pos}</td>
        <td><strong>${formatMoney(e.salary)}</strong></td>
        <td>${formatMoney(semi)}</td>
        <td>${formatMoney(daily)}</td>
      </tr>
    `;
  }).join("");
}

function renderThirteenthMonth() {
  const tbody = document.getElementById("thirteenthTable");
  tbody.innerHTML = employees.map(e => {
    const monthsWorked = 12; 
    const annualBasic = e.salary * monthsWorked;
    const thirteenthPay = annualBasic / 12;
    const isExempt = thirteenthPay <= 90000;

    return `
      <tr>
        <td>
          <div class="user-cell">
            <div class="avatar sm">${getInitials(e.name)}</div>
            <strong>${e.name}</strong>
          </div>
        </td>
        <td>${monthsWorked} Months</td>
        <td>${formatMoney(annualBasic)}</td>
        <td><strong>${formatMoney(thirteenthPay)}</strong></td>
        <td><span class="status-badge ${isExempt ? 'active' : 'leave'}">${isExempt ? 'Tax Exempt (= ?90k)' : 'Taxable Excess'}</span></td>
      </tr>
    `;
  }).join("");
}

function renderPayslipOptions() {
  const select = document.getElementById("slipEmployee");
  select.innerHTML = employees.map(e => `<option value="${e.id}">${e.name} (${e.id})</option>`).join("");
  document.getElementById("slipMonth").value = new Date().toISOString().slice(0, 7);
}

function renderReports() {
  let sssTot = 0, phicTot = 0, hdmfTot = 0, birTot = 0;

  employees.forEach(e => {
    const p = calculateEmployeePayroll(e.salary);
    sssTot += (p.sss + p.sssEr);
    phicTot += (p.phic + p.phicEr);
    hdmfTot += (p.hdmf + p.hdmfEr);
    birTot += p.tax;
  });

  document.getElementById("rSSS").textContent = formatMoney(sssTot);
  document.getElementById("rPhic").textContent = formatMoney(phicTot);
  document.getElementById("rHdmf").textContent = formatMoney(hdmfTot);
  document.getElementById("rBir").textContent = formatMoney(birTot);
}

// MODAL & HANDLERS
function openEmpModal(emp = null) {
  const modal = document.getElementById("empModal");
  const title = document.getElementById("modalTitle");
  const deptSelect = document.getElementById("empDept");

  const depts = ["Engineering", "Human Resources", "Finance", "Marketing"];
  deptSelect.innerHTML = depts.map(d => `<option value="${d}">${d}</option>`).join("");

  if (emp) {
    title.textContent = "Edit Employee";
    document.getElementById("empId").value = emp.id;
    document.getElementById("empName").value = emp.name;
    document.getElementById("empDept").value = emp.dept;
    document.getElementById("empPos").value = emp.pos;
    document.getElementById("empSalary").value = emp.salary;
    document.getElementById("empTin").value = emp.tin || "";
    document.getElementById("empSss").value = emp.sss || "";
    document.getElementById("empPhic").value = emp.phic || "";
    document.getElementById("empHdmf").value = emp.hdmf || "";
    document.getElementById("empStatus").value = emp.status;
  } else {
    title.textContent = "Add New Employee";
    document.getElementById("empForm").reset();
    document.getElementById("empId").value = "";
  }

  modal.classList.add("active");
}

function closeEmpModal() {
  document.getElementById("empModal").classList.remove("active");
}

function handleEmpSubmit(e) {
  e.preventDefault();
  const id = document.getElementById("empId").value;
  const name = document.getElementById("empName").value;
  const dept = document.getElementById("empDept").value;
  const pos = document.getElementById("empPos").value;
  const salary = Number(document.getElementById("empSalary").value);
  const tin = document.getElementById("empTin").value;
  const sss = document.getElementById("empSss").value;
  const phic = document.getElementById("empPhic").value;
  const hdmf = document.getElementById("empHdmf").value;
  const status = document.getElementById("empStatus").value;

  if (id) {
    const idx = employees.findIndex(e => e.id === id);
    if (idx !== -1) employees[idx] = { id, name, dept, pos, salary, tin, sss, phic, hdmf, status };
  } else {
    const newId = `EMP-00${employees.length + 1}`;
    employees.push({ id: newId, name, dept, pos, salary, tin, sss, phic, hdmf, status });
  }

  closeEmpModal();
  renderAll();
}

window.editEmployee = function(id) {
  const emp = employees.find(e => e.id === id);
  if (emp) openEmpModal(emp);
};

window.deleteEmployee = function(id) {
  if (confirm("Are you sure you want to remove this employee record?")) {
    employees = employees.filter(e => e.id !== id);
    renderAll();
  }
};

function recordAttendance(type) {
  const emp = employees[0];
  const today = new Date().toISOString().slice(0, 10);
  const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  const existing = attendance.find(a => a.empId === emp.id && a.date === today);
  if (existing) {
    if (type === "Out") existing.timeOut = time;
  } else {
    attendance.unshift({ empId: emp.id, name: emp.name, date: today, timeIn: time, timeOut: "--", status: "Present" });
  }

  renderAll();
  alert(`Attendance logged for ${emp.name}`);
}

function generatePayslip() {
  const empId = document.getElementById("slipEmployee").value;
  const month = document.getElementById("slipMonth").value;
  const emp = employees.find(e => e.id === empId);

  if (!emp) return;

  const p = calculateEmployeePayroll(emp.salary);

  const slipContainer = document.getElementById("slip");
  slipContainer.innerHTML = `
    <div class="payslip-card">
      <div class="payslip-header">
        <div>
          <h2 style="color:var(--sidebar-bg);">ENTERPRISE HR PHILIPPINES INC.</h2>
          <small>OFFICIAL STATUTORY PAYSLIP � ${month}</small>
        </div>
        <div style="text-align:right;">
          <strong>ID: ${emp.id}</strong>
          <p style="font-size:12px; color:#64748b;">Status: ${emp.status}</p>
        </div>
      </div>
      <div class="payslip-grid">
        <div>
          <p style="margin-bottom:4px;"><strong>Employee Name:</strong> ${emp.name}</p>
          <p style="margin-bottom:4px;"><strong>Department:</strong> ${emp.dept}</p>
          <p style="margin-bottom:4px;"><strong>Position Title:</strong> ${emp.pos}</p>
          <hr style="margin: 10px 0; border:0; border-top: 1px solid #e2e8f0;">
          <p style="font-size:11px; color:#64748b;">TIN: ${emp.tin || 'N/A'}</p>
          <p style="font-size:11px; color:#64748b;">SSS No: ${emp.sss || 'N/A'}</p>
          <p style="font-size:11px; color:#64748b;">PhilHealth No: ${emp.phic || 'N/A'}</p>
          <p style="font-size:11px; color:#64748b;">Pag-IBIG No: ${emp.hdmf || 'N/A'}</p>
        </div>
        <div class="payslip-calc">
          <div style="display:flex; justify-content:space-between; margin-bottom: 8px;">
            <span>Basic Monthly Gross:</span>
            <strong>${formatMoney(p.gross)}</strong>
          </div>
          <div style="font-size:11px; color:#64748b; margin-bottom: 4px;">STATUTORY DEDUCTIONS:</div>
          <div style="display:flex; justify-content:space-between; margin-bottom: 4px; color:#ef4444; font-size:12px;">
            <span>SSS Employee Share:</span>
            <span>-${formatMoney(p.sss)}</span>
          </div>
          <div style="display:flex; justify-content:space-between; margin-bottom: 4px; color:#ef4444; font-size:12px;">
            <span>PhilHealth EE Share:</span>
            <span>-${formatMoney(p.phic)}</span>
          </div>
          <div style="display:flex; justify-content:space-between; margin-bottom: 4px; color:#ef4444; font-size:12px;">
            <span>Pag-IBIG EE Share:</span>
            <span>-${formatMoney(p.hdmf)}</span>
          </div>
          <div style="display:flex; justify-content:space-between; margin-bottom: 4px; color:#ef4444; font-size:12px;">
            <span>BIR TRAIN Tax:</span>
            <span>-${formatMoney(p.tax)}</span>
          </div>
          <hr style="margin: 10px 0; border:0; border-top: 1px solid #cbd5e1;">
          <div style="display:flex; justify-content:space-between; font-size: 16px;">
            <strong>NET TAKE-HOME PAY:</strong>
            <strong style="color:var(--accent-blue);">${formatMoney(p.netPay)}</strong>
          </div>
        </div>
      </div>
      <button class="primary" onclick="window.print()">Print Official Payslip</button>
    </div>
  `;
}

// ==========================================
// RECRUITMENT & AI RESUME PARSER INTEGRATION
// ==========================================
let activeApiBase = window.location.hostname === "localhost" ? "https://localhost:8000" : "https://127.0.0.1:8000";
let cachedAuthToken = null;

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

async function getAdminToken() {
  if (cachedAuthToken) return cachedAuthToken;
  const candidateUrls = [activeApiBase];
  for (const baseUrl of Array.from(new Set(candidateUrls))) {
    try {
      const res = await fetch(`${baseUrl}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: "admin", password: "Admin@123" })
      });
      if (res.ok) {
        const data = await res.json();
        cachedAuthToken = data.access_token;
        activeApiBase = baseUrl;
        return cachedAuthToken;
      }
    } catch (err) {
      // Try next candidate URL
    }
  }
  return null;
}

async function loadApplicantsFromDatabase() {
  const tbody = document.getElementById("applicantsTable");
  if (!tbody) return;
  try {
    const token = await getAdminToken();
    const res = await fetch(`${activeApiBase}/recruitment/applicants`, {
      headers: token ? { "Authorization": `Bearer ${token}` } : {}
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const applicants = await res.json();
    if (!applicants.length) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No applicants yet. Upload a resume above to parse with AI.</td></tr>`;
      return;
    }
    tbody.innerHTML = applicants.map(a => {
      const allSkills = a.skills || [];
      const topSkills = allSkills.slice(0, 3);
      const remainingCount = allSkills.length - 3;
      const allSkillsTooltip = allSkills.map(s => `${s.name} (${Math.round((s.confidence || 0.8) * 100)}%)`).join(", ");

      const skillsBadges = topSkills.map(s => 
        `<span style="background: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 6px; font-size: 11px; white-space: nowrap;">
          ${escapeHtml(s.name)} <strong>${Math.round((s.confidence || 0.8) * 100)}%</strong>
        </span>`
      ).join("");

      const moreBadge = remainingCount > 0 
        ? `<span title="${escapeHtml(allSkillsTooltip)}" style="background: #f1f5f9; color: var(--text-muted); padding: 2px 6px; border-radius: 6px; font-size: 11px; cursor: help; border: 1px solid #cbd5e1; white-space: nowrap;">+${remainingCount} more</span>` 
        : "";

      const skillsHtml = `<div style="display: flex; flex-wrap: wrap; gap: 4px; max-width: 260px;">${skillsBadges}${moreBadge}</div>`;

      const isHired = a.application_status === 'hired';
      const isRejected = a.application_status === 'rejected';

      let statusBadge = `<span class="badge" style="background:#e2e8f0; color:#334155;">Applied</span>`;
      if (isHired) {
        statusBadge = `<span class="badge active" style="background:#dcfce7; color:#166534;">? Hired</span>`;
      } else if (isRejected) {
        statusBadge = `<span class="badge" style="background:#fee2e2; color:#991b1b;">? Rejected</span>`;
      } else if (a.application_status === 'offer') {
        statusBadge = `<span class="badge" style="background:#fef3c7; color:#92400e;">Offer</span>`;
      }

      let actionHtml = `<span style="color:var(--text-muted); font-size:12px;">--</span>`;
      if (!isHired && !isRejected) {
        actionHtml = `
          <div style="display:flex; gap:6px;">
            <button class="primary" style="padding:4px 10px; font-size:11px; background:#16a34a;" onclick="openHireModal(${a.applicant_id}, '${escapeHtml(a.first_name + ' ' + a.last_name)}', ${a.job_id || 1})">? Hire</button>
            <button class="secondary" style="padding:4px 10px; font-size:11px; color:#ef4444; border-color:#fca5a5;" onclick="handleRejectCandidate(${a.applicant_id}, ${a.job_id || 1})">? Reject</button>
          </div>
        `;
      } else if (isHired) {
        actionHtml = `<strong style="color:#16a34a; font-size:12px;">Employee</strong>`;
      } else if (isRejected) {
        actionHtml = `<span style="color:#ef4444; font-size:12px;">Archived</span>`;
      }

      return `
        <tr>
          <td><strong>#${a.applicant_id}</strong></td>
          <td><strong>${escapeHtml(a.first_name)} ${escapeHtml(a.last_name)}</strong></td>
          <td style="max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(a.email)}">${escapeHtml(a.email)}</td>
          <td>${a.years_experience ? a.years_experience + ' yrs' : '--'}</td>
          <td>${statusBadge}</td>
          <td>${skillsHtml}</td>
          <td style="text-align: center;">${actionHtml}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: #ef4444;">Could not connect to FastAPI backend at ${activeApiBase}. Ensure uvicorn is running!</td></tr>`;
  }
}

// Global modal helpers
window.openHireModal = function(applicantId, candidateName, jobId) {
  const modal = document.getElementById("hireModal");
  if (!modal) return;
  document.getElementById("hireApplicantId").value = applicantId;
  document.getElementById("hireCandidateName").value = candidateName;
  const select = document.getElementById("hireJobSelect");
  if (select) select.value = String(jobId || 1);
  modal.style.display = "flex";
};

window.handleRejectCandidate = async function(applicantId, jobId) {
  if (!confirm("Are you sure you want to reject this candidate?")) return;
  try {
    const token = await getAdminToken();
    const res = await fetch(`${activeApiBase}/recruitment/reject`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": `Bearer ${token}` } : {})
      },
      body: JSON.stringify({
        applicant_id: applicantId,
        job_id: jobId || 1,
        reason: "Does not meet current role requirements"
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to reject candidate");
    alert("Candidate application marked as Rejected.");
    loadApplicantsFromDatabase();
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
};

function setupRecruitmentAI() {
  const parseBtn = document.getElementById("parseResumeBtn");
  const fileInput = document.getElementById("resumeFileInput");
  const statusText = document.getElementById("parseStatusText");
  const resultCard = document.getElementById("parsedResultCard");
  const refreshBtn = document.getElementById("refreshApplicantsBtn");

  if (refreshBtn) {
    refreshBtn.addEventListener("click", loadApplicantsFromDatabase);
  }

  if (parseBtn && fileInput) {
    parseBtn.addEventListener("click", async () => {
      const file = fileInput.files[0];
      if (!file) {
        alert("Please select a resume file (.pdf or .txt) first!");
        return;
      }

      parseBtn.disabled = true;
      parseBtn.innerHTML = `<img src="gemini_logo.png" class="gemini-loading-icon" style="width: 18px; height: 18px; object-fit: contain;" alt="Gemini" /> <span>Parsing with Gemini AI...</span>`;
      statusText.textContent = "Extracting text and analyzing candidate skills with Google Gemini AI...";
      statusText.style.color = "var(--accent-blue)";

      try {
        const token = await getAdminToken();
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch(`${activeApiBase}/recruitment/parse-resume`, {
          method: "POST",
          headers: token ? { "Authorization": `Bearer ${token}` } : {},
          body: formData
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || `Upload failed with status ${res.status}`);
        }

        // Show parsed result card
        resultCard.style.display = "block";
        document.getElementById("parsedName").textContent = `${data.first_name} ${data.last_name}`;
        document.getElementById("parsedEmail").textContent = data.email || "--";
        document.getElementById("parsedPhone").textContent = data.phone || "--";
        document.getElementById("parsedExp").textContent = data.years_experience ? `${data.years_experience} years` : "--";
        document.getElementById("parsedEducation").textContent = data.education || "--";

        const skillsContainer = document.getElementById("parsedSkillsContainer");
        skillsContainer.innerHTML = (data.skills || []).map(s => `
          <span style="background: #dcfce7; color: #166534; padding: 4px 10px; border-radius: 12px; font-size: 13px; font-weight: 500; border: 1px solid #bbf7d0;">
            ${escapeHtml(s.name)} <strong style="color: #15803d;">(${Math.round(s.confidence * 100)}%)</strong>
          </span>
        `).join("") || "<em>None detected</em>";

        statusText.textContent = "? Candidate details and skills successfully saved into PostgreSQL!";
        statusText.style.color = "#16a34a";
        fileInput.value = "";

        // Reload applicants table
        loadApplicantsFromDatabase();
      } catch (err) {
        console.error(err);
        statusText.textContent = `? Error: ${err.message}`;
        statusText.style.color = "#dc2626";
      } finally {
        parseBtn.disabled = false;
        parseBtn.innerHTML = `<img src="gemini_logo.png" style="width: 18px; height: 18px; object-fit: contain;" alt="Gemini" /> <span>Parse with Gemini API</span>`;
      }
    });
  }

  // Hire Modal Listeners
  const modal = document.getElementById("hireModal");
  const cancelHireBtn = document.getElementById("cancelHireBtn");
  const confirmHireBtn = document.getElementById("confirmHireBtn");
  const jobSelect = document.getElementById("hireJobSelect");
  const salaryInput = document.getElementById("hireSalaryInput");
  const salaryHint = document.getElementById("salaryRangeHint");

  if (jobSelect && salaryInput && salaryHint) {
    jobSelect.addEventListener("change", () => {
      const opt = jobSelect.selectedOptions[0];
      const min = Number(opt.getAttribute("data-min") || 30000);
      const max = Number(opt.getAttribute("data-max") || 80000);
      salaryInput.value = Math.round((min + max) / 2);
      salaryHint.textContent = `Salary must be between ?${min.toLocaleString()} and ?${max.toLocaleString()}`;
    });
  }

  if (cancelHireBtn && modal) {
    cancelHireBtn.addEventListener("click", () => {
      modal.style.display = "none";
    });
  }

  if (confirmHireBtn && modal) {
    confirmHireBtn.addEventListener("click", async () => {
      const applicantId = Number(document.getElementById("hireApplicantId").value);
      const candidateName = document.getElementById("hireCandidateName").value;
      const jobId = Number(document.getElementById("hireJobSelect").value);
      const salary = Number(document.getElementById("hireSalaryInput").value);

      if (!salary || salary <= 0) {
        alert("Please enter a valid base salary.");
        return;
      }

      confirmHireBtn.disabled = true;
      confirmHireBtn.textContent = "Processing Hire...";

      try {
        const token = await getAdminToken();
        const res = await fetch(`${activeApiBase}/recruitment/hire`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { "Authorization": `Bearer ${token}` } : {})
          },
          body: JSON.stringify({
            applicant_id: applicantId,
            job_id: jobId,
            base_salary: salary,
            hire_date: new Date().toISOString().slice(0, 10)
          })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to hire applicant");

        modal.style.display = "none";
        alert(`?? Success! ${candidateName} has been officially hired as Employee #${data.new_employee_id} via PostgreSQL stored procedure sp_hire_applicant()!`);

        // Add to local employee list so they immediately show on Employees and Dashboard pages!
        const deptName = jobId === 2 ? "Human Resources" : "Engineering";
        const posTitle = jobId === 2 ? "HR Officer" : "Software Developer";
        const newEmpCode = `EMP-${1000 + Number(data.new_employee_id)}`;

        employees.unshift({
          id: newEmpCode,
          name: candidateName,
          dept: deptName,
          pos: posTitle,
          salary: salary,
          status: "Active",
          tin: "100-200-300-000",
          sss: "11-2233445-5",
          phic: "12-345678901-2",
          hdmf: "1234-5678-9012"
        });

        saveData();
        renderAll();
        loadApplicantsFromDatabase();
      } catch (err) {
        alert(`? Hire Error: ${err.message}`);
      } finally {
        confirmHireBtn.disabled = false;
        confirmHireBtn.textContent = "Confirm Hire";
      }
    });
  }
}