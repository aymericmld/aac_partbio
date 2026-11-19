-- =====================================================================
-- 07. TABLES DE SYNTHÈSE
-- Sorties : :"schema".synthese_aac         une ligne par AAC et millésime
--           :"schema".synthese_categorie   surfaces par catégorie (sans
--                                          double compte entre AAC)
--           :"schema".synthese_nationale   indicateurs clés du millésime
-- Variables psql : schema, annee, src_rpg, t_rpg_ign, rpg_surface,
--                  rpg_bio_expr
-- Les surfaces agricoles sont celles des parcelles situées dans les AAC
-- (partie intérieure seulement), en hectares.
-- =====================================================================

-- --- Par AAC -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS :"schema".synthese_aac (
    annee                  integer NOT NULL,
    cdaac                  text    NOT NULL,
    nom                    text,
    surface_aac_ha         double precision,
    nb_parcelles           integer,
    sau_ha                 double precision,
    sau_bio_ha             double precision,
    sau_ab_ha              double precision,
    sau_conversion_ha      double precision,
    sau_bio_pac_seul_ha    double precision,
    part_sau               double precision,
    part_bio               double precision,
    categorie_dominante    text,
    part_categorie_dominante double precision,
    PRIMARY KEY (annee, cdaac)
);
DELETE FROM :"schema".synthese_aac WHERE annee = :annee;

WITH par_aac AS (
    SELECT pa.cdaac,
           count(*)                                                          AS nb_parcelles,
           sum(pa.surface_dans_aac_ha)                                       AS sau_ha,
           sum(pa.surface_dans_aac_ha) FILTER (WHERE p.bio)                  AS sau_bio_ha,
           sum(pa.surface_dans_aac_ha) FILTER (WHERE p.conversion = 'AB')    AS sau_ab_ha,
           sum(pa.surface_dans_aac_ha) FILTER (WHERE p.conversion IN ('C1','C2','C3'))
                                                                             AS sau_conversion_ha,
           sum(pa.surface_dans_aac_ha) FILTER (WHERE p.conversion = 'BIO_PAC')
                                                                             AS sau_bio_pac_seul_ha
    FROM :"schema".parcel_aac pa
        JOIN :"schema".parcel p ON p.annee = pa.annee AND p.id_parcel = pa.id_parcel
    WHERE pa.annee = :annee
    GROUP BY pa.cdaac
),
par_categorie AS (
    SELECT pa.cdaac, p.categorie, sum(pa.surface_dans_aac_ha) AS surface_ha
    FROM :"schema".parcel_aac pa
        JOIN :"schema".parcel p ON p.annee = pa.annee AND p.id_parcel = pa.id_parcel
    WHERE pa.annee = :annee
    GROUP BY pa.cdaac, p.categorie
),
dominante AS (
    SELECT DISTINCT ON (cdaac) cdaac, categorie, surface_ha
    FROM par_categorie
    ORDER BY cdaac, surface_ha DESC, categorie
)
INSERT INTO :"schema".synthese_aac
SELECT :annee, a.cdaac, a.nom, a.surface_ha,
       COALESCE(s.nb_parcelles, 0),
       COALESCE(s.sau_ha, 0),
       COALESCE(s.sau_bio_ha, 0),
       COALESCE(s.sau_ab_ha, 0),
       COALESCE(s.sau_conversion_ha, 0),
       COALESCE(s.sau_bio_pac_seul_ha, 0),
       COALESCE(s.sau_ha, 0) / NULLIF(a.surface_ha, 0),
       s.sau_bio_ha / NULLIF(s.sau_ha, 0),
       d.categorie,
       d.surface_ha / NULLIF(s.sau_ha, 0)
FROM :"schema".aac a
    LEFT JOIN par_aac s   ON s.cdaac = a.cdaac
    LEFT JOIN dominante d ON d.cdaac = a.cdaac;

-- --- Par catégorie, toutes AAC confondues -------------------------------
CREATE TABLE IF NOT EXISTS :"schema".synthese_categorie (
    annee              integer NOT NULL,
    categorie          text    NOT NULL,
    sau_ha             double precision,
    sau_bio_ha         double precision,
    sau_ab_ha          double precision,
    sau_conversion_ha  double precision,
    part_bio           double precision,
    PRIMARY KEY (annee, categorie)
);
DELETE FROM :"schema".synthese_categorie WHERE annee = :annee;

INSERT INTO :"schema".synthese_categorie
SELECT :annee, p.categorie,
       sum(d.surface_dans_aac_ha),
       COALESCE(sum(d.surface_dans_aac_ha) FILTER (WHERE p.bio), 0),
       COALESCE(sum(d.surface_dans_aac_ha) FILTER (WHERE p.conversion = 'AB'), 0),
       COALESCE(sum(d.surface_dans_aac_ha) FILTER (WHERE p.conversion IN ('C1','C2','C3')), 0),
       COALESCE(sum(d.surface_dans_aac_ha) FILTER (WHERE p.bio), 0)
           / NULLIF(sum(d.surface_dans_aac_ha), 0)
FROM :"schema".parcel_dans_aac d
    JOIN :"schema".parcel p ON p.annee = d.annee AND p.id_parcel = d.id_parcel
WHERE d.annee = :annee
GROUP BY p.categorie;

-- --- Indicateurs nationaux ----------------------------------------------
CREATE TABLE IF NOT EXISTS :"schema".synthese_nationale (
    annee                    integer PRIMARY KEY,
    nb_aac                   integer,
    nb_aac_avec_sau          integer,
    surface_aac_ha           double precision,
    sau_aac_ha               double precision,
    sau_bio_aac_ha           double precision,
    part_bio_aac             double precision,
    nb_parcelles_aac         integer,
    part_bio_pac_aac         double precision,
    part_bio_pac_france      double precision
);
DELETE FROM :"schema".synthese_nationale WHERE annee = :annee;

INSERT INTO :"schema".synthese_nationale
SELECT
    :annee,
    (SELECT count(*) FROM :"schema".aac),
    (SELECT count(*) FROM :"schema".synthese_aac WHERE annee = :annee AND sau_ha > 0),
    (SELECT ST_Area(ST_UnaryUnion(ST_Collect(geom))) / 10000 FROM :"schema".aac),
    t.sau, t.sau_bio, t.sau_bio / NULLIF(t.sau, 0), t.nb,
    -- Comparaison à base égale : part constatée bio dans le RPG seul,
    -- dans les AAC puis sur l'ensemble du fichier chargé.
    (SELECT sum(i.surface_ha) FILTER (WHERE i.bio_pac) / NULLIF(sum(i.surface_ha), 0)
       FROM :"schema".:"t_rpg_ign" i
      WHERE EXISTS (SELECT 1 FROM :"schema".aac a WHERE ST_Intersects(a.geom, i.geom))),
    (SELECT sum(ign.:"rpg_surface"::double precision) FILTER (WHERE :rpg_bio_expr)
              / NULLIF(sum(ign.:"rpg_surface"::double precision), 0)
       FROM :"schema".:"src_rpg" ign)
FROM (
    SELECT sum(d.surface_dans_aac_ha)                     AS sau,
           sum(d.surface_dans_aac_ha) FILTER (WHERE p.bio) AS sau_bio,
           count(*)                                       AS nb
    FROM :"schema".parcel_dans_aac d
        JOIN :"schema".parcel p ON p.annee = d.annee AND p.id_parcel = d.id_parcel
    WHERE d.annee = :annee
) t;
