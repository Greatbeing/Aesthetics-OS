#!/usr/bin/env python3
"""Aesthetics-OS DSH bridge — JSON-in / JSON-out subprocess interface.

DeepSeek Harness 插件（lib/index.js）通过本桥调用已验证的审美状态机与欧拉透镜，
与 MCP 服务器（mcp_server.py）复用同一批被测函数，不重写任何判断逻辑。

用法：python dsh_bridge.py <tool> '<json-args>'
输出：stdout 恰好一个 JSON 对象。领域内的「拒绝」是 {ok:false, ...} 且退出码 0；
只有协议/用法错误才以非零码退出。agent 的工具循环必须处理 ok:false。

依赖：全部 aos_* 工具与 aos_probe 仅需 Python 3.9+ 标准库；
euler_* 工具惰性导入 euler_lens（numpy + Pillow），缺失时返回结构化错误，
不影响状态机工具。

工具目录（22）：与 MCP 的 21 工具一一对应，另加 aos_probe 环境自检。
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import traceback
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import aos  # noqa: E402
import delivery_gate  # noqa: E402


# ────────────────────────── 基础设施 ──────────────────────────
def _root(args: dict) -> Path:
    root = Path(args.get("project") or os.getcwd()).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _path(root: Path, value: str) -> str:
    """相对路径一律相对项目目录解析，避免依赖进程 cwd。"""
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = root / p
    return str(p)


def _run_aos(root: Path, argv: list[str]) -> dict:
    """用 aos 自己的 argparse 构造参数并调用对应 cmd_*，捕获 stdout/stderr/退出码。

    与 mcp_server._run_aos 同一实现：裁决类拒绝以 {ok:false, stdout:"⛔…"} 返回。
    """
    full = ["--root", str(root)] + argv
    args = aos.build_parser().parse_args(full)
    out, err = io.StringIO(), io.StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = args.func(args, root)
    except SystemExit as e:  # 防御：cmd_* 实际均 return int
        code = int(e.code or 0)
    return {"ok": code == 0, "exit_code": code,
            "stdout": out.getvalue(), "stderr": err.getvalue()}


def _euler():
    """惰性导入欧拉透镜；缺 numpy/Pillow 时返回结构化错误而不是崩溃。"""
    try:
        import euler_lens as el
        return el, None
    except ImportError as e:
        return None, {"ok": False, "error": "euler-deps-missing",
                      "detail": str(e),
                      "hint": "欧拉透镜需要 numpy 与 Pillow：pip install numpy pillow"}


# ────────────────────────── AOS 状态机（15） ──────────────────────────
def aos_init(args: dict) -> dict:
    root = _root(args)
    argv = ["init"]
    if args.get("name"):
        argv += ["--project", args["name"]]
    return _run_aos(root, argv)


def aos_propose(args: dict) -> dict:
    return _run_aos(_root(args), ["propose", args["text"]])


def aos_decide(args: dict) -> dict:
    return _run_aos(_root(args), ["decide", args["text"]])


def aos_brief(args: dict) -> dict:
    root = _root(args)
    argv = ["brief"]
    for key, flag in (("purpose", "--purpose"), ("audience", "--audience"),
                      ("like", "--like"), ("dislike", "--dislike"),
                      ("signature", "--signature")):
        if args.get(key):
            argv += [flag, args[key]]
    for ng in args.get("nongoal") or []:
        argv += ["--nongoal", ng]
    for ev in args.get("evidence") or []:
        argv += ["--evidence", _path(root, ev)]
    return _run_aos(root, argv)


def aos_evidence(args: dict) -> dict:
    root = _root(args)
    argv = ["evidence", _path(root, args["path"])]
    if args.get("surface"):
        argv += ["--surface", args["surface"]]
    return _run_aos(root, argv)


def aos_measure(args: dict) -> dict:
    root = _root(args)
    argv = ["measure", _path(root, args["path"])]
    if args.get("compare"):
        argv += ["--compare", _path(root, args["compare"])]
    return _run_aos(root, argv)


def aos_reject(args: dict) -> dict:
    return _run_aos(_root(args), ["reject", "--direction", args["direction"],
                                  "--mechanism", args["mechanism"]])


def aos_checkpoint(args: dict) -> dict:
    return _run_aos(_root(args), ["checkpoint"])


def aos_verdict(args: dict) -> dict:
    return _run_aos(_root(args), ["verdict", "--tech", args["tech"],
                                  "--aesthetic", args["aesthetic"],
                                  "--reason", args.get("reason", "")])


def aos_status(args: dict) -> dict:
    return _run_aos(_root(args), ["status"])


def aos_audit(args: dict) -> dict:
    return _run_aos(_root(args), ["audit"])


def aos_critique(args: dict) -> dict:
    root = _root(args)
    argv = ["critique", args["action"], _path(root, args["image"])]
    if args.get("file"):
        argv += ["--file", _path(root, args["file"])]
    if args.get("taste"):
        argv += ["--taste", _path(root, args["taste"])]
    if args.get("json_only"):
        argv += ["--json-only"]
    return _run_aos(root, argv)


def aos_loop(args: dict) -> dict:
    root = _root(args)
    argv = ["loop", _path(root, args["image"])]
    if args.get("fix"):
        argv += ["--fix", args["fix"]]
    return _run_aos(root, argv)


def aos_delivery_gate(args: dict) -> dict:
    return delivery_gate.gate(str(_root(args)))


def aos_probe(args: dict) -> dict:
    """环境自检：Python 版本 / 欧拉透镜依赖 / 技能根目录。状态机不需要 numpy。"""
    def _has(mod: str) -> bool:
        try:
            __import__(mod)
            return True
        except ImportError:
            return False
    return {"ok": True, "python": sys.version.split()[0],
            "executable": sys.executable,
            "numpy": _has("numpy"), "pillow": _has("PIL"),
            "skill_root": str(SKILL), "bridge": 1,
            "state_machine_requires": "Python 3.9+ stdlib only",
            "euler_requires": "numpy + pillow"}


# ────────────────────────── 欧拉五透镜（7） ──────────────────────────
def euler_hue(args: dict) -> dict:
    el, err = _euler()
    if err:
        return err
    return el.hue_phases(Path(_path(_root(args), args["image"])))


def euler_palette(args: dict) -> dict:
    el, err = _euler()
    if err:
        return err
    base = float(args["base_hue"])
    scheme = args.get("scheme", "triadic")
    sat = float(args.get("sat", 0.55))
    val = float(args.get("val", 0.82))
    return {"ok": True, "base_hue": base, "scheme": scheme, "sat": sat, "val": val,
            "colors": el.harmony_palette(base, scheme, sat, val)}


def euler_spectrum(args: dict) -> dict:
    el, err = _euler()
    if err:
        return err
    info = el.spectrum(Path(_path(_root(args), args["image"])))
    curve = info.pop("curve", [])
    info["curve_points"] = len(curve)
    return info


def euler_pc(args: dict) -> dict:
    el, err = _euler()
    if err:
        return err
    root = _root(args)
    p = Path(_path(root, args["image"]))
    info = el.phase_congruency(p)
    if args.get("render"):
        info["rendered"] = str(el.render_pc(p, Path(_path(root, args["render"]))))
    return info


def euler_gabor(args: dict) -> dict:
    el, err = _euler()
    if err:
        return err
    return el.gabor_orientation(Path(_path(_root(args), args["image"])))


def euler_spiral(args: dict) -> dict:
    el, err = _euler()
    if err:
        return err
    root = _root(args)
    p = Path(_path(root, args["image"]))
    info = el.spiral_analysis(p)
    if args.get("render"):
        info["rendered"] = str(el.render_spiral(p, Path(_path(root, args["render"]))))
    return info


def euler_circle(args: dict) -> dict:
    el, err = _euler()
    if err:
        return err
    root = _root(args)
    return {"ok": True, "rendered": str(el.render_hue_circle(
        Path(_path(root, args["image"])), Path(_path(root, args["out"]))))}


TOOLS = {
    "aos_init": aos_init, "aos_propose": aos_propose, "aos_decide": aos_decide,
    "aos_brief": aos_brief, "aos_evidence": aos_evidence, "aos_measure": aos_measure,
    "aos_reject": aos_reject, "aos_checkpoint": aos_checkpoint, "aos_verdict": aos_verdict,
    "aos_status": aos_status, "aos_audit": aos_audit, "aos_critique": aos_critique,
    "aos_loop": aos_loop, "aos_delivery_gate": aos_delivery_gate, "aos_probe": aos_probe,
    "euler_hue": euler_hue, "euler_palette": euler_palette, "euler_spectrum": euler_spectrum,
    "euler_pc": euler_pc, "euler_gabor": euler_gabor, "euler_spiral": euler_spiral,
    "euler_circle": euler_circle,
}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(json.dumps({"ok": False, "error": "usage",
                          "hint": "dsh_bridge.py <tool> '<json-args>'"}, ensure_ascii=False))
        return 2
    tool, payload = argv
    if tool not in TOOLS:
        print(json.dumps({"ok": False, "error": "unknown-tool", "tool": tool,
                          "available": sorted(TOOLS)}, ensure_ascii=False))
        return 2
    try:
        args = json.loads(payload) if payload.strip() else {}
        if not isinstance(args, dict):
            raise ValueError("args must be a JSON object")
    except (ValueError, TypeError) as e:
        print(json.dumps({"ok": False, "error": "bad-json", "detail": str(e)},
                         ensure_ascii=False))
        return 2
    try:
        result = TOOLS[tool](args)
    except KeyError as e:
        result = {"ok": False, "error": "missing-arg", "detail": str(e)}
    except Exception:
        result = {"ok": False, "error": "bridge-exception",
                  "detail": traceback.format_exc(limit=6)}
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
