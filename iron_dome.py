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
st_autorefresh(interval=300000, key="datarefresh") # 5分鐘自動刷新

# 🎨 UI 美化
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    h3 { color: #58a6ff; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 📡 核心功能函數 (新聞、LINE、美股、技術指標)
# ==========================================
def get_financial_news():
    url = "https://news.google.com/rss/search?q=台股+財經&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    return [item.title for item in feed.entries[:8]]

def send_line_push(access_token, user_id, message):
    if not access_token or not user_id: return None
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}
    payload = {"to": user_id, "messages": [{"type": "text", "text": message}]}
    try:
        r = requests.post(url, headers=headers, json=payload)
        return r.status_code
    except: return None

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

def get_advanced_tech(ticker):
    ticker = ticker.strip()
    symbol = f"{ticker}.TW" if ticker.isdigit() else ticker
    if ticker == "GC=F": symbol = "GC=F"
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo")
        if hist.empty and ".TW" in symbol:
            hist = yf.Ticker(symbol.replace(".TW", ".TWO")).history(period="6mo")
        if len(hist) < 30: return None
        close = hist['Close']
        ma20 = close.rolling(20).mean().iloc[-1]
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain.iloc[-1]/loss.iloc[-1]))
        std = close.rolling(20).std().iloc[-1]
        upper_bb = ma20 + (std * 2)
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd_h = (exp1 - exp2).iloc[-1] - (exp1 - exp2).ewm(span=9, adjust=False).mean().iloc[-1]
        vol_ratio = hist['Volume'].iloc[-1] / hist['Volume'].rolling(5).mean().iloc[-1]
        return {"name": ticker, "price": close.iloc[-1], "chg": (close.iloc[-1]/close.iloc[-2]-1)*100, 
                "ma20": ma20, "rsi": rsi, "upper_bb": upper_bb, "macd_h": macd_h, "vol_ratio": vol_ratio}
    except: return None

# ==========================================
# 🏰 側邊欄設定區
# ==========================================
with st.sidebar:
    st.header("🛡️ 指揮官核心設定")
    api_key = st.text_input("Gemini API Key", type="password")
    
    st.subheader("🤖 LINE 機器人設定")
    line_token = st.text_input("Channel Access Token", type="password")
    line_user_id = st.text_input("Your User ID (U...)")
    
    if st.button("測試 LINE 連線"):
        status = send_line_push(line_token, line_user_id, "🚀 鐵穹系統：連線測試成功！")
        if status == 200: st.success("發送成功！")
        else: st.error(f"錯誤代碼: {status}")

    st.divider()
    my_stocks = st.text_area("📋 監控清單", "2330, 2454, 3711, 0052, GC=F, 2603")
    hunt_pool = st.text_area("🚀 獵殺池 (代號)", "2317, 2382, 3324, 1519, 3017, 2303, 3231")

# ==========================================
# 📡 戰情室主畫面
# ==========================================
st.title("🛡️ 鐵穹戰略預言機")

# --- 1. 全球戰情 ---
st.subheader("🌍 全球戰情預警 (美股連動)")
pulse = get_us_pulse()
cols = st.columns(3)
for i, (name, chg) in enumerate(pulse.items()):
    color = "#ff4b4b" if chg < -2 else "#00ff00" if chg > 0 else "white"
    cols[i].markdown(f"**{name}**\n<h2 style='color:{color}'>{chg:.2f}%</h2>", unsafe_allow_html=True)

if pulse.get("台積電ADR", 0) < -3.0:
    st.error("🚨 警告：台積電ADR重挫，今日台股開盤有系統性風險！")

# --- 2. 持股監控 ---
st.subheader("🛡️ 持股防禦狀態")
p_results = []
for t in [x.strip() for x in my_stocks.split(",")]:
    if d := get_advanced_tech(t):
        status = "⚠️ 破線" if d['price'] < d['ma20'] else "✅ 安全"
        p_results.append({"代號": t, "現價": f"{d['price']:.2f}", "漲跌%": f"{d['chg']:.2f}%", "RSI": f"{d['rsi']:.1f}", "狀態": status})
st.table(pd.DataFrame(p_results))

# --- 3. AI 獵殺按鈕 (最重要的部分) ---
st.divider()
st.subheader("🚀 AI 綜合獵殺評估 (技術+新聞)")

if st.button("啟動 AI 獵殺評估", type="primary"):
    if not api_key:
        st.warning("⚠️ 請先輸入 Gemini API Key")
    else:
        # A. 抓新聞
        news = get_financial_news()
        st.write("📰 **最新財經動態：**")
        for n in news[:3]: st.write(f"- {n}")
        
        # B. 技術面過濾
        candidates = []
        scan_bar = st.progress(0, text="正在掃描獵殺池...")
        hunt_list = [x.strip() for x in hunt_pool.split(",")]
        for i, t in enumerate(hunt_list):
            scan_bar.progress((i + 1) / len(hunt_list))
            if d := get_advanced_tech(t):
                # 獵殺條件：爆量 + 站上月線 + MACD紅柱
                if d['vol_ratio'] > 1.2 and d['price'] > d['ma20'] and d['macd_h'] > 0:
                    candidates.append(d)
        scan_bar.empty()
        
        # C. AI 深度解讀
        if candidates:
            st.success(f"✅ 發現 {len(candidates)} 檔具備攻擊潛力標的！AI 正在整合新聞進行解讀...")
            client = genai.Client(api_key=api_key)
            for c in candidates:
                with st.expander(f"📊 分析報告：{c['name']}", expanded=True):
                    prompt = f"分析台股 {c['name']}。技術面：現價 {c['price']:.2f} 帶量突破月線，MACD轉正。參考新聞：{news[:5]}。請結合今日市場氣氛與技術面，給出這檔股票的短線(3天)操作建議。100字內。"
                    try:
                        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
                        st.info(response.text)
                    except:
                        st.error("AI 運算失敗，請檢查 API Key 或稍後再試。")
        else:
            st.warning("目前獵殺池內未發現符合『強勢突破』條件之標的。")
