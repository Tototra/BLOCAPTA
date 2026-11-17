from pathlib import Path

import pytest
import yaml

from blocapta.models import Hospital, SoftwareModel, SpecSheet

ROOT = Path(__file__).resolve().parents[1]
ARCHETYPES = ROOT / "src" / "blocapta" / "data" / "archetypes"
EXAMPLES = ROOT / "examples"


@pytest.fixture
def hospital() -> Hospital:
    return Hospital.model_validate(yaml.safe_load((ARCHETYPES / "ch_general.yaml").read_text(encoding="utf-8")))


@pytest.fixture
def spec() -> SpecSheet:
    return SpecSheet.model_validate(yaml.safe_load((EXAMPLES / "specs" / "archivactes.yaml").read_text(encoding="utf-8")))


@pytest.fixture
def software(spec) -> SoftwareModel:
    return SoftwareModel.from_spec_sheet(spec)
