"""
Damp — falling-sand / pixel-simulation sandbox game.
Built on pygaminal (JSON scene + component framework on top of pygame).
"""

import pygame
from pygaminal import Scene, App, Screen, InputManager, AudioManager
from time import time

LOGICAL_W = 160
LOGICAL_H = 90


def main():
    pygame.init()

    # Load scene
    scene = Scene.get_scene_from_json("scenes/main_scene.json")

    # ── FULLSCREEN + SCALED display ──────────────────────────
    Screen().surface = pygame.display.set_mode(
        (LOGICAL_W, LOGICAL_H),
        pygame.FULLSCREEN | pygame.SCALED,
    )
    Screen().width = LOGICAL_W
    Screen().height = LOGICAL_H

    if scene.background_image:
        Screen().set_background_image(scene.background_image)
    elif scene.background_color:
        Screen().set_background_color(scene.background_color)

    # ── Set up pygaminal singletons ─────────────────────────
    InputManager().init()
    AudioManager().init()
    pygame.display.set_caption("Sandcastle Builder")

    app = App()
    app.width = LOGICAL_W
    app.height = LOGICAL_H
    app.scenes = {"main": scene}
    app.current_scene_name = "main"
    app.running = True
    app.target_fps = 60
    app.clock = pygame.time.Clock()

    # ── Game loop ──────────────────────────────────────────
    input_mgr = InputManager()
    app.now = time()
    last_time = app.now

    while app.running:
        input_mgr.update()

        # F11 toggle — InputManager stores just-pressed keys
        if pygame.K_F11 in input_mgr.just_pressed_keys:
            pygame.display.toggle_fullscreen()

        scene.update()

        Screen().clear()
        scene.draw()
        Screen().refresh()

        app.clock.tick(app.target_fps)
        app.now = time()
        app.dt = app.now - last_time
        last_time = app.now

    pygame.quit()


if __name__ == "__main__":
    main()
