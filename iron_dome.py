import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import datetime
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

# ==========================================
# ⚙️ 系統設定
# ==========================================
st.set_page_config(page_title="股票戰情監控中心", layout="wide", page_icon="📈")

# 🎨 UI 美化
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 10px; }
    h3 { color: #58a6ff; }
    .stButton button { width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border-radius: 8px; border: none; }
</style>
""", unsafe_allow_html=True)

# 📖 12 檔核心部隊字典
STOCK_NAMES = {
    "2330": "台積電", "0052": "富邦科技", "006208": "富邦台50", "4958": "臻鼎-KY",
    "4420": "光明", "00919": "群益精選高息", "0056": "元大高股息", "6683": "雍智科技",
    "1717": "長興", "00929": "復華台灣科技優息", "00981A": "復華美債1-5Y", 
    "009816": "特定債券標的", "NVDA": "輝達", "GC=F": "🔥 國際黃金"
}

# ==========================================
# 📡 核心分析函數 (Yahoo 優先 + 法說會偵測)
# ==========================================
def send_line_push(token, uid, msg):
    if not token or not uid: return None
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": uid, "messages": [{"type": "text", "text": msg}]}
    try: return requests.post(url, headers=headers, json=payload, timeout=8).status_code
    except: return 500

def get_tech_data(ticker):
    t = ticker.strip().upper()
    if not t: return None
    
    # 🕵️ 多重路徑偵測：解決上櫃股抓不到的問題
    suffixes = [".TW", ".TWO", ""]
    hist = None
    stock_obj = None
    
    for s in suffixes:
        symbol = f"{t}{s}" if (t.isdigit() or "A" in t) else t
        if t == "GC=F": symbol = "GC=F"
        try:
            stock_obj = yf.Ticker(symbol)
            temp_hist = stock_obj.history(period="3mo")
            if not temp_hist.empty:
                hist = temp_hist
                break
        except: continue
            
    if hist is None or hist.empty:
        return {"code": t, "name": STOCK_NAMES.get(t, t), "is_error": True}

    # 💎 獲取法說會 (Earnings Date) 與 配息
    next_event = "待公布"
    try:
        cal = stock_obj.calendar
        # 偵測下一場法說會日期
        if cal is not None and 'Earnings Date' in cal:
            event_dates = cal['Earnings Date']
            if isinstance(event_dates, list) and len(event_dates) > 0:
                next_event = event_dates[0].strftime('%Y-%m-%d')
    except: pass

    div_data = stock_obj.dividends
    last_div = div_data.iloc[-1] if not div_data.empty else 0
    
    # 頻率偵測
    freq = "年配"
    if not div_data.empty:
        now_tz = pd.Timestamp.now(tz='UTC')
        if div_data.index.tz is None: div_data.index = div_data.index.tz_localize('UTC')
        count = len(div_data[div_data.index > (now_tz - pd.Timedelta(days=365))])
        if count >= 10: freq = "月配"
        elif 3 <= count <= 5: freq = "季配"
        elif count == 2: freq = "半年配"

    close = hist['Close']
    ma20 = close.rolling(20).mean().iloc[-1]
    
    return {
        "name": STOCK_NAMES.get(t, t), "code": t, "price": close.iloc[-1], 
        "chg": (close.iloc[-1]/close.iloc[-2]-1)*100, "ma20": ma20, 
        "div": last_div, "freq": freq, "event": next_event, "hist": hist, "is_error": False
    }

# ==========================================
# 🏰 戰情室主視覺
# ==========================================
st.title("🏛️ 股票戰情監控中心 (法說會與記憶強化版)")

with st.sidebar:
    st.header("📈 戰情監控設定")
    if st.button("🔄 刷新全場雷達"): st.rerun()
    st.divider()
    line_token = st.text_input("LINE Token", value=st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN", ""), type="password")
    line_uid = st.text_input("Your User ID", value=st.secrets.get("LINE_USER_ID", ""))
    
    st.divider()
    # 💥 指揮官的 12 檔永久記憶名單
    PERMANENT_LIST = "2330, 0052, 006208, 4958, 4420, 00919, 009816, 0056, 6683, 1717, 00929, 00981A"
    my_stocks = st.text_area("📋 核心部隊清單 (永久記憶)", PERMANENT_LIST, height=180)

# --- 數據同步 ---
current_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
p_data = []
broken_list = []

with st.spinner('📡 正在從 Yahoo Finance 接收法說會與股價數據...'):
    for t in current_list:
        data = get_tech_data(t)
        if data:
            p_data.append(data)
            if not data.get("is_error") and data['price'] < data['ma20']:
                broken_list.append(f"• {data['name']} ({data['code']})")

# --- 顯示防禦表格 ---
st.subheader("🛡️ 持股防禦、配息與法說會監控")
if p_data:
    df = pd.DataFrame([
        {
            "名稱": d['name'], "代號": d['code'], "現價": f"{d['price']:.2f}", 
            "最新配息": f"${d['div']:.2f}", "配息頻率": d['freq'], 
            "預計法說會": d['event'], # 💥 新增欄位
            "狀態": "⚠️ 破線" if d['price'] < d['ma20'] else "✅ 安全"
        } for d in p_data
    ])
    st.table(df)

    # LINE 彙整通知
    if broken_list and line_token and line_uid:
        if "last_alert" not in st.session_state:
            report = "🚨 戰情中心破線警報：\n" + "\n".join(broken_list)
            if send_line_push(line_token, line_uid, report) == 200:
                st.session_state["last_alert"] = report
else:
    st.warning("🔄 數據更新中，請確保網路暢通...")

# --- 趨勢預測 ---
st.divider()
valid_codes = [d['code'] for d in p_data if not d.get("is_error")]
if valid_codes:
    target = st.selectbox("🔮 選擇預測目標", valid_codes)
    d_plot = next(item for item in p_data if item["code"] == target)
    y = d_plot['hist']['Close'].tail(20).values
    X = np.arange(len(y)).reshape(-1, 1)
    model = LinearRegression().fit(X, y)
    future_y = model.predict(np.array([[len(y)], [len(y)+1], [len(y)+2]]))
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=y, name="實際價格", line=dict(color='#3b82f6', width=3)))
    fig.add_trace(go.Scatter(x=[len(y)-1, len(y), len(y)+1], y=[y[-1]]+list(future_y), name="預測趨勢", line=dict(color='#ff00ff', dash='dash')))
    st.plotly_chart(fig, use_container_width=True)
