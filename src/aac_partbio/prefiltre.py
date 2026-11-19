"""Pré-filtrage des sources volumineuses autour des AAC, sans PostgreSQL.

Le RPG France entière dépasse 6 Go. Sur une machine modeste, ou pour déplacer
les données, ce module ne garde que les parcelles qui touchent l'emprise des
AAC (tampon compris), en lisant le GeoPackage par carreaux grâce à son index
spatial. Il calcule au passage, sur le fichier complet, la part de surface
constatée bio du RPG, qui sert de point de comparaison national.

    python -m aac_partbio.prefiltre --rpg RPG_Parcelles.gpkg --bio cartobio.gpkg \
        --aac AAC.gpkg --sortie data/raw/2025

Dépendances supplémentaires : pyogrio, shapely, geopandas (extra `prefiltre`).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pyogrio
import shapely

from .config import BUFFER_M

CARREAU_M = 20_000


def emprise_aac(chemin_aac: Path, etendue: tuple[float, float, float, float]):
    """AAC en Lambert 93 limitées à l'étendue du RPG, et leur emprise tamponnée."""
    aac = gpd.read_file(chemin_aac).to_crs(2154)
    aac["geometry"] = aac.geometry.make_valid()
    cadre = shapely.box(*etendue)
    aac = aac[aac.intersects(cadre)].copy()
    emprise = shapely.union_all(aac.buffer(BUFFER_M).values)
    return aac, emprise


def carreaux(emprise) -> list:
    xmin, ymin, xmax, ymax = emprise.bounds
    grille = [
        shapely.box(x, y, x + CARREAU_M, y + CARREAU_M)
        for x in np.arange(xmin, xmax, CARREAU_M)
        for y in np.arange(ymin, ymax, CARREAU_M)
    ]
    return [c for c in grille if c.intersects(emprise)]


def filtrer(source: Path, emprise, sortie: Path, cle: str, par_fichier: int = 400_000) -> int:
    """Copie les entités de `source` qui intersectent l'emprise, en Lambert 93.

    La sortie est découpée en fichiers `<sortie>_NN.gpkg` d'au plus `par_fichier`
    entités, plus faciles à transférer qu'un seul gros fichier.
    """
    crs = pyogrio.read_info(source)["crs"]
    reprojeter = crs != "EPSG:2154"

    def vers_source(geom):
        return gpd.GeoSeries([geom], crs=2154).to_crs(crs).iloc[0] if reprojeter else geom

    index = shapely.STRtree(list(shapely.get_parts(shapely.make_valid(vers_source(emprise)))))
    for ancien in sortie.parent.glob(f"{sortie.stem}_*.gpkg"):
        ancien.unlink()
    vus: set[str] = set()
    total, numero, dans_fichier = 0, 1, 0
    for i, carreau in enumerate(carreaux(emprise)):
        df = pyogrio.read_dataframe(source, bbox=vers_source(carreau).bounds)
        if df.empty:
            continue
        df = df[~df[cle].astype(str).isin(vus)]
        touche = index.query(df.geometry.values, predicate="intersects")
        df = df.iloc[np.unique(touche[0])]
        if df.empty:
            continue
        vus.update(df[cle].astype(str))
        if reprojeter:
            df = df.to_crs(2154)
        if dans_fichier >= par_fichier:
            numero, dans_fichier = numero + 1, 0
        fichier = sortie.parent / f"{sortie.stem}_{numero:02d}.gpkg"
        pyogrio.write_dataframe(df, fichier, layer=sortie.stem, append=fichier.exists())
        total += len(df)
        dans_fichier += len(df)
        if i % 50 == 0:
            print(f"  {source.name} : carreau {i}, {total} entités retenues", flush=True)
    print(f"{source.name} -> {numero} fichier(s) {sortie.stem}_NN.gpkg : {total} entités")
    return total


def stats_rpg(source: Path) -> dict:
    """Part de surface constatée bio sur tout le RPG (sans géométrie)."""
    df = pyogrio.read_dataframe(source, columns=["surf_parc", "bio"], read_geometry=False)
    surface = float(df.surf_parc.sum())
    bio = float(df.loc[df.bio.astype(bool), "surf_parc"].sum())
    return {"nb_parcelles": len(df), "surface_ha": surface, "part_bio_pac_france": bio / surface}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpg", required=True, type=Path)
    parser.add_argument("--bio", required=True, type=Path)
    parser.add_argument("--aac", required=True, type=Path)
    parser.add_argument("--sortie", required=True, type=Path)
    args = parser.parse_args(argv)
    args.sortie.mkdir(parents=True, exist_ok=True)

    etendue = pyogrio.read_info(args.rpg)["total_bounds"]
    aac, emprise = emprise_aac(args.aac, tuple(etendue))
    aac_sortie = args.sortie / "aac.gpkg"
    if aac_sortie.exists():
        aac_sortie.unlink()
    aac.to_file(aac_sortie, layer="aac")
    print(f"{len(aac)} AAC dans l'étendue du RPG")

    stats = stats_rpg(args.rpg)
    (args.sortie / "rpg_stats_nationales.json").write_text(json.dumps(stats, indent=1))
    print("statistiques nationales :", stats)

    filtrer(args.rpg, emprise, args.sortie / "rpg_parcelles.gpkg", cle="id_parcel")
    filtrer(args.bio, emprise, args.sortie / "cartobio.gpkg", cle="id")


if __name__ == "__main__":
    main()
