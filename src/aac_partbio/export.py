"""Exports : tables CSV, données du site et couche SIG des parcelles."""

from __future__ import annotations

import json
import subprocess
from datetime import date

import pandas as pd

from . import db
from .classification import CATEGORIES
from .config import BUFFER_M, PAGES_SOURCES, PROCESSED, SCHEMA, SEUIL_RECOUVREMENT, SITE_DATA

S = SCHEMA
CATEGORIES_SITE = (*CATEGORIES, "Non classé")
TOLERANCE_SIMPLIFICATION_M = 50


def annees_traitees() -> list[int]:
    if not db.table_existe("synthese_nationale"):
        return []
    df = db.requete(f'SELECT annee FROM "{S}".synthese_nationale ORDER BY annee')
    return [int(a) for a in df.annee]


def exporter_csv() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    for table in ("synthese_aac", "synthese_categorie", "synthese_nationale"):
        df = db.requete(f'SELECT * FROM "{S}".{table} ORDER BY 1, 2')
        df.to_csv(PROCESSED / f"{table}.csv", index=False)
        print(f"{table}.csv : {len(df)} lignes")


def _arrondir(valeur, chiffres: int = 4):
    if valeur is None or pd.isna(valeur):
        return None
    return round(float(valeur), chiffres)


def exporter_geojson(annee: int, precedente: int | None) -> int:
    """AAC simplifiées en WGS 84 avec leurs indicateurs, pour la carte du site."""
    df = db.requete(
        f"""
        WITH cat AS (
            SELECT pa.cdaac, p.categorie,
                   sum(pa.surface_dans_aac_ha) AS sau,
                   COALESCE(sum(pa.surface_dans_aac_ha) FILTER (WHERE p.bio), 0) AS bio
            FROM "{S}".parcel_aac pa JOIN "{S}".parcel p USING (annee, id_parcel)
            WHERE pa.annee = %(annee)s
            GROUP BY pa.cdaac, p.categorie
        )
        SELECT s.cdaac, s.nom, s.surface_aac_ha, s.sau_ha, s.sau_bio_ha, s.sau_ab_ha,
               s.sau_conversion_ha, s.part_bio, s.part_sau, s.categorie_dominante,
               s.nb_parcelles, prec.part_bio AS part_bio_prec,
               (SELECT json_object_agg(c.categorie, json_build_array(round(c.sau::numeric, 1),
                                                                      round(c.bio::numeric, 1)))
                  FROM cat c WHERE c.cdaac = s.cdaac) AS categories,
               ST_AsGeoJSON(ST_Transform(
                   ST_SimplifyPreserveTopology(a.geom, {TOLERANCE_SIMPLIFICATION_M}), 4326), 5)
                   AS geometrie
        FROM "{S}".synthese_aac s
            JOIN "{S}".aac a USING (cdaac)
            LEFT JOIN "{S}".synthese_aac prec
                   ON prec.cdaac = s.cdaac AND prec.annee = %(precedente)s
        WHERE s.annee = %(annee)s
        ORDER BY s.cdaac
        """,
        {"annee": annee, "precedente": precedente},
    )
    entites = []
    for ligne in df.itertuples(index=False):
        proprietes = {
            "cdaac": ligne.cdaac,
            "nom": ligne.nom,
            "surface_aac_ha": _arrondir(ligne.surface_aac_ha, 1),
            "sau_ha": _arrondir(ligne.sau_ha, 1),
            "sau_bio_ha": _arrondir(ligne.sau_bio_ha, 1),
            "sau_ab_ha": _arrondir(ligne.sau_ab_ha, 1),
            "sau_conversion_ha": _arrondir(ligne.sau_conversion_ha, 1),
            "part_bio": _arrondir(ligne.part_bio),
            "part_bio_prec": _arrondir(ligne.part_bio_prec),
            "part_sau": _arrondir(ligne.part_sau),
            "categorie_dominante": ligne.categorie_dominante,
            "nb_parcelles": int(ligne.nb_parcelles),
            "categories": ligne.categories or {},
        }
        entites.append(
            {"type": "Feature", "properties": proprietes, "geometry": json.loads(ligne.geometrie)}
        )
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    collection = {"type": "FeatureCollection", "annee": annee, "features": entites}
    (SITE_DATA / "aac.geojson").write_text(json.dumps(collection, ensure_ascii=False))
    return len(entites)


def exporter_site(demo: bool = False) -> None:
    annees = annees_traitees()
    if not annees:
        raise RuntimeError("aucun millésime traité : lancer `traiter` d'abord")
    derniere = annees[-1]
    precedente = annees[-2] if len(annees) > 1 else None

    nationale = db.requete(f'SELECT * FROM "{S}".synthese_nationale ORDER BY annee')
    categories = db.requete(f'SELECT * FROM "{S}".synthese_categorie ORDER BY annee, categorie')
    qualite = {}
    for annee in annees:
        chemin = PROCESSED / f"rapport_qualite_{annee}.json"
        if chemin.exists():
            rapport = json.loads(chemin.read_text())
            qualite[annee] = {
                k: rapport.get(k)
                for k in (
                    "taux_appariement_bio",
                    "part_chevauchement_residuel",
                    "part_sau_non_classee",
                    "concordance_categories",
                    "parcelles_par_source",
                )
            }

    site = {
        "meta": {
            "genere_le": date.today().isoformat(),
            "demo": demo,
            "annees": annees,
            "derniere": derniere,
            "precedente": precedente,
            "buffer_m": BUFFER_M,
            "seuil_recouvrement": SEUIL_RECOUVREMENT,
            "categories": list(CATEGORIES_SITE),
            "sources": PAGES_SOURCES,
        },
        "nationale": {
            int(r["annee"]): {k: _arrondir(v) if k != "annee" else int(v) for k, v in r.items()}
            for r in nationale.to_dict("records")
        },
        "categories": {
            int(a): [
                {
                    k: (_arrondir(v) if isinstance(v, float) else v)
                    for k, v in r.items()
                    if k != "annee"
                }
                for r in groupe.to_dict("records")
            ]
            for a, groupe in categories.groupby("annee")
        },
        "qualite": qualite,
    }
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "site.json").write_text(
        json.dumps(site, ensure_ascii=False, indent=1, default=str)
    )
    nb = exporter_geojson(derniere, precedente)
    print(f"site : {len(annees)} millésime(s), {nb} AAC dans aac.geojson")


def exporter_gpkg(annee: int) -> None:
    """Parcelles rattachées aux AAC, pour QGIS (non versionné, trop volumineux)."""
    PROCESSED.mkdir(parents=True, exist_ok=True)
    sortie = PROCESSED / f"parcel_aac_{annee}.gpkg"
    requete = f"""
        SELECT p.annee, p.id_parcel, p.source, p.code_culture, p.categorie, p.conversion,
               p.bio, p.surface_ha, pa.cdaac, pa.surface_dans_aac_ha, p.geom
        FROM "{S}".parcel p JOIN "{S}".parcel_aac pa USING (annee, id_parcel)
        WHERE p.annee = {int(annee)}"""
    subprocess.run(
        [
            "ogr2ogr",
            "-f",
            "GPKG",
            str(sortie),
            db.chaine_ogr(),
            "-sql",
            requete,
            "-nln",
            "parcel_aac",
            "-overwrite",
        ],
        check=True,
    )
    print(f"{sortie.name} écrit")


def exporter(demo: bool = False, gpkg: int | None = None) -> None:
    exporter_csv()
    exporter_site(demo=demo)
    if gpkg:
        exporter_gpkg(gpkg)
