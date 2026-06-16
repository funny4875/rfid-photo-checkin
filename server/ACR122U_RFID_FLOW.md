# ACR122U RFID 自動登記流程記錄

記錄日期：2026-06-09

## 目的

將 ACR122U 讀卡機整合進出勤記錄系統。刷卡後系統會讀取 RFID UID，轉成資料庫使用的十進位分段格式，例如 `07937:26162`，再比對 `student_data.txt` 的 `UID` 欄位。

## 目前服務網址

```text
http://<伺服器IP>:5000
```

## 流程

1. 啟動 Flask 專案 `app.py`。
2. 系統在 Windows 背景啟動 ACR122U 讀卡執行緒。
3. 讀卡程式透過 Windows PC/SC WinSCard API 偵測讀卡機。
4. 使用者將卡片靠近 ACR122U。
5. 系統送出 APDU `FF CA 00 00 00` 讀取卡片 HEX UID。
6. 系統取 HEX UID 前 4 bytes，依舊版讀卡程式的 byte 順序轉成十進位分段 UID：

```text
第 4 byte + 第 3 byte : 第 2 byte + 第 1 byte
```

各段補成 5 碼，例如：

```text
HEX AABBCCDD -> 56780:48042
```

7. 前端輪詢 `/api/rfid/status`，取得最新刷卡事件。
8. 前端用目前選取的 `機台` 和 `刷進/刷出` 呼叫 `/api/checkin_uid`。
9. 後端用十進位分段 UID 比對 `student_data.txt` 的 `UID` 欄位。
10. 若 UID 匹配：
    - 顯示學生照片。
    - 顯示學生資料。
    - 呼叫既有 `write_record()` 寫入門禁記錄。
    - 更新今日記錄列表。
11. 若 UID 未建檔：
    - 顯示 `noUID.jpg`。
    - 顯示未建檔 UID。
    - 不寫入門禁記錄。

## 寫入記錄格式

寫入檔案：

```text
門禁記錄<機台編號>_<日期>.txt
```

範例：

```text
門禁記錄0_20260609.txt
```

每筆資料格式：

```text
時間	卡片UID	學號	班級	座號	姓名	進/出
```

## 新增與修改檔案

- `acr122_reader.py`
  - 新增 ACR122U 讀卡模組。
  - 使用 Windows WinSCard API，不依賴 Node 原生 PCSC 套件。
  - 提供讀卡機狀態、最後刷卡事件、HEX UID 與十進位分段 UID。

- `app.py`
  - 啟動 ACR122U 背景讀卡。
  - 新增 `load_students_by_uid()`。
  - 新增 `get_student_by_uid_or_none()`。
  - 新增 `POST /api/checkin_uid`。
  - 新增 `GET /api/rfid/status`。
  - 支援 `/photo/noUID.jpg`。

- `templates/index.html`
  - 新增 RFID 讀卡狀態列。

- `static/app.js`
  - 輪詢 RFID 狀態。
  - 偵測新刷卡事件後自動登記。
  - 匹配成功時顯示學生資料與照片。
  - 未建檔時顯示 UID 未建檔畫面。
  - 避免頁面重新整理後重複登記上一張卡。

- `static/style.css`
  - 新增 RFID 狀態列樣式。

- `SPEC.md`
  - 補上 RFID 自動登記流程規格。

## 驗證結果

- `python -m py_compile app.py acr122_reader.py` 通過。
- `/api/rfid/status` 可回傳讀卡機狀態。
- 已偵測到讀卡機：`ACS ACR122 0`。
- `/api/checkin_uid` 可用資料庫中既有 UID 成功匹配學生並寫入記錄。
- UID 未建檔時回傳 `UID 未建檔`，不寫入門禁記錄。
- 測試寫入的臨時記錄已移除。

## 注意事項

- 此讀卡整合目前使用 Windows WinSCard API，適用 Windows 環境。
- 若讀卡機未出現，請確認 ACR122U 驅動與 Windows Smart Card 服務是否正常。
- `student_data.txt` 中 UID 需使用十進位分段格式，例如 `33714:55657`。
- 若頁面有開多個分頁，可能會有多個前端同時輪詢 RFID 狀態；實際使用時建議只開一個前台登記頁面。
