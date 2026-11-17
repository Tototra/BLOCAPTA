from pathlib import Path

import pytest
import yaml

from blocapta.models import FicheLogiciel, Hospital, SoftwareModel
from blocapta.spec import fiche_to_software

ROOT = Path(__file__).resolve().parents[1]
ARCHETYPES = ROOT / "src" / "blocapta" / "data" / "archetypes"
EXAMPLES = ROOT / "examples"


@pytest.fixture
def hospital() -> Hospital:
    return Hospital.model_validate(yaml.safe_load((ARCHETYPES / "ch_general.yaml").read_text(encoding="utf-8")))


def load_fiche(name: str) -> FicheLogiciel:
    return FicheLogiciel.model_validate(yaml.safe_load((EXAMPLES / "fiches" / f"{name}.yaml").read_text(encoding="utf-8")))


@pytest.fixture
def fiche() -> FicheLogiciel:
    return load_fiche("archivactes")


@pytest.fixture
def software(fiche) -> SoftwareModel:
    return fiche_to_software(fiche)[0]
