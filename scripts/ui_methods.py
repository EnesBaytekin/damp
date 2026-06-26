"""Run with: python scripts/ui_methods.py"""
import sys, os
os.chdir('/home/imns/Desktop/sandgame')

def render_preview_code():
    return '''
    def _render_preview(self, t, surf, ox, oy, scale=1):
        w, h = t.width, t.height
        for ty in range(h):
            for tx in range(w):
                if t.grid[ty][tx] == 1:
                    for by in range(scale):
                        for bx in range(scale):
                            px = ox + tx * scale + bx
                            py = oy + ty * scale + by
                            if 0 <= px < surf.get_width() and 0 <= py < surf.get_height():
                                surf.set_at((px, py), (180, 220, 255, 200))

    def _render_text(self, text, surf, x, y, color=(255, 240, 200)):
        from scripts.Template import Template
        rows = Template.render_text(text)
        for row in range(Template.FONT_H):
            for col in range(len(rows[row])):
                if rows[row][col] == '1':
                    px, py = x + col, y + row
                    if 0 <= px < surf.get_width() and 0 <= py < surf.get_height():
                        surf.set_at((px, py), color)

    def _panel_btn(self, surf, x, y, w, h, text, hover=False):
        bg = (80, 72, 58) if not hover else (110, 100, 80)
        bd = (120, 110, 90) if not hover else (160, 150, 130)
        import pygame
        pygame.draw.rect(surf, bg, (x, y, w, h))
        pygame.draw.rect(surf, bd, (x, y, w, h), 1)
        tw = len(text) * 6
        self._render_text(text, surf, x + (w - tw) // 2, y + (h - 7) // 2, (255, 240, 200))

    def _draw_panel_mode_select(self, screen):
        pw, ph = 130, 62
        px0 = (160 - pw) // 2
        py0 = (90 - ph) // 2
        import pygame
        bg = pygame.Surface((pw, ph))
        bg.fill((22, 20, 35))
        screen.surface.blit(bg, (px0, py0))
        pygame.draw.rect(screen.surface, (100, 90, 80), (px0, py0, pw, ph), 1)
        inner = pygame.Surface((pw-4, ph-4))
        inner.fill((28, 25, 42))
        screen.surface.blit(inner, (px0+2, py0+2))
        from pygaminal.input_manager import InputManager
        im = InputManager()
        mx, my = im.get_mouse_position()
        self.quest_hover_btn = ""
        if self.quest_candidates:
            t = self.quest_candidates[self.quest_candidate_idx]
            pv = pygame.Surface((40, 30))
            pv.fill((28, 25, 42))
            sc = min(3, 38 // (t.width or 1), 28 // (t.height or 1))
            sc = max(1, sc)
            self._render_preview(t, pv, 1, 1, sc)
            screen.surface.blit(pv, (px0+6, py0+8))
            self._render_text(t.name.upper(), screen.surface, px0+50, py0+8)
            self._render_text(str(t.width)+'x'+str(t.height), screen.surface, px0+50, py0+16, (160, 180, 200))
            nbw, nbh = 24, 10
            nbx, nby = px0+50, py0+28
            h_prev = nbx <= mx <= nbx+nbw and nby <= my <= nby+nbh
            self._panel_btn(screen.surface, nbx, nby, nbw, nbh, '<--', h_prev)
            if h_prev: self.quest_hover_btn = 'prev'
            h_next = nbx+nbw+4 <= mx <= nbx+nbw*2+4 and nby <= my <= nby+nbh
            self._panel_btn(screen.surface, nbx+nbw+4, nby, nbw, nbh, '-->', h_next)
            if h_next: self.quest_hover_btn = 'next'
            sbx, sby = px0+50, py0+42
            sbw, sbh = 52, 10
            h_sel = sbx <= mx <= sbx+sbw and sby <= my <= sby+sbh
            self._panel_btn(screen.surface, sbx, sby, sbw, sbh, 'SELECT', h_sel)
            if h_sel: self.quest_hover_btn = 'select'

    def _draw_panel_mode_score(self, screen):
        pw, ph = 130, 50
        px0 = (160 - pw) // 2
        py0 = (90 - ph) // 2
        import pygame
        bg = pygame.Surface((pw, ph))
        bg.fill((22, 20, 35))
        screen.surface.blit(bg, (px0, py0))
        pygame.draw.rect(screen.surface, (100, 90, 80), (px0, py0, pw, ph), 1)
        inner = pygame.Surface((pw-4, ph-4))
        inner.fill((28, 25, 42))
        screen.surface.blit(inner, (px0+2, py0+2))
        self._render_text('BLUEPRINT COMPLETE', screen.surface, px0+8, py0+6, (200, 200, 200))
        self._render_text(self.quest_panel_score, screen.surface, px0+12, py0+22, (255, 240, 200))
        from pygaminal.input_manager import InputManager
        im = InputManager()
        mx, my = im.get_mouse_position()
        self.quest_hover_btn = ''
        bx, by, bw, bh = px0+30, py0+37, 60, 9
        h_ok = bx <= mx <= bx+bw and by <= my <= by+bh
        self._panel_btn(screen.surface, bx, by, bw, bh, 'OK', h_ok)
        if h_ok: self.quest_hover_btn = 'ok'
'''

def update_world_controller():
    path = "scripts/WorldController.py"
    with open(path) as f:
        code = f.read()

    # 1. Insert new helper methods before _quest_new_candidates (which already exists)
    insert_point = "    def _quest_new_candidates(self):"
    if insert_point not in code:
        print("ERROR: _quest_new_candidates not found")
        return False

    new_methods = render_preview_code()

    # 2. Replace _draw_panel body
    old_draw = "    def _draw_panel(self):\n        screen = Screen()\n        pw, ph = 110, 55\n        px0 = (160 - pw) // 2\n        py0 = (90 - ph) // 2"
    new_draw = "    def _draw_panel(self):\n        screen = Screen()\n        if self.quest_panel_mode == 'menu':\n            self._draw_panel_mode_select(screen)\n        elif self.quest_panel_mode == 'score':\n            self._draw_panel_mode_score(screen)"

    # 3. Add _quest_placed_done method before _quest_toggle
    score_method = '''
    def _quest_placed_done(self):
        if self.quest_placed and not self.quest_scored:
            w, h = self.quest_template.get_rect()
            c, t, p = self.quest_template.score(
                lambda x, y: self.cm.get_cell(x, y),
                self.quest_wx, self.quest_wy
            )
            self.quest_score = p
            self.quest_panel_score = str(c) + '/' + str(t) + ' = ' + str(p) + '%'
            self.quest_panel_mode = "score"
            self.quest_panel_open = True
            self.quest_scored = True
            self.quest_placed = False
            self.quest_active = False

'''

    insert_before = "    def _quest_toggle(self):"

    # Apply changes
    code = code.replace(old_draw, new_draw)
    code = code.replace(insert_before, score_method + insert_before)

    with open(path, 'w') as f:
        f.write(code)

    # Verify
    import py_compile
    try:
        py_compile.compile(path, doraise=True)
        print("Syntax OK")
        return True
    except py_compile.PyCompileError as e:
        print("Syntax error:", e)
        return False

if __name__ == '__main__':
    update_world_controller()
