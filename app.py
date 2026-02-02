"""
Streamlit 앱: ScoreBoard(전면) + Summit Check(사이드).
제출 시 자동 ML 채점 수행.
"""
from pathlib import Path

import streamlit as st
from scoring import run_scoring, load_scoreboard, load_recent_submissions

# save_db.csv 경로 (다운로드용)
SAVE_DB_PATH = Path(__file__).resolve().parent / "save_db.csv"
DB_DOWNLOAD_PASSWORD = "7496"

# 페이지 설정
st.set_page_config(
    page_title="ML ScoreBoard & Summit Check",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 스코어보드는 항상 save_score.csv 기준으로 표시 (case2 / case3 컬럼 분리 반영)
st.session_state.scoreboard = load_scoreboard()


# ========== 사이드바: Summit Check ==========
with st.sidebar:
    st.header("Summit Check")

    # case 선택 라디오 버튼 2개 (case2, case3)
    case = st.radio(
        "Case 선택",
        options=["case2", "case3"],
        index=0,
        horizontal=True,
    )

    st.divider()

    # 팀 선택용 버튼 8개 (1팀 ~ 8팀)
    team_label = st.radio(
        "팀 선택",
        options=[f"{i}팀" for i in range(1, 10)],
        index=0,
    )
    team_id = int(team_label.replace("팀", ""))

    st.divider()

    # 파일 업로드 (.csv만 허용)
    uploaded_file = st.file_uploader(
        "제출 파일 업로드 (.csv)",
        type=["csv"],
    )

    st.divider()

    # Submit 버튼
    submit_clicked = st.button("Submit", type="primary", use_container_width=True)

    if submit_clicked:
        if uploaded_file is None:
            st.error("파일을 업로드한 뒤 Submit 해주세요.")
        else:
            with st.spinner("채점 중..."):
                result = run_scoring(
                    uploaded_file.read(),
                    case=case,
                    team_id=team_id,
                )
            # run_scoring이 save_score.csv의 해당 case 컬럼에만 저장함 → rerun 시 load_scoreboard()로 반영
            if result.get("status") == "ok":
                st.success(f"채점 완료! 점수: {result['score']} (save_score.csv에 저장됨)")
            else:
                st.error(f"채점 오류: {result.get('details', '')}")
            st.rerun()


# ========== 전면: ScoreBoard (카드 형태, 케이스별 분리) ==========
st.title("ScoreBoard")

# 카드 스타일 CSS
st.markdown("""
<style>
div.score-card {
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    border: 1px solid #dee2e6;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
div.score-card .team-name { font-weight: 700; font-size: 1.1rem; color: #212529; }
div.score-card .case-name { font-size: 0.85rem; color: #6c757d; margin-top: 0.2rem; }
div.score-card .score-val { font-size: 1.5rem; font-weight: 800; color: #0d6efd; margin-top: 0.35rem; }
</style>
""", unsafe_allow_html=True)


def render_score_cards(case_key: str):
    """해당 케이스의 (팀, 점수) 목록을 점수 내림차순으로 카드 렌더링."""
    items = [
        (team_id, data["score"])
        for (team_id, c), data in st.session_state.scoreboard.items()
        if c == case_key
    ]
    items.sort(key=lambda x: x[1], reverse=True)

    if not items:
        st.caption(f"아직 {case_key} 제출 결과가 없습니다.")
        return

    for rank, (team_id, score) in enumerate(items, start=1):
        card = f"""
        <div class="score-card">
            <div class="team-name">{team_id}팀</div>
            <div class="case-name">{case_key}</div>
            <div class="score-val">{score:.1f}점</div>
        </div>
        """
        st.markdown(card, unsafe_allow_html=True)


# Case2 / Case3 스코어보드 나누어 표시
col2, col3 = st.columns(2)

with col2:
    st.subheader("Case2")
    render_score_cards("case2")

with col3:
    st.subheader("Case3")
    render_score_cards("case3")

# 채점 상세 내역: 최근 업데이트된 채점 결과 10건만 표시
with st.expander("채점 상세 내역"):
    recent = load_recent_submissions(limit=10)
    if recent:
        for r in recent:
            st.markdown(f"**{r['team']} · {r['case']}** — {r['score']}점 ({r['submitted_at']})")
    else:
        st.caption("최근 채점 내역 없음.")

# 스코어보드 맨 아래: 비밀번호 입력 시 save_db.csv 다운로드
st.divider()
pw = st.text_input("비밀번호", type="password", key="db_download_pw", placeholder="비밀번호 입력")
if pw == DB_DOWNLOAD_PASSWORD:
    if SAVE_DB_PATH.exists():
        db_content = SAVE_DB_PATH.read_text(encoding="utf-8")
        st.download_button(
            "save_db.csv 다운로드",
            data=db_content,
            file_name="save_db.csv",
            mime="text/csv",
            key="download_save_db",
        )
    else:
        st.caption("save_db.csv 파일이 아직 없습니다.")
elif pw and pw != DB_DOWNLOAD_PASSWORD:
    st.caption("비밀번호가 일치하지 않습니다.")
