#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
figure_layout_qa.py — 出图前的版面检查（matplotlib）：重叠与多余留白。

  python figure_layout_qa.py 作图脚本.py [脚本参数…] [--json 报告.json] [--max-gap-mm 4] [--min-fill 0.45]
  或在作图脚本里：  from figure_layout_qa import layout_qa, whitespace_qa;  issues = layout_qa(fig)

CLI 用 Agg 后端运行作图脚本，在每次 savefig 之前检查该图，**不写图**；脚本照常结束。
检查两类问题（第十一轮：作者先后指出“文字与元素重叠”和“不美观、多余空白”）：
- 重叠（必须处理）：文字与文字、文字与数据线或标记、文字与标签条（条内自身的标签除外）、图例框与任一面板的数据线与坐标轴线、
  文字超出画布。只计入实际画出的刻度标签。
- 图解（路径图、流程图）：箭头不得进入方框内部（FancyBboxPatch）、箭头端点离最近方框边不得超过 3 mm（悬空）、箭头不得穿过文字。
  箭头路径含闭合占位点与多段子路径，只取真实线段检查。
- 留白（供看）：面板标题与坐标区的间距超过 --max-gap-mm（默认 4 mm）；画布四边的空白超过 8 mm；
  坐标区、文字与图例合计占画布的比例低于 --min-fill（默认 0.45）。这些是提醒：期刊图通常紧凑，留白多时先看能否合并标签栏、
  共用坐标轴、把标题贴近坐标区，而不是缩小字号。
退出码：0 检查完成且没有重叠；1 检查完成且有重叠；2 检查无效（含无 savefig、脚本非零退出）。
--json 保留图件列表格式；状态另存为 报告.json.status.json，可用 --status-json 路径 指定。
未给 --json 时，状态默认写到当前目录的 作图脚本名.figure-qa.status.json。本工具上次写的报告与状态可以覆盖（复跑是常态）；
其他已有文件与输入脚本一律不覆盖。
检查运行可信的作图脚本，并非任意脚本的安全隔离；复杂遮挡和排版仍须人工看图。
"""
import argparse, json, os, runpy, sys
from pathlib import Path
import numpy as np

for _s in (sys.stdout, sys.stderr):          # Windows 控制台与 GBK 管道下也输出 UTF-8（与其他脚本一致）
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

MM = 1 / 25.4


def _texts(fig):
    out = [("figure", t) for t in fig.texts]
    for lg in fig.legends:
        if not lg.get_visible():
            continue
        out += [("figure:legend", t) for t in lg.get_texts()]
    for ax in fig.axes:
        if not ax.get_visible():
            continue
        name = "axes@%.0fmm" % (ax.get_position().x0 * fig.get_figwidth() / MM)
        out += [(name, t) for t in (ax.title, ax._left_title, ax._right_title, ax.xaxis.label, ax.yaxis.label)]
        for axis in (ax.xaxis, ax.yaxis):
            lo, hi = sorted(axis.get_view_interval())
            out += [(name, tk.label1) for tk in axis.get_major_ticks() if tk.label1.get_visible() and lo - 1e-9 <= tk.get_loc() <= hi + 1e-9]
        out += [(name, t) for t in ax.texts]
        if ax.get_legend() is not None and ax.get_legend().get_visible():
            out += [(name + ":legend", t) for t in ax.get_legend().get_texts()]
    from matplotlib.colors import to_rgba
    return [(n, t) for n, t in out if t.get_visible() and t.get_text().strip()
            and to_rgba(t.get_color(), t.get_alpha())[3] > 0]


def _box(b, px=0.75):
    return (b.x0 + px, b.y0 + px, b.x1 - px, b.y1 - px)


def _inside(p, r):
    return r[0] < p[0] < r[2] and r[1] < p[1] < r[3]


def _samples(xy, step=0.75):
    pts = [xy]
    for (x0, y0), (x1, y1) in zip(xy[:-1], xy[1:]):
        n = max(2, int(np.hypot(x1 - x0, y1 - y0) / step) + 1)
        pts.append(np.column_stack([np.linspace(x0, x1, n), np.linspace(y0, y1, n)]))
    return np.vstack(pts)


def _line_points(l, clip=None):
    xy = l.get_transform().transform(np.column_stack(l.get_data()).astype(float))
    pts = _samples(xy) if l.get_linestyle() not in ("None", "none", "") else xy
    if clip is not None:
        pts = pts[(pts[:, 0] >= clip.x0 - 1) & (pts[:, 0] <= clip.x1 + 1) & (pts[:, 1] >= clip.y0 - 1) & (pts[:, 1] <= clip.y1 + 1)]
    if l.get_marker() not in (None, "None", "none", "") and len(pts):
        r = l.get_markersize() * l.figure.dpi / 72 / 2
        pts = np.vstack([pts] + [pts + d for d in ((r, 0), (-r, 0), (0, r), (0, -r))])
    return pts


def _painted_geometry(fig):
    """Actual Agg paint, including marker sizes, transforms, alpha and clip paths.

    Render each data artist alone on a transparent canvas, retaining only its
    nonempty pixel bounds. This avoids treating a collection's bounding box as
    filled data (e.g. the space between scatter points or inside a hollow ring).
    It does not attempt to reason about all artists' final occlusion/z-order.
    """
    from matplotlib.backends.backend_agg import RendererAgg
    renderer = RendererAgg(fig.bbox.width, fig.bbox.height, fig.dpi)
    cache = {}

    def geometry(artist):
        if artist in cache:
            return cache[artist]
        alpha_value = artist.get_alpha()
        if (not fig.get_visible() or not artist.get_visible()
                or (np.ndim(alpha_value) == 0 and alpha_value == 0)
                or (artist.axes is not None and not artist.axes.get_visible())):
            cache[artist] = None
            return None
        renderer.clear()
        artist.draw(renderer)
        alpha = np.asarray(renderer.buffer_rgba())[:, :, 3]
        yy, xx = np.nonzero(alpha)
        result = None
        if len(xx):
            x0, x1, y0, y1 = xx.min(), xx.max() + 1, yy.min(), yy.max() + 1
            result = (x0, alpha.shape[0] - y1, alpha[y0:y1, x0:x1][::-1].copy())
        cache[artist] = result
        return result

    return geometry


def _paint_hits(paint, box, covered=None):
    if paint is None:
        return False
    x, y, alpha = paint
    x0, y0 = max(0, int(np.floor(box[0] - x))), max(0, int(np.floor(box[1] - y)))
    x1, y1 = min(alpha.shape[1], int(np.ceil(box[2] - x))), min(alpha.shape[0], int(np.ceil(box[3] - y)))
    if x0 >= x1 or y0 >= y1:
        return False
    visible = alpha[y0:y1, x0:x1] > 0
    if covered is not None:
        # An opaque annotation background above the data is a deliberate label.
        cx, cy, ca = covered
        xx0, yy0 = max(x + x0, cx), max(y + y0, cy)
        xx1, yy1 = min(x + x1, cx + ca.shape[1]), min(y + y1, cy + ca.shape[0])
        if xx0 < xx1 and yy0 < yy1:
            visible = visible.copy()
            visible[yy0 - y - y0:yy1 - y - y0, xx0 - x - x0:xx1 - x - x0] &= (
                ca[yy0 - cy:yy1 - cy, xx0 - cx:xx1 - cx] < 255)
    return bool(visible.any())


def layout_qa(fig):
    """Overlaps that must be fixed before saving: list of readable strings (empty = PASS)."""
    from matplotlib.patches import Rectangle
    from matplotlib.text import Text
    if not fig.get_visible():
        return []
    fig.canvas.draw()
    rd = fig.canvas.get_renderer()
    W, H = fig.bbox.width, fig.bbox.height
    geometry = _painted_geometry(fig)
    # Annotation.get_window_extent also includes its arrow. Treat only its text
    # as a label; otherwise a valid leader line makes its own label "overlap".
    texts = [(n, t, _box(Text.get_window_extent(t, rd))) for n, t in _texts(fig)]
    # Clipped-away text is not part of the visible layout. Retain ordinary text
    # boxes (including outside-canvas checks), but trim intentionally clipped text.
    visible_texts = []
    for n, t, b in texts:
        if t.get_clip_on() and (t.get_clip_box() is not None or t.get_clip_path() is not None):
            paint = geometry(t)
            if paint is None:
                continue
            x, y, alpha = paint
            b = (max(b[0], x), max(b[1], y), min(b[2], x + alpha.shape[1]), min(b[3], y + alpha.shape[0]))
        visible_texts.append((n, t, b))
    texts = visible_texts
    issues = []
    for i, (n1, t1, b1) in enumerate(texts):
        if b1[0] < -0.5 or b1[1] < -0.5 or b1[2] > W + 0.5 or b1[3] > H + 0.5:
            issues.append("text outside canvas: %r" % t1.get_text())
        for n2, t2, b2 in texts[i + 1:]:
            if b1[0] < b2[2] and b2[0] < b1[2] and b1[1] < b2[3] and b2[1] < b1[3]:
                issues.append("text/text: %r [%s] x %r [%s]" % (t1.get_text(), n1, t2.get_text(), n2))
    for ax in fig.axes:
        if not ax.get_visible():
            continue
        for artist in list(ax.get_lines()) + list(ax.collections):
            paint = geometry(artist)
            for n, t, b in texts:
                bg = t.get_bbox_patch()
                cover = geometry(bg) if bg is not None and t.get_zorder() > artist.get_zorder() else None
                if _paint_hits(paint, b, cover):
                    kind = "a line or marker" if artist in ax.get_lines() else "a plotted collection"
                    issues.append("text/data: %r [%s] crosses %s" % (t.get_text(), n, kind))
        for p in ax.patches:
            if isinstance(p, Rectangle) and p.get_visible():
                paint = geometry(p)
                if paint is None:
                    continue
                bb = p.get_window_extent(rd)
                rb = (bb.x0, bb.y0, bb.x1, bb.y1)
                for n, t, b in texts:
                    if _inside(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), rb):
                        continue
                    if _paint_hits(paint, b):
                        issues.append("text/bar: %r [%s] overlaps a label bar" % (t.get_text(), n))

    # --- 箭头与方框（图解、路径图）：箭头不得进入方框内部，端点离方框边不得超过 3 mm，也不得穿过文字 ---
    # 箭头路径含 CLOSEPOLY 占位点 (0,0) 与多段子路径：只取真实线段，不能把相邻顶点直接连成线（否则会产生横穿整图的假线段）
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    mmpx = fig.dpi * MM
    for ax in fig.axes:
        if not ax.get_visible():
            continue
        arrows = [p_ for p_ in ax.patches if isinstance(p_, FancyArrowPatch)]
        arrows += [t_.arrow_patch for t_ in ax.texts if getattr(t_, "arrow_patch", None) is not None]
        boxes = []
        for p_ in ax.patches:
            if isinstance(p_, FancyBboxPatch) and geometry(p_) is not None:
                bb = p_.get_window_extent(rd)
                boxes.append((bb.x0, bb.y0, bb.x1, bb.y1))
        for ar in arrows:
            paint = geometry(ar)
            if paint is None:
                continue
            disp = ar.get_transform().transform_path(ar.get_path())
            segments = [_samples(poly, 1.5) for poly in disp.to_polygons(closed_only=False) if len(poly) > 1]
            pts = np.vstack(segments) if segments else np.empty((0, 2))
            for bx in boxes:
                core = (bx[0] + 2.0, bx[1] + 2.0, bx[2] - 2.0, bx[3] - 2.0)
                if any(_inside(q, core) for q in pts) and _paint_hits(paint, core):
                    issues.append("arrow/box: an arrow runs into a box")
            for n, t, b in texts:
                if any(_inside(q, b) for q in pts) and _paint_hits(paint, b):
                    issues.append("text/arrow: %r [%s] is crossed by an arrow" % (t.get_text(), n))
            ends = getattr(ar, "_posA_posB", None)
            if boxes and ends:
                for q in ar.get_transform().transform(np.asarray(ends, float)):
                    d = min(((max(bx[0] - q[0], 0, q[0] - bx[2])) ** 2 + (max(bx[1] - q[1], 0, q[1] - bx[3])) ** 2) ** 0.5 for bx in boxes)
                    if d > 3.0 * mmpx:
                        issues.append("arrow/end: an arrow end floats %.1f mm away from every box" % (d / mmpx))
    for lg in list(fig.legends) + [a.get_legend() for a in fig.axes if a.get_visible() and a.get_legend() is not None]:
        if not lg.get_visible():
            continue
        lb = _box(lg.get_window_extent(rd), 0.0)
        for a in fig.axes:
            if not a.get_visible():
                continue
            for side, sp in a.spines.items():
                if _paint_hits(geometry(sp), lb):
                    issues.append("legend/axis: a legend box overlaps the %s axis line of a panel" % side)
            for artist in list(a.get_lines()) + list(a.collections):
                if _paint_hits(geometry(artist), lb):
                    issues.append("legend/data: a legend box crosses a plotted line or collection")
    return sorted(set(issues))


def whitespace_qa(fig, max_gap_mm=4.0, min_fill=0.45, edge_mm=8.0):
    """Advisory notes on redundant white space (empty list = compact)."""
    fig.canvas.draw()
    rd = fig.canvas.get_renderer()
    px_mm = fig.dpi * MM
    W, H = fig.bbox.width, fig.bbox.height
    notes, boxes = [], []
    for ax in fig.axes:
        boxes.append(ax.get_tightbbox(rd))
        b = ax.get_window_extent(rd)
        for t in (ax.title, ax._left_title):
            if t.get_text().strip():
                g = (t.get_window_extent(rd).y0 - b.y1) / px_mm
                if g > max_gap_mm:
                    notes.append("title %r sits %.1f mm above its axes (> %.1f mm)" % (t.get_text(), g, max_gap_mm))
    for t in fig.texts:
        if t.get_text().strip():
            tb = t.get_window_extent(rd)
            boxes.append(tb)
            below = [ax.get_window_extent(rd) for ax in fig.axes if ax.get_window_extent(rd).x0 - 2 < tb.x1 and tb.x0 < ax.get_window_extent(rd).x1 + 2 and ax.get_window_extent(rd).y1 <= tb.y0 + 1]
            if below and t.get_fontweight() in ("bold", 700) and len(t.get_text()) > 2:
                g = (tb.y0 - max(b.y1 for b in below)) / px_mm
                if g > max_gap_mm:
                    notes.append("heading %r sits %.1f mm above the panel below it (> %.1f mm)" % (t.get_text(), g, max_gap_mm))
    boxes += [lg.get_window_extent(rd) for lg in fig.legends]
    if boxes:
        x0, y0 = min(b.x0 for b in boxes), min(b.y0 for b in boxes)
        x1, y1 = max(b.x1 for b in boxes), max(b.y1 for b in boxes)
        for side, gap in (("left", x0), ("bottom", y0), ("right", W - x1), ("top", H - y1)):
            if gap / px_mm > edge_mm:
                notes.append("%.1f mm of empty %s margin (> %.0f mm)" % (gap / px_mm, side, edge_mm))
        grid = np.zeros((int(H // 4) + 1, int(W // 4) + 1), bool)
        for b in boxes:
            grid[max(0, int(b.y0 // 4)):int(b.y1 // 4) + 1, max(0, int(b.x0 // 4)):int(b.x1 // 4) + 1] = True
        fill = grid.mean()
        if fill < min_fill:
            notes.append("axes, text and legends cover %.0f%% of the canvas (< %.0f%%): consider shared axes, shorter label columns or a smaller canvas" % (100 * fill, 100 * min_fill))
    return notes


def _is_own_output(path):
    """True only for a previous status or report written by this tool (re-running a figure check is the normal loop)."""
    try:
        with Path(path).open(encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return False
    if isinstance(d, dict):
        return d.get("tool") == "figure_layout_qa" or {"status", "checked_count", "qa_exit"} <= set(d)
    return isinstance(d, list) and all(isinstance(x, dict) and {"file", "overlaps", "whitespace"} <= set(x) for x in d)


def _new_output(path, script=None):
    """Reject input aliases, foreign existing files, and unusable parent directories.
    A previous report or status written by this tool may be replaced; any other existing file is never overwritten."""
    path = Path(path).expanduser().resolve()
    if script is not None and path == Path(script).expanduser().resolve():
        raise ValueError("输出路径不能是输入脚本：%s" % path)
    if path.exists() and not _is_own_output(path):
        raise ValueError("输出已存在且不是本工具的报告，不覆盖：%s" % path)
    if not path.parent.is_dir():
        raise ValueError("输出目录不存在：%s" % path.parent)
    return path


def _write_new_json(path, data):
    # New files: exclusive creation (also protects a file created after validation).
    # A previous report of this tool: write a sibling temp file and replace it atomically.
    path = Path(path)
    if path.exists():
        if not _is_own_output(path):
            raise ValueError("输出已存在且不是本工具的报告，不覆盖：%s" % path)
        tmp = path.with_name(".%s.%d.tmp" % (path.name, os.getpid()))
        with tmp.open("x", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        return
    with path.open("x", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)


def _save_status(path, data, script=None):
    """Never replace a failed/unsafe target; put error status in a fresh fallback."""
    try:
        _write_new_json(_new_output(path, script), data)
        print("检查状态：%s [%s]" % (data["status"], path))
        return True
    except (OSError, ValueError) as e:
        print("状态输出不可用：%s" % e, file=sys.stderr)
        data.update(status="invalid", qa_exit=2, reason="状态报告无法保存：%s" % e)
    # Include the PID and use exclusive creation; no previous report is reused.
    for i in range(100):
        fallback = Path.cwd() / ("figure-qa.invalid.%s.%s.status.json" % (os.getpid(), i))
        try:
            _write_new_json(_new_output(fallback, script), data)
            print("检查状态：invalid [%s]" % fallback, file=sys.stderr)
            return False
        except (OSError, ValueError):
            continue
    print("无法保存检查状态", file=sys.stderr)
    return False


def main(argv=None):
    # 本工具的选项可以写在作图脚本前后任何位置；其余参数原样交给作图脚本
    argv = list(sys.argv[1:] if argv is None else argv)
    own = {"--json": "", "--status-json": "", "--max-gap-mm": "4.0", "--min-fill": "0.45"}
    rest, i, parse_error = [], 0, None
    while i < len(argv):
        if argv[i] in own:
            if i + 1 >= len(argv) or argv[i + 1] in own:
                parse_error = "选项缺少参数：%s" % argv[i]
                i += 1
                continue
            own[argv[i]] = argv[i + 1]
            i += 2
            continue
        if argv[i] in ("-h", "--help"):
            print(__doc__)
            return 0
        rest.append(argv[i])
        i += 1
    script = rest[0] if rest else None
    status_path = own["--status-json"] or (own["--json"] + ".status.json" if own["--json"] else
                                          (Path(script).name if script else "figure-layout-qa") + ".figure-qa.status.json")
    status = {"tool": "figure_layout_qa", "status": "invalid", "checked_count": 0, "script_exit": None, "qa_exit": 2}
    found, report_path = [], None
    try:
        if parse_error:
            raise ValueError(parse_error)
        if script is None:
            raise ValueError("用法：python figure_layout_qa.py 作图脚本.py [--json 报告.json]")
        a = argparse.Namespace(script=script, args=rest[1:], max_gap_mm=float(own["--max-gap-mm"]), min_fill=float(own["--min-fill"]))
        if not np.isfinite(a.max_gap_mm) or a.max_gap_mm < 0 or not 0 <= a.min_fill <= 1:
            raise ValueError("max-gap-mm 须非负且有限，min-fill 须在 0 到 1 之间")
        if not Path(script).is_file():
            raise ValueError("输入脚本不存在：%s" % script)
        if own["--json"]:
            report_path = _new_output(own["--json"], script)
        status_path = _new_output(status_path, script)
        if report_path == status_path:
            raise ValueError("图件报告与状态报告必须使用不同路径")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.figure as mf

        def check(self, fname, *k, **kw):
            found.append({"file": str(fname), "overlaps": layout_qa(self), "whitespace": whitespace_qa(self, a.max_gap_mm, a.min_fill)})

        savefig, old_argv, old_path = mf.Figure.savefig, sys.argv, sys.path[:]
        mf.Figure.savefig = check
        sys.argv = [a.script] + a.args
        sys.path.insert(0, os.path.dirname(os.path.abspath(a.script)))
        try:
            runpy.run_path(a.script, run_name="__main__")
            status["script_exit"] = 0
        except SystemExit as e:
            status["script_exit"] = 0 if e.code is None else e.code if isinstance(e.code, int) else 1
            if status["script_exit"] != 0:
                raise RuntimeError("作图脚本非零退出：%s" % e.code) from e
        except Exception as e:                                    # noqa: BLE001
            status["script_exit"] = 1
            status["script_exception"] = type(e).__name__
            raise RuntimeError("作图脚本运行出错：%s: %s" % (type(e).__name__, e)) from e
        finally:
            mf.Figure.savefig, sys.argv = savefig, old_argv
            sys.path[:] = old_path
        if not found:
            raise ValueError("脚本没有调用 savefig，没有可检查的图；检查无效")
        status.update(status="complete", qa_exit=1 if any(f["overlaps"] for f in found) else 0)
    except (Exception,) as e:                                     # noqa: BLE001
        status["reason"] = str(e)
        print("检查无效：%s" % e, file=sys.stderr)
    status["checked_count"] = len(found)
    for f in found:
        print("%s：重叠 %d 项；留白提醒 %d 项" % (f["file"], len(f["overlaps"]), len(f["whitespace"])))
        for x in f["overlaps"]:
            print("  [重叠] " + x)
        for x in f["whitespace"]:
            print("  [留白] " + x)
    # Keep partial checks on script failure, but never write a target rejected at
    # preflight (or a report created by the plotting script in the meantime).
    if report_path is not None and status["script_exit"] is not None:
        try:
            _write_new_json(_new_output(report_path, script), found)
        except (OSError, ValueError) as e:
            status.update(status="invalid", qa_exit=2, reason="图件报告无法保存：%s" % e)
            print(status["reason"], file=sys.stderr)
    if not _save_status(status_path, status, script):
        return 2
    return status["qa_exit"]


if __name__ == "__main__":
    sys.exit(main())
