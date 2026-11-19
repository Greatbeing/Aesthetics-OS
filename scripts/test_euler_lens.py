#!/usr/bin/env python3
"""euler_lens 回归测试：验证欧拉迁移的数学正确性与诚实边界。

需要 numpy + Pillow。用法：python scripts/test_euler_lens.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import euler_lens as E  # noqa: E402

PASS, FAIL = "✅", "⛔"
results: list[tuple[bool, str]] = []


def check(cond: bool, msg: str) -> None:
    results.append((cond, msg))
    print(f"{PASS if cond else FAIL} {msg}")


def save(arr: np.ndarray, path: Path) -> Path:
    Image.fromarray(arr.astype(np.uint8)).save(path)
    return path


def main() -> int:
    # 调色板相位旋转正确性
    pal = E.harmony_palette(210, "triadic")
    hues = [c["hue"] for c in pal]
    check(hues == [210.0, 330.0, 90.0], f"三角方案相位旋转 210→{hues}")
    pal = E.harmony_palette(210, "complementary")
    check([c["hue"] for c in pal] == [210.0, 30.0], "互补方案 210→210/30（+π）")
    pal = E.harmony_palette(0, "mono")
    check([c["hue"] for c in pal] == [0.0], "单色方案不变")
    pal = E.harmony_palette(30, "split")
    check([c["hue"] for c in pal] == [30.0, 180.0, 240.0], "分裂互补 30→30/180/240")
    try:
        E.harmony_palette(0, "bogus")
        check(False, "未知方案应抛错")
    except ValueError:
        check(True, "未知方案抛 ValueError")

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        # 无彩色（灰阶）→ achromatic
        gray = np.tile(np.linspace(0, 255, 256, dtype=np.uint8), (256, 1))
        gray = np.stack([gray] * 3, axis=-1)
        info = E.hue_phases(save(gray, d / "gray.png"))
        check(info["chromatic"] is False and info["R"] is None, "灰阶判 achromatic，R 无定义")

        # 单色（纯红）→ R→1 mono
        red = np.zeros((256, 256, 3), dtype=np.uint8)
        red[..., 0] = 200
        info = E.hue_phases(save(red, d / "red.png"))
        check(info["chromatic"] and info["R"] > 0.9, f"纯红 R={info['R']}→1 单色集中")

        # 互补（左红右青）→ R 低，平衡展开
        comp = np.zeros((256, 256, 3), dtype=np.uint8)
        comp[:, :128, 0] = 200          # 红 hue 0
        comp[:, 128:, 1] = 200          # 青 hue 180
        comp[:, 128:, 2] = 200
        info = E.hue_phases(save(comp, d / "comp.png"))
        check(info["R"] < 0.3, f"红青互补 R={info['R']}→0 平衡展开")
        check("complementary" in info["harmony"], f"互补图判互补：{info['harmony']}")

        # 谱：纯平坦 → flat_confounded
        flat = np.full((512, 512), 128, dtype=np.uint8)
        sp = E.spectrum(save(flat, d / "flat.png"))
        check(sp["flat_confounded"] is True, "纯平坦图鉴留白混淆警示")

        # 谱：白噪声 α 小（高频丰富）vs 平滑渐变 α 大
        rng = np.random.default_rng(1)
        noise = rng.integers(0, 256, (512, 512), dtype=np.uint8)
        grad = np.tile(np.linspace(0, 255, 512, dtype=np.uint8), (512, 1))
        a_noise = E.spectrum(save(noise, d / "noise.png"))["alpha"]
        a_grad = E.spectrum(save(grad, d / "grad.png"))["alpha"]
        check(a_noise < a_grad, f"噪声 α={a_noise:.2f} < 平滑渐变 α={a_grad:.2f}（高频决定斜率）")

    failed = [m for ok, m in results if not ok]
    print("\n" + "─" * 52)
    print(f"断言 {len(results) - len(failed)}/{len(results)} 通过")
    for m in failed:
        print(f"  未通过：{m}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())