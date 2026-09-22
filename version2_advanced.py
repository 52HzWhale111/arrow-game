# -*- coding: utf-8 -*-
"""
一箭又一箭 · 进阶版（第二次提交）
================================================
在基础版之上增加了：10 个关卡、选关界面、星级评价、计时、
提示、撤销、进度存档、程序合成音效、粒子特效。

规则：
    棋盘上每个格子最多有一个箭头（上/下/左/右四种方向）。
    点击箭头后，程序检查它前进方向上、到棋盘边界之间还有没有别的箭头：
        · 没有阻挡 -> 箭头飞出去并消失
        · 有阻挡   -> 箭头不能消失，会抖动变红并弹出提示，同时扣掉一次失误机会
    失误次数（爱心）耗尽则本关失败；清空全部箭头则通关。

运行： python version2_advanced.py
"""

import json
import math
import os
import random
import sys
from array import array

import pygame

# ============================================================================
# 一、基础配置
# ============================================================================

WIN_W, WIN_H = 480, 800
FPS = 60

TOP_H = 132
BOTTOM_H = 156
BOARD_AREA = pygame.Rect(0, TOP_H, WIN_W, WIN_H - TOP_H - BOTTOM_H)
MAX_LIVES = 3
MAX_HINTS = 3
STAR_TOTAL = 30                      # 10 关 × 3 星

C_BG_TOP = (146, 140, 236)
C_BG_BOT = (124, 118, 224)
C_BG_PATTERN = (163, 157, 244)
C_WHITE = (255, 255, 255)
C_BOARD = (255, 255, 255)
C_DOT = (203, 206, 220)
C_INK = (43, 47, 74)
C_INK_SOFT = (120, 125, 150)
C_RED = (245, 71, 92)
C_RED_DARK = (110, 34, 54)
C_GREEN = (79, 201, 79)
C_GREEN_DARK = (53, 160, 53)
C_BLUE = (78, 143, 224)
C_YELLOW = (255, 209, 92)
C_GOLD = (255, 194, 51)
C_GREY = (214, 217, 228)
C_ORANGE = (255, 160, 60)
C_PURPLE = (139, 132, 232)

# 打包成 exe 之后 __file__ 指向的是解包出来的临时目录，存档要跟着 exe 走才不会被清掉
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_PATH = os.path.join(BASE_DIR, "save.json")


def vgradient(size, top, bottom):
    """竖直渐变的小图。"""
    w, h = size
    surf = pygame.Surface((1, h))
    for y in range(h):
        k = y / max(1, h - 1)
        surf.set_at((0, y), (int(top[0] + (bottom[0] - top[0]) * k),
                             int(top[1] + (bottom[1] - top[1]) * k),
                             int(top[2] + (bottom[2] - top[2]) * k)))
    return pygame.transform.scale(surf, (w, h))


# ============================================================================
# 二、音效（用代码合成波形，不需要任何音频素材文件）
# ============================================================================

class Sound:
    """用 array 直接拼 16 位 PCM 采样，交给 pygame.mixer 播放。
    好处是：整个项目不需要任何外部素材文件，拷到哪都能跑。
    如果机器上没有声卡 / mixer 初始化失败，会自动降级为"静音"，不影响游戏。"""

    def __init__(self):
        self.enabled = True
        self.ok = False
        self.sounds = {}
        try:
            pygame.mixer.quit()                    # pygame.init() 可能已经用默认格式开过 mixer 了
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self.sounds = {
                "fly": self._sweep(880, 260, 0.22, 0.35),
                "block": self._buzz(170, 0.18, 0.30),
                "win": self._arpeggio([523, 659, 784, 1046], 0.11, 0.30),
                "lose": self._sweep(420, 120, 0.55, 0.32),
                "star": self._arpeggio([880, 1320], 0.09, 0.28),
                "click": self._sweep(700, 560, 0.06, 0.20),
                "undo": self._sweep(300, 620, 0.14, 0.25),
            }
            self.ok = True
        except Exception:                      # noqa: BLE001  没声音也要能玩
            self.ok = False

    # -- 波形合成 --
    @staticmethod
    def _pack(samples):
        buf = array("h", bytes(2 * len(samples)))
        for i, v in enumerate(samples):
            buf[i] = int(max(-1.0, min(1.0, v)) * 32767)
        return buf.tobytes()

    def _sweep(self, f0, f1, dur, vol):
        sr, n = 22050, int(22050 * dur)
        out, phase = [], 0.0
        for i in range(n):
            t = i / n
            phase += 2 * math.pi * (f0 + (f1 - f0) * t) / sr
            env = (1 - t) ** 1.6 * min(1.0, i / 160.0)
            out.append(math.sin(phase) * env * vol)
        return pygame.mixer.Sound(buffer=self._pack(out))

    def _buzz(self, f, dur, vol):
        sr, n = 22050, int(22050 * dur)
        out = []
        for i in range(n):
            t = i / n
            v = math.sin(2 * math.pi * f * i / sr)
            v = 1.0 if v > 0 else -1.0          # 方波，听起来"硬"一点
            env = (1 - t) ** 1.2 * min(1.0, i / 80.0)
            out.append(v * env * vol)
        return pygame.mixer.Sound(buffer=self._pack(out))

    def _arpeggio(self, freqs, step, vol):
        sr = 22050
        out = []
        for f in freqs:
            n = int(sr * step)
            for i in range(n):
                t = i / n
                env = (1 - t) ** 1.1 * min(1.0, i / 60.0)
                out.append(math.sin(2 * math.pi * f * i / sr) * env * vol)
        return pygame.mixer.Sound(buffer=self._pack(out))

    def play(self, name):
        if self.ok and self.enabled and name in self.sounds:
            try:
                self.sounds[name].play()
            except Exception:                  # noqa: BLE001
                pass


# ============================================================================
# 三、文字 / 图形小工具
# ============================================================================

_FONT_PATHS = [
    "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]
_font_cache, _text_cache = {}, {}


def get_font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        font = None
        for path in _FONT_PATHS:
            try:
                font = pygame.font.Font(path, size)
                break
            except (OSError, FileNotFoundError):
                continue
        if font is None:
            font = pygame.font.SysFont("microsoftyaheui,simhei,arial", size, bold=bold)
        _font_cache[key] = font
    return _font_cache[key]


def render_text(text, size, color, bold=False, outline=None, outline_w=2,
                shadow=None, shadow_off=(0, 3)):
    key = (text, size, color, bold, outline, outline_w, shadow, shadow_off)
    if key in _text_cache:
        return _text_cache[key]
    font = get_font(size, bold)
    base = font.render(text, True, color)
    w, h = base.get_size()
    pad = outline_w + abs(shadow_off[0]) + 2 if outline else 2
    pad_y = outline_w + abs(shadow_off[1]) + 2 if outline else 2
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


def render_gradient_text(text, size, top_color, bottom_color, bold=True,
                         outline=None, outline_w=3, shadow=None, shadow_off=(0, 4)):
    """渐变字：先合成"描边+投影"层，再把"白字蒙版 × 竖直渐变"叠上去。"""
    layer = render_text(text, size, C_WHITE, bold=bold, outline=outline,
                        outline_w=outline_w, shadow=shadow, shadow_off=shadow_off)
    mask = get_font(size, bold).render(text, True, C_WHITE).copy()
    mask.blit(vgradient(mask.get_size(), top_color, bottom_color), (0, 0),
              special_flags=pygame.BLEND_RGBA_MULT)
    pad = outline_w + abs(shadow_off[0]) + 2 if outline else 2
    pad_y = outline_w + abs(shadow_off[1]) + 2 if outline else 2
    out = layer.copy()
    out.blit(mask, (pad, pad_y))
    return out


def draw_round_rect(surf, rect, color, radius, width=0):
    pygame.draw.rect(surf, color, rect, width, border_radius=int(radius))


def draw_panel(surf, rect, color, radius, border=None, border_w=3, shadow=True):
    if shadow:
        sh = pygame.Surface((rect.w + 24, rect.h + 24), pygame.SRCALPHA)
        draw_round_rect(sh, pygame.Rect(12, 14, rect.w, rect.h), (60, 50, 130, 60), radius)
        surf.blit(sh, (rect.x - 12, rect.y - 12))
    if border:
        draw_round_rect(surf, rect.inflate(border_w * 2, border_w * 2), border, radius + border_w)
    draw_round_rect(surf, rect, color, radius)


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
    elif kind == "undo":                      # 和"重来"反方向的回转箭头
        pygame.draw.arc(surf, color, pygame.Rect(cx - r, cy - r, 2 * r, 2 * r), 3.9, 8.8, 3)
        pygame.draw.polygon(surf, color, [(cx - r * 0.95, cy - r * 0.95),
                                          (cx - r * 0.3, cy - r * 0.45),
                                          (cx - r * 1.1, cy - r * 0.05)])
    elif kind == "bulb":
        pygame.draw.circle(surf, color, (cx, cy - r * 0.25), int(r * 0.72))
        pygame.draw.rect(surf, color, pygame.Rect(cx - r * 0.32, cy + r * 0.4,
                                                  r * 0.64, r * 0.5), 0, border_radius=2)


def draw_button(surf, rect, fill, text, text_color=C_WHITE, radius=None, edge=None,
                border=None, border_w=3, size=24, icon=None, enabled=True, icon_color=None):
    """立体圆角按钮（参考图里那种有厚度、有白边的胶囊按钮）。
    图标和文字先量好宽度再整体居中，免得手动凑偏移量。"""
    if not enabled:
        fill, text_color, edge = (232, 233, 240), (166, 170, 186), (214, 216, 226)
    radius = radius if radius is not None else min(rect.h // 3, 24)
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
        draw_icon(surf, icon, (x + iw // 2, rect.centery), 12, icon_color or text_color)
    if text:
        draw_text(surf, text, size, text_color, center=(x + iw + gap + tw // 2, rect.centery),
                  bold=True, shadow=edge if enabled and fill != C_WHITE else None,
                  shadow_off=(0, 2))


def draw_heart(surf, center, size, color, outline=None):
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
                      [(cx + size * 0.4, cy - size * 0.7), (cx - size * 0.4, cy),
                       (cx + size * 0.4, cy + size * 0.7)], width)


def draw_gear(surf, center, r, color):
    """用 8 根粗线拼一个齿轮图标。"""
    for i in range(8):
        a = i * math.pi / 4
        pygame.draw.line(surf, color, (center[0] + math.cos(a) * r * 0.55,
                                       center[1] + math.sin(a) * r * 0.55),
                         (center[0] + math.cos(a) * r * 1.15,
                          center[1] + math.sin(a) * r * 1.15), max(2, int(r * 0.42)))
    pygame.draw.circle(surf, color, center, int(r * 0.78))
    pygame.draw.circle(surf, (0, 0, 0, 0), center, int(r * 0.34))


def draw_speaker(surf, center, r, color, on=True):
    pygame.draw.polygon(surf, color, [(center[0] - r * 0.7, center[1] - r * 0.3),
                                      (center[0] - r * 0.2, center[1] - r * 0.3),
                                      (center[0] + r * 0.35, center[1] - r * 0.8),
                                      (center[0] + r * 0.35, center[1] + r * 0.8),
                                      (center[0] - r * 0.2, center[1] + r * 0.3),
                                      (center[0] - r * 0.7, center[1] + r * 0.3)])
    if on:
        pygame.draw.arc(surf, color, pygame.Rect(center[0] + r * 0.1, center[1] - r * 0.7,
                                                 r * 1.1, r * 1.4), -1.0, 1.0, 2)
    else:
        pygame.draw.line(surf, color, (center[0] + r * 0.5, center[1] - r * 0.5),
                         (center[0] + r * 1.1, center[1] + r * 0.5), 2)


# ============================================================================
# 四、箭头绘制
# ============================================================================

DIR_VEC = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
DIR_ANGLE = {"R": 0, "U": 90, "L": 180, "D": 270}
CHAR_DIR = {"^": "U", "v": "D", "<": "L", ">": "R",
            "U": "U", "D": "D", "L": "L", "R": "R"}
_arrow_cache = {}


def _build_arrow(cell, color, fade=0.55):
    """一支"朝右"的箭头：粗圆头箭杆 + 大三角箭头，箭尾渐变淡出。
    先画白色剪影，再和横向透明度渐变相乘，最后染色。整支箭只算一次并缓存。"""
    S = cell
    mask = pygame.Surface((S, S), pygame.SRCALPHA)
    pad = S * 0.10
    cy = S / 2.0
    x_tail, x_tip = pad, S - pad
    head_len, head_w, shaft_w = S * 0.30, S * 0.58, S * 0.23
    x_head = x_tip - head_len
    pygame.draw.line(mask, (255, 255, 255, 255), (x_tail, cy), (x_head, cy), int(shaft_w))
    pygame.draw.circle(mask, (255, 255, 255, 255), (int(x_tail), int(cy)), int(shaft_w / 2))
    pygame.draw.polygon(mask, (255, 255, 255, 255),
                        [(x_tip, cy), (x_head, cy - head_w / 2), (x_head, cy + head_w / 2)])
    grad = pygame.Surface((S, S), pygame.SRCALPHA)
    for x in range(S):
        k = min(1.0, max(0.0, (x - x_tail) / max(1.0, x_tip - x_tail)))
        pygame.draw.line(grad, (255, 255, 255, int(255 * (fade + (1 - fade) * k ** 1.4))),
                         (x, 0), (x, S))
    mask.blit(grad, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    tint = pygame.Surface((S, S), pygame.SRCALPHA)
    tint.fill(color + (255,))
    tint.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return tint


def get_arrow_sprite(cell, direction, color, fade=0.55):
    key = (cell, direction, color, round(fade, 2))
    if key not in _arrow_cache:
        base = _build_arrow(cell, color, fade)
        angle = DIR_ANGLE[direction]
        _arrow_cache[key] = pygame.transform.rotate(base, angle) if angle else base
    return _arrow_cache[key]


def alpha_copy(surf, a):
    """复制一份并把整体透明度乘上 a（0~255），用来做淡入淡出。"""
    s = surf.copy()
    s.fill((255, 255, 255, max(0, min(255, int(a)))), None, pygame.BLEND_RGBA_MULT)
    return s


# ============================================================================
# 五、关卡数据
# ============================================================================
# 由 tools/gen_levels.py 用"逆推构造法"生成：从空棋盘开始逐个放箭头，
# 每次放的时候要求它朝着自己方向到边界之间没有任何已放好的箭头。
# 这样按放置的逆序消除一定可以通关，生成时逐关验证过。

LEVELS = [
    {"name": "第 1 关", "grid": [".D...", "R...R", "..U.U", "UR..U"]},
    {"name": "第 2 关", "grid": ["U....L", ".RRR..", "U.R..R", "U..L.."]},
    {"name": "第 3 关", "grid": ["DD.R.U", ".D..LU", "..D.L.", "R.R..U"]},
    {"name": "第 4 关", "grid": ["R.R.DU", ".....U", "LLUL.D", "...U..", "....DL"]},
    {"name": "第 5 关", "grid": ["D.L..LL", ".R..R.D", "DL...U.", ".LUR..R", ".R....."]},
    {"name": "第 6 关", "grid": ["LLRR...", "U..L...", ".UD.R.R", "UL...LU", "U...UL."]},
    {"name": "第 7 关", "grid": ["D.RUR.RU", "D...L..U", "...UD.UU", ".DRD....", ".D..LD.."]},
    {"name": "第 8 关", "grid": ["R...U...", "D..UD..L", "DR..DRR.", "DL.LD.U.", "L...DLRD"]},
    {"name": "第 9 关", "grid": [".URU.U..", ".U.U..R.", "DD....R.", "D.LU.U..",
                                 "D.LDR..D", "LLUR...D"]},
    {"name": "第 10 关", "grid": ["..L.ULRU", "LLUR..U.", ".D..R.R.", "...UD..L",
                                  ".LRDRRRD", "UL....LR"]},
]


# ============================================================================
# 六、存档
# ============================================================================

class Progress:
    """把解锁进度和每关最好成绩存到 save.json。
    读写失败（比如目录只读）时静默忽略，不影响玩。"""

    def __init__(self, path=None):
        self.path = path or SAVE_PATH
        self.unlocked = 0                       # 已解锁到第几关（下标）
        self.best = {}                          # {关卡下标: {"stars": n, "time": 秒}}
        self.sound = True
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.unlocked = max(0, min(len(LEVELS) - 1, int(data.get("unlocked", 0))))
            self.best = {int(k): v for k, v in data.get("best", {}).items()}
            self.sound = bool(data.get("sound", True))
        except (OSError, ValueError, TypeError):
            pass

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"unlocked": self.unlocked,
                           "best": {str(k): v for k, v in self.best.items()},
                           "sound": self.sound}, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def record(self, index, stars, seconds):
        """记录成绩，返回是否刷新了纪录。"""
        old = self.best.get(index)
        improved = old is None or stars > old.get("stars", 0) or \
            (stars == old.get("stars", 0) and seconds < old.get("time", 1e9))
        if improved:
            self.best[index] = {"stars": stars, "time": round(seconds, 2)}
        self.unlocked = max(self.unlocked, min(index + 1, len(LEVELS) - 1))
        self.save()
        return improved

    @property
    def total_stars(self):
        return sum(v.get("stars", 0) for v in self.best.values())


# ============================================================================
# 七、游戏对象
# ============================================================================

class Arrow:
    def __init__(self, x, y, direction):
        self.x, self.y, self.dir = x, y, direction
        self.alive = True
        self.spawn = 0.0        # <0：还没出场；0~1：入场动画；1：就位
        self.shake = 0.0
        self.flash = 0.0
        self.hint = 0.0         # 被提示高亮的剩余时间

    @property
    def vec(self):
        return DIR_VEC[self.dir]


class Flying:
    def __init__(self, x, y, direction):
        self.x, self.y, self.dir = float(x), float(y), direction
        self.t = 0.0
        self.trail = []


class Particle:
    def __init__(self, x, y, vx, vy, color, life=0.5, size=5):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.color, self.life, self.size, self.t = color, life, size, 0.0

    def update(self, dt):
        self.t += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= 0.94
        self.vy = self.vy * 0.94 + 260 * dt


class Toast:
    def __init__(self, text, pos, color, size=20, life=0.9, dy=-28):
        self.text, self.pos, self.color = text, pos, color
        self.size, self.life, self.dy = size, life, dy
        self.t = 0.0


# ============================================================================
# 八、游戏主类
# ============================================================================

class Game:
    def __init__(self):
        self.progress = Progress()
        self.sound = Sound()
        self.sound.enabled = self.progress.sound
        self.scene = "menu"          # menu / levels / play / win / lose / pause
        self.level_index = 0
        self.arrows, self.flies, self.parts, self.toasts = [], [], [], []
        self.history = []            # 用于撤销：记录已消除的箭头
        self.lives = MAX_LIVES
        self.hints = MAX_HINTS
        self.time_used = 0.0
        self.shake_t = 0.0
        self.shake_dir = (0, 0)
        self.board_rect = pygame.Rect(0, 0, 0, 0)
        self.cell = 80
        self.buttons = []
        self.level_rects = []
        self.result = {"stars": 0, "improved": False}
        self.anim_in = 0.0           # 浮层滑入动画
        self.running = True
        self._bg = None
        self._menu_bg = None
        self._top_grad = None
        self._bottom_grad = None

    # ---------------- 关卡 ----------------
    def load_level(self, index):
        self.level_index = max(0, min(len(LEVELS) - 1, index))
        grid = LEVELS[self.level_index]["grid"]
        self.grid_w, self.grid_h = len(grid[0]), len(grid)
        self.arrows, self.history = [], []
        self.flies.clear()
        self.parts.clear()
        self.toasts.clear()
        self.lives, self.hints = MAX_LIVES, MAX_HINTS
        self.time_used, self.anim_in = 0.0, 0.0
        order = 0
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch in CHAR_DIR:
                    a = Arrow(x, y, CHAR_DIR[ch])
                    a.spawn = -order * 0.03
                    self.arrows.append(a)
                    order += 1
        self.scene = "play"

    def restart(self):
        self.load_level(self.level_index)

    @property
    def remain(self):
        return sum(1 for a in self.arrows if a.alive)

    @property
    def total(self):
        return len(self.arrows)

    def arrow_at(self, x, y):
        for a in self.arrows:
            if a.alive and a.x == x and a.y == y:
                return a
        return None

    # ---------------- 路径检测（核心规则）----------------
    def blocked_by(self, arrow):
        """从箭头所在格出发，沿它的方向一格一格往边界走。
        路上碰到任何一个还活着的箭头，就是被它挡住了，返回那个箭头；
        一路走出棋盘都没碰到，返回 None 表示可以飞出去。"""
        dx, dy = arrow.vec
        cx, cy = arrow.x + dx, arrow.y + dy
        while 0 <= cx < self.grid_w and 0 <= cy < self.grid_h:
            other = self.arrow_at(cx, cy)
            if other is not None:
                return other
            cx += dx
            cy += dy
        return None

    def find_free(self):
        """找一个当前能飞出去的箭头（提示功能要用）。"""
        for a in self.arrows:
            if a.alive and a.spawn >= 0 and self.blocked_by(a) is None:
                return a
        return None

    # ---------------- 交互 ----------------
    def click(self, pos):
        # 浮层里的按钮在任何界面都优先响应
        if self.scene == "menu":
            if self.btn("start").collidepoint(pos):
                self.load_level(self.progress.unlocked)
                self.sound.play("click")
            elif self.btn("levels").collidepoint(pos):
                self.scene = "levels"
                self.sound.play("click")
            elif self.btn("sound").collidepoint(pos):
                self.toggle_sound()
            return

        if self.scene == "levels":
            if self.btn("home").collidepoint(pos):
                self.scene = "menu"
                return
            for i, r in enumerate(self.level_rects):
                if r.collidepoint(pos):
                    if i <= self.progress.unlocked:
                        self.load_level(i)
                        self.sound.play("click")
                    else:
                        self.toasts.append(Toast("还没解锁哦", r.center, C_WHITE, 18, 0.8))
                    return
            return

        if self.scene in ("win", "lose", "pause"):
            if self.scene == "win":
                if self.btn("next").collidepoint(pos):
                    self.load_level(self.level_index + 1)
                    self.sound.play("click")
                elif self.btn("back").collidepoint(pos):
                    self.scene = "levels"
                return
            if self.scene == "pause":
                if self.btn("resume").collidepoint(pos):
                    self.scene = "play"
                elif self.btn("restart").collidepoint(pos):
                    self.restart()
                elif self.btn("back").collidepoint(pos):
                    self.scene = "levels"
                elif self.btn("sound").collidepoint(pos):
                    self.toggle_sound()
                return
            if self.btn("retry").collidepoint(pos):
                self.restart()
                self.sound.play("click")
            elif self.btn("back").collidepoint(pos):
                self.scene = "levels"
            return

        # ---- 游戏中 ----
        if self.btn("home").collidepoint(pos):
            self.scene = "menu"
            return
        if self.btn("restart").collidepoint(pos):
            self.restart()
            self.sound.play("click")
            return
        if self.btn("hint").collidepoint(pos):
            self.use_hint()
            return
        if self.btn("undo").collidepoint(pos):
            self.undo()
            return
        if not BOARD_AREA.collidepoint(pos):
            return
        gx = int((pos[0] - self.board_rect.x) // self.cell)
        gy = int((pos[1] - self.board_rect.y) // self.cell)
        if 0 <= gx < self.grid_w and 0 <= gy < self.grid_h:
            a = self.arrow_at(gx, gy)
            if a is not None and a.spawn >= 0:
                self.try_fly(a)

    def toggle_sound(self):
        self.sound.enabled = not self.sound.enabled
        self.progress.sound = self.sound.enabled
        self.progress.save()
        if self.sound.enabled:
            self.sound.play("click")

    def try_fly(self, arrow):
        blocker = self.blocked_by(arrow)
        if blocker is not None:
            # 被挡住：抖动 + 变红 + 屏幕轻微震动 + 粒子 + 扣一次失误
            arrow.shake, arrow.flash = 0.45, 0.75
            self.lives -= 1
            self.shake_t = 0.22
            self.sound.play("block")
            cx, cy = self.cell_center(arrow.x, arrow.y)
            for _ in range(10):
                a = random.uniform(0, math.tau)
                sp = random.uniform(60, 190)
                self.parts.append(Particle(cx, cy, math.cos(a) * sp, math.sin(a) * sp,
                                           C_RED, 0.45, random.randint(3, 6)))
            tx, ty = self.cell_center(arrow.x, arrow.y, -0.55)
            self.toasts.append(Toast("被挡住了！", (tx, max(ty, BOARD_AREA.y + 26)), C_RED))
            if self.lives <= 0:
                self.lives = 0
                self.scene = "lose"
                self.sound.play("lose")
            return
        # 没被挡住：先做逻辑消除，再放动画（这样后面的箭头立刻就可以点了）
        arrow.alive = False
        arrow.hint = 0.0
        self.history.append(arrow)
        self.flies.append(Flying(arrow.x, arrow.y, arrow.dir))
        self.sound.play("fly")
        cx, cy = self.cell_center(arrow.x, arrow.y)
        dx, dy = DIR_VEC[arrow.dir]
        for _ in range(8):
            a = random.uniform(0, math.tau)
            sp = random.uniform(40, 130)
            self.parts.append(Particle(cx + dx * self.cell * 0.3, cy + dy * self.cell * 0.3,
                                       math.cos(a) * sp + dx * 90,
                                       math.sin(a) * sp + dy * 90,
                                       C_INK, 0.4, random.randint(2, 5)))
        if self.remain == 0:
            self.finish_level()

    def finish_level(self):
        stars = 3 if self.lives == MAX_LIVES else (2 if self.lives == MAX_LIVES - 1 else 1)
        improved = self.progress.record(self.level_index, stars, self.time_used)
        self.result = {"stars": stars, "improved": improved}
        self.anim_in = 0.0
        self.scene = "win"
        self.sound.play("win")

    def use_hint(self):
        if self.hints <= 0:
            self.toasts.append(Toast("提示次数用完了", (WIN_W // 2, BOARD_AREA.y + 40),
                                     C_WHITE, 20))
            return
        a = self.find_free()
        if a is None:
            return
        self.hints -= 1
        a.hint = 2.2
        self.sound.play("star")
        tx, ty = self.cell_center(a.x, a.y, -0.55)
        self.toasts.append(Toast("试试这个箭头", (tx, max(ty, BOARD_AREA.y + 26)), (240, 150, 20), 20))

    def undo(self):
        """撤销上一步已经飞出去的箭头。"""
        if self.scene != "play" or not self.history:
            return
        a = self.history.pop()
        a.alive = True
        a.spawn = 0.35               # 重新"长"出来
        a.shake = 0.0
        a.flash = 0.0
        a.hint = 0.0
        self.sound.play("undo")
        cx, cy = self.cell_center(a.x, a.y)
        for _ in range(8):
            ang = random.uniform(0, math.tau)
            self.parts.append(Particle(cx, cy, math.cos(ang) * 110, math.sin(ang) * 110,
                                       C_BLUE, 0.35, 4))

    # ---------------- 几何 ----------------
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
        if self.anim_in < 1.0:
            self.anim_in = min(1.0, self.anim_in + dt * 4.0)
        if self.shake_t > 0:
            self.shake_t = max(0.0, self.shake_t - dt)

        for a in self.arrows:
            if a.spawn < 0:
                a.spawn = min(0.0, a.spawn + dt)
            elif a.spawn < 1.0:
                a.spawn = min(1.0, a.spawn + dt * 3.2)
            a.shake = max(0.0, a.shake - dt)
            a.flash = max(0.0, a.flash - dt)
            a.hint = max(0.0, a.hint - dt)

        for f in self.flies:
            f.t += dt
            f.trail.append([f.x, f.y, 1.0])
            for tr in f.trail:
                tr[2] -= dt * 4.5
            f.trail = [t for t in f.trail if t[2] > 0][-14:]
            speed = 6 + 26 * (f.t ** 1.7)
            f.x += DIR_VEC[f.dir][0] * speed * dt
            f.y += DIR_VEC[f.dir][1] * speed * dt
        self.flies = [f for f in self.flies if f.t < 0.55]

        for p in self.parts:
            p.update(dt)
        self.parts = [p for p in self.parts if p.t < p.life]

        for t in self.toasts:
            t.t += dt
        self.toasts = [t for t in self.toasts if t.t < t.life]

    # ---------------- 背景 ----------------
    def background(self, surf):
        if self._bg is None:
            self._bg = vgradient((WIN_W, WIN_H), C_BG_TOP, C_BG_BOT)
        surf.blit(self._bg, (0, 0))

    def menu_background(self, surf):
        if self._menu_bg is None:
            bg = vgradient((WIN_W, WIN_H), (150, 144, 240), (116, 110, 218))
            rng = random.Random(2026)
            deco = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
            for _ in range(30):
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
                    s = alpha_copy(s, 60)
                    deco.blit(s, (x, y))
                else:
                    pygame.draw.polygon(deco, C_BG_PATTERN + (120,),
                                        [(x, y), (x - 9, y + 18), (x + 2, y + 16),
                                         (x - 3, y + 32), (x + 11, y + 11), (x - 1, y + 13)])
            bg.blit(deco, (0, 0))
            self._menu_bg = bg
        surf.blit(self._menu_bg, (0, 0))

    # ---------------- 各界面 ----------------
    def draw_menu(self, surf):
        self.menu_background(surf)
        cx = WIN_W // 2
        title = render_gradient_text("一箭又一箭", 62, (255, 248, 214), (255, 172, 54),
                                     outline=C_BLUE, outline_w=5,
                                     shadow=(60, 70, 150), shadow_off=(0, 6))
        surf.blit(title, title.get_rect(center=(cx, 200)))
        a1 = pygame.transform.rotate(get_arrow_sprite(64, "R", C_ORANGE, 0.85), -32)
        surf.blit(a1, a1.get_rect(center=(cx + 132, 158)))
        a2 = pygame.transform.rotate(get_arrow_sprite(56, "R", C_ORANGE, 0.85), 150)
        surf.blit(a2, a2.get_rect(center=(cx - 142, 250)))

        # 星星总进度
        star_panel = pygame.Rect(0, 0, 148, 44)
        star_panel.center = (cx, 300)
        draw_panel(surf, star_panel, (176, 170, 250), 22, shadow=False)
        draw_star(surf, (star_panel.x + 28, star_panel.centery), 13, C_GOLD)
        draw_text(surf, "%d / %d" % (self.progress.total_stars, STAR_TOTAL), 21, C_WHITE,
                  center=(star_panel.x + 86, star_panel.centery), bold=True)

        nxt = self.progress.unlocked
        r = pygame.Rect(0, 0, 260, 74)
        r.center = (cx, 400)
        draw_button(surf, r, C_GREEN, "开始游戏", size=30, icon="play",
                    edge=C_GREEN_DARK, border=C_WHITE)
        label = pygame.Rect(0, 0, 150, 40)
        label.center = (cx, r.bottom + 32)
        draw_panel(surf, label, C_WHITE, 12, shadow=False)
        draw_text(surf, "第 %d 关" % (nxt + 1), 21, C_INK, center=label.center, bold=True)

        r2 = pygame.Rect(0, 0, 260, 60)
        r2.center = (cx, 566)
        draw_button(surf, r2, C_WHITE, "选择关卡", text_color=C_INK, size=24)
        self.buttons = [("start", r), ("levels", r2)]

        # 音效开关
        sr = pygame.Rect(0, 0, 52, 52)
        sr.center = (WIN_W - 54, WIN_H - 62)
        draw_panel(surf, sr, (176, 170, 250), 26, shadow=False)
        draw_speaker(surf, sr.center, 13, C_WHITE, self.sound.enabled)
        self.buttons.append(("sound", sr))
        draw_text(surf, "音效", 13, (226, 224, 252), center=(sr.centerx, sr.bottom + 12))

        draw_text(surf, "共 %d 关 · 每关 %d 次机会 · %d 次提示" %
                  (len(LEVELS), MAX_LIVES, MAX_HINTS), 17, (226, 224, 252),
                  center=(cx, WIN_H - 62))

    def draw_levels(self, surf):
        self.menu_background(surf)
        scrim = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        scrim.fill((48, 42, 100, 90))
        surf.blit(scrim, (0, 0))
        draw_text(surf, "选择关卡", 40, C_WHITE, center=(WIN_W // 2, 60), bold=True,
                  shadow=(70, 64, 140), shadow_off=(0, 3))
        draw_text(surf, "★ %d / %d" % (self.progress.total_stars, STAR_TOTAL), 20,
                  (238, 236, 255), center=(WIN_W // 2, 100), bold=True)

        back = pygame.Rect(18, 34, 46, 46)
        pygame.draw.circle(surf, C_WHITE, back.center, 23)
        draw_chevron_left(surf, back.center, 12, C_INK, 4)
        self.buttons = [("home", back)]

        self.level_rects = []
        cols, size, gap = 4, 92, 16
        x0 = (WIN_W - (cols * size + (cols - 1) * gap)) // 2
        for i in range(len(LEVELS)):
            row, col = divmod(i, cols)
            r = pygame.Rect(x0 + col * (size + gap), 150 + row * (size + 44), size, size)
            self.level_rects.append(r)
            unlocked = i <= self.progress.unlocked
            done = i in self.progress.best
            fill = C_WHITE if unlocked else (150, 145, 205)
            if done:
                fill = (255, 246, 220)
            draw_panel(surf, r, fill, 20, shadow=False)
            if unlocked:
                draw_text(surf, str(i + 1), 34, C_INK if not done else (198, 130, 20),
                          center=(r.centerx, r.centery - 6), bold=True)
                stars = self.progress.best.get(i, {}).get("stars", 0)
                for s in range(3):
                    draw_star(surf, (r.centerx - 22 + s * 22, r.bottom - 22), 8,
                              C_GOLD if s < stars else (222, 224, 234))
                if i in self.progress.best:
                    t = self.progress.best[i].get("time", 0)
                    draw_text(surf, "%d:%02d" % divmod(int(t), 60), 13, (240, 238, 255),
                              center=(r.centerx, r.bottom + 16), bold=True)
            else:
                # 一把小锁
                body = pygame.Rect(0, 0, 26, 22)
                body.center = (r.centerx, r.centery + 4)
                pygame.draw.arc(surf, (238, 238, 248),
                                pygame.Rect(r.centerx - 11, r.centery - 20, 22, 26),
                                0.0, math.pi, 4)
                draw_round_rect(surf, body, (238, 238, 248), 6)
            self.buttons.append(("lv%d" % i, r))

        draw_text(surf, "通关后解锁下一关，失误越少星星越多", 16, (226, 224, 252),
                  center=(WIN_W // 2, WIN_H - 60))

    def draw_topbar(self, surf):
        if self._top_grad is None:                 # 渐变条只算一次，之后每帧直接贴
            self._top_grad = vgradient((WIN_W, TOP_H + 20), (150, 144, 240), (132, 126, 230))
        surf.blit(self._top_grad, (0, 0))
        cx = WIN_W // 2
        draw_text(surf, LEVELS[self.level_index]["name"], 34, C_WHITE, center=(cx, 30),
                  bold=True, shadow=(74, 68, 150), shadow_off=(0, 3))
        for i in range(MAX_LIVES):
            alive = i < self.lives
            draw_heart(surf, (cx - 44 + i * 44, 74), 17, C_RED if alive else C_RED_DARK,
                       outline=(198, 46, 70) if alive else None)
        m, s = divmod(int(self.time_used), 60)
        pygame.draw.circle(surf, (238, 238, 250), (cx - 34, 106), 9, 2)
        pygame.draw.line(surf, (238, 238, 250), (cx - 34, 106), (cx - 34, 100), 2)
        pygame.draw.line(surf, (238, 238, 250), (cx - 34, 106), (cx - 29, 106), 2)
        draw_text(surf, "%dm%02ds" % (m, s), 21, (245, 245, 255), center=(cx + 12, 106),
                  bold=True)

        back = pygame.Rect(18, 22, 46, 46)
        pygame.draw.circle(surf, C_WHITE, back.center, 23)
        draw_chevron_left(surf, back.center, 12, C_INK, 4)
        self.buttons.append(("home", back))

        badge = pygame.Rect(WIN_W - 106, 22, 88, 46)
        draw_panel(surf, badge, C_WHITE, 23, shadow=False)
        mini = get_arrow_sprite(30, "R", C_INK, 0.7)
        surf.blit(mini, mini.get_rect(center=(badge.x + 26, badge.centery)))
        draw_text(surf, str(self.remain), 26, C_INK, center=(badge.x + 60, badge.centery),
                  bold=True)
        draw_text(surf, "剩余箭头", 14, (232, 230, 252), center=(badge.centerx, badge.bottom + 14))

    def draw_board(self, surf):
        max_w, max_h = BOARD_AREA.w - 56, BOARD_AREA.h - 60
        cell = int(min(max_w / self.grid_w, max_h / self.grid_h, 96))
        self.cell = cell
        rect = pygame.Rect(0, 0, cell * self.grid_w, cell * self.grid_h)
        rect.center = BOARD_AREA.center
        if self.shake_t > 0:                      # 撞击时整个棋盘轻轻抖一下
            k = self.shake_t / 0.22
            rect = rect.move(int(math.sin(self.shake_t * 55) * 7 * k), 0)
        self.board_rect = rect

        pygame.draw.rect(surf, C_BOARD, BOARD_AREA.inflate(0, 40))
        card = rect.inflate(46, 46)
        sh = pygame.Surface((card.w + 24, card.h + 24), pygame.SRCALPHA)
        draw_round_rect(sh, pygame.Rect(12, 14, card.w, card.h), (70, 62, 140, 45), 26)
        surf.blit(sh, (card.x - 12, card.y - 12))
        draw_round_rect(surf, card, (250, 250, 254), 26, width=2)

        for gy in range(self.grid_h + 1):
            for gx in range(self.grid_w + 1):
                pygame.draw.circle(surf, C_DOT,
                                   (rect.x + gx * cell, rect.y + gy * cell), 3)

        for a in self.arrows:
            if a.alive and a.spawn >= 0:
                if a.hint > 0:                    # 提示：画一个脉动的光圈
                    k = 0.5 + 0.5 * math.sin(a.hint * 9)
                    cxp, cyp = self.cell_center(a.x, a.y)
                    ring = pygame.Surface((cell + 30, cell + 30), pygame.SRCALPHA)
                    pygame.draw.circle(ring, C_GOLD + (int(120 + 90 * k),),
                                       (ring.get_width() // 2, ring.get_height() // 2),
                                       int(cell * (0.44 + 0.05 * k)), 5)
                    surf.blit(ring, ring.get_rect(center=(cxp, cyp)))
                self.draw_arrow(surf, a)
        for f in self.flies:
            self.draw_flying(surf, f)
        for p in self.parts:                      # 粒子
            k = max(0.0, 1 - p.t / p.life)
            r = max(1, int(p.size * k))
            pygame.draw.circle(surf, p.color, (int(p.x), int(p.y)), r)

    def draw_arrow(self, surf, a):
        c = self.cell
        color = C_INK
        if a.flash > 0:
            k = abs(math.sin(a.flash * 22))
            color = tuple(int(C_INK[i] + (C_RED[i] - C_INK[i]) * k) for i in range(3))
        sp = get_arrow_sprite(c, a.dir, color)
        cx, cy = self.cell_center(a.x, a.y)
        k = max(0.0, min(1.0, a.spawn))
        if k < 1.0:
            e = 1 - (1 - k) ** 3
            size = max(2, int(c * (0.55 + 0.45 * e + 0.12 * math.sin(e * math.pi))))
            sp = pygame.transform.smoothscale(sp, (size, size))
        if a.shake > 0:
            off = math.sin(a.shake * 42) * 10 * (a.shake / 0.45)
            dx, dy = DIR_VEC[a.dir]
            cx += int(-dy * off)
            cy += int(dx * off)
        surf.blit(sp, sp.get_rect(center=(cx, cy)))

    def draw_flying(self, surf, f):
        c = self.cell
        sp = get_arrow_sprite(c, f.dir, C_INK)
        for i, (tx, ty, ta) in enumerate(f.trail):
            if i % 2:
                continue
            g = alpha_copy(sp, 70 * ta)
            surf.blit(g, g.get_rect(center=(self.board_rect.x + (tx + 0.5) * c,
                                            self.board_rect.y + (ty + 0.5) * c)))
        ghost = alpha_copy(sp, 255 * (1 - f.t / 0.55))
        surf.blit(ghost, ghost.get_rect(center=(self.board_rect.x + (f.x + 0.5) * c,
                                                self.board_rect.y + (f.y + 0.5) * c)))

    def draw_bottombar(self, surf):
        y = WIN_H - BOTTOM_H
        if self._bottom_grad is None:
            self._bottom_grad = vgradient((WIN_W, BOTTOM_H + 20), (132, 126, 230),
                                          (118, 112, 220))
        surf.blit(self._bottom_grad, (0, y))
        bw, gap = 138, 14
        x0 = (WIN_W - (bw * 3 + gap * 2)) // 2
        w = 54
        specs = [
            ("undo", "撤销", "undo", len(self.history) > 0),
            ("hint", "提示 %d" % self.hints, "bulb", self.hints > 0),
            ("restart", "重来", "loop", True),
        ]
        for i, (name, label, icon, enabled) in enumerate(specs):
            r = pygame.Rect(x0 + i * (bw + gap), y + 34, bw, w)
            draw_button(surf, r, C_WHITE, label, text_color=C_INK, size=20, icon=icon,
                        enabled=enabled)
            self.buttons.append((name, r))

        # 进度条：本关还剩多少箭头
        pw = WIN_W - 96
        pr = pygame.Rect(48, y + 108, pw, 12)
        draw_round_rect(surf, pr, (255, 255, 255, 70), 6)
        done = self.total - self.remain
        if self.total:
            draw_round_rect(surf, pygame.Rect(pr.x, pr.y, int(pw * done / self.total), 12),
                            C_GOLD, 6)
        draw_text(surf, "%d / %d" % (done, self.total), 15, (238, 236, 255),
                  center=(WIN_W // 2, pr.bottom + 16), bold=True)

    def draw_overlay(self, surf, title, title_color, subtitle, buttons, accent,
                     stars=0, extra=None):
        scrim = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        scrim.fill((40, 34, 90, 150))
        surf.blit(scrim, (0, 0))

        k = 1 - (1 - min(1.0, self.anim_in)) ** 3        # 卡片滑入
        start = 186 + (34 if stars else 0)               # 第一个按钮的纵向位置
        height = start + (len(buttons) - 1) * 68 + 28 + 26   # 按按钮个数撑高卡片
        card = pygame.Rect(0, 0, 340, height)
        card.center = (WIN_W // 2, WIN_H // 2 - 20 + int((1 - k) * 40))
        draw_panel(surf, card, C_WHITE, 30)
        pill = pygame.Rect(0, 0, 96, 9)
        pill.center = (card.centerx, card.y + 26)
        draw_round_rect(surf, pill, accent, 5)
        draw_text(surf, title, 44, title_color, center=(card.centerx, card.y + 80), bold=True,
                  shadow=(210, 210, 225), shadow_off=(0, 3))
        dy = 0
        if stars:
            for i in range(3):
                # 三颗星依次弹出
                pop = max(0.0, min(1.0, (self.anim_in - 0.15 - i * 0.14) * 5))
                if pop <= 0:
                    continue
                size = 22 * (pop + 0.25 * math.sin(pop * math.pi))
                draw_star(surf, (card.centerx - 52 + i * 52, card.y + 134), size,
                          C_GOLD if i < stars else (222, 224, 234))
            dy = 34
        if subtitle:
            draw_text(surf, subtitle, 19, C_INK_SOFT, center=(card.centerx, card.y + 130 + dy))
        if extra:
            draw_text(surf, extra, 19, C_GOLD, center=(card.centerx, card.y + 158 + dy), bold=True)
        rects = []
        for i, (label, name, color, text_color) in enumerate(buttons):
            r = pygame.Rect(0, 0, 230, 56)
            r.center = (card.centerx, card.y + 186 + dy + i * 68)
            draw_button(surf, r, color, label, text_color=text_color, size=24,
                        border=C_WHITE if color != C_WHITE else (225, 227, 238))
            rects.append((name, r))
        return rects

    def draw(self, surf):
        self.buttons = []
        if self.scene == "menu":
            self.draw_menu(surf)
            return
        if self.scene == "levels":
            self.draw_levels(surf)
            return

        self.background(surf)
        self.draw_board(surf)
        self.draw_topbar(surf)
        self.draw_bottombar(surf)

        for t in self.toasts:
            k = t.t / t.life
            s = alpha_copy(render_text(t.text, t.size, t.color, bold=True,
                                       outline=C_WHITE, outline_w=2), 255 * (1 - k))
            surf.blit(s, s.get_rect(center=(t.pos[0], t.pos[1] + t.dy * k)))

        if self.scene == "win":
            last = self.level_index == len(LEVELS) - 1
            m, s = divmod(int(self.time_used), 60)
            sub = "用时 %dm%02ds · 剩余 %d 次机会" % (m, s, self.lives)
            extra = "新纪录！" if self.result.get("improved") else None
            btns = [("下一关" if not last else "返回选关", "next", C_GREEN, C_WHITE),
                    ("返回选关", "back", C_WHITE, C_INK)]
            if last:
                btns = [("返回选关", "back", C_GREEN, C_WHITE)]
            self.buttons += self.draw_overlay(
                surf, "通关！" if not last else "全部通关！", (255, 168, 40), sub, btns,
                C_YELLOW, stars=self.result.get("stars", 0), extra=extra)
        elif self.scene == "lose":
            self.buttons += self.draw_overlay(
                surf, "挑战失败", C_RED, "失误次数用完了，再试一次吧",
                [("重新开始", "retry", C_GREEN, C_WHITE), ("返回选关", "back", C_WHITE, C_INK)],
                C_RED)
        elif self.scene == "pause":
            self.buttons += self.draw_overlay(
                surf, "暂停", C_INK, "休息一下～",
                [("继续游戏", "resume", C_GREEN, C_WHITE),
                 ("重新开始", "restart", C_WHITE, C_INK),
                 ("返回选关", "back", C_WHITE, C_INK)], C_BLUE)


# ============================================================================
# 九、主循环
# ============================================================================

def main():
    pygame.init()
    pygame.display.set_caption("一箭又一箭 · 进阶版")
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    clock = pygame.time.Clock()
    game = Game()

    while game.running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if game.scene == "play":
                        game.scene = "pause"
                    elif game.scene in ("pause", "levels", "win", "lose"):
                        game.scene = "menu"
                    else:
                        game.running = False
                elif event.key == pygame.K_r and game.scene == "play":
                    game.restart()
                elif event.key == pygame.K_u and game.scene == "play":
                    game.undo()
                elif event.key == pygame.K_h and game.scene == "play":
                    game.use_hint()
                elif event.key == pygame.K_m:
                    game.toggle_sound()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if game.scene == "menu":
                        game.load_level(game.progress.unlocked)
                    elif game.scene == "win":
                        game.load_level(game.level_index + 1)
                    elif game.scene == "lose":
                        game.restart()
                    elif game.scene == "pause":
                        game.scene = "play"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                game.click(event.pos)
        game.update(dt)
        game.draw(screen)
        pygame.display.flip()

    game.progress.save()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
