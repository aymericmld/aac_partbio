"""Paramètres partagés par toutes les étapes du pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "sql"
RAW = ROOT / "data" / "raw"
REFERENCE = ROOT / "data" / "reference"
PROCESSED = ROOT / "data" / "processed"
SITE_DATA = ROOT / "docs" / "data"

# Schéma PostgreSQL qui reçoit les sources et les résultats.
SCHEMA = os.environ.get("AAC_SCHEMA", "aac_partbio")

# Tampon autour des AAC pour sélectionner les parcelles à apparier (m).
BUFFER_M = 500
# Recouvrement minimal pour considérer deux parcelles comme identiques.
SEUIL_RECOUVREMENT = 0.5

# Noms de colonnes possibles, par ordre de préférence. Le pipeline retient le
# premier présent dans la table chargée, ce qui absorbe les changements de
# schéma d'un millésime à l'autre (ogr2ogr met les noms en minuscules).
COLONNES_RPG = {
    "id": ("id_parcel", "fid"),
    "culture": ("code_cultu", "code_culture", "culture_principale"),
    "surface": ("surf_parc", "surface_parcelle", "surface"),
    # Absente avant 2025. Depuis le RPG 4.0, l'information « constatée bio »
    # est un attribut de la couche Parcelles : vérifier son nom exact dans le
    # descriptif DC_DL_RPG_4-0 et l'ajouter ici si besoin.
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

# Valeurs interprétées comme « bio » dans la colonne bio du RPG.
VALEURS_VRAI = ("1", "t", "true", "o", "oui", "y", "yes", "bio", "ab", "x")


@dataclass(frozen=True)
class Sources:
    """Fichiers d'entrée d'un millésime."""

    rpg: Path
    bio: Path
    aac: Path
    ref_pac: Path
    ref_cpfbio: Path


def sources_par_defaut(annee: int, racine: Path = RAW) -> Sources:
    """Emplacements attendus des fichiers téléchargés (voir docs/DONNEES.md)."""
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
