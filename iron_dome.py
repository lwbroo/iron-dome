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
# ⚙️ 系統設定 & 版本控制
# ==========================================
VERSION = "v7.5.0"
APP_NAME = "股票戰情監控中心"

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon="📈")

# 🎨 UI 戰情室美化
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .metric-card { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 10px; }
    .dividend-box { background-color: #1e2327; padding: 20px; border-radius: 10px; border-left: 5px solid #238636; margin: 10px 0; }
    h3 { color: #58a6ff; }
    .stButton button { width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border-radius: 8px; border: none; }
</style>
""", unsafe_allow_html=True)

# 📖 12 檔核心親衛隊 (永久記憶清單)
STOCK_NAMES = {
    "2330": "台積電", "0052": "富邦科技", "006208": "富邦台50", "4958": "臻鼎-KY",
    "4420": "光明", "00919": "群益精選高息", "0056": "元大高股息", "6683": "雍智科技",
    "1717": "長興", "00929": "復華台灣科技優息", "00981A": "復華美債1-5Y", 
    "009816": "特定債券標的", "NVDA": "輝達", "GC=F": "🔥 國際黃金"
}

# ==========================================
# 📡 戰情核心函數
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
    # 🕵️ 多重路徑偵測：確保上櫃股 (4420, 6683) 能被正確抓取
    suffixes = [".TW", ".TWO", ""]
    hist = None
    stock_obj = None
    for s in suffixes:
        symbol = f"{t}{s}" if (t.isdigit() or "A" in t) else t
        if t == "GC=F": symbol = "GC=F"
        try:
            stock_obj = yf.Ticker(symbol)
            temp_hist = stock_obj.history(period="6mo")
            if not temp_hist.empty:
                hist = temp_hist
                break
        except: continue
            
    if hist is None or hist.empty:
        return {"code": t, "name": STOCK_NAMES.get(t, t), "is_error": True}

    # 💎 法說會日期 (Safety Check 7.3.1)
    event_date_obj = None
    try:
        cal = stock_obj.calendar
        if cal is not None and 'Earnings Date' in cal:
            dates = cal['Earnings Date']
            if isinstance(dates, (list, pd.DatetimeIndex)) and len(dates) > 0:
                event_date_obj = dates[0]
    except: pass

    # 💰 配息與頻率偵測 (Timezone Aware)
    div_data = stock_obj.dividends
    last_div = div_data.iloc[-1] if not div_data.empty else 0
    freq_multiplier = 1
    freq_name = "年配"
    if not div_data.empty:
        now_tz = pd.Timestamp.now(tz='UTC')
        if div_data.index.tz is None: div_data.index = div_data.index.tz_localize('UTC')
        count = len(div_data[div_data.index > (now_tz - pd.Timedelta(days=365))])
        if count >= 10: freq_name, freq_multiplier = "月配", 12
        elif 3 <= count <= 5: freq_name, freq_multiplier = "季配", 4
        elif count == 2: freq_name, freq_multiplier = "半年配", 2

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
    
    # 讀取 Secrets
    line_token = st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_uid = st.secrets.get("LINE_USER_ID", "")
    
    if st.button("🔔 測試 LINE 通訊"):
        if line_token and line_uid:
            status = send_line_push(line_token, line_uid, f"🚀 {APP_NAME} v{VERSION} 測試成功！")
            if status == 200: st.success("發送成功！")
            else: st.error(f"錯誤: {status}")

    st.divider()
    # 💥 指揮官的 12 檔永久記憶
    PERMANENT_LIST = "2330, 0052, 006208, 4958, 4420, 00919, 009816, 0056, 6683, 1717, 00929, 00981A"
    my_stocks = st.text_area("📋 核心監控名單", PERMANENT_LIST, height=150)
    
    # 💰 持股張數設定
    st.subheader("💰 持股張數設定")
    shares_input = st.text_area("依序輸入張數 (用逗號隔開)", "1,0,0,0,0,0,0,0,0,0,0,0")
    
    st.divider()
    st.caption(f"系統版本: {VERSION}")

# --- 數據同步與警報 ---
today = datetime.date.today()
warning_window = today + datetime.timedelta(days=3)
current_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
shares_list = [float(s.strip()) for s in shares_input.split(",")]

p_data = []
total_annual_dividend = 0
broken_list = []
earnings_warning_list = []

with st.spinner('📡 數據同步中...'):
    for idx, t in enumerate(current_list):
        data = get_tech_data(t)
        if data and not data.get("is_error"):
            shares = shares_list[idx] if idx < len(shares_list) else 0
            # 計算該標的年預計配息: 金額 * 頻率次數 * 1000股 * 張數
            total_annual_dividend += (data['div'] * data['multiplier'] * 1000 * shares)
            data['my_shares'] = shares
            p_data.append(data)
            
            # 破線偵測
            if data['price'] < data['ma20']: broken_list.append(f"• {data['name']}")
            # 法說預警 (3日內)
            if data['event_date']:
                try:
                    evt_date = data['event_date'].date() if hasattr(data['event_date'], 'date') else data['event_date']
                    if today <= evt_date <= warning_window:
                        earnings_warning_list.append(f"• {data['name']} ({evt_date.strftime('%m/%d')})")
                except: pass

# --- 1. 現金流看板 ---
st.markdown(f"""
<div class="dividend-box">
    <h3 style="margin:0; color:#238636;">💰 年度預計配息總額：NT$ {total_annual_dividend:,.0f}</h3>
    <p style="margin:0; color:#8b949e;">系統已自動對齊 12 檔核心部隊之發放頻率並計算年化收益</p>
</div>
""", unsafe_allow_html=True)

# --- 2. 持股防禦清單 ---
st.subheader("🛡️ 持股防禦與大震盪預警")
if p_data:
    df_rows = []
    for d in p_data:
        evt_str = "待公布"
        status = "✅ 安全"
        if d['event_date']:
            try:
                evt_date = d['event_date'].date() if hasattr(d['event_date'], 'date') else d['event_date']
                evt_str = evt_date.strftime('%Y-%m-%d')
                if today <= evt_date <= warning_window: status = "🔥 震盪預警"
            except: pass
        if d['price'] < d['ma20']:
            status = f"⚠️ 破線 ({status})" if "預警" in status else "⚠️ 破線"
        
        df_rows.append({
            "名稱": d['name'], "張數": f"{d['my_shares']:.0f}", "現價": f"{d['price']:.2f}", 
            "配息": f"${d['div']:.2f}", "頻率": d['freq_name'], "預計法說會": evt_str, "狀態": status
        })
    st.table(pd.DataFrame(df_rows))

    # --- 3. 🔮 趨勢路徑預測 (回歸分析) ---
    st.divider()
    st.subheader("🔮 趨勢路徑預測 (線性 vs 多項式)")
    valid_codes = [d['code'] for d in p_data]
    col_sel, col_algo, col_days = st.columns([1, 1, 1])
    target = col_sel.selectbox("選擇分析標的", valid_codes)
    algo_type = col_algo.radio("預測模式", ["線性趨勢 (看大勢)", "多項式轉折 (找妖股)"])
    lookback = col_days.slider("參考天數", 10, 60, 20)
    
    if st.button("執行演算法預報"):
        d_plot = next(item for item in p_data if item["code"] == target)
        y = d_plot['hist']['Close'].tail(lookback).values
        X = np.arange(len(y)).reshape(-1, 1)
        future_X = np.arange(len(y), len(y) + 3).reshape(-1, 1)
        
        if algo_type == "線性趨勢 (看大勢)":
            model = LinearRegression().fit(X, y)
            future_y = model.predict(future_X)
            formula = f"模型邏輯：$y = ax + b$"
        else:
            pf = PolynomialFeatures(degree=3)
            model = LinearRegression().fit(pf.fit_transform(X), y)
            future_y = model.predict(pf.transform(future_X))
            formula = f"模型邏輯：$y = ax^3 + bx^2 + cx + d$"
        
        st.caption(formula)
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=y, name="實際價格", line=dict(color='#3b82f6', width=3)))
        fig.add_trace(go.Scatter(x=[len(y)-1, len(y), len(y)+1], y=[y[-1]]+list(future_y), name="預測趨勢", line=dict(color='#ff00ff', dash='dash')))
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # --- 4. LINE 彙整通知 (防洪機制) ---
    if (broken_list or earnings_warning_list) and line_token and line_uid:
        if "last_alert" not in st.session_state:
            msg = f"【{APP_NAME}】偵測到戰情警報：\n"
            if earnings_warning_list: msg += f"\n📅 法說預警：\n" + "\n".join(earnings_warning_list)
            if broken_list: msg += f"\n🚨 破線警報：\n" + "\n".join(broken_list)
            if send_line_push(line_token, line_uid, msg) == 200:
                st.session_state["last_alert"] = msg
