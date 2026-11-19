"""Enchaîne les scripts SQL d'un millésime avec les colonnes détectées."""

from __future__ import annotations

from . import chargement, db
from .config import BUFFER_M, SCHEMA, SEUIL_RECOUVREMENT

ETAPES = (
    "01_aac_emprise.sql",
    "02_rpg_ign.sql",
    "03_rpg_bio.sql",
    "04_appariement.sql",
    "05_parcelles.sql",
    "06_rattachement_aac.sql",
    "07_syntheses.sql",
)


def variables(annee: int, colonnes: dict[str, str | None]) -> dict[str, object]:
    noms = colonnes.get("aac_noms") or ([colonnes["aac_nom"]] if colonnes["aac_nom"] else [])
    nom_expr = (
        "COALESCE(" + ", ".join(f"NULLIF(trim(src.\"{n}\"::text), '')" for n in noms) + ")"
        if noms
        else "NULL::text"
    )
    return {
        "schema": SCHEMA,
        "annee": annee,
        "buffer": BUFFER_M,
        "seuil": SEUIL_RECOUVREMENT,
        "src_rpg": f"src_rpg_{annee}",
        "src_bio": f"src_bio_{annee}",
        "t_rpg_ign": f"rpg_ign_{annee}",
        "t_rpg_bio": f"rpg_bio_{annee}",
        "t_recouvrement": f"recouvrement_{annee}",
        "t_appariement": f"appariement_{annee}",
        "t_ign_remplace": f"ign_remplace_{annee}",
        "rpg_id": colonnes["rpg_id"],
        "rpg_culture": colonnes["rpg_culture"],
        "rpg_surface": colonnes["rpg_surface"],
        "rpg_bio_expr": chargement.expression_bio(colonnes["rpg_bio"]),
        "aac_id": colonnes["aac_id"],
        "aac_nom_expr": nom_expr,
    }


def traiter(annee: int, depuis: int = 1) -> dict[str, float]:
    colonnes = chargement.detecter(annee)
    print("colonnes retenues :", colonnes)
    if colonnes["rpg_bio"] is None:
        print("information : pas d'attribut bio dans ce RPG, toutes ses parcelles sont CONV")
    db.executer_requete_simple("CREATE EXTENSION IF NOT EXISTS postgis")
    params = variables(annee, colonnes)
    durees = {}
    for etape in ETAPES[depuis - 1 :]:
        durees[etape] = db.executer_sql(etape, params)
        print(f"{etape} : {durees[etape]:.1f} s")
    return durees
