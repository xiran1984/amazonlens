"""
AmazonLens - 竞品异常预警模块
基于Z-score统计检测竞品评分和评论量异常

运行方式：python -m competitor_monitor
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ============================================
# 配置区
# ============================================

import kagglehub
def get_csv_path() -> str:
    print("检查数据集...")
    path = kagglehub.dataset_download("arhamrumi/amazon-product-reviews")
    csv_path = os.path.join(path, "Reviews.csv")
    return csv_path

CSV_FILE        = get_csv_path()
COMPETITOR_FILE = "competitors.csv"
OUTPUT          = "竞品预警报告.md"
RECENT_DAYS     = 180       # 近期窗口
ZSCORE_THRESHOLD = 1.5      # 超过1.5个标准差触发预警
API_KEY         = os.getenv("SILICONFLOW_API_KEY")
MODEL           = "Qwen/Qwen2.5-7B-Instruct"

# ============================================
# 第一步：读取竞品列表和评论数据
# ============================================

def load_data() -> tuple:
    print("读取竞品列表...")
    competitors = pd.read_csv(COMPETITOR_FILE)
    print(f"竞品数量：{len(competitors)} 个")

    print("读取评论数据...")
    reviews = pd.read_csv(CSV_FILE)
    reviews["date"]  = pd.to_datetime(reviews["Time"], unit="s")
    reviews["Score"] = pd.to_numeric(reviews["Score"], errors="coerce")

    # 只保留竞品列表里的ASIN
    asin_list        = competitors["ASIN"].tolist()
    filtered_reviews = reviews[reviews["ProductId"].isin(asin_list)].copy()
    print(f"匹配到 {filtered_reviews['ProductId'].nunique()} 个竞品的评论数据")

    return competitors, filtered_reviews


# ============================================
# 第二步：按时间窗口切分数据，计算基础指标
# ============================================

def calc_metrics(competitors: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    print("计算竞品指标...")

    cutoff    = reviews["date"].max() - pd.Timedelta(days=RECENT_DAYS)
    recent    = reviews[reviews["date"] >= cutoff]
    historic  = reviews[reviews["date"] <  cutoff]

    # 近期指标
    recent_agg = recent.groupby("ProductId").agg(
        recent_reviews = ("Id",    "count"),
        recent_score   = ("Score", "mean"),
    ).reset_index()

    # 历史指标
    historic_agg = historic.groupby("ProductId").agg(
        historic_reviews = ("Id",    "count"),
        historic_score   = ("Score", "mean"),
    ).reset_index()

    # 合并
    df = competitors.merge(
        recent_agg,   left_on="ASIN", right_on="ProductId", how="left"
    ).merge(
        historic_agg, left_on="ASIN", right_on="ProductId", how="left"
    ).fillna(0)

    # 评分变化
    df["score_change"] = (df["recent_score"] - df["historic_score"]).round(2)

    # 评论量变化率（近期 vs 历史，按天归一化）
    df["review_growth"] = (
        (df["recent_reviews"] - df["historic_reviews"])
        / (df["historic_reviews"] + 1)  # +1 防止除以0
    ).round(2)

    return df


# ============================================
# 第三步：Z-score异常检测
# ============================================

def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    print("检测异常...")

    def zscore(series: pd.Series) -> pd.Series:
        std = series.std()
        if std == 0:
            return pd.Series([0] * len(series), index=series.index)
        return (series - series.mean()) / std

    df["score_zscore"]  = zscore(df["score_change"]).round(2)
    df["review_zscore"] = zscore(df["review_growth"]).round(2)

    # 判断异常类型
    def classify_alert(row) -> str:
        alerts = []
        if row["score_zscore"] < -ZSCORE_THRESHOLD:
            alerts.append("🔴 评分异常下滑")
        if row["score_zscore"] > ZSCORE_THRESHOLD:
            alerts.append("🟢 评分异常上升")
        if row["review_zscore"] > ZSCORE_THRESHOLD:
            alerts.append("🟡 评论量异常暴增")
        if row["review_zscore"] < -ZSCORE_THRESHOLD:
            alerts.append("⚪ 评论量异常萎缩")
        return "、".join(alerts) if alerts else "✅ 正常"

    df["alert"] = df.apply(classify_alert, axis=1)
    df["has_alert"] = df["alert"] != "✅ 正常"

    return df


# ============================================
# 第四步：AI生成预警摘要
# ============================================

def ai_summarize(report: str) -> str:
    if not API_KEY:
        return "未配置API Key，跳过AI摘要"

    client = OpenAI(api_key=API_KEY, base_url="https://api.siliconflow.cn/v1")
    response = client.chat.completions.create(
        model      = MODEL,
        max_tokens = 300,
        messages   = [{
            "role": "user",
            "content": f"""
你是一个亚马逊运营专家。请把以下竞品预警报告压缩成3-5句话的执行摘要。
要求：
- 直接说最需要关注的竞品和原因
- 包含具体数字
- 最后一句给出本周最优先的一个应对建议

报告内容：
{report[:3000]}
"""
        }]
    )
    content = response.choices[0].message.content
    return content.strip() if content is not None else ""

# ============================================
# 第五步：生成报告
# ============================================

def generate_report(df: pd.DataFrame) -> str:
    date_str   = datetime.now().strftime("%Y年%m月%d日")
    alert_df   = df[df["has_alert"]]
    normal_df  = df[~df["has_alert"]]

    lines = []
    lines.append("# 竞品异常预警报告\n")
    lines.append(f"**生成时间：** {date_str}\n")
    lines.append(f"**监控竞品：** {len(df)} 个 ｜ "
                 f"**触发预警：** {len(alert_df)} 个 ｜ "
                 f"**状态正常：** {len(normal_df)} 个\n")
    lines.append("---\n")

    # 预警产品
    if len(alert_df) > 0:
        lines.append("## 触发预警的竞品\n")
        lines.append("| 产品名称 | ASIN | 近期评分 | 评分变化 | 近期评论数 | 评论增长率 | 预警类型 |")
        lines.append("|---------|------|---------|---------|----------|----------|---------|")
        for _, row in alert_df.iterrows():
            score_change = f"+{row['score_change']}" if row['score_change'] > 0 else str(row['score_change'])
            review_growth = f"+{row['review_growth']:.0%}" if row['review_growth'] > 0 else f"{row['review_growth']:.0%}"
            lines.append(
                f"| {row['product_name']} "
                f"| {row['ASIN']} "
                f"| {row['recent_score']:.1f}★ "
                f"| {score_change} "
                f"| {int(row['recent_reviews'])} "
                f"| {review_growth} "
                f"| {row['alert']} |"
            )
        lines.append("")
    else:
        lines.append("## 本周无异常预警 ✅\n")

    # 正常产品
    lines.append("## 状态正常的竞品\n")
    lines.append("| 产品名称 | ASIN | 近期评分 | 评分变化 | 近期评论数 |")
    lines.append("|---------|------|---------|---------|----------|")
    for _, row in normal_df.iterrows():
        score_change = f"+{row['score_change']}" if row['score_change'] > 0 else str(row['score_change'])
        lines.append(
            f"| {row['product_name']} "
            f"| {row['ASIN']} "
            f"| {row['recent_score']:.1f}★ "
            f"| {score_change} "
            f"| {int(row['recent_reviews'])} |"
        )
    lines.append("")
    lines.append("---\n")
    lines.append("## 说明\n")
    lines.append(f"- 预警阈值：Z-score > {ZSCORE_THRESHOLD}（偏离均值{ZSCORE_THRESHOLD}个标准差）")
    lines.append(f"- 近期窗口：最近 {RECENT_DAYS} 天")
    lines.append("- 评论增长率 = （近期评论数 - 历史评论数）/ 历史评论数")

    return "\n".join(lines)


# ============================================
# 主程序
# ============================================

def main():
    print("=" * 50)
    print("AmazonLens 竞品异常预警模块 启动")
    print("=" * 50)

    competitors, reviews = load_data()
    metrics_df           = calc_metrics(competitors, reviews)
    alert_df             = detect_anomalies(metrics_df)
    report               = generate_report(alert_df)

    print("\n生成AI摘要...")
    summary = ai_summarize(report)
    report_with_summary = f"## 执行摘要\n\n{summary}\n\n---\n\n{report}"

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(report_with_summary)

    print("\n===== 执行摘要 =====")
    print(summary.encode("gbk", errors="ignore").decode("gbk"))
    print(f"\n报告已保存至：{OUTPUT}")
    print(f"触发预警：{alert_df['has_alert'].sum()} 个竞品")


if __name__ == "__main__":
    main()


