#!/usr/bin/env python
# coding: utf-8
# In[ ]:
import time
import os
import json
import urllib.error
import urllib.request
import autoline
import tkinter as tk
# from tkinter import ttk
print("=====版本 beta 2.0 all right reserve by KY====")
 
def buildFile(date_text=None):#從門禁系統 API 取得指定日期資料
    date_text = date_text or time.strftime("%Y%m%d")
    server_url = os.environ.get("RFID_SERVER_URL", "http://127.0.0.1:5000").rstrip("/")
    api_url = f"{server_url}/api/attendance/summary/{date_text}"
    filename = "./msg.txt"
    try:
        with urllib.request.urlopen(api_url, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
        records = data.get("records") or []
        with open(filename, encoding="utf-8", mode="w", newline="") as f:
            f.write("時間\t卡片UID\t學號\t班級\t座號\t姓名\t進/出\n")
            for record in records:
                f.write(
                    "\t".join(
                        [
                            str(record.get("time") or ""),
                            str(record.get("uid") or ""),
                            str(record.get("student_id") or ""),
                            str(record.get("class_name") or ""),
                            str(record.get("seat") or ""),
                            str(record.get("name") or ""),
                            str(record.get("direction") or ""),
                        ]
                    )
                    + "\n"
                )
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as exc:
        print(f"取得出勤資料失敗：{exc}")
        return False
dic = {}
def getMsgList(filename):
    f = open(filename,'r',encoding='utf8')
    aLine = f.readline()
    dic.clear()
    #用班級當作 key
    while(aLine):
        aLine = f.readline()
        words = aLine.split()
        if len(words)>4:
            r = words[0]+'\t'+words[4]
            dkey = words[3]
            if len(dkey)==3:
                dkey=dkey[0:2]+"0"+dkey[2]
            if dkey in dic:
                dic[dkey].append(r)
            else:
                dic[dkey] = [r]
            #print(words[0]+words[3]+"-"+words[4])    
    f.close()
    i=1
    msg = "\n"+time.strftime("%m/%d")+"遲到學生名單-"+str(i)+"\n"
    lineCount = 1
    msgList = []
    
    MAX_LINE = 72
    keys = sorted(dic.keys())
    for k in keys:
        if lineCount+len(dic[k])+3>MAX_LINE:
            i+=1
            msgList.append(msg)
            msg = "\n"+time.strftime("%m/%d")+"遲到學生名單-"+str(i)+"\n"
            lineCount = 1
        lineCount+=len(dic[k])+1
        aLine ="["+ k +"]\n" 
        for r in dic[k]:
            aLine+=r+"\n"#aLine+=r+","
        msg+=aLine
    msgList.append(msg)
    return msgList

import time,datetime
import pygetwindow as gw            
import holidays            
import pyautogui
import pyperclip
# 設定台灣例假日
tw_holidays = holidays.TW()
def is_working_day(day):# 星期 0-4 為工作日，排除台灣例假日
    return day.weekday() < 5 and day not in tw_holidays
def work():
    if not is_working_day(datetime.datetime.now()):
        print(f'{datetime.datetime.now()}非上學日')
        return
    if not buildFile():
        print(f'{datetime.datetime.now()}無法取得出勤資料，停止本次推播')
        return
    filename = "./msg.txt"
    msgList = getMsgList(filename)
    time.sleep(1)
    group_title="家齊學生出勤推播群組"
    for msg in msgList:
        autoline.send(group_title, msg+'\n')
        
    if autoline.hideWindow(group_title) is None:
        log(f"未開啟視窗 [{group_title}] \n")    
#         print(msg)
    print(f'{datetime.datetime.now()}訊息傳送完畢')
    
print(f'{datetime.datetime.now()}啟動')
isDone = False
#============
# root = tk.Tk()
# root.title("每日推播提醒")
# def show_window():
#     root.deiconify()
#     root.lift()
#     root.attributes('-topmost', True)
#     root.after(100, lambda: root.attributes('-topmost', False))
# def bring_to_front():
#     global isDone
#     if now.hour == selected_hour and now.minute == selected_min and not isDone:
#         log(f"[{now.strftime('%H:%M:%S')}] 推播時間到達！\n")
#         show_window()
#         isDone = True
#         for fn in os.listdir('msg'):
#             f = open(f'msg/{fn}',encoding='utf-8')
#             msg = f.read()
#             if  autoline.send(group_title, msg+'\n') == None:
#                 isDone = False
#         if isDone:log('done')
#     if now.hour == 23 and now.minute > 50 : isDone = False
#     if autoline.hideWindow(group_title) is None:
#         log(f"未開啟視窗 [{group_title}] \n")
# 
#     try:interval = int(interval_var.get())
#     except:interval = 5
#     root.after(interval * 1000, bring_to_front)
# bring_to_front()
# root.mainloop()


while True:
    timeHM = int(time.strftime("%H%M"))
    if timeHM>1230 and timeHM<1830 and not isDone:
        work()
        isDone = True
    if timeHM>2350:
        time.sleep(3600*5)	
        isDone = False
    time.sleep(300)
