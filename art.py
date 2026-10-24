"""程序化像素美术。

整个游戏的图像素材都在这里用「字符画 + 调色板」现场生成，
不依赖任何外部图片文件，也不需要美术资源。
"""
from __future__ import annotations

import random
from typing import Iterable, Sequence

import pygame

# --------------------------------------------------------------------------
# 调色板：字符 -> RGBA
# --------------------------------------------------------------------------
PAL: dict[str, tuple[int, int, int, int] | None] = {
    ".": None,                      # 透明
    "K": (26, 20, 32, 255),         # 描边黑
    "k": (58, 44, 70, 255),         # 深灰
    "W": (255, 255, 255, 255),
    "w": (226, 226, 236, 255),

    # 皮肤 / 头发 / 帽子
    "S": (245, 200, 158, 255),
    "s": (206, 152, 112, 255),
    "H": (74, 46, 38, 255),
    "C": (58, 176, 186, 255),       # 帽子主色
    "c": (36, 128, 146, 255),       # 帽子暗部

    # 衣服 / 裤子 / 鞋
    "T": (78, 116, 196, 255),       # 上衣
    "t": (52, 80, 152, 255),        # 上衣暗部
    "P": (58, 62, 106, 255),        # 裤子
    "B": (188, 76, 72, 255),        # 鞋
    "b": (140, 52, 54, 255),

    # 草地 / 泥土
    "G": (108, 196, 106, 255),
    "g": (70, 148, 78, 255),
    "D": (150, 106, 70, 255),
    "d": (112, 74, 50, 255),
    "n": (86, 58, 40, 255),

    # 石头 / 砖
    "A": (126, 132, 156, 255),
    "a": (86, 92, 116, 255),
    "L": (168, 174, 196, 255),
    "R": (176, 96, 84, 255),        # 红砖
    "r": (128, 62, 60, 255),
    "M": (196, 190, 176, 255),      # 砂浆缝

    # 木头
    "O": (164, 118, 74, 255),
    "o": (120, 82, 50, 255),

    # 金属 / 机械
    "E": (156, 162, 178, 255),
    "e": (98, 104, 120, 255),
    "Y": (250, 206, 92, 255),       # 亮黄（金币 / 门把手 / 弹簧顶）
    "y": (196, 142, 46, 255),
    "X": (108, 214, 226, 255),      # 冰蓝
    "x": (62, 148, 174, 255),

    # 危险
    "Z": (232, 90, 96, 255),        # 危险红
    "z": (162, 50, 62, 255),

    # 敌人 - 史莱姆
    "F": (128, 216, 128, 255),
    "f": (72, 156, 96, 255),
    # 敌人 - 蝙蝠
    "V": (172, 118, 200, 255),
    "v": (116, 70, 148, 255),
    # 敌人 - 刺壳虫
    "Q": (208, 148, 88, 255),
    "q": (150, 94, 52, 255),

    # 装饰 / 火把
    "I": (108, 96, 128, 255),
    "i": (74, 64, 94, 255),
    "J": (255, 226, 140, 255),
    "j": (246, 148, 60, 255),

    # 爱心
    "U": (238, 92, 108, 255),
    "u": (168, 46, 74, 255),
}


def surf_from_ram(ram: Sequence[str]) -> pygame.Surface:
    """把字符画转成 Surface。行长度可以不一致，短行自动补透明。"""
    h = len(ram)
    w = max(len(r) for r in ram)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(ram):
        for x, ch in enumerate(row):
            col = PAL.get(ch, None)
            if col is not None:
                s.set_at((x, y), col)
    return s


def swap_colors(s: pygame.Surface, mapping: dict[str, str]) -> pygame.Surface:
    """按调色板字符替换颜色，用来从一个贴图派生出多种变体。"""
    table: dict[tuple[int, int, int, int], tuple[int, int, int, int]] = {}
    for src, dst in mapping.items():
        a, b = PAL[src], PAL[dst]
        if a is not None and b is not None:
            table[a] = b
    out = s.copy()
    pal = out.get_palette() if out.get_bitsize() == 8 else None
    if pal is not None:  # pragma: no cover - 理论上不会走到
        return out
    w, h = out.get_size()
    out.lock()
    for y in range(h):
        for x in range(w):
            c = out.get_at((x, y))
            key = (c.r, c.g, c.b, c.a)
            new = table.get(key)
            if new is not None:
                out.set_at((x, y), new)
    out.unlock()
    return out


def tint(s: pygame.Surface, color: tuple[int, int, int], alpha: int) -> pygame.Surface:
    out = s.copy()
    overlay = pygame.Surface(out.get_size(), pygame.SRCALPHA)
    overlay.fill((color[0], color[1], color[2], alpha))
    out.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return out


# --------------------------------------------------------------------------
# 角色贴图（12 x 24 的字符画）
# --------------------------------------------------------------------------
PLAYER_W, PLAYER_H = 12, 24

_IDLE = [
    "....KKKK....",
    "...KCCCCK...",
    "..KCCCCCCK..",
    "..KCCCCCCK..",
    "..KHHHHHHK..",
    "..KHSSSSHK..",
    "..KHSKSKSK..",  # 眼睛
    "..KHSSSSHK..",
    "...KSSSSK...",
    "....KTTK....",
    "..KKTTTTKK..",
    ".KSTTTTTTSK.",
    ".KSTTTTTTSK.",
    "..KTTTTTTK..",
    "..KTTTTTTK..",
    "..KtTTTTtK..",
    "...KKKKKK...",
    "...KPPPPK...",
    "...KPPPPK...",
    "...KP..PK...",
    "...KP..PK...",
    "...KP..PK...",
    "..KBBK.KBBK.",
    "..KKKK.KKKK.",
]

_RUN_A = [
    "....KKKK....",
    "...KCCCCK...",
    "..KCCCCCCK..",
    "..KCCCCCCK..",
    "..KHHHHHHK..",
    "..KHSSSSHK..",
    "..KHSKSKSK..",
    "..KHSSSSHK..",
    "...KSSSSK...",
    "..K.KTTK....",
    ".KSKTTTTKK..",
    ".KSKTTTTTSK.",
    "..KTTTTTTSK.",
    "..KTTTTTTK..",
    "..KtTTTTtK..",
    "...KKKKKK...",
    "...KPPPPK...",
    "...KPPPPK...",
    "..KPP.KPPK..",
    "..KPK..KPK..",
    ".KBK....KBK.",
    ".KKK....KKK.",
    "............",
    "............",
]

_RUN_B = [
    "....KKKK....",
    "...KCCCCK...",
    "..KCCCCCCK..",
    "..KCCCCCCK..",
    "..KHHHHHHK..",
    "..KHSSSSHK..",
    "..KHSKSKSK..",
    "..KHSSSSHK..",
    "...KSSSSK...",
    "....KTTK....",
    ".KKTTTTKK...",
    ".KSTTTTTTSK.",
    "..KTTTTTTSK.",
    "..KTTTTTTK..",
    "..KtTTTTtK..",
    "...KKKKKK...",
    "...KPPPPK...",
    "...KPPPPK...",
    "....KPPK....",
    "....KPPK....",
    "....KBBK....",
    "....KKKK....",
    "............",
    "............",
]

_JUMP = [
    "....KKKK....",
    "...KCCCCK...",
    "..KCCCCCCK..",
    "..KCCCCCCK..",
    "..KHHHHHHK..",
    "..KHSSSSHK..",
    "..KHSKSKSK..",
    "..KHSSSSHK..",
    "...KSSSSK...",
    "..K.KTTK.K..",
    ".KSKTTTTKSK.",
    ".KSKTTTTKSK.",
    "..KTTTTTTK..",
    "..KTTTTTTK..",
    "..KtTTTTtK..",
    "...KKKKKK...",
    "...KPPPPK...",
    "..KPPPPPPK..",
    "..KPP..PPK..",
    ".KBP....PBK.",
    ".KKK....KKK.",
    "............",
    "............",
    "............",
]

_FALL = [
    "....KKKK....",
    "...KCCCCK...",
    "..KCCCCCCK..",
    "..KCCCCCCK..",
    "..KHHHHHHK..",
    "..KHSSSSHK..",
    "..KHSKSKSK..",
    "..KHSSSSHK..",
    "...KSSSSK...",
    "..K.KTTK....",
    ".KSKTTTTKK..",
    ".KSKTTTTTSK.",
    "..KTTTTTTK..",
    "..KTTTTTTK..",
    "..KtTTTTtK..",
    "...KKKKKK...",
    "...KPPPPK...",
    "..KPPPPPPK..",
    "..KPP..PPK..",
    "..KPK..KPK..",
    ".KBK....KBK.",
    ".KKK....KKK.",
    "............",
    "............",
]

_HURT = [
    "....KKKK....",
    "...KCCCCK...",
    "..KCCCCCCK..",
    "..KCCCCCCK..",
    "..KHHHHHHK..",
    "..KHSSSSHK..",
    "..KHSKKSKK..",  # 眯眼
    "..KHSSSSHK..",
    "...KSZZSK...",  # 张嘴
    "..K.KTTK.K..",
    ".KSKTTTTKSK.",
    ".KSKTTTTKSK.",
    "..KTTTTTTK..",
    "..KTTTTTTK..",
    "..KtTTTTtK..",
    "...KKKKKK...",
    "...KPPPPK...",
    "..KPPPPPPK..",
    "..KPP..PPK..",
    ".KBP....PBK.",
    ".KKK....KKK.",
    "............",
    "............",
    "............",
]

# --------------------------------------------------------------------------
# 砖块（16 x 16）
# --------------------------------------------------------------------------
T_GRASS = [
    "gggggggggggggggg",
    "gGGGGGGGGGGGGGGg",
    "GGGGGGGGGGGGGGGG",
    "GGgGGGGGGGgGGGGG",
    "DDDDDDDDDDDDDDDD",
    "DDDDDdDDDDDDDDDD",
    "DDdDDDDDDDDDdDDD",
    "DDDDDDDDDdDDDDDD",
    "DDDdDDDDDDDDDDdD",
    "dDDDDDDdDDDDDDDD",
    "DDDDDDDDDDDDdDDD",
    "DDdDDDDDDDDDDDDD",
    "DDDDDDdDDDdDDDDD",
    "dDDDDDDDDDDDDDdD",
    "DDDDDDDDDDDDDDDD",
    "nnnnnnnnnnnnnnnn",
]

T_DIRT = [
    "DDDDDDDDDDDDDDDD",
    "DDdDDDDDDDDDDdDD",
    "DDDDDDDdDDDDDDDD",
    "DdDDDDDDDDDdDDDD",
    "DDDDDDDDDDDDDDDD",
    "DDDDdDDDDDDDDDDD",
    "dDDDDDDDdDDDDDDD",
    "DDDDDDDDDDDDDdDD",
    "DDDDdDDDDDDDDDDD",
    "DDDDDDDDDDdDDDDD",
    "DdDDDDDDDDDDDDDD",
    "DDDDDDDdDDDDDDDD",
    "DDDDDDDDDDDDdDDD",
    "DDdDDDDDDDDDDDDD",
    "DDDDDDdDDDDDDDDD",
    "nnnnnnnnnnnnnnnn",
]

T_STONE = [
    "AAAAAAAAAAAAAAAA",
    "ALAAAAAAAAAAAAaA",
    "AAAAAAAAAAAAAAaA",
    "AAAAAaAAAAAAAAAA",
    "AAAAAAAAAAAAAAaA",
    "AaAAAAAAAAAAAAAA",
    "AAAAAAaAAAAAAAAA",
    "AAAAAAAAAAAAAAaA",
    "AAAAAAAAaAAAAAAA",
    "AAaAAAAAAAAAAAAA",
    "AAAAAAAAAAAAAAaA",
    "AAAAAAAaAAAAAAAA",
    "AAAAAAAAAAAAAAAA",
    "AaAAAAAAAAAAAAaA",
    "AAAAAAAAAAAAAAAA",
    "aaaaaaaaaaaaaaaa",
]

T_BRICK = [
    "MMMMMMMMMMMMMMMM",
    "RRRRRRRMRRRRRRRM",
    "RRRRRRRMRRRRRRRM",
    "rrrrrrrMrrrrrrrm",
    "MMMMMMMMMMMMMMMM",
    "RRRMRRRRRRRRMRRR",
    "RRRMRRRRRRRRMRRR",
    "rrrMrrrrrrrrMrrr",
    "MMMMMMMMMMMMMMMM",
    "RRRRRRRMRRRRRRRM",
    "RRRRRRRMRRRRRRRM",
    "rrrrrrrMrrrrrrrm",
    "MMMMMMMMMMMMMMMM",
    "RRRMRRRRRRRRMRRR",
    "rrrMrrrrrrrrMrrr",
    "MMMMMMMMMMMMMMMM",
]

T_WOOD = [
    "oooooooooooooooo",
    "OOOOOOOOOOOOOOOO",
    "OOOoOOOOOOOOOOOO",
    "OOOOOOOOOOOoOOOO",
    "OOOoOOOOOOOOOOOO",
    "OOOOOOOOOOOoOOOO",
    "OOOOOoOOOOOOOOOO",
    "OOOOOOOOOOOOOOOO",
    "OOOOOOOoOOOOOOOO",
    "OOoOOOOOOOOOOOOO",
    "OOOOOOOOOOoOOOOO",
    "OOOOOOOOOOOOOOOO",
    "OOOoOOOOOOOOoOOO",
    "OOOOOOOOOOOOOOOO",
    "oooooOoooooooooo",
    "oooooooooooooooo",
]

T_CRATE = [
    "oooooooooooooooo",
    "oOOOOOOOOOOOOOOo",
    "oOooooooooooooOo",
    "oOoOOOOOOOOOOoOo",
    "oOoOooooooooOoOo",
    "oOoOoOOOOOOoOoOo",
    "oOoOoOooooOoOoOo",
    "oOoOoOoOOoOoOoOo",
    "oOoOoOoOOoOoOoOo",
    "oOoOoOooooOoOoOo",
    "oOoOoOOOOOOoOoOo",
    "oOoOooooooooOoOo",
    "oOoOOOOOOOOOOoOo",
    "oOooooooooooooOo",
    "oOOOOOOOOOOOOOOo",
    "oooooooooooooooo",
]

T_METAL = [
    "eeeeeeeeeeeeeeee",
    "eEEEEEEEEEEEEEEe",
    "eEeEEEEEEEEEEeEe",
    "eEEEEEEEEEEEEEEe",
    "eEEEEEEEEEEEEEEe",
    "eEeEEEEEEEEEEeEe",
    "eEEEEEEEEEEEEEEe",
    "eEEEEEEEEEEEEEEe",
    "eEEEEEEEEEEEEEEe",
    "eEEEEEEEEEEEEEEe",
    "eEeEEEEEEEEEEeEe",
    "eEEEEEEEEEEEEEEe",
    "eEEEEEEEEEEEEEEe",
    "eEeEEEEEEEEEEeEe",
    "eEEEEEEEEEEEEEEe",
    "eeeeeeeeeeeeeeee",
]

T_PLATFORM = [
    "eeeeeeeeeeeeeeee",
    "EEEEEEEEEEEEEEEE",
    "EEEEEEEEEEEEEEEE",
    "YYYYYYYYYYYYYYYY",
    "yyyyyyyyyyyyyyyy",
    "eEeEeEeEeEeEeEeE",
    "eeeeeeeeeeeeeeee",
    "EEEEEEEEEEEEEEEE",
    "EEEEEEEEEEEEEEEE",
    "eeeeeeeeeeeeeeee",
    "EEEEEEEEEEEEEEEE",
    "EEEEEEEEEEEEEEEE",
    "eeeeeeeeeeeeeeee",
    "EEEEEEEEEEEEEEEE",
    "eeeeeeeeeeeeeeee",
    "eeeeeeeeeeeeeeee",
]

T_SPIKE = [
    "................",
    "................",
    "................",
    ".......ZZ.......",
    ".......ZZ.......",
    "......ZWWZ......",
    "......ZWWZ......",
    ".....ZWWWWZ.....",
    ".....ZzWWzZ.....",
    "....ZWWWWWWZ....",
    "....ZzWWWWzZ....",
    "...ZWWWWWWWWZ...",
    "...ZzWWWWWWzZ...",
    "..ZWWWWWWWWWWZ..",
    "..ZzzzzzzzzzzZ..",
    "..ZZZZZZZZZZZZ..",
]

T_CRYSTAL = [
    "................",
    ".......x........",
    "......xXx.......",
    ".....xXXXx......",
    "....xXXXXXx.....",
    "...xXXXXXXXx....",
    "...xXXXXXXXx....",
    "..xXXXXXXXXXx...",
    "...xXXXXXXXx....",
    "...xXXXXXXXx....",
    "....xXXXXXx.....",
    "....xXXXXXx.....",
    ".....xXXXx......",
    ".....xXxXx......",
    "......xXx.......",
    ".......x........",
]

T_LADDER = [
    "oooo....oooo....",
    "OOOO....OOOO....",
    "OOOO....OOOO....",
    "OOOO....OOOO....",
    "OOOO....OOOO....",
    "oooooooooooooooo",
    "OOOOOOOOOOOOOOOO",
    "OOOOOOOOOOOOOOOO",
    "oooooooooooooooo",
    "OOOOOOOOOOOOOOOO",
    "OOOO....OOOO....",
    "OOOO....OOOO....",
    "OOOO....OOOO....",
    "OOOO....OOOO....",
    "oooo....oooo....",
    "oooo....oooo....",
]

T_DOOR = [
    "oooooooooooooooo",
    "oOOOOOOOOOOOOOOo",
    "oOooooooooooooOo",
    "oOoOOOOOOOOOOoOo",
    "oOoOooooooooOoOo",
    "oOoOoOOOOOOoOoOo",
    "oOoOoOooooOoOoOo",
    "oOoOoOoOOoOoOoOo",
    "oOoOoOoOOoOoOoOo",
    "oOoOoOooooOoOoOo",
    "oOoOoOOOOOOoOoOo",
    "oOoOooooooooOoOo",
    "oOoOOOOOOOOOOoOo",
    "oOooooooooooooOo",
    "oOOOOOOOOOOOOOOo",
    "oooooooooooooooo",
]

T_SPRING = [
    "................",
    "................",
    ".YYYYYYYYYYYYYY.",
    "YyyyyyyyyyyyyyyY",
    "YyyyyyyyyyyyyyyY",
    ".YYYYYYYYYYYYYY.",
    "....eE....Ee....",
    "...eEE....EEe...",
    "....eE....Ee....",
    "...eEE....EEe...",
    "....eE....Ee....",
    "...eEE....EEe...",
    "..eeeeeeeeeeee..",
    "..EEEEEEEEEEEE..",
    "..eeeeeeeeeeee..",
    "..eeeeeeeeeeee..",
]

T_CLOUD_BLOCK = [
    "wwwwwwwwwwwwwwww",
    "wwWWWWWWWWWWWWww",
    "wWWWWWWWWWWWWWWw",
    "wWWWWWWWWWWWWWWw",
    "wWWWWWWWWWWWWWWw",
    "wWWWWWWWWWWWWWWw",
    "wWWWWWWWWWWWWWWw",
    "wWWWWWWWWWWWWWWw",
    "wWWWWWWWWWWWWWWw",
    "wWWWWWWWWWWWWWWw",
    "wWWWWWWWWWWWWWWw",
    "wWWWWWWWWWWWWWWw",
    "wWWWWWWWWWWWWWWw",
    "wWWWWWWWWWWWWWWw",
    "wwWWWWWWWWWWWWww",
    "wwwwwwwwwwwwwwww",
]

_D = "."  # 占位，避免误用

# 树 / 火把 / 指示牌
T_TREE = [
    "......gggg......",
    ".....gggggg.....",
    "...gggggggggg...",
    "..gggggggggggg..",
    "..ggGGGGGGGGgg..",
    ".gggggggggggggg.",
    ".gggGGGGGGGGggg.",
    "gggggggggggggggg",
    "ggggGGGGGGGGgggg",
    ".gggggggggggggg.",
    "..gggggggggggg..",
    "...gggggggggg...",
    ".....oooooo.....",
    ".....oOooOo.....",
    ".....oooooo.....",
    "......oooo......",
]

T_TORCH = [
    "......jjj.......",
    ".....jJJJj......",
    "....jJJJJJj.....",
    "....jJJJJJj.....",
    "....jJJJJJj.....",
    ".....jJJJj......",
    "......jjj.......",
    "......ooo.......",
    "......oOo.......",
    "......oOo.......",
    "......oOo.......",
    "......oOo.......",
    "......oOo.......",
    "......oOo.......",
    "......ooo.......",
    "......ooo.......",
]

# --------------------------------------------------------------------------
# 敌人贴图（16 x 16）
# --------------------------------------------------------------------------
E_SLIME_A = [
    "................",
    "................",
    "................",
    "................",
    ".....KKKKKK.....",
    "...KKFFFFFFKK...",
    "..KFFFFFFFFFFK..",
    ".KFFFFFFFFFFFFK.",
    ".KFFFKFFFFKFFFK.",
    ".KFFFKFFFFKFFFK.",
    ".KFFFFFFFFFFFFK.",
    ".KFFFFFFFFFFFFK.",
    "KFFFFFFFFFFFFFFK",
    "KffFFFFFFFFFFFFK",
    "KffffffffffffffK",
    ".KKKKKKKKKKKKKK.",
]

E_SLIME_B = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "....KKKKKKKK....",
    "..KKFFFFFFFFKK..",
    ".KFFFFFFFFFFFFK.",
    ".KFFFKFFFFKFFFK.",
    "KFFFKFFFFKFFFFK.",
    "KFFFFFFFFFFFFFFK",
    "KFFFFFFFFFFFFFFK",
    "KFFFFFFFFFFFFFFK",
    "KffffFFFFFFFFfFK",
    "KffffffffffffffK",
    "KKKKKKKKKKKKKKKK",
]

E_BAT_A = [
    "................",
    "................",
    "................",
    "KK............KK",
    "VKK..........KKV",
    "VVKK...KK...KKVV",
    ".VVKKKVKKVKKKVV.",
    "..VVVVVVVVVVVV..",
    "...VVVKKKKVVV...",
    "...VVKZKKZKKV...",
    "...VVVKKKKVVV...",
    "....VVVVVVVV....",
    ".....VVVVVV.....",
    "......VVVV......",
    ".......VV.......",
    "................",
]

E_BAT_B = [
    "................",
    "................",
    "................",
    ".KK..........KK.",
    ".VKK........KKV.",
    "..VKK..KK..KKV..",
    "...VKKKVKKVKKV..",
    "....VVVVVVVV....",
    "...VVVKKKKVVV...",
    "...VVKZKKZKKV...",
    "...VVVKKKKVVV...",
    "....VVVVVVVV....",
    ".....VVVVVV.....",
    "......VVVV......",
    ".......VV.......",
    "................",
]

E_WALKER_A = [
    "................",
    "................",
    ".....KKKKKK.....",
    "....KQQQQQQK....",
    "...KQQQQQQQQK...",
    "...KQKQQQQKQK...",
    "...KQKQQQQKQK...",
    "...KQQQQQQQQK...",
    "...KQqqqqqqQK...",
    "..KQQQQQQQQQQK..",
    ".KQQQQQQQQQQQQK.",
    ".KqzqzqzqzqzqzK.",
    ".KQzQzQzQzQzQzK.",
    "..KKKKKKKKKKKK..",
    "...oooo..oooo...",
    "..ooooo..ooooo..",
]

E_WALKER_B = [
    "................",
    "................",
    ".....KKKKKK.....",
    "....KQQQQQQK....",
    "...KQQQQQQQQK...",
    "...KQKQQQQKQK...",
    "...KQKQQQQKQK...",
    "...KQQQQQQQQK...",
    "...KQqqqqqqQK...",
    "..KQQQQQQQQQQK..",
    ".KQQQQQQQQQQQQK.",
    ".KqzqzqzqzqzqzK.",
    ".KQzQzQzQzQzQzK.",
    "..KKKKKKKKKKKK..",
    "....oooooooo....",
    "...ooo....ooo...",
]

# --------------------------------------------------------------------------
# 金币（4 帧旋转）/ 爱心 / 宝石
# --------------------------------------------------------------------------
COIN_0 = [
    "................",
    "................",
    ".....KKKKKK.....",
    "....KYYYYYYK....",
    "...KYYWWYYYYK...",
    "...KYYWWYYYYK...",
    "...KYYWWYYYYK...",
    "...KYYWWYYYYK...",
    "...KYYWWYYYYK...",
    "...KYYWWYYYYK...",
    "...KYYWWYYYYK...",
    "...KYYWWYYYYK...",
    "....KYYYYYYK....",
    ".....KKKKKK.....",
    "................",
    "................",
]
COIN_1 = [
    "................",
    "................",
    "......KKKK......",
    ".....KYYYYK.....",
    ".....KYWWYK.....",
    ".....KYWWYK.....",
    ".....KYWWYK.....",
    ".....KYWWYK.....",
    ".....KYWWYK.....",
    ".....KYWWYK.....",
    ".....KYWWYK.....",
    ".....KYWWYK.....",
    ".....KYYYYK.....",
    "......KKKK......",
    "................",
    "................",
]
COIN_2 = [
    "................",
    "................",
    ".......KK.......",
    ".......KYK......",
    ".......KYK......",
    ".......KYK......",
    ".......KYK......",
    ".......KYK......",
    ".......KYK......",
    ".......KYK......",
    ".......KYK......",
    ".......KYK......",
    ".......KYK......",
    ".......KK.......",
    "................",
    "................",
]
COIN_3 = [
    "................",
    "................",
    "......KKKK......",
    ".....KYYYYK.....",
    ".....KYYWYK.....",
    ".....KYYWYK.....",
    ".....KYYWYK.....",
    ".....KYYWYK.....",
    ".....KYYWYK.....",
    ".....KYYWYK.....",
    ".....KYYWYK.....",
    ".....KYYWYK.....",
    ".....KYYYYK.....",
    "......KKKK......",
    "................",
]

HEART = [
    "................",
    "................",
    "...KKK...KKK....",
    "..KUUUK.KUUUK...",
    ".KUUUUUKUUUUUK..",
    ".KUUUUUUUUUUUK..",
    ".KUUUUUUUUUUUK..",
    ".KuUUUUUUUUUuK..",
    "..KuUUUUUUUuK...",
    "...KuUUUUUuK....",
    "....KuUUUuK.....",
    ".....KuUuK......",
    "......KuK.......",
    ".......K........",
    "................",
    "................",
]

GEM = [
    "................",
    "................",
    "......KKKK......",
    ".....KXXXXK.....",
    "....KXXWWXXK....",
    "...KXXXWWXXXK...",
    "...KXXXXXXXXK...",
    "...KxXXXXXXxK...",
    "....KxXXXXxK....",
    ".....KxXXxK.....",
    "......KxxK......",
    ".......KK.......",
    "................",
    "................",
    "................",
    "................",
]

SPARK = [
    "................",
    "................",
    "................",
    "................",
    "................",
    ".......WW.......",
    "......WWWW......",
    ".....WWWWWW.....",
    "......WWWW......",
    ".......WW.......",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
]


# --------------------------------------------------------------------------
# 图集
# --------------------------------------------------------------------------
class Atlas:
    """把所有小图拼成一张大 Surface，用名字取矩形。"""

    PAD = 1

    def __init__(self, entries: Iterable[tuple[str, Sequence[str], int, int]]) -> None:
        items: list[tuple[str, pygame.Surface, int, int]] = []
        for name, ram, cw, ch in entries:
            s = surf_from_ram(ram)
            if s.get_size() != (cw, ch):  # 自动裁齐，避免作者手误
                fixed = pygame.Surface((cw, ch), pygame.SRCALPHA)
                fixed.blit(s, (0, 0))
                s = fixed
            items.append((name, s, cw, ch))

        cols = 8
        rows = (len(items) + cols - 1) // cols
        cell_w = max(cw for _, _, cw, _ in items)
        cell_h = max(ch for _, _, _, ch in items)
        w = cols * (cell_w + self.PAD) + self.PAD
        h = rows * (cell_h + self.PAD) + self.PAD
        self.sheet = pygame.Surface((w, h), pygame.SRCALPHA)
        self.rects: dict[str, pygame.Rect] = {}
        for i, (name, s, cw, ch) in enumerate(items):
            cx = i % cols
            cy = i // cols
            x = self.PAD + cx * (cell_w + self.PAD)
            y = self.PAD + cy * (cell_h + self.PAD)
            self.sheet.blit(s, (x, y))
            self.rects[name] = pygame.Rect(x, y, cw, ch)

    def get(self, name: str) -> pygame.Surface:
        return self.sheet.subsurface(self.rects[name]).copy()

    def blit(self, target: pygame.Surface, name: str, x: int, y: int) -> None:
        target.blit(self.sheet, (x, y), self.rects[name])


def _entries() -> list[tuple[str, Sequence[str], int, int]]:
    e: list[tuple[str, Sequence[str], int, int]] = []
    e += [
        ("p_idle", _IDLE, PLAYER_W, PLAYER_H),
        ("p_run0", _RUN_A, PLAYER_W, PLAYER_H),
        ("p_run1", _IDLE, PLAYER_W, PLAYER_H),
        ("p_run2", _RUN_B, PLAYER_W, PLAYER_H),
        ("p_run3", _IDLE, PLAYER_W, PLAYER_H),
        ("p_jump", _JUMP, PLAYER_W, PLAYER_H),
        ("p_fall", _FALL, PLAYER_W, PLAYER_H),
        ("p_hurt", _HURT, PLAYER_W, PLAYER_H),
    ]
    e += [
        ("t_grass", T_GRASS, 16, 16),
        ("t_dirt", T_DIRT, 16, 16),
        ("t_stone", T_STONE, 16, 16),
        ("t_brick", T_BRICK, 16, 16),
        ("t_wood", T_WOOD, 16, 16),
        ("t_crate", T_CRATE, 16, 16),
        ("t_metal", T_METAL, 16, 16),
        ("t_platform", T_PLATFORM, 16, 16),
        ("t_spike", T_SPIKE, 16, 16),
        ("t_crystal", T_CRYSTAL, 16, 16),
        ("t_ladder", T_LADDER, 16, 16),
        ("t_door", T_DOOR, 16, 16),
        ("t_spring", T_SPRING, 16, 16),
        ("t_cloudblock", T_CLOUD_BLOCK, 16, 16),
        ("t_tree", T_TREE, 16, 16),
        ("t_torch", T_TORCH, 16, 16),
        ("e_slime0", E_SLIME_A, 16, 16),
        ("e_slime1", E_SLIME_B, 16, 16),
        ("e_bat0", E_BAT_A, 16, 16),
        ("e_bat1", E_BAT_B, 16, 16),
        ("e_walker0", E_WALKER_A, 16, 16),
        ("e_walker1", E_WALKER_B, 16, 16),
        ("i_coin0", COIN_0, 16, 16),
        ("i_coin1", COIN_1, 16, 16),
        ("i_coin2", COIN_2, 16, 16),
        ("i_coin3", COIN_3, 16, 16),
        ("i_heart", HEART, 16, 16),
        ("i_gem", GEM, 16, 16),
        ("i_spark", SPARK, 16, 16),
    ]
    return e


_atlas: Atlas | None = None


def build() -> Atlas:
    """构建图集（需要在 pygame.init / set_mode 之后调用）。"""
    global _atlas
    _atlas = Atlas(_entries())
    return _atlas


def atlas() -> Atlas:
    if _atlas is None:
        raise RuntimeError("图集尚未构建，请先调用 art.build()")
    return _atlas


# --------------------------------------------------------------------------
# 程序化背景
# --------------------------------------------------------------------------
def vertical_gradient(w: int, h: int, stops: Sequence[tuple[int, int, int]]) -> pygame.Surface:
    s = pygame.Surface((w, h))
    n = len(stops) - 1
    for y in range(h):
        t = y / max(1, h - 1) * n
        i = min(int(t), n - 1)
        f = t - i
        c0, c1 = stops[i], stops[i + 1]
        col = (
            int(c0[0] + (c1[0] - c0[0]) * f),
            int(c0[1] + (c1[1] - c0[1]) * f),
            int(c0[2] + (c1[2] - c0[2]) * f),
        )
        pygame.draw.line(s, col, (0, y), (w, y))
    return s


def starfield(w: int, h: int, rng: random.Random) -> pygame.Surface:
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for _ in range(int(w * h / 900)):
        x = rng.randrange(w)
        y = rng.randrange(0, int(h * 0.72))
        b = rng.choice([90, 130, 170, 210, 255])
        s.set_at((x, y), (b, b, min(255, b + 20), 255))
    return s


def cloud_sprite(rng: random.Random) -> pygame.Surface:
    w = rng.randint(26, 54)
    h = rng.randint(8, 14)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for _ in range(rng.randint(3, 6)):
        rw = rng.randint(int(w * 0.3), int(w * 0.6))
        rh = rng.randint(4, h - 1)
        x = rng.randint(0, max(0, w - rw))
        y = rng.randint(0, max(0, h - rh))
        pygame.draw.ellipse(s, (255, 255, 255, 255), (x, y, rw, rh))
    return s


def hill_layer(
    w: int,
    h: int,
    color: tuple[int, int, int],
    rng: random.Random,
    amplitude: int = 22,
    roughness: int = 3,
    trees: int = 0,
    tree_surf: pygame.Surface | None = None,
) -> pygame.Surface:
    """生成可无缝平铺的丘陵条带（左右边缘高度一致）。"""
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    base = h
    height = base - amplitude
    heights: list[int] = []
    step = max(2, w // 26)
    x = 0
    while x < w:
        nxt = x + step
        height += rng.randint(-roughness, roughness)
        height = max(4, min(base - 2, height))
        heights.append(height)
        x = nxt
    # 强制首尾闭合，保证平铺无缝
    heights[-1] = heights[0]

    pts: list[tuple[int, int]] = []
    x = 0
    for i, hh in enumerate(heights):
        pts.append((x, hh))
        nx = min(w, x + step)
        pts.append((nx, hh))
        x = nx
    poly = pts + [(w, h), (0, h)]
    pygame.draw.polygon(s, color, poly)

    # 边缘高光
    top = [(px, py) for px, py in pts]
    if len(top) > 1:
        light = (min(255, color[0] + 22), min(255, color[1] + 22), min(255, color[2] + 26))
        pygame.draw.lines(s, light, False, top, 1)

    if trees and tree_surf is not None:
        tw, th = tree_surf.get_size()
        for _ in range(trees):
            tx = rng.randrange(0, w)
            # 树站在丘陵轮廓线上，树根贴着坡面
            idx = min(len(pts) - 1, int(tx / max(1, step)))
            ty = pts[idx * 2 + 1][1] - th + 3
            s.blit(tree_surf, (tx, ty))
    return s


def cave_wall_tile(rng: random.Random, size: int = 16) -> pygame.Surface:
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    base = (34, 30, 46, 255)
    s.fill(base)
    for _ in range(rng.randint(6, 12)):
        x = rng.randrange(size)
        y = rng.randrange(size)
        c = rng.choice([(44, 38, 58, 255), (26, 22, 36, 255), (52, 44, 66, 255)])
        s.set_at((x, y), c)
    return s
