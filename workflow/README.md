# PDF workflow: code and benchmark data

Source code of the workflow used to build **PDF · Protein Database of Functionality**, and the data of the
ground-truth benchmark of vision–language models (VLMs). The workflow and its evaluation are described in the article
"Protein Database of Functionality (PDF): a large-scale resource of 1.93 million protein functional property values
built with LLM and VLM assistance" (submitted). The database itself is served from the root of this repository.

The code is published as it was run. Comments, log messages and several file and column names are in Chinese; the
tables below translate the names a user needs.

## Contents

| Folder | Content |
|---|---|
| `1_article_acquisition/` | `fetch_papers.py`: reads article pages of ACS, Elsevier, Wiley, Springer Nature, MDPI, OUP, RSC and Taylor & Francis in the user's own browser through [OpenCLI](https://github.com/jackwener/opencli) (v1.8.8) and saves the article content as Markdown, all figures and their captions, with tables rebuilt from their cells and a verbatim check against the raw page text. `elsevier_api.py`: the same output for Elsevier articles through the Elsevier text and data mining (TDM) API. `doi_lists/`: the 119,225 curated DOIs by publisher (one DOI link per line). |
| `2_vlm_benchmark/` | `extract.py`: runs a VLM on chart images and evaluates the readings against ground truth (`run`, `retry`, `truth`, `eval`, `compare`). `柱图/` (bar charts, 24 figures) and `线图 点图/` (line and scatter charts, 16 figures): ground truth, model readings and raw model outputs. |
| `3_processing_pipeline/` | `pipeline.py`: figure screening, classification and reading → cleaning and merging of article content → data-point extraction → test-method extraction → database build (`all`, `read`, `merge`, `datapoint`, `method`, `build-db`, `site`). `test_pipeline.py`: unit tests. Three decision lists read by the pipeline (see below). `run_all.bat`: runs `pipeline.py all`. |

The prompts and output schemas of all model steps are given in Text S2 of the Supporting Information of the article.

## Requirements

- Python 3.11 or later and the packages in `requirements.txt` (`pip install -r requirements.txt`).
- Article acquisition: OpenCLI 1.8.8 with its browser extension in Chrome or Edge, and lawful (for example
  institutional-subscription) access to the articles. For Elsevier: an Elsevier API key in `ELSEVIER_API_KEY`
  (and `ELSEVIER_INSTTOKEN` where the institution uses one).
- Model steps: an OpenAI-compatible endpoint. The scripts read `OPENROUTER_API_KEY` (default, OpenRouter),
  `GEMINI_API_KEY` (Google, used when OpenRouter is unavailable) and `OPENAI_API_KEY`. Model calls are charged by the
  provider; `pipeline.py ... --dry-run` lists what would be sent without calling a model.

## Usage

Run each script from its own folder; `python <script> --help` lists all options.

```bash
# article acquisition
python fetch_papers.py 10.1021/acs.jafc.5c12346 10.1016/j.indcrop.2026.124008   # selected DOIs
python fetch_papers.py --file doi_lists/Wiley.md                                 # one DOI list
python elsevier_api.py                                                           # doi_lists/Elsevier.md through the API

# VLM benchmark
python extract.py run --dir 柱图 --model google/gemini-3.8-flash
python extract.py compare                      # all models, both chart batches

# processing pipeline
python pipeline.py all --root <folder with articles>
python test_pipeline.py
```

The unit tests replace model calls with mocks; the end-to-end tests use a sample article from the
authors' local data and are skipped when it is not present.

Default folders are set as constants near the top of the scripts (`PAPERS_DIRS` in `fetch_papers.py`, `ACS_ROOT`,
`PAPER_ROOTS` and `bd_DB_DIR` in `pipeline.py`); they point to the authors' drive layout (`D:\1.acs_papers_done` …
`D:\8.Springer nature_papers`) and are overridden with `--root`. Interrupted runs resume when the same command is
repeated (progress ledgers and the checkpoint folder `断点/` are kept next to the scripts and removed when finished).

### Files of one article

The acquisition scripts write one folder per article, named after the DOI with `/` replaced by `_`, under
`<root>/papers/`; the pipeline adds its outputs to the same folder and writes reports to `<root>/_records/` and the
database tables to `<root>/database/`.

| File | Content |
|---|---|
| `全文.md` | article content as Markdown (title, abstract, sections, figure captions, tables) |
| `figure/` | original figure files and `figure_markdown.md` (title, image file and caption of each figure) |
| `反读数据.md`, `反读数据.json` | values read from figures |
| `全文合并.md` | cleaned article content with the figure readings inserted at the captions |
| `datapoint.md` | samples, treatments and values mapped by the language model and checked by code |
| `method.json` | test methods linked to the values |

### Decision lists read by the pipeline

| File | Content |
|---|---|
| `人工排除.tsv` | exclusion list compiled through LLM-assisted manual review (article, property, measure, reason; Table S9) |
| `不再问.tsv` | articles not sent to the model in data-point extraction (article, reason) |
| `不用重读.tsv` | figure panels or series not re-read (article, panel or series, reason) |

## Benchmark data

Two batches of figures from five published articles cited in the paper. The figure images and the authors' source
workbooks are not redistributed; the figures are identified by their file names.

| File | Content |
|---|---|
| `truth.csv` | ground truth: `图片名` image, `子图` panel, `系列` series, `X类别/数值` x category or value, `Y值` y value, `误差±` error bar (±), `显著性` significance letter |
| `difficulty.csv` | `图号` figure number, `难度` difficulty (`简单` easy, `中等` medium, `难` hard) |
| `stacked.csv` | stacking order (bottom to top) of the stacked bar chart, evaluated by segment height |
| `extracted_<model>.csv` | normalized readings of one model (same columns as `truth.csv`, plus point number, axis units, error-bar ends and notes) |
| `results_<model>.jsonl` | raw model outputs, one line per figure, including token usage and latency |

## Use of article content

The scripts process article content locally for text and data mining only; no article text is stored in this
repository. Use them only with lawful access to the articles and in line with the publishers' terms (the authors
relied on the text and data mining exception for non-commercial research, section 53A of the Irish Copyright and Related
Rights Act 2000).

## Licence

Code: MIT License (see `LICENSE` at the root of this repository). Benchmark data and DOI lists: CC BY-NC 4.0, like the
database (see `LICENSE-DATA.md`).
