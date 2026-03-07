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
# ⚙️ 系統設定 & 版本號
# ==========================================
VERSION = "v7.3.1"
APP_NAME = "股票戰情監控中心"

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon="📈")

# 🎨 UI 美化
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 10px; }
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

    # 💎 法說會日期 (安全讀取)
    event_date_obj = None
    try:
        cal = stock_obj.calendar
        if cal is not None and 'Earnings Date' in cal:
            dates = cal['Earnings Date']
            if isinstance(dates, (list, pd.DatetimeIndex)) and len(dates) > 0:
                event_date_obj = dates[0]
    except: pass

    # 配息偵測
    div_data = stock_obj.dividends
    last_div = div_data.iloc[-1] if not div_data.empty else 0
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
        "div": last_div, "freq": freq, "event_date": event_date_obj, 
        "hist": hist, "is_error": False
    }

# ==========================================
# 🏰 戰情室主視覺
# ==========================================
st.title(f"🏛️ {APP_NAME}")

with st.sidebar:
    st.header("📈 戰情設定")
    if st.button("🔄 刷新全場雷達"): st.rerun()
    st.divider()
    
    line_token = st.text_input("LINE Token", value=st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN", ""), type="password")
    line_uid = st.text_input("Your User ID", value=st.secrets.get("LINE_USER_ID", ""))
    
    if st.button("🔔 測試 LINE 通訊"):
        if line_token and line_uid:
            status = send_line_push(line_token, line_uid, f"🚀 {APP_NAME}測試：通訊頻道暢通！")
            if status == 200: st.success("發送成功！")
            else: st.error(f"發送失敗，代碼: {status}")
        else: st.warning("請先設定 Token 與 ID")

    st.divider()
    # 永久記憶名單
    PERMANENT_LIST = "2330, 0052, 006208, 4958, 4420, 00919, 009816, 0056, 6683, 1717, 00929, 00981A"
    my_stocks = st.text_area("📋 核心部隊 (永久記憶)", PERMANENT_LIST, height=180)
    
    st.divider()
    st.caption(f"系統版本: {VERSION}")

# --- 數據同步與預警 ---
today = datetime.date.today()
warning_window = today + datetime.timedelta(days=3)
current_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
p_data = []
broken_list = []
earnings_warning_list = []

with st.spinner('📡 正在同步法說會日期與價格防禦線...'):
    for t in current_list:
        data = get_tech_data(t)
        if data and not data.get("is_error"):
            p_data.append(data)
            # 1. 破線檢查
            if data['price'] < data['ma20']:
                broken_list.append(f"• {data['name']} ({data['code']})")
            
            # 2. 法說會預警檢查 (新增安全判斷)
            if data.get('event_date') is not None:
                # 確保轉換為 date 物件進行比較
                try:
                    evt_date = data['event_date'].date() if hasattr(data['event_date'], 'date') else data['event_date']
                    if today <= evt_date <= warning_window:
                        earnings_warning_list.append(f"• {data['name']} ({data['code']}): {evt_date.strftime('%m/%d')} 震盪預警")
                except: pass

# --- 顯示表格 ---
st.subheader("🛡️ 持股防禦、配息與大震盪預警")
if p_data:
    display_list = []
    for d in p_data:
        evt_str = "待公布"
        status = "✅ 安全"
        
        if d.get('event_date') is not None:
            try:
                evt_date = d['event_date'].date() if hasattr(d['event_date'], 'date') else d['event_date']
                evt_str = evt_date.strftime('%Y-%m-%d')
                if today <= evt_date <= warning_window:
                    status = "🔥 震盪預警"
            except: pass

        if d['price'] < d['ma20']:
            status = f"⚠️ 破線 ({status})" if "預警" in status else "⚠️ 破線"

        display_list.append({
            "名稱": d['name'], "代號": d['code'], "現價": f"{d['price']:.2f}", 
            "配息": f"${d['div']:.2f}", "頻率": d['freq'], "預計法說會": evt_str, "狀態": status
        })
    st.table(pd.DataFrame(display_list))

    # LINE 整合通知
    if (broken_list or earnings_warning_list) and line_token and line_uid:
        if "last_alert" not in st.session_state:
            report_lines = [f"【{APP_NAME} 日報】"]
            if earnings_warning_list:
                report_lines.append("\n📅 法說大震盪預警：")
                report_lines.extend(earnings_warning_list)
            if broken_list:
                report_lines.append("\n🚨 跌破月線警報：")
                report_lines.extend(broken_list)
            
            report = "\n".join(report_lines)
            if send_line_push(line_token, line_uid, report) == 200:
                st.session_state["last_alert"] = report
