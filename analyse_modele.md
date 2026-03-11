# 💻 Script : analyse_modele.py

**Source :** `analyse_modele.py`

```python
"""
Analyse du modèle de données
============================
Script pour vérifier et documenter l'état de la base de données.
"""

import sqlite3
import os

DB_PATH = "data/offres_emploi.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def analyser_dimensions(conn):
    """Analyse toutes les tables de dimensions."""
    print("=" * 70)
    print("ANALYSE DES DIMENSIONS")
    print("=" * 70)
    
    dimensions = [
        ("dim_source", "Sources de données"),
        ("dim_lieu", "Lieux géographiques"),
        ("dim_entreprise", "Entreprises"),
        ("dim_contrat", "Types de contrats"),
        ("dim_metier", "Métiers (codes ROME)"),
        ("dim_temps", "Dimension temporelle"),
        ("dim_competence", "Compétences"),
        ("dim_experience", "Niveaux d'expérience"),
        ("dim_qualification", "Niveaux de qualification"),
    ]
    
    cursor = conn.cursor()
    
    for table, description in dimensions:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        
        status = "✅" if count > 0 else "⚠️ VIDE"
        print(f"\n{status} {description} ({table}): {count} enregistrements")
        
        # Afficher quelques exemples si non vide
        if count > 0:
            cursor.execute(f"SELECT * FROM {table} LIMIT 3")
            rows = cursor.fetchall()
            colonnes = [desc[0] for desc in cursor.description]
            print(f"   Colonnes: {', '.join(colonnes)}")
            print(f"   Exemples:")
            for row in rows:
                exemple = dict(row)
                # Tronquer les valeurs longues
                for k, v in exemple.items():
                    if isinstance(v, str) and len(v) > 50:
                        exemple[k] = v[:50] + "..."
                print(f"      {exemple}")

def analyser_table_faits(conn):
    """Analyse la table de faits."""
    print("\n" + "=" * 70)
    print("ANALYSE DE LA TABLE DE FAITS (fait_offres)")
    print("=" * 70)
    
    cursor = conn.cursor()
    
    # Nombre total
    cursor.execute("SELECT COUNT(*) FROM fait_offres")
    total = cursor.fetchone()[0]
    print(f"\n📊 Total d'offres: {total}")
    
    # Offres actives vs inactives
    cursor.execute("SELECT actif, COUNT(*) FROM fait_offres GROUP BY actif")
    for row in cursor.fetchall():
        status = "Actives" if row[0] else "Inactives"
        print(f"   - {status}: {row[1]}")
    
    # Taux de remplissage des clés étrangères
    print("\n📊 Taux de remplissage des dimensions:")
    
    fk_columns = [
        ("id_source", "Source"),
        ("id_lieu", "Lieu"),
        ("id_entreprise", "Entreprise"),
        ("id_contrat", "Contrat"),
        ("id_metier", "Métier"),
        ("id_temps_publication", "Date publication"),
        ("id_experience", "Expérience"),
        ("id_qualification", "Qualification"),
    ]
    
    for col, nom in fk_columns:
        cursor.execute(f"SELECT COUNT(*) FROM fait_offres WHERE {col} IS NOT NULL")
        filled = cursor.fetchone()[0]
        pct = (filled / total * 100) if total > 0 else 0
        status = "✅" if pct > 80 else "⚠️" if pct > 50 else "❌"
        print(f"   {status} {nom}: {filled}/{total} ({pct:.1f}%)")
    
    # Champs texte remplis
    print("\n📊 Taux de remplissage des champs texte:")
    text_columns = [
        ("titre", "Titre"),
        ("description", "Description"),
        ("salaire_commentaire", "Salaire"),
        ("url_offre", "URL"),
    ]
    
    for col, nom in text_columns:
        cursor.execute(f"SELECT COUNT(*) FROM fait_offres WHERE {col} IS NOT NULL AND {col} != ''")
        filled = cursor.fetchone()[0]
        pct = (filled / total * 100) if total > 0 else 0
        status = "✅" if pct > 80 else "⚠️" if pct > 50 else "❌"
        print(f"   {status} {nom}: {filled}/{total} ({pct:.1f}%)")

def analyser_tables_associatives(conn):
    """Analyse les tables associatives."""
    print("\n" + "=" * 70)
    print("ANALYSE DES TABLES ASSOCIATIVES")
    print("=" * 70)
    
    cursor = conn.cursor()
    
    tables = [
        ("offre_competence", "Offres ↔ Compétences"),
        ("offre_formation", "Offres ↔ Formations"),
        ("offre_langue", "Offres ↔ Langues"),
        ("offre_permis", "Offres ↔ Permis"),
    ]
    
    for table, description in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(DISTINCT id_offre) FROM {table}")
        nb_offres = cursor.fetchone()[0]
        
        status = "✅" if count > 0 else "⚠️ VIDE"
        print(f"\n{status} {description} ({table})")
        print(f"   - {count} associations")
        print(f"   - {nb_offres} offres concernées")

def analyser_distribution_geographique(conn):
    """Analyse détaillée de la distribution géographique."""
    print("\n" + "=" * 70)
    print("DISTRIBUTION GÉOGRAPHIQUE")
    print("=" * 70)
    
    cursor = conn.cursor()
    
    # Par région
    print("\n📍 Par région:")
    cursor.execute("""
        SELECT l.region, COUNT(*) as nb
        FROM fait_offres f
        JOIN dim_lieu l ON f.id_lieu = l.id_lieu
        WHERE l.region IS NOT NULL
        GROUP BY l.region
        ORDER BY nb DESC
    """)
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]} offres")
    
    # Offres sans région
    cursor.execute("""
        SELECT COUNT(*) FROM fait_offres f
        LEFT JOIN dim_lieu l ON f.id_lieu = l.id_lieu
        WHERE l.region IS NULL OR f.id_lieu IS NULL
    """)
    sans_region = cursor.fetchone()[0]
    if sans_region > 0:
        print(f"\n   ⚠️ Offres sans région identifiée: {sans_region}")
    
    # Coordonnées GPS disponibles
    cursor.execute("""
        SELECT COUNT(*) FROM fait_offres f
        JOIN dim_lieu l ON f.id_lieu = l.id_lieu
        WHERE l.latitude IS NOT NULL AND l.longitude IS NOT NULL
    """)
    avec_gps = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM fait_offres WHERE id_lieu IS NOT NULL")
    total_avec_lieu = cursor.fetchone()[0]
    print(f"\n📍 Coordonnées GPS: {avec_gps}/{total_avec_lieu} lieux géolocalisés")

def analyser_competences(conn):
    """Analyse des compétences les plus demandées."""
    print("\n" + "=" * 70)
    print("TOP 15 COMPÉTENCES DEMANDÉES")
    print("=" * 70)
    
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT c.libelle_competence, COUNT(*) as nb
        FROM offre_competence oc
        JOIN dim_competence c ON oc.id_competence = c.id_competence
        GROUP BY c.libelle_competence
        ORDER BY nb DESC
        LIMIT 15
    """)
    
    for i, row in enumerate(cursor.fetchall(), 1):
        print(f"   {i:2}. {row[0]}: {row[1]} offres")

def generer_resume(conn):
    """Génère un résumé pour le rapport."""
    print("\n" + "=" * 70)
    print("RÉSUMÉ POUR LE RAPPORT")
    print("=" * 70)
    
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM fait_offres")
    nb_offres = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM dim_lieu WHERE region IS NOT NULL")
    nb_lieux = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM dim_entreprise")
    nb_entreprises = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM dim_competence")
    nb_competences = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT region) FROM dim_lieu WHERE region IS NOT NULL")
    nb_regions = cursor.fetchone()[0]
    
    print(f"""
📊 CHIFFRES CLÉS:
   - {nb_offres} offres d'emploi collectées
   - {nb_entreprises} entreprises distinctes
   - {nb_lieux} localisations uniques
   - {nb_regions} régions couvertes
   - {nb_competences} compétences identifiées
   
📁 MODÈLE EN ÉTOILE:
   - 1 table de faits (fait_offres)
   - 9 tables de dimensions
   - 4 tables associatives
   
🗄️ SGBD: SQLite
📅 Source: API France Travail (Offres d'emploi v2)
    """)

def main():
    if not os.path.exists(DB_PATH):
        print(f"❌ Base de données non trouvée: {DB_PATH}")
        return
    
    conn = get_connection()
    
    analyser_dimensions(conn)
    analyser_table_faits(conn)
    analyser_tables_associatives(conn)
    analyser_distribution_geographique(conn)
    analyser_competences(conn)
    generer_resume(conn)
    
    conn.close()
    
    print("\n✅ Analyse terminée !")

if __name__ == "__main__":
    main()

```