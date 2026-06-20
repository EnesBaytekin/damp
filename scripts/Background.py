"""
Simple background image renderer — sits behind everything.
"""

import pygame
from pygaminal.image import Image
from pygaminal.screen import Screen


class Background:
    def __init__(self):
        self.image = Image.from_file("assets/bg.png")

    def update(self, obj):
        pass

    def draw(self, obj):
        Screen().surface.blit(self.image.surface, (0, 0))
