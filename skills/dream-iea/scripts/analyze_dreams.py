#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dream-IEA · Step 2a 图式层客观统计引擎

输入：标注好的梦境日记 JSON（格式见 assets/dream_diary_template.md）
输出：图式频率 / 共现 / 情感分布 / Gestalt 闭合 / 日间残留 / 光谱打分 / 综合置信度指数

本脚本只做客观统计，不引入任何心理理论（理论翻译在 Step 2b 由分析者完成）。
不内置任何测试数据，所有输入来自用户提供的标注 JSON。

用法：
    python3 analyze_dreams.py -i diary.json --C2 5 --C3 5 --C4 4 \
        --baseline '{"BLOCKAGE":0.2,"恐惧":0.2}' -o report.txt

analyst 段（C2/C3/C4）也可内嵌在 JSON 顶层，无需命令行参数。
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations

# 九类意象图式（含 CONTAINER 破裂作为独立标记）
SCHEMAS = [
    "CONTAINER", "CONTAINER破裂", "SOURCE-PATH-GOAL", "VERTICALITY",
    "BALANCE", "LINK", "CENTER-PERIPHERY", "FORCE", "BLOCKAGE",
]

# 六类情感元素（全谱，正负对称）
EMOTIONS = ["恐惧", "敬畏", "厌恶", "喜悦", "悲伤", "愤怒"]

# 默认个人基线（可被 --baseline 覆盖）；用于偏离检测
DEFAULT_BASELINE = {s: 0.1 for s in SCHEMAS}
DEFAULT_EMO_BASELINE = {e: 0.1 for e in EMOTIONS}


def load_diary(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 支持两种结构：{"entries": [...]} 或 直接是 list
    if isinstance(data, list):
        entries = data
        analyst = {}
    elif isinstance(data, dict):
        entries = data.get("entries", [])
        analyst = {k: v for k, v in data.items() if k != "entries"}
    else:
        raise ValueError("JSON 根必须是 list 或含 entries 字段的 object")
    return entries, analyst


def collect_schema_counts(entries):
    """返回 (per_entry_schemas, schema_freq_counter, cooc_counter, emotion_freq_counter, residual_count)"""
    per_entry = []
    schema_freq = Counter()
    cooc = Counter()
    emotion_freq = Counter()
    residual = 0

    for e in entries:
        schemas = e.get("schemas", [])
        emotions = e.get("emotions", [])
        if e.get("residual", False):
            residual += 1
        per_entry.append(schemas)
        for s in schemas:
            schema_freq[s] += 1
        for em in emotions:
            emotion_freq[em] += 1
        # 同篇内两两共现
        for a, b in combinations(sorted(set(schemas)), 2):
            cooc[f"{a} + {b}"] += 1

    return per_entry, schema_freq, cooc, emotion_freq, residual


def gestalt_closure(schema_freq, n_entries):
    """Gestalt 闭合检测：组合在 >=5 篇完全闭合，>=3 篇部分闭合"""
    closed = {}
    for combo, cnt in schema_freq.items():
        # schema_freq 这里是单图式计数；闭合检测针对组合需从共现算，此处用单图式近似
        pass
    # 实际闭合针对组合：用共现中重复 >=5 的作为完全闭合候选
    return closed


def analyze_cooccurrence_closure(cooc, n_entries):
    """从共现计数推算 Gestalt 闭合：完全闭合(>=5篇) / 部分闭合(>=3篇)"""
    full = {}
    partial = {}
    for combo, cnt in cooc.items():
        if cnt >= 5:
            full[combo] = cnt
        elif cnt >= 3:
            partial[combo] = cnt
    return full, partial


def spectrum(value, anchors):
    """通用 1-10 光谱映射：anchors = [(阈值, 分数), ...] 升序"""
    for threshold, score in sorted(anchors, key=lambda x: x[0]):
        if value <= threshold:
            return score
    return 10


def bar(score, width=10):
    filled = int(round(score / 10 * width))
    return "▓" * filled + "░" * (width - filled)


def main():
    ap = argparse.ArgumentParser(description="Dream-IEA Step 2a 统计引擎")
    ap.add_argument("-i", "--input", required=True, help="标注日记 JSON 路径")
    ap.add_argument("--C2", type=float, default=None, help="理论一致性 1-10（分析者赋）")
    ap.add_argument("--C3", type=float, default=None, help="时间趋势 1-10（分析者赋，仅情绪相关）")
    ap.add_argument("--C4", type=float, default=None, help="传记共振 1-10（分析者赋）")
    ap.add_argument("--baseline", type=str, default="{}",
                    help='个人基线 JSON，如 \'{"BLOCKAGE":0.2,"恐惧":0.2}\'')
    ap.add_argument("-o", "--output", type=str, default=None, help="输出文件路径（默认 stdout）")
    args = ap.parse_args()

    try:
        user_baseline = json.loads(args.baseline) if args.baseline else {}
    except json.JSONDecodeError:
        print("⚠ --baseline 不是合法 JSON，使用默认基线", file=sys.stderr)
        user_baseline = {}

    schema_baseline = {**DEFAULT_BASELINE, **{k: v for k, v in user_baseline.items() if k in SCHEMAS}}
    emo_baseline = {**DEFAULT_EMO_BASELINE, **{k: v for k, v in user_baseline.items() if k in EMOTIONS}}

    entries, analyst = load_diary(args.input)
    n = len(entries)
    if n == 0:
        print("⚠ 日记为空，无法分析", file=sys.stderr)
        return

    per_entry, schema_freq, cooc, emotion_freq, residual = collect_schema_counts(entries)
    full_close, partial_close = analyze_cooccurrence_closure(cooc, n)

    # 分析者赋值（命令行优先，否则取 JSON 内嵌）
    C2 = args.C2 if args.C2 is not None else analyst.get("C2", 5.0)
    C3 = args.C3 if args.C3 is not None else analyst.get("C3", 5.0)
    C4 = args.C4 if args.C4 is not None else analyst.get("C4", 4.0)

    # ---- 光谱打分 ----
    # C1 数据充分度：N=1→1, N=7→5, N=14+→10
    C1 = spectrum(n, [(1, 1), (7, 5), (14, 10)])
    # S1 图式闭合度：单次1, 部分闭合(>=3)5, 完全闭合(>=5)9
    max_cooc = max(cooc.values()) if cooc else 0
    if max_cooc >= 5:
        S1 = 9
    elif max_cooc >= 3:
        S1 = 5
    else:
        S1 = 1
    # S2 基线偏离度：持平1, 1.5×基线5, >=2×基线10
    max_dev = 1.0
    for s, cnt in schema_freq.items():
        base = schema_baseline.get(s, 0.1)
        if base > 0:
            dev = (cnt / n) / base
            max_dev = max(max_dev, dev)
    S2 = spectrum(max_dev, [(1.0, 1), (1.5, 5), (2.0, 10)])
    # S3 情感主导度：均布1, 单一占0.4为5, 占0.8+为10
    total_em = sum(emotion_freq.values())
    max_em_ratio = (max(emotion_freq.values()) / total_em) if total_em > 0 else 0
    S3 = spectrum(max_em_ratio, [(0.2, 1), (0.4, 5), (0.8, 10)])

    # 综合置信度指数
    composite = 0.25 * C1 + 0.25 * S1 + 0.20 * C2 + 0.15 * S2 + 0.15 * C4
    if composite >= 7.0:
        mark = "■"
    elif composite >= 4.0:
        mark = "●"
    else:
        mark = "▲"
    mark_label = {"■": "强信号", "●": "中信号", "▲": "弱信号"}[mark]

    # ---- 渲染报告 ----
    L = []
    L.append("=" * 60)
    L.append(f"图式频率（共 {n} 篇日记）")
    L.append("=" * 60)
    for s in SCHEMAS:
        cnt = schema_freq.get(s, 0)
        if cnt == 0:
            continue
        ratio = cnt / n
        note = ""
        base = schema_baseline.get(s, 0.1)
        if base > 0 and ratio > 1.5 * base:
            note = f"  ⚠ 偏离基线({base})"
        L.append(f"  {s:<18} {ratio:.3f}  ({cnt}/{n}){note}")

    L.append("")
    L.append("=" * 60)
    L.append("图式共现（同篇内两两）")
    L.append("=" * 60)
    for combo, cnt in sorted(cooc.items(), key=lambda x: -x[1]):
        L.append(f"  {combo:<28} {cnt}")

    L.append("")
    L.append("=" * 60)
    L.append("情感分布（全谱）")
    L.append("=" * 60)
    pos_total = sum(emotion_freq.get(e, 0) for e in ["喜悦", "敬畏"]) + emotion_freq.get("敬畏", 0)
    neg_total = sum(emotion_freq.get(e, 0) for e in ["恐惧", "悲伤", "厌恶", "愤怒"])
    for e in EMOTIONS:
        cnt = emotion_freq.get(e, 0)
        if total_em > 0:
            ratio = cnt / total_em
            L.append(f"  {'－' if e in ['恐惧','悲伤','厌恶','愤怒'] else '＋'}{e:<6} {ratio:.3f} {bar(ratio*10)}")
    L.append("")
    L.append(f"  正面情感合计 {pos_total/total_em if total_em else 0:.3f} ｜ 负面情感合计 {neg_total/total_em if total_em else 0:.3f}")
    if total_em > 0:
        dom = max(emotion_freq, key=emotion_freq.get)
        L.append(f"  主导情感：{dom} ({emotion_freq[dom]/total_em:.3f})")
        fear_ratio = emotion_freq.get("恐惧", 0) / total_em
        if fear_ratio > 0.4:
            L.append(f"  ⚠ 恐惧 占比 {fear_ratio:.3f} > 0.4 → 负面情感主导，需关注")
        dom_ratio = emotion_freq[dom] / total_em
        if dom_ratio > 0.8:
            L.append(f"  ⚠ {dom} 占比 {dom_ratio:.3f} 偏离个人基线 → 该情感激活异常")

    L.append("")
    L.append("=" * 60)
    L.append("Gestalt 闭合检测（部分闭合≥3，完全闭合≥5）")
    L.append("=" * 60)
    if full_close:
        for combo, cnt in full_close.items():
            L.append(f"  完全闭合  {{{combo}}} ×{cnt}")
    if partial_close:
        for combo, cnt in partial_close.items():
            L.append(f"  部分闭合  {{{combo}}} ×{cnt}")
    if not full_close and not partial_close:
        L.append("  无闭合组合（样本不足或图式分散）")

    L.append("")
    L.append("=" * 60)
    L.append("日间残留标记")
    L.append("=" * 60)
    L.append(f"  标注为日间残留：{residual} 篇")
    L.append(f"  深层图式模式候选：{n - residual} 篇")

    L.append("")
    L.append("=" * 60)
    L.append("光谱打分（Step 2a 可客观量化维度 · 1-10）")
    L.append("=" * 60)
    L.append(f"  数据充分度      {bar(C1)} {C1:>4.0f}   (1-10)  └ N={n} → 脚本自动")
    L.append(f"  图式闭合度      {bar(S1)} {S1:>4.0f}   (1-10)  └ 最大共现重复 ×{max_cooc} → 脚本自动")
    L.append(f"  基线偏离度      {bar(S2)} {S2:>4.0f}   (1-10)  └ 最大偏离 {max_dev:.1f}×基线 → 脚本自动")
    L.append(f"  情感主导度      {bar(S3)} {S3:>4.0f}   (1-10)  └ 最大单一情感占比 → 脚本自动（不入综合公式）")
    L.append(f"  分析者赋值：C2理论一致性={C2}  C3时间趋势={C3}  C4传记共振={C4}")

    L.append("")
    L.append("=" * 60)
    L.append("综合置信度指数（加权启发式 · 需 C2/C4）")
    L.append("=" * 60)
    L.append(f"  公式 = 0.25·C1 + 0.25·S1 + 0.20·C2 + 0.15·S2 + 0.15·C4")
    L.append(f"       = 0.25·{C1:.0f} + 0.25·{S1:.0f} + 0.20·{C2} + 0.15·{S2:.0f} + 0.15·{C4} = {composite:.1f}")
    L.append(f"  {mark} [{composite:.1f}]  {mark_label}   纯公式映射（规则覆盖由分析者按 R1-R7 判定）")
    L.append(f"  （C3时间趋势={C3} 仅用于情绪相关推断的叙事层，不入综合公式；若缺失按 R5 记 5）")

    out = "\n".join(L) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"✓ 报告已写入 {args.output}")
    else:
        print(out)


if __name__ == "__main__":
    main()
