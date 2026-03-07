import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.genai as genai
import plotly.graph_objects as go
import requests
import feedparser
import datetime
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

# ==========================================
# ⚙️ 系統設定
# ==========================================
st.set_page_config(page_title="股票戰情監控中心", layout="wide", page_icon="📈")

# 🎨 UI 美化
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 10px; }
    h3 { color: #58a6ff; }
    .stButton button { width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border-radius: 8px; border: none; }
    .stTable { background-color: #0d1117; }
</style>
""", unsafe_allow_html=True)

# 📖 核心字典 (確保這 12 檔都有名字)
STOCK_NAMES = {
    "2330": "台積電", "0052": "富邦科技", "006208": "富邦台50", "4958": "臻鼎-KY",
    "4420": "光明", "00919": "群益精選高息", "0056": "元大高股息", "6683": "雍智科技",
    "1717": "長興", "00929": "復華台灣科技優息", "00981A": "復華美債1-5Y", 
    "009816": "特定債券標的", "NVDA": "輝達", "GC=F": "🔥 國際黃金"
}

def get_name(t, info=None):
    t = t.strip().upper()
    if t in STOCK_NAMES: return STOCK_NAMES[t]
    if info and 'shortName' in info: return info['shortName']
    return t

# ==========================================
# 📡 強化版資料抓取 (防止標的遺失)
# ==========================================
def get_tech_data(ticker):
    t = ticker.strip().upper()
    if not t: return None
    
    # 嘗試不同的後綴組合
    suffixes = [".TW", ".TWO", ""]
    hist = None
    final_symbol = ""
    
    for s in suffixes:
        symbol = f"{t}{s}" if (t.isdigit() or "A" in t) else t
        if t == "GC=F": symbol = "GC=F"
        
        try:
            stock = yf.Ticker(symbol)
            # 縮短抓取範圍以加快速度
            temp_hist = stock.history(period="3mo") 
            if not temp_hist.empty:
                hist = temp_hist
                final_symbol = symbol
                break
        except:
            continue
            
    if hist is None or hist.empty:
        return {"code": t, "name": STOCK_NAMES.get(t, t), "error": True}

    # 配息邏輯
    div_data = stock.dividends
    last_div = div_data.iloc[-1] if not div_data.empty else 0
    
    # 頻率偵測
    freq = "年配"
    if not div_data.empty:
        one_year = div_data[div_data.index > (datetime.datetime.now() - datetime.timedelta(days=365))]
        count = len(one_year)
        if count >= 10: freq = "月配"
        elif 3 <= count <= 5: freq = "季配"
        elif count == 2: freq = "半年配"

    close = hist['Close']
    ma20 = close.rolling(20).mean().iloc[-1]
    
    return {
        "name": get_name(t, stock.info if hasattr(stock, 'info') else None),
        "code": t, "price": close.iloc[-1], "chg": (close.iloc[-1]/close.iloc[-2]-1)*100, 
        "ma20": ma20, "div": last_div, "freq": freq, "hist": hist, "error": False
    }

# ==========================================
# 🏰 戰情室主視覺
# ==========================================
st.title("🏛️ 股票戰情監控中心 (全編制修復版)")

with st.sidebar:
    st.header("📈 戰術面板")
    if st.button("🔄 強制重整數據"): st.rerun()
    st.divider()
    PERMANENT_LIST = "0052, 00981A, 2330, 006208, 4958, 4420, 00919, 009816, 0056, 6683, 1717, 00929"
    my_stocks = st.text_area("📋 12 檔核心部隊", PERMANENT_LIST, height=150)

# --- 核心數據處理 ---
current_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
p_data = []

# 使用進度條讓指揮官知道進度
progress_text = "📡 正在與交易所同步數據..."
my_bar = st.progress(0, text=progress_text)

for idx, t in enumerate(current_list):
    data = get_tech_data(t)
    if data:
        p_data.append(data)
    my_bar.progress((idx + 1) / len(current_list), text=f"正在同步: {get_name(t)} ({t})")
my_bar.empty()

# --- 顯示表格 ---
st.subheader("🛡️ 持股防禦與配息清單")
if p_data:
    display_rows = []
    for d in p_data:
        if d.get("error"):
            display_rows.append({"名稱": d['name'], "代號": d['code'], "現價": "連線失敗", "配息": "-", "頻率": "-", "狀態": "❌ 訊號中斷"})
        else:
            status = "✅ 安全"
            if d['price'] < d['ma20']: status = "⚠️ 破線"
            display_rows.append({
                "名稱": d['name'], "代號": d['code'], "現價": f"{d['price']:.2f}", 
                "最新配息": f"${d['div']:.2f}", "頻率": d['freq'], "狀態": status
            })
    st.table(pd.DataFrame(display_rows))

# --- 趨勢預測區 ---
st.divider()
valid_codes = [d['code'] for d in p_data if not d.get("error")]
if valid_codes:
    target = st.selectbox("🔮 選擇預測目標", valid_codes)
    # ... (後續預測繪圖邏輯與之前相同，確保 d 是從有效數據中抓取)
    d_plot = next(item for item in p_data if item["code"] == target)
    y = d_plot['hist']['Close'].tail(20).values
    X = np.arange(len(y)).reshape(-1, 1)
    model = LinearRegression().fit(X, y)
    future_y = model.predict(np.array([[len(y)], [len(y)+1], [len(y)+2]]))
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=y, name="實際價格", line=dict(color='#3b82f6', width=3)))
    fig.add_trace(go.Scatter(x=[len(y)-1, len(y), len(y)+1], y=[y[-1]]+list(future_y), name="預測趨勢", line=dict(color='#ff00ff', dash='dash')))
    st.plotly_chart(fig, use_container_width=True)
