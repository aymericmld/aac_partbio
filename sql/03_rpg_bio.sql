-- =====================================================================
-- ÉTAPE 03 : SÉLECTIONNER LES PARCELLES BIO PROCHES DES AAC
-- =====================================================================
--
-- À quoi sert ce script ?
--   CartoBio (Agence Bio) recense les parcelles certifiées en agriculture
--   biologique ou en conversion, y compris celles qui ne sont pas déclarées à
--   la PAC. Ce script fait pour elles ce que l'étape 02 fait pour le RPG :
--   sélection dans la zone de travail, réparation, catégorie de culture.
--
-- Ce qu'il lit   : :src_bio              CartoBio chargé par ogr2ogr
--                  ref_cultures_cpfbio   le référentiel des cultures bio, déjà classé
--                  emprise               la zone de travail (étape 01)
-- Ce qu'il crée  : :t_rpg_bio            une ligne par parcelle bio retenue
--
-- Champs CartoBio utilisés :
--   fid      numéro de ligne ajouté au chargement ;
--   culture  code de culture CPFBIO (plusieurs codes séparés par une virgule
--            quand la parcelle porte plusieurs cultures) ;
--   convers  niveau de conversion : AB (certifié), C1, C2, C3 (1re, 2e, 3e
--            année de conversion) ;
--   surface  surface déclarée, en hectares.
-- =====================================================================

DROP TABLE IF EXISTS :"schema".:"t_rpg_bio" CASCADE;

CREATE TABLE :"schema".:"t_rpg_bio" AS
SELECT
    -- Identifiant préfixé par « AB » pour ne jamais se confondre avec un
    -- identifiant du RPG dans la table fusionnée (étape 05).
    'AB' || bio.fid                           AS id_source,
    c.code_culture,
    bio.culture LIKE '%,%'                    AS multiculture,   -- vrai si plusieurs codes
    ref.categorie                             AS categorie,
    upper(trim(bio.convers))                  AS conversion,     -- « ab » -> « AB »
    bio.surface::double precision             AS surface_declaree_ha,
    ST_Area(g.geom) / 10000                   AS surface_ha,
    g.geom
FROM :"schema".:"src_bio" bio

    -- Géométrie réparée (voir l'étape 01 pour le détail des fonctions).
    CROSS JOIN LATERAL (
        SELECT ST_Multi(ST_CollectionExtract(ST_MakeValid(bio.geom), 3))
               ::geometry(MultiPolygon, 2154) AS geom
    ) g

    -- Culture principale : en cas de multiculture (« code1,code2 »), on garde
    -- le premier code. split_part(texte, ',', 1) renvoie ce qui précède la
    -- première virgule ; trim retire les espaces autour.
    CROSS JOIN LATERAL (SELECT trim(split_part(bio.culture, ',', 1)) AS code_culture) c

    -- Catégorie de la culture principale ; NULL si le code est inconnu.
    LEFT JOIN :"schema".ref_cultures_cpfbio ref ON ref.code_production = c.code_culture

WHERE NOT ST_IsEmpty(g.geom)
  -- Même filtre spatial qu'à l'étape 02 : test rapide sur les rectangles
  -- englobants (&&), puis contact réel (ST_Intersects).
  AND EXISTS (
        SELECT 1 FROM :"schema".emprise e
        WHERE e.geom && bio.geom AND ST_Intersects(e.geom, g.geom)
  );

ALTER TABLE :"schema".:"t_rpg_bio" ADD PRIMARY KEY (id_source);
CREATE INDEX ON :"schema".:"t_rpg_bio" USING GIST (geom);
ANALYZE :"schema".:"t_rpg_bio";
