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

# 📖 名稱對照表 (更新您的持股)
STOCK_NAMES = {
    "2330": "台積電", "0052": "富邦科技", "006208": "富邦台50", "4958": "臻鼎-KY",
    "00981A": "復華美債(類)", "00985A": "中信債(類)", "009816": "特定債券標的",
    "2603": "長榮", "3017": "奇鋐", "3231": "緯創", "NVDA": "輝達", "GC=F": "🔥 國際黃金"
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

def get_tech_data(ticker):
    t = ticker.strip()
    # 處理台灣代碼與特殊代碼
    symbol = f"{t}.TW" if t.isdigit() and len(t) <= 5 else t
    if "A" in t: symbol = f"{t}.TW" # 處理特別股/類股格式
    if t == "GC=F": symbol = "GC=F"
    
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo")
        if hist.empty: hist = yf.Ticker(symbol.replace(".TW", ".TWO")).history(period="6mo")
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
# 🏰 側邊欄 (自動載入您的持股)
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
    # 自動填入您的最新持股
    default_my = "0052, 00981A, 00985A, 2330, 006208, 009816, 4958"
    my_stocks = st.text_area("📋 目前持股監控", default_my)
    
    # 妖股獵殺池 (增加高波動中小型股)
    default_monster = "3324, 3017, 1519, 2363, 6125, 3231, 2603, 2317, 8046"
    hunt_pool = st.text_area("🚀 妖股獵殺池", default_monster, height=120)

# ==========================================
# 📡 戰情室畫面
# ==========================================
st.title("🏛️ 股票戰情監控中心")

# 1. 持股即時防禦 (自動發送 LINE)
st.subheader("🛡️ 持股防禦狀態")
p_data = [get_tech_data(t) for t in my_stocks.split(",") if get_tech_data(t)]
if p_data:
    defense_list = []
    for d in p_data:
        status = "✅ 安全"
        if d['price'] < d['ma20']:
            status = "⚠️ 破線危險"
            # 破線自動 LINE 通知 (防禦功能)
            if line_token:
                send_line_push(line_token, line_uid, f"🛡️ 戰情室警報：您的持股 {d['name']} ({d['code']}) 已跌破月線，請注意部位！")
        
        defense_list.append({"名稱": d['name'], "代號": d['code'], "現價": f"{d['price']:.2f}", "漲跌": f"{d['chg']:.2f}%", "狀態": status})
    st.table(pd.DataFrame(defense_list))

# 2. 妖股分析：起漲點預測
st.divider()
st.subheader("🔮 妖股回歸預測 (尋找加速轉折)")
target = st.selectbox("選擇獵殺標的", [d['code'] for d in p_data] + [t.strip() for t in hunt_pool.split(",")])
if st.button("執行多項式轉折預測"):
    d = get_tech_data(target)
    hist = d['hist'].tail(20)
    y = hist['Close'].values; X = np.arange(len(y)).reshape(-1, 1)
    # 使用度數 3 的多項式抓取強烈轉折
    poly = PolynomialFeatures(degree=3); model = LinearRegression().fit(poly.fit_transform(X), y)
    future_X = np.arange(len(y), len(y) + 3).reshape(-1, 1); future_y = model.predict(poly.transform(future_X))
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(len(y))), y=y, name="近期股價", line=dict(color='#3b82f6', width=3)))
    fig.add_trace(go.Scatter(x=list(range(len(y)-1, len(y)+3)), y=np.append(y[-1], future_y), name="妖股路徑", line=dict(color='#ff00ff', width=2, dash='dash')))
    fig.update_layout(template="plotly_dark", height=400)
    st.plotly_chart(fig, use_container_width=True)
    st.write(f"💡 結論：模型預測該標的未來 3 天可能路徑，目標價約：{future_y[-1]:.2f}")

# 3. AI 獵殺：起漲妖股掃描
st.divider()
st.subheader("🚀 AI 妖股獵殺掃描 (爆量+起漲)")
if st.button("啟動 AI 獵殺掃描分析", type="primary"):
    if not api_key: st.warning("請設定 API Key")
    else:
        news = get_financial_news()
        candidates = []
        scan_bar = st.progress(0, text="正在全場掃描具有『妖氣』的標的...")
        h_list = [x.strip() for x in hunt_pool.split(",") if x.strip()]
        for i, t in enumerate(h_list):
            scan_bar.progress((i + 1) / len(h_list))
            if d := get_tech_data(t):
                # 妖股起漲邏輯：量能比>1.5(爆量) + RSI在55-70(起漲區) + 站上月線
                if d['vol_ratio'] > 1.5 and 55 < d['rsi'] < 75 and d['price'] > d['ma20']:
                    candidates.append(d)
        scan_bar.empty()
        
        if candidates:
            st.success(f"✅ 捕獲 {len(candidates)} 檔具備『起漲妖股』潛力標的！")
            client = genai.Client(api_key=api_key)
            for c in candidates:
                with st.expander(f"🔥 妖股報告：{c['name']} ({c['code']})", expanded=True):
                    prompt = f"分析台股妖股標的 {c['name']}。技術面：爆量 {c['vol_ratio']:.1f} 倍且 RSI 進入起漲攻擊區。參考新聞：{news[:5]}。請評估今日是否為起漲第一根，並給出獵殺建議。100字內。"
                    res = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
                    st.info(res.text)
        else: st.warning("目前獵殺池內尚未發現具有強烈起漲信號的妖股。")
