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
    .stButton button { width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border: none; }
    .stButton button:hover { background-color: #2ea043; border: none; }
</style>
""", unsafe_allow_html=True)

# 📖 擴展名稱對照表 (含主動式 ETF、美股、權值股)
STOCK_NAMES = {
    # 核心權值
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2382": "廣達", "2308": "台達電", "3711": "日月光", "2303": "聯電",
    # 關鍵標的
    "2603": "長榮", "2609": "陽明", "3017": "奇鋐", "3324": "雙鴻", "6669": "緯穎", "3231": "緯創", "1519": "華城",
    # 策略/主動式 ETF (2026 焦點)
    "00949": "復華科技優選", "00919": "群益精選高息", "00929": "復華台灣科技優息", "00878": "國泰高股息", "0056": "元大高股息",
    "00940": "元大台灣價值", "00713": "元大低波動", "0050": "元大台灣50", "006208": "富邦台50",
    # 國際連動
    "GC=F": "🔥 國際黃金", "TSM": "台積電ADR", "NVDA": "輝達", "AAPL": "蘋果", "SOXX": "費半ETF"
}

def get_name(t): return STOCK_NAMES.get(t.strip(), t.strip())

# ==========================================
# 📡 核心分析函數
# ==========================================
def send_line_push(token, uid, msg):
    if not token or not uid: return None
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": uid, "messages": [{"type": "text", "text": msg}]}
    try: r = requests.post(url, headers=headers, json=payload); return r.status_code
    except: return 500

def get_us_pulse():
    tickers = {"TSM": "台積電ADR", "^SOX": "費半", "^IXIC": "那指", "NVDA": "輝達"}
    pulse = {}
    for ticker, name in tickers.items():
        try:
            d = yf.Ticker(ticker).history(period="2d")
            chg = (d['Close'].iloc[-1] / d['Close'].iloc[-2] - 1) * 100
            pulse[name] = chg
        except: pulse[name] = 0
    return pulse

def get_financial_news():
    url = "https://news.google.com/rss/search?q=台股+ETF+財經&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    return [item.title for item in feed.entries[:8]]

def get_tech_data(ticker):
    t = ticker.strip()
    symbol = f"{t}.TW" if t.isdigit() and len(t) <= 5 else t
    if t == "GC=F": symbol = "GC=F"
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo")
        if hist.empty and ".TW" in symbol: hist = yf.Ticker(symbol.replace(".TW", ".TWO")).history(period="6mo")
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
# 🏰 戰情室介面
# ==========================================
st.title("🏛️ 股票戰情監控中心")

with st.sidebar:
    st.header("📈 戰情核心設定")
    api_key = st.text_input("Gemini API Key", type="password")
    line_token = st.text_input("LINE Token", type="password")
    line_uid = st.text_input("LINE User ID")
    st.divider()
    my_stocks = st.text_area("📋 監控清單", "2330, 2454, 3711, 2603, GC=F, 00949")
    
    # 預設全方位擴展獵殺池
    default_hunt = "2330, 2317, 2454, 2382, 2308, 3711, 2303, 6669, 3231, 2603, 2609, 3017, 3324, 1519, 00949, 00919, 00929, 00878, 0056, 00940, 00713, 0050, 006208, TSM, NVDA, GC=F"
    hunt_pool = st.text_area("🚀 獵殺池 (包含主動式 ETF)", default_hunt, height=180)

# 1. 全球脈動
pulse = get_us_pulse()
cols = st.columns(len(pulse))
for i, (name, chg) in enumerate(pulse.items()):
    color = "#ff4b4b" if chg < -2 else "#00ff00" if chg > 0 else "white"
    cols[i].markdown(f"<div class='metric-card'><b>{name}</b><br><h2 style='color:{color}; margin:0;'>{chg:.2f}%</h2></div>", unsafe_allow_html=True)

# 2. 持股防禦
st.subheader("🛡️ 持股防禦監控")
p_data = [get_tech_data(t) for t in my_stocks.split(",") if get_tech_data(t)]
if p_data:
    df = pd.DataFrame([{"名稱": d['name'], "代號": d['code'], "現價": f"{d['price']:.2f}", "漲跌": f"{d['chg']:.2f}%", "狀態": "⚠️ 破線" if d['price'] < d['ma20'] else "✅ 安全"} for d in p_data])
    st.table(df)

# 3. 數學預測：演算法趨勢預報
st.divider()
st.subheader("🔮 數學分析：趨勢預測 (免費)")
col_l, col_r = st.columns([1, 2.5])
with col_l:
    target = st.selectbox("選擇預測標的", [d['code'] for d in p_data])
    algo_type = st.radio("演算邏輯", ["線性 (看大勢)", "多項式 (找轉折)"])
    lookback = st.slider("參考天數", 10, 60, 20)
    predict_days = st.slider("預測未來天數", 1, 7, 3)
    poly_degree = st.slider("多項式次方", 2, 4, 2) if algo_type == "多項式 (找轉折)" else 1

if st.button("執行趨勢預測"):
    d = get_tech_data(target)
    hist = d['hist'].tail(lookback)
    y = hist['Close'].values; X = np.arange(len(y)).reshape(-1, 1)
    future_X = np.arange(len(y), len(y) + predict_days).reshape(-1, 1)
    
    if algo_type == "線性 (看大勢)":
        model = LinearRegression().fit(X, y)
        future_y = model.predict(future_X)
    else:
        poly = PolynomialFeatures(degree=poly_degree)
        model = LinearRegression().fit(poly.fit_transform(X), y)
        future_y = model.predict(poly.transform(future_X))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(len(y))), y=y, name="實際價格", line=dict(color='#3b82f6', width=3)))
    fig.add_trace(go.Scatter(x=list(range(len(y)-1, len(y)+predict_days)), y=np.append(y[-1], future_y), name="預測延伸", line=dict(color='#ef4444', dash='dash')))
    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.write(f"💡 結論：預計 {predict_days} 天後目標價約 {future_y[-1]:.2f}")

# 4. AI 綜合獵殺評估 (消耗 Token)
st.divider()
st.subheader("🚀 AI 綜合獵殺與新聞分析 (消耗 Token)")
if st.button("啟動 AI 獵殺掃描分析", type="primary"):
    if not api_key: st.warning("⚠️ 請輸入 Gemini API Key")
    else:
        news = get_financial_news()
        st.info("📰 正在讀取前夜財經與 ETF 專欄新聞...")
        for n in news[:3]: st.write(f"- {n}")
        
        candidates = []
        scan_bar = st.progress(0, text="正在掃描全市場與主動式 ETF...")
        h_list = [x.strip() for x in hunt_pool.split(",") if x.strip()]
        for i, t in enumerate(h_list):
            scan_bar.progress((i + 1) / len(h_list))
            if d := get_tech_data(t):
                # 獵殺邏輯：爆量 + 站上月線 + MACD紅柱
                if d['vol_ratio'] > 1.2 and d['price'] > d['ma20'] and d['macd_h'] > 0:
                    candidates.append(d)
        scan_bar.empty()
        
        if candidates:
            st.success(f"✅ 發現 {len(candidates)} 檔具攻擊潛力標的！AI 解讀中...")
            client = genai.Client(api_key=api_key)
            for c in candidates:
                with st.expander(f"📈 戰略建議：{c['name']} ({c['code']})", expanded=True):
                    prompt = f"分析台股/ETF {c['name']}。技術面：帶量站上月線，MACD轉正。參考新聞：{news[:5]}。請結合今日市場氣氛與技術面，給出3天內的操作建議。100字內。"
                    response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
                    st.write(response.text)
        else: st.warning("目前獵殺池未發現強勢標的。")
