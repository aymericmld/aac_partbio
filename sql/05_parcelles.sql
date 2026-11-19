-- =====================================================================
-- 05. RÉFÉRENTIEL PARCELLAIRE FUSIONNÉ
-- Sortie : :"schema".parcel (tous millésimes ; celui-ci est remplacé)
-- Variables psql : schema, annee, t_rpg_bio, t_rpg_ign, t_appariement,
--                  t_ign_remplace
--
-- conversion : AB, C1, C2, C3 (CartoBio), BIO_PAC (constatée bio dans le
--              RPG sans parcelle CartoBio correspondante), CONV (le reste)
-- source     : cartobio_rpg       parcelle bio appariée à une parcelle RPG
--              cartobio_hors_rpg  parcelle bio sans équivalent RPG
--              rpg                parcelle RPG conservée
-- =====================================================================

CREATE TABLE IF NOT EXISTS :"schema".parcel (
    id                bigserial PRIMARY KEY,
    annee             integer   NOT NULL,
    id_parcel         text      NOT NULL,
    source            text      NOT NULL,
    id_rpg_apparie    text,
    code_culture      text,
    categorie         text      NOT NULL,
    conversion        text      NOT NULL,
    bio               boolean   NOT NULL,
    surface_declaree_ha double precision,
    surface_ha        double precision NOT NULL,
    geom              geometry(MultiPolygon, 2154) NOT NULL,
    CONSTRAINT parcel_annee_id_uq UNIQUE (annee, id_parcel)
);
CREATE INDEX IF NOT EXISTS parcel_geom_idx  ON :"schema".parcel USING GIST (geom);
CREATE INDEX IF NOT EXISTS parcel_annee_idx ON :"schema".parcel (annee);

DELETE FROM :"schema".parcel WHERE annee = :annee;

INSERT INTO :"schema".parcel
    (annee, id_parcel, source, id_rpg_apparie, code_culture, categorie, conversion, bio,
     surface_declaree_ha, surface_ha, geom)
SELECT
    :annee,
    b.id_source,
    CASE WHEN a.retenu THEN 'cartobio_rpg' ELSE 'cartobio_hors_rpg' END,
    CASE WHEN a.retenu THEN a.ign_id END,
    b.code_culture,
    COALESCE(b.categorie, 'Non classé'),
    COALESCE(NULLIF(b.conversion, ''), 'AB'),
    true,
    b.surface_declaree_ha,
    b.surface_ha,
    b.geom
FROM :"schema".:"t_rpg_bio" b
    LEFT JOIN :"schema".:"t_appariement" a ON a.bio_id = b.id_source

UNION ALL

SELECT
    :annee,
    i.id_source,
    'rpg',
    i.id_source,
    i.code_culture,
    COALESCE(i.categorie, 'Non classé'),
    CASE WHEN i.bio_pac THEN 'BIO_PAC' ELSE 'CONV' END,
    COALESCE(i.bio_pac, false),
    i.surface_declaree_ha,
    i.surface_ha,
    i.geom
FROM :"schema".:"t_rpg_ign" i
WHERE NOT EXISTS (SELECT 1 FROM :"schema".:"t_ign_remplace" r WHERE r.ign_id = i.id_source);

ANALYZE :"schema".parcel;
