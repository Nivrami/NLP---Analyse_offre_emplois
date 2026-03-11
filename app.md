# 💻 Script : app.py

**Source :** `app.py`

```python
"""
Application Streamlit - Analyse des Offres d'Emploi Data/IA
===========================================================
Application interactive pour explorer les offres d'emploi
dans le domaine de la data science et de l'IA en France.

Usage:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from datetime import datetime, timedelta
import json

# Configuration de la page
st.set_page_config(
    page_title="Offres Data/IA en France",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# CONNEXION BASE DE DONNÉES
# =============================================================================

DB_PATH = "data/offres_emploi.db"

@st.cache_resource
def get_connection():
    """Connexion à la base SQLite."""
    return sqlite3.connect(DB_PATH, check_same_thread=False)

@st.cache_data(ttl=300)  # Cache de 5 minutes
def load_offres():
    """Charge toutes les offres avec leurs dimensions."""
    conn = get_connection()
    query = """
        SELECT 
            f.id_offre,
            f.titre,
            f.description,
            f.salaire_min,
            f.salaire_max,
            f.salaire_commentaire,
            f.nombre_postes,
            f.date_creation,
            f.url_offre,
            f.alternance,
            s.nom_source,
            l.commune,
            l.departement,
            l.region,
            l.code_region,
            l.latitude,
            l.longitude,
            e.nom as entreprise,
            c.libelle_contrat as type_contrat,
            m.libelle_rome as metier,
            m.code_rome,
            exp.libelle_experience as experience
        FROM fait_offres f
        LEFT JOIN dim_source s ON f.id_source = s.id_source
        LEFT JOIN dim_lieu l ON f.id_lieu = l.id_lieu
        LEFT JOIN dim_entreprise e ON f.id_entreprise = e.id_entreprise
        LEFT JOIN dim_contrat c ON f.id_contrat = c.id_contrat
        LEFT JOIN dim_metier m ON f.id_metier = m.id_metier
        LEFT JOIN dim_experience exp ON f.id_experience = exp.id_experience
        WHERE f.actif = 1
    """
    df = pd.read_sql_query(query, conn, parse_dates=False)
    df['date_creation'] = pd.to_datetime(df['date_creation'], format='mixed', errors='coerce')
    return df

@st.cache_data(ttl=300)
def load_competences():
    """Charge les compétences par offre."""
    conn = get_connection()
    query = """
        SELECT 
            oc.id_offre,
            c.libelle_competence as competence
        FROM offre_competence oc
        JOIN dim_competence c ON oc.id_competence = c.id_competence
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=300)
def load_stats_regions():
    """Charge les statistiques par région."""
    conn = get_connection()
    query = """
        SELECT 
            l.region,
            l.code_region,
            COUNT(*) as nb_offres,
            AVG(f.salaire_min) as salaire_moyen_min,
            AVG(f.salaire_max) as salaire_moyen_max
        FROM fait_offres f
        JOIN dim_lieu l ON f.id_lieu = l.id_lieu
        WHERE l.region IS NOT NULL
        GROUP BY l.region, l.code_region
        ORDER BY nb_offres DESC
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=300)
def load_top_competences(limit=20):
    """Charge le top des compétences."""
    conn = get_connection()
    query = f"""
        SELECT 
            c.libelle_competence as competence,
            COUNT(*) as nb_offres
        FROM offre_competence oc
        JOIN dim_competence c ON oc.id_competence = c.id_competence
        GROUP BY c.libelle_competence
        ORDER BY nb_offres DESC
        LIMIT {limit}
    """
    return pd.read_sql_query(query, conn)

@st.cache_data(ttl=300)
def load_stats_contrats():
    """Charge les statistiques par type de contrat."""
    conn = get_connection()
    query = """
        SELECT 
            c.libelle_contrat as type_contrat,
            COUNT(*) as nb_offres
        FROM fait_offres f
        JOIN dim_contrat c ON f.id_contrat = c.id_contrat
        GROUP BY c.libelle_contrat
        ORDER BY nb_offres DESC
    """
    return pd.read_sql_query(query, conn)


# =============================================================================
# COORDONNÉES DES RÉGIONS (pour la carte)
# =============================================================================

REGIONS_COORDS = {
    "Île-de-France": {"lat": 48.8566, "lon": 2.3522},
    "Auvergne-Rhône-Alpes": {"lat": 45.7640, "lon": 4.8357},
    "Occitanie": {"lat": 43.6047, "lon": 1.4442},
    "Provence-Alpes-Côte d'Azur": {"lat": 43.9352, "lon": 6.0679},
    "Nouvelle-Aquitaine": {"lat": 44.8378, "lon": -0.5792},
    "Pays de la Loire": {"lat": 47.2184, "lon": -1.5536},
    "Bretagne": {"lat": 48.1173, "lon": -1.6778},
    "Hauts-de-France": {"lat": 49.8941, "lon": 2.2958},
    "Grand Est": {"lat": 48.5734, "lon": 7.7521},
    "Normandie": {"lat": 49.1829, "lon": -0.3707},
    "Bourgogne-Franche-Comté": {"lat": 47.2805, "lon": 4.9994},
    "Centre-Val de Loire": {"lat": 47.9029, "lon": 1.9093},
    "Corse": {"lat": 42.0396, "lon": 9.0129},
    "La Réunion": {"lat": -21.1151, "lon": 55.5364},
    "Martinique": {"lat": 14.6415, "lon": -61.0242},
    "Guadeloupe": {"lat": 16.2650, "lon": -61.5510},
    "Guyane": {"lat": 3.9339, "lon": -53.1258},
    "Mayotte": {"lat": -12.8275, "lon": 45.1662},
}


# =============================================================================
# SIDEBAR - FILTRES
# =============================================================================

def normaliser_type_contrat(type_contrat: str) -> str:
    """Normalise les types de contrats pour regrouper les variantes."""
    if not type_contrat:
        return "Non spécifié"

    type_lower = type_contrat.lower()

    # Stages (toutes variantes)
    if "stage" in type_lower:
        return "Stage"

    # Alternance (apprentissage, professionnalisation)
    if any(x in type_lower for x in ["apprentissage", "alternance", "professionnalisation"]):
        return "Alternance"

    # CDI
    if "cdi" in type_lower or "indéterminée" in type_lower:
        return "CDI"

    # CDD
    if "cdd" in type_lower or "déterminée" in type_lower:
        return "CDD"

    # Intérim
    if any(x in type_lower for x in ["intérim", "interim", "mission", "temporaire"]):
        return "Intérim"

    # Freelance
    if any(x in type_lower for x in ["freelance", "indépendant", "libéral"]):
        return "Freelance"

    return type_contrat


def render_sidebar(df):
    """Affiche les filtres dans la sidebar."""
    st.sidebar.header("🔍 Filtres")

    # Filtre région
    regions = ["Toutes"] + sorted(df['region'].dropna().unique().tolist())
    selected_region = st.sidebar.selectbox("📍 Région", regions)

    # =========================================================================
    # FILTRE TYPE DE CONTRAT AMÉLIORÉ
    # =========================================================================
    st.sidebar.subheader("📄 Type de contrat")

    # Normaliser les types de contrats dans le dataframe
    df['type_contrat_normalise'] = df['type_contrat'].apply(normaliser_type_contrat)

    # Obtenir les types uniques normalisés
    types_disponibles = sorted(df['type_contrat_normalise'].dropna().unique().tolist())

    # Boutons rapides pour les types les plus courants
    col1, col2 = st.sidebar.columns(2)

    # Initialiser l'état des filtres rapides si nécessaire
    if 'filtre_stages' not in st.session_state:
        st.session_state.filtre_stages = False
    if 'filtre_alternance' not in st.session_state:
        st.session_state.filtre_alternance = False

    with col1:
        if st.button("🎓 Stages", use_container_width=True,
                     type="primary" if st.session_state.filtre_stages else "secondary"):
            st.session_state.filtre_stages = not st.session_state.filtre_stages
            st.session_state.filtre_alternance = False
            st.rerun()

    with col2:
        if st.button("📚 Alternance", use_container_width=True,
                     type="primary" if st.session_state.filtre_alternance else "secondary"):
            st.session_state.filtre_alternance = not st.session_state.filtre_alternance
            st.session_state.filtre_stages = False
            st.rerun()

    # Multi-sélection des types de contrats
    if st.session_state.filtre_stages:
        selected_contrats = ["Stage"]
    elif st.session_state.filtre_alternance:
        selected_contrats = ["Alternance"]
    else:
        selected_contrats = st.sidebar.multiselect(
            "Sélectionner les types",
            options=types_disponibles,
            default=[],
            placeholder="Tous les types"
        )

    # Filtre expérience
    experiences = ["Toutes"] + sorted(df['experience'].dropna().unique().tolist())
    selected_exp = st.sidebar.selectbox("💼 Expérience", experiences)

    # Filtre salaire
    st.sidebar.subheader("💰 Salaire annuel (k€)")
    salaire_min = st.sidebar.slider("Minimum", 0, 100, 0, step=5)
    salaire_max = st.sidebar.slider("Maximum", 0, 150, 150, step=5)

    # Filtre mot-clé
    keyword = st.sidebar.text_input("🔎 Mot-clé dans le titre")

    # =========================================================================
    # APPLIQUER LES FILTRES
    # =========================================================================
    df_filtered = df.copy()

    if selected_region != "Toutes":
        df_filtered = df_filtered[df_filtered['region'] == selected_region]

    # Filtre contrat amélioré (multi-sélection)
    if selected_contrats:
        df_filtered = df_filtered[df_filtered['type_contrat_normalise'].isin(selected_contrats)]

    if selected_exp != "Toutes":
        df_filtered = df_filtered[df_filtered['experience'] == selected_exp]

    if salaire_min > 0:
        df_filtered = df_filtered[
            (df_filtered['salaire_min'].isna()) |
            (df_filtered['salaire_min'] >= salaire_min * 1000)
        ]

    if salaire_max < 150:
        df_filtered = df_filtered[
            (df_filtered['salaire_max'].isna()) |
            (df_filtered['salaire_max'] <= salaire_max * 1000)
        ]

    if keyword:
        df_filtered = df_filtered[
            df_filtered['titre'].str.contains(keyword, case=False, na=False)
        ]

    # Afficher le nombre de résultats
    st.sidebar.markdown("---")

    # Indicateur spécial pour les stages/alternance
    nb_stages = len(df[df['type_contrat_normalise'] == 'Stage'])
    nb_alternance = len(df[df['type_contrat_normalise'] == 'Alternance'])

    st.sidebar.metric("Offres filtrées", len(df_filtered), f"{len(df_filtered) - len(df):+d}")

    # Compteurs par type
    st.sidebar.caption(f"🎓 {nb_stages} stages | 📚 {nb_alternance} alternances disponibles")

    return df_filtered


# =============================================================================
# PAGE 1 : ACCUEIL / DASHBOARD
# =============================================================================

def page_accueil(df, df_competences):
    """Page d'accueil avec les statistiques globales."""
    st.title("📊 Analyse des Offres d'Emploi Data/IA en France")
    st.markdown("*Exploration interactive du marché de l'emploi dans la data science et l'intelligence artificielle*")
    
    # Métriques principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 Total offres", f"{len(df):,}")
    
    with col2:
        nb_regions = df['region'].nunique()
        st.metric("📍 Régions", nb_regions)
    
    with col3:
        nb_entreprises = df['entreprise'].nunique()
        st.metric("🏢 Entreprises", f"{nb_entreprises:,}")
    
    with col4:
        salaire_moyen = df['salaire_min'].mean()
        if pd.notna(salaire_moyen):
            st.metric("💰 Salaire moyen", f"{salaire_moyen/1000:.0f}k€")
        else:
            st.metric("💰 Salaire moyen", "N/A")
    
    st.markdown("---")
    
    # Graphiques
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📍 Répartition par région")
        df_regions = load_stats_regions()
        fig = px.bar(
            df_regions.head(10), 
            x='nb_offres', 
            y='region',
            orientation='h',
            color='nb_offres',
            color_continuous_scale='Blues'
        )
        fig.update_layout(
            yaxis={'categoryorder': 'total ascending'},
            showlegend=False,
            height=400,
            xaxis_title="Nombre d'offres",
            yaxis_title=""
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("📄 Types de contrats")
        # Utiliser les types normalisés
        df_contrats_norm = df.groupby('type_contrat_normalise').size().reset_index(name='nb_offres')
        df_contrats_norm = df_contrats_norm.sort_values('nb_offres', ascending=False)

        # Couleurs personnalisées pour mettre en évidence stages et alternance
        color_map = {
            'Stage': '#FF6B6B',        # Rouge/rose pour les stages
            'Alternance': '#4ECDC4',   # Turquoise pour l'alternance
            'CDI': '#45B7D1',          # Bleu pour CDI
            'CDD': '#96CEB4',          # Vert pour CDD
            'Intérim': '#FFEAA7',      # Jaune pour intérim
            'Freelance': '#DDA0DD',    # Violet pour freelance
            'Non spécifié': '#95A5A6'  # Gris pour non spécifié
        }

        fig = px.pie(
            df_contrats_norm,
            values='nb_offres',
            names='type_contrat_normalise',
            color='type_contrat_normalise',
            color_discrete_map=color_map
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(height=400, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
    
    # Top compétences
    st.subheader("🛠️ Top 15 compétences demandées")
    df_comp = load_top_competences(15)
    fig = px.bar(
        df_comp,
        x='nb_offres',
        y='competence',
        orientation='h',
        color='nb_offres',
        color_continuous_scale='Viridis'
    )
    fig.update_layout(
        yaxis={'categoryorder': 'total ascending'},
        showlegend=False,
        height=500,
        xaxis_title="Nombre d'offres",
        yaxis_title=""
    )
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# PAGE 2 : CARTE INTERACTIVE
# =============================================================================

def page_carte(df):
    """Page avec la carte interactive des offres par région."""
    st.title("🗺️ Carte des Offres par Région")
    
    # Préparer les données
    df_regions = df.groupby('region').agg({
        'id_offre': 'count',
        'salaire_min': 'mean',
        'salaire_max': 'mean'
    }).reset_index()
    df_regions.columns = ['region', 'nb_offres', 'salaire_moyen_min', 'salaire_moyen_max']
    
    # Ajouter les coordonnées
    df_regions['lat'] = df_regions['region'].map(lambda x: REGIONS_COORDS.get(x, {}).get('lat'))
    df_regions['lon'] = df_regions['region'].map(lambda x: REGIONS_COORDS.get(x, {}).get('lon'))
    df_regions = df_regions.dropna(subset=['lat', 'lon'])
    
    # Créer la carte avec Plotly
    fig = px.scatter_mapbox(
        df_regions,
        lat='lat',
        lon='lon',
        size='nb_offres',
        color='nb_offres',
        hover_name='region',
        hover_data={
            'nb_offres': True,
            'salaire_moyen_min': ':.0f',
            'lat': False,
            'lon': False
        },
        color_continuous_scale='Reds',
        size_max=50,
        zoom=4.5,
        center={"lat": 46.603354, "lon": 1.888334}
    )
    
    fig.update_layout(
        mapbox_style="carto-positron",
        height=600,
        margin={"r": 0, "t": 0, "l": 0, "b": 0}
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Tableau récapitulatif
    st.subheader("📊 Détail par région")
    df_display = df_regions[['region', 'nb_offres', 'salaire_moyen_min', 'salaire_moyen_max']].copy()
    df_display['salaire_moyen_min'] = df_display['salaire_moyen_min'].apply(lambda x: f"{x/1000:.0f}k€" if pd.notna(x) else "N/A")
    df_display['salaire_moyen_max'] = df_display['salaire_moyen_max'].apply(lambda x: f"{x/1000:.0f}k€" if pd.notna(x) else "N/A")
    df_display.columns = ['Région', 'Nb offres', 'Salaire min moyen', 'Salaire max moyen']
    st.dataframe(df_display.sort_values('Nb offres', ascending=False), use_container_width=True, hide_index=True)


# =============================================================================
# PAGE 3 : EXPLORATION DES OFFRES
# =============================================================================

def get_contrat_badge(type_contrat: str, type_normalise: str) -> str:
    """Retourne un badge coloré pour le type de contrat."""
    badges = {
        "Stage": "🎓 Stage",
        "Alternance": "📚 Alternance",
        "CDI": "✅ CDI",
        "CDD": "📋 CDD",
        "Intérim": "⏱️ Intérim",
        "Freelance": "💼 Freelance"
    }
    return badges.get(type_normalise, type_contrat or "Non spécifié")


def page_exploration(df):
    """Page d'exploration détaillée des offres."""
    st.title("🔍 Exploration des Offres")

    # Compteurs par type de contrat
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        nb_stages = len(df[df['type_contrat_normalise'] == 'Stage'])
        st.metric("🎓 Stages", nb_stages)
    with col2:
        nb_alternance = len(df[df['type_contrat_normalise'] == 'Alternance'])
        st.metric("📚 Alternances", nb_alternance)
    with col3:
        nb_cdi = len(df[df['type_contrat_normalise'] == 'CDI'])
        st.metric("✅ CDI", nb_cdi)
    with col4:
        nb_cdd = len(df[df['type_contrat_normalise'] == 'CDD'])
        st.metric("📋 CDD", nb_cdd)

    st.markdown("---")

    # Options d'affichage
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info(f"📋 {len(df)} offres correspondent à vos critères")
    with col2:
        nb_display = st.selectbox("Afficher", [10, 25, 50, 100], index=1)

    # Tableau des offres avec badges colorés
    df_display = df[['titre', 'entreprise', 'region', 'type_contrat', 'type_contrat_normalise', 'salaire_commentaire', 'date_creation']].copy()
    # Gérer les dates manquantes (NaT)
    df_display['date_creation'] = df_display['date_creation'].apply(
        lambda x: x.strftime('%d/%m/%Y') if pd.notna(x) else 'N/A'
    )

    # Appliquer les badges aux types de contrats
    df_display['Contrat'] = df_display.apply(
        lambda row: get_contrat_badge(row['type_contrat'], row['type_contrat_normalise']),
        axis=1
    )

    df_display = df_display[['titre', 'entreprise', 'region', 'Contrat', 'salaire_commentaire', 'date_creation']]
    df_display.columns = ['Titre', 'Entreprise', 'Région', 'Contrat', 'Salaire', 'Date']

    st.dataframe(
        df_display.head(nb_display),
        use_container_width=True,
        hide_index=True
    )
    
    # Détail d'une offre
    st.markdown("---")
    st.subheader("📄 Détail d'une offre")
    
    offre_titles = df['titre'].tolist()[:100]  # Limiter pour la performance
    selected_title = st.selectbox("Sélectionner une offre", offre_titles)
    
    if selected_title:
        offre = df[df['titre'] == selected_title].iloc[0]
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**🏢 Entreprise:** {offre['entreprise'] or 'Non spécifiée'}")
            st.markdown(f"**📍 Lieu:** {offre['commune'] or ''}, {offre['region'] or 'Non spécifié'}")
            st.markdown(f"**📄 Contrat:** {offre['type_contrat']}")
        
        with col2:
            st.markdown(f"**💼 Expérience:** {offre['experience'] or 'Non spécifiée'}")
            st.markdown(f"**💰 Salaire:** {offre['salaire_commentaire'] or 'Non spécifié'}")
            date_str = offre['date_creation'].strftime('%d/%m/%Y') if pd.notna(offre['date_creation']) else 'N/A'
            st.markdown(f"**📅 Date:** {date_str}")
        
        st.markdown("**📝 Description:**")
        st.text_area("", offre['description'][:2000] if offre['description'] else "Pas de description", height=200, disabled=True)
        
        if offre['url_offre']:
            st.markdown(f"[🔗 Voir l'offre originale]({offre['url_offre']})")


# =============================================================================
# PAGE 4 : ANALYSE DES COMPÉTENCES
# =============================================================================

def page_competences(df, df_competences):
    """Page d'analyse des compétences."""
    st.title("🛠️ Analyse des Compétences")
    
    # Fusionner avec les offres filtrées
    df_comp_filtered = df_competences[df_competences['id_offre'].isin(df['id_offre'])]
    
    # Top compétences
    top_comp = df_comp_filtered['competence'].value_counts().head(20).reset_index()
    top_comp.columns = ['competence', 'nb_offres']
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Top 20 compétences")
        fig = px.bar(
            top_comp,
            x='nb_offres',
            y='competence',
            orientation='h',
            color='nb_offres',
            color_continuous_scale='Plasma'
        )
        fig.update_layout(
            yaxis={'categoryorder': 'total ascending'},
            showlegend=False,
            height=600,
            xaxis_title="Nombre d'offres",
            yaxis_title=""
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("☁️ Nuage de compétences")
        # Afficher comme liste avec tailles
        st.markdown("**Compétences les plus demandées :**")
        for _, row in top_comp.head(15).iterrows():
            size = int(10 + row['nb_offres'] / top_comp['nb_offres'].max() * 20)
            st.markdown(f"<span style='font-size:{size}px'>{row['competence']}</span> ({row['nb_offres']})", unsafe_allow_html=True)
    
    # Compétences par région
    st.markdown("---")
    st.subheader("📍 Compétences par région")
    
    # Sélection de région
    regions = sorted(df['region'].dropna().unique().tolist())
    selected_region = st.selectbox("Choisir une région", regions)
    
    if selected_region:
        offres_region = df[df['region'] == selected_region]['id_offre']
        comp_region = df_comp_filtered[df_comp_filtered['id_offre'].isin(offres_region)]
        top_comp_region = comp_region['competence'].value_counts().head(10).reset_index()
        top_comp_region.columns = ['competence', 'nb_offres']
        
        fig = px.bar(
            top_comp_region,
            x='competence',
            y='nb_offres',
            color='nb_offres',
            color_continuous_scale='Teal'
        )
        fig.update_layout(
            showlegend=False,
            height=400,
            xaxis_title="",
            yaxis_title="Nombre d'offres"
        )
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# PAGE 5 : ÉVOLUTION TEMPORELLE
# =============================================================================

def page_evolution(df):
    """Page d'analyse de l'évolution temporelle."""
    st.title("📈 Évolution Temporelle")
    
    # Offres par jour
    df_time = df.groupby(df['date_creation'].dt.date).size().reset_index()
    df_time.columns = ['date', 'nb_offres']
    df_time['date'] = pd.to_datetime(df_time['date'], format='mixed', errors='coerce')
    
    st.subheader("📅 Nouvelles offres par jour")
    fig = px.line(
        df_time,
        x='date',
        y='nb_offres',
        markers=True
    )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Nombre d'offres",
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Offres par semaine
    df['semaine'] = df['date_creation'].dt.isocalendar().week
    df_week = df.groupby('semaine').size().reset_index()
    df_week.columns = ['semaine', 'nb_offres']
    
    st.subheader("📊 Offres par semaine")
    fig = px.bar(
        df_week,
        x='semaine',
        y='nb_offres',
        color='nb_offres',
        color_continuous_scale='Blues'
    )
    fig.update_layout(
        xaxis_title="Semaine",
        yaxis_title="Nombre d'offres",
        showlegend=False,
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Fonction principale."""
    
    # Charger les données
    try:
        df = load_offres()
        df_competences = load_competences()
    except Exception as e:
        st.error(f"❌ Erreur de connexion à la base de données : {e}")
        st.info("Vérifiez que le fichier `data/offres_emploi.db` existe.")
        return
    
    # Sidebar avec filtres
    df_filtered = render_sidebar(df)
    
    # Navigation
    st.sidebar.markdown("---")
    st.sidebar.header("📑 Navigation")
    
    pages = {
        "🏠 Accueil": "accueil",
        "🗺️ Carte": "carte",
        "🔍 Exploration": "exploration",
        "🛠️ Compétences": "competences",
        "📈 Évolution": "evolution"
    }
    
    selected_page = st.sidebar.radio("", list(pages.keys()))
    
    # Afficher la page sélectionnée
    if pages[selected_page] == "accueil":
        page_accueil(df_filtered, df_competences)
    elif pages[selected_page] == "carte":
        page_carte(df_filtered)
    elif pages[selected_page] == "exploration":
        page_exploration(df_filtered)
    elif pages[selected_page] == "competences":
        page_competences(df_filtered, df_competences)
    elif pages[selected_page] == "evolution":
        page_evolution(df_filtered)
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"*Données : {len(df)} offres*")


if __name__ == "__main__":
    main()

```