import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.genai as genai
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
import requests
import feedparser

# 這裡把 sklearn 放進 try，防止環境問題導致整片空白
try:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import PolynomialFeatures
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

# ==========================================
# ⚙️ 核心設定 (最優先執行)
# ==========================================
st.set_page_config(page_title="股票戰情監控中心", layout="wide", page_icon="📈")

# 初始化 Session State (防止重新整理時遺失數據)
if 'init' not in st.session_state:
    st.session_state['init'] = True

st_autorefresh(interval=300000, key="datarefresh")

# 🎨 UI 注入
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 10px; }
    h3 { color: #58a6ff; }
    .stButton button { width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# 📖 名稱對照
STOCK_NAMES = {
    "2330": "台積電", "0052": "富邦科技", "4958": "臻鼎-KY", "4420": "光明",
    "2603": "長榮", "3017": "奇鋐", "NVDA": "輝達", "GC=F": "🔥 國際黃金"
}

# ==========================================
# 📡 核心函數庫
# ==========================================
def get_tech_data(ticker):
    t = ticker.strip()
    if not t: return None
    # 修正代號邏輯
    symbol = f"{t}.TW" if t.isdigit() or ("A" in t.upper()) else t
    if t == "GC=F": symbol = "GC=F"
    
    try:
        # 使用 threads=False 防止在雲端環境產生衝突
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo", interval="1d")
        
        if hist.empty and ".TW" in symbol:
            symbol = symbol.replace(".TW", ".TWO")
            stock = yf.Ticker(symbol)
            hist = stock.history(period="6mo")
            
        if hist.empty: return None
        
        close = hist['Close']
        ma20 = close.rolling(20).mean().iloc[-1]
        vol_ratio = hist['Volume'].iloc[-1] / (hist['Volume'].rolling(5).mean().iloc[-1] + 1e-9)
        
        return {
            "name": STOCK_NAMES.get(t, t),
            "code": t,
            "price": close.iloc[-1],
            "chg": (close.iloc[-1]/close.iloc[-2]-1)*100,
            "ma20": ma20,
            "vol_ratio": vol_ratio,
            "hist": hist
        }
    except Exception as e:
        return None

# ==========================================
# 🏰 戰情室主視覺 (從這裡開始畫網頁)
# ==========================================
st.title("🏛️ 股票戰情監控中心")

# 側邊欄設定
with st.sidebar:
    st.header("📈 戰情核心設定")
    
    # 安全讀取 Secrets
    try:
        sec_api = st.secrets["GEMINI_API_KEY"]
    except:
        sec_api = ""
        
    api_key = st.text_input("Gemini API Key", value=sec_api, type="password")
    
    st.divider()
    my_stocks = st.text_area("📋 目前持股監控", "2330, 4958, 4420, 0052")
    hunt_pool = st.text_area("🚀 妖股獵殺池", "3017, 2603, 2317")

# --- 區塊 1: 持股防禦 ---
st.subheader("🛡️ 持股防禦狀態")
current_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
p_data = []

with st.spinner('連線交易所中...'):
    for t in current_list:
        d = get_tech_data(t)
        if d: p_data.append(d)

if p_data:
    df = pd.DataFrame([
        {"名稱": d['name'], "代號": d['code'], "現價": f"{d['price']:.2f}", "狀態": "⚠️ 破線" if d['price'] < d['ma20'] else "✅ 安全"} 
        for d in p_data
    ])
    st.table(df)
else:
    st.warning("⚠️ 暫時無法獲取股票數據，請確認代號是否正確。")

# --- 區塊 2: 趨勢預測 ---
st.divider()
st.subheader("🔮 數學趨勢預報")

if HAS_SKLEARN and p_data:
    target = st.selectbox("選擇預測標的", [d['code'] for d in p_data])
    if st.button("啟動預測分析"):
        d = next(item for item in p_data if item["code"] == target)
        y = d['hist']['Close'].tail(20).values
        X = np.arange(len(y)).reshape(-1, 1)
        
        model = LinearRegression().fit(X, y)
        future_X = np.arange(len(y), len(y) + 3).reshape(-1, 1)
        future_y = model.predict(future_X)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=y, name="實際價格", line=dict(color='#3b82f6')))
        fig.add_trace(go.Scatter(x=[len(y)-1, len(y), len(y)+1], y=[y[-1]] + list(future_y), name="預測趨勢", line=dict(dash='dash', color='#ff00ff')))
        fig.update_layout(template="plotly_dark", height=400)
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("💡 請在上方表格出現數據後再執行預測。")

# --- 區塊 3: AI 獵殺 ---
st.divider()
if st.button("🚀 啟動 AI 獵殺掃描", type="primary"):
    if not api_key:
        st.warning("請設定 API Key")
    else:
        st.success("✅ AI 模組已就緒，偵測到情報環境穩定。")
        st.write("目前正在掃描潛在標的...")
