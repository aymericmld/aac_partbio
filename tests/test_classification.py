import pandas as pd
import pytest

from aac_partbio import classification as c


def test_normaliser_retire_accents_et_espaces():
    assert c.normaliser("  Blé   tendre ") == "ble tendre"
    assert c.normaliser(None) == ""
    assert c.normaliser(float("nan")) == ""


@pytest.mark.parametrize(
    "groupe, culture, attendu",
    [
        ("Blé tendre", "Blé tendre d'hiver", c.CEREALES),
        ("Maïs grain et ensilage", "Maïs ensilage", c.CEREALES),
        ("Prairies temporaires", "Autre prairie temporaire", c.PRAIRIES),
        ("Légumes ou fleurs", "Carotte", c.MARAICHAGE),
        ("Légumineuses à grains", "Lentille", c.CEREALES),
        ("Fruits à coque", "Noyer", c.FRUITS),
        ("Gel (surfaces gelées sans production)", "Jachère", c.AUTRES),
        ("Autres cultures industrielles", "Lavande / Lavandin", c.PPAM),
        ("Autres cultures industrielles", "Houblon", c.PPAM),
        ("Autres cultures industrielles", "Betterave non fourragère", c.AUTRES),
        ("Divers", "Cameline", c.CEREALES),
        ("Divers", "Bordure de champ", c.AUTRES),
    ],
)
def test_categorie_pac(groupe, culture, attendu):
    categorie, reconnu = c.categorie_pac(groupe, culture)
    assert categorie == attendu
    assert reconnu


def test_exceptions_limitees_aux_groupes_heterogenes():
    # « Persil » dans un groupe homogène garde la catégorie du groupe.
    assert c.categorie_pac("Légumes ou fleurs", "Persil")[0] == c.MARAICHAGE


def test_groupe_pac_inconnu_signale():
    assert c.categorie_pac("Groupe inventé", "Culture") == (c.AUTRES, False)


@pytest.mark.parametrize(
    "groupe, sous_groupe, libelle, attendu",
    [
        ("Grandes Cultures", "Céréales", "Blé tendre", c.CEREALES),
        ("Surfaces fourragères", "Prairies, parcours", "Prairie permanente", c.PRAIRIES),
        ("Surfaces fourragères", "Plantes fourragères", "Luzerne", c.FOURRAGE),
        ("Fruits", "Fruits à pépins", "Pommier", c.FRUITS),
        ("Viticulture", "Vignes", "Raisin de cuve", c.VIGNES),
        ("Plantes à parfums, aromatiques et médicinales et plantes à boissons", "", "Thym", c.PPAM),
        (
            "Autres surfaces",
            "Semences",
            "Semences de céréales, légumineuses et oléagineux",
            c.CEREALES,
        ),
        ("Autres surfaces", "Semences", "Plants et semences potagers", c.MARAICHAGE),
        ("Autres surfaces", "", "Zone de cueillette de PPAM", c.PPAM),
        ("Autres surfaces", "", "Bois", c.AUTRES),
        ("Inconnu", "", "Inconnu", c.AUTRES),
    ],
)
def test_categorie_cpfbio(groupe, sous_groupe, libelle, attendu):
    assert c.categorie_cpfbio(groupe, sous_groupe, libelle)[0] == attendu


def test_classer_pac_toutes_les_lignes_ont_une_categorie():
    ref = pd.DataFrame(
        {
            "CODE_CULTURE": ["BTH", "LAV", "XXX", "BTH"],
            "LIBELLE_CULTURE": ["Blé tendre d'hiver", "Lavande", "Inconnue", "Doublon"],
            "CODE_GROUPE_CULTURE": ["1", "24", "99", "1"],
            "LIBELLE_GROUPE_CULTURE": ["Blé tendre", "Autres cultures industrielles", "?", "Blé"],
        }
    )
    sortie = c.classer_pac(ref)
    assert list(sortie.code_culture) == ["BTH", "LAV", "XXX"]
    assert sortie.categorie.isin(c.CATEGORIES).all()
    assert not sortie.set_index("code_culture").loc["XXX", "groupe_reconnu"]


def test_classer_pac_refuse_colonnes_manquantes():
    with pytest.raises(ValueError, match="colonnes manquantes"):
        c.classer_pac(pd.DataFrame({"CODE_CULTURE": ["BTH"]}))


def test_classer_cpfbio_accepte_la_colonne_precisions_accentuee():
    ref = pd.DataFrame(
        {
            "groupe": ["Fruits"],
            "sous_groupe": ["Agrumes"],
            "lbl_production": ["Citron"],
            "code_production": [" 01.23.1 "],
            "précisions": [None],
        }
    )
    sortie = c.classer_cpfbio(ref)
    assert sortie.iloc[0].code_production == "01.23.1"
    assert sortie.iloc[0].categorie == c.FRUITS
