"""
AmazonLens - Review情感分析模块
硅基流动（SiliconFlow）版本

运行前准备：
1. pip install openai pandas
2. 把你的硅基流动 API Key 填入下方
3. python review_analyzer.py

API Key 获取：
- 打开 https://cloud.siliconflow.cn
- 注册登录 → 左侧菜单"API密钥" → 新建密钥
- 新用户有免费额度
"""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import json
import pandas as pd
from openai import OpenAI

# ============================================
# 配置区：只需要改这里
# ============================================

API_KEY   = "sk-ttvxjsfggmbesixuvibjyujixehvdmruprcanomvpahtvszg"
MODEL     = "Qwen/Qwen2.5-7B-Instruct"
OUTPUT    = "分析报告.md"
CSV_FILE  = "D:\Py code\AmazonLens\Reviews.csv"   # 你下载的文件名
MAX_ROWS  = 10              # 先跑20条，省额度，跑通再加大

# ============================================
# 核心函数：分析单条 Review
# ============================================

def analyze_one_review(client: OpenAI, review: dict) -> dict:
    prompt = f"""
你是一个亚马逊电商运营专家。分析以下买家评论，严格以JSON格式返回，不要有任何多余文字。

评论内容：{review['text']}
评分：{review['rating']}/5星

返回格式：
{{
  "sentiment": "正面/负面/中性",
  "pain_points": ["痛点1", "痛点2"],
  "highlights": ["优点1", "优点2"],
  "listing_suggestion": "Listing可以改进的一点建议",
  "priority": 重要程度1到5的整数
}}
"""

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=500,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    raw = response.choices[0].message.content
    if not raw:
        raise ValueError("API返回了空内容，请检查 API Key 是否正确")
    raw = raw.strip()

    # 兼容模型可能返回markdown代码块的情况
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # 尝试提取JSON片段
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError(f"无法解析返回内容：{raw}")
        result = json.loads(raw[start:end])

    result["asin"]          = review["asin"]
    result["product"]       = review["product"]
    result["rating"]        = review["rating"]
    result["original_text"] = review["text"]
    return result


# ============================================
# 报告生成：把结果汇总成可读的 Markdown
# ============================================

def generate_report(results: list) -> str:
    df = pd.DataFrame(results)
    lines = ["# 竞品 Review 分析报告\n"]

    for asin, group in df.groupby("asin"):
        product_name = group["product"].iloc[0]
        total        = len(group)
        negative     = len(group[group["sentiment"] == "负面"])
        avg_rating   = group["rating"].mean()

        lines.append(f"## {product_name}（{asin}）\n")
        lines.append(
            f"**评论数：** {total}条 ｜ "
            f"**平均评分：** {avg_rating:.1f}星 ｜ "
            f"**负面占比：** {negative/total*100:.0f}%\n"
        )

        # 汇总痛点
        all_pain = []
        for pts in group["pain_points"]:
            if isinstance(pts, list):
                all_pain.extend(pts)
        if all_pain:
            lines.append("**主要痛点：**")
            for pain, cnt in pd.Series(all_pain).value_counts().items():
                lines.append(f"- {pain}（{cnt}次）")
            lines.append("")

        # 汇总优点
        all_highlights = []
        for pts in group["highlights"]:
            if isinstance(pts, list):
                all_highlights.extend(pts)
        if all_highlights:
            lines.append("**主要优点：**")
            for h, cnt in pd.Series(all_highlights).value_counts().items():
                lines.append(f"- {h}（{cnt}次）")
            lines.append("")

        # 最高优先级的建议
        top = group.sort_values("priority", ascending=False).iloc[0]
        lines.append(f"**Listing优化建议：** {top['listing_suggestion']}\n")
        lines.append("---\n")

    return "\n".join(lines)


# ============================================
# 主程序
# ============================================

def main():
    print("=" * 50)
    print("AmazonLens Review分析器 启动")
    print(f"模型：{MODEL}")
    print("=" * 50)

    # 读取真实CSV数据
    df_raw = pd.read_csv(CSV_FILE)
    print(f"CSV共 {len(df_raw)} 条数据，取前 {MAX_ROWS} 条分析")

    # 把CSV列名映射到我们的格式
    # Kaggle这个数据集的列名是：Id, ProductId, UserId, Score, Summary, Text
    reviews = []
    for _, row in df_raw.head(MAX_ROWS).iterrows():
        reviews.append({
            "asin":    str(row["ProductId"]),
            "product": str(row.get("Summary", "未知产品"))[:30],  # 用Summary做产品名
            "rating":  int(row["Score"]),
            "text":    str(row["Text"])[:500]  # 截断超长评论，省token
        })

    client  = OpenAI(api_key=API_KEY, base_url="https://api.siliconflow.cn/v1")
    results = []
    total   = len(reviews)

    for i, review in enumerate(reviews, 1):
        print(f"正在分析第 {i}/{total} 条评论...", end=" ")
        result = analyze_one_review(client, review)
        results.append(result)
        print(f"完成 | 情感: {result['sentiment']}")

    print("\n生成报告中...\n")
    report = generate_report(results)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n报告已保存至：{OUTPUT}")


if __name__ == "__main__":
    main()
