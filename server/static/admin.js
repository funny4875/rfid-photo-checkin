const statusText = document.querySelector("#admin-status");
const mergeButton = document.querySelector("#merge-now");
const archiveButton = document.querySelector("#archive-now");
const locationsList = document.querySelector("#locations-list");
const addLocationButton = document.querySelector("#add-location");
const saveLocationsButton = document.querySelector("#save-locations");
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
    <label>機台編號<input class="location-machine" inputmode="numeric" value="${machineId}"></label>
    <label>場域名稱<input class="location-label" value="${label}"></label>
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
loadAdminRecords();
