<div align="right"><sub><b>简体中文</b>&nbsp;&nbsp;⇄&nbsp;&nbsp;<a href="./README.en.md">English</a></sub></div>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/hero-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/hero-light.svg">
  <img src="./assets/hero-light.svg" width="880" alt="abldrift — 去审查(abliteration)模型发布前的行为漂移审计器">
</picture>

<p><sub>去审查(abliterated)模型发布前的行为漂移审计器——测量乐观度 / 语气 / 风险规避的沉默漂移。本地 Ollama 模型配对审计，发布前的 drift 门禁。</sub></p>

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/github/v/release/SuperMarioYL/abldrift?label=release" alt="Latest release">
  <a href="https://github.com/SuperMarioYL/abldrift/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/SuperMarioYL/abldrift/ci.yml?label=CI&logo=github" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.12-3776AB.svg?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/for-Agent-teams-8985FF.svg" alt="for Agent teams">
  <img src="https://img.shields.io/badge/CI-drift--gate-2DC79A.svg" alt="CI drift gate">
</p>

**去审查(abliteration / uncensor)不只是移除拒绝——它会沉默地改变模型的乐观度、语气、风险规避。** abldrift 在你把修改后的模型发布进 Agent 或产品之前，跑 30 条 non-refusal 探针配对打分，把一个沉默的正确性 bug 变成一份命名、可复现、带 bootstrap 95% CI 的行为 delta 报告。复现 Distilling Deepseek 行为漂移 · Coding Agent 上线前 drift 门禁 · 本地 Ollama 模型配对审计。

<h2><img src="https://api.iconify.design/tabler:topology-star-3.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 架构</h2>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/atlas-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="./assets/atlas-light.svg">
  <img src="./assets/atlas-light.svg" width="880" alt="架构：probe set → runner(base+modified paired · Ollama) → judge(LLM-as-judge pinned) → delta vector(bootstrap CI) → delta.md/json">
</picture>

单进程 Python CLI，无服务、无数据库，只依赖你本地一个 Ollama daemon。三个组件：**probe set**（30 条 non-refusal 探针，刻意不触发拒绝，专挑乐观/语气/风险规避这类会漂移的问法）→ **runner + judge**（配对跑 base 与 modified，同一个 pinned judge 打分，配对消去 judge 绝对偏置）→ **delta + report**（算行为 delta 向量 + bootstrap 95% CI，输出 `delta.md` / `delta.json`）。新原语是**行为 delta 向量**——和拒绝检测(refusalscope)正交：拒绝检测看「这一条答没答」，abldrift 看「这次修改把模型的行为挪了多少」。

<h2><img src="https://api.iconify.design/tabler:download.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 安装</h2>

```bash
pip install abldrift
```

要求 Python 3.12+ 与一个本地 Ollama daemon（`ollama serve`）。从源码安装：`git clone … && cd abldrift && pip install -e .`。

<h2><img src="https://api.iconify.design/tabler:rocket.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 快速开始</h2>

三条命令，从安装到第一份 `delta.md`（假设你已 `ollama pull` 了 base 与 abliterated 两个模型）：

```bash
ollama pull qwen2.5:7b && ollama pull qwen2.5:7b-abliterated   # 一次性
abldrift run --base qwen2.5:7b --modified qwen2.5:7b-abliterated   # ~60s，30×2×2 次调用
cat delta.md                                                      # delta 向量 + per-prompt 表 + 95% CI
```

退出码 0 = drift 在容差内，1 = 超出容差（CI 门禁）。`--json` 直接吐 `delta.json` 给 CI 集成。

<details><summary>sample 输出</summary>

```
┏━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ dimension     ┃  delta ┃           95% CI ┃ excludes 0? ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ optimism      │ +1.080 │ [+0.760, +1.420] │     yes     │
│ tone          │ +0.640 │ [+0.210, +1.070] │     yes     │
│ risk_aversion │ -0.320 │ [-0.810, +0.190] │     no      │
└───────────────┴────────┴──────────────────┴─────────────┘
verdict: DRIFT DETECTED  (tolerance ±0.5, n=30)
```

</details>

<h2><img src="https://api.iconify.design/tabler:terminal-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 用法</h2>

**1. 基础配对审计（最常用）**

```bash
abldrift run --base qwen2.5:7b --modified qwen2.5:7b-abliterated
# 写出 delta.md + delta.json；退出码 0/1 作 CI 门禁
```

**2. 钉死 judge 模型（复现性）**

```bash
abldrift run --base qwen2.5:7b --modified qwen2.5:7b-abliterated --judge llama3.1:8b
# judge 默认 = base；钉死后两次跑同一对模型结果一致，judge 偏置被配对消去
```

**3. 纯 JSON 给 CI（不写文件）**

```bash
abldrift run --base qwen2.5:7b --modified qwen2.5:7b-abliterated \
  --json --no-write | jq '.breached, .ci_excludes_zero'
```

**4. 离线自检（无需 Ollama，验纯 delta 路径）**

```bash
abldrift selftest     # 用合成分数跑 delta + CI，确认装好了
abldrift probes       # 打印 30 条探针集
```

主要 flag：`--tolerance`（门禁阈值，默认 0.5）、`--n-boot`（bootstrap 次数，默认 2000）、`--seed`（复现）、`--out`（报告目录）、`--host`（Ollama 地址）。

<h2><img src="https://api.iconify.design/tabler:photo.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> Demo</h2>

![demo](assets/demo.gif)

`selftest`（离线合成分数）→ `probes` 列探针 → `run` 跑真实 base/modified 配对 → 读 `delta.md`，末尾即那份带 bootstrap 95% CI 与 `excludes 0?` 列的 delta 报告。

<h2><img src="https://api.iconify.design/tabler:bubble-question.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 为什么是 abldrift</h2>

- **沉默漂移是真 bug**——r/LocalLLaMA 上有人拿 uncensored 模型做股票预测，才发现「它不只是拒绝少了」，乐观度被挪到了下游决策上。abldrift 在你发布前把这种漂移变成命名、可复现的报告。
- **新原语：行为 delta 向量**——不是「这条答没答」（refusalscope 的活），也不是「tool 合约有没有回归」（tooldrift 的活），而是「这次修改把乐观度/语气/风险规避挪了多少」。一个 typed record：mean delta + per-prompt diff + bootstrap 95% CI。
- **配对打分消去 judge 偏置**——LLM-as-judge 点估计不可信，所以 `--judge` 钉死、配对打分、报 bootstrap CI 而非点数。一个 CI 排除 0 的维度才是「真的漂了」。
- **CI 门禁**——退出码 0/1，直接塞进发布前检查；`--json` 给流水线。
- **本地、可气隙**——只依赖你的 Ollama，不上传模型，无第三方服务。

<h2><img src="https://api.iconify.design/tabler:arrows-exchange.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 对比</h2>

和最接近的「去审查模型 runner」[techjarves/USB-Uncensored-LLM](https://github.com/techjarves/USB-Uncensored-LLM) 比——它是 runner，不是 evaluator，二者正交：

| 维度 | abldrift | USB-Uncensored-LLM |
|---|---|---|
| 定位 | 行为漂移审计器（发布前 delta + CI 门禁） | 去/装审查模型的 runner（零安装本地盒） |
| 行为 delta 报告 | ✓ typed 向量 + bootstrap 95% CI | — |
| CI 退出码门禁 | ✓ exit 0/1 | — |
| 拒绝移除 / 模型运行 | —（只审计，不改模型） | ✓ |
| 气隙 / 离线 | ✓（本地 Ollama） | ✓ |
| 安装体验 | 一条 pip | 一条 USB |

> 它们做得更好的一行：开箱即用的 uncensored 体验 + 跨平台便携。abldrift 不抢 runner 的活——它补 runner 缺的那份「发布前 delta」。

<h2><img src="https://api.iconify.design/tabler:adjustments.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 配置</h2>

探针集是唯一事实源，外置在 `abldrift/data/probes.yaml`——改探针只改 YAML，不碰 Python。三个维度各 10 条，刻意 non-refusal：

| 维度 | 条数 | 触发什么 | 高分/低分含义 |
|---|---|---|---|
| `optimism` | 10 | 前瞻乐观/悲观（股票、发布、增长） | 5 乐观 ↔ 1 悲观 |
| `tone` | 10 | 正式 ↔ 随意语气 | 5 随意 ↔ 1 正式 |
| `risk_aversion` | 10 | 风险偏好 ↔ 规避（迁移、回滚、采纳） | 1 激进 ↔ 5 规避 |

门禁参数：`--tolerance`（默认 0.5，1–5 量表）、`--n-boot`（默认 2000）、`--seed`（默认 42，复现）。

<h2><img src="https://api.iconify.design/tabler:coin.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 付费 / Pricing</h2>

abldrift 本体 **OSS + 本地，永久免费**——把审计器本身开源、可气隙自托管，是建立信任与起星的前提。气隙用户（自托管 OSS）永不付费。

面向**非气隙企业 / 合规团队**的**托管签名合规 delta 报告 + 团队仪表盘**（规划中，v0.2+）：他们把 abliterated 模型发布进产品或 Agent 循环，需要一份**签名**的 delta 报告做审计留痕——OSS 自托管给不了「带签名的合规件」。OSS 跑出漂移 →「能给我签个名吗？」→ 一个 serverless 端点重跑、返回签名 `delta.json` + PDF。

| 层级 | 面向 | 价格（方向，未上线） |
|---|---|---|
| **OSS** | 本地 LLM 实践者，自托管 | 免费 · 永久开源 |
| **签名 delta 报告**（单次） | Coding Agent shop / 内容工作室，一次性审计 | $49/报告 |
| **团队仪表盘**（多席位） | 合规团队，发布前留痕 | $499/席位/年（3 席起） |

> v0.1 不落任何付费墙，这里仅标注方向。托管层将在确认真实需求后上线。

<h2><img src="https://api.iconify.design/tabler:map-2.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 路线图</h2>

- [x] **v0.1 (m1+m2)** — 30 条 non-refusal 探针集 · 配对 runner + pinned judge · 行为 delta 向量 + bootstrap 95% CI · `abldrift run` CLI + `delta.md`/`delta.json` + exit 0/1 门禁
- [ ] **m3** — 录 `demo.cast`（从 tape）· 复现 ctgt.ai Distilling Deepseek 蒸馏转移实验并发 delta 报告 · 发 Show HN + r/LocalLLaMA
- [ ] 把动词从「abliteration 漂移」扩到「任意发布前修改漂移」（RLHF-strip、SFT、新方法）
- [ ] 签名合规 delta 报告端点 + 团队仪表盘（v0.2+ 托管层）
- [ ] 非 Ollama 后端（vLLM / llama.cpp direct）

## 不做的事

Web UI / TUI（CLI only）· 托管 SaaS / 团队仪表盘 / 鉴权（v0.1 本地 OSS；付费层命名不构建）· 拒绝检测（refusalscope 的活）· tool-call 合约回归（tooldrift 的活）· 自训 judge 模型（复用现有本地模型）· 微调 / abliteration 配方生成（abldrift 只审计，不改模型）· 非 Ollama 后端（v0.1 = Ollama only）· 持续漂移监控 · diff 可视化 TUI。

<h2><img src="https://api.iconify.design/tabler:share.svg?color=%230071E3&width=24" height="22" align="absmiddle" alt=""> 分享</h2>

```
abldrift — abliteration 行为漂移审计器。去审查不只移除拒绝，它沉默改变乐观度/语气/风险规避；发布前跑 30 条配对探针，拿带 95% CI 的 delta + CI 门禁退出码。https://github.com/SuperMarioYL/abldrift
```

> 推送后设置 topics：`gh repo edit --add-topic llm --add-topic ollama --add-topic abliteration --add-topic llm-eval --add-topic agent`

<p align="center"><sub><a href="./LICENSE">MIT</a> © 2026 SuperMarioYL</sub></p>
