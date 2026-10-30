import io
import os
import sqlite3
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

import qrcode
import streamlit as st

st.set_page_config(page_title="장보기 알림 메모", page_icon="🛒", layout="centered", initial_sidebar_state="collapsed")

# Streamlit Community Cloud의 로컬 파일은 재배포/재시작 시 초기화될 수 있습니다.
# 장기 보관용 서비스라면 이 SQLite 저장소를 외부 DB로 교체하세요.
DB_PATH = os.environ.get("SHOPPING_DB_PATH", "shopping.sqlite3")
CATEGORIES = ["🥬 야채", "🍎 과일", "🥩 육류·생선", "🥛 유제품·달걀", "🍚 쌀·면·빵", "🥫 가공·냉동", "🧻 생활용품", "📦 기타"]
PRIORITIES = {1: "1 · 꼭 필요", 2: "2 · 가격 보고", 3: "3 · 저렴할 때"}


def connect():
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def initialize():
    with connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY, list_id TEXT NOT NULL, name TEXT NOT NULL,
            category TEXT NOT NULL, priority INTEGER NOT NULL CHECK(priority BETWEEN 1 AND 3),
            target INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'todo', quantity REAL, unit_price INTEGER,
            total INTEGER, created TEXT NOT NULL, purchased TEXT
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS list_idx ON items(list_id, status)")


def rows(list_id, status=None):
    with connect() as con:
        if status:
            return con.execute("SELECT * FROM items WHERE list_id=? AND status=? ORDER BY priority, created", (list_id, status)).fetchall()
        return con.execute("SELECT * FROM items WHERE list_id=? ORDER BY priority, created", (list_id,)).fetchall()


def change(item_id, status):
    with connect() as con:
        con.execute("UPDATE items SET status=? WHERE id=? AND list_id=?", (status, item_id, list_id))


def line_total(quantity, price):
    return int((Decimal(str(quantity)) * Decimal(str(price))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


initialize()
raw_id = st.query_params.get("list", "")
try:
    list_id = str(uuid.UUID(raw_id))
except (ValueError, TypeError, AttributeError):
    list_id = str(uuid.uuid4())
    st.query_params["list"] = list_id

st.markdown("""<style>
header[data-testid="stHeader"] {height: 0; min-height:0;}
.block-container {padding: .65rem .65rem .4rem; max-width: 680px;}
.stMainBlockContainer {padding-top:.65rem;}
h3 {padding:0 !important; margin:0 !important; font-size:1.22rem !important;}
[data-testid="stVerticalBlock"] {gap:.35rem;}
[data-testid="stHorizontalBlock"] {gap:.35rem;}
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {min-width:0 !important;}
[data-testid="stMarkdownContainer"] p {margin-bottom:.1rem; font-size:.88rem;}
[data-testid="stCaptionContainer"] p {font-size:.73rem;}
.stButton button {min-height:2.25rem; padding:.2rem .35rem; font-size:.79rem;}
[data-testid="stMetric"] {background:#edf7ee; border-radius:12px; padding:.4rem .65rem;}
[data-testid="stMetricLabel"] {font-size:.8rem;}
[data-testid="stMetricValue"] {font-size:1.5rem;}
[data-testid="stElementToolbar"] {display:none;}
@media(max-width:640px){
 [data-testid="stHorizontalBlock"] {flex-wrap:nowrap !important;}
 [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {flex:1 1 0; width:auto !important;}
 .block-container {padding-left:.5rem; padding-right:.5rem;}
}
</style>""", unsafe_allow_html=True)


@st.dialog("➕ 장보기 메모 추가")
def add_item():
    with st.form("add_form", clear_on_submit=False):
        category = st.selectbox("카테고리", CATEGORIES)
        name = st.text_input("상품명", placeholder="예: 양파 3개, 우유 1L", max_chars=60)
        priority = st.select_slider("중요도", options=[1, 2, 3], value=2, format_func=lambda p: PRIORITIES[p])
        target = 0  # 메모 추가 화면에서는 희망 단가를 입력받지 않습니다.
        note = st.text_input("짧은 메모 (선택)", placeholder="예: 국내산 / 1+1이면 구매", max_chars=100)
        if st.form_submit_button("메모에 추가", use_container_width=True):
            if not name.strip():
                st.error("상품명을 입력해 주세요.")
            else:
                with connect() as con:
                    con.execute("INSERT INTO items(id,list_id,name,category,priority,target,note,created) VALUES(?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), list_id, name.strip(), category, priority, int(target), note.strip(), datetime.now().isoformat()))
                st.rerun()


@st.dialog("🛒 카트에 담기")
def buy_item(item):
    st.write(f"**{item['name']}** · {PRIORITIES[item['priority']]}")
    if item["note"]:
        st.caption(item["note"])
    quantity = st.number_input("수량 (무게 상품은 0.5 등 소수 가능)", min_value=0.01, max_value=100000.0, value=1.0, step=1.0, format="%.2f")
    price = st.number_input("개당 가격 (원, 할인 반영)", min_value=0, max_value=100000000, value=int(item["target"]), step=100)
    total = line_total(quantity, price)
    st.metric("이번 상품 합계", f"{total:,}원")
    exceeds = item["target"] > 0 and price > item["target"]
    if exceeds:
        st.warning(f"생각한 개당 가격보다 {price - item['target']:,}원 비싸요. 안 사도 괜찮아요!")
    elif item["priority"] >= 2:
        st.info("비싸게 느껴지면 보류하세요. 메모는 남아 있습니다.")
    confirm = True
    if exceeds:
        confirm = st.checkbox("가격을 확인했고, 그래도 구매할게요")
    a, b = st.columns(2)
    if a.button("담기 확정", type="primary", disabled=not confirm, use_container_width=True):
        with connect() as con:
            con.execute("UPDATE items SET status='cart',quantity=?,unit_price=?,total=?,purchased=? WHERE id=? AND list_id=? AND status IN ('todo','hold')", (quantity, int(price), total, datetime.now().isoformat(), item["id"], list_id))
        st.rerun()
    if b.button("비싸요 · 보류", use_container_width=True):
        change(item["id"], "hold")
        st.rerun()


@st.dialog("🔗 QR로 이 목록 열기")
def share_list():
    st.caption("배포한 앱의 주소를 입력하면, 현재 목록을 여는 QR이 만들어집니다. 주소를 아는 사람은 같은 목록을 보고 수정할 수 있습니다.")
    base = st.text_input("배포된 앱 주소", placeholder="https://your-app.streamlit.app", key="public_url")
    if base.strip():
        from urllib.parse import urlsplit, urlunsplit, parse_qsl
        parsed = urlsplit(base.strip())
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            st.error("https://로 시작하는 올바른 앱 주소를 입력하세요.")
            return
        query = dict(parse_qsl(parsed.query))
        query["list"] = list_id
        url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))
        image = qrcode.make(url)
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        st.image(buf.getvalue(), width=220)
        st.link_button("이 목록 열기", url, use_container_width=True)
        st.code(url, language=None)
        st.download_button("QR 이미지 저장", buf.getvalue(), "shopping_qr.png", "image/png")
    st.info("첫 배포 후 이 QR 주소를 북마크하세요. 기본 주소로 새로 접속하면 새 목록이 만들어집니다.")
    st.caption("휴대폰 알림을 보내는 앱은 아닙니다. 앱을 열어 확인하는 장보기 메모입니다. 로컬 DB는 서버 재시작·재배포 시 사라질 수 있으므로 중요한 기록은 CSV로 저장하세요.")


@st.dialog("🧹 목록 관리")
def manage():
    st.caption("삭제는 구매와 다릅니다. 구매 기록이 필요하면 메모의 ‘담기’를 사용하세요.")
    items = rows(list_id)
    if not items:
        st.info("아직 메모가 없습니다.")
        return
    choices = {r["id"]: f"{r['name']} · {'카트' if r['status']=='cart' else '보류' if r['status']=='hold' else '메모'}" for r in items}
    picked = st.selectbox("잘못 입력한 항목", list(choices), format_func=choices.get)
    confirmed = st.checkbox("이 항목을 영구 삭제합니다 (카트 항목이면 총액에서도 제외)")
    if st.button("선택 항목 삭제", disabled=not confirmed, use_container_width=True):
        with connect() as con:
            con.execute("DELETE FROM items WHERE id=? AND list_id=?", (picked, list_id))
        st.rerun()
    import csv
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["상품명", "카테고리", "중요도", "희망단가", "메모", "상태", "수량", "구매단가", "합계"])
    for r in items:
        # 스프레드시트에서 사용자 입력을 수식으로 해석하지 않도록 방지합니다.
        def safe(v):
            return "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v
        writer.writerow([safe(r[k]) for k in ["name", "category", "priority", "target", "note", "status", "quantity", "unit_price", "total"]])
    st.download_button("전체 기록 CSV 저장", buf.getvalue().encode("utf-8-sig"), "shopping.csv", "text/csv", use_container_width=True)


all_items = rows(list_id)
cart = [r for r in all_items if r["status"] == "cart"]
pending = [r for r in all_items if r["status"] != "cart"]
pending.sort(key=lambda r: (r["status"] == "hold", r["priority"], r["created"]))
total = sum(r["total"] or 0 for r in cart)

head, qr, settings = st.columns([6, 1.3, 1.3])
head.markdown("### 🛒 장보기 알림 메모")
if qr.button("QR", use_container_width=True):
    share_list()
if settings.button("⚙️", use_container_width=True):
    manage()

st.metric("현재 카트 총액 · 할인 반영 입력가 기준", f"{total:,}원", help="수량 × 개당 가격의 합계입니다. 실제 결제 시 추가 할인·봉투값 등에 따라 달라질 수 있습니다.")
left, right = st.columns([3, 1])
left.caption(f"남은 메모 {len(pending)}개 · 카트 {len(cart)}개 · 1 필수 / 2 가격 보고 / 3 저렴할 때")
if right.button("＋ 추가", type="primary", use_container_width=True):
    add_item()

st.markdown("**📝 살 것 · 보류**")
with st.container(height=225, border=True):
    if not pending:
        st.caption("살 것을 추가하세요. 담은 상품은 아래 카트로 이동합니다.")
    for item in pending:
        label, buy, hold = st.columns([5, 1.5, 1.5])
        prefix = "⏸ " if item["status"] == "hold" else ""
        label.write(f"{prefix}**{item['name']}**")
        detail = f"{item['category']} · 중요 {item['priority']}"
        if item["target"]:
            detail += f" · ≤{item['target']:,}원/개"
        if item["note"]:
            detail += f" · {item['note']}"
        label.caption(detail)
        if buy.button("담기", key=f"buy_{item['id']}", use_container_width=True):
            buy_item(dict(item))
        if hold.button("복원" if item["status"] == "hold" else "보류", key=f"hold_{item['id']}", use_container_width=True):
            change(item["id"], "todo" if item["status"] == "hold" else "hold")
            st.rerun()

st.markdown(f"**🛒 카트 · {len(cart)}개 품목**")
with st.container(height=115, border=True):
    if not cart:
        st.caption("카트에 담을 때 수량과 가격을 입력하세요.")
    for item in cart:
        label, undo = st.columns([7, 2])
        label.write(f"**{item['name']}** · {item['total']:,}원")
        label.caption(f"{item['quantity']:g} × {item['unit_price']:,}원")
        if undo.button("되돌리기", key=f"undo_{item['id']}", use_container_width=True):
            with connect() as con:
                con.execute("UPDATE items SET status='todo',quantity=NULL,unit_price=NULL,total=NULL,purchased=NULL WHERE id=? AND list_id=?", (item["id"], list_id))
            st.rerun()

st.caption("목록 안쪽만 스크롤 · 공유 목록 새로고침 시 다른 사람의 변경 반영")
