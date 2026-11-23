"""Étape « controler » : vérifier les résultats avant de les publier.

Deux niveaux de contrôle :
- les contrôles bloquants vérifient des règles qui doivent toujours être
  vraies (une part bio entre 0 et 100 %, une surface dans l'AAC jamais plus
  grande que la parcelle...). Si l'un échoue, le programme s'arrête : les
  résultats sont faux et ne doivent pas être exportés ;
- les diagnostics sont des mesures à lire, sans bon ou mauvais absolu (part
  des parcelles bio retrouvées dans le RPG, codes cultures sans catégorie...).
  Ils sont écrits dans data/processed/rapport_qualite_AAAA.json.
"""

from __future__ import annotations

import json

from . import chargement, db
from .config import PROCESSED, SCHEMA

S = SCHEMA  # nom court, pour alléger l'écriture des requêtes
# Marge acceptée sur les comparaisons de surfaces, en hectares (100 m²) :
# les calculs géométriques produisent de minuscules écarts d'arrondi.
TOLERANCE_HA = 0.01


def _valeur(sql: str, params: tuple = ()) -> float:
    """Exécute une requête qui renvoie un seul nombre et renvoie ce nombre (0 si vide)."""
    df = db.requete(sql, params)
    v = df.iat[0, 0]
    return float(v) if v is not None else 0.0


def controles_bloquants(annee: int) -> list[str]:
    """Renvoie la liste des règles non respectées ; une liste vide signifie « tout va bien ».

    Chaque bloc ci-dessous compte les lignes qui violent une règle, ou
    compare deux totaux qui devraient être égaux.
    """
    erreurs: list[str] = []
    a = (annee,)
    if _valeur(f'SELECT count(*) FROM "{S}".parcel WHERE annee = %s', a) == 0:
        erreurs.append("aucune parcelle produite")
    if _valeur(
        f"""SELECT count(*) FROM "{S}".parcel_aac pa JOIN "{S}".parcel p USING (annee, id_parcel)
            WHERE pa.annee = %s AND pa.surface_dans_aac_ha > p.surface_ha + {TOLERANCE_HA}""",
        a,
    ):
        erreurs.append("surface dans l'AAC supérieure à la surface de la parcelle")
    if _valeur(
        f'SELECT count(*) FROM "{S}".synthese_aac WHERE annee = %s AND '
        "(part_bio < 0 OR part_bio > 1 + 1e-9 OR sau_bio_ha > sau_ha + 0.01)",
        a,
    ):
        erreurs.append("part bio hors de [0, 1]")
    nb_aac = _valeur(f'SELECT count(*) FROM "{S}".aac')
    if _valeur(f'SELECT count(*) FROM "{S}".synthese_aac WHERE annee = %s', a) != nb_aac:
        erreurs.append("synthese_aac ne couvre pas toutes les AAC")
    total = _valeur(f'SELECT sau_aac_ha FROM "{S}".synthese_nationale WHERE annee = %s', a)
    somme = _valeur(f'SELECT sum(sau_ha) FROM "{S}".synthese_categorie WHERE annee = %s', a)
    if abs(total - somme) > 1:
        erreurs.append(f"catégories non réconciliées : {somme:.1f} ha contre {total:.1f} ha")
    surface_aac = _valeur(
        f'SELECT surface_aac_ha FROM "{S}".synthese_nationale WHERE annee = %s', a
    )
    if total > surface_aac + 1:
        erreurs.append("plus de surface agricole que de surface d'AAC")
    sans_union = _valeur(
        f'SELECT sum(surface_dans_aac_ha) FROM "{S}".parcel_aac WHERE annee = %s', a
    )
    if total > sans_union + 1:
        erreurs.append("le dédoublonnage entre AAC augmente la surface")
    return erreurs


def diagnostics(annee: int) -> dict:
    """Calcule les mesures de qualité du croisement (voir le docstring du module)."""
    a = (annee,)
    colonnes = chargement.detecter(annee)
    sources = db.requete(
        f"""SELECT source, count(*) AS parcelles, round(sum(surface_ha)::numeric, 1) AS surface_ha
            FROM "{S}".parcel WHERE annee = %s GROUP BY source ORDER BY source""",
        a,
    )
    nb_bio = _valeur(f'SELECT count(*) FROM "{S}".rpg_bio_{annee}')
    appariees = _valeur(f'SELECT count(*) FROM "{S}".appariement_{annee} WHERE retenu')
    # Chevauchement restant entre parcelles RPG conservées et parcelles bio.
    residuel = _valeur(
        f"""SELECT COALESCE(sum(r.surface_commune_ha), 0) FROM "{S}".recouvrement_{annee} r
            WHERE NOT EXISTS (SELECT 1 FROM "{S}".ign_remplace_{annee} x WHERE x.ign_id = r.ign_id)"""
    )
    sau = _valeur(f'SELECT sau_aac_ha FROM "{S}".synthese_nationale WHERE annee = %s', a)
    non_classes = db.requete(
        f"""SELECT source, code_culture, count(*) AS parcelles,
                   round(sum(surface_ha)::numeric, 1) AS surface_ha
            FROM "{S}".parcel WHERE annee = %s AND categorie = 'Non classé'
            GROUP BY source, code_culture ORDER BY surface_ha DESC LIMIT 20""",
        a,
    )
    surface_non_classee = _valeur(
        f"""SELECT COALESCE(sum(d.surface_dans_aac_ha), 0) FROM "{S}".parcel_dans_aac d
            JOIN "{S}".parcel p USING (annee, id_parcel)
            WHERE d.annee = %s AND p.categorie = 'Non classé'""",
        a,
    )
    # Les deux référentiels sont classés séparément : on mesure leur accord
    # sur les parcelles appariées, pondéré par la surface commune.
    concordance = _valeur(
        f"""SELECT sum(a.surface_commune_ha) FILTER (WHERE b.categorie IS NOT DISTINCT FROM i.categorie)
                   / NULLIF(sum(a.surface_commune_ha), 0)
            FROM "{S}".appariement_{annee} a
            JOIN "{S}".rpg_bio_{annee} b ON b.id_source = a.bio_id
            JOIN "{S}".rpg_ign_{annee} i ON i.id_source = a.ign_id
            WHERE a.retenu"""
    )
    discordances = db.requete(
        f"""SELECT i.categorie AS categorie_rpg, b.categorie AS categorie_cartobio,
                   round(sum(a.surface_commune_ha)::numeric, 1) AS surface_ha
            FROM "{S}".appariement_{annee} a
            JOIN "{S}".rpg_bio_{annee} b ON b.id_source = a.bio_id
            JOIN "{S}".rpg_ign_{annee} i ON i.id_source = a.ign_id
            WHERE a.retenu AND b.categorie IS DISTINCT FROM i.categorie
            GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 15"""
    )
    valeurs_bio = None
    if colonnes["rpg_bio"]:
        valeurs_bio = db.requete(
            f'SELECT "{colonnes["rpg_bio"]}"::text AS valeur, count(*) AS parcelles '
            f'FROM "{S}".src_rpg_{annee} GROUP BY 1 ORDER BY 2 DESC LIMIT 10'
        ).to_dict("records")
    return {
        "annee": annee,
        "colonnes": colonnes,
        "parcelles_par_source": sources.to_dict("records"),
        "taux_appariement_bio": appariees / nb_bio if nb_bio else None,
        "chevauchement_residuel_ha": residuel,
        "part_chevauchement_residuel": residuel / sau if sau else None,
        "part_sau_non_classee": surface_non_classee / sau if sau else None,
        "concordance_categories": concordance,
        "discordances_categories": discordances.to_dict("records"),
        "codes_non_classes": non_classes.to_dict("records"),
        "valeurs_colonne_bio_rpg": valeurs_bio,
    }


def controler(annee: int) -> dict:
    """Lance les contrôles bloquants, puis écrit le rapport de diagnostics."""
    erreurs = controles_bloquants(annee)
    if erreurs:
        raise ValueError("Contrôles qualité en échec :\n- " + "\n- ".join(erreurs))
    rapport = diagnostics(annee)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    chemin = PROCESSED / f"rapport_qualite_{annee}.json"
    chemin.write_text(json.dumps(rapport, ensure_ascii=False, indent=2, default=str))
    print(f"contrôles qualité {annee} : 7 contrôles bloquants validés, rapport dans {chemin.name}")
    taux = rapport["taux_appariement_bio"]
    if taux is not None:
        print(f"  parcelles bio appariées au RPG : {taux:.1%}")
    print(f"  catégories identiques RPG / CartoBio : {rapport['concordance_categories']:.1%}")
    if rapport["part_sau_non_classee"]:
        print(f"  surface sans catégorie : {rapport['part_sau_non_classee']:.2%}")
    return rapport
