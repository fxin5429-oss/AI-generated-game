"""主游戏：状态机、输入、循环、计分。"""
from __future__ import annotations

import math
import os
import random
import sys

import pygame

import art
import settings as S
import ui
from audio import Audio
from entities import ENEMY_TYPES, Particle, Pickup, Player, Popup, PoppedCoin
from levels import LEVELS
from settings import TILE, VIEW_H, VIEW_W
from world import World

# 需要按住才能持续移动的按键
LEFT_KEYS = (pygame.K_LEFT, pygame.K_a)
RIGHT_KEYS = (pygame.K_RIGHT, pygame.K_d)
JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w, pygame.K_z)
CONFIRM_KEYS = (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER)


class Camera:
    def __init__(self) -> None:
        self.x = 0.0
        self.y = 0.0

    def snap_to(self, target: pygame.Rect, world: World) -> None:
        self.x, self.y = self._desired(target, world, 1.0)
        self._clamp(world)

    def _desired(self, target: pygame.Rect, world: World, lead: float) -> tuple[float, float]:
        dx = self.x + VIEW_W / 2 - target.centerx
        dy = self.y + VIEW_H * 0.58 - target.centery
        return self.x - dx, self.y - dy

    def _clamp(self, world: World) -> None:
        self.x = max(0.0, min(world.width - VIEW_W, self.x)) if world.width > VIEW_W else 0.0
        self.y = max(0.0, min(world.height - VIEW_H, self.y)) if world.height > VIEW_H else 0.0

    def update(self, target: pygame.Rect, world: World, facing: int, dt: float, look: float = 1.0) -> None:
        desired_x = self.x + VIEW_W / 2 - (target.centerx + facing * S.CAMERA_LOOK_AHEAD * look)
        desired_y = self.y + VIEW_H * 0.58 - target.centery
        k = min(1.0, S.CAMERA_LERP * dt)
        self.x -= desired_x * k
        self.y -= desired_y * k
        self._clamp(world)


class Game:
    def __init__(self, level_index: int = 0, audio: bool = True, autoplay: bool = False,
                 start_immediately: bool = False) -> None:
        pygame.init()
        pygame.display.set_caption(S.CAPTION)
        self.autoplay = autoplay
        flags = 0
        self.screen = pygame.display.set_mode((S.WINDOW_W, S.WINDOW_H), flags)
        self.buffer = pygame.Surface((VIEW_W, VIEW_H)).convert()
        self.fullscreen = False
        self.clock = pygame.time.Clock()

        art.build()
        self.atlas = art.atlas()
        self.fonts = ui.Fonts()
        self.hud = ui.HUD(self.fonts)
        self.audio = Audio(enabled=audio)
        self._icon()

        self.rng = random.Random(20260410)
        self.state = "menu"
        self.state_time = 0.0
        self.level_index = level_index
        self.world: World | None = None
        self.player: Player | None = None
        self.camera = Camera()
        self.enemies: list = []
        self.pickups: list[Pickup] = []
        self.particles: list[Particle] = []
        self.popups: list[Popup] = []
        self.popped: list[PoppedCoin] = []
        self.level_time = 0.0
        self.total_score = 0
        self.best_score = self._load_best()
        self.shake = 0.0
        self.running = True
        self.vignette = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        self.show_fps = False
        self.result_lines: list[tuple[str, str, tuple[int, int, int]]] = []
        self.result_title = ""
        self.result_footer = ""

        if level_index > 0 or start_immediately:
            self.start_level(level_index)
        else:
            self.state = "menu"

    # ------------------------------------------------------------------
    def _icon(self) -> None:
        img = pygame.transform.scale(self.atlas.get("p_idle"), (32, 64))
        pygame.display.set_icon(img)

    def _best_path(self) -> str:
        # 打包成 exe 后 __file__ 指向临时解包目录，存档要放到 exe 旁边才不会丢
        anchor = sys.executable if getattr(sys, "frozen", False) else __file__
        return os.path.join(os.path.dirname(os.path.abspath(anchor)), ".dawnleap_best")

    def _load_best(self) -> int:
        try:
            with open(self._best_path(), "r", encoding="utf-8") as f:
                return int(f.read().strip() or 0)
        except Exception:
            return 0

    def _save_best(self) -> None:
        try:
            with open(self._best_path(), "w", encoding="utf-8") as f:
                f.write(str(self.best_score))
        except Exception:
            pass

    # ------------------------------------------------------------------
    def start_level(self, index: int) -> None:
        self.level_index = max(0, min(len(LEVELS) - 1, index))
        level = LEVELS[self.level_index]
        self.world = World(level, seed=self.level_index * 977 + 13)
        self.level_time = 0.0
        self._reset_entities()
        self.camera.snap_to(self.player.rect, self.world)
        self.state = "play"
        self.state_time = 0.0
        self._auto_deaths = 0
        self._auto_progress_t = 0.0
        self._auto_last_x = self.player.rect.centerx
        if self.audio.ok:
            self.audio.music(level.music)

    def _reset_entities(self) -> None:
        world = self.world
        assert world is not None
        sx, sy = world.spawn_pos()
        self.player = Player(sx, sy, world)
        self.enemies = [ENEMY_TYPES[ch](x * TILE + TILE / 2, (y + 1) * TILE, world)
                        for ch, x, y in world.enemy_spawns]
        self.pickups = [Pickup(ch, x, y) for ch, x, y in world.item_spawns]
        self.particles.clear()
        self.popups.clear()
        self.popped.clear()
        self.shake = 0.0

    def restart_level(self) -> None:
        """重开本关：重建世界，金币砖和收集品全部还原。"""
        self.start_level(self.level_index)

    def respawn(self) -> None:
        """死亡后原地重来：保留已经破坏的砖块和已收集的物品。"""
        self._reset_entities()
        assert self.world is not None and self.player is not None
        self.camera.snap_to(self.player.rect, self.world)
        self.state = "play"
        self.state_time = 0.0
        if self.audio.ok:
            self.audio.music(self.world.level.music)

    # ------------------------------------------------------------------
    # 输入
    # ------------------------------------------------------------------
    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.QUIT:
            self.running = False
        elif e.type == pygame.KEYDOWN:
            self._keydown(e)
        elif e.type == pygame.WINDOWFOCUSLOST and self.state == "play":
            self.state = "pause"

    def _keydown(self, e: pygame.event.Event) -> None:
        k = e.key
        if k == pygame.K_F11:
            self._toggle_fullscreen()
            return
        if k == pygame.K_m:
            muted = self.audio.toggle_mute()
            if not muted and self.world is not None and self.audio.ok:
                self.audio.music(self.world.level.music)
            if self.audio.ok:
                self.audio.play("select")
            return
        if k == pygame.K_F3:
            self.show_fps = not self.show_fps
            return
        if k == pygame.K_ESCAPE:
            if self.state in ("play", "pause"):
                self.state = "pause" if self.state == "play" else "play"
                if self.audio.ok:
                    self.audio.play("pause")
            elif self.state == "menu":
                self.running = False
            else:
                self.state = "menu"
            return

        if self.state == "menu":
            if k in CONFIRM_KEYS:
                self.total_score = 0
                self.start_level(0)
                if self.audio.ok:
                    self.audio.play("select")
            return

        if self.state == "pause":
            if k == pygame.K_p or k in CONFIRM_KEYS:
                self.state = "play"
            elif k == pygame.K_r:
                self.restart_level()
            elif k == pygame.K_q:
                self.state = "menu"
            return

        if self.state == "play":
            if k == pygame.K_p:
                self.state = "pause"
            elif k == pygame.K_r:
                self.restart_level()
            elif k in JUMP_KEYS and self.player is not None:
                self.player.want_jump()
            return

        if self.state in ("complete", "gameover", "win"):
            if k in CONFIRM_KEYS:
                if self.state == "complete":
                    nxt = self.level_index + 1
                    if nxt < len(LEVELS):
                        self.start_level(nxt)
                    else:
                        self.state = "win"
                        if self.audio.ok:
                            self.audio.music("calm")
                elif self.state == "gameover":
                    self.total_score = 0
                    self.start_level(0)
                else:  # win
                    self.state = "menu"
            elif k == pygame.K_q:
                self.state = "menu"

    def _toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((S.WINDOW_W, S.WINDOW_H))

    def _collect_input(self, keys) -> None:
        p = self.player
        if p is None:
            return
        direction = 0.0
        if any(keys[k] for k in LEFT_KEYS):
            direction -= 1.0
        if any(keys[k] for k in RIGHT_KEYS):
            direction += 1.0
        p.set_move_intent(direction)
        held = any(keys[k] for k in JUMP_KEYS)
        if held and not p.jump_held and self.state == "play":
            p.want_jump()
        p.set_jump_held(held)

    # ------------------------------------------------------------------
    # 更新
    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        self.state_time += dt
        if self.autoplay and self.state == "play":
            self._autopilot(dt)
        if self.state == "play":
            self._update_play(dt)
        elif self.state == "dying":
            self._update_dying(dt)
        else:
            if self.world is not None:
                self.world.update(dt)
        self._update_effects(dt)

    def _update_play(self, dt: float) -> None:
        world, p = self.world, self.player
        assert world is not None and p is not None
        self.level_time += dt
        world.update(dt)
        p.update(dt)
        self._consume_events(p, world)

        for e in self.enemies:
            if e.alive:
                e.update(dt, p)

        for pk in self.pickups:
            pk.update(dt)

        self._resolve_player_interactions(p, world)

        if p.alive and world.goal_rect() and p.rect.colliderect(world.goal_rect()):
            self._level_complete()

        self.camera.update(p.rect, world, p.facing, dt)
        self._emit_walk_dust(dt)

    def _update_dying(self, dt: float) -> None:
        p = self.player
        if p is None:
            return
        p.update(dt)
        if self.world is not None:
            self.camera.update(p.rect, self.world, p.facing, dt, look=0.0)
        if self.state_time > 1.5:
            if self.autoplay:
                self.respawn()
                return
            self.state = "gameover"
            self.state_time = 0.0
            self.result_title = "GAME OVER" if not self.fonts.has_cjk else "游戏结束"
            self.result_lines = [
                ("到达关卡", LEVELS[self.level_index].name, S.C_TEXT),
                ("累计得分", str(self.total_score), S.C_ACCENT),
            ]
            self.result_footer = "空格 重新开始    Q 返回主菜单"

    def _consume_events(self, p: Player, world: World) -> None:
        for name, data in p.events:
            if name == "jump":
                self._sfx("jump")
                self._dust(p.rect.centerx, p.rect.bottom, 5, (232, 226, 208))
            elif name == "double_jump":
                self._sfx("double_jump")
                self._burst(p.rect.centerx, p.rect.centery + 4, 10, (150, 224, 232))
                self._burst(p.rect.centerx, p.rect.centery + 4, 4, (250, 226, 140))
            elif name == "land":
                self._dust(p.rect.centerx, p.rect.bottom, 7, (222, 210, 190))
                self.shake = max(self.shake, 1.2)
            elif name == "spring":
                self._sfx("spring")
                tx, ty = data  # type: ignore[misc]
                self._burst(tx * TILE + TILE / 2, ty * TILE, 10, (250, 226, 140))
            elif name == "bump":
                tx, ty, kind = data  # type: ignore[misc]
                if kind == "coin":
                    self.popped.append(PoppedCoin(tx * TILE, ty * TILE - TILE))
                    p.coins += 1
                    self.total_score += 10
                    self.popups.append(Popup(tx * TILE + TILE / 2, ty * TILE - 10, "+1", S.C_ACCENT))
                    self._sfx("coin")
                    self._burst(tx * TILE + TILE / 2, ty * TILE, 6, (250, 226, 140))
                else:
                    self._dust(tx * TILE + TILE / 2, ty * TILE + TILE, 4, (200, 190, 170))
            elif name == "hazard":
                if p.hurt(direction=-p.facing):
                    self._sfx("hurt")
                    self.shake = 6.0
                    self._burst(p.rect.centerx, p.rect.centery, 12, (232, 90, 96))
            elif name == "fall_out":
                p.die("fall")
            elif name == "hurt":
                pass
            elif name == "die":
                self._sfx("die")
                self.audio.stop_music()
                self._auto_deaths = getattr(self, "_auto_deaths", 0) + 1
                self.state = "dying"
                self.state_time = 0.0
                self._burst(p.rect.centerx, p.rect.centery, 18, (232, 120, 130))
        p.events.clear()

    def _resolve_player_interactions(self, p: Player, world: World) -> None:
        # 收集品
        for pk in self.pickups:
            if pk.taken or not p.alive:
                continue
            if p.rect.colliderect(pk.rect):
                pk.taken = True
                if pk.kind == "o":
                    p.coins += 1
                    self.total_score += 10
                    self.popups.append(Popup(pk.rect.centerx, pk.rect.top, "+1", S.C_ACCENT))
                    self._sfx("coin")
                elif pk.kind == "*":
                    p.gems += 1
                    self.total_score += 100
                    self.popups.append(Popup(pk.rect.centerx, pk.rect.top, "+10", (150, 224, 232)))
                    self._sfx("gem")
                else:
                    if p.hp < S.PLAYER_MAX_HP:
                        p.hp += 1
                    self.total_score += 20
                    self.popups.append(Popup(pk.rect.centerx, pk.rect.top, "+HP", (232, 120, 140)))
                    self._sfx("gem")
                self._burst(pk.rect.centerx, pk.rect.centery, 8, (250, 226, 140))

        # 敌人
        for e in self.enemies:
            if not e.alive or not p.alive:
                continue
            if not p.rect.colliderect(e.rect):
                continue
            stomp = (p.vel.y > 40 and p.rect.bottom - e.rect.top < 12)
            if stomp and e.stompable:
                e.on_stomped(p)
                p.vel.y = S.STOMP_BOUNCE_HELD if p.jump_held else S.STOMP_BOUNCE
                p.jumps_left = max(p.jumps_left, 1)
                self.total_score += 200
                self.popups.append(Popup(e.rect.centerx, e.rect.top, "+20", (200, 240, 180)))
                self._sfx("stomp")
                self.shake = max(self.shake, 2.5)
                self._burst(e.rect.centerx, e.rect.centery, 10, (150, 230, 150))
            else:
                if p.hurt(direction=1 if p.rect.centerx < e.rect.centerx else -1):
                    self._sfx("hurt")
                    self.shake = 6.0
                    self._burst(p.rect.centerx, p.rect.centery, 10, (232, 90, 96))

        # 敌人碰到尖刺自己消失
        for e in self.enemies:
            if not e.alive:
                continue
            if world.hazards_touching(e.rect):
                e.alive = False
                self._burst(e.rect.centerx, e.rect.centery, 8, (200, 160, 120))

    def _level_complete(self) -> None:
        level = LEVELS[self.level_index]
        p = self.player
        assert p is not None
        self.state = "complete"
        self.state_time = 0.0
        self._sfx("door")
        self.audio.stop_music()
        self._burst(p.rect.centerx, p.rect.centery, 20, (250, 226, 140))
        self.shake = 3.0

        coin_total = sum(1 for pk in self.pickups if pk.kind == "o")
        gem_total = sum(1 for pk in self.pickups if pk.kind == "*")
        time_bonus = max(0, int(level.par_time - self.level_time) * 5)
        hp_bonus = max(0, p.hp) * 50
        self.total_score += time_bonus + hp_bonus

        rank = "S" if self.level_time <= level.par_time * 0.8 else (
            "A" if self.level_time <= level.par_time else
            "B" if self.level_time <= level.par_time * 1.4 else "C")

        self.result_title = f"{level.name} 通关" if self.fonts.has_cjk else f"{level.subtitle} CLEAR"
        self.result_lines = [
            ("用时", f"{self.level_time:5.1f}s", S.C_TEXT),
            ("金币", f"{p.coins}/{coin_total}", S.C_ACCENT),
            ("宝石", f"{p.gems}/{gem_total}", (150, 224, 232)),
            ("生命奖励", f"+{hp_bonus}", (232, 140, 150)),
            ("时间奖励", f"+{time_bonus}", (200, 220, 160)),
            ("累计得分", str(self.total_score), S.C_WHITE),
            ("评价", rank, S.C_ACCENT),
        ]
        last = self.level_index >= len(LEVELS) - 1
        self.result_footer = ("空格 查看结局" if last else "空格 进入下一关") + "    Q 返回主菜单"
        if self.total_score > self.best_score:
            self.best_score = self.total_score
            self._save_best()

    def _emit_walk_dust(self, dt: float) -> None:
        p = self.player
        assert p is not None
        if p.on_ground and abs(p.vel.x) > 60 and self.rng.random() < 0.25:
            self.particles.append(Particle(
                p.rect.centerx - p.facing * 5, p.rect.bottom - 1,
                -p.facing * 20 + self.rng.uniform(-10, 10), self.rng.uniform(-30, -6),
                0.35, (214, 204, 186), 2, 120))

    def _update_effects(self, dt: float) -> None:
        self.particles = [x for x in self.particles if x.update(dt)]
        self.popups = [x for x in self.popups if x.update(dt)]
        self.popped = [x for x in self.popped if x.update(dt)]
        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt * 22.0)

    def _sfx(self, name: str) -> None:
        self.audio.play(name)

    def _dust(self, x: float, y: float, n: int, color) -> None:
        for _ in range(n):
            self.particles.append(Particle(
                x + self.rng.uniform(-5, 5), y - 1,
                self.rng.uniform(-46, 46), self.rng.uniform(-42, -8),
                self.rng.uniform(0.22, 0.42), color, 2, 160))

    def _burst(self, x: float, y: float, n: int, color) -> None:
        for _ in range(n):
            a = self.rng.uniform(0, math.tau)
            sp = self.rng.uniform(30, 96)
            self.particles.append(Particle(
                x, y, math.cos(a) * sp, math.sin(a) * sp - 20,
                self.rng.uniform(0.25, 0.6), color, self.rng.choice((2, 2, 3)), 200))

    # ------------------------------------------------------------------
    # 自动演示（用于无头自测，不是一个可玩的 AI）
    # ------------------------------------------------------------------
    def _autopilot(self, dt: float) -> None:
        """自动演示：只用于无头自测，会真的按键、跳跃。

        不是可玩的 AI，只是一个「能验证流程跑得通」的机器人：
        一直朝终点的方向跑，遇到墙 / 坑 / 尖刺就跳；如果长时间卡住
        或反复死亡，就直接传送到终点，保证通关流程一定被验证到。
        """
        p, world = self.player, self.world
        assert p is not None and world is not None
        p.set_jump_held(False)
        if not p.alive:
            return

        self._auto_last_x = getattr(self, "_auto_last_x", p.rect.centerx)
        self._auto_progress_t = getattr(self, "_auto_progress_t", 0.0)
        if abs(p.rect.centerx - self._auto_last_x) > 6:
            self._auto_last_x = p.rect.centerx
            self._auto_progress_t = 0.0
        else:
            self._auto_progress_t += dt

        if self._auto_progress_t > 6.0 or getattr(self, "_auto_deaths", 0) >= 2:
            goal = world.goal_rect()
            if goal is not None:
                p.rect.midbottom = (goal.centerx, goal.bottom)
                p.pos.update(float(p.rect.x), float(p.rect.y))
                p.vel.update(0.0, 0.0)
                p.invuln = max(p.invuln, 0.4)
            self._auto_progress_t = 0.0
            return

        goal = world.goal_rect()
        target_x = goal.centerx if goal else p.rect.centerx + 60
        direction = 0.0
        if abs(target_x - p.rect.centerx) > 6:
            direction = 1.0 if target_x > p.rect.centerx else -1.0
        if direction == 0.0:
            direction = 1.0
        d = int(direction)

        need_jump = False
        if world.wall_ahead(p.rect, d):
            need_jump = True
        # 前方 1~3 格的危险／坑洞
        for ahead in (14, 26, 38):
            probe = pygame.Rect(p.rect.x + d * ahead, p.rect.y, p.rect.width, p.rect.height)
            if world.hazards_touching(probe):
                need_jump = True
        if p.on_ground:
            foot = pygame.Rect(p.rect.x + d * 16, p.rect.bottom + 2, p.rect.width, 10)
            if not world.solid_at_rect(foot):
                need_jump = True
        elif p.vel.y > 0 and p.coyote <= 0 and p.jumps_left > 0 and not p.on_ground:
            need_jump = True    # 空中补一次二段跳
        if need_jump:
            p.want_jump()
        p.set_move_intent(direction)

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------
    def draw(self) -> None:
        surf = self.buffer
        if self.state == "menu":
            if self.world is None:
                self.world = World(LEVELS[0], seed=1)
                self._reset_entities()
            menu_scroll = (pygame.time.get_ticks() / 1000.0 * 18.0) % max(1.0, self.world.width - VIEW_W)
            self.world.draw_background(surf, menu_scroll, 0)
            self.world.draw_tiles(surf, menu_scroll, self.world.height - VIEW_H)
            ui.menu_screen(surf, self.fonts, self.atlas, pygame.time.get_ticks() / 1000.0,
                           self.best_score, self.fonts.has_cjk)
        else:
            assert self.world is not None and self.player is not None
            cam_x, cam_y = self.camera.x, self.camera.y
            if self.shake > 0:
                cam_x += self.rng.uniform(-self.shake, self.shake)
                cam_y += self.rng.uniform(-self.shake, self.shake)
            self.world.draw_background(surf, cam_x, cam_y)
            self.world.draw_tiles(surf, cam_x, cam_y)
            icx, icy = int(cam_x), int(cam_y)

            for pk in self.pickups:
                if pk.taken:
                    continue
                if -TILE <= pk.x - icx <= VIEW_W and -TILE <= pk.y - icy <= VIEW_H:
                    pk.draw(surf, icx, icy, self.atlas)

            for e in self.enemies:
                if not e.alive:
                    continue
                if -TILE * 2 <= e.rect.x - icx <= VIEW_W + TILE and -TILE * 2 <= e.rect.y - icy <= VIEW_H + TILE:
                    e.draw(surf, icx, icy, self.atlas)

            for c in self.popped:
                c.draw(surf, icx, icy, self.atlas)

            if self.player.alive or self.state == "dying":
                self.player.draw(surf, icx, icy, self.atlas)

            for pt in self.particles:
                pt.draw(surf, icx, icy)
            for pop in self.popups:
                pop.draw(surf, icx, icy, self.fonts.small)

            self.world.draw_foreground(surf, cam_x, cam_y)
            ui.draw_vignette(self.buffer)

            if self.state == "play":
                self.hud.draw(surf, self.player, LEVELS[self.level_index].name, self.level_index + 1,
                              len(LEVELS), self.level_time, self.atlas, self._hint())
            elif self.state == "pause":
                self.hud.draw(surf, self.player, LEVELS[self.level_index].name, self.level_index + 1,
                              len(LEVELS), self.level_time, self.atlas)
                ui.pause_screen(surf, self.fonts)
            elif self.state == "dying":
                pass
            elif self.state == "complete":
                ui.results_screen(surf, self.fonts, self.atlas, self.result_title,
                                  self.result_lines, S.C_OK, self.result_footer)
            elif self.state == "gameover":
                ui.results_screen(surf, self.fonts, self.atlas, self.result_title,
                                  self.result_lines, S.C_DANGER, self.result_footer)
            elif self.state == "win":
                self._draw_win(surf)

        if self.show_fps:
            ui.draw_text(surf, self.fonts.small, f"{self.clock.get_fps():.0f} FPS", 4, VIEW_H - 12, (120, 240, 140))

        # 整数倍缩放输出（保持像素锐利）
        win_w, win_h = self.screen.get_size()
        scale = max(1, min(win_w // VIEW_W, win_h // VIEW_H))
        out_w, out_h = VIEW_W * scale, VIEW_H * scale
        if scale == 1:
            scaled = self.buffer
        else:
            scaled = pygame.transform.scale(self.buffer, (out_w, out_h))
        self.screen.fill((0, 0, 0))
        self.screen.blit(scaled, ((win_w - out_w) // 2, (win_h - out_h) // 2))
        pygame.display.flip()

    def _hint(self) -> str:
        if self.level_index == 0 and self.level_time < 9:
            if self.player and self.player.coins == 0:
                return "←→ 移动   空格 跳跃（空中再按一次可二段跳）"
            return "踩敌人得分 · 顶金币砖出金币 · 走进发光的门过关"
        if self.level_index == 1 and self.level_time < 8:
            return "按 ↑ 抓住梯子上下移动 · 小心尖刺和冰晶"
        if self.level_index == 2 and self.level_time < 8:
            return "移动平台会带着你走 · 掉下去就重来"
        return ""

    def _draw_win(self, surf) -> None:
        overlay = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        overlay.fill((8, 6, 18, 190))
        surf.blit(overlay, (0, 0))
        bob = int(math.sin(pygame.time.get_ticks() / 320.0) * 2)
        title = "全部通关！" if self.fonts.has_cjk else "ALL CLEAR!"
        ui.draw_text(surf, self.fonts.big, title, VIEW_W // 2, 60 + bob, S.C_ACCENT, align="center")
        ui.draw_text(surf, self.fonts.small, "DAWN LEAP — THE END", VIEW_W // 2, 86, S.C_TEXT_DIM, align="center")
        for i in range(5):
            surf.blit(self.atlas.get("i_coin0"), (60 + i * 26, 116 + (i % 2) * 6))
            surf.blit(self.atlas.get("i_gem"), (VIEW_W - 80 - i * 26, 116 + (i % 2) * 6))
        surf.blit(self.atlas.get("p_idle"), (VIEW_W // 2 - 18, 150))
        ui.draw_text(surf, self.fonts.mid, f"最终得分  {self.total_score}", VIEW_W // 2, 196, S.C_WHITE, align="center")
        ui.draw_text(surf, self.fonts.small, "空格 / Q 返回主菜单", VIEW_W // 2, 224, S.C_TEXT_DIM, align="center")

    # ------------------------------------------------------------------
    def run(self, profile_frames: int = 0) -> None:
        accumulator = 0.0
        frames = 0
        while self.running:
            dt = self.clock.tick(S.FPS) / 1000.0
            dt = min(dt, 0.1)
            for e in pygame.event.get():
                self.handle_event(e)

            keys = pygame.key.get_pressed()
            if self.state == "play" and not self.autoplay:
                self._collect_input(keys)

            accumulator += dt
            while accumulator >= S.FIXED_DT:
                self.update(S.FIXED_DT)
                accumulator -= S.FIXED_DT

            self.draw()
            frames += 1
            if profile_frames and frames >= profile_frames:
                self.running = False
        pygame.quit()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    level = 0
    no_audio = False
    autoplay = False
    profile = 0
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--level", "-l") and i + 1 < len(argv):
            level = max(0, int(argv[i + 1]) - 1)
            i += 2
            continue
        if a == "--no-audio":
            no_audio = True
        elif a == "--autoplay":
            autoplay = True
        elif a in ("--profile",) and i + 1 < len(argv):
            profile = int(argv[i + 1])
            i += 2
            continue
        elif a in ("--help", "-h"):
            print(__doc__)
            return 0
        i += 1
    game = Game(level_index=level, audio=not no_audio, autoplay=autoplay)
    game.run(profile_frames=profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
