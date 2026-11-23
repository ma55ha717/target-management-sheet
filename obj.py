import base64
import calendar
import datetime
import json
import os
import requests
import streamlit as st

st.set_page_config(page_icon="icon.jpg")
st.set_page_config(page_title="目標管理シート", layout="centered")

st.title("🎯 目標管理シート")

# --- 自動保存用のファイル名 ---
DATA_FILE = "data_store.json"


def _get_github_config():
    token = st.secrets.get("GITHUB_TOKEN") if hasattr(st, "secrets") else None
    repo = st.secrets.get("GITHUB_REPO") if hasattr(st, "secrets") else None
    path = (
        st.secrets.get("GITHUB_FILE_PATH", DATA_FILE)
        if hasattr(st, "secrets")
        else DATA_FILE
    )
    if token and repo:
        return token, repo, path
    return None, None, DATA_FILE


def _load_raw_json_from_github():
    token, repo, path = _get_github_config()
    if not token or not repo:
        return None, None

    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    res = requests.get(url, headers=headers, timeout=15)
    if res.status_code == 200:
        body = res.json()
        content = base64.b64decode(body["content"]).decode("utf-8")
        return json.loads(content), body.get("sha")
    if res.status_code == 404:
        return {}, None
    raise RuntimeError(f"GitHub読み込みエラー ({res.status_code}): {res.text}")


def _save_raw_json_to_github(raw_dict, message="Update data_store.json"):
    token, repo, path = _get_github_config()
    if not token or not repo:
        return False

    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    get_res = requests.get(url, headers=headers, timeout=15)
    sha = get_res.json().get("sha") if get_res.status_code == 200 else None

    json_text = json.dumps(raw_dict, ensure_ascii=False, indent=4)
    encoded = base64.b64encode(json_text.encode("utf-8")).decode("utf-8")
    payload = {"message": message, "content": encoded}
    if sha:
        payload["sha"] = sha

    put_res = requests.put(url, headers=headers, json=payload, timeout=15)
    if put_res.status_code not in (200, 201):
        raise RuntimeError(f"GitHub保存エラー ({put_res.status_code}): {put_res.text}")
    return True


def _load_raw_json():
    token, repo, _ = _get_github_config()
    if token and repo:
        raw_data, _ = _load_raw_json_from_github()
        return raw_data if isinstance(raw_data, dict) else {}

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            return raw_data if isinstance(raw_data, dict) else {}
    return {}


# --- データの読み込み・保存関数 ---
def load_data():
    try:
        raw_data = _load_raw_json()
        loaded_store = {}
        for k, val in raw_data.items():
            if k == "meta":
                continue
            parts = k.split("-")
            if len(parts) == 3:
                loaded_store[(int(parts[0]), int(parts[1]), int(parts[2]))] = val
        return loaded_store
    except Exception as e:
        st.warning(f"データの読み込み中に問題が発生しました: {e}")
        return {}


def load_meta():
    try:
        raw_data = _load_raw_json()
        return raw_data.get("meta", {})
    except Exception:
        return {}


def save_data_to_file():
    try:
        export_data = {
            f"{y}-{m}-{d}": val
            for (y, m, d), val in st.session_state.data_store.items()
        }
        export_data["meta"] = {
            "target_title": st.session_state.get(
                "target_title", "基本情報技術者試験の取得"
            ),
            "target_deadline": str(
                st.session_state.get(
                    "target_deadline", datetime.date(2026, 12, 31)
                )
            ),
        }

        token, repo, _ = _get_github_config()
        if token and repo:
            _save_raw_json_to_github(export_data, message="Update target sheet data")
        else:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"自動保存に失敗しました: {e}")


# --- セッションステートの初期化 ---
if "selected_day" not in st.session_state:
    st.session_state.selected_day = datetime.date.today().day

if "data_store" not in st.session_state:
    st.session_state.data_store = load_data()

# メタデータの初期化（当面目標の内容など）
meta_data = load_meta()
if "target_title" not in st.session_state:
    st.session_state["target_title"] = meta_data.get(
        "target_title", "基本情報技術者試験の取得"
    )
if "target_deadline" not in st.session_state:
    saved_deadline = meta_data.get("target_deadline")
    if saved_deadline:
        try:
            st.session_state["target_deadline"] = datetime.date.fromisoformat(
                saved_deadline
            )
        except Exception:
            st.session_state["target_deadline"] = datetime.date(2026, 12, 31)
    else:
        st.session_state["target_deadline"] = datetime.date(2026, 12, 31)

if "goal_saved_msg" not in st.session_state:
    st.session_state.goal_saved_msg = ""
if "result_saved_msg" not in st.session_state:
    st.session_state.result_saved_msg = ""


# --- 選択日付のデータをフォーム用キーに反映させる関数 ---
def update_form_values(y, m, d):
    saved_data = st.session_state.data_store.get((y, m, d), {})
    g_data = saved_data.get("goal", {})
    r_data = saved_data.get("result", {})

    # 目標フォーム用
    st.session_state["goal_work"] = g_data.get(
        "work", "日勤 🌞(D) 8:30～17:15"
    )
    st.session_state["plan_target"] = g_data.get("plan_target", "")
    st.session_state["expected_time"] = g_data.get("target_time", 60)
    st.session_state["plan_other"] = g_data.get("plan_other", "")
    st.session_state["expected_time_other"] = g_data.get("other_time", 0)
    st.session_state["exercise_plan"] = g_data.get("exercise_plan", "")
    st.session_state["goal_ex_time"] = g_data.get("ex_time", 0)
    st.session_state["goal_ex_dist"] = g_data.get("ex_dist", 0.0)
    st.session_state["goal_alcohol"] = g_data.get("alcohol", "飲まない")

    # 結果フォーム用
    st.session_state["res_work"] = r_data.get(
        "work", "日勤 🌞(D) 8:30～17:15"
    )
    st.session_state["act_t_time"] = r_data.get("target_time", 0)
    st.session_state["act_o_time"] = r_data.get("other_time", 0)
    st.session_state["act_ex_time"] = r_data.get("ex_time", 0)
    st.session_state["act_ex_dist"] = r_data.get("ex_dist", 0.0)
    st.session_state["res_alcohol"] = r_data.get("alcohol", "飲まなかった")


# 初回起動時や日付変更時にフォーム値を同期
if "last_loaded_date" not in st.session_state:
    st.session_state.last_loaded_date = (
        datetime.date.today().year,
        datetime.date.today().month,
        st.session_state.selected_day,
    )
    update_form_values(
        st.session_state.last_loaded_date[0],
        st.session_state.last_loaded_date[1],
        st.session_state.last_loaded_date[2],
    )


# 当面目標の設定 ＆ バックアップ（サイドバー）
with st.sidebar:
    st.header("📌 当面目標の設定")
    target_title = st.text_input("目標内容", key="target_title")
    target_deadline = st.date_input("目標期日", key="target_deadline")

    if st.button("当面目標を更新・保存"):
        save_data_to_file()
        st.success("当面目標を保存しました！")

    today_date = datetime.date.today()
    remaining_days = (target_deadline - today_date).days
    st.info(
        f"🏆 **{target_title}**\n\n期日: {target_deadline}\n(残り **{remaining_days}** 日)"
    )

    st.divider()
    st.header("💾 データのバックアップ")
    st.caption("※データは自動保存されますが、期間を指定して書き出すことも可能です。")

    bk_mode = st.radio(
        "ダウンロード範囲", ["全期間データ", "期間を指定する"], key="bk_mode"
    )

    filtered_export_data = {}
    if bk_mode == "期間を指定する":
        col_from, col_to = st.columns(2)
        with col_from:
            d_from = st.date_input(
                "開始日", value=datetime.date.today().replace(day=1), key="bk_from"
            )
        with col_to:
            d_to = st.date_input("終了日", value=datetime.date.today(), key="bk_to")

        for (y, m, d), val in st.session_state.data_store.items():
            try:
                current_d = datetime.date(y, m, d)
                if d_from <= current_d <= d_to:
                    filtered_export_data[f"{y}-{m}-{d}"] = val
            except Exception:
                pass
    else:
        filtered_export_data = {
            f"{y}-{m}-{d}": val
            for (y, m, d), val in st.session_state.data_store.items()
        }

    json_str = json.dumps(filtered_export_data, ensure_ascii=False, indent=4)
    st.download_button(
        label="📥 選択したデータをファイルに保存",
        data=json_str,
        file_name="target_sheet_custom.json",
        mime="application/json",
    )

    uploaded_file = st.file_uploader(
        "📤 別のファイルを読み込んでマージ", type=["json"]
    )
    if uploaded_file is not None:
        try:
            imported_raw = json.load(uploaded_file)
            for k, val in imported_raw.items():
                if k == "meta":
                    continue
                parts = k.split("-")
                st.session_state.data_store[
                    (int(parts[0]), int(parts[1]), int(parts[2]))
                ] = val
            save_data_to_file()
            st.success("ファイルを追加読み込みしました！")
            st.rerun()
        except Exception as e:
            st.error(f"ファイルの読み込みに失敗しました: {e}")

# --- タブでシートを分ける ---
tab_goal, tab_result = st.tabs(
    ["🎯 目標シート（予定・入力）", "📊 結果シート（実績・成果）"]
)

# ==========================================
# 1. 目標シート（カレンダー ＆ 予定入力）
# ==========================================
with tab_goal:
    st.subheader("📅 月別カレンダー ＆ 予定入力")

    col_y, col_m = st.columns(2)
    with col_y:
        selected_year = st.selectbox(
            "年を選択", range(2025, 2031), index=1, key="goal_year"
        )
    with col_m:
        selected_month = st.selectbox(
            "月を選択",
            range(1, 13),
            index=datetime.date.today().month - 1,
            key="goal_month",
        )

    st.divider()

    cal = calendar.monthrange(selected_year, selected_month)
    num_days = cal[1]

    cols = st.columns(7)
    week_days = ["日", "月", "火", "水", "木", "金", "土"]
    for i, day_name in enumerate(week_days):
        cols[i].markdown(f"**{day_name}**")

    for day in range(1, num_days + 1):
        date_obj = datetime.date(selected_year, selected_month, day)
        w_idx = date_obj.weekday()
        sun_start_idx = (w_idx + 1) % 7

        is_today = date_obj == datetime.date.today()
        is_selected = day == st.session_state.selected_day
        is_deadline = date_obj == target_deadline

        btn_label = f"{day}日"
        if is_deadline:
            btn_label = f"🎯 {day}日"

        if is_selected:
            btn_label = f"👉 {day}日"
            btn_type = "primary"
        elif is_today:
            btn_label = f"⭐ {day}日"
            btn_type = "secondary"
        else:
            btn_type = "secondary"

        if cols[sun_start_idx].button(
            btn_label, key=f"goal_day_{day}", type=btn_type
        ):
            st.session_state.selected_day = day
            st.session_state.goal_saved_msg = ""
            st.session_state.last_loaded_date = (selected_year, selected_month, day)
            update_form_values(selected_year, selected_month, day)
            st.rerun()

    st.divider()

    target_day = st.session_state.selected_day
    st.markdown(
        f"### ✏️ {selected_year}年{selected_month}月{target_day}日の目標・予定"
    )

    work_options = [
        "日勤 🌞(D) 8:30～17:15",
        "夜勤 🌟(N) 17:15～8:30",
        "明け 💤(ー) 次回勤務まで休み",
        "休み 🙌(B)",
        "その他",
    ]

    with st.form(key="goal_form"):
        work_status = st.selectbox(
            "今日の勤務予定", work_options, key="goal_work"
        )

        st.markdown("#### 【当面目標に対しての予定】🎯")
        plan_target = st.text_input("予定内容", key="plan_target")
        expected_time = st.number_input(
            "予定時間 (分)", min_value=0, step=15, key="expected_time"
        )

        st.markdown("#### 【当面目標以外の予定】")
        plan_other = st.text_input("予定内容", key="plan_other")
        expected_time_other = st.number_input(
            "予定時間 (分)", min_value=0, step=15, key="expected_time_other"
        )

        st.markdown("#### 【運動・健康予定】🏃")
        exercise_plan = st.text_input(
            "運動の種類・目標（例: ランニング）", key="exercise_plan"
        )
        exercise_time = st.number_input(
            "予定運動時間 (分)", min_value=0, step=5, key="goal_ex_time"
        )
        exercise_dist = st.number_input(
            "予定距離 (km)", min_value=0.0, step=0.1, key="goal_ex_dist"
        )

        st.markdown("#### 【飲酒の予定】🍺")
        alcohol_goal = st.radio(
            "お酒は飲む予定ですか？", ["飲まない", "飲む"], key="goal_alcohol"
        )

        submitted_goal = st.form_submit_button("💾 目標を保存する")

    if submitted_goal:
        key_date = (selected_year, selected_month, target_day)
        if key_date not in st.session_state.data_store:
            st.session_state.data_store[key_date] = {}
        st.session_state.data_store[key_date]["goal"] = {
            "work": work_status,
            "plan_target": plan_target,
            "target_time": expected_time,
            "plan_other": plan_other,
            "other_time": expected_time_other,
            "exercise_plan": exercise_plan,
            "ex_time": exercise_time,
            "ex_dist": exercise_dist,
            "alcohol": alcohol_goal,
        }
        save_data_to_file()
        st.session_state.goal_saved_msg = (
            f"{selected_year}年{selected_month}月{target_day}日の目標を保存しました！"
        )
        st.rerun()

    if st.session_state.goal_saved_msg:
        st.success(st.session_state.goal_saved_msg)


# ==========================================
# 2. 結果シート（実績・成果の確認）
# ==========================================
with tab_result:
    st.subheader("📈 実績・成果の振り返り")

    col_ry, col_rm = st.columns(2)
    with col_ry:
        res_year = st.selectbox(
            "年を選択", range(2025, 2031), index=1, key="res_year"
        )
    with col_rm:
        res_month = st.selectbox(
            "月を選択",
            range(1, 13),
            index=datetime.date.today().month - 1,
            key="res_month",
        )

    st.divider()

    res_day = st.selectbox(
        "振り返る日を選択",
        range(1, calendar.monthrange(res_year, res_month)[1] + 1),
        key="res_day_select",
    )

    saved_data = st.session_state.data_store.get(
        (res_year, res_month, res_day), {}
    )
    g_goal = saved_data.get("goal", {})
    r_result = saved_data.get("result", {})

    p_target_time = g_goal.get("target_time", 0)
    p_other_time = g_goal.get("other_time", 0)
    p_ex_time = g_goal.get("ex_time", 0)
    p_ex_dist = g_goal.get("ex_dist", 0.0)
    p_alcohol = g_goal.get("alcohol", "飲まない")

    st.markdown(f"### 📝 {res_year}年{res_month}月{res_day}日の結果入力")

    res_work_options = [
        "日勤 🌞(D) 8:30～17:15",
        "夜勤 🌟(N) 17:15～8:30",
        "明け 💤(ー) 次回勤務まで休み",
        "休み 🙌(B)",
        "その他",
    ]

    with st.form(key="result_form"):
        actual_work = st.selectbox(
            "実際の勤務", res_work_options, key="res_work"
        )

        st.markdown("#### 【当面目標の実績】🎯")
        actual_target_time = st.number_input(
            "実施した時間 (分)", min_value=0, step=15, key="act_t_time"
        )
        st.markdown(
            f"<p style='color:red; font-size:14px;'>👉 目標の予定時間: {p_target_time} 分</p>",
            unsafe_allow_html=True,
        )

        st.markdown("#### 【当面目標以外の実績】")
        actual_other_time = st.number_input(
            "その他の実施時間 (分)", min_value=0, step=15, key="act_o_time"
        )
        st.markdown(
            f"<p style='color:red; font-size:14px;'>👉 目標の予定時間: {p_other_time} 分</p>",
            unsafe_allow_html=True,
        )

        st.markdown("#### 【運動・健康の実績】🏃")
        actual_exercise_time = st.number_input(
            "運動時間 (分)", min_value=0, step=5, key="act_ex_time"
        )
        st.markdown(
            f"<p style='color:red; font-size:14px;'>👉 目標の予定時間: {p_ex_time} 分</p>",
            unsafe_allow_html=True,
        )

        actual_exercise_dist = st.number_input(
            "距離 (km)", min_value=0.0, step=0.1, key="act_ex_dist"
        )
        st.markdown(
            f"<p style='color:red; font-size:14px;'>👉 目標の予定距離: {p_ex_dist} km</p>",
            unsafe_allow_html=True,
        )

        st.markdown("#### 【飲酒の実績】🍺")
        alcohol = st.radio(
            "お酒は飲みましたか？",
            ["飲まなかった", "飲んだ"],
            key="res_alcohol",
        )
        st.markdown(
            f"<p style='color:red; font-size:14px;'>👉 お酒の予定: {p_alcohol}</p>",
            unsafe_allow_html=True,
        )

        submitted_result = st.form_submit_button("💾 結果を保存する")

    if submitted_result:
        if (res_year, res_month, res_day) not in st.session_state.data_store:
            st.session_state.data_store[(res_year, res_month, res_day)] = {}
        st.session_state.data_store[(res_year, res_month, res_day)]["result"] = {
            "work": actual_work,
            "target_time": actual_target_time,
            "other_time": actual_other_time,
            "ex_time": actual_exercise_time,
            "ex_dist": actual_exercise_dist,
            "alcohol": alcohol,
            "target_achieved": actual_target_time >= p_target_time,
            "other_achieved": actual_other_time >= p_other_time,
            "ex_time_achieved": actual_exercise_time >= p_ex_time,
            "ex_dist_achieved": actual_exercise_dist >= p_ex_dist,
        }
        save_data_to_file()
        st.session_state.result_saved_msg = (
            f"{res_year}年{res_month}月{res_day}日の実績を保存し、サマリーを更新しました！"
        )
        st.rerun()

    if st.session_state.result_saved_msg:
        st.success(st.session_state.result_saved_msg)

    # --- 月間集計サマリーの集計 ---
    tot_target_mins = 0
    tot_other_mins = 0
    tot_ex_mins = 0
    tot_ex_dist = 0.0
    alcohol_days = 0

    target_achieve_count = 0
    other_achieve_count = 0
    ex_time_achieve_count = 0
    ex_dist_achieve_count = 0

    for (y, m, d), val in st.session_state.data_store.items():
        if y == res_year and m == res_month and "result" in val:
            res = val["result"]
            tot_target_mins += res.get("target_time", 0)
            tot_other_mins += res.get("other_time", 0)
            tot_ex_mins += res.get("ex_time", 0)
            tot_ex_dist += res.get("ex_dist", 0.0)

            if res.get("alcohol") == "飲んだ":
                alcohol_days += 1

            if res.get("target_achieved", False):
                target_achieve_count += 1
            if res.get("other_achieved", False):
                other_achieve_count += 1
            if res.get("ex_time_achieved", False):
                ex_time_achieve_count += 1
            if res.get("ex_dist_achieved", False):
                ex_dist_achieve_count += 1

    tot_target_hours = tot_target_mins / 60
    tot_other_hours = tot_other_mins / 60
    tot_ex_hours = tot_ex_mins / 60

    st.divider()
    st.markdown(f"### 🏆 {res_year}年{res_month}月度 月間集計サマリー")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "目標達成 時間",
        f"{tot_target_hours:.1f} 時間",
        f"達成: {target_achieve_count}回",
    )
    col2.metric(
        "その他 時間",
        f"{tot_other_hours:.1f} 時間",
        f"達成: {other_achieve_count}回",
    )
    col3.metric(
        "運動 合計時間",
        f"{tot_ex_hours:.1f} 時間",
        f"達成: {ex_time_achieve_count}回",
    )
    col4.metric(
        "運動 合計距離",
        f"{tot_ex_dist:.1f} km",
        f"達成: {ex_dist_achieve_count}回",
    )

    st.metric("飲酒 合計日数", f"{alcohol_days} 日")