import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.genai as genai
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
from sklearn.linear_model import LinearRegression
import plotly.graph_objects as go

# ==========================================
# ⚙️ 系統設定 & 自動更新
# ==========================================
st.set_page_config(page_title="鐵穹戰略指揮中心", layout="wide", page_icon="🛡️")

# 設定每 5 分鐘 (300,000 毫秒) 自動刷新一次
st_autorefresh(interval=300000, key="datarefresh")

# 🎨 UI 美化 (深色戰情室風格)
st.markdown("""
<style>
    .stApp { background-color: #0f172a; color: #e2e8f0; }
    .stButton button { width: 100%; border-radius: 8px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ 鐵穹防禦系統 (終極戰略版)")
st.caption(f"⚡ 系統自動監控中 | 最後更新: {datetime.now().strftime('%H:%M:%S')} | 下次更新：5分鐘後")

# 📝 股票名稱對照 (包含您的主動型ETF與黃金)
STOCK_MAP = {
    "GC=F": "🔥 國際黃金 (期貨)",
    "00635U": "元大S&P黃金",
    "00985A": "野村台灣50",
    "00981A": "統一台股增長",
    "00982A": "群益台灣強棒",
    "0052": "富邦科技",
    "2330": "台積電",
    "00878": "國泰永續高股息",
    "0050": "元大台灣50",
    "2884": "玉山金",
    "3711": "日月光投控"
}

# --- 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 指揮官設定")
    api_key = st.text_input("Gemini API Key", type="password")
    
    st.subheader("📊 1. 我的庫存 (防禦區)")
    # 載入您的完整投資組合
    my_portfolio = "GC=F, 00635U, 00985A, 00981A, 00982A, 0052, 2330, 00878, 0050, 2884, 3711"
    stock_input = st.text_area("持股清單", my_portfolio, height=150)
    
    st.subheader("🚀 2. 飆股掃描池 (獵殺區)")
    # 預設一些熱門權值股作為掃描範例
    default_scanner = "2317, 2454, 2382, 3231, 2603, 3324, 1519, 3017, 2376, 2303"
    scanner_pool = st.text_area("輸入想掃描的潛力股", default_scanner, height=100)

# ==========================================
# 🔧 核心資料抓取與計算
# ==========================================
def get_technical_data(ticker):
    ticker = ticker.strip()
    
    if ticker == "GC=F":
        symbol = "GC=F"
    elif ticker == "00635U":
        symbol = "00635U.TW"
    elif ticker.isdigit():
        symbol = f"{ticker}.TW"
    else:
        symbol = ticker

    stock = yf.Ticker(symbol)
    try:
        # 抓 3 個月資料供回歸預測使用
        hist = stock.history(period="3mo")
        if hist.empty and symbol.endswith(".TW"):
            symbol = symbol.replace(".TW", ".TWO")
            stock = yf.Ticker(symbol)
            hist = stock.history(period="3mo")
            
        if hist.empty or len(hist) < 20: 
            return None # 資料不足
            
        price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2]
        change_pct = (price - prev_price) / prev_price * 100
        
        ma5 = hist['Close'].rolling(5).mean().iloc[-1]
        ma20 = hist['Close'].rolling(20).mean().iloc[-1]
        
        vol = hist['Volume'].iloc[-1]
        vol_ma5 = hist['Volume'].rolling(5).mean().iloc[-1]
        
        # RSI
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        curr_rsi = rsi.iloc[-1]

        # 狀態判斷
        if price < ma5 and curr_rsi < 45:
            status = "🔴 弱勢破線"
        elif price > ma5 and price > ma20:
            status = "🟢 強勢多頭"
        else:
            status = "🟡 盤整"

        return {
            "symbol": symbol,
            "代號": ticker,
            "名稱": STOCK_MAP.get(ticker, ticker),
            "現價": price,
            "漲跌幅": change_pct,
            "MA5": ma5,
            "MA20": ma20,
            "Vol": vol,
            "Vol_MA5": vol_ma5,
            "RSI": curr_rsi,
            "狀態": status,
            "hist_data": hist # 保留歷史資料供畫圖
        }
    except Exception as e:
        return None

# ==========================================
# 🛡️ 模組 1：持股防禦監控 (Iron Dome)
# ==========================================
st.subheader("📊 我的資產戰略儀表板")

portfolio_tickers = [t.strip() for t in stock_input.split(",")]
portfolio_data = []
alert_stocks = []

scan_bar = st.progress(0, text="正在掃描投資組合...")
for i, t in enumerate(portfolio_tickers):
    scan_bar.progress((i + 1) / len(portfolio_tickers))
    if data := get_technical_data(t):
        if "🔴" in data['狀態'] and "黃金" not in data['名稱']:
            alert_stocks.append(f"{data['名稱']} ({data['代號']})")
        
        portfolio_data.append({
            "代號": data['代號'],
            "名稱": data['名稱'],
            "現價": f"{data['現價']:.2f}",
            "漲跌幅%": f"{data['漲跌幅']:.2f}%",
            "MA5": f"{data['MA5']:.2f}",
            "MA20": f"{data['MA20']:.2f}",
            "RSI": f"{data['RSI']:.1f}",
            "狀態": data['狀態']
        })
scan_bar.empty()

# 空襲警報
if alert_stocks:
    st.error(f"⚠️ 空襲警報：以下持股跌破防線且動能弱勢，建議立即檢視！\n\n" + " | ".join(alert_stocks))

if portfolio_data:
    df_port = pd.DataFrame(portfolio_data)
    def highlight_row(row):
        if "🔴" in row['狀態']: return ['background-color: #450a0a; color: #fca5a5'] * len(row)
        elif "🟢" in row['狀態']: return ['background-color: #064e3b; color: #6ee7b7'] * len(row)
        elif "黃金" in row['名稱']: return ['background-color: #422006; color: #fcd34d; font-weight: bold'] * len(row)
        return [''] * len(row)
    
    st.dataframe(df_port.style.apply(highlight_row, axis=1), use_container_width=True, hide_index=True)

st.divider()

# ==========================================
# 🚀 模組 2：AI 飆股獵殺 (Funnel Scanner)
# ==========================================
st.subheader("🚀 潛力飆股雷達 (AI 深度分析)")

if st.button("啟動 AI 獵殺掃描", type="primary"):
    if not api_key:
        st.warning("⚠️ 請先輸入 Gemini API Key")
    else:
        scanner_tickers = [t.strip() for t in scanner_pool.split(",") if t.strip()]
        candidates = []
        
        filter_bar = st.progress(0, text="Step 1: 正在進行數學技術面過濾...")
        for i, t in enumerate(scanner_tickers):
            filter_bar.progress((i + 1) / len(scanner_tickers))
            if d := get_technical_data(t):
                # 獵殺條件：價格大於月線，成交量大於5日均量，RSI大於50
                if d['現價'] > d['MA20'] and d['Vol'] > d['Vol_MA5'] * 1.2 and d['RSI'] > 50:
                    candidates.append(d)
        
        filter_bar.empty()
        
        if candidates:
            st.success(f"✅ 發現 {len(candidates)} 檔具備量價齊揚潛力的標的！AI 正在解讀...")
            cols = st.columns(min(len(candidates), 3))
            client = genai.Client(api_key=api_key)
            
            for i, stock in enumerate(candidates):
                with cols[i % 3]:
                    st.info(f"**{stock['名稱']} ({stock['代號']})**\n\n現價: {stock['現價']:.2f} | RSI: {stock['RSI']:.1f}")
                    with st.spinner("AI 運算中..."):
                        try:
                            prompt = f"分析台股 {stock['名稱']}。剛站上月線且爆出近期大量，RSI為 {stock['RSI']:.1f}。判斷是有效突破還是假突破？並給出未來3天操作規劃。100字內。"
                            response = client.models.generate_content(model='gemini-2.0-flash-exp', contents=prompt)
                            st.write(response.text)
                        except Exception as e:
                            try:
                                response = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
                                st.write(response.text)
                            except:
                                st.error("AI 連線失敗")
        else:
            st.warning("目前掃描池內沒有符合突破條件的標的。")

st.divider()

# ==========================================
# 📈 模組 3：機器學習回歸預測 (Regression)
# ==========================================
st.subheader("📈 機器學習趨勢預測 (5日推演)")

# 從現有的投資組合中提取有抓到歷史資料的標的
valid_stocks = {t.strip(): get_technical_data(t.strip()) for t in stock_input.split(",")}
valid_options = {k: v for k, v in valid_stocks.items() if v is not None}

if valid_options:
    pred_options = [f"{k} {v['名稱']}" for k, v in valid_options.items()]
    selected_pred = st.selectbox("選擇預測標的：", pred_options)
    
    if st.button("執行回歸模型"):
        code = selected_pred.split(" ")[0]
        data = valid_options[code]
        hist_df = data['hist_data'].tail(60) # 取最近 60 天
        
        # 準備回歸資料
        y = hist_df['Close'].values
        X = np.arange(len(y)).reshape(-1, 1)
        
        # 訓練模型
        model = LinearRegression()
        model.fit(X, y)
        
        # 預測未來 5 天
        future_X = np.arange(len(y), len(y) + 5).reshape(-1, 1)
        future_y = model.predict(future_X)
        
        # 繪圖
        fig = go.Figure()
        
        # 歷史真實股價
        fig.add_trace(go.Scatter(
            x=list(range(len(y))), y=y, 
            mode='lines', name='實際收盤價', line=dict(color='#3b82f6', width=2)
        ))
        
        # 回歸趨勢線
        trendline = model.predict(X)
        fig.add_trace(go.Scatter(
            x=list(range(len(y))), y=trendline, 
            mode='lines', name='AI 趨勢線', line=dict(color='#ef4444', width=2, dash='dash')
        ))
        
        # 未來預測點
        fig.add_trace(go.Scatter(
            x=list(range(len(y), len(y) + 5)), y=future_y, 
            mode='markers+lines', name='未來 5 日預測', marker=dict(color='#10b981', size=8)
        ))
        
        fig.update_layout(
            title=f"{data['名稱']} ({code}) - 60日線性回歸預測",
            xaxis_title="時間 (天)", yaxis_title="股價",
            template="plotly_dark", height=400,
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.info(f"💡 **AI 模型預測結論**：根據過去 60 天的線性回歸趨勢，預估 5 天後的目標價約落在 **{future_y[-1]:.2f}** 左右。")
