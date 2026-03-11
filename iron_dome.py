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
VERSION = "v7.9.0"
APP_NAME = "股票戰情監控中心"

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon="📈")

# 🎨 UI 戰情室美化
st.markdown(f"""
<style>
    .stApp {{ background-color: #0d1117; color: #c9d1d9; }}
    .metric-card {{ background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 10px; }}
    .dividend-box {{ background-color: #1e2327; padding: 20px; border-radius: 10px; border-left: 5px solid #238636; margin: 10px 0; }}
    h3 {{ color: #58a6ff; }}
    .stButton button {{ width: 100%; background-color: #238636; color: white; height: 50px; font-weight: bold; border-radius: 8px; border: none; }}
    /* 💥 指揮官要求：版本號顯示於左下角 */
    .version-footer {{ position: fixed; bottom: 10px; left: 10px; font-size: 11px; color: #8b949e; z-index: 999; background: rgba(13,17,23,0.8); padding: 2px 5px; border-radius: 3px; }}
</style>
""", unsafe_allow_html=True)

# 📖 14 檔精銳部隊 (確保名稱與代號精確匹配)
STOCK_NAMES = {
    "^TWII": "台股大盤", 
    "TSM": "台積電 ADR (夜盤)", 
    "2330": "台積電", 
    "0052": "富邦科技", 
    "006208": "富邦台50", 
    "4958": "臻鼎-KY", 
    "4420": "光明", 
    "00919": "群益精選高息", 
    "0056": "元大高股息", 
    "6683": "雍智科技", 
    "1717": "長興", 
    "00929": "復華台灣科技優息", 
    "00981A": "復華美債1-5Y", 
    "GC=F": "🔥 國際黃金"
}

# ==========================================
# 📡 戰情核心函數
# ==========================================
def get_tech_data(ticker):
    t = ticker.strip().upper()
    if not t: return None
    # 🕵️ 指標特殊處理 (防止 ^TWII 等符號被加上後綴)
    symbol_list = [t] if (t.startswith("^") or t in ["TSM", "GC=F"]) else [f"{t}.TW", f"{t}.TWO", t]
    
    hist, stock_obj = None, None
    for symbol in symbol_list:
        try:
            stock_obj = yf.Ticker(symbol)
            temp_hist = stock_obj.history(period="6mo")
            if not temp_hist.empty:
                hist = temp_hist; break
        except: continue
    if hist is None or hist.empty: return {"code": t, "name": STOCK_NAMES.get(t, t), "is_error": True}

    # 💎 法說會 & 配息
    event_date_obj, last_div, freq_name, mult = None, 0, "年配", 1
    try:
        cal = stock_obj.calendar
        if cal is not None and 'Earnings Date' in cal:
            dates = cal['Earnings Date']
            if isinstance(dates, (list, pd.DatetimeIndex)) and len(dates) > 0: event_date_obj = dates[0]
        div_data = stock_obj.dividends
        if not div_data.empty:
            last_div = div_data.iloc[-1]
            now_tz = pd.Timestamp.now(tz='UTC')
            if div_data.index.tz is None: div_data.index = div_data.index.tz_localize('UTC')
            count = len(div_data[div_data.index > (now_tz - pd.Timedelta(days=365))])
            if count >= 10: freq_name, mult = "月配", 12
            elif 3 <= count <= 5: freq_name, mult = "季配", 4
            elif count == 2: freq_name, mult = "半年配", 2
    except: pass

    close = hist['Close']
    ma20 = close.rolling(20).mean().iloc[-1]
    return {
        "name": STOCK_NAMES.get(t, t), "code": t, "price": close.iloc[-1], 
        "chg": (close.iloc[-1]/close.iloc[-2]-1)*100, "ma20": ma20, 
        "div": last_div, "freq_name": freq_name, "multiplier": mult,
        "event_date": event_date_obj, "hist": hist, "is_error": False
    }

# ==========================================
# 🏰 戰情室主視覺
# ==========================================
st.title(f"🏛️ {APP_NAME}")
st.markdown(f'<div class="version-footer">系統版本: {VERSION}</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("📈 戰情設定中心")
    if st.button("🔄 刷新全場雷達"): st.rerun()
    st.divider()
    line_token = st.secrets.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_uid = st.secrets.get("LINE_USER_ID", "")
    PERMANENT_LIST = "^TWII, TSM, 2330, 0052, 006208, 4958, 4420, 00919, 0056, 6683, 1717, 00929, 00981A, GC=F"
    my_stocks = st.text_area("📋 核心監控名單", PERMANENT_LIST, height=180)
    shares_input = st.text_area("依序輸入張數 (指數設為 0)", "0,0,1.152,0,0,0,0,0,0,0,0,0,0,0")

# --- 數據同步 ---
today, current_list = datetime.date.today(), [x.strip() for x in my_stocks.split(",") if x.strip()]
shares_list = [float(s.strip()) for s in shares_input.split(",")]
p_data, total_annual_dividend, broken_list, earnings_warning_list = [], 0, [], []

with st.spinner('📡 正在校準名稱代號與先行指標...'):
    for idx, t in enumerate(current_list):
        data = get_tech_data(t)
        if data and not data.get("is_error"):
            shares = shares_list[idx] if idx < len(shares_list) else 0
            total_annual_dividend += (data['div'] * data['multiplier'] * 1000 * shares)
            data['my_shares'] = shares
            p_data.append(data)
            if data['price'] < data['ma20']: broken_list.append(f"• {data['name']}")
            if data.get('event_date'):
                evt_date = data['event_date'].date() if hasattr(data['event_date'], 'date') else data['event_date']
                if today <= evt_date <= today + datetime.timedelta(days=3):
                    earnings_warning_list.append(f"• {data['name']} ({evt_date.strftime('%m/%d')})")

# --- UI 渲染 ---
st.markdown(f'<div class="dividend-box"><h3 style="margin:0; color:#238636;">💰 年度預計配息總額：NT$ {total_annual_dividend:,.0f}</h3></div>', unsafe_allow_html=True)

st.subheader("🛡️ 持股防禦與先行指標 (夜盤)")
if p_data:
    df_rows = []
    for d in p_data:
        evt_str, status = "待公布", "✅ 安全"
        if d.get('event_date'):
            try:
                evt_date = d['event_date'].date() if hasattr(d['event_date'], 'date') else d['event_date']
                evt_str = evt_date.strftime('%Y-%m-%d')
                if today <= evt_date <= today + datetime.timedelta(days=3): status = "🔥 震盪預警"
            except: pass
        if d['price'] < d['ma20']: status = f"⚠️ 破線 ({status})" if "預警" in status else "⚠️ 破線"
        df_rows.append({
            "名稱 (代號)": f"{d['name']} ({d['code']})", "張數": f"{d['my_shares']:.3f}",
            "現價": f"{d['price']:.2f}", "漲跌幅": f"{d['chg']:+.2f}%", "月線支撐": f"{d['ma20']:.2f}", 
            "預計法說會": evt_str, "狀態": status
        })
    st.table(pd.DataFrame(df_rows))

# --- 💥 指揮官要求：Latest News & Comment ---
st.divider()
st.subheader("📰 市場戰情即時分析 (2026/03/11)")
col_news, col_comment = st.columns([2, 1])

with col_news:
    st.info("""
    **🔥 今日關鍵新聞：**
    - **台股絕地反攻**：大盤今日狂飆 1,342 點，創下史上收盤第二大漲點紀錄，收復 34,000 點大關。
    - **護國神山噴發**：台積電 (2330) 收盤大漲 90 元，以 1,940 元作收，成功收復十日線，V 型反轉確立。
    - **特化供應鏈起義**：受台積電帶動，長興 (1717) 等半導體特化族群盤中一度大漲逾 8%。
    - **高息股最新公告**：00919 公告配息 0.78 元創新高，3/17 為除息基準日。
    """)

with col_comment:
    st.warning("""
    **🛡️ GiGi 戰略評論：**
    1. **先行指標回穩**：夜盤大漲後，TSM (ADR) 溢價持續擴大，顯示國際資金在非理性殺盤後正回補「核心資產」。
    2. **配息與股價博弈**：00919 配息雖高，但股價今日才剛嘗試收復失土，需警惕「除息後貼息」風險。
    3. **1,940 的意義**：台積電目前處於強勢回歸軌道，若能在 1,900 元之上築底，退休計畫將提速前進。
    """)
