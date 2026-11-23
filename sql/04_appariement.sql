-- =====================================================================
-- ÉTAPE 04 : RETROUVER CHAQUE PARCELLE BIO DANS LE RPG
-- =====================================================================
--
-- À quoi sert ce script ?
--   Une même parcelle peut figurer deux fois : dans le RPG (étape 02) et
--   dans CartoBio (étape 03). Si on additionnait les deux sources telles
--   quelles, sa surface serait comptée deux fois. Ce script repère les
--   parcelles qui se superposent, pour qu'à l'étape 05 on n'en garde qu'une,
--   en donnant la priorité à la version bio, plus précise sur le bio.
--
--   Les contours ne coïncident jamais exactement d'une source à l'autre :
--   on mesure donc la surface réellement commune entre deux parcelles, puis
--   on la compare à un seuil (:seuil, 0,5 par défaut, soit 50 %).
--
-- Ce qu'il lit   : :t_rpg_bio, :t_rpg_ign (étapes 02 et 03)
-- Ce qu'il crée  : :t_recouvrement  toutes les paires bio x RPG qui se chevauchent
--                  :t_appariement   pour chaque parcelle bio, la parcelle RPG
--                                   qu'elle recouvre le plus
--                  :t_ign_remplace  les parcelles RPG à retirer car déjà
--                                   couvertes par des parcelles bio
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Toutes les paires de parcelles qui se chevauchent
-- ---------------------------------------------------------------------
-- La jointure ON ST_Intersects(...) associe chaque parcelle bio à chaque
-- parcelle RPG qu'elle touche (grâce aux index spatiaux, PostGIS ne teste
-- que les parcelles proches). ST_Intersection dessine la zone commune,
-- ST_Area en donne la surface.
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

-- Deux parcelles voisines qui se touchent seulement par un bord ou un coin
-- « s'intersectent » pour PostGIS, mais leur surface commune est nulle :
-- ce ne sont pas des doublons, on les retire.
DELETE FROM :"schema".:"t_recouvrement" WHERE surface_commune_ha <= 0;

-- Index simples (non spatiaux) pour accélérer les regroupements qui suivent.
CREATE INDEX ON :"schema".:"t_recouvrement" (bio_id);
CREATE INDEX ON :"schema".:"t_recouvrement" (ign_id);
ANALYZE :"schema".:"t_recouvrement";


-- ---------------------------------------------------------------------
-- 2. Pour chaque parcelle bio, la parcelle RPG qu'elle recouvre le plus
-- ---------------------------------------------------------------------
-- DISTINCT ON (bio_id) garde une seule ligne par parcelle bio : la première
-- selon l'ordre du ORDER BY, donc celle qui a la plus grande surface commune
-- (DESC = décroissant). ign_id sert à départager deux ex aequo, pour que le
-- résultat soit toujours le même d'une exécution à l'autre.
--
-- Le taux de recouvrement divise la surface commune par la plus petite des
-- deux parcelles (LEAST). Exemple : une parcelle RPG de 2 ha découpée en deux
-- parcelles bio de 1 ha. Chaque moitié est entièrement dans la parcelle RPG :
-- son taux vaut 1 ha / 1 ha = 100 %, et elle est bien appariée. Rapporté à la
-- plus grande parcelle, le taux ne serait que de 50 %.
--
-- NULLIF(x, 0) renvoie NULL si x vaut 0 : cela évite une erreur de division
-- par zéro sur une parcelle de surface nulle.
--
-- La colonne « retenu » vaut vrai quand le taux atteint le seuil : on
-- considère alors que les deux parcelles décrivent le même terrain.
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


-- ---------------------------------------------------------------------
-- 3. Les parcelles RPG à remplacer par du bio
-- ---------------------------------------------------------------------
-- On raisonne maintenant du point de vue de chaque parcelle RPG : on
-- additionne la surface de toutes les parcelles bio qui la chevauchent
-- (GROUP BY ign_id + sum). Si ce total couvre au moins :seuil de sa surface,
-- la parcelle RPG est remplacée par ces parcelles bio à l'étape 05.
--
-- HAVING filtre après le regroupement (WHERE filtrerait avant). max() sert
-- seulement à récupérer la surface de la parcelle RPG, identique sur toutes
-- les lignes du groupe.
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
