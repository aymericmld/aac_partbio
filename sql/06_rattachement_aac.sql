-- =====================================================================
-- 06. RATTACHEMENT DES PARCELLES AUX AAC
-- Sorties : :"schema".parcel_aac       une ligne par couple parcelle x AAC
--           :"schema".parcel_dans_aac  une ligne par parcelle, surface dans
--                                      l'union des AAC (sans double compte)
-- Variables psql : schema, annee
--
-- Une parcelle qui chevauche la limite d'une AAC est rattachée à l'AAC,
-- mais seule la partie située dans l'AAC est comptée en surface.
-- Les AAC peuvent se superposer : parcel_dans_aac évite de compter deux
-- fois la même surface dans les totaux nationaux.
-- =====================================================================

CREATE TABLE IF NOT EXISTS :"schema".parcel_aac (
    annee                integer NOT NULL,
    id_parcel            text    NOT NULL,
    cdaac                text    NOT NULL,
    surface_dans_aac_ha  double precision NOT NULL,
    PRIMARY KEY (annee, id_parcel, cdaac)
);
DELETE FROM :"schema".parcel_aac WHERE annee = :annee;

INSERT INTO :"schema".parcel_aac (annee, id_parcel, cdaac, surface_dans_aac_ha)
SELECT p.annee, p.id_parcel, a.cdaac,
       ST_Area(ST_Intersection(p.geom, a.geom)) / 10000
FROM :"schema".parcel p
    JOIN :"schema".aac a ON ST_Intersects(p.geom, a.geom)
WHERE p.annee = :annee;

DELETE FROM :"schema".parcel_aac WHERE annee = :annee AND surface_dans_aac_ha <= 0;
CREATE INDEX IF NOT EXISTS parcel_aac_cdaac_idx ON :"schema".parcel_aac (annee, cdaac);

CREATE TABLE IF NOT EXISTS :"schema".parcel_dans_aac (
    annee                integer NOT NULL,
    id_parcel            text    NOT NULL,
    nb_aac               integer NOT NULL,
    surface_dans_aac_ha  double precision NOT NULL,
    PRIMARY KEY (annee, id_parcel)
);
DELETE FROM :"schema".parcel_dans_aac WHERE annee = :annee;

-- Pour une parcelle dans une seule AAC, la surface est déjà connue ;
-- l'union des AAC n'est calculée que pour les parcelles à cheval sur plusieurs.
INSERT INTO :"schema".parcel_dans_aac (annee, id_parcel, nb_aac, surface_dans_aac_ha)
SELECT pa.annee, pa.id_parcel, 1, pa.surface_dans_aac_ha
FROM :"schema".parcel_aac pa
WHERE pa.annee = :annee
  AND NOT EXISTS (
        SELECT 1 FROM :"schema".parcel_aac x
        WHERE x.annee = pa.annee AND x.id_parcel = pa.id_parcel AND x.cdaac <> pa.cdaac
  );

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
