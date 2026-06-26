"""
Damp — falling-sand / pixel-simulation sandbox game.
Built on pygaminal (JSON scene + component framework on top of pygame).
"""

import os
import sys
import pygame
from pygaminal import Scene, App, Screen, InputManager, AudioManager
from time import time

LOGICAL_W = 160
LOGICAL_H = 90


def get_component(scene, class_name):
    """Find a component instance by class name in a scene's objects."""
    for obj in scene.objects.values():
        for comp in obj.components.values():
            if type(comp.instance).__name__ == class_name:
                return comp.instance
    return None


def load_scene(scene_name: str) -> Scene:
    scene = Scene.get_scene_from_json(f"scenes/{scene_name}_scene.json")
    app.scenes = {scene_name: scene}
    app.current_scene_name = scene_name
    scene.update()
    return scene


def main():
    # PyInstaller: switch to the temp bundle directory so relative paths work
    if getattr(sys, 'frozen', False):
        os.chdir(sys._MEIPASS)

    pygame.init()

    Screen().surface = pygame.display.set_mode(
        (LOGICAL_W, LOGICAL_H),
        pygame.FULLSCREEN | pygame.SCALED,
    )
    Screen().width = LOGICAL_W
    Screen().height = LOGICAL_H

    InputManager().init()
    AudioManager().init()
    pygame.display.set_caption("Damp")

    global app
    app = App()
    app.width = LOGICAL_W
    app.height = LOGICAL_H
    app.running = True
    app.target_fps = 60
    app.clock = pygame.time.Clock()

    # ── Start with menu scene ──────────────────────────────
    load_scene("menu")
    menu_ctrl = get_component(app.get_current_scene(), "MenuController")

    input_mgr = InputManager()
    app.now = time()
    last_time = app.now

    while app.running:
        input_mgr.update()

        if pygame.K_F11 in input_mgr.just_pressed_keys:
            pygame.display.toggle_fullscreen()

        scene = app.get_current_scene()

        # ── Scene switching ────────────────────────────────
        if menu_ctrl and menu_ctrl.game_started:
            load_scene("game")
            menu_ctrl = None

        if not menu_ctrl:
            world_ctrl = get_component(app.get_current_scene(), "WorldController")
            if world_ctrl and world_ctrl.quit_to_menu:
                load_scene("menu")
                menu_ctrl = get_component(app.get_current_scene(), "MenuController")

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
