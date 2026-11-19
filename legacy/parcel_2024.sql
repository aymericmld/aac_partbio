-- =====================================================================
-- SCRIPT : Construction de la table parcel
-- OBJECTIF : Croisement des AAC et des parcelles en fusionnant le RPG bio et le RPG IGN 2024 en une seule table
--            de parcelles et en donnant la priorité aux parcelles bio
--            lorsqu'elles correspondent (recouvrement spatial)
--            à une parcelle IGN.
--
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. EMPRISE DE TRAVAIL : UNION DES AAC + BUFFER
-- ---------------------------------------------------------------------

CREATE INDEX CONCURRENTLY IF NOT EXISTS rpg_francemet_2024_geom_idx
    ON public.rpg_francemet_2024 USING GIST (geom);

CREATE INDEX CONCURRENTLY IF NOT EXISTS parcelles_bio_francemet_2024_geom_idx
    ON public.parcelles_bio_francemet_2024 USING GIST (geom);

CREATE INDEX CONCURRENTLY IF NOT EXISTS aac_france_112024_geom_idx
    ON public.aac_france_112024 USING GIST (geom);

DROP TABLE IF EXISTS public.aac_emprise CASCADE;
CREATE TABLE public.aac_emprise AS
SELECT
    ST_Union(
        ST_Buffer(ST_Transform(geom, 2154), 500) 
    ) AS geom
FROM public.aac_france_112024;

CREATE INDEX aac_emprise_geom_idx ON public.aac_emprise USING GIST (geom);
ANALYZE public.aac_emprise;


-- ---------------------------------------------------------------------
-- 1. TABLE FINALE parcel
-- ---------------------------------------------------------------------

DROP TABLE IF EXISTS public.parcel CASCADE;

CREATE TABLE public.parcel
(
    id       bigserial      NOT NULL,
    year     integer        NOT NULL,
    id_parcel text,
    categorie      character varying COLLATE pg_catalog."default",
    conversion      character varying COLLATE pg_catalog."default",
    surface  numeric(12,2),
    geom     geometry(Geometry, 2154),
    CONSTRAINT parcel_pkey PRIMARY KEY (id),
    CONSTRAINT parcel_year_id_parcel_uq UNIQUE (year, id_parcel)
);


CREATE INDEX parcel_geom_idx ON public.parcel USING GIST (geom);
CREATE INDEX parcel_id_parcel_idx ON public.parcel (id_parcel);


-- ---------------------------------------------------------------------
-- 2. INDEX DE SUPPORT SUR LA TABLE DE REFERENCE cpf_pac
-- ---------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS code_production_idx ON public.liste_cultures_cpfbio_classifie (code_production);
CREATE INDEX IF NOT EXISTS code_culture_idx ON public.ref_cultures_groupes_cultures (code_culture);



-- ---------------------------------------------------------------------
-- 3. VUE MATERIALISEE : RPG BIO 2024
-- ---------------------------------------------------------------------

DROP MATERIALIZED VIEW IF EXISTS public.mv_rpg_bio CASCADE;
CREATE MATERIALIZED VIEW public.mv_rpg_bio
AS
    SELECT
        concat('AB', fid)                              AS id_parcel,
        cp.categorie                                   AS categorie,
        bio.convers                                 AS conversion,
        bio.surface::double precision               AS surface,
        ST_Centroid(g.geom_valid)  AS center,
        g.geom_valid              AS geom
    FROM public.parcelles_bio_francemet_2024 bio
        CROSS JOIN LATERAL (SELECT ST_Transform(ST_MakeValid(bio.geom),2154) AS geom_valid) g
        LEFT JOIN public.liste_cultures_cpfbio_classifie cp ON bio.culture = cp.code_production
    WHERE EXISTS (
        SELECT 1 FROM public.aac_emprise e
        WHERE ST_Intersects(g.geom_valid, e.geom)
    )
WITH DATA;

CREATE INDEX mv_rpg_bio_id_parcel_idx ON public.mv_rpg_bio (id_parcel);
CREATE INDEX mv_rpg_bio_center_idx    ON public.mv_rpg_bio USING GIST (center);
CREATE INDEX mv_rpg_bio_geom_idx      ON public.mv_rpg_bio USING GIST (geom);

ANALYZE public.mv_rpg_bio;


-- ---------------------------------------------------------------------
-- 4. VUE MATERIALISEE : RPG IGN 2024
-- ---------------------------------------------------------------------

DROP MATERIALIZED VIEW IF EXISTS public.mv_rpg_ign CASCADE;
CREATE MATERIALIZED VIEW public.mv_rpg_ign
AS
    SELECT
        cast(ign.fid  as text)                                AS id_parcel,
        cp.categorie                                   AS categorie,
        'CONV'                                         AS conversion,
        ign.surf_parc                                  AS surface,
        ST_Centroid(g.geom_valid)  AS center,
        g.geom_valid               AS geom
    FROM public.rpg_francemet_2024 ign
        CROSS JOIN LATERAL (SELECT ST_Transform(ST_MakeValid(ign.geom),2154) AS geom_valid) g
        LEFT JOIN public.ref_cultures_groupes_cultures cp ON ign.code_cultu = cp.code_culture
    WHERE EXISTS (
        SELECT 1 FROM public.aac_emprise e
        WHERE ST_Intersects(g.geom_valid, e.geom)
    )
WITH DATA;

CREATE INDEX mv_rpg_ign_id_parcel_idx ON public.mv_rpg_ign (id_parcel);
CREATE INDEX mv_rpg_ign_center_idx    ON public.mv_rpg_ign USING GIST (center);
CREATE INDEX mv_rpg_ign_geom_idx      ON public.mv_rpg_ign USING GIST (geom);

ANALYZE public.mv_rpg_ign;


-- ---------------------------------------------------------------------
-- 5. VUE MATERIALISEE : APPARIEMENT BIO <-> IGN
-- ---------------------------------------------------------------------

DROP MATERIALIZED VIEW IF EXISTS public.mv_rpg CASCADE;
CREATE MATERIALIZED VIEW public.mv_rpg
AS
SELECT
    bio.id_parcel                          AS bio_id_parcel,
    ign.id_parcel                          AS ign_id_parcel,
    ign.dist,
    bio.categorie                          AS bio_categorie,
    ign.categorie                          AS ign_categorie,
    bio.conversion                         AS bio_conversion,
    ign.conversion                         AS ign_conversion,
    ign.surface                            AS ign_surface,
    bio.surface                            AS bio_surface,
    abs(ign.surface - bio.surface)         AS diff_surface,
    bio.geom                               AS bio_geom,
    ign.geom                               AS ign_geom,
    ST_Intersects(bio.geom, ign.geom)      AS bio_ign_intersects
FROM public.mv_rpg_bio bio
    CROSS JOIN LATERAL (
        SELECT ign.id_parcel, ign.categorie, ign.conversion, ign.surface, ign.geom,
               ign.center <-> bio.center AS dist
        FROM public.mv_rpg_ign ign
        ORDER BY dist
        LIMIT 1
    ) ign
WITH DATA;

CREATE INDEX mv_rpg_ign2_id_parcel_idx ON public.mv_rpg (ign_id_parcel);
CREATE INDEX mv_rpg_bio2_id_parcel_idx ON public.mv_rpg (bio_id_parcel);

ANALYZE public.mv_rpg;


-- ---------------------------------------------------------------------
-- 6. PURGE DES DONNEES EXISTANTES POUR L'ANNEE 2024
-- ---------------------------------------------------------------------
DELETE FROM public.parcel WHERE year = 2024;


-- ---------------------------------------------------------------------
-- 7. INSERTION DES DONNEES FUSIONNEES
-- ---------------------------------------------------------------------

WITH joined AS (
    SELECT
        rpg.id_parcel   AS ign_id_parcel,
        rpg.categorie         AS ign_categorie,
        rpg.conversion         AS ign_conversion,
        rpg.surface     AS ign_surface,
        rpg.geom        AS ign_geom,
        bio.bio_id_parcel,
        bio.bio_categorie,
        bio.bio_conversion,
        bio.bio_surface,
        bio.bio_geom,
        bio.bio_ign_intersects
    FROM public.mv_rpg_ign rpg
        FULL OUTER JOIN public.mv_rpg bio
            ON rpg.id_parcel = bio.ign_id_parcel
),
parcel_data AS (
    SELECT
        '2024'                                            AS year,
        COALESCE(bio_id_parcel, ign_id_parcel)           AS id_parcel,
        COALESCE(bio_categorie, ign_categorie)                       AS categorie,
        COALESCE(bio_conversion, ign_conversion)                       AS conversion,
        COALESCE(bio_surface, ign_surface)               AS surface,
        COALESCE(bio_geom, ign_geom)                     AS geom
    FROM joined

    union
    
    SELECT DISTINCT
        2024                AS year,
        ign_id_parcel       AS id_parcel,
        ign_categorie             AS categorie,
        ign_conversion            AS conversion,
        ign_surface         AS surface,
        ign_geom            AS geom
    FROM joined
    WHERE bio_ign_intersects IS FALSE
)
INSERT INTO public.parcel (year, id_parcel, categorie, conversion, surface, geom)
SELECT DISTINCT * FROM parcel_data;

-- ---------------------------------------------------------------------
-- 8. CREATION DE LA TABLE FINALE
-- ---------------------------------------------------------------------


drop table if exists parcel_aac;

create table parcel_aac as
select
    p.*,
    aac.cdaac 
from public.parcel p
right join public."aac_france_112024" aac
    on p.geom && ST_Transform(aac.geom,2154)
   and st_intersects(p.geom, ST_Transform(aac.geom,2154));



