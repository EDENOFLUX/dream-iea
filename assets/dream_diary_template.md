# 梦境日记采集模板

> 碎片化和完整叙事两种形态平等兼容。每天记录一篇，至少积累 7 天再分析。

---

## 格式一：碎片化（推荐日常使用）

只需记录关键词和短句，不需要完整句子。

```
日期 | 场景关键词 动作关键词 感受关键词 [事件: 当天值得记的事]
```

### 示例

```
2026-03-01 | 地下停车场 找不到出口 人影跟着 墙裂 水涌 害怕   [事件: 项目deadline临近]
2026-03-02 | 教室 铁链锁桌椅 黑影堵门 叫不出声 焦虑          [事件: 准备汇报]
2026-03-03 | 看悬疑片 场景重现 追逐                          [事件: 白天看了悬疑电影] ← 日间残留
```

---

## 格式二：完整叙事

写出完整的故事和感受。

```
日期：YYYY-MM-DD
梦境：[完整描述]
情绪：[主要感受]
事件：[当天或前1-2天的关键事件]
日间残留？：是/否（当天看过的影视/经历过的场景直接入梦）
```

---

## JSON 标注格式（供脚本消费）

积累日记后，标注为以下 JSON 格式供 `analyze_dreams.py` 使用：

```json
{
  "analyst": {
    "C2": 5, "C3": 5, "C4": 4,
    "notes": "分析者备注"
  },
  "baseline": {
    "BLOCKAGE": 0.2, "CONTAINER": 0.3, "FORCE": 0.1,
    "恐惧": 0.2, "喜悦": 0.1
  },
  "diaries": [
    {
      "date": "2026-03-01",
      "content": "梦境原文或关键词",
      "schemas": ["CONTAINER", "BLOCKAGE"],
      "schema_combo": "BLOCKAGE+CONTAINER",
      "emotions": [{"type": "恐惧", "intensity": 1.0}],
      "day_residue": false,
      "event": "近期事件"
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| date | string | 日期 YYYY-MM-DD |
| content | string | 梦境原文（碎片或完整） |
| schemas | string[] | 当篇识别到的意象图式列表 |
| schema_combo | string\|null | 分析者标注的主组合模式（如 "BLOCKAGE+CONTAINER"），用于 Gestalt 闭合 |
| schema_combos | string[]\|null | 同篇多个闭合组合（列表形式，优先于 schema_combo） |
| emotions | object[] | 情感列表，每项 {type, intensity}；type 须为六类之一 |
| day_residue | bool | 是否为日间残留（当天事件直接回放） |
| event | string | 梦前 1-7 天的关键事件 |

> **schema_combo vs schema_combos**：`schema_combo` 是单字符串（向后兼容），`schema_combos` 是列表（同篇有多个闭合组合时使用）。脚本优先读 `schema_combos`，若无则回退到 `schema_combo`。

### 意象图式可选值

CONTAINER / CONTAINER破裂 / SOURCE-PATH-GOAL / VERTICALITY / BALANCE / LINK / CENTER-PERIPHERY / FORCE / BLOCKAGE

### 情感可选值

恐惧 / 敬畏 / 厌恶 / 喜悦 / 悲伤 / 愤怒

---

*Dream-IEA · 梦境采集模板 · 2026-03 · 2026-07 增补 schema_combos 字段*
