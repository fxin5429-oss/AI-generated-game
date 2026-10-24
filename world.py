"""世界：关卡解析、瓦片物理、视差背景、地面渲染、机关。"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import pygame

import art
from levels import LevelDef
from settings import THEMES, TILE, VIEW_H, VIEW_W

TILE_SPRITE = {
    "#": "t_grass",
    ".": "t_dirt",
    "%": "t_stone",
    "B": "t_brick",
    "W": "t_wood",
    "C": "t_crate",
    "M": "t_metal",
    "=": "t_platform",
    "x": "t_metal",
    "~": "t_cloudblock",
    "L": "t_ladder",
    "T": "t_tree",
    "V": "t_crystal",
}

SOLID_CHARS = set("#.=%BWCMx~?")
HAZARD_CHARS = set("^V")
LADDER_CHARS = set("L")
DECOR_CHARS = set("T")

# 不同主题下部分方块换贴图，让关卡有区分度
THEME_SPRITE_OVERRIDE = {
    "cave": {"#": "t_stone", ".": "t_stone", "%": "t_stone", "B": "t_brick"},
    "night": {"#": "t_brick", ".": "t_brick", "%": "t_stone", "B": "t_wood"},
}


@dataclass
class MovingPlatform:
    """水平往返的移动平台。"""

    x: float
    y: float
    w: int
    dx: float = 42.0
    left: float = 0.0
    right: float = 0.0
    prev_x: float = 0.0

    def __post_init__(self) -> None:
        self.prev_x = self.x

    @property
    def h(self) -> int:
        return TILE

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(round(self.x)), int(round(self.y)), self.w, TILE)

    def update(self, dt: float) -> None:
        self.prev_x = self.x
        self.x += self.dx * dt
        if self.x <= self.left:
            self.x = self.left
            self.dx = abs(self.dx)
        elif self.x >= self.right:
            self.x = self.right
            self.dx = -abs(self.dx)


@dataclass
class Spring:
    tx: int
    ty: int
    sprite: str = "t_spring"
    compress: float = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.tx * TILE, self.ty * TILE, TILE, TILE)

    def launch(self) -> None:
        self.compress = 1.0

    def update(self, dt: float) -> None:
        if self.compress > 0:
            self.compress = max(0.0, self.compress - dt * 4.5)


@dataclass
class Background:
    """视差背景构件。"""

    theme: str
    seed: int

    sky: pygame.Surface | None = None
    stars: pygame.Surface | None = None
    haze: pygame.Surface | None = None
    clouds: list[tuple[float, float, pygame.Surface]] = field(default_factory=list)
    hills: list[tuple[float, float, pygame.Surface]] = field(default_factory=list)

    def build(self) -> None:
        rng = random.Random(self.seed)
        cfg = THEMES[self.theme]
        # 天空渐变：先生成 1 像素宽的竖条再横向放大，覆盖整屏
        strip = art.vertical_gradient(1, VIEW_H, cfg["sky"])
        self.sky = pygame.transform.scale(strip, (VIEW_W, VIEW_H)).convert()
        if cfg.get("star"):
            self.stars = art.starfield(VIEW_W, VIEW_H, rng).convert_alpha()

        # 地平线雾带：让远处的丘陵和天空融合，不会出现硬边
        self.haze = pygame.Surface((VIEW_W, 64), pygame.SRCALPHA)
        low = cfg["sky"][-1]
        for i in range(64):
            a = int(200 * (i / 63.0) ** 1.3)
            pygame.draw.line(self.haze, (low[0], low[1], low[2], a), (0, i), (VIEW_W, i))

        colors = cfg["hills"]
        tree = art.atlas().get("t_tree")
        if self.theme == "cave":
            self.hills.append((0.14, VIEW_H * 0.60, art.hill_layer(VIEW_W, 80, colors[1], rng, amplitude=30)))
            self.hills.append((0.28, VIEW_H * 0.74, art.hill_layer(VIEW_W, 90, colors[2], rng, amplitude=34)))
            return

        for _ in range(9):
            s = art.cloud_sprite(rng).convert_alpha()
            cx = rng.uniform(0, VIEW_W)
            cy = rng.uniform(6, VIEW_H * 0.40)
            self.clouds.append((cx, cy, s))

        self.hills.append((0.08, VIEW_H * 0.56, art.hill_layer(VIEW_W, 70, colors[0], rng, amplitude=24)))
        self.hills.append((0.18, VIEW_H * 0.68, art.hill_layer(VIEW_W, 80, colors[1], rng, amplitude=28)))
        self.hills.append((0.32, VIEW_H * 0.78, art.hill_layer(VIEW_W, 90, colors[2], rng, amplitude=30,
                                                             trees=6, tree_surf=tree)))

    def draw(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        assert self.sky is not None
        surf.blit(self.sky, (0, 0))

        if self.stars is not None:
            oy = -int(cam_y * 0.05)
            off = int(cam_x * 0.03) % VIEW_W
            surf.blit(self.stars, (-off, oy))
            if off:
                surf.blit(self.stars, (VIEW_W - off, oy))

        for cx, cy, s in self.clouds:
            ox = (cx - cam_x * 0.06) % (VIEW_W + 80) - 40
            oy = cy - cam_y * 0.08
            surf.blit(s, (int(ox), int(oy)))

        # 丘陵：横向平铺并再复制一份，保证任何镜头位置都铺满整屏
        for factor, base_y, layer in self.hills:
            lw = layer.get_width()
            off = int(cam_x * factor) % lw
            oy = int(base_y - cam_y * factor * 0.35)
            x = -off
            while x < VIEW_W:
                surf.blit(layer, (x, oy))
                x += lw

        if self.haze is not None:
            assert self.sky is not None
            top = int(VIEW_H * 0.52)
            surf.blit(self.haze, (0, top))


class World:
    def __init__(self, level: LevelDef, seed: int = 0) -> None:
        self.level = level
        self.rows = level.rows
        self.h = len(self.rows)
        self.w = max(len(r) for r in self.rows)
        self.width = self.w * TILE
        self.height = self.h * TILE
        self.theme = level.theme
        self.override = THEME_SPRITE_OVERRIDE.get(self.theme, {})

        self.tiles: dict[tuple[int, int], str] = {}
        self.spawn_tile: tuple[int, int] = (1, 1)
        self.goal_tile: tuple[int, int] | None = None
        self.item_spawns: list[tuple[str, int, int]] = []
        self.enemy_spawns: list[tuple[str, int, int]] = []
        self.springs: list[Spring] = []
        self.moving: list[MovingPlatform] = []
        self.bump: dict[tuple[int, int], float] = {}
        self._parse()

        self.background = Background(self.theme, seed=seed if seed else 1234 + self.w)
        self.background.build()

        self._cache: dict[str, pygame.Surface] = {}
        self._build_tile_cache()

    # -- 解析 ------------------------------------------------------------
    def _parse(self) -> None:
        for y, row in enumerate(self.rows):
            for x, ch in enumerate(row):
                if ch == " ":
                    continue
                if ch == "P":
                    self.spawn_tile = (x, y)
                    continue
                if ch == "G":
                    self.goal_tile = (x, y)
                    continue
                if ch in SOLID_CHARS or ch in HAZARD_CHARS or ch in LADDER_CHARS or ch in DECOR_CHARS:
                    self.tiles[(x, y)] = ch
                    continue
                if ch == "j":
                    self.springs.append(Spring(x, y))
                    continue
                if ch in ("o", "*", "h"):
                    self.item_spawns.append((ch, x, y))
                    continue
                if ch in ("s", "b", "w"):
                    self.enemy_spawns.append((ch, x, y))
                    continue
                raise ValueError(f"关卡「{self.level.name}」第 {y} 行第 {x} 列有未知字符 {ch!r}")

        self._build_moving_platforms()

    def _build_moving_platforms(self) -> None:
        """把由 = 组成的连续段变成移动平台。"""
        by_row: dict[int, list[int]] = {}
        for (x, y), ch in self.tiles.items():
            if ch == "=":
                by_row.setdefault(y, []).append(x)

        for y, xs in by_row.items():
            xs.sort()
            run: list[int] = []
            for x in xs:
                if run and x == run[-1] + 1:
                    run.append(x)
                else:
                    if len(run) >= 2:
                        self._make_platform(run, y)
                    elif run:
                        self.tiles[(run[0], y)] = "x"
                    run = [x]
            if len(run) >= 2:
                self._make_platform(run, y)
            elif run:
                self.tiles[(run[0], y)] = "x"

    def _make_platform(self, xs: list[int], y: int) -> None:
        x0, x1 = min(xs), max(xs)
        w = (x1 - x0 + 1) * TILE
        span = 3 * TILE
        for x in xs:
            self.tiles.pop((x, y), None)
        left = max(0.0, x0 * TILE - span)
        right = min(self.width - w, x1 * TILE + span)
        if right <= left:
            left = right = x0 * TILE
        self.moving.append(MovingPlatform(x=x0 * TILE, y=y * TILE, w=w, dx=42.0,
                                         left=left, right=right))

    # -- 瓦片查询 --------------------------------------------------------
    def in_bounds(self, tx: int, ty: int) -> bool:
        return 0 <= tx < self.w and 0 <= ty < self.h

    def tile_at(self, tx: int, ty: int) -> str:
        if tx < 0 or tx >= self.w:
            return "#"          # 左右边界当作墙
        if ty < 0 or ty >= self.h:
            return " "          # 上方开放，下方是深渊
        return self.tiles.get((tx, ty), " ")

    def is_solid(self, tx: int, ty: int) -> bool:
        return self.tile_at(tx, ty) in SOLID_CHARS

    def is_hazard(self, tx: int, ty: int) -> bool:
        return self.tile_at(tx, ty) in HAZARD_CHARS

    def is_ladder(self, tx: int, ty: int) -> bool:
        return self.tile_at(tx, ty) in LADDER_CHARS

    def solid_at_rect(self, rect: pygame.Rect) -> bool:
        x0, x1 = rect.left // TILE, (rect.right - 1) // TILE
        y0, y1 = rect.top // TILE, (rect.bottom - 1) // TILE
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                if self.is_solid(tx, ty):
                    return True
        return False

    def hazards_touching(self, rect: pygame.Rect) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        x0, x1 = rect.left // TILE, (rect.right - 1) // TILE
        y0, y1 = rect.top // TILE, (rect.bottom - 1) // TILE
        for ty in range(max(0, y0), min(self.h - 1, y1) + 1):
            for tx in range(max(0, x0), min(self.w - 1, x1) + 1):
                if self.is_hazard(tx, ty):
                    out.append((tx, ty))
        return out

    def ladder_overlapping(self, rect: pygame.Rect) -> bool:
        x0, x1 = rect.left // TILE, (rect.right - 1) // TILE
        y0, y1 = rect.top // TILE, (rect.bottom - 1) // TILE
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                if self.is_ladder(tx, ty):
                    return True
        return False

    def ground_below(self, rect: pygame.Rect, max_tiles: int = 6) -> bool:
        tx0, tx1 = rect.left // TILE, (rect.right - 1) // TILE
        ty = (rect.bottom - 1) // TILE
        for k in range(1, max_tiles + 1):
            for tx in range(tx0, tx1 + 1):
                if self.is_solid(tx, ty + k):
                    return True
        return False

    def wall_ahead(self, rect: pygame.Rect, direction: int) -> bool:
        tx = (rect.right if direction > 0 else rect.left - 1) // TILE
        ty0, ty1 = rect.top // TILE, (rect.bottom - 1) // TILE
        return any(self.is_solid(tx, ty) for ty in range(ty0, ty1 + 1))

    def hazard_tiles_near(self, x: int, y: int, radius: int = 2) -> int:
        n = 0
        for ty in range(y - radius, y + radius + 1):
            for tx in range(x - radius, x + radius + 1):
                if self.is_hazard(tx, ty):
                    n += 1
        return n

    # -- 机关 ------------------------------------------------------------
    def bump_tile(self, tx: int, ty: int) -> str | None:
        """从下面顶到砖块。返回 'coin' 表示这是金币砖。"""
        ch = self.tile_at(tx, ty)
        if ch == "?":
            self.tiles[(tx, ty)] = "x"
            self.bump[(tx, ty)] = 1.0
            return "coin"
        if ch in SOLID_CHARS:
            self.bump[(tx, ty)] = 0.5
        return None

    def spring_at(self, rect: pygame.Rect) -> Spring | None:
        for s in self.springs:
            if rect.colliderect(s.rect):
                return s
        return None

    def update(self, dt: float) -> None:
        for p in self.moving:
            p.update(dt)
        for s in self.springs:
            s.update(dt)
        for k in list(self.bump.keys()):
            self.bump[k] -= dt * 5.5
            if self.bump[k] <= 0:
                del self.bump[k]

    # -- 贴图缓存 --------------------------------------------------------
    def _build_tile_cache(self) -> None:
        atlas = art.atlas()
        for ch, sprite in TILE_SPRITE.items():
            name = self.override.get(ch, sprite)
            self._cache[ch] = atlas.get(name)
        self._cache["^"] = atlas.get("t_spike")
        self._cache["?"] = atlas.get("t_metal")
        self._cache["x"] = atlas.get("t_metal")
        self._cache["j"] = atlas.get("t_spring")
        self._cache["T"] = atlas.get("t_tree")
        self._cache["door"] = atlas.get("t_door")
        self._cache["spark"] = atlas.get("i_spark")

    def tile_surface(self, ch: str) -> pygame.Surface:
        return self._cache.get(ch, self._cache["%"])

    def _coin_block_frame(self) -> pygame.Surface:
        img = self._cache["?"].copy()
        t = pygame.time.get_ticks()
        pulse = int((math.sin(t / 180.0) * 0.5 + 0.5) * 3)
        dot = pygame.Surface((6 + pulse, 2), pygame.SRCALPHA)
        dot.fill((250, 206, 92, 230))
        img.blit(dot, (5 - pulse // 2, 7))
        return img

    # -- 渲染 ------------------------------------------------------------
    def draw_background(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        self.background.draw(surf, cam_x, cam_y)

    def draw_tiles(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        icx, icy = int(cam_x), int(cam_y)
        tx0 = max(0, icx // TILE - 1)
        tx1 = min(self.w - 1, (icx + VIEW_W) // TILE + 1)
        ty0 = max(0, icy // TILE - 1)
        ty1 = min(self.h - 1, (icy + VIEW_H) // TILE + 2)

        coin_img: pygame.Surface | None = None
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                ch = self.tiles.get((tx, ty))
                if ch is None or ch == "T":
                    continue
                if ch == "?":
                    if coin_img is None:
                        coin_img = self._coin_block_frame()
                    surf.blit(coin_img, (tx * TILE - icx, ty * TILE - icy))
                    continue
                img = self.tile_surface(ch)
                sx = tx * TILE - icx
                sy = ty * TILE - icy
                anim = self.bump.get((tx, ty))
                if anim:
                    dev = int(math.sin(min(1.0, anim) * math.pi) * 4.0)
                    surf.blit(img, (sx, sy + dev))
                else:
                    surf.blit(img, (sx, sy))

        # 装饰
        for (tx, ty), ch in self.tiles.items():
            if ch != "T":
                continue
            sx = tx * TILE - icx
            sy = ty * TILE - icy
            if -TILE <= sx <= VIEW_W and -TILE <= sy <= VIEW_H:
                surf.blit(art.atlas().get("t_tree" if self.theme != "cave" else "t_torch"), (sx, sy))

        # 弹簧
        for s in self.springs:
            sx = s.tx * TILE - icx
            sy = s.ty * TILE - icy
            if not (-TILE <= sx <= VIEW_W and -TILE <= sy <= VIEW_H):
                continue
            img = self._cache["j"]
            c = int(s.compress * 3)
            if c:
                img = pygame.transform.scale(img, (TILE, max(4, TILE - c)))
                surf.blit(img, (sx, sy + c))
            else:
                surf.blit(img, (sx, sy))

        # 移动平台
        for p in self.moving:
            r = p.rect
            sx = r.x - icx
            sy = r.y - icy
            if not (-r.w <= sx <= VIEW_W and -TILE <= sy <= VIEW_H):
                continue
            img = art.atlas().get("t_platform" if self.theme == "night" else "t_metal")
            for ox in range(0, r.w, TILE):
                surf.blit(img, (sx + ox, sy))

        # 终点门
        if self.goal_tile:
            gx, gy = self.goal_tile
            door = self._cache["door"]
            sx = gx * TILE - icx
            sy = (gy - 1) * TILE - icy
            glow = math.sin(pygame.time.get_ticks() / 260.0) * 0.5 + 0.5
            halo = pygame.Surface((TILE * 3, TILE * 4), pygame.SRCALPHA)
            pygame.draw.circle(halo, (250, 220, 140, int(26 + 26 * glow)),
                               (TILE * 3 // 2, TILE * 2), int(TILE * 1.1))
            surf.blit(halo, (sx - TILE, sy - TILE))
            surf.blit(door, (sx, sy))
            surf.blit(door, (sx, sy + TILE))
            if int(pygame.time.get_ticks() / 300) % 2 == 0:
                surf.blit(self._cache["spark"], (sx + 2, sy - 10))

    def draw_foreground(self, surf: pygame.Surface, cam_x: float, cam_y: float) -> None:
        """洞窟主题加一层顶部阴影，营造封闭感。"""
        if self.theme != "cave":
            return
        if not hasattr(self, "_shade"):
            shade = pygame.Surface((VIEW_W, 46), pygame.SRCALPHA)
            for i in range(46):
                a = int(150 * (1 - i / 46.0) ** 1.6)
                pygame.draw.line(shade, (8, 6, 16, a), (0, i), (VIEW_W, i))
            self._shade = shade
        surf.blit(self._shade, (0, 0))

    def goal_rect(self) -> pygame.Rect | None:
        if not self.goal_tile:
            return None
        gx, gy = self.goal_tile
        return pygame.Rect(gx * TILE, (gy - 1) * TILE, TILE, TILE * 2)

    def spawn_pos(self) -> tuple[float, float]:
        """出生点：瓦片底部中心（配合 Player 的 midbottom 定位）。"""
        tx, ty = self.spawn_tile
        return tx * TILE + TILE / 2.0, (ty + 1) * TILE
