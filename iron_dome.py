import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.genai as genai
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import feedparser
import requests
from sklearn.linear_model import LinearRegression
import plotly.graph_objects as go

# ==========================================
# ⚙️ 系統設定 & 自動更新
# ==========================================
st.set_page_config(page_title="鐵穹預言機", layout="wide", page_icon="🛡️")
st_autorefresh(interval=300000, key="datarefresh") # 5分鐘自動重整

# 🎨 UI 美化 (行動裝置優化)
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    @media (max-width: 600px) { .stButton button { height: 50px; font-size: 18px; } }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 📡 外部功能函數 (新聞、LINE、美股)
# ==========================================

def get_financial_news():
    """抓取 Google News 財經新聞 RSS"""
    url = "https://news.google.com/rss/search?q=台股+財經+時事&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    news_items = [f"{item.title}" for item in feed.entries[:8]]
    return news_items

def send_line_notify(token, msg):
    """發送 LINE Notify 訊息"""
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": "Bearer " + token}
    payload = {"message": msg}
    try:
        r = requests.post(url, headers=headers, params=payload)
        return r.status_code
    except:
        return None

def get_us_pulse():
    """監控美股先行指標"""
    tickers = {"TSM": "台積電ADR", "^SOX": "費城半導體", "^IXIC": "那斯達克"}
    pulse = {}
    for ticker, name in tickers.items():
        try:
            d = yf.Ticker(ticker).history(period="2d")
            change = (d['Close'].iloc[-1] - d['Close'].iloc[-2]) / d['Close'].iloc[-2] * 100
            pulse[name] = change
        except: pulse[name] = 0
    return pulse

# ==========================================
# 🔧 核心技術指標計算 (強化版)
# ==========================================
def get_advanced_tech(ticker):
    ticker = ticker.strip()
    symbol = f"{ticker}.TW" if ticker.isdigit() else ticker
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo")
        if hist.empty: hist = yf.Ticker(symbol.replace(".TW", ".TWO")).history(period="6mo")
        if len(hist) < 30: return None

        close = hist['Close']
        # 1. 均線 & RSI
        ma20 = close.rolling(20).mean().iloc[-1]
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain/loss)).iloc[-1]

        # 2. 布林通道
        std = close.rolling(20).std().iloc[-1]
        upper_bb = ma20 + (std * 2)

        # 3. MACD
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        hist_macd = macd.iloc[-1] - signal.iloc[-1]

        return {
            "name": ticker, "price": close.iloc[-1], "chg": (close.iloc[-1]/close.iloc[-2]-1)*100,
            "ma20": ma20, "rsi": rsi, "upper_bb": upper_bb, "macd_h": hist_macd,
            "vol_ratio": hist['Volume'].iloc[-1] / hist['Volume'].rolling(5).mean().iloc[-1],
            "raw_hist": hist
        }
    except: return None

# ==========================================
# 🏰 介面佈局
# ==========================================
with st.sidebar:
    st.header("🛡️ 指揮官核心設定")
    api_key = st.text_input("Gemini API Key", type="password")
    line_token = st.text_input("LINE Notify Token", type="password")
    
    st.divider()
    my_stocks = st.text_area("📋 監控清單", "2330, 2454, 3711, 0052, GC=F, 00635U", height=100)
    hunt_stocks = st.text_area("🚀 獵殺池 (前300大)", "2317, 2382, 3324, 1519, 2603, 3017", height=100)

# --- 1. 全球戰情快報 ---
st.subheader("🌍 全球戰情預警 (美股連動)")
pulse_data = get_us_pulse()
cols = st.columns(len(pulse_data))
crash_signal = False
for i, (name, chg) in enumerate(pulse_data.items()):
    color = "red" if chg < -2 else "green" if chg > 0 else "white"
    cols[i].markdown(f"**{name}**\n<h3 style='color:{color}'>{chg:.2f}%</h3>", unsafe_allow_html=True)
    if chg < -2.5: crash_signal = True

if crash_signal:
    st.error("⚠️ 偵測到美股顯著下跌，台股開盤有大跌風險！已準備發送預警訊息。")
    if line_token:
        send_line_notify(line_token, f"🚨 預警：美股重挫，TSM ADR/費半跌幅過大，請注意台股開盤風險！")

# --- 2. 持股監控 ---
st.subheader("🛡️ 持股防禦狀態")
p_list = [t.strip() for t in my_stocks.split(",")]
p_results = []
for t in p_list:
    if d := get_advanced_tech(t):
        status = "⚠️ 破線危險" if d['price'] < d['ma20'] else "✅ 趨勢安全"
        p_results.append({"代號": t, "現價": round(d['price'],2), "漲跌%": round(d['chg'],2), "RSI": round(d['rsi'],1), "狀態": status})
        if "危險" in status and line_token:
            send_line_notify(line_token, f"🛡️ 鐵穹提醒：您的持股 {t} 已跌破月線，請檢視部位！")
st.table(pd.DataFrame(p_results))

# --- 3. AI 獵殺掃描 (新聞整合) ---
st.subheader("🚀 AI 獵殺與新聞分析")
if st.button("啟動 AI 綜合獵殺評估"):
    if not api_key: st.error("請輸入 API Key")
    else:
        news = get_financial_news()
        st.write("📰 **前夜關鍵新聞摘要：**")
        for n in news[:3]: st.write(f"- {n}")
        
        candidates = []
        for t in [x.strip() for x in hunt_stocks.split(",")]:
            if d := get_advanced_tech(t):
                # 獵殺條件：爆量 + 突破布林上軌 + MACD紅柱
                if d['vol_ratio'] > 1.3 and d['price'] > d['ma20'] and d['macd_h'] > 0:
                    candidates.append(d)
        
        if candidates:
            client = genai.Client(api_key=api_key)
            st.success(f"發現 {len(candidates)} 檔突破標的！AI 分析中...")
            for c in candidates:
                prompt = f"綜合考量新聞：{news[:5]}。分析台股 {c['name']}，現價 {c['price']} 已帶量突破技術面。請評估今日盤勢風險，並給出這檔標的的操作建議 (100字內)。"
                response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
                st.info(f"**{c['name']} 戰略建議：**\n{response.text}")
        else:
            st.warning("目前獵殺池未發現符合「強勢突破」之標的。")
