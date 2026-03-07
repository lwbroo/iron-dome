import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.genai as genai
import plotly.graph_objects as go
from FinMind.data import DataLoader
import datetime
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

# ==========================================
# ⚙️ 系統設定
# ==========================================
st.set_page_config(page_title="股票戰情監控中心", layout="wide", page_icon="📈")
dl = DataLoader() # 初始化 FinMind

# 🎨 UI 美化
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 10px; }
    h3 { color: #58a6ff; }
    .stButton button { width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# 📖 12 檔核心部隊 (FinMind 不需要後綴，直接用 2330)
STOCK_NAMES = {
    "2330": "台積電", "0052": "富邦科技", "006208": "富邦台50", "4958": "臻鼎-KY",
    "4420": "光明", "00919": "群益精選高息", "0056": "元大高股息", "6683": "雍智科技",
    "1717": "長興", "00929": "復華台灣科技優息", "00981A": "復華美債1-5Y", 
    "009816": "特定債券標的", "NVDA": "輝達", "GC=F": "🔥 國際黃金"
}

# ==========================================
# 📡 核心分析函數 (FinMind + yfinance 混合)
# ==========================================
def get_tech_data(ticker):
    t = ticker.strip().upper()
    if not t: return None
    
    is_taiwan = t.isdigit() or t.startswith("00")
    hist = pd.DataFrame()
    last_div = 0
    freq = "年配"
    
    try:
        if is_taiwan:
            # 🛡️ 優先使用 FinMind 抓取台股 (穩定性 100%)
            df = dl.taiwan_stock_daily(stock_id=t, start_date=(datetime.datetime.now() - datetime.timedelta(days=180)).strftime('%Y-%m-%d'))
            if not df.empty:
                hist = df.rename(columns={'close': 'Close', 'date': 'Date', 'volume': 'Volume'})
                hist.set_index('Date', inplace=True)
                # 抓取配息資訊
                div_df = dl.taiwan_stock_dividend(stock_id=t, start_date='2024-01-01')
                if not div_df.empty:
                    last_div = div_df['dividend_cash'].iloc[-1]
                    count = len(div_df)
                    if count >= 10: freq = "月配"
                    elif 3 <= count <= 5: freq = "季配"
                    elif count == 2: freq = "半年配"
        else:
            # 🇺🇸 使用 Yahoo Finance 處理美股與黃金
            stock = yf.Ticker(t if t != "GC=F" else "GC=F")
            hist = stock.history(period="6mo")
            if not stock.dividends.empty:
                last_div = stock.dividends.iloc[-1]

        if hist.empty: return {"code": t, "name": STOCK_NAMES.get(t, t), "is_error": True}

        close = hist['Close']
        ma20 = close.rolling(20).mean().iloc[-1]
        
        return {
            "name": STOCK_NAMES.get(t, t), "code": t, "price": close.iloc[-1], 
            "chg": (close.iloc[-1]/close.iloc[-2]-1)*100, "ma20": ma20, 
            "div": last_div, "freq": freq, "hist": hist, "is_error": False
        }
    except:
        return {"code": t, "name": STOCK_NAMES.get(t, t), "is_error": True}

# ==========================================
# 🏰 戰情室主視覺
# ==========================================
st.title("🏛️ 股票戰情監控中心 (FinMind 強化版)")

with st.sidebar:
    st.header("📈 戰情設定")
    if st.button("🔄 刷新偵測雷達"): st.rerun()
    st.divider()
    PERMANENT_LIST = "0052, 00981A, 2330, 006208, 4958, 4420, 00919, 009816, 0056, 6683, 1717, 00929"
    my_stocks = st.text_area("📋 12 檔核心部隊", PERMANENT_LIST, height=150)

# --- 資料同步 ---
current_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
p_data = []

with st.spinner('📡 正在從 FinMind 衛星接收台股數據...'):
    for t in current_list:
        p_data.append(get_tech_data(t))

# --- 顯示表格 ---
st.subheader("🛡️ 持股防禦與配息戰訊")
if p_data:
    display_rows = []
    for d in p_data:
        if d.get("is_error"):
            display_rows.append({"名稱": d['name'], "代號": d['code'], "現價": "連線中...", "狀態": "🔄"})
        else:
            status = "✅ 安全"
            if d['price'] < d['ma20']: status = "⚠️ 破線"
            display_rows.append({
                "名稱": d['name'], "代號": d['code'], "現價": f"{d['price']:.2f}", 
                "最新配息": f"${d['div']:.2f}", "頻率": d['freq'], "狀態": status
            })
    st.table(pd.DataFrame(display_rows))

# --- 趨勢預測 ---
st.divider()
valid_codes = [d['code'] for d in p_data if not d.get("is_error")]
if valid_codes:
    target = st.selectbox("🔮 鎖定預測目標", valid_codes)
    d_plot = next(item for item in p_data if item["code"] == target)
    y = d_plot['hist']['Close'].tail(20).values
    X = np.arange(len(y)).reshape(-1, 1)
    model = LinearRegression().fit(X, y)
    future_y = model.predict(np.array([[len(y)], [len(y)+1], [len(y)+2]]))
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=y, name="實際價格", line=dict(color='#3b82f6', width=3)))
    fig.add_trace(go.Scatter(x=[len(y)-1, len(y), len(y)+1], y=[y[-1]]+list(future_y), name="預測趨勢", line=dict(color='#ff00ff', dash='dash')))
    st.plotly_chart(fig, use_container_width=True)
