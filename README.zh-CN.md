<p align="center">
  <a href="https://dzjxzyd.github.io/ai4fh-lab/">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="assets/ai4fh-white.svg">
      <source media="(prefers-color-scheme: light)" srcset="assets/ai4fh.svg">
      <img src="assets/ai4fh.svg" alt="AI4FH Lab — Artificial Intelligence for Food &amp; Health" width="240">
    </picture>
  </a>
</p>

<h1 align="center">PDF · Protein Database of Functionality</h1>

<p align="center">食品蛋白质功能特性数据库 · 从文献数值追溯样品与实验条件</p>

<p align="center"><a href="README.md">English</a> · <strong>简体中文</strong></p>

<p align="center">
  <a href="https://dzjxzyd.github.io/Protein-Database_Functionality/#/changelog"><img src="https://img.shields.io/badge/release-1.2-24634a" alt="Release 1.2"></a>
  <a href="LICENSE-DATA.md"><img src="https://img.shields.io/badge/data-CC_BY_4.0-25658a" alt="Data license: CC BY 4.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/code-MIT-5c6370" alt="Code license: MIT"></a>
</p>

<p align="center">
  <a href="https://dzjxzyd.github.io/Protein-Database_Functionality/">打开数据库</a> &nbsp;·&nbsp; <a href="https://dzjxzyd.github.io/Protein-Database_Functionality/#/search">检索</a> &nbsp;·&nbsp; <a href="https://dzjxzyd.github.io/Protein-Database_Functionality/#/download">下载</a> &nbsp;·&nbsp; <a href="llms.txt">AI 使用指南</a> &nbsp;·&nbsp; <a href="https://dzjxzyd.github.io/ai4fh-lab/">AI4FH Lab</a>
</p>

---

PDF 汇集了已发表文献中 **17 项食品蛋白质功能特性**的测量数据。每个数值都关联到具体样品、蛋白组成、复配物、处理条件与测试方法，便于在比较数值的同时理解其完整实验背景。

**直接在浏览器中使用：** 无需安装软件或注册账号，即可检索、比较与下载数据。

[数据概览](#数据概览) · [快速开始](#快速开始) · [主要功能](#主要功能) · [数据质量](#数据质量) · [数据下载](#数据下载) · [供 AI 助手使用](#供-ai-助手使用) · [开发与维护](#开发与维护) · [许可](#许可)

## 数据概览

**版本 1.2 · 数据快照：2026 年 11 月 12 日**

| 论文 | 期刊 | 蛋白质样品 | 性质数值 | 测试方法 |
|:---:|:---:|:---:|:---:|:---:|
| **49,978** | **149** | **390,530** | **1,929,357** | **133,542** |

> **使用数值前，请先检查数据来源。** 约 64% 的数值由模型从文献图中读取，属于估计值，并非作者直接报告的数值。每条数据保留来源信息；重要结果请通过 DOI 对照原始论文核实。

<details>
<summary><strong>查看 17 项功能特性</strong></summary>

溶解度、乳化性、起泡性、凝胶性、持水性、持油性、粒径、ζ-电位、PDI、巯基含量、二硫键含量、表面疏水性、浊度、水解度、游离氨基含量、包埋率/负载率、抗氧化活性。

</details>

<details>
<summary><strong>按出版商查看收录范围</strong></summary>


| 出版商 | 期刊 | 论文 | 样品 | 数值 |
|---|---:|---:|---:|---:|
| Elsevier | 54 | 32,135 | 250,753 | 1,268,981 |
| Wiley | 39 | 5,788 | 45,474 | 210,368 |
| Springer Nature | 26 | 3,782 | 29,972 | 138,602 |
| MDPI | 5 | 2,970 | 23,492 | 114,063 |
| ACS | 6 | 2,382 | 19,199 | 98,050 |
| Oxford University Press | 5 | 1,444 | 10,948 | 51,323 |
| Taylor & Francis | 12 | 1,210 | 9,070 | 40,123 |
| Royal Society of Chemistry | 3 | 267 | 1,622 | 7,847 |

</details>

## 快速开始

| 你的目标 | 建议入口 |
|---|---|
| 查找某种蛋白或处理方式的实验数值 | 打开[数据库检索](https://dzjxzyd.github.io/Protein-Database_Functionality/#/search)，按性质、样品、处理、测试方法或文献筛选。 |
| 了解数据库覆盖范围 | 按性质或蛋白来源[浏览](https://dzjxzyd.github.io/Protein-Database_Functionality/#/browse)，或查看[统计](https://dzjxzyd.github.io/Protein-Database_Functionality/#/stats)。 |
| 比较不同实验样品 | 跨检索添加样品到数据篮，一次并排比较 **2–6 个样品**。 |
| 分析单项性质 | 下载对应的**平铺 CSV 表**，每行一个数值，附样品与实验背景。 |
| 使用完整数据库 | 下载**八张关系表**，通过 `doi`、`sample_id` 和 `measurement_id` 关联。 |
| 交给 AI 助手或脚本分析 | 从 [`llms.txt`](llms.txt) 和[下载清单](data/download/manifest.json) 开始。 |

## 主要功能

| 检索与探索 | 比较与复用 |
|---|---|
| 输入提示、批量查询与 AND / OR / NOT 条件组合 | 浏览器内保存数据篮，并排比较实验样品 |
| 按性质、蛋白、处理条件、测试方法与论文筛选 | 导出 CSV、TSV、Excel、JSON；选择字段和长／宽表布局 |
| 处理参数范围、标准差与纯蛋白样品筛选 | 导出 RIS、BibTeX、纯文本参考文献，以及 PNG、SVG、CSV 图表 |
| 分类浏览、分布统计与性质级证据展示 | 可分享的检索网址、中英切换、深色模式与手机布局 |

<details>
<summary><strong>完整检索、导出与浏览功能</strong></summary>

- **检索**：一个检索框认蛋白来源、处理方式、性质、测试方法、期刊和 DOI，边输边提示；分页签筛选（性质与数值、蛋白、样品处理、测试方法、文献），每个选项带计数；处理温度、时间、pH、压力、功率、频率范围；只看有 SD 的数值、只看纯蛋白样品；批量检索（粘贴一列 DOI 或样品名）；高级查询（条件之间 AND / OR / NOT，可复制链接、保存）；结果按数值、样品或论文显示；没有结果时提示去掉哪个条件。
- **性质说明**：17 项性质分四类（功能特性、胶体与颗粒、结构与化学、递送与活性），每项写测什么、常见单位、库里最常用的测试方法和数值数；首页用可点的色环展示同样的分类。
- **浏览、统计、性质分布页**：按性质、蛋白来源、处理类型、测试方法、期刊浏览；全库分布图；某性质 × 某蛋白 × 某处理的数值按论文分列画图，附方法概述、处理条件和数值表。
- **下载**：完整数据库按表分别下载，或按 17 项性质下载平铺表（一行一个数值，Excel 直接打开），附行数和大小；检索结果导出 CSV / TSV / Excel / JSON（全部结果、当前页或勾选的行，长表或宽表，可自选列）；文献列表导出 RIS / BibTeX / 纯文本；每张图可下载 PNG / SVG / 数据 CSV。
- **数据篮**：跨多次检索收集样品（存在浏览器里），对比 2–6 个样品，或一起导出。
- 中英双语、深色模式、手机可用；筛选条件写进网址，可以收藏和分享。

</details>

## 数据质量

- **来源于模型**：约 64% 的数值是由模型从论文图中读取的估计值（`data_origin` 含 `model-derived`，网站上标「模型」）。其余是作者在表格或正文中给出的原值（`data_origin` 含 `author-reported`）。
- **样品处理和测试方法是两回事**：样品处理是样品在测定前经过的制备和改性（超声、加热、酶解…），见 `treatments`；测试方法是这项性质怎么测的，见 `methods` 和数值的 `test_method`。约 98% 的数值对应到了具体测试方法，其余标「原文未写明」或「不确定」（一项性质用了几种方法、分不清某个数用的哪种）。
- **显著性字母**（`significance`，如 a、b、ab）照抄原文：只在同一篇论文、同一张表或图里的样品之间比较，字母相同表示差异不显著；不同论文之间不可比。
- 样品组成、处理条件、测试方法和数值的对应关系由自动流程完成（大模型解读 + 程序核对）。使用前请通过 DOI 对照原文核对。
- 本库只包含数值、样品组成、处理条件和测试方法，不包含论文原文句子。论文版权归原作者和出版商所有；使用数据请引用对应的原始论文。

## 数据下载

全部是 UTF-8 CSV（Excel 可直接打开），每个压缩包里都附本说明和数据许可；全部文件及行数、大小列在 [`data/download/manifest.json`](data/download/manifest.json)。

- **关系表**：`data/download/<表名>.csv.zip`，即下表前八张，各表用 `doi`、`sample_id`、`measurement_id` 互相关联。
- **平铺表**：`data/download/flat_<性质>.csv.zip`，按 17 项性质各一个文件（如 `flat_solubility.csv.zip`），一行一个数值，样品、配料、处理、测试方法和论文信息都在同一行。整张平铺表太大（约 2 GB），不单独提供。

**按用途选择格式：** 单项性质分析优先使用平铺表；需要完整数据库结构时使用关系表。

<details>
<summary><strong>表结构与主要字段</strong></summary>

| 文件 | 每行代表 | 主要字段 |
|---|---|---|
| `papers.csv` | 一篇论文 | `doi`, `title`, `journal` |
| `samples.csv` | 一个样品 | `sample_id` (`doi#N`), `sample_name`, `protein_source`, `protein_source_std`, `protein_category`, `protein_form`, `protein_form_std`, `protein_conc`, `ingredients_summary`, `treatment_summary`, `treatment_types`, `system` |
| `ingredients.csv` | 一种复配物 | `sample_id`, `name`, `category`, `amount` |
| `treatments.csv` | 一个样品处理步骤 | `sample_id`, `step_no`, `treatment_method`, `category`, `treatment_type`, `params`, `temperature_c`, `time_min`, `ph`, `pressure_mpa`, `power_w`, `frequency_khz` |
| `treatment_params.csv` | 一个处理参数 | `sample_id`, `step_no`, `name`, `value`, `unit` |
| `measurements.csv` | 一个数值 | `measurement_id`, `sample_id`, `property`, `measure_name`, `value`, `sd`, `unit`, `significance`, `value_std`, `unit_std`, `conditions_all`, `test_method`, `test_method_en`, `method_params`, `method_status`, `source_type`, `data_origin`, `source_item` |
| `measurement_conditions.csv` | 一个测定条件 | `measurement_id`, `name`, `value`, `unit` |
| `methods.csv` | 一种测试方法 | `doi`, `method_id`, `property`, `test_method`, `test_method_en`, `method_raw`, `reference`, `instrument`, `method_params`, `method_summary`, `applies_to` |
| `flat_<property>.csv` | 某项性质的一个数值，含样品与论文信息 | 上述相关字段 |

</details>

<details>
<summary><strong>字段约定、单位与关联标识</strong></summary>

- `value` 是纯数字；原文不是单个数（如「<0.1」）时留空，原样在 `value_text`。
- 读图数值有纵轴倍率（`multiplier`，如 10^3）时，`value` 是刻度读数，没有乘倍率。
- `value_std` / `unit_std`：按性质换成标准单位（粒径 nm、ζ-电位 mV、溶解度 % 或 mg/mL、乳化活性 m²/g、乳化稳定性 min 或 %、凝胶强度 Pa 或 N、持水持油 g/g 或 mL/g、巯基二硫键 µmol/g…），单位写法认不出或基准不同的留空；处理温度 °C、时间 min、压力 MPa、功率 W、频率 kHz。
- 规范化的列（程序按规则从原文列推出，原文列照留）：`protein_source_std`（蛋白来源标准名称，如 Soybean、Milk (bovine)）、`protein_form_std`（Isolate、Hydrolysate…）、`treatment_types` / `treatment_type`（Heating、Ultrasound、Enzymatic hydrolysis…）、`test_method_en`（测试方法英文名）、`method_summary`（英文方法概述，可照着复现）。一格里有多个值时用 ` | ` 隔开。
- 一个数值的 `method_id`（如 M2）指向 `methods.csv` 里同一 `doi` 的那一行。
- 其余类别值是中文（网站上可切换英文）。

</details>

## 供 AI 助手使用

网站依赖 JavaScript 渲染。AI 助手和脚本应从 [`llms.txt`](llms.txt) 与 [`data/download/manifest.json`](data/download/manifest.json) 开始：前者说明文件选择、字段含义及 Python 读取示例，后者列出下载地址、行数、文件大小与 SHA-256。无需注册或 API key。

可以将以下说明直接交给 AI 助手：

```text
请使用 PDF 蛋白质功能特性数据库：
https://dzjxzyd.github.io/Protein-Database_Functionality/
先阅读：
https://dzjxzyd.github.io/Protein-Database_Functionality/llms.txt
再按以下清单下载所需数据：
https://dzjxzyd.github.io/Protein-Database_Functionality/data/download/manifest.json
data_origin 含 model-derived 的数值是模型从图中读取的估计值。
报告每个数值时请给出对应论文的 DOI。
```

## 开发与维护

### 本地预览

```bash
git clone https://github.com/dzjxzyd/Protein-Database_Functionality.git
cd Protein-Database_Functionality
python scripts/serve.py
```

打开 [localhost:8765](http://localhost:8765)。若端口已被占用，运行 `python scripts/serve.py --port 8766`。

仓库包含已发布的数据文件，首次下载可能需要较长时间。网站为纯静态页面，数据按需加载，检索、绘图与导出均在浏览器内完成。

<details>
<summary><strong>网站结构与数据更新流程</strong></summary>

数据库由项目提取流程生成。`scripts/build_site_data.py` 将数据库转换为网站数据：去掉论文原文句子，将读图数值标为 `model-derived`。发布新版时，在脚本的 `RELEASES` 中添加版本号、日期和中英文更新说明；首页、更新日志和下载页会同步显示。

```bash
python scripts/build_site_data.py --db <database-folder>
```

检查生成内容后，再提交并推送更新。

网站由 `index.html` 和 `assets/` 构成：`i18n.js` 管理文案，`core.js` 管理数据与筛选，`search.js` 提供检索页，`pages.js` 提供其他页面，`main.js` 管理路由，`charts.js` 提供图表，`xlsx.js` 支持 Excel 导出。打开网站时加载 `data/index.*`，后续按需读取 `data/chunk/`。

后续重新生成的下载压缩包会附带中英文 README、logo 资源和数据许可。

</details>

## 许可

- 数据（`data/`）：[CC BY 4.0](LICENSE-DATA.md)——可以使用和再发布，须注明出处，并引用对应的原始论文。
- 代码（网站和脚本）：[MIT](LICENSE)。

由都柏林大学 [AI4FH 实验室](https://dzjxzyd.github.io/ai4fh-lab/)（Artificial Intelligence for Food & Health）开发。

<p align="center"><a href="README.md">Read in English →</a></p>
