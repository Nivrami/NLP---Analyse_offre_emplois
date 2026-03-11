# Documentation du Modèle de Données

## 1. Architecture générale

Le modèle de données suit une architecture en **étoile (star schema)**, adaptée à l'analyse OLAP des offres d'emploi. Cette structure permet des requêtes analytiques performantes et une navigation intuitive entre les différentes dimensions d'analyse.

### Composants du modèle

| Type | Nombre | Description |
|------|--------|-------------|
| Table de faits | 1 | `fait_offres` - Les offres d'emploi |
| Tables de dimensions | 9 | Axes d'analyse (lieu, temps, métier, etc.) |
| Tables associatives | 4 | Relations many-to-many (compétences, langues, etc.) |

## 2. Table de faits : `fait_offres`

La table centrale contient les offres d'emploi avec leurs mesures et clés étrangères vers les dimensions.

### Colonnes principales

| Colonne | Type | Description | Taux remplissage |
|---------|------|-------------|------------------|
| `id_offre` | INTEGER | Clé primaire auto-incrémentée | 100% |
| `id_offre_source` | VARCHAR | Identifiant original de l'offre | 100% |
| `titre` | VARCHAR | Intitulé du poste | 100% |
| `description` | TEXT | Description complète de l'offre | 100% |
| `salaire_commentaire` | VARCHAR | Information sur le salaire | 32% |
| `nombre_postes` | INTEGER | Nombre de postes à pourvoir | 100% |
| `alternance` | BOOLEAN | Offre en alternance | 100% |
| `accessible_th` | BOOLEAN | Accessible travailleurs handicapés | 100% |
| `date_creation` | DATETIME | Date de publication | 100% |
| `url_offre` | VARCHAR | Lien vers l'offre originale | 100% |
| `actif` | BOOLEAN | Offre encore active | 100% |

### Clés étrangères

| FK | Dimension | Taux remplissage |
|----|-----------|------------------|
| `id_source` | dim_source | 100% |
| `id_lieu` | dim_lieu | 90.3% |
| `id_entreprise` | dim_entreprise | 60.7% |
| `id_contrat` | dim_contrat | 100% |
| `id_metier` | dim_metier | 100% |
| `id_temps_publication` | dim_temps | 100% |
| `id_experience` | dim_experience | 100% |

## 3. Tables de dimensions

### 3.1 `dim_lieu` - Dimension géographique

Dimension essentielle pour l'analyse régionale demandée dans le projet.

| Colonne | Description |
|---------|-------------|
| `code_postal` | Code postal |
| `code_commune` | Code INSEE de la commune |
| `commune` | Nom de la commune |
| `code_departement` | Code département (2-3 chiffres) |
| `departement` | Nom du département |
| `code_region` | Code région |
| `region` | Nom de la région |
| `latitude` | Coordonnée GPS latitude |
| `longitude` | Coordonnée GPS longitude |

**Statistiques :**
- 491 localisations distinctes
- 10 régions couvertes
- 1747 offres géolocalisées (coordonnées GPS)

### 3.2 `dim_temps` - Dimension temporelle

Permet l'analyse de l'évolution des offres dans le temps.

| Colonne | Description |
|---------|-------------|
| `date_complete` | Date au format ISO |
| `jour`, `mois`, `annee` | Composants de la date |
| `trimestre` | Trimestre (1-4) |
| `semaine` | Numéro de semaine ISO |
| `jour_semaine` | Jour de la semaine (0=Lundi) |
| `nom_jour`, `nom_mois` | Libellés en français |

### 3.3 `dim_metier` - Dimension métier

Basée sur le référentiel ROME (Répertoire Opérationnel des Métiers et des Emplois).

| Colonne | Description |
|---------|-------------|
| `code_rome` | Code ROME (ex: M1405) |
| `libelle_rome` | Intitulé du métier |
| `code_domaine` | Code du domaine professionnel |
| `libelle_domaine` | Libellé du domaine |

**Statistiques :** 214 métiers distincts identifiés

### 3.4 `dim_contrat` - Dimension type de contrat

| Colonne | Description |
|---------|-------------|
| `code_contrat` | Code (CDI, CDD, MIS, etc.) |
| `libelle_contrat` | Libellé complet |
| `code_nature` | Nature du contrat |

**Répartition observée :**
- CDI : 1725 offres (82%)
- CDD : 197 offres (9%)
- Intérim : 152 offres (7%)
- Autres : 34 offres (2%)

### 3.5 `dim_entreprise` - Dimension entreprise

| Colonne | Description |
|---------|-------------|
| `nom` | Raison sociale |
| `description` | Présentation de l'entreprise |
| `logo_url` | URL du logo |
| `secteur_activite` | Secteur d'activité |
| `code_naf` | Code NAF |

**Statistiques :** 566 entreprises distinctes

### 3.6 `dim_competence` - Dimension compétences

| Colonne | Description |
|---------|-------------|
| `code_competence` | Code interne |
| `libelle_competence` | Description de la compétence |
| `type_competence` | Type (savoir, savoir-faire, savoir-être) |

**Statistiques :** 679 compétences identifiées

### 3.7 `dim_experience` - Dimension expérience

| Code | Libellé |
|------|---------|
| D | Débutant accepté |
| S | Expérience souhaitée |
| E | Expérience exigée |

### 3.8 `dim_source` - Dimension source

| Source | Type | URL |
|--------|------|-----|
| France Travail | API | francetravail.fr |
| Welcome to the Jungle | Scraping | welcometothejungle.com |
| Indeed | Scraping | indeed.fr |
| HelloWork | Scraping | hellowork.com |

## 4. Tables associatives

### 4.1 `offre_competence`

Relation N-N entre offres et compétences.

| Colonne | Description |
|---------|-------------|
| `id_offre` | FK vers fait_offres |
| `id_competence` | FK vers dim_competence |
| `exigence` | E (Exigé) ou S (Souhaité) |

**Statistiques :** 1466 associations pour 292 offres

### 4.2 `offre_formation`

Formations requises pour les offres.

| Colonne | Description |
|---------|-------------|
| `id_offre` | FK vers fait_offres |
| `code_formation` | Code de la formation |
| `libelle_formation` | Intitulé |
| `niveau_requis` | Niveau demandé |

### 4.3 `offre_langue`

Langues demandées.

| Colonne | Description |
|---------|-------------|
| `id_offre` | FK vers fait_offres |
| `code_langue` | Code ISO de la langue |
| `libelle_langue` | Nom de la langue |
| `niveau` | Niveau requis |

## 5. Index de performance

```sql
CREATE INDEX idx_offres_date_creation ON fait_offres(date_creation);
CREATE INDEX idx_offres_source ON fait_offres(id_source);
CREATE INDEX idx_offres_lieu ON fait_offres(id_lieu);
CREATE INDEX idx_offres_metier ON fait_offres(id_metier);
CREATE INDEX idx_offres_contrat ON fait_offres(id_contrat);
CREATE INDEX idx_offres_actif ON fait_offres(actif);
CREATE INDEX idx_lieu_region ON dim_lieu(code_region);
CREATE INDEX idx_lieu_departement ON dim_lieu(code_departement);
```

## 6. Volumétrie actuelle

| Élément | Volume |
|---------|--------|
| Offres d'emploi | 1 029 |
| Entreprises | 566 |
| Localisations | 491 |
| Compétences | 679 |
| Métiers (ROME) | 214 |
| Régions couvertes | 10 |

## 7. Qualité des données

### Points forts
- Taux de remplissage excellent sur les champs essentiels (titre, description, contrat, métier)
- 90% des offres géolocalisées
- Bonne couverture géographique nationale

### Points d'attention
- Salaire renseigné dans seulement 32% des cas
- Compétences explicites pour 14% des offres seulement
- 546 offres sans région identifiée (départements non mappés)


