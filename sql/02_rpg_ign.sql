-- =====================================================================
-- ÉTAPE 02 : SÉLECTIONNER LES PARCELLES DU RPG PROCHES DES AAC
-- =====================================================================
--
-- À quoi sert ce script ?
--   Le Registre parcellaire graphique (RPG) de l'IGN contient toutes les
--   parcelles déclarées à la PAC. Ce script ne garde que celles qui touchent
--   la zone de travail créée à l'étape 01, répare leur géométrie et leur
--   attribue une catégorie de culture.
--
-- Ce qu'il lit   : :src_rpg            le RPG chargé par ogr2ogr (src_rpg_2025...)
--                  ref_cultures_pac    le référentiel des cultures PAC, déjà classé
--                  emprise             la zone de travail (étape 01)
-- Ce qu'il crée  : :t_rpg_ign          une ligne par parcelle RPG retenue
--
-- Variables remplies par traitement.py :
--   rpg_id, rpg_culture, rpg_surface : noms des colonnes du RPG (ils peuvent
--       changer d'un millésime à l'autre, le programme les détecte) ;
--   rpg_bio_expr : expression SQL qui vaut vrai si la parcelle est
--       « constatée bio » dans le RPG. Pour un millésime sans cette
--       information, elle vaut NULL (valeur inconnue).
-- =====================================================================

DROP TABLE IF EXISTS :"schema".:"t_rpg_ign" CASCADE;

CREATE TABLE :"schema".:"t_rpg_ign" AS
SELECT
    ign.:"rpg_id"::text                       AS id_source,      -- identifiant de la parcelle
    ign.:"rpg_culture"::text                  AS code_culture,   -- code culture PAC (BTH, PPH...)
    ref.categorie                             AS categorie,      -- une des 8 catégories du projet
    (:rpg_bio_expr)                           AS bio_pac,        -- vrai si constatée bio dans le RPG
    ign.:"rpg_surface"::double precision      AS surface_declaree_ha,  -- surface déclarée par l'exploitant
    ST_Area(g.geom) / 10000                   AS surface_ha,     -- surface recalculée sur le dessin
    g.geom
FROM :"schema".:"src_rpg" ign

    -- CROSS JOIN LATERAL permet de calculer une valeur une seule fois par
    -- ligne et de la réutiliser ensuite sous le nom g.geom. Ici : la géométrie
    -- réparée (voir l'étape 01 pour le détail des fonctions).
    CROSS JOIN LATERAL (
        SELECT ST_Multi(ST_CollectionExtract(ST_MakeValid(ign.geom), 3))
               ::geometry(MultiPolygon, 2154) AS geom
    ) g

    -- LEFT JOIN : on garde la parcelle même si son code culture est absent du
    -- référentiel. Sa catégorie vaut alors NULL, et elle sera classée
    -- « Non classé » à l'étape 05 et signalée par le contrôle qualité.
    LEFT JOIN :"schema".ref_cultures_pac ref ON ref.code_culture = ign.:"rpg_culture"::text

WHERE NOT ST_IsEmpty(g.geom)      -- la réparation peut vider une géométrie dégénérée
  -- On ne garde la parcelle que si elle touche au moins un morceau de la zone
  -- de travail. EXISTS s'arrête dès qu'il en trouve un.
  --   e.geom && ign.geom      compare seulement les rectangles englobants :
  --                           test très rapide qui profite de l'index spatial ;
  --   ST_Intersects(...)      vérifie ensuite le contact réel des formes.
  AND EXISTS (
        SELECT 1 FROM :"schema".emprise e
        WHERE e.geom && ign.geom AND ST_Intersects(e.geom, g.geom)
  );

-- Clé primaire, index spatial et statistiques (voir l'étape 01).
ALTER TABLE :"schema".:"t_rpg_ign" ADD PRIMARY KEY (id_source);
CREATE INDEX ON :"schema".:"t_rpg_ign" USING GIST (geom);
ANALYZE :"schema".:"t_rpg_ign";
