# Récupérer les données

Le pipeline lit des fichiers déposés dans `data/raw/`, qui n'est pas versionné. Ce guide indique où trouver chaque source et sous quel nom la déposer. Tous les chemins peuvent aussi être passés en option (`--rpg`, `--bio`, `--aac`, `--ref-pac`, `--ref-cpfbio`).

```text
data/raw/
├── aac.gpkg                                   AAC, France entière (commun à tous les millésimes)
├── liste-cultures-cpfbio.xlsx                 référentiel des cultures bio, onglet CPFBIO
└── 2025/
    ├── rpg_parcelles.gpkg                     RPG Parcelles, France métropolitaine
    ├── cartobio.gpkg                          parcelles bio CartoBio
    └── REF_CULTURES_GROUPES_CULTURES_2025.csv référentiel des codes cultures PAC
```

## 1. RPG, IGN

- **Page :** [cartes.gouv.fr, fiche RPG](https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_RPG), puis la [page de téléchargement](https://data.geopf.fr/telechargement/resource/RPG).
- **Fichier :** RPG Parcelles, GeoPackage, Lambert 93, France métropolitaine (FXX). L'archive est en `.7z`. Après extraction, déposer le `.gpkg` des parcelles sous `data/raw/2025/rpg_parcelles.gpkg`.
- **Référentiel des cultures :** le fichier `REF_CULTURES_GROUPES_CULTURES_2025.csv` est livré avec la documentation du RPG. Si le CSV de l'année n'est pas encore publié, celui de l'année précédente convient pour la plupart des codes : le contrôle qualité liste ceux qui restent sans catégorie.

**Ce qui change en 2025 (RPG 4.0) :** l'IGN a publié le millésime 2025 en octobre 2026. Les informations « constatée bio », prairies permanentes, grandes catégories et IAE ne sont plus des couches séparées : elles deviennent des attributs de la couche Parcelles. Les cultures dérobées ne sont plus diffusées. Le pipeline détecte la colonne bio parmi les noms listés dans `src/aac_partbio/config.py` (`COLONNES_RPG["bio"]`).

> **À vérifier au premier chargement :** le nom exact de cet attribut n'a pas pu être confirmé avant la rédaction (descriptif `DC_DL_RPG_4-0.pdf`). Lancer `ogrinfo -so data/raw/2025/rpg_parcelles.gpkg` et, si la colonne bio porte un autre nom, l'ajouter en tête de la liste. Le rapport qualité affiche les valeurs trouvées dans cette colonne pour vérifier qu'elles sont bien interprétées.

## 2. Parcelles bio, Agence Bio

- **Page :** [Parcelles certifiées en Agriculture Biologique sur CartoBio](https://www.data.gouv.fr/datasets/parcelles-certifiees-en-agriculture-biologique-sur-cartobio) (data.gouv.fr). Les fichiers ont été mis à jour le 29 juin 2026.
- **Fichier :** la ressource France entière au format GeoPackage, déposée sous `data/raw/2025/cartobio.gpkg`. Vérifier dans la table que le champ `annee` correspond au millésime voulu.
- **Champs utilisés :** `culture` (code CPFBIO, plusieurs codes séparés par une virgule en cas de multiculture), `convers` (AB, C1, C2, C3), `surface`.
- **Référentiel CPFBIO :** `liste-cultures-cpfbio.xlsx`, onglet `CPFBIO`, colonnes `groupe`, `sous_groupe`, `lbl_production`, `code_production`.

Le jeu « Parcelles en Agriculture Biologique déclarées à la PAC » de l'Agence Bio s'arrête à la campagne 2023 ; il n'est plus utilisé.

## 3. Aires d'alimentation de captage, Sandre

- **Page :** [Aires d'Alimentation de Captages - France entière](https://www.data.gouv.fr/datasets/aires-dalimentation-de-captages-france-entiere-1) (OFB, Sandre).
- **Fichier :** export GeoPackage ou Shapefile du référentiel, déposé sous `data/raw/aac.gpkg`. Le code `CdAAC` sert d'identifiant ; un libellé d'AAC est repris s'il existe.
- Seules les AAC validées par le Sandre sont diffusées ; les aires en cours de délimitation sont visibles sur [aires-captages.fr](https://aires-captages.fr).

Le même référentiel d'AAC s'applique à tous les millésimes traités : après une nouvelle extraction, relancer aussi le millésime précédent pour comparer les années sur le même périmètre.

## Volumétrie

Le RPG 2025 compte près de 10 millions de parcelles, outre-mer compris. Le chargement par `ogr2ogr` est l'étape la plus longue ; les traitements SQL ne portent ensuite que sur les parcelles proches des AAC. L'option `--sans-aac` évite de recharger les AAC, et `traiter --depuis N` reprend au script SQL n° N.
