# Part des parcelles en AB sur les aires d'alimentation de captage (AAC)

## Pré-requis

Extension postgis installée sur le serveur PostgreSQL

Installation de GDAL par le terminal avec la commande
`git clone https://github.com/OSGeo/GDAL.git`

Création d'une base données des parcelles bio à partir des dernières données disponibles<br>
`ogr2ogr
-f PostgreSQL
PG:"host=localhost port=5432 dbname=postgres user=postgres password=postgres" 
"https://www.data.gouv.fr/api/1/datasets/r/aeed2565-d52b-4f0a-ab46-734498a1ae6e"
-nln public.parcelles_bio_france_2025
-lco GEOMETRY_NAME=geom
-nlt PROMOTE_TO_MULTI`

Création d'une base données des AAC à partir des dernières données disponibles<br>
`ogr2ogr
-f PostgreSQL
PG:"host=localhost port=5432 dbname=postgres user=postgres password=postgres" 
"https://www.data.gouv.fr/api/1/datasets/r/aeed2565-d52b-4f0a-ab46-734498a1ae6e"
-nln public.parcelles_bio_france_2025
-lco GEOMETRY_NAME=geom
-nlt PROMOTE_TO_MULTI`





