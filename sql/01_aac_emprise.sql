-- =====================================================================
-- ÉTAPE 01 : PRÉPARER LES AAC ET LA ZONE DE TRAVAIL
-- =====================================================================
--
-- À quoi sert ce script ?
--   Les aires d'alimentation de captage (AAC) arrivent telles que le Sandre
--   les diffuse. Ce script les nettoie, puis dessine autour d'elles une
--   « zone de travail » (l'emprise) : seules les parcelles agricoles situées
--   dans cette zone seront analysées par la suite. Cela évite de traiter les
--   10 millions de parcelles de France alors que seule une partie touche une AAC.
--
-- Ce qu'il lit   : la table src_aac (les AAC chargées par ogr2ogr)
-- Ce qu'il crée  : aac      -> une ligne par AAC, géométrie propre, surface
--                  emprise  -> les AAC élargies d'un tampon de :buffer mètres
--
-- Les mots précédés de « : » (:schema, :buffer, :aac_id...) ne sont pas du
-- SQL : ce sont des variables que psql remplace avant d'exécuter le script.
-- Le programme Python (traitement.py) leur donne leur valeur. Écrites
-- :"variable", elles deviennent un nom de table ou de colonne entre guillemets.
--
-- Rappel : toutes les géométries sont en Lambert 93 (code EPSG 2154), une
-- projection en mètres. Une surface calculée en m² se divise par 10 000 pour
-- obtenir des hectares.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Table des AAC nettoyées
-- ---------------------------------------------------------------------
-- On repart de zéro à chaque exécution : DROP supprime l'ancienne table si
-- elle existe, CASCADE supprime aussi ce qui en dépend (index...).
DROP TABLE IF EXISTS :"schema".aac CASCADE;

CREATE TABLE :"schema".aac AS
SELECT
    -- Code de l'AAC, converti en texte pour servir d'identifiant.
    src.:"aac_id"::text                                        AS cdaac,
    -- Nom de l'AAC. Comme on regroupe les lignes par code (GROUP BY plus bas),
    -- il faut une fonction d'agrégation : max() garde simplement un nom.
    max(:aac_nom_expr)                                         AS nom,
    -- Géométrie de l'AAC, en quatre opérations lues de l'intérieur vers
    -- l'extérieur :
    --   ST_Union            fusionne les morceaux d'une même AAC en un seul objet ;
    --   ST_MakeValid        répare les polygones mal dessinés (contour qui se
    --                       croise, etc.), sinon les calculs suivants échouent ;
    --   ST_CollectionExtract(..., 3) ne garde que les polygones (type 3) et
    --                       jette les lignes ou points produits par la réparation ;
    --   ST_Multi            met tout au format MultiPolygon, pour que toutes les
    --                       lignes aient le même type de géométrie.
    ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Union(src.geom)), 3))
        ::geometry(MultiPolygon, 2154)                         AS geom
FROM :"schema".src_aac src
WHERE src.geom IS NOT NULL          -- une AAC sans contour est inutilisable
GROUP BY src.:"aac_id";             -- une ligne par code d'AAC

-- Le code devient la clé primaire : il ne peut plus y avoir de doublon.
ALTER TABLE :"schema".aac ADD PRIMARY KEY (cdaac);

-- Surface de chaque AAC en hectares (ST_Area renvoie des m²).
ALTER TABLE :"schema".aac ADD COLUMN surface_ha double precision;
UPDATE :"schema".aac SET surface_ha = ST_Area(geom) / 10000;

-- Index spatial GiST : l'équivalent, pour les géométries, de l'index d'un
-- livre. Sans lui, chaque recherche « quelles parcelles touchent cette AAC ? »
-- comparerait toutes les géométries une à une.
CREATE INDEX ON :"schema".aac USING GIST (geom);

-- ANALYZE met à jour les statistiques de la table, que PostgreSQL utilise
-- pour choisir la façon la plus rapide d'exécuter les requêtes suivantes.
ANALYZE :"schema".aac;


-- ---------------------------------------------------------------------
-- 2. Zone de travail : les AAC élargies d'un tampon
-- ---------------------------------------------------------------------
-- Pourquoi un tampon ? Pour l'étape d'appariement (script 04), on veut aussi
-- les parcelles qui débordent juste à l'extérieur d'une AAC : une parcelle
-- bio et sa parcelle RPG correspondante doivent être présentes toutes les
-- deux, même si l'une dépasse un peu de la limite.
--
-- ST_Buffer(geom, :buffer)  élargit chaque AAC de :buffer mètres (500 par défaut) ;
-- ST_Subdivide(..., 256)    découpe le résultat en petits morceaux d'au plus
--                           256 sommets.
--
-- Pourquoi découper ? Un très grand polygone aux contours détaillés est lent à
-- comparer : pour savoir si une parcelle le touche, PostGIS doit parcourir
-- tous ses sommets. Avec des petits morceaux, l'index spatial élimine
-- d'emblée tous ceux qui sont loin, et le test ne porte que sur quelques
-- morceaux proches. ST_Subdivide renvoie plusieurs lignes par AAC.
DROP TABLE IF EXISTS :"schema".emprise CASCADE;
CREATE TABLE :"schema".emprise AS
SELECT cdaac, ST_Subdivide(ST_Buffer(geom, :buffer), 256) AS geom
FROM :"schema".aac;

CREATE INDEX ON :"schema".emprise USING GIST (geom);
ANALYZE :"schema".emprise;
