# -*- coding: utf-8 -*-
"""
关卡生成 / 可解性验证脚本（开发辅助工具，游戏运行本身不需要它）

思路（逆推构造法）：
  一箭又一箭的规则是"箭头前方到边界之间没有其它箭头才能飞出去"。
  如果直接随机撒箭头，很容易撒出死局，例如 2 格棋盘上的 "→ ←" 谁也走不了。
  所以这里反过来构造：从空棋盘开始，每次往一个空格放一个箭头，
  要求"放下去的时候，它朝着自己方向到边界之间没有任何已经放好的箭头"。

  设放置顺序为 p1, p2, ... pn，则 pn 放下去时它的射线是干净的，
  所以在完整棋盘里 pn 一定能先飞走；飞走之后棋盘回到 {p1..p(n-1)}，
  正好是 p(n-1) 放置时的样子，于是 p(n-1) 也一定能飞走……
  即：**按放置顺序的逆序消除，一定可以通关**。构造即证明。

  为了保险，脚本最后还会用一个暴力搜索求解器（带记忆化）再验证一遍。

运行： python tools/gen_levels.py
"""

import random
import sys
from functools import lru_cache

DIRS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
ARROW_CHARS = {"U": "^", "D": "v", "L": "<", "R": ">"}


def ray_clear(x, y, d, occupied, w, h):
    """从 (x,y) 沿方向 d 走到边界，路上是否没有其它箭头。occupied 是坐标集合。"""
    dx, dy = DIRS[d]
    cx, cy = x + dx, y + dy
    while 0 <= cx < w and 0 <= cy < h:
        if (cx, cy) in occupied:
            return False
        cx += dx
        cy += dy
    return True


def generate(w, h, n, rng):
    """逆推构造一个必定可解的布局。返回 (布局字典, 一个合法解法)。"""
    cells = [(x, y) for y in range(h) for x in range(w)]
    placed = {}
    order = []
    for _ in range(n):
        cands = []
        for c in cells:
            if c in placed:
                continue
            for d in DIRS:
                if ray_clear(c[0], c[1], d, placed, w, h):
                    cands.append((c, d))
        if not cands:          # 棋盘太满，放不下了
            return None
        c, d = rng.choice(cands)
        placed[c] = d
        order.append(c)
    return placed, list(reversed(order))     # 解法 = 放置顺序的逆序


def count_free(placed, w, h):
    """初始棋盘上一开始就能飞出去的箭头数量（越大越简单）。"""
    occ = set(placed)
    return sum(1 for c, d in placed.items() if ray_clear(c[0], c[1], d, occ - {c}, w, h))


def solve(placed, w, h):
    """暴力搜索求解（记忆化），用于独立验证布局真的可解。"""
    memo = {}

    def rec(state):
        if not state:
            return []
        if state in memo:
            return memo[state]
        memo[state] = None                     # 先标记，避免环
        for c in sorted(state):
            d = placed[c]
            if ray_clear(c[0], c[1], d, state - {c}, w, h):
                rest = rec(state - {c})
                if rest is not None:
                    memo[state] = [c] + rest
                    return memo[state]
        return None

    return rec(frozenset(placed))


def to_text(placed, w, h):
    rows = []
    for y in range(h):
        rows.append("".join(placed.get((x, y), ".") for x in range(w)))
    return rows


def to_pretty(placed, w, h):
    rows = []
    for y in range(h):
        rows.append(" ".join(ARROW_CHARS.get(placed.get((x, y), "."), ".") for x in range(w)))
    return rows


def simulate(placed, order, w, h):
    """按给定顺序依次消除，检查每一步是否真的可以飞出去。返回 None 表示解法非法。"""
    board = set(placed)
    for c in order:
        if c not in board:
            return None
        if not ray_clear(c[0], c[1], placed[c], board - {c}, w, h):
            return None
        board.remove(c)
    return True if not board else None


def make_level(w, h, n, rng, max_free, tries=6000):
    """随机生成若干个布局，挑一个"初始能直接消除的箭头数最少"的（越少越有挑战性）。"""
    best = None
    best_free = 10 ** 9
    for _ in range(tries):
        r = generate(w, h, n, rng)
        if r is None:
            continue
        placed, order = r
        xs = {c[0] for c in placed}
        ys = {c[1] for c in placed}
        if len(xs) < 3 or len(ys) < 3:       # 排除所有箭头挤在一条线上的难看布局
            continue
        if simulate(placed, order, w, h) is None:
            continue
        f = count_free(placed, w, h)
        if f < best_free:
            best, best_free = (placed, order), f
            if f <= 1:                       # 已经足够难了，提前收工
                break
    if best is not None and best_free <= max_free:
        return best
    return best                              # 实在达不到要求就用当前最优的


# 关卡规格：(列数, 行数, 箭头数, 初始可直接消除数量上限)
SPECS_V1 = [
    (4, 3, 5, 3),
    (5, 4, 8, 2),
    (6, 4, 10, 2),
]

def build_one(i, w, h, n, mx, seed, tries=6000):
    rng = random.Random(seed + i * 977)
    r = make_level(w, h, n, rng, mx, tries=tries)
    if r is None:
        return None
    placed, order = r
    assert simulate(placed, order, w, h), "解法验证失败！"
    f = count_free(placed, w, h)
    out = []
    out.append("")
    out.append("# ---- 第 %d 关  %dx%d  共 %d 个箭头  初始可直接消除 %d 个 ----"
               % (i, w, h, len(placed), f))
    out.append("# 参考解法（按此顺序点击即可通关）:")
    out.append("#   " + " -> ".join("(%d,%d)" % c for c in order))
    out.append("# 图形预览:")
    for line in to_pretty(placed, w, h):
        out.append("#   " + line)
    out.append("    [")
    for row in to_text(placed, w, h):
        out.append('        "%s",' % row)
    out.append("    ],")
    return "\n".join(out)


def emit(name, specs, seed, fh):
    fh.write("=" * 64 + "\n" + name + "\n" + "=" * 64 + "\n")
    for i, (w, h, n, mx) in enumerate(specs, 1):
        block = build_one(i, w, h, n, mx, seed)
        if block is None:
            block = "\n# 第 %d 关生成失败！" % i
        fh.write(block + "\n")
        print("关 %d 完成" % i)


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    with open("tools/levels_out.txt", "w", encoding="utf-8") as fh:
        emit("基础版 3 关", SPECS_V1, 20260921, fh)
    print("结果已写入 tools/levels_out.txt")
