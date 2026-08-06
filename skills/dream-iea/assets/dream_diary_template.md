# 梦境采集模板（Dream Diary Template）

> 用于 Step 1 元素解码。支持两种形态，**平等兼容**：
> - **碎片化**：词组 / 短句 / 跳跃片段
> - **完整叙事**：语法规范的梦境描述
>
> 两者走同一解码路径，不偏废任一种。

## 一、JSON 结构

```json
{
  "entries": [
    {
      "date": "YYYY-MM-DD",
      "raw": "原始梦境表述（碎片化或完整均可）",
      "residual": false,
      "schemas": ["CONTAINER", "BLOCKAGE"],
      "emotions": ["恐惧"],
      "event_note": "梦前 1-7 天相关事件（用于近期事件线）"
    }
  ],
  "C2": 5,
  "C3": 5,
  "C4": 4
}
```

字段说明：
- `date`：日期
- `raw`：原始梦境文本（保留原貌，便于复核）
- `residual`：是否为日间残留（当天回放 vs 深层模式），默认 false
- `schemas`：Step 1 解码出的意象图式（取自 `references/element_typology.md` 九类）
- `emotions`：情感元素（六类：恐惧/敬畏/厌恶/喜悦/悲伤/愤怒）
- `event_note`：梦前事件备注，用于 Step 3 近期事件线
- `C2/C3/C4`：分析者赋值（也可在命令行传入，见 SKILL.md）

## 二、碎片化示例占位（结构演示，非真实数据）

```json
{
  "date": "YYYY-MM-DD",
  "raw": "[地点] 找不到出口 [实体]人影跟着 [动作]墙裂 水涌 [情感]害怕",
  "residual": false,
  "schemas": ["CONTAINER", "BLOCKAGE", "CONTAINER破裂", "FORCE"],
  "emotions": ["恐惧"],
  "event_note": "<梦前 1-7 天相关事件>"
}
```

> 说明：上方为字段结构示范。实际分析请填入真实梦境，至少 7 篇（理想 14 篇）以建立基线。

## 三、完整叙事占位

将整段梦境放入 `raw`，标注时先去叙事化、再拆解为 `schemas` / `emotions`。碎片化与完整叙事解码路径一致。
