"""
Schéma de la base de données SQLite
===================================
Modèle en étoile (star schema) pour l'entrepôt de données des offres d'emploi.

Structure :
- Table de faits : fait_offres (les offres d'emploi)
- Dimensions : lieu, entreprise, contrat, metier, temps, source, competence
"""

import sqlite3
from pathlib import Path

# =============================================================================
# SCHÉMA SQL
# =============================================================================

SCHEMA_SQL = """
-- ============================================================================
-- DIMENSIONS
-- ============================================================================

-- Dimension géographique (cruciale pour l'analyse régionale)
CREATE TABLE IF NOT EXISTS dim_lieu (
    id_lieu INTEGER PRIMARY KEY AUTOINCREMENT,
    code_postal VARCHAR(10),
    code_commune VARCHAR(10),
    commune VARCHAR(255),
    code_departement VARCHAR(5),
    departement VARCHAR(255),
    code_region VARCHAR(5),
    region VARCHAR(255),
    latitude REAL,
    longitude REAL,
    UNIQUE(code_commune)
);

-- Dimension entreprise
CREATE TABLE IF NOT EXISTS dim_entreprise (
    id_entreprise INTEGER PRIMARY KEY AUTOINCREMENT,
    nom VARCHAR(255),
    description TEXT,
    url_site VARCHAR(500),
    logo_url VARCHAR(500),
    secteur_activite VARCHAR(255),
    code_naf VARCHAR(10),
    taille VARCHAR(50),
    UNIQUE(nom)
);

-- Dimension type de contrat
CREATE TABLE IF NOT EXISTS dim_contrat (
    id_contrat INTEGER PRIMARY KEY AUTOINCREMENT,
    code_contrat VARCHAR(10),
    libelle_contrat VARCHAR(100),
    code_nature VARCHAR(10),
    libelle_nature VARCHAR(100),
    UNIQUE(code_contrat, code_nature)
);

-- Dimension métier (basée sur le référentiel ROME)
CREATE TABLE IF NOT EXISTS dim_metier (
    id_metier INTEGER PRIMARY KEY AUTOINCREMENT,
    code_rome VARCHAR(10),
    libelle_rome VARCHAR(255),
    code_domaine VARCHAR(5),
    libelle_domaine VARCHAR(255),
    code_grand_domaine VARCHAR(5),
    libelle_grand_domaine VARCHAR(255),
    UNIQUE(code_rome)
);

-- Dimension temps (pour l'analyse temporelle)
CREATE TABLE IF NOT EXISTS dim_temps (
    id_temps INTEGER PRIMARY KEY AUTOINCREMENT,
    date_complete DATE,
    jour INTEGER,
    mois INTEGER,
    annee INTEGER,
    trimestre INTEGER,
    semaine INTEGER,
    jour_semaine INTEGER,
    nom_jour VARCHAR(20),
    nom_mois VARCHAR(20),
    UNIQUE(date_complete)
);

-- Dimension source (France Travail, Welcome to the Jungle, etc.)
CREATE TABLE IF NOT EXISTS dim_source (
    id_source INTEGER PRIMARY KEY AUTOINCREMENT,
    nom_source VARCHAR(100),
    url_base VARCHAR(255),
    type_source VARCHAR(50),  -- 'api' ou 'scraping'
    UNIQUE(nom_source)
);

-- Dimension compétence
CREATE TABLE IF NOT EXISTS dim_competence (
    id_competence INTEGER PRIMARY KEY AUTOINCREMENT,
    code_competence VARCHAR(20),
    libelle_competence VARCHAR(255),
    type_competence VARCHAR(50),  -- 'savoir', 'savoir-faire', 'savoir-etre'
    UNIQUE(code_competence)
);

-- Dimension niveau d'expérience
CREATE TABLE IF NOT EXISTS dim_experience (
    id_experience INTEGER PRIMARY KEY AUTOINCREMENT,
    code_experience VARCHAR(5),
    libelle_experience VARCHAR(100),
    UNIQUE(code_experience)
);

-- Dimension niveau de qualification
CREATE TABLE IF NOT EXISTS dim_qualification (
    id_qualification INTEGER PRIMARY KEY AUTOINCREMENT,
    code_qualification VARCHAR(5),
    libelle_qualification VARCHAR(100),
    UNIQUE(code_qualification)
);

-- ============================================================================
-- TABLE DE FAITS
-- ============================================================================

CREATE TABLE IF NOT EXISTS fait_offres (
    id_offre INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Identifiant unique de l'offre (source originale)
    id_offre_source VARCHAR(50) NOT NULL,
    
    -- Clés étrangères vers les dimensions
    id_source INTEGER,
    id_lieu INTEGER,
    id_entreprise INTEGER,
    id_contrat INTEGER,
    id_metier INTEGER,
    id_temps_publication INTEGER,
    id_experience INTEGER,
    id_qualification INTEGER,
    
    -- Informations principales de l'offre
    titre VARCHAR(500),
    description TEXT,
    
    -- Salaire
    salaire_min REAL,
    salaire_max REAL,
    salaire_commentaire VARCHAR(255),
    salaire_complement1 VARCHAR(255),
    salaire_complement2 VARCHAR(255),
    
    -- Conditions de travail
    duree_travail VARCHAR(100),
    conditions_travail TEXT,
    alternance BOOLEAN DEFAULT 0,
    
    -- Informations complémentaires
    nombre_postes INTEGER DEFAULT 1,
    accessible_th BOOLEAN DEFAULT 0,  -- Accessible aux travailleurs handicapés
    
    -- Dates
    date_creation DATETIME,
    date_actualisation DATETIME,
    
    -- URL de l'offre originale
    url_offre VARCHAR(500),
    
    -- Métadonnées de collecte
    date_collecte DATETIME DEFAULT CURRENT_TIMESTAMP,
    actif BOOLEAN DEFAULT 1,  -- Pour marquer les offres expirées
    
    -- Contraintes
    FOREIGN KEY (id_source) REFERENCES dim_source(id_source),
    FOREIGN KEY (id_lieu) REFERENCES dim_lieu(id_lieu),
    FOREIGN KEY (id_entreprise) REFERENCES dim_entreprise(id_entreprise),
    FOREIGN KEY (id_contrat) REFERENCES dim_contrat(id_contrat),
    FOREIGN KEY (id_metier) REFERENCES dim_metier(id_metier),
    FOREIGN KEY (id_temps_publication) REFERENCES dim_temps(id_temps),
    FOREIGN KEY (id_experience) REFERENCES dim_experience(id_experience),
    FOREIGN KEY (id_qualification) REFERENCES dim_qualification(id_qualification),
    
    UNIQUE(id_offre_source, id_source)  -- Évite les doublons par source
);

-- ============================================================================
-- TABLES ASSOCIATIVES (relations many-to-many)
-- ============================================================================

-- Association offre <-> compétences (une offre peut demander plusieurs compétences)
CREATE TABLE IF NOT EXISTS offre_competence (
    id_offre INTEGER,
    id_competence INTEGER,
    exigence VARCHAR(50),  -- 'E' = Exigé, 'S' = Souhaité
    PRIMARY KEY (id_offre, id_competence),
    FOREIGN KEY (id_offre) REFERENCES fait_offres(id_offre) ON DELETE CASCADE,
    FOREIGN KEY (id_competence) REFERENCES dim_competence(id_competence)
);

-- Association offre <-> formations requises
CREATE TABLE IF NOT EXISTS offre_formation (
    id_offre INTEGER,
    code_formation VARCHAR(20),
    libelle_formation VARCHAR(255),
    niveau_requis VARCHAR(100),
    exigence VARCHAR(50),
    PRIMARY KEY (id_offre, code_formation),
    FOREIGN KEY (id_offre) REFERENCES fait_offres(id_offre) ON DELETE CASCADE
);

-- Association offre <-> langues requises
CREATE TABLE IF NOT EXISTS offre_langue (
    id_offre INTEGER,
    code_langue VARCHAR(10),
    libelle_langue VARCHAR(100),
    niveau VARCHAR(50),
    exigence VARCHAR(50),
    PRIMARY KEY (id_offre, code_langue),
    FOREIGN KEY (id_offre) REFERENCES fait_offres(id_offre) ON DELETE CASCADE
);

-- Association offre <-> permis requis
CREATE TABLE IF NOT EXISTS offre_permis (
    id_offre INTEGER,
    code_permis VARCHAR(10),
    libelle_permis VARCHAR(100),
    exigence VARCHAR(50),
    PRIMARY KEY (id_offre, code_permis),
    FOREIGN KEY (id_offre) REFERENCES fait_offres(id_offre) ON DELETE CASCADE
);

-- ============================================================================
-- INDEX POUR OPTIMISER LES REQUÊTES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_offres_date_creation ON fait_offres(date_creation);
CREATE INDEX IF NOT EXISTS idx_offres_source ON fait_offres(id_source);
CREATE INDEX IF NOT EXISTS idx_offres_lieu ON fait_offres(id_lieu);
CREATE INDEX IF NOT EXISTS idx_offres_metier ON fait_offres(id_metier);
CREATE INDEX IF NOT EXISTS idx_offres_contrat ON fait_offres(id_contrat);
CREATE INDEX IF NOT EXISTS idx_offres_actif ON fait_offres(actif);
CREATE INDEX IF NOT EXISTS idx_lieu_region ON dim_lieu(code_region);
CREATE INDEX IF NOT EXISTS idx_lieu_departement ON dim_lieu(code_departement);

-- ============================================================================
-- DONNÉES INITIALES
-- ============================================================================

-- Sources de données
INSERT OR IGNORE INTO dim_source (nom_source, url_base, type_source) VALUES 
    ('France Travail', 'https://www.francetravail.fr', 'api'),
    ('Welcome to the Jungle', 'https://www.welcometothejungle.com', 'scraping');

-- Quelques régions françaises (sera enrichi automatiquement)
INSERT OR IGNORE INTO dim_lieu (code_region, region, code_departement, departement) VALUES
    ('84', 'Auvergne-Rhône-Alpes', '69', 'Rhône'),
    ('11', 'Île-de-France', '75', 'Paris'),
    ('44', 'Grand Est', '67', 'Bas-Rhin'),
    ('75', 'Nouvelle-Aquitaine', '33', 'Gironde'),
    ('76', 'Occitanie', '31', 'Haute-Garonne'),
    ('93', 'Provence-Alpes-Côte d''Azur', '13', 'Bouches-du-Rhône'),
    ('52', 'Pays de la Loire', '44', 'Loire-Atlantique'),
    ('32', 'Hauts-de-France', '59', 'Nord'),
    ('28', 'Normandie', '76', 'Seine-Maritime'),
    ('53', 'Bretagne', '35', 'Ille-et-Vilaine');
"""

# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def create_database(db_path: str = "offres_emploi.db") -> sqlite3.Connection:
    """
    Crée la base de données et toutes les tables.
    
    Args:
        db_path: Chemin vers le fichier de base de données
        
    Returns:
        Connexion à la base de données
    """
    # Créer le dossier parent si nécessaire
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Connexion à la base
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Pour accéder aux colonnes par nom
    
    # Activer les clés étrangères
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Créer les tables
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    
    print(f"✅ Base de données créée : {db_path}")
    return conn


def get_table_info(conn: sqlite3.Connection) -> dict:
    """
    Retourne les informations sur toutes les tables de la base.
    """
    cursor = conn.cursor()
    
    # Liste des tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    info = {}
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cursor.fetchall()]
        
        info[table] = {"count": count, "columns": columns}
    
    return info


def print_database_summary(conn: sqlite3.Connection):
    """
    Affiche un résumé de la base de données.
    """
    print("\n" + "=" * 60)
    print("RÉSUMÉ DE LA BASE DE DONNÉES")
    print("=" * 60)
    
    info = get_table_info(conn)
    
    print("\n📊 Tables de dimensions :")
    for table, data in info.items():
        if table.startswith("dim_"):
            print(f"   - {table}: {data['count']} enregistrements")
    
    print("\n📋 Table de faits :")
    for table, data in info.items():
        if table.startswith("fait_"):
            print(f"   - {table}: {data['count']} enregistrements")
    
    print("\n🔗 Tables associatives :")
    for table, data in info.items():
        if table.startswith("offre_"):
            print(f"   - {table}: {data['count']} enregistrements")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Créer la base de données
    db_path = "data/offres_emploi.db"
    conn = create_database(db_path)
    
    # Afficher le résumé
    print_database_summary(conn)
    
    # Fermer la connexion
    conn.close()
    
    print("\n✅ Base de données initialisée avec succès !")
    print(f"   Fichier : {db_path}")
