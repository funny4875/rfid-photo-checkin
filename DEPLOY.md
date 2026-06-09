# RFID 前後端部署

## 後端主機

後端主機放學生資料、照片、網頁、API 與門禁記錄檔。

執行：

```bat
server.bat
```

啟動後服務位址為：

```text
http://<後端主機IP>:5000
```

後端程式與資料位置：

```text
server\
```

## 前端主機

前端主機接 ACR122U 讀卡機。

執行：

```bat
client.bat
```

執行後會開啟 RFID 前端連線視窗，可選擇場域、輸入後端主機 IP，按下「網頁連線」後會開啟本機代理網頁。

設定會寫入：

```text
client\config.txt
```

之後再次執行會帶入 `config.txt` 的 IP 與場域。

Chrome 會開啟：

```text
http://127.0.0.1:5055/
```

若要更換後端 IP，刪除 `client\config.txt` 後再執行 `client.bat`。

## 場域設定

後端主機的場域對應檔案：

```text
server\場域對應.txt
```

格式為 tab 分隔：

```text
0	警衛室
1	教官室
2	總務處
```

也可以在後台網頁 `/admin` 的「場域設定」新增、刪除、儲存場域。

## 學生資料更新

學期初更新全校學生資料時，到後台網頁 `/admin` 的「學生資料更新」區塊：

1. 下載 Excel 範本。
2. 填入或貼上全校學生資料。
3. 上傳 `.xlsx`。

系統會覆寫：

```text
server\student_data.txt
```

並自動備份舊檔到：

```text
server\backups
```

## 資料流

```text
ACR122U -> client\client_agent.py -> Chrome 網頁 -> server\app.py -> 門禁記錄檔
```

前端本機讀卡代理固定提供：

```text
http://127.0.0.1:5055/api/rfid/status
```
