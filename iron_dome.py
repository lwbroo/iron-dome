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
VERSION = "v7.8.0"
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
    /* 左下角版本號樣式 */
    .version-footer { position: fixed; bottom: 10px; left: 10px; font-size: 12px; color: #8b949e; z-index: 999; }
</style>
""", unsafe_allow_html=True)

# 📖 14 檔精銳部隊 (含先行指標)
STOCK_NAMES = {
    "^TWII": "台股大盤", "TSM": "台積電 ADR", "2330": "台積電", "0052": "富邦科技", 
    "006208": "富邦台50", "4958": "臻鼎-KY", "4420": "光明", "00919": "群益精選高息", 
    "0056": "元大高股息", "6683": "雍智科技", "1717": "長興", "00929": "復華科技優息", 
    "00981A": "復華美債1-5Y", "GC=F": "🔥 國際黃金"
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
    # 🕵️ 指標特殊處理 (防止 ^TWII 等符號被加上後綴)
    if t.startswith("^") or t in ["TSM", "GC=F"]:
        symbol_list = [t]
    else:
        symbol_list = [f"{t}.TW", f"{t}.TWO", t]
    
    hist = None
    stock_obj = None
    for symbol in symbol_list:
        try:
            stock_obj = yf.Ticker(symbol)
            temp_hist = stock_obj.history(period="6mo")
            if not temp_hist.empty:
                hist = temp_hist
                break
        except: continue
    if hist is None or hist.empty:
        return {"code": t, "name": STOCK_NAMES.get(t, t), "is_error": True}

    # 💎 法說會日期
    event_date_obj = None
    try:
        cal = stock_obj.calendar
        if cal is not None and 'Earnings Date' in cal:
            dates = cal['Earnings Date']
            if isinstance(dates, (list, pd.DatetimeIndex)) and len(dates) > 0:
                event_date_obj = dates[0]
    except: pass

    # 💰 配息偵測
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
# 🏰 戰情室主視覺
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
            status = send_line_push(line_token, line_uid, f"🚀 {APP_NAME} v{VERSION} 通訊測試！")
            if status == 200: st.success("發送成功！")
            else: st.error(f"錯誤: {status}")

    st.divider()
    # 永久名單 (先行指標置頂)
    PERMANENT_LIST = "^TWII, TSM, 2330, 0052, 006208, 4958, 4420, 00919, 0056, 6683, 1717, 00929, 00981A, GC=F"
    my_stocks = st.text_area("📋 核心監控名單", PERMANENT_LIST, height=180)
    
    st.subheader("💰 持股張數設定")
    shares_input = st.text_area("依序輸入張數 (指數位設為 0)", "0,0,1.152,0,0,0,0,0,0,0,0,0,0,0")
    
    # 左下角版本號 (側邊欄底部)
    st.markdown(f'<div class="version-footer">系統版本: {VERSION}</div>', unsafe_allow_html=True)

# --- 數據處理 ---
today = datetime.date.today()
warning_window = today + datetime.timedelta(days=3)
current_list = [x.strip() for x in my_stocks.split(",") if x.strip()]
shares_list = [float(s.strip()) for s in shares_input.split(",")]

p_data = []
total_annual_dividend = 0
broken_list = []
earnings_warning_list = []

with st.spinner('📡 正在同步夜盤數據與防禦戰線...'):
    for idx, t in enumerate(current_list):
        data = get_tech_data(t)
        if data and not data.get("is_error"):
            shares = shares_list[idx] if idx < len(shares_list) else 0
            total_annual_dividend += (data['div'] * data['multiplier'] * 1000 * shares)
            data['my_shares'] = shares
            p_data.append(data)
            
            if data['price'] < data['ma20']: broken_list.append(f"• {data['name']}")
            if data['event_date']:
                try:
                    evt_date = data['event_date'].date() if hasattr(data['event_date'], 'date') else data['event_date']
                    if today <= evt_date <= warning_window:
                        earnings_warning_list.append(f"• {data['name']} ({evt_date.strftime('%m/%d')})")
                except: pass

# --- UI 渲染 ---
st.markdown(f"""
<div class="dividend-box">
    <h3 style="margin:0; color:#238636;">💰 年度預計配息總額：NT$ {total_annual_dividend:,.0f}</h3>
    <p style="margin:0; color:#8b949e;">已整合大盤、TSM ADR 與核心持股現金流</p>
</div>
""", unsafe_allow_html=True)

st.subheader("🛡️ 持股防禦與先行指標 (夜盤)")
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
            "名稱 (代號)": f"{d['name']} ({d['code']})", 
            "張數": f"{d['my_shares']:.3f}",
            "現價": f"{d['price']:.2f}", 
            "漲跌幅": f"{d['chg']:+.2f}%",
            "月線支撐": f"{d['ma20']:.2f}", 
            "預計法說會": evt_str, 
            "狀態": status
        })
    st.table(pd.DataFrame(df_rows))

    # 🔮 趨勢路徑預測
    st.divider()
    st.subheader("🔮 先行指標預測 (大盤與 TSM)")
    valid_codes = [d['code'] for d in p_data]
    col_sel, col_algo, col_days = st.columns([1, 1, 1])
    target = col_sel.selectbox("選擇分析標的", valid_codes, index=1)
    algo_type = col_algo.radio("預測模式", ["線性趨勢", "多項式轉折"])
    lookback = col_days.slider("參考天數", 10, 60, 20)
    
    if st.button("執行演算法預報"):
        d_plot = next(item for item in p_data if item["code"] == target)
        y = d_plot['hist']['Close'].tail(lookback).values
        X = np.arange(len(y)).reshape(-1, 1)
        future_X = np.arange(len(y), len(y) + 3).reshape(-1, 1)
        
        if algo_type == "線性趨勢":
            model = LinearRegression().fit(X, y)
            future_y = model.predict(future_X)
        else:
            pf = PolynomialFeatures(degree=3)
            model = LinearRegression().fit(pf.fit_transform(X), y)
            future_y = model.predict(pf.transform(future_X))
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=y, name="實際價格", line=dict(color='#3b82f6', width=3)))
        fig.add_trace(go.Scatter(x=[len(y)-1, len(y), len(y)+1], y=[y[-1]]+list(future_y), name="預測趨勢", line=dict(color='#ff00ff', dash='dash')))
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # LINE 通訊
    if (broken_list or earnings_warning_list) and line_token and line_uid:
        if "last_alert" not in st.session_state:
            msg = f"【{APP_NAME} v{VERSION}】戰報：\n"
            if earnings_warning_list: msg += f"\n📅 法說預警：\n" + "\n".join(earnings_warning_list)
            if broken_list: msg += f"\n🚨 破線警報：\n" + "\n".join(broken_list)
            if send_line_push(line_token, line_uid, msg) == 200:
                st.session_state["last_alert"] = msg
