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

# 🎨 UI 美化
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 10px; }
    h3 { color: #58a6ff; }
    .stButton button { width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 📖 台股名稱對照表 (核心擴展)
# ==========================================
STOCK_NAMES = {
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2382": "廣達", "2412": "中華電",
    "2308": "台達電", "3711": "日月光", "2303": "聯電", "6669": "緯穎", "3231": "緯創",
    "2881": "富邦金", "2882": "國泰金", "2891": "中信金", "2886": "兆豐金", "2884": "玉山金",
    "2885": "元大金", "5880": "合庫金", "2892": "第一金", "2880": "華南金", "2890": "永豐金",
    "2603": "長榮", "2609": "陽明", "2615": "萬海", "2618": "長榮航", "2610": "華航",
    "3017": "奇鋐", "3324": "雙鴻", "2376": "技嘉", "2357": "華碩", "1519": "華城",
    "0050": "元大台灣50", "0052": "富邦科技", "00878": "國泰高股息", "0056": "元大高股息",
    "GC=F": "🔥 國際黃金", "00635U": "元大黃金", "TSM": "台積電ADR"
}

def get_name(ticker):
    return STOCK_NAMES.get(ticker.strip(), ticker.strip())

# ==========================================
# 📡 功能函數
# ==========================================
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

def get_financial_news():
    url = "https://news.google.com/rss/search?q=台股+財經&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    return [item.title for item in feed.entries[:8]]

def get_tech_data(ticker):
    t = ticker.strip()
    symbol = f"{t}.TW" if t.isdigit() else t
    if t == "GC=F": symbol = "GC=F"
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
        macd_h = (close.ewm(span=12).mean() - close.ewm(span=26).mean()).iloc[-1]
        vol_ratio = hist['Volume'].iloc[-1] / hist['Volume'].rolling(5).mean().iloc[-1]
        return {"name": get_name(t), "code": t, "price": close.iloc[-1], "chg": (close.iloc[-1]/close.iloc[-2]-1)*100, 
                "ma20": ma20, "rsi": rsi, "macd_h": macd_h, "vol_ratio": vol_ratio}
    except: return None

# ==========================================
# 🏰 側邊欄
# ==========================================
with st.sidebar:
    st.header("🛡️ 指揮官核心設定")
    api_key = st.text_input("Gemini API Key", type="password")
    line_token = st.text_input("Channel Access Token", type="password")
    line_user_id = st.text_input("Your User ID (U...)")
    
    st.divider()
    my_stocks = st.text_area("📋 監控清單", "2330, 2454, 3711, 0052, GC=F, 2603")
    # 預設百大清單
    default_hunt = "2330, 2317, 2454, 2382, 2412, 2308, 3711, 2303, 6669, 3231, 2881, 2882, 2891, 2886, 2884, 2885, 2603, 2609, 2618, 3017, 3324, 1519"
    hunt_pool = st.text_area("🚀 獵殺池", default_hunt, height=150)

# ==========================================
# 📡 戰情室畫面
# ==========================================
st.title("🛡️ 鐵穹預言機 2026")

# 1. 全球戰情
pulse = get_us_pulse()
cols = st.columns(3)
for i, (name, chg) in enumerate(pulse.items()):
    color = "#ff4b4b" if chg < -2 else "#00ff00" if chg > 0 else "white"
    cols[i].markdown(f"<div class='metric-card'><b>{name}</b><br><h2 style='color:{color}; margin:0;'>{chg:.2f}%</h2></div>", unsafe_allow_html=True)

# 2. 持股防禦 (含中文名稱)
st.subheader("📊 持股防禦狀態")
p_results = []
for t in [x.strip() for x in my_stocks.split(",")]:
    if d := get_tech_data(t):
        status = "⚠️ 破線" if d['price'] < d['ma20'] else "✅ 安全"
        p_results.append({"名稱": d['name'], "代號": d['code'], "現價": f"{d['price']:.2f}", "漲跌%": f"{d['chg']:.2f}%", "狀態": status})
st.table(pd.DataFrame(p_results))

# 3. AI 獵殺 (含進度條與新聞)
st.divider()
st.subheader("🚀 AI 綜合獵殺評估")
if st.button("啟動 AI 獵殺掃描", type="primary"):
    if not api_key: st.warning("請輸入 API Key")
    else:
        news = get_financial_news()
        st.write("📰 **最新財經摘要：**")
        for n in news[:3]: st.write(f"- {n}")
        
        candidates = []
        scan_bar = st.progress(0, text="正在掃描全市場標的...")
        h_list = [x.strip() for x in hunt_pool.split(",") if x.strip()]
        for i, t in enumerate(h_list):
            scan_bar.progress((i + 1) / len(h_list))
            if d := get_tech_data(t):
                if d['vol_ratio'] > 1.2 and d['price'] > d['ma20']:
                    candidates.append(d)
        scan_bar.empty()
        
        if candidates:
            client = genai.Client(api_key=api_key)
            for c in candidates:
                with st.expander(f"📈 {c['name']} ({c['code']}) - 戰略解讀", expanded=True):
                    prompt = f"分析台股 {c['name']} ({c['code']})。技術面：帶量站上月線。參考新聞：{news[:5]}。請給出3天內的操作建議，100字內。"
                    response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
                    st.info(response.text)
        else: st.warning("目前獵殺池未發現強勢標的。")
