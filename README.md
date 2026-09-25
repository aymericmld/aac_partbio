# Parcelles agricoles sur les aires d'alimentation de captage (AAC)

## Présentation du projet
Croisement des parcelles du Registre parcellaire graphique (RPG) publié par l'IGN et des parcelles certifiées en agriculture biologique publiées par l'Agence BIO afin de spécifier les cultures présentes sur les AAC et la part en bio. 

Le projet propose une classification des cultures communes entre les deux sources de données. 

## Pré-requis

Extension postgis installée sur le serveur PostgreSQL

Installation de GDAL par le terminal avec la commande
`git clone https://github.com/OSGeo/GDAL.git`

Création d'une table SQL à partir du dernier RPG disponible (2024 à date) <br>
`ogr2ogr \
-f PostgreSQL \
PG:"host=localhost port=5432 dbname=postgres user=postgres password=postgres" \
"~/RPG_3-0__GPKG_LAMB93_FXX_2024-01-01/RPG/1_DONNEES_LIVRAISON_2024/RPG_3-0__GPKG_LAMB93_FXX_2024-01-01/RPG_Parcelles.gpkg" \
-nln public.rpg_francemet_2024 \
-lco GEOMETRY_NAME=geom \
-nlt PROMOTE_TO_MULTI \
-overwrite`

Création d'une table SQL des parcelles bio à partir des dernières données disponibles<br>
`ogr2ogr
-f PostgreSQL
PG:"host=localhost port=5432 dbname=postgres user=postgres password=postgres" 
"https://www.data.gouv.fr/api/1/datasets/r/aeed2565-d52b-4f0a-ab46-734498a1ae6e"
-nln public.parcelles_bio_francemet_2024
-lco GEOMETRY_NAME=geom
-nlt PROMOTE_TO_MULTI`

Création d'une table SQL des AAC à partir des dernières données disponibles<br>
`ogr2ogr
-f PostgreSQL
PG:"host=localhost port=5432 dbname=postgres user=postgres password=postgres" 
"https://www.data.gouv.fr/api/1/datasets/r/aeed2565-d52b-4f0a-ab46-734498a1ae6e"
-nln public.parcelles_bio_france_2025
-lco GEOMETRY_NAME=geom
-nlt PROMOTE_TO_MULTI`

## Classification des cultures par catégorie agricole

Ce projet ajoute une colonne `categorie` aux référentiels de cultures utilisés pour la
qualification des parcelles agricoles (CPFBIO, PAC/RPG), en rattachant chaque code de
production à l'une des 8 grandes catégories métier définies ci-dessous.

### Catégories cibles

| Catégorie | Description |
|---|---|
| Céréales et oléoprotéagineux | Céréales, oléagineux, protéagineux, légumineuses à grains |
| Cultures fourragères | Plantes cultivées pour l'alimentation animale (hors prairies) |
| Prairies | Prairies permanentes/temporaires, parcours, estives et landes |
| Cultures fruitières | Vergers, fruits à coque, oliviers, petits fruits |
| Maraîchage | Légumes, cultures potagères, horticulture ornementale |
| Vignes | Viticulture |
| Plantes à parfum, aromatiques et médicinales (PPAM) | PPAM et plantes à boisson (café, thé, houblon...) |
| Autres | Tout le reste : cultures industrielles non oléagineuses, jachères, surfaces non productives, sylviculture, aquaculture, éléments paysagers... |

### Méthodologie

1. **Classification par groupe/sous-groupe.** Chaque référentiel source possède déjà une
   hiérarchie (`groupe` + `sous_groupe` pour CPFBIO, `CODE_GROUPE_CULTURE` +
   `LIBELLE_GROUPE_CULTURE` pour le référentiel PAC). Une première règle mappe chaque
   groupe/sous-groupe vers l'une des 8 catégories cibles.
2. **Exceptions au niveau du code.** Certains groupes sources sont hétérogènes
   (ex. "Autres surfaces" dans CPFBIO ou "Autres cultures industrielles" / "Divers" dans le
   référentiel PAC mélangent des cultures industrielles, des PPAM, des semences...).
   Pour ces groupes, chaque `code_production` / `CODE_CULTURE` est examiné individuellement
   à partir de son libellé (et des précisions le cas échéant) et rattaché à la catégorie la
   plus pertinente, avec une liste d'exceptions explicites.
3. **Catégorie par défaut.** Toute culture ne correspondant clairement à aucune des 7
   catégories agronomiques (semences génériques, surfaces non productives, sylviculture,
   aquaculture, éléments paysagers type haies/bandes tampons, cultures industrielles non
   oléagineuses comme la betterave sucrière, le tabac ou la canne à sucre) est classée en
   **Autres**.

### Fichiers traités

#### 1. `liste-cultures-cpfbio.xlsx` (onglet `CPFBIO`)

Colonnes sources : `groupe`, `sous_groupe`, `lbl_production`, `code_production`, `précisions`.

Mapping principal par `groupe` :

| groupe | catégorie |
|---|---|
| Grandes Cultures | Céréales et oléoprotéagineux |
| Surfaces fourragères / sous_groupe "Prairies, parcours" | Prairies |
| Surfaces fourragères / sous_groupe "Plantes fourragères" | Cultures fourragères |
| Fruits | Cultures fruitières |
| Légumes | Maraîchage |
| Viticulture | Vignes |
| Plantes à parfums, aromatiques et médicinales et plantes à boissons | Plantes à parfum, aromatiques et médicinales |
| Autres surfaces / Inconnu | Autres (avec exceptions ci-dessous) |

Exceptions dans "Autres surfaces" (reclassées hors "Autres") :
- Semences de céréales, légumineuses et oléagineux ; Semences de riz → Céréales et oléoprotéagineux
- Plants et semences potagers → Maraîchage
- Semences fruitières → Cultures fruitières
- Semences de plantes fourragères → Cultures fourragères
- Zone de cueillette de PPAM → Plantes à parfum, aromatiques et médicinales

→ Fichier produit : `liste-cultures-cpfbio-classifie.xlsx`

#### 2. `REF_CULTURES_GROUPES_CULTURES_2024.csv`

Colonnes sources : `CODE_CULTURE`, `LIBELLE_CULTURE`, `CODE_GROUPE_CULTURE`, `LIBELLE_GROUPE_CULTURE`.

Mapping principal par `CODE_GROUPE_CULTURE` :

| Groupe PAC | catégorie |
|---|---|
| Blé tendre, Maïs, Orge, Autres céréales, Colza, Tournesol, Autres oléagineux, Protéagineux, Riz, Légumineuses à grains | Céréales et oléoprotéagineux |
| Fourrage | Cultures fourragères |
| Estives et landes, Prairies permanentes, Prairies temporaires | Prairies |
| Vergers, Fruits à coque, Oliviers | Cultures fruitières |
| Vignes | Vignes |
| Légumes ou fleurs | Maraîchage |
| Plantes à fibres, Gel, Canne à sucre, Divers, Autres cultures industrielles | Autres (avec exceptions ci-dessous) |

Exceptions dans "Autres cultures industrielles" / "Divers" (reclassées hors "Autres") :
- Houblon, Lavande et lavandin, Vanille, Persil, Fenugrec, Plantes médicinales/aromatiques
  (pérennes ou non, arbustives ou non) → Plantes à parfum, aromatiques et médicinales
- Cameline, Moutarde d'hiver → Céréales et oléoprotéagineux (oléagineux)

Restent en "Autres" : betterave, tabac, chanvre/lin fibre, canne à sucre, jachères, et les
éléments "Divers" (bordures, bandes tampons, taillis, pépinières, truffières, marais salants...).

→ Fichiers produits : `REF_CULTURES_GROUPES_CULTURES_2024_classifie.csv` /
`.xlsx`

### Limites et arbitrages

- Ces classifications reposent sur une lecture métier des libellés de culture ; certains
  arbitrages sont discutables
- Les deux référentiels sont traités indépendamment : la cohérence est assurée par
  l'application de la même grille de catégories et des mêmes principes d'arbitrage, mais pas
  par un recoupement systématique code à code entre les deux fichiers.

### Prompt réutilisable (pour IA)

Le prompt ci-dessous peut être copié tel quel pour reproduire cette classification sur un
nouveau référentiel de cultures.

```
Tu es chargé de classer des cultures agricoles dans une des 8 catégories suivantes :
1. Céréales et oléoprotéagineux
2. Cultures fourragères
3. Prairies
4. Cultures fruitières
5. Maraîchage
6. Vignes
7. Plantes à parfum, aromatiques et médicinales (PPAM)
8. Autres

Contexte : ces catégories servent à qualifier des parcelles agricoles à partir d'un
référentiel de cultures (colonnes possibles : code culture, libellé culture, groupe,
sous-groupe, précisions...).

Tâche :
1. Charge le fichier fourni et identifie toutes ses colonnes, notamment celles qui
   décrivent une hiérarchie de classification déjà présente (groupe, sous-groupe, famille...).
2. Si une hiérarchie existe déjà dans le fichier, commence par établir une règle de mapping
   groupe → catégorie cible, en te basant sur le sens agronomique du groupe (ex. "Vergers"
   → Cultures fruitières, "Prairies permanentes" → Prairies, "Légumes ou fleurs" →
   Maraîchage).
3. Repère les groupes hétérogènes (ex. "Autres cultures industrielles", "Divers", "Autres
   surfaces") qui mélangent plusieurs types de cultures. Pour ces groupes uniquement,
   examine chaque ligne individuellement à partir de son libellé et affecte la catégorie la
   plus pertinente, en listant explicitement les exceptions retenues.
4. Applique la catégorie "Autres" par défaut aux cultures qui ne correspondent clairement à
   aucune des 7 catégories agronomiques : cultures industrielles non oléagineuses (betterave
   sucrière, tabac, canne à sucre, coton...), semences génériques non rattachables à une
   catégorie précise, surfaces non productives (jachères, gel), éléments paysagers (haies,
   bandes tampons, bordures), sylviculture, aquaculture, gazon/semences de graminées non
   fourragères.
5. Ajoute une colonne `categorie` au fichier source (ne modifie aucune autre colonne) et
   exporte le résultat dans le même format que le fichier d'entrée (xlsx reste xlsx, csv
   reste csv avec le même séparateur et encodage).
6. Vérifie ton travail : affiche la distribution du nombre de lignes par catégorie, et
   liste le détail des lignes classées en "Autres" pour validation manuelle.
7. Documente les règles de mapping utilisées (groupe → catégorie, et liste des exceptions
   ligne à ligne) pour permettre de reproduire ou d'auditer la classification.

Contraintes :
- Ne jamais laisser de ligne sans catégorie.
- Une même catégorie "Autres" doit rester une catégorie de repli explicite et documentée,
  pas un résidu implicite.
- Si le fichier contient plusieurs référentiels/onglets, traiter et documenter chacun
  séparément.
```

## Données


## Méthodologie de croisement des données


Le traitement consiste à croiser deux sources de données parcellaires :

- **Les parcelles certifiées publiées par l'Agence BIO**, contenant les parcelles identifiées comme biologiques ;
- **Le RPG publié par l'IGN**, utilisé comme référentiel général des parcelles.

L'objectif est de produire une table unique de parcelles en donnant la priorité aux informations issues du RPG Bio lorsqu'une parcelle biologique correspond spatialement à une parcelle IGN.

### 1. Définition de l'emprise géographique

Une emprise de travail est d'abord construite à partir des **AAC (Aires d'Alimentation de Captages)**.

Les géométries des AAC sont transformées dans un même système de coordonnées, puis une **zone tampon de 500 mètres** est appliquée. 

Cette emprise permet de limiter le traitement aux parcelles situées dans ou à proximité des AAC et de faciliter le croisement des données par la suite. 

### 2. Préparation des données géographiques

Les géométries des parcelles Bio et IGN sont :

1. transformées dans un même système de coordonnées ;
2. corrigées afin de disposer de géométries valides ;
3. amendées avec les groupes de culture définis en amont ;
4. filtrées pour ne conserver que les parcelles qui intersectent l'emprise des AAC.

Pour chaque parcelle, un **centroïde** est également calculé. Celui-ci sert ensuite à rechercher la parcelle IGN la plus proche d'une parcelle Bio.

### 3. Recherche de la correspondance Bio → IGN

Pour chaque parcelle du RPG Bio, le traitement recherche la parcelle du RPG IGN dont le **centroïde est le plus proche**.

La distance entre les deux centroïdes permet d'identifier la parcelle IGN candidate la plus proche.

Cette étape permet donc d'établir une relation entre une parcelle Bio et sa parcelle IGN de référence.

### 4. Vérification du recouvrement spatial

La proximité des centres ne suffit pas à elle seule pour considérer deux parcelles comme correspondantes.

La correspondance est donc vérifiée en comparant directement les géométries des deux parcelles.

Deux parcelles sont considérées comme se correspondant lorsqu'elles présentent un **recouvrement spatial**.

Cette vérification permet notamment d'éviter de considérer comme équivalentes deux parcelles simplement parce qu'elles sont proches géographiquement.

### 5. Fusion des informations

Une fois les correspondances établies, les informations des deux sources sont regroupées dans un référentiel parcellaire commun.

Lorsqu'une parcelle Bio correspond à une parcelle IGN, les informations du **RPG Bio sont prioritaires**.

Cela concerne notamment :

- l'identifiant de parcelle ;
- le groupe de culture ;
- le statut de conversion ;
- la surface ;
- la géométrie.

Lorsqu'aucune information Bio n'est disponible, les informations issues du RPG IGN sont utilisées.

Les parcelles IGN qui ne trouvent pas de correspondance avec une parcelle Bio sont également conservées. Le croisement ne supprime donc pas les parcelles présentes uniquement dans le référentiel IGN. Idem pour les parcelles Bio non présentes dans le référentiel IGN. 

### 6. Rattachement aux AAC

Après la fusion des deux référentiels, les parcelles obtenues sont à nouveau croisées avec les AAC afin d'identifier les AAC auxquelles elles sont rattachées.

Le rattachement repose sur le **recouvrement géographique entre la parcelle et l'AAC**.

Une parcelle n'a pas besoin d'être entièrement située dans une AAC pour être conservée : **une parcelle qui chevauche la limite d'une AAC est également prise en compte**.

Le centroïde de la parcelle n'intervient pas dans ce rattachement final. Il est uniquement utilisé lors de la recherche de correspondance entre les parcelles Bio et IGN.

Le résultat final associe ainsi les parcelles retenues à l'identifiant de l'AAC correspondante.

### Schéma simplifié du croisement

```text
              AAC 2024
                  │
          Buffer de 500 m
                  │
          ┌───────▼───────┐
          │ Emprise AAC   │
          └───────┬───────┘
                  │
        ┌─────────┴─────────┐
        │                   │
    RPG Bio 2024        RPG IGN 2024
        │                   │
        └───────┬───────────┘
                │
       Recherche du plus
       proche par centroïde
                │
                ▼
       Vérification spatiale
        du recouvrement
                │
                ▼
       Correspondance Bio ↔ IGN
                │
                ▼
       Fusion des informations
       Priorité aux données Bio
                │
                ▼
       Référentiel parcellaire
              final
                │
                │
                ▼
       Rattachement aux AAC
                │
                ▼
            parcel_aac


## Licence









