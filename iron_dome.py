import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.genai as genai
import plotly.graph_objects as go
import requests
import feedparser
import datetime  # 新增時間模組
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
        st_autorefresh(interval=300000, key="datarefresh") # 維持 5 分鐘刷新 UI
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
    "00985A": "中信優先金融債", "009816": "特定債券標的", "NVDA": "輝達", "GC=F": "🔥 國際黃金"
}

def get_name(t, stock_info=None):
    t = t.strip().upper()
    if t in STOCK_NAMES: return STOCK_NAMES[t]
    if stock_info and 'shortName' in stock_info: return stock_info['shortName']
    return t

# ==========================================
# 📡 核心分析函數
# ==========================================
def send_line_push(token, uid, msg):
    if not token or not uid or token == "" or uid == "": return None
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": uid, "messages": [{"type": "text", "text": msg}]}
    try: 
        res = requests.post(url, headers=headers, json=payload, timeout=8)
        return res.status_code
    except: return 500

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
            stock = yf.Ticker(symbol_two := symbol)
            hist = stock.history(period="6mo")
        if hist.empty: return None
        
        div_data = stock.dividends
        last_div = div_data.iloc[-1] if not div_data.empty else 0
        last_div_date = div_data.index[-1].strftime('%m-%d') if not div_data.empty else "N/A"
        
        close = hist['Close']
        ma20 = close.rolling(20).mean().iloc[-1]
        
        return {
            "name": get_name(t, stock.info if hasattr(stock, 'info') else None),
            "code": t, "price": close.iloc[-1], "chg": (close.iloc[-1]/close.iloc[-2]-1)*100, 
            "ma20": ma20, "div": last_div, "div_date": last_div_date, "hist": hist
        }
    except: return None

# ==========================================
# 🏰 戰情室介面
# ==========================================
st.title("🏛️ 股票戰情監控中心 (每日定時簡報版)")

with st.sidebar:
    st.header("📈 戰情設定")
    # 💥 新增：每日通知小時設定 (預設 15 點，收盤後)
    alert_hour = st.slider("每日通知小時 (24H 格式)", 0, 23, 15)
    
    st.divider()
    line_token = st.text_input("LINE Token", value=st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN", ""), type="password")
    line_uid = st.text_input("Your User ID", value=st.secrets.get("LINE_USER_ID", ""))
    
    if st.button("🔄 手動刷新 UI"): st.rerun()

    st.divider()
    PERMANENT_LIST = "0052, 00981A, 2330, 006208, 4958, 4420, 00919, 009816, 0056, 6683, 1717, 00929"
    my_stocks = st.text_area("📋 監控清單", PERMANENT_LIST, height=150)

# --- 1. 數據分析與定時報警 ---
now = datetime.datetime.now()
current_date = now.strftime("%Y-%m-%d")

current_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
p_data = [get_tech_data(t) for t in current_list if get_tech_data(t)]

if p_data:
    defense_rows = []
    broken_list = [] # 儲存破線名單
    
    for d in p_data:
        status = "✅ 安全"
        if d['price'] < d['ma20']:
            status = "⚠️ 破線"
            broken_list.append(f"• {d['name']} ({d['code']}): 現價 {d['price']:.2f} < 月線 {d['ma20']:.2f}")
        
        defense_rows.append({
            "名稱": d['name'], "代號": d['code'], "現價": f"{d['price']:.2f}", 
            "配息": f"${d['div']:.2f}", "狀態": status
        })
    
    st.table(pd.DataFrame(defense_rows))
    
    # 💥 核心邏輯：每日定時發送 (僅在設定的小時內，且今天還沒發過時發送)
    if broken_list and line_token and line_uid:
        if now.hour == alert_hour:
            # 使用 session_state 來確保「當前連線中」今天只發一次
            if "last_send_date" not in st.session_state or st.session_state["last_send_date"] != current_date:
                report = f"🚨 {current_date} 戰情中心破線日報：\n" + "\n".join(broken_list)
                res = send_line_push(line_token, line_uid, report)
                if res == 200:
                    st.session_state["last_send_date"] = current_date
                    st.sidebar.success(f"✅ 今日戰報已於 {now.strftime('%H:%M')} 送出")
                else:
                    st.sidebar.error(f"❌ 發送失敗，代碼: {res}")
        else:
            st.sidebar.info(f"⏳ 預計通知時間：{alert_hour}:00 (目前 {now.strftime('%H:%M')})")

else:
    st.warning("🔄 數據更新中...")

# --- 2. 趨勢預測 ---
st.divider()
st.subheader("🔮 趨勢路徑預測")
all_codes = sorted(list(set([d['code'] for d in p_data])))
if all_codes:
    target = st.selectbox("分析標的", all_codes)
    if st.button("執行演算法預報"):
        d = get_tech_data(target)
        if d:
            y = d['hist']['Close'].tail(20).values
            X = np.arange(len(y)).reshape(-1, 1)
            model = LinearRegression().fit(X, y)
            future_y = model.predict(np.array([[len(y)], [len(y)+1], [len(y)+2]]))
            fig = go.Figure()
            fig.add_trace(go.Scatter(y=y, name="實際價格", line=dict(color='#3b82f6')))
            fig.add_trace(go.Scatter(x=[len(y)-1, len(y), len(y)+1], y=[y[-1]]+list(future_y), name="預測趨勢", line=dict(color='#ff00ff', dash='dash')))
            st.plotly_chart(fig, use_container_width=True)
