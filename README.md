# AmazonLens 🔍

AI驱动的跨境电商数据分析系统，自动生成运营周报，将人工分析时间从8小时压缩至40分钟。

---

## 项目背景

亚马逊运营每周需要处理大量数据决策：哪些产品需要补货？竞品有没有异常动态？差评集中在哪些痛点？传统方式依赖人工汇总Excel，耗时且主观。

AmazonLens 将这三个核心决策自动化，一条命令生成完整周报。

---

## 功能模块

### 📊 模块一：Review 情感分析
- 批量分析竞品买家评论，提取痛点和优点
- 自动生成 Listing 优化建议
- AI 汇总输出执行摘要

### 📦 模块二：补货决策模型
- 基于评论频率和评分趋势计算销量热度
- 动态生成补货优先级清单（紧急/计划/暂缓）
- AI 汇总输出补货行动建议

### 🔍 模块三：竞品异常预警
- 用 Z-score 统计检测评分异常下滑和评论量暴增
- 自动标记需要关注的竞品
- AI 汇总输出应对建议

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/xiran1984/amazonlens.git
cd amazonlens
```

### 2. 安装依赖

```bash
pip install openai pandas numpy python-dotenv kagglehub
```

### 3. 配置 API Key

复制 `.env.example` 为 `.env`，填入你的硅基流动 API Key：

```bash
cp .env.example .env
```

```
SILICONFLOW_API_KEY=你的APIKey
```

> 硅基流动 API Key 获取：[cloud.siliconflow.cn](https://cloud.siliconflow.cn)

### 4. 配置 Kaggle（用于自动下载数据集）

去 [kaggle.com](https://www.kaggle.com) → Account → Create New Token，下载 `kaggle.json` 放到：

```
Windows: C:\Users\你的用户名\.kaggle\kaggle.json
Mac/Linux: ~/.kaggle/kaggle.json
```

### 5. 准备竞品列表

编辑 `competitors.csv`，填入你要监控的竞品 ASIN：

```csv
ASIN,product_name,category
B001E4KFG0,产品名称,类目
```

### 6. 一键运行

```bash
python -m main
```

运行完成后生成 `AmazonLens周报_YYYYMMDD.md`，包含三个模块的完整分析报告。

---

## 项目结构

```
AmazonLens/
├── main.py                 # 一键运行入口
├── review_analyzer.py      # 模块一：Review 情感分析
├── restock_analyzer.py     # 模块二：补货决策模型
├── competitor_monitor.py   # 模块三：竞品异常预警
├── competitors.csv         # 竞品 ASIN 列表
├── .env.example            # 环境变量示例
└── .gitignore
```

---

## 技术栈

| 用途 | 技术 |
|------|------|
| 数据处理 | Python · pandas · numpy |
| AI 分析 | 硅基流动 API · Qwen2.5 |
| 统计检测 | Z-score 异常检测 |
| 数据集 | Kaggle Amazon Product Reviews |
| 自动化 | kagglehub · python-dotenv |

---

## 数据来源

本项目使用 [Amazon Product Reviews](https://www.kaggle.com/datasets/arhamrumi/amazon-product-reviews) 公开数据集，共 568,454 条评论记录。

---
