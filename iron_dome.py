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
# ⚙️ 系統設定
# ==========================================
st.set_page_config(page_title="股票戰情監控中心", layout="wide", page_icon="📈")
st_autorefresh(interval=300000, key="datarefresh")

# 🎨 UI 美化
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 10px; }
    .stButton button { width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# 📖 擴展名稱對照表 (已加入 4420 光明)
STOCK_NAMES = {
    "2330": "台積電", "0052": "富邦科技", "006208": "富邦台50", "4958": "臻鼎-KY",
    "4420": "光明", "2603": "長榮", "3017": "奇鋐", "GC=F": "🔥 國際黃金", 
    "00981A": "復華美債", "00985A": "中信債", "009816": "債券標的"
}

def get_name(t): return STOCK_NAMES.get(t.strip(), t.strip())

# ==========================================
# 📡 核心分析函數 (強化上櫃股票辨識)
# ==========================================
def get_tech_data(ticker):
    t = ticker.strip()
    if not t: return None
    
    # 判斷輸入格式並轉換為 Yahoo Finance 代號
    if t.isdigit():
        symbol = f"{t}.TW"
    elif "A" in t.upper():
        symbol = f"{t}.TW"
    else:
        symbol = t
        
    if t == "GC=F": symbol = "GC=F"
    
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo")
        
        # 關鍵 Debug：如果 .TW 沒資料，自動嘗試 .TWO (上櫃股票如光明 4420)
        if (hist is None or hist.empty) and ".TW" in symbol:
            symbol_two = symbol.replace(".TW", ".TWO")
            stock = yf.Ticker(symbol_two)
            hist = stock.history(period="6mo")
            
        if hist is None or hist.empty: return None
        
        close = hist['Close']
        ma20 = close.rolling(20).mean().iloc[-1]
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain.iloc[-1]/(loss.iloc[-1]+1e-9)))
        vol_ratio = hist['Volume'].iloc[-1] / (hist['Volume'].rolling(5).mean().iloc[-1] + 1e-9)
        macd_h = (close.ewm(span=12).mean() - close.ewm(span=26).mean()).iloc[-1]
        
        return {"name": get_name(t), "code": t, "price": close.iloc[-1], "chg": (close.iloc[-1]/close.iloc[-2]-1)*100, 
                "ma20": ma20, "rsi": rsi, "vol_ratio": vol_ratio, "macd_h": macd_h, "hist": hist}
    except: return None

# ... (其餘新聞與 LINE 推播函數保持不變) ...

# ==========================================
# 🏰 側邊欄與介面
# ==========================================
with st.sidebar:
    st.header("📈 戰情設定")
    # 自動載入 Secrets
    sec_gemini = st.secrets.get("GEMINI_API_KEY", "")
    api_key = st.text_input("Gemini API Key", value=sec_gemini, type="password")
    
    st.divider()
    # 指揮官，請在這裡直接輸入「4420」即可
    default_my = "0052, 2330, 4958, 4420" 
    my_stocks = st.text_area("📋 目前持股監控 (請輸入代號，如: 4420)", default_my)
    
# ... (其餘 UI 顯示邏輯與 AI 獵殺按鈕代碼) ...
