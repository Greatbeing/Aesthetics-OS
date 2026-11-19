#!/usr/bin/env python3
"""aesthetics-OS 核心的回归测试：重点验证「该拒绝时真的拒绝」。

用法：python scripts/test_aos.py
退出码 0 表示全部断言通过。测试使用合成头部文件，不依赖任何真实素材；
真实成品走 demo 时用项目里的实际图片。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

AOS = Path(__file__).with_name("aos.py")
PASS, FAIL = "✅", "⛔"
results: list[tuple[bool, str]] = []


def run(project: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(AOS), "--root", str(project), *args],
        capture_output=True, text=True, encoding="utf-8",
    )
    return proc.returncode, proc.stdout + proc.stderr


def check(condition: bool, message: str) -> None:
    results.append((condition, message))
    print(f"{PASS if condition else FAIL} {message}")


def fake_png(path: Path, width: int, height: int) -> None:
    ihdr = (
        width.to_bytes(4, "big") + height.to_bytes(4, "big")
        + bytes([8, 2, 0, 0, 0])
    )
    chunk = b"IHDR" + ihdr
    body = b"\x89PNG\r\n\x1a\n" + len(ihdr).to_bytes(4, "big") + chunk + zlib.crc32(chunk).to_bytes(4, "big")
    path.write_bytes(body + b"\x00" * 32)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "demo"
        project.mkdir()
        ref = project / "参考.png"
        desk = project / "成品-desktop.png"
        phone = project / "成品-mobile.png"
        fake_png(ref, 1200, 800)
        fake_png(desk, 1440, 900)
        fake_png(phone, 375, 812)

        code, out = run(project, "init", "--project", "回归测试")
        check(code == 0 and "已初始化" in out, "init 建立状态")

        code, out = run(project, "verdict", "--tech", "pass", "--aesthetic", "pass",
                        "--reason", "看起来挺好的，整体舒服，没什么大问题，就这样交付吧")
        check(code == 1 and "拒绝签发" in out, "空状态直接被拒绝签发审美通过")

        code, out = run(project, "propose", "要很高级、很现代")
        check(code == 1 and "模板要素" in out, "缺模板要素的命题被拒绝")

        code, out = run(project, "propose", "面向财务负责人完成月度对账时呈现可托付的克制，通过精确数字的层级差表达，高级=对比度+密度+材料")
        check(code == 0, "合模板且宽泛词已映射的命题被接受")

        code, out = run(project, "propose", "面向财务负责人完成月度对账时呈现可托付的克制，通过精确数字的层级差表达，要高级")
        check(code == 1 and "宽泛词" in out, "未映射参数的「高级」被拒绝")

        for text in ("差异行进入视觉重力第一层", "强调色只用于待核实状态", "动效只表达状态迁移"):
            run(project, "decide", text)

        code, out = run(project, "brief", "--purpose", "让财务快速定位差异",
                        "--audience", "财务负责人", "--dislike", "渐变光带与装饰性插画",
                        "--signature", "唯一一处朱砂红标记待核实", "--nongoal", "不做科技感暗色",
                        "--nongoal", "不加网格与扫描线")
        check(code == 1 and "参考证据" in out, "没有参考证据的简报被拒绝")

        code, out = run(project, "brief", "--purpose", "让财务快速定位差异",
                        "--audience", "财务负责人", "--dislike", "渐变光带与装饰性插画",
                        "--signature", "唯一一处朱砂红标记待核实", "--nongoal", "不做科技感暗色",
                        "--nongoal", "不加网格与扫描线", "--evidence", str(ref))
        check(code == 0 and "简报完整" in out, "补齐证据与决策后简报完整")

        code, out = run(project, "evidence", str(project / "不存在.png"))
        check(code == 1 and "不存在" in out, "不存在的成品不能登记")

        code, out = run(project, "evidence", str(desk), "--surface", "desktop")
        check(code == 0 and "1440×900" in out, "真实成品登记并读出尺寸")

        code, out = run(project, "checkpoint")
        check(code == 1, "只有一份成品时检查点不通过（需 ≥2 且覆盖两种宽度）")

        code, out = run(project, "verdict", "--tech", "pass", "--aesthetic", "pass",
                        "--reason", "差异行提前后视线落点正确，但状态色与品牌色对比不足，需再检查移动端")
        check(code == 1, "证据不足时仍然拒绝签发")

        code, out = run(project, "evidence", str(phone), "--surface", "mobile")
        check(code == 0 and "375×812" in out, "第二份成品（移动端）登记成功")

        code, out = run(project, "checkpoint")
        check(code == 0 and "可以进入完整实现" in out, "两份断点证据齐备后检查点通过")

        code, out = run(project, "verdict", "--tech", "fail", "--aesthetic", "pass",
                        "--reason", "差异行提前后视线落点正确，但状态色与品牌色对比不足，需再检查移动端")
        check(code == 1 and "技术验收不是 pass" in out, "技术未通过时不得签审美通过")

        code, out = run(project, "verdict", "--tech", "pass", "--aesthetic", "pass",
                        "--reason", "差异行提前后视线落点正确，但状态色与品牌色对比不足，需再检查移动端")
        check(code == 0 and "审美状态：pass" in out, "条件齐备后签发出审美通过")

        run(project, "reject", "--direction", "方向A-深色玻璃卡", "--mechanism", "只换了材质，层级与重力没变")
        code, out = run(project, "reject", "--direction", "方向B-编辑极简", "--mechanism", "间距收紧但仍靠装饰建立焦点")
        check(code == 1 or "两个方向被拒" in out, "第二次被拒后提示必须换证据")

        code, out = run(project, "verdict", "--tech", "pass", "--aesthetic", "pass",
                        "--reason", "这次真的不一样了，因为我把差异行提到了第一层，删掉了渐变光带")
        check(code == 1 and "新证据" in out, "两次被拒后没有新证据，拒绝签发")

        code, out = run(project, "audit")
        check(code in (0, 1) and "审美审计" in out, "audit 可运行并给出报告")

        # 伪造一次「零证据通过」，验证审计能抓出来
        state_file = project / ".aos" / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["verdicts"].append({"tech": "pass", "aesthetic": "pass",
                                  "reason": "好", "evidence_n": 0, "at": "2026-01-01T00:00:00+08:00"})
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        code, out = run(project, "audit")
        check(code == 1 and "零份成品证据" in out, "审计抓出伪造的零证据通过")

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