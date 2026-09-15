# 开源竞品调研 — 双语字幕 + 记单词

> 调研时间：2026-09 · 目的：看别人怎么拆问题，校准 Leran 的产品与技术选型。  
> 来源：GitHub API 检索 + 已知高星仓库元数据（star 为查询时快照）。

---

## 1. 先说结论

开源世界把这件事拆成了 **三条互不打通的产品线**，几乎没有一家把「无字幕视频 → 双语字幕工作台 → 内置 SRS 记词」做成同一条 Web 产品闭环：

| 产品线 | 代表 | 输入假设 | 输出 | 缺什么 |
|--------|------|----------|------|--------|
| **字幕/翻译流水线** | pyvideotrans, VideoLingo, jzsub | 视频（常无字幕） | 双语 SRT / 成片 | 不管学习、不管复习 |
| **挖矿/制卡** | asbplayer, mpvacious, movies2anki | **已有字幕** 的视频 | Anki 卡片（含音频截图） | 不生成字幕；依赖外部 Anki |
| **语言学习播放器** | LLPlayer, SuViPlayer, voracious | 已有字幕 | 播放时点词/循环/查词 | 多是桌面端；复习很弱或外挂 |

**对 Leran 的含义：**  
我们做的「双核闭环」不是已经饱和的红海，而是把上面三类的断点接起来。差异化不在「再写一个 Whisper wrapper」，而在：

1. **字幕是学习语料的中间态**，不是终点成片（和搬运字幕组工具不同）。
2. **点词入卡必须带 media_id + t_ms**，复习能一键回放原句（挖矿工具擅长，流水线工具没有）。
3. **Web + 云/本地混合 Provider**（多数高星工具是桌面 GUI 或 CLI）。

---

## 2. 三条线的代表项目与思路

### 2.1 字幕/翻译流水线（解决「无字幕 → 双语字幕」）

| 项目 | Star | 技术/形态 | 核心思路 |
|------|------|-----------|----------|
| [jianchang512/pyvideotrans](https://github.com/jianchang512/pyvideotrans) | ~19.0k | Python 桌面/GUI，GPL-3.0 | 视频语言互译 + 配音 + 字幕；供应商极多（ASR/TTS/翻译可换）；目标是「成片」 |
| [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) | ~18.4k | Python 流水线，Apache-2.0 | 「Netflix 级」切割→翻译→对齐→配音；强在 **分步 + LLM 润色** 的质量链，不是一发 Whisper 就完 |
| [pengchujin/jzsub](https://github.com/pengchujin/jzsub) | ~986 | Python，MIT | 一条链接 → 最高画质视频 + GPT 双语字幕 MP4；产品化「一键交付」 |
| [Ifan24/GPT_subtitles](https://github.com/Ifan24/GPT_subtitles) | ~121 | Notebook/脚本 | yt-dlp + Whisper + GPT 译文合并双语；最简参考实现 |
| [skindhu/VideoLingua](https://github.com/skindhu/VideoLingua) | ~52 | Python | 提取/翻译/烧录/内容总结模块化；Whisper + Gemini |
| [DualSubs/Universal](https://github.com/DualSubs/Universal) | ~1.4k | JS 脚本（Surge 等） | **不生成字幕**：拦截流媒体已有字幕轨做双语叠加；另一条路 |

**可借鉴的流水线心智（VideoLingo / pyvideotrans 共性）：**

```text
抽取音频
  → ASR（本地 Whisper / 云端可切换）
  → 句子级清理与切割（过短合并、过长拆分、标点）
  → 分批翻译（上下文窗口，不是逐句孤立）
  → 时间对齐回写
  → （可选）TTS 配音 / 烧录
```

**和 Leran 的差异：**  
它们服务「搬运/本地化成片」。我们只需要到「可编辑双语字幕 + 可入卡」，**不要** MVP 做配音、烧录、说话人克隆。但 **切割 + 分批上下文翻译 + 重跑单段** 必须抄作业。

### 2.2 挖矿 / 制卡（解决「字幕 → 单词/句子卡」）

| 项目 | Star | 形态 | 核心思路 |
|------|------|------|----------|
| [asbplayer/asbplayer](https://github.com/asbplayer/asbplayer) | 高星（浏览器播放器 + Chrome 扩展） | Web/扩展 | 「sentence mining」标准交互：当前字幕句 → 截帧 + 音频片段 → Anki |
| [Ajatt-Tools/mpvacious](https://github.com/Ajatt-Tools/mpvacious) | ~889 | mpv Lua | 热键制卡；音频+截图+字幕上下文推 AnkiConnect |
| [kelciour/movies2anki](https://github.com/kelciour/movies2anki) | ~341（已归档） | Python | 经典 subs2srs：电影+字幕批量切卡；启发了整个社区 |
| [rsimmons/voracious](https://github.com/rsimmons/voracious) | ~370（停更） | 桌面播放器 | 学习型播放器 + 导出 Anki；早期形态验证 |

**可借鉴的制卡心智：**

- 卡片必须带 **原句、音频切片、可选截图、时间戳**，否则脱离语境等于退回词书。
- 挖矿发生在 **播放当前句** 时，而不是事后在词库里手输。
- 社区默认出口是 Anki；Leran 要么内置 SRS，要么 **双出口**（内置复习 + Anki 导出）。

**和 Leran 的差异：**  
它们假设字幕已存在。Leran 要把「造字幕」和「挖词」接在同一个工作台里，避免用户先跑 pyvideotrans 再开 asbplayer。

### 2.3 语言学习播放器（解决「播放时怎么学」）

| 项目 | Star | 形态 | 核心思路 |
|------|------|------|----------|
| [umlx5h/LLPlayer](https://github.com/umlx5h/LLPlayer) | ~4.1k | C#/WPF 桌面 | 双语字幕、AI 生成字幕、实时翻译、OCR、LLM 查词、yt-dlp |
| [ahmedismailc/SuViPlayer](https://github.com/ahmedismailc/SuViPlayer) | 小众 | C# Windows | 交互字幕、生词本、A-B 循环、影子跟读 |
| [translate-tools/linguist](https://github.com/translate-tools/linguist) | ~1.1k | 浏览器扩展 | 网页/Netflix 字幕翻译 + **离线个人词典** |

**可借鉴：**  
A-B 循环、当前句高亮、点词弹词典、生词本列表——这些是「90% 时间用户在的状态」，比花哨首页重要。LLPlayer 把 AI 字幕做进播放器，说明用户要的是 **边看边处理**，不是永远停留在上传页。

### 2.4 最接近 Leran 理念的「缝合怪」

| 项目 | 说明 |
|------|------|
| [Vinson1014/LinguaReel](https://github.com/Vinson1014/LinguaReel) | Obsidian 插件：视频影子跟读 + 同步字幕 + LLM 词典 + **FSRS 卡片** + Whisper/多 LLM。概念上几乎是我们双核的插件版，但绑定笔记软件，不是独立 Web 产品 |
| bilibili-digest 等扩展 | 字幕阅读、双语对照、划词、带时间戳笔记——「视频即语料」的交互验证，偏平台扩展 |

---

## 3. 技术栈共识（抄作业清单）

从高星项目里反复出现的零件：

| 环节 | 高频选择 | 备注 |
|------|----------|------|
| 拉视频 | yt-dlp | URL 导入用；本地文件上传可跳过 |
| 抽音频 | ffmpeg | 16kHz mono 几乎是标准 |
| 词级时间戳 | whisperX / faster-whisper + alignment | **点词高亮、精确入卡需要词级**；句级 SRT 不够 |
| 说话人 | whisperX diarization | P2，MVP 不做 |
| 翻译 | OpenAI 兼容 API / DeepL / Gemini / Ollama | 分批 + 上下文；术语表 |
| 双语合并 | 自写 SRT 合并（en 上 zh 下） | 格式简单，别引入重型字幕编辑器 |
| 制卡出口 | AnkiConnect / CSV / 内置 FSRS | 我们内置 + 导出 |
| UI 形态 | 多数桌面 GUI；Web 学习产品稀缺 | Leran 选 Web 是差异也是风险（大文件上传） |

**本地 ASR：** faster-whisper 是当前质量/速度共识；Windows 打包可参考 whisper-standalone-win / faster-whisper-GUI 的依赖方式，但 **应用层只依赖 Provider 接口**，不要绑死某个 GUI。

---

## 4. 对 PRODUCT_DESIGN 的校准

### 4.1 确认正确的（保持）

- 双核闭环：字幕生产 + SRS，而不是做成「又一个字幕精灵」或「又一个 Anki」。
- Provider 适配层 + 用户自带 Key。
- raw/edited 字幕分离、段级重跑。
- 卡片带 media + t_ms，复习可回看。

### 4.2 建议加强（从竞品补进设计）

| 优先级 | 改动 | 来源 |
|--------|------|------|
| P0.5 | ASR 结果增加 **词级时间戳**（whisperX 或云端 word timestamps），工作台支持句内点词高亮与入卡定位 | asbplayer / LLPlayer |
| P0.5 | 翻译必须 **带上下文分批**（前后 N 句），禁止严格逐句独立请求 | VideoLingo |
| P1 | 「挖矿模式」快捷键：播放到句末自动暂停可选；`A` 入卡当前句整句 | mpvacious / asbplayer |
| P1 | 卡片媒体附件：可选 2–3s 音频切片（复习时听原声） | movies2anki 传统 |
| P1 | Anki 导出（TSV + 媒体文件夹）作为内置 SRS 的旁路 | 社区刚需 |
| P2 | A-B 循环、影子跟读 | SuViPlayer / LinguaReel |
| P2 | URL 导入（yt-dlp） | jzsub / VideoLingo |

### 4.3 明确不抄的

| 不做 | 原因 |
|------|------|
| 配音 / 声音克隆 / 成片烧录 | 属于搬运字幕组赛道，膨胀快、与学习闭环无关 |
| 绑定 Obsidian / Anki 为唯一宿主 | 我们是独立 Web 产品；Anki 只是导出 |
| 重做完整 VLC 级播放器 | 播放器是手段；工作台用原生 `<video>` + cue 层够 MVP |
| 流媒体字幕劫持（DualSubs 路线） | 法律与平台风险高，且解决不了「无字幕」 |

### 4.4 架构层小修正（写入下一版设计）

1. **Segment 模型** 增加可选 `words: [{text, start_ms, end_ms}]`，供点词与卡拉 OK 式高亮。  
2. **TranslateProvider** 输入应是 `[{id, text}]` 数组 + `context_before/context_after`，输出同 id 对齐。  
3. **Card** 增加可选 `audio_clip_key`（从 media 按 t_ms 截 2–4s）。  
4. MVP 仍 **不做** 词级强制依赖：没有 words 时退化为整句入卡（降低首版风险）。

---

## 5. 竞品地图（一句话定位）

```text
                    无字幕 ──────────────────────────► 有字幕
                         │                              │
  做成片/搬运            │  pyvideotrans / VideoLingo    │  DualSubs（劫持已有轨）
                         │  jzsub / GPT_subtitles        │
                         │                              │
  做学习闭环             │  ★ Leran 的目标空档 ★        │  asbplayer / mpvacious
                         │  （Web 工作台 + 内置 SRS）    │  movies2anki → Anki
                         │                              │  LLPlayer / SuViPlayer
                         │                              │  LinguaReel（Obsidian+FSRS）
```

---

## 6. 建议的参考阅读顺序（实现前）

1. **VideoLingo** 流水线目录结构与切割/翻译脚本 — 学质量链。  
2. **asbplayer** 的 sentence mining 交互与 Anki 字段 — 学入卡 UX。  
3. **mpvacious** 的快捷键与音频切片逻辑 — 学「播放中制卡」。  
4. **whisperX** README 中 word timestamps 输出格式 — 学数据结构。  
5. **pyvideotrans** 的 Provider 配置面 — 学「可切换云厂商」如何做用户设置。

不必整仓 fork；Leran 自建 Web 产品，零件级借鉴即可。注意许可证：pyvideotrans 为 GPL-3.0，**不要直接拷贝其代码进商业闭源**；VideoLingo Apache-2.0、whisperX BSD-2、asbplayer 需再核对具体 license 后再引用代码。

---

## 7. 对当前设计文档的影响摘要

- **产品定位不变**，空档得到验证。  
- **P0 增加：** 词级时间戳可选字段 + 上下文分批翻译（写入流水线规格）。  
- **P1 增加：** 句级音频切片入卡、Anki 导出、播放挖矿快捷键。  
- **继续砍掉：** 配音烧录、流媒体劫持、重播放器。

详见 `docs/PRODUCT_DESIGN.md`；实现阶段以本文档 §4.2/§4.4 为增量约束。
