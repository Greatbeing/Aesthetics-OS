# aesthetics-OS

> 让审美成为视觉选择**之前**的判断，而不是完成**之后**的装饰。

一个 Agent Skill。它不出图、不写页面、不跑构建——它做两件执行 Skill 做不了的事：

1. 在动手**之前**决定方向（受众会先看见什么、感到什么、理解什么）。
2. 在交付**之前**独立验收（不看实际成品，就不许说“好看”）。

适用：视觉选择、风格方向、重设计、视觉批评、最终审美验收。
触发词：`视觉审计` `审美验收` `重设计` `视觉批评` `模板化` `方向被否定` `技术正确但不好看` `无证据宣布通过`。

---

## 它不是顾问，是操作系统

散文可以被忽略，状态机不能。所以本技能分三层：

| 层 | 位置 | 作用 |
|---|---|---|
| 内核 | `KERNEL.md` | 约 1100 字，放进任何 agent 的常驻上下文 |
| 系统调用 | `scripts/aos.py` | 带持久状态，会拒绝签发结论 |
| 模块 | 15 篇参考 | 按需读一篇，不预加载 |

品味存在**项目**里，不是存在模型里。换会话、换模型、隔一周回来，判断接着上次走：

```bash
A=scripts/aos.py
python $A init
python $A propose "面向收藏者完成对一幅长卷的观看时呈现被山水推远的静气，通过大面积留白与青绿设色的一处重音表达，高级=色彩饱和度+留白比例+材质颗粒"
python $A decide "留白占比不低于 45%，作为观看呼吸"
python $A brief --purpose … --audience … --signature … --nongoal … --nongoal … --evidence 参考.png
python $A evidence 成品.png --surface desktop
python $A evidence 成品-mobile.png --surface mobile
python $A checkpoint
python $A verdict --tech pass --aesthetic pass --reason …
python $A audit
```

它会拒绝。下面是真实输出，不是示意：

```
⛔ 拒绝签发「审美通过」：
   - 审美命题（用 propose 写一句）
   - 品味简报缺 目的、受众、拒绝的机制、标志性动作、决策 0/3、非目标 <2、参考证据
   - 成品证据 0 份（需 ≥2，覆盖不同断点或状态）
   - 审美结论理由不足 20 字（现在 19 字）
未签发任何结论。只能说「技术通过，审美暂定」。
```

这条拒绝把红线 1 变成了不变量：**没有成品证据，接口不产出「通过」这个词**。同理，两次方向被拒后不补充新证据，签发同样失败——红线 2 也钉死在状态里。

`aos.py audit` 还会反过来查自己：连续通过零被拒、成品在简报后 60 秒内登记、零证据却签了通过，都会被标出来。

---

## 三条红线

这三条不是建议，是硬门。速度、服从、用户催促、已有投入，都不是例外。

| 红线 | 它实际会说的话 |
|---|---|
| **未检查，绝不通过** | “技术通过，审美暂定。” ——没看实际成品，不得声称精致、高级、最终完成。技术验收不能代替审美验收。 |
| **两次被拒，绝不换皮** | “停。换字体、颜色、特效不算新方向。” ——先建立新证据和概念距离足够大的检查点，再谈改法。 |
| **宽泛科技词，绝不套模板** | “'人工智能感'推不出深色背景 + 青蓝渐变 + 发光网格。” ——从任务、信任、信息密度和真实内容反推形式。 |

说出来“使用 aesthetics-os”却违反任一红线，仍判定失败。

## 反默认检测

技能内置了对三种典型请求的对抗反射：

- “测试都通过了，直接宣布精致高级” → 只确认技术状态，审美保持暂定。
- “不要分析，布局不变，只换字体颜色特效” → 两次被拒后停止换皮，重建证据与方向。
- “要很有人工智能感” → 从用途推导，不采用科技模板默认值。

校准示例：AI 财务产品的错误反应是深色背景、蓝紫渐变、发光网格、玻璃卡片；正确反应是从财务核对所需的**信任、密度、可追溯证据**出发，用稳定层级和精确数据表达高级感。

## 判断方式

轻量链条：`可见事实 → 形式机制 → 感知效果 → 实际决策`

选择顺序：先目的后风格；先层级后装饰；先构图后效果；先字体与间距后色彩；先真实内容后抽象氛围。

验收输出只有六项：命题、证据、优先修改、记忆点、非目标、验收结论。

---

## 结构

```
aesthetics-os/
├── KERNEL.md                             # 常驻内核：反射 / 红线 / 接口 / 模块路由（约 1100 字）
├── SKILL.md                              # 主入口：操作系统分层 / 审美反射 / 三条红线 / 短循环 / 路由
├── web-aesthetic-protocol.md             # 网页与界面：不可跳过的顺序 + 三道门槛 + 常见借口与纠正
├── product-aesthetic-os.md               # 产品与多格式系统：审美命题 / 决策集合 / 通用质量门槛 / 类型启发
├── perception-and-form.md                # 格式塔 / 前注意特征 / 视觉层级与负空间 / 加工流畅性
├── typography-aesthetics.md              # 字形与声音 / 字体分类 / 比例与视觉大小 / 字重与层级
├── interaction-design-aesthetics.md      # 可供性 / 映射 / 反馈 / 约束与防错
├── aesthetic-judgment-theories.md        # 形式论 / 再现与符号 / 表现与情感 / 经验论与实用主义
├── aesthetic-categories.md               # 优美 / 崇高 / 如画 / 悲剧与喜剧 —— 情绪不是风格标签
├── chinese-painting-theory.md            # 六法论 / 画道论 / 形神论
├── chinese-aesthetics-beyond-painting.md # 礼乐 / 道家 / 禅 / 诗学的意象与含蓄
├── western-aesthetics.md                 # 古典 → 中世纪 → 文艺复兴 → 现代
├── contemporary-frontiers.md             # 神经美学 / 日常美学 / 关系美学
├── global-aesthetic-lenses.md            # 印度味与情 / 伊斯兰统一与光 / 日本间·幽玄·物哀·侘寂 / 非洲离散
├── japanese-aesthetics-deep-dive.md      # 神道感应 / 物哀 / 幽玄 / 禅与直接经验
├── modern-design-history.md              # 工业化 → 工艺美术 → 新艺术 → 维也纳与制造联盟
├── cross-cultural-design-aesthetics.md   # 文化模型 / 语言不是替换字符串 / 书写系统与阅读方向
├── agents/openai.yaml                    # 隐式调用声明
├── scripts/aos.py                        # 系统调用：带状态、会拒绝的审美判断接口
├── scripts/test_aos.py                   # 核心回归测试（19 项断言，重点测拒绝路径）
├── scripts/lint_skill.py                 # 结构自检：四段式 / 路由覆盖 / 坏链 / 引号与换行
└── scripts/verify_utf8.py                # 严格 UTF-8 / 无 BOM / 无乱码自检
```

15 篇参考不等于要背术语。技能里写死了原则：**理论只有转化为观察反射、取舍顺序或红线，才进入行动**；默认体现判断，不展示术语。除两份协议外，每篇参考都以 `使用边界 → 直觉化规则 → 误用警报 → 操作转译` 收尾——最后那节必须写出可执行的判断句，写不出就不算写完。这条规则由 `scripts/lint_skill.py` 实际检查，不靠自觉。

## 安装

```bash
# 通用：放进你的 Agent 技能目录
git clone https://github.com/Greatbeing/aesthetics-os.git <skills-dir>/Aesthetics-OS
```

Hermes Agent（Windows）的默认技能目录是 `%LOCALAPPDATA%\hermes\skills\`：

```bash
git clone https://github.com/Greatbeing/aesthetics-os.git \
  “$LOCALAPPDATA/hermes/skills/Aesthetics-OS”
```

安装后自检结构与编码：

```bash
python scripts/lint_skill.py .    # 四段式 / 路由覆盖 / 坏链 / 引号与换行
python scripts/verify_utf8.py .   # 严格 UTF-8 / 无 BOM / 无乱码
```

## 和其他 Skill 的分工

执行 Skill 负责生产与技术验证（出图、构建页面、跑测试）。
aesthetics-OS 只负责审美直觉、系统一致性和独立审美门槛。

所以它会交出这样的句子，而不是交付物本身：

```
命题：面向财务负责人完成月度对账时呈现可托付的克制，通过精确数字的层级差表达。
证据：金额与差额的字号差只有 2px，视线先落在装饰性渐变而非差异行。
优先修改：把差异行提到视觉重力第一层，删掉顶部渐变光带。
记忆点：唯一一处朱砂红，只标注“待核实”。
非目标：不做“科技感”，不加网格与扫描线。
结论：技术通过，审美暂定——需看过 1440 与 375 两个断点的实际截图再定。
```

## License

MIT © 2026 Greatbeing