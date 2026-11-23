"""Classement des cultures des deux référentiels dans 8 catégories communes.

Pourquoi ? Le RPG et CartoBio décrivent les cultures avec deux listes de
codes différentes (codes PAC d'un côté, codes CPFBIO de l'autre). Pour les
comparer et les additionner, chaque code est rangé dans l'une des 8 mêmes
catégories (céréales, prairies, vignes...).

Comment ? Les règles reprennent la classification de docs/METHODOLOGIE.md :
1. chaque groupe de cultures est rattaché à une catégorie (ex. le groupe PAC
   « Blé tendre » va dans « Céréales et oléoprotéagineux ») ;
2. dans les groupes fourre-tout (« Divers », « Autres surfaces »...), quelques
   cultures sont reclassées une par une grâce à un mot de leur libellé (ex.
   « lavande » va dans les plantes à parfum) ;
3. ce qui ne correspond à rien va dans « Autres ».

Les règles portent sur les libellés (le texte) plutôt que sur les codes :
elles restent valables quand une nouvelle année ajoute des codes.
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
    """Simplifie un texte pour comparer des libellés : minuscules, sans accents.

    Exemple : "  Blé   tendre " devient "ble tendre". Ainsi, une règle écrite
    "ble tendre" reconnaît « Blé tendre », « BLE TENDRE » ou « blé  tendre ».
    """
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
    """Catégorie d'une culture PAC, et un booléen : le groupe est-il connu des règles ?

    Exemple : categorie_pac("Autres cultures industrielles", "Lavande")
    renvoie ("Plantes à parfum, aromatiques et médicinales", True).
    """
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
    """Classe tout le référentiel PAC : ajoute les colonnes `categorie` et `groupe_reconnu`.

    `ref` est le CSV de l'IGN lu par lire_ref_pac. Les noms de colonnes sont
    cherchés sans tenir compte des majuscules.
    """
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
    """Catégorie d'une culture CPFBIO, et un booléen : le groupe est-il connu des règles ?

    Particularité : le groupe « Surfaces fourragères » est partagé selon le
    sous-groupe, entre « Prairies » (prairies, parcours) et « Cultures fourragères ».
    """
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
    """Classe toute la liste CPFBIO : ajoute les colonnes `categorie` et `groupe_reconnu`."""
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
    """Lit le CSV des cultures PAC de l'IGN.

    sep=None laisse pandas deviner le séparateur (« ; » ou « , »). Si le
    fichier n'est pas en UTF-8, on réessaie en latin-1, l'autre encodage
    courant des fichiers français.
    """
    for encodage in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(chemin, sep=None, engine="python", dtype=str, encoding=encodage)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"encodage illisible : {chemin}")


def lire_ref_cpfbio(chemin) -> pd.DataFrame:
    """Lit la liste CPFBIO : un CSV, ou l'onglet « CPFBIO » du fichier Excel."""
    if str(chemin).endswith(".csv"):
        return pd.read_csv(chemin, dtype=str)
    return pd.read_excel(chemin, sheet_name="CPFBIO", dtype=str)
