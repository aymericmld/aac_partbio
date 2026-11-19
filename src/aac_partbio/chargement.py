"""Chargement des sources dans PostgreSQL et détection de leurs colonnes."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd
from psycopg import sql

from . import classification, db
from .config import COLONNES_AAC, COLONNES_RPG, REFERENCE, SCHEMA, VALEURS_VRAI, Sources


def choisir_colonne(disponibles: list[str], candidats: tuple[str, ...]) -> str | None:
    """Premier candidat présent dans la table, sans tenir compte de la casse."""
    index = {c.lower(): c for c in disponibles}
    for candidat in candidats:
        if candidat.lower() in index:
            return index[candidat.lower()]
    return None


def expression_bio(colonne: str | None, alias: str = "ign") -> str:
    """Expression SQL booléenne « parcelle constatée bio » pour le RPG."""
    if colonne is None:
        return "NULL::boolean"
    valeurs = ", ".join(f"'{v}'" for v in VALEURS_VRAI)
    return f'(lower(trim({alias}."{colonne}"::text)) IN ({valeurs}))'


def ogr2ogr(fichier: Path, table: str, couche: str | None = None) -> None:
    """Charge un fichier vectoriel en Lambert 93, géométrie `geom`, clé `fid`."""
    if not fichier.exists():
        raise FileNotFoundError(f"{fichier} introuvable : voir docs/DONNEES.md")
    db.executer_requete_simple("CREATE EXTENSION IF NOT EXISTS postgis")
    db.executer_requete_simple(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
    commande = [
        "ogr2ogr",
        "-f",
        "PostgreSQL",
        db.chaine_ogr(),
        str(fichier),
        "-nln",
        f"{SCHEMA}.{table}",
        "-t_srs",
        "EPSG:2154",
        "-nlt",
        "PROMOTE_TO_MULTI",
        "-lco",
        "GEOMETRY_NAME=geom",
        "-lco",
        "FID=fid",
        "-lco",
        "SPATIAL_INDEX=GIST",
        "-overwrite",
        "-progress",
        "--config",
        "PG_USE_COPY",
        "YES",
    ]
    if couche:
        commande.append(couche)
    print(f"chargement de {fichier.name} -> {SCHEMA}.{table}")
    subprocess.run(commande, check=True)


def charger_referentiel(df: pd.DataFrame, table: str) -> None:
    """Remplace une table de référence par le contenu d'un DataFrame (texte)."""
    with db.connexion() as conn, conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(SCHEMA)))
        cible = sql.Identifier(SCHEMA, table)
        cur.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(cible))
        definition = sql.SQL(", ").join(
            sql.SQL("{} text").format(sql.Identifier(c)) for c in df.columns
        )
        cur.execute(sql.SQL("CREATE TABLE {} ({})").format(cible, definition))
        with cur.copy(sql.SQL("COPY {} FROM STDIN").format(cible)) as copie:
            for ligne in df.astype(object).where(df.notna(), None).itertuples(index=False):
                copie.write_row([None if v is None else str(v) for v in ligne])
        cle = df.columns[0]
        cur.execute(sql.SQL("CREATE INDEX ON {} ({})").format(cible, sql.Identifier(cle)))


def charger_referentiels(sources: Sources, annee: int) -> dict[str, int]:
    """Classe les deux référentiels, les exporte dans data/reference et les charge."""
    # Les référentiels du jeu de démonstration ne doivent pas se mêler aux vrais.
    sortie = REFERENCE / "demo" if "demo" in sources.ref_pac.parts else REFERENCE
    sortie.mkdir(parents=True, exist_ok=True)
    pac = classification.classer_pac(classification.lire_ref_pac(sources.ref_pac))
    cpfbio = classification.classer_cpfbio(classification.lire_ref_cpfbio(sources.ref_cpfbio))
    pac.to_csv(sortie / f"ref_cultures_pac_{annee}_classifie.csv", index=False)
    cpfbio.to_csv(sortie / "ref_cultures_cpfbio_classifie.csv", index=False)
    charger_referentiel(pac.drop(columns="groupe_reconnu"), "ref_cultures_pac")
    charger_referentiel(cpfbio.drop(columns="groupe_reconnu"), "ref_cultures_cpfbio")
    for nom, ref in (("PAC", pac), ("CPFBIO", cpfbio)):
        inconnus = ref.loc[~ref.groupe_reconnu, "groupe"].dropna().unique()
        if len(inconnus):
            print(f"attention : groupes {nom} non reconnus, classés en Autres : {list(inconnus)}")
    return {"pac": len(pac), "cpfbio": len(cpfbio)}


def charger(annee: int, sources: Sources, avec_aac: bool = True) -> None:
    if avec_aac:
        ogr2ogr(sources.aac, "src_aac")
    ogr2ogr(sources.rpg, f"src_rpg_{annee}")
    ogr2ogr(sources.bio, f"src_bio_{annee}")
    print("référentiels :", charger_referentiels(sources, annee))


def detecter(annee: int) -> dict[str, str | None]:
    """Colonnes à utiliser dans les tables chargées pour ce millésime."""
    rpg = db.colonnes(f"src_rpg_{annee}")
    aac = db.colonnes("src_aac")
    bio = db.colonnes(f"src_bio_{annee}")
    if not rpg or not aac or not bio:
        raise RuntimeError(f"sources {annee} absentes du schéma {SCHEMA} : lancer `charger`")
    choix = {f"rpg_{k}": choisir_colonne(rpg, v) for k, v in COLONNES_RPG.items()}
    choix.update({f"aac_{k}": choisir_colonne(aac, v) for k, v in COLONNES_AAC.items()})
    obligatoires = ["rpg_id", "rpg_culture", "rpg_surface", "aac_id"]
    manquantes = [k for k in obligatoires if choix[k] is None]
    for colonne in ("fid", "culture", "convers", "surface"):
        if colonne not in bio:
            manquantes.append(f"bio.{colonne}")
    if manquantes:
        raise RuntimeError(
            f"colonnes introuvables : {manquantes}. Compléter les candidats dans config.py."
        )
    return choix
