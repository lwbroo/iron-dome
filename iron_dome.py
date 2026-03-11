import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import datetime
from sklearn.linear_model import LinearRegression

# 💥 安全載入 AI 零件，避免 Module 缺失導致整機崩潰
try:
    import google.generativeai as genai
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# ==========================================
# ⚙️ 系統設定 & 版本控制
# ==========================================
VERSION = "v8.0.1"
APP_NAME = "股票戰情監控中心"

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon="📈")

# 🎨 UI 戰情室美化
st.markdown(f"""
<style>
    .stApp {{ background-color: #0d1117; color: #c9d1d9; }}
    .dividend-box {{ background-color: #1e2327; padding: 20px; border-radius: 10px; border-left: 5px solid #238636; margin: 10px 0; }}
    .ai-box {{ background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #58a6ff; margin-top: 20px; }}
    h3 {{ color: #58a6ff; }}
    .stButton button {{ width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border-radius: 8px; border: none; }}
    /* 💥 指揮官要求：版本號顯示於左下角 */
    .version-footer {{ position: fixed; bottom: 10px; left: 10px; font-size: 11px; color: #8b949e; z-index: 999; background: rgba(13,17,23,0.8); padding: 2px 5px; border-radius: 3px; }}
</style>
""", unsafe_allow_html=True)

# 📖 14 檔精銳部隊 (確保名稱與代號嚴格對齊)
STOCK_NAMES = {
    "^TWII": "台股大盤", 
    "TSM": "台積電 ADR (夜盤)", 
    "2330": "台積電", 
    "0052": "富邦科技", 
    "006208": "富邦台50", 
    "4958": "臻鼎-KY", 
    "4420": "光明", 
    "00919": "群益精選高息", 
    "0056": "元大高股息", 
    "6683": "雍智科技", 
    "1717": "長興", 
    "00929": "復華台灣科技優息", 
    "00981A": "復華美債1-5Y", 
    "GC=F": "🔥 國際黃金"
}

# ==========================================
# 📡 戰情核心函數
# ==========================================
def get_tech_data(ticker):
    t = ticker.strip().upper()
    if not t: return None
    # 🕵️ 指標特殊處理，確保夜盤資料不失聯
    if t.startswith("^") or t in ["TSM", "GC=F"]:
        symbol_list = [t]
    else:
        symbol_list = [f"{t}.TW", f"{t}.TWO", t]
    
    hist, stock_obj = None, None
    for symbol in symbol_list:
        try:
            stock_obj = yf.Ticker(symbol)
            temp_hist = stock_obj.history(period="6mo")
            if not temp_hist.empty:
                hist = temp_hist; break
        except: continue
            
    if hist is None or hist.empty:
        return {"code": t, "name": STOCK_NAMES.get(t, t), "is_error": True}

    # 💎 股息與頻率
    div_data = stock_obj.dividends
    last_div = div_data.iloc[-1] if not div_data.empty else 0
    freq_mult = 1
    if not div_data.empty:
        count = len(div_data[div_data.index > (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=365))])
        freq_mult = 12 if count >= 10 else (4 if 3 <= count <= 5 else (2 if count == 2 else 1))

    close = hist['Close']
    ma20 = close.rolling(20).mean().iloc[-1]
    return {
        "name": STOCK_NAMES.get(t, t), "code": t, "price": close.iloc[-1], 
        "chg": (close.iloc[-1]/close.iloc[-2]-1)*100, "ma20": ma20, 
        "div": last_div, "multiplier": freq_mult, "hist": hist, "is_error": False
    }

def get_ai_analysis(api_key, market_summary):
    if not AI_AVAILABLE:
        return "⚠️ 系統組件遺失：請先在 requirements.txt 加入 google-generativeai"
    if not api_key:
        return "⚠️ 請輸入 Gemini API Key 以啟動 AI 參謀。"
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"你是操盤參謀GiGi。Kurt持有1152股台積電(2330)，目標5千萬退休。分析：{market_summary}。請給專業幽默的建議。"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ AI 運算異常: {str(e)}"

# ==========================================
# 🏰 戰情室介面
# ==========================================
st.title(f"🏛️ {APP_NAME}")
st.markdown(f'<div class="version-footer">系統版本: {VERSION}</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("📈 戰情設定")
    if st.button("🔄 刷新全場雷達"): st.rerun()
    st.divider()
    ai_key = st.text_input("🔑 Gemini API Key", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
    
    st.divider()
    PERMANENT_LIST = "^TWII, TSM, 2330, 0052, 006208, 4958, 4420, 00919, 0056, 6683, 1717, 00929, 00981A, GC=F"
    my_stocks = st.text_area("📋 監控名單", PERMANENT_LIST, height=180)
    shares_input = st.text_area("依序張數", "0,0,1.152,0,0,0,0,0,0,0,0,0,0,0")

# --- 數據同步 ---
current_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
shares_list = [float(s.strip()) for s in shares_input.split(",")]
p_data, total_div, summary_text = [], 0, ""

with st.spinner('📡 數據同步中...'):
    for idx, t in enumerate(current_list):
        data = get_tech_data(t)
        if data and not data.get("is_error"):
            shares = shares_list[idx] if idx < len(shares_list) else 0
            total_div += (data['div'] * data['multiplier'] * 1000 * shares)
            p_data.append(data)
            summary_text += f"{data['name']}: {data['price']:.2f}, "

# --- UI 渲染 ---
st.markdown(f'<div class="dividend-box"><h3 style="margin:0; color:#238636;">💰 年度預計配息總額：NT$ {total_div:,.0f}</h3></div>', unsafe_allow_html=True)

st.subheader("🛡️ 持股防禦與先行指標 (夜盤)")
if p_data:
    df_rows = []
    for d in p_data:
        status = "✅ 安全" if d['price'] >= d['ma20'] else "⚠️ 破線"
        # 💥 精確校準：名稱 (代號) 格式
        df_rows.append({
            "名稱 (代號)": f"{d['name']} ({d['code']})", 
            "張數": f"{shares_list[p_data.index(d)]:.3f}",
            "現價": f"{d['price']:.2f}", 
            "漲跌幅": f"{d['chg']:+.2f}%",
            "月線": f"{d['ma20']:.2f}", 
            "狀態": status
        })
    st.table(pd.DataFrame(df_rows))

st.divider()
st.subheader("🧠 AI 參謀戰略評論")
if st.button("🪄 生成 AI 深度分析"):
    st.markdown(f'<div class="ai-box">{get_ai_analysis(ai_key, summary_text)}</div>', unsafe_allow_html=True)
