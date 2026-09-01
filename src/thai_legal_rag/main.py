import argparse
from importlib.resources import files
from pathlib import Path

from thai_legal_rag.llm import BBLClient
from thai_legal_rag.workflow import RAGState, build_graph


def run_query(question: str, knowledge_base_path: Path | None = None) -> RAGState:
    path = knowledge_base_path or _default_knowledge_base_path()
    graph = build_graph(BBLClient.from_environment(), path)
    return graph.invoke({"question": question, "subqueries": [], "evidence": [], "answer": ""})


def _default_knowledge_base_path() -> Path:
    checkout_path = Path("knowledge_base.txt")
    if checkout_path.is_file():
        return checkout_path
    return Path(str(files("thai_legal_rag").joinpath("knowledge_base.txt")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Small Thai legal two-agent RAG demo")
    parser.add_argument("--query", required=True, help="Thai legal question")
    args = parser.parse_args()

    try:
        result = run_query(args.query)
    except RuntimeError as error:
        raise SystemExit(f"Error: {error}") from None

    print(f"[Question] {result['question']}")
    print("[Subqueries]")
    print("\n".join(f"- {query}" for query in result["subqueries"]))
    print("[Evidence]")
    print("\n".join(f"- {chunk['id']} (section {chunk['section']})" for chunk in result["evidence"]))
    print("[Answer]")
    print(result["answer"])


if __name__ == "__main__":
    main()
