"""Similarity engine: SBERT semantic similarity, TF-IDF lexical baseline,
and zero-shot domain classification."""
import re
import time

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Short descriptions used for zero-shot domain classification.
DOMAINS = {
    "Machine Learning & AI": "machine learning model, deep learning, neural network, prediction, classification, image recognition, natural language processing, chatbot, training data",
    "Web Development": "website, web portal, web application, online platform, frontend, backend, html, database driven site, e-commerce, management system for users",
    "Mobile Applications": "android app, ios app, mobile application, smartphone, flutter, notifications on phone, location based mobile service",
    "Internet of Things": "sensors, microcontroller, arduino, raspberry pi, esp32, hardware device, automation, monitoring physical environment, actuators",
    "Blockchain": "blockchain, smart contract, ethereum, decentralized ledger, cryptocurrency, tamper proof records, tokens, distributed trust",
    "Cybersecurity": "security, intrusion detection, malware, phishing, encryption, authentication, vulnerability, attack, privacy protection",
    "Data Science & Analytics": "data analysis, dashboard, visualization, statistics, forecasting trends, business insights, reports from datasets",
    "Cloud & DevOps": "cloud computing, aws, azure, docker, kubernetes, deployment pipeline, serverless, scaling, infrastructure monitoring",
}

# Bands are starting points; they must be re-calibrated on institutional data.
HIGH_OVERLAP = 0.75
RELATED = 0.55


def clean(text):
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def combined(title, abstract):
    # Title is repeated once so that it carries more weight than a long abstract.
    return f"{title}. {title}. {abstract or ''}".strip()


def band(score):
    if score >= HIGH_OVERLAP:
        return "High overlap"
    if score >= RELATED:
        return "Related"
    return "Original"


class Engine:
    def __init__(self):
        self._model = None
        self._domain_vecs = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(MODEL_NAME, device="cpu")
        return self._model

    def embed(self, texts):
        vecs = self.model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)

    def classify(self, vec):
        if self._domain_vecs is None:
            self._domain_vecs = self.embed(DOMAINS.values())
        scores = self._domain_vecs @ vec
        names = list(DOMAINS)
        best = int(np.argmax(scores))
        return names[best], float(scores[best])

    def sbert_scores(self, query_vec, matrix):
        if len(matrix) == 0:
            return np.zeros(0, dtype=np.float32)
        return matrix @ query_vec

    @staticmethod
    def tfidf_scores(query_text, corpus_texts):
        if not corpus_texts:
            return np.zeros(0)
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        m = vec.fit_transform([clean(t) for t in corpus_texts] + [clean(query_text)])
        q = m[-1]
        return (m[:-1] @ q.T).toarray().ravel()

    def check(self, title, abstract, records, top_k=5):
        """records: list of dicts with id, title, abstract, domain, year, embedding."""
        t0 = time.perf_counter()
        text = combined(title, abstract)
        qv = self.embed([text])[0]
        matrix = np.stack([r["embedding"] for r in records]) if records else np.zeros((0, qv.shape[0]))
        sem = self.sbert_scores(qv, matrix)
        lex = self.tfidf_scores(text, [combined(r["title"], r["abstract"]) for r in records])
        order = np.argsort(-sem)[:top_k]
        matches = [
            {
                "id": records[i]["id"],
                "title": records[i]["title"],
                "domain": records[i]["domain"],
                "year": records[i].get("year"),
                "semantic": round(float(sem[i]), 4),
                "lexical": round(float(lex[i]), 4),
                "band": band(float(sem[i])),
            }
            for i in order
        ]
        top = float(sem[order[0]]) if len(order) else 0.0
        domain, _ = self.classify(qv)
        return {
            "top_score": round(top, 4),
            "originality": round(max(0.0, 1.0 - max(top, 0.0)) * 100, 1),
            "band": band(top),
            "domain": domain,
            "matches": matches,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            "embedding": qv,
        }


engine = Engine()
