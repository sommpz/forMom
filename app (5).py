import json
import os
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

st.set_page_config(page_title="우리 집 생활 체크", page_icon="🏡", initial_sidebar_state="collapsed")
TASKS = {
    "wash": "🚿 씻기", "teeth": "🪥 양치하기", "tidy": "🧹 정리정돈",
    "homework": "✏️ 숙제·과제", "bible": "📖 말씀 읽기", "exercise": "🏃 운동·산책",
    "shopping": "🛒 장보기", "reading": "📚 독서", "prayer": "🙏 기도",
    "study": "📝 공부·업무", "dishes": "🍽️ 설거지", "laundry": "🧺 빨래",
    "recycling": "♻️ 분리수거", "prepare": "🎒 내일 준비", "water": "💧 물 마시기",
    "bed": "🌙 잠자리 준비", "kindness": "💛 가족 돕기", "hobby": "🎨 취미 시간",
    "plants": "🌱 식물 돌보기", "pet": "🐾 반려동물 돌보기"
}
DEFAULT_TASKS = ["wash", "teeth", "tidy", "homework", "bible", "exercise", "shopping"]
DB = os.environ.get("HABIT_DB_PATH", "family_habits.sqlite3")


def connect():
    con = sqlite3.connect(DB, timeout=15)
    con.execute("PRAGMA busy_timeout=15000")
    con.execute("CREATE TABLE IF NOT EXISTS members (name TEXT PRIMARY KEY)")
    con.execute("CREATE TABLE IF NOT EXISTS checks (day TEXT NOT NULL, member TEXT NOT NULL, task TEXT NOT NULL, done INTEGER NOT NULL, changed TEXT NOT NULL, PRIMARY KEY(day,member,task))")
    con.execute("CREATE TABLE IF NOT EXISTS preferences (member TEXT PRIMARY KEY, tasks TEXT NOT NULL)")
    con.commit()
    return con


def members():
    with connect() as con:
        return [r[0] for r in con.execute("SELECT name FROM members ORDER BY rowid")]


def add_member(name):
    with connect() as con:
        con.execute("INSERT OR IGNORE INTO members(name) VALUES (?)", (name,))


def get_tasks(member):
    with connect() as con:
        row = con.execute("SELECT tasks FROM preferences WHERE member=?", (member,)).fetchone()
    return [t for t in json.loads(row[0]) if t in TASKS] if row else DEFAULT_TASKS.copy()


def set_tasks(member, tasks):
    with connect() as con:
        con.execute("INSERT INTO preferences(member,tasks) VALUES(?,?) ON CONFLICT(member) DO UPDATE SET tasks=excluded.tasks", (member, json.dumps(tasks)))


def read_checks(day):
    with connect() as con:
        return {(m, t): bool(d) for m, t, d in con.execute("SELECT member,task,done FROM checks WHERE day=?", (day,))}


def save_check(day, member, task, done):
    with connect() as con:
        con.execute("INSERT INTO checks(day,member,task,done,changed) VALUES(?,?,?,?,?) ON CONFLICT(day,member,task) DO UPDATE SET done=excluded.done,changed=excluded.changed", (day, member, task, int(done), datetime.now(ZoneInfo("Asia/Seoul")).isoformat()))


def changed(day, member, task, key):
    save_check(day, member, task, st.session_state[key])


# 선택 사항: Streamlit의 Secrets에 app_password를 설정하면 공용 암호를 요구합니다.
try:
    password = st.secrets.get("app_password", "")
except Exception:
    password = ""
if password and not st.session_state.get("authenticated", False):
    st.title("🏡 우리 집 생활 체크")
    with st.form("login"):
        entered = st.text_input("가족 공용 암호", type="password")
        login = st.form_submit_button("들어가기", use_container_width=True)
    if login:
        import hmac
        if hmac.compare_digest(entered, str(password)):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("암호를 다시 확인해 주세요.")
    st.stop()

st.markdown("""<style>
.block-container {max-width:650px;padding-top:1rem;padding-bottom:1rem;}
h1 {font-size:1.7rem !important; margin-bottom:0 !important;}
[data-testid="stVerticalBlock"] {gap:.55rem;}
[data-testid="stMetricValue"] {font-size:1.4rem;}
.stCheckbox label {min-height:42px;}
</style>""", unsafe_allow_html=True)
st.title("🏡 우리 집 생활 체크")
st.caption("오늘의 작은 약속, 하나씩 체크해요. 잘못 누르면 다시 해제할 수 있어요.")

names = members()

@st.dialog("👨‍👩‍👧‍👦 가족 추가")
def add_dialog():
    with st.form("new_member", clear_on_submit=True):
        name = st.text_input("이름 또는 별명", max_chars=20, placeholder="예: 민지")
        submitted = st.form_submit_button("추가", use_container_width=True)
    if submitted:
        cleaned = name.strip()
        if not cleaned:
            st.warning("이름을 입력해 주세요.")
        elif cleaned in members():
            st.warning("이미 등록된 이름이에요.")
        else:
            add_member(cleaned)
            st.session_state["member_select"] = cleaned
            st.rerun()

if not names:
    st.info("먼저 체크할 가족의 이름이나 별명을 추가해 주세요.")
    if st.button("➕ 가족 추가", use_container_width=True):
        add_dialog()
    st.caption("같은 주소로 접속하면 같은 목록을 사용합니다. 가족 전용으로 사용하려면 공용 암호를 설정하세요.")
    st.stop()

a, b = st.columns([3, 1])
with a:
    member = st.selectbox("누구의 하루인가요?", names, key="member_select")
with b:
    st.write("")
    if st.button("➕ 가족", use_container_width=True):
        add_dialog()

with st.expander("⚙️ 내 체크 항목 선택"):
    st.caption("나에게 필요한 항목만 고르세요. 체크 해제한 항목의 기존 기록은 삭제되지 않아요. 장보기는 완료 확인용이며 상품·금액 관리는 포함하지 않습니다.")
    with st.form(f"preferences_{member}"):
        picked = st.multiselect("사용할 항목", list(TASKS), default=get_tasks(member), format_func=lambda t: TASKS[t])
        if st.form_submit_button("항목 저장", use_container_width=True):
            if not picked:
                st.warning("한 가지 이상 선택해 주세요.")
            else:
                set_tasks(member, picked)
                st.rerun()
active_tasks = get_tasks(member)

now = datetime.now(ZoneInfo("Asia/Seoul"))
today = now.date()
selected = st.date_input("확인할 날짜", value=today, min_value=today-timedelta(days=365), max_value=today, format="YYYY/MM/DD")
day = selected.isoformat()
# 페이지를 다시 열거나 새로고침하면 DB에서 최신 기록을 읽습니다.
records = read_checks(day)
with st.container(border=True):
    st.markdown(f"**{member} · {'오늘' if selected == today else selected.strftime('%m월 %d일')}의 약속**")
    for task in active_tasks:
        label = TASKS[task]
        key = json.dumps([day, member, task], ensure_ascii=False)
        st.checkbox(label, value=records.get((member, task), False), key=key, on_change=changed, args=(day, member, task, key))

records = read_checks(day)
count = sum(records.get((member, task), False) for task in active_tasks)
st.progress(count / len(active_tasks), text=f"{count} / {len(active_tasks)} 완료 · " + ("모두 해냈어요! 🎉" if count == len(active_tasks) else "차근차근 해봐요 🌱"))

with st.expander("👨‍👩‍👧‍👦 가족 현황 · 최근 7일"):
    if st.button("🔄 최신 기록 불러오기", use_container_width=True):
        # 다른 기기의 변경을 체크박스에도 반영합니다.
        for k in list(st.session_state):
            if k.startswith('["'):
                del st.session_state[k]
        st.rerun()
    st.caption("선택한 날짜의 현황 · 다른 기기의 변경은 위 버튼으로 갱신하세요.")
    for person in names:
        person_tasks = get_tasks(person)
        done_count = sum(records.get((person, t), False) for t in person_tasks)
        st.write(f"{'⭐' if done_count == len(person_tasks) else '🌱'} {person}: {done_count}/{len(person_tasks)}")
    st.divider()
    st.caption(f"{member}의 최근 7일 (현재 선택한 항목 기준)")
    history = []
    for i in range(7):
        d = selected - timedelta(days=i)
        rows = read_checks(d.isoformat())
        n = sum(rows.get((member, t), False) for t in active_tasks)
        history.append({"날짜": d.isoformat(), "완료": f"{n}/{len(active_tasks)}", **{label: "✅" if rows.get((member, t), False) else "—" for t, label in TASKS.items() if t in active_tasks}})
    st.dataframe(history, hide_index=True, use_container_width=True)
    st.download_button("📥 이 사람의 7일 기록 저장", json.dumps(history, ensure_ascii=False, indent=2), file_name=f"habits_{day}.json", mime="application/json", use_container_width=True)

with st.expander("ℹ️ 사용 안내"):
    st.write("체크와 해제는 즉시 저장됩니다. 날짜는 한국 시간 기준이며, 새 날짜에는 새 체크 목록이 표시됩니다. 지난 날짜도 수정할 수 있습니다.")
    st.write("QR은 배포된 앱 주소를 QR로 만들어 사용하세요. QR 자체는 접근 권한을 제한하지 않습니다.")
    st.warning("이 버전은 로컬 SQLite 저장 방식입니다. Streamlit Community Cloud의 재시작·재배포 등으로 기록이 사라질 수 있으므로 장기 보관용으로는 외부 DB 연결이 필요합니다. 건강·학교 등 민감한 정보 대신 별명을 사용하세요.")
    st.caption('가족 공용 암호를 쓰려면 Streamlit 앱 설정의 Secrets에 app_password = "원하는 암호"를 추가하세요. 공용 암호는 개인별 권한을 구분하지 않으므로 접속한 가족은 서로의 기록을 수정할 수 있습니다.')
