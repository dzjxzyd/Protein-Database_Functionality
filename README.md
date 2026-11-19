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

<p align="center">Food protein functionality, connected to its experimental context.</p>

<p align="center"><strong>English</strong> · <a href="README.zh-CN.md">简体中文</a></p>

<p align="center">
  <a href="https://dzjxzyd.github.io/Protein-Database_Functionality/#/changelog"><img src="https://img.shields.io/badge/release-1.2-24634a" alt="Release 1.2"></a>
  <a href="LICENSE-DATA.md"><img src="https://img.shields.io/badge/data-CC_BY_4.0-25658a" alt="Data license: CC BY 4.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/code-MIT-5c6370" alt="Code license: MIT"></a>
</p>

<p align="center">
  <a href="https://dzjxzyd.github.io/Protein-Database_Functionality/">Explore the database</a> &nbsp;·&nbsp; <a href="https://dzjxzyd.github.io/Protein-Database_Functionality/#/search">Search</a> &nbsp;·&nbsp; <a href="https://dzjxzyd.github.io/Protein-Database_Functionality/#/download">Download</a> &nbsp;·&nbsp; <a href="llms.txt">AI guide</a> &nbsp;·&nbsp; <a href="https://dzjxzyd.github.io/ai4fh-lab/">AI4FH Lab</a>
</p>

---

PDF brings together literature-derived measurements of **17 food protein functional properties**. Each value is linked to its protein sample, composition, added ingredients, processing history and measurement method—so you can compare the experimental context as well as the number.

**Start in your browser:** search, compare and download data without installing software or creating an account.

[Overview](#overview) · [Get started](#get-started) · [Features](#features) · [Data quality](#data-quality) · [Downloads](#downloads) · [For AI agents](#for-ai-agents) · [Development](#development) · [License](#license)

## Overview

**Release 1.2 · Data snapshot: 12 November 2026**

| Papers | Journals | Protein samples | Property values | Test methods |
|:---:|:---:|:---:|:---:|:---:|
| **49,978** | **149** | **390,530** | **1,929,357** | **133,542** |

> **Read the provenance before using a value.** About 64% of values are model estimates read from figures, rather than author-reported numbers. Each value retains its source information; verify important results against the original article using its DOI.

<details>
<summary><strong>Explore the 17 properties</strong></summary>

solubility, emulsifying properties, foaming properties, gelling properties, water-holding capacity, oil-holding capacity, particle size, ζ-potential, PDI, sulfhydryl content, disulfide bond content, surface hydrophobicity, turbidity, degree of hydrolysis, free amino groups, encapsulation/loading efficiency, antioxidant activity.

</details>

<details>
<summary><strong>Coverage by publisher</strong></summary>


| Publisher | Journals | Papers | Samples | Values |
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

## Get started

| Your goal | Where to start |
|---|---|
| Find values for a protein or treatment | [Search the database](https://dzjxzyd.github.io/Protein-Database_Functionality/#/search), then refine by property, sample, treatment, test method or literature. |
| Explore the coverage | [Browse](https://dzjxzyd.github.io/Protein-Database_Functionality/#/browse) by property or protein source, or open [Statistics](https://dzjxzyd.github.io/Protein-Database_Functionality/#/stats). |
| Compare experimental samples | Add samples to the basket across searches, then compare **2–6 samples**. |
| Analyse one property | Download its **flat CSV table**: one row per value, including sample and experimental context. |
| Work with the complete database | Download the **eight relational tables** and join them by `doi`, `sample_id` and `measurement_id`. |
| Use an AI assistant or script | Start with [`llms.txt`](llms.txt) and the [download manifest](data/download/manifest.json). |

## Features

| Search & explore | Compare & reuse |
|---|---|
| Search suggestions, batch queries and AND / OR / NOT conditions | A persistent browser basket and side-by-side sample comparison |
| Filters for properties, proteins, processing, methods and papers | CSV, TSV, Excel and JSON result exports; selectable columns and layouts |
| Treatment ranges, standard-deviation filters and pure-protein filters | RIS, BibTeX and plain-text references; PNG, SVG and CSV chart exports |
| Browse pages, distribution charts and property-level evidence | Shareable search URLs, English / Chinese, dark mode and mobile layouts |

<details>
<summary><strong>Detailed search, export and browsing capabilities</strong></summary>

- **Search:** one search box with suggestions for protein sources, treatments, properties, test methods, journals and DOIs; tabbed filters (property and value, protein, sample treatment, test method, literature) with a count next to every option; ranges for treatment temperature, time, pH, pressure, power and frequency; filters for values with an SD and for pure-protein samples; batch search (paste a list of DOIs or sample names); a query builder (AND / OR / NOT between conditions, with a link you can copy and save); results per value, per sample or per paper; suggestions for which filter to drop when nothing matches.
- **Property guide:** the 17 properties in four groups (techno-functional, colloidal, structure & chemistry, delivery & bioactivity), each with what it measures, common units, the test methods used most in the database and the number of values; the home page shows the same groups as a clickable ring.
- **Browse, statistics and property pages:** browse by property, protein source, treatment type, test method or journal; distribution charts for the whole database; for a property × protein × treatment, the values plotted paper by paper, with method summaries, treatment conditions and a table of values.
- **Download:** the complete database table by table, or one flat table per property (one row per value, opens directly in Excel), with row counts and file sizes; search results export to CSV / TSV / Excel / JSON (all results, the current page or selected rows; long or wide layout; columns of your choice); reference lists export to RIS / BibTeX / plain text; every chart downloads as PNG / SVG / data CSV.
- **Basket:** collect samples across searches (kept in your browser), compare 2–6 samples, or export them together.
- Chinese / English, dark mode and a mobile layout; filters are kept in the URL, so a search can be bookmarked and shared.

</details>

## Data quality

- **Model-derived values:** about 64% of the values were read from figures by a model and are estimates (`data_origin` contains `model-derived`; marked "Model" on the website). The rest are author-reported values from tables or the main text (`data_origin` contains `author-reported`).
- **Sample treatment is not the test method:** the sample treatment (sonication, heating, hydrolysis …; in `treatments`) is the processing a sample received before measurement; the test method (`methods`, `test_method`) is how the property was measured. About 98% of values are linked to a specific test method; the rest are marked "not stated" or "uncertain" (several methods were used for one property and it is unclear which one gave a value).
- **Significance letters** (`significance`, e.g. a, b, ab) are copied from the article. They compare samples only within the same table or figure of the same paper — values sharing a letter are not significantly different — and cannot be compared across papers.
- Samples, conditions and test methods were matched to values by an automated pipeline (LLM interpretation plus programmatic checks). Please check against the original article (DOI) before use.
- Only numerical values, sample composition, processing conditions and test methods are included — no text from the articles. Copyright of the articles remains with their authors and publishers; please cite the original articles.

## Downloads

All files are UTF-8 CSV (open directly in Excel); each archive also contains this README and the data licence. Every file, with its row count and size, is listed in [`data/download/manifest.json`](data/download/manifest.json).

- **Relational tables:** `data/download/<table>.csv.zip`, the first eight tables below, one archive each, linked by `doi`, `sample_id` and `measurement_id`.
- **Flat tables:** `data/download/flat_<property>.csv.zip`, one archive per property (e.g. `flat_solubility.csv.zip`), one row per value with all sample, ingredient, treatment, method and paper fields. The full flat table (about 2 GB) is not provided as a single file.

**Choose the format for your workflow:** flat tables are convenient for a single property; relational tables preserve the full database structure.

<details>
<summary><strong>Table schema and key columns</strong></summary>

| File | One row per | Key columns |
|---|---|---|
| `papers.csv` | paper | `doi`, `title`, `journal` |
| `samples.csv` | sample | `sample_id` (`doi#N`), `sample_name`, `protein_source`, `protein_source_std`, `protein_category`, `protein_form`, `protein_form_std`, `protein_conc`, `ingredients_summary`, `treatment_summary`, `treatment_types`, `system` |
| `ingredients.csv` | ingredient | `sample_id`, `name`, `category`, `amount` |
| `treatments.csv` | sample treatment step | `sample_id`, `step_no`, `treatment_method`, `category`, `treatment_type`, `params`, `temperature_c`, `time_min`, `ph`, `pressure_mpa`, `power_w`, `frequency_khz` |
| `treatment_params.csv` | treatment parameter | `sample_id`, `step_no`, `name`, `value`, `unit` |
| `measurements.csv` | value | `measurement_id`, `sample_id`, `property`, `measure_name`, `value`, `sd`, `unit`, `significance`, `value_std`, `unit_std`, `conditions_all`, `test_method`, `test_method_en`, `method_params`, `method_status`, `source_type`, `data_origin`, `source_item` |
| `measurement_conditions.csv` | measurement condition | `measurement_id`, `name`, `value`, `unit` |
| `methods.csv` | test method | `doi`, `method_id`, `property`, `test_method`, `test_method_en`, `method_raw`, `reference`, `instrument`, `method_params`, `method_summary`, `applies_to` |
| `flat_<property>.csv` | value of one property, with all sample and paper information | all of the above |

</details>

<details>
<summary><strong>Field conventions, units and identifiers</strong></summary>

- `value` is numeric; entries that are not a single number (e.g. "<0.1") are kept in `value_text`.
- For figure values with an axis multiplier (`multiplier`, e.g. 10^3), `value` is the axis reading and has not been multiplied.
- `value_std` / `unit_std`: values converted to a standard unit per property (particle size nm, ζ-potential mV, solubility % or mg/mL, emulsifying activity m²/g, emulsion stability min or %, gel strength Pa or N, water/oil holding g/g or mL/g, sulfhydryl/disulfide µmol/g …); left empty where the unit could not be recognised or the basis differs. Treatment temperature °C, time min, pressure MPa, power W, frequency kHz.
- Normalised columns, derived by rules from the original columns (which are kept): `protein_source_std` (standard protein source, e.g. Soybean, Milk (bovine)), `protein_form_std` (Isolate, Hydrolysate …), `treatment_types` / `treatment_type` (Heating, Ultrasound, Enzymatic hydrolysis …), `test_method_en` (English test-method name) and `method_summary` (English method summary for reproducing the test). Several values in one cell are separated by ` | `.
- A value's `method_id` (e.g. M2) points to the row with the same `doi` in `methods.csv`.
- Other category values are in Chinese (the website shows English translations).

</details>

## For AI agents

The website needs JavaScript, so an AI agent fetching it sees no content. Agents should start from [`llms.txt`](llms.txt) (plain-text instructions: which file to use, how to read the columns, a Python example) and [`data/download/manifest.json`](data/download/manifest.json) (every download file with its URL, row count, size and SHA-256). No sign-up or API key is needed. To hand the database to your AI, send it:

```
Use the PDF protein functionality database at https://dzjxzyd.github.io/Protein-Database_Functionality/ . Read https://dzjxzyd.github.io/Protein-Database_Functionality/llms.txt first, then download the files listed in https://dzjxzyd.github.io/Protein-Database_Functionality/data/download/manifest.json . Values whose data_origin contains "model-derived" are estimates read from figures. Give the DOI for every number you report.
```

## Development

### Preview locally

```bash
git clone https://github.com/dzjxzyd/Protein-Database_Functionality.git
cd Protein-Database_Functionality
python scripts/serve.py
```

Open [localhost:8765](http://localhost:8765). If that port is occupied, use `python scripts/serve.py --port 8766`.

The repository includes the published data files and can take time to download. The website is static: data are loaded on demand and searched, plotted and exported in the browser.

<details>
<summary><strong>Website structure and data-release workflow</strong></summary>

The database is produced by the project's extraction pipeline; `scripts/build_site_data.py` turns it into the website data (article text removed, figure-read values labelled model-derived). For a new release, add an entry to `RELEASES` in the script (version, date, Chinese and English notes); it appears on the home page, the changelog and the download page.

```bash
python scripts/build_site_data.py --db <database-folder>
```

Review the generated changes before committing and pushing a release. Newly generated download archives include both README languages, logo assets and the data licence.

The website is fully static (`index.html` + `assets/`: `i18n.js` text, `core.js` data and filters, `search.js` search page, `pages.js` other pages, `main.js` routing, `charts.js` charts, `xlsx.js` Excel export). Data are loaded on demand (`data/index.*` on opening, `data/chunk/` as needed) and filtered, plotted and exported in the browser; no server is needed. Local preview: `python scripts/serve.py`, then open http://localhost:8765.

</details>

## License

- Data (`data/`): [CC BY 4.0](LICENSE-DATA.md) — free to use and redistribute with attribution; please also cite the original articles.
- Code (website and scripts): [MIT](LICENSE).

Developed by the [AI4FH Lab](https://dzjxzyd.github.io/ai4fh-lab/) (Artificial Intelligence for Food & Health), University College Dublin.

<p align="center"><a href="README.zh-CN.md">阅读中文版 →</a></p>
