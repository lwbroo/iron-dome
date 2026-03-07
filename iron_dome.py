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
        st.sidebar.warning("⚠️ 自動刷新組件異常。")

# 🎨 UI 美化
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 10px; }
    h3 { color: #58a6ff; }
    .stButton button { width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border-radius: 8px; border: none; }
</style>
""", unsafe_allow_html=True)

# 📖 核心標正名字典
STOCK_NAMES = {
    "2330": "台積電", "0052": "富邦科技", "006208": "富邦台50", "4958": "臻鼎-KY",
    "4420": "光明", "00919": "群益精選高息", "0056": "元大高股息", "6683": "雍智科技",
    "1717": "長興", "00929": "復華台灣科技優息", "00981A": "復華美債1-5Y", 
    "00985A": "中信優先金融債", "009816": "債券標的", "NVDA": "輝達", "GC=F": "🔥 國際黃金"
}

def get_name(t, stock_info=None):
    t = t.strip().upper()
    if t in STOCK_NAMES: return STOCK_NAMES[t]
    if stock_info and 'shortName' in stock_info: return stock_info['shortName']
    return t

# ==========================================
# 📡 核心分析函數 (新增頻率偵測)
# ==========================================
def get_tech_data(ticker):
    t = ticker.strip().upper()
    if not t: return None
    symbol = f"{t}.TW" if (t.isdigit() or "A" in t) else t
    if t == "GC=F": symbol = "GC=F"
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo")
        if hist.empty and ".TW" in symbol:
            symbol = symbol.replace(".TW", ".TWO")
            stock = yf.Ticker(symbol)
            hist = stock.history(period="6mo")
        if hist.empty: return None
        
        # --- 💥 配息與頻率偵測邏輯 ---
        div_data = stock.dividends
        freq_str = "不定期"
        last_div = 0
        last_div_date = "N/A"
        
        if not div_data.empty:
            # 抓取最近一次配息
            last_div = div_data.iloc[-1]
            last_div_date = div_data.index[-1].strftime('%m-%d')
            
            # 偵測過去一年的配息次數
            one_year_ago = datetime.datetime.now() - datetime.timedelta(days=365)
            recent_divs = div_data[div_data.index > one_year_ago]
            count = len(recent_divs)
            
            if count >= 10: freq_str = "月配"
            elif 3 <= count <= 5: freq_str = "季配"
            elif count == 2: freq_str = "半年配"
            elif count == 1: freq_str = "年配"
        
        close = hist['Close']
        ma20 = close.rolling(20).mean().iloc[-1]
        
        return {
            "name": get_name(t, stock.info if hasattr(stock, 'info') else None),
            "code": t, "price": close.iloc[-1], "chg": (close.iloc[-1]/close.iloc[-2]-1)*100, 
            "ma20": ma20, "div": last_div, "div_date": last_div_date, "freq": freq_str, "hist": hist
        }
    except: return None

# ==========================================
# 🏰 戰情室介面
# ==========================================
st.title("🏛️ 股票戰情監控中心 (配息頻率強化版)")

with st.sidebar:
    st.header("📈 戰情設定")
    alert_hour = st.slider("每日通知小時", 0, 23, 15)
    if st.button("🔄 手動刷新 UI"): st.rerun()
    st.divider()
    PERMANENT_LIST = "0052, 00981A, 2330, 006208, 4958, 4420, 00919, 009816, 0056, 6683, 1717, 00929"
    my_stocks = st.text_area("📋 監控清單", PERMANENT_LIST, height=150)

# --- 1. 持股防禦與配息數據 ---
st.subheader("🛡️ 持股防禦與配息頻率")
current_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
p_data = [get_tech_data(t) for t in current_list if get_tech_data(t)]

if p_data:
    df = pd.DataFrame([
        {
            "名稱": d['name'], "代號": d['code'], "現價": f"{d['price']:.2f}", 
            "最新配息": f"${d['div']:.2f}", 
            "配息頻率": d['freq'],  # 💥 新增欄位
            "除息日": d['div_date'],
            "狀態": "⚠️ 破線" if d['price'] < d['ma20'] else "✅ 安全"
        } for d in p_data
    ])
    st.table(df)
else:
    st.warning("🔄 數據更新中...")
