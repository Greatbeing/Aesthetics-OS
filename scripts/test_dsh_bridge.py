#!/usr/bin/env python3
"""dsh_bridge.py 回归测试：仅标准库（自带 PNG 编码器），重点测拒绝路径与协议。

与 test_aos.py 同一套门（证据≥2、两种宽度、测过≠评过、理由≥20字、换皮拦截），
但走 DSH 插件真实使用的 JSON 桥协议：subprocess → 单 JSON 输出。
欧拉透镜相关断言在缺 numpy/Pillow 时改为验证「结构化降级错误」。

用法：python scripts/test_dsh_bridge.py
退出码 0 表示全部断言通过。
"""
from __future__ import annotations

import json
import random
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

BRIDGE = Path(__file__).with_name("dsh_bridge.py")
PASS, FAIL = "✅", "⛔"
results: list[tuple[bool, str]] = []

try:
    import numpy  # noqa: F401
    from PIL import Image  # noqa: F401
    EULER_DEPS = True
except ImportError:
    EULER_DEPS = False


def check(condition: bool, message: str) -> None:
    results.append((condition, message))
    print(f"{PASS if condition else FAIL} {message}")


def call(tool: str, args: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, str(BRIDGE), tool, json.dumps(args, ensure_ascii=False)],
        capture_output=True, text=True, encoding="utf-8",
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if len(lines) == 1:
        try:
            r = json.loads(lines[0])
            r["_exit"] = proc.returncode
            return r
        except ValueError:
            pass
    return {"ok": False, "error": "protocol", "code": proc.returncode,
            "stdout": proc.stdout, "stderr": proc.stderr}


def said(r: dict) -> str:
    """aos 的 ⛔ 拒绝走 stderr，✅ 正常输出走 stdout——两者都算「说过」。"""
    return r.get("stdout", "") + r.get("stderr", "")


# ── 标准库 PNG 编码（measure.py 自己解码，不需要 Pillow） ──
def write_png(path: Path, w: int, h: int, pixel) -> None:
    rows = []
    for y in range(h):
        row = bytearray(b"\x00")
        for x in range(w):
            row.extend(bytes(pixel(x, y)))
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def calm_png(path: Path, w: int = 1200, h: int = 800, shift: float = 0.0) -> None:
    x0 = int(w * (0.62 + shift))
    y0 = int(h * 0.55)

    def pixel(x: int, y: int):
        if x0 <= x < x0 + 90 and y0 <= y < y0 + 130:
            return (28, 26, 24)
        return (242, 236, 224)
    write_png(path, w, h, pixel)


def busy_png(path: Path, w: int = 480, h: int = 1024, seed: int = 7) -> None:
    rng = random.Random(seed)
    cache = [[(rng.randrange(256), rng.randrange(256), rng.randrange(256))
              for _ in range(w)] for _ in range(h)]

    def pixel(x: int, y: int):
        return cache[y][x]
    write_png(path, w, h, pixel)


def make_critique(conclusion: str = "pass", fail_line: str | None = None,
                  anonymous: bool = False) -> dict:
    rl = {k: {"status": "pass", "evidence": "看见的具体证据说明"}
          for k in ("CS", "FP", "TX", "AI", "CU", "CM")}
    if fail_line:
        rl[fail_line]["status"] = "fail"
    result = {
        "red_lines": rl,
        "three_axis": {"x": 2, "y": 3, "z": 1, "note": "对照锚点"},
        "reflexes": {k: {"observed": "看见的事实", "mechanism": "机制", "effect": "效果"}
                     for k in ("purpose", "system", "material", "specificity", "restraint")},
        "conclusion": conclusion,
        "priority_fix": "把主体提到左侧三分位" if conclusion != "pass" else "",
        "judge": "test-fixture",
    }
    if anonymous:
        del result["judge"]
    return result


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "demo"
        project.mkdir()
        ref = project / "ref.png"
        calm = project / "calm.png"
        busy = project / "busy.png"
        calm2 = project / "calm-v2.png"
        calm_png(ref, shift=-0.02)
        calm_png(calm)
        busy_png(busy)
        calm_png(calm2, shift=-0.22)
        P = str(project)

        # ── 协议与环境 ──
        r = call("aos_probe", {})
        check(r.get("ok") is True and r.get("python", "").startswith("3."),
              "probe 报告 Python 版本与技能根")
        r = call("no_such_tool", {})
        check(r.get("error") == "unknown-tool", "未知工具返回结构化错误")
        proc = subprocess.run([sys.executable, str(BRIDGE), "aos_probe", "{bad"],
                              capture_output=True, text=True, encoding="utf-8")
        check(proc.returncode == 2 and "bad-json" in proc.stdout, "坏 JSON 以退出码 2 拒绝")

        # ── 状态机：拒绝路径 ──
        r = call("aos_init", {"project": P, "name": "桥回归"})
        check(r.get("ok") is True and (project / ".aos" / "state.json").exists(),
              "init 建立 .aos/state.json")
        r = call("aos_verdict", {"project": P, "tech": "pass", "aesthetic": "pass",
                                 "reason": "看起来挺好的，整体舒服，没什么大问题，就这样交付吧"})
        check(r.get("ok") is False and "拒绝签发" in said(r),
              "空状态签审美通过被拒绝（红线1）")
        r = call("aos_propose", {"project": P, "text": "要很高级、很现代"})
        check(r.get("ok") is False and "模板要素" in said(r),
              "缺模板要素的命题被拒绝")
        r = call("aos_propose", {"project": P, "text":
                                 "面向财务负责人完成月度对账时呈现可托付的克制，通过精确数字的层级差表达，高级=对比度+密度+材料"})
        check(r.get("ok") is True, "合模板且宽泛词已映射的命题被接受")

        for text in ("留白占比不低于 45%，作为观看呼吸", "强调色只用于待核实状态", "动效只表达状态迁移"):
            call("aos_decide", {"project": P, "text": text})
        r = call("aos_brief", {"project": P, "purpose": "让财务快速定位差异",
                               "audience": "财务负责人", "dislike": "渐变光带与装饰性插画",
                               "signature": "唯一一处朱砂红标记待核实",
                               "nongoal": ["不做科技感暗色", "不加网格与扫描线"],
                               "evidence": ["ref.png"]})  # 相对路径 → 相对项目解析
        check(r.get("ok") is True and "简报完整" in said(r),
              "brief 数组参数与相对路径证据可用")

        r = call("aos_evidence", {"project": P, "path": "calm.png", "surface": "desktop"})
        check(r.get("ok") is True and "形式指纹" in said(r),
              "evidence 登记即自动测量（相对路径）")
        r = call("aos_evidence", {"project": P, "path": "busy.png", "surface": "mobile"})
        check(r.get("ok") is True, "第二份成品（另一宽度）登记成功")

        r = call("aos_measure", {"project": P, "path": "busy.png", "compare": "busy.png"})
        check("疑似只换皮" in said(r), "同图自比判为只换皮（红线2数值证据）")
        r = call("aos_measure", {"project": P, "path": "busy.png", "compare": "calm.png"})
        check("画面确有变化" in said(r), "不同图判为确有变化")

        # ── 质量审判：测过≠评过 ──
        r = call("aos_verdict", {"project": P, "tech": "pass", "aesthetic": "pass",
                                 "reason": "差异行提前后视线落点正确，但状态色与品牌色对比不足，需再检查移动端"})
        check(r.get("ok") is False and "没有质量审判" in said(r),
              "测过结构但未评质量，拒绝签发")
        r = call("aos_critique", {"project": P, "action": "prepare", "image": "busy.png",
                                  "json_only": True})
        check(r.get("ok") is True and len(r.get("stdout", "")) > 200,
              "critique prepare 生成审判提示")
        bad = project / "bad.json"
        bad.write_text(json.dumps(make_critique(anonymous=True), ensure_ascii=False),
                       encoding="utf-8")
        r = call("aos_critique", {"project": P, "action": "register", "image": "busy.png",
                                  "file": "bad.json"})
        check(r.get("ok") is False and "匿名" in said(r), "匿名审判被拒绝登记")
        good = project / "good.json"
        good.write_text(json.dumps(make_critique("pass"), ensure_ascii=False), encoding="utf-8")
        r = call("aos_critique", {"project": P, "action": "register", "image": "busy.png",
                                  "file": "good.json"})
        check(r.get("ok") is True, "pass 审判登记成功")

        r = call("aos_delivery_gate", {"project": P})
        check(r.get("passed") is False, "证据不足时交付门禁 passed=false")

        r = call("aos_verdict", {"project": P, "tech": "pass", "aesthetic": "pass",
                                 "reason": "差异行提前后视线落点正确，但状态色与品牌色对比不足，需再检查移动端"})
        check(r.get("ok") is True and "审美状态：pass" in said(r),
              "条件齐备后签发出审美通过")
        r = call("aos_delivery_gate", {"project": P})
        check(r.get("passed") is True, "签发通过后交付门禁 passed=true")

        r = call("aos_loop", {"project": P, "image": "calm-v2.png", "fix": "主体左移，留白结构改变"})
        check(r.get("ok") is True and "迭代轮次" in said(r), "loop 记录迭代轮次")
        r = call("aos_status", {"project": P})
        check(r.get("ok") is True, "status 可跨调用接续")
        r = call("aos_audit", {"project": P})
        check("审美审计" in said(r), "audit 可运行")

        # ── 欧拉透镜：有依赖测真值，无依赖测诚实降级 ──
        r = call("euler_palette", {"base_hue": 210, "scheme": "triadic"})
        if EULER_DEPS:
            colors = r.get("colors") or []
            check(r.get("ok") is not False and len(colors) == 3,
                  "euler_palette 三角色组返回 3 色")
            r = call("euler_hue", {"project": P, "image": "calm.png"})
            check("resultant" in json.dumps(r) or "R" in json.dumps(r),
                  "euler_hue 返回相位统计")
            r = call("euler_gabor", {"project": P, "image": "busy.png"})
            check(r.get("ok") is not False and "entropy" in json.dumps(r).lower(),
                  "euler_gabor 返回方向熵")
        else:
            check(r.get("error") == "euler-deps-missing" and "pip install" in r.get("hint", ""),
                  "缺 numpy/Pillow 时欧拉工具返回结构化降级错误")

    failed = [m for ok, m in results if not ok]
    print("\n" + "─" * 52)
    print(f"断言 {len(results) - len(failed)}/{len(results)} 通过")
    if failed:
        for item in failed:
            print(f"  未通过：{item}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
