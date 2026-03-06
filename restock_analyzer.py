import os
import pandas as pd

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ============================================
# 配置区
# ============================================

CSV_FILE   = r"Reviews.csv"
OUTPUT     = "补货决策报告.md"
TOP_N      = 50    # 分析销量前N名产品
RECENT_DAYS = 180  # 只看最近180天的评论趋势

# ============================================
# 第一步：读取数据，计算每个产品的基础指标
# ============================================

def load_and_aggregate(csv_file: str) -> tuple:
    print("读取数据中...")
    df = pd.read_csv(csv_file)
    # Time列是Unix时间戳，转成日期
    df["date"] = pd.to_datetime(df["Time"], unit="s")
    df["Score"] = pd.to_numeric(df["Score"], errors="coerce")

    # 按产品聚合：总评论数、平均评分
    agg = df.groupby("ProductId").agg(
        total_reviews  = ("Id", "count"),
        avg_score      = ("Score", "mean"),
        latest_review  = ("date", "max"),
        earliest_review= ("date", "min"),
    ).reset_index()

    return df, agg


# ============================================
# 第二步：计算评分趋势（早期评分 vs 近期评分）
# ============================================

def calc_score_trend(df: pd.DataFrame, agg: pd.DataFrame) -> pd.DataFrame:
    print("计算评分趋势...")

    cutoff = df["date"].max() - pd.Timedelta(days=RECENT_DAYS)

    # 直接用向量化分组，不用逐行循环
    recent_df   = df[df["date"] >= cutoff].groupby("ProductId").agg(
        recent_score   = ("Score", "mean"),
        recent_reviews = ("Id", "count")
    ).reset_index()

    historic_df = df[df["date"] < cutoff].groupby("ProductId").agg(
        historic_score = ("Score", "mean")
    ).reset_index()

    # 合并
    trend_df = recent_df.merge(historic_df, on="ProductId", how="left")
    trend_df["score_trend"] = (
        trend_df["recent_score"] - trend_df["historic_score"]
    ).round(2).fillna(0)

    return agg.merge(trend_df, on="ProductId", how="left").fillna(0)


# ============================================
# 第三步：生成补货优先级评分
# ============================================

def calc_priority(df: pd.DataFrame) -> pd.DataFrame:
    print("计算补货优先级...")

    # 取销量前N的产品
    top = df.nlargest(TOP_N, "total_reviews").copy()

    # 优先级评分逻辑：
    # - 近期评论多 → 热销，需要补货（+分）
    # - 近期评分下滑 → 产品出问题，需要关注（+预警分）
    # - 近期评分上升 → 健康，补货优先级正常

    max_recent = top["recent_reviews"].max() or 1

    top["demand_score"] = (top["recent_reviews"] / max_recent * 5).round(1)
    top["risk_score"]   = top["score_trend"].apply(
        lambda x: min(abs(x) * 2, 3) if x < 0 else 0
    ).round(1)
    top["priority_score"] = (top["demand_score"] + top["risk_score"]).round(1)

    # 补货建议
    def restock_action(row):
        if row["priority_score"] >= 6:
            return "🔴 紧急补货"
        elif row["priority_score"] >= 4:
            return "🟡 计划补货"
        elif row["risk_score"] >= 2:
            return "⚠️  关注质量问题，暂缓补货"
        else:
            return "🟢 正常库存"

    top["action"] = top.apply(restock_action, axis=1)
    return top.sort_values("priority_score", ascending=False)


# ============================================
# 第四步：生成报告
# ============================================

def generate_report(df: pd.DataFrame) -> str:
    lines = ["# 补货决策报告\n"]

    # 汇总统计
    urgent   = len(df[df["action"] == "🔴 紧急补货"])
    plan     = len(df[df["action"] == "🟡 计划补货"])
    warning  = len(df[df["action"].str.contains("关注")])
    normal   = len(df[df["action"] == "🟢 正常库存"])

    lines.append("## 总览\n")
    lines.append(f"- 🔴 紧急补货：{urgent} 个产品")
    lines.append(f"- 🟡 计划补货：{plan} 个产品")
    lines.append(f"- ⚠️  需关注质量：{warning} 个产品")
    lines.append(f"- 🟢 正常库存：{normal} 个产品")
    lines.append("")

    # 明细表
    lines.append("## 补货优先级明细\n")
    lines.append("| 产品ID | 总评论数 | 近期评论 | 平均评分 | 评分趋势 | 优先级分 | 建议 |")
    lines.append("|--------|---------|---------|---------|---------|---------|------|")

    for _, row in df.iterrows():
        trend_str = f"+{row['score_trend']}" if row['score_trend'] > 0 else str(row['score_trend'])
        lines.append(
            f"| {row['ProductId']} "
            f"| {int(row['total_reviews'])} "
            f"| {int(row['recent_reviews'])} "
            f"| {row['avg_score']:.1f}★ "
            f"| {trend_str} "
            f"| {row['priority_score']} "
            f"| {row['action']} |"
        )

    lines.append("")
    lines.append("## 说明\n")
    lines.append("- **优先级分** = 需求分（近期销量热度）+ 风险分（评分下滑幅度）")
    lines.append("- **评分趋势** = 近180天均分 − 历史均分，负数表示口碑下滑")
    lines.append("- **近期评论数** 作为销量热度的代理指标")

    return "\n".join(lines)


# ============================================
# 主程序
# ============================================

def main():
    print("=" * 50)
    print("AmazonLens 补货决策模块 启动")
    print("=" * 50)

    df_raw, agg  = load_and_aggregate(CSV_FILE)
    result_df    = calc_score_trend(df_raw, agg)
    priority_df  = calc_priority(result_df)
    report       = generate_report(priority_df)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n分析完成，报告已保存至：{OUTPUT}")
    print(f"共分析 {TOP_N} 个热销产品")
    print(f"紧急补货：{len(priority_df[priority_df['action'] == '🔴 紧急补货'])} 个")


if __name__ == "__main__":
    main()
