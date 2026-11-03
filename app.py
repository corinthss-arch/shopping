"""쇼핑 리스트 앱 (Streamlit).

PRD.md 기준 2단계: 주요 기능 (4.1 ~ 4.8).
실행: streamlit run app.py
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
DATA_FILE = Path(__file__).parent / "shopping_list.json"
MAX_NAME_LENGTH = 50
MIN_QTY = 1
MAX_QTY = 99

MSG_EMPTY = "아이템 이름을 입력해 주세요."
MSG_TOO_LONG = f"아이템 이름은 {MAX_NAME_LENGTH}자 이하로 입력해 주세요."
MSG_DUPLICATE = "이미 리스트에 있는 아이템입니다."
MSG_BAD_QTY = f"수량은 {MIN_QTY}~{MAX_QTY} 사이로 입력해 주세요."
MSG_EMPTY_LIST = "쇼핑 리스트가 비어 있어요. 위에서 아이템을 추가해 보세요!"


# ---------------------------------------------------------------------------
# 데이터 모델 (PRD 5.1)
# ---------------------------------------------------------------------------
def new_item(name: str, quantity: int = 1) -> dict:
    """새 아이템 dict를 만든다."""
    return {
        "id": uuid.uuid4().hex[:8],
        "name": name,
        "quantity": quantity,
        "checked": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def _is_valid_item(raw: object) -> bool:
    """파일에서 읽은 값이 올바른 아이템 구조인지 확인한다."""
    return (
        isinstance(raw, dict)
        and isinstance(raw.get("id"), str)
        and isinstance(raw.get("name"), str)
        and isinstance(raw.get("checked"), bool)
    )


def _normalize(name: str) -> str:
    """중복 비교용: 공백 정리 + 대소문자 무시."""
    return " ".join(name.split()).casefold()


# ---------------------------------------------------------------------------
# 저장소 (PRD 4.5)
# ---------------------------------------------------------------------------
def load_items() -> list[dict]:
    """shopping_list.json에서 아이템 목록을 불러온다.

    파일이 없으면 빈 리스트. 손상되었으면 빈 리스트 + 경고 플래그를 남긴다.
    """
    if not DATA_FILE.exists():
        return []
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        raw_items = data["items"]
        if not isinstance(raw_items, list):
            raise ValueError("items is not a list")
    except (OSError, ValueError, KeyError, TypeError):
        st.session_state.load_warning = (
            "저장된 쇼핑 리스트 파일을 읽을 수 없어 빈 리스트로 시작합니다."
        )
        return []

    items = []
    for raw in raw_items:
        if not _is_valid_item(raw):
            continue
        qty = raw.get("quantity", 1)
        items.append(
            {
                "id": raw["id"],
                "name": raw["name"],
                "quantity": qty if isinstance(qty, int) and MIN_QTY <= qty <= MAX_QTY else 1,
                "checked": raw["checked"],
                "created_at": str(raw.get("created_at", "")),
            }
        )
    return items


def save_items(items: list[dict]) -> None:
    """아이템 목록을 shopping_list.json에 저장한다."""
    try:
        DATA_FILE.write_text(
            json.dumps({"items": items}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        st.session_state.flash = ("error", "파일 저장에 실패했습니다.")


def _items() -> list[dict]:
    return st.session_state["items"]


def _find(item_id: str) -> dict | None:
    return next((it for it in _items() if it["id"] == item_id), None)


# ---------------------------------------------------------------------------
# 비즈니스 로직 (PRD 4.1 ~ 4.4, 4.7)
# ---------------------------------------------------------------------------
def validate_name(name: str, exclude_id: str | None = None) -> str | None:
    """이름을 검증해 에러 메시지를 반환한다. 정상이면 None."""
    name = name.strip()
    if not name:
        return MSG_EMPTY
    if len(name) > MAX_NAME_LENGTH:
        return MSG_TOO_LONG
    key = _normalize(name)
    for it in _items():
        if it["id"] != exclude_id and _normalize(it["name"]) == key:
            return MSG_DUPLICATE
    return None


def _valid_qty(quantity: object) -> bool:
    return isinstance(quantity, int) and MIN_QTY <= quantity <= MAX_QTY


def add_item(name: str, quantity: int = 1) -> tuple[bool, str]:
    """아이템을 추가한다. (성공 여부, 메시지)를 반환한다."""
    error = validate_name(name)
    if error:
        return False, error
    if not _valid_qty(quantity):
        return False, MSG_BAD_QTY
    _items().append(new_item(name.strip(), quantity))
    save_items(_items())
    return True, f"'{name.strip()}' 추가됨"


def update_item(item_id: str, name: str, quantity: int) -> tuple[bool, str]:
    """아이템 이름·수량을 수정한다. (성공 여부, 메시지)를 반환한다."""
    item = _find(item_id)
    if item is None:
        return False, "아이템을 찾을 수 없습니다."
    error = validate_name(name, exclude_id=item_id)
    if error:
        return False, error
    if not _valid_qty(quantity):
        return False, MSG_BAD_QTY
    item["name"] = name.strip()
    item["quantity"] = quantity
    save_items(_items())
    return True, f"'{item['name']}' 수정됨"


def delete_item(item_id: str) -> None:
    """아이템을 삭제한다."""
    item = _find(item_id)
    if item is None:
        return
    st.session_state["items"] = [it for it in _items() if it["id"] != item_id]
    if st.session_state.editing_id == item_id:
        st.session_state.editing_id = None
    save_items(_items())
    st.session_state.toast = f"'{item['name']}' 삭제됨"


def toggle_item(item_id: str) -> None:
    """아이템의 체크 상태를 반전한다."""
    item = _find(item_id)
    if item is None:
        return
    item["checked"] = not item["checked"]
    save_items(_items())


def clear_checked() -> None:
    """체크된 아이템을 모두 삭제한다."""
    removed = [it for it in _items() if it["checked"]]
    if not removed:
        return
    st.session_state["items"] = [it for it in _items() if not it["checked"]]
    if st.session_state.editing_id in {it["id"] for it in removed}:
        st.session_state.editing_id = None
    save_items(_items())
    st.session_state.toast = f"완료 항목 {len(removed)}개 삭제됨"


def sorted_items() -> list[dict]:
    """미체크 먼저, 체크 나중. 각 그룹 안에서는 추가 순서."""
    indexed = list(enumerate(_items()))
    indexed.sort(key=lambda p: (p[1]["checked"], p[1]["created_at"], p[0]))
    return [it for _, it in indexed]


# ---------------------------------------------------------------------------
# 위젯 콜백
# ---------------------------------------------------------------------------
def on_add() -> None:
    ok, msg = add_item(st.session_state.new_name, st.session_state.new_qty)
    if ok:
        # 성공했을 때만 입력값 초기화 (실패 시 사용자가 고칠 수 있게 유지)
        st.session_state.new_name = ""
        st.session_state.new_qty = 1
    else:
        st.session_state.flash = ("warning", msg)


def on_start_edit(item_id: str) -> None:
    # 이전 편집 위젯의 잔여 상태 제거 → 항상 현재 값으로 채워짐
    for key in (f"edit_name_{item_id}", f"edit_qty_{item_id}"):
        st.session_state.pop(key, None)
    st.session_state.editing_id = item_id


def on_save_edit(item_id: str) -> None:
    ok, msg = update_item(
        item_id,
        st.session_state[f"edit_name_{item_id}"],
        st.session_state[f"edit_qty_{item_id}"],
    )
    if ok:
        st.session_state.editing_id = None
    else:
        st.session_state.flash = ("warning", msg)


def on_cancel_edit() -> None:
    st.session_state.editing_id = None


# ---------------------------------------------------------------------------
# 상태 초기화
# ---------------------------------------------------------------------------
def init_state() -> None:
    """session_state를 초기화한다. 최초 1회만 파일에서 불러온다."""
    if "items" not in st.session_state:
        st.session_state["items"] = load_items()
    st.session_state.setdefault("editing_id", None)
    st.session_state.setdefault("new_name", "")
    st.session_state.setdefault("new_qty", 1)
    st.session_state.setdefault("flash", None)
    st.session_state.setdefault("toast", None)


def show_messages() -> None:
    """콜백에서 남긴 메시지를 한 번만 표시한다."""
    warning = st.session_state.pop("load_warning", None)
    if warning:
        st.warning(warning)
    if st.session_state.toast:
        st.toast(st.session_state.toast)
        st.session_state.toast = None


def show_flash() -> None:
    flash = st.session_state.flash
    if flash:
        level, msg = flash
        getattr(st, level)(msg)
        st.session_state.flash = None


# ---------------------------------------------------------------------------
# 화면 영역 (PRD 6장)
# ---------------------------------------------------------------------------
_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|~<>:$])")


def escape_md(text: str) -> str:
    """사용자 입력이 마크다운/HTML로 해석되지 않도록 이스케이프한다."""
    return _MD_SPECIAL.sub(r"\\\1", text)


def display_name(item: dict) -> str:
    label = escape_md(item["name"])
    if item["quantity"] > 1:
        label += f" ×{item['quantity']}"
    return label

ACCENT = "#3E9A72"  # 글자용 포인트 컬러: 라이트/다크 배경 모두에서 읽히는 중간 톤
WEEKDAYS = "월화수목금토일"

CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');

/* 폰트: 아이콘 폰트는 건드리지 않는다 */
.stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp label,
.stApp input, .stApp button, .stApp [data-testid="stMetricValue"] {
    font-family: 'Pretendard', 'Noto Sans KR', -apple-system, sans-serif;
}

/* 헤더 */
.stApp h1 { font-weight: 800; letter-spacing: -0.02em; padding-bottom: 0; }
.app-sub { margin: -0.4rem 0 1.2rem; font-size: 0.95rem; }
.app-sub b { color: __ACCENT__; font-weight: 700; }
.app-sub span { opacity: 0.65; }

/* 그룹 소제목 */
.group-title {
    margin: 1.2rem 0 0.4rem; font-size: 0.85rem; font-weight: 700;
    letter-spacing: 0.02em; opacity: 0.6;
}

/* 아이템 카드 */
[class*="st-key-row_"] {
    border: 1px solid rgba(128, 128, 128, 0.22);
    border-radius: 12px;
    padding: 0.35rem 0.6rem 0.35rem 0.9rem;
    transition: background-color 0.15s ease, border-color 0.15s ease;
}
[class*="st-key-row_"]:hover {
    background-color: rgba(46, 125, 91, 0.07);
    border-color: rgba(46, 125, 91, 0.45);
}
[class*="st-key-row_done_"] { opacity: 0.72; }
[class*="st-key-row_"] p { margin: 0; font-size: 1.02rem; overflow-wrap: anywhere; }
/* Streamlit 기본 마크다운 하단 음수 여백 제거 → 체크박스와 글자 높이 맞춤 */
[class*="st-key-row_"] [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }

/* 카드 안 아이콘 버튼: 테두리 없이 작게 */
[class*="st-key-row_"] [data-testid="stBaseButton-secondary"] {
    border: none; background: transparent; padding: 0.2rem 0.4rem; min-height: 2rem;
}
[class*="st-key-row_"] [data-testid="stBaseButton-secondary"]:hover {
    background: rgba(128, 128, 128, 0.15);
}
/* 좁은 화면에서 '저장'/'취소'가 두 줄로 꺾이지 않게 */
[class*="st-key-row_"] button { padding-left: 0.5rem; padding-right: 0.5rem; }
[class*="st-key-row_"] button p { white-space: nowrap; }

/* 모바일에서도 한 줄 유지 (Streamlit 기본은 좁은 화면에서 컬럼을 세로로 쌓음) */
[class*="st-key-row_"] [data-testid="stHorizontalBlock"],
.st-key-add_row [data-testid="stHorizontalBlock"],
.st-key-summary [data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: 0.5rem;
}
[class*="st-key-row_"] [data-testid="stColumn"],
.st-key-add_row [data-testid="stColumn"],
.st-key-summary [data-testid="stColumn"] {
    min-width: 0 !important;
}
.st-key-summary [data-testid="stMetricLabel"] p { font-size: 0.8rem; white-space: nowrap; }

/* 진행률 텍스트 */
.progress-text {
    display: flex; justify-content: space-between;
    font-size: 0.85rem; margin-top: 0.2rem; opacity: 0.8;
}
.progress-done { color: __ACCENT__; font-weight: 700; }

/* 빈 상태 */
.empty-state { text-align: center; padding: 2.5rem 1rem; opacity: 0.75; }
.empty-state .emoji { font-size: 3.5rem; line-height: 1; }
.empty-state p { margin-top: 0.8rem; }
</style>
""".replace("__ACCENT__", ACCENT)


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def render_header() -> None:
    today = datetime.now()
    date_str = f"{today.month}월 {today.day}일 ({WEEKDAYS[today.weekday()]})"
    st.title("🛒 쇼핑 리스트")
    st.markdown(
        f'<p class="app-sub"><b>{date_str}</b><span> · 오늘 살 것들을 정리해 보세요</span></p>',
        unsafe_allow_html=True,
    )


def render_input_form() -> None:
    """아이템 이름·수량 입력 폼과 [추가] 버튼."""
    with st.form("add_form", border=False), st.container(key="add_row"):
        col_name, col_qty, col_btn = st.columns([0.6, 0.22, 0.18], vertical_alignment="bottom")
        col_name.text_input(
            "아이템 이름",
            key="new_name",
            placeholder="살 물건을 입력하세요",
            max_chars=MAX_NAME_LENGTH,
        )
        col_qty.number_input(
            "수량", key="new_qty", min_value=MIN_QTY, max_value=MAX_QTY, step=1
        )
        col_btn.form_submit_button("추가", on_click=on_add, type="primary", width="stretch")
    show_flash()


def render_summary() -> None:
    """전체/남은/완료 개수 metric과 진행률 바."""
    items = _items()
    total = len(items)
    done = sum(it["checked"] for it in items)
    ratio = done / total if total else 0.0

    with st.container(border=True, key="summary"):
        c1, c2, c3 = st.columns(3)
        c1.metric("전체", total)
        c2.metric("남은 아이템", total - done)
        c3.metric("구매 완료", done)
        st.progress(ratio)
        if total and done == total:
            right = '<span class="progress-done">🎉 장보기 완료!</span>'
        else:
            right = f"<span>{done} / {total}</span>"
        st.markdown(
            f'<div class="progress-text"><span>{ratio:.0%} 완료</span>{right}</div>',
            unsafe_allow_html=True,
        )


def render_item_row(item: dict) -> None:
    item_id = item["id"]
    state = "done" if item["checked"] else "todo"

    with st.container(key=f"row_{state}_{item_id}"):
        if st.session_state.editing_id == item_id:
            c_name, c_qty, c_save, c_cancel = st.columns(
                [0.42, 0.22, 0.18, 0.18], vertical_alignment="center"
            )
            c_name.text_input(
                "이름 수정",
                value=item["name"],
                key=f"edit_name_{item_id}",
                max_chars=MAX_NAME_LENGTH,
                label_visibility="collapsed",
            )
            c_qty.number_input(
                "수량 수정",
                value=item["quantity"],
                min_value=MIN_QTY,
                max_value=MAX_QTY,
                step=1,
                key=f"edit_qty_{item_id}",
                label_visibility="collapsed",
            )
            c_save.button("저장", key=f"save_{item_id}", on_click=on_save_edit,
                          args=(item_id,), type="primary", width="stretch")
            c_cancel.button("취소", key=f"cancel_{item_id}", on_click=on_cancel_edit,
                            width="stretch")
            return

        c_chk, c_name, c_edit, c_del = st.columns(
            [0.08, 0.72, 0.1, 0.1], vertical_alignment="center"
        )
        c_chk.checkbox(
            item["name"],
            value=item["checked"],
            key=f"chk_{item_id}",
            on_change=toggle_item,
            args=(item_id,),
            label_visibility="collapsed",
        )
        label = display_name(item)
        c_name.markdown(f":gray[~~{label}~~]" if item["checked"] else label)
        c_edit.button("✏️", key=f"edit_{item_id}", on_click=on_start_edit,
                      args=(item_id,), help="수정")
        c_del.button("🗑️", key=f"del_{item_id}", on_click=delete_item,
                     args=(item_id,), help="삭제")


def render_item_list() -> None:
    """아이템 목록: '살 것' 그룹과 '담은 것' 그룹."""
    items = sorted_items()
    if not items:
        st.markdown(
            '<div class="empty-state"><div class="emoji">🧺</div>'
            f"<p>{MSG_EMPTY_LIST}</p></div>",
            unsafe_allow_html=True,
        )
        return

    todo = [it for it in items if not it["checked"]]
    done = [it for it in items if it["checked"]]
    for title, group in (("살 것", todo), ("담은 것", done)):
        if not group:
            continue
        st.markdown(f'<div class="group-title">{title} {len(group)}개</div>',
                    unsafe_allow_html=True)
        for item in group:
            render_item_row(item)


def render_footer() -> None:
    """[완료 항목 모두 삭제] 버튼 — 체크된 아이템이 있을 때만."""
    if any(it["checked"] for it in _items()):
        st.write("")
        st.button("🧹 완료 항목 모두 삭제", key="clear_checked", on_click=clear_checked,
                  width="stretch")


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")
    init_state()
    inject_css()

    render_header()
    show_messages()

    render_input_form()
    render_summary()
    render_item_list()
    render_footer()


main()
