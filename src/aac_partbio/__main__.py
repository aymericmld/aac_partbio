"""Point d'entrée du projet : la commande `python -m aac_partbio`.

Usage : python -m aac_partbio <étape> [--annee AAAA] [options]

Les étapes, dans l'ordre où elles s'enchaînent :
  charger    copie les fichiers sources dans PostgreSQL (chargement.py)
  traiter    exécute les scripts SQL 01 à 07 (traitement.py)
  controler  vérifie la cohérence des résultats (qualite.py)
  exporter   écrit les CSV et les données de la page web (export.py)
  tout       les quatre étapes à la suite
  demo       fabrique de fausses données et lance tout dessus (demo.py)

Ce fichier ne contient pas de calcul : il lit les options tapées par
l'utilisateur et appelle les modules dans le bon ordre.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import chargement, demo, export, qualite, traitement
from .config import PROCESSED, RAW, Sources, sources_par_defaut


def _sources(args: argparse.Namespace) -> Sources:
    """Chemins des fichiers sources : ceux passés en option, sinon les chemins par défaut."""
    defaut = sources_par_defaut(args.annee, RAW / "demo" if args.demo else RAW)
    return Sources(
        rpg=Path(args.rpg) if args.rpg else defaut.rpg,
        bio=Path(args.bio) if args.bio else defaut.bio,
        aac=Path(args.aac) if args.aac else defaut.aac,
        ref_pac=Path(args.ref_pac) if args.ref_pac else defaut.ref_pac,
        ref_cpfbio=Path(args.ref_cpfbio) if args.ref_cpfbio else defaut.ref_cpfbio,
    )


def main(argv: list[str] | None = None) -> None:
    # argparse décrit les options acceptées et produit l'aide affichée par
    # `python -m aac_partbio --help`.
    parser = argparse.ArgumentParser(prog="aac_partbio", description=__doc__)
    parser.add_argument(
        "etape", choices=("demo", "charger", "traiter", "controler", "exporter", "tout")
    )
    parser.add_argument("--annee", type=int, default=2025, help="millésime du RPG (défaut 2025)")
    parser.add_argument("--demo", action="store_true", help="utiliser le jeu synthétique")
    parser.add_argument("--sans-aac", action="store_true", help="ne pas recharger les AAC")
    parser.add_argument("--depuis", type=int, default=1, help="reprendre au script SQL n°")
    parser.add_argument("--gpkg", action="store_true", help="exporter aussi les parcelles en GPKG")
    for nom in ("rpg", "bio", "aac", "ref-pac", "ref-cpfbio"):
        parser.add_argument(f"--{nom}", help=f"chemin du fichier {nom} (sinon data/raw)")
    args = parser.parse_args(argv)

    if args.etape == "demo":
        # Deux millésimes synthétiques, pour montrer aussi l'évolution sur le site.
        args.demo = True
        # Les sorties de démonstration restent à part des vrais résultats.
        qualite.PROCESSED = export.PROCESSED = PROCESSED / "demo"
        for annee in (2024, 2025):
            args.annee = annee
            demo.generer(annee)
            chargement.charger(annee, _sources(args), avec_aac=annee == 2024)
            traitement.traiter(annee)
            qualite.controler(annee)
        export.exporter(demo=True)
        return
    # Chaque bloc ci-dessous s'exécute si l'étape demandée le concerne :
    # « tout » passe donc dans les quatre.
    if args.etape in ("charger", "tout"):
        chargement.charger(args.annee, _sources(args), avec_aac=not args.sans_aac)
    if args.etape in ("traiter", "tout"):
        traitement.traiter(args.annee, depuis=args.depuis)
        # Si le RPG a été pré-filtré autour des AAC, la part bio « France » se
        # reprend du fichier de statistiques calculé sur le RPG complet.
        chargement.appliquer_stats_nationales(args.annee, _sources(args))
    if args.etape in ("controler", "tout"):
        qualite.controler(args.annee)
    if args.etape in ("exporter", "tout"):
        export.exporter(demo=args.demo, gpkg=args.annee if args.gpkg else None)


if __name__ == "__main__":
    main()
