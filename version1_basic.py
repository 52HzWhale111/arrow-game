# -*- coding: utf-8 -*-
"""
一箭又一箭 · 基础版（第一次提交）
================================================
一款点击式箭头解谜小游戏，使用 Python + Pygame 开发。

当前进度：先把画面搭起来——紫色背景、白色棋盘、按方向绘制的箭头。
（点击、路径检测、失误次数等玩法下一步再做。）

运行： python version1_basic.py
"""

import math
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


def draw_icon(surf, kind, center, r, color):
    """按钮里的小图标，统一以 center 为中心、r 为半径来画。"""
    cx, cy = center
    if kind == "loop":
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
# 每关用一个字符串列表表示，U/D/L/R 表示箭头方向，"." 表示空格。
# 这些关卡由 tools/gen_levels.py 用"逆推构造法"生成，
# 生成时就已经保证了必定存在通关顺序。

GRID = [
    ".R.D",
    "RU..",
    "...L",
]


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

    @property
    def vec(self):
        return DIR_VEC[self.dir]


class Game:
    def __init__(self):
        self.arrows = []
        self.gate = 0.0               # 入场动画的总时长
        self.running = True
        self.buttons = []             # 每帧重建的可点击区域
        self.board_rect = pygame.Rect(0, 0, 0, 0)
        self.cell = 80
        self._bg = None
        self._bottom_grad = None

    # ---------------- 关卡 ----------------
    def load_level(self):
        grid = GRID
        self.grid_w, self.grid_h = len(grid[0]), len(grid)
        self.arrows = []
        order = 0
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch in CHAR_DIR:
                    a = Arrow(x, y, CHAR_DIR[ch])
                    a.spawn = -order * 0.035      # 依次弹出的错峰
                    self.arrows.append(a)
                    order += 1
        self.gate = order * 0.035 + 0.45

    @property
    def remain(self):
        return sum(1 for a in self.arrows if a.alive)

    def arrow_at(self, x, y):
        for a in self.arrows:
            if a.alive and a.x == x and a.y == y:
                return a
        return None

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
        for a in self.arrows:
            if a.spawn < 0:
                a.spawn = min(0.0, a.spawn + dt)
            elif a.spawn < 1.0:
                a.spawn = min(1.0, a.spawn + dt * 3.2)

    # ---------------- 绘制 ----------------
    def background(self, surf):
        if self._bg is None:
            self._bg = vgradient((WIN_W, WIN_H), C_BG_TOP, C_BG_BOT)
        surf.blit(self._bg, (0, 0))

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

    def draw_arrow(self, surf, a):
        c = self.cell
        sp = get_arrow_sprite(c, a.dir, C_INK)
        cx, cy = self.cell_center(a.x, a.y)
        # 入场：从小到大弹出来
        k = max(0.0, min(1.0, a.spawn))
        if k < 1.0:
            e = 1 - (1 - k) ** 3
            scale = 0.55 + 0.45 * e + 0.12 * math.sin(e * math.pi)
            size = max(2, int(c * scale))
            sp = pygame.transform.smoothscale(sp, (size, size))
        surf.blit(sp, sp.get_rect(center=(cx, cy)))

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

    def draw(self, surf):
        self.buttons = []
        self.background(surf)
        self.draw_board(surf)
        self.draw_bottombar(surf)


# ============================================================================
# 六、主循环
# ============================================================================

def main():
    pygame.init()
    pygame.display.set_caption("一箭又一箭 · 基础版")
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    clock = pygame.time.Clock()
    game = Game()
    game.load_level()

    while game.running:
        dt = clock.tick(FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    game.running = False
                elif event.key == pygame.K_r:
                    game.load_level()          # 还没做玩法，先只重播一遍入场动画
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if game.btn("restart").collidepoint(event.pos):
                    game.load_level()
        game.update(dt)
        game.draw(screen)
        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
