# 💻 Script : france_travail_client.py

**Source :** `france_travail_client.py`

```python
"""
Client API France Travail
==========================
Client personnalisé pour l'API Offres d'emploi v2 de France Travail.
Utilise les URLs actuelles (2024-2025).
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import json


class FranceTravailClient:
    """
    Client pour l'API France Travail (ex Pôle Emploi).
    
    Exemple d'utilisation:
        client = FranceTravailClient(client_id="xxx", client_secret="yyy")
        offres = client.search({"motsCles": "data scientist", "region": "84"})
    """
    
    # URLs de l'API
    TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
    API_BASE_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2"
    
    # Scope par défaut
    DEFAULT_SCOPE = "api_offresdemploiv2 o2dsoffre"
    
    # Limite de requêtes par seconde
    RATE_LIMIT = 3
    
    def __init__(self, client_id: str, client_secret: str, scope: str = None):
        """
        Initialise le client.
        
        Args:
            client_id: Identifiant de l'application
            client_secret: Clé secrète de l'application
            scope: Scope OAuth2 (optionnel, utilise le défaut sinon)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope or self.DEFAULT_SCOPE
        
        # Token et expiration
        self._access_token = None
        self._token_expires_at = None
        
        # Pour le rate limiting
        self._last_request_time = 0
    
    def _get_token(self) -> str:
        """
        Obtient ou renouvelle le token d'accès.
        
        Returns:
            Token d'accès valide
        """
        # Vérifier si le token est encore valide (avec 60s de marge)
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - timedelta(seconds=60):
                return self._access_token
        
        # Demander un nouveau token
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scope
        }
        
        response = requests.post(self.TOKEN_URL, data=data, timeout=30)
        response.raise_for_status()
        
        token_data = response.json()
        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 1499)
        self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        return self._access_token
    
    def _rate_limit(self):
        """Applique le rate limiting (max 3 requêtes/seconde)."""
        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / self.RATE_LIMIT
        
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        
        self._last_request_time = time.time()
    
    def _request(self, method: str, endpoint: str, params: Dict = None) -> Dict:
        """
        Effectue une requête à l'API.
        
        Args:
            method: Méthode HTTP (GET, POST, etc.)
            endpoint: Endpoint de l'API (ex: /offres/search)
            params: Paramètres de la requête
            
        Returns:
            Réponse JSON de l'API
        """
        self._rate_limit()
        
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        url = f"{self.API_BASE_URL}{endpoint}"
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            timeout=30
        )
        response.raise_for_status()
        
        # Extraire Content-Range si présent
        result = response.json()
        
        if "Content-Range" in response.headers:
            content_range = response.headers["Content-Range"]
            # Format: "offres X-Y/Z" ou "referentiel */Z"
            try:
                parts = content_range.split("/")
                max_results = int(parts[1]) if parts[1] != "*" else None
                
                range_part = parts[0].split(" ")[-1]  # Prend la partie après "offres " ou "referentiel "
                if "-" in range_part and "*" not in range_part:
                    range_parts = range_part.split("-")
                    result["Content-Range"] = {
                        "first_index": int(range_parts[0]),
                        "last_index": int(range_parts[1]),
                        "max_results": max_results
                    }
                else:
                    result["Content-Range"] = {
                        "first_index": 0,
                        "last_index": max_results - 1 if max_results else 0,
                        "max_results": max_results
                    }
            except (ValueError, IndexError):
                # Si le parsing échoue, on ignore
                pass
        
        return result
    
    def search(self, params: Dict = None, range_start: int = 0, range_end: int = 149) -> Dict:
        """
        Recherche des offres d'emploi.
        
        Args:
            params: Paramètres de recherche (motsCles, region, departement, etc.)
            range_start: Index de début (max 1000)
            range_end: Index de fin (max 1149, écart max 150)
            
        Returns:
            Dictionnaire avec 'resultats', 'filtresPossibles' et 'Content-Range'
            
        Exemple:
            # Recherche simple
            client.search({"motsCles": "python"})
            
            # Recherche avancée
            client.search({
                "motsCles": "data scientist",
                "region": "84",  # Auvergne-Rhône-Alpes
                "typeContrat": "CDI",
                "minCreationDate": "2024-01-01T00:00:00Z"
            })
        """
        params = params or {}
        params["range"] = f"{range_start}-{range_end}"
        
        return self._request("GET", "/offres/search", params)
    
    def get_offre(self, id_offre: str) -> Dict:
        """
        Récupère le détail d'une offre spécifique.
        
        Args:
            id_offre: Identifiant de l'offre
            
        Returns:
            Détail complet de l'offre
        """
        return self._request("GET", f"/offres/{id_offre}")
    
    def referentiel(self, nom: str) -> List[Dict]:
        """
        Récupère un référentiel.
        
        Args:
            nom: Nom du référentiel. Valeurs possibles:
                - appellations
                - domaines
                - metiers
                - themes
                - typesContrats
                - niveauxFormations
                - regions
                - departements
                - communes
                - continents
                - pays
                - naturesContrats
                - permis
                - langues
                - niveauxLangues
                
        Returns:
            Liste des entrées du référentiel
        """
        # Les référentiels retournent directement une liste, pas un dict
        self._rate_limit()
        
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        url = f"{self.API_BASE_URL}/referentiel/{nom}"
        
        response = requests.request(
            method="GET",
            url=url,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        
        return response.json()
    
    def search_all(self, params: Dict = None, max_results: int = None, 
                   progress_callback=None) -> List[Dict]:
        """
        Recherche toutes les offres correspondant aux critères (avec pagination).
        
        Note: L'API limite à 1150 résultats max par recherche. Pour plus,
        il faut affiner les critères (dates, localisation, etc.)
        
        Args:
            params: Paramètres de recherche
            max_results: Nombre maximum de résultats à récupérer (défaut: tous)
            progress_callback: Fonction appelée à chaque page (reçoit nb_fetched, nb_total)
            
        Returns:
            Liste de toutes les offres
        """
        all_results = []
        range_start = 0
        range_size = 150
        
        while True:
            range_end = range_start + range_size - 1
            
            # L'API limite à 1149 max
            if range_end > 1149:
                range_end = 1149
            if range_start > 1000:
                break
            
            try:
                response = self.search(params, range_start, range_end)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 416:
                    # Range non satisfaisable = plus de résultats
                    break
                raise
            
            results = response.get("resultats", [])
            if not results:
                break
            
            all_results.extend(results)
            
            # Callback de progression
            content_range = response.get("Content-Range", {})
            total = content_range.get("max_results", len(all_results))
            
            if progress_callback:
                progress_callback(len(all_results), total)
            
            # Vérifier si on a tout récupéré ou atteint la limite
            if max_results and len(all_results) >= max_results:
                all_results = all_results[:max_results]
                break
            
            if len(results) < range_size:
                break
            
            if len(all_results) >= total:
                break
            
            range_start += range_size
        
        return all_results


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def datetime_to_iso(dt: datetime) -> str:
    """Convertit un datetime en format ISO 8601 pour l'API."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_salaire(salaire: Dict) -> tuple:
    """
    Parse les informations de salaire d'une offre.
    
    Returns:
        Tuple (salaire_min, salaire_max, commentaire)
    """
    if not salaire:
        return None, None, None
    
    libelle = salaire.get("libelle", "")
    commentaire = salaire.get("commentaire", "")
    
    # Essayer d'extraire les valeurs numériques
    # Format typique: "Annuel de 35000 Euros à 45000 Euros"
    salaire_min = None
    salaire_max = None
    
    # TODO: Parser le libellé pour extraire les valeurs
    
    return salaire_min, salaire_max, commentaire or libelle


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    import os
    
    # Récupérer les identifiants depuis les variables d'environnement
    # ou les définir directement pour le test
    CLIENT_ID = os.getenv("FRANCE_TRAVAIL_CLIENT_ID", "REMPLACE_MOI")
    CLIENT_SECRET = os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET", "REMPLACE_MOI")
    
    if CLIENT_ID == "REMPLACE_MOI":
        print("⚠️  Configure tes identifiants dans les variables d'environnement")
        print("   ou modifie ce fichier directement pour tester.")
        exit(1)
    
    print("=" * 60)
    print("TEST DU CLIENT FRANCE TRAVAIL")
    print("=" * 60)
    
    # Créer le client
    client = FranceTravailClient(CLIENT_ID, CLIENT_SECRET)
    
    # Test 1: Recherche simple
    print("\n📋 Test recherche simple...")
    result = client.search()
    print(f"   ✅ {result['Content-Range']['max_results']} offres disponibles")
    print(f"   ✅ {len(result['resultats'])} offres récupérées")
    
    # Test 2: Recherche data scientist
    print("\n📋 Test recherche 'data scientist'...")
    result = client.search({"motsCles": "data scientist"})
    print(f"   ✅ {result['Content-Range']['max_results']} offres trouvées")
    
    # Test 3: Afficher une offre
    if result['resultats']:
        offre = result['resultats'][0]
        print(f"\n📋 Exemple d'offre:")
        print(f"   Titre: {offre.get('intitule', 'N/A')}")
        print(f"   Entreprise: {offre.get('entreprise', {}).get('nom', 'N/A')}")
        print(f"   Lieu: {offre.get('lieuTravail', {}).get('libelle', 'N/A')}")
        print(f"   Contrat: {offre.get('typeContrat', 'N/A')}")
    
    # Test 4: Référentiels
    print("\n📋 Test référentiels...")
    regions = client.referentiel("regions")
    print(f"   ✅ {len(regions)} régions récupérées")
    
    print("\n" + "=" * 60)
    print("✅ TOUS LES TESTS SONT PASSÉS !")
    print("=" * 60)
```