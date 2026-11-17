"""Interface en ligne de commande : ``blocapta --help``."""

from __future__ import annotations

import json
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from .calibration import ColumnMapping, build_pathway, generate_bloc_log, load_event_log
from .configurator import (
    answers_template,
    apply_answers_file,
    dump_yaml,
    list_archetypes,
    load_hospital,
    load_hospital_dict,
    load_questionnaire,
    propose_patch,
    render_markdown,
)
from .llm import get_llm
from .models.software import SoftwareModel
from .pipeline import run_audit
from .settings import get_settings
from .simulation import simulate_audit, validate_twin
from .spec import validate_document

app = typer.Typer(help="BLOCAPTA — jumeau numérique hospitalier pour l'audit de compatibilité logicielle.", no_args_is_help=True)
console = Console()


def _llm(role: str, enabled: bool):
    return get_llm(role) if enabled else None


# --------------------------------------------------------------- template
@app.command()
def template(
    output: Path = typer.Option(Path("questionnaire_dsi.md"), "-o", help="Fichier Markdown à remettre à la DSI"),
    answers: Path | None = typer.Option(None, "--answers", help="Génère aussi le fichier de réponses YAML"),
):
    """Génère le questionnaire à remettre à la DSI (et le gabarit de réponses)."""
    q = load_questionnaire()
    output.write_text(render_markdown(q), encoding="utf-8")
    console.print(f"[green]Questionnaire :[/] {output} ({len(q.questions())} questions)")
    if answers:
        answers.write_text(answers_template(q), encoding="utf-8")
        console.print(f"[green]Gabarit de réponses :[/] {answers}")


@app.command("apply-answers")
def apply_answers_cmd(
    answers: Path = typer.Argument(..., help="Fichier reponses.yaml"),
    output: Path = typer.Option(Path("hopital.yaml"), "-o"),
    llm: bool = typer.Option(False, help="Utiliser le LLM pour intégrer les réponses en texte libre"),
):
    """Construit la configuration de l'hôpital à partir des réponses au questionnaire."""
    r = apply_answers_file(answers, llm=_llm("configurator", llm))
    if r.config:
        output.write_text(dump_yaml(r.config), encoding="utf-8")
    console.print(f"[green]{len(r.applied)} réponse(s) appliquée(s)[/] → {output}")
    for m in r.missing_required:
        console.print(f"[yellow]Manquant (obligatoire) :[/] {m}")
    for w in r.warnings:
        console.print(f"[yellow]Attention :[/] {w}")
    for e in r.errors:
        console.print(f"[red]Erreur :[/] {e}")
    for h in r.llm_hypotheses:
        console.print(f"[cyan]Hypothèse LLM :[/] {h}")


@app.command()
def archetypes():
    """Liste les archétypes d'établissements disponibles."""
    for k, v in list_archetypes().items():
        console.print(f"[bold]{k}[/] — {v}")


@app.command()
def resolve(hospital: Path, output: Path | None = typer.Option(None, "-o")):
    """Affiche la configuration complète d'un hôpital (héritage résolu et validé)."""
    text = dump_yaml(load_hospital(hospital))
    if output:
        output.write_text(text, encoding="utf-8")
    else:
        console.print(text)


@app.command()
def configure(
    hospital: Path,
    instruction: str = typer.Argument(..., help="Consigne en langage naturel"),
    apply: bool = typer.Option(False, "--apply", help="Écrit le résultat dans le fichier"),
    output: Path | None = typer.Option(None, "-o"),
):
    """Modifie la configuration d'un hôpital via le LLM configurateur (diff + validation)."""
    llm = get_llm("configurator")
    if llm is None:
        raise typer.BadParameter("LLM désactivé (BLOCAPTA_LLM_ENABLED=false)")
    config = load_hospital_dict(hospital)
    patch, result = propose_patch(config, instruction, llm)
    console.print(f"[bold]Justification :[/] {patch.rationale}")
    for h in patch.hypotheses:
        console.print(f"[cyan]Hypothèse :[/] {h}")
    if not result.ok:
        for e in result.errors:
            console.print(f"[red]{e}[/]")
        raise typer.Exit(1)
    for line in result.diff:
        console.print(f"  {line}")
    for w in result.warnings:
        console.print(f"[yellow]Attention :[/] {w}")
    if apply or output:
        target = output or hospital
        target.write_text(dump_yaml(result.config), encoding="utf-8")
        console.print(f"[green]Écrit :[/] {target}")


# ------------------------------------------------------------ fiche technique
@app.command("validate-spec")
def validate_spec_cmd(
    spec: Path,
    hospital: Path | None = typer.Option(None, help="Pour aligner les tâches sur celles de l'hôpital"),
    llm: bool = typer.Option(True, help="Utiliser le LLM (obligatoire pour PDF/texte libre)"),
    output: Path | None = typer.Option(None, "-o", help="Sauvegarde la fiche structurée (YAML)"),
):
    """Valide une fiche technique éditeur contre les critères minimum."""
    kinds = load_hospital(hospital).documentation_kinds() if hospital else None
    v = validate_document(spec, _llm("extraction", llm), known_task_kinds=kinds)
    t = Table(title=f"Fiche « {v.spec.produit.nom} » — complétude {v.score} %")
    for col in ("Critère", "Gravité", "Statut", "Libellé"):
        t.add_column(col)
    colors = {"ok": "green", "echec": "red", "non_applicable": "dim"}
    for r in v.results:
        t.add_row(r.id, r.severity, f"[{colors[r.status]}]{r.status}[/]", r.label)
    console.print(t)
    console.print("[green]ADMISSIBLE[/]" if v.admissible else "[red]NON ADMISSIBLE[/] (critère bloquant en échec)")
    for q in v.questions:
        console.print(f"  • {q.question}")
    if output:
        output.write_text(yaml.safe_dump(v.spec.model_dump(), allow_unicode=True, sort_keys=False), encoding="utf-8")


# ---------------------------------------------------------------- calibration
@app.command("generate-log")
def generate_log(
    output: Path = typer.Option(Path("data/demo_bloc_log.csv"), "-o"),
    days: int = 60,
    cases_per_day: float = 30,
    seed: int = 7,
):
    """Génère un journal d'événements synthétique (bloc + brancardage) pour la démo."""
    output.parent.mkdir(parents=True, exist_ok=True)
    df = generate_bloc_log(days, cases_per_day, seed)
    df.to_csv(output, index=False)
    console.print(f"[green]{len(df)} événements, {df.case_id.nunique()} cas[/] → {output}")


@app.command()
def calibrate(
    log: Path,
    pathway_id: str = typer.Option("chirurgie_programmee", "--pathway"),
    service: str = typer.Option("bloc"),
    mapping: Path | None = typer.Option(None, help="YAML de correspondance des colonnes (ColumnMapping)"),
    resources: Path | None = typer.Option(None, help="YAML activité -> ressources mobilisées"),
    hospital: Path | None = typer.Option(None, help="Valide le parcours calibré dans cet hôpital"),
    output: Path = typer.Option(Path("parcours_calibre.yaml"), "-o"),
):
    """Calibre un parcours (durées, arrivées) à partir d'un journal horodaté."""
    m = ColumnMapping.model_validate(yaml.safe_load(mapping.read_text())) if mapping else None
    df = load_event_log(log, m)
    step_res = yaml.safe_load(resources.read_text()) if resources else None
    pw, report = build_pathway(df, pathway_id, service, step_resources=step_res)
    output.write_text(dump_yaml(pw.model_dump(mode="json", exclude_none=True)), encoding="utf-8")
    t = Table(title=f"Calibration — {report.cases} cas, variante principale {report.main_variant_share:.0%}")
    for col in ("Étape", "Loi", "n", "Moyenne observée (min)", "p KS"):
        t.add_column(col)
    for s in report.steps:
        t.add_row(s.transition, s.distribution, str(s.n), f"{s.mean_observed_min:.1f}", f"{s.ks_pvalue:.3f}" if s.ks_pvalue is not None else "-")
    console.print(t)
    console.print(f"[green]Parcours calibré :[/] {output}")
    if hospital:
        cfg = load_hospital_dict(hospital)
        cfg["pathways"] = [p for p in cfg.get("pathways", []) if p["id"] != pathway_id] + [pw.model_dump(mode="json")]
        v = validate_twin(load_hospital(cfg), [report])
        for row in v.rows:
            status = "[green]OK[/]" if row.ok else "[red]ÉCART[/]"
            console.print(f"{status} {row.kpi} : observé {row.observed:.1f} / simulé {row.simulated:.1f} ({row.error_pct:.1f} %)")


# ----------------------------------------------------------------- simulation
@app.command()
def simulate(
    hospital: Path,
    software: Path = typer.Option(..., help="Modèle logiciel YAML ou fiche technique structurée"),
    days: int = 20,
    replications: int = 20,
    seed: int = 42,
    workers: int = 1,
    output: Path | None = typer.Option(None, "-o", help="Résultats JSON"),
):
    """Simule l'hôpital sans et avec le logiciel et compare."""
    h = load_hospital(hospital)
    data = yaml.safe_load(software.read_text(encoding="utf-8"))
    if "produit" in data:
        from .models.spec_sheet import SpecSheet

        sw = SoftwareModel.from_spec_sheet(SpecSheet.model_validate(data))
    else:
        sw = SoftwareModel.model_validate(data)
    with console.status("Simulation en cours…"):
        r = simulate_audit(h, sw, days, replications, seed, workers)
    t = Table(title=f"{sw.name} @ {h.name} — {replications} × {days} jours")
    for col in ("Indicateur", "Actuel", "Avec logiciel", "Écart %"):
        t.add_column(col)
    for k in r.kpis:
        t.add_row(k.label, f"{k.baseline.mean:.2f}", f"{k.software.mean:.2f}", f"{k.delta_pct:+.1f}" if k.delta_pct is not None else "-")
    console.print(t)
    for f in r.frictions:
        console.print(f"[bold]{f.severity}[/] {f.type} — {f.pathway}/{f.step} : {f.example} ({f.affected_share:.0%} des tâches)")
    if output:
        output.write_text(r.model_dump_json(indent=2), encoding="utf-8")


# ---------------------------------------------------------------------- audit
@app.command()
def audit(
    hospital: Path,
    spec: Path,
    days: int = 20,
    replications: int = 20,
    seed: int = 42,
    workers: int = 1,
    llm: bool = typer.Option(True, help="LLM pour l'extraction de fiche et la rédaction"),
    output: Path = typer.Option(Path("out/rapport_audit.md"), "-o"),
):
    """Audit complet : validation de la fiche, simulation, rapport (Markdown + HTML + JSON)."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with console.status("Audit en cours…"):
        r = run_audit(
            hospital, spec, days=days, replications=replications, seed=seed, workers=workers,
            extraction_llm=_llm("extraction", llm), report_llm=_llm("report", llm),
        )
    output.write_text(r.markdown, encoding="utf-8")
    output.with_suffix(".html").write_text(r.html, encoding="utf-8")
    output.with_suffix(".json").write_text(r.facts.model_dump_json(indent=2), encoding="utf-8")
    s = r.facts.score
    console.print(f"[bold]Score : {s.score}/100 — {s.level}[/]  (rédaction : {r.narrative.generated_by})")
    console.print(f"[green]Rapport :[/] {output}, {output.with_suffix('.html')}, {output.with_suffix('.json')}")


@app.command("reference")
def reference_cmd(
    output: Path = typer.Option(Path("src/blocapta/data/archetypes/bloc_reference.yaml"), "-o"),
    stats: Path | None = typer.Option(None, help="Statistiques agrégées (tools/oproom_aggregate.py)"),
    staffing: Path | None = typer.Option(None, help="Effectifs, horaires et hypothèses (YAML)"),
):
    """(Re)construit le bloc de référence à partir des données agrégées et des effectifs."""
    from .reference import build_reference_bloc, load_staffing, load_stats

    d = build_reference_bloc(load_stats(stats), load_staffing(staffing))
    header = (
        "# FICHIER GÉNÉRÉ par `blocapta reference build` à partir de data/reference/ (ne pas éditer à la main).\n"
        "# Hériter de cet archétype avec  extends: bloc_reference  pour décrire un autre bloc.\n"
    )
    output.write_text(header + dump_yaml(d), encoding="utf-8")
    console.print(f"[green]Bloc de référence :[/] {output} ({len(d['pathways'])} parcours)")
    for item in d["metadata"]["parametres_a_calibrer"].split(" | "):
        console.print(f"  [yellow]à calibrer[/] {item}")


@app.command()
def fidelite(
    hospital: Path | None = typer.Option(None, help="Configuration à tester (défaut : bloc de référence)"),
    days: int = 56,
    replications: int = 10,
    seed: int = 7,
    workers: int = 1,
    output: Path | None = typer.Option(None, "-o", help="Résultat JSON"),
):
    """Test de fidélité (Stop/Go) : le bloc simulé sans outil retrouve-t-il les chiffres réels ?"""
    from .reference import fidelity_targets
    from .simulation import check_fidelity

    h = load_hospital(hospital) if hospital else load_hospital({"id": "ref", "name": "ref", "extends": "bloc_reference"})
    with console.status("Simulation de l'existant…"):
        r = check_fidelity(h, fidelity_targets(), days=days, replications=replications, seed=seed, workers=workers)
    t = Table(title=f"Fidélité — {replications} × {days} jours — verdict {r.verdict}")
    for col in ("Indicateur", "Observé", "Simulé [IC 95 %]", "Écart", "Tolérance", ""):
        t.add_column(col)
    for row in r.rows:
        t.add_row(
            row.indicator, f"{row.observed:.1f}", f"{row.simulated:.1f} [{row.ci_low:.1f} ; {row.ci_high:.1f}]",
            f"{row.error_pct:.1f} %", row.tolerance, "[green]OK[/]" if row.ok else "[red]ÉCART[/]",
        )
    console.print(t)
    console.print(f"Contrôles physiques : {r.invariants} → {'[green]OK[/]' if r.invariants_ok else '[red]ÉCHEC[/]'}")
    console.print(f"[bold]Verdict : {r.verdict}[/]")
    if output:
        output.write_text(r.model_dump_json(indent=2), encoding="utf-8")
    if r.verdict != "GO":
        raise typer.Exit(1)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Lance l'API REST (documentation sur /docs)."""
    import uvicorn

    uvicorn.run("blocapta.api:app", host=host, port=port, reload=reload)


@app.command()
def config():
    """Affiche la configuration active (modèles Ollama, chemins)."""
    console.print_json(json.dumps(get_settings().model_dump(mode="json")))


if __name__ == "__main__":
    app()
