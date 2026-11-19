"""Accès à PostgreSQL : psql pour les scripts SQL, psycopg pour les requêtes.

La connexion suit les variables standard de libpq (PGHOST, PGPORT, PGDATABASE,
PGUSER, PGPASSWORD), lues aussi dans un fichier .env à la racine du dépôt.
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
    """Complète l'environnement avec le fichier .env, sans écraser l'existant."""
    if not chemin.exists():
        return
    for ligne in chemin.read_text().splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            cle, valeur = ligne.split("=", 1)
            os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


def connexion() -> psycopg.Connection:
    charger_env()
    return psycopg.connect(autocommit=True)


def chaine_ogr() -> str:
    """Chaîne de connexion PG: pour ogr2ogr, construite depuis les variables libpq."""
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
    """Exécute un script de sql/ avec psql et renvoie sa durée en secondes."""
    charger_env()
    commande = ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1"]
    for cle, valeur in variables.items():
        commande += ["-v", f"{cle}={valeur}"]
    commande += ["-f", str(SQL / fichier)]
    env = {**os.environ, "PGOPTIONS": "-c client_min_messages=warning"}
    debut = time.perf_counter()
    subprocess.run(commande, check=True, env=env)
    return time.perf_counter() - debut


def requete(sql: str, params: tuple | dict | None = None) -> pd.DataFrame:
    with connexion() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return pd.DataFrame()
        colonnes = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=colonnes)


def executer_requete_simple(sql: str) -> None:
    with connexion() as conn:
        conn.execute(sql)


def colonnes(table: str, schema: str = SCHEMA) -> list[str]:
    df = requete(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
        (schema, table),
    )
    return df.column_name.tolist()


def table_existe(table: str, schema: str = SCHEMA) -> bool:
    return bool(colonnes(table, schema))
