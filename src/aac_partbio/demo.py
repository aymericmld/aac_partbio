"""Jeu de données synthétique au format des vraies sources.

Il sert à tester la chaîne de bout en bout et à prévisualiser le site sans
télécharger plusieurs gigaoctets. Les AAC, parcelles et cultures sont
inventées : aucun chiffre issu de ce jeu ne décrit la réalité.
"""

from __future__ import annotations

import json
import math
import random
import subprocess
from pathlib import Path

import pandas as pd

from .config import RAW, Sources

# Culture PAC : (libellé, code groupe, libellé groupe, code CPFBIO équivalent
#                [, groupe CPFBIO s'il diffère du groupe PAC])
CULTURES = {
    "BTH": ("Blé tendre d'hiver", "1", "Blé tendre", "01.11.11"),
    "MIS": ("Maïs", "2", "Maïs grain et ensilage", "01.11.31"),
    "MIE": ("Maïs ensilage", "2", "Maïs grain et ensilage", "01.19.11"),
    "ORH": ("Orge d'hiver", "3", "Orge", "01.11.41"),
    "CZH": ("Colza d'hiver", "5", "Colza", "01.11.91"),
    "TRN": ("Tournesol", "6", "Tournesol", "01.11.92"),
    "LUZ": ("Luzerne", "16", "Fourrage", "01.19.12"),
    "PPH": ("Prairie permanente - herbe prédominante", "18", "Prairies permanentes", "01.19.21"),
    "PTR": ("Autre prairie temporaire de 5 ans ou moins", "19", "Prairies temporaires", "01.19.22"),
    "VRG": ("Verger", "20", "Vergers", "01.24.10"),
    "VRC": ("Vigne : raisins de cuve", "21", "Vignes", "01.21.12"),
    "LAV": ("Lavande / Lavandin", "24", "Autres cultures industrielles", "01.28.15", "ppam"),
    "BTN": ("Betterave non fourragère", "24", "Autres cultures industrielles", "01.13.71"),
    "PTC": ("Pomme de terre de consommation", "25", "Légumes ou fleurs", "01.13.51"),
    "J6P": ("Jachère de 6 ans ou plus", "11", "Gel (surfaces gelées sans production)", "01.99.01"),
}
CPFBIO_GROUPES = {
    "1": ("Grandes Cultures", "Céréales"),
    "2": ("Grandes Cultures", "Céréales"),
    "3": ("Grandes Cultures", "Céréales"),
    "5": ("Grandes Cultures", "Oléagineux"),
    "6": ("Grandes Cultures", "Oléagineux"),
    "16": ("Surfaces fourragères", "Plantes fourragères"),
    "18": ("Surfaces fourragères", "Prairies, parcours"),
    "19": ("Surfaces fourragères", "Prairies, parcours"),
    "20": ("Fruits", "Fruits à pépins"),
    "21": ("Viticulture", "Vignes"),
    "24": ("Autres surfaces", "Cultures industrielles"),
    "ppam": ("Plantes à parfums, aromatiques et médicinales et plantes à boissons", "PPAM"),
    "25": ("Légumes", "Légumes de plein champ"),
    "11": ("Autres surfaces", "Jachères"),
}
# Code présent dans le RPG mais absent du référentiel : doit sortir en « Non classé ».
CODE_INCONNU = "ZZZ"

# Territoire : (nom, x, y en Lambert 93, mélange de cultures, part bio)
TERRITOIRES = (
    ("Monts d'Arrée", 175_000, 6_820_000, {"PTR": 3, "PPH": 3, "MIE": 2, "BTH": 1}, 0.14),
    ("Pays de Léon", 160_000, 6_850_000, {"PTC": 3, "PTR": 2, "MIE": 2, "BTH": 2}, 0.08),
    ("Beauce chartraine", 590_000, 6_810_000, {"BTH": 4, "ORH": 2, "CZH": 2, "BTN": 1}, 0.03),
    (
        "Champagne crayeuse",
        780_000,
        6_890_000,
        {"BTH": 3, "ORH": 2, "BTN": 2, "LUZ": 1, "VRC": 1},
        0.05,
    ),
    ("Plaine d'Alsace", 1_030_000, 6_790_000, {"MIS": 5, "BTH": 2, "VRC": 1, "PPH": 1}, 0.07),
    ("Entre-deux-Mers", 425_000, 6_420_000, {"VRC": 6, "PPH": 2, "MIS": 1}, 0.19),
    ("Diois", 880_000, 6_400_000, {"LAV": 2, "VRG": 2, "BTH": 2, "PPH": 2, "VRC": 1}, 0.36),
    ("Pays d'Auge", 500_000, 6_900_000, {"PPH": 5, "PTR": 2, "BTH": 2, "VRG": 1}, 0.11),
    ("Flandre intérieure", 680_000, 7_060_000, {"BTH": 4, "BTN": 2, "PTC": 2, "MIS": 1}, 0.02),
    ("Planèze du Cantal", 680_000, 6_440_000, {"PPH": 7, "PTR": 2}, 0.13),
    ("Coteaux du Gers", 500_000, 6_290_000, {"TRN": 3, "BTH": 3, "MIS": 2, "PPH": 1}, 0.22),
    ("Plateau lorrain", 930_000, 6_870_000, {"BTH": 3, "CZH": 2, "ORH": 2, "PPH": 2}, 0.06),
    ("Bocage vendéen", 370_000, 6_630_000, {"MIS": 3, "BTH": 3, "PTR": 2, "PPH": 1}, 0.10),
)
CONVERSIONS = (("AB", 0.75), ("C1", 0.10), ("C2", 0.08), ("C3", 0.07))


def _cercle_irregulier(rng: random.Random, x: float, y: float, rayon: float) -> list:
    points = []
    n = 28
    for i in range(n):
        angle = 2 * math.pi * i / n
        r = rayon * (0.75 + 0.5 * rng.random())
        points.append([round(x + r * math.cos(angle), 1), round(y + r * math.sin(angle), 1)])
    points.append(points[0])
    return [points]


def _rectangle(x0: float, y0: float, x1: float, y1: float) -> list:
    return [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]


def _ecrire_gpkg(entites: list[dict], chemin: Path, couche: str) -> None:
    geojson = chemin.with_suffix(".geojson")
    geojson.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::2154"}},
                "features": entites,
            }
        )
    )
    subprocess.run(
        [
            "ogr2ogr",
            "-f",
            "GPKG",
            str(chemin),
            str(geojson),
            "-nln",
            couche,
            "-overwrite",
            "-a_srs",
            "EPSG:2154",
        ],
        check=True,
    )
    geojson.unlink()


def _poly(coords: list) -> dict:
    return {"type": "Polygon", "coordinates": coords}


def generer(annee: int = 2025, graine: int = 2025, dossier: Path | None = None) -> Sources:
    # Géométries identiques d'une année à l'autre, attributs propres à l'année.
    rng_geo = random.Random(graine)
    rng = random.Random(graine * 10_000 + annee)
    dossier = dossier or RAW / "demo"
    (dossier / str(annee)).mkdir(parents=True, exist_ok=True)

    aac, rpg, bio = [], [], []
    id_rpg = 0
    numero_aac = 0
    for t, (nom, cx, cy, melange, part_bio) in enumerate(TERRITOIRES):
        codes = list(melange)
        poids = list(melange.values())
        cercles = []
        for k in range(2):
            numero_aac += 1
            # Dans le premier territoire, les deux AAC se superposent volontairement.
            ecart = 3000 if t == 0 else 9000
            x = cx + rng_geo.uniform(-ecart, ecart) if k else cx
            y = cy + rng_geo.uniform(-ecart, ecart) if k else cy
            rayon = rng_geo.uniform(2000, 4200)
            cercles.append((x, y, rayon))
            aac.append(
                {
                    "type": "Feature",
                    "properties": {"cdaac": f"AAC{numero_aac:05d}", "nomaac": f"{nom} {k + 1}"},
                    "geometry": _poly(_cercle_irregulier(rng_geo, x, y, rayon)),
                }
            )
        # Une seule grille de parcelles par territoire, sur l'emprise des deux AAC.
        xmin = min(x - r * 1.25 for x, _, r in cercles) - 700
        xmax = max(x + r * 1.25 for x, _, r in cercles) + 700
        ymin = min(y - r * 1.25 for _, y, r in cercles) - 700
        ymax = max(y + r * 1.25 for _, y, r in cercles) + 700
        pas_x, pas_y = rng_geo.choice((350, 420, 500)), rng_geo.choice((260, 300, 340))
        gx = xmin
        while gx < xmax:
            gy = ymin
            while gy < ymax:
                x0, y0 = gx + rng_geo.uniform(4, 12), gy + rng_geo.uniform(4, 12)
                x1, y1 = gx + pas_x - rng_geo.uniform(4, 12), gy + pas_y - rng_geo.uniform(4, 12)
                gy += pas_y
                if not any(
                    math.hypot((x0 + x1) / 2 - x, (y0 + y1) / 2 - y) < r * 1.25 + 700
                    for x, y, r in cercles
                ):
                    continue
                id_rpg += 1
                code = rng.choices(codes, poids)[0]
                if rng.random() < 0.004:
                    code = CODE_INCONNU
                # Part bio en légère baisse entre 2024 et 2025, comme un signal à lire.
                est_bio = rng.random() < part_bio * (1 - 0.04 * (annee - 2024))
                # Une parcelle bio sur vingt n'est pas déclarée à la PAC.
                hors_rpg = est_bio and rng.random() < 0.05
                # Le RPG ne constate pas toutes les parcelles bio, et en signale
                # quelques-unes absentes de CartoBio.
                bio_pac = (est_bio and rng.random() < 0.8) or rng.random() < 0.01
                if not hors_rpg:
                    rpg.append(
                        {
                            "type": "Feature",
                            "properties": {
                                "id_parcel": str(id_rpg),
                                "code_cultu": code,
                                "surf_parc": round((x1 - x0) * (y1 - y0) / 10000, 2),
                                "bio": "Oui" if bio_pac else "Non",
                            },
                            "geometry": _poly(_rectangle(x0, y0, x1, y1)),
                        }
                    )
                if not est_bio:
                    continue
                cpf = CULTURES.get(code, (None, None, None, "99.99.99"))[3]
                conversion = rng.choices(*zip(*CONVERSIONS))[0]
                # Contours numérisés différemment : léger décalage.
                dx, dy = rng.uniform(-12, 12), rng.uniform(-12, 12)
                if rng.random() < 0.1:
                    xm = (x0 + x1) / 2
                    morceaux = [(x0, y0, xm, y1), (xm, y0, x1, y1)]
                else:
                    morceaux = [(x0, y0, x1, y1)]
                for a0, b0, a1, b1 in morceaux:
                    bio.append(
                        {
                            "type": "Feature",
                            "properties": {
                                "annee": annee,
                                "culture": cpf if rng.random() > 0.05 else f"{cpf},01.19.22",
                                "convers": conversion,
                                "surface": round((a1 - a0) * (b1 - b0) / 10000, 2),
                            },
                            "geometry": _poly(_rectangle(a0 + dx, b0 + dy, a1 + dx, b1 + dy)),
                        }
                    )
            gx += pas_x

    sources = Sources(
        rpg=dossier / str(annee) / "rpg_parcelles.gpkg",
        bio=dossier / str(annee) / "cartobio.gpkg",
        aac=dossier / "aac.gpkg",
        ref_pac=dossier / str(annee) / f"REF_CULTURES_GROUPES_CULTURES_{annee}.csv",
        ref_cpfbio=dossier / "liste-cultures-cpfbio.xlsx",
    )
    _ecrire_gpkg(aac, sources.aac, "aac")
    _ecrire_gpkg(rpg, sources.rpg, "rpg_parcelles")
    _ecrire_gpkg(bio, sources.bio, "cartobio")

    pd.DataFrame(
        [
            {
                "CODE_CULTURE": c,
                "LIBELLE_CULTURE": v[0],
                "CODE_GROUPE_CULTURE": v[1],
                "LIBELLE_GROUPE_CULTURE": v[2],
            }
            for c, v in CULTURES.items()
        ]
    ).to_csv(sources.ref_pac, sep=";", index=False, encoding="utf-8")
    lignes = [
        {
            "groupe": CPFBIO_GROUPES[v[-1] if len(v) > 4 else v[1]][0],
            "sous_groupe": CPFBIO_GROUPES[v[-1] if len(v) > 4 else v[1]][1],
            "lbl_production": v[0],
            "code_production": v[3],
            "précisions": None,
        }
        for v in CULTURES.values()
    ]
    lignes.append(
        {
            "groupe": "Surfaces fourragères",
            "sous_groupe": "Prairies, parcours",
            "lbl_production": "Prairie temporaire",
            "code_production": "01.19.22",
            "précisions": None,
        }
    )
    pd.DataFrame(lignes).drop_duplicates("code_production").to_excel(
        sources.ref_cpfbio, sheet_name="CPFBIO", index=False
    )
    print(f"démo : {len(aac)} AAC, {len(rpg)} parcelles RPG, {len(bio)} parcelles bio")
    return sources
