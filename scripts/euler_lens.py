#!/usr/bin/env python3
"""欧拉透镜（euler_lens）：把欧拉公式 e^(iθ)=cosθ+i·sinθ 的数学结构迁移为图像美学工具。

不是「欧拉魔法让图变美」。是三条可严格验证的迁移：

  ① 色相环 = 复平面单位圆。色相就是相位 θ，颜色和谐 = 相位关系。
     互补 = e^(iπ)（+180°），三角 = e^(i·2π/3)（±120°），邻近 = 小 Δθ。
     用圆统计 resultant R=|Σw·e^(iθ)|/Σw 度量色彩集中/展开。
     → harmony_palette() 用相位旋转生成和谐调色板，直接指导生成 prompt。

  ② 傅里叶 = 复指数分解（欧拉公式是 FFT 的基石）。图像功率谱 P(f)∝1/f^α。
     自然照片/绘画 α≈1.8-2.3；平滑渐变塑料感 α 偏大（高频缺失）。
     ⚠️ 诚实边界：全局径向谱被构图混淆——大片留白会主导谱（船占画面极小时，
     谱斜率反映的是纸白而非笔触）。α 是「全局纹理平衡」信号，不是普适自然度分，
     须与 measure.py 的 flat_area/edge_density 合看，不可单独裁决。

  ③ 对数螺线 e^((a+ib)θ) = 生长×旋转 → 黄金螺线构图视觉重力（叠加分析）。

依赖 numpy + Pillow（无 scipy）。本模块只描述结构，不判美丑；裁决仍归 critique。
"""

from __future__ import annotations

import argparse
import colorsys
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PHI = (1 + 5 ** 0.5) / 2
GOLDEN_B = math.log(PHI) / (math.pi / 2)  # 黄金螺线增长率 ≈0.3063

# 色彩和谐方案 = 相位差（度）。欧拉旋转 e^(iΔθ)
SCHEMES = {
    "mono": [0],
    "analogous": [-30, 0, 30],
    "complementary": [0, 180],
    "split": [0, 150, 210],
    "triadic": [0, 120, 240],
    "tetradic": [0, 90, 180, 270],
}


def harmony_palette(base_hue: float, scheme: str = "triadic",
                    sat: float = 0.55, val: float = 0.82) -> list[dict]:
    """用欧拉相位旋转从基色生成和谐调色板。base_hue 单位度。"""
    if scheme not in SCHEMES:
        raise ValueError(f"未知方案 {scheme}，可选 {list(SCHEMES)}")
    z0 = np.exp(1j * np.deg2rad(base_hue))
    out = []
    for dphase in SCHEMES[scheme]:
        z = z0 * np.exp(1j * np.deg2rad(dphase))  # 欧拉旋转
        hue = float(np.rad2deg(np.angle(z)) % 360)
        r, g, b = colorsys.hsv_to_rgb(hue / 360, sat, val)
        out.append({
            "hue": round(hue, 1), "phase_shift": dphase,
            "hex": "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255)),
        })
    return out


def hue_phases(path: Path, size: int = 256) -> dict:
    """色相=单位圆相位。resultant R 度量集中/展开；检测主色相簇与和谐方案。"""
    img = Image.open(path).convert("HSV").resize((size, size))
    arr = np.asarray(img).astype(np.float64)
    h, s, v = arr[..., 0], arr[..., 1], arr[..., 2]
    hue_deg = h / 255.0 * 360.0
    sat, val = s / 255.0, v / 255.0
    w = (sat * val).ravel()
    chroma_frac = float(w.sum() / (size * size))
    if chroma_frac < 0.02:
        return {"chromatic": False, "chroma_frac": round(chroma_frac, 4),
                "R": None, "dom_hue": None, "harmony": "achromatic 无彩色（水墨/灰阶）",
                "note": "饱和度极低，色相无定义；和谐由墨色浓淡而非色相决定"}
    theta = np.deg2rad(hue_deg.ravel())
    z = np.exp(1j * theta)  # 欧拉公式
    resultant = np.sum(w * z) / np.sum(w)
    R = float(np.abs(resultant))
    dom_hue = float(np.rad2deg(np.angle(resultant)) % 360)
    # 加权色相直方图找主簇
    hist, edges = np.histogram(hue_deg.ravel(), bins=36, range=(0, 360), weights=w)
    peaks = []
    for i in range(36):
        if hist[i] > 0.08 * hist.max() and hist[i] >= hist[(i - 1) % 36] and hist[i] >= hist[(i + 1) % 36]:
            peaks.append((edges[i] + 5, hist[i]))
    peaks.sort(key=lambda x: -x[1])
    dom_hues = [round(p[0], 1) for p in peaks[:4]]
    harmony = _classify(R, dom_hues)
    return {"chromatic": True, "chroma_frac": round(chroma_frac, 4),
            "R": round(R, 3), "dom_hue": round(dom_hue, 1),
            "dom_hues": dom_hues, "harmony": harmony}


def _classify(R: float, dom_hues: list[float]) -> str:
    if R > 0.90:
        return "mono 单色（高度集中，R→1）"
    if R > 0.70:
        return "analogous 邻近（较集中）"
    if len(dom_hues) >= 2:
        diffs = sorted(abs((dom_hues[0] - h + 180) % 360 - 180) for h in dom_hues[1:])
        near = diffs[0]
        if 150 <= near <= 210:
            return "complementary 互补（相位差≈180°，平衡展开）"
        if 100 <= near <= 140:
            return "triadic 三角（相位差≈120°）"
        if near < 60:
            return "analogous 邻近"
    if R < 0.45:
        return "spread 多色平衡展开（R→0）"
    return "mixed 混合"


def spectrum(path: Path, size: int = 512) -> dict:
    """径向功率谱斜率 α（P(f)∝1/f^α）。FFT=欧拉公式图像化。
    ⚠️ 留白构图会混淆全局谱；返回 flat_confounded 警示，须与 flat_area 合看。"""
    img = Image.open(path).convert("L").resize((size, size))
    a = np.asarray(img, dtype=np.float64)
    flat_frac = float(np.mean(np.abs(a - np.median(a)) < 8))  # 近平坦像素占比
    a = a - a.mean()
    w = np.hanning(size)
    a = a * np.outer(w, w)
    F = np.fft.fftshift(np.fft.fft2(a))
    power = np.abs(F) ** 2
    fy, fx = np.mgrid[0:size, 0:size] - size // 2
    fr = np.sqrt(fx ** 2 + fy ** 2)
    bins = np.logspace(np.log10(2), np.log10(size // 2), 24)
    idx = np.digitize(fr.ravel(), bins)
    pr = power.ravel()
    centers, means = [], []
    for i in range(1, len(bins)):
        m = idx == i
        if m.sum() > 8:
            centers.append(math.sqrt(bins[i - 1] * bins[i]))
            means.append(pr[m].mean())
    centers, means = np.array(centers), np.array(means)
    sel = slice(2, -2)
    slope, _ = np.polyfit(np.log(centers[sel]), np.log(means[sel] + 1e-12), 1)
    alpha = float(-slope)
    confounded = flat_frac > 0.6
    if confounded:
        note = f"⚠️ 近平坦像素 {flat_frac:.0%}，全局谱被留白主导，α 反映纸白而非笔触；不可单独当自然度裁决"
    elif alpha > 2.8:
        note = "α 偏大：高频缺失，倾向平滑渐变/塑料感（与 edge_density 合看）"
    elif alpha < 1.5:
        note = "α 偏小：高频丰富，纹理密集或人工噪点"
    else:
        note = "α 落在自然图像常见区间 1.8-2.3 附近"
    return {"alpha": round(alpha, 3), "flat_frac": round(flat_frac, 3),
            "flat_confounded": confounded, "note": note,
            "curve": [(round(float(c), 2), round(float(m), 3)) for c, m in zip(centers, means)]}


def render_hue_circle(path: Path, out: Path, size: int = 720) -> Path:
    """把图像色相画成单位圆上的相位向量 e^(iθ)——欧拉→色彩的可视化。"""
    info = hue_phases(path)
    img = Image.open(path).convert("HSV").resize((256, 256))
    arr = np.asarray(img).astype(np.float64)
    hue_deg = arr[..., 0] / 255.0 * 360.0
    w = (arr[..., 1] / 255.0 * arr[..., 2] / 255.0)
    canvas = Image.new("RGB", (size, size), (248, 248, 245))
    draw = ImageDraw.Draw(canvas)
    cx, cy, rad = size // 2, size // 2 + 20, size // 2 - 90
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22)
        fontS = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
    except Exception:
        font = fontS = ImageFont.load_default()
    draw.text((24, 20), f"色相环 = 单位圆  e^(iθ)   {Path(path).name}", font=font, fill=(40, 40, 40))
    # 单位圆与色相刻度
    draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=(180, 180, 180), width=2)
    for deg in range(0, 360, 30):
        th = np.deg2rad(deg)
        x1, y1 = cx + rad * np.cos(th), cy - rad * np.sin(th)
        x2, y2 = cx + (rad + 12) * np.cos(th), cy - (rad + 12) * np.sin(th)
        draw.line([x1, y1, x2, y2], fill=(150, 150, 150), width=1)
        rr, gg, bb = colorsys.hsv_to_rgb(deg / 360, 0.7, 0.85)
        draw.ellipse([x2 - 5, y2 - 5, x2 + 5, y2 + 5], fill=(int(rr * 255), int(gg * 255), int(bb * 255)))
    # 图像色相相位向量（按权重采样）
    mask = w > 0.05
    hs = hue_deg[mask]
    ws = w[mask]
    if len(hs) > 4000:
        sel = np.random.default_rng(0).choice(len(hs), 4000, replace=False)
        hs, ws = hs[sel], ws[sel]
    for hdeg, wt in zip(hs, ws):
        th = np.deg2rad(hdeg)
        rr, gg, bb = colorsys.hsv_to_rgb(hdeg / 360, 0.75, 0.85)
        length = rad * (0.35 + 0.6 * min(wt, 1.0))
        x, y = cx + length * np.cos(th), cy - length * np.sin(th)
        draw.line([cx, cy, x, y], fill=(int(rr * 255), int(gg * 255), int(bb * 255)), width=1)
    # resultant 向量
    if info["R"] is not None:
        th = np.deg2rad(info["dom_hue"])
        x, y = cx + rad * info["R"] * np.cos(th), cy - rad * info["R"] * np.sin(th)
        draw.line([cx, cy, x, y], fill=(196, 30, 58), width=4)
        draw.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(196, 30, 58))
    sub = (f"R={info['R']}  主色相={info['dom_hue']}°  彩度={info['chroma_frac']}  {info['harmony']}"
           if info["R"] is not None else f"无彩色  彩度={info['chroma_frac']}  {info['harmony']}")
    draw.text((24, size - 46), sub, font=fontS, fill=(70, 70, 70))
    canvas.save(out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="euler_lens.py", description="欧拉透镜：色相相位/和谐调色板/功率谱")
    sub = parser.add_subparsers(dest="command", required=True)
    h = sub.add_parser("hue", help="色相相位和谐分析")
    h.add_argument("image")
    p = sub.add_parser("palette", help="欧拉相位旋转生成和谐调色板")
    p.add_argument("base_hue", type=float)
    p.add_argument("--scheme", default="triadic", choices=list(SCHEMES))
    p.add_argument("--sat", type=float, default=0.55)
    p.add_argument("--val", type=float, default=0.82)
    s = sub.add_parser("spectrum", help="径向功率谱斜率 α（带留白混淆警示）")
    s.add_argument("image")
    c = sub.add_parser("circle", help="渲染色相单位圆可视化")
    c.add_argument("image")
    c.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    if args.command == "palette":
        pal = harmony_palette(args.base_hue, args.scheme, args.sat, args.val)
        print(f"基色 {args.base_hue}°  方案 {args.scheme}（相位旋转 e^(iΔθ)）")
        for c in pal:
            print(f"  Δ{c['phase_shift']:+4d}° → 色相 {c['hue']:6.1f}°  {c['hex']}")
        return 0
    if args.command == "circle":
        out = render_hue_circle(Path(args.image), Path(args.out))
        print(f"已渲染 {out}")
        return 0
    path = Path(args.image).expanduser()
    if not path.is_file():
        print(f"⛔ 图像不存在：{args.image}", file=sys.stderr)
        return 1
    if args.command == "hue":
        print(json.dumps(hue_phases(path), ensure_ascii=False, indent=2))
    elif args.command == "spectrum":
        info = spectrum(path)
        curve = info.pop("curve")
        print(json.dumps(info, ensure_ascii=False, indent=2))
        print(f"  谱曲线点数：{len(curve)}（freq, power）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())