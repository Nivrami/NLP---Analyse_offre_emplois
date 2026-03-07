"""
Script de diagnostic pour tester la collecte
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.france_travail_client import FranceTravailClient
from datetime import datetime, timedelta

# Mets tes identifiants ici
CLIENT_ID = "CLIENT_ID_SUPPRIME"
CLIENT_SECRET = "CLIENT_SECRET_SUPPRIME"

client = FranceTravailClient(CLIENT_ID, CLIENT_SECRET)

print("=" * 60)
print("TEST 1 : Recherche sans date (devrait fonctionner)")
print("=" * 60)

try:
    result = client.search({"motsCles": "data scientist"})
    print(f"✅ Succès ! {result['Content-Range']['max_results']} offres trouvées")
except Exception as e:
    print(f"❌ Erreur : {e}")

print("\n" + "=" * 60)
print("TEST 2 : Recherche avec date ISO format")
print("=" * 60)

date_min = datetime.now() - timedelta(days=30)
date_iso = date_min.strftime("%Y-%m-%dT%H:%M:%SZ")
print(f"   Date utilisée : {date_iso}")

try:
    result = client.search({
        "motsCles": "data scientist",
        "minCreationDate": date_iso
    })
    print(f"✅ Succès ! {result['Content-Range']['max_results']} offres trouvées")
except Exception as e:
    print(f"❌ Erreur : {e}")

print("\n" + "=" * 60)
print("TEST 3 : Recherche avec date format simplifié")
print("=" * 60)

date_simple = date_min.strftime("%Y-%m-%dT00:00:00Z")
print(f"   Date utilisée : {date_simple}")

try:
    result = client.search({
        "motsCles": "data scientist",
        "minCreationDate": date_simple
    })
    print(f"✅ Succès ! {result['Content-Range']['max_results']} offres trouvées")
except Exception as e:
    print(f"❌ Erreur : {e}")

print("\n" + "=" * 60)
print("TEST 4 : Vérifier search_all (pagination)")
print("=" * 60)

try:
    # Sans date, juste quelques résultats
    offres = client.search_all({"motsCles": "data scientist"}, max_results=10)
    print(f"✅ Succès ! {len(offres)} offres récupérées")
    if offres:
        print(f"   Première offre : {offres[0].get('intitule', 'N/A')}")
except Exception as e:
    print(f"❌ Erreur : {e}")

print("\n" + "=" * 60)
print("DIAGNOSTIC TERMINÉ")
print("=" * 60)
