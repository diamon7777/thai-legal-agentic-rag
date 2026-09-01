import json
import re
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from thai_legal_rag.llm import BBLClient
from thai_legal_rag.retrieval import EvidenceChunk, load_knowledge_base, search_knowledge_base

_CITATION = re.compile(r"\[KB-\d+\]")


class RAGState(TypedDict):
    question: str
    subqueries: list[str]
    evidence: list[EvidenceChunk]
    answer: str


def build_graph(client: BBLClient, knowledge_base_path: Path):
    chunks = load_knowledge_base(knowledge_base_path)

    def data_retriever(state: RAGState) -> dict[str, object]:
        subqueries = _plan_subqueries(client, state["question"])
        evidence_by_id: dict[str, EvidenceChunk] = {}
        for subquery in subqueries:
            for chunk in search_knowledge_base(subquery, chunks):
                current = evidence_by_id.get(chunk["id"])
                if current is None or chunk["score"] > current["score"]:
                    evidence_by_id[chunk["id"]] = chunk
        evidence = sorted(evidence_by_id.values(), key=lambda chunk: (-chunk["score"], chunk["id"]))
        return {"subqueries": subqueries, "evidence": evidence}

    def report_generator(state: RAGState) -> dict[str, str]:
        if not state["evidence"]:
            return {
                "answer": (
                    "ไม่พบหลักฐานเพียงพอใน knowledge_base.txt สำหรับคำถามนี้ "
                    "ระบบจึงไม่สร้างข้อสรุปจากข้อมูลภายนอก"
                )
            }
        return {"answer": _write_report(client, state["question"], state["evidence"])}

    graph = StateGraph(RAGState)
    graph.add_node("data_retriever", data_retriever)
    graph.add_node("report_generator", report_generator)
    graph.add_edge(START, "data_retriever")
    graph.add_edge("data_retriever", "report_generator")
    graph.add_edge("report_generator", END)
    return graph.compile()


def _plan_subqueries(client: BBLClient, question: str) -> list[str]:
    response = client.complete(
        [
            {
                "role": "system",
                "content": (
                    "You are the Data Retriever Agent. Return strict JSON only in the form "
                    '{"subqueries":["keyword phrase"]}. Create one to three short Thai legal '
                    "search phrases. Use terms likely to appear in legal text. Do not answer the question."
                ),
            },
            {"role": "user", "content": question},
        ],
        max_output_tokens=180,
    )
    try:
        payload = json.loads(response)
        subqueries = payload["subqueries"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise RuntimeError("Retriever agent did not return the required JSON") from error

    if not isinstance(subqueries, list) or not 1 <= len(subqueries) <= 3:
        raise RuntimeError("Retriever agent must return one to three subqueries")
    if not all(isinstance(query, str) and query.strip() for query in subqueries):
        raise RuntimeError("Retriever agent returned an empty subquery")
    clean_subqueries = list(dict.fromkeys(query.strip() for query in subqueries))
    if len(clean_subqueries) != len(subqueries):
        raise RuntimeError("Retriever agent returned duplicate subqueries")
    return clean_subqueries


def _write_report(client: BBLClient, question: str, evidence: list[EvidenceChunk]) -> str:
    sources = "\n\n".join(
        f"[{chunk['id']}] มาตรา {chunk['section']}\n{chunk['text']}" for chunk in evidence
    )
    allowed_ids = {chunk["id"] for chunk in evidence}
    allowed_citations = ", ".join(f"[{chunk['id']}]" for chunk in evidence)
    response = client.complete(
        [
            {
                "role": "system",
                "content": (
                    "You are the Report Generator Agent. Return strict JSON only in the form "
                    '{"statements":[{"text":"Thai legal statement","citation_ids":["KB-01"]}]}. '
                    "Return one to three concise Thai statements using only the supplied legal excerpts. "
                    f"The only permitted citation IDs are: {allowed_citations}. Do not use any other ID, "
                    "do not infer beyond the excerpts, and do not give legal advice."
                ),
            },
            {"role": "user", "content": f"Question: {question}\n\nEvidence:\n{sources}"},
        ],
        max_output_tokens=400,
    )
    try:
        statements = json.loads(response)["statements"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise RuntimeError("Report generator did not return the required JSON") from error

    if not isinstance(statements, list) or not 1 <= len(statements) <= 3:
        raise RuntimeError("Report generator must return one to three statements")

    lines: list[str] = []
    for statement in statements:
        if not isinstance(statement, dict):
            raise RuntimeError("Report generator returned an invalid statement")
        text = statement.get("text")
        citation_ids = statement.get("citation_ids")
        if (
            not isinstance(text, str)
            or not text.strip()
            or "\n" in text
            or _CITATION.search(text)
        ):
            raise RuntimeError("Report generator returned an invalid statement text")
        if (
            not isinstance(citation_ids, list)
            or not citation_ids
            or not all(isinstance(citation_id, str) for citation_id in citation_ids)
            or len(set(citation_ids)) != len(citation_ids)
        ):
            raise RuntimeError("Report generator returned invalid citations")
        unknown_ids = set(citation_ids) - allowed_ids
        if unknown_ids:
            raise RuntimeError(f"Report generator cited unknown evidence: {sorted(unknown_ids)}")
        citations = " ".join(f"[{citation_id}]" for citation_id in citation_ids)
        lines.append(f"- {text.strip()} {citations}")
    return "\n".join(lines)
