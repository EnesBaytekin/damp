# Damp

A falling-sand / pixel-simulation sandbox game. Mix sand and water to build castles, bridges, and other structures in an infinite procedural world.

## Objective

There is no fixed goal — Damp is a creative sandbox. The built-in **blueprint system** gives you objectives: open the catalogue, pick a castle silhouette, place it on the map, and fill it in with sand. The game scores your accuracy when you submit. Try to get 100%!

Beyond quests, you're free to experiment with the physics — build towers, dig caves, divert rivers with sand dams, or just watch the sand pile up.

## How to play

1. Move around the world with **WASD**. Jump with **W** or **Space**.
2. Use number keys **1-4** to select a material (dry sand, water, wet sand, water eraser).
3. **Left click** to paint material onto the map. **Right click** to erase.
4. Wet sand sticks together and can form overhangs, arches, and bridges. Dry sand always settles at its natural angle.
5. Press **5** or click the small quest button on the right edge of the screen to open the blueprint panel. Browse castle shapes, select one, place it on the map, and try to match it perfectly.
6. Walk far in any direction — the world generates infinite procedural terrain with mountains, caves, rivers, and valleys.

## Controls

| Key | Action |
|-----|--------|
| `W` / `Space` | Jump |
| `A` / `D` | Move left / right |
| **1** | Dry sand brush |
| **2** | Water brush |
| **3** | Wet sand brush |
| **4** | Water eraser |
| **5** / Quest button | Open blueprint panel |
| Left click | Paint / Place quest template |
| Right click | Erase |
| `Ctrl` + drag | Paint / erase a straight line |
| `-` / `+` / Scroll wheel | Brush radius |
| `F3` | Debug overlay |
| `F11` | Toggle fullscreen |
| `ESC` | Return to menu |

## Features

- **Particle physics**: Sand falls and piles naturally. Water flows, spreads, and wets adjacent sand. Wetness diffuses through piles over time.
- **Sleep system**: Settled particles go to sleep to save CPU. Disturbances (erosion, vibration from above) wake them up.
- **Infinite world**: Horizontally infinite procedural terrain with seeded generation. Caves, overhangs, and worm tunnels carved into the landscape.
- **Blueprints**: Random castle-shaped templates to find and fill. Score tracks your accuracy.
- **Character**: Walk, jump, and interact with the sand world in first-person-pixel style.
- **2× zoom pixel art**: 80×45 logical viewport scaled 2× to 160×90, crisp pixel-perfect rendering.

## Running

### Pre-built binary (recommended)
```bash
./dist/Damp
```

### From source
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Built with

- Python + [pygaminal](https://github.com/enesbaytekin/gaminal) + pygame
- 160×90 logical resolution, hardware-scaled to fullscreen via pygame.SCALED
