"""Lecture d'une fiche logiciel (YAML/JSON structuré, ou PDF, Word, texte à extraire par LLM)."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import yaml

from ..llm import LLMClient
from ..models.fiche import FicheLogiciel

SYSTEM_EXTRACTION = """Tu es l'assistant d'une DSI hospitalière française (projet Blocapta).
Tu lis une fiche logiciel (template Blocapta v0.1, 11 blocs) ou une documentation d'éditeur,
et tu remplis le schéma JSON FicheLogiciel.
Règles impératives :
- N'invente JAMAIS une information. Si elle n'est pas écrite, laisse null (ou une liste vide).
  Si l'auteur a écrit « Inconnu », recopie « Inconnu ».
- Un booléen vaut true uniquement si le document l'affirme clairement.
- Les durées du bloc 4 sont en minutes. `unite_duree` = "par_element" si la durée s'entend
  par implant, par acte, par dispositif ; sinon "par_cas".
- `niveau_preuve` : mesure_site, etude_publiee, retour_utilisateur, estimation_bloc ou declaration_editeur.
- `elements_max_par_saisie` : 1 si le document dit « un seul acte / un seul élément par saisie ».
- Ne recopie aucun nom de patient ou de soignant.
"""


def _docx_text(path: Path) -> str:
    """Texte d'un .docx sans dépendance (paragraphes et cellules de tableaux)."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"</w:tc>", " | ", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    return re.sub(r"\n{3,}", "\n\n", text)


def read_document(path: Path) -> str | FicheLogiciel:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return FicheLogiciel.model_validate(json.loads(path.read_text(encoding="utf-8")))
    if suffix in {".yaml", ".yml"}:
        return FicheLogiciel.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("Lecture PDF : installez l'extra `pip install blocapta[pdf]`") from e
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    if suffix == ".docx":
        return _docx_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


def extract_fiche(text: str, llm: LLMClient, known_task_kinds: set[str] | None = None) -> FicheLogiciel:
    hint = ""
    if known_task_kinds:
        hint = (
            "\nPour `processus[].tache_bloc`, utilise l'un de ces identifiants de tâche du jumeau "
            f"s'il correspond à l'étape : {sorted(known_task_kinds)} ; sinon null."
        )
    prompt = f"Document à analyser :\n\"\"\"\n{text[:60000]}\n\"\"\"\n{hint}\nRemplis le schéma."
    return llm.structured(prompt, FicheLogiciel, system=SYSTEM_EXTRACTION)
