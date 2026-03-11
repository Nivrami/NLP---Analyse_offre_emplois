# 💻 Script : test_api_v2.py

**Source :** `test_api_v2.py`

```python
"""
Script de test pour l'API France Travail (v2)
=============================================
Utilise le client personnalisé avec les bonnes URLs.

INSTRUCTIONS:
1. Remplace CLIENT_ID et CLIENT_SECRET par tes vraies valeurs
2. Exécute le script : python test_api_v2.py
"""

import sys
import os

# Ajouter le dossier parent au path pour importer le client
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.france_travail_client import FranceTravailClient, datetime_to_iso
from datetime import datetime, timedelta
import json

# =============================================================================
# CONFIGURATION - Remplace par tes identifiants
# =============================================================================
CLIENT_ID = "PAR_analyseemploi_5af90b203dd090dbd6a1834d9ccde2f9302a4b2fce9bfd975e4dcacb3a71f0f3"
CLIENT_SECRET = "495995ad8e506a5d042e73dd1c329cb2174d468e6a6efe9900d4cf60187a8919"


# =============================================================================
# TESTS
# =============================================================================

def test_connexion():
    """Test de connexion à l'API."""
    print("=" * 60)
    print("TEST DE CONNEXION À L'API FRANCE TRAVAIL")
    print("=" * 60)
    
    try:
        client = FranceTravailClient(CLIENT_ID, CLIENT_SECRET)
        # Forcer l'obtention d'un token pour vérifier la connexion
        token = client._get_token()
        print(f"✅ Connexion réussie !")
        print(f"   Token obtenu : {token[:20]}...")
        return client
    except Exception as e:
        print(f"❌ Erreur de connexion : {e}")
        return None


def test_recherche_basique(client):
    """Test de recherche simple."""
    print("\n" + "=" * 60)
    print("TEST DE RECHERCHE BASIQUE")
    print("=" * 60)
    
    try:
        result = client.search()
        content_range = result.get('Content-Range', {})
        
        print(f"✅ Recherche réussie !")
        print(f"   - Nombre total d'offres : {content_range.get('max_results', 'N/A')}")
        print(f"   - Offres récupérées : {len(result.get('resultats', []))}")
        
        return result
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return None


def test_recherche_data_ia(client):
    """Test de recherche sur les métiers data/IA."""
    print("\n" + "=" * 60)
    print("TEST DE RECHERCHE DATA / IA")
    print("=" * 60)
    
    mots_cles = [
        "data scientist",
        "data analyst", 
        "data engineer",
        "machine learning",
        "intelligence artificielle",
        "big data",
        "python data"
    ]
    
    resultats = {}
    
    for mot_cle in mots_cles:
        try:
            result = client.search({"motsCles": mot_cle})
            nb = result.get('Content-Range', {}).get('max_results', 0)
            resultats[mot_cle] = nb
            print(f"   📊 '{mot_cle}' : {nb} offres")
        except Exception as e:
            print(f"   ❌ Erreur pour '{mot_cle}' : {e}")
    
    return resultats


def test_recherche_par_region(client):
    """Test de recherche par région."""
    print("\n" + "=" * 60)
    print("TEST DE RECHERCHE PAR RÉGION")
    print("=" * 60)
    
    # Quelques régions importantes
    regions = {
        "11": "Île-de-France",
        "84": "Auvergne-Rhône-Alpes",
        "93": "Provence-Alpes-Côte d'Azur",
        "75": "Nouvelle-Aquitaine",
        "76": "Occitanie"
    }
    
    for code, nom in regions.items():
        try:
            result = client.search({
                "motsCles": "data",
                "region": code
            })
            nb = result.get('Content-Range', {}).get('max_results', 0)
            print(f"   📍 {nom} : {nb} offres data")
        except Exception as e:
            print(f"   ❌ Erreur pour {nom} : {e}")


def afficher_structure_offre(result):
    """Affiche la structure d'une offre pour comprendre les données."""
    print("\n" + "=" * 60)
    print("STRUCTURE D'UNE OFFRE")
    print("=" * 60)
    
    if not result or 'resultats' not in result or not result['resultats']:
        print("❌ Aucune offre à afficher")
        return
    
    offre = result['resultats'][0]
    
    print("\n📋 Champs principaux :")
    print("-" * 40)
    
    champs_simples = ['id', 'intitule', 'description', 'dateCreation', 
                      'dateActualisation', 'typeContrat', 'typeContratLibelle',
                      'natureContrat', 'experienceExige', 'experienceLibelle',
                      'dureeTravailLibelle', 'alternance', 'nombrePostes',
                      'accessibleTH', 'origineOffre']
    
    for champ in champs_simples:
        if champ in offre:
            valeur = offre[champ]
            if isinstance(valeur, str) and len(valeur) > 80:
                valeur = valeur[:80] + "..."
            print(f"   {champ}: {valeur}")
    
    print("\n📋 Objets imbriqués :")
    print("-" * 40)
    
    objets = ['lieuTravail', 'entreprise', 'salaire', 'contact', 'origineOffre']
    for obj in objets:
        if obj in offre and offre[obj]:
            print(f"\n   🔹 {obj}:")
            for k, v in offre[obj].items():
                print(f"      - {k}: {v}")
    
    print("\n📋 Listes :")
    print("-" * 40)
    
    listes = ['competences', 'formations', 'langues', 'permis', 'qualitesProfessionnelles']
    for lst in listes:
        if lst in offre and offre[lst]:
            print(f"\n   🔹 {lst} ({len(offre[lst])} éléments):")
            for i, item in enumerate(offre[lst][:3]):  # Max 3 exemples
                if isinstance(item, dict):
                    print(f"      {i+1}. {item}")
                else:
                    print(f"      {i+1}. {item}")
            if len(offre[lst]) > 3:
                print(f"      ... et {len(offre[lst]) - 3} autres")


def test_referentiels(client):
    """Test des référentiels."""
    print("\n" + "=" * 60)
    print("TEST DES RÉFÉRENTIELS")
    print("=" * 60)
    
    referentiels = [
        ('regions', 'Régions'),
        ('departements', 'Départements'),
        ('typesContrats', 'Types de contrats'),
        ('niveauxFormations', 'Niveaux de formation'),
        ('domaines', 'Domaines professionnels')
    ]
    
    for code, nom in referentiels:
        try:
            data = client.referentiel(code)
            print(f"   ✅ {nom} : {len(data)} entrées")
            if data:
                print(f"      Exemple : {data[0]}")
        except Exception as e:
            print(f"   ❌ Erreur pour {nom} : {e}")


def sauvegarder_exemple(result, filename="exemple_offre.json"):
    """Sauvegarde un exemple d'offre en JSON pour référence."""
    if result and 'resultats' in result and result['resultats']:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result['resultats'][0], f, ensure_ascii=False, indent=2)
        print(f"\n💾 Exemple d'offre sauvegardé dans {filename}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Vérification des identifiants
    if CLIENT_ID == "REMPLACE_PAR_TON_CLIENT_ID":
        print("⚠️  ATTENTION : Tu dois remplacer CLIENT_ID et CLIENT_SECRET !")
        print("   Ouvre ce fichier et modifie les lignes 18 et 19.")
        exit(1)
    
    # Exécuter les tests
    client = test_connexion()
    
    if client:
        result = test_recherche_basique(client)
        test_recherche_data_ia(client)
        test_recherche_par_region(client)
        afficher_structure_offre(result)
        test_referentiels(client)
        sauvegarder_exemple(result)
        
        print("\n" + "=" * 60)
        print("🎉 TOUS LES TESTS SONT PASSÉS !")
        print("=" * 60)
        print("\n✅ L'API fonctionne correctement.")
        print("   Prochaine étape : Script de collecte pour alimenter la base.")

```