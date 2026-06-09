# RFID Photo Check-in

RFID Photo Check-in 是一套校園門禁/出勤登記系統，支援 ACR122U 讀卡機、照片核對、場域別名管理與每日門禁紀錄整併。

目前版本：`1.1.10`

## 功能

- 後端 Flask server 提供前台、後台、照片與 API。
- 前端 Windows client 連接 ACR122U，讀取 RFID UID。
- client GUI 可選擇場域、輸入伺服器 IP，並開啟本機代理網頁。
- 前台顯示學生照片與資料，刷卡後自動寫入門禁紀錄。
- 後台可管理場域對應，例如 `機台0 = 警衛室`、`機台1 = 教官室`。
- 後台可下載學生資料 Excel 範本、上傳 Excel 更新 `student_data.txt`，並可回復最近一次備份。
- 每日紀錄支援手動/排程整併與歸檔。

## 專案結構

```text
client/        前端 ACR122U 讀卡代理與 GUI
server/        Flask 後端、前台/後台網頁、API
client.bat     啟動前端 GUI
server.bat     啟動後端 GUI
DEPLOY.md      部署流程
VERSION        版本序號
```

## 不放入 Git 的資料

以下資料含個資或屬於本機執行資料，已由 `.gitignore` 排除：

- `server/student_data.txt`
- `server/ccsh_data/`
- `server/門禁記錄*.txt`
- `client/config.txt`
- log、cache、preview 截圖

學生資料格式請參考：

```text
server/student_data.example.txt
server/student_data_template.xlsx
```

## 後端啟動

在後端主機執行：

```bat
server.bat
```

啟動時會先連到 GitHub 檢查是否有新版本；若有新版本，會跳出對話框詢問是否更新。
命令列會顯示目前版本、GitHub 版本，以及是否已是最新版本。

開啟後會出現「門禁網頁伺服器」視窗，按下「啟動」開始提供網頁服務，按下「停止」關閉服務。

預設服務：

```text
http://伺服器IP:5000
```

## 前端啟動

在接有 ACR122U 的前端主機執行：

```bat
client.bat
```

啟動時會先連到 GitHub 檢查是否有新版本；若有新版本，會跳出對話框詢問是否更新。
命令列會顯示目前版本、GitHub 版本，以及是否已是最新版本。

操作流程：

1. 選擇場域。
2. 輸入後端伺服器 IP。
3. 按下「網頁連線」。
4. Chrome 會開啟本機代理頁面 `http://127.0.0.1:5055/`。

## 場域設定

後端場域設定檔：

```text
server/場域對應.txt
```

格式為 tab 分隔：

```text
0	警衛室
1	教官室
2	總務處
```

也可以到後台 `/admin` 編輯。

## 學生資料匯入

學期初可到後台 `/admin` 的「學生資料更新」區塊：

1. 下載 Excel 範本。
2. 依範本填入或貼上全校資料。
3. 上傳 `.xlsx`。

匯入後會覆寫 `server/student_data.txt`，並只保留最近一次舊檔備份。按下「回復上一版的資料」可回到上次上傳前的資料；回復後不能連續再回復，需重新上傳後才會再次開放。

同一區塊也可上傳全校學生照片 ZIP：

1. 照片檔名需為 `<學號>.jpg`，例如 `410054.jpg`。
2. 將照片整批壓縮成 `.zip`。
3. 按「上傳照片ZIP」選擇檔案。
4. 可勾選「上傳新照片後刪除舊照片」，決定是否先清空 `server/ccsh_data/`。

## 資料保護

- `student_data.txt` 與備份檔沒有 HTTP/FTP 下載接口。
- 學生照片需由前台查詢或刷卡成功後取得短效 token 才能讀取。
- 同一來源若在短時間內大量下載照片，系統會暫時阻擋照片請求。

## 需求

- Windows
- Python 3.10+
- Flask
- ACR122U 與 Windows Smart Card / PCSC 支援

後端會由 `server.bat` 自動安裝 `server/requirements.txt` 內的套件。

## 驗證

```powershell
python -m py_compile server\app.py client\client_ui.py client\client_agent.py client\acr122_reader.py
```
