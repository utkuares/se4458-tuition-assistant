"""Splits the tuition policy document into sections and searches them with BM25."""
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel
from rank_bm25 import BM25Okapi

DOCUMENT_NAME = "University_Tuition_Policies.md"
DEFAULT_DOCUMENT_PATH = Path(__file__).resolve().parents[1] / "data" / DOCUMENT_NAME

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from", "how",
    "i", "if", "in", "is", "it", "my", "of", "on", "or", "the", "to", "what", "when", "which",
    "with", "you", "your",
}

SECTION_HEADING = re.compile(r"^(#{2,3})\s+(\d+(?:\.\d+)?)\.?\s+(.*)$")


class PolicyMatch(BaseModel):
    section: str
    heading: str
    text: str
    score: float


class PolicySearchResult(BaseModel):
    document: str
    query: str
    matches: list[PolicyMatch]


@dataclass
class Chunk:
    section: str
    heading: str
    text: str


def tokenize(text: str) -> list[str]:
    """Lowercases, keeps words and numbers, drops stop words and a plural 's'."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    tokens = []
    for word in words:
        if word in STOP_WORDS:
            continue
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        tokens.append(word)
    return tokens


def split_into_chunks(markdown: str) -> list[Chunk]:
    """One chunk per '###' subsection, plus '##' sections that have text but no subsections."""
    chunks: list[Chunk] = []
    current: Chunk | None = None

    for line in markdown.splitlines():
        match = SECTION_HEADING.match(line)
        if match:
            if current and current.text.strip():
                chunks.append(current)
            _, section, heading = match.groups()
            current = Chunk(section=section, heading=heading.strip(), text="")
        elif current is not None:
            current.text += line + "\n"

    if current and current.text.strip():
        chunks.append(current)

    for chunk in chunks:
        chunk.text = " ".join(chunk.text.split())
    return chunks


class PolicyIndex:
    """Builds the BM25 index once and answers search queries."""

    def __init__(self, document_path: Path = DEFAULT_DOCUMENT_PATH):
        self.document_name = document_path.name
        self.chunks = split_into_chunks(document_path.read_text(encoding="utf-8"))
        corpus = [tokenize(f"{c.heading} {c.heading} {c.text}") for c in self.chunks]
        self.bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 3) -> PolicySearchResult:
        """Returns the best matching sections in the format from section 9 of the document."""
        tokens = tokenize(query)
        if not tokens:
            return PolicySearchResult(document=self.document_name, query=query, matches=[])

        scores = self.bm25.get_scores(tokens)
        ranked = sorted(range(len(self.chunks)), key=lambda i: scores[i], reverse=True)
        matches = [
            PolicyMatch(
                section=self.chunks[i].section,
                heading=self.chunks[i].heading,
                text=self.chunks[i].text,
                score=round(float(scores[i]), 3),
            )
            for i in ranked[:top_k]
            if scores[i] > 0
        ]
        return PolicySearchResult(document=self.document_name, query=query, matches=matches)