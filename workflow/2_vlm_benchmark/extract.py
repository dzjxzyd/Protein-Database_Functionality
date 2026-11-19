# -*- coding: utf-8 -*-
"""
VLM 图表数据提取评测 —— 唯一脚本：选图配额 + 合成图 + 提取 + 真值解析 + 单模型评估 + 多模型对比
（2026-10-05 由 extract / parse_truth / evaluate / report / compare_models / gen_synth /
  make_selection_plan 七个脚本合并而成；qwen_extraction、hybird_extraction 两套提取脚本已退役，
  以后所有 VLM 都只用这一个）

每批图一个文件夹（柱图\、线图 点图\），里面放图片 FigureN.png/jpg、真值工作簿 原始数据*.xlsx、
可选的 difficulty.csv（列：图号, 难度）。脚本产物也写在该文件夹：
    results_<模型>.jsonl   模型原始输出，每张一行，失败也记一行（断点续跑靠它）
    extracted_<模型>.csv   规范表（run / retry 结束自动导出）
    truth.csv              真值规范表（truth 子命令生成）

用法（在本文件所在目录跑）:
    python extract.py run     --dir 柱图 --model gpt-6-astra   批量提取（可 Ctrl+C，重跑自动续）
    python extract.py retry   --dir 柱图 --model gpt-6-astra   只重跑失败的
    python extract.py one     柱图/Figure5.png --model ...     单张调试，终端表格
    python extract.py export  --dir 柱图 --model ...           从 jsonl 重新导出 extracted_<模型>.csv
    python extract.py truth   --dir 柱图                       真值工作簿 -> truth.csv
    python extract.py eval    --dir 柱图 --model ...           单模型报告 -> 该批文件夹\\报告_<模型>.xlsx
    python extract.py compare                                  多模型对比 -> 报告_多模型对比.xlsx
        compare 默认用本目录下所有含 truth.csv 的子文件夹、找到的全部 extracted_*.csv；
        也可 --models A B ... --batch 名称=目录 ... 指定。
    python extract.py synth [--seed 20260917] [--n 30]         生成合成图批次 -> 合成图\\（图 + truth.csv + difficulty.csv + meta.csv）
    python extract.py plan                                     生成选图配额表 -> selection_plan.csv（已存在不覆盖）

    模型接口是 OpenAI 兼容的：OpenAI 直连 / OpenRouter / 本地 Ollama，用环境变量切换，见 README.md。
    paper_pipeline\\read.py 和 figure_reader\\figure_reader.py 按绝对路径 import 本文件的
    SYSTEM_PROMPT / Extraction / MAX_SIDE / DETAIL 等，改动提取部分前先想清楚。

依赖:
    pip install openai pydantic pillow tqdm pandas openpyxl
"""
import os, io, re, csv, json, math, time, base64, glob, random, string, argparse, threading, difflib
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
from openai import OpenAI
from pydantic import BaseModel, Field
from PIL import Image
from tqdm import tqdm

# ============================================================
# ① 配置
# ============================================================
BASE      = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = "images"
MODEL     = "gpt-5.5"
DETAIL    = "high"
WORKERS   = 4
MAX_SIDE  = 2048
EXTS      = ("*.png", "*.jpg", "*.jpeg", "*.webp")

SYSTEM_PROMPT = """你是科研图表数据反读专家。从图片中的柱状图、折线图或散点图提取数据。

【强制工作顺序】
1. 判断图中有几个子图（panel），逐个处理。子图编号用图中标注（A/B/C…），无标注填 null。
2. 核对坐标轴：读出每条轴的标题、单位、刻度标签、最小值、最大值。
3. 核对刻度倍率与尺度类型：判断是线性还是对数轴；注意轴标题里的倍率标注（如 ×10^3）。
4. 必须确认 Y 轴起点是否为 0。很多图的 Y 轴从非零值开始（例如从 70 开始），
   此时绝对不能按柱子的视觉高度比例估值，必须以刻度线为基准做线性插值。
5. 识别图例中每个系列的名称与图案或颜色，判断它属于左轴还是右轴。
6. 逐点读数：柱状图读柱端（柱子顶端），折线与散点读点中心。
   有误差棒的读出上下端的绝对坐标值。

【折线图 / 散点图 专用规则】
- 只读真实存在的数据点：折线读转折顶点或标记符（圆、方、三角…）的中心；
  散点读点中心。绝不沿曲线采样、绝不在两点之间插值生成中间点。
- 一个系列有几个标记点就输出几个点，不得为了凑齐与其他系列相同的点数而补点。
- X 轴刻度标签是数字、但相邻标签间距不等时（例如 0, 1, 10, 30, 50, 70 却在图上
  等距排列），这是序数轴：x_value 必须填标签上写的数字本身，
  不得按像素位置在数轴上反推。
- 多条曲线重叠时，严格按图例的颜色 + 标记形状配对，不要按上下顺序猜。
  若某点被其他曲线遮挡无法确认归属，该点 y_value 填 null 并在 note 说明。
- 误差棒是竖直短线（可能带横帽），不要把误差棒的端点当成数据点中心。

【读数规则】
- 数值按刻度线线性插值（对数轴按对数插值），保留与刻度相称的合理精度。
- 凡是靠插值估读、而非直接对齐刻度线得到的值，estimated 填 true（导出时标注“估算”）。
- 无法辨认的量一律填 null（导出为 NA）。
- 不编造、不补点：图中没有的系列、分类、数据点，一律不得凭空生成。
  某系列在某分类下没有柱子或点，就不要输出那一条。
- X 轴若是分类标签，填 x_category；若是连续数值，填 x_value；
  若标签本身是数字（如储藏天数 0/6/12/18/24），两者都填。
- point_index 是该系列内从左到右的序号，从 1 开始。
- 显著性字母原样抄写；双层字母（大写叠小写）合并写成如 Ca。

【本阶段禁止】
只依据图片内容作答。不得参考、猜测或对齐任何外部真实数据。"""

USER_PROMPT = "提取这张图片中所有子图的全部数据点。"


# ============================================================
# ② 字段定义
# ============================================================
class Axis(BaseModel):
    label:  Optional[str]   = Field(description="轴标题")
    unit:   Optional[str]   = Field(description="单位，无则 null")
    scale:  Optional[str]   = Field(description="linear 或 log")
    min:    Optional[float] = Field(description="刻度最小值")
    max:    Optional[float] = Field(description="刻度最大值")
    ticks:  Optional[str]   = Field(description="刻度标签，逗号分隔，供人工核对")
    starts_at_zero: Optional[bool] = Field(description="Y 轴起点是否为 0")
    multiplier: Optional[str] = Field(description="轴倍率标注如 x10^3，无则 null")


class Series(BaseModel):
    name:       str = Field(description="图例中的系列名")
    axis:       str = Field(description="left 或 right")
    chart_type: str = Field(description="bar / line / scatter")


class Point(BaseModel):
    series:      str = Field(description="所属系列名")
    point_index: int = Field(description="该系列内从左到右的序号，从 1 开始")
    x_category:  Optional[str]   = Field(description="X 分类标签，连续轴则 null")
    x_value:     Optional[float] = Field(description="X 数值，纯分类轴则 null")
    y_value:     Optional[float] = Field(description="Y 值，读不出填 null")
    err_low:     Optional[float] = Field(description="误差棒下端绝对值，无则 null")
    err_high:    Optional[float] = Field(description="误差棒上端绝对值，无则 null")
    estimated:   bool            = Field(description="是否为插值估读")
    sig:         Optional[str]   = Field(description="显著性字母，无则 null")
    note:        Optional[str]   = Field(description="该点的异常说明，正常则 null")


class Panel(BaseModel):
    panel_id:   Optional[str] = Field(description="子图编号 A/B/C，无标注则 null")
    chart_type: Optional[str] = Field(description="bar / line / scatter / mixed")
    x_axis:     Axis
    y_left:     Axis
    y_right:    Optional[Axis] = Field(description="无右轴则 null")
    series:     List[Series]
    points:     List[Point]


class Extraction(BaseModel):
    panels:     List[Panel]
    confidence: Optional[str] = Field(description="整体可信度 high/medium/low")
    note:       Optional[str] = Field(description="整图层面的说明，正常则 null")


# ============================================================
# ③ 提取核心
# ============================================================
_lock   = threading.Lock()
_client = None


def get_client():
    global _client
    if _client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit(
                "没读到 OPENAI_API_KEY。\n"
                '  临时设置: $env:OPENAI_API_KEY = "sk-..."\n'
                '  永久设置: setx OPENAI_API_KEY "sk-..."  (之后需重开终端)')
        kw = {}
        # Vast.ai 的 Instance Portal 用 ?token=xxx 鉴权：设了 OLLAMA_TOKEN 就给每个请求带上
        # （手动塞进 OPENAI_BASE_URL 无效，SDK 拼子路径时会丢 query）。不设则与原来完全一样。
        if os.environ.get("OLLAMA_TOKEN"):
            kw["default_query"] = {"token": os.environ["OLLAMA_TOKEN"]}
        _client = OpenAI(max_retries=5, timeout=300, **kw)
    return _client


def file_tag(model):
    """文件名里用的模型名：OpenRouter 的模型 ID 带斜杠（deepseek/deepseek-v4.1-flash），换成下划线，免得被当成文件夹。"""
    return model.replace("/", "_").replace(":", "_")


def out_path(ext="jsonl"):
    return f"results_{file_tag(MODEL)}.{ext}"


def to_data_url(path: str) -> str:
    """图表用 PNG 无损编码，避免压缩糊掉刻度线"""
    im = Image.open(path)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    if max(im.size) > MAX_SIDE:
        r = MAX_SIDE / max(im.size)
        im = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# 只有这些老模型接受 temperature；推理模型（gpt-5/6、o 系列）传了会 400。
# 用「白名单老模型」而不是「白名单新模型」，将来出 gpt-7 也不会再踩这个坑。
LEGACY_TEMP = ("gpt-4", "gpt-3.5", "chatgpt-4")


def call_api(path: str):
    extra = {"temperature": 0} if MODEL.startswith(LEGACY_TEMP) else {}
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": USER_PROMPT},
            {"type": "image_url",
             "image_url": {"url": to_data_url(path), "detail": DETAIL}},
        ]},
    ]
    try:
        r = get_client().chat.completions.parse(
            model=MODEL, **extra, messages=msgs, response_format=Extraction)
    except Exception as e:
        # 兜底：模型拒绝某个采样参数时，去掉重试一次
        if extra and "temperature" in str(e).lower():
            r = get_client().chat.completions.parse(
                model=MODEL, messages=msgs, response_format=Extraction)
        else:
            raise
    u = r.usage
    det = getattr(u, "completion_tokens_details", None)
    return (r.choices[0].message.parsed, u.total_tokens,
            getattr(det, "reasoning_tokens", 0) if det else 0,
            u.prompt_tokens, u.completion_tokens)


def work(path: str) -> dict:
    t0 = time.time()
    try:
        ext, tok, rtok, ptok, ctok = call_api(path)
        return {"file": path, "ok": True, "sec": round(time.time() - t0, 2),
                "tokens": tok, "reasoning_tokens": rtok,
                "prompt_tokens": ptok, "completion_tokens": ctok,
                "data": ext.model_dump()}
    except Exception as e:
        return {"file": path, "ok": False, "sec": round(time.time() - t0, 2),
                "error": f"{type(e).__name__}: {e}"}


def load_done():
    done, failed = set(), []
    if os.path.exists(out_path()):
        with open(out_path(), encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                (done.add(r["file"]) if r["ok"] else failed.append(r["file"]))
    return done, failed


def natural_key(s):
    """Figure2 排在 Figure10 前面。返回补零字符串——可哈希，pandas 排序能用。"""
    return "".join(t.zfill(10) if t.isdigit() else t.lower()
                   for t in re.split(r"(\d+)", str(s)))


def resolve_image_dir():
    """images/ 子目录优先；没有就用当前目录（图片直接摊在文件夹里的情况）"""
    if os.path.isdir(IMAGE_DIR):
        for e in EXTS:
            if glob.glob(os.path.join(IMAGE_DIR, "**", e), recursive=True):
                return IMAGE_DIR
    return "."


def scan_images():
    d = resolve_image_dir()
    out = []
    for e in EXTS:
        out += glob.glob(os.path.join(d, "**", e), recursive=True)
    return sorted(set(out), key=natural_key)


def run_batch(files):
    if not files:
        print("没有待处理的图片。")
        return
    get_client()        # 没有 key 先在这里停下，不留空的 results_*.jsonl
    print(f"待处理 {len(files)} 张，模型 {MODEL}，并发 {WORKERS}")
    tok = ok = bad = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex, \
         open(out_path(), "a", encoding="utf-8") as fout:
        futs = [ex.submit(work, p) for p in files]
        for fu in tqdm(as_completed(futs), total=len(futs), ncols=80):
            rec = fu.result()
            with _lock:
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fout.flush()
            if rec["ok"]:
                ok += 1; tok += rec["tokens"]
            else:
                bad += 1
    print(f"\n成功 {ok} / 失败 {bad} / 总 token {tok:,}")
    if bad:
        print(f'补跑失败的: python extract.py retry --dir "{os.path.basename(os.getcwd())}" --model {MODEL}')


# ============================================================
# ④ 终端表格（单张调试用）
# ============================================================
def show(ext, path=""):
    d = ext.model_dump()
    print("=" * 84)
    print(f"文件 {os.path.basename(path)}   子图数 {len(d['panels'])}   "
          f"可信度 {d.get('confidence')}")
    for p in d["panels"]:
        print("-" * 84)
        xa, yl, yr = p["x_axis"], p["y_left"], p.get("y_right")
        print(f"[子图 {p.get('panel_id')}] 类型 {p.get('chart_type')}")
        print(f"  X: {xa.get('label')} ({xa.get('unit')})  刻度 {xa.get('ticks')}")
        print(f"  Y左: {yl.get('label')} ({yl.get('unit')})  {yl.get('scale')}  "
              f"起点为0={yl.get('starts_at_zero')}  刻度 {yl.get('ticks')}")
        if yr:
            print(f"  Y右: {yr.get('label')} ({yr.get('unit')})  {yr.get('scale')}  "
                  f"刻度 {yr.get('ticks')}")
        print("  系列: " + ", ".join(
            f"{s['name']}[{s['chart_type']}/{'左' if s['axis']=='left' else '右'}]"
            for s in p["series"]))

        def w(s, n):
            s = "NA" if s is None else str(s)
            pad = n - sum(2 if ord(c) > 0x2E80 else 1 for c in s)
            return s + " " * max(pad, 1)

        print("  " + w("系列", 14) + w("#", 4) + w("X", 10) + w("Y", 10) +
              w("误差下", 9) + w("误差上", 9) + w("估算", 6) + "显著性")
        for q in p["points"]:
            x = q.get("x_category") or q.get("x_value")
            print("  " + w(q["series"], 14) + w(q["point_index"], 4) + w(x, 10) +
                  w(q.get("y_value"), 10) + w(q.get("err_low"), 9) +
                  w(q.get("err_high"), 9) + w("是" if q["estimated"] else "", 6) +
                  str(q.get("sig") or ""))
    if d.get("note"):
        print(f"\n备注: {d['note']}")


# ============================================================
# ⑤ 导出规范 CSV（只出这一份；原来的 _full.csv 和 xlsx 是过程文件，已停产）
#    列: 图片名 子图 系列 点编号 X类别/数值 Y值 X单位 Y单位 误差棒下限 误差棒上限 备注
# ============================================================
NA = "NA"


def fmt(v):
    return NA if v is None else v


def export():
    rows, n_ok, n_rec = [], 0, 0
    with open(out_path(), encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if not r["ok"]:
                continue
            n_ok += 1
            if "panels" not in (r.get("data") or {}):
                continue        # 不是本脚本写的记录（qwen / fig2table 的旧结果）
            n_rec += 1
            img = os.path.basename(r["file"])
            for p in r["data"]["panels"]:
                axis_of = {s["name"]: s["axis"] for s in p["series"]}
                xa, yl, yr = p["x_axis"], p["y_left"], p.get("y_right") or {}
                for q in p["points"]:
                    side = axis_of.get(q["series"], "left")
                    ya = yr if side == "right" else yl
                    x = q.get("x_category")
                    if x is None:
                        x = q.get("x_value")
                    notes = []
                    if q["estimated"]:
                        notes.append("估算")
                    if q.get("sig"):
                        notes.append(f"显著性={q['sig']}")
                    if q.get("note"):
                        notes.append(q["note"])
                    if ya.get("scale") == "log":
                        notes.append("对数轴")
                    if ya.get("starts_at_zero") is False:
                        notes.append("Y轴非零起点")
                    rows.append({
                        "图片名": img,
                        "子图": fmt(p.get("panel_id")),
                        "系列": q["series"],
                        "点编号": q["point_index"],
                        "X类别/数值": fmt(x),
                        "Y值": fmt(q.get("y_value")),
                        "X单位": fmt(xa.get("unit")),
                        "Y单位": fmt(ya.get("unit")),
                        "误差棒下限": fmt(q.get("err_low")),
                        "误差棒上限": fmt(q.get("err_high")),
                        "备注": "; ".join(notes) if notes else "",
                    })
    if not n_ok:
        raise SystemExit(f"{out_path()} 里没有成功的记录，未导出")
    if not n_rec:
        raise SystemExit(f"{out_path()} 不是本脚本写的格式（qwen / fig2table 的旧结果），"
                         f"不能重新导出；extracted_{file_tag(MODEL)}.csv 未改动")

    df = pd.DataFrame(rows, columns=[
        "图片名", "子图", "系列", "点编号", "X类别/数值", "Y值",
        "X单位", "Y单位", "误差棒下限", "误差棒上限", "备注"])
    # 并发写入的 jsonl 是完成顺序，这里统一排成 图→子图→系列→点编号
    if not df.empty:
        df["_k"] = df["图片名"].map(natural_key)
        df["_p"] = df["子图"].astype(str)
        df = (df.sort_values(["_k", "_p", "系列", "点编号"], kind="stable")
                .drop(columns=["_k", "_p"]).reset_index(drop=True))
    df.to_csv(f"extracted_{file_tag(MODEL)}.csv", index=False, encoding="utf-8-sig")

    n_est = sum("估算" in r["备注"] for r in rows)
    n_na = sum(r["Y值"] == NA for r in rows)
    print(f"导出 {len(df)} 个数据点 -> extracted_{file_tag(MODEL)}.csv（规范 11 列）")
    print(f"  其中标注“估算” {n_est} 个，Y 值为 NA {n_na} 个")


# ============================================================
# ⑥ 真值解析：真值工作簿 -> truth.csv
#    列: 图片名, 子图, 系列, X类别/数值, Y值, 误差±, 显著性
#    兼容两种工作簿：
#      A. 通用块式（如「原始数据1-16.xlsx」）—— 自动识别，无需硬编码
#         锚点 = 任意写着 FigureN 的单元格，往右到下一个锚点为该块范围。
#           · 有 Valu/±SD/Label 子表头 -> 三元组模式，系列名取锚点行上 Valu 所在列
#           · 无 Valu 子表头           -> 宽表模式，子表头那行即系列名，无 SD/字母
#      B. 旧版「原始数据1-24.xlsx」—— 6 种不规则布局，按图号硬编码
# ============================================================
VAL = re.compile(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*±\s*([-+]?\d*\.?\d+)\s*$")
FIG = re.compile(r"^\s*Figure\s*(\d+)\s*[:：]?\s*(.*)$", re.I)


def parse_val(s):
    """'3.054 ± 0.214' -> (3.054, 0.214)；纯数字 -> (v, None)；否则 (None, None)"""
    t = str(s).replace("−", "-").strip()
    m = VAL.match(t)
    if m:
        return float(m.group(1)), float(m.group(2))
    try:
        return float(t), None
    except (TypeError, ValueError):
        return None, None


def load_sheet(src, sheet=None):
    xl = pd.ExcelFile(src)
    name = sheet or ("Mean±SD" if "Mean±SD" in xl.sheet_names else xl.sheet_names[0])
    return pd.read_excel(src, sheet_name=name, header=None).fillna(""), name


def parse_generic(d):
    def cell(r, c):
        if 0 <= r < d.shape[0] and 0 <= c < d.shape[1]:
            return str(d.iat[r, c]).strip()
        return ""

    anchors = []
    for r in range(d.shape[0]):
        for c in range(d.shape[1]):
            m = FIG.match(cell(r, c))
            if m:
                anchors.append((r, c, int(m.group(1))))

    rows = []
    for r, c, fig in anchors:
        same_row = sorted(k for rr, k, _ in anchors if rr == r and k > c)
        c_end = same_row[0] if same_row else d.shape[1]

        def valu_cols(row):
            return [k for k in range(c, c_end)
                    if cell(row, k).lower().startswith("valu")]

        vc, sub = valu_cols(r), r
        if not vc:
            vc, sub = valu_cols(r + 1), r + 1

        if vc:                                   # —— 三元组模式 ——
            series = [(cell(r, k) if sub != r else "", k, k + 1, k + 2) for k in vc]
        else:                                    # —— 宽表模式 ——
            sub = r + 1
            series = []
            for k in range(c + 1, c_end):
                nm = cell(sub, k)
                if not nm:
                    break
                series.append((nm, k, None, None))

        for rr in range(sub + 1, d.shape[0]):
            x = cell(rr, c)
            if not x:
                break
            for nm, kv, ks, kl in series:
                v, sd = parse_val(cell(rr, kv))
                if v is None:
                    continue
                if ks is not None:
                    s2, _ = parse_val(cell(rr, ks))
                    sd = s2 if s2 is not None else sd
                rows.append({"图号": fig, "系列": nm, "X类别/数值": x, "Y值": v,
                             "误差±": sd,
                             "显著性": cell(rr, kl) if kl is not None else ""})
    return rows


def parse_legacy(d):
    def cell(r, c):
        if 0 <= r < d.shape[0] and 0 <= c < d.shape[1]:
            return str(d.iat[r, c]).strip()
        return ""

    def title_of(s):
        return s.split(":", 1)[1].strip() if ":" in s else ""

    rows = []

    def block(fig, x_col, series_cols, data_rows, scale=1):
        for r in data_rows:
            x = cell(r, x_col)
            if not x:
                continue
            for name, vc, sc in series_cols:
                v, sd = parse_val(cell(r, vc))
                if v is not None and scale != 1:
                    v, sd = round(v * scale, 6), (None if sd is None else round(sd * scale, 6))
                if v is not None:
                    rows.append({"图号": fig, "系列": name, "X类别/数值": x,
                                 "Y值": v, "误差±": sd, "显著性": cell(r, sc)})

    for hr, figs in ((0, [1, 2, 3]), (7, [4, 5, 6]), (14, [7, 8, 9])):
        for c, fig in zip((0, 5, 10), figs):
            block(fig, c, [(cell(hr, c + 1), c + 1, c + 2),
                           (cell(hr, c + 3), c + 3, c + 4)], range(hr + 1, hr + 6))
    for hr, cols, figs in ((22, (0, 3, 6, 9, 12), [10, 11, 12, 13, 14]),
                           (31, (0, 3), [15, 16])):
        for c, fig in zip(cols, figs):
            nm = title_of(cell(hr, c + 1)) or f"Figure{fig}"
            block(fig, c, [(nm, c + 1, c + 2)], range(hr + 1, hr + 7))
    block(17, 6, [(cell(30, 7), 7, 8), (cell(30, 9), 9, 10)], range(31, 38))
    for hr, fig in ((41, 18), (50, 19)):
        # 2026-11-04：Figure18 工作簿里存的是分数（0.1701），图上纵轴是百分数（17.01%），真值按图上的单位记
        block(fig, 0, [(cell(hr, c), c, c + 1) for c in (1, 3, 5, 7)],
              range(hr + 1, hr + 7), scale=100 if fig == 18 else 1)
    block(20, 0, [("Figure20", 1, 2)], range(59, 65))
    for hr, fig in ((67, 21), (76, 22), (85, 23), (94, 24)):
        block(fig, 0, [(cell(hr + 1, c), c, c + 1) for c in (1, 3, 5, 7, 9)],
              range(hr + 2, hr + 7))
    return rows


def find_source():
    cands = [p for p in glob.glob("*.xlsx")
             if not os.path.basename(p).startswith(("报告", "extracted", "~$"))]
    if not cands:
        raise SystemExit("当前目录没找到真值 .xlsx，用 --src 指定")
    pref = [p for p in cands if "原始" in p or "truth" in p.lower()]
    return (pref or cands)[0]


def cmd_truth(a):
    src = a.src or find_source()
    d, sheet = load_sheet(src, a.sheet)

    has_valu = d.map(lambda v: str(v).strip().lower().startswith("valu")).any().any()
    mode = "通用块式" if has_valu else "旧版硬编码"
    print(f"源文件: {src}    工作表: {sheet}    形状: {d.shape}")
    print(f"识别布局: {mode}（依据: 是否存在 Valu 子表头）\n")

    rows = parse_generic(d) if has_valu else parse_legacy(d)
    if not rows:
        raise SystemExit("没有解析出任何数据，请检查工作表布局")

    files = {}
    root = "images" if os.path.isdir("images") else "."
    for p in glob.glob(os.path.join(root, "*")):
        m = re.match(r"Figure(\d+)\.", os.path.basename(p), re.I)
        if m:
            files[int(m.group(1))] = os.path.basename(p)

    T = pd.DataFrame(rows)
    T["图片名"] = T["图号"].map(files)
    T["子图"] = ""
    T = T[["图片名", "子图", "系列", "X类别/数值", "Y值", "误差±", "显著性", "图号"]]

    got = sorted(T["图号"].unique())
    nofile = sorted(set(T.loc[T["图片名"].isna(), "图号"]))
    print(f"解析出 {len(T)} 个真值点，覆盖 {len(got)} 张图: {got}")
    if nofile:
        print(f"  ⚠ 找不到对应图片文件的图号: {nofile}")
    miss = [i for i in range(1, max(got) + 1) if i not in got]
    if miss:
        print(f"  ⚠ 区间内没解析到数据的图号: {miss}")

    chk = T.groupby(["图号", "图片名"], dropna=False).agg(
        系列数=("系列", "nunique"), 点数=("Y值", "size"),
        缺SD=("误差±", lambda s: s.isna().sum()),
        缺字母=("显著性", lambda s: (s.astype(str).str.strip() == "").sum()),
    ).reset_index()
    print("\n逐图点数:")
    print(chk.to_string(index=False))

    out = a.out or "truth.csv"
    T.drop(columns=["图号"]).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n已写入 {os.path.abspath(out)}")


# ============================================================
# ⑦ 评估：提取结果 vs 真值 配对
#   * 只做单位统一，绝不用真实值修正提取结果。
#   * 先确定匹配规则再配对：系列级 -> 点级，都不按行号硬配。
#   * 达标率只在指定容差时计算；缺失点计入分母且不算达标。
#   * 达标率与模型自评都不是统计置信度。
# ============================================================
ALIAS = {
    "图片名": ["图片名", "file", "image", "图片", "文件名", "filename"],
    "子图":   ["子图", "panel", "subplot", "面板"],
    "系列":   ["系列", "series", "组", "group"],
    "X":      ["x类别/数值", "x", "x类别", "x数值", "category", "类别", "分组"],
    "Y":      ["y值", "y", "value", "值", "均值", "mean"],
    "误差下": ["误差棒下限", "err_low", "误差下", "lower"],
    "误差上": ["误差棒上限", "err_high", "误差上", "upper"],
    "误差±":  ["误差±", "err_pm", "sd", "se", "std"],
    "X单位":  ["x单位", "x_unit", "xunit"],
    "Y单位":  ["y单位", "y_unit", "yunit"],
    "显著性": ["显著性", "sig", "字母", "letter"],
}


def norm_cols(df):
    low = {re.sub(r"\s+", "", c).lower(): c for c in df.columns}
    out = {}
    for std, names in ALIAS.items():
        for n in names:
            k = re.sub(r"\s+", "", n).lower()
            if k in low:
                out[std] = low[k]
                break
    return out


def base_frame(df, m, ycol):
    return pd.DataFrame({
        "图片名": df[m["图片名"]].astype(str),
        "子图":   (df[m["子图"]].fillna("").astype(str) if "子图" in m else ""),
        "系列":   df[m["系列"]].fillna("").astype(str),
        "X_raw":  df[m["X"]],
        ycol:     pd.to_numeric(df[m["Y"]], errors="coerce"),
    })


def load_truth(path):
    df = pd.read_csv(path)
    m = norm_cols(df)
    for need in ("图片名", "系列", "X", "Y"):
        if need not in m:
            raise SystemExit(f"真值文件缺少必需列: {need}")
    t = base_frame(df, m, "Y_true")
    t["err_pm_true"] = pd.to_numeric(df[m["误差±"]], errors="coerce") if "误差±" in m else np.nan
    t["sig_true"] = df[m["显著性"]].fillna("").astype(str) if "显著性" in m else ""
    t["Y单位_true"] = df[m["Y单位"]].astype(str) if "Y单位" in m else None
    return t


def load_extracted(path):
    df = pd.read_csv(path)
    m = norm_cols(df)
    e = base_frame(df, m, "Y_ext")
    lo = pd.to_numeric(df[m["误差下"]], errors="coerce") if "误差下" in m else np.nan
    hi = pd.to_numeric(df[m["误差上"]], errors="coerce") if "误差上" in m else np.nan
    e["err_pm_ext"] = (hi - lo) / 2
    e["Y单位_ext"] = df[m["Y单位"]].astype(str) if "Y单位" in m else None
    e["备注_ext"] = df["备注"].fillna("").astype(str) if "备注" in df.columns else ""
    e["sig_ext"] = e["备注_ext"].str.extract(r"显著性=([^;]+)")[0].fillna("").str.strip()
    return e


# ---------- 单位统一（只换算，不改判读结果） ----------
def norm_unit(u):
    if u is None or (isinstance(u, float) and pd.isna(u)):
        return ""
    s = str(u).strip()
    if s.upper() in ("NA", "NAN", "NONE", ""):
        return ""
    return (s.replace("μ", "u").replace("µ", "u").replace("·", " ")
             .replace("^", "").replace(" ", "").lower())


FACTORS = {
    ("%", "fraction"): 0.01, ("fraction", "%"): 100.0,
    ("mg/g", "ug/g"): 1000.0, ("ug/g", "mg/g"): 0.001,
    ("min", "s"): 60.0, ("s", "min"): 1 / 60.0,
    ("h", "min"): 60.0, ("min", "h"): 1 / 60.0,
    ("mm", "cm"): 0.1, ("cm", "mm"): 10.0,
}


def unify(vals, u_ext, u_true):
    a, b = norm_unit(u_ext), norm_unit(u_true)
    if not a or not b or a == b:
        return vals, 1.0, "同单位/未声明"
    f = FACTORS.get((a, b))
    if f is None:
        return vals, 1.0, f"单位不一致({a}->{b})未换算"
    return vals * f, f, f"单位换算{a}->{b}(x{f:g})"


# ---------- 系列级匹配规则（先定规则，不按出现顺序硬配） ----------
def nkey(s):
    return re.sub(r"[\s\-_()（）]", "", str(s)).lower()


def match_series(names_e, names_t):
    """返回 [(提取系列, 真值系列, 匹配方式)] 及两侧未匹配的名字"""
    pairs, ue, ut = [], list(names_e), list(names_t)

    # 1) 归一化后完全相同
    for ne in list(ue):
        for nt in list(ut):
            if nkey(ne) == nkey(nt):
                pairs.append((ne, nt, "名称完全匹配")); ue.remove(ne); ut.remove(nt)
                break

    # 2) 互为子串（图例简称 vs 表格全称）
    for ne in list(ue):
        for nt in list(ut):
            a, b = nkey(ne), nkey(nt)
            if a and b and (a in b or b in a):
                pairs.append((ne, nt, "名称包含匹配")); ue.remove(ne); ut.remove(nt)
                break

    # 3) 高相似度（容忍真值表里的拼写错误，如 RG-GG / RN-GG）
    cand = sorted(
        ((difflib.SequenceMatcher(None, nkey(a), nkey(b)).ratio(), a, b)
         for a in ue for b in ut), reverse=True)
    for r, a, b in cand:
        if r >= 0.70 and a in ue and b in ut:
            pairs.append((a, b, f"名称近似匹配(相似度{r:.2f})"))
            ue.remove(a); ut.remove(b)

    # 4) 两侧各只剩一个 -> 唯一对应
    if len(ue) == 1 and len(ut) == 1:
        pairs.append((ue[0], ut[0], "唯一剩余系列对应"))
        ue, ut = [], []

    return pairs, ue, ut


# ---------- 点级匹配规则 ----------
def as_num(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return np.nan


NUMISH = re.compile(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*[a-zA-Z%°]*\s*$")


def as_num_loose(v):
    """允许带单位后缀的数值标签：'0d' -> 0, '12 d' -> 12, '28' -> 28"""
    n = as_num(v)
    if not np.isnan(n):
        return n
    m = NUMISH.match(str(v))
    return float(m.group(1)) if m else np.nan


def match_points(ge, gt, x_tol_pct):
    """
    规则优先级（先定规则，绝不按行号配对）：
      1) 两侧 X 都是纯数值            -> 数值最近邻，容差 = x_tol% × 真值跨度
      2) 两侧 X 都是「数值+单位后缀」 -> 剥离后缀后同上（如 0d vs 0）
      3) 否则                         -> 分类标签精确匹配（归一化后）
    """
    strict = ge["X_raw"].map(as_num), gt["X_raw"].map(as_num)
    loose = ge["X_raw"].map(as_num_loose), gt["X_raw"].map(as_num_loose)
    if strict[0].notna().all() and strict[1].notna().all() and len(gt):
        xe, xt, tag = strict[0], strict[1], ""
    elif loose[0].notna().all() and loose[1].notna().all() and len(gt):
        xe, xt, tag = loose[0], loose[1], ",已剥离单位后缀"
    else:
        xe = None

    if xe is not None:
        span = float(xt.max() - xt.min())
        tol = (abs(span) * x_tol_pct / 100.0 if span
               else max(abs(float(xt.iloc[0])) * x_tol_pct / 100.0, 1e-9))
        # 序数轴保护：X 标签是数字但间距不等时（如 0,1,10,30,50,70），
        # 跨度的 5% 可能大于相邻标签间距，会让 0 和 1 互相抢匹配。
        # 容差再压到「最小相邻间距的一半」以内。
        u = sorted(set(float(v) for v in xt))
        if len(u) > 1:
            gap = min(b - a for a, b in zip(u, u[1:]))
            tol = min(tol, gap / 2)
            tag += f",间距保护(最小间距{gap:g})" if tol == gap / 2 else ""
        cand = sorted((abs(a - b), ie, it)
                      for ie, a in xe.items() for it, b in xt.items()
                      if abs(a - b) <= tol)
        pe, pt, out = set(), set(), []
        for _, ie, it in cand:
            if ie not in pe and it not in pt:
                pe.add(ie); pt.add(it); out.append((ie, it))
        return out, f"数值最近邻(容差={x_tol_pct}%跨度{tag})"

    by = {}
    for it, v in gt["X_raw"].items():
        by.setdefault(nkey(v), []).append(it)
    out, left_e = [], []
    for ie, v in ge["X_raw"].items():
        k = nkey(v)
        if by.get(k):
            out.append((ie, by[k].pop(0)))
        else:
            left_e.append(ie)

    # 精确匹配剩下的，用高相似度兜底（容忍 OCR 误读，如 P-A / P-4），并记录规则
    left_t = [i for v in by.values() for i in v]
    fuzzy = 0
    if left_e and left_t:
        cand = sorted(((difflib.SequenceMatcher(
            None, nkey(ge.loc[ie, "X_raw"]), nkey(gt.loc[it, "X_raw"])).ratio(), ie, it)
            for ie in left_e for it in left_t), reverse=True)
        ue, ut = set(left_e), set(left_t)
        for r, ie, it in cand:
            if r >= 0.60 and ie in ue and it in ut:
                out.append((ie, it)); ue.discard(ie); ut.discard(it); fuzzy += 1
    rule = "分类标签精确匹配"
    if fuzzy:
        rule += f"+近似兜底{fuzzy}点"
    return out, rule


def sig_agree(a, b):
    """
    显著性字母比对。返回 True / 'tier' / False / None(双方都空)
    'tier' = 层级不同但同层字母一致（图上是大写叠小写双层，真值表只记了其中一层）
    """
    a, b = str(a or "").strip(), str(b or "").strip()
    if not a and not b:
        return None
    if a.lower() == b.lower():
        return True
    al, bl = "".join(c for c in a if c.islower()), "".join(c for c in b if c.islower())
    au, bu = "".join(c for c in a if c.isupper()), "".join(c for c in b if c.isupper())
    if (al and bl and al == bl) or (au and bu and au == bu):
        return "tier"
    return False


def load_stacked(d="."):
    """{图片名: [系列, 自下而上]}，读 <d>/stacked.csv（列: 图片名, 堆叠顺序，系列名用 | 分隔）；文件不存在返回空表"""
    p = os.path.join(d, "stacked.csv")
    if not os.path.exists(p):
        return {}
    t = pd.read_csv(p)
    return {str(r.iloc[0]).strip(): [s.strip() for s in str(r.iloc[1]).split("|")] for _, r in t.iterrows()}


def destack(Ei, order):
    """
    堆叠柱：真值记每段高度；模型有的报段高度，有的报每段顶端在纵轴上的累计坐标，两种读法都对。
    只看模型自己的输出判断读法：同一张图里每个 X 的读数沿堆叠方向（自下而上）都不减 -> 累计坐标，
    换算成段高度 = 本段读数 − 下面一段的读数。不用真值。返回 (换算后的 Ei, 说明)
    """
    sp, _, _ = match_series(Ei.系列.unique(), order)
    rank = {se: order.index(st) for se, st, _ in sp}
    g = Ei[Ei.系列.isin(rank) & Ei.Y_ext.notna()]
    g = g.assign(_r=g.系列.map(rank), _x=g.X_raw.map(nkey))
    stacks = [s.sort_values("_r") for _, s in g.groupby("_x") if len(s) > 1]
    if not stacks or not all(s.Y_ext.is_monotonic_increasing for s in stacks):
        return Ei, "堆叠柱：模型给的是段高度，未换算"
    Ei = Ei.copy()
    for s in stacks:
        Ei.loc[s.index[1:], "Y_ext"] = s.Y_ext.values[1:] - s.Y_ext.values[:-1]
    return Ei, "堆叠柱：模型给的是累计顶端坐标，已换算为段高度"


def pair_up(E, T, x_tol=5.0, stacked=None):
    """
    系列级 + 点级配对。返回 (逐点DataFrame, 匹配规则DataFrame, 漏检, 多检)。
    eval 与 compare 共用此函数，确保匹配规则完全同源。
    stacked：{图片名: 自下而上的系列}，这些堆叠柱按段高度评（见 destack）。
    """
    rows, rules = [], []
    mi_e, mi_t = set(), set()

    for img in sorted(set(T["图片名"]) | set(E["图片名"]),
                      key=lambda s: [int(x) if x.isdigit() else x
                                     for x in re.split(r"(\d+)", str(s))]):
        Ei, Ti = E[E.图片名 == img], T[T.图片名 == img]
        if Ti.empty or Ei.empty:
            rules.append({"图片名": img, "提取系列": "", "真值系列": "",
                          "系列匹配": "整图缺失" if Ei.empty else "真值无此图",
                          "点匹配规则": "", "配对点数": 0})
            continue
        snote = ""
        if stacked and img in stacked:
            Ei, snote = destack(Ei, stacked[img])

        sp, ue, ut = match_series(Ei.系列.unique(), Ti.系列.unique())
        for n in ue:
            rules.append({"图片名": img, "提取系列": n, "真值系列": "",
                          "系列匹配": "未匹配(多检系列)", "点匹配规则": "", "配对点数": 0})
        for n in ut:
            rules.append({"图片名": img, "提取系列": "", "真值系列": n,
                          "系列匹配": "未匹配(漏检系列)", "点匹配规则": "", "配对点数": 0})

        for se, st, how in sp:
            ge, gt = Ei[Ei.系列 == se], Ti[Ti.系列 == st]
            pp, prule = match_points(ge, gt, x_tol)
            yv, factor, unote = unify(ge["Y_ext"], ge["Y单位_ext"].iloc[0],
                                      gt["Y单位_true"].iloc[0])
            if snote:
                unote = f"{unote}；{snote}"
            rules.append({"图片名": img, "提取系列": se, "真值系列": st,
                          "系列匹配": how, "点匹配规则": prule,
                          "配对点数": len(pp), "单位处理": unote,
                          "真值点数": len(gt), "提取点数": len(ge)})

            for ie, it in pp:
                mi_e.add(ie); mi_t.add(it)
                y_e, y_t = yv.loc[ie], gt.loc[it, "Y_true"]
                x_e, x_t = as_num(ge.loc[ie, "X_raw"]), as_num(gt.loc[it, "X_raw"])
                r = {"图片名": img, "提取系列": se, "真值系列": st,
                     "X_提取": ge.loc[ie, "X_raw"], "X_真值": gt.loc[it, "X_raw"],
                     "Y_提取": y_e, "Y_真值": y_t,
                     "误差±_提取": ge.loc[ie, "err_pm_ext"],
                     "误差±_真值": gt.loc[it, "err_pm_true"],
                     "显著性_提取": ge.loc[ie, "sig_ext"],
                     "显著性_真值": gt.loc[it, "sig_true"],
                     "系列匹配": how, "点匹配规则": prule, "单位处理": unote,
                     "单位告警": "", "备注_提取": ge.loc[ie, "备注_ext"]}
                sa = sig_agree(r["显著性_提取"], r["显著性_真值"])
                # 双方都没有字母 -> 记 NaN，不计入分子也不计入分母
                r["显著性一致"] = np.nan if sa is None else (sa is True)
                r["显著性同层一致"] = np.nan if sa is None else (sa in (True, "tier"))
                r["显著性判定"] = {True: "完全一致", "tier": "同层一致(层级记法不同)",
                                   False: "不一致", None: "双方均无"}[sa]
                if pd.notna(y_e) and pd.notna(y_t):
                    r["Y_绝对误差"] = abs(y_e - y_t)
                    r["Y_相对误差%"] = ("NA" if y_t == 0 else
                                        round(abs(y_e - y_t) / abs(y_t) * 100, 4))
                    if factor != 1.0 and y_t != 0:
                        raw = ge.loc[ie, "Y_ext"]
                        ec = abs(y_e - y_t) / abs(y_t)
                        er = abs(raw - y_t) / abs(y_t) if pd.notna(raw) else np.inf
                        if ec > 0.5 and ec > er * 10:
                            r["单位告警"] = (f"换算后误差{ec*100:.0f}%远大于换算前"
                                            f"{er*100:.0f}%，疑似单位标注错误")
                else:
                    r["Y_绝对误差"] = np.nan; r["Y_相对误差%"] = "NA"
                if pd.notna(x_e) and pd.notna(x_t):
                    r["X_绝对误差"] = abs(x_e - x_t)
                    r["X_相对误差%"] = ("NA" if x_t == 0 else
                                        round(abs(x_e - x_t) / abs(x_t) * 100, 4))
                else:
                    r["X_绝对误差"] = np.nan; r["X_相对误差%"] = "NA"
                rows.append(r)

    D = pd.DataFrame(rows)
    R = pd.DataFrame(rules)
    return D, R, T.drop(index=list(mi_t)), E.drop(index=list(mi_e))


# ============================================================
# ⑧ 报告公共部分（颜色、难度）
# ============================================================
GREEN, LIME, YELLOW, RED, GREY = "C6EFCE", "E2EFDA", "FFEB9C", "FFC7CE", "F2F2F2"
DIFF_ORDER = {"简单": 0, "中等": 1, "难": 2, "未定义": 9}
DIFF_FILL = {"简单": "DDEBF7", "中等": "FFF2CC", "难": "FCE4D6"}


def _styles():
    """openpyxl 只在写报告时才导入（paper_pipeline import 本文件时用不到）"""
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    return Font, PatternFill, get_column_letter


def fig_no(name):
    m = re.search(r"(\d+)", str(name))
    return int(m.group(1)) if m else -1


def load_diff(d="."):
    """{图号: 难度}，读 <d>/difficulty.csv（列: 图号 或 图片名, 难度）；文件不存在返回空表"""
    p = os.path.join(d, "difficulty.csv")
    if not os.path.exists(p):
        return {}
    t = pd.read_csv(p)
    cols = {re.sub(r"\s+", "", c).lower(): c for c in t.columns}
    kc = cols.get("图号") or cols.get("图片名") or cols.get("file") or t.columns[0]
    vc = cols.get("难度") or cols.get("difficulty") or t.columns[-1]
    return {fig_no(r[kc]): str(r[vc]).strip() for _, r in t.iterrows()}


def band(e):
    """误差 -> 颜色。绿<1% 浅绿<2% 黄<5% 红>=5%"""
    try:
        e = float(e)
    except (TypeError, ValueError):
        return GREY
    if pd.isna(e):
        return GREY
    return GREEN if e < 1 else LIME if e < 2 else YELLOW if e < 5 else RED


def verdict(mx, miss_n, extra_n):
    if mx is not None and not pd.isna(mx) and mx >= 100:
        return "不可用(系统性错误)"
    if miss_n or extra_n:
        return "需复核(漏检/多检)"
    if pd.isna(mx):
        return "需复核"
    if mx < 2:
        return "优秀"
    if mx < 5:
        return "良好"
    return "需复核"


# ============================================================
# ⑨ 单模型报告（eval）
# ============================================================
def cmd_eval(a):
    ext_path = a.extracted or f"extracted_{file_tag(MODEL)}.csv"
    truth = a.truth or "truth.csv"
    E, T = load_extracted(ext_path), load_truth(truth)
    print(f"提取 {len(E)} 点 ({ext_path})    真值 {len(T)} 点 ({truth})\n")
    D, R, miss, extra = pair_up(E, T, a.x_tol, load_stacked("."))
    diff = load_diff(".")
    if diff:
        print(f"难度定义: difficulty.csv（{len(diff)} 张图）")
    write_report(D, R, miss, extra, T, MODEL, truth, a.tol_abs, a.tol_rel, diff)


def write_report(D, R, miss, extra, T, model, truth, tol_abs, tol_rel, diff):
    Font, PatternFill, get_column_letter = _styles()
    HEAD = PatternFill("solid", fgColor="305496")
    HF = Font(color="FFFFFF", bold=True)

    def difficulty(name):
        return diff.get(fig_no(name), "未定义")

    OUT = f"报告_{file_tag(model)}.xlsx"   # 模型 ID 里的斜杠换成下划线
    D = D.copy()
    D["rel"] = pd.to_numeric(D["Y_相对误差%"], errors="coerce")

    # ---------------- 逐点对比 ----------------
    pts = pd.DataFrame({
        "图片名": D["图片名"], "难度": D["图片名"].map(difficulty),
        "系列": D["提取系列"], "X": D["X_真值"],
        "真实值": D["Y_真值"], "模型值": D["Y_提取"],
        "差值": (D["Y_提取"] - D["Y_真值"]).round(4),
        "相对误差%": D["rel"].round(3),
        "真值字母": D["显著性_真值"], "模型字母": D["显著性_提取"],
        "字母判定": D["显著性判定"],
        "真值±": D["误差±_真值"], "模型±": D["误差±_提取"],
        "匹配方式": D["系列匹配"].astype(str) + " / " + D["点匹配规则"].astype(str),
        "备注": D["备注_提取"],
    })
    pts["判定"] = pts["相对误差%"].map(
        lambda e: "NA" if pd.isna(e) else
        ("优 <1%" if e < 1 else "良 <2%" if e < 2 else
         "可 <5%" if e < 5 else "超差 ≥5%"))
    pts = pts[["图片名", "难度", "系列", "X", "真实值", "模型值", "差值", "相对误差%",
               "判定", "真值字母", "模型字母", "字母判定",
               "真值±", "模型±", "匹配方式", "备注"]]

    # ---------------- 逐图明细 ----------------
    figs = []
    for f, g in D.groupby("图片名"):
        r = g["rel"].dropna()
        mn = int((miss["图片名"] == f).sum())
        ex = int((extra["图片名"] == f).sum())
        ae = pd.to_numeric(g["Y_绝对误差"], errors="coerce").dropna()
        figs.append({
            "图片名": f, "难度": difficulty(f), "点数": len(g),
            "中位相对误差%": round(r.median(), 3) if len(r) else np.nan,
            "最大相对误差%": round(r.max(), 2) if len(r) else np.nan,
            "MAE": round(ae.mean(), 4) if len(ae) else np.nan,
            "RMSE": round(math.sqrt((ae ** 2).mean()), 4) if len(ae) else np.nan,
            "误差<1%": int((r < 1).sum()), "误差<5%": int((r < 5).sum()),
            "字母一致": (lambda v: f"{int(v.sum())}/{len(v)}" if len(v) else "无字母")(
                g["显著性同层一致"].dropna()),
            "漏检": mn, "多检": ex,
            "结论": verdict(r.max() if len(r) else np.nan, mn, ex),
        })
    F = pd.DataFrame(figs)
    F["_k"] = F["图片名"].str.extract(r"(\d+)").astype(int)
    F = F.sort_values("_k").drop(columns="_k").reset_index(drop=True)

    # ---------------- 需复核 ----------------
    prob = pts[(pts["相对误差%"] >= 2) | (pts["字母判定"] == "不一致")
               | pts["相对误差%"].isna()].copy()
    m2 = miss.assign(问题="漏检：真值有此点，模型未输出").rename(
        columns={"X_raw": "X", "Y_true": "真实值"})[
        ["图片名", "系列", "X", "真实值", "问题"]]
    e2 = extra.assign(问题="多检：模型输出了真值里没有的点").rename(
        columns={"X_raw": "X", "Y_ext": "模型值"})[
        ["图片名", "系列", "X", "模型值", "问题"]]
    ME = pd.concat([m2, e2], ignore_index=True)

    # ---------------- 总览 KPI ----------------
    bad = F.loc[F["结论"].str.startswith("不可用"), "图片名"].tolist()
    rc = D.loc[~D["图片名"].isin(bad), "rel"].dropna()
    ra = D["rel"].dropna()
    ae = pd.to_numeric(D["Y_绝对误差"], errors="coerce").dropna()
    tag = f"剔除 {', '.join(bad)}" if bad else "无需剔除"

    kpi = [
        ("真值点总数", len(T), f"来自 {truth}"),
        ("成功配对", len(D), "系列级 + 点级匹配，规则见「④ 匹配规则」"),
        ("漏检 / 多检", f"{len(miss)} / {len(extra)}", "明细见「③ 需复核」"),
        ("", "", ""),
        ("★ 中位相对误差", f"{rc.median():.3f}%", tag),
        ("★ 最大相对误差", f"{rc.max():.2f}%", tag),
        ("★ 误差 <1% 的点", f"{int((rc < 1).sum())}/{len(rc)}"
         f"  ({(rc < 1).mean() * 100:.1f}%)", tag),
        ("★ 误差 <5% 的点", f"{int((rc < 5).sum())}/{len(rc)}"
         f"  ({(rc < 5).mean() * 100:.1f}%)", tag),
        ("★ 显著性字母一致",
         (lambda v: f"{int(v.sum())}/{len(v)}  ({v.mean() * 100:.1f}%)"
          if len(v) else "本批无字母")(D["显著性同层一致"].dropna()),
         f"同层比对；{int(D['显著性同层一致'].isna().sum())} 点双方均无字母，已排除"),
        ("", "", ""),
        ("中位相对误差（含全部图）", f"{ra.median():.3f}%", "不剔除任何图"),
        ("平均相对误差（含全部图）", f"{ra.mean():.1f}%",
         "被系统性错误图拉高，不代表典型水平"),
        ("MAE / RMSE", f"{ae.mean():.4f} / {math.sqrt((ae ** 2).mean()):.4f}",
         "原始单位，不同图量纲不同，不可跨图比较"),
        ("", "", ""),
    ]
    # 按难度分档（难度由使用者指定，见「⑤ 说明」）
    DD = D.assign(难度=D["图片名"].map(difficulty))
    levels = [l for l in DD["难度"].unique() if l != "未定义"]
    if not levels:
        kpi.append(("难度分档", "未定义",
                    "在工作目录放 difficulty.csv（列：图号, 难度）即可启用"))
    for lv in sorted(levels, key=lambda x: DIFF_ORDER.get(x, 9)):
        g = DD[DD["难度"] == lv]
        gc = g.loc[~g["图片名"].isin(bad), "rel"].dropna()
        nfig = g["图片名"].nunique()
        if len(gc):
            kpi.append((f"【{lv}】{nfig} 张图 / {len(g)} 点",
                        f"中位 {gc.median():.3f}%  最大 {gc.max():.2f}%",
                        f"误差<1%: {(gc < 1).mean() * 100:.0f}%"
                        f"   误差<5%: {(gc < 5).mean() * 100:.0f}%"))
        else:
            kpi.append((f"【{lv}】{nfig} 张图 / {len(g)} 点",
                        "全部被剔除", f"剔除 {', '.join(bad)}"))
    if tol_abs is not None or tol_rel is not None:
        ok = pd.Series(True, index=D.index)
        desc = []
        if tol_abs is not None:
            ok &= pd.to_numeric(D["Y_绝对误差"], errors="coerce") <= tol_abs
            desc.append(f"绝对≤{tol_abs}")
        if tol_rel is not None:
            ok &= D["rel"] <= tol_rel
            desc.append(f"相对≤{tol_rel}%")
        ok = ok.fillna(False)
        kpi.append(("达标率", f"{int(ok.sum())}/{len(T)} = {ok.sum() / len(T) * 100:.1f}%",
                    f"容差 {' 且 '.join(desc)}；缺失点计入分母且不算达标"))
    else:
        kpi.append(("达标率", "未计算", "未指定容差（--tol-rel / --tol-abs）"))
    K = pd.DataFrame(kpi, columns=["指标", "值", "说明"])

    # ---------------- 写盘 ----------------
    with pd.ExcelWriter(OUT, engine="openpyxl") as w:
        K.to_excel(w, sheet_name="① 总览", index=False, startrow=2)
        F.to_excel(w, sheet_name="① 总览", index=False, startrow=len(K) + 6)
        pts.to_excel(w, sheet_name="② 逐点对比", index=False)
        prob.to_excel(w, sheet_name="③ 需复核", index=False)
        ME.to_excel(w, sheet_name="③ 需复核", index=False, startrow=len(prob) + 4)
        R.to_excel(w, sheet_name="④ 匹配规则", index=False)
        wb = w.book

        for ws in wb.worksheets:
            for c in ws[1]:
                if c.value:
                    c.fill, c.font = HEAD, HF
            for col in ws.columns:
                ln = max((len(str(c.value)) for c in col if c.value is not None),
                         default=8)
                ws.column_dimensions[get_column_letter(col[0].column)].width = \
                    min(max(ln + 2, 9), 48)

        ov = wb["① 总览"]
        ov["A1"] = f"图表数据提取评估报告 — 模型 {model}"
        ov["A1"].font = Font(size=15, bold=True)
        ov["A2"] = "★ 为核心结论；颜色：绿<1%  浅绿<2%  黄<5%  红≥5%"
        ov["A2"].font = Font(size=10, color="808080")
        for c in ov[3]:
            if c.value:
                c.fill, c.font = HEAD, HF
        # K 从 startrow=2 写起 -> 表头在 Excel 第 3 行；F 从 startrow=len(K)+6
        # 写起 -> 表头在 Excel 第 len(K)+7 行（Excel 行号 = startrow + 1）
        hb = len(K) + 6
        ov.cell(hb, 1).value = "逐图明细"
        ov.cell(hb, 1).font = Font(size=13, bold=True)
        hr = len(K) + 7
        for c in ov[hr]:
            if c.value:
                c.fill, c.font = HEAD, HF
        cid = {c.value: i + 1 for i, c in enumerate(ov[hr]) if c.value}
        for r in range(hr + 1, hr + 1 + len(F)):
            for nm in ("中位相对误差%", "最大相对误差%"):
                cell = ov.cell(r, cid[nm])
                cell.fill = PatternFill("solid", fgColor=band(cell.value))
            dc = ov.cell(r, cid["难度"])
            dc.fill = PatternFill("solid", fgColor=DIFF_FILL.get(dc.value, GREY))
            v = ov.cell(r, cid["结论"])
            v.fill = PatternFill("solid", fgColor=(
                GREEN if v.value == "优秀" else LIME if v.value == "良好"
                else RED if "不可用" in str(v.value) else YELLOW))
        for r in range(4, 4 + len(K)):
            if str(ov.cell(r, 1).value or "").startswith("★"):
                for c in range(1, 4):
                    ov.cell(r, c).font = Font(bold=True)
        ov.freeze_panes = "A4"

        ws = wb["② 逐点对比"]
        ws.freeze_panes = "A2"
        cid = {c.value: i + 1 for i, c in enumerate(ws[1]) if c.value}
        for r in range(2, ws.max_row + 1):
            f = band(ws.cell(r, cid["相对误差%"]).value)
            for nm in ("相对误差%", "判定"):
                ws.cell(r, cid[nm]).fill = PatternFill("solid", fgColor=f)
            dc = ws.cell(r, cid["难度"])
            dc.fill = PatternFill("solid", fgColor=DIFF_FILL.get(dc.value, GREY))
            if ws.cell(r, cid["字母判定"]).value == "不一致":
                ws.cell(r, cid["字母判定"]).fill = PatternFill("solid", fgColor=RED)

        note = wb.create_sheet("⑤ 说明")
        lines = [
            "指标含义与使用边界", "",
            "图片难度由使用者在 difficulty.csv 中指定（列：图号, 难度），非模型自评；",
            "  该文件缺失时难度记为「未定义」，总览的难度分档随之跳过。",
            "",
            "相对误差% = |模型值 − 真实值| / |真实值| × 100%；真实值为 0 时记 NA。",
            "MAE / RMSE 为原始单位下的误差，不同图量纲不同，不可跨图直接比较。",
            "颜色分级：绿 <1%，浅绿 1~2%，黄 2~5%，红 ≥5%。",
            "",
            "匹配规则（完整记录见「④ 匹配规则」，逐条可审计）",
            "  系列级：①名称完全匹配 ②互为子串 ③高相似度 ④两侧各剩一个则唯一对应",
            "  点级：①两侧纯数值→最近邻，容差=真值跨度的 5%",
            "        ②带单位后缀的数值标签先剥离后缀（如 0d 对 0）",
            "        ③否则分类标签精确匹配，剩余项相似度≥0.60 兜底",
            "  任何情况下都不按行号配对。",
            "  堆叠柱（批次文件夹 stacked.csv 里列出的图）按段高度评：模型若给的是每段顶端的累计坐标"
            "（同一 X 自下而上读数都不减，只看模型输出判断），先换算成段高度再比，见「单位处理」列。",
            "",
            "对真实数据的使用边界",
            "  单位统一只按双方各自声明的单位换算，绝不依据真实值修正模型输出。",
            "  若换算后误差反而放大一个量级，只在「单位告警」提示，不回退数值。",
            "  提取（run / retry / one）完全不读取真值文件，真值只在 eval / compare 里读。",
            "",
            "可信度说明",
            f"  本报告所有数值均为在这 {len(T)} 个真值点上的经验指标，",
            "  描述的是模型输出与该批真值的符合程度。",
            "  达标率不是统计置信度，模型自评的 confidence 字段也不是。",
            "  要把结论推广到更大的图集，需要独立抽样与区间估计，本报告不提供。",
        ]
        for i, t in enumerate(lines):
            note.cell(i + 1, 1).value = t
        note["A1"].font = Font(size=14, bold=True)
        note.column_dimensions["A"].width = 78

    print("=" * 74)
    print(F.to_string(index=False))
    print("=" * 74)
    print(f"报告: {OUT}    （① 总览 ② 逐点对比 ③ 需复核 ④ 匹配规则 ⑤ 说明）")
    return OUT


# ============================================================
# ⑩ 多模型对比（compare）：一份 Excel，真实值与各模型值并排
#    匹配规则与单模型报告完全同源——共用 pair_up()。
# ============================================================
def discover_batches():
    """本文件所在目录下所有含 truth.csv 的子文件夹 -> [(批次名, 目录)]"""
    out = []
    for d in sorted(os.listdir(BASE)):
        p = os.path.join(BASE, d)
        if os.path.isfile(os.path.join(p, "truth.csv")):
            out.append((d, p))
    return out


def discover_models(batches):
    """各批文件夹里 extracted_<模型>.csv 的模型名（文件名里的写法，斜杠已换成下划线）"""
    tags = set()
    for _, d in batches:
        for p in glob.glob(os.path.join(d, "extracted_*.csv")):
            tags.add(os.path.basename(p)[len("extracted_"):-len(".csv")])
    return sorted(tags, key=natural_key)


def collect(batches, models, x_tol):
    """返回 逐点长表, 匹配规则表, 缺漏统计"""
    long, rules, counts = [], [], []
    for bname, bdir in batches:
        tpath = os.path.join(bdir, "truth.csv")
        if not os.path.exists(tpath):
            raise SystemExit(f"{bdir} 下没有 truth.csv")
        T = load_truth(tpath)
        diff = load_diff(bdir)
        stacked = load_stacked(bdir)
        for m in models:
            epath = os.path.join(bdir, f"extracted_{file_tag(m)}.csv")
            if not os.path.exists(epath):
                print(f"  - {bname}/{m}：没跑这批（无 {os.path.basename(epath)}）")
                counts.append({"批次": bname, "模型": m, "状态": "缺提取结果",
                               "真值点": len(T), "配对": 0, "漏检": len(T), "多检": 0})
                continue
            E = load_extracted(epath)
            # 只评真值里有的图（2026-10-05：images\fig2.jpg 是 09-23 下午后放进来的，真值里没有，
            # 原来新跑的模型读了它就整图算「多检」，对比 gpt-6-astra 等早先跑的模型不公平）
            E = E[E["图片名"].map(lambda f: os.path.basename(str(f))).isin(set(T["图片名"]))]
            D, R, miss, extra = pair_up(E, T, x_tol, stacked)
            counts.append({"批次": bname, "模型": m, "状态": "已跑",
                           "真值点": len(T), "配对": len(D),
                           "漏检": len(miss), "多检": len(extra)})
            R.insert(0, "模型", m); R.insert(0, "批次", bname)
            rules.append(R)
            if D.empty:
                continue
            D = D.assign(批次=bname, 模型=m,
                         难度=D["图片名"].map(lambda f: diff.get(fig_no(f), "未定义")),
                         rel=pd.to_numeric(D["Y_相对误差%"], errors="coerce"))
            long.append(D)
            print(f"  {bname:6s} {m:14s} 配对 {len(D):4d}  漏检 {len(miss):3d}"
                  f"  多检 {len(extra):3d}  中位误差 {D['rel'].median():.3f}%")
    if not long:
        raise SystemExit("没有任何可用的提取结果")
    return (pd.concat(long, ignore_index=True),
            pd.concat(rules, ignore_index=True) if rules else pd.DataFrame(),
            pd.DataFrame(counts))


def build_wide(L, models):
    """一行一个真值点，各模型的值与误差并排"""
    key = ["批次", "难度", "图片名", "真值系列", "X_真值"]
    base = (L.drop_duplicates(key)[key + ["Y_真值", "误差±_真值", "显著性_真值"]]
            .rename(columns={"真值系列": "系列", "X_真值": "X", "Y_真值": "真实值",
                             "误差±_真值": "真值±", "显著性_真值": "真值字母"}))
    out = base
    for m in models:
        g = L[L["模型"] == m]
        if g.empty:
            out[f"{m}·值"] = np.nan
            out[f"{m}·误差%"] = np.nan
            continue
        v = (g.drop_duplicates(key).set_index(key)[["Y_提取", "rel", "显著性同层一致"]]
             .rename(columns={"Y_提取": f"{m}·值", "rel": f"{m}·误差%",
                              "显著性同层一致": f"{m}·字母对"}))
        out = out.merge(v.reset_index().rename(
            columns={"真值系列": "系列", "X_真值": "X"}),
            on=["批次", "难度", "图片名", "系列", "X"], how="left")
    out["_k"] = out["批次"] + "|" + out["图片名"].map(natural_key) + "|" + out["系列"].astype(str)
    return out.sort_values(["_k", "X"], kind="stable").drop(columns="_k").reset_index(drop=True)


def kpi_table(L, models, T_total, counts, tol_rel, tol_abs):
    rows = []
    for m in models:
        g = L[L["模型"] == m]
        # 只按这个模型实际跑过的批次计真值点和漏检（qwen / fig2table 只跑了柱图，
        # 不能把线图整批算成它们的漏检）
        c = counts[(counts["模型"] == m) & (counts["状态"] == "已跑")]
        nt = int(c["真值点"].sum()) or T_total
        if g.empty:
            rows.append({"模型": m, "状态": "未跑/无结果", "真值点": nt})
            continue
        r = g["rel"].dropna()
        ae = pd.to_numeric(g["Y_绝对误差"], errors="coerce").dropna()
        sg = g["显著性同层一致"].dropna()
        row = {
            "模型": m, "状态": "已跑", "覆盖批次": "+".join(c["批次"]),
            "真值点": nt, "配对点": len(g),
            "漏检": int(c["漏检"].sum()), "多检": int(c["多检"].sum()),
            "中位误差%": round(r.median(), 3),
            "平均误差%": round(r.mean(), 3),
            "最大误差%": round(r.max(), 2),
            "误差<1%": f"{int((r < 1).sum())}/{len(r)} ({(r < 1).mean()*100:.0f}%)",
            "误差<5%": f"{int((r < 5).sum())}/{len(r)} ({(r < 5).mean()*100:.0f}%)",
            "MAE": round(ae.mean(), 4),
            "RMSE": round(math.sqrt((ae ** 2).mean()), 4),
            "字母一致": (f"{int(sg.sum())}/{len(sg)} ({sg.mean()*100:.0f}%)"
                         if len(sg) else "无字母"),
        }
        if tol_rel is not None or tol_abs is not None:
            ok = pd.Series(True, index=g.index)
            if tol_abs is not None:
                ok &= pd.to_numeric(g["Y_绝对误差"], errors="coerce") <= tol_abs
            if tol_rel is not None:
                ok &= g["rel"] <= tol_rel
            ok = ok.fillna(False)
            row["达标率"] = f"{int(ok.sum())}/{nt} = {ok.sum()/nt*100:.1f}%"
        rows.append(row)
    K = pd.DataFrame(rows)
    return K.sort_values("中位误差%", na_position="last").reset_index(drop=True)


def breakdown(L, models, by):
    """按 批次 或 难度 分组的中位误差矩阵"""
    piv = L.pivot_table(index=by, columns="模型", values="rel", aggfunc="median")
    piv = piv.reindex(columns=[m for m in models if m in piv.columns])
    if by == "难度":
        piv = piv.reindex([k for k in ["简单", "中等", "难", "未定义"]
                           if k in piv.index])
    n = L.groupby(by)["rel"].size().rename("点数")
    return piv.round(3).join(n).reset_index()


def fig_matrix(L, models):
    piv = L.pivot_table(index=["批次", "难度", "图片名"], columns="模型",
                        values="rel", aggfunc="median")
    piv = piv.reindex(columns=[m for m in models if m in piv.columns]).round(3)
    piv = piv.reset_index()
    piv["_k"] = piv["批次"] + "|" + piv["图片名"].map(natural_key)
    return piv.sort_values("_k").drop(columns="_k").reset_index(drop=True)


def perf_table(batches, models):
    """从 results_<模型>.jsonl 统计速度与 token 用量（只认本脚本写的记录）"""
    import statistics
    rows = []
    for bname, bdir in batches:
        names = set(load_truth(os.path.join(bdir, "truth.csv"))["图片名"])
        for m in models:
            p = os.path.join(bdir, f"results_{file_tag(m)}.jsonl")
            if not os.path.exists(p):
                continue
            ok = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
            # 用量和耗时也只算真值里有的图，和打分口径一致；
            # qwen / fig2table 的旧记录格式不同、也不是 API 调用，不计
            ok = [r for r in ok if r.get("ok") and "panels" in (r.get("data") or {})
                  and os.path.basename(str(r.get("file", "")).replace("\\", "/")) in names]
            if not ok:
                continue
            secs = [r["sec"] for r in ok if r.get("sec") is not None]
            tok = [r["tokens"] for r in ok]
            rea = [r.get("reasoning_tokens") or 0 for r in ok]
            pin = [r.get("prompt_tokens") or 0 for r in ok]
            row = {
                "批次": bname, "模型": m, "成功张数": len(ok), "状态": "正常",
                "总token": sum(tok), "平均token/张": int(statistics.mean(tok)),
                "最少token": min(tok), "最多token": max(tok),
                "输入token/张": int(statistics.mean(pin)) if any(pin) else None,
                "reasoning/张": int(statistics.mean(rea)) if any(rea) else None,
                "reasoning占比%": (round(sum(rea) / max(sum(tok) - sum(pin), 1) * 100, 1)
                                   if any(rea) else None),
            }
            if secs:
                row.update({
                    "中位延迟s": round(statistics.median(secs), 1),
                    "最快s": round(min(secs), 1), "最慢s": round(max(secs), 1),
                    "API总耗时s": round(sum(secs), 1),
                    "并发4墙钟估计s": round(sum(secs) / 4, 1),
                })
            else:
                row["中位延迟s"] = None
            rows.append(row)
    P = pd.DataFrame(rows)
    if P.empty:
        return P, P
    # 跨批次合计
    agg = []
    for m in models:
        g = P[(P["模型"] == m) & (P["成功张数"] > 0)]
        if g.empty:
            continue
        n = int(g["成功张数"].sum())
        d = {"模型": m, "总张数": n, "总token": int(g["总token"].sum()),
             "平均token/张": int(g["总token"].sum() / n)}
        if g["中位延迟s"].notna().any():
            # 只除以记了耗时的张数（2026-10-05：gpt-6-astra 柱图那批早期结果没记耗时，原来按 40 张除，每张用时偏低）
            timed = g[g["中位延迟s"].notna()]
            nt = int(timed["成功张数"].sum())
            d["计时张数"] = nt
            d["中位延迟s"] = round(float(timed["中位延迟s"].median()), 1)
            d["API总耗时s"] = round(float(timed["API总耗时s"].sum()), 1)
            d["s/张(并发4)"] = round(float(timed["API总耗时s"].sum()) / 4 / nt, 2)
        if g["reasoning/张"].notna().any():
            d["reasoning/张"] = int(g["reasoning/张"].mean())
        agg.append(d)
    return P, pd.DataFrame(agg)


def cmd_compare(a):
    Font, PatternFill, get_column_letter = _styles()
    HEAD = PatternFill("solid", fgColor="305496")
    HF = Font(color="FFFFFF", bold=True)
    BEST = PatternFill("solid", fgColor="FFD966")      # 每行最优模型

    if a.batch:
        batches = []
        for b in a.batch:
            if "=" not in b:
                raise SystemExit(f"--batch 格式应为 名称=目录，收到: {b}")
            n, d = b.split("=", 1)
            batches.append((n.strip(), d.strip()))
    else:
        batches = discover_batches()
        if not batches:
            raise SystemExit(f"{BASE} 下没有含 truth.csv 的子文件夹，用 --batch 名称=目录 指定")
    models = a.models or discover_models(batches)
    out = a.out or os.path.join(BASE, "报告_多模型对比.xlsx")

    print("批次:", ", ".join(f"{n} -> {d}" for n, d in batches))
    print("模型:", ", ".join(models), "\n")
    L, R, counts = collect(batches, models, a.x_tol)
    print()

    W = build_wide(L, models)
    K = kpi_table(L, models, len(W), counts, a.tol_rel, a.tol_abs)
    B_batch = breakdown(L, models, "批次")
    B_diff = breakdown(L, models, "难度")
    FM = fig_matrix(L, models)

    PERF, PAGG = perf_table(batches, models)
    # 用户 2026-10-05：「报告加上用的时间和花费的token」——总览表直接带上用量和耗时，
    # 和 ⑥ 速度与用量 的「跨批次合计」是同一组数（各批次 results_<模型>.jsonl 里成功的那几次调用）
    if not PAGG.empty:
        use = [c for c in ("总token", "平均token/张", "reasoning/张", "计时张数", "中位延迟s", "API总耗时s", "s/张(并发4)")
               if c in PAGG.columns]
        K = K.merge(PAGG[["模型"] + use], on="模型", how="left")
    # 需复核：任一模型误差≥2%，或某模型跑了这批却没读出这个点（没跑的批次不算）
    ran = counts[counts["状态"] == "已跑"].groupby("模型")["批次"].apply(set).to_dict()
    flag = pd.Series(False, index=W.index)
    for m in models:
        k = f"{m}·误差%"
        if k in W.columns:
            flag |= W[k] >= 2
            flag |= W[k].isna() & W["批次"].isin(ran.get(m, set()))
    prob = W[flag].copy()

    with pd.ExcelWriter(out, engine="openpyxl") as w:
        K.to_excel(w, sheet_name="① 总览", index=False, startrow=2)
        r2 = len(K) + 6
        B_batch.to_excel(w, sheet_name="① 总览", index=False, startrow=r2)
        r3 = r2 + len(B_batch) + 4
        B_diff.to_excel(w, sheet_name="① 总览", index=False, startrow=r3)
        W.to_excel(w, sheet_name="② 逐点对比", index=False)
        FM.to_excel(w, sheet_name="③ 逐图对比", index=False)
        prob.to_excel(w, sheet_name="④ 需复核", index=False)
        R.to_excel(w, sheet_name="⑤ 匹配规则", index=False)
        if not PAGG.empty:
            PAGG.to_excel(w, sheet_name="⑥ 速度与用量", index=False, startrow=1)
            PERF.to_excel(w, sheet_name="⑥ 速度与用量", index=False,
                          startrow=len(PAGG) + 5)
        wb = w.book

        for ws in wb.worksheets:
            for c in ws[1]:
                if c.value:
                    c.fill, c.font = HEAD, HF
            ws.freeze_panes = "A2"
            for col in ws.columns:
                ln = max((len(str(c.value)) for c in col if c.value is not None),
                         default=8)
                ws.column_dimensions[get_column_letter(col[0].column)].width = \
                    min(max(ln + 2, 9), 42)

        ov = wb["① 总览"]
        ov["A1"] = "多模型横向对比报告"
        ov["A1"].font = Font(size=15, bold=True)
        ov["A2"] = ("按中位相对误差排序；颜色：绿<1% 浅绿<2% 黄<5% 红≥5%；"
                    "每行最优模型标金色")
        ov["A2"].font = Font(size=10, color="808080")
        for hr, title in ((3, None), (r2 + 1, "按批次 · 中位相对误差%"),
                          (r3 + 1, "按难度 · 中位相对误差%")):
            if title:
                ov.cell(hr - 1, 1).value = title
                ov.cell(hr - 1, 1).font = Font(size=12, bold=True)
            for c in ov[hr]:
                if c.value:
                    c.fill, c.font = HEAD, HF

        # KPI 表：中位/平均/最大误差上色
        cid = {c.value: i + 1 for i, c in enumerate(ov[3]) if c.value}
        for r in range(4, 4 + len(K)):
            for nm in ("中位误差%", "平均误差%", "最大误差%"):
                if nm in cid:
                    cell = ov.cell(r, cid[nm])
                    cell.fill = PatternFill("solid", fgColor=band(cell.value))
            ov.cell(r, 1).font = Font(bold=(r == 4))     # 第一名加粗

        # 两张分组矩阵：每行最优标金色
        for hr, tbl in ((r2 + 1, B_batch), (r3 + 1, B_diff)):
            hid = {c.value: i + 1 for i, c in enumerate(ov[hr]) if c.value}
            mcols = [m for m in models if m in hid]
            for i in range(len(tbl)):
                rr = hr + 1 + i
                vals = {m: ov.cell(rr, hid[m]).value for m in mcols}
                vals = {k: v for k, v in vals.items() if isinstance(v, (int, float))}
                for m in mcols:
                    ov.cell(rr, hid[m]).fill = PatternFill(
                        "solid", fgColor=band(ov.cell(rr, hid[m]).value))
                if vals:
                    ov.cell(rr, hid[min(vals, key=vals.get)]).fill = BEST

        # 逐点对比：各模型误差列上色 + 难度列
        ws = wb["② 逐点对比"]
        cid = {c.value: i + 1 for i, c in enumerate(ws[1]) if c.value}
        for r in range(2, ws.max_row + 1):
            if "难度" in cid:
                dc = ws.cell(r, cid["难度"])
                dc.fill = PatternFill("solid", fgColor=DIFF_FILL.get(dc.value, GREY))
            vals = {}
            for m in models:
                k = f"{m}·误差%"
                if k in cid:
                    v = ws.cell(r, cid[k]).value
                    ws.cell(r, cid[k]).fill = PatternFill("solid", fgColor=band(v))
                    if isinstance(v, (int, float)):
                        vals[k] = v
            if vals:
                ws.cell(r, cid[min(vals, key=vals.get)]).fill = BEST

        # 逐图对比：整表上色 + 每行最优
        ws = wb["③ 逐图对比"]
        cid = {c.value: i + 1 for i, c in enumerate(ws[1]) if c.value}
        for r in range(2, ws.max_row + 1):
            if "难度" in cid:
                dc = ws.cell(r, cid["难度"])
                dc.fill = PatternFill("solid", fgColor=DIFF_FILL.get(dc.value, GREY))
            vals = {}
            for m in models:
                if m in cid:
                    v = ws.cell(r, cid[m]).value
                    ws.cell(r, cid[m]).fill = PatternFill("solid", fgColor=band(v))
                    if isinstance(v, (int, float)):
                        vals[m] = v
            if vals:
                ws.cell(r, cid[min(vals, key=vals.get)]).fill = BEST

        if not PAGG.empty:
            pf = wb["⑥ 速度与用量"]
            pf["A1"] = "跨批次合计"; pf["A1"].font = Font(size=13, bold=True)
            for c in pf[2]:
                if c.value:
                    c.fill, c.font = HEAD, HF
            hr = len(PAGG) + 5
            pf.cell(hr, 1).value = "分批次明细"
            pf.cell(hr, 1).font = Font(size=13, bold=True)
            for c in pf[hr + 1]:
                if c.value:
                    c.fill, c.font = HEAD, HF
            for col in pf.columns:
                ln = max((len(str(c.value)) for c in col if c.value is not None),
                         default=8)
                pf.column_dimensions[get_column_letter(col[0].column)].width = \
                    min(max(ln + 2, 11), 20)

        note = wb.create_sheet("⑦ 说明")
        lines = [
            "多模型横向对比 — 指标含义与使用边界", "",
            f"批次: " + "; ".join(f"{n} -> {os.path.basename(d) or d}" for n, d in batches),
            f"模型: " + ", ".join(models),
            f"真值点合计: {len(W)}", "",
            "只统计真值里有的图：文件夹里真值没有的图不算多检，也不计入 token 和耗时。",
            "只跑了部分批次的模型（如 qwen3.8-27b、fig2table 只跑了柱图），真值点、漏检、达标率都只按它跑过的批次算，"
            "见「① 总览」的「覆盖批次」列；不同覆盖的模型之间比中位误差要看「按批次」那张表。",
            "「① 总览」后几列的 token 与耗时与「⑥ 速度与用量」的跨批次合计同口径；耗时是各次 API 调用的耗时之和，"
            "实际墙钟时间约为它除以并发数 4。只统计本脚本走 API 写下的记录（qwen / fig2table 的旧记录不计）。",
            "相对误差% = |模型值 − 真实值| / |真实值| × 100%；真实值为 0 时记 NA。",
            "MAE / RMSE 为原始单位下的误差，不同图量纲不同，不可跨图直接比较。",
            "颜色：绿 <1%，浅绿 1~2%，黄 2~5%，红 ≥5%；每行最优模型标金色。",
            "",
            "匹配规则（见「⑤ 匹配规则」，逐条可审计）",
            "  与单模型报告（eval）共用同一个 pair_up() 函数，规则完全一致：",
            "  系列级：①名称完全匹配 ②互为子串 ③高相似度 ④两侧各剩一个则唯一对应",
            "  点级：①两侧纯数值→最近邻(容差=真值跨度的 x-tol%，且不超过最小相邻间距的一半)",
            "        ②带单位后缀的数值标签先剥离后缀  ③否则分类标签精确匹配 + 相似度兜底",
            "  任何情况下都不按行号配对。",
            "  堆叠柱（批次文件夹 stacked.csv 里列出的图）按段高度评：模型若给的是每段顶端的累计坐标"
            "（同一 X 自下而上读数都不减，只看模型输出判断），先换算成段高度再比，见「单位处理」列。",
            "",
            "对真实数据的使用边界",
            "  单位统一只按双方各自声明的单位换算，绝不依据真实值修正模型输出。",
            "  提取（run / retry / one）完全不读取真值文件，真值只在 eval / compare 里读。",
            "",
            "可信度说明",
            "  以上均为在本批真值点上的经验指标，描述模型输出与该批真值的符合程度。",
            "  达标率不是统计置信度，模型自评的 confidence 也不是。",
            "  模型之间的名次差异在样本量有限时可能不稳定，跨批次结论需谨慎。",
        ]
        for i, t in enumerate(lines):
            note.cell(i + 1, 1).value = t
        note["A1"].font = Font(size=14, bold=True)
        note.column_dimensions["A"].width = 84

    print("=" * 78)
    print(K.to_string(index=False))
    print("=" * 78)
    print(f"报告: {os.path.abspath(out)}")
    if not PAGG.empty:
        print()
        print(PAGG.to_string(index=False))
    print("  ① 总览 ② 逐点对比 ③ 逐图对比 ④ 需复核 ⑤ 匹配规则"
          " ⑥ 速度与用量 ⑦ 说明")


# ============================================================
# ⑪ 合成图（synth）：随机数据 + 随机外观的图 + 零误差真值，直接生成一个批次文件夹
#    （原 实验方案\gen_synth.py，设计见 PROTOCOL.md 1.2 节）
#  * 数据完全随机，轴标签与单位故意错配 —— 堵死模型靠常识反推量级的路
#  * 外观全随机：图类型/配色/柱宽/线宽/点形/线型/字体/字号/网格/边框/画布尺寸/DPI
#  * 真值 = 绘图时的原始数组，零误差，不经任何数字化
#  * 30 张中 6 张故意做成"不可提取"，用于测模型敢不敢拒答
#  两个刻意的设计约束，改的时候别改掉：bar_values() 的柱高下限随机化、place_legend() 先留顶部空白。
#  matplotlib 只在 synth 里才导入（paper_pipeline import 本文件时用不到）。
# ============================================================

# 属性名与单位故意分开抽、随机配对，产生 "Viscosity / mol·L⁻¹" 这类无意义组合
PROPERTIES = [
    "Viscosity", "Turbidity", "Water holding capacity", "Surface hydrophobicity",
    "Emulsifying activity", "Zeta potential", "Foaming capacity", "Hardness",
    "Thermal conductivity", "Free radical scavenging", "Solubility index",
    "Particle diameter", "Storage modulus", "Yield stress", "Oxidation index",
    "Gel strength", "Colour difference", "Peroxide value", "Total phenolics",
]
# 单位一律用 ASCII 安全写法：部分 Windows 字体缺上标减号/上标数字的字形，
# 会渲染成豆腐块，反而给模型制造了非预期的干扰。
UNITS = [
    "mPa s", "mol/L", "g/kg", "%", "mV", "kJ/mol", "nm", "Pa",
    "mg/g", "umol/L", "N", "W/(m K)", "a.u.", "cm2/g", "meq/kg",
    "g/100 g", "kPa", "min", "S/m", "AU",
]
X_LABELS_CAT = [
    "Treatment", "Sample", "Formulation", "Storage time", "Group",
    "Condition", "Batch", "Concentration level",
]
CAT_POOLS = [
    ["Control", "P", "P-4", "P-8", "P-12", "P-16"],
    ["0 h", "2 h", "4 h", "8 h", "12 h", "24 h"],
    ["CK", "T1", "T2", "T3", "T4", "T5"],
    ["A", "B", "C", "D", "E", "F"],
    ["0%", "5%", "10%", "15%", "20%", "25%"],
]
X_LABELS_NUM = [
    "Time", "Temperature", "Concentration", "Frequency", "Shear rate",
    "Wavelength", "pH", "Strain",
]

MARKERS = ["o", "s", "^", "v", "D", "<", ">", "p", "*", "h"]
LINESTYLES = ["-", "--", "-.", ":"]
HATCHES = [None, "//", "\\\\", "xx", "..", "++", "oo"]

PALETTES = [
    ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"],
    ["#4c72b0", "#dd8452", "#55a868", "#c44e52"],
    ["#000000", "#555555", "#999999", "#cccccc"],   # 灰度：故意做成难区分
    ["#264653", "#2a9d8f", "#e9c46a", "#e76f51"],
    ["#003f5c", "#58508d", "#bc5090", "#ff6361"],
    ["#8c510a", "#d8b365", "#5ab4ac", "#01665e"],
]

FONT_CANDIDATES = [
    "DejaVu Sans", "Arial", "Times New Roman", "Calibri",
    "Georgia", "Verdana", "Tahoma", "Courier New", "Cambria",
]


def available_fonts():
    from matplotlib import font_manager
    have = {f.name for f in font_manager.fontManager.ttflist}
    got = [f for f in FONT_CANDIDATES if f in have]
    return got or ["DejaVu Sans"]


def rand_scale(rng):
    """随机量级：1e-3 ~ 1e5，覆盖食品期刊里常见的各种数量级。"""
    return 10.0 ** rng.integers(-3, 6)


def trend(rng, n):
    """随机基础函数 + 噪声。用函数只为给出大致走势，噪声和随机量级会让
    模型无法靠识别函数形态来倒推数值。"""
    x = np.linspace(0, 1, n)
    kind = rng.choice(["sine", "log", "linear", "gauss", "exp"])
    if kind == "sine":
        y = np.sin(2 * np.pi * rng.uniform(0.4, 1.6) * x + rng.uniform(0, 6.3))
    elif kind == "log":
        y = np.log(x + rng.uniform(0.05, 0.4))
    elif kind == "linear":
        y = rng.uniform(-1, 1) * x
    elif kind == "gauss":
        y = np.exp(-((x - rng.uniform(0.2, 0.8)) ** 2) / rng.uniform(0.02, 0.2))
    else:
        y = np.exp(rng.uniform(-2, 2) * x)
    y = (y - y.min()) / (np.ptp(y) + 1e-12)               # 归一到 0~1
    y = y + rng.normal(0, rng.uniform(0.01, 0.10), n)      # 加噪
    return np.clip(y, 0.02, 1.0)


def bar_values(rng, k, scale):
    """生成一组柱高。

    关键：随机抽一个「最矮柱 / 最高柱」比值 floor。不控制它的话，trend() 的
    下限会让每张柱状图都出现一根极矮的柱，于是全部图都落进 D3（矮柱是已知的
    像素分辨率死角），难度分布失衡。这里约 1/3 的图故意留矮柱，其余不留。
    """
    floor = float(rng.choice([0.02, 0.06, 0.11,            # 矮柱风险组 (~1/3)
                              0.20, 0.30, 0.45, 0.55, 0.65, 0.75]))
    y = trend(rng, k)
    y = (y - y.min()) / (np.ptp(y) + 1e-12)                # 归一到 0~1
    return (floor + (1.0 - floor) * y) * scale


def sig_letters(values, errs):
    """按误差棒是否重叠生成显著性字母（会自然产生 'ab'、'bc' 这类多字母）。"""
    n = len(values)
    order = np.argsort(-np.asarray(values))
    groups = []
    for idx in order:
        joined = False
        for g in groups:
            ok = all(
                values[idx] + errs[idx] >= values[j] - errs[j]
                and values[j] + errs[j] >= values[idx] - errs[idx]
                for j in g
            )
            if ok:
                g.append(idx)
                joined = True
        if not joined:
            groups.append([idx])
    out = [""] * n
    for gi, g in enumerate(groups):
        for idx in g:
            out[idx] += string.ascii_lowercase[gi % 26]
    return ["".join(sorted(s)) for s in out]


def style(rng, fonts):
    """随机一套外观参数。"""
    return dict(
        palette=list(rng.permutation(PALETTES[rng.integers(len(PALETTES))])),
        font=fonts[rng.integers(len(fonts))],
        fontsize=int(rng.integers(8, 15)),
        figw=float(rng.uniform(4.2, 8.5)),
        figh=float(rng.uniform(3.2, 6.0)),
        dpi=int(rng.choice([100, 120, 150, 200, 300])),
        grid=bool(rng.random() < 0.45),
        spines_all=bool(rng.random() < 0.3),      # 是否保留上/右边框
        lw=float(rng.uniform(0.8, 3.0)),
        ms=float(rng.uniform(4, 11)),
        barwidth=float(rng.uniform(0.45, 0.9)),
        capsize=float(rng.choice([0, 2, 3, 5])),
        hatch=bool(rng.random() < 0.25),
        # 图例只走 best / 图外两种。曾用随机固定方位，结果图例整块盖住柱子，
        # 那些点在真值表里却标着「可提取」，等于给所有模型埋读不出的题。
        legend_above=bool(rng.random() < 0.35),
    )


def place_legend(ax, st, handles=None, labels=None, ncol_max=3):
    """放图例前先留出顶部空白，保证图例不会遮挡任何数据。"""
    y0, y1 = ax.get_ylim()
    ax.set_ylim(y0, y1 + (y1 - y0) * 0.30)
    kw = dict(fontsize=st["fontsize"] - 2)
    args = (handles, labels) if handles is not None else ()
    if st["legend_above"]:
        n = len(labels) if labels is not None else len(ax.get_legend_handles_labels()[0])
        ax.legend(*args, loc="lower center", bbox_to_anchor=(0.5, 1.01),
                  ncol=min(max(n, 1), ncol_max), frameon=False, **kw)
    else:
        ax.legend(*args, loc="best", framealpha=0.9, **kw)


def apply_style(ax, st, xlab, ylab):
    ax.set_xlabel(xlab, fontsize=st["fontsize"], fontfamily=st["font"])
    ax.set_ylabel(ylab, fontsize=st["fontsize"], fontfamily=st["font"])
    ax.tick_params(labelsize=st["fontsize"] - 1)
    for t in ax.get_xticklabels() + ax.get_yticklabels():
        t.set_fontfamily(st["font"])
    if st["grid"]:
        ax.grid(True, alpha=0.3, linestyle=":")
        ax.set_axisbelow(True)
    if not st["spines_all"]:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)


def axlabel(rng):
    """属性名与单位随机配对（故意错配）。"""
    p = PROPERTIES[rng.integers(len(PROPERTIES))]
    u = UNITS[rng.integers(len(UNITS))]
    return p, u, f"{p} ({u})"


# ---------- 各图种绘制：每个函数返回 (truth_rows, meta_extra) ----------
# truth_rows: dict(panel, series, axis, x, value, err_low, err_high, sig)
def draw_bar(fig, rng, st, grouped=False):
    ax = fig.add_subplot(111)
    cats = CAT_POOLS[rng.integers(len(CAT_POOLS))]
    k = int(rng.integers(4, 7))
    cats = list(cats[:k])
    ns = int(rng.integers(2, 5)) if grouped else 1
    scale = rand_scale(rng)
    prop, unit, ylab = axlabel(rng)
    xlab = X_LABELS_CAT[rng.integers(len(X_LABELS_CAT))]

    rows = []
    idx = np.arange(k)
    w = st["barwidth"] / ns
    allvals = []
    for s in range(ns):
        vals = bar_values(rng, k, scale) * rng.uniform(0.6, 1.0)
        errs = vals * rng.uniform(0.02, 0.12)
        letters = sig_letters(vals, errs)
        sname = f"{prop} {s+1}" if ns > 1 else prop
        off = (s - (ns - 1) / 2) * w
        ax.bar(idx + off, vals, width=w * 0.92,
               yerr=errs, capsize=st["capsize"],
               color=st["palette"][s % len(st["palette"])],
               edgecolor="black", linewidth=0.6,
               hatch=HATCHES[(s + 1) % len(HATCHES)] if st["hatch"] else None,
               label=sname)
        if rng.random() < 0.75:                     # 75% 的图带显著性字母
            for i, (v, e, L) in enumerate(zip(vals, errs, letters)):
                ax.text(idx[i] + off, v + e + 0.02 * scale, L,
                        ha="center", fontsize=st["fontsize"] - 2,
                        fontfamily=st["font"])
        for i, c in enumerate(cats):
            rows.append(dict(panel="", series=sname, axis="left", x=c,
                             value=vals[i], err_low=vals[i] - errs[i],
                             err_high=vals[i] + errs[i], sig=letters[i]))
        allvals.extend(vals)

    ax.set_xticks(idx)
    ax.set_xticklabels(cats, fontfamily=st["font"])
    apply_style(ax, st, xlab, ylab)
    if ns > 1:
        place_legend(ax, st)
    ymax = ax.get_ylim()[1]
    return rows, dict(chart_type="grouped_bar" if grouped else "bar",
                      n_series=ns, n_points=k * ns, dual_axis=0, n_panel=1,
                      min_bar_ratio=float(min(allvals) / ymax))


def draw_stacked_bar(fig, rng, st):
    ax = fig.add_subplot(111)
    cats = list(CAT_POOLS[rng.integers(len(CAT_POOLS))][:int(rng.integers(4, 7))])
    k, ns = len(cats), int(rng.integers(2, 4))
    scale = rand_scale(rng)
    prop, unit, ylab = axlabel(rng)
    xlab = X_LABELS_CAT[rng.integers(len(X_LABELS_CAT))]

    rows, bottom, allvals = [], np.zeros(k), []
    for s in range(ns):
        vals = bar_values(rng, k, scale) * rng.uniform(0.3, 0.6)
        sname = f"Fraction {string.ascii_uppercase[s]}"
        ax.bar(np.arange(k), vals, bottom=bottom, width=st["barwidth"],
               color=st["palette"][s % len(st["palette"])],
               edgecolor="black", linewidth=0.6, label=sname)
        bottom += vals
        for i, c in enumerate(cats):
            # 真值记「分段高度」，不是累计值
            rows.append(dict(panel="", series=sname, axis="left", x=c,
                             value=vals[i], err_low="", err_high="", sig=""))
        allvals.extend(vals)

    ax.set_xticks(np.arange(k))
    ax.set_xticklabels(cats, fontfamily=st["font"])
    apply_style(ax, st, xlab, ylab)
    place_legend(ax, st)
    return rows, dict(chart_type="stacked_bar", n_series=ns, n_points=k * ns,
                      dual_axis=0, n_panel=1,
                      min_bar_ratio=float(min(allvals) / ax.get_ylim()[1]))


def draw_xy(fig, rng, st, mode):
    """mode: scatter / line / line_points"""
    ax = fig.add_subplot(111)
    ns = int(rng.integers(1, 5))
    n = int(rng.integers(6, 16))
    ysc, xsc = rand_scale(rng), rand_scale(rng)
    prop, unit, ylab = axlabel(rng)
    xp = X_LABELS_NUM[rng.integers(len(X_LABELS_NUM))]
    xu = UNITS[rng.integers(len(UNITS))]
    xlab = f"{xp} ({xu})"

    # x 间距：均匀 or 随机
    if rng.random() < 0.5:
        xs = np.linspace(0, 1, n) * xsc
    else:
        xs = np.sort(rng.uniform(0, 1, n)) * xsc

    rows = []
    for s in range(ns):
        ys = trend(rng, n) * ysc
        sname = f"{prop} {s+1}" if ns > 1 else prop
        c = st["palette"][s % len(st["palette"])]
        if mode == "scatter":
            ax.plot(xs, ys, linestyle="none", marker=MARKERS[s % len(MARKERS)],
                    markersize=st["ms"], color=c, label=sname)
        elif mode == "line":
            ax.plot(xs, ys, linestyle=LINESTYLES[s % len(LINESTYLES)],
                    linewidth=st["lw"], color=c, label=sname)
        else:
            ax.plot(xs, ys, linestyle=LINESTYLES[s % len(LINESTYLES)],
                    marker=MARKERS[s % len(MARKERS)], markersize=st["ms"],
                    linewidth=st["lw"], color=c, label=sname)
        for xv, yv in zip(xs, ys):
            rows.append(dict(panel="", series=sname, axis="left", x=float(xv),
                             value=float(yv), err_low="", err_high="", sig=""))

    apply_style(ax, st, xlab, ylab)
    if ns > 1:
        place_legend(ax, st)
    return rows, dict(chart_type=mode, n_series=ns, n_points=n * ns,
                      dual_axis=0, n_panel=1, min_bar_ratio="")


def draw_dual_axis(fig, rng, st):
    """双 Y 轴 —— 已知最易触发『右轴系列按左轴刻度读』的串扰错误。"""
    ax = fig.add_subplot(111)
    ax2 = ax.twinx()
    cats = list(CAT_POOLS[rng.integers(len(CAT_POOLS))][:int(rng.integers(4, 7))])
    k = len(cats)
    pL, uL, ylabL = axlabel(rng)
    pR, uR, ylabR = axlabel(rng)
    xlab = X_LABELS_CAT[rng.integers(len(X_LABELS_CAT))]
    sL, sR = rand_scale(rng), rand_scale(rng)

    vL = bar_values(rng, k, sL)
    eL = vL * rng.uniform(0.02, 0.10)
    vR = trend(rng, k) * sR
    letters = sig_letters(vL, eL)

    ax.bar(np.arange(k), vL, width=st["barwidth"], yerr=eL,
           capsize=st["capsize"], color=st["palette"][0],
           edgecolor="black", linewidth=0.6, label=pL)
    ax2.plot(np.arange(k), vR, marker=MARKERS[rng.integers(len(MARKERS))],
             markersize=st["ms"], linewidth=st["lw"],
             color=st["palette"][1], label=pR)

    rows = []
    for i, c in enumerate(cats):
        rows.append(dict(panel="", series=pL, axis="left", x=c, value=vL[i],
                         err_low=vL[i] - eL[i], err_high=vL[i] + eL[i],
                         sig=letters[i]))
        rows.append(dict(panel="", series=pR, axis="right", x=c, value=vR[i],
                         err_low="", err_high="", sig=""))

    ax.set_xticks(np.arange(k))
    ax.set_xticklabels(cats, fontfamily=st["font"])
    apply_style(ax, st, xlab, ylabL)
    ax2.set_ylabel(ylabR, fontsize=st["fontsize"], fontfamily=st["font"])
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax2.set_ylim(ax2.get_ylim()[0],
                 ax2.get_ylim()[1] + np.ptp(ax2.get_ylim()) * 0.30)
    place_legend(ax, st, h1 + h2, l1 + l2, ncol_max=2)
    return rows, dict(chart_type="dual_axis", n_series=2, n_points=k * 2,
                      dual_axis=1, n_panel=1,
                      min_bar_ratio=float(min(vL) / ax.get_ylim()[1]))


def draw_multi_panel(fig, rng, st):
    """双 panel，共用一套图例 —— 考模型能不能把 panel 分开报。"""
    axes = fig.subplots(1, 2)
    ns = int(rng.integers(1, 4))
    rows, allvals = [], []
    for pi, ax in enumerate(axes):
        tag = string.ascii_uppercase[pi]
        cats = list(CAT_POOLS[rng.integers(len(CAT_POOLS))][:int(rng.integers(4, 6))])
        k = len(cats)
        scale = rand_scale(rng)
        prop, unit, ylab = axlabel(rng)
        xlab = X_LABELS_CAT[rng.integers(len(X_LABELS_CAT))]
        w = st["barwidth"] / ns
        for s in range(ns):
            vals = bar_values(rng, k, scale)
            errs = vals * rng.uniform(0.02, 0.10)
            letters = sig_letters(vals, errs)
            sname = f"{prop} {s+1}" if ns > 1 else prop
            ax.bar(np.arange(k) + (s - (ns - 1) / 2) * w, vals, width=w * 0.9,
                   yerr=errs, capsize=st["capsize"],
                   color=st["palette"][s % len(st["palette"])],
                   edgecolor="black", linewidth=0.5,
                   label=sname if pi == 0 else None)
            for i, c in enumerate(cats):
                rows.append(dict(panel=tag, series=sname, axis="left", x=c,
                                 value=vals[i], err_low=vals[i] - errs[i],
                                 err_high=vals[i] + errs[i], sig=letters[i]))
            allvals.extend(vals)
        ax.set_xticks(np.arange(k))
        ax.set_xticklabels(cats, fontfamily=st["font"])
        apply_style(ax, st, xlab, ylab)
        ax.set_title(f"({tag})", loc="left", fontsize=st["fontsize"],
                     fontfamily=st["font"])
    if ns > 1:
        place_legend(axes[0], st, ncol_max=2)
    return rows, dict(chart_type="multi_panel", n_series=ns, n_points=len(rows),
                      dual_axis=0, n_panel=2, min_bar_ratio="")


def draw_broken(fig, rng, st, flavor):
    """故意做成人工也无法提取的图。真值为空，模型正确行为是拒答。"""
    ax = fig.add_subplot(111)
    cats = list(CAT_POOLS[rng.integers(len(CAT_POOLS))][:5])
    k = len(cats)
    scale = rand_scale(rng)
    vals = trend(rng, k) * scale
    prop, unit, ylab = axlabel(rng)

    if flavor == "no_axis":
        ax.bar(np.arange(k), vals, width=st["barwidth"], color=st["palette"][0])
        ax.set_axis_off()
        reason = "坐标轴与刻度完全缺失"

    elif flavor == "scrambled_ticks":
        ax.bar(np.arange(k), vals, width=st["barwidth"], color=st["palette"][0],
               edgecolor="black")
        ticks = ax.get_yticks()
        shuffled = list(rng.permutation([f"{t:.3g}" for t in ticks]))
        ax.set_yticks(ticks)
        ax.set_yticklabels(shuffled)       # 刻度数字乱序 → 无法建立映射
        ax.set_xticks(np.arange(k)); ax.set_xticklabels(cats)
        apply_style(ax, st, "Treatment", ylab)
        reason = "Y 轴刻度数字乱序，无法建立像素-数值映射"

    elif flavor == "no_ticklabels":
        ax.plot(np.linspace(0, 1, 12), trend(rng, 12), marker="o",
                color=st["palette"][0])
        ax.set_xticklabels([]); ax.set_yticklabels([])
        apply_style(ax, st, "Time", ylab)
        reason = "两轴均无刻度数字"

    elif flavor == "occluded":
        c = st["palette"][0]
        ax.bar(np.arange(k), vals, width=0.9, color=c, edgecolor=c)
        ax.bar(np.arange(k), vals * rng.uniform(0.5, 0.95), width=0.9,
               color=c, edgecolor=c)     # 同色完全覆盖，两系列不可分辨
        ax.set_xticks(np.arange(k)); ax.set_xticklabels(cats)
        apply_style(ax, st, "Sample", ylab)
        ax.legend(["Series 1", "Series 2"], fontsize=st["fontsize"] - 2,
                  loc="best", framealpha=0.9)
        reason = "两个系列同色完全重叠，无法分辨"

    elif flavor == "no_legend":
        for s in range(4):
            ax.plot(np.linspace(0, 1, 12), trend(rng, 12),
                    color=PALETTES[2][s], linewidth=st["lw"])
        apply_style(ax, st, "Time", ylab)
        reason = "4 条灰度相近曲线且无图例，系列无法归属"

    else:  # missing_axis_label
        ax.bar(np.arange(k), vals, width=st["barwidth"],
               color=st["palette"][0], edgecolor="black")
        ax.set_xticks(np.arange(k)); ax.set_xticklabels(cats)
        yt = ax.get_yticks()
        ax.set_yticks(yt)
        ax.set_yticklabels([f"{t:.3g}" for t in yt])
        ax.set_ylabel("")                  # 纵轴无标签无单位
        ax.set_xlabel("")
        reason = "纵轴无标签无单位，数值含义不明"

    return [], dict(chart_type=f"broken_{flavor}", n_series="", n_points=0,
                    dual_axis=0, n_panel=1, min_bar_ratio="",
                    reject_reason=reason)


# 24 张可提取 + 6 张不可提取
SYNTH_PLAN = (
    ["bar"] * 5 + ["grouped_bar"] * 4 + ["stacked_bar"] * 2
    + ["scatter"] * 3 + ["line"] * 3 + ["line_points"] * 3
    + ["dual_axis"] * 2 + ["multi_panel"] * 2
    + ["broken:no_axis", "broken:scrambled_ticks", "broken:no_ticklabels",
       "broken:occluded", "broken:no_legend", "broken:missing_axis_label"]
)
SYNTH_DIFF = {"D1": "简单", "D2": "中等", "D3": "难"}


def synth_difficulty(m):
    """按结构特征自动定难度 D1/D2/D3，人工可在 meta.csv / difficulty.csv 里覆盖。"""
    if str(m["chart_type"]).startswith("broken"):
        return "D3"
    ns = m["n_series"] or 1
    mbr = m["min_bar_ratio"]
    hard = (m["dual_axis"] == 1 or m["n_panel"] > 1
            or (mbr != "" and float(mbr) < 0.15))
    if hard:
        return "D3"
    return "D2" if int(ns) >= 2 else "D1"


def cmd_synth(a):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = a.out or os.path.join(BASE, "合成图")
    if os.path.isdir(out) and os.listdir(out):
        raise SystemExit(f"{out} 已存在且不是空的：换个 --out，或先把它挪走")
    os.makedirs(out, exist_ok=True)

    rng = np.random.default_rng(a.seed)
    random.seed(a.seed)
    fonts = available_fonts()

    n = a.n
    plan = SYNTH_PLAN[:n] if n <= len(SYNTH_PLAN) else SYNTH_PLAN + SYNTH_PLAN[:n - len(SYNTH_PLAN)]
    plan = list(rng.permutation(plan))       # 打乱，避免文件名与图类型相关

    truth_rows, meta_rows = [], []
    for i, kind in enumerate(plan, 1):
        st = style(rng, fonts)
        fig = plt.figure(figsize=(st["figw"], st["figh"]), dpi=st["dpi"])
        fname = f"S{i:02d}.png"

        if kind.startswith("broken:"):
            rows, meta = draw_broken(fig, rng, st, kind.split(":", 1)[1])
        elif kind == "bar":
            rows, meta = draw_bar(fig, rng, st, grouped=False)
        elif kind == "grouped_bar":
            rows, meta = draw_bar(fig, rng, st, grouped=True)
        elif kind == "stacked_bar":
            rows, meta = draw_stacked_bar(fig, rng, st)
        elif kind == "dual_axis":
            rows, meta = draw_dual_axis(fig, rng, st)
        elif kind == "multi_panel":
            rows, meta = draw_multi_panel(fig, rng, st)
        else:
            rows, meta = draw_xy(fig, rng, st, kind)

        fig.tight_layout()
        fig.savefig(os.path.join(out, fname), dpi=st["dpi"], facecolor="white")
        plt.close(fig)

        for r in rows:
            r["file"] = fname
            truth_rows.append(r)

        meta.setdefault("reject_reason", "")
        meta_rows.append(dict(
            file=fname, publisher="synthetic", journal="synthetic", year="",
            chart_type=meta["chart_type"], n_series=meta["n_series"],
            n_points=meta["n_points"], dual_axis=meta["dual_axis"],
            n_panel=meta["n_panel"], min_bar_ratio=meta["min_bar_ratio"],
            difficulty=synth_difficulty(meta),
            extractable=0 if str(meta["chart_type"]).startswith("broken") else 1,
            reject_reason=meta["reject_reason"],
            px_w=int(round(st["figw"] * st["dpi"])),
            px_h=int(round(st["figh"] * st["dpi"])),
            dpi=st["dpi"], font=st["font"], truth_uncertainty=0.0,
        ))
        print(f"  {fname}  {meta['chart_type']:<26} {len(rows):>3} pts")

    # truth.csv 与 truth 子命令同一套列，run / eval / compare 直接能用；
    # 误差± = 误差棒半宽（合成图误差棒对称），另附「轴」列（left / right）
    with open(os.path.join(out, "truth.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["图片名", "子图", "系列", "X类别/数值", "Y值", "误差±", "显著性", "轴"])
        for r in truth_rows:
            pm = "" if r["err_low"] == "" else (r["err_high"] - r["err_low"]) / 2
            w.writerow([r["file"], r["panel"], r["series"], r["x"], r["value"], pm, r["sig"], r["axis"]])
    with open(os.path.join(out, "difficulty.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["图片名", "难度"])
        for m in meta_rows:
            w.writerow([m["file"], SYNTH_DIFF[m["difficulty"]]])
    mcols = ["file", "publisher", "journal", "year", "chart_type", "n_series",
             "n_points", "dual_axis", "n_panel", "min_bar_ratio", "difficulty",
             "extractable", "reject_reason", "px_w", "px_h", "dpi", "font",
             "truth_uncertainty"]
    with open(os.path.join(out, "meta.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=mcols)
        w.writeheader()
        w.writerows(meta_rows)

    nb = sum(1 for m in meta_rows if m["extractable"] == 0)
    print(f"\n完成：{len(meta_rows)} 张图（{len(meta_rows)-nb} 可提取 / {nb} 不可提取）"
          f"，{len(truth_rows)} 条真值")
    print(f"输出目录：{out}（truth.csv / difficulty.csv / meta.csv）")
    print(f"seed={a.seed}（同 seed 可完全复现这批图）")


# ============================================================
# ⑫ 选图配额表（plan）：90 个待填槽位（每刊 30），把配额固化下来
#    （原 实验方案\make_selection_plan.py，设计见 PROTOCOL.md 1.1 节）
#    配额三个维度同时约束：期刊 × 年份档 × 图类型。筛图时对着这张表填 DOI / 图号即可，
#    填满就停——避免"看见好图就收"的选择偏倚。
#    年份规则：2016 年后的新图占 70%（63 张），2016 年前占 30%（27 张）。
#    Food Frontiers 创刊于 2020 年 3 月，27 张老图全部由 JAFC 与 Food Hydrocolloids 承担。
# ============================================================
# task: full    = 全部数据点逐点提取（主评测集）
#       feature = 连续曲线，只提取特征点（峰位/峰高/交点/平台值）
#       reject  = 预期不可提取，只评"敢不敢拒答"
JOURNALS = {
    "JAFC": dict(
        publisher="ACS", started=1953,
        # 化学分析导向：理化指标柱状图为主，兼有光谱/色谱与动力学曲线
        types=[
            ("bar",             6, "full",    "D1"),
            ("grouped_bar",     6, "full",    "D2"),
            ("scatter_line",    5, "full",    "D1"),
            ("dual_axis",       3, "full",    "D3"),
            ("multi_panel",     4, "full",    "D3"),
            ("semilog_kinetic", 2, "full",    "D3"),
            ("spectrum_chrom",  3, "feature", "D3"),
            ("unextractable",   1, "reject",  "D3"),
        ],
        bands=[("2006-2015", 14), ("2016-2020", 8), ("2021-2026", 8)],
    ),
    "Food Hydrocolloids": dict(
        publisher="Elsevier", started=1986,
        # 流变/结构导向：双对数流变曲线与粒径分布是本刊特色
        types=[
            ("bar",             4, "full",    "D1"),
            ("grouped_bar",     5, "full",    "D2"),
            ("scatter_line",    4, "full",    "D1"),
            ("dual_axis",       3, "full",    "D3"),
            ("multi_panel",     4, "full",    "D3"),
            ("loglog_rheology", 4, "feature", "D3"),
            ("freq_sweep",      2, "feature", "D3"),
            ("size_distrib",    3, "feature", "D2"),
            ("unextractable",   1, "reject",  "D3"),
        ],
        bands=[("2006-2015", 13), ("2016-2020", 9), ("2021-2026", 8)],
    ),
    "Food Frontiers": dict(
        publisher="Wiley", started=2020,
        # 综述/组学占比高：热图、PCA 多，可提取的数值图相对少，需多筛几篇
        types=[
            ("bar",             5, "full",    "D1"),
            ("grouped_bar",     6, "full",    "D2"),
            ("scatter_line",    4, "full",    "D1"),
            ("dual_axis",       3, "full",    "D3"),
            ("multi_panel",     4, "full",    "D3"),
            ("radar",           2, "full",    "D2"),
            ("heatmap",         3, "feature", "D3"),
            ("pca_biplot",      2, "feature", "D3"),
            ("unextractable",   1, "reject",  "D3"),
        ],
        # 创刊于 2020，无 2016 年前的图
        bands=[("2020-2022", 15), ("2023-2026", 15)],
    ),
}


def spread(types, bands):
    """把年份档尽量均匀地摊到各图类型上，避免"老图全是柱状图"这种共线。"""
    slots = []
    for t, n, task, diff in types:
        slots.extend([(t, task, diff)] * n)
    band_seq = []
    for name, n in bands:
        band_seq.extend([name] * n)
    assert len(band_seq) == len(slots), (len(band_seq), len(slots))
    # 交错分配：按图类型轮转着取年份档，而不是整块切
    order = sorted(range(len(slots)), key=lambda i: (i % len(types), i))
    assigned = [None] * len(slots)
    for rank, idx in enumerate(order):
        assigned[idx] = band_seq[rank]
    return [(t, task, diff, band) for (t, task, diff), band in zip(slots, assigned)]


def cmd_plan(a):
    import collections
    path = a.out or os.path.join(BASE, "selection_plan.csv")
    if os.path.exists(path):
        raise SystemExit(f"{path} 已存在（可能已经填了 DOI），不覆盖：换个 --out")
    rows, sid = [], 0
    for jname, cfg in JOURNALS.items():
        for t, task, diff, band in spread(cfg["types"], cfg["bands"]):
            sid += 1
            rows.append(dict(
                slot_id=f"{sid:03d}",
                journal=jname, publisher=cfg["publisher"],
                year_band=band, chart_type_target=t,
                task_type=task, difficulty_target=diff,
                # ↓ 以下为筛图时手工填写
                doi="", fig_no="", year="", file="",
                n_series="", dual_axis="", n_panel="", y_scale="",
                has_errbar="", has_sig_letter="", min_bar_ratio="",
                px_w="", px_h="", source="", extractable="", notes="",
            ))

    cols = ["slot_id", "journal", "publisher", "year_band", "chart_type_target",
            "task_type", "difficulty_target", "doi", "fig_no", "year", "file",
            "n_series", "dual_axis", "n_panel", "y_scale", "has_errbar",
            "has_sig_letter", "min_bar_ratio", "px_w", "px_h", "source",
            "extractable", "notes"]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    print(f"共 {len(rows)} 个槽位 → {path}\n")
    for j in JOURNALS:
        sub = [r for r in rows if r["journal"] == j]
        print(f"{j:<20} {len(sub)} 张  "
              f"{dict(collections.Counter(r['year_band'] for r in sub))}")
    pre = sum(1 for r in rows if r["year_band"] == "2006-2015")
    print(f"\n2016 年前(老): {pre}  |  2016 年后(新): {len(rows)-pre} "
          f"({(len(rows)-pre)/len(rows)*100:.0f}%)")
    print("task_type:", dict(collections.Counter(r["task_type"] for r in rows)))
    print("difficulty:", dict(collections.Counter(r["difficulty_target"] for r in rows)))


# ============================================================
# ⑬ 命令行
# ============================================================
def enter_dir(d):
    """--dir：先按当前目录找，找不到再按本文件所在目录找"""
    p = d if os.path.isdir(d) else os.path.join(BASE, d)
    if not os.path.isdir(p):
        raise SystemExit(f"找不到文件夹: {d}")
    os.chdir(p)
    print(f"工作目录: {os.getcwd()}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="VLM 图表数据提取评测：run/retry/one/export 提取，truth 解析真值，eval 单模型报告，"
                    "compare 多模型对比，synth 生成合成图批次，plan 生成选图配额表")
    ap.add_argument("cmd", choices=["run", "retry", "one", "export", "truth", "eval", "compare",
                                    "synth", "plan"])
    ap.add_argument("path", nargs="?", help="one：图片路径")
    ap.add_argument("--dir", help="批次文件夹（如 柱图、\"线图 点图\"），结果文件也写在那里")
    ap.add_argument("--model", help=f"模型（默认 {MODEL}）")
    ap.add_argument("--models", nargs="+", help="compare：参与对比的模型，默认全部")
    ap.add_argument("--batch", action="append", help="compare：名称=目录，可给多次，默认自动找")
    ap.add_argument("--truth", help="eval：真值 CSV，默认 truth.csv")
    ap.add_argument("--extracted", help="eval：提取结果 CSV，默认 extracted_<模型>.csv")
    ap.add_argument("--tol-rel", type=float, help="达标率的相对容差 %%")
    ap.add_argument("--tol-abs", type=float, help="达标率的绝对容差")
    ap.add_argument("--x-tol", type=float, default=5.0, help="X 数值最近邻容差，真值跨度的 %%")
    ap.add_argument("--src", help="truth：真值工作簿，默认自动找")
    ap.add_argument("--sheet", help="truth：工作表名，默认自动选")
    ap.add_argument("--out", help="truth / compare / plan：输出文件；synth：输出文件夹（默认 合成图）")
    ap.add_argument("--seed", type=int, default=20260917, help="synth：随机种子，同 seed 完全复现")
    ap.add_argument("--n", type=int, default=30, help="synth：生成几张")
    a = ap.parse_args()
    if a.model:
        MODEL = a.model
    if a.dir and a.cmd not in ("compare", "synth", "plan"):
        enter_dir(a.dir)

    if a.cmd == "one":
        if not a.path:
            raise SystemExit("用法: python extract.py one 柱图/Figure5.png --model ...")
        t0 = time.time()
        ext, tok, rtok, ptok, ctok = call_api(a.path)
        show(ext, a.path)
        print(f"\n模型 {MODEL}   耗时 {time.time() - t0:.1f}s   tokens {tok:,} "
              f"(输入 {ptok:,} / 输出 {ctok:,}，其中 reasoning {rtok:,})")
    elif a.cmd in ("run", "retry"):
        done, failed = load_done()
        if a.cmd == "run":
            run_batch([p for p in scan_images() if p not in done])
        else:
            run_batch([p for p in failed if p not in done])
        if os.path.exists(out_path()):
            export()
    elif a.cmd == "export":
        export()
    elif a.cmd == "truth":
        cmd_truth(a)
    elif a.cmd == "eval":
        cmd_eval(a)
    elif a.cmd == "synth":
        cmd_synth(a)
    elif a.cmd == "plan":
        cmd_plan(a)
    else:
        cmd_compare(a)
