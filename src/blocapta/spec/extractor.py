"""Extraction d'une fiche technique (PDF, texte, JSON, YAML) vers le schéma ``SpecSheet``."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ..llm import LLMClient, LLMError
from ..models.spec_sheet import SpecSheet

SYSTEM_EXTRACTION = """Tu es un assistant d'une DSI hospitalière française.
Tu lis la fiche technique d'un logiciel proposé par un éditeur et tu remplis un schéma JSON.
Règles impératives :
- N'invente JAMAIS une information. Si elle n'est pas explicitement écrite, mets null (ou une liste vide).
- Un booléen vaut true uniquement si la fiche l'affirme clairement.
- Les durées sont en secondes dans les champs *_sec.
- `elements_max_par_saisie` : nombre maximal d'éléments (ex. actes) enregistrables en UNE saisie.
  Si la fiche dit « un acte à la fois » → 1. Si rien n'est dit → null.
- Normalise les standards : HL7v2, FHIR, DICOM, HPRIM, CDA.
"""


class Ambiguity(BaseModel):
    champ: str = Field(description="Chemin du champ concerné, ex. metier.points_de_contact[0].elements_max_par_saisie")
    question: str = Field(description="Question précise à poser à l'éditeur")


class Ambiguities(BaseModel):
    items: list[Ambiguity] = Field(default_factory=list)


def read_document(path: Path) -> str | SpecSheet:
    """Lit un document. Renvoie directement une ``SpecSheet`` si le fichier est déjà structuré."""
    suffix = path.suffix.lower()
    if suffix in {".json"}:
        return SpecSheet.model_validate(json.loads(path.read_text(encoding="utf-8")))
    if suffix in {".yaml", ".yml"}:
        return SpecSheet.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("Lecture PDF : installez l'extra `pip install blocapta[pdf]`") from e
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(encoding="utf-8", errors="replace")


def extract_spec(text: str, llm: LLMClient, known_task_kinds: set[str] | None = None) -> SpecSheet:
    hint = ""
    if known_task_kinds:
        hint = (
            "\nPour `metier.points_de_contact[].tache`, utilise de préférence l'un de ces identifiants "
            f"s'il correspond : {sorted(known_task_kinds)}."
        )
    prompt = f"Fiche technique à analyser :\n\"\"\"\n{text[:60000]}\n\"\"\"\n{hint}\nRemplis le schéma."
    try:
        return llm.structured(prompt, SpecSheet, system=SYSTEM_EXTRACTION)
    except LLMError:
        raise


def find_ambiguities(text: str, spec: SpecSheet, llm: LLMClient) -> list[Ambiguity]:
    prompt = (
        "Voici une fiche technique et les données qui en ont été extraites.\n"
        f"Fiche :\n\"\"\"\n{text[:30000]}\n\"\"\"\n"
        f"Extraction :\n{spec.model_dump_json(indent=1)}\n\n"
        "Liste les informations floues, contradictoires ou manquantes qui empêchent d'évaluer "
        "l'intégration du logiciel dans un hôpital (cardinalités, interfaces, rôles, horaires, postes). "
        "Formule une question précise à l'éditeur pour chacune. Maximum 10."
    )
    return llm.structured(prompt, Ambiguities, system=SYSTEM_EXTRACTION).items
