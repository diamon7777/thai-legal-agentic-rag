import re
from pathlib import Path
from typing import TypedDict


class EvidenceChunk(TypedDict):
    id: str
    section: str
    text: str
    score: int


_HEADER = re.compile(r"^## (?P<id>KB-\d+) \| มาตรา (?P<section>\d+)$")
_TOKEN = re.compile(r"[\u0E00-\u0E7Fa-zA-Z0-9]+")
_STOP_WORDS = frozenset({"การ", "และ", "หรือ", "ของ", "ใน", "ที่", "ให้", "มี", "เป็น", "ได้", "ไม่", "ตาม"})
_THAI_PHRASE_LENGTH = 14


def load_knowledge_base(path: Path) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []
    for block in path.read_text(encoding="utf-8").strip().split("\n\n---\n\n"):
        header, _, text = block.partition("\n")
        match = _HEADER.fullmatch(header.strip())
        if not match or not text.strip():
            raise ValueError(f"Invalid knowledge-base chunk: {header!r}")
        chunks.append(
            {
                "id": match["id"],
                "section": match["section"],
                "text": text.strip(),
                "score": 0,
            }
        )
    return chunks


def search_knowledge_base(query: str, chunks: list[EvidenceChunk], limit: int = 3) -> list[EvidenceChunk]:
    terms = _search_terms(query)
    haystacks = {chunk["id"]: _normalise(chunk["text"]).replace(" ", "") for chunk in chunks}
    scores = {chunk["id"]: 0 for chunk in chunks}
    for term in terms:
        needle = term.replace(" ", "")
        matching_ids = [chunk_id for chunk_id, haystack in haystacks.items() if needle in haystack]
        is_ambiguous_keyword = " " not in term and len(needle) < _THAI_PHRASE_LENGTH
        if len(matching_ids) == len(chunks) or (is_ambiguous_keyword and len(matching_ids) > 1):
            continue
        for chunk_id in matching_ids:
            scores[chunk_id] += 1
    matches = [{**chunk, "score": scores[chunk["id"]]} for chunk in chunks if scores[chunk["id"]]]
    return sorted(matches, key=lambda chunk: (-chunk["score"], chunk["id"]))[:limit]


def _search_terms(query: str) -> list[str]:
    normalised_query = _normalise(query)
    tokens = [
        token
        for token in _TOKEN.findall(normalised_query)
        if len(token) >= 3 and token not in _STOP_WORDS
    ]
    phrases = [" ".join(tokens[index : index + 2]) for index in range(len(tokens) - 1)]
    compact_query = normalised_query.replace(" ", "")
    thai_phrases = [
        compact_query[index : index + _THAI_PHRASE_LENGTH]
        for index in range(max(0, len(compact_query) - _THAI_PHRASE_LENGTH + 1))
    ]
    return list(dict.fromkeys([*tokens, *phrases, *thai_phrases]))


def _normalise(text: str) -> str:
    return " ".join(text.casefold().split())
