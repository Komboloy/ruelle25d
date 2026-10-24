# Ruelle25D — pixel art dans une scène 3D (Godot 4)

Test de l'approche « The Last Night » : des plans en pixel art placés en profondeur dans le
moteur 3D de Godot, qui fournit l'éclairage et l'atmosphère.

Testé sur **Godot 4.7.2**, renderer **Forward+** (obligatoire pour le brouillard volumétrique).

## Ouvrir
Godot → *Import* → `project.godot` → F5.

## Contrôles
| Touche | Effet |
|---|---|
| Flèches / Espace | marcher / sauter (les caisses s'escaladent) |
| 1 | brouillard volumétrique on/off |
| 2 | bloom on/off |
| 3 | profondeur de champ on/off |
| 4 | reflets du sol (SSR) on/off |
| 5 | pluie on/off |
| F1 | masquer / afficher les infos (FPS en tête) |

Les touches 1 à 5 servent à mesurer le coût de chaque effet sur ton Mac (regarde les FPS).

## Ce qui est démontré
- **Profondeur** : ciel, ville lointaine, immeubles, mur de la ruelle, plan de jeu, premier plan.
  Chaque plan est une image pixel art posée sur un quad, à sa distance réelle.
- **Brouillard volumétrique** : faisceaux visibles sous le réverbère, depuis les fenêtres
  (projecteur « barreaux ») et depuis les portes.
- **Bloom** sur les néons et les fenêtres, **profondeur de champ** (ville en bokeh),
  **sol mouillé** avec reflets, **pluie**, néons qui grésillent.
- **Personnage** : sprite sheet Blender + normal map, éclairé par les lumières 3D (il prend la
  couleur des néons qu'il croise), retournement géré dans le shader `sprite_lit.gdshader`.

## Où régler l'ambiance
Tout est dans `alley.gd`, section par section :
- `_build_environment()` : brouillard (densité, couleur), bloom, étalonnage, reflets ;
- `_build_camera()` : focale et profondeur de champ ;
- `_build_lights()`, `_add_door()`, `_add_window_beam()` : lumières et faisceaux
  (`light_volumetric_fog_energy` = intensité du faisceau dans le brouillard).

### Le mur de la ruelle
Peint pixel par pixel par `tools/paint_wall.py` (ruelle japonaise : échoppe de ramen, lanternes,
distributeurs, rideaux de fer, climatiseurs, vélo, gachapon…). Le script produit :
- `wall.png` (couleurs), `wall_normal.png` (calculée depuis une carte de hauteur peinte en même
  temps), `wall_emit.png` (tout ce qui brille) ;
- `wall_lights.json` : une lumière 3D devant chaque élément lumineux (lanternes, néons,
  distributeurs, vitrine), les portes et les fenêtres éclairées. La scène les crée toute seule,
  donc ce qui brille sur le mur éclaire vraiment le personnage.

Pour modifier le mur : édite la section « composition » en bas du script, puis
`python3 tools/paint_wall.py assets/env`.

### Les autres plans
Ville, montagnes et premier plan restent des placeholders générés : remplace-les par tes images
en gardant les noms, ou ajoute-en dans `layers.json` (`z` = profondeur, `x`/`y`/`w`/`h` en
mètres). Densité conseillée : 32 texels/m au plan de jeu, moins pour les plans lointains.

## Le personnage
`blender/` contient les mêmes scripts que le test précédent :
```
blender -b -P blender/demo_personnage.py -P blender/render_sprites.py -- --out assets/player
```
