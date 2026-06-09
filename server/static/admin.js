const statusText = document.querySelector("#admin-status");
const appVersion = document.querySelector("#app-version");
const mergeButton = document.querySelector("#merge-now");
const archiveButton = document.querySelector("#archive-now");
const locationsList = document.querySelector("#locations-list");
const addLocationButton = document.querySelector("#add-location");
const saveLocationsButton = document.querySelector("#save-locations");
const studentUploadForm = document.querySelector("#student-upload-form");
const studentFileInput = document.querySelector("#student-file");
const uploadStudentButton = document.querySelector("#upload-student-data");
const restoreStudentButton = document.querySelector("#restore-student-data");
const adminGrid = document.querySelector(".admin-grid");
const mergedArticle = document.querySelector(".merged");

function renderList(target, records) {
  target.innerHTML = "";
  if (!records.length) {
    target.innerHTML = '<div class="empty">目前沒有記錄</div>';
    return;
  }
  records.forEach((record) => {
    const row = document.createElement("div");
    row.className = "record-row readonly";
    row.innerHTML = `
      <span>${record.time}</span>
      <strong>${record.student_id}</strong>
      <span>${record.class_name}</span>
      <span>${record.seat}</span>
      <span>${record.name}</span>
      <b>${record.direction}</b>
    `;
    target.appendChild(row);
  });
}

function renderLocations(locations) {
  locationsList.innerHTML = "";
  locations.forEach((location) => addLocationRow(location.machine_id, location.label));
}

function addLocationRow(machineId = "", label = "") {
  const row = document.createElement("div");
  row.className = "location-row";
  row.innerHTML = `
    <label>機台編號<input class="location-machine" name="machine_id" inputmode="numeric" value="${machineId}"></label>
    <label>場域名稱<input class="location-label" name="location_label" value="${label}"></label>
    <button type="button">刪除</button>
  `;
  row.querySelector("button").addEventListener("click", () => row.remove());
  locationsList.appendChild(row);
}

function currentLocations() {
  return [...document.querySelectorAll(".location-row")]
    .map((row) => ({
      machine_id: row.querySelector(".location-machine").value.trim(),
      label: row.querySelector(".location-label").value.trim(),
    }))
    .filter((location) => location.machine_id && location.label);
}

function renderMachinePanels(locations, machines) {
  document.querySelectorAll(".machine-records").forEach((item) => item.remove());
  locations.forEach((location) => {
    const article = document.createElement("article");
    article.className = "machine-records";
    article.innerHTML = `
      <h2>${location.label}<small>機台${location.machine_id}</small></h2>
      <div class="records-list compact"></div>
    `;
    renderList(article.querySelector(".records-list"), machines[location.machine_id] || []);
    adminGrid.insertBefore(article, mergedArticle);
  });
}

async function loadAdminRecords() {
  const response = await fetch("/api/admin/records");
  const data = await response.json();
  renderLocations(data.locations || []);
  renderMachinePanels(data.locations || [], data.machines || {});
  renderList(document.querySelector("#merged-records"), data.merged || []);
}

async function loadVersion() {
  try {
    const response = await fetch("/api/version");
    const data = await response.json();
    appVersion.textContent = `v${data.version || "-"}`;
  } catch (_error) {
    appVersion.textContent = "v-";
  }
}

async function loadStudentRestoreStatus() {
  try {
    const response = await fetch("/api/admin/student-data/restore/status");
    const data = await response.json();
    restoreStudentButton.disabled = !data.can_restore;
    if (!data.backup_exists) {
      restoreStudentButton.title = "目前沒有上一版備份";
    } else if (data.already_restored) {
      restoreStudentButton.title = "已回復上一版，需重新上傳後才能再次回復";
    } else {
      restoreStudentButton.title = "將 student_data.txt 回復成最近一次上傳前的版本";
    }
  } catch (_error) {
    restoreStudentButton.disabled = true;
    restoreStudentButton.title = "無法讀取備份狀態";
  }
}

async function postAction(url, doneText) {
  statusText.textContent = "執行中...";
  const response = await fetch(url, { method: "POST" });
  const data = await response.json();
  if (!response.ok) {
    statusText.textContent = data.error || "執行失敗";
    return;
  }
  statusText.textContent = doneText;
  await loadAdminRecords();
}

async function saveLocations() {
  statusText.textContent = "儲存中...";
  const response = await fetch("/api/admin/locations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ locations: currentLocations() }),
  });
  const data = await response.json();
  if (!response.ok) {
    statusText.textContent = data.error || "儲存失敗";
    return;
  }
  statusText.textContent = "已儲存場域";
  await loadAdminRecords();
}

mergeButton.addEventListener("click", () => postAction("/api/admin/merge", "已完成整併"));
archiveButton.addEventListener("click", () => postAction("/api/admin/archive", "已完成歸檔"));
addLocationButton.addEventListener("click", () => addLocationRow());
saveLocationsButton.addEventListener("click", saveLocations);
uploadStudentButton.addEventListener("click", () => studentFileInput.click());
restoreStudentButton.addEventListener("click", async () => {
  if (!confirm("確定要回復上一版學生資料？回復後不能連續再回復。")) return;
  statusText.textContent = "回復學生資料中...";
  const response = await fetch("/api/admin/student-data/restore", { method: "POST" });
  const data = await response.json();
  if (!response.ok) {
    statusText.textContent = data.error || "回復失敗";
    await loadStudentRestoreStatus();
    return;
  }
  statusText.textContent = data.message || "已回復上一版學生資料";
  await loadStudentRestoreStatus();
});
studentFileInput.addEventListener("change", async () => {
  if (!studentFileInput.files.length) return;
  const formData = new FormData(studentUploadForm);
  statusText.textContent = "學生資料匯入中...";
  const response = await fetch("/api/admin/student-data/upload", {
    method: "POST",
    body: formData,
  });
  const data = await response.json();
  if (!response.ok) {
    statusText.textContent = data.error || "匯入失敗";
    studentUploadForm.reset();
    await loadStudentRestoreStatus();
    return;
  }
  statusText.textContent = `${data.message}，共 ${data.count} 筆`;
  studentUploadForm.reset();
  await loadStudentRestoreStatus();
});
loadAdminRecords();
loadVersion();
loadStudentRestoreStatus();
