"""Étape « charger » : copier les fichiers sources dans PostgreSQL.

Ce module fait trois choses :
1. il charge les fichiers géographiques (RPG, CartoBio, AAC) dans des tables
   src_... avec l'outil ogr2ogr, en les convertissant en Lambert 93 ;
2. il classe les deux référentiels de cultures dans les 8 catégories du projet
   (voir classification.py) et les charge aussi ;
3. il détecte, dans les tables chargées, le nom réel des colonnes utiles,
   pour que les scripts SQL fonctionnent même si un producteur les renomme.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd
from psycopg import sql

from . import classification, db
from .config import COLONNES_AAC, COLONNES_RPG, REFERENCE, SCHEMA, VALEURS_VRAI, Sources


def choisir_colonne(disponibles: list[str], candidats: tuple[str, ...]) -> str | None:
    """Renvoie le premier nom de `candidats` présent dans `disponibles`, ou None.

    Exemple : disponibles = ["fid", "id_parcel", "geom"] et
    candidats = ("id_parcel", "fid") renvoie "id_parcel". La comparaison
    ignore les majuscules, mais on renvoie le nom tel qu'il est écrit dans la table.
    """
    # Dictionnaire « nom en minuscules -> nom réel », pour retrouver le nom exact.
    index = {c.lower(): c for c in disponibles}
    for candidat in candidats:
        if candidat.lower() in index:
            return index[candidat.lower()]
    return None


def expression_bio(colonne: str | None, alias: str = "ign") -> str:
    """Morceau de SQL qui vaut vrai quand une parcelle RPG est constatée bio.

    Avec colonne="bio", on obtient par exemple :
        (lower(trim(ign."bio"::text)) IN ('1', 't', 'true', 'oui', ...))
    La valeur est convertie en texte puis en minuscules, pour accepter aussi
    bien un booléen (true / t) qu'un texte (« Oui »). Sans colonne bio, on
    renvoie NULL::boolean : l'information est simplement inconnue.
    """
    if colonne is None:
        return "NULL::boolean"
    valeurs = ", ".join(f"'{v}'" for v in VALEURS_VRAI)
    return f'(lower(trim({alias}."{colonne}"::text)) IN ({valeurs}))'


def morceaux(fichier: Path) -> list[Path]:
    """Liste des fichiers à charger pour une source.

    En temps normal, c'est le fichier lui-même. Si le fichier n'existe pas mais
    que des morceaux numérotés existent à côté (rpg_parcelles_01.gpkg,
    rpg_parcelles_02.gpkg..., produits par prefiltre.py), on renvoie ces morceaux.
    """
    if fichier.exists():
        return [fichier]
    parties = sorted(fichier.parent.glob(f"{fichier.stem}_[0-9][0-9]{fichier.suffix}"))
    if not parties:
        raise FileNotFoundError(f"{fichier} introuvable : voir docs/DONNEES.md")
    return parties


def ogr2ogr(fichier: Path, table: str, couche: str | None = None) -> None:
    """Charge un fichier géographique dans la table `table` du schéma du projet.

    Si la source est découpée en plusieurs morceaux, le premier crée la table
    et les suivants s'y ajoutent.
    """
    parties = morceaux(fichier)
    if len(parties) > 1:
        for i, partie in enumerate(parties):
            _ogr2ogr(partie, table, couche, ajout=i > 0)
        return
    _ogr2ogr(parties[0], table, couche, ajout=False)


def _ogr2ogr(fichier: Path, table: str, couche: str | None, ajout: bool) -> None:
    """Lance ogr2ogr pour un fichier (voir la liste des options ci-dessous)."""
    # PostGIS est l'extension qui ajoute les géométries à PostgreSQL : on
    # l'active si ce n'est pas déjà fait, ainsi que le schéma du projet.
    db.executer_requete_simple("CREATE EXTENSION IF NOT EXISTS postgis")
    db.executer_requete_simple(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
    # Options d'ogr2ogr, deux par deux :
    #   -f PostgreSQL <base>  écrire dans PostgreSQL, à l'adresse donnée ;
    #   -nln schema.table     nom de la table créée ;
    #   -t_srs EPSG:2154      convertir en Lambert 93 (mètres), la projection
    #                         officielle de la France métropolitaine ;
    #   -nlt PROMOTE_TO_MULTI stocker tous les polygones en MultiPolygon ;
    #   -lco GEOMETRY_NAME=geom / FID=fid  noms des colonnes géométrie et numéro ;
    #   -lco SPATIAL_INDEX=GIST  créer l'index spatial ;
    #   -overwrite / -append  remplacer la table, ou ajouter à la suite ;
    #   PG_USE_COPY=YES       méthode d'écriture rapide.
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
        "-append" if ajout else "-overwrite",
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
    """Écrit un tableau pandas dans une table PostgreSQL (toutes colonnes en texte).

    La table est supprimée puis recréée. Les lignes sont envoyées avec COPY,
    beaucoup plus rapide qu'un INSERT par ligne. sql.Identifier protège les
    noms de tables et de colonnes (guillemets, caractères spéciaux).
    """
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
    """Classe les deux référentiels de cultures et les charge dans la base.

    Les versions classées sont aussi écrites en CSV dans data/reference/, pour
    pouvoir vérifier à l'œil la catégorie de chaque code culture.
    """
    # Les référentiels du jeu de démonstration ne doivent pas se mêler aux vrais.
    sortie = REFERENCE / "demo" if "demo" in sources.ref_pac.parts else REFERENCE
    sortie.mkdir(parents=True, exist_ok=True)
    pac = classification.classer_pac(classification.lire_ref_pac(sources.ref_pac))
    cpfbio = classification.classer_cpfbio(classification.lire_ref_cpfbio(sources.ref_cpfbio))
    pac.to_csv(sortie / f"ref_cultures_pac_{annee}_classifie.csv", index=False)
    cpfbio.to_csv(sortie / "ref_cultures_cpfbio_classifie.csv", index=False)
    charger_referentiel(pac.drop(columns="groupe_reconnu"), "ref_cultures_pac")
    charger_referentiel(cpfbio.drop(columns="groupe_reconnu"), "ref_cultures_cpfbio")
    # Un groupe de cultures inconnu des règles de classement est rangé dans
    # « Autres » ; on le signale pour qu'une personne décide s'il faut une règle.
    for nom, ref in (("PAC", pac), ("CPFBIO", cpfbio)):
        inconnus = ref.loc[~ref.groupe_reconnu, "groupe"].dropna().unique()
        if len(inconnus):
            print(f"attention : groupes {nom} non reconnus, classés en Autres : {list(inconnus)}")
    return {"pac": len(pac), "cpfbio": len(cpfbio)}


def charger(annee: int, sources: Sources, avec_aac: bool = True) -> None:
    """Charge toutes les sources d'un millésime.

    avec_aac=False évite de recharger les AAC, communes à tous les millésimes.
    """
    if avec_aac:
        ogr2ogr(sources.aac, "src_aac")
    ogr2ogr(sources.rpg, f"src_rpg_{annee}")
    ogr2ogr(sources.bio, f"src_bio_{annee}")
    print("référentiels :", charger_referentiels(sources, annee))


def appliquer_stats_nationales(annee: int, sources: Sources) -> None:
    """Remplace la part bio « France » si le RPG chargé a été pré-filtré.

    Le pré-filtrage ne garde que les parcelles proches des AAC : la part bio du
    fichier chargé ne représente plus le territoire. prefiltre a calculé la
    vraie valeur sur le RPG complet dans rpg_stats_nationales.json.
    """
    chemin = sources.rpg.parent / "rpg_stats_nationales.json"
    if not chemin.exists():
        return
    stats = json.loads(chemin.read_text())
    db.executer_requete_simple(
        f'UPDATE "{SCHEMA}".synthese_nationale SET part_bio_pac_france = '
        f"{float(stats['part_bio_pac_france'])} WHERE annee = {int(annee)}"
    )
    print(f"part bio du RPG complet reprise de {chemin.name} : {stats['part_bio_pac_france']:.2%}")


def detecter(annee: int) -> dict[str, str | None]:
    """Trouve le nom réel des colonnes utiles dans les tables chargées.

    Renvoie un dictionnaire comme {"rpg_id": "id_parcel", "rpg_bio": "bio",
    "aac_id": "cdaac", ...}. Lève une erreur claire si une colonne
    indispensable est introuvable, plutôt que de laisser un script SQL
    échouer plus loin avec un message obscur.
    """
    rpg = db.colonnes(f"src_rpg_{annee}")
    aac = db.colonnes("src_aac")
    bio = db.colonnes(f"src_bio_{annee}")
    if not rpg or not aac or not bio:
        raise RuntimeError(f"sources {annee} absentes du schéma {SCHEMA} : lancer `charger`")
    choix = {f"rpg_{k}": choisir_colonne(rpg, v) for k, v in COLONNES_RPG.items()}
    choix.update({f"aac_{k}": choisir_colonne(aac, v) for k, v in COLONNES_AAC.items()})
    # Plusieurs champs de nom peuvent coexister (usage, administratif) : on les
    # combine pour qu'un nom vide dans l'un soit complété par l'autre.
    index = {c.lower(): c for c in aac}
    choix["aac_noms"] = [index[c] for c in COLONNES_AAC["nom"] if c in index]
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
