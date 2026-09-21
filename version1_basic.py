# -*- coding: utf-8 -*-
"""
一箭又一箭 · 基础版（第一次提交）
================================================
一款点击式箭头解谜小游戏，使用 Python + Pygame 开发。

规则：
    棋盘上每个格子最多有一个箭头（上/下/左/右四种方向）。
    点击箭头后，程序检查它前进方向上、到棋盘边界之间还有没有别的箭头：
        · 没有阻挡 -> 箭头飞出去并消失
        · 有阻挡   -> 箭头不能消失，会抖动变红并弹出提示，同时扣掉一次失误机会
    失误次数（爱心）耗尽则本关失败；清空全部箭头则通关。

运行： python version1_basic.py
"""

import math
import random
import sys

import pygame

# ============================================================================
# 一、基础配置
# ============================================================================

WIN_W, WIN_H = 480, 800
FPS = 60

TOP_H = 132                       # 顶部信息栏高度
BOTTOM_H = 148                    # 底部操作栏高度
BOARD_AREA = pygame.Rect(0, TOP_H, WIN_W, WIN_H - TOP_H - BOTTOM_H)

# ---- 配色（取自参考截图的风格：紫罗兰底 + 白色棋盘 + 深藏青箭头 + 玫红强调）----
C_BG_TOP = (146, 140, 236)        # 背景紫（上）
C_BG_BOT = (124, 118, 224)        # 背景紫（下）
C_BG_PATTERN = (163, 157, 244)    # 背景上的浅色装饰图案
C_WHITE = (255, 255, 255)
C_BOARD = (255, 255, 255)
C_DOT = (203, 206, 220)           # 棋盘上的点阵
C_INK = (43, 47, 74)              # 深藏青（箭头主色 / 正文）
C_INK_SOFT = (120, 125, 150)
C_RED = (245, 71, 92)             # 玫红（碰撞反馈 / 爱心）
C_RED_DARK = (110, 34, 54)        # 失去的爱心
C_GREEN = (79, 201, 79)           # 主按钮绿
C_GREEN_DARK = (53, 160, 53)
C_BLUE = (78, 143, 224)           # 标题描边蓝
C_YELLOW = (255, 209, 92)
C_ORANGE = (255, 160, 60)


def vgradient(size, top, bottom):
    """生成一张竖直渐变的小图（缓存在调用方）。"""
    w, h = size
    surf = pygame.Surface((1, h))
    for y in range(h):
        k = y / max(1, h - 1)
        surf.set_at((0, y), (int(top[0] + (bottom[0] - top[0]) * k),
                             int(top[1] + (bottom[1] - top[1]) * k),
                             int(top[2] + (bottom[2] - top[2]) * k)))
    return pygame.transform.scale(surf, (w, h))


# ============================================================================
# 二、文字 / 图形小工具
# ============================================================================

_FONT_PATHS = [
    "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]
_font_cache = {}
_text_cache = {}


def get_font(size, bold=False):
    """按尺寸取字体。优先用系统中文字体，找不到就退回默认字体（避免中文变方块）。"""
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    font = None
    candidates = _FONT_PATHS[::1] if bold else _FONT_PATHS
    for path in candidates:
        try:
            font = pygame.font.Font(path, size)
            break
        except (OSError, FileNotFoundError):
            continue
    if font is None:
        font = pygame.font.SysFont("microsoftyaheui,simhei,arial", size, bold=bold)
    _font_cache[key] = font
    return font


def render_text(text, size, color, bold=False, outline=None, outline_w=2,
                shadow=None, shadow_off=(0, 3)):
    """渲染带描边 / 阴影的文字，结果做缓存（同一段文字只渲染一次）。"""
    key = (text, size, color, bold, outline, outline_w, shadow, shadow_off)
    if key in _text_cache:
        return _text_cache[key]
    font = get_font(size, bold)
    base = font.render(text, True, color)
    w, h = base.get_size()
    pad = (outline_w + abs(shadow_off[0]) + 2) if outline else 2
    pad_y = (outline_w + abs(shadow_off[1]) + 2) if outline else 2
    surf = pygame.Surface((w + pad * 2, h + pad_y * 2 + 4), pygame.SRCALPHA)
    if shadow is not None:
        sh = font.render(text, True, shadow)
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            surf.blit(sh, (pad + shadow_off[0] + dx, pad_y + shadow_off[1] + dy))
    if outline is not None:
        out = font.render(text, True, outline)
        for dx in range(-outline_w, outline_w + 1):
            for dy in range(-outline_w, outline_w + 1):
                if dx * dx + dy * dy <= outline_w * outline_w:
                    surf.blit(out, (pad + dx, pad_y + dy))
    surf.blit(base, (pad, pad_y))
    _text_cache[key] = surf
    return surf


def draw_text(surf, text, size, color, center=None, topleft=None, **kw):
    s = render_text(text, size, color, **kw)
    rect = s.get_rect()
    if center:
        rect.center = center
    elif topleft:
        rect.topleft = topleft
    surf.blit(s, rect)
    return rect


def draw_round_rect(surf, rect, color, radius, width=0):
    pygame.draw.rect(surf, color, rect, width, border_radius=int(radius))


def draw_panel(surf, rect, color, radius, border=None, border_w=3, shadow=True):
    """带底部厚度和阴影的圆角面板，是参考图里按钮的那种立体感。"""
    if shadow:
        sh = pygame.Surface((rect.w + 20, rect.h + 20), pygame.SRCALPHA)
        draw_round_rect(sh, pygame.Rect(10, 12, rect.w, rect.h), (60, 50, 130, 60), radius)
        surf.blit(sh, (rect.x - 10, rect.y - 10))
    if border:
        draw_round_rect(surf, rect.inflate(border_w * 2, border_w * 2), border, radius + border_w)
    draw_round_rect(surf, rect, color, radius)


def draw_heart(surf, center, size, color, outline=None):
    """用爱心参数方程画一颗饱满的心（比两个圆加三角形好看）。"""
    cx, cy = center
    pts = []
    for i in range(40):
        t = 2 * math.pi * i / 40
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * size / 32.0, cy - y * size / 32.0))
    pygame.draw.polygon(surf, color, pts)
    if outline:
        pygame.draw.polygon(surf, outline, pts, 2)


def draw_star(surf, center, size, color, points=5):
    cx, cy = center
    pts = []
    for i in range(points * 2):
        r = size if i % 2 == 0 else size * 0.45
        a = -math.pi / 2 + i * math.pi / points
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pygame.draw.polygon(surf, color, pts)


def draw_chevron_left(surf, center, size, color, width=4):
    cx, cy = center
    pygame.draw.lines(surf, color, False,
                      [(cx + size * 0.4, cy - size * 0.7),
                       (cx - size * 0.4, cy),
                       (cx + size * 0.4, cy + size * 0.7)], width)


def render_gradient_text(text, size, top_color, bottom_color, bold=True,
                         outline=None, outline_w=3, shadow=None, shadow_off=(0, 4)):
    """渐变填充 + 描边 + 投影的标题字（参考图里那种糖果立体字）。

    关键点：渐变只能染在"字身"上，不能染到描边和投影上，
    所以先把描边+投影合成一层，再用"白字蒙版 × 竖直渐变"合成字身层，最后叠起来。
    """
    layer = render_text(text, size, C_WHITE, bold=bold, outline=outline,
                        outline_w=outline_w, shadow=shadow, shadow_off=shadow_off)
    mask = get_font(size, bold).render(text, True, C_WHITE)
    grad = vgradient(mask.get_size(), top_color, bottom_color)
    mask = mask.copy()
    mask.blit(grad, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    pad = outline_w + abs(shadow_off[0]) + 2 if outline else 2
    pad_y = outline_w + abs(shadow_off[1]) + 2 if outline else 2
    out = layer.copy()
    out.blit(mask, (pad, pad_y))
    return out


def draw_icon(surf, kind, center, r, color):
    """按钮里的小图标，统一以 center 为中心、r 为半径来画。"""
    cx, cy = center
    if kind == "play":
        pygame.draw.polygon(surf, color, [(cx - r * 0.55, cy - r * 0.8),
                                          (cx - r * 0.55, cy + r * 0.8),
                                          (cx + r * 0.75, cy)])
    elif kind == "loop":
        pygame.draw.arc(surf, color, pygame.Rect(cx - r, cy - r, 2 * r, 2 * r), 0.7, 5.5, 3)
        pygame.draw.polygon(surf, color, [(cx + r * 0.95, cy - r * 0.95),
                                          (cx + r * 1.15, cy - r * 0.05),
                                          (cx + r * 0.35, cy - r * 0.4)])


def draw_button(surf, rect, fill, text, text_color=C_WHITE, radius=None,
                edge=None, border=None, border_w=3, size=26, icon=None):
    """立体感圆角按钮：底下垫一层深色当厚度，上面盖按钮面，再加白描边。
    图标和文字先量好宽度再整体居中，免得手动凑偏移量。"""
    radius = radius if radius is not None else min(rect.h // 2, 22)
    edge = edge or tuple(max(0, c - 45) for c in fill)
    if border:
        draw_round_rect(surf, pygame.Rect(rect.x - border_w, rect.y - border_w + 6,
                                          rect.w + border_w * 2, rect.h + border_w * 2),
                        border, radius + border_w)
    draw_round_rect(surf, pygame.Rect(rect.x, rect.y + 6, rect.w, rect.h), edge, radius)
    draw_round_rect(surf, rect, fill, radius)
    tw = get_font(size, True).size(text)[0] if text else 0
    iw = 30 if icon else 0
    gap = 10 if (icon and text) else 0
    x = rect.centerx - (tw + iw + gap) // 2
    if icon:
        draw_icon(surf, icon, (x + iw // 2, rect.centery), 12, text_color)
    if text:
        draw_text(surf, text, size, text_color, center=(x + iw + gap + tw // 2, rect.centery),
                  bold=True, shadow=edge if fill != C_WHITE else None, shadow_off=(0, 2))


# ============================================================================
# 三、箭头绘制
# ============================================================================

DIR_VEC = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
# 规范方向：先把箭头画成"朝右"，其它方向靠旋转得到
DIR_ANGLE = {"R": 0, "U": 90, "L": 180, "D": 270}
CHAR_DIR = {"^": "U", "v": "D", "<": "L", ">": "R", "U": "U", "D": "D", "L": "L", "R": "R"}

_arrow_cache = {}


def _build_arrow(cell, color, fade=0.55):
    """画一个"朝右"的箭头：粗圆头箭杆 + 大三角箭头，箭尾渐变淡出（参考图的效果）。

    做法：先在一个蒙版上画出整支箭头的白色剪影，
          再和一张"横向透明度渐变图"做 BLEND_RGBA_MULT 相乘，
          最后用同样的方式染上颜色。整支箭只需要算一次，之后缓存复用。
    """
    S = cell
    mask = pygame.Surface((S, S), pygame.SRCALPHA)

    pad = S * 0.10
    cy = S / 2.0
    x_tail, x_tip = pad, S - pad
    head_len = S * 0.30
    head_w = S * 0.58
    shaft_w = S * 0.23
    x_head = x_tip - head_len

    # 箭杆（一条粗线 + 圆头，尾巴用圆头才不会有尖角）
    pygame.draw.line(mask, (255, 255, 255, 255), (x_tail, cy), (x_head, cy), int(shaft_w))
    pygame.draw.circle(mask, (255, 255, 255, 255), (int(x_tail), int(cy)), int(shaft_w / 2))
    # 箭头（三角形）
    pygame.draw.polygon(mask, (255, 255, 255, 255),
                        [(x_tip, cy), (x_head, cy - head_w / 2), (x_head, cy + head_w / 2)])

    # 横向渐变：箭尾最淡，箭头处最实
    grad = pygame.Surface((S, S), pygame.SRCALPHA)
    for x in range(S):
        k = (x - x_tail) / max(1.0, x_tip - x_tail)
        k = min(1.0, max(0.0, k))
        alpha = int(255 * (fade + (1 - fade) * (k ** 1.4)))
        pygame.draw.line(grad, (255, 255, 255, alpha), (x, 0), (x, S))

    mask.blit(grad, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)   # 让剪影带上渐变透明度
    tint = pygame.Surface((S, S), pygame.SRCALPHA)
    tint.fill(color + (255,))
    tint.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)   # 染成目标颜色
    return tint


def get_arrow_sprite(cell, direction, color, fade=0.55):
    key = (cell, direction, color, round(fade, 2))
    if key not in _arrow_cache:
        base = _build_arrow(cell, color, fade)
        angle = DIR_ANGLE[direction]
        _arrow_cache[key] = pygame.transform.rotate(base, angle) if angle else base
    return _arrow_cache[key]


# ============================================================================
# 四、关卡数据
# ============================================================================
# 每个关卡用一个字符串列表表示，U/D/L/R 表示箭头方向，"." 表示空格。
# 这些关卡由 tools/gen_levels.py 用"逆推构造法"生成，
# 生成时就已经保证了必定存在通关顺序，并逐关用程序验证过。

LEVELS = [
    {
        "name": "第 1 关",
        "grid": [
            ".R.D",
            "RU..",
            "...L",
        ],
    },
    {
        "name": "第 2 关",
        "grid": [
            ".R..U",
            "L..L.",
            ".UR.U",
            "....U",
        ],
    },
    {
        "name": "第 3 关",
        "grid": [
            "LRR.U.",
            "DL...L",
            "DL.L..",
            "......",
        ],
    },
]

MAX_LIVES = 3


# ============================================================================
# 五、游戏逻辑
# ============================================================================

class Arrow:
    """棋盘上的一个箭头。x/y 是格子坐标（列/行）。"""

    def __init__(self, x, y, direction):
        self.x, self.y = x, y
        self.dir = direction
        self.alive = True
        self.spawn = 0.0          # 入场动画进度
        self.shake = 0.0          # 碰撞抖动剩余时间
        self.flash = 0.0          # 碰撞变红剩余时间

    @property
    def vec(self):
        return DIR_VEC[self.dir]


class Flying:
    """一个正在飞出棋盘的箭头（纯表现层，不影响逻辑）。"""

    def __init__(self, x, y, direction, cell):
        self.x, self.y = float(x), float(y)
        self.dir = direction
        self.cell = cell
        self.t = 0.0
        self.trail = []


class Toast:
    """屏幕上飘一下就消失的小提示文字。"""

    def __init__(self, text, pos, color, size=22, life=0.9):
        self.text, self.pos, self.color, self.size = text, pos, color, size
        self.t, self.life = 0.0, life


class Game:
    def __init__(self):
        self.scene = "menu"           # menu / play / win / lose
        self.level_index = 0
        self.level = None
        self.arrows = []
        self.flies = []
        self.toasts = []
        self.lives = MAX_LIVES
        self.time_used = 0.0
        self.gate = 0.0               # 入场动画的总时长
        self.running = True
        self.buttons = []             # 每帧重建的可点击区域
        self.board_rect = pygame.Rect(0, 0, 0, 0)
        self.cell = 80
        self._bg = None
        self._menu_bg = None
        self._top_grad = None
        self._bottom_grad = None

    # ---------------- 关卡 ----------------
    def load_level(self, index):
        self.level_index = index % len(LEVELS)
        data = LEVELS[self.level_index]
        grid = data["grid"]
        self.grid_w, self.grid_h = len(grid[0]), len(grid)
        self.arrows = []
        self.flies.clear()
        self.toasts.clear()
        self.lives = MAX_LIVES
        self.time_used = 0.0
        order = 0
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch in CHAR_DIR:
                    a = Arrow(x, y, CHAR_DIR[ch])
                    a.spawn = -order * 0.035      # 依次弹出的错峰
                    self.arrows.append(a)
                    order += 1
        self.gate = order * 0.035 + 0.45
        self.scene = "play"

    def restart(self):
        self.load_level(self.level_index)

    @property
    def remain(self):
        return sum(1 for a in self.arrows if a.alive)

    def arrow_at(self, x, y):
        for a in self.arrows:
            if a.alive and a.x == x and a.y == y:
                return a
        return None

    def blocked_by(self, arrow):
        """路径检测：从箭头所在格出发，沿它的方向一步一步走到棋盘边界，
        路上只要遇到另一个还活着的箭头，就是被挡住了。"""
        dx, dy = arrow.vec
        cx, cy = arrow.x + dx, arrow.y + dy
        while 0 <= cx < self.grid_w and 0 <= cy < self.grid_h:
            other = self.arrow_at(cx, cy)
            if other is not None:
                return other
            cx += dx
            cy += dy
        return None          # 一路走到边界都没东西 -> 可以飞出去

    # ---------------- 交互 ----------------
    def click(self, pos):
        if self.scene == "menu":
            if self.btn("start").collidepoint(pos):
                self.load_level(0)
            return
        # 顶部左上角的返回按钮在任何界面都有效
        if self.btn("home").collidepoint(pos):
            self.scene = "menu"
            return
        if self.scene == "play":
            if self.btn("restart").collidepoint(pos):
                self.restart()
                return
            if not BOARD_AREA.collidepoint(pos):
                return
            gx = int((pos[0] - self.board_rect.x) // self.cell)
            gy = int((pos[1] - self.board_rect.y) // self.cell)
            if 0 <= gx < self.grid_w and 0 <= gy < self.grid_h:
                a = self.arrow_at(gx, gy)
                if a is not None and a.spawn >= 0:     # spawn<0 表示还没轮到它出场
                    self.try_fly(a)
            return
        if self.scene == "win":
            if self.btn("next").collidepoint(pos):
                if self.level_index + 1 < len(LEVELS):
                    self.load_level(self.level_index + 1)
                else:
                    self.scene = "menu"
            elif self.btn("back").collidepoint(pos):
                self.scene = "menu"
            return
        if self.scene == "lose":
            if self.btn("retry").collidepoint(pos):
                self.restart()
            elif self.btn("back").collidepoint(pos):
                self.scene = "menu"

    def try_fly(self, arrow):
        """点到一个箭头：先判断能不能飞，再分别处理。"""
        blocker = self.blocked_by(arrow)
        if blocker is not None:
            # ---- 被挡住：抖动 + 变红 + 文字提示 + 扣一次失误 ----
            arrow.shake = 0.45
            arrow.flash = 0.7
            self.lives -= 1
            tx, ty = self.cell_center(arrow.x, arrow.y, -0.55)
            ty = max(ty, BOARD_AREA.y + 26)        # 别让提示飘到画面外面去
            self.toasts.append(Toast("被挡住了！", (tx, ty), C_RED, 20))
            if self.lives <= 0:
                self.lives = 0
                self.scene = "lose"
            return
        # ---- 没有阻挡：立刻从棋盘逻辑上移除，然后播放飞出动画 ----
        arrow.alive = False
        self.flies.append(Flying(arrow.x, arrow.y, arrow.dir, self.cell))
        if self.remain == 0:
            self.scene = "win"

    def cell_center(self, gx, gy, dy_cells=0.0):
        return (int(self.board_rect.x + (gx + 0.5) * self.cell),
                int(self.board_rect.y + (gy + 0.5 + dy_cells) * self.cell))

    def btn(self, name):
        for n, r in self.buttons:
            if n == name:
                return r
        return pygame.Rect(-999, -999, 0, 0)

    # ---------------- 更新 ----------------
    def update(self, dt):
        if self.scene == "play":
            self.time_used += dt
        for a in self.arrows:
            if a.spawn < 0:
                a.spawn = min(0.0, a.spawn + dt)
            elif a.spawn < 1.0:
                a.spawn = min(1.0, a.spawn + dt * 3.2)
            if a.shake > 0:
                a.shake = max(0.0, a.shake - dt)
            if a.flash > 0:
                a.flash = max(0.0, a.flash - dt)
        for f in self.flies:
            f.t += dt
            f.trail.append((f.x, f.y, 1.0))
            f.trail = [(tx, ty, ta - dt * 4.5) for tx, ty, ta in f.trail if ta - dt * 4.5 > 0]
            speed = 6 + 26 * (f.t ** 1.7)          # 起步慢、越来越快
            f.x += DIR_VEC[f.dir][0] * speed * dt
            f.y += DIR_VEC[f.dir][1] * speed * dt
        self.flies = [f for f in self.flies if f.t < 0.55]
        for t in self.toasts:
            t.t += dt
        self.toasts = [t for t in self.toasts if t.t < t.life]

    # ---------------- 绘制 ----------------
    def background(self, surf):
        if self._bg is None:
            self._bg = vgradient((WIN_W, WIN_H), C_BG_TOP, C_BG_BOT)
        surf.blit(self._bg, (0, 0))

    def menu_background(self, surf):
        """开始界面：紫色底 + 淡淡的箭头/星星/云朵图案（模仿参考图的背景装饰）。"""
        if self._menu_bg is None:
            bg = vgradient((WIN_W, WIN_H), (150, 144, 240), (116, 110, 218))
            rng = random.Random(2026)
            deco = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
            for _ in range(26):
                x, y = rng.randint(0, WIN_W), rng.randint(0, WIN_H)
                kind = rng.choice(["star", "star", "cloud", "arrow", "bolt"])
                if kind == "star":
                    draw_star(deco, (x, y), rng.randint(8, 18), C_BG_PATTERN + (150,))
                elif kind == "cloud":
                    for k in range(3):
                        pygame.draw.circle(deco, C_BG_PATTERN + (110,),
                                           (x + k * 14 - 14, y + (k % 2) * 4 - 2), 13)
                elif kind == "arrow":
                    s = pygame.transform.rotate(get_arrow_sprite(54, "R", C_BG_PATTERN, 0.8),
                                                rng.choice([0, 90, 180, 270, 45, 135]))
                    s.set_alpha(60)
                    deco.blit(s, (x, y))
                else:
                    pygame.draw.polygon(deco, C_BG_PATTERN + (120,),
                                        [(x, y), (x - 9, y + 18), (x + 2, y + 16),
                                         (x - 3, y + 32), (x + 11, y + 11), (x - 1, y + 13)])
            bg.blit(deco, (0, 0))
            self._menu_bg = bg
        surf.blit(self._menu_bg, (0, 0))

    # ---- 开始界面 ----
    def draw_menu(self, surf):
        self.menu_background(surf)
        cx = WIN_W // 2

        # 标题：渐变填充 + 蓝色描边 + 深色投影（模仿参考图的立体字）
        title = render_gradient_text("一箭又一箭", 62, (255, 248, 214), (255, 172, 54),
                                     outline=C_BLUE, outline_w=5,
                                     shadow=(60, 70, 150), shadow_off=(0, 6))
        surf.blit(title, title.get_rect(center=(cx, 250)))

        # 两支橙色小箭头穿过标题（呼应参考图的 logo）
        a1 = pygame.transform.rotate(get_arrow_sprite(64, "R", C_ORANGE, 0.85), -32)
        surf.blit(a1, a1.get_rect(center=(cx + 132, 208)))
        a2 = pygame.transform.rotate(get_arrow_sprite(56, "R", C_ORANGE, 0.85), 150)
        surf.blit(a2, a2.get_rect(center=(cx - 142, 300)))

        draw_text(surf, "点击箭头，让它们按顺序飞出去", 20, (238, 236, 255),
                  center=(cx, 352))

        # 开始游戏按钮
        r = pygame.Rect(0, 0, 260, 74)
        r.center = (cx, 470)
        draw_button(surf, r, C_GREEN, "开始游戏", size=30, icon="play",
                    edge=C_GREEN_DARK, border=C_WHITE)

        label = pygame.Rect(0, 0, 140, 40)
        label.center = (cx, r.bottom + 34)
        draw_panel(surf, label, C_WHITE, 12, shadow=False)
        draw_text(surf, LEVELS[0]["name"], 22, C_INK, center=label.center, bold=True)
        self.buttons = [("start", r)]

        draw_text(surf, "共 %d 关 · 每关 %d 次机会" % (len(LEVELS), MAX_LIVES), 18,
                  (226, 224, 252), center=(cx, WIN_H - 70))
        draw_text(surf, "Python + Pygame 课程作业", 16, (206, 202, 244),
                  center=(cx, WIN_H - 44))

    # ---- 顶部信息栏 ----
    def draw_topbar(self, surf):
        if self._top_grad is None:                 # 渐变条只算一次，之后每帧直接贴
            self._top_grad = vgradient((WIN_W, TOP_H + 20), (150, 144, 240), (132, 126, 230))
        surf.blit(self._top_grad, (0, 0))
        cx = WIN_W // 2

        draw_text(surf, LEVELS[self.level_index]["name"], 34, C_WHITE,
                  center=(cx, 30), bold=True, shadow=(74, 68, 150), shadow_off=(0, 3))
        # 爱心 = 剩余失误次数
        for i in range(MAX_LIVES):
            alive = i < self.lives
            draw_heart(surf, (cx - 44 + i * 44, 74), 17,
                       C_RED if alive else C_RED_DARK,
                       outline=(198, 46, 70) if alive else None)
        # 计时
        m, s = divmod(int(self.time_used), 60)
        pygame.draw.circle(surf, (238, 238, 250), (cx - 34, 106), 9, 2)
        pygame.draw.line(surf, (238, 238, 250), (cx - 34, 106), (cx - 34, 100), 2)
        pygame.draw.line(surf, (238, 238, 250), (cx - 34, 106), (cx - 29, 106), 2)
        draw_text(surf, "%dm%02ds" % (m, s), 21, (245, 245, 255),
                  center=(cx + 12, 106), bold=True)

        # 左上角：返回主菜单
        back = pygame.Rect(18, 22, 46, 46)
        pygame.draw.circle(surf, (255, 255, 255), back.center, 23)
        draw_chevron_left(surf, back.center, 12, C_INK, 4)

        # 右上角：剩余箭头数
        badge = pygame.Rect(WIN_W - 106, 22, 88, 46)
        draw_panel(surf, badge, C_WHITE, 23, shadow=False)
        mini = get_arrow_sprite(30, "R", C_INK, 0.7)
        surf.blit(mini, mini.get_rect(center=(badge.x + 26, badge.centery)))
        draw_text(surf, str(self.remain), 26, C_INK, center=(badge.x + 60, badge.centery),
                  bold=True)
        draw_text(surf, "剩余箭头", 14, (232, 230, 252), center=(badge.centerx, badge.bottom + 14))

        self.buttons.append(("home", back))

    # ---- 棋盘 ----
    def draw_board(self, surf):
        # 根据关卡大小算格子边长，让棋盘居中
        max_w, max_h = BOARD_AREA.w - 56, BOARD_AREA.h - 60
        cell = int(min(max_w / self.grid_w, max_h / self.grid_h, 96))
        self.cell = cell
        bw, bh = cell * self.grid_w, cell * self.grid_h
        rect = pygame.Rect(0, 0, bw, bh)
        rect.center = BOARD_AREA.center
        self.board_rect = rect

        pygame.draw.rect(surf, C_BOARD, BOARD_AREA.inflate(0, 40))
        # 棋盘底衬
        card = rect.inflate(46, 46)
        sh = pygame.Surface((card.w + 24, card.h + 24), pygame.SRCALPHA)
        draw_round_rect(sh, pygame.Rect(12, 14, card.w, card.h), (70, 62, 140, 45), 26)
        surf.blit(sh, (card.x - 12, card.y - 12))
        draw_round_rect(surf, card, (250, 250, 254), 26, width=2)

        # 点阵（每个格子的十字交点上都点一个小圆点）
        for gy in range(self.grid_h + 1):
            for gx in range(self.grid_w + 1):
                pygame.draw.circle(surf, C_DOT,
                                   (rect.x + gx * cell, rect.y + gy * cell), 3)

        # 箭头
        for a in self.arrows:
            if not a.alive:
                continue
            if a.spawn < 0:
                continue
            self.draw_arrow(surf, a)
        # 正在飞出的箭头（带拖尾）
        for f in self.flies:
            self.draw_flying(surf, f)

    def draw_arrow(self, surf, a):
        c = self.cell
        color = C_INK
        if a.flash > 0:
            # 碰撞后闪红：在深藏青和玫红之间来回
            k = abs(math.sin(a.flash * 22))
            color = tuple(int(C_INK[i] + (C_RED[i] - C_INK[i]) * k) for i in range(3))
        sp = get_arrow_sprite(c, a.dir, color)
        cx, cy = self.cell_center(a.x, a.y)
        # 入场：从小到大弹出来
        k = max(0.0, min(1.0, a.spawn))
        if k < 1.0:
            e = 1 - (1 - k) ** 3
            scale = 0.55 + 0.45 * e + 0.12 * math.sin(e * math.pi)
            size = max(2, int(c * scale))
            sp = pygame.transform.smoothscale(sp, (size, size))
        # 碰撞：垂直于自身方向来回抖动
        if a.shake > 0:
            off = math.sin(a.shake * 42) * 10 * (a.shake / 0.45)
            dx, dy = DIR_VEC[a.dir]
            cx += int(-dy * off)
            cy += int(dx * off)
        surf.blit(sp, sp.get_rect(center=(cx, cy)))

    def draw_flying(self, surf, f):
        c = self.cell
        base = self.board_rect.x + (f.x + 0.5) * c, self.board_rect.y + (f.y + 0.5) * c
        sp = get_arrow_sprite(c, f.dir, C_INK)
        # 拖尾：几个逐渐变淡的残影
        for i, (tx, ty, ta) in enumerate(f.trail):
            if i % 2:
                continue
            g = sp.copy()
            g.fill((255, 255, 255, int(70 * ta)), None, pygame.BLEND_RGBA_MULT)
            surf.blit(g, g.get_rect(center=(self.board_rect.x + (tx + 0.5) * c,
                                            self.board_rect.y + (ty + 0.5) * c)))
        ghost = sp.copy()
        ghost.fill((255, 255, 255, max(0, int(255 * (1 - f.t / 0.55)))), None,
                   pygame.BLEND_RGBA_MULT)
        surf.blit(ghost, ghost.get_rect(center=base))

    # ---- 底部操作栏 ----
    def draw_bottombar(self, surf):
        y = WIN_H - BOTTOM_H
        if self._bottom_grad is None:
            self._bottom_grad = vgradient((WIN_W, BOTTOM_H + 20), (132, 126, 230),
                                          (118, 112, 220))
        surf.blit(self._bottom_grad, (0, y))
        r = pygame.Rect(0, 0, 220, 58)
        r.center = (WIN_W // 2, y + 62)
        draw_button(surf, r, C_WHITE, "重新开始", text_color=C_INK, size=25, icon="loop")
        self.buttons.append(("restart", r))

        draw_text(surf, "点击箭头，前方没有阻挡就能飞出去", 16, (222, 220, 250),
                  center=(WIN_W // 2, y + 118))

    # ---- 通关 / 失败浮层 ----
    def draw_overlay(self, surf, title, title_color, subtitle, buttons, accent):
        scrim = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        scrim.fill((40, 34, 90, 150))
        surf.blit(scrim, (0, 0))

        card = pygame.Rect(0, 0, 340, 306)
        card.center = (WIN_W // 2, WIN_H // 2 - 20)
        draw_panel(surf, card, C_WHITE, 30)
        pill = pygame.Rect(0, 0, 96, 9)
        pill.center = (card.centerx, card.y + 26)
        draw_round_rect(surf, pill, accent, 5)
        draw_text(surf, title, 44, title_color, center=(card.centerx, card.y + 80), bold=True,
                  shadow=(210, 210, 225), shadow_off=(0, 3))
        draw_text(surf, subtitle, 20, C_INK_SOFT, center=(card.centerx, card.y + 130))

        rects = []
        for i, (label, name, color, text_color) in enumerate(buttons):
            r = pygame.Rect(0, 0, 230, 56)
            r.center = (card.centerx, card.y + 182 + i * 68)
            draw_button(surf, r, color, label, text_color=text_color, size=24,
                        border=C_WHITE if color != C_WHITE else (225, 227, 238))
            rects.append((name, r))
        return rects

    def draw(self, surf):
        self.buttons = []
        if self.scene == "menu":
            self.draw_menu(surf)
            return
        self.background(surf)
        self.draw_board(surf)
        self.draw_topbar(surf)
        self.draw_bottombar(surf)
        # 飘字提示
        for t in self.toasts:
            k = t.t / t.life
            s = render_text(t.text, t.size, t.color, bold=True, outline=C_WHITE, outline_w=2)
            s = s.copy()
            s.fill((255, 255, 255, int(255 * (1 - k))), None, pygame.BLEND_RGBA_MULT)
            surf.blit(s, s.get_rect(center=(t.pos[0], t.pos[1] - 26 * k)))
        if self.scene == "win":
            last = self.level_index == len(LEVELS) - 1
            m, s = divmod(int(self.time_used), 60)
            sub = "用时 %dm%02ds，剩余 %d 次机会" % (m, s, self.lives)
            btns = [("下一关" if not last else "返回主菜单", "next", C_GREEN, C_WHITE),
                    ("返回主菜单", "back", C_WHITE, C_INK)] if not last else \
                   [("返回主菜单", "back", C_GREEN, C_WHITE)]
            self.buttons += self.draw_overlay(
                surf, "通关！" if not last else "全部通关！", (255, 168, 40), sub, btns, C_YELLOW)
        elif self.scene == "lose":
            self.buttons += self.draw_overlay(
                surf, "挑战失败", C_RED, "失误次数用完了，再试一次吧",
                [("重新开始", "retry", C_GREEN, C_WHITE), ("返回主菜单", "back", C_WHITE, C_INK)],
                C_RED)


# ============================================================================
# 六、主循环
# ============================================================================

def main():
    pygame.init()
    pygame.display.set_caption("一箭又一箭 · 基础版")
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    clock = pygame.time.Clock()
    game = Game()

    while game.running:
        dt = clock.tick(FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if game.scene == "play":
                        game.scene = "menu"
                    else:
                        game.running = False
                elif event.key == pygame.K_r and game.scene == "play":
                    game.restart()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if game.scene == "win":
                        if game.level_index + 1 < len(LEVELS):
                            game.load_level(game.level_index + 1)
                        else:
                            game.scene = "menu"
                    elif game.scene == "lose":
                        game.restart()
                    elif game.scene == "menu":
                        game.load_level(0)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                game.click(event.pos)
        game.update(dt)
        game.draw(screen)
        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
