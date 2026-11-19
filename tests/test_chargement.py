from aac_partbio.chargement import choisir_colonne, expression_bio
from aac_partbio.config import COLONNES_RPG


def test_choisir_colonne_respecte_l_ordre_de_preference():
    assert choisir_colonne(["fid", "id_parcel", "geom"], COLONNES_RPG["id"]) == "id_parcel"
    assert choisir_colonne(["fid", "geom"], COLONNES_RPG["id"]) == "fid"


def test_choisir_colonne_ignore_la_casse_et_renvoie_le_nom_reel():
    assert choisir_colonne(["CODE_CULTU"], COLONNES_RPG["culture"]) == "CODE_CULTU"


def test_choisir_colonne_absente():
    assert choisir_colonne(["geom"], COLONNES_RPG["bio"]) is None


def test_expression_bio_sans_colonne():
    assert expression_bio(None) == "NULL::boolean"


def test_expression_bio_avec_colonne():
    expression = expression_bio("bio")
    assert expression.startswith('(lower(trim(ign."bio"::text)) IN (')
    assert "'oui'" in expression and "'true'" in expression
