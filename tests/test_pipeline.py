"""Test d'intégration : scénario d'appariement construit à la main.

Nécessite un PostgreSQL avec PostGIS (variables PG* ou fichier .env). Le test
crée une base dédiée `aac_partbio_test` et l'ignore si le serveur est absent.
Toutes les parcelles mesurent 100 m x 100 m, soit 1 ha.

    x (m) : 0    100  200  300  400  500  600  700  800  900  1000 1050
    RPG   : [ A ]     [   B   ] [ C ]               [ E ]   [  F  ]
    Bio   :  [a1]     [b1][b2]     [c1]   [d1]
    AAC   : T1 de 0 à 1000 ; T2 de 900 à 1400 (chevauche T1 sur 100 m)
"""

from __future__ import annotations

import pandas as pd
import psycopg
import pytest

from aac_partbio import classification, db, qualite, traitement
from aac_partbio.chargement import charger_referentiel
from aac_partbio.config import SCHEMA

BASE_TEST = "aac_partbio_test"
X0, Y0 = 700_000, 6_600_000
ANNEE = 2099


def carre(x0, x1, y0=0, y1=100):
    return f"ST_Multi(ST_MakeEnvelope({X0 + x0}, {Y0 + y0}, {X0 + x1}, {Y0 + y1}, 2154))"


@pytest.fixture(scope="module")
def base(request):
    db.charger_env()
    try:
        with psycopg.connect(autocommit=True, connect_timeout=3) as conn:
            existe = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (BASE_TEST,)
            ).fetchone()
            if not existe:
                conn.execute(f'CREATE DATABASE "{BASE_TEST}"')
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL indisponible")
    mp = pytest.MonkeyPatch()
    mp.setenv("PGDATABASE", BASE_TEST)
    request.addfinalizer(mp.undo)

    with db.connexion() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        conn.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE')
        conn.execute(f'CREATE SCHEMA "{SCHEMA}"')
        s = SCHEMA
        conn.execute(
            f"""CREATE TABLE "{s}".src_aac AS
                SELECT 'T1'::text AS cdaac, 'AAC test 1'::text AS nomaac,
                       {carre(0, 1000, -500, 500)} AS geom
                UNION ALL
                SELECT 'T2', 'AAC test 2', {carre(900, 1400, -500, 500)}"""
        )
        conn.execute(
            f"""CREATE TABLE "{s}".src_rpg_{ANNEE} AS
                SELECT * FROM (VALUES
                    ('A', 'BTH', 1.0, 'Non', {carre(0, 100)}),
                    ('B', 'BTH', 1.0, 'Non', {carre(200, 300)}),
                    ('C', 'BTH', 1.0, 'Non', {carre(400, 500)}),
                    ('E', 'PPH', 1.0, 'Oui', {carre(800, 900)}),
                    ('F', 'PPH', 1.0, 'Non', {carre(950, 1050)}),
                    ('G', 'BTH', 1.0, 'Non', {carre(5000, 5100)})
                ) v(id_parcel, code_cultu, surf_parc, bio, geom)"""
        )
        conn.execute(
            f"""CREATE TABLE "{s}".src_bio_{ANNEE} AS
                SELECT * FROM (VALUES
                    (1, '01.11.11', 'AB', 1.0, {carre(3, 103)}),
                    (2, '01.11.11', 'C1', 0.5, {carre(200, 250)}),
                    (3, '01.11.11,01.19.22', 'AB', 0.5, {carre(250, 300)}),
                    (4, '01.11.11', 'C2', 1.0, {carre(480, 580)}),
                    (5, '01.19.21', 'AB', 1.0, {carre(600, 700)})
                ) v(fid, culture, convers, surface, geom)"""
        )
    pac = classification.classer_pac(
        pd.DataFrame(
            {
                "CODE_CULTURE": ["BTH", "PPH"],
                "LIBELLE_CULTURE": ["Blé tendre d'hiver", "Prairie permanente"],
                "LIBELLE_GROUPE_CULTURE": ["Blé tendre", "Prairies permanentes"],
            }
        )
    )
    cpfbio = classification.classer_cpfbio(
        pd.DataFrame(
            {
                "groupe": ["Grandes Cultures", "Surfaces fourragères"],
                "sous_groupe": ["Céréales", "Prairies, parcours"],
                "lbl_production": ["Blé tendre", "Prairie permanente"],
                "code_production": ["01.11.11", "01.19.21"],
            }
        )
    )
    charger_referentiel(pac.drop(columns="groupe_reconnu"), "ref_cultures_pac")
    charger_referentiel(cpfbio.drop(columns="groupe_reconnu"), "ref_cultures_cpfbio")
    traitement.traiter(ANNEE)
    return SCHEMA


def test_sources_des_parcelles(base):
    df = db.requete(
        f'SELECT id_parcel, source, conversion, bio FROM "{base}".parcel WHERE annee = %s',
        (ANNEE,),
    ).set_index("id_parcel")
    assert df.source.to_dict() == {
        "AB1": "cartobio_rpg",  # décalée de 3 m : appariée à A
        "AB2": "cartobio_rpg",  # B découpée en deux dans CartoBio
        "AB3": "cartobio_rpg",
        "AB4": "cartobio_hors_rpg",  # ne recouvre C qu'à 20 %
        "AB5": "cartobio_hors_rpg",  # absente du RPG
        "C": "rpg",
        "E": "rpg",
        "F": "rpg",
    }
    assert df.loc["E", "conversion"] == "BIO_PAC"
    assert bool(df.loc["E", "bio"])
    assert df.loc["C", "conversion"] == "CONV"
    assert df.loc["AB2", "conversion"] == "C1"


def test_multiculture_prend_la_premiere_culture(base):
    df = db.requete(
        f"SELECT categorie FROM \"{base}\".parcel WHERE annee = %s AND id_parcel = 'AB3'",
        (ANNEE,),
    )
    assert df.categorie.iat[0] == classification.CEREALES


def test_parcelle_hors_emprise_exclue(base):
    df = db.requete(f'SELECT id_source FROM "{base}".rpg_ign_{ANNEE}')
    assert "G" not in set(df.id_source)


def test_double_compte_entre_aac_evite(base):
    pa = db.requete(
        f'SELECT cdaac, surface_dans_aac_ha FROM "{base}".parcel_aac '
        f"WHERE annee = %s AND id_parcel = 'F' ORDER BY cdaac",
        (ANNEE,),
    )
    assert pa.surface_dans_aac_ha.round(3).tolist() == [0.5, 1.0]
    d = db.requete(
        f'SELECT surface_dans_aac_ha FROM "{base}".parcel_dans_aac '
        f"WHERE annee = %s AND id_parcel = 'F'",
        (ANNEE,),
    )
    assert round(d.surface_dans_aac_ha.iat[0], 3) == 1.0


def test_synthese_nationale(base):
    n = db.requete(f'SELECT * FROM "{base}".synthese_nationale WHERE annee = %s', (ANNEE,))
    ligne = n.iloc[0]
    # a1 (1 ha) + b1, b2 (1 ha) + C + c1 + d1 + E + F (1 ha une seule fois) = 7 ha
    assert round(ligne.sau_aac_ha, 3) == 7.0
    assert round(ligne.sau_bio_aac_ha, 3) == 5.0
    assert ligne.nb_aac == 2


def test_controles_qualite(base):
    assert qualite.controles_bloquants(ANNEE) == []
    rapport = qualite.diagnostics(ANNEE)
    assert rapport["taux_appariement_bio"] == pytest.approx(3 / 5)
    assert rapport["chevauchement_residuel_ha"] == pytest.approx(0.2)
