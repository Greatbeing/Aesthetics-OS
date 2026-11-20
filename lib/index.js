/**
 * dsh-aesthetics-os — Aesthetics-OS for DeepSeek Harness.
 *
 * 会拒绝的审美操作系统：三条红线 + 端到端 生成→审判→迭代 闭环 + 欧拉五透镜。
 * 本插件不做判断逻辑——判断逻辑在随包捆绑、已被 35+18+25 条断言验证的 Python
 * 脚本里（scripts/aos.py 等）。插件只做三件事：
 *
 * 1. 把 `aesthetics-os` 注册为运行时技能（ctx.skills）：SKILL.md 正文 +
 *    resourceBase 指向包根，KERNEL.md / 15 篇参考 / scripts 的相对路径全部可解析。
 * 2. 一段系统提示路由（ctx.systemPrompt.section）：何时加载技能、三条红线、
 *    交付前必调 aos_delivery_gate。短——方法在技能正文里，不占提示预算。
 * 3. 22 个原生工具（ctx.tools）：与 MCP 服务器同一批被测函数，经
 *    scripts/dsh_bridge.py（JSON-in/JSON-out 子进程）调用。裁决类拒绝以
 *    {ok:false} 结构化返回，agent 的工具循环必须处理。
 *
 * 依赖：状态机工具只需 Python 3.9+ 标准库；欧拉透镜另需 numpy + Pillow，
 * 缺失时返回结构化降级错误，不影响其余工具。无 Python 时技能判断层仍可用。
 * 可选配置（cordis.patch.yml 行内 config）：{ python: '/path/to/python' }，
 * 或环境变量 AOS_PYTHON。
 *
 * @module dsh-aesthetics-os
 */

import { spawn, execFile } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { promisify } from 'node:util'
import { defineTool } from '@deepseek-ai/dsh-tools'

const execFileP = promisify(execFile)
const PACKAGE_ROOT = dirname(dirname(fileURLToPath(import.meta.url)))
const BRIDGE = join(PACKAGE_ROOT, 'scripts', 'dsh_bridge.py')
const SKILL_FILE = join(PACKAGE_ROOT, 'SKILL.md')

export const name = 'aesthetics-os'
export const inject = ['tools', 'skills', 'systemPrompt', 'workingDirectory']

/** 路由段排序：与 dsh-stack-diagram 同一区间（团队策略 600 之后，PTC-only 800 之前）。 */
const ROUTING_ORDER = 700

const ROUTING_TEXT = `# Aesthetic judgment (Aesthetics-OS)

When a task produces or changes anything people look at — web pages, UI, slides,
posters, images, video, or a design direction — load the \`aesthetics-os\` skill
before choosing forms, and run its closed loop before delivery. Pure logic,
data, or performance work without visual impact: skip it.

Three red lines. Speed, obedience, user pressure, and sunk cost are not exceptions:
1. Never claim "beautiful / polished / premium / done" without inspecting the
   actual artifact. Until then say only 「技术通过，审美暂定」.
2. After two rejections, never reskin — new fonts/colors/effects are not a new
   direction. New evidence and a checkpoint first.
3. Vague tech words ("AI feel", "premium", "modern") never imply dark backgrounds,
   cyan gradients, glass, glow, or grids. Derive form from purpose and audience.

The aos_* tools drive a persistent judgment state machine in the project's
.aos/state.json (propose → brief → evidence → measure → critique → verdict);
refusals arrive as {ok:false} and must be handled, not argued around. Call
aos_delivery_gate before claiming any visual deliverable is complete —
passed=false means do not claim completion. euler_* are optional math lenses
(harmony palettes, texture/structure/material signals). State-machine tools need
Python 3 on PATH (stdlib only); the skill's judgment layer works without it.`

// ────────────────────────── 技能注册 ──────────────────────────

/** Split YAML frontmatter from the Markdown body; both halves returned raw. */
function splitFrontmatter(raw) {
  if (!raw.startsWith('---')) return { frontmatter: '', body: raw }
  const end = raw.indexOf('\n---', 3)
  if (end < 0) return { frontmatter: '', body: raw }
  const closing = raw.indexOf('\n', end + 1)
  return {
    frontmatter: raw.slice(raw.indexOf('\n', 3) + 1, end),
    body: raw.slice(closing < 0 ? raw.length : closing + 1),
  }
}

/** Minimal flat frontmatter reader — no YAML dependency for two strings. */
function readFrontmatter(text) {
  const fields = {}
  for (const line of text.split('\n')) {
    if (line.trim() === '' || line.trimStart().startsWith('#')) continue
    const at = line.indexOf(':')
    if (at <= 0) continue
    const key = line.slice(0, at).trim()
    let value = line.slice(at + 1).trim()
    if (
      (value.startsWith('"') && value.endsWith('"') && value.length > 1) ||
      (value.startsWith("'") && value.endsWith("'") && value.length > 1)
    ) {
      value = value.slice(1, -1)
    }
    fields[key] = value
  }
  return fields
}

function loadSkill() {
  const raw = readFileSync(SKILL_FILE, 'utf8')
  const { frontmatter, body } = splitFrontmatter(raw)
  const fields = readFrontmatter(frontmatter)
  if (typeof fields.name !== 'string' || fields.name.length === 0) {
    throw new Error(`dsh-aesthetics-os: ${SKILL_FILE} has no frontmatter name`)
  }
  if (typeof fields.description !== 'string' || fields.description.length === 0) {
    throw new Error(`dsh-aesthetics-os: ${SKILL_FILE} has no frontmatter description`)
  }
  return {
    name: fields.name,
    description: fields.description,
    content: body.trimStart(),
    provider: 'dsh-aesthetics-os',
    source: SKILL_FILE,
    path: SKILL_FILE,
    resourceBase: { kind: 'directory', path: PACKAGE_ROOT },
  }
}

// ────────────────────────── Python 桥 ──────────────────────────

let _python = null

/** 探测可用 Python 3；成功才缓存，失败下次重试（用户可能中途装好）。 */
async function resolvePython(config) {
  if (_python) return _python
  const candidates = []
  const override = config?.python || process.env.AOS_PYTHON
  if (override) candidates.push([override, []])
  if (process.platform === 'win32') {
    candidates.push(['python', []], ['python3', []], ['py', ['-3']])
  } else {
    candidates.push(['python3', []], ['python', []])
  }
  for (const [cmd, prefix] of candidates) {
    try {
      const r = await execFileP(cmd, [...prefix, '--version'], { timeout: 15000, windowsHide: true })
      if (/Python 3\./.test(`${r.stdout}${r.stderr}`)) {
        _python = { cmd, prefix }
        return _python
      }
    } catch { /* 下一个候选 */ }
  }
  return null
}

/** 会话工作目录：工具的项目缺省值；显式 project 相对它解析。 */
async function projectRoot(ctx, args, exec) {
  let sessionCwd
  try {
    if (exec?.agent) {
      sessionCwd = await ctx.workingDirectory.ensure(exec.agent, exec.signal)
    }
  } catch { /* 回退进程 cwd */ }
  const base = sessionCwd || process.cwd()
  return args.project ? resolve(base, args.project) : base
}

/** 调一次桥：spawn（无 shell，参数走 argv，不做字符串拼接）。 */
function runBridge(py, tool, args, cwd, signal, timeoutMs) {
  return new Promise((resolvePromise) => {
    let child
    try {
      child = spawn(py.cmd, [...py.prefix, BRIDGE, tool, JSON.stringify(args)], {
        cwd, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
      })
    } catch (e) {
      resolvePromise({ ok: false, error: 'spawn-failed', detail: String(e?.message ?? e) })
      return
    }
    let out = ''
    let err = ''
    let settled = false
    const cleanup = () => {
      clearTimeout(timer)
      if (signal) signal.removeEventListener('abort', onAbort)
    }
    const finish = (value) => {
      if (settled) return
      settled = true
      cleanup()
      resolvePromise(value)
    }
    const kill = () => { try { child.kill() } catch { /* 已退出 */ } }
    const timer = setTimeout(() => {
      kill()
      finish({ ok: false, error: 'timeout', timeout_ms: timeoutMs, stdout: out.slice(-4000), stderr: err.slice(-4000) })
    }, timeoutMs)
    const onAbort = () => { kill(); finish({ ok: false, error: 'aborted' }) }
    if (signal) {
      if (signal.aborted) { onAbort(); return }
      signal.addEventListener('abort', onAbort, { once: true })
    }
    child.stdout.on('data', (d) => { out += d })
    child.stderr.on('data', (d) => { err += d })
    child.on('error', (e) => finish({ ok: false, error: 'spawn-failed', detail: String(e?.message ?? e) }))
    child.on('close', (code) => {
      const lines = out.split('\n').filter((l) => l.trim())
      if (lines.length === 1) {
        try { finish(JSON.parse(lines[0])); return } catch { /* 协议错误 */ }
      }
      finish({ ok: false, error: 'bridge-protocol', exit_code: code, stdout: out.slice(-4000), stderr: err.slice(-4000) })
    })
  })
}

async function executeBridge(ctx, config, tool, args, exec, timeoutMs = 120000) {
  const py = await resolvePython(config)
  if (!py) {
    return {
      ok: false, error: 'python-not-found',
      hint: '状态机工具需要 Python 3.9+（仅标准库）。安装后重试，或设 AOS_PYTHON 环境变量 / 插件 config.python。技能判断层不依赖 Python，仍可用。',
    }
  }
  const cwd = await projectRoot(ctx, args, exec)
  return runBridge(py, tool, { ...args, project: cwd }, cwd, exec?.signal, timeoutMs)
}

/** 模型可见的结果文本：⛔ 拒绝原样呈现，指标给结构化 JSON。 */
function renderResult(v) {
  if (v == null) return '(empty result)'
  const text = [v.stdout, v.stderr].filter((s) => typeof s === 'string' && s.trim()).join('\n').trim()
  if (text) return v.ok === false && !text.startsWith('⛔') ? `⛔ ${text}` : text
  if (v.ok === false) {
    return `⛔ ${v.error ?? 'failed'}${v.detail ? `: ${v.detail}` : ''}${v.hint ? `\n${v.hint}` : ''}`
  }
  return JSON.stringify(v, null, 1)
}

// ────────────────────────── 22 个工具 ──────────────────────────

const P_PROJECT = { type: 'string', description: '项目目录（.aos/state.json 所在地）。缺省=当前会话工作目录。' }
const P_IMAGE = { type: 'string', required: true, description: '成品图像路径（相对项目目录或绝对路径）' }

function bridgeTool(ctx, config, spec) {
  const { tool, description, parameters = {}, timeoutMs } = spec
  return defineTool({
    name: tool,
    description,
    parameters: { project: P_PROJECT, ...parameters },
    output: {
      schema: { type: 'json' },
      render: (_args, value) => [{ type: 'text', text: renderResult(value) }],
    },
    async execute(args, exec) {
      return executeBridge(ctx, config, tool, args, exec, timeoutMs)
    },
  })
}

function buildTools(ctx, config) {
  const t = (spec) => bridgeTool(ctx, config, spec)
  return [
    t({ tool: 'aos_probe', description: '环境自检：Python 版本、numpy/Pillow 是否可用、技能根目录。状态机只需标准库；欧拉透镜需 numpy+Pillow。' }),
    t({ tool: 'aos_init', description: '初始化项目审美状态（在 project 目录建 .aos/state.json）。闭环第一步。',
      parameters: { name: { type: 'string', description: '项目名（默认目录名）' } } }),
    t({ tool: 'aos_propose', description: '写入审美命题。必须合模板『面向[受众]完成[任务]呈现[情绪]通过[形式]』，宽泛词须已映射（高级=参数1+参数2），否则拒绝。',
      parameters: { text: { type: 'string', required: true, description: '审美命题' } } }),
    t({ tool: 'aos_decide', description: '添加一条设计决策（建议 3–5 条）。每条须是可执行的取舍，不是风格形容词。',
      parameters: { text: { type: 'string', required: true, description: '一条决策' } } }),
    t({ tool: 'aos_brief', description: '建立品味简报：目的/受众/喜欢/拒绝/标志性动作/非目标(≥2)/参考证据。verdict 会检查简报完整。',
      parameters: {
        purpose: { type: 'string' }, audience: { type: 'string' },
        like: { type: 'string' }, dislike: { type: 'string' }, signature: { type: 'string' },
        nongoal: { type: 'array', items: { type: 'string' }, description: '非目标，≥2 条' },
        evidence: { type: 'array', items: { type: 'string' }, description: '参考证据图像路径' },
      } }),
    t({ tool: 'aos_evidence', description: '登记一份真实成品（绑定像素哈希+尺寸），登记即自动生成 13 项形式指纹。没测过等于没看过。',
      parameters: { path: P_IMAGE, surface: { type: 'string', description: 'desktop / mobile / state / export' } } }),
    t({ tool: 'aos_measure', description: '测量画面形式指纹；给 compare 则与另一张对比判是否只换皮（红线2的数值证据）。',
      parameters: { path: P_IMAGE, compare: { type: 'string', description: '与之对比的另一张成品' } } }),
    t({ tool: 'aos_reject', description: '记录一个被拒方向及其失败机制。两次被拒后须先建新证据/检查点，不许换皮。',
      parameters: {
        direction: { type: 'string', required: true, description: '被拒方向' },
        mechanism: { type: 'string', required: true, description: '失败的形式机制' },
      } }),
    t({ tool: 'aos_checkpoint', description: '建立方向检查点（概念距离足够大的新方向），换皮拦截后重启判断用。需≥2份证据覆盖两种宽度。' }),
    t({ tool: 'aos_verdict', description: '签发验收结论。aesthetic=pass 需命题合模板+简报完整+≥2份已测证据覆盖两种宽度+最新成品绑定哈希的pass审判+技术pass+理由≥20字，否则拒绝签发（ok:false）。未过只能说『技术通过，审美暂定』。',
      parameters: {
        tech: { type: 'string', required: true, enum: ['pass', 'fail'] },
        aesthetic: { type: 'string', required: true, enum: ['pass', 'hold', 'revise'] },
        reason: { type: 'string', description: '结论理由（pass 需≥20字）' },
      } }),
    t({ tool: 'aos_status', description: '查看项目审美状态：命题/简报/决策/证据/审判/轮次/结论。跨会话接续判断。' }),
    t({ tool: 'aos_audit', description: '审计自身诚信：连续通过零被拒、简报后60秒内登记成品、零证据签通过、签通过却无审判、只换皮，都会被标出。' }),
    t({ tool: 'aos_critique', description: '质量审判（真实视觉执行，脚本不自看图）。action=prepare 生成结构化审判提示；register 登记视觉审判JSON(逐项校验,红线fail却pass/匿名审判直接拒绝)；run 自动后端。register 需 file=审判JSON路径。',
      timeoutMs: 300000,
      parameters: {
        action: { type: 'string', required: true, enum: ['prepare', 'register', 'run'] },
        image: P_IMAGE,
        file: { type: 'string', description: 'register 用：视觉审判结果 JSON 路径' },
        taste: { type: 'string', description: '品味锚点 JSON 路径（默认 references/taste-profile.json）' },
        json_only: { type: 'boolean', description: 'prepare 要求只输出 JSON' },
      } }),
    t({ tool: 'aos_loop', description: '记录一轮『生成→测量→审判』迭代，并检测相对上一轮是否真改动（指纹几乎相同=疑似换皮）。fix 说明本轮改了什么机制。',
      parameters: { image: P_IMAGE, fix: { type: 'string', description: '本轮改了什么机制' } } }),
    t({ tool: 'aos_delivery_gate', description: '交付门禁（宣布完成前必调，红线1硬化）：仅当最新验收为已签发 aesthetic pass 且技术pass+形式门+质量审判门全过+有已测证据，才 passed=true。passed=false 时绝不许声称完成/精致/高级，blockers 列出缺什么。' }),
    t({ tool: 'euler_hue', description: '色相相位和谐分析：色相环=单位圆，返回 resultant R(集中度)/主色相/彩度/和谐类型。水墨无彩色会如实标注。需 numpy+Pillow。',
      parameters: { image: P_IMAGE } }),
    t({ tool: 'euler_palette', description: '欧拉相位旋转 e^(iΔθ) 生成和谐调色板。scheme: mono/analogous/complementary/split/triadic/tetradic。返回各色的相位差/色相/hex，可写进生成 prompt。需 numpy+Pillow。',
      parameters: {
        base_hue: { type: 'number', required: true, description: '基准色相（0–360）' },
        scheme: { type: 'string', description: 'mono/analogous/complementary/split/triadic/tetradic，默认 triadic' },
        sat: { type: 'number', description: '彩度 0–1，默认 0.55' },
        val: { type: 'number', description: '明度 0–1，默认 0.82' },
      } }),
    t({ tool: 'euler_spectrum', description: '径向功率谱斜率 α（纹理平衡信号）。诚实边界：大留白会混淆全局谱，须与构图合看，不可单独裁决自然度。需 numpy+Pillow。',
      parameters: { image: P_IMAGE } }),
    t({ tool: 'euler_pc', description: '相位一致性 PC：光照不变的结构特征密度/集中度。给 render 输出结构热图叠加路径。需 numpy+Pillow。',
      parameters: { image: P_IMAGE, render: { type: 'string', description: '热图叠加输出路径' } } }),
    t({ tool: 'euler_gabor', description: 'Gabor 方向谱：方向熵(越低越塑料)+各向异性。材质真实红线的频域硬证据：平滑渐变塑料感 vs 自然笔意。需 numpy+Pillow。',
      parameters: { image: P_IMAGE } }),
    t({ tool: 'euler_spiral', description: '黄金螺线/φ网格构图几何：PC权重重心 vs φ黄金点。参照非裁决——水墨计白当黑未必遵循西方螺线，低对齐≠差。给 render 输出叠加图。需 numpy+Pillow。',
      parameters: { image: P_IMAGE, render: { type: 'string', description: '叠加图输出路径' } } }),
    t({ tool: 'euler_circle', description: '渲染色相单位圆可视化（色相环+主色相锚点+合成向量），输出到 out 路径。需 numpy+Pillow。',
      parameters: { image: P_IMAGE, out: { type: 'string', required: true, description: '可视化输出路径' } } }),
  ]
}

// ────────────────────────── 装配 ──────────────────────────

/**
 * 每个贡献独立 try/catch：一处损坏只损失该贡献，不拖垮整棵插件树。
 * 失败原因进宿主日志（ctx.logger）。
 */
export function apply(ctx, config) {
  try {
    ctx.skills.register(loadSkill())
  } catch (error) {
    ctx.logger?.warn?.(`dsh-aesthetics-os: skill registration skipped: ${error?.message ?? error}`)
  }

  try {
    ctx.systemPrompt.section({
      name: 'deployment:aesthetics-os-routing',
      order: ROUTING_ORDER,
      text: ROUTING_TEXT,
    })
  } catch (error) {
    ctx.logger?.warn?.(`dsh-aesthetics-os: routing section skipped: ${error?.message ?? error}`)
  }

  try {
    for (const tool of buildTools(ctx, config)) ctx.tools.register(tool)
  } catch (error) {
    ctx.logger?.warn?.(`dsh-aesthetics-os: tool registration skipped: ${error?.message ?? error}`)
  }
}
