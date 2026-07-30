# Part des parcelles en AB sur les aires d'alimentation de captage (AAC)

## Présentation du projet

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

## Données

## Licence









