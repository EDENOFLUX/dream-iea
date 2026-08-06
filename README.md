# dream-iea · 梦境分析 Skill

> © 2026 Luci逻辑喵 (EDENOFLUX) · [CC BY-NC-SA 4.0](./LICENSE)

基于 **IEA（信息元素回溯法）** 改造的梦境分析框架，将梦境叙事（碎片化或完整均可）经
**「信息元素 → 意象图式 → 心理状态」三层映射**，用心理学 / 神经科学理论反推近期心理状态。

> 灵感草案阶段之外的**已成型可运行**作品。评分体系对齐 [LPP 言灵](https://github.com/EDENOFLUX/yanling-lpp)。

## 核心纪律

信息元素**绝不直接**指向心理状态，必须经过意象图式这一中层。不做「梦到 X = 你在 Y」的象征跳译。

## 三层映射（不可跳步）

```
梦境叙事（碎片化 or 完整均可）
  ↓ Step 1  元素解码      → 信息元素（客观标注，不解释）
  ↓ Step 2a 图式识别      → 意象图式（客观模式检测，不推断）
  ↓ Step 2b 理论翻译      → 心理状态（心理学/神经科学驱动）
  ↓ Step 3  三线叠图      → 锚定到个人时空框架
```

## 目录结构

```
skills/dream-iea/
├── SKILL.md                      # 技能主指令
├── references/
│   ├── element_typology.md       # 七类元素 + 意象图式速查
│   ├── scoring.md                # 光谱评分 + ■●▲△ 置信规范 + R1-R7 规则
│   └── theory_translation.md     # 六理论翻译函数 + 排除项
├── scripts/
│   └── analyze_dreams.py         # Step 2a 图式层客观统计引擎
├── assets/
│   ├── dream_diary_template.md   # 梦境采集模板（JSON）
│   └── report_template.md        # 三层报告标准格式
└── examples/                     # 空白占位（不含任何样本数据）
```

## 快速使用

```bash
# 1) 按 assets/dream_diary_template.md 标注梦境（至少 7 篇，理想 14 篇），存为 JSON
# 2) 运行 Step 2a 客观统计 + 光谱打分
python3 skills/dream-iea/scripts/analyze_dreams.py \
    -i your_diary.json \
    --C2 5 --C3 5 --C4 4 \
    --baseline '{"<图式名>":<基线频率>,"<情感名>":<基线频率>}' -o report.txt
# （C2/C3/C4 也可内嵌在 JSON 顶层，无需命令行参数）
# 3) 分析者据 references/scoring.md 完成 Step 2b 翻译 + Step 3 三线叠图
# 4) 套用 assets/report_template.md 输出三层报告
```

## 设计要点

- **三层映射纪律**：元素 → 图式 → 状态，中间层不可省（区别于「象征解梦」）
- **碎片化 + 完整叙事兼容（平等）**：梦境常碎片化呈现，skill 接得住词组/短句
- **六理论翻译 + 选入/排除逻辑**：排除弗洛伊德象征、随机激活论、荣格原型（缺可操作中间层或不可检验）
- **全情感谱（含正面）**：R7 正面模式同权 —— 积极模式不因「积极」降权
- **评分对齐 LPP**：1-10 光谱 + ■●▲△ 四级置信标记，标记决定动词

## 诚实边界

- 本 skill **不提供临床诊断**，不输出 DSM/ICD 标签
- 所有心理推断**必须交还梦者本人验证**，分析者不拥有最终解释权
- 单篇日记不足以建立基线，至少 7 篇，理想 14 篇
- 综合置信度指数为**启发式指标**，权重非经验校准；其作用是指引谨慎程度，而非量化可靠性

---

*版本：2026-08 重建发布 · 自包含可运行，不依赖 Obsidian。*
