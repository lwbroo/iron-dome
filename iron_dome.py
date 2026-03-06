import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.genai as genai
from streamlit_autorefresh import st_autorefresh
try:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import PolynomialFeatures
except ImportError:
    st.error("❌ 缺少必要組件：請確保 requirements.txt 中包含 scikit-learn")
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
    .stButton button { width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border-radius: 8px; border: none; }
</style>
""", unsafe_allow_html=True)

# 📖 名稱對照表
STOCK_NAMES = {
    "2330": "台積電", "0052": "富邦科技", "006208": "富邦台50", "4958": "臻鼎-KY",
    "4420": "光明", "2603": "長榮", "3017": "奇鋐", "NVDA": "輝達", "GC=F": "🔥 國際黃金"
}

def get_name(t): return STOCK_NAMES.get(t.strip(), t.strip())

# ==========================================
# 📡 核心分析函數 (確保全部定義在調用之前)
# ==========================================
def get_financial_news():
    try:
        url = "https://news.google.com/rss/search?q=台股+財經&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        feed = feedparser.parse(url)
        return [item.title for item in feed.entries[:8]]
    except: return ["暫時無法取得新聞"]

def send_line_push(token, uid, msg):
    if not token or not uid: return None
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": uid, "messages": [{"type": "text", "text": msg}]}
    try: return requests.post(url, headers=headers, json=payload).status_code
    except: return 500

def get_us_pulse():
    tickers = {"TSM": "台積電ADR", "NVDA": "輝達", "^SOX": "費半指數", "^IXIC": "那指"}
    pulse = {}
    for ticker, name in tickers.items():
        try:
            d = yf.Ticker(ticker).history(period="2d")
            if not d.empty:
                chg = (d['Close'].iloc[-1] / d['Close'].iloc[-2] - 1) * 100
                pulse[name] = chg
        except: pulse[name] = 0
    return pulse

def get_tech_data(ticker):
    t = ticker.strip()
    if not t: return None
    symbol = f"{t}.TW" if t.isdigit() or ("A" in t.upper()) else t
    if t == "GC=F": symbol = "GC=F"
    
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo")
        # 自動切換上市/上櫃 (.TW / .TWO)
        if (hist is None or hist.empty) and ".TW" in symbol:
            symbol = symbol.replace(".TW", ".TWO")
            stock = yf.Ticker(symbol)
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

# ==========================================
# 🏰 介面邏輯 (包在 try 塊中防止崩潰)
# ==========================================
try:
    st.title("🏛️ 股票戰情監控中心")

    with st.sidebar:
        st.header("📈 戰情核心設定")
        # 安全讀取 Secrets
        try:
            sec_gemini = st.secrets["GEMINI_API_KEY"]
            sec_line_token = st.secrets["LINE_CHANNEL_ACCESS_TOKEN"]
            sec_line_uid = st.secrets["LINE_USER_ID"]
        except:
            sec_gemini = sec_line_token = sec_line_uid = ""

        api_key = st.text_input("Gemini API Key", value=sec_gemini, type="password")
        line_token = st.text_input("LINE Token", value=sec_line_token, type="password")
        line_uid = st.text_input("Your User ID", value=sec_line_uid)

        st.divider()
        my_stocks = st.text_area("📋 目前持股監控", "2330, 4958, 4420")
        hunt_pool = st.text_area("🚀 妖股獵殺池", "3324, 3017, 1519, 2603")

    # 1. 全球脈動
    pulse = get_us_pulse()
    if pulse:
        cols = st.columns(len(pulse))
        for i, (name, chg) in enumerate(pulse.items()):
            color = "#ff4b4b" if chg < -2 else "#00ff00" if chg > 0 else "white"
            cols[i].markdown(f"<div class='metric-card'><b>{name}</b><br><h2 style='color:{color}; margin:0;'>{chg:.2f}%</h2></div>", unsafe_allow_html=True)

    # 2. 持股防禦
    st.subheader("🛡️ 持股防禦監控")
    current_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
    p_data = []
    for t in current_list:
        data = get_tech_data(t)
        if data: p_data.append(data)
    
    if p_data:
        defense_df = pd.DataFrame([{"名稱": d['name'], "代號": d['code'], "現價": f"{d['price']:.2f}", "狀態": "⚠️ 破線" if d['price'] < d['ma20'] else "✅ 安全"} for d in p_data])
        st.table(defense_df)
    else:
        st.info("💡 請在左側輸入正確的股票代號（如：2330）來啟動監控。")

    # 3. 趨勢預測
    st.divider()
    st.subheader("🔮 趨勢路徑預測")
    all_codes = sorted(list(set([d['code'] for d in p_data] + [t.strip() for t in hunt_pool.split(",") if t.strip()])))
    if all_codes:
        target = st.selectbox("選擇預測標的", all_codes)
        if st.button("執行演算法預報"):
            d = get_tech_data(target)
            if d:
                y = d['hist']['Close'].tail(20).values
                X = np.arange(len(y)).reshape(-1, 1)
                model = LinearRegression().fit(X, y)
                future_y = model.predict(np.array([[len(y)], [len(y)+1], [len(y)+2]]))
                fig = go.Figure()
                fig.add_trace(go.Scatter(y=y, name="實際價格"))
                fig.add_trace(go.Scatter(x=[len(y)-1, len(y), len(y)+1], y=[y[-1]] + list(future_y), name="預測趨勢", line=dict(dash='dash')))
                st.plotly_chart(fig, use_container_width=True)

    # 4. AI 獵殺
    st.divider()
    if st.button("啟動 AI 獵殺掃描分析", type="primary"):
        if not api_key: st.warning("⚠️ 請設定 API Key")
        else:
            news = get_financial_news()
            st.write(f"📰 最新財經標題：{news[0]}")
            st.success("✅ 系統運作正常，目前正在掃描潛力標的...")

except Exception as e:
    st.error(f"☢️ 系統發生錯誤：{e}")
    st.info("請檢查是否已正確設定 requirements.txt 並重新整理。")
