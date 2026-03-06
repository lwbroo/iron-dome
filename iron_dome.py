import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.genai as genai
import plotly.graph_objects as go
import requests
import feedparser
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

# 🛡️ 組件安全載入
try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_MODE = True
except ImportError:
    AUTOREFRESH_MODE = False

# ==========================================
# ⚙️ 系統設定
# ==========================================
st.set_page_config(page_title="股票戰情監控中心", layout="wide", page_icon="📈")

if AUTOREFRESH_MODE:
    try:
        st_autorefresh(interval=300000, key="datarefresh")
    except:
        st.sidebar.warning("⚠️ 自動刷新組件異常，請手動刷新。")

# 🎨 UI 美化
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 10px; }
    h3 { color: #58a6ff; }
    .stButton button { width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border-radius: 8px; border: none; }
    .stButton button:hover { background-color: #2ea043; }
</style>
""", unsafe_allow_html=True)

# 📖 名稱對照表
STOCK_NAMES = {
    "2330": "台積電", "0052": "富邦科技", "006208": "富邦台50", "4958": "臻鼎-KY",
    "4420": "光明", "00981A": "復華美債1-5Y", "00985A": "中信優先金融債", 
    "009816": "債券標的", "2603": "長榮", "3017": "奇鋐", "NVDA": "輝達", "GC=F": "🔥 國際黃金"
}

def get_name(t): return STOCK_NAMES.get(t.strip().upper(), t.strip())

# ==========================================
# 📡 核心分析函數
# ==========================================
def get_tech_data(ticker):
    t = ticker.strip().upper()
    if not t: return None
    symbol = f"{t}.TW" if (t.isdigit() or "A" in t) else t
    if t == "GC=F": symbol = "GC=F"
    
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo")
        # 處理上市/上櫃
        if hist.empty and ".TW" in symbol:
            symbol = symbol.replace(".TW", ".TWO")
            stock = yf.Ticker(symbol)
            hist = stock.history(period="6mo")
            
        if hist.empty: return None
        
        # --- 獲取配息資訊 ---
        div_data = stock.dividends
        if not div_data.empty:
            last_div = div_data.iloc[-1]
            last_div_date = div_data.index[-1].strftime('%Y-%m-%d')
        else:
            last_div = 0
            last_div_date = "無數據"
            
        close = hist['Close']
        ma20 = close.rolling(20).mean().iloc[-1]
        vol_ratio = hist['Volume'].iloc[-1] / (hist['Volume'].rolling(5).mean().iloc[-1] + 1e-9)
        
        return {
            "name": get_name(t), "code": t, "price": close.iloc[-1], 
            "chg": (close.iloc[-1]/close.iloc[-2]-1)*100, 
            "ma20": ma20, "div": last_div, "div_date": last_div_date,
            "vol_ratio": vol_ratio, "hist": hist
        }
    except: return None

# ==========================================
# 🏰 戰情室介面
# ==========================================
st.title("🏛️ 股票戰情監控中心 (配息強化版)")

with st.sidebar:
    st.header("📈 戰情設定")
    if st.button("🔄 立即刷新戰情"): st.rerun()
    st.divider()
    
    api_key = st.text_input("Gemini API Key", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
    line_token = st.text_input("LINE Token", value=st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN", ""), type="password")
    line_uid = st.text_input("Your User ID", value=st.secrets.get("LINE_USER_ID", ""))

    st.divider()
    default_my = "0052, 00981A, 2330, 006208, 4958, 4420"
    my_stocks = st.text_area("📋 持股監控 (代號,逗號格開)", default_my)
    hunt_pool = st.text_area("🚀 妖股獵殺池", "3324, 3017, 1519, 2603")

# --- 1. 全球脈動 ---
pulse_tickers = {"TSM": "台積電ADR", "NVDA": "輝達", "^SOX": "費半", "GC=F": "黃金"}
p_cols = st.columns(len(pulse_tickers))
for i, (tic, nm) in enumerate(pulse_tickers.items()):
    try:
        d = yf.Ticker(tic).history(period="2d")
        chg = (d['Close'].iloc[-1]/d['Close'].iloc[-2]-1)*100
        color = "#ff4b4b" if chg < -1.5 else "#00ff00" if chg > 0 else "white"
        p_cols[i].markdown(f"<div class='metric-card'><b>{nm}</b><br><h2 style='color:{color}; margin:0;'>{chg:.2f}%</h2></div>", unsafe_allow_html=True)
    except: p_cols[i].write(f"{nm} 讀取中...")

# --- 2. 持股防禦 (含配息公告) ---
st.subheader("🛡️ 持股防禦與配息公告")
current_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
p_data = [get_tech_data(t) for t in current_list if get_tech_data(t)]

if p_data:
    df = pd.DataFrame([
        {
            "名稱": d['name'], 
            "代號": d['code'],
            "現價": f"{d['price']:.2f}", 
            "最新配息": f"${d['div']:.2f}",
            "除息日期": d['div_date'],
            "殖利率": f"{(d['div']/d['price']*100):.2f}%" if d['div'] > 0 else "N/A",
            "狀態": "⚠️ 破線" if d['price'] < d['ma20'] else "✅ 安全"
        } for d in p_data
    ])
    st.table(df)
else:
    st.info("💡 正在連線交易所，請確保左側代號正確。")

# --- 3. 趨勢預測 ---
st.divider()
st.subheader("🔮 數學趨勢路徑 (線性 vs 多項式)")
all_codes = sorted(list(set([d['code'] for d in p_data] + [t.strip() for t in hunt_pool.split(",") if t.strip()])))
if all_codes:
    target = st.selectbox("分析標的", all_codes)
    col_l, col_r = st.columns([1, 2.5])
    with col_l:
        algo = st.radio("預測模式", ["線性趨勢", "多項式轉折"])
        lookback = st.slider("參考天數", 10, 60, 20)
    
    if st.button("執行演算法預報"):
        d = get_tech_data(target)
        if d:
            y = d['hist']['Close'].tail(lookback).values
            X = np.arange(len(y)).reshape(-1, 1)
            future_X = np.arange(len(y), len(y) + 3).reshape(-1, 1)
            if algo == "線性趨勢":
                model = LinearRegression().fit(X, y); future_y = model.predict(future_X)
            else:
                pf = PolynomialFeatures(degree=3); model = LinearRegression().fit(pf.fit_transform(X), y)
                future_y = model.predict(pf.transform(future_X))
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(y=y, name="實際價格", line=dict(color='#3b82f6', width=3)))
            fig.add_trace(go.Scatter(x=[len(y)-1, len(y), len(y)+1], y=[y[-1]]+list(future_y), name="預測趨勢", line=dict(color='#ff00ff', dash='dash')))
            fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
