"""
ChunkManager — owns all horizontal chunks (80×90), handles cross-chunk
movement and terrain generation with caves, overhangs, and worm tunnels.
"""

import random
import math
from scripts.Chunk import Chunk, CHUNK_SIZE, CHUNK_HEIGHT, EMPTY


def _smooth_noise(wx: int, seed: int, spacing: float = 80.0) -> float:
    """Very smooth 1D pseudo-noise by cosine-interpolating sparse samples."""
    p = wx / spacing
    i0 = int(math.floor(p))
    i1 = i0 + 1

    def _sample(idx: int) -> float:
        h = hash((idx, seed, 0xBEAD))
        h = (h * 0x9E3779B9) & 0xFFFFFFFF
        return (h % 10000) / 10000.0

    v0 = _sample(i0)
    v1 = _sample(i1)
    t = p - i0
    ct = (1.0 - math.cos(t * math.pi)) * 0.5
    return v0 + (v1 - v0) * ct


def _height_at(wx: int, seed: int) -> int:
    """Terrain height (0-80) at world x — large hills + micro-roughness."""
    macro = _smooth_noise(wx, seed, 80.0)
    micro = _smooth_noise(wx, seed + 7777, 6.0)
    roughness = (micro - 0.5) * 6
    raw = macro * 80 + roughness
    return int(max(0, min(80, raw)))




# ── ChunkManager ───────────────────────────────────────────

class ChunkManager:
    """Horizontally-chunked world manager."""

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.chunks: dict[int, Chunk] = {}
        self.rng = random.Random(seed)
        self.frame = 0
        self._cross_moves: list[tuple[int, int, int, int]] = []
        self._diffusion_xfers: list[tuple[int, int, int, int, int, int, float]] = []
        self._ptypes: dict = {}

    def get_chunk(self, cx: int, create: bool = True) -> Chunk | None:
        if cx not in self.chunks and create:
            c = Chunk(cx, manager=self)
            c.particle_types = self._ptypes
            self.chunks[cx] = c
            return c
        return self.chunks.get(cx)

    def set_particle_types(self, types: dict):
        self._ptypes = types
        for c in self.chunks.values():
            c.particle_types = types

    def register(self, type_id: int, props: dict):
        self._ptypes[type_id] = props
        for c in self.chunks.values():
            c.particle_types = self._ptypes

    # ── world-level cell access ────────────────────────────

    def get_cell(self, wx: int, wy: int) -> int:
        cx, lx = wx // CHUNK_SIZE, wx % CHUNK_SIZE
        if not (0 <= wy < CHUNK_HEIGHT):
            return EMPTY
        chunk = self.get_chunk(cx, create=False)
        return EMPTY if chunk is None else chunk.grid[wy][lx]

    def get_wetness(self, wx: int, wy: int) -> float:
        cx, lx = wx // CHUNK_SIZE, wx % CHUNK_SIZE
        if not (0 <= wy < CHUNK_HEIGHT):
            return 0.0
        chunk = self.get_chunk(cx, create=False)
        return 0.0 if chunk is None else chunk.wetness[wy][lx]

    def set_cell(self, wx: int, wy: int, type_id: int) -> bool:
        if not (0 <= wy < CHUNK_HEIGHT):
            return False
        cx, lx = wx // CHUNK_SIZE, wx % CHUNK_SIZE
        return self.get_chunk(cx).spawn(lx, wy, type_id)

    def set_cell_with_wetness(self, wx: int, wy: int, type_id: int, wetness: float) -> bool:
        if not (0 <= wy < CHUNK_HEIGHT):
            return False
        cx, lx = wx // CHUNK_SIZE, wx % CHUNK_SIZE
        chunk = self.get_chunk(cx)
        if chunk.spawn(lx, wy, type_id):
            chunk.wetness[wy][lx] = wetness
            return True
        return False

    def can_occupy_world(self, wx: int, wy: int, mover_id: int) -> bool:
        cx, lx = wx // CHUNK_SIZE, wx % CHUNK_SIZE
        if not (0 <= wy < CHUNK_HEIGHT):
            return False
        chunk = self.get_chunk(cx, create=False)
        if chunk is None:
            return True
        return chunk.can_occupy(lx, wy, mover_id)

    # ── cross-chunk movement ───────────────────────────────

    def add_cross_chunk_move(self, wx1, wy1, wx2, wy2):
        self._cross_moves.append((wx1, wy1, wx2, wy2))

    def add_diffusion_transfer(self, src_cx, src_cy, src_lx, src_ly,
                                dst_wx, dst_wy, src_w):
        self._diffusion_xfers.append((src_cx, src_cy, src_lx, src_ly, dst_wx, dst_wy, src_w))

    def _apply_cross_moves(self):
        for wx1, wy1, wx2, wy2 in self._cross_moves:
            cx1, lx1 = wx1 // CHUNK_SIZE, wx1 % CHUNK_SIZE
            cx2, lx2 = wx2 // CHUNK_SIZE, wx2 % CHUNK_SIZE
            chunk1 = self.get_chunk(cx1, create=False)
            if chunk1 is None or not (0 <= wy1 < CHUNK_HEIGHT):
                continue
            t1 = chunk1.grid[wy1][lx1]
            if t1 == EMPTY:
                continue
            chunk2 = self.get_chunk(cx2)
            if not (0 <= wy2 < CHUNK_HEIGHT):
                continue
            t2 = chunk2.grid[wy2][lx2]

            if t2 != EMPTY:
                m = chunk1.particle_types.get(t1)
                tt = chunk2.particle_types.get(t2)
                if not (m and tt and m["density"] > tt["density"]):
                    continue
                chunk2.grid[wy2][lx2] = t1
                chunk2.wetness[wy2][lx2] = chunk1.wetness[wy1][lx1]
                chunk2.asleep[wy2][lx2] = chunk1.asleep[wy1][lx1]
                chunk2.wake_frame[wy2][lx2] = chunk1.wake_frame[wy1][lx1]
                chunk2.water_charge[wy2][lx2] = chunk1.water_charge[wy1][lx1]
                chunk2.dirty.append((lx2, wy2))
                chunk2.updated[wy2][lx2] = chunk2.frame
                chunk1.grid[wy1][lx1] = t2
                chunk1.wetness[wy1][lx1] = chunk2.wetness[wy2][lx2]
                chunk1.dirty.append((lx1, wy1))
                chunk1.updated[wy1][lx1] = chunk1.frame
            else:
                chunk2.grid[wy2][lx2] = t1
                chunk2.wetness[wy2][lx2] = chunk1.wetness[wy1][lx1]
                chunk2.asleep[wy2][lx2] = chunk1.asleep[wy1][lx1]
                chunk2.wake_frame[wy2][lx2] = chunk1.wake_frame[wy1][lx1]
                chunk2.water_charge[wy2][lx2] = chunk1.water_charge[wy1][lx1]
                chunk2.dirty.append((lx2, wy2))
                chunk2.updated[wy2][lx2] = chunk2.frame
                chunk2.filled_count += 1
                chunk1.grid[wy1][lx1] = EMPTY
                chunk1.wetness[wy1][lx1] = 0.0
                chunk1.asleep[wy1][lx1] = 0
                chunk1.wake_frame[wy1][lx1] = 0
                chunk1.water_charge[wy1][lx1] = 0
                chunk1.dirty.append((lx1, wy1))
                chunk1.filled_count -= 1

        self._cross_moves.clear()
        self._diffusion_xfers.clear()

    # ── activation & stepping ──────────────────────────────

    def get_chunks_in_radius(self, center_wx: int, radius_chunks: int) -> list[int]:
        c_cx = center_wx // CHUNK_SIZE
        return [c_cx + dx for dx in range(-radius_chunks, radius_chunks + 1)]

    def step_active(self, center_wx: int, radius: int = 0):
        self.frame += 1
        stepped = set()
        for cx in self.get_chunks_in_radius(center_wx, radius):
            chunk = self.get_chunk(cx, create=False)
            if chunk is not None and chunk.filled_count > 0:
                chunk.step()
                stepped.add(cx)
        for wx1, wy1, wx2, wy2 in self._cross_moves:
            dst_cx = wx2 // CHUNK_SIZE
            if dst_cx not in stepped:
                chunk = self.get_chunk(dst_cx, create=False)
                if chunk is not None and chunk.filled_count > 0:
                    chunk.frame = self.frame
                    chunk.step()
                    stepped.add(dst_cx)
        self._apply_cross_moves()

    def evict_far(self, center_wx, max_chunks):
        """Disabled — chunks stay in memory for revisit."""
        pass

    # ── terrain generation ─────────────────────────────────

    def generate_terrain(self, cx: int):
        """Fill chunk at cx with full solid terrain, then carve worm tunnels."""
        chunk = self.get_chunk(cx)
        if chunk is None or chunk.filled_count > 0:
            return

        heights = [_height_at(cx * CHUNK_SIZE + lx, self.seed) for lx in range(CHUNK_SIZE)]

        for lx in range(CHUNK_SIZE):
            wx = cx * CHUNK_SIZE + lx
            h_val = heights[lx]

            sand_top = 90 - h_val
            sand_top = max(5, min(87, sand_top))

            for ly in range(sand_top, CHUNK_HEIGHT):
                h2 = hash((wx, ly, self.seed, 0xCAFE))
                h2 = (h2 * 0x9E3779B9) & 0xFFFFFFFF
                wet = (h2 % 6) / 2.0
                chunk.spawn(lx, ly, 1)
                if wet > 0:
                    chunk.wetness[ly][lx] = wet

            for ly in range(70, CHUNK_HEIGHT):
                if chunk.grid[ly][lx] == EMPTY:
                    chunk.spawn(lx, ly, 2)

        # ── worm tunnels (brush circle radius) ──
        rng = random.Random(cx * CHUNK_SIZE + self.seed + 42)
        n_tunnels = rng.randint(0, 3)
        for _ in range(n_tunnels):
            wx = cx * CHUNK_SIZE + rng.randint(8, CHUNK_SIZE - 8)
            wy = rng.randint(20, 65)
            if chunk.grid[wy][wx % CHUNK_SIZE] != 1:
                continue
            tunnel_len = rng.randint(30, 50)
            smooth_radius = rng.uniform(7, 9)
            radius_target = smooth_radius
            for step_i in range(tunnel_len):
                cx_local = wx % CHUNK_SIZE
                # Pick new target every few steps for organic variation
                if step_i % 4 == 0:
                    radius_target = rng.uniform(6, 12)
                smooth_radius += (radius_target - smooth_radius) * 0.12
                radius = max(4, min(13, int(smooth_radius + 0.5)))
                # Carve a circle of `radius` at this point
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        if dx * dx + dy * dy <= radius * radius:
                            lx = cx_local + dx
                            ly = wy + dy
                            if 0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_HEIGHT:
                                if chunk.grid[ly][lx] == 1:
                                    chunk.grid[ly][lx] = EMPTY
                                    chunk.wetness[ly][lx] = 0.0
                                    chunk.asleep[ly][lx] = 0
                                    chunk.wake_frame[ly][lx] = 0
                                    chunk.water_charge[ly][lx] = 0
                                    chunk.filled_count -= 1
                                    # Wet sand around carved cell for stability
                                    for ndx in (-1, 0, 1):
                                        for ndy in (-1, 0, 1):
                                            nlx, nly = lx + ndx, ly + ndy
                                            if 0 <= nlx < CHUNK_SIZE and 0 <= nly < CHUNK_HEIGHT:
                                                if chunk.grid[nly][nlx] == 1:
                                                    chunk.wetness[nly][nlx] = max(chunk.wetness[nly][nlx], 2.0)
                                                    chunk.asleep[nly][nlx] = 1
                                                    chunk.wake_frame[nly][nlx] = 0
                # Move rightward with vertical drift
                wx += rng.randint(1, 2)
                wy += rng.choice([-1, 0, 0, 0, 1])
                wy = max(15, min(75, wy))
                # Stop before leaving the chunk
                if wx >= (cx + 1) * CHUNK_SIZE - 4:
                    break



    def generate_around(self, center_wx: int, radius: int = 5):
        for cx in self.get_chunks_in_radius(center_wx, radius):
            chunk = self.get_chunk(cx, create=False)
            if chunk is None or chunk.filled_count == 0:
                self.generate_terrain(cx)
