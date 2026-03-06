"""
AmazonLens - 主程序
一条命令运行所有模块，汇总生成完整周报

运行方式：python -m main
"""

import os
import pandas as pd
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 导入三个模块
from review_analyzer import (
    API_KEY, MODEL, CSV_FILE as REVIEW_CSV,
    MAX_ROWS, analyze_one_review,
    generate_report as review_report,
    ai_summarize
)
from restock_analyzer import (
    CSV_FILE as RESTOCK_CSV, TOP_N,
    load_and_aggregate, calc_score_trend, calc_priority,
    generate_report as restock_report,
    ai_summarize as restock_summarize
)
from competitor_monitor import (
    load_data, calc_metrics, detect_anomalies,
    generate_report as competitor_report,
    ai_summarize as competitor_summarize
)

# ============================================
# 配置区
# ============================================

OUTPUT = f"AmazonLens周报_{datetime.now().strftime('%Y%m%d')}.md"


# ============================================
# 运行 Review 模块
# ============================================

def run_review_module() -> tuple:
    print("\n[1/3] 运行 Review 情感分析模块...")
    client  = OpenAI(api_key=API_KEY, base_url="https://api.siliconflow.cn/v1")
    df_raw  = pd.read_csv(REVIEW_CSV)
    reviews = []
    for _, row in df_raw.head(MAX_ROWS).iterrows():
        reviews.append({
            "asin":    str(row["ProductId"]),
            "product": str(row.get("Summary", "未知产品"))[:30],
            "rating":  int(row["Score"]),
            "text":    str(row["Text"])[:500]
        })

    results = []
    total   = len(reviews)
    for i, review in enumerate(reviews, 1):
        print(f"  分析第 {i}/{total} 条评论...", end=" ")
        result = analyze_one_review(client, review)
        results.append(result)
        print(f"{result['sentiment']}")

    report  = review_report(results)
    summary = ai_summarize(report)
    return summary, report


# ============================================
# 运行补货模块
# ============================================

def run_restock_module() -> tuple:
    print("\n[2/3] 运行补货决策模块...")
    df_raw, agg = load_and_aggregate(RESTOCK_CSV)
    result_df   = calc_score_trend(df_raw, agg)
    priority_df = calc_priority(result_df)
    report      = restock_report(priority_df)
    summary     = restock_summarize(report)
    return summary, report


# ============================================
# 运行竞品预警模块
# ============================================

def run_competitor_module() -> tuple:
    print("\n[3/3] 运行竞品异常预警模块...")
    competitors, reviews = load_data()
    metrics_df           = calc_metrics(competitors, reviews)
    alert_df             = detect_anomalies(metrics_df)
    report               = competitor_report(alert_df)
    summary              = competitor_summarize(report)
    return summary, report


# ============================================
# 汇总成完整周报
# ============================================

def generate_weekly_report(
    review_summary,   review_detail,
    restock_summary,  restock_detail,
    competitor_summary, competitor_detail
) -> str:
    date_str = datetime.now().strftime("%Y年%m月%d日")
    lines = []
    lines.append("# AmazonLens 运营周报")
    lines.append(f"**生成时间：** {date_str}\n")
    lines.append("---\n")

    # 总执行摘要
    lines.append("## 本周总结\n")
    lines.append("### 📊 Review 分析摘要")
    lines.append(review_summary)
    lines.append("")
    lines.append("### 📦 补货决策摘要")
    lines.append(restock_summary)
    lines.append("")
    lines.append("### 🔍 竞品预警摘要")
    lines.append(competitor_summary)
    lines.append("\n---\n")

    # 详细报告
    lines.append("## 📊 Review 情感分析详情\n")
    lines.append(review_detail)
    lines.append("\n---\n")

    lines.append("## 📦 补货决策详情\n")
    lines.append(restock_detail)
    lines.append("\n---\n")

    lines.append("## 🔍 竞品异常预警详情\n")
    lines.append(competitor_detail)

    return "\n".join(lines)


# ============================================
# 主程序
# ============================================

def main():
    print("=" * 50)
    print("AmazonLens 周报生成器 启动")
    print("=" * 50)

    review_summary,     review_detail     = run_review_module()
    restock_summary,    restock_detail    = run_restock_module()
    competitor_summary, competitor_detail = run_competitor_module()

    print("\n汇总生成周报...")
    report = generate_weekly_report(
        review_summary,     review_detail,
        restock_summary,    restock_detail,
        competitor_summary, competitor_detail
    )

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(report)

    print("\n" + "=" * 50)
    print("本周总结")
    print("=" * 50)
    print("\n【Review分析】")
    print(review_summary.encode("gbk", errors="ignore").decode("gbk"))
    print("\n【补货决策】")
    print(restock_summary.encode("gbk", errors="ignore").decode("gbk"))
    print("\n【竞品预警】")
    print(competitor_summary.encode("gbk", errors="ignore").decode("gbk"))
    print("=" * 50)
    print(f"\n完整周报已保存至：{OUTPUT}")


if __name__ == "__main__":
    main()
