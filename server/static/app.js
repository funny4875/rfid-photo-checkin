const form = document.querySelector("#checkin-form");
const input = document.querySelector("#student-id");
const machineSelect = document.querySelector("#machine-id");
const photo = document.querySelector("#student-photo");
const info = document.querySelector("#student-info");
const recordsList = document.querySelector("#records-list");
const deleteButton = document.querySelector("#delete-record");
const toggleRecordsButton = document.querySelector("#toggle-records");
const appShell = document.querySelector(".app-shell");
const rfidStatus = document.querySelector("#rfid-status");
const rfidStatusText = document.querySelector("#rfid-status-text");
let selectedIndex = null;
let lastRfidSequence = 0;
let rfidBusy = false;
let rfidInitialized = false;
const RFID_STATUS_URL = "/api/rfid/status";
let lockedMachineId = new URLSearchParams(window.location.search).get("machine_id") || "0";

async function loadLocations() {
  try {
    const response = await fetch("/api/locations");
    const data = await response.json();
    const locations = data.locations || [];
    if (!locations.some((location) => location.machine_id === lockedMachineId)) {
      lockedMachineId = locations[0]?.machine_id || "0";
    }
    machineSelect.innerHTML = "";
    locations.forEach((location) => {
      const option = document.createElement("option");
      option.value = location.machine_id;
      option.textContent = location.label;
      machineSelect.appendChild(option);
    });
    machineSelect.value = lockedMachineId;
  } catch (error) {
    machineSelect.value = lockedMachineId;
  } finally {
    machineSelect.disabled = true;
  }
}

function selectedDirection() {
  return document.querySelector("input[name='direction']:checked").value;
}

function renderStudent(student) {
  photo.src = student.photo_url;
  info.innerHTML = `
    <div><dt>UID</dt><dd>${student.record_uid}</dd></div>
    <div><dt>學號</dt><dd>${student.student_id}</dd></div>
    <div><dt>班級</dt><dd>${student.class_name}</dd></div>
    <div><dt>座號</dt><dd>${student.seat}</dd></div>
    <div><dt>姓名</dt><dd>${student.name}</dd></div>
  `;
}

function renderUnknownUid(uid) {
  photo.src = "/photo/noUID.jpg";
  info.innerHTML = `
    <div><dt>UID</dt><dd>${uid}</dd></div>
    <div><dt>學號</dt><dd>未建檔</dd></div>
    <div><dt>班級</dt><dd>-</dd></div>
    <div><dt>座號</dt><dd>-</dd></div>
    <div><dt>姓名</dt><dd>-</dd></div>
  `;
}

function setRfidStatus(text, mode = "") {
  rfidStatusText.textContent = text;
  rfidStatus.classList.toggle("ready", mode === "ready");
  rfidStatus.classList.toggle("active", mode === "active");
  rfidStatus.classList.toggle("error", mode === "error");
}

function renderRecords(records) {
  selectedIndex = null;
  deleteButton.disabled = true;
  recordsList.innerHTML = "";
  if (!records.length) {
    recordsList.innerHTML = '<div class="empty">目前沒有今日記錄</div>';
    return;
  }
  records.forEach((record) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "record-row";
    row.dataset.index = record.index;
    row.innerHTML = `
      <span>${record.time}</span>
      <strong>${record.student_id}</strong>
      <span>${record.class_name}</span>
      <span>${record.seat}</span>
      <span>${record.name}</span>
      <b>${record.direction}</b>
    `;
    row.addEventListener("click", () => {
      document.querySelectorAll(".record-row.selected").forEach((item) => item.classList.remove("selected"));
      row.classList.add("selected");
      selectedIndex = Number(record.index);
      deleteButton.disabled = false;
    });
    recordsList.appendChild(row);
  });
}

async function loadRecords() {
  const response = await fetch(`/api/records?machine_id=${machineSelect.value}`);
  const data = await response.json();
  renderRecords(data.records || []);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const studentId = input.value.trim();
  if (!studentId) return;
  const response = await fetch("/api/checkin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      student_id: studentId,
      machine_id: machineSelect.value,
      direction: selectedDirection(),
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    alert(data.error || "登記失敗");
    input.select();
    return;
  }
  renderStudent(data.student);
  renderRecords(data.records || []);
  input.value = "";
  input.focus();
});

async function checkinUid(card) {
  if (rfidBusy) return;
  rfidBusy = true;
  setRfidStatus(`讀到 UID ${card.uid_decimal}，正在登記`, "active");
  try {
    const response = await fetch("/api/checkin_uid", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        uid: card.uid_decimal,
        machine_id: machineSelect.value,
        direction: selectedDirection(),
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      renderUnknownUid(card.uid_decimal);
      renderRecords(data.records || []);
      setRfidStatus(`${data.error || "UID 登記失敗"}：${card.uid_decimal}`, "error");
      return;
    }
    renderStudent(data.student);
    renderRecords(data.records || []);
    input.value = "";
    input.focus();
    setRfidStatus(`已登記 ${data.student.name}（${card.uid_decimal}）`, "ready");
  } catch (error) {
    setRfidStatus(`RFID 登記失敗：${error.message}`, "error");
  } finally {
    rfidBusy = false;
  }
}

async function pollRfid() {
  try {
    const response = await fetch(RFID_STATUS_URL);
    const data = await response.json();
    if (!data.enabled) {
      setRfidStatus(data.error || "RFID 未啟用", "error");
      return;
    }
    if (data.error) {
      setRfidStatus(data.error, "error");
      return;
    }
    const readerText = data.readers?.length ? data.readers.join("、") : "尚未偵測到讀卡機";
    if (!rfidBusy) {
      setRfidStatus(readerText, data.readers?.length ? "ready" : "");
    }
    if (!rfidInitialized) {
      lastRfidSequence = data.sequence || 0;
      rfidInitialized = true;
      return;
    }
    if (data.last_card && data.last_card.sequence > lastRfidSequence) {
      lastRfidSequence = data.last_card.sequence;
      await checkinUid(data.last_card);
    }
  } catch (error) {
    const message =
      error.message === "Failed to fetch"
        ? "RFID 狀態讀取失敗：請確認 client.bat 視窗仍在執行，並可開啟 http://127.0.0.1:5055/health"
        : `RFID 狀態讀取失敗：${error.message}`;
    setRfidStatus(message, "error");
  }
}

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    form.requestSubmit();
  }
});

async function deleteSelected() {
  if (selectedIndex === null) return;
  const selected = document.querySelector(".record-row.selected");
  const label = selected ? selected.textContent.trim().replace(/\s+/g, " ") : "選取的記錄";
  if (!confirm(`確定刪除這筆今日記錄？\n${label}`)) return;
  const response = await fetch(`/api/records/${machineSelect.value}/${selectedIndex}`, { method: "DELETE" });
  const data = await response.json();
  if (!response.ok) {
    alert(data.error || "刪除失敗");
    return;
  }
  renderRecords(data.records || []);
  input.focus();
}

deleteButton.addEventListener("click", deleteSelected);
toggleRecordsButton.addEventListener("click", () => {
  const expanded = appShell.classList.toggle("records-expanded");
  toggleRecordsButton.textContent = expanded ? "縮小" : "放大";
  toggleRecordsButton.setAttribute("aria-pressed", String(expanded));
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Delete" && selectedIndex !== null) {
    deleteSelected();
  }
});
loadLocations().then(loadRecords);
setInterval(pollRfid, 500);
pollRfid();
