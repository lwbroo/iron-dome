import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.genai as genai
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import feedparser
import requests

# ==========================================
# ⚙️ 系統設定 & 自動更新
# ==========================================
st.set_page_config(page_title="鐵穹預言機 2026", layout="wide", page_icon="🛡️")
st_autorefresh(interval=300000, key="datarefresh")

# ==========================================
# 📡 2026 最新 LINE Messaging API 函數
# ==========================================
def send_line_push(access_token, user_id, message):
    """使用 Messaging API 發送 1對1 推播訊息"""
    if not access_token or not user_id:
        return None
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}]
    }
    try:
        r = requests.post(url, headers=headers, json=payload)
        return r.status_code
    except:
        return None

# ==========================================
# 🌍 美股 & 新聞功能
# ==========================================
def get_us_pulse():
    tickers = {"TSM": "台積電ADR", "^SOX": "費半", "^IXIC": "那指"}
    pulse = {}
    for ticker, name in tickers.items():
        try:
            d = yf.Ticker(ticker).history(period="2d")
            chg = (d['Close'].iloc[-1] / d['Close'].iloc[-2] - 1) * 100
            pulse[name] = chg
        except: pulse[name] = 0
    return pulse

def get_financial_news():
    url = "https://news.google.com/rss/search?q=台股+財經&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    return [item.title for item in feed.entries[:5]]

# ==========================================
# 🏰 介面與側邊欄 (設定區)
# ==========================================
with st.sidebar:
    st.header("🛡️ 指揮官核心設定")
    api_key = st.text_input("Gemini API Key", type="password")
    
    st.subheader("🤖 LINE 機器人設定")
    line_token = st.text_input("Channel Access Token", type="password")
    line_user_id = st.text_input("Your User ID (U...)")
    
    if st.button("測試 LINE 連線"):
        status = send_line_push(line_token, line_user_id, "🚀 鐵穹系統：連線測試成功！")
        if status == 200: st.success("發送成功！請檢查手機。")
        else: st.error(f"發送失敗，代碼: {status}")

    st.divider()
    my_stocks = st.text_area("📋 監控清單", "2330, 2454, 3711, 0052, GC=F, 2603")

# ==========================================
# 📡 戰情室主畫面
# ==========================================
st.subheader("🌍 全球戰情預警 (美股連動)")
pulse = get_us_pulse()
cols = st.columns(3)
for i, (name, chg) in enumerate(pulse.items()):
    color = "#ff4b4b" if chg < -2 else "#00ff00" if chg > 0 else "white"
    cols[i].markdown(f"**{name}**\n<h2 style='color:{color}'>{chg:.2f}%</h2>", unsafe_allow_html=True)

# 觸發大跌預警
if pulse.get("台積電ADR", 0) < -3.0 or pulse.get("費半", 0) < -3.0:
    st.error("⚠️ 偵測到美股重挫！台股開盤有大跌風險。")
    if line_token and line_user_id:
        send_line_push(line_token, line_user_id, f"🚨 鐵穹預警：美股重挫！台積電ADR跌幅 {pulse['台積電ADR']:.2f}%，請注意今日開盤風險。")

# ... 接下來的持股分析與 AI 獵殺程式碼保持不變 ...
# (請確保將原本 iron_dome.py 下半部的分析邏輯也保留在此檔案中)
