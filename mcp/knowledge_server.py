from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Knowledge MCP Server")

KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parent / "knowledge_base"


def _load_documents() -> list[dict[str, Any]]:
    docs = []
    if not KNOWLEDGE_BASE_DIR.exists():
        return docs

    for filepath in KNOWLEDGE_BASE_DIR.glob("**/*.md"):
        content = filepath.read_text(encoding="utf-8")
        lines = content.strip().splitlines()
        title = lines[0].lstrip("# ").strip() if lines else filepath.name
        docs.append(
            {
                "filename": filepath.name,
                "path": str(filepath),
                "title": title,
                "content": content,
                "tokens": content.lower().replace("(", " ").replace(")", " ").split(),
            }
        )
    return docs


def search_runbooks_engine(query_term: str, top_k: int = 3) -> list[dict[str, Any]]:
    docs = _load_documents()
    if not docs:
        return []

    corpus = [doc["tokens"] for doc in docs]
    bm25 = BM25Okapi(corpus)

    query_tokens = query_term.lower().replace("(", " ").replace(")", " ").split()
    scores = bm25.get_scores(query_tokens)

    scored_docs = []
    for idx, score in enumerate(scores):
        if score > 0:
            d = docs[idx]
            scored_docs.append(
                {
                    "filename": d["filename"],
                    "title": d["title"],
                    "score": float(score),
                    "snippet": d["content"][:300],
                }
            )

    scored_docs.sort(key=lambda x: x["score"], reverse=True)
    return scored_docs[:top_k]


@mcp.tool()
def search_runbooks(session_id: str, query_term: str, top_k: int = 3) -> list[dict[str, Any]]:
    """
    Search operational runbooks and troubleshooting guides using BM25 text relevance.
    """
    return search_runbooks_engine(query_term, top_k=top_k)


if __name__ == "__main__":
    mcp.run()
