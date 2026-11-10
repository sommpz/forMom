import os
import sqlite3
import secrets
import hashlib
import hmac
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st

st.set_page_config(page_title="강의문답", page_icon="📘", layout="centered")
DB = os.environ.get("QA_DB_PATH", "lecture_qa.sqlite3")
KEYWORDS = ["리더십", "조직·팀", "동기부여", "의사결정", "강의 내용", "과제·평가", "기타"]

def connect():
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, course TEXT NOT NULL,
        keyword TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
        context TEXT NOT NULL, answer TEXT DEFAULT '', pinned INTEGER DEFAULT 0,
        salt TEXT NOT NULL, digest TEXT NOT NULL, created TEXT NOT NULL)''')
    c.commit()
    return c

def stamp():
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")

def digest(code, salt):
    return hashlib.pbkdf2_hmac("sha256", code.encode(), bytes.fromhex(salt), 150000).hex()

def add_question(course, keyword, title, body, context, code):
    salt = secrets.token_hex(16)
    with connect() as c:
        cur = c.execute("INSERT INTO questions(course,keyword,title,body,context,salt,digest,created) VALUES(?,?,?,?,?,?,?,?)",
                        (course, keyword, title, body, context, salt, digest(code,salt), stamp()))
        return cur.lastrowid

def remove_question(qid, code):
    with connect() as c:
        row = c.execute("SELECT salt,digest FROM questions WHERE id=?", (qid,)).fetchone()
        if row and hmac.compare_digest(digest(code,row['salt']), row['digest']):
            c.execute("DELETE FROM questions WHERE id=?", (qid,))
            return True
    return False

def secret_value(key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

st.markdown('''<style>
.stApp {background:#f6f7fa; color:#202b3c;}
.block-container {max-width:960px;padding-top:2rem;}
h1 {letter-spacing:-1px;color:#213a57;}
[data-testid="stVerticalBlockBorderWrapper"] {background:white;border-radius:14px;}
.stButton>button {border-radius:9px;min-height:42px;}
</style>''', unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state.page = "home"
if "admin" not in st.session_state:
    st.session_state.admin = False

if st.session_state.page == "home":
    st.title("강의문답")
    st.subheader("질문에서 시작하는 더 깊은 수업")
    st.write("교수님께 묻고 싶었던 내용을 이름 없이 남기세요. 질문과 답변은 수업별·주제별로 함께 살펴볼 수 있습니다.")
    with st.container(border=True):
        st.markdown("**리더십·경영 강의를 위한 익명 질문 공간**")
        st.write("① 수업 선택 → ② 주제와 질문 등록 → ③ 교수님 답변 확인")
        st.caption("실명·학번 입력은 받지 않습니다. 군사·비공개 자료, 개인정보는 올리지 마세요. 질문에 신원이 드러나는 내용도 적지 않는 것이 좋습니다.")
    if st.button("질문 게시판 입장", type="primary", use_container_width=True):
        st.session_state.page = "board"
        st.rerun()
    st.caption("질문은 공개 게시판에 올라갑니다. 성적 이의나 개인 상담은 학교의 공식 연락 경로를 이용하세요.")
    st.stop()

left,right = st.columns([4,1])
left.title("강의문답")
if right.button("홈으로"):
    st.session_state.page = "home"
    st.rerun()

# Configure COURSES in Streamlit secrets as a list of actual course names.
configured = secret_value("COURSES", ["리더십·경영"])
courses = configured if isinstance(configured,list) and configured else ["리더십·경영"]
course = st.selectbox("수업", courses)

with st.expander("교수자 관리"):
    password = secret_value("ADMIN_PASSWORD")
    if st.session_state.admin:
        st.success("교수자 모드입니다.")
        if st.button("교수자 로그아웃"):
            st.session_state.admin = False
            st.rerun()
    elif not password:
        st.info('교수자 답변 기능을 사용하려면 배포 설정의 Secrets에 ADMIN_PASSWORD = "충분히 긴 비밀번호"를 등록하세요. 기본 비밀번호는 없습니다.')
    else:
        with st.form("login"):
            entry = st.text_input("교수자 비밀번호", type="password")
            login = st.form_submit_button("로그인")
        if login:
            if hmac.compare_digest(entry.encode(),str(password).encode()):
                st.session_state.admin = True
                st.rerun()
            else:
                st.error("비밀번호가 일치하지 않습니다.")

with st.expander("새 질문 등록", expanded=False):
    with st.form("new_question", clear_on_submit=True):
        keyword = st.selectbox("키워드", KEYWORDS)
        title = st.text_input("질문 제목", max_chars=100, placeholder="예: 팀의 자율성과 책임은 어떻게 함께 높이나요?")
        context = st.text_input("수업 맥락 (선택)", max_chars=150, placeholder="예: 3주차 / 교재 42쪽 / 사례 토론")
        body = st.text_area("질문 내용", max_chars=3000, placeholder="궁금한 점과 본인이 생각해 본 내용을 적어주세요.")
        code = st.text_input("삭제용 암호 (6자 이상)", type="password", max_chars=100, help="다른 곳에서 쓰는 비밀번호는 피하세요. 분실하면 본인이 직접 삭제할 수 없습니다.")
        agreed = st.checkbox("공개 가능한 내용이며 개인정보·군사·비공개 정보가 없음을 확인했습니다.")
        submitted = st.form_submit_button("익명으로 등록", type="primary")
    if submitted:
        if not title.strip() or not body.strip() or len(code.strip()) < 6 or not agreed:
            st.error("제목·내용·6자 이상 삭제 암호와 공개 확인이 필요합니다. 입력 칸을 다시 작성해 주세요.")
        else:
            qid = add_question(course,keyword,title.strip(),body.strip(),context.strip(),code)
            st.success(f"질문 #{qid}을 등록했습니다. 삭제 암호는 별도로 기억해 주세요.")

c1,c2,c3 = st.columns([2,1,1])
search = c1.text_input("질문 검색", placeholder="제목·내용·답변 검색")
status = c2.selectbox("답변 상태", ["전체", "답변 대기", "답변 완료"])
if c3.button("새로고침", use_container_width=True):
    st.rerun()
with connect() as c:
    rows = [dict(r) for r in c.execute("SELECT * FROM questions WHERE course=? ORDER BY pinned DESC,id DESC",(course,))]
if search:
    rows = [r for r in rows if search.casefold() in (r['title']+' '+r['body']+' '+r['answer']+' '+r['context']).casefold()]
if status != "전체":
    rows = [r for r in rows if bool(r['answer'].strip()) == (status == "답변 완료")]
st.caption(f"현재 조건의 질문 {len(rows)}개 · 답변은 새로고침하면 갱신됩니다.")

# Each keyword has a separate board; two-column cards resemble a sticky-note board.
for tab, kw in zip(st.tabs(["전체"]+KEYWORDS), [None]+KEYWORDS):
    with tab:
        selected = [r for r in rows if kw is None or r['keyword']==kw]
        if not selected:
            st.info("아직 질문이 없습니다. 첫 질문을 남겨보세요.")
        cols = st.columns(2)
        for i, q in enumerate(selected):
            prefix = f"{kw or 'all'}_{q['id']}"
            with cols[i%2]:
                with st.container(border=True):
                    st.caption(f"{'📌 ' if q['pinned'] else ''}{q['keyword']} · #{q['id']} · {q['created']}")
                    st.subheader(q['title'])
                    st.text(q['body'])
                    if q['context']:
                        st.caption("수업 맥락: "+q['context'])
                    if q['answer'].strip():
                        st.markdown("**교수님 답변**")
                        st.text(q['answer'])
                    else:
                        st.caption("답변 대기 중")
                    with st.expander("질문 삭제"):
                        with st.form("delete_"+prefix):
                            deletion = st.text_input("등록 시 설정한 암호",type="password")
                            delete = st.form_submit_button("이 질문 삭제")
                        if delete:
                            if remove_question(q['id'],deletion):
                                st.rerun()
                            else:
                                st.error("암호가 다르거나 이미 삭제된 질문입니다.")
                    if st.session_state.admin:
                        with st.expander("답변·관리"):
                            with st.form("answer_"+prefix):
                                answer = st.text_area("답변",value=q['answer'],max_chars=6000)
                                pin = st.checkbox("중요 질문으로 상단 고정",value=bool(q['pinned']))
                                save = st.form_submit_button("답변·고정 저장")
                            if save:
                                with connect() as c:
                                    c.execute("UPDATE questions SET answer=?,pinned=? WHERE id=?",(answer,int(pin),q['id']))
                                st.rerun()
                            confirm = st.checkbox("부적절한 질문임을 확인하고 삭제",key="confirm_"+prefix)
                            if st.button("교수자 삭제",key="admin_delete_"+prefix,disabled=not confirm):
                                with connect() as c:
                                    c.execute("DELETE FROM questions WHERE id=?",(q['id'],))
                                st.rerun()

st.divider()
st.caption("공개 가능한 강의 질문 전용 · 이름·학번은 수집하지 않지만 서비스 운영 과정의 접속 정보까지 익명성을 보장하지는 않습니다.")
with st.expander("운영 안내"):
    st.write("이 버전은 SQLite 로컬 저장을 사용합니다. 서버 초기화·재배포 시 질문이 사라질 수 있으므로 실제 수업에서는 외부 DB와 백업 구성을 권장합니다. 게시판 주소를 아는 사람은 질문을 읽고 등록할 수 있습니다.")
    st.write("배포 설정의 Secrets에서 COURSES = [\"실제 수업명\", \"다른 수업명\"]으로 수업 목록을 지정할 수 있습니다. 교수자 비밀번호는 코드나 공개 GitHub에 넣지 마세요.")
