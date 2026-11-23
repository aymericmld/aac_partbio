-- =====================================================================
-- ÉTAPE 05 : CONSTRUIRE UN SEUL RÉFÉRENTIEL DE PARCELLES
-- =====================================================================
--
-- À quoi sert ce script ?
--   Il assemble les deux sources en une seule table, parcel, où chaque
--   morceau de terrain n'apparaît qu'une fois :
--     - toutes les parcelles bio (CartoBio) sont gardées ;
--     - les parcelles RPG sont gardées, sauf celles déjà couvertes par du
--       bio (liste établie à l'étape 04).
--
-- Ce qu'il lit   : :t_rpg_bio, :t_rpg_ign, :t_appariement, :t_ign_remplace
-- Ce qu'il crée  : parcel (si elle n'existe pas encore)
--
-- La colonne annee indique l'année des données (2025 dans ce projet). Si l'on
-- traitait un jour une autre année, ses lignes s'ajouteraient à côté :
-- chaque exécution efface puis réécrit seulement son année.
--
-- Signification des colonnes :
--   source      cartobio_rpg       parcelle bio retrouvée dans le RPG
--               cartobio_hors_rpg  parcelle bio absente du RPG
--               rpg                parcelle RPG gardée telle quelle
--   conversion  AB                 certifiée bio
--               C1, C2, C3         en 1re, 2e ou 3e année de conversion
--               BIO_PAC            constatée bio dans le RPG, sans parcelle
--                                  CartoBio correspondante
--               CONV               conventionnelle (tout le reste)
--   bio         vrai pour toutes les valeurs de conversion sauf CONV
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Créer la table si c'est la première exécution
-- ---------------------------------------------------------------------
-- CREATE TABLE IF NOT EXISTS ne fait rien si la table existe déjà : les
-- autres années déjà calculées sont préservées.
CREATE TABLE IF NOT EXISTS :"schema".parcel (
    id                bigserial PRIMARY KEY,     -- numéro automatique
    annee             integer   NOT NULL,        -- année des données
    id_parcel         text      NOT NULL,        -- identifiant d'origine (RPG ou « AB... »)
    source            text      NOT NULL,        -- voir l'en-tête
    id_rpg_apparie    text,                      -- parcelle RPG correspondante, si elle existe
    code_culture      text,
    categorie         text      NOT NULL,        -- une des 8 catégories, ou « Non classé »
    conversion        text      NOT NULL,        -- voir l'en-tête
    bio               boolean   NOT NULL,
    surface_declaree_ha double precision,
    surface_ha        double precision NOT NULL, -- surface calculée sur le dessin
    geom              geometry(MultiPolygon, 2154) NOT NULL,
    -- Une même parcelle ne peut apparaître qu'une fois par année.
    CONSTRAINT parcel_annee_id_uq UNIQUE (annee, id_parcel)
);
CREATE INDEX IF NOT EXISTS parcel_geom_idx  ON :"schema".parcel USING GIST (geom);
CREATE INDEX IF NOT EXISTS parcel_annee_idx ON :"schema".parcel (annee);


-- ---------------------------------------------------------------------
-- 2. Effacer l'année en cours de calcul, pour pouvoir relancer le script
-- ---------------------------------------------------------------------
DELETE FROM :"schema".parcel WHERE annee = :annee;


-- ---------------------------------------------------------------------
-- 3. Remplir la table : parcelles bio, puis parcelles RPG restantes
-- ---------------------------------------------------------------------
-- Deux requêtes SELECT sont mises bout à bout par UNION ALL. Elles doivent
-- renvoyer les mêmes colonnes, dans le même ordre que la liste de l'INSERT.
INSERT INTO :"schema".parcel
    (annee, id_parcel, source, id_rpg_apparie, code_culture, categorie, conversion, bio,
     surface_declaree_ha, surface_ha, geom)

-- 3a. Toutes les parcelles bio.
--     LEFT JOIN : une parcelle bio qui ne recouvre aucune parcelle RPG n'a pas
--     de ligne dans t_appariement ; elle est gardée, avec a.retenu à NULL.
--     CASE WHEN ... THEN ... ELSE ... END : un « si ... alors ... sinon ».
--     COALESCE(a, b) renvoie a, ou b si a est NULL.
SELECT
    :annee,
    b.id_source,
    CASE WHEN a.retenu THEN 'cartobio_rpg' ELSE 'cartobio_hors_rpg' END,
    CASE WHEN a.retenu THEN a.ign_id END,
    b.code_culture,
    COALESCE(b.categorie, 'Non classé'),
    -- Niveau de conversion manquant : la parcelle figure dans CartoBio, on la
    -- considère comme certifiée (AB).
    COALESCE(NULLIF(b.conversion, ''), 'AB'),
    true,
    b.surface_declaree_ha,
    b.surface_ha,
    b.geom
FROM :"schema".:"t_rpg_bio" b
    LEFT JOIN :"schema".:"t_appariement" a ON a.bio_id = b.id_source

UNION ALL

-- 3b. Les parcelles RPG, sauf celles remplacées par du bio (étape 04).
--     NOT EXISTS (...) est vrai quand la sous-requête ne trouve aucune ligne,
--     c'est-à-dire quand la parcelle n'est pas dans t_ign_remplace.
SELECT
    :annee,
    i.id_source,
    'rpg',
    i.id_source,
    i.code_culture,
    COALESCE(i.categorie, 'Non classé'),
    CASE WHEN i.bio_pac THEN 'BIO_PAC' ELSE 'CONV' END,
    -- bio_pac vaut NULL quand le RPG n'a pas d'information bio : on le
    -- considère alors comme faux.
    COALESCE(i.bio_pac, false),
    i.surface_declaree_ha,
    i.surface_ha,
    i.geom
FROM :"schema".:"t_rpg_ign" i
WHERE NOT EXISTS (SELECT 1 FROM :"schema".:"t_ign_remplace" r WHERE r.ign_id = i.id_source);

ANALYZE :"schema".parcel;
