import streamlit as st
import pandas as pd
import time
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import random
from supabase import create_client, Client

# --- ページ設定 ---
st.set_page_config(page_title="園芸施設 統合管理 (Supabase版)", layout="wide")

# --- 【重要】機密情報の設定 ---
# ※本来はStreamlit CloudのSecretsを使うのが安全ですが、ご要望通り直接記述します
SUPABASE_URL = "https://rmaycprutdkwrfpmuqrk.supabase.co/rest/v1/"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJtYXljcHJ1dGRrd3JmcG11cXJrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcwMTcwNzQsImV4cCI6MjA5MjU5MzA3NH0.1gx8b-sIvZpb5Ms2oy5cIqC9LXUQb5bkdlg6CoGgUD8"

# URLやKEYに空白が混じっているとエラーになるので .strip() を推奨
if SUPABASE_URL == "あなたのURL" or SUPABASE_KEY == "あなたのKEY":
    st.error("SupabaseのURLまたはKEYが設定されていません。")
    st.stop()

# Supabaseクライアントの初期化（optionsを明示的に渡す）
from supabase.lib.client_options import ClientOptions

try:
    supabase: Client = create_client(
        SUPABASE_URL.strip(), 
        SUPABASE_KEY.strip(),
        options=ClientOptions(postgrest_client_timeout=10)
    )
except Exception as e:
    st.error("Supabaseクライアントの起動に失敗しました。")
    st.code(str(e))
    st.stop()

# --- データベース操作関数 ---
def save_to_supabase(t, h):
    """エラーの詳細を画面に表示するデバッグ版"""
    data = {"temperature": t, "humidity": h}
    try:
        # execute() の戻り値を確認
        result = supabase.table("environment").insert(data).execute()
        return result
    except Exception as e:
        # 画面に赤いボックスでエラー内容をすべて表示します
        st.error(f"⚠️ Supabase接続エラーが発生しました:")
        st.code(str(e)) # ここに本当の理由が表示されます
        st.stop() # エラーが出たら一旦止める

def fetch_data_from_supabase(limit=30):
    """最新のデータを取得してPandas DataFrameで返す"""
    response = supabase.table("environment") \
        .select("*") \
        .order("timestamp", desc=True) \
        .limit(limit) \
        .execute()
    
    df = pd.DataFrame(response.data)
    if not df.empty:
        # 時刻を見やすく整形
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%H:%M:%S')
        # グラフ表示用に古い順に並べ替え
        df = df.sort_values('timestamp')
    return df

def delete_old_data(days):
    """古いデータを削除"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    supabase.table("environment").delete().lt("timestamp", cutoff).execute()

# --- サイドバー設定 ---
st.sidebar.header("⚙️ システム管理")
retention_days = st.sidebar.number_input("データ保持期間 (日間)", 1, 365, 30)
if st.sidebar.button("古いデータを削除"):
    delete_old_data(retention_days)
    st.sidebar.success("削除完了")

# --- メイン画面 ---
st.title("🌿 園芸施設 環境モニタリング (Supabase)")
alert_placeholder = st.empty()
col1, col2 = st.columns(2)
placeholder_temp = col1.empty()
placeholder_hum = col2.empty()
chart_placeholder = st.empty()

# アラート設定
st.sidebar.header("📢 アラート設定")
temp_min, temp_max = st.sidebar.slider("温度範囲", 0.0, 50.0, (15.0, 30.0))
hum_min, hum_max = st.sidebar.slider("湿度範囲", 0.0, 100.0, (40.0, 80.0))

# --- 実行ループ ---
while True:
    # 1. 擬似データ生成とSupabase保存
    t = round(random.uniform(10.0, 35.0), 1)
    h = round(random.uniform(30.0, 90.0), 1)
    save_to_supabase(t, h)
    
    # 2. Supabaseから最新データを取得
    df_display = fetch_data_from_supabase(30)

    # 3. UI更新
    if not df_display.empty:
        latest_t = df_display.iloc[-1]['temperature']
        latest_h = df_display.iloc[-1]['humidity']
        
        placeholder_temp.metric("🌡️ 温度", f"{latest_t} °C")
        placeholder_hum.metric("💧 湿度", f"{latest_h} %")

        # アラート判定
        is_alert = (latest_t < temp_min or latest_t > temp_max or latest_h < hum_min or latest_h > hum_max)
        if is_alert:
            alert_placeholder.error("⚠️ 異常検知")
        else:
            alert_placeholder.success("✅ 正常")

        # グラフ
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_display['timestamp'], y=df_display['temperature'], name="温度", line=dict(color='#FF4B4B')))
        fig.add_trace(go.Scatter(x=df_display['timestamp'], y=df_display['humidity'], name="湿度", line=dict(color='#1C83E1')))
        chart_placeholder.plotly_chart(fig, use_container_width=True)
    
    time.sleep(2) # Supabaseへの負荷を考え少し間隔を空けます
