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
    .stButton button { width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# 📖 名稱對照表 (您的最新持股清單)
STOCK_NAMES = {
    "2330": "台積電", "0052": "富邦科技", "006208": "富邦台50", "4958": "臻鼎-KY",
    "00981A": "復華美債1-5Y", "00985A": "中信優先金融債", "009816": "債券標的",
    "2603": "長榮", "3017": "奇鋐", "NVDA": "輝達", "GC=F": "🔥 國際黃金"
}

def get_name(t): return STOCK_NAMES.get(t.strip(), t.strip())

# ==========================================
# 📡 核心分析函數 (修復缺失的函數)
# ==========================================
def get_financial_news():
    """抓取財經新聞情報"""
    url = "https://news.google.com/rss/search?q=台股+財經+妖股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    return [item.title for item in feed.entries[:8]]

def send_line_push(token, uid, msg):
    """發送 LINE 警報"""
    if not token or not uid: return None
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": uid, "messages": [{"type": "text", "text": msg}]}
    try: r = requests.post(url, headers=headers, json=payload); return r.status_code
    except: return 500

def get_us_pulse():
    """美股領先指標偵測"""
    tickers = {"TSM": "台積電ADR", "NVDA": "輝達", "^SOX": "費半指數", "^IXIC": "那指"}
    pulse = {}
    for ticker, name in tickers.items():
        try:
            d = yf.Ticker(ticker).history(period="2d")
            chg = (d['Close'].iloc[-1] / d['Close'].iloc[-2] - 1) * 100
            pulse[name] = chg
        except: pulse[name] = 0
    return pulse

def get_tech_data(ticker):
    """計算技術指標與回歸數據"""
    t = ticker.strip()
    symbol = f"{t}.TW" if t.isdigit() or ("A" in t) else t
    if t == "GC=F": symbol = "GC=F"
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo")
        if hist.empty and ".TW" in symbol:
            hist = yf.Ticker(symbol.replace(".TW", ".TWO")).history(period="6mo")
        if len(hist) < 20: return None
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
# 🏰 側邊欄 (Secrets & 手動持股調整)
# ==========================================
with st.sidebar:
    st.header("📈 戰情核心設定")
    sec_gemini = st.secrets.get("GEMINI_API_KEY", "")
    sec_line_token = st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    sec_line_uid = st.secrets.get("LINE_USER_ID", "")

    api_key = st.text_input("Gemini API Key", value=sec_gemini, type="password")
    line_token = st.text_input("LINE Token", value=sec_line_token, type="password")
    line_uid = st.text_input("Your User ID", value=sec_line_uid)

    st.divider()
    # 這裡就是您可以用來手動增加持股的文字框
    default_my = "0052, 00981A, 00985A, 2330, 006208, 009816, 4958"
    my_stocks = st.text_area("📋 目前持股監控 (可手動增減)", default_my)
    
    # 擴展妖股獵殺池
    default_monster = "3324, 3017, 1519, 2363, 6125, 3231, 2603, 2317, 8046, 3037, 2382"
    hunt_pool = st.text_area("🚀 妖股獵殺池", default_monster, height=120)

# ==========================================
# 📡 戰情室主畫面
# ==========================================
st.title("🏛️ 股票戰情監控中心")

# 1. 全球脈動
pulse = get_us_pulse()
cols = st.columns(len(pulse))
for i, (name, chg) in enumerate(pulse.items()):
    color = "#ff4b4b" if chg < -2 else "#00ff00" if chg > 0 else "white"
    cols[i].markdown(f"<div class='metric-card'><b>{name}</b><br><h2 style='color:{color}; margin:0;'>{chg:.2f}%</h2></div>", unsafe_allow_html=True)

# 2. 持股防禦狀態 (手動輸入會即時出現在這)
st.subheader("🛡️ 持股防禦監控")
current_stock_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
p_data = [get_tech_data(t) for t in current_stock_list if get_tech_data(t)]

if p_data:
    defense_list = []
    for d in p_data:
        status = "✅ 安全"
        if d['price'] < d['ma20']:
            status = "⚠️ 破線危險"
            if line_token: # 若有設定 LINE 就發送
                send_line_push(line_token, line_uid, f"🛡️ 戰情警報：{d['name']} ({d['code']}) 跌破月線！")
        
        defense_list.append({"名稱": d['name'], "代號": d['code'], "現價": f"{d['price']:.2f}", "漲跌": f"{d['chg']:.2f}%", "狀態": status})
    st.table(pd.DataFrame(defense_list))

# 3. 妖股分析：趨勢預測
st.divider()
st.subheader("🔮 趨勢路徑預測 (線性 vs 多項式)")
all_codes = sorted(list(set([d['code'] for d in p_data] + [t.strip() for t in hunt_pool.split(",")])))
target = st.selectbox("選擇分析標的", all_codes)

col_l, col_r = st.columns([1, 2.5])
with col_l:
    algo = st.radio("預測模式", ["線性趨勢", "多項式轉折 (妖股專用)"])
    lookback = st.slider("參考天數", 10, 60, 20)
    
if st.button("執行演算法趨勢預報"):
    d = get_tech_data(target)
    hist = d['hist'].tail(lookback)
    y = hist['Close'].values; X = np.arange(len(y)).reshape(-1, 1)
    future_X = np.arange(len(y), len(y) + 3).reshape(-1, 1)
    
    if algo == "線性趨勢":
        model = LinearRegression().fit(X, y); future_y = model.predict(future_X)
    else:
        pf = PolynomialFeatures(degree=3); model = LinearRegression().fit(pf.fit_transform(X), y)
        future_y = model.predict(pf.transform(future_X))
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(len(y))), y=y, name="實際價格", line=dict(color='#3b82f6', width=3)))
    fig.add_trace(go.Scatter(x=list(range(len(y)-1, len(y)+3)), y=np.append(y[-1], future_y), name="預測趨勢", line=dict(color='#ff00ff', dash='dash')))
    fig.update_layout(template="plotly_dark", height=400)
    st.plotly_chart(fig, use_container_width=True)

# 4. AI 獵殺：起漲妖股掃描
st.divider()
st.subheader("🚀 AI 妖股獵殺掃描 (爆量+起漲)")
if st.button("啟動 AI 獵殺掃描分析", type="primary"):
    if not api_key: st.warning("請設定 API Key")
    else:
        news = get_financial_news() # 這裡現在已經修復了！
        st.info("📰 正在讀取情報並掃描獵殺池...")
        candidates = []
        h_list = [x.strip() for x in hunt_pool.split(",") if x.strip()]
        for t in h_list:
            if d := get_tech_data(t):
                # 妖股邏輯：爆量 + RSI 剛轉強
                if d['vol_ratio'] > 1.3 and 55 < d['rsi'] < 75 and d['price'] > d['ma20']:
                    candidates.append(d)
        
        if candidates:
            client = genai.Client(api_key=api_key)
            for c in candidates:
                with st.expander(f"🔥 妖股報告：{c['name']} ({c['code']})", expanded=True):
                    prompt = f"分析台股妖股 {c['name']}。爆量 {c['vol_ratio']:.1f} 倍且 RSI 剛起漲。參考新聞：{news[:5]}。請評估今日是否為第一根起漲，並給出獵殺建議。100字內。"
                    res = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
                    st.info(res.text)
        else: st.warning("目前尚未發現起漲妖股信號。")
