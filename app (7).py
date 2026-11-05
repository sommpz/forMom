import json
import os
import uuid
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

st.set_page_config(page_title="손씨네 하루 To Do", page_icon="🏡", initial_sidebar_state="collapsed")
TASKS = {
    "wash": "🚿 씻기", "teeth": "🪥 양치하기", "tidy": "🧹 정리정돈",
    "homework": "✏️ 숙제·과제", "bible": "📖 말씀 읽기", "exercise": "🏃 운동·산책",
    "shopping": "🛒 장보기", "reading": "📚 독서", "prayer": "🙏 기도",
    "study": "📝 공부·업무", "dishes": "🍽️ 설거지", "laundry": "🧺 빨래",
    "recycling": "♻️ 분리수거", "prepare": "🎒 내일 준비", "water": "💧 물 마시기",
    "bed": "🌙 잠자리 준비", "kindness": "💛 가족 돕기", "hobby": "🎨 취미 시간",
    "plants": "🌱 식물 돌보기", "pet": "🐾 반려동물 돌보기",
    "breakfast": "🍳 아침 식사", "lunch": "🍱 점심 식사", "dinner": "🍚 저녁 식사",
    "stretch": "🙆 스트레칭", "thanks": "🌷 감사한 일 떠올리기", "rest": "☕ 쉬는 시간 갖기"
}
DEFAULT_TASKS = ["wash", "teeth", "tidy", "homework", "bible", "exercise", "shopping", "breakfast", "lunch", "dinner"]
DB = os.environ.get("HABIT_DB_PATH", "family_habits.sqlite3")


def connect():
    con = sqlite3.connect(DB, timeout=15)
    con.execute("PRAGMA busy_timeout=15000")
    con.execute("CREATE TABLE IF NOT EXISTS members (name TEXT PRIMARY KEY)")
    con.execute("CREATE TABLE IF NOT EXISTS checks (day TEXT NOT NULL, member TEXT NOT NULL, task TEXT NOT NULL, done INTEGER NOT NULL, changed TEXT NOT NULL, PRIMARY KEY(day,member,task))")
    con.execute("CREATE TABLE IF NOT EXISTS preferences (member TEXT PRIMARY KEY, tasks TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS custom_tasks (id TEXT PRIMARY KEY, member TEXT NOT NULL, label TEXT NOT NULL, UNIQUE(member,label))")
    con.execute("CREATE TABLE IF NOT EXISTS daily_plans (day TEXT, member TEXT, tasks TEXT NOT NULL, PRIMARY KEY(day,member))")
    con.execute("CREATE TABLE IF NOT EXISTS rewards (day TEXT, member TEXT, points INTEGER NOT NULL, PRIMARY KEY(day,member))")
    con.execute("CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT, sender TEXT, recipient TEXT, task TEXT, created TEXT, seen INTEGER DEFAULT 0)")
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
    return [t for t in json.loads(row[0]) if t in catalog(member)] if row else DEFAULT_TASKS.copy()


def set_tasks(member, tasks):
    with connect() as con:
        con.execute("INSERT INTO preferences(member,tasks) VALUES(?,?) ON CONFLICT(member) DO UPDATE SET tasks=excluded.tasks", (member, json.dumps(tasks)))


def catalog(member):
    result = TASKS.copy()
    with connect() as con:
        for key, label in con.execute("SELECT id,label FROM custom_tasks WHERE member=? ORDER BY rowid", (member,)):
            result[key] = display_label(label)
    return result


def guess_icon(text):
    rules = [
        ("🙏", ["기도", "예배"]), ("📖", ["말씀", "성경"]),
        ("🪥", ["양치", "치실"]), ("🚿", ["씻", "샤워", "목욕", "세수"]),
        ("🎹", ["피아노", "건반"]), ("🎸", ["기타", "악기", "음악", "연주"]),
        ("🎨", ["그림", "미술", "만들기"]), ("🇬🇧", ["영어", "단어"]),
        ("✏️", ["숙제", "과제", "공부", "수학"]), ("📚", ["독서", "책 읽"]),
        ("⚽", ["축구"]), ("🏊", ["수영"]), ("🚲", ["자전거"]),
        ("🏃", ["운동", "산책", "달리기", "걷기"]), ("🙆", ["스트레칭"]),
        ("🍳", ["아침"]), ("🍱", ["점심"]), ("🍚", ["저녁", "식사", "밥"]),
        ("🛒", ["장보기", "구매", "쇼핑"]), ("🧹", ["정리", "청소"]),
        ("🍽️", ["설거지"]), ("🧺", ["빨래", "세탁"]), ("♻️", ["분리", "쓰레기"]),
        ("💧", ["물 마", "수분"]), ("🌱", ["식물", "물주기", "화분"]),
        ("🐾", ["강아지", "고양이", "반려", "사료"]), ("🌙", ["잠", "취침"]),
        ("🎒", ["준비", "등교", "가방"]), ("💻", ["코딩", "업무", "컴퓨터"]),
        ("💛", ["돕기", "감사", "배려"]), ("☕", ["쉬기", "휴식"])
    ]
    for icon, words in rules:
        if any(word in text for word in words):
            return icon
    return "🌟"


def display_label(label):
    # 예전 버전의 공통 별 아이콘도 이름에 맞춰 표시합니다.
    if label.startswith(("⭐ ", "🌟 ")):
        text = label.split(" ",1)[1]
        return guess_icon(text) + " " + text
    return label


def add_custom(member, label):
    label = label.strip()
    if not label or len(label) > 40:
        raise ValueError("항목은 1~40자로 입력해 주세요.")
    if label in [v.split(" ",1)[-1] for v in catalog(member).values()]:
        raise ValueError("이미 있는 항목이에요.")
    key = "custom_" + uuid.uuid4().hex
    with connect() as con:
        con.execute("INSERT INTO custom_tasks(id,member,label) VALUES(?,?,?)", (key, member, guess_icon(label) + " " + label))
    set_tasks(member, get_tasks(member) + [key])


def remove_task(member,task):
    tasks = [t for t in get_tasks(member) if t != task]
    if not tasks:
        raise ValueError("목표는 한 개 이상 남겨 주세요.")
    set_tasks(member,tasks)
    today = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    with connect() as con:
        row = con.execute("SELECT tasks FROM daily_plans WHERE day=? AND member=?",(today,member)).fetchone()
        if row:
            remaining = [t for t in json.loads(row[0]) if t != task]
            if remaining:
                con.execute("UPDATE daily_plans SET tasks=? WHERE day=? AND member=?",(json.dumps(remaining),today,member))
    sync_reward(today,member)


def send_reminder(day,sender,recipient,task):
    if sender == recipient:
        return "자신에게는 알림을 보낼 수 없어요."
    if task not in plan(day,recipient,False) or read_checks(day).get((recipient,task),False):
        return "이미 완료했거나 현재 목표에 없는 항목이에요. 새로고침해 주세요."
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    with connect() as con:
        last = con.execute("SELECT created FROM reminders WHERE day=? AND recipient=? AND task=? ORDER BY id DESC LIMIT 1",(day,recipient,task)).fetchone()
        if last and (now-datetime.fromisoformat(last[0])).total_seconds() < 1800:
            return "이 항목은 이미 알려줬어요. 30분 뒤 다시 보낼 수 있어요."
        con.execute("INSERT INTO reminders(day,sender,recipient,task,created) VALUES(?,?,?,?,?)",(day,sender,recipient,task,now.isoformat()))
    return "다정한 알림을 보냈어요 💌"


def plan(day, member, create=True):
    with connect() as con:
        row = con.execute("SELECT tasks FROM daily_plans WHERE day=? AND member=?", (day,member)).fetchone()
        if row:
            return json.loads(row[0])
        if not create:
            return []
        tasks = get_tasks(member)
        con.execute("INSERT OR IGNORE INTO daily_plans(day,member,tasks) VALUES(?,?,?)", (day,member,json.dumps(tasks)))
        row = con.execute("SELECT tasks FROM daily_plans WHERE day=? AND member=?", (day,member)).fetchone()
        return json.loads(row[0])


def sync_reward(day, member):
    tasks = plan(day,member,False)
    records = read_checks(day)
    complete = bool(tasks) and all(records.get((member,t),False) for t in tasks)
    with connect() as con:
        if complete:
            con.execute("INSERT OR IGNORE INTO rewards(day,member,points) VALUES(?,?,10)",(day,member))
        else:
            con.execute("DELETE FROM rewards WHERE day=? AND member=?",(day,member))


def points(member):
    with connect() as con:
        return con.execute("SELECT COALESCE(SUM(points),0) FROM rewards WHERE member=?",(member,)).fetchone()[0]


def read_checks(day):
    with connect() as con:
        return {(m, t): bool(d) for m, t, d in con.execute("SELECT member,task,done FROM checks WHERE day=?", (day,))}


def save_check(day, member, task, done):
    with connect() as con:
        con.execute("INSERT INTO checks(day,member,task,done,changed) VALUES(?,?,?,?,?) ON CONFLICT(day,member,task) DO UPDATE SET done=excluded.done,changed=excluded.changed", (day, member, task, int(done), datetime.now(ZoneInfo("Asia/Seoul")).isoformat()))


def changed(day, member, task, key):
    save_check(day, member, task, st.session_state[key])
    sync_reward(day,member)


# 선택 사항: Streamlit의 Secrets에 app_password를 설정하면 공용 암호를 요구합니다.
try:
    password = st.secrets.get("app_password", "")
except Exception:
    password = ""
if password and not st.session_state.get("authenticated", False):
    st.title("🌳 손씨네 하루 To Do")
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
.stApp {background:#F2FAF6;color:#263E35;}
[data-testid="stHeader"] {background:transparent;}
[data-testid="stExpander"], [data-testid="stVerticalBlockBorderWrapper"] {background:#FFFFFF;border-radius:20px;}
.stButton > button, .stFormSubmitButton > button {border-radius:15px;border:1px solid #B9DCCB;background:#FFF0E7;color:#263E35;min-height:42px;}
.stButton > button:hover {background:#DBF1E5;border-color:#49856A;}
[data-testid="stProgress"] {color:#49856A;}
.block-container {max-width:650px;padding-top:1rem;padding-bottom:1rem;}
h1 {font-size:1.7rem !important; margin-bottom:0 !important;}
[data-testid="stVerticalBlock"] {gap:.55rem;}
[data-testid="stMetricValue"] {font-size:1.4rem;}
.stCheckbox label {min-height:42px;}
</style>""", unsafe_allow_html=True)
st.title("🌳 손씨네 하루 To Do")
st.caption("🐣 작은 실천이 모여 쑥쑥! 서로 재촉하기보다 다정하게 도와줘요.")

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

with st.expander("⚙️ 내 체크 항목 선택 · 직접 추가"):
    st.caption("설정은 아직 시작하지 않은 날짜부터 적용됩니다. 오늘 목표는 아래에서 명시적으로 변경할 수 있어요.")
    with st.form(f"custom_{member}", clear_on_submit=True):
        new_label = st.text_input("새 항목 이름", max_chars=40, placeholder="예: 악기 연습, 영어 단어 외우기")
        if st.form_submit_button("➕ 내 항목 추가", use_container_width=True):
            try:
                add_custom(member,new_label)
                st.rerun()
            except (ValueError, sqlite3.IntegrityError) as exc:
                st.warning(str(exc))
    labels = catalog(member)
    with st.form(f"preferences_{member}"):
        picked = st.multiselect("사용할 항목", list(labels), default=get_tasks(member), format_func=lambda t: labels[t])
        if st.form_submit_button("기본 항목 저장", use_container_width=True):
            if not picked:
                st.warning("한 가지 이상 선택해 주세요.")
            else:
                set_tasks(member,picked)
                st.rerun()
    st.markdown("**🗑️ 내 목록에서 빼기**")
    st.caption("기본·직접 만든 항목 모두 삭제할 수 있어요. 오늘과 이후 기본 목록에서 빠지고 지난 기록은 유지돼요. 위 선택창에서 다시 추가할 수도 있어요.")
    for task in get_tasks(member):
        left, right = st.columns([4,1])
        left.write(labels[task])
        if right.button("🗑️",key=f"remove_{member}_{task}",help="내 목록에서 삭제"):
            try:
                remove_task(member,task)
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))
labels = catalog(member)

with st.expander("💌 내 알림함", expanded=True):
    st.caption("앱 안 알림이에요. 새 알림은 앱을 열거나 새로고침하면 보여요. 휴대폰 푸시는 전송하지 않아요.")
    with connect() as con:
        inbox = con.execute("SELECT id,day,sender,task,created FROM reminders WHERE recipient=? AND seen=0 ORDER BY id DESC",(member,)).fetchall()
    if not inbox:
        st.caption("도착한 알림이 없어요. 오늘도 응원해요 🐥")
    for rid,rday,sender,task,created in inbox:
        done = read_checks(rday).get((member,task),False)
        st.write(f"{'✅' if done else '🔔'} {sender} → {labels.get(task,task)} · {rday}")
        st.caption("이미 완료했어요!" if done else "혹시 잊었나요? 시간 될 때 함께 챙겨요 💛")
        if st.button("확인했어요 💛",key=f"seen_{rid}"):
            with connect() as con:
                con.execute("UPDATE reminders SET seen=1 WHERE id=? AND recipient=?",(rid,member))
            st.rerun()

now = datetime.now(ZoneInfo("Asia/Seoul"))
today = now.date()
selected = st.date_input("확인할 날짜", value=today, min_value=today-timedelta(days=365), max_value=today, format="YYYY/MM/DD")
day = selected.isoformat()
active_tasks = plan(day,member)
if selected == today:
    with st.expander("✏️ 오늘 목표 목록 변경"):
        st.caption("기본 항목 설정을 오늘에도 적용합니다. 오늘의 완료 상태와 10포인트도 새 목록으로 재계산됩니다.")
        if st.button("저장한 기본 항목을 오늘에 적용", key="apply_today", use_container_width=True):
            with connect() as con:
                con.execute("UPDATE daily_plans SET tasks=? WHERE day=? AND member=?",(json.dumps(get_tasks(member)),day,member))
            sync_reward(day,member)
            st.rerun()
sync_reward(day,member)
st.caption(f"🏅 누적 {points(member)}포인트 · 하루 목표 전부 완료하면 10포인트")
# 페이지를 다시 열거나 새로고침하면 DB에서 최신 기록을 읽습니다.
records = read_checks(day)
with st.container(border=True):
    st.markdown(f"**{member} · {'오늘' if selected == today else selected.strftime('%m월 %d일')}의 약속**")
    for task in active_tasks:
        label = labels.get(task,task)
        key = json.dumps([day, member, task], ensure_ascii=False)
        st.checkbox(label, value=records.get((member, task), False), key=key, on_change=changed, args=(day, member, task, key))

records = read_checks(day)
count = sum(records.get((member, task), False) for task in active_tasks)
st.caption("🌱 → 🌿 → 🌳 · " + ("오늘의 나무가 활짝 자랐어요! 🎉" if count == len(active_tasks) else "하나씩 실천하며 나무를 키워요."))
st.progress(count / len(active_tasks), text=f"{count} / {len(active_tasks)} 완료 · " + ("모두 해냈어요! 🎉" if count == len(active_tasks) else "차근차근 해봐요 🌱"))

with st.expander("🤝 가족 둘러보기 · 다정한 알림 보내기"):
    st.caption("위에서 선택한 별명이 보내는 사람이에요. 알림을 받는 가족은 자기 별명으로 앱을 열어 확인해 주세요.")
    others = [p for p in names if p != member]
    if not others:
        st.caption("다른 가족이 별명을 추가하면 함께 사용할 수 있어요.")
    else:
        recipient = st.selectbox("누구를 응원할까요?",others,key=f"recipient_{member}")
        target_labels = catalog(recipient)
        target_tasks = plan(day,recipient,False)
        if not target_tasks:
            st.info("이 가족은 선택한 날짜의 목표를 아직 시작하지 않았어요.")
        for task in target_tasks:
            done = records.get((recipient,task),False)
            left,right = st.columns([3,2])
            left.write(f"{'✅' if done else '🌱'} {target_labels.get(task,task)}")
            if not done and selected == today:
                if right.button("🔔 알려주기",key=f"remind_{member}_{recipient}_{day}_{task}"):
                    st.info(send_reminder(day,member,recipient,task))
        st.caption("오늘 미완료 항목에만 알림을 보낼 수 있어요. 같은 항목은 가족 전체 기준 30분에 한 번만 보내져요.")

with st.expander("👨‍👩‍👧‍👦 가족 현황 · 최근 7일"):
    if st.button("🔄 최신 기록 불러오기", use_container_width=True):
        # 다른 기기의 변경을 체크박스에도 반영합니다.
        for k in list(st.session_state):
            if k.startswith('["'):
                del st.session_state[k]
        st.rerun()
    st.caption("선택한 날짜의 현황 · 다른 기기의 변경은 위 버튼으로 갱신하세요.")
    for person in names:
        person_tasks = plan(day,person,False)
        done_count = sum(records.get((person, t), False) for t in person_tasks)
        st.write(f"{'⭐' if bool(person_tasks) and done_count == len(person_tasks) else '🌱'} {person}: {done_count}/{len(person_tasks)}")
        meal_text = " · ".join(f"{title} {'✅' if records.get((person,t),False) else '미확인'}" for t,title in [("breakfast","아침"),("lunch","점심"),("dinner","저녁")])
        st.caption(meal_text + f" · 누적 {points(person)}P")
    st.caption("미확인은 식사하지 않았다는 뜻이 아니라 아직 체크 기록이 없다는 뜻이에요. 0/0은 그날 목표를 아직 시작하지 않은 상태예요.")
    st.divider()
    st.caption(f"{member}의 최근 7일 (날짜별 저장한 목표 기준)")
    history = []
    for i in range(7):
        d = selected - timedelta(days=i)
        rows = read_checks(d.isoformat())
        day_tasks = plan(d.isoformat(),member,False)
        n = sum(rows.get((member, t), False) for t in day_tasks)
        history.append({"날짜": d.isoformat(), "완료": f"{n}/{len(day_tasks)}", "포인트": 10 if day_tasks and n == len(day_tasks) else 0, **{label: "✅" if rows.get((member, t), False) else "—" for t, label in labels.items() if t in set(active_tasks) | set(day_tasks)}})
    st.dataframe(history, hide_index=True, use_container_width=True)
    st.download_button("📥 이 사람의 7일 기록 저장", json.dumps(history, ensure_ascii=False, indent=2), file_name=f"habits_{day}.json", mime="application/json", use_container_width=True)

with st.expander("ℹ️ 사용 안내"):
    st.info("포인트는 하루 10점으로 중복 지급되지 않습니다. 완료 체크를 해제하면 그날 점수는 회수되고, 다시 모두 완료하면 복구됩니다. 지난 날짜도 동일하게 적용됩니다. 포인트는 현금이나 상품이 아닌 가족 응원용 기록입니다. 장보기는 완료 체크 기능입니다.")
    st.write("체크와 해제는 즉시 저장됩니다. 날짜는 한국 시간 기준이며, 새 날짜에는 새 체크 목록이 표시됩니다. 지난 날짜도 수정할 수 있습니다.")
    st.write("QR은 배포된 앱 주소를 QR로 만들어 사용하세요. QR 자체는 접근 권한을 제한하지 않습니다. 별명 선택은 본인 인증이 아니므로, 가족끼리 자신의 별명을 선택해 사용하세요.")
    st.warning("이 버전은 로컬 SQLite 저장 방식입니다. Streamlit Community Cloud의 재시작·재배포 등으로 기록이 사라질 수 있으므로 장기 보관용으로는 외부 DB 연결이 필요합니다. 건강·학교 등 민감한 정보 대신 별명을 사용하세요.")
    st.caption('가족 공용 암호를 쓰려면 Streamlit 앱 설정의 Secrets에 app_password = "원하는 암호"를 추가하세요. 공용 암호는 개인별 권한을 구분하지 않으므로 접속한 가족은 서로의 기록을 수정할 수 있습니다.')
