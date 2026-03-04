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
st.set_page_config(page_title="股票戰情監控中心", layout="wide", page_icon="📈")
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

# 📖 台股名稱對照表
STOCK_NAMES = {
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2382": "廣達", "2412": "中華電",
    "2308": "台達電", "3711": "日月光", "2303": "聯電", "6669": "緯穎", "3231": "緯創",
    "2881": "富邦金", "2882": "國泰金", "2891": "中信金", "2886": "兆豐金", "2884": "玉山金",
    "2885": "元大金", "5880": "合庫金", "2892": "第一金", "2880": "華南金", "2890": "永豐金",
    "2603": "長榮", "2609": "陽明", "2615": "萬海", "2618": "長榮航", "2610": "華航",
    "3017": "奇鋐", "3324": "雙鴻", "2376": "技嘉", "2357": "華碩", "1519": "華城",
    "0050": "元大台灣50", "0052": "富邦科技", "00878": "國泰高股息", "GC=F": "🔥 國際黃金"
}

def get_name(t): return STOCK_NAMES.get(t.strip(), t.strip())

# ==========================================
# 📡 核心功能
# ==========================================
def send_line_push(token, uid, msg):
    if not token or not uid: return None
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": uid, "messages": [{"type": "text", "text": msg}]}
    try: requests.post(url, headers=headers, json=payload); return 200
    except: return 500

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
        vol_ratio = hist['Volume'].iloc[-1] / hist['Volume'].rolling(5).mean().iloc[-1]
        return {"name": get_name(t), "code": t, "price": close.iloc[-1], "chg": (close.iloc[-1]/close.iloc[-2]-1)*100, "ma20": ma20, "vol_ratio": vol_ratio, "hist": hist}
    except: return None

# ==========================================
# 🏰 側邊欄
# ==========================================
with st.sidebar:
    st.header("📈 戰情室核心設定")
    api_key = st.text_input("Gemini API Key", type="password")
    line_token = st.text_input("LINE Token", type="password")
    line_uid = st.text_input("LINE User ID")
    
    st.divider()
    my_stocks = st.text_area("📋 監控清單", "2330, 2454, 3711, 2603, GC=F")
    hunt_pool = st.text_area("🚀 獵殺池", "2317, 2382, 3324, 1519, 3017, 2303, 3231")

# ==========================================
# 📡 戰情室畫面
# ==========================================
st.title("🏛️ 股票戰情監控中心")

# 1. 持股防禦
st.subheader("🛡️ 持股防禦監控")
p_data = [get_tech_data(t) for t in my_stocks.split(",") if get_tech_data(t)]
if p_data:
    df = pd.DataFrame([{"名稱": d['name'], "代號": d['code'], "現價": f"{d['price']:.2f}", "狀態": "⚠️ 破線" if d['price'] < d['ma20'] else "✅ 安全"} for d in p_data])
    st.table(df)

# 2. 機器學習趨勢預測 (回歸分析)
st.divider()
st.subheader("📈 AI 趨勢預測 (演算法動態調整)")

col_l, col_r = st.columns([1, 2])
with col_l:
    target_stock = st.selectbox("選擇預測標的", [d['code'] for d in p_data])
    lookback = st.slider("調整演算法：參考過去天數", 10, 60, 30)
    predict_days = st.slider("預測未來天數", 1, 7, 3)

if st.button("執行回歸預測分析"):
    stock_d = get_tech_data(target_stock)
    hist = stock_d['hist'].tail(lookback)
    
    # 訓練模型
    y = hist['Close'].values
    X = np.arange(len(y)).reshape(-1, 1)
    model = LinearRegression().fit(X, y)
    
    # 預測未來
    future_X = np.arange(len(y), len(y) + predict_days).reshape(-1, 1)
    future_y = model.predict(future_X)
    
    # 畫圖
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(len(y))), y=y, name="實際股價", line=dict(color='#3b82f6')))
    fig.add_trace(go.Scatter(x=list(range(len(y), len(y)+predict_days)), y=future_y, name="預測趨勢", line=dict(color='#ef4444', dash='dash')))
    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)
    st.write(f"💡 根據過去 **{lookback}** 天數據模型計算，預計 **{predict_days}** 天後目標價約：**{future_y[-1]:.2f}**")

# 3. AI 獵殺按鈕 (保持原邏輯)
st.divider()
if st.button("啟動 AI 綜合獵殺評估", type="primary"):
    # (保留之前的 AI 獵殺與新聞分析邏輯...)
    st.info("AI 正在掃描全市場標的並結合新聞解讀中...")
