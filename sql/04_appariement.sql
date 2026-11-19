-- =====================================================================
-- 04. APPARIEMENT BIO <-> RPG PAR RECOUVREMENT SPATIAL
-- Entrées : :"t_rpg_bio", :"t_rpg_ign"
-- Sorties : :"t_recouvrement"  toutes les paires qui se chevauchent
--           :"t_appariement"   pour chaque parcelle bio, sa parcelle RPG
--                              de plus fort recouvrement
--           :"t_ign_remplace"  parcelles RPG couvertes par du bio
-- Variables psql : schema, t_rpg_bio, t_rpg_ign, t_recouvrement,
--                  t_appariement, t_ign_remplace, seuil
--
-- Le script de 2024 cherchait la parcelle RPG au centroïde le plus proche.
-- Deux défauts : une parcelle RPG voisine pouvait être retenue alors qu'une
-- autre chevauchait davantage, et une parcelle RPG couverte par une parcelle
-- bio non retenue comme « plus proche » restait en double. Le recouvrement
-- mesuré directement corrige les deux.
-- =====================================================================

DROP TABLE IF EXISTS :"schema".:"t_recouvrement" CASCADE;
CREATE TABLE :"schema".:"t_recouvrement" AS
SELECT
    b.id_source                                    AS bio_id,
    i.id_source                                    AS ign_id,
    ST_Area(ST_Intersection(b.geom, i.geom)) / 10000 AS surface_commune_ha,
    b.surface_ha                                   AS surface_bio_ha,
    i.surface_ha                                   AS surface_ign_ha
FROM :"schema".:"t_rpg_bio" b
    JOIN :"schema".:"t_rpg_ign" i ON ST_Intersects(b.geom, i.geom);

-- Les contacts par un bord ou un sommet n'ont pas de surface commune.
DELETE FROM :"schema".:"t_recouvrement" WHERE surface_commune_ha <= 0;
CREATE INDEX ON :"schema".:"t_recouvrement" (bio_id);
CREATE INDEX ON :"schema".:"t_recouvrement" (ign_id);
ANALYZE :"schema".:"t_recouvrement";

-- Taux de recouvrement rapporté à la plus petite des deux parcelles :
-- une parcelle bio découpée en deux dans CartoBio garde un taux élevé
-- avec la parcelle RPG qui la contient.
DROP TABLE IF EXISTS :"schema".:"t_appariement" CASCADE;
CREATE TABLE :"schema".:"t_appariement" AS
SELECT DISTINCT ON (r.bio_id)
    r.bio_id,
    r.ign_id,
    r.surface_commune_ha,
    r.surface_commune_ha / NULLIF(LEAST(r.surface_bio_ha, r.surface_ign_ha), 0) AS taux,
    r.surface_commune_ha / NULLIF(LEAST(r.surface_bio_ha, r.surface_ign_ha), 0) >= :seuil
                                                                               AS retenu
FROM :"schema".:"t_recouvrement" r
ORDER BY r.bio_id, r.surface_commune_ha DESC, r.ign_id;

ALTER TABLE :"schema".:"t_appariement" ADD PRIMARY KEY (bio_id);
ANALYZE :"schema".:"t_appariement";

-- Priorité au bio : une parcelle RPG est remplacée dès que l'ensemble des
-- parcelles bio qui la chevauchent couvre au moins :seuil de sa surface.
DROP TABLE IF EXISTS :"schema".:"t_ign_remplace" CASCADE;
CREATE TABLE :"schema".:"t_ign_remplace" AS
SELECT
    r.ign_id,
    sum(r.surface_commune_ha)                       AS surface_bio_ha,
    sum(r.surface_commune_ha) / max(r.surface_ign_ha) AS taux_couverture
FROM :"schema".:"t_recouvrement" r
GROUP BY r.ign_id
HAVING sum(r.surface_commune_ha) / NULLIF(max(r.surface_ign_ha), 0) >= :seuil;

ALTER TABLE :"schema".:"t_ign_remplace" ADD PRIMARY KEY (ign_id);
ANALYZE :"schema".:"t_ign_remplace";
