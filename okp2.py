import streamlit as st
import pandas as pd
import sqlite3
import time
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import random

# --- ページ設定とカスタムCSS ---
st.set_page_config(page_title="園芸施設 統合管理システム", layout="wide")

st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 48px !important; }
    [data-testid="stMetricLabel"] { font-size: 24px !important; }
    .alert-box { padding: 20px; border-radius: 10px; color: white; font-weight: bold; font-size: 24px; text-align: center; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- データベース設定 & クリーンアップ機能 ---
DB_FILE = "sensor_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS environment 
                 (timestamp DATETIME, temperature REAL, humidity REAL)''')
    conn.commit()
    conn.close()

def save_to_db(t, h):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT INTO environment VALUES (?, ?, ?)", (now, t, h))
    conn.commit()
    conn.close()

def delete_old_data(days_to_keep):
    """指定された日数より古いデータを削除する"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 削除の基準となる日時を計算
    cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute("DELETE FROM environment WHERE timestamp < ?", (cutoff_date,))
    # データベースファイルのサイズを再最適化
    c.execute("VACUUM")
    conn.commit()
    conn.close()

# 起動時にDB初期化
init_db()

# --- サイドバー：管理設定 ---
st.sidebar.header("⚙️ システム管理")

# 自動削除の設定
retention_days = st.sidebar.number_input("データ保持期間 (日間)", min_value=1, max_value=365, value=30)
if st.sidebar.button("古いデータを今すぐ削除"):
    delete_old_data(retention_days)
    st.sidebar.success(f"{retention_days}日より前のデータを削除しました。")

# --- サイドバー：CSV保存 ---
st.sidebar.header("📁 データエクスポート")
export_date = st.sidebar.date_input("抽出する日付を選択", date.today())

if st.sidebar.button("CSVデータを生成"):
    conn = sqlite3.connect(DB_FILE)
    query = f"SELECT * FROM environment WHERE timestamp LIKE '{export_date}%'"
    export_df = pd.read_sql_query(query, conn)
    conn.close()

    if not export_df.empty:
        csv = export_df.to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button(
            label=f"📥 {export_date} のCSVをダウンロード",
            data=csv, file_name=f"env_data_{export_date}.csv", mime='text/csv'
        )
    else:
        st.sidebar.warning("選択した日付のデータはありません。")

# --- サイドバー：アラート設定 ---
st.sidebar.header("📢 アラート設定")
temp_min, temp_max = st.sidebar.slider("温度範囲 (°C)", 0.0, 50.0, (15.0, 30.0))
hum_min, hum_max = st.sidebar.slider("湿度範囲 (%)", 0.0, 100.0, (40.0, 80.0))
alert_logic = st.sidebar.selectbox("アラート条件", ["OR", "AND", "温度のみ", "湿度のみ"])

# --- メイン画面 ---
st.title("🌿 園芸施設 環境モニタリング")
alert_placeholder = st.empty()
col1, col2 = st.columns(2)
placeholder_temp = col1.empty()
placeholder_hum = col2.empty()
chart_placeholder = st.empty()

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=['Time', 'Temperature', 'Humidity'])

# --- 実行ループ ---
count = 0
while True:
    # 1. データ取得と保存
    t = round(random.uniform(10.0, 35.0), 1)
    h = round(random.uniform(30.0, 90.0), 1)
    save_to_db(t, h)
    
    # 定期的（ここでは100回に1回）に自動クリーンアップを実行
    count += 1
    if count >= 100:
        delete_old_data(retention_days)
        count = 0

    # 2. 表示用データ更新
    now_full = datetime.now().strftime('%H:%M:%S')
    new_data = pd.DataFrame({'Time': [now_full], 'Temperature': [t], 'Humidity': [h]})
    st.session_state.df = pd.concat([st.session_state.df, new_data], ignore_index=True).tail(30)

    # 3. アラート判定
    t_alert = (t < temp_min or t > temp_max)
    h_alert = (h < hum_min or h > hum_max)
    is_alert = (alert_logic == "OR" and (t_alert or h_alert)) or \
               (alert_logic == "AND" and (t_alert and h_alert)) or \
               (alert_logic == "温度のみ" and t_alert) or \
               (alert_logic == "湿度のみ" and h_alert)

    if is_alert:
        alert_placeholder.markdown('<div class="alert-box" style="background-color: #FF4B4B;">⚠️ 異常検知</div>', unsafe_allow_html=True)
    else:
        alert_placeholder.markdown('<div class="alert-box" style="background-color: #28a745;">✅ 正常</div>', unsafe_allow_html=True)

    # 4. UI更新
    placeholder_temp.metric("🌡️ 温度", f"{t} °C")
    placeholder_hum.metric("💧 湿度", f"{h} %")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=st.session_state.df['Time'], y=st.session_state.df['Temperature'], name="温度", line=dict(color='#FF4B4B', width=4)))
    fig.add_trace(go.Scatter(x=st.session_state.df['Time'], y=st.session_state.df['Humidity'], name="湿度", line=dict(color='#1C83E1', width=4)))
    fig.update_layout(hovermode="x unified", font=dict(size=18), height=500, margin=dict(l=50, r=50, t=30, b=50))
    chart_placeholder.plotly_chart(fig, use_container_width=True)
    
    time.sleep(1)