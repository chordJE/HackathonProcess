"""
머신러닝 채점 모듈.
제출 CSV의 predict 컬럼과 정답 파일(case2_answer.csv / case3_answer.csv)의 answer 컬럼을
sklearn accuracy_score로 비교하여 채점합니다.
- save_score.csv: 팀·케이스별 최고점 (스코어보드용)
- score_recent.csv: 최근 10건 (채점 상세 내역용)
- save_db.csv: 모든 제출 기록·점수 (저장용, 스코어보드와 무관)
"""
from pathlib import Path
from typing import Literal
import io
from datetime import datetime

import pandas as pd
from sklearn.metrics import accuracy_score

# 프로젝트 루트 (정답 파일·save_score.csv 위치)
BASE_DIR = Path(__file__).resolve().parent
ANSWER_FILES = {"case2": BASE_DIR / "case2_answer.csv", "case3": BASE_DIR / "case3_answer.csv"}
SAVE_SCORE_PATH = BASE_DIR / "save_score.csv"
RECENT_SCORE_PATH = BASE_DIR / "score_recent.csv"  # 최근 채점 결과 10건 (채점 상세 내역용)
SAVE_DB_PATH = BASE_DIR / "save_db.csv"  # 모든 제출 기록·점수 저장용 (스코어보드와 무관)
MAX_RECENT = 10


def run_scoring(
    uploaded_file: bytes,
    case: Literal["case2", "case3"],
    team_id: int,
) -> dict:
    """
    업로드된 CSV(predict 컬럼)와 해당 케이스 정답 파일(answer 컬럼)을 비교해
    accuracy_score로 채점하고, save_score.csv에 저장합니다.

    Args:
        uploaded_file: 업로드된 CSV 파일 바이트
        case: "case2" 또는 "case3"
        team_id: 팀 번호 (1~8)

    Returns:
        {"score": float (0~100), "details": str, "status": "ok"|"error"}
    """
    try:
        # 제출 파일 로드
        submit_df = pd.read_csv(io.BytesIO(uploaded_file))
        if "predict" not in submit_df.columns:
            return {
                "score": 0.0,
                "details": "제출 파일에 'predict' 컬럼이 없습니다.",
                "status": "error",
            }

        predict = submit_df["predict"].astype(int).values

        # 정답 파일 로드
        answer_path = ANSWER_FILES[case]
        if not answer_path.exists():
            return {
                "score": 0.0,
                "details": f"정답 파일이 없습니다: {answer_path.name}",
                "status": "error",
            }

        answer_df = pd.read_csv(answer_path)
        if "answer" not in answer_df.columns:
            return {
                "score": 0.0,
                "details": f"정답 파일에 'answer' 컬럼이 없습니다: {answer_path.name}",
                "status": "error",
            }

        answer = answer_df["answer"].astype(int).values

        # 길이 맞추기 (짧은 쪽에 맞춤)
        min_len = min(len(predict), len(answer))
        if min_len == 0:
            return {
                "score": 0.0,
                "details": "예측 또는 정답 데이터가 비어 있습니다.",
                "status": "error",
            }
        predict = predict[:min_len]
        answer = answer[:min_len]

        # accuracy_score (0~1)
        acc = accuracy_score(answer, predict)
        score_100 = round(acc * 100.0, 2)
        submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # save_score.csv: 해당 팀·케이스의 최고점만 갱신
        _save_score(team_id=team_id, case=case, score=score_100, submitted_at=submitted_at)
        # 최근 채점 결과 10건 로그 (채점 상세 내역용)
        _append_recent(team_id=team_id, case=case, score=score_100, submitted_at=submitted_at)
        # save_db.csv: 모든 제출 기록·점수 저장 (스코어보드와 무관)
        _append_save_db(team_id=team_id, case=case, score=score_100, submitted_at=submitted_at)

        return {
            "score": score_100,
            "details": f"Case: {case}, Team {team_id}, accuracy(0~100): {score_100}, 제출시각: {submitted_at}",
            "status": "ok",
        }
    except Exception as e:
        return {
            "score": 0.0,
            "details": str(e),
            "status": "error",
        }


def _parse_score_from_cell(cell) -> float:
    """셀 값 "85.5(2025-02-03 14:30:00)" 에서 점수만 추출. 없으면 -1."""
    if pd.isna(cell) or str(cell).strip() == "":
        return -1.0
    s = str(cell).strip()
    score_str = s.split("(")[0].strip() if "(" in s else s
    try:
        return float(score_str)
    except ValueError:
        return -1.0


def _save_score(team_id: int, case: str, score: float, submitted_at: str) -> None:
    """
    save_score.csv에 팀별·케이스별 '최고점'만 갱신합니다.
    새 점수가 기존 점수보다 클 때만 저장합니다.
    """
    value = f"{score}({submitted_at})"
    cols = ["team", "case2", "case3"]

    if SAVE_SCORE_PATH.exists():
        df = pd.read_csv(SAVE_SCORE_PATH)
        if not all(c in df.columns for c in cols):
            df = pd.DataFrame(columns=cols)
    else:
        df = pd.DataFrame(columns=cols)

    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df = df[cols]
    team_label = f"{team_id}팀"
    mask = df["team"].astype(str).str.strip() == team_label

    if mask.any():
        idx = df.loc[mask].index[0]
        current_score = _parse_score_from_cell(df.at[idx, case])
        if score > current_score:
            df.at[idx, case] = value
    else:
        new_row = {"team": team_label, "case2": "", "case3": ""}
        new_row[case] = value
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    df[cols].to_csv(SAVE_SCORE_PATH, index=False)


def _append_recent(team_id: int, case: str, score: float, submitted_at: str) -> None:
    """최근 채점 결과를 score_recent.csv에 추가하고, 최대 10건만 유지합니다."""
    cols = ["team", "case", "score", "submitted_at"]
    new_row = pd.DataFrame([{"team": f"{team_id}팀", "case": case, "score": score, "submitted_at": submitted_at}])

    if RECENT_SCORE_PATH.exists():
        try:
            df = pd.read_csv(RECENT_SCORE_PATH)
            if not all(c in df.columns for c in cols):
                df = pd.DataFrame(columns=cols)
        except Exception:
            df = pd.DataFrame(columns=cols)
    else:
        df = pd.DataFrame(columns=cols)

    df = pd.concat([df, new_row], ignore_index=True)
    df = df.tail(MAX_RECENT)
    df[cols].to_csv(RECENT_SCORE_PATH, index=False)


def _append_save_db(team_id: int, case: str, score: float, submitted_at: str) -> None:
    """모든 제출 기록·점수를 save_db.csv에 추가합니다. 스코어보드와 연동되지 않는 저장용."""
    cols = ["team", "case", "score", "submitted_at"]
    new_row = pd.DataFrame([{"team": f"{team_id}팀", "case": case, "score": score, "submitted_at": submitted_at}])

    if SAVE_DB_PATH.exists():
        try:
            df = pd.read_csv(SAVE_DB_PATH)
            if not all(c in df.columns for c in cols):
                df = pd.DataFrame(columns=cols)
        except Exception:
            df = pd.DataFrame(columns=cols)
    else:
        df = pd.DataFrame(columns=cols)

    df = pd.concat([df, new_row], ignore_index=True)
    df[cols].to_csv(SAVE_DB_PATH, index=False)


def load_scoreboard() -> dict:
    """
    save_score.csv를 읽어서 scoreboard 형태로 반환합니다.
    (각 팀·케이스별 최고점만 저장되어 있음)
    Returns: {(team_id, case): {"score": float, "details": str}}
    """
    board = {}
    if not SAVE_SCORE_PATH.exists():
        return board

    try:
        df = pd.read_csv(SAVE_SCORE_PATH)
        if "team" not in df.columns:
            return board

        for _, row in df.iterrows():
            team_str = str(row.get("team", "")).strip()
            if not team_str or not team_str.endswith("팀"):
                continue
            team_id = int(team_str.replace("팀", ""))

            for case in ("case2", "case3"):
                cell = row.get(case, "")
                if pd.isna(cell) or str(cell).strip() == "":
                    continue
                s = str(cell).strip()
                score = _parse_score_from_cell(cell)
                if score < 0:
                    continue
                board[(team_id, case)] = {
                    "score": score,
                    "details": f"최고점 기록: {s}",
                }
    except Exception:
        pass
    return board


def load_recent_submissions(limit: int = MAX_RECENT) -> list:
    """
    최근 채점 결과를 최대 limit건 반환합니다 (최신순).
    Returns: [{"team": "1팀", "case": "case2", "score": 85.5, "submitted_at": "..."}, ...]
    """
    if not RECENT_SCORE_PATH.exists():
        return []
    try:
        df = pd.read_csv(RECENT_SCORE_PATH)
        cols = ["team", "case", "score", "submitted_at"]
        if not all(c in df.columns for c in cols):
            return []
        df = df[cols].dropna(how="all")
        # 최신순 (마지막 행이 최신)
        df = df.tail(limit).iloc[::-1].reset_index(drop=True)
        return df.to_dict("records")
    except Exception:
        return []
