"""
Utilitaires partagés pour l'accès à la base de données
=======================================================
Toutes les fonctions get_or_create_* et inserer_offre sont définies ici
une seule fois et importées par collect_offres.py et les scrapers.

Usage:
    from database.db_utils import get_db_connection, inserer_offre, get_or_create_source
"""

import sqlite3
from datetime import datetime
from typing import Dict, Optional

DB_PATH = "data/offres_emploi.db"

# Mapping libellé de contrat -> code court (utilisé à l'insertion)
CODE_CONTRAT = {
    "CDI": "CDI",
    "CDD": "CDD",
    "Stage": "STA",
    "Alternance": "ALT",
    "Intérim": "INT",
    "Interim": "INT",
    "Freelance": "FRE",
    "VIE": "VIE",
}

_JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
_MOIS = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
         "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


# =============================================================================
# CONNEXION
# =============================================================================

def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Ouvre et retourne une connexion à la base SQLite."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# =============================================================================
# DIMENSIONS — fonctions get_or_create_*
# =============================================================================

def get_or_create_source(conn: sqlite3.Connection, nom: str, url_base: str,
                          type_source: str = "scraping") -> int:
    """Récupère ou crée une source et retourne son ID."""
    cursor = conn.cursor()
    cursor.execute("SELECT id_source FROM dim_source WHERE nom_source = ?", (nom,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        "INSERT INTO dim_source (nom_source, url_base, type_source) VALUES (?, ?, ?)",
        (nom, url_base, type_source),
    )
    conn.commit()
    return cursor.lastrowid


def get_or_create_lieu(conn: sqlite3.Connection, lieu_str: str,
                        region_mapping: Dict[str, tuple] = None) -> Optional[int]:
    """
    Récupère ou crée un lieu à partir d'une chaîne de localisation.

    Args:
        lieu_str      : ex. "Paris, Île-de-France" ou "Lyon"
        region_mapping: dict {mot_cle_lower: (code_region, nom_region)}
                        fourni par le scraper qui connaît ses propres libellés
    """
    if not lieu_str:
        return None

    commune = lieu_str.split(",")[0].strip()
    code_region, nom_region = None, None

    if region_mapping:
        lieu_lower = lieu_str.lower()
        for key, (code, nom) in region_mapping.items():
            if key in lieu_lower:
                code_region, nom_region = code, nom
                break

    cursor = conn.cursor()
    cursor.execute("SELECT id_lieu FROM dim_lieu WHERE commune = ?", (commune,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        "INSERT INTO dim_lieu (commune, region, code_region) VALUES (?, ?, ?)",
        (commune, nom_region, code_region),
    )
    conn.commit()
    return cursor.lastrowid


def get_or_create_entreprise(conn: sqlite3.Connection, nom: Optional[str]) -> Optional[int]:
    """Récupère ou crée une entreprise et retourne son ID."""
    if not nom:
        return None

    cursor = conn.cursor()
    cursor.execute("SELECT id_entreprise FROM dim_entreprise WHERE nom = ?", (nom,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute("INSERT INTO dim_entreprise (nom) VALUES (?)", (nom,))
    conn.commit()
    return cursor.lastrowid


def get_or_create_contrat(conn: sqlite3.Connection,
                           libelle: Optional[str]) -> Optional[int]:
    """Récupère ou crée un type de contrat et retourne son ID."""
    if not libelle:
        return None

    cursor = conn.cursor()
    cursor.execute(
        "SELECT id_contrat FROM dim_contrat WHERE libelle_contrat = ?", (libelle,)
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    code = CODE_CONTRAT.get(libelle, libelle[:3].upper())
    cursor.execute(
        "INSERT INTO dim_contrat (code_contrat, libelle_contrat) VALUES (?, ?)",
        (code, libelle),
    )
    conn.commit()
    return cursor.lastrowid


def get_or_create_temps(conn: sqlite3.Connection,
                         date: Optional[datetime] = None) -> int:
    """
    Récupère ou crée une entrée dans dim_temps.
    Si date est None, utilise aujourd'hui.
    """
    dt = date or datetime.now()
    date_str = dt.strftime("%Y-%m-%d")

    cursor = conn.cursor()
    cursor.execute(
        "SELECT id_temps FROM dim_temps WHERE date_complete = ?", (date_str,)
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        """INSERT INTO dim_temps
           (date_complete, jour, mois, annee, trimestre, semaine, jour_semaine, nom_jour, nom_mois)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            date_str,
            dt.day,
            dt.month,
            dt.year,
            (dt.month - 1) // 3 + 1,
            dt.isocalendar()[1],
            dt.weekday(),
            _JOURS[dt.weekday()],
            _MOIS[dt.month],
        ),
    )
    conn.commit()
    return cursor.lastrowid


# =============================================================================
# TABLE DE FAITS
# =============================================================================

def offre_existe(conn: sqlite3.Connection, id_offre_source: str,
                  id_source: int) -> bool:
    """Retourne True si l'offre est déjà présente en base."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM fait_offres WHERE id_offre_source = ? AND id_source = ?",
        (id_offre_source, id_source),
    )
    return cursor.fetchone() is not None


def inserer_offre(conn: sqlite3.Connection, offre: Dict, id_source: int,
                   region_mapping: Dict[str, tuple] = None) -> Optional[int]:
    """
    Insère une offre dans fait_offres et ses dimensions associées.

    L'offre est un dict avec les clés normalisées suivantes :
        id            : identifiant source (optionnel, fallback sur url[:50])
        titre         : str
        description   : str
        entreprise    : str
        lieu          : str  (ex: "Paris, Île-de-France")
        type_contrat  : str  (ex: "CDI", "Stage")
        salaire       : str  (commentaire libre)
        url           : str
        date_creation : datetime (optionnel, défaut: now)

    Retourne l'id_offre inséré, ou None si doublon.
    """
    id_offre_source = offre.get("id") or (offre.get("url") or "")[:50]

    if offre_existe(conn, id_offre_source, id_source):
        return None

    id_lieu = get_or_create_lieu(conn, offre.get("lieu"), region_mapping)
    id_entreprise = get_or_create_entreprise(conn, offre.get("entreprise"))
    id_contrat = get_or_create_contrat(conn, offre.get("type_contrat"))
    id_temps = get_or_create_temps(conn, offre.get("date_creation"))

    now = datetime.now().isoformat()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO fait_offres (
               id_offre_source, id_source, id_lieu, id_entreprise, id_contrat,
               id_temps_publication,
               titre, description, salaire_commentaire,
               date_creation, url_offre, date_collecte, actif
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            id_offre_source,
            id_source,
            id_lieu,
            id_entreprise,
            id_contrat,
            id_temps,
            offre.get("titre"),
            offre.get("description"),
            offre.get("salaire"),
            offre.get("date_creation", now),
            offre.get("url"),
            now,
            True,
        ),
    )
    conn.commit()
    return cursor.lastrowid
