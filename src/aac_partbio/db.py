"""Petits outils pour parler à la base PostgreSQL.

Le projet utilise deux façons d'envoyer du SQL :
- psql, l'outil en ligne de commande de PostgreSQL, pour exécuter les scripts
  du dossier sql/ (fonction executer_sql) ;
- psycopg, la bibliothèque Python de PostgreSQL, pour les requêtes courtes
  dont on veut récupérer le résultat en Python (fonction requete).

Où trouver la base ? Les deux outils lisent les mêmes variables
d'environnement : PGHOST (adresse du serveur), PGPORT, PGDATABASE (nom de la
base), PGUSER et PGPASSWORD. Pour ne pas les taper à chaque fois, on les écrit
dans un fichier .env à la racine du dépôt (modèle : .env.example).
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pandas as pd
import psycopg

from .config import ROOT, SCHEMA, SQL


def charger_env(chemin: Path = ROOT / ".env") -> None:
    """Lit le fichier .env et place ses valeurs dans les variables d'environnement.

    Chaque ligne « CLE=valeur » devient une variable. Les lignes vides ou qui
    commencent par # sont ignorées. setdefault ne remplace pas une variable
    déjà définie : une valeur tapée dans le terminal reste prioritaire.
    """
    if not chemin.exists():
        return
    for ligne in chemin.read_text().splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            cle, valeur = ligne.split("=", 1)
            os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


def connexion() -> psycopg.Connection:
    """Ouvre une connexion à la base.

    autocommit=True : chaque requête est enregistrée aussitôt exécutée, sans
    avoir à valider une transaction à la main.
    """
    charger_env()
    return psycopg.connect(autocommit=True)


def chaine_ogr() -> str:
    """Adresse de la base au format attendu par ogr2ogr.

    ogr2ogr (l'outil de chargement des fichiers géographiques) veut une chaîne
    du type « PG:host=localhost dbname=ma_base user=moi ». On la construit à
    partir des mêmes variables PG* que psql.
    """
    charger_env()
    cles = {
        "host": "PGHOST",
        "port": "PGPORT",
        "dbname": "PGDATABASE",
        "user": "PGUSER",
        "password": "PGPASSWORD",
    }
    morceaux = [f"{k}={os.environ[v]}" for k, v in cles.items() if os.environ.get(v)]
    return "PG:" + " ".join(morceaux)


def executer_sql(fichier: str, variables: dict[str, object]) -> float:
    """Exécute un script du dossier sql/ avec psql et renvoie sa durée en secondes.

    La commande construite ressemble à :
        psql -X -q -v ON_ERROR_STOP=1 -v annee=2025 -v schema=aac_partbio ... -f sql/01_aac_emprise.sql
    -X           ignore la configuration personnelle de psql ;
    -q           mode silencieux ;
    ON_ERROR_STOP=1  arrête le script à la première erreur, au lieu de continuer
                 sur des tables incomplètes ;
    -v nom=val   donne sa valeur à la variable :nom du script ;
    -f fichier   le script à exécuter.
    """
    charger_env()
    commande = ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1"]
    for cle, valeur in variables.items():
        commande += ["-v", f"{cle}={valeur}"]
    commande += ["-f", str(SQL / fichier)]
    # N'afficher que les avertissements et les erreurs, pas les messages
    # d'information de PostgreSQL (« la table n'existe pas, ignorée »...).
    env = {**os.environ, "PGOPTIONS": "-c client_min_messages=warning"}
    debut = time.perf_counter()
    # check=True : si psql échoue, Python lève une erreur et le programme s'arrête.
    subprocess.run(commande, check=True, env=env)
    return time.perf_counter() - debut


def requete(sql: str, params: tuple | dict | None = None) -> pd.DataFrame:
    """Exécute une requête et renvoie son résultat sous forme de tableau pandas.

    Les valeurs variables se passent dans `params`, jamais collées dans le
    texte de la requête : dans le SQL, %s marque leur place, et psycopg les
    insère de façon sûre. Exemple :
        requete("SELECT * FROM t WHERE annee = %s", (2025,))
    """
    with connexion() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return pd.DataFrame()
        colonnes = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=colonnes)


def executer_requete_simple(sql: str) -> None:
    """Exécute une commande sans résultat à lire (CREATE, UPDATE...)."""
    with connexion() as conn:
        conn.execute(sql)


def colonnes(table: str, schema: str = SCHEMA) -> list[str]:
    """Noms des colonnes d'une table, ou liste vide si la table n'existe pas.

    information_schema.columns est une vue de PostgreSQL qui décrit toutes les
    colonnes de toutes les tables de la base.
    """
    df = requete(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
        (schema, table),
    )
    return df.column_name.tolist()


def table_existe(table: str, schema: str = SCHEMA) -> bool:
    """Vrai si la table existe (elle a au moins une colonne)."""
    return bool(colonnes(table, schema))
