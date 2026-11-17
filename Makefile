.PHONY: install test lint format demo demo-llm serve ollama-pull docker-up clean

PY ?= python3
MODEL ?= qwen3:8b

install:
	$(PY) -m pip install -e ".[dev,pdf]"

test:
	$(PY) -m pytest

lint:
	ruff check src tests

format:
	ruff check --fix src tests
	ruff format src tests

# Démo complète SANS LLM : journal synthétique -> calibration -> audit
demo:
	mkdir -p out
	blocapta generate-log -o out/demo_bloc_log.csv
	blocapta calibrate out/demo_bloc_log.csv -o out/parcours_calibre.yaml
	blocapta template -o out/questionnaire_dsi.md --answers out/reponses.yaml
	blocapta apply-answers examples/questionnaire/reponses_exemple.yaml -o out/hopital.yaml
	blocapta audit out/hopital.yaml examples/specs/archivactes.yaml --no-llm -o out/rapport_audit.md
	@echo "Rapport : out/rapport_audit.md / .html"

# Même démo avec Ollama (extraction depuis la brochure texte + rédaction LLM)
demo-llm:
	mkdir -p out
	blocapta validate-spec examples/specs/archivactes_brochure.txt -o out/fiche_extraite.yaml
	blocapta audit examples/hospitals/ch_exemple.yaml examples/specs/archivactes_brochure.txt -o out/rapport_audit_llm.md

serve:
	blocapta serve --reload

ollama-pull:
	ollama pull $(MODEL)

docker-up:
	docker compose up -d --build

clean:
	rm -rf out .pytest_cache .ruff_cache
