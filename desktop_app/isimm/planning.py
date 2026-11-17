"""Calcul des durées quand l’étudiant demande de répartir un budget de temps."""

import json
import re

from .knowledge import normalize


PARTITION = re.compile(
    r"\b(?:repartir|partager|decouper|diviser|split|divide|allocate|نقسم|نوزع|اقسم|اوزع|تقسيم|توزيع)\b"
)
NUMBERS = {
    "deux": 2,
    "trois": 3,
    "quatre": 4,
    "cinq": 5,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "dix": 10,
    "quinze": 15,
    "vingt": 20,
    "trente": 30,
    "quarante": 40,
    "soixante": 60,
    "ten": 10,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "sixty": 60,
}
DURATION = re.compile(
    r"\b(\d+|"
    + "|".join(NUMBERS)
    + r")\s*(min(?:ute)?s?|heures?|hours?|دقيقة|دقايق|دقائق|ساعة|ساعات)\b"
)
FRACTIONS = re.compile(
    r"\b(demi heure|une demi heure|half an hour|half hour|نص ساعة|نصف ساعة|ربع ساعة|quart d heure|quarter of an hour)\b"
)
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "activities": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "activity": {
                        "type": "string",
                        "description": "A concrete action as a short spoken phrase in the student's language. Use ordinary words, never an identifier or a numbered placeholder.",
                    },
                    "weight": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["activity", "weight"],
            },
        }
    },
    "required": ["activities"],
}


def time_budget(question):
    q = normalize(question)
    if not PARTITION.search(q):
        return None
    times = list(DURATION.finditer(q))
    fractions = list(FRACTIONS.finditer(q))
    if len(times) + len(fractions) != 1:
        return None
    if fractions:
        duration = 15 if fractions[0][0].startswith(("ربع", "quart")) else 30
    else:
        match = times[0]
        before = q[: match.start()].split()
        after = q[match.end() :].strip()
        if (before and before[-1] in NUMBERS) or re.match(
            r"(?:et demie?|and a half|et quart|\d)", after
        ):
            return None
        number, unit = match.groups()
        duration = int(number) if number.isdecimal() else NUMBERS[number]
        if unit.startswith(("heur", "hour", "ساعة", "ساعات")):
            duration *= 60
    return duration if 2 <= duration <= 1440 else None


def render_plan(raw, budget, locale):
    """Conserver les proportions de Qwen et attribuer chaque minute exactement une fois."""
    try:
        activities = json.loads(raw)["activities"]
        if not isinstance(activities, list) or not 1 <= len(activities) <= min(
            5, budget
        ):
            return None
        labels = [a["activity"].replace("_", " ").strip() for a in activities]
        weights = [a["weight"] for a in activities]
        if any(type(w) is not int or not 1 <= w <= 100 for w in weights) or not all(
            labels
        ):
            return None
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    total = sum(weights)
    # Réserver une minute par activité, puis attribuer les minutes restantes aux
    # plus grands restes pour que la somme reste égale au budget.
    available = budget - len(weights)
    minutes = [1 + available * w // total for w in weights]
    order = sorted(
        range(len(weights)), key=lambda i: available * weights[i] % total, reverse=True
    )
    for i in order[: budget - sum(minutes)]:
        minutes[i] += 1
    if locale.startswith("ar"):
        return (
            "، ".join(f"{label} ({n} دقيقة)" for label, n in zip(labels, minutes)) + "."
        )
    return (
        ". ".join(
            f"{label} ({n} minute{'s' if n != 1 else ''})"
            for label, n in zip(labels, minutes)
        )
        + "."
    )
