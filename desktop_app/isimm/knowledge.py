import json
from pathlib import Path
import re
import unicodedata

from .config import ROOT


def normalize(text):
    plain = "".join(
        c
        for c in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(c)
    )
    return " ".join(re.findall(r"\w+", plain))


def words(text):
    return set(normalize(text).split())


# Une relance peut dépendre d’un sujet antérieur. Un nouveau sujet utilise ses propres résultats.
REFERENCE = re.compile(
    r"^(?:combien|quand|ou exactement|a quelle date|peux tu preciser|how many|when exactly|كم|وقتاش|متى)$|^(?:et\b|and\b|what about\b|وفي|وماذا|وكم|وعلاش)|\b(?:cet|cette liste|cette demarche|ces documents|cela|celui|celle|combien y|les repartir|deuxieme|seconde|that|those|which one|the second|هذا|هذه|القرار|الثانية|الثاني|مثال اخر)\b"
)
TOPIC_CHANGE = re.compile(
    r"\b(?:changeons de sujet|autre sujet|autre question|new topic|different question|موضوع اخر)\b"
)


class Library:
    def __init__(self, directory=ROOT / "knowledge"):
        self.docs = []
        self.index = []
        for file in sorted(Path(directory).glob("*.json")):
            for row in json.loads(file.read_text()):
                if row["status"] not in ("verified", "to_confirm", "unavailable"):
                    raise ValueError("Statut documentaire invalide")
                if row["status"] == "verified" and not row.get("source"):
                    raise ValueError("Source obligatoire pour un fait vérifié")
                self.docs.append(row)
                self.index.append(
                    (words(row["tags"]), [normalize(p) for p in row.get("phrases", [])])
                )

    def search(self, question):
        query = normalize(question)
        tokens = set(query.split())
        ranked = []
        for doc, (tags, phrases) in zip(self.docs, self.index):
            score = len(tokens & tags) + 4 * sum(
                f" {p} " in f" {query} " for p in phrases
            )
            if score:
                ranked.append((score, doc))
        # La mention du nom de l’institut départage mal un horaire ou une procédure.
        ranked.sort(key=lambda item: (-item[0], item[1]["id"] == "institut"))
        return [doc for _, doc in ranked[:3]]

    def retrieve(self, question, history):
        found = self.search(question)
        query = normalize(question)
        if REFERENCE.search(query) and not TOPIC_CHANGE.search(query):
            for message in reversed(history):
                if message["role"] != "user":
                    continue
                for row in self.search(message["content"]):
                    if row not in found and len(found) < 3:
                        found.append(row)
                if not REFERENCE.search(normalize(message["content"])):
                    break
        return found
