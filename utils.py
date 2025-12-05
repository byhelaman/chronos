import re
import os
import sys
import unicodedata
from rapidfuzz import process, fuzz
from typing import Dict, Any

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

IRRELEVANT_WORDS = re.compile(
    r"\b("
    + "|".join(
        [
            # Modalities
            r"online",
            r"presencial",
            r"virtual",
            r"hibrido",
            r"remoto",
            # Languages
            r"english",
            r"espanol",
            r"aleman",
            r"coreano",
            r"chino",
            r"ruso",
            r"japones",
            r"frances",
            r"italiano",
            r"mandarin",
            # Levels and courses
            r"nivelacion",
            r"beginner",
            r"electiv[oa]s?",
            r"leccion[es]?",
            r"repit[eo]?",
            r"repaso",
            r"crash",
            r"complete",
            r"revision",
            r"evaluacion[es]?",
            # Organization / structure
            # r"grupo",
            r"bvp",
            r"bvd",
            r"bvs",
            r"pia",
            r"mod",
            # r"l\d+",
            r"otg",
            r"kids",
            r"look\s?\d+",
            r"tz\d+",
            # Location / country
            r"per",
            r"ven",
            r"arg",
            r"uru",
            # Others
            r"true",
            r"business",
            r"impact",
            r"social",
            r"travel",
            r"gerencia",
            r"beca",
            r"camacho",
            r"esp",
        ]
    )
    + r")\b",
    flags=re.IGNORECASE,
)


def remove_irrelevant(text: str) -> str:
    tokens = re.findall(r"\w+", text.lower())
    filtered_tokens = [t for t in tokens if not IRRELEVANT_WORDS.search(t)]
    return " ".join(filtered_tokens)


def canonical(s: str) -> str:
    s = remove_irrelevant(s or "")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\W+", "", s)
    return s.casefold()


def normalizar_cadena(s: str) -> str:
    s = remove_irrelevant(s or "")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.strip().casefold()
    s = re.sub(r"[’‘ʻ‚]", "'", s)
    s = re.sub(r"[-_–—]", " ", s)
    s = re.sub(r"[^\w\s']", " ", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\d+", "", s)
    return s.strip()


def fuzzy_find(
    raw: str, choices: Dict[str, Any], scorer=fuzz.token_set_ratio, threshold: int = 85
) -> Any:
    if not raw or not choices:
        return None

    normalized_query = normalizar_cadena(raw)

    result = process.extractOne(
        normalized_query, list(choices.keys()), scorer=scorer, score_cutoff=threshold
    )

    if result:
        best_match_key = result[0]
        return choices[best_match_key]

    return None
