#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dream-IEA Step 2a: 图式层客观统计引擎
=======================================
功能：
  1. 图式频率（对比基线）
  2. 图式共现（同篇内两两）
  3. 情感分布（全谱，正负对称检测）
  4. Gestalt 闭合检测（部分闭合≥3，完全闭合≥5）
  5. 日间残留检测（区分当天回放 vs 深层模式）
  6. 光谱打分（1-10）+ 综合置信度指数

输入：JSON 格式梦境日记（含 schemas, emotions, schema_combo, day_residue, event 等字段）
输出：文本报告（stdout 或 -o 指定文件）

用法：
  python analyze_dreams.py -i examples/your_diary.json
  python analyze_dreams.py -i examples/your_diary.json --C2 5 --C3 5 --C4 4
  python analyze_dreams.py -i examples/your_diary.json -o report.txt
  （analyst 段也可内嵌在 JSON 顶层，无需命令行参数）
  注：examples/ 下的样例数据已移除，请用自己的梦境日记 JSON 作为输入。
"""

import json
import sys
import argparse
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

# ============================================================
# 常量定义
# ============================================================

# 六类情感 + 效价映射
EMOTION_VALENCE = {
    "恐惧": "negative",
    "敬畏": "positive",
    "厌恶": "negative",
    "喜悦": "positive",
    "悲伤": "negative",
    "愤怒": "negative",
}

# 默认图式基线频率（可被 JSON 顶层 baseline 字段覆盖）
DEFAULT_BASELINE = {
    "BLOCKAGE": 0.2,
    "CONTAINER": 0.3,
    "CONTAINER破裂": 0.1,
    "FORCE": 0.1,
    "SOURCE-PATH-GOAL": 0.2,
    "LINK": 0.15,
    "VERTICALITY": 0.15,
    "BALANCE": 0.15,
    "CENTER-PERIPHERY": 0.1,
}

# 光谱条字符
BAR_FULL = "\u2593"   # ▓
BAR_EMPTY = "\u2591"  # ░
EMO_BAR = "\u2588"    # █

# 有效值定义
VALID_SCHEMAS = {
    "CONTAINER", "CONTAINER破裂", "SOURCE-PATH-GOAL", "VERTICALITY",
    "BALANCE", "LINK", "CENTER-PERIPHERY", "FORCE", "BLOCKAGE",
}

VALID_EMOTIONS = {"恐惧", "敬畏", "厌恶", "喜悦", "悲伤", "愤怒"}

# 常见非标准情绪 → 六类映射建议
EMOTION_MAPPING_HINTS = {
    "焦虑": "恐惧", "紧张": "恐惧", "恐慌": "恐惧", "害怕": "恐惧",
    "满足": "喜悦", "兴奋": "喜悦", "快乐": "喜悦", "释然": "喜悦", "开心": "喜悦", "幸福": "喜悦",
    "愧疚": "悲伤", "无力": "悲伤", "失落": "悲伤", "孤独": "悲伤", "沮丧": "悲伤",
    "尴尬": "厌恶", "恶心": "厌恶", "反感": "厌恶",
    "生气": "愤怒", "烦躁": "愤怒", "恼怒": "愤怒",
    "惊奇": "敬畏", "震撼": "敬畏", "崇敬": "敬畏",
}

# ============================================================
# 数据加载
# ============================================================

def load_data(filepath):
    """加载 JSON 格式梦境日记数据"""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    diaries = data.get("diaries", [])
    if not diaries:
        print("错误：未找到日记数据（diaries 字段为空）", file=sys.stderr)
        sys.exit(1)

    # 基线（JSON 覆盖默认）
    baseline = {**DEFAULT_BASELINE, **data.get("baseline", {})}

    # 分析者赋值（JSON 顶层 analyst 段 或 命令参数）
    analyst = data.get("analyst", {})

    # 基线来源标记
    json_baseline = data.get("baseline", {})
    baseline_source = "个人校准基线（JSON 提供）" if json_baseline else "默认基线（未经个人校准，建议积累≥14篇后校准）"

    return data, diaries, baseline, analyst, baseline_source


# ============================================================
# 统计计算
# ============================================================

def compute_frequency(diaries):
    """图式频率统计"""
    total = len(diaries)
    freq = Counter()
    for d in diaries:
        for s in d.get("schemas", []):
            freq[s] += 1
    # 返回 {schema: (count, ratio)} 按频率降序
    result = {}
    for s, c in freq.most_common():
        result[s] = (c, c / total)
    return result, total


def compute_cooccurrence(diaries):
    """图式共现（同篇内两两组合）"""
    cooc = Counter()
    for d in diaries:
        schemas = sorted(set(d.get("schemas", [])))
        for pair in combinations(schemas, 2):
            cooc[pair] += 1
    return cooc


def compute_emotions(diaries):
    """情感分布（全谱）"""
    # 支持两种格式：
    #   1. ["恐惧", "喜悦"]  — 简单字符串列表
    #   2. [{"type": "恐惧", "intensity": 0.8}]  — 带强度
    emo_weight = Counter()
    total_weight = 0.0

    for d in diaries:
        for e in d.get("emotions", []):
            if isinstance(e, dict):
                etype = e.get("type", "未知")
                intensity = e.get("intensity", 1.0)
            else:
                etype = e
                intensity = 1.0
            emo_weight[etype] += intensity
            total_weight += intensity

    if total_weight == 0:
        return {}, 0.0

    emo_freq = {e: w / total_weight for e, w in emo_weight.items()}
    return emo_freq, total_weight


def compute_gestalt(diaries, cooc):
    """Gestalt 闭合检测
    优先使用 schema_combo 字段；若无，回退到共现模式
    """
    # 方式 1: schema_combo / schema_combos 字段
    combo_count = Counter()
    for d in diaries:
        # 支持 schema_combos（列表）和 schema_combo（字符串，向后兼容）
        combos = d.get("schema_combos")
        if combos is None:
            combo = d.get("schema_combo")
            if combo:
                combos = [combo]
        if combos:
            for combo in combos:
                combo_count[combo] += 1

    # 方式 2: 共现模式回退（仅当无 schema_combo 时）
    if not combo_count and cooc:
        for pair, count in cooc.items():
            combo_name = "+".join(pair)
            combo_count[combo_name] = count

    return combo_count


def compute_day_residue(diaries):
    """日间残留检测"""
    residue = []
    deep = []
    for d in diaries:
        if d.get("day_residue", False):
            residue.append(d)
        else:
            deep.append(d)
    return residue, deep


def compute_trend(diaries, dominant_valence="unknown"):
    """情绪衰减趋势分析
    按日期排序，提取每天主导情绪的强度，做简单线性回归。
    dominant_valence: 主导情绪效价 ("positive"/"negative"/"unknown")
    返回: (daily_dates, daily_values, slope, status)
    正面情绪: "增强中" / "稳定（积极持续）" / "减弱中" / "稳定" / "数据不足"
    负面情绪: "衰减中（处理进展）" / "稳定" / "衰减失败⚠" / "上升中（强度增加）" / "数据不足"
    """
    sorted_diaries = sorted(diaries, key=lambda d: d.get("date", ""))

    daily_values = []
    daily_dates = []
    for d in sorted_diaries:
        emos = d.get("emotions", [])
        daily_dates.append(d.get("date", "???"))

        if not emos:
            daily_values.append(0.0)
            continue

        emo_weight = Counter()
        for e in emos:
            if isinstance(e, dict):
                etype = e.get("type", "未知")
                intensity = e.get("intensity", 1.0)
            else:
                etype = e
                intensity = 1.0
            emo_weight[etype] += intensity

        daily_values.append(max(emo_weight.values()) if emo_weight else 0.0)

    # 线性回归
    valid = [(i, v) for i, v in enumerate(daily_values) if v is not None and v > 0]
    if len(valid) < 2:
        return daily_dates, daily_values, 0.0, "数据不足"

    xs = [v[0] for v in valid]
    ys = [v[1] for v in valid]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    slope = numerator / denominator if denominator != 0 else 0.0

    avg_value = sum(ys) / n

    if slope < -0.02:
        if dominant_valence == "positive":
            status = "减弱中（积极情绪下降）"
        else:
            status = "衰减中（处理进展）"
    elif slope > 0.02:
        if dominant_valence == "positive":
            status = "增强中（积极上升）"
        else:
            status = "上升中（强度增加）"
    else:
        if avg_value >= 0.7:
            if dominant_valence == "positive":
                status = "稳定（积极持续）"
            elif dominant_valence == "negative":
                status = "衰减失败⚠（高强度不衰减，卡住）"
            else:
                status = "高强度稳定（效价未知，需人工判断）"
        else:
            status = "稳定"

    return daily_dates, daily_values, round(slope, 4), status


# ============================================================
# 光谱打分（1-10）
# ============================================================

def score_C1(n):
    """数据充分度: N=1→1, N=7→5, N=14+→10"""
    if n <= 1:
        return 1
    if n >= 14:
        return 10
    if n <= 7:
        return round(1 + (n - 1) * (5 - 1) / (7 - 1), 1)
    return round(5 + (n - 7) * (10 - 5) / (14 - 7), 1)


def score_S1(combo_count):
    """图式闭合度: 单次1, 弱闭合(×2)3, 部分闭合(≥3)5, 完全闭合(≥5)9"""
    if not combo_count:
        return 1
    max_count = max(combo_count.values())
    if max_count >= 5:
        return 9
    if max_count >= 3:
        return 5
    if max_count >= 2:
        return 3
    return 1


def score_S2(freq, baseline):
    """基线偏离度: 持平1, 1.5×=5, ≥2×=10"""
    if not freq or not baseline:
        return 1
    max_ratio = 0.0
    for s, (count, ratio) in freq.items():
        b = baseline.get(s, 0.15)
        if b > 0:
            r = ratio / b
            max_ratio = max(max_ratio, r)
    if max_ratio <= 1.0:
        return 1
    if max_ratio >= 2.0:
        return 10
    if max_ratio <= 1.5:
        return round(1 + (max_ratio - 1.0) * (5 - 1) / (1.5 - 1.0), 1)
    return round(5 + (max_ratio - 1.5) * (10 - 5) / (2.0 - 1.5), 1)


def score_S3(emo_freq):
    """情感主导度: 均布1, 单一占0.4=5, 占0.8+=10（不入综合公式）"""
    if not emo_freq:
        return 1
    max_emo = max(emo_freq.values())
    if max_emo <= 0.1:
        return 1
    if max_emo >= 0.8:
        return 10
    if max_emo <= 0.4:
        return round(1 + (max_emo - 0.1) * (5 - 1) / (0.4 - 0.1), 1)
    return round(5 + (max_emo - 0.4) * (10 - 5) / (0.8 - 0.4), 1)


def composite_index(C1, S1, C2, S2, C4):
    """综合置信度指数（加权启发式）
    = 0.25*C1 + 0.25*S1 + 0.20*C2 + 0.15*S2 + 0.15*C4
    （C3 仅用于情绪相关推断的叙事层，不入综合公式）
    """
    return round(0.25 * C1 + 0.25 * S1 + 0.20 * C2 + 0.15 * S2 + 0.15 * C4, 1)


def apply_rules(score, S1, C2, C1, S2):
    """应用 R1-R7 硬规则，返回 (marker, label, rule_notes)"""
    # 公式映射
    if score >= 7.0:
        marker = "\u25a0"  # ■
        label = "强信号"
    elif score >= 4.0:
        marker = "\u25cf"  # ●
        label = "中信号"
    else:
        marker = "\u25b2"  # ▲
        label = "弱信号"

    notes = []

    # R1: 闭合门槛 — S1=1(不闭合) → 封顶 ▲
    if S1 <= 1:
        marker = "\u25b2"
        label = "弱信号"
        notes.append("R1(S1=不闭合\u2192封顶\u25b2)")

    # R2: 数据门槛 — C1<5(N<7) → 封顶 ●
    if C1 < 5:
        if marker == "\u25a0":
            marker = "\u25cf"
            label = "中信号"
            notes.append("R2(N<7\u2192C1<5\u2192封顶\u25cf)")

    # R3: 高置信触发 — S1>=9(完全闭合) 且 C2>=7(高收敛) 且 S2>=5(基线偏离达标) → ≥ ■
    if S1 >= 9 and C2 >= 7 and S2 >= 5:
        notes.append("R3触发(完全闭合+C2≥7+S2≥5→≥■)")
        if marker != "\u25a0":
            marker = "\u25a0"
            label = "强信号"

    # R4: 低收敛封顶 — C2<3.4(低收敛/冲突) → 封顶 ●
    if C2 < 3.4:
        notes.append("R4触发(C2<3.4→封顶●)")
        if marker == "\u25a0":
            marker = "\u25cf"
            label = "中信号"

    if not notes:
        notes.append("纯公式映射，无规则覆盖")

    return marker, label, "; ".join(notes)


# ============================================================
# 数据校验
# ============================================================

def validate_data(diaries):
    """校验日记数据，警告未知情绪类型和图式名称"""
    warnings = []

    for i, d in enumerate(diaries):
        date = d.get("date", f"\u7b2c{i+1}\u7bc7")

        # 校验图式名
        for s in d.get("schemas", []):
            if s not in VALID_SCHEMAS:
                warnings.append(
                    f"  [{date}] \u672a\u77e5\u56fe\u5f0f\u540d: '{s}'"
                    f"\uff08\u6709\u6548\u503c: {', '.join(sorted(VALID_SCHEMAS))}\uff09"
                )

        # 校验情绪类型
        for e in d.get("emotions", []):
            etype = e.get("type", "") if isinstance(e, dict) else e
            if etype and etype not in VALID_EMOTIONS:
                hint = EMOTION_MAPPING_HINTS.get(etype, "")
                hint_str = f" \u2192 \u5efa\u8bae\u6620\u5c04\u4e3a '{hint}'" if hint else ""
                warnings.append(
                    f"  [{date}] \u672a\u77e5\u60c5\u7eea\u7c7b\u578b: '{etype}'"
                    f"\uff08\u6709\u6548\u503c: {', '.join(VALID_EMOTIONS)}\uff09{hint_str}"
                )

    if warnings:
        print("\u26a0 \u6570\u636e\u6821\u9a8c\u8b66\u544a\uff1a", file=sys.stderr)
        for w in warnings:
            print(w, file=sys.stderr)
        print("", file=sys.stderr)

    return len(warnings)


# ============================================================
# 格式化输出
# ============================================================

def bar(score, width=10):
    """生成光谱条：▓▓▓▓▓░░░░░"""
    filled = int(round(score))
    return BAR_FULL * filled + BAR_EMPTY * (width - filled)


def emo_bar(ratio, max_width=40):
    """生成情感分布条：████████"""
    return EMO_BAR * max(1, int(round(ratio * max_width)))


def format_report(diaries, baseline, analyst, cli_args, baseline_source):
    """生成完整文本报告"""
    lines = []

    # --- 图式频率 ---
    freq, total = compute_frequency(diaries)
    lines.append("")
    lines.append("=" * 60)
    lines.append(f"\u56fe\u5f0f\u9891\u7387\uff08\u5171 {total} \u7bc7\u65e5\u8bb0\uff09")
    lines.append("=" * 60)
    lines.append(f"  基线来源: {baseline_source}")
    for s, (count, ratio) in freq.items():
        b = baseline.get(s, 0.15)
        dev_str = ""
        if ratio > b:
            dev_str = f"  \u26a0 \u504f\u79bb\u57fa\u7ebf({b})"
        lines.append(f"  {s:<20s} {ratio:.3f}  ({count}/{total}){dev_str}")

    # --- 图式共现 ---
    cooc = compute_cooccurrence(diaries)
    lines.append("")
    lines.append("=" * 60)
    lines.append("\u56fe\u5f0f\u5171\u73b0\uff08\u540c\u7bc7\u5185\u4e24\u4e24\uff09")
    lines.append("=" * 60)
    for (a, b_name), count in cooc.most_common():
        if count > 0:
            lines.append(f"  {a} + {b_name:<20s} {count}")

    # --- 情感分布 ---
    emo_freq, emo_total = compute_emotions(diaries)
    lines.append("")
    lines.append("=" * 60)
    lines.append("\u60c5\u611f\u5206\u5e03\uff08\u5168\u8c31\uff09")
    lines.append("=" * 60)

    pos_total = 0.0
    neg_total = 0.0
    # 按频率降序排列
    for etype, fr in sorted(emo_freq.items(), key=lambda x: -x[1]):
        valence = EMOTION_VALENCE.get(etype, "unknown")
        sign = "+" if valence == "positive" else ("\u2212" if valence == "negative" else "?")
        lines.append(f"  {sign}{etype}   {fr:.3f} {emo_bar(fr)}")
        if valence == "positive":
            pos_total += fr
        elif valence == "negative":
            neg_total += fr

    lines.append("")
    lines.append(f"  \u6b63\u9762\u60c5\u611f\u5408\u8ba1 {pos_total:.3f} \uff5c \u8d1f\u9762\u60c5\u611f\u5408\u8ba1 {neg_total:.3f}")

    if emo_freq:
        dominant_emo = max(emo_freq, key=emo_freq.get)
        dominant_ratio = emo_freq[dominant_emo]
        lines.append(f"  \u4e3b\u5bfc\u60c5\u611f\uff1a{dominant_emo} ({dominant_ratio:.3f})")

        # 风险标记
        if dominant_ratio > 0.4:
            valence = EMOTION_VALENCE.get(dominant_emo, "unknown")
            if valence == "negative":
                lines.append(f"  \u26a0 {dominant_emo} \u5360\u6bd4 {dominant_ratio:.3f} > 0.4 \u2192 \u8d1f\u9762\u60c5\u611f\u4e3b\u5bfc\uff0c\u9700\u5173\u6ce8")
            elif valence == "positive":
                lines.append(f"  \u26a0 {dominant_emo} \u5360\u6bd4 {dominant_ratio:.3f} > 0.4 \u2192 \u6b63\u9762\u60c5\u611f\u4e3b\u5bfc\uff0c\u9700\u5173\u6ce8")

        if pos_total < 0.1 and neg_total > 0.5:
            lines.append(f"  \u26a0 \u6b63\u9762\u60c5\u611f {pos_total:.3f} < 0.1 \u4e14\u8d1f\u9762 {neg_total:.3f} \u504f\u9ad8 \u2192 \u60c5\u7eea\u57fa\u8c03\u504f\u8d1f")
        elif pos_total > 0.5 and neg_total < 0.1:
            lines.append(f"  \u25cb \u6b63\u9762\u60c5\u611f {pos_total:.3f} > 0.5 \u2192 \u60c5\u7eea\u57fa\u8c03\u504f\u6b63\uff08\u79ef\u6781\u4fe1\u53f7\uff0c\u7ed3\u5408\u56fe\u5f0f\u770b\u6765\u6e90\uff09")

        # 基线偏离
        emo_baseline = baseline.get(dominant_emo, 0.1)
        if dominant_ratio > emo_baseline:
            lines.append(f"  \u26a0 {dominant_emo} \u5360\u6bd4 {dominant_ratio:.3f} \u504f\u79bb\u4e2a\u4eba\u57fa\u7ebf {emo_baseline} \u2192 \u8be5\u60c5\u611f\u6fc0\u6d3b\u5f02\u5e38")

    # --- Gestalt 闭合检测 ---
    combo_count = compute_gestalt(diaries, cooc)
    lines.append("")
    lines.append("=" * 60)
    lines.append("Gestalt \u95ed\u5408\u68c0\u6d4b\uff08\u90e8\u5206\u95ed\u5408\u22653\uff0c\u5b8c\u5168\u95ed\u5408\u22655\uff09")
    lines.append("=" * 60)

    has_closure = False
    for combo, count in combo_count.most_common():
        if count >= 5:
            lines.append(f"  \u5b8c\u5168\u95ed\u5408  {{{combo}}} \u00d7{count}")
            has_closure = True
        elif count >= 3:
            lines.append(f"  \u90e8\u5206\u95ed\u5408  {{{combo}}} \u00d7{count}")
            has_closure = True

    if not has_closure:
        lines.append("  \u65e0\u8fbe\u5230\u90e8\u5206\u95ed\u5408\u9608\u503c\u7684\u56fe\u5f0f\u7ec4\u5408\uff08\u9700\u66f4\u591a\u65e5\u8bb0\u6216\u6807\u6ce8 schema_combo\uff09")

    # --- 日间残留 ---
    residue, deep = compute_day_residue(diaries)
    lines.append("")
    lines.append("=" * 60)
    lines.append("\u65e5\u95f4\u6b8b\u7559\u6807\u8bb0")
    lines.append("=" * 60)
    lines.append(f"  \u6807\u6ce8\u4e3a\u65e5\u95f4\u6b8b\u7559\uff1a{len(residue)} \u7bc7")
    lines.append(f"  \u6df1\u5c42\u56fe\u5f0f\u6a21\u5f0f\u5019\u9009\uff1a{len(deep)} \u7bc7")
    for d in residue:
        event = d.get("event", "")
        if event:
            lines.append(f"    - {d.get('date', '???')}: {event}")

    # --- 收敛预检 ---
    # 确定主导情绪效价（用于趋势分析语义解释）
    dominant_valence = "unknown"
    if emo_freq:
        _dom_emo = max(emo_freq, key=emo_freq.get)
        dominant_valence = EMOTION_VALENCE.get(_dom_emo, "unknown")

    trend_dates, trend_values, trend_slope, trend_status = compute_trend(diaries, dominant_valence)
    lines.append("")
    lines.append("=" * 60)
    lines.append("收敛预检（供 C2/C3 赋值参考）")
    lines.append("=" * 60)

    # 1. 图式信号
    if combo_count:
        top_combo, top_count = combo_count.most_common(1)[0]
        lines.append(f"  图式信号:  {top_combo} ×{top_count}闭合")
    else:
        lines.append(f"  图式信号:  无闭合模式")

    # 2. 情绪信号
    if emo_freq:
        dom_emo = max(emo_freq, key=emo_freq.get)
        dom_ratio = emo_freq[dom_emo]
        valence = EMOTION_VALENCE.get(dom_emo, "unknown")
        lines.append(f"  情绪信号:  {dom_emo} {dom_ratio:.1%} ({valence})")
    else:
        lines.append(f"  情绪信号:  无情绪数据")

    # 3. 残留信号
    if residue:
        residue_events = [f"{d.get('date', '???')}: {d.get('event', '?')}" for d in residue]
        lines.append(f"  残留信号:  {len(residue)}篇标注 day_residue → {'; '.join(residue_events[:3])}")
        lines.append(f"            （残留关联需人工确认）")
    else:
        lines.append(f"  残留信号:  无日间残留标记")

    # 4. 趋势信号
    valid_trend = [v for v in trend_values if v is not None and v > 0]
    if len(valid_trend) >= 2:
        seq_str = ", ".join([f"{v:.2f}" for v in trend_values])
        lines.append(f"  趋势信号:  强度序列 [{seq_str}]")
        lines.append(f"            slope={trend_slope} → {trend_status}")
    else:
        lines.append(f"  趋势信号:  数据不足")

    # 自动预检结论
    lines.append(f"  " + "-" * 40)
    auto_items = 0
    if combo_count:
        auto_items += 1
    if emo_freq:
        auto_items += 1
    auto_items += 1  # 残留总是有信号
    if len(valid_trend) >= 2:
        auto_items += 1

    # C2 建议
    if "衰减失败" in trend_status:
        c2_suggest = "趋势确认卡住模式（负面不衰减）→ 若图式/情绪一致，建议 C2 在 7-10"
    elif "衰减中" in trend_status:
        c2_suggest = "趋势显示负面衰减中（处理进展）→ 若情绪/图式一致，建议 C2 在 5-8"
    elif "上升" in trend_status:
        c2_suggest = "负面强度上升中 → 需关注，建议 C2 在 5-8"
    elif "减弱" in trend_status:
        c2_suggest = "积极情绪减弱中 → 关注正向体验是否减少，建议 C2 在 4-7"
    elif "增强" in trend_status:
        c2_suggest = "积极情绪增强中 → 正向体验增加，建议 C2 在 5-8"
    else:
        c2_suggest = "建议 C2 在 5-8（结合残留关联人工确认）"

    # C3 建议
    if any(k in trend_status for k in ["衰减", "上升", "减弱", "增强"]):
        c3_suggest = f"C3 建议 7-10（趋势清晰：{trend_status}）"
    elif "稳定" in trend_status:
        c3_suggest = "C3 建议 5-7（无明显变化）"
    else:
        c3_suggest = "C3 按 R5 记 5"

    lines.append(f"  自动预检:  {auto_items}/4 可判定（残留关联需人工确认）")
    lines.append(f"  C2 建议:  {c2_suggest}")
    lines.append(f"  C3 建议:  {c3_suggest}")

    # --- 光谱打分 ---
    # 分析者赋值（命令行 > JSON analyst 段）
    C2 = cli_args.C2 if cli_args.C2 is not None else analyst.get("C2", 5)
    C3 = cli_args.C3 if cli_args.C3 is not None else analyst.get("C3", 5)
    C4 = cli_args.C4 if cli_args.C4 is not None else analyst.get("C4", 4)

    # 脚本自动计算
    C1 = score_C1(total)
    S1 = score_S1(combo_count)
    S2 = score_S2(freq, baseline)
    S3 = score_S3(emo_freq)

    lines.append("")
    lines.append("=" * 60)
    lines.append("\u5149\u8c31\u6253\u5206\uff08Step 2a \u53ef\u5ba2\u89c2\u91cf\u5316\u7ef4\u5ea6 \u00b7 1-10\uff09")
    lines.append("=" * 60)

    lines.append(f"  \u6570\u636e\u5145\u5206\u5ea6      {bar(C1)}  {C1:>4.1f}   (1-10)")
    lines.append(f"      \u2514 N={total} \u2192 \u811a\u672c\u81ea\u52a8")
    lines.append(f"  \u56fe\u5f0f\u95ed\u5408\u5ea6      {bar(S1)}  {S1:>4.1f}   (1-10)")
    max_combo = max(combo_count.values()) if combo_count else 0
    if S1 >= 9:
        lines.append(f"      \u2514 \u5b8c\u5168\u95ed\u5408\uff08\u6700\u5927\u7ec4\u5408\u91cd\u590d \u00d7{max_combo}\uff09\u2192 \u811a\u672c\u81ea\u52a8")
    elif S1 >= 5:
        lines.append(f"      \u2514 \u90e8\u5206\u95ed\u5408\uff08\u6700\u5927\u7ec4\u5408\u91cd\u590d \u00d7{max_combo}\uff09\u2192 \u811a\u672c\u81ea\u52a8")
    elif S1 >= 3:
        lines.append(f"      \u2514 \u5f31\u95ed\u5408\uff08\u6700\u5927\u7ec4\u5408\u91cd\u590d \u00d7{max_combo}\uff09\u2192 \u811a\u672c\u81ea\u52a8")
    else:
        lines.append(f"      \u2514 \u5355\u6b21\uff08\u6700\u5927\u7ec4\u5408\u91cd\u590d \u00d7{max_combo}\uff09\u2192 \u811a\u672c\u81ea\u52a8")
    lines.append(f"  \u57fa\u7ebf\u504f\u79bb\u5ea6      {bar(S2)}  {S2:>4.1f}   (1-10)")
    lines.append(f"      \u2514 \u5404\u56fe\u5f0f\u504f\u79bb\u4e2a\u4eba\u57fa\u7ebf\u7684\u6700\u5927\u500d\u6570\uff082\u00d7\u219210\uff09\u2192 \u811a\u672c\u81ea\u52a8")
    lines.append(f"  \u60c5\u611f\u4e3b\u5bfc\u5ea6      {bar(S3)}  {S3:>4.1f}   (1-10)")
    lines.append(f"      \u2514 \u6700\u5927\u5355\u4e00\u60c5\u611f\u5360\u6bd4 \u2192 \u811a\u672c\u81ea\u52a8\uff08\u7528\u4e8e\u98ce\u9669/\u57fa\u8c03\u6807\u8bb0\uff0c\u4e0d\u5165\u7efc\u5408\u516c\u5f0f\uff09")

    lines.append("")
    lines.append(f"  \u5206\u6790\u8005\u8d4b\u503c\uff1aC2\u8f93\u51fa\u6536\u655b\u5ea6={C2}  C3\u65f6\u95f4\u8d8b\u52bf={C3}  C4\u4f20\u8bb0\u5171\u632f={C4}")
    lines.append(f"      └ 趋势参考: {trend_status} (slope={trend_slope})")

    # --- 综合置信度指数 ---
    idx = composite_index(C1, S1, C2, S2, C4)
    marker, label, rule_notes = apply_rules(idx, S1, C2, C1, S2)

    lines.append("")
    lines.append("=" * 60)
    lines.append("\u7efc\u5408\u7f6e\u4fe1\u5ea6\u6307\u6570\uff08\u52a0\u6743\u542f\u53d1\u5f0f \u00b7 \u9700 C2/C4\uff09")
    lines.append("=" * 60)
    lines.append(f"  \u516c\u5f0f = 0.25\u00b7C1 + 0.25\u00b7S1 + 0.20\u00b7C2 + 0.15\u00b7S2 + 0.15\u00b7C4")
    lines.append(f"       = 0.25\u00b7{C1} + 0.25\u00b7{S1} + 0.20\u00b7{C2} + 0.15\u00b7{S2} + 0.15\u00b7{C4} = {idx}")
    lines.append(f"  {marker} [{idx}]  {label}   {rule_notes}")
    lines.append(f"  \uff08C3\u65f6\u95f4\u8d8b\u52bf={C3} \u4ec5\u7528\u4e8e\u60c5\u7eea\u76f8\u5173\u63a8\u65ad\u7684\u53d9\u4e8b\u5c42\uff0c\u4e0d\u5165\u7efc\u5408\u516c\u5f0f\uff1b\u82e5\u7f3a\u5931\u6309 R5 \u8bb0 5\uff09")

    return "\n".join(lines)


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Dream-IEA Step 2a: \u56fe\u5f0f\u5c42\u5ba2\u89c2\u7edf\u8ba1\u5f15\u64ce"
    )
    parser.add_argument("-i", "--input", required=True, help="\u8f93\u5165 JSON \u6587\u4ef6\u8def\u5f84")
    parser.add_argument("-o", "--output", help="\u8f93\u51fa\u6587\u4ef6\u8def\u5f84\uff08\u9ed8\u8ba4 stdout\uff09")
    parser.add_argument("--C2", type=float, help="\u5206\u6790\u8005\u8d4b\u503c\uff1a\u8f93\u51fa\u6536\u655b\u5ea6")
    parser.add_argument("--C3", type=float, help="\u5206\u6790\u8005\u8d4b\u503c\uff1a\u65f6\u95f4\u8d8b\u52bf")
    parser.add_argument("--C4", type=float, help="\u5206\u6790\u8005\u8d4b\u503c\uff1a\u4f20\u8bb0\u5171\u632f")

    args = parser.parse_args()

    data, diaries, baseline, analyst, baseline_source = load_data(args.input)
    validate_data(diaries)
    report = format_report(diaries, baseline, analyst, args, baseline_source)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\u62a5\u544a\u5df2\u4fdd\u5b58\u81f3 {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
