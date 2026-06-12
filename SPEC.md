# RFID Photo Check-in 規格

## 1. 專案目標

RFID Photo Check-in 是一套校園門禁/出勤登記系統，用於在前台快速核對學生照片與資料，並依場域記錄刷進/刷出。系統支援人工輸入學號登記、ACR122U RFID 讀卡自動登記、前台照片核對、後台資料維護、今日記錄整併與歸檔，以及啟動時 GitHub 版本檢查與更新。

目前版本由根目錄 `VERSION` 控制，前後端 UI 皆需顯示或可取得版本資訊。

## 2. 專案結構

```text
client/        前端 ACR122U 讀卡代理與 GUI
server/        Flask 後端、前台/後台網頁、API
scripts/       更新檢查腳本
client.bat     啟動前端 GUI
server.bat     啟動後端 GUI
README.md      使用說明
DEPLOY.md      部署流程
SPEC.md        本規格文件
VERSION        版本序號
```

含個資或本機執行資料不得放入 Git：

- `server/student_data.txt`
- `server/ccsh_data/`
- `server/backups/`
- `server/門禁記錄*.txt`
- `server/<西元年份>/`
- `client/config.txt`
- log、cache、preview 截圖

## 3. 執行環境與啟動

後端主機放學生資料、照片、網頁、API 與門禁記錄檔。執行 `server.bat` 後，流程為：

1. 呼叫 `scripts/check_update.ps1` 檢查 GitHub 更新。
2. 安裝 `server/requirements.txt` 所需套件。
3. 開啟 `server/server_gui.py`。
4. 顯示標題為 `門禁網頁伺服器` 的 GUI。
5. GUI 列出本機可用 IPv4 位址，使用者需選擇一個 IP。
6. 按 `啟動` 後，Flask server 只綁定所選 IP。
7. 啟動後 GUI 的 `網頁網址` 唯讀欄位需顯示完整 URL，例如 `http://210.70.250.152:5000`，並允許選取複製。
8. 選擇的綁定 IP 儲存在 `server/config.txt`；下次開啟時若該 IP 仍在可用清單中，需自動選為預設。
9. 已儲存 IP 不再可用時，需退回目前第一個可用 IP。
10. server 執行期間不可切換綁定 IP；停止後可重新選擇。
11. 按 `停止` 後關閉 Flask server，`網頁網址` 顯示為尚未啟動。

後端服務位址：

```text
http://後端主機IP:5000
```

前端主機接 ACR122U 讀卡機。執行 `client.bat` 後，流程為：

1. 檢查 GitHub 更新。
2. 開啟 `client/client_ui.py`。
3. 使用者選擇場域、輸入後端主機 IP。
4. 按 `伺服器連線`，GUI 顯示 `伺服器連線中，請稍後 ...`。
5. 連線成功後停用 `伺服器連線`，並啟用 `網頁連線`。
6. 按 `網頁連線` 後啟動本機代理 `http://127.0.0.1:5055/`。
7. Chrome 開啟本機代理頁面。

修改伺服器 IP 後必須重設已連線狀態、停用 `網頁連線`，並要求重新執行 `伺服器連線`。

若無法連線到 `client/config.txt` 中已儲存的預設伺服器 IP，client GUI 需顯示「連線不上伺服器，是否重新輸入伺服器 IP？」；使用者同意後清空 IP 欄位並聚焦輸入框。

前端設定寫入：

```text
client/config.txt
```

## 4. 前後端資料流

ACR122U 接在前端主機，因此瀏覽器前台需透過本機代理取得 RFID 狀態。

```text
ACR122U -> client/client_agent.py -> Chrome -> server/app.py -> 門禁記錄檔
```

一般網頁與 API 由 `client_agent.py` 轉送到後端 server；`/api/rfid/status` 由前端本機代理直接回傳讀卡狀態。

## 5. 場域設定

場域設定檔固定為：

```text
server/場域對應.txt
```

格式為 tab 分隔：

```text
0	警衛室
1	教官室
2	總務處
```

規則：

- 機台編號必須是數字。
- 場域名稱不可空白。
- 至少需保留一個場域。
- 後台可新增、刪除、儲存場域。
- client GUI 讀取 `/api/locations` 後顯示場域名稱。
- 使用者在 client GUI 啟動網頁後，前台不得再切換機台。

## 6. 學生資料

學生資料檔固定為：

```text
server/student_data.txt
```

檔案為 tab 分隔，欄位固定如下：

```text
編號	UID	學號	座號	班級	姓名
```

規則：

- 不使用身份證欄位。
- 登記時以 `學號` 查詢學生。
- RFID 登記時以 `UID` 查詢學生。
- `UID` 空白或 `?????:?????` 時，門禁記錄中的卡片 UID 顯示為 `?`。
- 座號顯示與記錄格式需補上 `號`。

## 7. 學生資料 Excel 匯入與回復

後台 `/admin` 的 `學生資料更新` 區塊需提供：

- `上傳更新學生資料`
- `下載學生資料excel格式`
- `回復上一版的資料`

Excel 範本由 `/api/admin/student-template` 產生，工作表名稱為 `學生資料`，欄位為 `編號, UID, 學號, 座號, 班級, 姓名`，不包含身份證欄位。

上傳 `.xlsx` 成功前，系統將目前 `student_data.txt` 備份為：

```text
server/backups/student_data_previous.txt
```

備份只保留最近一次。匯入成功後覆寫 `server/student_data.txt`。

回復規則：

- 只有有上一版備份且尚未回復時可按。
- 回復成功後會鎖定，不可連續回復。
- 需重新上傳一次學生資料後，才可再次回復。

## 8. 學生照片與 ZIP 匯入

學生照片固定放在：

```text
server/ccsh_data/
```

找不到學生照片時顯示：

```text
server/noPicture.jpg
```

RFID UID 未建檔時顯示：

```text
server/noUID.jpg
```

照片路徑不可再由文字檔設定；目前固定為原本 `ccsh_data` 位置。

後台另有 `學生照片更新` 介面：

- 核取方塊：`上傳新照片後刪除舊照片`
- 按鈕：`上傳照片ZIP`

ZIP 匯入規則：

- ZIP 內照片檔名需符合 `<學號>.jpg` 或 `<學號>.jpeg`。
- ZIP 內可有子資料夾，但系統只取檔名，不保留子資料夾結構。
- 系統只匯入符合格式的照片。
- 若勾選刪除舊照片，系統先驗證 ZIP 內有有效照片，再清空 `server/ccsh_data/`。
- 解壓後新照片會取代同名舊照片。
- 匯入後清除照片 token 與流量限制暫存狀態。
- 清空舊照片時，目標資料夾名稱必須是 `ccsh_data`。
- 不接受 ZIP 內任意路徑寫入，避免 zip-slip。

## 9. 照片與學生資料安全

照片不得只靠猜 URL 取得。

- `/photo/ccsh_data/<學號>.jpg` 直接開啟時應回 `404`。
- 前台查詢學生或刷卡成功後，後端才簽發短效照片 token。
- token 有效時間為 60 秒。
- token 最多可使用 3 次。
- token 只對指定照片檔名有效。
- 預設圖片 `noPicture.jpg` 與 `noUID.jpg` 可直接提供。

大量下載阻擋：

- 依來源 IP 統計照片請求。
- 60 秒內超過 120 次照片請求時，封鎖 5 分鐘。
- 無 token 或錯 token 的照片請求也會計入。
- 封鎖時照片路由回 `429`。

學生資料保護：

- 不得提供任何 HTTP 或 FTP 介面下載 `student_data.txt`。
- 不得提供任何 HTTP 或 FTP 介面下載 `server/backups/` 備份檔。
- `/photo` 路由只允許白名單照片檔與預設圖。
- `student_data.txt`、照片資料夾、備份、門禁記錄均不得提交 Git。

## 10. 前台功能

前台 `/` 需提供：

- 學號輸入框。
- 學生照片顯示。
- 學生資料顯示。
- `刷進` / `刷出` 選項。
- 今日記錄列表。
- 刪除選取記錄。
- 今日記錄列表放大/縮小。
- RFID 狀態顯示。

人工登記流程：

1. 使用者輸入學號。
2. 按 Enter 送出。
3. 後端查詢學生資料。
4. 存在時顯示學生資料與照片，寫入今日門禁記錄。
5. 不存在時顯示錯誤，不寫入記錄。

RFID 登記流程：

1. `client_agent.py` 偵測 ACR122U。
2. 讀到卡片後取得 UID。
3. UID 轉為十進位分段格式。
4. 前台輪詢 `/api/rfid/status` 取得最新卡片。
5. 前台呼叫 `/api/checkin_uid`。
6. 後端以 UID 查詢學生。
7. 存在時顯示學生資料與照片，寫入今日門禁記錄。
8. 不存在時顯示 `noUID.jpg` 與未建檔 UID，不寫入記錄。

## 11. 門禁記錄、刪除、整併與歸檔

單機台記錄檔名：

```text
server/門禁記錄<機台編號>_<YYYYMMDD>.txt
```

整併記錄檔名：

```text
server/門禁記錄_<YYYYMMDD>.txt
```

每筆資料為 tab 分隔：

```text
時間	卡片UID	學號	班級	座號	姓名	進/出
```

今日記錄刪除規則：

- 使用者需先選取一筆記錄。
- 可按 Delete 鍵或刪除按鈕。
- 刪除前需顯示確認訊息。
- 只允許刪除今日記錄。
- 只刪除目前機台的記錄。
- 一次只刪除一筆。

自動整併：

- 每天 `12:10` 執行。
- 讀取當日所有 `門禁記錄<機台編號>_<YYYYMMDD>.txt`。
- 合併後依時間排序。
- 輸出 `門禁記錄_<YYYYMMDD>.txt`。
- 不自動去重。

自動歸檔：

- 每天 `00:15` 執行。
- 找出超過 7 天的 `門禁記錄*.txt`。
- 移到年份資料夾，例如 `server/2026/`。

後台提供 `整併今日記錄` 與 `清理歸檔`。

## 12. 後台功能

後台 `/admin` 需提供：

- 今日各場域/機台記錄。
- 今日整併記錄。
- 手動整併。
- 手動歸檔。
- 場域設定。
- 學生資料 Excel 範本下載。
- 學生資料 Excel 上傳。
- 回復上一版學生資料。
- 學生照片 ZIP 上傳。

## 13. API 規格

主要 API：

- `GET /`
- `GET /admin`
- `GET /api/version`
- `GET /api/locations`
- `POST /api/checkin`
- `POST /api/checkin_uid`
- `GET /api/student/<student_id>`
- `GET /api/records?machine_id=<id>`
- `DELETE /api/records/<machine_id>/<index>`
- `GET /api/rfid/status`
- `GET /photo/<path>`

後台 API：

- `POST /api/admin/locations`
- `GET /api/admin/records`
- `POST /api/admin/merge`
- `POST /api/admin/archive`
- `GET /api/admin/student-template`
- `POST /api/admin/student-data/upload`
- `GET /api/admin/student-data/restore/status`
- `POST /api/admin/student-data/restore`
- `POST /api/admin/photos/upload`

## 14. 更新機制

`client.bat` 與 `server.bat` 啟動時都需執行：

```text
scripts/check_update.ps1
```

更新規則：

- 命令列需顯示正在連至 GitHub 檢查版本。
- 命令列需顯示 GitHub repo URL。
- 命令列需顯示目前版本。
- 可讀取遠端版本時，命令列需顯示 GitHub 版本。
- 已是最新時，命令列需明確顯示目前已是最新版本。
- 遠端 `VERSION` 需優先透過 GitHub Contents API 讀取，避免 raw 檔案快取造成版本落後。
- `check_update.ps1` 需使用 Windows PowerShell 可穩定讀取的 UTF-8 BOM 編碼。
- 更新腳本需先整理 `RepoRoot` 參數，避免多餘引號或空白造成路徑解析錯誤。
- 優先使用 Git 檢查 `origin/main`。
- 若本機落後且可 fast-forward，跳出對話框詢問是否更新。
- 更新完成後提示重新執行啟動檔。
- 若不是 Git repo 或無 Git，可用 GitHub ZIP fallback。
- 更新時需保留本機資料與設定。

必須保留/跳過：

- `server/student_data.txt`
- `server/ccsh_data/`
- `server/backups/`
- `server/場域對應.txt`
- `server/門禁記錄*.txt`
- `server/<西元年份>/`
- `client/config.txt`
- `server/config.txt`
- log、cache、preview 圖

## 15. 測試與驗證

基本語法檢查：

```powershell
python -m py_compile server\app.py server\server_gui.py client\client_ui.py client\client_agent.py client\acr122_reader.py
```

必要測試情境：

- 後端 GUI 可啟動與停止 server。
- `GET /api/version` 回傳 `VERSION`。
- 前台以學號登記成功。
- RFID UID 登記成功。
- UID 未建檔時顯示 `noUID.jpg` 且不寫記錄。
- 場域設定可新增、刪除、儲存。
- client GUI 可讀取場域並鎖定選擇。
- 今日記錄可選取、確認後刪除。
- 手動整併產生 `門禁記錄_<日期>.txt`。
- 手動歸檔會移動超過 7 天記錄。
- 學生 Excel 範本欄位正確且無身份證欄位。
- 上傳學生 Excel 後會備份上一版。
- 回復上一版後不可連續回復。
- 上傳照片 ZIP 可匯入 `<學號>.jpg`。
- 勾選刪除舊照片時會先清空 `server/ccsh_data`。
- 直接猜照片 URL 會失敗。
- API 簽發 token 後照片可顯示。
- 大量照片請求會被 429 阻擋。
- 任何 HTTP/FTP 介面都不可取得 `student_data.txt` 或備份檔。
- GitHub 更新檢查不會覆蓋本機個資資料。

## 16. 已決定事項

- Repo 名稱：`rfid-photo-checkin`。
- GitHub repo：`funny4875/rfid-photo-checkin`。
- 後端固定使用 Flask。
- 後端固定使用 GUI 啟動器。
- 前端需有 GUI，並由本機代理連接 ACR122U。
- 照片固定放在 `server/ccsh_data`。
- 學生資料固定放在 `server/student_data.txt`。
- 場域設定固定放在 `server/場域對應.txt`。
- Excel 學生資料格式不包含身份證欄位。
- 學生照片 ZIP 以 `<學號>.jpg` 為主要格式。
- `student_data.txt`、照片、門禁紀錄、備份不可上 GitHub。
