"""全局配置：屏幕、时间步、物理手感、颜色。

所有数值都是「像素 / 秒」或「像素 / 秒²」，方便直接调手感。
"""

# ---------- 屏幕 ----------
TILE = 16                 # 美术素材的原始像素尺寸
ZOOM = 3                  # 整数倍放大 -> 像素风不糊
VIEW_W, VIEW_H = 480, 270  # 逻辑分辨率（16:9）
WINDOW_W, WINDOW_H = VIEW_W * ZOOM, VIEW_H * ZOOM
CAPTION = "晨光跳跃 - Dawn Leap"
FPS = 60
FIXED_DT = 1.0 / 60.0

# ---------- 物理 ----------
GRAVITY = 900.0
MAX_FALL = 340.0

PLAYER_RUN_SPEED = 118.0
PLAYER_ACCEL = 900.0
PLAYER_AIR_ACCEL = 620.0
PLAYER_FRICTION = 1000.0
PLAYER_JUMP_VELOCITY = -232.0
JUMP_CUT_MULT = 0.48        # 松开跳跃键立即削减上升速度 -> 可变跳跃高度
COYOTE_TIME = 0.10          # 离开平台后仍可起跳的宽容时间
JUMP_BUFFER = 0.12          # 落地前提前按跳的缓冲时间
MAX_JUMPS = 2               # 二段跳
STOMP_BOUNCE = -196.0       # 踩敌人后的弹起
STOMP_BOUNCE_HELD = -252.0  # 踩敌人时按住跳跃键弹得更高
SPRING_VELOCITY = -330.0

PLAYER_W, PLAYER_H = 10, 14  # 碰撞盒（比贴图小，手感更宽厚）
PLAYER_MAX_HP = 3
INVULN_TIME = 1.4
KNOCKBACK_X = 96.0
KNOCKBACK_Y = -150.0
HAZARD_DAMAGE = 1

ENEMY_GRAVITY = 780.0
SLIME_SPEED = 26.0
WALKER_SPEED = 44.0
BAT_SPEED = 40.0

# ---------- 表现 ----------
CAMERA_LERP = 8.0           # 越大跟得越紧
CAMERA_LOOK_AHEAD = 22.0    # 朝向前方的预览距离
SQUASH_RECOVER = 9.0

# ---------- 调色板 ----------
C_SKY_TOP = (34, 26, 56)
C_SKY_MID = (86, 74, 132)
C_SKY_LOW = (232, 148, 118)
C_SKY_HORIZON = (250, 208, 150)
C_HILL_FAR = (150, 104, 130)
C_HILL_MID = (108, 80, 118)
C_HILL_NEAR = (72, 58, 98)
C_CLOUD = (250, 226, 214)
C_CAVE_TOP = (18, 16, 28)
C_CAVE_LOW = (40, 34, 54)
C_CAVE_HILL = (26, 22, 38)
C_WHITE = (255, 255, 255)
C_BLACK = (18, 14, 22)
C_TEXT = (246, 241, 232)
C_TEXT_DIM = (168, 158, 176)
C_ACCENT = (250, 206, 92)
C_DANGER = (232, 90, 96)
C_OK = (128, 214, 132)

# 主题：不同关卡用不同的天空 / 远景配色
THEMES = {
    "dawn": {
        "sky": [(34, 26, 56), (86, 74, 132), (186, 116, 140), (232, 148, 118), (250, 208, 150)],
        "hills": [(150, 104, 130), (108, 80, 118), (72, 58, 98)],
        "clouds": (250, 226, 214),
        "star": True,
    },
    "cave": {
        "sky": [(16, 14, 28), (26, 22, 42), (36, 30, 52), (50, 42, 64)],
        "hills": [(46, 40, 62), (34, 29, 48), (24, 21, 36)],
        "clouds": (60, 52, 78),
        "star": False,
    },
    "night": {
        "sky": [(10, 12, 32), (20, 24, 56), (40, 46, 88), (70, 76, 124)],
        "hills": [(34, 36, 70), (24, 26, 54), (16, 18, 38)],
        "clouds": (196, 200, 226),
        "star": True,
    },
}
