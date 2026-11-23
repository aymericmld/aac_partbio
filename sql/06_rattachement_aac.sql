-- =====================================================================
-- ÉTAPE 06 : RATTACHER LES PARCELLES AUX AAC
-- =====================================================================
--
-- À quoi sert ce script ?
--   Il indique dans quelle(s) AAC se trouve chaque parcelle, et quelle
--   surface de la parcelle est réellement à l'intérieur. Deux règles :
--
--   1. Seule la partie intérieure compte. Une parcelle de 10 ha dont 3 ha
--      sont dans l'AAC n'apporte que 3 ha à cette AAC.
--
--   2. Pas de double compte dans les totaux. Des AAC voisines peuvent se
--      superposer. Une parcelle située dans la zone commune à deux AAC compte
--      pour chacune d'elles, mais ne doit compter qu'une fois dans le total
--      national.
--
-- Ce qu'il lit   : parcel (étape 05), aac (étape 01)
-- Ce qu'il crée  : parcel_aac       une ligne par couple parcelle x AAC
--                                   (sert aux chiffres par AAC)
--                  parcel_dans_aac  une ligne par parcelle, avec sa surface
--                                   dans l'ensemble des AAC (sert aux totaux)
--
-- Contrairement à l'étape 01, aucun tampon ici : on se limite aux AAC
-- elles-mêmes.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Couples parcelle x AAC
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS :"schema".parcel_aac (
    annee                integer NOT NULL,
    id_parcel            text    NOT NULL,
    cdaac                text    NOT NULL,
    surface_dans_aac_ha  double precision NOT NULL,   -- partie de la parcelle dans cette AAC
    PRIMARY KEY (annee, id_parcel, cdaac)
);
DELETE FROM :"schema".parcel_aac WHERE annee = :annee;

-- Chaque parcelle est associée à chaque AAC qu'elle touche. ST_Intersection
-- découpe la parcelle selon le contour de l'AAC ; ST_Area mesure le résultat.
INSERT INTO :"schema".parcel_aac (annee, id_parcel, cdaac, surface_dans_aac_ha)
SELECT p.annee, p.id_parcel, a.cdaac,
       ST_Area(ST_Intersection(p.geom, a.geom)) / 10000
FROM :"schema".parcel p
    JOIN :"schema".aac a ON ST_Intersects(p.geom, a.geom)
WHERE p.annee = :annee;

-- Une parcelle qui touche l'AAC seulement par son bord a une surface
-- intérieure nulle : on la retire.
DELETE FROM :"schema".parcel_aac WHERE annee = :annee AND surface_dans_aac_ha <= 0;
CREATE INDEX IF NOT EXISTS parcel_aac_cdaac_idx ON :"schema".parcel_aac (annee, cdaac);


-- ---------------------------------------------------------------------
-- 2. Surface de chaque parcelle dans l'ensemble des AAC
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS :"schema".parcel_dans_aac (
    annee                integer NOT NULL,
    id_parcel            text    NOT NULL,
    nb_aac               integer NOT NULL,            -- nombre d'AAC touchées
    surface_dans_aac_ha  double precision NOT NULL,   -- surface comptée une seule fois
    PRIMARY KEY (annee, id_parcel)
);
DELETE FROM :"schema".parcel_dans_aac WHERE annee = :annee;

-- 2a. Cas le plus fréquent : la parcelle n'est que dans une AAC. Sa surface
--     est déjà connue, on la recopie (calcul géométrique inutile).
INSERT INTO :"schema".parcel_dans_aac (annee, id_parcel, nb_aac, surface_dans_aac_ha)
SELECT pa.annee, pa.id_parcel, 1, pa.surface_dans_aac_ha
FROM :"schema".parcel_aac pa
WHERE pa.annee = :annee
  -- « il n'existe pas d'autre AAC pour cette même parcelle »
  AND NOT EXISTS (
        SELECT 1 FROM :"schema".parcel_aac x
        WHERE x.annee = pa.annee AND x.id_parcel = pa.id_parcel AND x.cdaac <> pa.cdaac
  );

-- 2b. Parcelle dans plusieurs AAC : on fusionne ces AAC (ST_Union) puis on
--     mesure la partie de la parcelle dans cette zone fusionnée. La zone où
--     les AAC se superposent n'est ainsi comptée qu'une fois.
--     HAVING count(*) > 1 limite le calcul aux parcelles touchant au moins 2 AAC.
INSERT INTO :"schema".parcel_dans_aac (annee, id_parcel, nb_aac, surface_dans_aac_ha)
SELECT p.annee, p.id_parcel, count(*),
       ST_Area(ST_Intersection(p.geom, ST_Union(a.geom))) / 10000
FROM :"schema".parcel p
    JOIN :"schema".parcel_aac pa ON pa.annee = p.annee AND pa.id_parcel = p.id_parcel
    JOIN :"schema".aac a ON a.cdaac = pa.cdaac
WHERE p.annee = :annee
GROUP BY p.annee, p.id_parcel, p.geom
HAVING count(*) > 1;

ANALYZE :"schema".parcel_aac;
ANALYZE :"schema".parcel_dans_aac;
