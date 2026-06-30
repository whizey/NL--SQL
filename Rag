"""
rag.py
Retrieval layer for the NL->SQL system.

Embeds the 15 verified question->SQL pairs once at startup, then for each new
question retrieves the most similar prior examples (cosine similarity over
TF-IDF vectors) to inject as few-shot context. This is the "RAG" in the system:
generation is augmented with retrieved, verified examples.

TF-IDF is used deliberately: the example store is small (15 items) and lexical
overlap between a user's phrasing and a verified question is a strong signal for
the right SQL template. For a larger store this would move to sentence
embeddings + a vector index — the retrieval interface here stays the same.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from knowledge_base import VERIFIED_PAIRS


class SQLRetriever:
    def __init__(self, pairs=VERIFIED_PAIRS):
        self.pairs = pairs
        self._questions = [p["q"] for p in pairs]
        # Fit once; word-level 1-2 grams capture phrases like "how many"
        self.vectorizer = TfidfVectorizer(
            lowercase=True, stop_words="english", ngram_range=(1, 2)
        )
        self._matrix = self.vectorizer.fit_transform(self._questions)

    def retrieve(self, question: str, k: int = 3, min_score: float = 0.05):
        """Return up to k most-similar verified pairs, each with its score."""
        q_vec = self.vectorizer.transform([question])
        sims = cosine_similarity(q_vec, self._matrix)[0]
        ranked = sorted(
            zip(self.pairs, sims), key=lambda t: t[1], reverse=True
        )
        out = []
        for pair, score in ranked[:k]:
            if score >= min_score:
                out.append({"q": pair["q"], "sql": pair["sql"], "score": round(float(score), 3)})
        return out

    def build_fewshot_block(self, question: str, k: int = 3) -> str:
        """Format retrieved examples as a few-shot block for the prompt."""
        examples = self.retrieve(question, k=k)
        if not examples:
            return ""
        lines = ["Here are verified examples of similar questions and their correct SQL:"]
        for ex in examples:
            lines.append(f"Q: {ex['q']}\nSQL: {ex['sql']}")
        return "\n\n".join(lines)


# Singleton built once at import
retriever = SQLRetriever()
