-- =====================================================================
-- 01. AAC NETTOYÉES ET EMPRISE DE TRAVAIL
-- Entrée  : :"schema".src_aac (chargée par ogr2ogr, Lambert 93)
-- Sorties : :"schema".aac      une ligne par AAC, géométrie valide
--           :"schema".emprise  AAC + tampon de :buffer m, découpées
-- Variables psql : schema, aac_id, aac_nom_expr, buffer
-- =====================================================================

DROP TABLE IF EXISTS :"schema".aac CASCADE;
CREATE TABLE :"schema".aac AS
SELECT
    src.:"aac_id"::text                                        AS cdaac,
    max(:aac_nom_expr)                                         AS nom,
    ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Union(src.geom)), 3))
        ::geometry(MultiPolygon, 2154)                         AS geom
FROM :"schema".src_aac src
WHERE src.geom IS NOT NULL
GROUP BY src.:"aac_id";

ALTER TABLE :"schema".aac ADD PRIMARY KEY (cdaac);
ALTER TABLE :"schema".aac ADD COLUMN surface_ha double precision;
UPDATE :"schema".aac SET surface_ha = ST_Area(geom) / 10000;
CREATE INDEX ON :"schema".aac USING GIST (geom);
ANALYZE :"schema".aac;

-- L'emprise n'est pas fusionnée en un seul polygone national : un polygone
-- géant rend chaque test d'intersection coûteux. Chaque AAC tamponnée est
-- découpée en morceaux d'au plus 256 sommets, que l'index GiST filtre vite.
DROP TABLE IF EXISTS :"schema".emprise CASCADE;
CREATE TABLE :"schema".emprise AS
SELECT cdaac, ST_Subdivide(ST_Buffer(geom, :buffer), 256) AS geom
FROM :"schema".aac;

CREATE INDEX ON :"schema".emprise USING GIST (geom);
ANALYZE :"schema".emprise;
