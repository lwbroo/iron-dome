import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import datetime
from sklearn.linear_model import LinearRegression

# ==========================================
# ⚙️ 系統設定 & 版本號
# ==========================================
VERSION = "v7.4.0"
APP_NAME = "股票戰情監控中心"

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon="📈")

# 🎨 UI 美化
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 10px; }
    .dividend-box { background-color: #1e2327; padding: 20px; border-radius: 10px; border-left: 5px solid #238636; margin: 10px 0; }
    h3 { color: #58a6ff; }
    .stButton button { width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border-radius: 8px; border: none; }
</style>
""", unsafe_allow_html=True)

# 📖 12 檔核心部隊 (永久記憶清單)
STOCK_NAMES = {
    "2330": "台積電", "0052": "富邦科技", "006208": "富邦台50", "4958": "臻鼎-KY",
    "4420": "光明", "00919": "群益精選高息", "0056": "元大高股息", "6683": "雍智科技",
    "1717": "長興", "00929": "復華台灣科技優息", "00981A": "復華美債1-5Y", 
    "009816": "特定債券標的", "NVDA": "輝達", "GC=F": "🔥 國際黃金"
}

# ==========================================
# 📡 核心分析函數
# ==========================================
def send_line_push(token, uid, msg):
    if not token or not uid: return None
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": uid, "messages": [{"type": "text", "text": msg}]}
    try: 
        res = requests.post(url, headers=headers, json=payload, timeout=8)
        if res.status_code == 429: return "429 (流量過載)"
        return res.status_code
    except: return 500

def get_tech_data(ticker):
    t = ticker.strip().upper()
    if not t: return None
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

    # 法說會日期
    event_date_obj = None
    try:
        cal = stock_obj.calendar
        if cal is not None and 'Earnings Date' in cal:
            dates = cal['Earnings Date']
            if isinstance(dates, (list, pd.DatetimeIndex)) and len(dates) > 0:
                event_date_obj = dates[0]
    except: pass

    # 配息與頻率偵測
    div_data = stock_obj.dividends
    last_div = div_data.iloc[-1] if not div_data.empty else 0
    freq_multiplier = 1 # 預設年配
    freq_name = "年配"
    
    if not div_data.empty:
        now_tz = pd.Timestamp.now(tz='UTC')
        if div_data.index.tz is None: div_data.index = div_data.index.tz_localize('UTC')
        count = len(div_data[div_data.index > (now_tz - pd.Timedelta(days=365))])
        if count >= 10: 
            freq_name, freq_multiplier = "月配", 12
        elif 3 <= count <= 5: 
            freq_name, freq_multiplier = "季配", 4
        elif count == 2: 
            freq_name, freq_multiplier = "半年配", 2

    close = hist['Close']
    ma20 = close.rolling(20).mean().iloc[-1]
    return {
        "name": STOCK_NAMES.get(t, t), "code": t, "price": close.iloc[-1], 
        "chg": (close.iloc[-1]/close.iloc[-2]-1)*100, "ma20": ma20, 
        "div": last_div, "freq_name": freq_name, "multiplier": freq_multiplier,
        "event_date": event_date_obj, "hist": hist, "is_error": False
    }

# ==========================================
# 🏰 戰情室介面
# ==========================================
st.title(f"🏛️ {APP_NAME}")

with st.sidebar:
    st.header("📈 戰情設定中心")
    if st.button("🔄 刷新全場雷達"): st.rerun()
    st.divider()
    
    line_token = st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_uid = st.secrets.get("LINE_USER_ID", "")
    
    if st.button("🔔 測試 LINE 通訊"):
        if line_token and line_uid:
            status = send_line_push(line_token, line_uid, f"🚀 {APP_NAME} v{VERSION} 測試：通訊暢通！")
            if status == 200: st.success("發送成功！")
            else: st.error(f"錯誤: {status}")

    st.divider()
    PERMANENT_LIST = "2330, 0052, 006208, 4958, 4420, 00919, 009816, 0056, 6683, 1717, 00929, 00981A"
    my_stocks = st.text_area("📋 核心監控名單", PERMANENT_LIST, height=130)
    
    # 💰 新增：持股張數輸入
    st.subheader("💰 持股張數設定")
    shares_input = st.text_area("依序輸入張數 (用逗號隔開)", "1,0,0,0,0,0,0,0,0,0,0,0", help="請依照上方名單順序填寫持有張數")
    
    st.divider()
    st.caption(f"系統版本: {VERSION}")

# --- 數據同步 ---
today = datetime.date.today()
warning_window = today + datetime.timedelta(days=3)
current_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
shares_list = [float(s.strip()) for s in shares_input.split(",")]

p_data = []
total_annual_dividend = 0

with st.spinner('📡 正在同步法說會、股價與配息預算...'):
    for idx, t in enumerate(current_list):
        data = get_tech_data(t)
        if data and not data.get("is_error"):
            # 計算該標的年預計配息
            shares = shares_list[idx] if idx < len(shares_list) else 0
            # 計算公式：配息金額 * 頻率 * 1000股 * 張數
            annual_div = data['div'] * data['multiplier'] * 1000 * shares
            total_annual_dividend += annual_div
            data['my_shares'] = shares
            p_data.append(data)

# --- 顯示現金流概況 ---
st.markdown(f"""
<div class="dividend-box">
    <h3 style="margin:0; color:#238636;">💰 年度預計配息總額：NT$ {total_annual_dividend:,.0f}</h3>
    <p style="margin:0; color:#8b949e;">基於當前持股張數與最新配息資訊計算 (未含除權息手續費與稅務)</p>
</div>
""", unsafe_allow_html=True)

# --- 顯示防禦表格 ---
st.subheader("🛡️ 持股防禦與大震盪預警")
if p_data:
    display_list = []
    broken_list = []
    for d in p_data:
        evt_str = "待公布"
        status = "✅ 安全"
        if d.get('event_date') is not None:
            try:
                evt_date = d['event_date'].date()
                evt_str = evt_date.strftime('%Y-%m-%d')
                if today <= evt_date <= warning_window: status = "🔥 震盪預警"
            except: pass
        if d['price'] < d['ma20']:
            status = f"⚠️ 破線 ({status})" if "預警" in status else "⚠️ 破線"
            broken_list.append(f"• {d['name']}")

        display_list.append({
            "名稱": d['name'], "張數": f"{d['my_shares']:.0f}", "現價": f"{d['price']:.2f}", 
            "配息": f"${d['div']:.2f}", "頻率": d['freq_name'], "預計法說會": evt_str, "狀態": status
        })
    st.table(pd.DataFrame(display_list))

    # LINE 彙整通知 (防 429 邏輯)
    if broken_list and line_token and line_uid:
        if "last_alert" not in st.session_state:
            report = f"【{APP_NAME}】偵測到破線警報：\n" + "\n".join(broken_list)
            send_line_push(line_token, line_uid, report)
            st.session_state["last_alert"] = report
