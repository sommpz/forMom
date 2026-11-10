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
KEYWORDS = [ "동기부여", "의사결정", "강의 내용", "과제·평가", "기타"]

def connect():
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, course TEXT NOT NULL,
        keyword TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
        context TEXT NOT NULL, answer TEXT DEFAULT '', pinned INTEGER DEFAULT 0,
        salt TEXT NOT NULL, digest TEXT NOT NULL, created TEXT NOT NULL)''')
    columns = {r[1] for r in c.execute("PRAGMA table_info(questions)")}
    if "author" not in columns:
        c.execute("ALTER TABLE questions ADD COLUMN author TEXT NOT NULL DEFAULT '익명'")
    c.execute("UPDATE questions SET keyword='기타' WHERE keyword IN ('리더십','조직·팀','조직','팀')")
    c.commit()
    return c

def stamp():
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")

def digest(code, salt):
    return hashlib.pbkdf2_hmac("sha256", code.encode(), bytes.fromhex(salt), 150000).hex()

def add_question(keyword, body, code, author="익명"):
    salt = secrets.token_hex(16)
    with connect() as c:
        cur = c.execute("INSERT INTO questions(course,keyword,title,body,context,salt,digest,created,author) VALUES(?,?,?,?,?,?,?,?,?)",
                        ("전용 게시판", keyword, "", body, "", salt, digest(code,salt), stamp(), author))
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
.stApp {background:#f5f7fb;color:#172c49;}
.block-container {max-width:960px;padding-top:2rem;padding-bottom:3rem;}
h1,h2,h3 {color:#142d50 !important;letter-spacing:-.6px;}
[data-testid="stVerticalBlockBorderWrapper"] {background:#fff;border-radius:16px;border-color:#dce3ef;}
.stButton>button,.stFormSubmitButton>button {border-radius:10px;min-height:44px;font-weight:600;}
button[kind="primary"],button[kind="primaryFormSubmit"] {background:#16345b !important;color:white !important;border-color:#16345b !important;}
button[kind="secondary"] {background:white;color:#16345b;border:1px solid #cbd6e6;}
[data-baseweb="tab-list"] {border-bottom:1px solid #dce3ef;gap:8px;}
[data-baseweb="tab"] {color:#25436b;}
[data-baseweb="tab-highlight"] {background:#16345b !important;}
[data-testid="stExpander"] {background:white;border-radius:12px;}
input,textarea {color:#172c49 !important;}
.home-mark {width:88px;height:88px;margin:0 auto 24px;background:#16345b;border-radius:24px;display:flex;align-items:center;justify-content:center;color:white;font-size:43px;font-weight:600;}
.home-title {text-align:center;font-size:clamp(36px,7vw,48px);font-weight:750;color:#142d50;letter-spacing:-2px;margin:0 0 32px;}
@media(max-width:600px){.block-container{padding-left:1rem;padding-right:1rem;}}
</style>''', unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state.page = "home"
if "admin" not in st.session_state:
    st.session_state.admin = False

if st.session_state.page == "home":
    st.markdown('<div style="height:12vh"></div><div class="home-mark" aria-label="책 아이콘">▤</div><div class="home-title">강의문답</div>', unsafe_allow_html=True)
    _, center, _ = st.columns([1, 2, 1])
    with center:
        if st.button("시작하기", type="primary", use_container_width=True):
            st.session_state.page = "board"
            st.rerun()
    st.stop()

left,right = st.columns([4,1])
left.title("강의문답")
if right.button("홈으로"):
    st.session_state.page = "home"
    st.rerun()

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
    st.caption("질문은 공개됩니다. 군사·비공개 자료나 타인의 개인정보는 올리지 마세요. 이름 공개 시 입력한 이름도 게시판에 표시됩니다.")
    mode = st.radio("작성자 표시", ["익명", "이름 공개"], horizontal=True)
    with st.form("new_question", clear_on_submit=False):
        name = st.text_input("공개할 이름", max_chars=40) if mode == "이름 공개" else ""
        keyword = st.selectbox("키워드", KEYWORDS)
        body = st.text_area("질문", max_chars=3000, placeholder="궁금한 내용을 적어주세요. 필요한 경우 주차나 교재 쪽수도 함께 적어주세요.")
        code = st.text_input("삭제용 암호 (6자 이상)", type="password", max_chars=100, help="다른 곳에서 쓰는 비밀번호는 피하세요. 분실하면 본인이 직접 삭제할 수 없습니다.")
        agreed = st.checkbox("공개 가능한 내용이며 비공개 정보·타인의 개인정보가 없음을 확인했습니다.")
        submitted = st.form_submit_button("질문 등록", type="primary")
    if submitted:
        if not body.strip() or len(code.strip()) < 6 or not agreed or (mode == "이름 공개" and not name.strip()):
            st.error("질문·6자 이상 삭제 암호·공개 확인을 입력해 주세요. 이름 공개를 선택했다면 이름도 필요합니다.")
        else:
            qid = add_question(keyword, body.strip(), code, name.strip() if mode == "이름 공개" else "익명")
            st.success(f"질문 #{qid}을 등록했습니다. 삭제 암호는 별도로 기억해 주세요. 같은 질문을 중복 등록하지 않도록 주의하세요.")

c1,c2,c3 = st.columns([2,1,1])
search = c1.text_input("질문 검색", placeholder="질문·답변 검색")
status = c2.selectbox("답변 상태", ["전체", "답변 대기", "답변 완료"])
if c3.button("새로고침", use_container_width=True):
    st.rerun()
with connect() as c:
    rows = [dict(r) for r in c.execute("SELECT * FROM questions ORDER BY pinned DESC,id DESC")]
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
                    st.caption("작성자: " + q['author'])
                    if q['title']:
                        st.text(q['title'])  # 이전 버전 질문 제목 보존
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
st.caption("공개 질문 게시판 · 공개 이름은 본인 인증되지 않습니다. 익명 선택도 서비스 운영 과정의 접속 정보까지 익명성을 보장하지는 않습니다.")
with st.expander("운영 안내"):
    st.write("이 버전은 SQLite 로컬 저장을 사용합니다. 서버 초기화·재배포 시 질문이 사라질 수 있으므로 실제 수업에서는 외부 DB와 백업 구성을 권장합니다. 게시판 주소를 아는 사람은 질문을 읽고 등록할 수 있습니다.")
    st.write("교수자 비밀번호 ADMIN_PASSWORD는 배포 설정의 Secrets에만 등록하세요. 코드나 공개 GitHub에 넣지 마세요.")
