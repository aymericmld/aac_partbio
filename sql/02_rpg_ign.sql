-- =====================================================================
-- 02. PARCELLES DU RPG (IGN) DANS L'EMPRISE
-- Entrées : :"schema".:"src_rpg", :"schema".ref_cultures_pac
-- Sortie  : :"schema".:"t_rpg_ign"
-- Variables psql : schema, src_rpg, t_rpg_ign, rpg_id, rpg_culture,
--                  rpg_surface, rpg_bio_expr
-- rpg_bio_expr vaut NULL::boolean quand le millésime n'a pas d'attribut bio
-- (avant 2025), sinon une expression booléenne sur la colonne détectée.
-- =====================================================================

DROP TABLE IF EXISTS :"schema".:"t_rpg_ign" CASCADE;
CREATE TABLE :"schema".:"t_rpg_ign" AS
SELECT
    ign.:"rpg_id"::text                       AS id_source,
    ign.:"rpg_culture"::text                  AS code_culture,
    ref.categorie                             AS categorie,
    (:rpg_bio_expr)                           AS bio_pac,
    ign.:"rpg_surface"::double precision      AS surface_declaree_ha,
    ST_Area(g.geom) / 10000                   AS surface_ha,
    g.geom
FROM :"schema".:"src_rpg" ign
    CROSS JOIN LATERAL (
        SELECT ST_Multi(ST_CollectionExtract(ST_MakeValid(ign.geom), 3))
               ::geometry(MultiPolygon, 2154) AS geom
    ) g
    LEFT JOIN :"schema".ref_cultures_pac ref ON ref.code_culture = ign.:"rpg_culture"::text
WHERE NOT ST_IsEmpty(g.geom)
  AND EXISTS (
        SELECT 1 FROM :"schema".emprise e
        WHERE e.geom && ign.geom AND ST_Intersects(e.geom, g.geom)
  );

ALTER TABLE :"schema".:"t_rpg_ign" ADD PRIMARY KEY (id_source);
CREATE INDEX ON :"schema".:"t_rpg_ign" USING GIST (geom);
ANALYZE :"schema".:"t_rpg_ign";
