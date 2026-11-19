-- =====================================================================
-- 03. PARCELLES BIO (CARTOBIO, AGENCE BIO) DANS L'EMPRISE
-- Entrées : :"schema".:"src_bio", :"schema".ref_cultures_cpfbio
-- Sortie  : :"schema".:"t_rpg_bio"
-- Variables psql : schema, src_bio, t_rpg_bio
-- =====================================================================

DROP TABLE IF EXISTS :"schema".:"t_rpg_bio" CASCADE;
CREATE TABLE :"schema".:"t_rpg_bio" AS
SELECT
    'AB' || bio.fid                           AS id_source,
    c.code_culture,
    bio.culture LIKE '%,%'                    AS multiculture,
    ref.categorie                             AS categorie,
    upper(trim(bio.convers))                  AS conversion,
    bio.surface::double precision             AS surface_declaree_ha,
    ST_Area(g.geom) / 10000                   AS surface_ha,
    g.geom
FROM :"schema".:"src_bio" bio
    CROSS JOIN LATERAL (
        SELECT ST_Multi(ST_CollectionExtract(ST_MakeValid(bio.geom), 3))
               ::geometry(MultiPolygon, 2154) AS geom
    ) g
    -- CartoBio sépare les codes par une virgule en cas de multiculture :
    -- la première culture déclarée sert de culture principale.
    CROSS JOIN LATERAL (SELECT trim(split_part(bio.culture, ',', 1)) AS code_culture) c
    LEFT JOIN :"schema".ref_cultures_cpfbio ref ON ref.code_production = c.code_culture
WHERE NOT ST_IsEmpty(g.geom)
  AND EXISTS (
        SELECT 1 FROM :"schema".emprise e
        WHERE e.geom && bio.geom AND ST_Intersects(e.geom, g.geom)
  );

ALTER TABLE :"schema".:"t_rpg_bio" ADD PRIMARY KEY (id_source);
CREATE INDEX ON :"schema".:"t_rpg_bio" USING GIST (geom);
ANALYZE :"schema".:"t_rpg_bio";
