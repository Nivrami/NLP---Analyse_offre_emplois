"""
Génération du diagramme du modèle en étoile
===========================================
Crée une image du schéma de base de données pour le rapport.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, ConnectionPatch
import numpy as np

def create_star_schema_diagram():
    """Crée un diagramme visuel du modèle en étoile."""
    
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 12)
    ax.set_aspect('equal')
    ax.axis('off')
    
    # Couleurs
    color_fact = '#E74C3C'      # Rouge pour la table de faits
    color_dim = '#3498DB'        # Bleu pour les dimensions
    color_assoc = '#27AE60'      # Vert pour les tables associatives
    color_text = 'white'
    
    # Position centrale pour la table de faits
    center_x, center_y = 8, 6
    
    # Table de faits (centre)
    fact_box = FancyBboxPatch((center_x - 1.8, center_y - 1.2), 3.6, 2.4,
                               boxstyle="round,pad=0.05,rounding_size=0.2",
                               facecolor=color_fact, edgecolor='black', linewidth=2)
    ax.add_patch(fact_box)
    ax.text(center_x, center_y + 0.6, 'fait_offres', fontsize=12, fontweight='bold',
            ha='center', va='center', color=color_text)
    ax.text(center_x, center_y + 0.1, '2 108 offres', fontsize=9,
            ha='center', va='center', color=color_text)
    ax.text(center_x, center_y - 0.4, 'TABLE DE FAITS', fontsize=8,
            ha='center', va='center', color=color_text, style='italic')
    
    # Dimensions (autour du centre)
    dimensions = [
        ('dim_source', '2 sources', 2, 10),
        ('dim_lieu', '491 lieux', 5, 10.5),
        ('dim_temps', '151 dates', 8, 11),
        ('dim_entreprise', '566 entreprises', 11, 10.5),
        ('dim_contrat', '10 types', 14, 10),
        ('dim_metier', '214 métiers', 14, 6),
        ('dim_experience', '3 niveaux', 14, 2),
        ('dim_competence', '679 compétences', 8, 1),
        ('dim_qualification', '(vide)', 2, 2),
    ]
    
    for name, count, x, y in dimensions:
        # Box de la dimension
        box = FancyBboxPatch((x - 1.3, y - 0.6), 2.6, 1.2,
                             boxstyle="round,pad=0.03,rounding_size=0.15",
                             facecolor=color_dim, edgecolor='black', linewidth=1.5)
        ax.add_patch(box)
        ax.text(x, y + 0.2, name, fontsize=9, fontweight='bold',
                ha='center', va='center', color=color_text)
        ax.text(x, y - 0.2, count, fontsize=8,
                ha='center', va='center', color=color_text)
        
        # Ligne vers le centre
        ax.annotate('', xy=(center_x, center_y), xytext=(x, y),
                    arrowprops=dict(arrowstyle='->', color='gray', lw=1.5))
    
    # Tables associatives
    assoc_tables = [
        ('offre_competence', '1466 assoc.', 5, 3),
        ('offre_formation', '172 assoc.', 11, 3),
        ('offre_langue', '188 assoc.', 5, 8),
    ]
    
    for name, count, x, y in assoc_tables:
        box = FancyBboxPatch((x - 1.2, y - 0.5), 2.4, 1.0,
                             boxstyle="round,pad=0.03,rounding_size=0.1",
                             facecolor=color_assoc, edgecolor='black', linewidth=1)
        ax.add_patch(box)
        ax.text(x, y + 0.15, name, fontsize=8, fontweight='bold',
                ha='center', va='center', color=color_text)
        ax.text(x, y - 0.2, count, fontsize=7,
                ha='center', va='center', color=color_text)
        
        # Ligne vers le centre
        ax.annotate('', xy=(center_x, center_y), xytext=(x, y),
                    arrowprops=dict(arrowstyle='->', color='gray', lw=1, ls='--'))
    
    # Légende
    legend_elements = [
        mpatches.Patch(facecolor=color_fact, edgecolor='black', label='Table de faits'),
        mpatches.Patch(facecolor=color_dim, edgecolor='black', label='Dimensions'),
        mpatches.Patch(facecolor=color_assoc, edgecolor='black', label='Tables associatives'),
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=10)
    
    # Titre
    ax.text(8, 11.8, 'Modèle en Étoile - Entrepôt de Données des Offres d\'Emploi',
            fontsize=14, fontweight='bold', ha='center', va='center')
    
    # Sous-titre
    ax.text(8, 0.3, 'SGBD: SQLite | Source: API France Travail | 2 108 offres collectées',
            fontsize=10, ha='center', va='center', color='gray')
    
    plt.tight_layout()
    plt.savefig('docs/modele_etoile.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.savefig('docs/modele_etoile.pdf', bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print("✅ Diagramme sauvegardé : docs/modele_etoile.png et docs/modele_etoile.pdf")
    plt.show()

if __name__ == "__main__":
    create_star_schema_diagram()
