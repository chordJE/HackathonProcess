"""
머신러닝 채점 모듈.
제출 CSV의 predict 컬럼과 정답 파일(case2_answer.csv / case3_answer.csv)의 answer 컬럼을
sklearn accuracy_score로 비교하여 채점하고, 결과를 save_score.csv에 저장합니다.
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

        # save_score.csv 갱신
        _save_score(team_id=team_id, case=case, score=score_100, submitted_at=submitted_at)

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


def _save_score(team_id: int, case: str, score: float, submitted_at: str) -> None:
    """
    save_score.csv에 팀별로 해당 case 컬럼만 갱신합니다.
    - case2 제출 → case2 컬럼에만 저장
    - case3 제출 → case3 컬럼에만 저장
    컬럼: team, case2, case3 (각 셀은 "점수(제출시각)" 형식).
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
        df.at[idx, case] = value  # 선택한 case 컬럼에만 기록
    else:
        new_row = {"team": team_label, "case2": "", "case3": ""}
        new_row[case] = value
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    df[cols].to_csv(SAVE_SCORE_PATH, index=False)


def load_scoreboard() -> dict:
    """
    save_score.csv를 읽어서 scoreboard 형태로 반환합니다.
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
                # "85.5(2025-02-03 14:30:00)" 형태에서 점수만 추출
                s = str(cell).strip()
                if "(" in s:
                    score_str = s.split("(")[0].strip()
                else:
                    score_str = s
                try:
                    score = float(score_str)
                except ValueError:
                    continue
                board[(team_id, case)] = {
                    "score": score,
                    "details": f"제출 기록: {s}",
                }
    except Exception:
        pass
    return board
