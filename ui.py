"""界面：字体加载、HUD、菜单、结算画面。"""
from __future__ import annotations

import os

import pygame

from settings import C_ACCENT, C_BLACK, C_DANGER, C_TEXT, C_TEXT_DIM, C_WHITE, VIEW_H, VIEW_W

_CJK_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msjh.ttc",
    r"C:\Windows\Fonts\Deng.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def _find_cjk_font() -> str | None:
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("msyh.ttc", "simhei.ttf", "SourceHanSansCN-Regular.otf"):
        p = os.path.join(here, "assets", "fonts", name)
        if os.path.exists(p):
            return p
    for p in _CJK_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


class Fonts:
    def __init__(self) -> None:
        self.cjk_path = _find_cjk_font()
        self.has_cjk = self.cjk_path is not None
        self.big = self._make(20)
        self.mid = self._make(13)
        self.small = self._make(9)

    def _make(self, size: int) -> pygame.font.Font:
        if self.cjk_path:
            try:
                return pygame.font.Font(self.cjk_path, size)
            except Exception:
                pass
        return pygame.font.Font(None, size)


def draw_text(
    surf: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    x: int,
    y: int,
    color=C_TEXT,
    align: str = "left",
    shadow: bool = True,
    shadow_color=(0, 0, 0),
) -> pygame.Rect:
    img = font.render(text, True, color)
    rect = img.get_rect()
    if align == "center":
        rect.midtop = (x, y)
    elif align == "right":
        rect.topright = (x, y)
    else:
        rect.topleft = (x, y)
    if shadow:
        sh = font.render(text, True, shadow_color)
        surf.blit(sh, (rect.x + 1, rect.y + 1))
    surf.blit(img, rect.topleft)
    return rect


def draw_bar(surf, x, y, w, h, ratio, color, back=(40, 34, 52)) -> None:
    pygame.draw.rect(surf, back, (x, y, w, h))
    ratio = max(0.0, min(1.0, ratio))
    pygame.draw.rect(surf, color, (x, y, int(w * ratio), h))


class HUD:
    def __init__(self, fonts: Fonts) -> None:
        self.fonts = fonts

    def draw(self, surf, player, level_name, stage, total_stages, elapsed, atlas, hint=None) -> None:
        # 左上：生命
        for i in range(player.hp):
            surf.blit(atlas.get("i_heart"), (6 + i * 14, 5))
        if player.hp <= 0:
            draw_text(surf, self.fonts.small, "0", 6, 8, C_DANGER)

        # 右上：金币 / 宝石 / 时间
        coin = atlas.get("i_coin0")
        surf.blit(coin, (VIEW_W - 92, 5))
        draw_text(surf, self.fonts.mid, f"x{player.coins:02d}", VIEW_W - 74, 7, C_ACCENT)
        surf.blit(atlas.get("i_gem"), (VIEW_W - 44, 5))
        draw_text(surf, self.fonts.mid, f"x{player.gems:02d}", VIEW_W - 26, 7, (140, 214, 226))

        # 顶部中间：关卡
        draw_text(surf, self.fonts.small, f"{stage}/{total_stages}  {level_name}",
                  VIEW_W // 2, 6, C_TEXT_DIM, align="center")
        mm = int(elapsed) // 60
        ss = int(elapsed) % 60
        draw_text(surf, self.fonts.small, f"{mm:02d}:{ss:02d}", VIEW_W // 2, 18, C_TEXT, align="center")

        if hint:
            # 画在半透明底条上，避免和背景的树木混在一起看不清
            img = self.fonts.small.render(hint, True, C_TEXT)
            r = img.get_rect(midbottom=(VIEW_W // 2, VIEW_H - 42))
            bg = pygame.Surface((r.width + 10, r.height + 6), pygame.SRCALPHA)
            bg.fill((10, 8, 18, 150))
            surf.blit(bg, (r.x - 5, r.y - 3))
            surf.blit(img, r.topleft)


def draw_vignette(surf: pygame.Surface, strength: int = 66) -> None:
    if getattr(draw_vignette, "_surf", None) is None:
        v = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        cx, cy = VIEW_W / 2, VIEW_H / 2
        maxd = (cx ** 2 + cy ** 2) ** 0.5
        for y in range(0, VIEW_H, 2):
            for x in range(0, VIEW_W, 2):
                d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / maxd
                a = int(max(0.0, d - 0.5) ** 1.7 * strength * 3)
                if a > 0:
                    pygame.draw.rect(v, (6, 4, 12, min(255, a)), (x, y, 2, 2))
        draw_vignette._surf = v
    surf.blit(draw_vignette._surf, (0, 0))


def draw_panel(surf, rect: pygame.Rect, alpha: int = 232, border=C_ACCENT) -> None:
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    panel.fill((18, 14, 26, alpha))
    surf.blit(panel, rect.topleft)
    pygame.draw.rect(surf, border, rect, 1)
    pygame.draw.rect(surf, (10, 8, 16), rect.inflate(4, 4), 1)


def menu_screen(surf, fonts: Fonts, atlas, t: float, best_score: int, has_cjk: bool) -> None:
    overlay = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
    overlay.fill((8, 6, 16, 205))
    surf.blit(overlay, (0, 0))

    title = "晨光跳跃" if has_cjk else "DAWN LEAP"
    sub = "DAWN LEAP" if has_cjk else "A tiny pixel platformer"

    bob = int((pygame.time.get_ticks() / 400.0) % 2)
    draw_text(surf, fonts.big, title, VIEW_W // 2, 46 + bob, C_ACCENT, align="center")
    draw_text(surf, fonts.small, sub, VIEW_W // 2, 74 + bob, C_TEXT_DIM, align="center")

    # 一个小预览角色
    surf.blit(atlas.get("p_run2" if int(t * 6) % 2 == 0 else "p_run0"), (VIEW_W // 2 - 18, 96))

    draw_text(surf, fonts.mid, "按 空格 / 回车 开始游戏", VIEW_W // 2, 140, C_WHITE, align="center")
    draw_text(surf, fonts.small, "空格/↑ 跳跃（可二段跳）   ←→/AD 移动   R 重开本关",
              VIEW_W // 2, 162, C_TEXT_DIM, align="center")
    draw_text(surf, fonts.small, "P 暂停   M 静音   ESC 返回   F11 全屏",
              VIEW_W // 2, 176, C_TEXT_DIM, align="center")
    draw_text(surf, fonts.small, "踩敌人得分 · 收集金币与宝石 · 走到发光的门过关",
              VIEW_W // 2, 196, (150, 200, 160), align="center")
    if best_score:
        draw_text(surf, fonts.small, f"历史最高分  {best_score}", VIEW_W // 2, 216, C_ACCENT, align="center")
    tip = "提示：所有美术和音效都由代码生成，没有外部素材" if has_cjk else \
          "All art & audio are generated by code"
    draw_text(surf, fonts.small, tip, VIEW_W // 2, VIEW_H - 18, (110, 104, 126), align="center")


def pause_screen(surf, fonts: Fonts) -> None:
    overlay = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
    overlay.fill((8, 6, 16, 190))
    surf.blit(overlay, (0, 0))
    r = pygame.Rect(0, 0, 190, 92)
    r.center = (VIEW_W // 2, VIEW_H // 2)
    draw_panel(surf, r)
    draw_text(surf, fonts.mid, "已暂停", VIEW_W // 2, r.y + 14, C_ACCENT, align="center")
    draw_text(surf, fonts.small, "P / ESC 继续", VIEW_W // 2, r.y + 42, C_TEXT, align="center")
    draw_text(surf, fonts.small, "R 重开本关    Q 回主菜单", VIEW_W // 2, r.y + 60, C_TEXT_DIM, align="center")


def results_screen(surf, fonts: Fonts, atlas, title, lines, accent=C_ACCENT, footer="") -> None:
    overlay = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
    overlay.fill((8, 6, 16, 205))
    surf.blit(overlay, (0, 0))
    r = pygame.Rect(0, 0, 250, 60 + 16 * len(lines))
    r.center = (VIEW_W // 2, VIEW_H // 2)
    draw_panel(surf, r, border=accent)
    draw_text(surf, fonts.mid, title, VIEW_W // 2, r.y + 12, accent, align="center")
    y = r.y + 38
    for label, value, color in lines:
        draw_text(surf, fonts.small, label, r.x + 16, y, C_TEXT_DIM)
        draw_text(surf, fonts.small, value, r.right - 16, y, color, align="right")
        y += 16
    if footer:
        draw_text(surf, fonts.small, footer, VIEW_W // 2, r.bottom + 10, C_TEXT, align="center")
