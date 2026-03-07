"""
Script de collecte des offres d'emploi
======================================
Collecte les offres depuis l'API France Travail et les stocke dans la base SQLite.

Usage:
    python collect_offres.py --mots-cles "data scientist" --region 84
    python collect_offres.py --all-data-jobs
    python collect_offres.py --update
"""

import sys
import os
import argparse
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import time

# Ajouter le dossier parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.france_travail_client import FranceTravailClient, datetime_to_iso
from database.db_utils import (
    get_db_connection,
    get_or_create_source,
    get_or_create_entreprise,
    get_or_create_contrat,
    get_or_create_temps,
    offre_existe,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Identifiants API (à remplacer ou utiliser des variables d'environnement)
CLIENT_ID = "PAR_analyseemploi_5af90b203dd090dbd6a1834d9ccde2f9302a4b2fce9bfd975e4dcacb3a71f0f3"
CLIENT_SECRET = "495995ad8e506a5d042e73dd1c329cb2174d468e6a6efe9900d4cf60187a8919"

# Chemin de la base de données
DB_PATH = "data/offres_emploi.db"

# Mots-clés pour les métiers data/IA
DATA_KEYWORDS = [
    "data scientist",
    "data analyst",
    "data engineer",
    "machine learning",
    "intelligence artificielle",
    "deep learning",
    "big data",
    "data science",
    "IA",
    "NLP",
    "computer vision",
    "MLOps",
    "python data",
    "statisticien",
    "analyste données"
]

# Codes des régions françaises
REGIONS = {
    "84": "Auvergne-Rhône-Alpes",
    "27": "Bourgogne-Franche-Comté",
    "53": "Bretagne",
    "24": "Centre-Val de Loire",
    "94": "Corse",
    "44": "Grand Est",
    "32": "Hauts-de-France",
    "11": "Île-de-France",
    "28": "Normandie",
    "75": "Nouvelle-Aquitaine",
    "76": "Occitanie",
    "52": "Pays de la Loire",
    "93": "Provence-Alpes-Côte d'Azur"
}


# =============================================================================
# FONCTIONS DE BASE DE DONNÉES
# =============================================================================

# get_db_connection, get_or_create_source, get_or_create_entreprise,
# get_or_create_contrat, get_or_create_temps et offre_existe sont importés
# depuis database.db_utils.


def get_or_create_lieu(conn: sqlite3.Connection, lieu_data: Dict) -> Optional[int]:
    """Récupère ou crée un lieu et retourne son ID."""
    if not lieu_data:
        return None
    
    code_commune = lieu_data.get("commune")
    if not code_commune:
        return None
    
    cursor = conn.cursor()
    cursor.execute("SELECT id_lieu FROM dim_lieu WHERE code_commune = ?", (code_commune,))
    row = cursor.fetchone()
    if row:
        return row[0]
    
    # Extraire les infos du libellé (format: "XX - Ville")
    libelle = lieu_data.get("libelle", "")
    parts = libelle.split(" - ", 1)
    code_dept = parts[0] if len(parts) > 1 else None
    commune_nom = parts[1] if len(parts) > 1 else libelle
    
    # Déterminer la région à partir du département
    code_region = None
    region_nom = None
    if code_dept:
        # Mapping simplifié département -> région
        dept_to_region = {
            "75": ("11", "Île-de-France"), "77": ("11", "Île-de-France"),
            "78": ("11", "Île-de-France"), "91": ("11", "Île-de-France"),
            "92": ("11", "Île-de-France"), "93": ("11", "Île-de-France"),
            "94": ("11", "Île-de-France"), "95": ("11", "Île-de-France"),
            "69": ("84", "Auvergne-Rhône-Alpes"), "01": ("84", "Auvergne-Rhône-Alpes"),
            "03": ("84", "Auvergne-Rhône-Alpes"), "07": ("84", "Auvergne-Rhône-Alpes"),
            "15": ("84", "Auvergne-Rhône-Alpes"), "26": ("84", "Auvergne-Rhône-Alpes"),
            "38": ("84", "Auvergne-Rhône-Alpes"), "42": ("84", "Auvergne-Rhône-Alpes"),
            "43": ("84", "Auvergne-Rhône-Alpes"), "63": ("84", "Auvergne-Rhône-Alpes"),
            "73": ("84", "Auvergne-Rhône-Alpes"), "74": ("84", "Auvergne-Rhône-Alpes"),
            "13": ("93", "Provence-Alpes-Côte d'Azur"), "83": ("93", "Provence-Alpes-Côte d'Azur"),
            "84": ("93", "Provence-Alpes-Côte d'Azur"), "04": ("93", "Provence-Alpes-Côte d'Azur"),
            "05": ("93", "Provence-Alpes-Côte d'Azur"), "06": ("93", "Provence-Alpes-Côte d'Azur"),
            "31": ("76", "Occitanie"), "34": ("76", "Occitanie"),
            "33": ("75", "Nouvelle-Aquitaine"), "44": ("52", "Pays de la Loire"),
            "59": ("32", "Hauts-de-France"), "67": ("44", "Grand Est"),
            "35": ("53", "Bretagne"), "76": ("28", "Normandie"),
        }
        if code_dept in dept_to_region:
            code_region, region_nom = dept_to_region[code_dept]
    
    cursor.execute("""
        INSERT INTO dim_lieu (code_commune, commune, code_postal, code_departement, 
                              code_region, region, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        code_commune,
        commune_nom,
        lieu_data.get("codePostal"),
        code_dept,
        code_region,
        region_nom,
        lieu_data.get("latitude"),
        lieu_data.get("longitude")
    ))
    conn.commit()
    return cursor.lastrowid


def _get_or_create_entreprise_ft(conn: sqlite3.Connection, entreprise_data: Dict) -> Optional[int]:
    """Variante France Travail : enrichit aussi description, logo et url_site."""
    if not entreprise_data:
        return None
    nom = entreprise_data.get("nom")
    if not nom:
        return None

    cursor = conn.cursor()
    cursor.execute("SELECT id_entreprise FROM dim_entreprise WHERE nom = ?", (nom,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        "INSERT INTO dim_entreprise (nom, description, logo_url, url_site) VALUES (?, ?, ?, ?)",
        (nom, entreprise_data.get("description"),
         entreprise_data.get("logo"), entreprise_data.get("url")),
    )
    conn.commit()
    return cursor.lastrowid


def _get_or_create_contrat_ft(conn: sqlite3.Connection, offre: Dict) -> Optional[int]:
    """Variante France Travail : utilise code_contrat + code_nature comme clé composite."""
    code_contrat = offre.get("typeContrat")
    if not code_contrat:
        return None

    cursor = conn.cursor()
    cursor.execute(
        "SELECT id_contrat FROM dim_contrat WHERE code_contrat = ? AND code_nature = ?",
        (code_contrat, offre.get("natureContrat")),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        """INSERT INTO dim_contrat (code_contrat, libelle_contrat, code_nature, libelle_nature)
           VALUES (?, ?, ?, ?)""",
        (code_contrat, offre.get("typeContratLibelle"),
         offre.get("natureContrat"), offre.get("natureContrat")),
    )
    conn.commit()
    return cursor.lastrowid


def get_or_create_metier(conn: sqlite3.Connection, offre: Dict) -> Optional[int]:
    """Récupère ou crée un métier (code ROME) et retourne son ID."""
    code_rome = offre.get("romeCode")
    if not code_rome:
        return None
    
    cursor = conn.cursor()
    cursor.execute("SELECT id_metier FROM dim_metier WHERE code_rome = ?", (code_rome,))
    row = cursor.fetchone()
    if row:
        return row[0]
    
    cursor.execute("""
        INSERT INTO dim_metier (code_rome, libelle_rome)
        VALUES (?, ?)
    """, (code_rome, offre.get("romeLibelle")))
    conn.commit()
    return cursor.lastrowid


def _get_or_create_temps_ft(conn: sqlite3.Connection, date_str: str) -> Optional[int]:
    """Variante France Travail : parse une date ISO string avant d'appeler get_or_create_temps."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None
    return get_or_create_temps(conn, dt)


def get_or_create_experience(conn: sqlite3.Connection, offre: Dict) -> Optional[int]:
    """Récupère ou crée un niveau d'expérience et retourne son ID."""
    code = offre.get("experienceExige")
    if not code:
        return None
    
    cursor = conn.cursor()
    cursor.execute("SELECT id_experience FROM dim_experience WHERE code_experience = ?", (code,))
    row = cursor.fetchone()
    if row:
        return row[0]
    
    cursor.execute("""
        INSERT INTO dim_experience (code_experience, libelle_experience)
        VALUES (?, ?)
    """, (code, offre.get("experienceLibelle")))
    conn.commit()
    return cursor.lastrowid


def inserer_offre(conn: sqlite3.Connection, offre: Dict, id_source: int) -> Optional[int]:
    """Insère une offre France Travail dans la base de données."""
    id_offre_source = offre.get("id")

    if offre_existe(conn, id_offre_source, id_source):
        return None

    id_lieu = get_or_create_lieu(conn, offre.get("lieuTravail"))
    id_entreprise = _get_or_create_entreprise_ft(conn, offre.get("entreprise"))
    id_contrat = _get_or_create_contrat_ft(conn, offre)
    id_metier = get_or_create_metier(conn, offre)
    id_temps = _get_or_create_temps_ft(conn, offre.get("dateCreation"))
    id_experience = get_or_create_experience(conn, offre)

    salaire = offre.get("salaire", {})
    salaire_commentaire = salaire.get("libelle") if salaire else None

    origine = offre.get("origineOffre", {})
    url_offre = origine.get("urlOrigine") if origine else None
    
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO fait_offres (
            id_offre_source, id_source, id_lieu, id_entreprise, id_contrat,
            id_metier, id_temps_publication, id_experience,
            titre, description, salaire_commentaire,
            duree_travail, alternance, nombre_postes, accessible_th,
            date_creation, date_actualisation, url_offre, date_collecte, actif
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        id_offre_source,
        id_source,
        id_lieu,
        id_entreprise,
        id_contrat,
        id_metier,
        id_temps,
        id_experience,
        offre.get("intitule"),
        offre.get("description"),
        salaire_commentaire,
        offre.get("dureeTravailLibelle"),
        offre.get("alternance", False),
        offre.get("nombrePostes", 1),
        offre.get("accessibleTH", False),
        offre.get("dateCreation"),
        offre.get("dateActualisation"),
        url_offre,
        datetime.now().isoformat(),
        True
    ))
    conn.commit()
    
    id_offre = cursor.lastrowid
    
    # Insérer les compétences
    inserer_competences(conn, id_offre, offre.get("competences", []))
    
    # Insérer les formations
    inserer_formations(conn, id_offre, offre.get("formations", []))
    
    # Insérer les langues
    inserer_langues(conn, id_offre, offre.get("langues", []))
    
    return id_offre


def inserer_competences(conn: sqlite3.Connection, id_offre: int, competences: List[Dict]):
    """Insère les compétences d'une offre."""
    if not competences:
        return
    
    cursor = conn.cursor()
    
    for comp in competences:
        code = comp.get("code")
        libelle = comp.get("libelle")
        
        if not libelle:
            continue
        
        # Créer la compétence si elle n'existe pas
        cursor.execute("SELECT id_competence FROM dim_competence WHERE libelle_competence = ?", (libelle,))
        row = cursor.fetchone()
        
        if row:
            id_competence = row[0]
        else:
            cursor.execute("""
                INSERT INTO dim_competence (code_competence, libelle_competence, type_competence)
                VALUES (?, ?, ?)
            """, (code, libelle, comp.get("typeCompetence")))
            id_competence = cursor.lastrowid
        
        # Lier à l'offre
        try:
            cursor.execute("""
                INSERT INTO offre_competence (id_offre, id_competence, exigence)
                VALUES (?, ?, ?)
            """, (id_offre, id_competence, comp.get("exigence")))
        except sqlite3.IntegrityError:
            pass  # Déjà liée
    
    conn.commit()


def inserer_formations(conn: sqlite3.Connection, id_offre: int, formations: List[Dict]):
    """Insère les formations requises d'une offre."""
    if not formations:
        return
    
    cursor = conn.cursor()
    
    for form in formations:
        try:
            cursor.execute("""
                INSERT INTO offre_formation (id_offre, code_formation, libelle_formation, 
                                             niveau_requis, exigence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                id_offre,
                form.get("codeFormation"),
                form.get("domaineLibelle"),
                form.get("niveauLibelle"),
                form.get("exigence")
            ))
        except sqlite3.IntegrityError:
            pass
    
    conn.commit()


def inserer_langues(conn: sqlite3.Connection, id_offre: int, langues: List[Dict]):
    """Insère les langues requises d'une offre."""
    if not langues:
        return
    
    cursor = conn.cursor()
    
    for langue in langues:
        try:
            cursor.execute("""
                INSERT INTO offre_langue (id_offre, code_langue, libelle_langue, 
                                          niveau, exigence)
                VALUES (?, ?, ?, ?, ?)
            """, (
                id_offre,
                langue.get("code"),
                langue.get("libelle"),
                langue.get("niveau"),
                langue.get("exigence")
            ))
        except sqlite3.IntegrityError:
            pass
    
    conn.commit()


# =============================================================================
# FONCTIONS DE COLLECTE
# =============================================================================

def collecter_offres(client: FranceTravailClient, params: Dict, 
                     conn: sqlite3.Connection, id_source: int,
                     max_offres: int = None) -> Tuple[int, int]:
    """
    Collecte les offres correspondant aux critères et les stocke en base.
    
    Returns:
        Tuple (nombre d'offres insérées, nombre d'offres ignorées car doublon)
    """
    inserees = 0
    doublons = 0
    
    def progress(fetched, total):
        print(f"\r   Récupération : {fetched}/{total} offres...", end="", flush=True)
    
    try:
        offres = client.search_all(params, max_results=max_offres, progress_callback=progress)
        print()  # Nouvelle ligne après la progression
        
        for offre in offres:
            result = inserer_offre(conn, offre, id_source)
            if result:
                inserees += 1
            else:
                doublons += 1
        
    except Exception as e:
        print(f"\n   ⚠️ Erreur lors de la collecte : {e}")
    
    return inserees, doublons


def collecter_data_jobs(client: FranceTravailClient, conn: sqlite3.Connection, 
                        id_source: int, jours: int = 30):
    """Collecte toutes les offres data/IA."""
    print("\n" + "=" * 60)
    print("COLLECTE DES OFFRES DATA / IA")
    print("=" * 60)
    
    total_inserees = 0
    total_doublons = 0
    
    for keyword in DATA_KEYWORDS:
        print(f"\n📊 Recherche : '{keyword}'")
        
        # Recherche sans filtre de date (l'API retourne les offres actives récentes)
        params = {
            "motsCles": keyword
        }
        
        inserees, doublons = collecter_offres(client, params, conn, id_source)
        total_inserees += inserees
        total_doublons += doublons
        
        print(f"   ✅ {inserees} nouvelles offres, {doublons} doublons ignorés")
    
    print(f"\n📈 TOTAL : {total_inserees} offres insérées, {total_doublons} doublons")
    return total_inserees


def collecter_par_region(client: FranceTravailClient, conn: sqlite3.Connection,
                         id_source: int, mots_cles: str = "data", jours: int = 30):
    """Collecte les offres région par région."""
    print("\n" + "=" * 60)
    print("COLLECTE PAR RÉGION")
    print("=" * 60)
    
    total_inserees = 0
    
    for code_region, nom_region in REGIONS.items():
        print(f"\n📍 {nom_region} (code {code_region})")
        
        # Recherche sans filtre de date
        params = {
            "motsCles": mots_cles,
            "region": code_region
        }
        
        inserees, doublons = collecter_offres(client, params, conn, id_source)
        total_inserees += inserees
        
        print(f"   ✅ {inserees} nouvelles offres")
    
    print(f"\n📈 TOTAL : {total_inserees} offres insérées")
    return total_inserees


def afficher_stats(conn: sqlite3.Connection):
    """Affiche les statistiques de la base de données."""
    print("\n" + "=" * 60)
    print("STATISTIQUES DE LA BASE DE DONNÉES")
    print("=" * 60)
    
    cursor = conn.cursor()
    
    # Nombre total d'offres
    cursor.execute("SELECT COUNT(*) FROM fait_offres WHERE actif = 1")
    nb_offres = cursor.fetchone()[0]
    print(f"\n📊 Total offres actives : {nb_offres}")
    
    # Par source
    cursor.execute("""
        SELECT s.nom_source, COUNT(*) 
        FROM fait_offres f
        JOIN dim_source s ON f.id_source = s.id_source
        GROUP BY s.nom_source
    """)
    print("\n📊 Par source :")
    for row in cursor.fetchall():
        print(f"   - {row[0]} : {row[1]}")
    
    # Par région
    cursor.execute("""
        SELECT l.region, COUNT(*) 
        FROM fait_offres f
        JOIN dim_lieu l ON f.id_lieu = l.id_lieu
        WHERE l.region IS NOT NULL
        GROUP BY l.region
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """)
    print("\n📊 Top 10 régions :")
    for row in cursor.fetchall():
        print(f"   - {row[0]} : {row[1]}")
    
    # Par type de contrat
    cursor.execute("""
        SELECT c.libelle_contrat, COUNT(*) 
        FROM fait_offres f
        JOIN dim_contrat c ON f.id_contrat = c.id_contrat
        GROUP BY c.libelle_contrat
        ORDER BY COUNT(*) DESC
        LIMIT 5
    """)
    print("\n📊 Top 5 types de contrat :")
    for row in cursor.fetchall():
        print(f"   - {row[0]} : {row[1]}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Collecte des offres d'emploi France Travail")
    parser.add_argument("--mots-cles", "-m", help="Mots-clés de recherche")
    parser.add_argument("--region", "-r", help="Code région (ex: 84 pour Auvergne-Rhône-Alpes)")
    parser.add_argument("--jours", "-j", type=int, default=30, help="Nombre de jours à collecter (défaut: 30)")
    parser.add_argument("--all-data-jobs", action="store_true", help="Collecter toutes les offres data/IA")
    parser.add_argument("--par-region", action="store_true", help="Collecter par région")
    parser.add_argument("--stats", action="store_true", help="Afficher les statistiques")
    parser.add_argument("--max", type=int, help="Nombre maximum d'offres à collecter")
    
    args = parser.parse_args()
    
    # Vérifier les identifiants
    if CLIENT_ID == "REMPLACE_PAR_TON_CLIENT_ID":
        print("⚠️  Configure tes identifiants API !")
        print("   Modifie CLIENT_ID et CLIENT_SECRET dans ce fichier")
        print("   ou définis les variables d'environnement FRANCE_TRAVAIL_CLIENT_ID et FRANCE_TRAVAIL_CLIENT_SECRET")
        return
    
    # Connexion à la base
    conn = get_db_connection()
    
    # Afficher seulement les stats si demandé
    if args.stats:
        afficher_stats(conn)
        conn.close()
        return
    
    # Créer le client API
    print("🔌 Connexion à l'API France Travail...")
    client = FranceTravailClient(CLIENT_ID, CLIENT_SECRET)
    
    # Récupérer l'ID de la source France Travail
    id_source = get_or_create_source(conn, "France Travail", "https://www.francetravail.fr", "api")
    
    # Exécuter la collecte demandée
    if args.all_data_jobs:
        collecter_data_jobs(client, conn, id_source, args.jours)
    elif args.par_region:
        mots_cles = args.mots_cles or "data"
        collecter_par_region(client, conn, id_source, mots_cles, args.jours)
    elif args.mots_cles:
        print(f"\n📊 Recherche : '{args.mots_cles}'")
        
        params = {"motsCles": args.mots_cles}
        if args.region:
            params["region"] = args.region
        
        inserees, doublons = collecter_offres(client, params, conn, id_source, args.max)
        print(f"   ✅ {inserees} offres insérées, {doublons} doublons ignorés")
    else:
        print("Usage:")
        print("  python collect_offres.py --all-data-jobs        # Collecter toutes les offres data/IA")
        print("  python collect_offres.py --mots-cles 'python'   # Recherche par mots-clés")
        print("  python collect_offres.py --par-region           # Collecter par région")
        print("  python collect_offres.py --stats                # Voir les statistiques")
        conn.close()
        return
    
    # Afficher les stats finales
    afficher_stats(conn)
    
    conn.close()
    print("\n✅ Collecte terminée !")


if __name__ == "__main__":
    main()
