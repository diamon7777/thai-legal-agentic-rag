import os
import re
from pathlib import Path

import pytest
from dotenv import load_dotenv

from thai_legal_rag.main import run_query


@pytest.mark.live
def test_live_pipeline_returns_grounded_banking_answer() -> None:
    load_dotenv()
    if not os.getenv("BBL_LLM_API_KEY"):
        pytest.skip("BBL_LLM_API_KEY is not configured")

    result = run_query(
        "ใครสามารถประกอบธุรกิจธนาคารพาณิชย์ได้",
        knowledge_base_path=Path("knowledge_base.txt"),
    )

    evidence_ids = [chunk["id"] for chunk in result["evidence"]]
    assert "KB-01" in evidence_ids
    assert result["answer"].strip()
    answer_lines = [line for line in result["answer"].splitlines() if line.strip()]
    citations = re.findall(r"\[(KB-\d+)\]", result["answer"])
    assert answer_lines
    assert citations
    assert set(citations) <= set(evidence_ids)
    assert all(re.search(r"\[KB-\d+\]$", line) for line in answer_lines)
