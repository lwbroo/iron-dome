import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import datetime
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

# 💥 安全載入 AI 模組
try:
    import google.generativeai as genai
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# ==========================================
# ⚙️ 系統設定 & 版本控制
# ==========================================
VERSION = "v8.0.3"
APP_NAME = "股票戰情監控中心"

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon="📈")

# 🎨 UI 戰情室美化
st.markdown(f"""
<style>
    .stApp {{ background-color: #0d1117; color: #c9d1d9; }}
    .dividend-box {{ background-color: #1e2327; padding: 20px; border-radius: 10px; border-left: 5px solid #238636; margin: 10px 0; }}
    .ai-box {{ background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #58a6ff; margin-top: 10px; }}
    .news-box {{ background-color: #1c2128; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }}
    h3 {{ color: #58a6ff; }}
    .stButton button {{ width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border-radius: 8px; border: none; }}
    /* 💥 指揮官要求：版本號顯示於左下角 */
    .version-footer {{ position: fixed; bottom: 10px; left: 10px; font-size: 11px; color: #8b949e; z-index: 999; background: rgba(13,17,23,0.8); padding: 2px 5px; border-radius: 3px; }}
</style>
""", unsafe_allow_html=True)

# 📖 14 檔精銳部隊 (確保名稱與代號嚴格對齊)
STOCK_NAMES = {
    "^TWII": "台股大盤", "TSM": "台積電 ADR (夜盤)", "2330": "台積電", "0052": "富邦科技", 
    "006208": "富邦台50", "4958": "臻鼎-KY", "4420": "光明", "00919": "群益精選高息", 
    "0056": "元大高股息", "6683": "雍智科技", "1717": "長興", "00929": "復華台灣科技優息", 
    "00981A": "復華美債1-5Y", "GC=F": "🔥 國際黃金"
}

# ==========================================
# 📡 戰情核心函數
# ==========================================
def get_tech_data(ticker):
    t = ticker.strip().upper()
    if not t: return None
    symbol_list = [t] if (t.startswith("^") or t in ["TSM", "GC=F"]) else [f"{t}.TW", f"{t}.TWO", t]
    hist, stock_obj = None, None
    for symbol in symbol_list:
        try:
            stock_obj = yf.Ticker(symbol)
            temp_hist = stock_obj.history(period="6mo")
            if not temp_hist.empty:
                hist = temp_hist; break
        except: continue
    if hist is None or hist.empty: return {"code": t, "name": STOCK_NAMES.get(t, t), "is_error": True}

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
    if not AI_AVAILABLE: return "⚠️ 請在 requirements.txt 加入 google-generativeai"
    if not api_key: return "⚠️ 請在側邊欄輸入 API Key 以啟動 AI 參謀。"
    try:
        genai.configure(api_key=api_key)
        # 💥 修正點：改用更穩定的模型名稱，並增加異常處理
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"你是操盤參謀GiGi。指揮官Kurt持有1152股台積電(2330)，目標5千萬退休金。今日市場數據：{market_summary}。請給出專業、幽默且精確的戰略建議，並點評台積電與夜盤ADR的關係。"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        # 如果 flash-latest 也失敗，嘗試 fallback 到 gemini-1.5-flash
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            return response.text
        except:
            return f"❌ AI 腦部掃描失敗 (Error 404): 模型名稱或 API 版本不匹配。請檢查 API Key 權限或更新函式庫版本。具體錯誤: {str(e)}"

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
            summary_text += f"{data['name']}: {data['price']:.2f}({data['chg']:+.2f}%), "

# --- UI 渲染 ---
st.markdown(f'<div class="dividend-box"><h3 style="margin:0; color:#238636;">💰 年度預計配息總額：NT$ {total_div:,.0f}</h3></div>', unsafe_allow_html=True)

st.subheader("🛡️ 持股防禦與先行指標 (夜盤)")
if p_data:
    df_rows = []
    for d in p_data:
        status = "✅ 安全" if d['price'] >= d['ma20'] else "⚠️ 破線"
        df_rows.append({
            "名稱 (代號)": f"{d['name']} ({d['code']})", 
            "張數": f"{shares_list[current_list.index(d['code'])]:.3f}",
            "現價": f"{d['price']:.2f}", 
            "漲跌幅": f"{d['chg']:+.2f}%", 
            "月線": f"{d['ma20']:.2f}", 
            "狀態": status
        })
    st.table(pd.DataFrame(df_rows))

# --- 📈 趨勢分析 ---
st.divider()
st.subheader("🔮 趨勢路測 (先行指標)")
col_sel, col_algo, col_days = st.columns([1, 1, 1])
target = col_sel.selectbox("選擇分析標的", [d['code'] for d in p_data], index=1)
algo_type = col_algo.radio("預測模式", ["線性趨勢", "多項式轉折"])
lookback = col_days.slider("參考天數", 10, 60, 20)
if st.button("執行演算法"):
    d_plot = next(item for item in p_data if item["code"] == target)
    y = d_plot['hist']['Close'].tail(lookback).values
    X = np.arange(len(y)).reshape(-1, 1)
    future_X = np.arange(len(y), len(y) + 3).reshape(-1, 1)
    if algo_type == "線性趨勢":
        model = LinearRegression().fit(X, y)
        future_y = model.predict(future_X)
    else:
        pf = PolynomialFeatures(degree=3)
        model = LinearRegression().fit(pf.fit_transform(X), y)
        future_y = model.predict(pf.transform(future_X))
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=y, name="實際價格", line=dict(color='#3b82f6')))
    fig.add_trace(go.Scatter(x=[len(y)-1, len(y), len(y)+1], y=[y[-1]]+list(future_y), name="預測", line=dict(color='#ff00ff', dash='dash')))
    st.plotly_chart(fig, use_container_width=True)

# --- 📰 News & AI ---
st.divider()
st.subheader("🧠 AI 參謀戰略評論")
if st.button("🪄 生成 AI 深度分析"):
    st.markdown(f'<div class="ai-box">{get_ai_analysis(ai_key, summary_text)}</div>', unsafe_allow_html=True)

st.divider()
st.subheader("📰 市場即時戰訊")
st.info("""
**今日關鍵焦點：**
- **台積電 (2330) V 轉成功**：收盤價 1,940 元站穩重要支撐。
- **夜盤指標 (TSM)**：美股盤前表現將決定明日開盤動能，目前處於溢價回穩狀態。
- **除息行情預熱**：高息 ETF (00919, 00929) 資金回流，關注除息前夕買盤。
""")
