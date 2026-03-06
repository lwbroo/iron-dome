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

# 嘗試啟動自動刷新，若遇網路延遲則提供手動備案
if AUTOREFRESH_MODE:
    try:
        st_autorefresh(interval=300000, key="datarefresh")
    except:
        st.sidebar.warning("⚠️ 自動刷新組件異常，請使用手動刷新。")

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

# 📖 名稱對照表 (補全指揮官最新持股)
STOCK_NAMES = {
    "2330": "台積電", "0052": "富邦科技", "006208": "富邦台50", "4958": "臻鼎-KY",
    "4420": "光明", "00981A": "復華美債1-5Y", "00985A": "中信優先金融債", 
    "009816": "債券標的", "2603": "長榮", "3017": "奇鋐", "NVDA": "輝達", "GC=F": "🔥 國際黃金"
}

def get_name(t): return STOCK_NAMES.get(t.strip().upper(), t.strip())

# ==========================================
# 📡 核心分析函數
# ==========================================
def get_financial_news():
    url = "https://news.google.com/rss/search?q=台股+財經+妖股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    return [item.title for item in feed.entries[:8]]

def send_line_push(token, uid, msg):
    if not token or not uid: return None
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": uid, "messages": [{"type": "text", "text": msg}]}
    try: return requests.post(url, headers=headers, json=payload).status_code
    except: return 500

def get_tech_data(ticker):
    t = ticker.strip().upper()
    if not t: return None
    # 自動識別市場 (台股、上櫃、特別股、美股)
    symbol = f"{t}.TW" if (t.isdigit() or "A" in t) else t
    if t == "GC=F": symbol = "GC=F"
    
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo")
        # 二次檢查：若上市沒資料則嘗試上櫃 (.TWO)
        if hist.empty and ".TW" in symbol:
            symbol = symbol.replace(".TW", ".TWO")
            stock = yf.Ticker(symbol)
            hist = stock.history(period="6mo")
            
        if hist.empty: return None
        
        close = hist['Close']
        ma20 = close.rolling(20).mean().iloc[-1]
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain.iloc[-1]/(loss.iloc[-1]+1e-9)))
        vol_ratio = hist['Volume'].iloc[-1] / (hist['Volume'].rolling(5).mean().iloc[-1] + 1e-9)
        macd_h = (close.ewm(span=12).mean() - close.ewm(span=26).mean()).iloc[-1]
        
        return {"name": get_name(t), "code": t, "price": close.iloc[-1], "chg": (close.iloc[-1]/close.iloc[-2]-1)*100, 
                "ma20": ma20, "rsi": rsi, "vol_ratio": vol_ratio, "macd_h": macd_h, "hist": hist}
    except: return None

# ==========================================
# 🏰 戰情室介面啟動
# ==========================================
st.title("🏛️ 股票戰情監控中心")

with st.sidebar:
    st.header("📈 戰情設定")
    if st.button("🔄 立即刷新戰情"): st.rerun()
    st.divider()
    
    sec_gemini = st.secrets.get("GEMINI_API_KEY", "")
    sec_line_t = st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    sec_line_u = st.secrets.get("LINE_USER_ID", "")

    api_key = st.text_input("Gemini API Key", value=sec_gemini, type="password")
    line_token = st.text_input("LINE Token", value=sec_line_t, type="password")
    line_uid = st.text_input("Your User ID", value=sec_line_u)

    st.divider()
    # 預設持股更新
    default_my = "0052, 00981A, 00985A, 2330, 006208, 009816, 4958, 4420"
    my_stocks = st.text_area("📋 持股監控 (代號,逗號格開)", default_my)
    hunt_pool = st.text_area("🚀 妖股獵殺池", "3324, 3017, 1519, 2363, 6125, 3231, 2603")

# --- 1. 全球脈動 ---
pulse_tickers = {"TSM": "台積電ADR", "NVDA": "輝達", "^SOX": "費半指數", "^IXIC": "那指"}
p_cols = st.columns(len(pulse_tickers))
for i, (tic, nm) in enumerate(pulse_tickers.items()):
    try:
        d = yf.Ticker(tic).history(period="2d")
        chg = (d['Close'].iloc[-1]/d['Close'].iloc[-2]-1)*100
        color = "#ff4b4b" if chg < -1.5 else "#00ff00" if chg > 0 else "white"
        p_cols[i].markdown(f"<div class='metric-card'><b>{nm}</b><br><h2 style='color:{color}; margin:0;'>{chg:.2f}%</h2></div>", unsafe_allow_html=True)
    except: p_cols[i].write(f"{nm} 讀取中...")

# --- 2. 持股防禦 ---
st.subheader("🛡️ 持股防禦監控")
current_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
p_data = [get_tech_data(t) for t in current_list if get_tech_data(t)]

if p_data:
    df = pd.DataFrame([
        {"名稱": d['name'], "現價": f"{d['price']:.2f}", "漲跌": f"{d['chg']:.2f}%", 
         "狀態": "⚠️ 破線" if d['price'] < d['ma20'] else "✅ 安全"} for d in p_data
    ])
    st.table(df)
    # LINE 警報觸發 (若破線)
    for d in p_data:
        if d['price'] < d['ma20'] and line_token:
            send_line_push(line_token, line_uid, f"🛡️ 戰情警報：{d['name']} ({d['code']}) 跌破月線！")

# --- 3. 趨勢預測 ---
st.divider()
st.subheader("🔮 數學趨勢路徑 (線性 $y=ax+b$ vs 多項式)")
all_codes = sorted(list(set([d['code'] for d in p_data] + [t.strip() for t in hunt_pool.split(",") if t.strip()])))
target = st.selectbox("分析標的", all_codes)
col_l, col_r = st.columns([1, 2.5])
with col_l:
    algo = st.radio("預測模式", ["線性趨勢 (看大勢)", "多項式轉折 (找妖股)"])
    lookback = st.slider("參考天數", 10, 60, 20)
    
if st.button("執行演算法趨勢預報"):
    d = get_tech_data(target)
    if d:
        y = d['hist']['Close'].tail(lookback).values
        X = np.arange(len(y)).reshape(-1, 1)
        future_X = np.arange(len(y), len(y) + 3).reshape(-1, 1)
        if algo == "線性趨勢 (看大勢)":
            model = LinearRegression().fit(X, y); future_y = model.predict(future_X)
        else:
            pf = PolynomialFeatures(degree=3); model = LinearRegression().fit(pf.fit_transform(X), y)
            future_y = model.predict(pf.transform(future_X))
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=y, name="實際價格", line=dict(color='#3b82f6', width=3)))
        fig.add_trace(go.Scatter(x=[len(y)-1, len(y), len(y)+1], y=[y[-1]]+list(future_y), name="預測趨勢", line=dict(color='#ff00ff', dash='dash')))
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

# --- 4. AI 獵殺 ---
st.divider()
if st.button("🚀 啟動 AI 獵殺掃描", type="primary"):
    if not api_key: st.warning("請設定 API Key")
    else:
        news = get_financial_news()
        st.info("📰 正在掃描具有『妖氣』的標的...")
        candidates = []
        for t in [x.strip() for x in hunt_pool.split(",")]:
            if d := get_tech_data(t):
                if d['vol_ratio'] > 1.3 and 55 < d['rsi'] < 75: candidates.append(d)
        
        if candidates:
            client = genai.Client(api_key=api_key)
            for c in candidates:
                with st.expander(f"🔥 妖股報告：{c['name']} ({c['code']})", expanded=True):
                    prompt = f"分析台股妖股 {c['name']}。爆量且 RSI 轉強。參考新聞：{news[:3]}。100字內給出建議。"
                    res = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
                    st.write(res.text)
        else: st.warning("目前尚未發現起漲妖股。")
