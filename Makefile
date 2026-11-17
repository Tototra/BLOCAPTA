.PHONY: install test lint format demo demo-llm fidelite scenarios serve ollama-pull docker-up clean

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

REF = src/blocapta/data/archetypes/bloc_reference.yaml

# Démo complète SANS LLM sur le bloc de référence (données OPROOM)
demo:
	mkdir -p out
	blocapta fidelite --replications 6 --workers 4
	blocapta fiche examples/fiches/scantrace.yaml --no-llm -o out/agent1_scantrace.json
	blocapta audit $(REF) examples/fiches/scantrace.yaml --no-llm --workers 4 -o out/rapport_scantrace.md
	blocapta audit $(REF) examples/fiches/archivactes.yaml --no-llm --workers 4 -o out/rapport_archivactes.md
	@echo "Rapports : out/rapport_*.md / .html"

# Test de fidélité du jumeau (Stop/Go)
fidelite:
	blocapta fidelite --replications 10 --workers 4

# Les scénarios fil rouge du cahier des charges
scenarios:
	for s in examples/scenarios/*.yaml; do \
		blocapta simulate $(REF) --software examples/fiches/archivactes.yaml --days 28 --replications 4 --workers 4 --scenario $$s; \
	done

# Avec Ollama : extraction d'une brochure en texte libre + rédaction du rapport par le LLM
demo-llm:
	mkdir -p out
	blocapta fiche examples/fiches/archivactes_brochure.txt --hospital $(REF) --save-fiche out/fiche_extraite.yaml
	blocapta audit $(REF) examples/fiches/archivactes_brochure.txt --workers 4 -o out/rapport_audit_llm.md

serve:
	blocapta serve --reload

ollama-pull:
	ollama pull $(MODEL)

docker-up:
	docker compose up -d --build

clean:
	rm -rf out .pytest_cache .ruff_cache
