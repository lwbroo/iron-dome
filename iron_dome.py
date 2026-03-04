import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.genai as genai
from streamlit_autorefresh import st_autorefresh
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
import plotly.graph_objects as go
import requests
import feedparser

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

# 📖 標配名稱對照表
STOCK_NAMES = {
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2382": "廣達", "2603": "長榮",
    "3017": "奇鋐", "3324": "雙鴻", "1519": "華城", "GC=F": "🔥 國際黃金", "TSM": "台積電ADR"
}

def get_name(t): return STOCK_NAMES.get(t.strip(), t.strip())

# ==========================================
# 📡 核心分析函數
# ==========================================
def get_tech_data(ticker):
    t = ticker.strip()
    symbol = f"{t}.TW" if t.isdigit() else t
    if t == "GC=F": symbol = "GC=F"
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo")
        if hist.empty and ".TW" in symbol: hist = yf.Ticker(symbol.replace(".TW", ".TWO")).history(period="6mo")
        if len(hist) < 30: return None
        close = hist['Close']
        ma20 = close.rolling(20).mean().iloc[-1]
        return {"name": get_name(t), "code": t, "price": close.iloc[-1], "ma20": ma20, "hist": hist}
    except: return None

# ==========================================
# 🏰 戰情室介面
# ==========================================
st.title("🏛️ 股票戰情監控中心")

with st.sidebar:
    st.header("📈 戰情核心設定")
    api_key = st.text_input("Gemini API Key", type="password")
    line_token = st.text_input("LINE Token", type="password")
    line_uid = st.text_input("LINE User ID")
    st.divider()
    my_stocks = st.text_area("📋 監控清單", "2330, 2454, 3711, 2603, GC=F")

# 1. 持股狀態
p_data = [get_tech_data(t) for t in my_stocks.split(",") if get_tech_data(t)]
if p_data:
    df = pd.DataFrame([{"名稱": d['name'], "代號": d['code'], "現價": f"{d['price']:.2f}", "狀態": "⚠️ 破線" if d['price'] < d['ma20'] else "✅ 安全"} for d in p_data])
    st.table(df)

# 2. 進化版趨勢預測 (多項式回歸)
st.divider()
st.subheader("🔮 演算法趨勢預測 (線性 vs 多項式)")

col_l, col_r = st.columns([1, 2])
with col_l:
    target = st.selectbox("預測標的", [d['code'] for d in p_data])
    algo_type = st.radio("選擇演算法", ["線性 (直線趨勢)", "多項式 (轉折預測)"])
    lookback = st.slider("參考天數", 10, 60, 20)
    predict_days = st.slider("預測天數", 1, 7, 3)
    poly_degree = st.slider("多項式次方 (度數)", 2, 4, 2) if algo_type == "多項式 (轉折預測)" else 1

if st.button("執行演算法預測分析"):
    d = get_tech_data(target)
    hist = d['hist'].tail(lookback)
    y = hist['Close'].values
    X = np.arange(len(y)).reshape(-1, 1)
    
    # 建立預測點
    future_X = np.arange(len(y), len(y) + predict_days).reshape(-1, 1)
    
    if algo_type == "線性 (直線趨勢)":
        model = LinearRegression().fit(X, y)
        future_y = model.predict(future_X)
        trend_y = model.predict(X)
    else:
        poly = PolynomialFeatures(degree=poly_degree)
        X_poly = poly.fit_transform(X)
        model = LinearRegression().fit(X_poly, y)
        future_y = model.predict(poly.transform(future_X))
        trend_y = model.predict(X_poly)

    # 繪製圖表
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(len(y))), y=y, name="實際價格", line=dict(color='#3b82f6', width=3)))
    fig.add_trace(go.Scatter(x=list(range(len(y))), y=trend_y, name="擬合趨勢", line=dict(color='rgba(255,255,255,0.3)', dash='dot')))
    fig.add_trace(go.Scatter(x=list(range(len(y)-1, len(y)+predict_days)), y=np.append(y[-1], future_y), name="預測延伸", line=dict(color='#ef4444', width=2, dash='dash')))
    
    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig, use_container_width=True)
    st.write(f"💡 分析結論：使用 **{algo_type}** 模型，預計 **{predict_days}** 天後目標價約：**{future_y[-1]:.2f}**")
