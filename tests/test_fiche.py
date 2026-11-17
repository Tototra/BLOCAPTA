"""Agent 1 (contrôle de complétude), grille réglementaire et normalisation de la fiche."""

from blocapta.llm import FakeLLM
from blocapta.models import FicheLogiciel
from blocapta.models.fiche import Acteur, EtapeProcessus
from blocapta.spec import check_completeness, fiche_to_software, load_grid, validate_document, validate_fiche

from .conftest import EXAMPLES, load_fiche


def test_grid_matches_specification():
    grid = load_grid()
    counts = {s: sum(g.statut == s for g in grid) for s in "ORF"}
    assert counts == {"O": 25, "R": 12, "F": 3}
    assert {g.id for g in grid if g.critique} == {"B2.acteurs", "B4.etapes", "B6.mode_degrade", "B8.risques_patient"}


def test_empty_fiche_is_not_analysable_with_questions():
    r = check_completeness(FicheLogiciel())
    assert r.verdict == "NON_ANALYSABLE" and r.confiance == "aucune"
    assert r.fiche_normalisee is None
    assert len(r.questions_a_l_auteur) == 10
    assert r.questions_a_l_auteur[0].champ_id in {"B2.acteurs", "B4.etapes", "B6.mode_degrade", "B8.risques_patient"}
    assert "doit être complétée" in r.resume


def test_unknown_on_mandatory_field_blocks():
    f = load_fiche("scantrace")
    f.fiabilite.mode_degrade = "Inconnu"
    r = check_completeness(f)
    assert r.verdict == "NON_ANALYSABLE"
    assert any(c.id == "B6.mode_degrade" and c.statut_champ == "Inconnu" for c in r.champs)


def test_partial_critical_field_blocks():
    f = load_fiche("scantrace")
    f.processus = [EtapeProcessus(etape="Tracer un implant", qui="IBODE", action="scan")]  # durées manquantes
    r = check_completeness(f)
    assert r.verdict == "NON_ANALYSABLE"


def test_example_scantrace_unsupported_gain_alert():
    r = check_completeness(load_fiche("scantrace"))
    assert r.verdict == "ANALYSABLE_AVEC_RESERVES"
    assert any(a.type == "affirmation_non_etayee" and "75 %" in a.detail for a in r.alertes)
    assert r.fiche_normalisee is not None


def test_role_incoherence_detected():
    f = load_fiche("scantrace")
    f.processus[0].qui = "Brancardier"
    r = check_completeness(f)
    assert any(a.type == "incoherence" for a in r.alertes)
    assert r.verdict == "NON_ANALYSABLE"  # B4 devient incohérent


def test_personal_data_blocks_without_copying():
    f = load_fiche("scantrace")
    f.preuves.retours_soignants = "Avis du Dr Martin très positif"
    r = check_completeness(f)
    assert r.verdict == "NON_ANALYSABLE"
    rgpd = [a for a in r.alertes if a.type == "rgpd"]
    assert rgpd and all("Martin" not in a.detail for a in rgpd)


def test_vague_text_is_partial():
    f = load_fiche("scantrace")
    f.perimetre.salles_specialites = "plusieurs salles"
    r = check_completeness(f)
    assert any(c.id == "B3.salles_specialites" and c.statut_champ == "Partiel" for c in r.champs)


def test_availability_100_is_suspect():
    f = load_fiche("scantrace")
    f.fiabilite.disponibilite_pct = 100
    assert any("100 %" in a.detail for a in check_completeness(f).alertes)


def test_regulatory_go_nogo():
    assert validate_fiche(load_fiche("scantrace")).go_nogo == "GO"
    v = validate_fiche(load_fiche("archivactes"))
    assert v.go_nogo == "NO_GO"
    assert "GO-01" in {r.id for r in v.blocking_failures}  # AIPD non réalisée


def test_hds_only_when_hosted_outside():
    f = load_fiche("scantrace")  # sur site : HDS non applicable
    ids = {r.id: r.status for r in validate_fiche(f).reglementaire}
    assert ids["GO-02"] == "non_applicable"


def test_normalisation_and_uncertainty():
    sw, hyps = fiche_to_software(load_fiche("archivactes"), {"tracabilite_actes"})
    tp = sw.touchpoints[0]
    assert tp.task_kind == "tracabilite_actes" and tp.roles == ["chirurgien"]
    assert tp.max_items_per_entry == 1
    assert tp.time_per_item_min.high == 0.75  # déclaration éditeur : +50 %
    assert any("éditeur" in h.hypothese for h in hyps)


def test_step_mapped_by_analogy():
    f = load_fiche("scantrace")
    f.processus[0].tache_bloc = None
    sw, hyps = fiche_to_software(f, {"tracabilite_dm"})
    assert sw.touchpoints[0].task_kind == "tracabilite_dm"
    assert any("analogie" in h.hypothese for h in hyps)


def test_free_text_goes_through_llm():
    structured = load_fiche("archivactes")
    llm = FakeLLM(structured_handler=lambda p, schema: structured if schema is FicheLogiciel else schema())
    v = validate_document(EXAMPLES / "fiches" / "archivactes_brochure.txt", llm=llm)
    assert v.fiche.identite.nom_version == "ArchivActes v2.3"


def test_users_must_appear_in_process():
    f = load_fiche("scantrace")
    f.acteurs.append(Acteur(role="IADE", utilise_logiciel=True, actions="consulte", moment_parcours="en salle", frequence="chaque cas"))
    assert any("iade" in a.detail for a in check_completeness(f).alertes)
