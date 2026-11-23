-- =====================================================================
-- ÉTAPE 07 : CALCULER LES INDICATEURS
-- =====================================================================
--
-- À quoi sert ce script ?
--   Il résume les tables précédentes en trois tables d'indicateurs, celles
--   qui sont exportées en CSV et affichées sur la page web.
--
-- Ce qu'il lit   : aac, parcel, parcel_aac, parcel_dans_aac, :t_rpg_ign, :src_rpg
-- Ce qu'il crée  : synthese_aac        une ligne par AAC et par millésime
--                  synthese_categorie  une ligne par catégorie de culture
--                  synthese_nationale  une ligne par millésime : chiffres clés
--
-- Vocabulaire :
--   SAU       surface agricole utile : ici, la surface des parcelles agricoles
--             situées à l'intérieur des AAC, en hectares ;
--   part bio  surface bio (certifiée + en conversion + constatée bio dans le
--             RPG) divisée par la SAU, entre 0 et 1.
--
-- Deux outils SQL reviennent souvent :
--   sum(x) FILTER (WHERE condition)  additionne x seulement sur les lignes qui
--                                    respectent la condition. Exemple :
--                                    sum(surface) FILTER (WHERE bio) donne la
--                                    surface bio. Sans aucune ligne, le résultat
--                                    est NULL ;
--   COALESCE(x, 0)                   remplace ce NULL par 0.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Indicateurs par AAC
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS :"schema".synthese_aac (
    annee                  integer NOT NULL,
    cdaac                  text    NOT NULL,
    nom                    text,
    surface_aac_ha         double precision,  -- surface totale de l'AAC
    nb_parcelles           integer,           -- parcelles qui la touchent
    sau_ha                 double precision,  -- surface agricole dans l'AAC
    sau_bio_ha             double precision,  -- dont bio (toutes formes)
    sau_ab_ha              double precision,  -- dont certifiée AB
    sau_conversion_ha      double precision,  -- dont en conversion (C1 à C3)
    sau_bio_pac_seul_ha    double precision,  -- dont constatée bio dans le RPG seulement
    part_sau               double precision,  -- part de l'AAC occupée par l'agriculture
    part_bio               double precision,  -- part bio de la surface agricole
    categorie_dominante    text,              -- catégorie de culture la plus étendue
    part_categorie_dominante double precision,
    PRIMARY KEY (annee, cdaac)
);
DELETE FROM :"schema".synthese_aac WHERE annee = :annee;

-- WITH définit des requêtes intermédiaires nommées (par_aac, par_categorie,
-- dominante), utilisées ensuite comme des tables temporaires.
WITH
-- Totaux de surface par AAC.
par_aac AS (
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
-- Surface de chaque catégorie de culture dans chaque AAC.
par_categorie AS (
    SELECT pa.cdaac, p.categorie, sum(pa.surface_dans_aac_ha) AS surface_ha
    FROM :"schema".parcel_aac pa
        JOIN :"schema".parcel p ON p.annee = pa.annee AND p.id_parcel = pa.id_parcel
    WHERE pa.annee = :annee
    GROUP BY pa.cdaac, p.categorie
),
-- Catégorie la plus étendue de chaque AAC : DISTINCT ON garde la première
-- ligne par AAC, triée par surface décroissante (voir l'étape 04).
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
       -- Une AAC agricole sans parcelle bio a une part de 0, pas une part
       -- inconnue. Une AAC sans aucune surface agricole garde une part NULL :
       -- diviser par une SAU nulle n'a pas de sens (NULLIF évite l'erreur).
       COALESCE(s.sau_bio_ha, 0) / NULLIF(s.sau_ha, 0),
       d.categorie,
       d.surface_ha / NULLIF(s.sau_ha, 0)
-- On part de la table aac et non des parcelles, avec des LEFT JOIN : ainsi,
-- toutes les AAC figurent dans le résultat, même celles sans aucune parcelle.
FROM :"schema".aac a
    LEFT JOIN par_aac s   ON s.cdaac = a.cdaac
    LEFT JOIN dominante d ON d.cdaac = a.cdaac;


-- ---------------------------------------------------------------------
-- 2. Indicateurs par catégorie de culture, toutes AAC confondues
-- ---------------------------------------------------------------------
-- On utilise parcel_dans_aac (et non parcel_aac) pour que les zones où des
-- AAC se superposent ne soient comptées qu'une fois (voir l'étape 06).
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


-- ---------------------------------------------------------------------
-- 3. Chiffres clés du millésime
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS :"schema".synthese_nationale (
    annee                    integer PRIMARY KEY,
    nb_aac                   integer,           -- nombre d'AAC analysées
    nb_aac_avec_sau          integer,           -- dont AAC avec au moins une parcelle
    surface_aac_ha           double precision,  -- surface de toutes les AAC, sans double compte
    sau_aac_ha               double precision,  -- surface agricole dans les AAC
    sau_bio_aac_ha           double precision,  -- dont bio
    part_bio_aac             double precision,  -- part bio
    nb_parcelles_aac         integer,
    part_bio_pac_aac         double precision,  -- part bio selon le RPG seul, dans les AAC
    part_bio_pac_france      double precision   -- part bio selon le RPG seul, sur tout le fichier
);
DELETE FROM :"schema".synthese_nationale WHERE annee = :annee;

-- Chaque valeur entre parenthèses (SELECT ...) est une petite requête qui
-- renvoie un seul nombre. La requête principale (FROM (...) t, à la fin)
-- calcule les surfaces agricoles.
INSERT INTO :"schema".synthese_nationale
SELECT
    :annee,
    (SELECT count(*) FROM :"schema".aac),
    (SELECT count(*) FROM :"schema".synthese_aac WHERE annee = :annee AND sau_ha > 0),
    -- ST_Collect regroupe toutes les AAC, ST_UnaryUnion les fusionne : les
    -- zones de superposition ne sont comptées qu'une fois.
    (SELECT ST_Area(ST_UnaryUnion(ST_Collect(geom))) / 10000 FROM :"schema".aac),
    t.sau, t.sau_bio, t.sau_bio / NULLIF(t.sau, 0), t.nb,
    -- Comparaison à base égale : CartoBio n'existe pas « hors AAC » dans nos
    -- tables, donc pour comparer les AAC au reste du territoire on utilise une
    -- seule source, l'information « constatée bio » du RPG :
    --   d'abord sur les parcelles RPG qui touchent une AAC...
    (SELECT sum(i.surface_ha) FILTER (WHERE i.bio_pac) / NULLIF(sum(i.surface_ha), 0)
       FROM :"schema".:"t_rpg_ign" i
      WHERE EXISTS (SELECT 1 FROM :"schema".aac a WHERE ST_Intersects(a.geom, i.geom))),
    --   ...puis sur tout le fichier RPG chargé. Si ce fichier a été pré-filtré
    --   autour des AAC, cette valeur est remplacée ensuite par celle calculée
    --   sur le RPG complet (voir chargement.appliquer_stats_nationales).
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
