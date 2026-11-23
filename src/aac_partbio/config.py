"""Réglages communs à tout le projet.

Ce fichier ne fait aucun calcul : il rassemble en un seul endroit les valeurs
que les autres modules utilisent (dossiers, nom du schéma PostgreSQL, seuils,
noms de colonnes attendus dans les sources). Pour changer un réglage, c'est
ici qu'il faut le modifier, une seule fois.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# --- Dossiers -----------------------------------------------------------
# ROOT est la racine du dépôt : ce fichier est dans src/aac_partbio/, on
# remonte donc de deux niveaux (parents[2]).
ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "sql"
RAW = ROOT / "data" / "raw"
REFERENCE = ROOT / "data" / "reference"
PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "docs" / "data"
# raw        : fichiers sources téléchargés (non versionnés, trop volumineux)
# reference  : référentiels de cultures classés, écrits au chargement
# processed  : tables de résultats (CSV) et rapports qualité
# docs/data  : données lues par la page web

# --- Base de données -------------------------------------------------------
# Un schéma PostgreSQL est un « dossier » de tables à l'intérieur d'une base.
# Toutes les tables du projet y sont rangées. On peut en changer sans toucher
# au code avec la variable d'environnement AAC_SCHEMA (os.environ.get lit
# cette variable, ou prend "aac_partbio" si elle n'existe pas).
SCHEMA = os.environ.get("AAC_SCHEMA", "aac_partbio")

# --- Réglages de la méthode (voir docs/METHODOLOGIE.md) -------------------
# Largeur, en mètres, de la marge ajoutée autour des AAC pour sélectionner
# les parcelles à comparer (script SQL 01).
BUFFER_M = 500
# Part minimale de surface commune pour considérer qu'une parcelle bio et une
# parcelle RPG décrivent le même terrain : 0.5 = 50 % (script SQL 04).
SEUIL_RECOUVREMENT = 0.5

# --- Noms de colonnes attendus dans les sources ---------------------------
# Les producteurs de données renomment parfois leurs colonnes d'une année à
# l'autre. Pour chaque information, on liste donc plusieurs noms possibles,
# du plus probable au moins probable. Au moment du traitement, le programme
# prend le premier nom qui existe vraiment dans la table chargée
# (voir chargement.detecter). Les noms sont en minuscules, car l'outil de
# chargement ogr2ogr met tous les noms de colonnes en minuscules.
COLONNES_RPG = {
    "id": ("id_parcel", "fid"),
    "culture": ("code_cultu", "code_culture", "culture_principale"),
    "surface": ("surf_parc", "surface_parcelle", "surface"),
    # Information « constatée bio » du RPG. Dans le RPG 2025 (version 4.0),
    # c'est la colonne booléenne « bio ». Si aucun de ces noms n'existe, le
    # traitement continue et considère toutes les parcelles RPG comme
    # conventionnelles.
    "bio": ("bio", "agri_bio", "parcelle_bio", "est_bio", "constate_bio"),
}
COLONNES_AAC = {
    "id": ("cdaac", "code_aac", "cd_aac", "id_aac"),
    "nom": (
        "nomdeaacusage",
        "nomdeaacadministratif",
        "nomaac",
        "lbaac",
        "nom_aac",
        "libelle",
        "nom",
    ),
}

# Valeurs de la colonne bio du RPG qui signifient « oui, parcelle bio ». La
# comparaison se fait en minuscules : « True », « OUI » ou « t » conviennent.
VALEURS_VRAI = ("1", "t", "true", "o", "oui", "y", "yes", "bio", "ab", "x")


# --- Fichiers sources -------------------------------------------------------
# Une « dataclass » est une petite structure qui regroupe des valeurs sous des
# noms : ici, les chemins des cinq fichiers nécessaires au traitement d'une année.
# frozen=True interdit de les modifier une fois créés.
@dataclass(frozen=True)
class Sources:
    """Chemins des fichiers d'entrée pour une année."""

    rpg: Path
    bio: Path
    aac: Path
    ref_pac: Path
    ref_cpfbio: Path


def sources_par_defaut(annee: int, racine: Path = RAW) -> Sources:
    """Emplacements attendus des fichiers téléchargés (voir docs/DONNEES.md).

    Exemple pour 2025 : data/raw/2025/rpg_parcelles.gpkg, data/raw/aac.gpkg...
    Les AAC et la liste CPFBIO sont indépendantes de l'année, d'où leur
    place à la racine de data/raw.
    """
    dossier = racine / str(annee)
    return Sources(
        rpg=dossier / "rpg_parcelles.gpkg",
        bio=dossier / "cartobio.gpkg",
        aac=racine / "aac.gpkg",
        ref_pac=dossier / f"REF_CULTURES_GROUPES_CULTURES_{annee}.csv",
        ref_cpfbio=racine / "liste-cultures-cpfbio.xlsx",
    )


# Pages officielles des sources, reprises dans la documentation et le site.
PAGES_SOURCES = {
    "rpg": "https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_RPG",
    "bio": "https://www.data.gouv.fr/datasets/parcelles-certifiees-en-agriculture-biologique-sur-cartobio",
    "aac": "https://www.data.gouv.fr/datasets/aires-dalimentation-de-captages-france-entiere-1",
}
