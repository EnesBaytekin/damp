"""
ChunkManager — owns all Chunks, handles cross-chunk movement,
activation radius, and terrain generation.
"""

import random
from scripts.Chunk import Chunk, CHUNK_SIZE, EMPTY


class ChunkManager:
    """Dict of chunks + cross-chunk movement buffers."""

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.chunks: dict[tuple[int, int], Chunk] = {}
        self.rng = random.Random(seed)
        self.frame = 0

        # Cross-chunk movement buffer: list of (src_wx, src_wy, dst_wx, dst_wy)
        self._cross_moves: list[tuple[int, int, int, int]] = []
        # Diffusion transfers: list of (dst_wx, dst_wy, amount)
        self._diffusion_xfers: list[tuple[int, int, float]] = []

    # ── chunk access ───────────────────────────────────────

    def get_chunk(self, cx: int, cy: int, create: bool = True) -> Chunk | None:
        key = (cx, cy)
        if key not in self.chunks and create:
            c = Chunk(cx, cy, manager=self)
            c.particle_types = self._particle_types() if hasattr(self, '_ptypes') else {}
            self.chunks[key] = c
            return c
        return self.chunks.get(key)

    def _particle_types(self):
        return getattr(self, '_ptypes', {})

    def set_particle_types(self, types: dict):
        self._ptypes = types
        for chunk in self.chunks.values():
            chunk.particle_types = types

    def register(self, type_id: int, props: dict):
        if not hasattr(self, '_ptypes') or not self._ptypes:
            self._ptypes = {}
        self._ptypes[type_id] = props
        for chunk in self.chunks.values():
            chunk.particle_types = self._ptypes

    # ── world-level cell access ────────────────────────────

    def get_cell(self, wx: int, wy: int) -> int:
        cx, cy, lx, ly = self._world_to_local(wx, wy)
        chunk = self.get_chunk(cx, cy, create=False)
        if chunk is None:
            return EMPTY
        return chunk.grid[ly][lx]

    def get_wetness(self, wx: int, wy: int) -> float:
        cx, cy, lx, ly = self._world_to_local(wx, wy)
        chunk = self.get_chunk(cx, cy, create=False)
        if chunk is None:
            return 0.0
        return chunk.wetness[ly][lx]

    def set_cell(self, wx: int, wy: int, type_id: int) -> bool:
        cx, cy, lx, ly = self._world_to_local(wx, wy)
        chunk = self.get_chunk(cx, cy)
        if chunk.spawn(lx, ly, type_id):
            return True
        return False

    def set_cell_with_wetness(self, wx: int, wy: int, type_id: int, wetness: float) -> bool:
        cx, cy, lx, ly = self._world_to_local(wx, wy)
        chunk = self.get_chunk(cx, cy)
        if chunk.spawn(lx, ly, type_id):
            chunk.wetness[ly][lx] = wetness
            return True
        return False

    def can_occupy_world(self, wx: int, wy: int, mover_id: int) -> bool:
        cx, cy, lx, ly = self._world_to_local(wx, wy)
        chunk = self.get_chunk(cx, cy, create=False)
        if chunk is None:
            return True  # ungenerated = empty = always occupy
        return chunk.can_occupy(lx, ly, mover_id)

    # ── cross-chunk movement ───────────────────────────────

    def add_cross_chunk_move(self, wx1: int, wy1: int, wx2: int, wy2: int):
        self._cross_moves.append((wx1, wy1, wx2, wy2))

    def add_diffusion_transfer(self, src_cx: int, src_cy: int, src_lx: int, src_ly: int,
                                dst_wx: int, dst_wy: int, src_w: float):
        self._diffusion_xfers.append((src_cx, src_cy, src_lx, src_ly, dst_wx, dst_wy, src_w))

    def _apply_cross_moves(self):
        """Apply buffered cross-chunk moves after all chunks have stepped."""
        for wx1, wy1, wx2, wy2 in self._cross_moves:
            # Source chunk
            cx1, cy1, lx1, ly1 = self._world_to_local(wx1, wy1)
            chunk1 = self.get_chunk(cx1, cy1, create=False)
            if chunk1 is None:
                continue

            # Target chunk
            cx2, cy2, lx2, ly2 = self._world_to_local(wx2, wy2)
            chunk2 = self.get_chunk(cx2, cy2)

            # Read source state
            t1 = chunk1.grid[ly1][lx1]
            if t1 == EMPTY:
                continue
            w1 = chunk1.wetness[ly1][lx1]
            a1 = chunk1.asleep[ly1][lx1]
            wf1 = chunk1.wake_frame[ly1][lx1]
            c1 = chunk1.water_charge[ly1][lx1]

            # Read target state
            t2 = chunk2.grid[ly2][lx2]
            if t2 != EMPTY:
                # Check density
                mover = chunk1.particle_types.get(t1)
                target_t = chunk2.particle_types.get(t2)
                if not (mover and target_t and mover["density"] > target_t["density"]):
                    continue
                # Swap: move target back to source
                chunk2.grid[ly2][lx2] = t1
                chunk2.wetness[ly2][lx2] = w1
                chunk2.asleep[ly2][lx2] = a1
                chunk2.wake_frame[ly2][lx2] = wf1
                chunk2.water_charge[ly2][lx2] = c1
                chunk2.dirty.append((lx2, ly2))
                chunk2.updated[ly2][lx2] = chunk2.frame

                chunk1.grid[ly1][lx1] = t2
                chunk1.wetness[ly1][lx1] = chunk2.wetness[ly2][lx2]  # already swapped above
                chunk1.dirty.append((lx1, ly1))
                chunk1.updated[ly1][lx1] = chunk1.frame
            else:
                # Simple move
                chunk2.grid[ly2][lx2] = t1
                chunk2.wetness[ly2][lx2] = w1
                chunk2.asleep[ly2][lx2] = a1
                chunk2.wake_frame[ly2][lx2] = wf1
                chunk2.water_charge[ly2][lx2] = c1
                chunk2.dirty.append((lx2, ly2))
                chunk2.updated[ly2][lx2] = chunk2.frame
                chunk2.filled_count += 1

                # Clear source
                chunk1.grid[ly1][lx1] = EMPTY
                chunk1.wetness[ly1][lx1] = 0.0
                chunk1.asleep[ly1][lx1] = 0
                chunk1.wake_frame[ly1][lx1] = 0
                chunk1.water_charge[ly1][lx1] = 0
                chunk1.dirty.append((lx1, ly1))
                chunk1.filled_count -= 1

        self._cross_moves.clear()

        # Apply diffusion transfers
        for src_cx, src_cy, src_lx, src_ly, dst_wx, dst_wy, src_w in self._diffusion_xfers:
            chunk1 = self.get_chunk(src_cx, src_cy, create=False)
            if chunk1 is None:
                continue
            cx2, cy2, lx2, ly2 = self._world_to_local(dst_wx, dst_wy)
            chunk2 = self.get_chunk(cx2, cy2)
            if chunk2.grid[ly2][lx2] != 1:
                continue
            nw = chunk2.wetness[ly2][lx2]
            if not (src_w - nw >= 1.0):
                continue
            chunk1.wetness[src_ly][src_lx] -= 0.5
            chunk2.wetness[ly2][lx2] += 0.5
            chunk1.dirty.append((src_lx, src_ly))
            chunk2.dirty.append((lx2, ly2))

        self._diffusion_xfers.clear()

    # ── coordinate helpers ─────────────────────────────────

    @staticmethod
    def _world_to_local(wx: int, wy: int) -> tuple[int, int, int, int]:
        return wx // CHUNK_SIZE, wy // CHUNK_SIZE, wx % CHUNK_SIZE, wy % CHUNK_SIZE

    # ── activation & stepping ──────────────────────────────

    def get_chunks_in_radius(self, center_wx: int, center_wy: int, radius_chunks: int) -> list[tuple[int, int]]:
        """Return list of (cx, cy) for chunks within radius of world position."""
        c_cx = center_wx // CHUNK_SIZE
        c_cy = center_wy // CHUNK_SIZE
        result = []
        for dy in range(-radius_chunks, radius_chunks + 1):
            for dx in range(-radius_chunks, radius_chunks + 1):
                if dx * dx + dy * dy <= radius_chunks * radius_chunks:
                    result.append((c_cx + dx, c_cy + dy))
        return result

    def step_active(self, center_wx: int, center_wy: int, radius: int = 6):
        """Step all chunks within *radius* chunks of the player."""
        self.frame += 1
        keys = self.get_chunks_in_radius(center_wx, center_wy, radius)

        # Step each active chunk
        for cx, cy in keys:
            chunk = self.get_chunk(cx, cy, create=False)
            if chunk is not None and chunk.filled_count > 0:
                chunk.step()

        # Apply cross-chunk changes
        self._apply_cross_moves()

    # ── terrain generation ─────────────────────────────────

    def generate_terrain(self, cx: int, cy: int):
        """Fill a chunk with procedural terrain (simple for now)."""
        chunk = self.get_chunk(cx, cy)
        if chunk is None or chunk.filled_count > 0:
            return

        seed = self.seed + cx * 1000 + cy * 777
        rng = random.Random(seed)

        for ly in range(CHUNK_SIZE):
            for lx in range(CHUNK_SIZE):
                wx = cx * CHUNK_SIZE + lx
                wy = cy * CHUNK_SIZE + ly

                # Simple height-based terrain using nested random
                height_val = rng.random() * 2 - 1  # -1..1

                # Use position-based deterministic pseudo-noise
                h = ((wx * 13 + wy * 71) * (seed & 0xFFFF)) & 0x7FFF
                noise_val = (h / 8192.0) - 1.0  # approx -1..1

                val = (noise_val + height_val * 0.3) / 1.3

                if val < -0.15:
                    # Water
                    chunk.spawn(lx, ly, 2)
                elif val < 0.0:
                    # Wet sand (beach)
                    chunk.spawn(lx, ly, 1)
                    chunk.wetness[ly][lx] = 2.0
                elif val < 0.4:
                    # Sand (dry)
                    chunk.spawn(lx, ly, 1)
                else:
                    # Higher ground — sand
                    chunk.spawn(lx, ly, 1)

    def generate_around(self, center_wx: int, center_wy: int, radius: int = 8):
        """Ensure terrain is generated for all chunks within *radius*."""
        keys = self.get_chunks_in_radius(center_wx, center_wy, radius)
        for cx, cy in keys:
            chunk = self.get_chunk(cx, cy, create=False)
            if chunk is None or chunk.filled_count == 0:
                self.generate_terrain(cx, cy)
