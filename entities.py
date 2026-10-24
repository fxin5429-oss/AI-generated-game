"""实体：玩家、敌人、收集品、粒子效果。"""
from __future__ import annotations

import math
import random

import pygame

import settings as S
from settings import TILE

# --------------------------------------------------------------------------
# 通用物理工具
# --------------------------------------------------------------------------
_BBOX_CACHE: dict[int, pygame.Rect] = {}


def sprite_bbox(surf: pygame.Surface) -> pygame.Rect:
    """贴图里非透明像素的包围盒（带缓存）。"""
    key = id(surf)
    b = _BBOX_CACHE.get(key)
    if b is None or b.width == 0:
        b = surf.get_bounding_rect()
        if key not in _BBOX_CACHE or b.width:
            _BBOX_CACHE[key] = b
    return b


def anchored_blit(
    target: pygame.Surface,
    img: pygame.Surface,
    hitbox: pygame.Rect,
    cam_x: int,
    cam_y: int,
    flip: bool = False,
    offset: tuple[int, int] = (0, 0),
) -> None:
    """把贴图按其可见像素对齐到碰撞盒：水平居中、脚底贴地。"""
    b = sprite_bbox(img)
    if b.width == 0 or b.height == 0:
        return
    if flip:
        img = pygame.transform.flip(img, True, False)
        b.x = img.get_width() - b.x - b.width
    hx = hitbox.centerx - b.centerx + offset[0] - cam_x
    hy = hitbox.bottom - b.bottom + offset[1] - cam_y
    target.blit(img, (hx, hy))


def move_and_collide(
    pos: pygame.Vector2,
    vel: pygame.Vector2,
    rect: pygame.Rect,
    world,
    dt: float,
    on_land=None,
    on_head=None,
) -> tuple[bool, bool]:
    """逐轴推进并解决瓦片碰撞。返回 (是否落地, 是否撞头)。"""
    landed = False
    bumped = False

    # --- 水平 ---
    dx = vel.x * dt
    if dx:
        rect.x += int(round(dx))
        if world.solid_at_rect(rect):
            step = 1 if dx > 0 else -1
            guard = 0
            while world.solid_at_rect(rect) and guard < 64:
                rect.x -= step
                guard += 1
            vel.x = 0.0

    # --- 垂直 ---
    dy = vel.y * dt
    if dy:
        rect.y += int(round(dy))
        if world.solid_at_rect(rect):
            step = 1 if dy > 0 else -1
            guard = 0
            while world.solid_at_rect(rect) and guard < 64:
                rect.y -= step
                guard += 1
            if dy > 0:
                landed = True
                if on_land:
                    on_land()
            else:
                bumped = True
                if on_head:
                    on_head(rect)
            vel.y = 0.0

    pos.x, pos.y = float(rect.x), float(rect.y)
    return landed, bumped


# --------------------------------------------------------------------------
# 粒子 / 飘字
# --------------------------------------------------------------------------
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size", "gravity")

    def __init__(self, x, y, vx, vy, life, color, size=2, gravity=280.0):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.gravity = gravity

    def update(self, dt: float) -> bool:
        self.life -= dt
        self.vy += self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        return self.life > 0

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int) -> None:
        a = max(0.0, min(1.0, self.life / self.max_life))
        s = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        s.fill((self.color[0], self.color[1], self.color[2], int(255 * a)))
        surf.blit(s, (int(self.x) - cam_x, int(self.y) - cam_y))


class Popup:
    """飘起来的小数字 / 文字。"""

    __slots__ = ("x", "y", "text", "life", "color", "max_life")

    def __init__(self, x, y, text, color=(250, 226, 140), life=0.9):
        self.x, self.y = x, y
        self.text = text
        self.life = life
        self.max_life = life
        self.color = color

    def update(self, dt: float) -> bool:
        self.life -= dt
        self.y -= 22 * dt
        return self.life > 0

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int, font) -> None:
        a = max(0.0, min(1.0, self.life / self.max_life))
        img = font.render(self.text, False, self.color)
        img = img.convert_alpha()
        img.set_alpha(int(255 * a))
        surf.blit(img, (int(self.x) - cam_x - img.get_width() // 2, int(self.y) - cam_y))


class PoppedCoin:
    """从金币砖里蹦出来的金币动画。"""

    def __init__(self, x: float, y: float) -> None:
        self.x, self.y = x, y
        self.vy = -172.0
        self.life = 0.55
        self.frame = 0

    def update(self, dt: float) -> bool:
        self.vy += 620 * dt
        self.y += self.vy * dt
        self.life -= dt
        return self.life > 0

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int, atlas) -> None:
        name = f"i_coin{int(pygame.time.get_ticks() / 70) % 4}"
        img = atlas.get(name)
        surf.blit(img, (int(self.x) - cam_x, int(self.y) - cam_y))


# --------------------------------------------------------------------------
# 玩家
# --------------------------------------------------------------------------
class Player:
    def __init__(self, x: float, y: float, world) -> None:
        self.world = world
        rect = pygame.Rect(0, 0, S.PLAYER_W, S.PLAYER_H)
        rect.midbottom = (int(x), int(y))
        self.rect = rect
        self.pos = pygame.Vector2(rect.x, rect.y)
        self.vel = pygame.Vector2(0.0, 0.0)

        self.facing = 1
        self.on_ground = False
        self.coyote = 0.0
        self.jump_buffer = 0.0
        self.jumps_left = S.MAX_JUMPS
        self.jump_held = False
        self.invuln = 0.0
        self.hp = S.PLAYER_MAX_HP
        self.alive = True
        self.death_cause = ""

        self.coins = 0
        self.gems = 0
        self.anim_time = 0.0
        self.squash = 1.0          # 1 = 正常
        self.squash_target = 1.0
        self.was_airborne = False
        self.land_impact = 0.0

        self.events: list[tuple[str, object]] = []   # 每帧产生的事件，供游戏逻辑消费
        self._move_intent = 0.0

    # -- 输入接口 --------------------------------------------------------
    def set_move_intent(self, direction: float) -> None:
        self._move_intent = max(-1.0, min(1.0, direction))

    def want_jump(self) -> None:
        self.jump_buffer = S.JUMP_BUFFER

    def set_jump_held(self, held: bool) -> None:
        self.jump_held = held

    # -- 主更新 ----------------------------------------------------------
    def update(self, dt: float) -> None:
        if not self.alive:
            self.vel.y = min(S.MAX_FALL, self.vel.y + S.GRAVITY * dt)
            self.rect.y += int(round(self.vel.y * dt))
            self.pos.update(self.rect.x, self.rect.y)
            return

        self.anim_time += dt
        if self.invuln > 0:
            self.invuln = max(0.0, self.invuln - dt)

        # 水平移动
        want = self._move_intent
        accel = S.PLAYER_ACCEL if self.on_ground else S.PLAYER_AIR_ACCEL
        if want != 0:
            self.vel.x = _approach(self.vel.x, want * S.PLAYER_RUN_SPEED, accel * dt)
            self.facing = 1 if want > 0 else -1
        elif self.on_ground:
            self.vel.x = _approach(self.vel.x, 0.0, S.PLAYER_FRICTION * dt)

        was_on_ground = self.on_ground

        # 重力
        self.vel.y = min(S.MAX_FALL, self.vel.y + S.GRAVITY * dt)
        if self.vel.y < 0 and not self.jump_held:
            self.vel.y *= S.JUMP_CUT_MULT

        # 跳跃缓冲
        if self.jump_buffer > 0:
            self.jump_buffer = max(0.0, self.jump_buffer - dt)

        # 移动平台承载
        carrier = self._find_carrier()
        if carrier is not None:
            self.rect.x += int(round(carrier.x - carrier.prev_x))

        landed, bumped = move_and_collide(self.pos, self.vel, self.rect, self.world, dt,
                                          on_head=self._hit_head)
        # 垂直位移不足 1 像素时不会触发碰撞回调，所以额外用探针确认脚下是否有地。
        # grounded 表示「这一帧确实站在地上」，用来替代裸的 landed。
        grounded = landed or self._ground_probe()
        if grounded:
            # 贴紧地面，避免悬空 1 像素导致动画抖动
            probe = pygame.Rect(self.rect.x, self.rect.bottom, self.rect.width, 1)
            if not self.world.solid_at_rect(probe):
                for _ in range(4):
                    self.rect.y += 1
                    self.pos.y = float(self.rect.y)
                    if self.world.solid_at_rect(probe):
                        self.rect.y -= 1
                        self.pos.y = float(self.rect.y)
                        break
            self.vel.y = 0.0

        self.on_ground = grounded
        if grounded and not was_on_ground:
            self.land_impact = 1.0
            self.squash = 0.78
            self.squash_target = 1.0
            self.events.append(("land", None))
        if grounded:
            self.jumps_left = S.MAX_JUMPS
            self.coyote = S.COYOTE_TIME
        else:
            self.coyote = max(0.0, self.coyote - dt)
            if was_on_ground:
                self.events.append(("leave_ground", None))

        # 起跳判定（用 grounded 而不是本帧新算出的 on_ground）
        if self.jump_buffer > 0 and (grounded or self.coyote > 0 or self.jumps_left > 0):
            if grounded or self.coyote > 0:
                self.vel.y = S.PLAYER_JUMP_VELOCITY
                self.jumps_left = S.MAX_JUMPS - 1
                self.events.append(("jump", None))
            else:
                self.vel.y = S.PLAYER_JUMP_VELOCITY * 0.92
                self.jumps_left -= 1
                self.events.append(("double_jump", None))
            self.jump_buffer = 0.0
            self.coyote = 0.0
            self.squash = 1.22
            self.squash_target = 1.0

        # 弹簧
        spring = self.world.spring_at(self.rect)
        if spring is not None:
            self.vel.y = S.SPRING_VELOCITY
            self.jumps_left = S.MAX_JUMPS
            spring.launch()
            self.events.append(("spring", (spring.tx, spring.ty)))
            self.squash = 1.3
            self.squash_target = 1.0

        # 地形伤害
        if self.invuln <= 0:
            hits = self.world.hazards_touching(self.rect)
            if hits:
                n = sum(1 for tx, ty in hits
                        if self.rect.colliderect(pygame.Rect(tx * TILE, ty * TILE, TILE, TILE)))
                if n:
                    self.events.append(("hazard", hits[0]))

        # 挤压恢复
        self.squash += (self.squash_target - self.squash) * min(1.0, dt * S.SQUASH_RECOVER)
        self.land_impact = max(0.0, self.land_impact - dt * 3.0)

        # 掉出地图
        if self.rect.top > self.world.height + 80:
            self.events.append(("fall_out", None))

    # -- 受伤 / 死亡 -----------------------------------------------------
    def hurt(self, direction: int = 0, knock: bool = True) -> bool:
        if self.invuln > 0 or not self.alive:
            return False
        self.hp -= S.HAZARD_DAMAGE
        self.invuln = S.INVULN_TIME
        if knock:
            self.vel.x = S.KNOCKBACK_X * direction
            self.vel.y = S.KNOCKBACK_Y
        self.squash = 0.8
        self.events.append(("hurt", None))
        if self.hp <= 0:
            self.die("hp")
        return True

    def die(self, cause: str) -> None:
        if not self.alive:
            return
        self.alive = False
        self.death_cause = cause
        self.vel.y = -190.0
        self.vel.x = 0.0
        self.events.append(("die", cause))

    # -- 内部 ------------------------------------------------------------
    def _ground_probe(self) -> bool:
        """脚下 1 像素内是否有实心地面。"""
        probe = pygame.Rect(self.rect.x, self.rect.bottom, self.rect.width, 1)
        if self.world.solid_at_rect(probe):
            return True
        foot = pygame.Rect(self.rect.x, self.rect.bottom, self.rect.width, 2)
        for p in self.world.moving:
            if foot.colliderect(p.rect):
                return True
        return False

    def _find_carrier(self):
        if self.vel.y < 0:
            return None
        foot = pygame.Rect(self.rect.x, self.rect.bottom, self.rect.width, 3)
        for p in self.world.moving:
            if foot.colliderect(p.rect):
                return p
        return None

    def _hit_head(self, rect: pygame.Rect) -> None:
        """头撞到砖块：找出被顶的那一格并触发弹跳。"""
        if self.vel.y >= 0:
            return
        ty = rect.top // TILE
        cx0 = rect.left // TILE
        cx1 = (rect.right - 1) // TILE
        best = None
        for tx in range(cx0, cx1 + 1):
            if self.world.is_solid(tx, ty):
                if best is None or abs(tx * TILE + TILE / 2 - rect.centerx) < \
                        abs(best * TILE + TILE / 2 - rect.centerx):
                    best = tx
        if best is not None:
            kind = self.world.bump_tile(best, ty)
            self.events.append(("bump", (best, ty, kind)))

    # -- 渲染 ------------------------------------------------------------
    def sprite_name(self, atlas) -> str:
        if not self.alive:
            return "p_hurt"
        if self.invuln > 0 and int(self.invuln * 14) % 2 == 0:
            return "p_hurt"
        if not self.on_ground:
            return "p_jump" if self.vel.y < 0 else "p_fall"
        if abs(self.vel.x) > 8:
            frames = ["p_run0", "p_run1", "p_run2", "p_run3"]
            return frames[int(self.anim_time * 11) % 4]
        return "p_idle"

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int, atlas) -> None:
        name = self.sprite_name(atlas)
        img = atlas.get(name)
        if self.squash != 1.0:
            w = max(1, int(img.get_width() * (2.0 - self.squash)))
            h = max(1, int(img.get_height() * self.squash))
            img = pygame.transform.scale(img, (w, h))
        anchored_blit(surf, img, self.rect, cam_x, cam_y, flip=self.facing < 0)


def _approach(value: float, target: float, delta: float) -> float:
    if value < target:
        return min(target, value + delta)
    if value > target:
        return max(target, value - delta)
    return value


# --------------------------------------------------------------------------
# 敌人
# --------------------------------------------------------------------------
class Enemy:
    kind = "enemy"
    stompable = True
    sprite_names = ("e_slime0", "e_slime1")
    w, h = 12, 11

    def __init__(self, x: float, y: float, world) -> None:
        self.world = world
        rect = pygame.Rect(0, 0, self.w, self.h)
        rect.midbottom = (int(x), int(y))
        self.rect = rect
        self.pos = pygame.Vector2(rect.x, rect.y)
        self.vel = pygame.Vector2(0.0, 0.0)
        self.alive = True
        self.facing = -1
        self.anim_time = 0.0
        self.squash = 1.0
        self.contact_damage = 1

    def update(self, dt: float, player: Player) -> None:
        raise NotImplementedError

    def on_stomped(self, player: Player) -> None:
        """被踩扁后的处理。"""
        self.alive = False

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int, atlas) -> None:
        name = self.sprite_names[int(self.anim_time * 6) % len(self.sprite_names)]
        img = atlas.get(name)
        if self.squash != 1.0:
            img = pygame.transform.scale(
                img, (max(1, int(img.get_width() * (2 - self.squash))), max(1, int(img.get_height() * self.squash)))
            )
        anchored_blit(surf, img, self.rect, cam_x, cam_y, flip=self.facing > 0)


class Slime(Enemy):
    kind = "slime"
    sprite_names = ("e_slime0", "e_slime1")
    w, h = 12, 11

    def __init__(self, x: float, y: float, world) -> None:
        super().__init__(x, y, world)
        self.hop_timer = random.uniform(0.0, 1.0)

    def update(self, dt: float, player: Player) -> None:
        self.anim_time += dt
        self.hop_timer -= dt
        if self.hop_timer <= 0:
            self.hop_timer = 1.5
            # 玩家在附近就朝玩家跳
            if abs(player.rect.centerx - self.rect.centerx) < 120 and player.alive:
                self.facing = 1 if player.rect.centerx > self.rect.centerx else -1
            if self.on_ground():
                self.vel.y = -150.0
                self.vel.x = self.facing * S.SLIME_SPEED * 1.8

        self.vel.y = min(S.MAX_FALL, self.vel.y + S.ENEMY_GRAVITY * dt)
        if self.on_ground():
            self.vel.x = _approach(self.vel.x, 0.0, 240 * dt)

        move_and_collide(self.pos, self.vel, self.rect, self.world, dt)

        if self.world.wall_ahead(self.rect, -1 if self.facing < 0 else 1) and self.on_ground():
            self.facing *= -1
        if not self.world.ground_below(self.rect, 2) and self.on_ground():
            self.facing *= -1
        if self.rect.top > self.world.height + 60:
            self.alive = False

    def on_ground(self) -> bool:
        probe = pygame.Rect(self.rect.x, self.rect.bottom, self.rect.width, 2)
        return self.world.solid_at_rect(probe)


class Bat(Enemy):
    kind = "bat"
    sprite_names = ("e_bat0", "e_bat1")
    w, h = 12, 10

    def __init__(self, x: float, y: float, world) -> None:
        super().__init__(x, y, world)
        self.base_y = float(self.rect.y)
        self.phase = random.uniform(0, math.tau)
        self.facing = -1

    def update(self, dt: float, player: Player) -> None:
        self.anim_time += dt
        self.phase += dt * 3.0
        # 缓慢朝玩家漂移
        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        if dist < 150 and player.alive:
            self.vel.x = _approach(self.vel.x, S.BAT_SPEED * (1 if dx > 0 else -1), 90 * dt)
            self.vel.y = _approach(self.vel.y, S.BAT_SPEED * 0.6 * (1 if dy > 0 else -1), 90 * dt)
        else:
            self.vel.x = _approach(self.vel.x, S.BAT_SPEED * self.facing, 40 * dt)

        self.facing = 1 if self.vel.x > 0 else (-1 if self.vel.x < 0 else self.facing)
        old_x = self.rect.x
        self.rect.x += int(round(self.vel.x * dt))
        if self.world.solid_at_rect(self.rect):
            step = 1 if self.vel.x > 0 else -1
            guard = 0
            while self.world.solid_at_rect(self.rect) and guard < 64:
                self.rect.x -= step
                guard += 1
            self.vel.x = 0.0
            self.facing *= -1
        if self.rect.x == old_x and self.vel.x == 0:
            self.facing *= -1
        # 蝙蝠不落地，上下浮动
        self.rect.y += int(round(math.sin(self.phase) * 6))
        self.pos.update(float(self.rect.x), float(self.rect.y))

    def on_stomped(self, player: Player) -> None:
        self.alive = False


class Walker(Enemy):
    """刺壳虫：走直线，外壳有刺，只能从上方踩。"""

    kind = "walker"
    sprite_names = ("e_walker0", "e_walker1")
    w, h = 12, 12

    def update(self, dt: float, player: Player) -> None:
        self.anim_time += dt
        self.vel.y = min(S.MAX_FALL, self.vel.y + S.ENEMY_GRAVITY * dt)
        self.vel.x = self.facing * S.WALKER_SPEED

        move_and_collide(self.pos, self.vel, self.rect, self.world, dt)

        if self.world.wall_ahead(self.rect, self.facing):
            self.facing *= -1
        if not self.world.ground_below(self.rect, 3):
            self.facing *= -1
        if self.world.hazard_tiles_near(self.rect.centerx // TILE, self.rect.bottom // TILE, 1):
            self.facing *= -1
        if self.rect.top > self.world.height + 60:
            self.alive = False


ENEMY_TYPES = {"s": Slime, "b": Bat, "w": Walker}


# --------------------------------------------------------------------------
# 收集品
# --------------------------------------------------------------------------
class Pickup:
    def __init__(self, kind: str, tx: int, ty: int) -> None:
        self.kind = kind
        self.x = tx * TILE
        self.y = ty * TILE
        self.taken = False
        self.phase = random.uniform(0, math.tau)
        self.rect = pygame.Rect(self.x + 2, self.y + 2, TILE - 4, TILE - 4)

    def update(self, dt: float) -> None:
        self.phase += dt * 3.0

    def draw(self, surf: pygame.Surface, cam_x: int, cam_y: int, atlas) -> None:
        bob = int(math.sin(self.phase) * 2)
        sx = self.x - cam_x
        sy = self.y - cam_y + bob
        if self.kind == "o":
            img = atlas.get(f"i_coin{int(pygame.time.get_ticks() / 90) % 4}")
        elif self.kind == "*":
            img = atlas.get("i_gem")
        else:
            img = atlas.get("i_heart")
        surf.blit(img, (sx, sy))

    @property
    def score(self) -> int:
        return {"o": 1, "h": 0, "*": 10}[self.kind]
