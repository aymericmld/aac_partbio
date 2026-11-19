"""Classement des cultures des deux référentiels dans 8 catégories communes.

Les règles reprennent la classification documentée dans docs/METHODOLOGIE.md :
d'abord un rattachement par groupe, puis des exceptions ligne à ligne pour les
groupes hétérogènes. Elles s'appuient sur les libellés plutôt que sur les codes,
pour rester valables quand un millésime ajoute des codes.
"""

from __future__ import annotations

import unicodedata

import pandas as pd

CEREALES = "Céréales et oléoprotéagineux"
FOURRAGE = "Cultures fourragères"
PRAIRIES = "Prairies"
FRUITS = "Cultures fruitières"
MARAICHAGE = "Maraîchage"
VIGNES = "Vignes"
PPAM = "Plantes à parfum, aromatiques et médicinales"
AUTRES = "Autres"

CATEGORIES = (CEREALES, FOURRAGE, PRAIRIES, FRUITS, MARAICHAGE, VIGNES, PPAM, AUTRES)


def normaliser(texte: object) -> str:
    """Minuscules, sans accents ni espaces superflus."""
    if texte is None or (isinstance(texte, float) and pd.isna(texte)):
        return ""
    sans_accents = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return " ".join(sans_accents.lower().replace("’", "'").split())


# --- Référentiel PAC (REF_CULTURES_GROUPES_CULTURES_AAAA.csv) ---------------

# Début du libellé de groupe normalisé -> catégorie.
GROUPES_PAC = (
    ("ble tendre", CEREALES),
    ("mais", CEREALES),
    ("orge", CEREALES),
    ("autres cereales", CEREALES),
    ("colza", CEREALES),
    ("tournesol", CEREALES),
    ("autres oleagineux", CEREALES),
    ("proteagineux", CEREALES),
    ("riz", CEREALES),
    ("legumineuses a grains", CEREALES),
    ("fourrage", FOURRAGE),
    ("estives", PRAIRIES),
    ("prairies permanentes", PRAIRIES),
    ("prairies temporaires", PRAIRIES),
    ("vergers", FRUITS),
    ("fruits a coque", FRUITS),
    ("oliviers", FRUITS),
    ("vignes", VIGNES),
    ("legumes", MARAICHAGE),
    ("plantes a fibres", AUTRES),
    ("gel", AUTRES),
    ("canne a sucre", AUTRES),
    ("divers", AUTRES),
    ("autres cultures industrielles", AUTRES),
)
GROUPES_PAC_HETEROGENES = ("divers", "autres cultures industrielles")

# Mots du libellé de culture qui sortent une ligne de « Autres ».
EXCEPTIONS_PAC = (
    ("houblon", PPAM),
    ("lavande", PPAM),
    ("lavandin", PPAM),
    ("vanille", PPAM),
    ("persil", PPAM),
    ("fenugrec", PPAM),
    ("plante medicinale", PPAM),
    ("plantes medicinales", PPAM),
    ("plante aromatique", PPAM),
    ("plantes aromatiques", PPAM),
    ("plante a parfum", PPAM),
    ("plantes a parfum", PPAM),
    ("cameline", CEREALES),
    ("moutarde", CEREALES),
)


def categorie_pac(libelle_groupe: object, libelle_culture: object) -> tuple[str, bool]:
    """Catégorie d'une culture PAC et indicateur « groupe reconnu »."""
    groupe = normaliser(libelle_groupe)
    culture = normaliser(libelle_culture)
    for debut, categorie in GROUPES_PAC:
        if groupe.startswith(debut):
            if debut in GROUPES_PAC_HETEROGENES:
                for mot, exception in EXCEPTIONS_PAC:
                    if mot in culture:
                        return exception, True
            return categorie, True
    return AUTRES, False


def classer_pac(ref: pd.DataFrame) -> pd.DataFrame:
    """Ajoute `categorie` au référentiel PAC (colonnes de l'IGN, casse libre)."""
    colonnes = {c.lower(): c for c in ref.columns}
    requis = ("code_culture", "libelle_culture", "libelle_groupe_culture")
    manquantes = [c for c in requis if c not in colonnes]
    if manquantes:
        raise ValueError(f"référentiel PAC : colonnes manquantes {manquantes}")
    sortie = pd.DataFrame(
        {
            "code_culture": ref[colonnes["code_culture"]].astype(str).str.strip(),
            "libelle_culture": ref[colonnes["libelle_culture"]],
            "groupe": ref[colonnes["libelle_groupe_culture"]],
        }
    )
    resultats = [categorie_pac(g, c) for g, c in zip(sortie.groupe, sortie.libelle_culture)]
    sortie["categorie"] = [r[0] for r in resultats]
    sortie["groupe_reconnu"] = [r[1] for r in resultats]
    return sortie.drop_duplicates("code_culture")


# --- Référentiel CPFBIO (liste-cultures-cpfbio.xlsx, onglet CPFBIO) ---------

GROUPES_CPFBIO = (
    ("grandes cultures", CEREALES),
    ("fruits", FRUITS),
    ("legumes", MARAICHAGE),
    ("viticulture", VIGNES),
    ("plantes a parfum", PPAM),
    ("autres surfaces", AUTRES),
    ("inconnu", AUTRES),
)
EXCEPTIONS_CPFBIO = (
    ("semences de cereales", CEREALES),
    ("semences de riz", CEREALES),
    ("plants et semences potagers", MARAICHAGE),
    ("semences potageres", MARAICHAGE),
    ("semences fruitieres", FRUITS),
    ("semences de plantes fourrageres", FOURRAGE),
    ("cueillette de ppam", PPAM),
)


def categorie_cpfbio(groupe: object, sous_groupe: object, libelle: object) -> tuple[str, bool]:
    """Catégorie d'une culture CPFBIO et indicateur « groupe reconnu »."""
    g, sg, lbl = normaliser(groupe), normaliser(sous_groupe), normaliser(libelle)
    if g.startswith("surfaces fourrageres"):
        if "prairie" in sg or "parcours" in sg:
            return PRAIRIES, True
        return FOURRAGE, True
    for debut, categorie in GROUPES_CPFBIO:
        if g.startswith(debut):
            if categorie == AUTRES:
                for mot, exception in EXCEPTIONS_CPFBIO:
                    if mot in lbl:
                        return exception, True
            return categorie, True
    return AUTRES, False


def classer_cpfbio(ref: pd.DataFrame) -> pd.DataFrame:
    """Ajoute `categorie` à la liste CPFBIO."""
    colonnes = {normaliser(c).replace(" ", "_"): c for c in ref.columns}
    requis = ("groupe", "sous_groupe", "lbl_production", "code_production")
    manquantes = [c for c in requis if c not in colonnes]
    if manquantes:
        raise ValueError(f"référentiel CPFBIO : colonnes manquantes {manquantes}")
    sortie = pd.DataFrame(
        {
            "code_production": ref[colonnes["code_production"]].astype(str).str.strip(),
            "lbl_production": ref[colonnes["lbl_production"]],
            "groupe": ref[colonnes["groupe"]],
            "sous_groupe": ref[colonnes["sous_groupe"]],
        }
    )
    resultats = [
        categorie_cpfbio(g, sg, lbl)
        for g, sg, lbl in zip(sortie.groupe, sortie.sous_groupe, sortie.lbl_production)
    ]
    sortie["categorie"] = [r[0] for r in resultats]
    sortie["groupe_reconnu"] = [r[1] for r in resultats]
    return sortie.drop_duplicates("code_production")


def lire_ref_pac(chemin) -> pd.DataFrame:
    """Lit le CSV de l'IGN, dont le séparateur et l'encodage varient selon les années."""
    for encodage in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(chemin, sep=None, engine="python", dtype=str, encoding=encodage)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"encodage illisible : {chemin}")


def lire_ref_cpfbio(chemin) -> pd.DataFrame:
    if str(chemin).endswith(".csv"):
        return pd.read_csv(chemin, dtype=str)
    return pd.read_excel(chemin, sheet_name="CPFBIO", dtype=str)
