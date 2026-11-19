# -*- coding: utf-8 -*-
"""pipeline.py 的离线测试：不联网、不调 API（原 figure_reader\test_figure_reader.py，读图部分的测试照旧，
末尾加了整条流程的测试）。

    python -B test_pipeline.py

一、和流水线原代码逐项比对（提示词、schema、闸门、读图指令、读后自检、合并、数值门槛、不合格原因），
    证明是"原样扒出来"的；两处修正（堆叠图、第三遍）单独测。
二、用假的 API 把 papers 里一篇真实文章的副本从头跑到尾：输出、断点续跑、失败保留断点。
三、elsevier_papers 里全部抓取脚本产物的 figure_markdown.md 都能解析。
四、svg 图（ACS 有的图只给矢量图）送模型前渲染成白底位图，长边 2048。
"""
import csv
import importlib.util
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
PIPE = os.path.join(os.path.expanduser('~'), 'Desktop', 'paper_pipeline')
PAPERS = r'D:\2.elsevier_papers'   # 用户 2026-10-30 把 Elsevier 总文件夹改名为 2.elsevier_papers
SAMPLE = os.path.join(PAPERS, 'papers', '10.1016_j.ijfoodmicro.2026.111637')   # 10-30 起文章都在 papers 子文件夹
sys.path.insert(0, HERE)
sys.path.insert(1, PIPE)

import pipeline as fr               # noqa: E402  （读图部分的名字合并时没改）

HAVE_PIPE = os.path.isdir(PIPE)
if HAVE_PIPE:
    import classify as pc            # noqa: E402
    import read as pr                # noqa: E402
    import pipeline_data as pd       # noqa: E402
    import backfill as pb            # noqa: E402
    import image_quality as piq      # noqa: E402
    VE = pr.load_ve()


# 用户 2026-10-05 有意改的两处（其余与流水线逐字一致）：蛋白质体系包括蛋白被包埋/负载在载体里的；分类时附文章标题
OLD_PROTEIN = ('1. protein_system：测的对象是不是蛋白质，或以蛋白质为主要功能成分的体系（蛋白稳定的\n'
               '   乳液和泡沫、蛋白凝胶、蛋白-多糖复合物）。淀粉、多糖、膳食纤维、油脂等本身填 false。')
NEW_PROTEIN = ('1. protein_system：测的对象是不是蛋白质，或以蛋白质为主要功能成分的体系（蛋白稳定的\n'
               '   乳液和泡沫、蛋白凝胶、蛋白-多糖复合物），或蛋白质被包埋、负载在载体里的体系（如包埋蛋白质的\n'
               '   海藻酸盐纳米凝胶、负载蛋白质的脂质体）。%s常常只写载体名、不写里面包的蛋白质，要结合文章标题判断。\n'
               '   淀粉、多糖、膳食纤维、油脂等本身（不含蛋白质）填 false。')
TITLE_BLOCK = '文章标题（可能为空）：\n{title}\n\n'
# 用户 2026-10-06：每张图分类时附上全篇所有图注原文；原来的「图注」一栏改叫「这张图的图注」，免得和全篇图注混
CAPTIONS_BLOCK = ('全篇所有图和表格的图注（figure_markdown.md 原文，按页面顺序；可能为空）。只用来前后对照，比如缩写和\n'
                  '样品名的全称、整篇研究的是什么体系；要判断的是**这一张**，以它自己的图注和图像为准：\n{captions}\n\n')
# 用户 2026-10-05 再加的五项指标
NEW_CODES = {'turbidity': '浊度', 'degree_of_hydrolysis': '水解度', 'free_amino': '游离氨基含量',
             'encapsulation': '包埋率/负载率', 'antioxidant': '抗氧化活性'}
SURFACE_LINE = '- surface_hydrophobicity 表面疏水性：表面疏水性指数（H₀、S₀），包括 ANS 等荧光探针法测得的\n'
NEW_DEFS = ('- turbidity 浊度：浊度，以及用某一个波长的吸光度（如 A600、A350）表示的浑浊或聚集程度\n'
            '- degree_of_hydrolysis 水解度：水解度（DH）\n'
            '- free_amino 游离氨基含量：游离氨基（–NH₂）含量，包括 OPA、TNBS、茚三酮等方法测得的\n'
            '- encapsulation 包埋率和负载率：包埋率（包封率，EE）、负载率（载药量，LC）\n'
            '- antioxidant 抗氧化活性：DPPH、ABTS、羟自由基等自由基清除率，还原力、FRAP、ORAC，金属离子螯合能力\n')


# 用户 2026-10-08：一个子图里又分几格、各格坐标轴不同的（散点矩阵等）不读
BAR3D_TAIL = '  普通的平面柱状图，柱子带一点阴影或渐变色的，照常填 bar / grouped_bar。\n'
NEW_MATRIX = ('- 一个子图里又分成好几格小图、各格用不同的坐标轴（散点矩阵、配对图、边际图，例如四格分别是吸水性对蛋白、\n'
              '  吸油性对糖……）的，填 scatter_matrix：点多、各格的轴又不一样，读不准，保留原图即可。\n'
              '  几张小图用同样的坐标轴、只是样品或条件不同（各有自己的小标题）的不算，照常判断。\n')


# 用户 2026-10-09（不用 astra 了，提高 gemini 准确性、少漏读）：分类提示写明哪些算蛋白质、拿不准填 true
PROTEIN_EXAMPLES = ('   这些都是蛋白质：明胶（gelatin，包括 GelMA 等明胶衍生物）、胶原、丝素蛋白、玉米醇溶蛋白（zein）、乳清蛋白、\n'
                    '   酪蛋白、大豆/豌豆/米糠等植物蛋白、肌原纤维蛋白、卵清蛋白、乳铁蛋白、肌红蛋白、溶菌酶等各种酶、蛋白水解物和肽、\n'
                    '   聚赖氨酸等多肽；主要成分里有这些的复合体系（如明胶-壳聚糖水凝胶、含明胶微球的水凝胶、蛋白-多酚复合物）也填 true。\n'
                    '   拿不准是不是蛋白质体系时填 true。\n')
# 用户 2026-10-09 定的不读：粒径分布曲线、温度 / 应变 / 应力 / 时间扫描、模型拟合的模量、纤维长度和直径
SIZE_LINE = ('等粒径数值，以及粒径分布曲线', '等粒径数值（画成柱状图或点图的）')
FREQ_LINE = '凝胶或乳液的频率扫描曲线（G′、G″ 随频率变化）不读，填 none。'
NOT_READ_1009 = ('温度扫描、应变（振幅）扫描、应力扫描和\n'
                 '成胶时间扫描曲线（G′、G″ 随温度、应变、应力或时间变化），用蠕变或应力松弛模型（Burgers、Maxwell 等）拟合出的\n'
                 '模量参数，也都不读，填 none。\n'
                 '粒径分布曲线和粒径分布直方图（横轴是粒径、纵轴是强度 / 体积 / 数量占比）不读，填 none；纤维（如淀粉样纤维）的\n'
                 '长度和直径不算粒径，填 none。')
# 用户 2026-10-12（全量测试后）定的不读：模型预测值对实验值的图；力学性能不算凝胶性、水凝胶溶胀率不算持水性
NOT_READ_1012 = ('\n模型预测值对实验值（实测值）的图（响应面、机器学习等模型的验证图，横轴、纵轴是同一个指标的实验值和预测值）不是测定数据，\n'
                 '不读，填 none。')
GEL_LINE = ('- gelling 凝胶性：凝胶强度、凝胶的硬度和弹性等质构指标、各样品凝胶的储能模量数值、最小凝胶浓度\n',
            # 2026-10-13 起质构（TPA）不算凝胶性，定义里的「凝胶的硬度和弹性等质构指标」删掉
            '- gelling 凝胶性：凝胶强度、各样品凝胶的储能模量数值、最小凝胶浓度；压缩强度、拉伸强度、杨氏模量、韧性、\n'
            '  断裂应变等力学性能，和质构（TPA）的硬度、弹性、咀嚼性、胶黏性、内聚性、回复性、黏附性都不算，填 none\n')
WATER_LINE = ('- water_holding 持水性：持水力、吸水性（WHC、WAC、WBC）、溶胀力、膨胀力\n',
              '- water_holding 持水性：持水力、吸水性（WHC、WAC、WBC）、溶胀力、膨胀力；水凝胶、膜、微球的溶胀率（溶胀比）不算，填 none\n')


def pipeline_to_ours(text, where):
    """流水线的分类提示词加上这边有意改的几处，应当和 figure_reader 的一字不差。"""
    text = text.replace(*SIZE_LINE).replace(FREQ_LINE, FREQ_LINE + NOT_READ_1009 + NOT_READ_1012)
    text = text.replace(*GEL_LINE).replace(*WATER_LINE)
    text = (text.replace(OLD_PROTEIN, NEW_PROTEIN % where)
            .replace(BAR3D_TAIL, BAR3D_TAIL + NEW_MATRIX)
            .replace('这几项理化指标。先读', '这几项理化指标，还有浊度、水解度、游离氨基含量、包埋率和负载率、抗氧化活性。先读')
            .replace(SURFACE_LINE, SURFACE_LINE + NEW_DEFS)
            .replace('（巯基、二硫键含量除外）', '（巯基、二硫键、游离氨基含量除外）')
            .replace('要结合文章标题判断。\n   淀粉', '要结合文章标题判断。\n' + PROTEIN_EXAMPLES + '   淀粉'))
    return text


def without_protein_desc(schema):
    """比对 schema 时去掉有意改过的 protein_system 说明、functional_property 的说明和可选代号，其余必须一模一样。"""
    s = json.loads(json.dumps(schema))
    for d in s.get('$defs', {}).values():
        props = d.get('properties', {})
        if 'protein_system' in props:
            props['protein_system'].pop('description', None)
        if 'functional_property' in props:
            props['functional_property'].pop('description', None)
            props['functional_property'].pop('enum', None)
        if 'chart_type' in props:                       # 2026-10-08 加了 scatter_matrix 的说明
            props['chart_type'].pop('description', None)
    return s


@unittest.skipUnless(HAVE_PIPE, '没有 paper_pipeline，跳过比对')
class SameAsPipeline(unittest.TestCase):
    def test_prompts_identical(self):
        self.assertEqual(fr.FUNCTIONAL_RULES, pipeline_to_ours(pc.FUNCTIONAL_RULES, '图注'))
        self.assertEqual(fr.PROPERTY_CODES, pc.PROPERTY_CODES + ' / turbidity 浊度 / degree_of_hydrolysis 水解度 / '
                         'free_amino 游离氨基含量 / encapsulation 包埋率和负载率 / antioxidant 抗氧化活性')
        self.assertEqual(fr.FUNCTIONAL, dict(pc.FUNCTIONAL, **NEW_CODES))
        self.assertEqual(fr.SYSTEM, pipeline_to_ours(pc.SYSTEM, '图注'))
        self.assertEqual(fr.TABLE_SYSTEM, pipeline_to_ours(pc.TABLE_SYSTEM, '表题'))
        self.assertTrue(all(code in fr.SYSTEM and code in fr.TABLE_SYSTEM for code in NEW_CODES))
        self.assertEqual(fr.USER, pc.USER.replace('图注（可能为空）：',
                                                  TITLE_BLOCK + CAPTIONS_BLOCK + '这张图的图注（可能为空）：'))
        self.assertEqual(fr.TABLE_USER, pc.TABLE_USER.replace('表题和表注（可能为空）：',
                                                              TITLE_BLOCK + CAPTIONS_BLOCK + '这张表的表题和表注（可能为空）：'))
        for name in ('SERIES_POLICY', 'TABLE_RULES', 'TABLE_NOTE', 'REPLICATE_NOTE', 'CAPTION_NOTE',
                     'SMOOTH_NOTE', 'UNRESOLVED_NOTE', 'UNRESOLVED_EMPTY', 'BLOCKING'):
            self.assertEqual(getattr(fr, name), getattr(pr, name), name)
        self.assertEqual(fr.SYSTEM_PROMPT, VE.SYSTEM_PROMPT)
        self.assertEqual((fr.MAX_SIDE, fr.DETAIL), (VE.MAX_SIDE, VE.DETAIL))

    def test_schemas_identical(self):
        self.assertEqual(without_protein_desc(fr.FigureClass.model_json_schema()),
                         without_protein_desc(pc.FigureClass.model_json_schema()))
        self.assertEqual(without_protein_desc(fr.TableClass.model_json_schema()),
                         without_protein_desc(pc.TableClass.model_json_schema()))
        self.assertIn('包埋', fr.FigureClass.model_json_schema()['$defs']['Panel']['properties']['protein_system']['description'])
        # 读图 schema：extract.py 的原样继承，只多第三条纵轴（2026-10-13）
        self.assertTrue(issubclass(fr.Extraction, fr.VE.Extraction))      # 测试另外加载的 VE 是另一份类对象
        self.assertEqual(set(fr.ReadPanel.model_fields), set(VE.Panel.model_fields) | {'y_third'})
        self.assertEqual(set(fr.ReadSeries.model_fields), set(VE.Series.model_fields))
        for name, f in VE.Panel.model_fields.items():
            if name != 'series':
                self.assertEqual(fr.ReadPanel.model_fields[name].description, f.description, name)
        from openai.lib._pydantic import to_strict_json_schema
        strict = to_strict_json_schema(fr.Extraction)       # 发给模型的严格 schema：y_third 必填、可为 null
        self.assertIn('y_third', strict['$defs']['ReadPanel']['required'])
        self.assertNotIn('default', strict['$defs']['ReadPanel']['properties']['y_third'])
        self.assertEqual(without_protein_desc(to_strict_json_schema(fr.FigureClass)),
                         without_protein_desc(to_strict_json_schema(pc.FigureClass)))

    def test_gate_constants_identical(self):
        for name in ('NON_QUANT', 'FREQUENCY_X', 'RHEOLOGY_Y', 'SPECTRAL_X', 'PPM_SPECTRAL_CTX',
                     'PPM_CONC_CTX', 'PRIMARY_STRUCTURE_X', 'BIBLIOMETRIC_Y', 'BIBLIOMETRIC_CTX', 'STACKED',
                     'DENSE_LIMIT', 'SIDE_BY_SIDE', 'CHART_TYPES', 'PLAIN_MARKS', 'SURFACE', 'THREE_D_BARS'):
            self.assertEqual(getattr(fr, name), getattr(pc, name), name)

    def random_panel(self, rnd, label):
        return dict(
            label=label,
            mark_types=rnd.sample(['bar', 'point', 'line', 'box', 'area', 'other'], rnd.choice([0, 1, 1, 2, 2, 3])),
            chart_type=rnd.choice(['bar', 'grouped_bar', 'stacked_bar', 'line', 'scatter', 'combo', 'box',
                                   'heatmap', 'other', 'bar_line', '', 'micrograph', 'surface', 'bar_3d',
                                   '3d_bar', 'stacked_column', 'percent_stacked_bar', 'contour', 'Scatter ']),
            x_axis_label=rnd.choice([None, 'pH', 'Wavenumber (cm-1)', 'Frequency (rad/s)', 'Time (min)',
                                     'Protein concentration (ppm)', 'Chemical shift (ppm)', 'Lane', 'ppm']),
            y_axis_label=rnd.choice([None, "G' (Pa)", 'Solubility (%)', 'EAI (m2/g)', 'Number of papers']),
            caption_part=rnd.choice([None, 'solubility (A)']),
            protein_system=rnd.random() < 0.8,
            functional_property=rnd.choice(list(pc.FUNCTIONAL) + ['none', 'none']),
            y_tick_labels=rnd.choice([None, [], ['0', '10', '20'], ['a', 'b'], ['0', 'x']]),
            n_series=rnd.choice([None, 1, 2, 5]), points_per_series=rnd.choice([None, 0, 4, 9, 30]),
            has_error_bars=rnd.random() < 0.5, has_significance_letters=rnd.random() < 0.5,
            series_overlap_risk=rnd.choice(['low', 'medium', 'high', 'HIGH']),
            overlap_reason=rnd.choice([None, 'curves overlap']))

    def test_gates_identical_except_stacked_fix(self):
        rnd = random.Random(7)
        differ = 0
        for case in range(3000):
            n = rnd.choice([1, 2, 3])
            d = dict(n_panels=rnd.choice([n, n, n + 1]),
                     panels=[self.random_panel(rnd, rnd.choice(['A', 'B', None, 'c'])) for _ in range(n)],
                     caption_topic=rnd.choice(['蛋白溶解度', 'Scopus 文献计量', '乳化性']), notes=None)
            mine = fr.verdict_detail(fr.FigureClass(**d))
            theirs = pc.verdict_detail(pc.FigureClass(**d))
            stacked_rename = any(
                fr.is_stacked((p['chart_type'] or '').strip().lower())
                and pc.chart_type_of(pc.Panel(**p)) not in pc.STACKED for p in d['panels'])
            if stacked_rename:
                differ += 1
                continue
            self.assertEqual(mine, theirs, d)
        self.assertGreater(differ, 0)

    def test_figure_instruction_identical(self):
        hints = [{'panel': 'A', 'chart_type': 'bar', 'property': '溶解度', 'n_series': 2, 'y_axis': 'Solubility (%)',
                  'has_error_bars': True, 'has_significance_letters': True, 'overlap_risk': 'medium',
                  'caption_part': 'solubility (A)'},
                 {'panel': 'C', 'chart_type': 'combo', 'property': '乳化性', 'n_series': None, 'y_axis': None,
                  'has_error_bars': False, 'has_significance_letters': False, 'overlap_risk': 'low',
                  'caption_part': None}]
        base = {'read_panels': ['A', 'C'], 'ignore_panels': ['B', None], 'hints': hints,
                'caption': 'Fig. 3. (A) solubility; (B) FTIR; (C) EAI.'}
        # 2026-10-13 起多一段纵轴和横轴的说明（AXIS_NOTE），2026-10-19 起再多一句一个字母下几张小图（MULTI_PLOT_NOTE），
        # 其余一字不差
        mine = fr.panel_instruction(dict(base, kind='figure', label='3', case=False))
        self.assertIn(fr.MULTI_PLOT_NOTE, mine)
        self.assertEqual(mine.replace(fr.AXIS_NOTE + '\n', '').replace(fr.MULTI_PLOT_NOTE + '\n', ''),
                         pr.panel_instruction(dict(base, fig=3)))
        # 分类已经看出 A 下面有几张小图（MULTI_NOTE）时不再加 MULTI_PLOT_NOTE
        multi = fr.panel_instruction(dict(base, kind='figure', label='3', case=False, multi={'A': 2}))
        self.assertIn(fr.MULTI_NOTE % ('A', 2, 'A'), multi)
        self.assertNotIn(fr.MULTI_PLOT_NOTE, multi)
        for rule in ('横向柱状图', '纵轴的颜色', '漏印了负号'):
            self.assertIn(rule, fr.AXIS_NOTE)
        table = {'read_panels': ['WHC (g/g)'], 'ignore_panels': ['Digestibility (%)'], 'caption': 'Table 4. x',
                 'hints': [{'panel': 'WHC (g/g)', 'property': '持水性', 'layout': 'column', 'n_values': 6}]}
        self.assertEqual(fr.panel_instruction(dict(table, kind='table', label='4', case=False)),
                         pr.panel_instruction(dict(table, kind='table', table=4, fig=1004)))

    def random_extraction(self, rnd, labels):
        panels = []
        for lab in labels + rnd.sample(['Z', 'd(i)'], rnd.choice([0, 1])):
            names = rnd.sample(['WPI', 'SPI', 'UNRESOLVED_red', 'Control'], rnd.choice([1, 2]))
            pts = []
            for s in names:
                for i in range(rnd.choice([0, 3, 4])):
                    y = rnd.choice([None, round(rnd.uniform(0, 120), 2)])
                    pts.append(dict(series=rnd.choice([s, s, s, 'ghost']), point_index=i + 1,
                                    x_category=rnd.choice(['pH 3', 'pH 5', None]), x_value=rnd.choice([None, 3.0]),
                                    y_value=y, err_low=None if y is None else y - rnd.choice([1, -1]),
                                    err_high=None if y is None else y + 1, estimated=rnd.random() < .5,
                                    sig=rnd.choice([None, 'a']), note=rnd.choice([None, '9.03±0.10a', '12'])))
            axis = dict(label='y', unit='%', scale='linear', min=0.0, max=100.0, ticks='0,20,40,60,80,100',
                        starts_at_zero=True, multiplier=None)
            panels.append(dict(panel_id=lab, chart_type='bar', x_axis=dict(axis, unit=None), y_left=axis,
                               y_right=None, series=[dict(name=s, axis='left', chart_type='bar') for s in names],
                               points=pts))
        return dict(panels=panels, confidence='high', note=None)

    def test_reading_checks_identical(self):
        rnd = random.Random(3)
        for case in range(400):
            labels = rnd.sample(['A', 'B', 'D i'], rnd.choice([1, 2]))
            raw = self.random_extraction(rnd, labels)
            hints = [{'panel': lab, 'mark_types': rnd.choice([['bar'], ['line']])} for lab in labels]
            table = rnd.random() < 0.2
            t = {'key': 'fig2', 'kind': 'table' if table else 'figure', 'label': '2', 'case': False,
                 'read_panels': labels, 'ignore_panels': [], 'hints': hints}
            from unittest import mock
            # 只丢超出刻度的点、不在图例里的系列（2026-10-13 起）流水线没有，比对时关掉
            with mock.patch.object(fr, 'fix_series_names', lambda data, case=False: {}), \
                    mock.patch.object(fr, 'drop_out_of_range', lambda data, case=False: {}):
                mine = fr.check_reading(t, json.loads(json.dumps(raw)))
            # 流水线 read.read_one 里的同一串后处理
            f = {'fig': 1004 if table else 2, 'read_panels': labels, 'hints': hints, 'kind': t['kind']}
            piq.CASE_FIGURES.clear()
            data, dropped = pr.only_requested(json.loads(json.dumps(raw)), labels, f['fig'])
            copied = pr.printed_cells(data) if table else []
            lost, emptied = pr.drop_unresolved(data, f['fig'])
            smooth = pr.smooth_panels(f)
            fl = pr.gates(VE.Extraction(**data), labels, f['fig'], smooth, emptied) + copied + pr.unresolved_flags(lost, emptied)
            if dropped:
                fl.append('已丢弃未要求的子图 %s（不是这次要读的数据）' % dropped)
            self.assertEqual(mine['flags'], fl)
            self.assertEqual(mine['data'], VE.Extraction(**data).model_dump())
            self.assertEqual(mine['ok'], not any(pr.is_blocking(x) for x in fl))
            self.assertEqual(mine['smooth_empty'], pr.smooth_empty(data, smooth, f['fig']))
            self.assertEqual((mine['unresolved_series'], mine['unresolved_empty']), (lost, emptied))

    def synthetic_runs(self, rnd, table=False):
        """两遍读图记录：同一组点加一点噪声，偶尔漏点、换系列名、同一点读两次。"""
        xs = rnd.choice([['pH 3', 'pH 5', 'pH 7'], [0.0, 10.0, 20.0, 30.0], ['0', '5', 'S1']])
        truth = {(p, s, str(x)): round(rnd.uniform(1, 90), 2) for p in ('A', 'B') for s in ('WPI', 'SPI') for x in xs}
        runs = []
        for r in range(2):
            panels = []
            for p in ('A', 'B'):
                pts = []
                for s in ('WPI', 'SPI'):
                    # 偶尔换一个系列名（写法统一后也不一样的；只差大小写的 2026-10-12 起会统一，见 test_series_names_and_blank_x）
                    name = s if rnd.random() > 0.1 else s + '2'
                    for i, x in enumerate(xs):
                        if rnd.random() < 0.1:
                            continue
                        y = truth[(p, s, str(x))]
                        if not table:
                            y = round(y * (1 + rnd.choice([0, 0, 0.004, -0.03, 0.08])), 2)
                        if rnd.random() < 0.05:
                            y = None
                        num = isinstance(x, float)
                        q = dict(series=name, point_index=i + 1, x_category=None if num else x,
                                 x_value=(x + rnd.choice([0, 0.4])) if num else None, y_value=y,
                                 err_low=None if y is None else round(y - 1, 2), err_high=None if y is None else round(y + 1, 2),
                                 estimated=False, sig=rnd.choice([None, 'a']), note=None)
                        pts.append(q)
                        if rnd.random() < 0.03:
                            pts.append(dict(q, y_value=None if y is None else y + 5))
                axis = dict(label='y', unit=rnd.choice(['%', '%', '%', 'g/g']), scale='linear', min=0.0, max=100.0,
                            ticks=None, starts_at_zero=True, multiplier=None)
                panels.append(dict(panel_id=p, chart_type='bar', x_axis=dict(axis, unit=None), y_left=axis,
                                   y_right=None, series=[], points=pts))
            runs.append(dict(panels=panels, confidence='high', note=None))
        return runs

    def pipeline_merge(self, runs, hints, table=False):
        fig = 1004 if table else 3
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'stage3_targets.json'), 'w', encoding='utf-8') as fh:
                json.dump({'figures': [{'fig': fig, 'read_panels': ['A', 'B'], 'ignore_panels': [], 'hints': hints}]}, fh)
            for i, data in enumerate(runs, 1):
                tag = '' if i == 1 else '_run%d' % i
                with open(os.path.join(d, 'results_stage3%s.jsonl' % tag), 'w', encoding='utf-8') as fh:
                    fh.write(json.dumps({'fig': fig, 'ok': True, 'data': data}) + '\n')
            p = subprocess.run([sys.executable, '-B', os.path.join(PIPE, 'merge.py'), d, '--mode', 'whole'],
                               capture_output=True, text=True, encoding='utf-8', errors='replace',
                               env=dict(os.environ, PYTHONIOENCODING='utf-8'))
            path = os.path.join(d, 'merged.csv')
            if not os.path.exists(path):
                return []
            with open(path, encoding='utf-8-sig', newline='') as fh:
                return list(csv.DictReader(fh))

    def test_merge_identical(self):
        rnd = random.Random(11)
        fields = ('子图', '系列', 'X类别/数值', 'X单位', 'Y值', 'Y单位', 'Y轴', '轴倍率', '显著性', '估读', '误差棒下限',
                  '误差棒上限', 'n_runs_seen', 'n_runs_valid', 'y_spread_pct', 'confidence', '备注',
                  'n_runs_expected', 'review_reason')
        for case in range(25):
            table = case % 5 == 4
            runs = self.synthetic_runs(rnd, table)
            hints = [{'panel': 'A', 'n_series': 2}, {'panel': 'B', 'n_series': rnd.choice([1, 2])}]
            target = {'key': 'fig3', 'kind': 'table' if table else 'figure', 'label': '3', 'case': False,
                      'read_panels': ['A', 'B'], 'ignore_panels': [], 'hints': hints}
            recs = [('run%d' % i, {'fig3': {'ok': True, 'data': data, 'scope': ['A', 'B']}})
                    for i, data in enumerate(runs, 1)]
            from unittest import mock
            # 流水线没有按数值配系列（2026-10-13 起才有，见 test_series_matched_by_values），比对时关掉
            with mock.patch.object(fr, 'unify_by_values', lambda points: None):
                mine = fr.merge({'fig3': target}, recs)
            theirs = self.pipeline_merge(runs, hints, table)

            def norm(row):
                out = []
                for k in fields:
                    v = row.get(k)
                    out.append('' if v is None else str(v))
                return tuple(out)
            self.assertEqual([norm(r) for r in mine], [norm(r) for r in theirs], case)
            for a, b in zip(mine, theirs):
                self.assertEqual(a['各次读数'], b['各次读数'].replace('_run', 'run'))

    def test_threshold_and_reasons_identical(self):
        rnd = random.Random(5)
        for case in range(15):
            runs = self.synthetic_runs(rnd)
            target = {'key': 'fig3', 'kind': 'figure', 'label': '3', 'case': False,
                      'read_panels': ['A', 'B'], 'ignore_panels': [], 'hints': []}
            recs = [('run%d' % i, {'fig3': {'ok': True, 'data': data, 'scope': ['A', 'B']}})
                    for i, data in enumerate(runs, 1)]
            rows = fr.merge({'fig3': target}, recs)
            strs = [{k: ('' if v is None else str(v)) for k, v in r.items()} for r in rows]
            acc, rej = fr.select_rows(rows)
            pacc, prej, _ = pd.select_rows(strs)
            # 用户 2026-10-12 有意改的：离散度超过 5%、但几遍最多只差纵轴满量程 1% 的算一致、通过
            fs_of = {id(s): r.get('y_diff_fs_pct') for r, s in zip(rows, strs)}
            rescued = [(s, w) for s, w in prej if 'y_spread_pct=' in w
                       and fs_of.get(id(s)) is not None and fs_of[id(s)] <= fr.FS_TOL]
            prej = [x for x in prej if x not in rescued]
            self.assertEqual(len(acc), len(pacc) + len(rescued))
            self.assertEqual([why for _, why in rej], [why for _, why in prej])
            for (r, why), (s, pwhy) in zip(rej, prej):
                mine = fr.why_rejected(r, why, rows)
                if 'y_spread_pct=' in pwhy:
                    # 用户 2026-10-09 有意改的：读数相差超过 5% 的写出各遍读数、取平均值（三遍取中位数）、需人工复核
                    self.assertTrue(mine.endswith('，需人工复核。'), mine)
                    self.assertIn('表中取', mine)
                    continue
                if fr.is_single(r, why):
                    # 用户 2026-10-12 有意改的：只有一遍读出的，入库判定一栏标「只有一遍读出」，原因一栏不另写
                    self.assertEqual(mine, '')
                    continue
                theirs = (pb.OVERLAP_REASON if 'confidence=invalid' in pwhy and pb.hidden_by_overlap(s, strs)
                          else pb.display_reason(s, pwhy))
                self.assertEqual(mine, theirs)


class Fixes(unittest.TestCase):
    def test_italic_g_in_centrifugation(self):
        """用户 2026-11-02：离心力「10,000_g」（原文斜体 g 的下划线残留）写库时改成「10,000 g」；下标写法 D_h、R_g 不动。"""
        cases = [('centrifugation=10,000_g, 10 min', 'centrifugation=10,000 g, 10 min'),
                 ('Centrifugation force: 12 000_g; time: 20 min', 'Centrifugation force: 12 000 g; time: 20 min'),
                 ('fugation（3000 _g, 5 min）', 'fugation（3000 g, 5 min）'), ('at 7000_g_ for 10 min', 'at 7000 g for 10 min'),
                 ('_g', 'g'), ('hydrodynamic diameter (D_h)', 'hydrodynamic diameter (D_h)'), ('R_g (nm)', 'R_g (nm)'),
                 ('d_{4,3} = ∑n_id_i⁴/∑n_id_i³', 'd_{4,3} = ∑n_id_i⁴/∑n_id_i³'), ('10_gly', '10_gly'), ('', ''), (None, None)]
        for raw, want in cases:
            self.assertEqual(fr.bd_fix_g(raw), want, raw)

    def test_journal_from_elsevier_api_fulltext(self):
        """11-11：Elsevier API 抓的全文开头「## 期刊名」+「## Published by …」或「# 题目」，期刊名要读出来；非 Elsevier DOI 不按这条认。"""
        with tempfile.TemporaryDirectory() as root:
            cases = [('10.1016_j.foodchem.2020.1', '## Food Chemistry\n\n## Published by: Elsevier Ltd.\n\n# Title\n', 'Food Chemistry'),
                     ('10.1016_j.fbp.2017.2', '## Food and Bioproducts Processing\n\n# Title\n', 'Food and Bioproducts Processing'),
                     ('10.1016_j.lwt.2020.3', '[![LWT](x.gif)](/journal/lwt)\n\n## [LWT](/journal/lwt "Go")\n', 'LWT'),
                     ('10.3390_foods1', '## Something\n\n# Title\n', ''),
                     ('10.1080_08905430701191148', '[Advanced search](/search/advanced)\n\n[Food Biotechnology](/journals/lfbt20) '
                      'Volume 21, 2007 - [Issue 1](/toc/lfbt20/21/1)\n', 'Food Biotechnology')]
            for art, text, want in cases:
                os.makedirs(os.path.join(fr.ed_papers_dir(root), art))
                with open(os.path.join(fr.ed_papers_dir(root), art, '全文.md'), 'w', encoding='utf-8') as fh:
                    fh.write(text)
                self.assertEqual(fr.bd_journal_from_fulltext(root, art), want, art)
            # Springer / Nature：页面标题（figure_markdown.md 第一行）
            for art, title, want in (('10.1007_s00217-003-0684-5', '# Changes in myofibrillar proteins | European Food Research '
                                      'and Technology | Springer Nature Link', 'European Food Research and Technology'),
                                     ('10.1038_s41538-017-0003-3', '# Direct interaction of particles | npj Science of Food',
                                      'npj Science of Food'),
                                     ('10.3390_foods2', '# Some title | Something', '')):
                os.makedirs(os.path.join(fr.ed_papers_dir(root), art, 'figure'))
                with open(os.path.join(fr.ed_papers_dir(root), art, '全文.md'), 'w', encoding='utf-8') as fh:
                    fh.write('# title\n')
                with open(os.path.join(fr.ed_papers_dir(root), art, 'figure', 'figure_markdown.md'), 'w', encoding='utf-8') as fh:
                    fh.write(title + '\n')
                self.assertEqual(fr.bd_journal_from_fulltext(root, art), want, art)

    def panel(self, **kw):
        base = dict(label='A', mark_types=['bar'], chart_type='bar', x_axis_label='Sample', y_axis_label='Solubility (%)',
                    caption_part=None, protein_system=True, functional_property='solubility',
                    y_tick_labels=['0', '20', '40'], n_series=2, points_per_series=5, has_error_bars=True,
                    has_significance_letters=True, series_overlap_risk='low', overlap_reason=None)
        base.update(kw)
        return base

    def test_size_distribution_and_sweeps_not_read(self):
        """用户 2026-10-09：粒径只读平均粒径的柱、点图，粒径分布曲线和分布直方图不读；温度 / 应变 / 应力扫描曲线不读。
        和频率扫描一样按规则不读，不列进「没读的功能特性子图」。"""
        cases = [
            (dict(functional_property='particle_size', chart_type='line', mark_types=['line'],
                  x_axis_label='Size (d.nm)', y_axis_label='Intensity (%)'), False),
            (dict(functional_property='particle_size', chart_type='histogram', mark_types=['bar'],
                  x_axis_label='Diameter (nm)', y_axis_label='Frequency (%)'), False),
            (dict(functional_property='emulsifying', chart_type='line', mark_types=['line'],
                  x_axis_label='Droplet size (μm)', y_axis_label='Volume (%)'), False),
            (dict(functional_property='particle_size', x_axis_label='Sample', y_axis_label='Particle size (nm)'), True),
            (dict(functional_property='particle_size', chart_type='line', mark_types=['line', 'point'],
                  x_axis_label='Storage time (d)', y_axis_label='Z-average diameter (nm)'), True),
            (dict(functional_property='gelling', chart_type='line', mark_types=['line'],
                  x_axis_label='Temperature (°C)', y_axis_label="G', G'' (Pa)"), False),
            (dict(functional_property='gelling', chart_type='line', mark_types=['line', 'point'],
                  x_axis_label='Strain (%)', y_axis_label='Storage modulus (Pa)'), False),
            (dict(functional_property='gelling', x_axis_label='Sample', y_axis_label="G' (Pa)"), True),
            # 压缩的应力-应变曲线不归流变扫描那条管，但 2026-10-12 起力学性能不算凝胶性，照样不读
            (dict(functional_property='gelling', chart_type='line', mark_types=['line'],
                  x_axis_label='Strain (%)', y_axis_label='Compressive stress (kPa)'), False),
            # 用户 2026-10-12：力学性能不算凝胶性，水凝胶溶胀率不算持水性，模型预测值对实验值的图不读
            (dict(functional_property='gelling', y_axis_label="Young's Modulus (MPa)"), False),
            (dict(functional_property='gelling', y_axis_label='Toughness (MJ/m³)'), False),
            (dict(functional_property='gelling', y_axis_label='Compressive strength (kPa)'), False),
            (dict(functional_property='gelling', y_axis_label='Gel strength (g)'), True),
            # 用户 2026-10-13：质构（TPA）的硬度、咀嚼性等不算凝胶性；弹性模量（G′）照旧算
            (dict(functional_property='gelling', y_axis_label='Hardness (g)'), False),
            (dict(functional_property='gelling', y_axis_label='Chewiness'), False),
            (dict(functional_property='gelling', y_axis_label='硬度 (N)'), False),
            (dict(functional_property='gelling', y_axis_label="弹性模量 G' (Pa)"), True),
            # 用户 2026-10-15：剪切力、断裂应力、断裂形变、易碎性、firmness、黏性、剪切功、屈服应力、最大力也不算；
            # 凝胶断裂强度、凝乳硬度（curd firmness）照旧算凝胶性
            (dict(functional_property='gelling', y_axis_label='Shear force (N)'), False),
            (dict(functional_property='gelling', y_axis_label='Breaking stress (kPa)'), False),
            (dict(functional_property='gelling', y_axis_label='Deformation (mm)'), False),
            (dict(functional_property='gelling', y_axis_label='Fracturability (N)'), False),
            (dict(functional_property='gelling', y_axis_label='Firmness (N)'), False),
            (dict(functional_property='gelling', y_axis_label='Stickiness (kN/m²)'), False),
            (dict(functional_property='gelling', y_axis_label='Work of Shear (g.sec)'), False),
            (dict(functional_property='gelling', y_axis_label='Yield stress (Pa)'), False),
            (dict(functional_property='gelling', y_axis_label='Maximum force [N]'), False),
            (dict(functional_property='gelling', y_axis_label='Breaking strength (g)'), True),
            (dict(functional_property='gelling', y_axis_label='Gel strength (maximum force, g)'), True),
            (dict(functional_property='gelling', y_axis_label='Curd firmness (g)'), True),
            (dict(functional_property='water_holding', chart_type='line', mark_types=['line', 'point'],
                  x_axis_label='Time (h)', y_axis_label='Swelling ratio (%)'), False),
            (dict(functional_property='water_holding', y_axis_label='Swelling power (g/g)'), True),
            (dict(functional_property='solubility', chart_type='scatter', mark_types=['point'],
                  x_axis_label='Experimental value', y_axis_label='Predicted value'), False),
            (dict(functional_property='solubility', y_axis_label='Solubility (%)'), True),
        ]
        for kw, read in cases:
            fc = fr.FigureClass(n_panels=1, panels=[self.panel(**kw)], caption_topic='x', notes=None)
            quant, _, _, _, why = fr.verdict_detail(fc)
            self.assertEqual(quant == ['A'], read, kw)
            if not read:
                self.assertEqual(why, {}, kw)

    def test_referenced_caption_and_point_labels(self):
        """用户 2026-10-15：图注写「Symbols as in Figure 6」时把图 6 的图注也交给读图；读散点图时，点旁边印的名称写进
        x_category。别的图读图指令不变（断点里读完的图不用重读）。"""
        items = [{'kind': 'figure', 'label': '6', 'caption': 'Figure 6. Foam stability. (●) WPI; (○) SPI.'},
                 {'kind': 'figure', 'label': '7', 'caption': 'Figure 7. Foam overrun. Symbols as in Figure 6.'},
                 {'kind': 'table', 'label': '6', 'caption': 'Table 6. Composition.'}]
        self.assertEqual(fr.referenced_captions(items[1]['caption'], items, '7'), [('6', items[0]['caption'])])
        self.assertEqual(fr.referenced_captions('图 4 的符号同图 6。', items, '4'), [('6', items[0]['caption'])])
        self.assertEqual(fr.referenced_captions('Figure 7. Compared with Figure 6, the overrun rose.', items, '7'), [])
        self.assertEqual(fr.referenced_captions('Figure 6. Symbols as in Figure S2.', items, '6'), [])

        def target(chart_type, refs=()):
            return {'kind': 'figure', 'label': '7', 'read_panels': ['A'], 'ignore_panels': [], 'caption': items[1]['caption'],
                    'hints': [{'panel': 'A', 'chart_type': chart_type}], 'ref_captions': list(refs)}
        plain = fr.panel_instruction(target('bar'))
        self.assertNotIn(fr.POINT_LABEL_NOTE, plain)
        self.assertNotIn('Figure 6. Foam stability', plain)
        self.assertIn(fr.POINT_LABEL_NOTE, fr.panel_instruction(target('scatter')))
        self.assertIn('Figure 6. Foam stability', fr.panel_instruction(target('bar', [('6', items[0]['caption'])])))

    def test_stacked_names_not_read(self):
        for name in ('stacked_column', 'percent_stacked_bar', 'stacked_bar', 'Stacked bar chart', '100% stacked bar'):
            fc = fr.FigureClass(n_panels=1, panels=[self.panel(chart_type=name)], caption_topic='x', notes=None)
            quant, _, _, _, why = fr.verdict_detail(fc)
            self.assertEqual(quant, [], name)
            self.assertEqual(why, {'A': '堆叠图，不送反读'}, name)
        fc = fr.FigureClass(n_panels=1, panels=[self.panel(chart_type='bar_line', mark_types=['bar', 'point'])],
                            caption_topic='x', notes=None)
        self.assertEqual(fr.verdict_detail(fc)[0], ['A'])           # 组合图照读

    def reading(self, panels):
        return {'ok': True, 'data': {'panels': panels}, 'scope': ['A', 'B', 'C'],
                'smooth_empty': [p['panel_id'] for p in panels if not p['points']], 'unresolved_empty': []}

    def pan(self, pid, ys):
        axis = dict(label='y', unit='%', scale='linear', min=0.0, max=100.0, ticks=None, starts_at_zero=True,
                    multiplier=None)
        return dict(panel_id=pid, chart_type='bar', x_axis=axis, y_left=axis, y_right=None,
                    series=[dict(name='WPI', axis='left', chart_type='bar')],
                    points=[dict(series='WPI', point_index=i + 1, x_category='S%d' % i, x_value=None, y_value=y,
                                 err_low=None, err_high=None, estimated=False, sig=None, note=None)
                            for i, y in enumerate(ys)])

    def test_equivalent_notation_not_conflict(self):
        """同一个意思的写法不算冲突（用户 2026-10-09）：一遍倍数空着、一遍写 1 或 ×1，10^5 / x10^5 / ×10⁵，单位 ℃ / °C、
        µ / μ，一遍没写单位；真的不一样的（10^3 和 10^5、mV 和 V）照旧算冲突、转人工。表里显示原来的写法。"""
        t = {'key': 'fig1', 'kind': 'figure', 'label': '1', 'case': False, 'read_panels': ['A'], 'ignore_panels': [],
             'caption': 'Fig. 1.', 'hints': [{'panel': 'A', 'mark_types': ['bar']}]}

        def run(unit, mul, xunit=None):
            p = self.pan('A', [10, 20])
            p['y_left'] = dict(p['y_left'], unit=unit, multiplier=mul)
            p['x_axis'] = dict(p['x_axis'], unit=xunit)
            r = self.reading([p])
            r['scope'] = ['A']
            return r

        def merged(a, b):
            rows = fr.merge({'fig1': t}, [('run1', {'fig1': a}), ('run2', {'fig1': b})])
            return rows, fr.select_rows(rows)
        rows, (acc, rej) = merged(run('µmol/g', None, '℃'), run('μmol/g', '1', '°C'))
        self.assertEqual([r['confidence'] for r in rows], ['high', 'high'])
        self.assertEqual((len(acc), len(rej)), (2, 0))
        rows, (acc, rej) = merged(run('', '×10⁵'), run('A633 nm', 'x10^5'))
        self.assertEqual([r['confidence'] for r in rows], ['high', 'high'])
        self.assertEqual([r['Y单位'] for r in rows], ['A633 nm', 'A633 nm'])     # 显示写了单位的那一遍
        self.assertEqual((len(acc), len(rej)), (2, 0))
        rows, _ = merged(run('%', '10^3'), run('%', '10^5'))
        self.assertTrue(all(r['confidence'] == 'invalid' and 'mul 冲突' in r['review_reason'] for r in rows))
        rows, _ = merged(run('mV', None), run('V', None))
        self.assertTrue(all(r['confidence'] == 'invalid' and 'yu 冲突' in r['review_reason'] for r in rows))
        # 一遍在单位前面多写了指标名（用户 2026-10-12）：「FS %」和「%」、「Ser-NH₂ equiv/g …」和「equiv/g …」不算冲突；
        # 前面多的是单位（mg %）的照旧算冲突
        rows, (acc, rej) = merged(run('FS %', None), run('%', None))
        self.assertEqual(([r['confidence'] for r in rows], len(acc), len(rej)), (['high', 'high'], 2, 0))
        self.assertTrue(fr.unit_same('Ser-NH₂ equiv/g soluble protein', 'equiv/g soluble protein'))
        self.assertTrue(fr.unit_same('LD %', '%'))
        self.assertFalse(fr.unit_same('mg %', '%'))
        self.assertFalse(fr.unit_same('mL %', '%'))
        self.assertFalse(fr.unit_same('g/100 g', 'g'))
        rows, _ = merged(run('mg %', None), run('%', None))
        self.assertTrue(all(r['confidence'] == 'invalid' and 'yu 冲突' in r['review_reason'] for r in rows))
        # 用户 2026-10-12：单位中间多写了被测物名的（0c00757）、倍率写进单位的（jf402159a）也算同一个写法
        self.assertTrue(fr.unit_same('mol free thiol / mol protein', 'mol/mol protein'))
        self.assertTrue(fr.unit_same('% (w/v)', '%(w/v)'))
        self.assertTrue(fr.unit_same('mol L^-1', 'mol L⁻¹'))
        self.assertFalse(fr.unit_same('mol/L', 'mmol/L'))
        for a, b in ((('10^-6 mol L^-1', None), ('x 10⁻⁶ mol L⁻¹', '10^-6')),
                     (('mol L^-1', '10^-6'), ('10^-6 mol L^-1', '1')),
                     (('×10³ g', None), ('g', 'x10^3'))):
            rows, (acc, rej) = merged(run(*a), run(*b))
            self.assertEqual(([r['confidence'] for r in rows], len(acc)), (['high', 'high'], 2), (a, b))
        rows, _ = merged(run('10^-3 mol L^-1', None), run('10^-6 mol L^-1', None))
        self.assertTrue(all(r['confidence'] == 'invalid' and 'mul 冲突' in r['review_reason'] for r in rows))

    def test_generic_inset_label(self):
        """分类把没印编号的嵌入小图叫作「inset」（用户 2026-10-12，jafc.0c05792 图 1）：当作没有编号，起名「未编号1」、
        读图指令里按图型和坐标轴点名；色谱主图照旧不读。"""
        main = self.panel(label='main', mark_types=['line'], chart_type='line', x_axis_label='Time (min)',
                          y_axis_label='Absorbance (mAu)', functional_property='none', n_series=1, points_per_series=200)
        inset = self.panel(label='inset', x_axis_label='Fraction', y_axis_label='Zinc binding capacity (%)',
                           functional_property='antioxidant', n_series=1, points_per_series=3)
        item = {'key': 'fig1', 'label': '1', 'heading': 'Figure 1', 'files': ['fig1.png'], 'caption': 'Figure 1.'}
        t = fr.figure_target(item, {'data': {'n_panels': 2, 'panels': [main, inset], 'caption_topic': 'x', 'notes': None}})
        self.assertEqual(t['read_panels'], ['未编号1'])
        text = fr.panel_instruction(t)
        self.assertIn('只提取它们：未编号1。', text)
        self.assertIn('Y 轴「Zinc binding capacity (%)」', text)
        self.assertIn('X 轴「Fraction」', text)
        self.assertNotIn('inset', text)

    def test_reversed_axis_error_bars(self):
        """纵轴倒过来画（ζ-电位越往上越负）时模型常把误差棒两端对调（用户 2026-10-12，jafc.0c01250 图 5A 两遍都判读图失败）：
        两端按大小排一下再比，读数夹在中间就正常；只有一端、读数是负数的不比；读数在两端之外的照旧判异常。"""
        self.assertTrue(fr.error_bars_ok(-32, -31, -33))
        self.assertTrue(fr.error_bars_ok(-32, None, -33))
        self.assertTrue(fr.error_bars_ok(10, 9, 11))
        self.assertFalse(fr.error_bars_ok(10, 12, 13))
        self.assertFalse(fr.error_bars_ok(10, None, 8))
        self.assertFalse(fr.error_bars_ok(-32, -20, -25))
        t = {'key': 'fig5', 'kind': 'figure', 'label': '5', 'case': False, 'read_panels': ['A'], 'ignore_panels': [],
             'caption': 'Figure 5.', 'hints': [{'panel': 'A', 'mark_types': ['bar']}]}
        p = self.pan('A', [-32.0, -40.0])
        p['y_left'] = dict(p['y_left'], min=-50.0, max=0.0)
        for q in p['points']:
            q['err_low'], q['err_high'] = q['y_value'] + 1, q['y_value'] - 1        # 画面上的上端（数值更小）填进了上限
        rec = fr.check_reading(t, {'panels': [p], 'confidence': None, 'note': None})
        self.assertTrue(rec['ok'], rec['flags'])
        rec['scope'] = ['A']
        rows = fr.merge({'fig5': t}, [('run1', {'fig5': rec}), ('run2', {'fig5': rec})])
        self.assertEqual([(r['误差棒下限'], r['误差棒上限']) for r in rows], [(-33.0, -31.0), (-41.0, -39.0)])

    def test_single_read_marked(self):
        """只有一遍读出的点（用户 2026-10-12）：照样写进表里，入库判定一栏标「只有一遍读出」，原因一栏不另写；
        子图标题和评价里单独计数；不入库。"""
        t = {'key': 'fig1', 'kind': 'figure', 'label': '1', 'case': False, 'read_panels': ['A'], 'ignore_panels': [],
             'caption': 'Fig. 1.', 'hints': [{'panel': 'A', 'mark_types': ['bar']}]}
        r1, r2 = self.reading([self.pan('A', [10, 20, 30])]), self.reading([self.pan('A', [10, 20])])
        r1['scope'] = r2['scope'] = ['A']
        rows = fr.merge({'fig1': t}, [('run1', {'fig1': r1}), ('run2', {'fig1': r2})])
        acc, rej = fr.select_rows(rows)
        self.assertEqual((len(acc), len(rej)), (2, 1))
        self.assertTrue(fr.is_single(*rej[0]))
        table, n_ok, n_bad, n_review = fr.panel_table(rows)
        self.assertIn('| WPI | S2 | % | 30 | % | 1/1 |  | low | **只有一遍读出** |', table)
        self.assertNotIn('重复读取的有效覆盖不足', table)
        self.assertEqual(fr.review_line(acc, rej), '- 反读表含 2 个通过数值筛选的点、1 个只有一遍读出的点和 0 个未满足要求的点，'
                                                   '均已在对应表内标注。')
        # 同一个点分成了两行：单位只是写法不同、读数一样的照常通过；单位真的不一样的全部转人工
        a = {'图片名': 'fig1', '子图': 'A', '系列': 'WPI', 'X类别/数值': 'S0', 'X单位': '℃', 'Y值': 10.0, 'Y单位': 'µmol/g',
             'Y轴': 'left', '轴倍率': '', 'confidence': 'high', 'y_spread_pct': 0.0, 'n_runs_valid': 2,
             'n_runs_expected': 2, 'review_reason': ''}
        acc, rej = fr.select_rows([a, dict(a, **{'X单位': '°C', 'Y单位': 'μmol/g', '轴倍率': '1'})])
        self.assertEqual((len(acc), len(rej)), (1, 0))
        acc, rej = fr.select_rows([a, dict(a, **{'Y单位': 'mmol/g'})])
        self.assertEqual((len(acc), len(rej)), (0, 2))

    def test_third_read_only_disagreeing_panels(self):
        """第三遍只读有问题的子图：某一遍漏读的点，和两遍都读到、相差超过 5% 又超过满量程 1% 的点（用户 2026-10-12；
        10-09 到 10-12 之间后一种不补）。三遍里两遍一致就采用那两遍；三遍两两都不一致才取中位数转人工复核。"""
        t = {'key': 'fig1', 'kind': 'figure', 'label': '1', 'case': False, 'read_panels': ['A', 'B', 'C', 'E', 'F'],
             'ignore_panels': ['D'], 'caption': 'Fig. 1.',
             'hints': [{'panel': 'A', 'mark_types': ['bar']}, {'panel': 'B', 'mark_types': ['bar']},
                       {'panel': 'C', 'mark_types': ['line']}, {'panel': 'E', 'mark_types': ['bar']},
                       {'panel': 'F', 'mark_types': ['bar']}]}
        run1 = self.reading([self.pan('A', [10, 20]), self.pan('B', [30, 40]), self.pan('C', []), self.pan('E', [5, 9]),
                             self.pan('F', [50, 9])])
        run2 = self.reading([self.pan('A', [10, 20]), self.pan('B', [30]), self.pan('C', []), self.pan('E', [5, 15]),
                             self.pan('F', [50, 15])])
        run1['scope'] = run2['scope'] = ['A', 'B', 'C', 'E', 'F']
        plan = fr.retry_plan({'fig1': t}, [('run1', {'fig1': run1}), ('run2', {'fig1': run2})])
        self.assertEqual(plan, {'fig1': ['B', 'E', 'F']})    # B 第 2 遍漏了一个点；E、F 两遍差 6 个刻度单位（满量程 6%）
        third = fr.narrowed(t, set(plan['fig1']))
        text = fr.panel_instruction(third)
        self.assertIn('只提取它们：B、E、F。', text)
        self.assertIn('其余子图（D、A、C）', text)
        run3 = fr.check_reading(third, {'panels': [self.pan('B', [30, 41]), self.pan('E', [8, 9.3]), self.pan('F', [50, 30])],
                                        'confidence': None, 'note': None})
        self.assertEqual(run3['scope'], ['B', 'E', 'F'])
        rows = fr.merge({'fig1': t}, [('run1', {'fig1': run1}), ('run2', {'fig1': run2}), ('run3', {'fig1': run3})])
        a = [r for r in rows if r['子图'] == 'A']
        self.assertTrue(all(r['n_runs_expected'] == 2 and r['confidence'] == 'high' for r in a))
        b = [r for r in rows if r['子图'] == 'B' and r['X类别/数值'] == 'S1'][0]
        self.assertEqual((b['n_runs_expected'], b['n_runs_valid'], b['Y值']), (3, 2, 40.5))   # 第三遍补上了漏读的点
        # E：9 / 15 / 9.3，第 1、3 遍一致 → 取这两遍的平均 9.15，写明第 2 遍没采用；一致性最多 medium
        e = [r for r in rows if r['子图'] == 'E' and r['X类别/数值'] == 'S1'][0]
        self.assertEqual((e['Y值'], e['y_spread_pct'], e['n_runs_valid'], e['confidence']), (9.15, 3.279, 3, 'medium'))
        self.assertEqual(e['说明'], '3 遍里 2 遍一致（9 / 9.3），第 2 遍 15 和它们差得多，没采用')
        # E 的 S0 前两遍本来就一致（5 / 5），第三遍是为 S1 补读的、读成 8：只用前两遍，一致性照两遍算
        e0 = [r for r in rows if r['子图'] == 'E' and r['X类别/数值'] == 'S0'][0]
        self.assertEqual((e0['Y值'], e0['y_spread_pct'], e0['confidence']), (5, 0.0, 'high'))
        self.assertEqual(e0['说明'], '前两遍一致（5 / 5），第 3 遍 8 和它们差得多，没采用')
        # 用户 2026-10-12 选 F：前两遍不一致、靠第三遍凑出两遍一致的，给这两遍的平均值，仍转人工复核
        acc, rej = fr.select_rows(rows)
        self.assertNotIn(fr.point_key(e), {fr.point_key(r) for r in acc})
        why = dict((fr.point_key(r), w) for r, w in rej)[fr.point_key(e)]
        self.assertTrue(fr.is_deviation(why))
        self.assertEqual(fr.why_rejected(e, why, rows),
                         '3 遍里 2 遍一致（9 / 9.3），第 2 遍 15 和它们差得多，没采用；表中取这两遍的平均值，需人工复核。')
        table, n_ok, n_bad, n_review = fr.panel_table([r for r in rows if r['子图'] == 'E'])
        self.assertEqual((n_ok, n_bad, n_review), (1, 1, 1))
        self.assertIn('| 满足数值门槛 |  | 前两遍一致（5 / 5），第 3 遍 8 和它们差得多，没采用 |', table)
        self.assertIn('| **需人工复核** | 3 遍里 2 遍一致（9 / 9.3），第 2 遍 15 和它们差得多，没采用；表中取这两遍的平均值，'
                      '需人工复核。 |  |', table)
        # F：9 / 15 / 30 两两都不一致 → 取中位数 15、需人工复核
        f = [r for r in rows if r['子图'] == 'F' and r['X类别/数值'] == 'S1'][0]
        self.assertEqual((f['Y值'], f['y_spread_pct'], f['y_diff_fs_pct']), (15, 140.0, 21.0))
        why = dict((fr.point_key(r), w) for r, w in rej)[fr.point_key(f)]
        self.assertTrue(fr.is_deviation(why))
        self.assertEqual(fr.why_rejected(f, why, rows), '三遍读数 9 / 15 / 30，两两都不一致，相差 140.0%（约为纵轴满量程的 21%），'
                                                        '超过 5%，也超过满量程的 1%；表中取中位数，需人工复核。')
        table, n_ok, n_bad, n_review = fr.panel_table([r for r in rows if r['子图'] == 'F'])
        self.assertEqual((n_ok, n_bad, n_review), (1, 1, 1))
        self.assertIn('| **需人工复核** |', table)
        # 第三遍没读成（连续两次没过自检）时只有两遍：取平均值、需人工复核
        rows = fr.merge({'fig1': t}, [('run1', {'fig1': run1}), ('run2', {'fig1': run2})])
        e = [r for r in rows if r['子图'] == 'E' and r['X类别/数值'] == 'S1'][0]
        why = dict((fr.point_key(r), w) for r, w in fr.select_rows(rows)[1])[fr.point_key(e)]
        self.assertEqual(fr.why_rejected(e, why, rows), '两遍读数 9 / 15，相差 50.0%（约为纵轴满量程的 6%），'
                                                        '超过 5%，也超过满量程的 1%；表中取平均值，需人工复核。')

    def test_small_values_judged_by_full_scale(self):
        """小数值（用户 2026-10-12）：0–100 的轴上两遍读 0.5 和 0.6，离散度 18%，但只差满量程的 0.1% → 算一致、通过，
        表里写明；只差满量程 2% 的仍不通过。读图没报刻度范围时，满量程按这个子图同一纵轴上的最大读数算。"""
        t = {'key': 'fig1', 'kind': 'figure', 'label': '1', 'case': False, 'read_panels': ['A'], 'ignore_panels': [],
             'caption': 'Fig. 1.', 'hints': [{'panel': 'A', 'mark_types': ['bar']}]}

        def run(ys, axis_range=True):
            p = self.pan('A', ys)
            if not axis_range:
                p['y_left'] = dict(p['y_left'], min=None, max=None)
            r = self.reading([p])
            r['scope'] = ['A']
            return r
        rows = fr.merge({'fig1': t}, [('run1', {'fig1': run([0.5, 50, 3])}), ('run2', {'fig1': run([0.6, 50, 5])})])
        small, big = rows[0], rows[2]
        self.assertEqual((small['y_spread_pct'], small['y_diff_fs_pct'], small['confidence']), (18.182, 0.1, 'medium'))
        self.assertEqual(small['说明'], '数值小：几遍最多只差纵轴满量程的 0.1%，按满量程判为一致')
        self.assertEqual(big['y_diff_fs_pct'], 2.0)
        acc, rej = fr.select_rows(rows)
        self.assertEqual(sorted(r['X类别/数值'] for r in acc), ['S0', 'S1'])
        self.assertEqual([r['X类别/数值'] for r, _ in rej], ['S2'])
        self.assertEqual(fr.retry_plan({'fig1': t}, [('run1', {'fig1': run([0.5, 50, 3])}),
                                                       ('run2', {'fig1': run([0.6, 50, 5])})]), {'fig1': ['A']})
        table = fr.panel_table(rows)[0]
        self.assertIn('| 满足数值门槛 |  | 数值小：几遍最多只差纵轴满量程的 0.1%，按满量程判为一致 |', table)
        # 没报刻度范围：满量程 = 最大读数 50
        rows = fr.merge({'fig1': t}, [('run1', {'fig1': run([0.5, 50, 3], False)}),
                                      ('run2', {'fig1': run([0.6, 50, 5], False)})])
        self.assertEqual([r['y_diff_fs_pct'] for r in rows], [0.2, 0.0, 4.0])

    def test_third_read_uses_agreed_names(self):
        """第三遍沿用前两遍的名称（用户 2026-10-12）：只给前两遍写法统一后一致的系列名、样品名（第一遍的写法），
        只有一遍有的不给；数字标签不进名单；不给读数。"""
        t = {'key': 'fig1', 'kind': 'figure', 'label': '1', 'case': False, 'read_panels': ['A', 'B'], 'ignore_panels': [],
             'caption': 'Fig. 1.', 'hints': [{'panel': 'A', 'mark_types': ['bar']}, {'panel': 'B', 'mark_types': ['bar']}]}

        def rec(names, cats):
            pts = [dict(series=n, x_category=c, y_value=1.0) for n, _ in names for c in cats]
            return {'ok': True, 'data': {'panels': [
                {'panel_id': 'A', 'series': [{'name': n, 'axis': ax} for n, ax in names], 'points': pts},
                {'panel_id': 'B', 'series': [{'name': 'WPI', 'axis': 'left'}],
                 'points': [dict(series='WPI', x_category='0', y_value=1.0), dict(series='WPI', x_category='6', y_value=2.0)]}]}}
        r1 = rec([('Chickpea—暗红色圆点', 'left'), ('SPI', 'left'), ('PDI', 'right')], ['Native', 'Dry'])
        r2 = rec([('Chickpea：暗红色圆点', 'left'), ('PDI', 'right')], ['native', 'Dry', '4.5'])
        names = fr.agreed_names(t, [r1, r2])
        self.assertEqual(names, {'A': {'series': [('Chickpea—暗红色圆点', 'left'), ('PDI', 'right')], 'cats': ['Native', 'Dry']},
                                 'B': {'series': [('WPI', 'left')], 'cats': []}})
        third = fr.narrowed(dict(t, names=names), {'A'})
        text = fr.panel_instruction(third)
        self.assertTrue(text.endswith(fr.GIVEN_NAMES + '\n- 子图 A：系列名 「Chickpea—暗红色圆点」（左轴）、「PDI」（右轴）；'
                                                         '样品名 「Native」、「Dry」'))
        self.assertNotIn(fr.GIVEN_NAMES, fr.panel_instruction(t))            # 前两遍不带
        self.assertEqual(fr.agreed_names(t, [r1, {'ok': False}]), {})       # 有一遍没读成：不给

    def test_series_names_and_blank_x(self):
        """配对（用户 2026-10-12）：两遍对同一条系列的写法不同（破折号 / 冒号、全角、大小写、模型自己加的 [bar] /（柱）），
        统一后配成一个点；哪一遍里本来就有两条写法统一后一样的系列，不统一。没写 X 的点每遍一个时配成同一个点。"""
        t = {'key': 'fig1', 'kind': 'figure', 'label': '1', 'case': False, 'read_panels': ['A'], 'ignore_panels': [],
             'caption': 'Fig. 1.', 'hints': [{'panel': 'A', 'mark_types': ['bar', 'point']}]}

        def run(series, xs=('S1', 'S2')):
            axis = dict(label='y', unit='%', scale='linear', min=0.0, max=100.0, ticks=None, starts_at_zero=True,
                        multiplier=None)
            pts = [dict(series=name, point_index=i + 1, x_category=x, x_value=None, y_value=y + i, err_low=None,
                        err_high=None, estimated=False, sig=None, note=None)
                   for name, _, y in series for i, x in enumerate(xs)]
            p = dict(panel_id='A', chart_type='combo', x_axis=axis, y_left=axis, y_right=dict(axis, unit='nm'),
                     series=[dict(name=name, axis=ax, chart_type='bar') for name, ax, _ in series], points=pts)
            r = self.reading([p])
            r['scope'] = ['A']
            return r

        def merged(a, b):
            return fr.merge({'fig1': t}, [('run1', {'fig1': a}), ('run2', {'fig1': b})])
        rows = merged(run([('Chickpea—暗红色圆点', 'left', 40), ('0 U [bar]', 'left', 20), ('0 U [line]', 'right', 70)]),
                      run([('Chickpea：暗红色圆点', 'left', 40), ('0 U（柱）', 'left', 20), ('0 u (点线)', 'right', 70)]))
        self.assertEqual(sorted({(r['系列'], r['Y轴']) for r in rows}),
                         [('0 U [bar]', 'left'), ('0 U [line]', 'right'), ('Chickpea—暗红色圆点', 'left')])
        self.assertTrue(all(r['n_runs_valid'] == 2 and r['confidence'] == 'high' for r in rows))
        # 用词一样、只是顺序不同的算同一条（用户 2026-10-12，afres.2026.102097）；某一遍里本来就有两条这样的，不统一
        rows = merged(run([('Air phase fraction (0% sucrose)', 'left', 40)]), run([('0% sucrose - Air phase fraction', 'left', 40)]))
        self.assertEqual([(r['系列'], r['n_runs_valid']) for r in rows],
                         [('Air phase fraction (0% sucrose)', 2), ('Air phase fraction (0% sucrose)', 2)])
        rows = merged(run([('WPI-CS', 'left', 40), ('CS-WPI', 'left', 60)]), run([('WPI CS', 'left', 40), ('CS-WPI', 'left', 60)]))
        self.assertEqual(sorted({(r['系列'], r['n_runs_valid']) for r in rows}), [('CS-WPI', 2), ('WPI-CS', 2)])   # 写法统一照样配上
        # 第 1 遍本来就有 WPI 和 wpi 两组：按写法不统一；按数值（2026-10-13）第 2 遍的 Wpi 和 WPI 读数一样，配成一组
        rows = merged(run([('WPI', 'left', 40), ('wpi', 'left', 60)]), run([('Wpi', 'left', 40), ('wpi', 'left', 60)]))
        self.assertEqual(sorted({(r['系列'], r['n_runs_valid']) for r in rows}), [('WPI', 2), ('wpi', 2)])
        rows = merged(run([('WPI', 'left', 40), ('wpi', 'left', 60)]), run([('Wpi', 'left', 80), ('wpi', 'left', 60)]))
        self.assertEqual(sorted({r['系列'] for r in rows}), ['WPI', 'Wpi', 'wpi'])        # 读数对不上：不配
        # 没写 X：每遍一个点 → 同一个点；某一遍有两个 → 分不清，照旧各自一组
        rows = merged(run([('Control', 'left', 18.8)], xs=(None,)), run([('Control', 'left', 18.7)], xs=(None,)))
        self.assertEqual([(r['n_runs_valid'], r['Y值'], r['confidence']) for r in rows], [(2, 18.75, 'high')])
        rows = merged(run([('Control', 'left', 18.8)], xs=(None, None)), run([('Control', 'left', 18.7)], xs=(None,)))
        self.assertEqual(len(rows), 3)

    def test_series_matched_by_values(self):
        """名字配不上、数值是同一条线的按数值配（用户 2026-10-13；jf0607866 三遍把同一条浊度线写成三个名字，
        原来各自只算一遍读出）。一条配上好几条的、读数对不上的、相同 X 不到 2 个的、UNRESOLVED 的都不配。"""
        t = {'key': 'fig1', 'kind': 'figure', 'label': '1', 'case': False, 'read_panels': ['A'], 'ignore_panels': [],
             'caption': 'Fig. 1.', 'hints': [{'panel': 'A', 'mark_types': ['point']}]}

        def run(series, xs=(6.0, 6.1, 6.2, 6.3)):
            axis = dict(label='y', unit='RU', scale='linear', min=0.0, max=1.6, ticks=None, starts_at_zero=True,
                        multiplier=None)
            pts = [dict(series=name, point_index=i + 1, x_category=None, x_value=x, y_value=ys[i], err_low=None,
                        err_high=None, estimated=False, sig=None, note=None)
                   for name, _, ys in series for i, x in enumerate(xs[:len(ys)])]
            p = dict(panel_id='A', chart_type='line', x_axis=dict(axis, unit='', max=7.0), y_left=axis,
                     y_right=dict(axis, unit='nm', max=300.0),
                     series=[dict(name=name, axis=ax, chart_type='line') for name, ax, _ in series], points=pts)
            r = self.reading([p])
            r['scope'] = ['A']
            return r

        def merged(*rs):
            return fr.merge({'fig1': t}, [('run%d' % (i + 1), {'fig1': r}) for i, r in enumerate(rs)])
        size = ('Particle size', 'right', [258, 172, 143, 132])
        rows = merged(run([('Turbidity', 'left', [1.42, 0.19, 0.12, 0.06]), size]),
                      run([('Turbidity (A600)', 'left', [1.42, 0.20, 0.13, 0.06]), size]),
                      run([('Turbidity (A600, RU)', 'left', [1.42, 0.20, 0.13, 0.05]), size]))
        self.assertEqual(sorted({(r['系列'], r['Y轴'], r['n_runs_valid']) for r in rows}),
                         [('Particle size', 'right', 3), ('Turbidity', 'left', 3)])
        # 两遍里各有一条叫错了：照样配上（用第一遍的写法）
        rows = merged(run([('Closed circle', 'left', [1.4, 1.0, 0.8, 0.6]), ('Open circle', 'left', [0.2, 0.6, 0.9, 1.1])]),
                      run([('WPI pH 6.0', 'left', [1.41, 1.0, 0.82, 0.6]), ('Open circle', 'left', [0.2, 0.6, 0.9, 1.1])]))
        self.assertEqual(sorted({(r['系列'], r['n_runs_valid']) for r in rows}), [('Closed circle', 2), ('Open circle', 2)])
        # 一遍里有两条几乎重合的线、另一遍只读出一条：分不清是哪条，不配
        rows = merged(run([('Closed circle', 'left', [1.4, 1.0, 0.8, 0.6]), ('Closed triangle', 'left', [1.41, 1.0, 0.81, 0.6])]),
                      run([('Sample A', 'left', [1.4, 1.0, 0.8, 0.6])]))
        self.assertEqual(sorted({r['系列'] for r in rows}), ['Closed circle', 'Closed triangle', 'Sample A'])
        # 读数对不上、相同 X 只有一个、没认出系列（UNRESOLVED）的：不配
        rows = merged(run([('A', 'left', [1.4, 1.0, 0.8, 0.6])]), run([('B', 'left', [0.4, 0.3, 0.2, 0.1])]))
        self.assertEqual(sorted({r['系列'] for r in rows}), ['A', 'B'])
        rows = merged(run([('A', 'left', [1.4])]), run([('B', 'left', [1.4])]))
        self.assertEqual(sorted({r['系列'] for r in rows}), ['A', 'B'])
        rows = merged(run([('A', 'left', [1.4, 1.0, 0.8, 0.6])]), run([('UNRESOLVED_1', 'left', [1.4, 1.0, 0.8, 0.6])]))
        self.assertEqual(sorted({r['系列'] for r in rows}), ['A', 'UNRESOLVED_1'])

    def test_generalized_checks_1013(self):
        """用户 2026-10-13「全都改吧」：读图失败的 11 张图看出的几类，不再让整张图失败。"""
        t = {'key': 'fig1', 'kind': 'figure', 'label': '1', 'case': False, 'read_panels': ['A'], 'ignore_panels': [],
             'hints': [{'panel': 'A', 'mark_types': ['point']}]}

        def axis(lo, hi, scale='linear', ticks=None):
            return dict(label='y', unit=None, scale=scale, min=lo, max=hi, ticks=ticks, starts_at_zero=True, multiplier=None)

        def pt(series, x, y):
            return dict(series=series, point_index=1, x_category=None, x_value=x, y_value=y, err_low=None,
                        err_high=None, estimated=False, sig=None, note=None)

        def panel(series, points, pid='A', **axes):
            p = dict(panel_id=pid, chart_type='line', x_axis=axis(0, 10), y_left=axes.get('y_left', axis(0, 70)),
                     y_right=axes.get('y_right'), series=[dict(name=n, axis=a, chart_type='line') for n, a in series],
                     points=points)
            if 'y_third' in axes:
                p['y_third'] = axes['y_third']
            return {'panels': [p], 'confidence': None, 'note': None}

        # 对数纵轴：最高标到 1000、点在 1350 —— 按一个数量级算不超出（jafc.6b02966 图 6A）；超出一个数量级照旧判
        log = axis(0.01, 1000.0, 'log', '0.01, 0.1, 1, 10, 100, 1000')
        rec = fr.check_reading(t, panel([('PDI', 'left'), ('Size', 'right')],
                                        [pt('PDI', 0, 0.2), pt('PDI', 2, 0.3), pt('Size', 0, 300.0), pt('Size', 2, 1350.0)],
                                        y_left=axis(0, 3), y_right=log))
        self.assertTrue(rec['ok'], rec['flags'])
        self.assertFalse(fr.outside_axis(log, 5000.0))
        self.assertTrue(fr.outside_axis(log, 20000.0))
        self.assertTrue(fr.outside_axis(log, -1.0))
        # 第三条纵轴：系列 axis 填 third，按 y_third 的刻度比（jafc.9b02003 图 2a）
        three = panel([('Size', 'left'), ('Zeta', 'right'), ('PdI', 'third')],
                      [pt('Size', 0, 198.0), pt('Size', 1, 150.0), pt('Zeta', 0, -52.6), pt('Zeta', 1, -44.2),
                       pt('PdI', 0, 0.41), pt('PdI', 1, 0.2)],
                      y_left=axis(0, 220), y_right=axis(-60, 0), y_third=axis(0, 1.0))
        rec = fr.check_reading(t, three)
        self.assertTrue(rec['ok'], rec['flags'])
        pts = fr.load_points({'fig1': t}, 'run1', {'fig1': dict(rec, scope=['A'])})
        self.assertEqual({(q['series'], q['axis'], q['span']) for q in pts},
                         {('Size', 'left', 220.0), ('Zeta', 'right', 60.0), ('PdI', 'third', 1.0)})
        # 少数点超出刻度（图上文字标的 167）：只丢这个点、写明，其余照收（jafc.1c00432 图 2）；过半超出照旧判失败
        rec = fr.check_reading(t, panel([('SPI', 'left'), ('LEC', 'left')],
                                        [pt('SPI', 0, 1.0), pt('SPI', 2, 167.0), pt('SPI', 4, 12.0),
                                         pt('LEC', 0, 1.0), pt('LEC', 2, 18.0), pt('LEC', 4, 34.0)]))
        self.assertTrue(rec['ok'], rec['flags'])
        self.assertEqual(len(rec['data']['panels'][0]['points']), 5)
        self.assertEqual(rec['out_of_range'], {'A': ['SPI 2=167.0']})
        self.assertTrue(any('只丢这几个点' in f for f in rec['flags']))
        rec = fr.check_reading(t, panel([('PSH', 'left')], [pt('PSH', 0, 160.0), pt('PSH', 2, 190.0), pt('PSH', 4, 30.0)]))
        self.assertFalse(rec['ok'])
        # 单系列：点上的名字和列表里的不一样，就是这一条（acsfoodscitech.1c00288 图 2）
        rec = fr.check_reading(t, panel([('Zeta potential', 'left')], [pt('Zeta practical', 0, 3.0), pt('Zeta practical', 1, 2.0)]))
        self.assertTrue(rec['ok'], rec['flags'])
        self.assertEqual([s['name'] for s in rec['data']['panels'][0]['series']], ['Zeta practical'])
        rec = fr.check_reading(t, panel([], [pt('Zeta', 0, 3.0), pt('Zeta', 1, 2.0)]))
        self.assertTrue(rec['ok'], rec['flags'])
        # 多系列：不在图例里的系列不过半就只丢它的点（jafc.5c17360 图 8a）；过半照旧判失败
        legend = [('SGF', 'left'), ('SIF', 'left')]
        rec = fr.check_reading(t, panel(legend, [pt('SGF', 0, 9.0), pt('SGF', 1, 8.0), pt('SIF', 0, 7.0), pt('SIF', 1, 6.0),
                                                 pt('CX@Lut', 2, 5.0)]))
        self.assertTrue(rec['ok'], rec['flags'])
        self.assertEqual(rec['orphan_series'], {'A': ['CX@Lut']})
        rec = fr.check_reading(t, panel(legend, [pt('SGF', 0, 9.0), pt('X1', 1, 8.0), pt('X2', 0, 7.0)]))
        self.assertFalse(rec['ok'])
        # 子图名带括号说明：「A (lower panel)」和读图回来的「A」认作同一个（jafc.7b05889 图 3）
        t2 = dict(t, read_panels=['A (lower panel)', 'B (lower panel)'])
        raw = {'panels': [panel([('SPN', 'left')], [pt('SPN', 0, 10.0)], pid=pid)['panels'][0] for pid in ('A', 'B')],
               'confidence': None, 'note': None}
        rec = fr.check_reading(t2, raw)
        self.assertEqual([p['panel_id'] for p in rec['data']['panels']], ['A (lower panel)', 'B (lower panel)'])
        self.assertEqual(fr._core('(c) C'), '(c) C')
        # 单位里的坏字符（jf300409y 图 9：一遍把 °C 写成 \x00C、μM 写成单独的组合附加符号）当作没写，不算冲突
        self.assertEqual(fr.canonical_unit('\x00C'), '')
        self.assertEqual(fr.canonical_unit('F / mg \u0327M'), '')
        self.assertEqual(fr.canonical_unit('°C'), '°C')
        self.assertEqual(fr.canonical_unit('µmol TE/g'), 'µmol TE/g')
        self.assertEqual(fr.canonical_unit('Å'), 'Å')
        # 读图指令写了三条纵轴、拆系列、两层横轴
        self.assertIn('y_third', fr.panel_instruction(t))
        self.assertIn('两层', fr.panel_instruction(t))

    def test_sample_names_written_differently(self):
        """同一系列里样品名写法不同的配成同一个点（用户 2026-10-13「加一条规则」）；同一遍里本来就有两个统一后一样的不统一；
        有单独数字、百分数的样品名词序不能乱换；不按读数配。"""
        t = {'key': 'fig1', 'kind': 'figure', 'label': '1', 'case': False, 'read_panels': ['A'], 'ignore_panels': [],
             'hints': [{'panel': 'A', 'mark_types': ['bar']}]}

        def run(cats):
            axis = dict(label='y', unit='%', scale='linear', min=0.0, max=100.0, ticks=None, starts_at_zero=True,
                        multiplier=None)
            pts = [dict(series='EAI', point_index=i + 1, x_category=c, x_value=None, y_value=y, err_low=None,
                        err_high=None, estimated=False, sig=None, note=None) for i, (c, y) in enumerate(cats)]
            p = dict(panel_id='A', chart_type='bar', x_axis=dict(axis, unit=None), y_left=axis, y_right=None,
                     series=[dict(name='EAI', axis='left', chart_type='bar')], points=pts)
            r = self.reading([p])
            r['scope'] = ['A']
            return r

        def merged(a, b):
            return fr.merge({'fig1': t}, [('run1', {'fig1': a}), ('run2', {'fig1': b})])
        rows = merged(run([('45% sucrose 60 s', 40.0), ('I • IIb', 20.0), ('PPI 1 hr', 30.0), ('3R 5P', 50.0)]),
                      run([('45% sucrose 60s', 40.2), ('I·IIb', 20.1), ('PPI 1h', 30.0), ('5P 3R', 50.5)]))
        self.assertEqual(sorted((r['X类别/数值'], r['n_runs_valid']) for r in rows),
                         [('3R 5P', 2), ('45% sucrose 60 s', 2), ('I • IIb', 2), ('PPI 1 hr', 2)])
        # 同一遍里本来就有「60 s」「60s」两个：分不清，不统一
        rows = merged(run([('45% sucrose 60 s', 40.0), ('45% sucrose 60s', 41.0)]), run([('45% sucrose 60s', 40.2)]))
        self.assertEqual(sorted((r['X类别/数值'], r['n_runs_valid']) for r in rows),
                         [('45% sucrose 60 s', 1), ('45% sucrose 60s', 2)])     # 一字不差的照旧配上
        # 词序：有单独百分数的不能换（不是同一个样品），读数再接近也不配
        rows = merged(run([('1% CS 2% LF', 40.0)]), run([('2% CS 1% LF', 40.1)]))
        self.assertEqual(len(rows), 2)
        rows = merged(run([('1% CS', 0.84)]), run([('14% LF', 0.8)]))
        self.assertEqual(len(rows), 2)

    def test_compound_panel_label(self):
        """组图编号「(c) C」，读图模型只写「C」：唯一对得上时认作同一个（foodchem.2025.147510 图 7）。"""
        t = {'key': 'fig7', 'kind': 'figure', 'label': '7', 'case': False, 'read_panels': ['(c) C'],
             'ignore_panels': ['(a) C', '(b) A'], 'hints': [{'panel': '(c) C', 'mark_types': ['bar']}]}
        rec = fr.check_reading(t, {'panels': [self.pan('C', [10, 20])], 'confidence': None, 'note': None})
        self.assertTrue(rec['ok'], rec['flags'])
        self.assertEqual([p['panel_id'] for p in rec['data']['panels']], ['(c) C'])
        self.assertEqual(rec['scope'], ['(c) C'])
        # 两个要读的子图最后一级都是 C、只回来一个 C：分不清是哪个，照旧丢掉
        two = dict(t, read_panels=['(a) C', '(c) C'])
        rec = fr.check_reading(two, {'panels': [self.pan('C', [10, 20])], 'confidence': None, 'note': None})
        self.assertEqual(rec['data']['panels'], [])
        # 一个精确对上，另一个只写了 C：剩下的那个唯一，认作 (c) C
        rec = fr.check_reading(two, {'panels': [self.pan('(a) C', [1, 2]), self.pan('C', [10, 20])],
                                     'confidence': None, 'note': None})
        self.assertEqual([p['panel_id'] for p in rec['data']['panels']], ['(a) C', '(c) C'])
        # 和要读的无关的多余子图照旧丢
        rec = fr.check_reading(t, {'panels': [self.pan('C', [10, 20]), self.pan('D', [1, 2])],
                                   'confidence': None, 'note': None})
        self.assertEqual([p['panel_id'] for p in rec['data']['panels']], ['(c) C'])

    def test_new_indicators_read(self):
        """用户 2026-10-05 加的五项：蛋白质体系里照读；非蛋白照旧不读。"""
        for code, name in (('turbidity', '浊度'), ('degree_of_hydrolysis', '水解度'), ('free_amino', '游离氨基含量'),
                           ('encapsulation', '包埋率/负载率'), ('antioxidant', '抗氧化活性')):
            fc = fr.FigureClass(n_panels=2, panels=[self.panel(functional_property=code),
                                                    self.panel(label='B', functional_property=code, protein_system=False)],
                                caption_topic='x', notes=None)
            self.assertEqual(fr.verdict_detail(fc)[0], ['A'], code)
            t = fr.figure_target({'key': 'fig1', 'label': '1', 'heading': 'Fig. 1', 'files': [], 'caption': ''},
                                 {'data': fc.model_dump()})
            self.assertEqual(t['hints'][0]['property'], name)
            dense = fr.FigureClass(n_panels=1, panels=[self.panel(functional_property=code, points_per_series=50)],
                                   caption_topic='x', notes=None)
            self.assertEqual(fr.functional_unread(dense, fr.verdict_detail(dense)[4]),
                             [{'panel': 'A', 'property': name, 'reason': '密集图（预估 100 点）'}])

    def test_duplicate_labels_small_plots(self):
        """一个字母下几张小图都标成 A（afres.2026.102097 图 1A）；同名里有一张与功能特性无关（afres.2026.102130 报
        KeyError 'none'）。逐个子图判断、名单去重，读图指令交代系列名带小标题，合并时各算各的。"""
        foam = self.panel(label='A', chart_type='combo', mark_types=['bar', 'line'], functional_property='foaming',
                          y_axis_label='Air phase fraction', n_series=2, points_per_series=6)
        none = self.panel(label='A', functional_property='none', y_axis_label='Viscosity (mPa s)')
        b = self.panel(label='B', functional_property='foaming', y_axis_label='Foam stability (%)')
        fc = fr.FigureClass(n_panels=5, panels=[foam, foam, none, foam, b], caption_topic='x', notes=None)
        item = {'key': 'fig1', 'label': '1', 'heading': 'Fig. 1', 'files': ['fig1.jpg'], 'caption': 'Fig. 1. x'}
        t = fr.figure_target(item, {'data': fc.model_dump()})
        self.assertEqual(t['read_panels'], ['A', 'B'])
        self.assertEqual(t['ignore_panels'], [])
        self.assertEqual(t['multi'], {'A': 4})
        self.assertEqual([h['panel'] for h in t['hints']], ['A', 'B'])
        self.assertTrue(all(h['property'] == '起泡性' for h in t['hints']))
        text = fr.panel_instruction(t)
        self.assertIn('只提取它们：A、B。', text)
        self.assertIn(fr.MULTI_NOTE % ('A', 4, 'A'), text)
        self.assertIn('「Overrun（0% sucrose）」', text)
        self.assertNotIn('子图 B 里画了', text)
        # 读图模型照指令给每张小图的系列名带上小标题：合并时是不同系列，不再「同键多值」
        def run():
            pts = [dict(series='Air phase fraction（%s）' % s, point_index=1, x_category=None, x_value=60.0,
                        y_value=y, err_low=None, err_high=None, estimated=False, sig=None, note=None)
                   for s, y in (('0% sucrose', 0.79), ('25% sucrose', 0.77), ('45% sucrose', 0.70))]
            axis = dict(label='y', unit=None, scale='linear', min=0.0, max=1.0, ticks=None, starts_at_zero=True,
                        multiplier=None)
            return dict(panel_id='A', chart_type='bar', x_axis=axis, y_left=axis, y_right=None,
                        series=[dict(name=p['series'], axis='left', chart_type='bar') for p in pts], points=pts)
        only_a = fr.narrowed(t, {'A'})
        self.assertIn(fr.MULTI_NOTE % ('A', 4, 'A'), fr.panel_instruction(only_a))
        recs = [('run%d' % i, {'fig1': fr.check_reading(only_a, {'panels': [run()], 'confidence': None, 'note': None})})
                for i in (1, 2)]
        self.assertTrue(all(r['fig1']['ok'] for _, r in recs))
        rows = fr.merge({'fig1': t}, recs)
        self.assertEqual(len(rows), 3)
        acc, rej = fr.select_rows(rows)
        self.assertEqual((len(acc), rej), (3, []))

    def test_scatter_matrix_not_read(self):
        """一个子图里又分几格、各格坐标轴不同（散点矩阵、配对图、边际图）不读，评价里写明（用户 2026-10-08）；
        普通散点图照读。名字带 matrix 的都算，记号只有点也不会被按记号改成普通 scatter。"""
        for name in ('scatter_matrix', 'pair_plot', 'Scatter matrix', 'marginal_plot'):
            p = self.panel(label='C', chart_type=name, mark_types=['point'], functional_property='water_holding',
                           points_per_series=10)
            fc = fr.FigureClass(n_panels=1, panels=[p], caption_topic='x', notes=None)
            quant, _, _, _, why = fr.verdict_detail(fc)
            self.assertEqual(quant, [], name)
            self.assertEqual(why, {'C': '一个子图里分成几格、各格坐标轴不同（散点矩阵等），不读'}, name)
            self.assertEqual(fr.functional_unread(fc, why)[0]['property'], '持水性')
        plain = self.panel(chart_type='scatter', mark_types=['point'], functional_property='water_holding')
        self.assertEqual(fr.verdict_detail(fr.FigureClass(n_panels=1, panels=[plain], caption_topic='x',
                                                          notes=None))[0], ['A'])
        self.assertIn('scatter_matrix', fr.SYSTEM)
        self.assertIn('scatter_matrix', fr.FigureClass.model_json_schema()['$defs']['Panel']['properties']
                      ['chart_type']['description'])

    def test_unlabeled_panels_named(self):
        """图上没有字母编号、又不止一个子图（2026-10-06 afres.2026.102130 图 5：示意图里嵌了红外、热重和一张持水柱状图）：
        给要读的子图起名「未编号1」，按图型和坐标轴点名；多交回来的曲线小图丢掉，不算失败。"""
        none = dict(functional_property='none', n_series=None, points_per_series=None)
        flow = self.panel(label=None, chart_type='flowchart', mark_types=[], x_axis_label=None, y_axis_label=None,
                          y_tick_labels=None, **none)
        ftir = self.panel(label=None, chart_type='line', mark_types=['line'], x_axis_label='Wavenumber (cm⁻¹)',
                          y_axis_label='Transmittance (a.u.)', **none)
        dtg = self.panel(label=None, chart_type='line', mark_types=['line'], x_axis_label='Temperature (°C)',
                         y_axis_label='Deriv. Weight (%/°C)', **none)
        bar = self.panel(label=None, chart_type='grouped_bar', x_axis_label=None, y_axis_label='Percentage (%)',
                         functional_property='water_holding', n_series=2, points_per_series=2)
        item = {'key': 'fig5', 'label': '5', 'heading': 'Fig. 5', 'files': ['fig5.jpg'], 'caption': 'Fig. 5. x'}

        def target(*panels):
            fc = fr.FigureClass(n_panels=len(panels), panels=list(panels), caption_topic='x', notes=None)
            return fr.figure_target(item, {'data': fc.model_dump()})
        t = target(flow, ftir, dtg, bar)
        self.assertEqual(t['read_panels'], ['未编号1'])
        self.assertEqual(t['unlabeled'], {'未编号1': 'grouped_bar，Y 轴「Percentage (%)」'})
        text = fr.panel_instruction(t)
        self.assertIn('只提取它们：未编号1。', text)
        self.assertIn(fr.UNLABELED_NOTE % '「未编号1」', text)
        self.assertIn('- 子图 未编号1：grouped_bar，测的是持水性，约 2 个系列，Y 轴「Percentage (%)」，有误差棒', text)
        self.assertIn(fr.UNLABELED_OTHER % ('flowchart；line，Y 轴「Transmittance (a.u.)」，X 轴「Wavenumber (cm⁻¹)」；'
                                            'line，Y 轴「Deriv. Weight (%/°C)」，X 轴「Temperature (°C)」'), text)
        self.assertNotIn('提取这张图片中所有子图的全部数据点', text)
        # 读图模型照指令填了 panel_id，另外把曲线小图也交回来（没编号、0 个点）：丢掉，不算失败
        curve = self.pan(None, [])
        rec = fr.check_reading(t, {'panels': [curve, curve, self.pan('未编号1', [41.0, 52.0])],
                                   'confidence': None, 'note': None})
        self.assertTrue(rec['ok'], rec['flags'])
        self.assertEqual([p['panel_id'] for p in rec['data']['panels']], ['未编号1'])
        rows = fr.merge({'fig5': t}, [('run1', {'fig5': rec}), ('run2', {'fig5': rec})])
        self.assertEqual([(r['子图'], r['confidence']) for r in rows], [('未编号1', 'high')] * 2)
        self.assertEqual(fr.panel_name(t, '未编号1'), '未编号1（图上没有编号：grouped_bar，Y 轴「Percentage (%)」）')
        # 只有一个子图、没编号：照旧整图读（与流水线一致）
        single = target(bar)
        self.assertEqual((single['read_panels'], single['unlabeled']), ([None], {}))
        self.assertTrue(fr.panel_instruction(single).endswith('提取这张图片中所有子图的全部数据点。'))
        # 两个图型和坐标轴一样的没编号子图：按从左到右、从上到下数第几个区分
        two = target(bar, flow, bar)
        self.assertEqual(two['read_panels'], ['未编号1', '未编号2'])
        text = fr.panel_instruction(two)
        self.assertIn('Y 轴「Percentage (%)」，' + fr.NTH_NOTE % 1, text)
        self.assertIn('Y 轴「Percentage (%)」，' + fr.NTH_NOTE % 2, text)
        # 有字母编号的图不受影响
        self.assertEqual(target(dict(bar, label='A'), dict(ftir, label='B'))['unlabeled'], {})

    def test_missing_panel_still_retried(self):
        t = {'key': 'fig1', 'kind': 'figure', 'label': '1', 'case': False, 'read_panels': ['A', 'B'],
             'ignore_panels': [], 'hints': [{'panel': 'A', 'mark_types': ['bar']}, {'panel': 'B', 'mark_types': ['bar']}]}
        run = {'ok': True, 'data': {'panels': [self.pan('A', [10])]}, 'scope': ['A', 'B'],
               'smooth_empty': [], 'unresolved_empty': []}
        self.assertEqual(fr.retry_plan({'fig1': t}, [('run1', {'fig1': run}), ('run2', {'fig1': run})]),
                         {'fig1': ['B']})

    def test_done_layout_and_moved_checkpoint(self):
        """用户 2026-10-21：D:\\acs_papers_done 这种结构（文章在 <根>\\papers\\<文章>，旁边 _records、database）也找得到文章；
        文章换了位置，断点按文章文件夹名接着用；同名的断点不止一个时不猜，用这个路径自己的。"""
        tmp = tempfile.mkdtemp()
        old_ckpt, fr.CHECKPOINT_DIR = fr.CHECKPOINT_DIR, os.path.join(tmp, '断点')
        try:
            def paper(path):
                os.makedirs(os.path.join(path, fr.FIGURE_DIR))
                open(os.path.join(path, fr.FIGURE_DIR, 'figure_markdown.md'), 'w', encoding='utf-8').write('# t\n')
                return path
            done = os.path.join(tmp, 'acs_papers_done')
            a = paper(os.path.join(done, 'papers', '10.1021_a'))
            b = paper(os.path.join(done, 'papers', '10.1021_b'))
            os.makedirs(os.path.join(done, '_records', '数据点'))
            os.makedirs(os.path.join(done, 'database'))
            flat = os.path.join(tmp, 'elsevier_papers')
            c = paper(os.path.join(flat, '10.1016_c'))
            self.assertEqual(fr.find_papers([done]), [a, b])
            self.assertEqual(fr.find_papers([os.path.join(done, 'papers')]), [a, b])
            self.assertEqual(fr.find_papers([flat, a]), [c, a])
            # 断点是在老位置（flat 下）读的：挪进 papers 以后照样认
            old_dir = fr.work_dir(c)
            os.makedirs(old_dir)
            moved = os.path.join(done, 'papers', '10.1016_c')
            shutil.move(c, moved)
            self.assertEqual(fr.work_dir(moved), old_dir)
            self.assertEqual(fr.Claims.path(moved), old_dir + '.lock')
            # 新位置自己有断点时用自己的；同名的断点有两个时也用自己路径的
            other = paper(os.path.join(tmp, 'copy', '10.1016_c'))
            self.assertEqual(fr.work_dir(other), old_dir)
            mine = os.path.join(fr.CHECKPOINT_DIR, os.path.basename(fr.work_dir(a)))
            os.makedirs(mine)
            self.assertEqual(fr.work_dir(a), mine)
            exact = os.path.join(fr.CHECKPOINT_DIR, '10.1016_c_ffffffff')
            os.makedirs(exact)
            got = fr.work_dir(other)
            self.assertNotIn(got, [old_dir, exact])
            self.assertTrue(os.path.basename(got).startswith('10.1016_c_'))
        finally:
            fr.CHECKPOINT_DIR = old_ckpt
            shutil.rmtree(tmp, ignore_errors=True)

    def test_salvage_keeps_passing_panels(self):
        """用户 2026-10-19：放弃的这一遍只丢没过自检的子图（I 刻度对不上、D 没读回来），A 照常；
        没放弃的、一个子图都不剩的、整图只有一个没编号子图的不动。"""
        t = {'key': 'fig7', 'kind': 'figure', 'label': '7', 'case': False, 'read_panels': ['A', 'I', 'D'],
             'ignore_panels': [], 'hints': [{'panel': p, 'mark_types': ['bar']} for p in 'AID']}
        bad = self.pan('I', [-5.35, -8.72, -9.14])
        bad['y_left'] = dict(bad['y_left'], min=0.0, max=12.0, ticks='0,2,4,6,8,10,12')
        raw = {'panels': [self.pan('A', [10, 20]), bad], 'confidence': 'high', 'note': None}
        rec = dict(fr.check_reading(t, json.loads(json.dumps(raw))), raw=raw, gave_up=True, fails=2)
        self.assertFalse(rec['ok'])
        out = fr.salvage(t, rec)
        self.assertTrue(out['ok'])
        self.assertFalse(out['gave_up'])
        self.assertEqual([p['panel_id'] for p in out['data']['panels']], ['A'])
        self.assertEqual(out['scope'], ['A'])
        self.assertEqual(sorted(out['salvaged']), ['D', 'I'])
        self.assertIn('超出自报刻度', out['salvaged']['I'])
        self.assertEqual(out['salvaged']['D'], '缺少这个子图')
        not_given_up = dict(rec, gave_up=False)
        self.assertIs(fr.salvage(t, not_given_up), not_given_up)
        all_bad = dict(fr.check_reading(t, {'panels': [bad]}), gave_up=True)
        self.assertIs(fr.salvage(t, all_bad), all_bad)
        whole = dict(t, read_panels=[None])
        self.assertIs(fr.salvage(whole, rec), rec)


class Inputs(unittest.TestCase):
    def test_parse_variants(self):
        text = '\n'.join([
            '# Title - ScienceDirect', '', 'DOI: https://doi.org/10.1/x  ', '网页: https://x', '',
            '## Graphical abstract', '', '![Graphical abstract](graphical_abstract.jpg)', '',
            '## Fig. 1', '', '![Fig. 1](fig1.jpg)', '', 'Fig. 1. Solubility of WPI.', '',
            '## Fig. 6', '', '![Fig. 6](fig6a.jpg)', '', '![Fig. 6](fig6b.jpg)', '', 'Fig. 6. Two parts.', '',
            '## Fig. A13', '', '![Fig. A13](fx1.jpg)', '', 'Fig. A13. Appendix.', '',
            '## Fig.e 2:', '', '![x](fig2.jpg)', '',
            '## Scheme 1', '', '![Scheme 1](scheme1.jpg)', '', 'Scheme 1. Flowchart for preparation.', '',
            '## Table 4（图片版表格）', '', '![Table 4](table4.jpg)', '', 'Functional properties of WPI.', '',
            '*a* WHC, water holding capacity.', '',
            '## figs1', '', '![figs1](mmcfigs1.jpg)', '', 'figs1.', '',
            '## Fig. 3', '', '（图片下载失败，原图地址：https://x/gr3.jpg）', '', 'Fig. 3. Lost.', ''])
        items = fr.parse_figure_markdown(text)
        got = [(i['key'], i['kind'], i['label'], i['files']) for i in items]
        self.assertEqual(got, [
            ('ga', 'graphical_abstract', '', ['graphical_abstract.jpg']),
            ('fig1', 'figure', '1', ['fig1.jpg']),
            ('fig6', 'figure', '6', ['fig6a.jpg', 'fig6b.jpg']),
            ('figA13', 'figure', 'A13', ['fx1.jpg']),
            ('fig2', 'figure', '2', ['fig2.jpg']),
            ('sc1', 'scheme', '1', ['scheme1.jpg']),
            ('tab4', 'table', '4', ['table4.jpg']),
            ('other:figs1', 'other', 'figs1', ['mmcfigs1.jpg']),
            ('fig3', 'figure', '3', [])])
        self.assertEqual(items[6]['caption'], 'Table 4. Functional properties of WPI. *a* WHC, water holding capacity.')
        self.assertEqual(items[8]['failed'], ['https://x/gr3.jpg'])

    def test_exclusions(self):
        self.assertEqual(fr.exclusion_reason('Fig. 2. Flowchart of the process.'), '流程图')
        self.assertEqual(fr.exclusion_reason('Fig. A2. 3D response surface of yield.'), '三维响应面图')
        self.assertEqual(fr.exclusion_reason('Fig. 2. Solubility.'), '')

    def test_classify_text_has_no_full_text(self):
        """不读全文（用户 2026-10-02）：正文引用一栏照流水线取不到时的写法填（未取到）。"""
        fig = {'kind': 'figure', 'label': '1', 'caption': 'Fig. 1. Solubility of WPI.',
               'paper_title': 'Ultrasonic emulsification of alginate nanogel formulation for phycocyanin encapsulation'}
        self.assertEqual(fr.classify_text(fig), fr.USER.format(
            title='Ultrasonic emulsification of alginate nanogel formulation for phycocyanin encapsulation',
            captions='（未取到）', caption='Fig. 1. Solubility of WPI.', mentions='（未取到）'))
        table = {'kind': 'table', 'label': '4', 'caption': ''}
        self.assertEqual(fr.classify_text(table), fr.TABLE_USER.format(n='4', title='（未取到）', captions='（未取到）',
                                                                       caption='（未取到）', mentions='（未取到）'))
        # 全篇图注（用户 2026-10-06）：放在这张图自己的图注前面
        fig['paper_captions'] = '- Fig. 1：Fig. 1. Solubility of WPI.\n- Fig. 2：Fig. 2. EAI of WPI–SPI blends.'
        text = fr.classify_text(fig)
        self.assertIn(CAPTIONS_BLOCK.format(captions=fig['paper_captions']) + '这张图的图注（可能为空）：\n'
                      'Fig. 1. Solubility of WPI.\n', text)

    def test_slot_rotation(self):
        """同时开 N 个窗口：第 K 个从 (K-1)/N 处开始、到末尾再从头接着；每个窗口都走遍全部（用户 2026-10-08）。"""
        todo = list(range(10))
        self.assertEqual(fr.rotate(todo, (1, 5)), (todo, 0))
        self.assertEqual(fr.rotate(todo, (2, 5)), ([2, 3, 4, 5, 6, 7, 8, 9, 0, 1], 2))
        self.assertEqual(fr.rotate(todo, (5, 5))[1], 8)
        for k in range(1, 6):
            self.assertEqual(sorted(fr.rotate(todo, (k, 5))[0]), todo)
        self.assertEqual(fr.rotate([], (3, 5)), ([], 0))
        self.assertEqual(fr.parse_slot(' 2 / 5 '), (2, 5))
        for bad in ('0/5', '6/5', '2', 'a/b', '2/0', ''):
            with self.assertRaises(ValueError):
                fr.parse_slot(bad)

    def test_started_papers_first(self):
        """用户 2026-10-21「脚本优先有跑断点的文章」：停在断点的先做，再开没开始的；开几个窗口时两段各自错开起点。"""
        tmp = tempfile.mkdtemp()
        old_ckpt, fr.CHECKPOINT_DIR = fr.CHECKPOINT_DIR, os.path.join(tmp, '断点')
        try:
            todo = [os.path.join(tmp, 'p%d' % i) for i in range(10)]
            for i in (3, 7):
                os.makedirs(fr.work_dir(todo[i]))
            order, first, n = fr.started_first(todo)
            self.assertEqual((order[:2], n, first), ([todo[3], todo[7]], 2, 0))
            self.assertEqual(order[2:], [p for i, p in enumerate(todo) if i not in (3, 7)])
            order, first, n = fr.started_first(todo, (2, 2))           # 第 2 个窗口：两段都从一半处开始
            self.assertEqual(order[:2], [todo[7], todo[3]])
            fresh = [p for i, p in enumerate(todo) if i not in (3, 7)]
            self.assertEqual((order[2:], first), (fresh[4:] + fresh[:4], 4))
            for k in (1, 2):
                self.assertEqual(sorted(fr.started_first(todo, (k, 2))[0]), sorted(todo))
            self.assertEqual(fr.started_first([todo[3], todo[7]], (2, 2)), ([todo[7], todo[3]], 1, 2))
            self.assertEqual(fr.started_first([], (3, 5)), ([], 0, 0))
        finally:
            fr.CHECKPOINT_DIR = old_ckpt
            shutil.rmtree(tmp, ignore_errors=True)

    @unittest.skipUnless(os.path.isdir(PAPERS), '没有 papers 文件夹')
    def test_every_fetched_paper_parses(self):
        roots = fr.find_papers([PAPERS])
        self.assertGreater(len(roots), 0)
        kinds = {}
        for root in roots:
            paper = fr.load_paper(root)
            for it in paper['items']:
                kinds[it['kind']] = kinds.get(it['kind'], 0) + 1
            fr.plan_items(paper)
        self.assertGreater(kinds.get('figure', 0), 0)


# ---------------------------------------------------------------- 假 API ----
class FakeCompletions:
    """按 response_format 和指令内容回一个固定结果；记录每次调用。"""

    def __init__(self, fail_reads=0, empty_reads=0):
        self.calls = []
        self.fail_reads = fail_reads          # 前几次读图抛网络错误
        self.empty_reads = empty_reads        # 前几次读图交回子图却一个点都没有（自检「0 个数据点」不过）
        self.lock = __import__('threading').Lock()

    def parse(self, model, messages, response_format):
        text = messages[1]['content'][0]['text']
        with self.lock:
            self.calls.append((response_format.__name__, text))
            n = sum(1 for c in self.calls if c[0] == 'Extraction')
        if response_format is fr.Screen:                           # 初筛：图注写 Growth curve 的回 4（凝胶性），别的回 0
            own = text.split('这张图的图注（可能为空）：', 1)[1]
            parsed = fr.Screen(indicators=[4] if 'Growth curve' in own else [0])
        elif response_format is fr.FigureClass:
            own = text.split('这张图的图注（可能为空）：', 1)[1]       # 全篇图注里每张都有，只看这张图自己的
            if 'Growth curve' in own:
                panels = [dict(label='A', mark_types=['bar', 'point'], chart_type='other', x_axis_label='Strain',
                               y_axis_label='Curd firmness (g)', caption_part=None, protein_system=True,
                               functional_property='gelling', y_tick_labels=['0', '50', '100'], n_series=2,
                               points_per_series=3, has_error_bars=True, has_significance_letters=False,
                               series_overlap_risk='low', overlap_reason=None),
                          dict(label='B', mark_types=['bar'], chart_type='stacked_column', x_axis_label='Strain',
                               y_axis_label='Solubility (%)', caption_part=None, protein_system=True,
                               functional_property='solubility', y_tick_labels=['0', '50'], n_series=3,
                               points_per_series=3, has_error_bars=False, has_significance_letters=False,
                               series_overlap_risk='low', overlap_reason=None)]
            else:
                panels = [dict(label=None, mark_types=[], chart_type='pca_embedding', x_axis_label='PC1',
                               y_axis_label='PC2', caption_part=None, protein_system=False,
                               functional_property='none', y_tick_labels=None, n_series=None,
                               points_per_series=None, has_error_bars=False, has_significance_letters=False,
                               series_overlap_risk='low', overlap_reason=None)]
            parsed = fr.FigureClass(n_panels=len(panels), panels=panels, caption_topic='t', notes=None)
        else:
            if n <= self.fail_reads:
                raise RuntimeError('模拟网络错误')
            axis = dict(label='Curd firmness', unit='g', scale='linear', min=0.0, max=100.0, ticks='0,50,100',
                        starts_at_zero=True, multiplier=None)
            pts = [dict(series=s, point_index=i + 1, x_category=x, x_value=None,
                        y_value=y + (0.2 if n % 2 else 0), err_low=y - 2, err_high=y + 2, estimated=True,
                        sig=None, note=None)
                   for s, base in (('P6', 40.0), ('NI', 60.0)) for i, (x, y) in
                   enumerate((('D0', base), ('D3', base - 10), ('D6', base - 25)))]
            if n <= self.empty_reads:
                pts = []
            parsed = fr.Extraction(panels=[dict(panel_id='A', chart_type='bar', x_axis=dict(axis, unit=None),
                                                y_left=axis, y_right=None,
                                                series=[dict(name='P6', axis='left', chart_type='bar'),
                                                        dict(name='NI', axis='left', chart_type='bar')],
                                                points=pts)], confidence='high', note=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))],
                               usage=SimpleNamespace(total_tokens=100))


class ScreenErrorCompletions(FakeCompletions):
    """初筛时图注不是 Growth curve 的都报错（模拟接口出错），别的照常。"""

    def parse(self, model, messages, response_format, **kw):
        if response_format is fr.Screen and 'Growth curve' not in messages[1]['content'][0]['text']:
            with self.lock:
                self.calls.append(('Screen', messages[1]['content'][0]['text']))
            raise RuntimeError('模拟初筛出错')
        return super().parse(model, messages, response_format)


def fake_api(**kw):
    comp = FakeCompletions(**kw)
    client = SimpleNamespace(chat=SimpleNamespace(completions=comp))
    return fr.Api('gpt-6-astra', 4, client=client), comp


def openai_error(cls, status, body, headers=None):
    """和 openai 程序库真报出来的一样的错误对象（状态码、错误码、回复头）。"""
    import httpx
    import openai
    resp = httpx.Response(status, headers=headers or {},
                          request=httpx.Request('POST', 'https://api.openai.com/v1/chat/completions'))
    return getattr(openai, cls)(body['message'], response=resp, body=body)


# 2026-10-08 实际碰到的：429，「You have no credits remaining …」
NO_MONEY = {'message': 'You have no credits remaining. Add credits to continue using the API at '
                       'https://platform.openai.com/settings/organization/billing/.',
            'type': 'insufficient_quota', 'code': 'insufficient_quota'}
RATE = {'message': 'Rate limit reached for gpt-6-astra on tokens per min (TPM): Limit 40000000.',
        'type': 'tokens', 'code': 'rate_limit_exceeded'}


class ErrorCompletions(FakeCompletions):
    """前几次调用依次抛给定的错误，之后照常回答。"""

    def __init__(self, errors):
        super().__init__()
        self.errors = list(errors)

    def parse(self, model, messages, response_format, **kw):
        with self.lock:
            err = self.errors.pop(0) if self.errors else None
            if err is not None:
                self.calls.append(('error', ''))
        if err is not None:
            raise err
        return super().parse(model, messages, response_format)


class RawCompletions(FakeCompletions):
    """有 with_raw_response 的假客户端：回复带限额回复头。"""

    @property
    def with_raw_response(self):
        outer = self
        headers = {'x-ratelimit-limit-tokens': '40000000', 'x-ratelimit-remaining-tokens': '39990000',
                   'x-ratelimit-limit-requests': '15000', 'x-ratelimit-remaining-requests': '14990'}

        class Raw:
            def parse(self, **kw):
                r = outer.parse(**kw)
                return SimpleNamespace(headers=headers, parse=lambda: r)
        return Raw()


def api_of(comp):
    return fr.Api('gpt-6-astra', 4, client=SimpleNamespace(chat=SimpleNamespace(completions=comp)))


class UsageCompletions(FakeCompletions):
    """回复带完整用量（输入 1000，其中缓存 600；输出 300，其中思考 200）；记下每次用的模型、推理强度和系统提示。"""

    def __init__(self):
        super().__init__()
        self.seen = []

    def parse(self, model, messages, response_format, **kw):
        with self.lock:
            self.seen.append((response_format.__name__, model, kw.get('reasoning_effort'), messages[0]['content']))
        rf = fr.FigureClass if response_format is fr.FigureClassSlim else response_format
        r = super().parse(model, messages, rf)
        usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=300, total_tokens=1300,
                                prompt_tokens_details=SimpleNamespace(cached_tokens=600),
                                completion_tokens_details=SimpleNamespace(reasoning_tokens=200))
        return SimpleNamespace(choices=r.choices, usage=usage)


@unittest.skipUnless(os.path.isdir(SAMPLE), '没有样例文章')
class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, os.path.basename(SAMPLE))
        # 只拷 figure 子文件夹：没有 全文.md 也照常跑
        # 样例文章正式读过以后也有 反读数据.json（2026-10-13 Elsevier 跑到了它）：复制时一起去掉；
        # 2026-11-04 正式合并也跑到了它，全文合并.md 一样去掉
        shutil.copytree(SAMPLE, self.root, ignore=shutil.ignore_patterns('反读数据', fr.MD_NAME, fr.DB_NAME, '全文.md',
                                                                         fr.pc_MERGED_NAME))
        self.old_ckpt, fr.CHECKPOINT_DIR = fr.CHECKPOINT_DIR, os.path.join(self.tmp, '断点')   # 不碰真正的断点

    def tearDown(self):
        fr.CHECKPOINT_DIR = self.old_ckpt
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_whole_paper(self):
        api, comp = fake_api()
        self.assertTrue(fr.process_paper(fr.load_paper(self.root), api))
        # 文章文件夹里只多一个 反读数据.md（不要 csv、不要子文件夹）；断点删干净
        # 文章文件夹里多 反读数据.md 和建库用的 反读数据.json（用户 2026-10-12）；不要 csv、不要子文件夹
        self.assertEqual(sorted(os.listdir(self.root)), sorted([fr.FIGURE_DIR, fr.MD_NAME, fr.DB_NAME]))
        self.assertFalse(os.path.exists(fr.CHECKPOINT_DIR))
        with open(os.path.join(self.root, fr.MD_NAME), encoding='utf-8') as fh:
            md = fh.read()
        self.assertIn('## Fig. 1', md)
        self.assertIn('![Fig. 1](figure/fig1.jpg)', md)
        self.assertIn('**图 1：图像估读数据**（6 个点）', md)
        self.assertIn('子图 A**（6 点满足数值门槛，0 点不满足要求', md)
        self.assertIn('图 1 子图 B，溶解度，堆叠图，不送反读', md)      # 修正 ③：stacked_column 不读，末尾写明
        self.assertIn('读图模型：`gpt-6-astra`', md)
        self.assertTrue(md.rstrip().endswith(fr.DONE_MARK % fr.input_digest(self.root)))
        self.assertNotIn('## Fig. 2', md)                                   # 没读的图不出现
        # 7 张图各分类 1 次；图 1 读两遍；两遍差 0.2/40≈0.5%，不补第三遍
        kinds = [c[0] for c in comp.calls]
        self.assertEqual((kinds.count('FigureClass'), kinds.count('Extraction')), (7, 2))
        reads = [c[1] for c in comp.calls if c[0] == 'Extraction']
        self.assertTrue(all('只提取它们：A。' in r and '其余子图（B）' in r for r in reads))
        rows = [line for line in md.splitlines() if line.startswith(('| P6 |', '| NI |'))]
        self.assertEqual(len(rows), 6)
        self.assertTrue(all('| 满足数值门槛 |' in r for r in rows))
        # 完成的跳过；figure 文件夹一个字节都没动
        self.assertTrue(fr.is_done(self.root))
        for name in (os.path.join('figure', 'figure_markdown.md'), os.path.join('figure', 'fig1.jpg')):
            with open(os.path.join(SAMPLE, name), 'rb') as a, open(os.path.join(self.root, name), 'rb') as b:
                self.assertEqual(a.read(), b.read())

    def test_prescreen_skips_figures(self):
        """--prescreen-model（用户 2026-10-09）：初筛判成没有 17 项的图不做正式分类，判成有的照常分类、读图；初筛不附全篇
        图注；中途停下的话初筛和分类都在断点里，重跑不重花；评价里写明初筛模型；用量按 初筛 / 分类 / 读图 分开记。"""
        api, comp = fake_api(fail_reads=1)
        api.prescreen_model = 'gpt-6-luna'
        self.assertFalse(fr.process_paper(fr.load_paper(self.root), api))        # 读图出错，这篇先停下
        kinds = [c[0] for c in comp.calls]
        self.assertEqual((kinds.count('Screen'), kinds.count('FigureClass')), (7, 1))   # 7 张初筛，只有图 1 正式分类
        self.assertTrue(all('全篇所有图和表格的图注' not in c[1] for c in comp.calls if c[0] == 'Screen'))
        self.assertEqual(api.usage['初筛']['calls'], 7)
        self.assertTrue(fr.usage_text(api.usage).startswith('初筛 7 次'))
        api2, comp2 = fake_api()
        api2.prescreen_model = 'gpt-6-luna'
        self.assertTrue(fr.process_paper(fr.load_paper(self.root), api2))
        kinds = [c[0] for c in comp2.calls]
        self.assertEqual((kinds.count('Screen'), kinds.count('FigureClass'), kinds.count('Extraction')), (0, 0, 1))
        with open(os.path.join(self.root, fr.MD_NAME), encoding='utf-8') as fh:
            md = fh.read()
        self.assertIn('子图 A**（6 点满足数值门槛，0 点不满足要求', md)
        self.assertIn('读图模型：`gpt-6-astra`，初筛模型：`gpt-6-luna`', md)
        self.assertFalse(os.path.isdir(fr.work_dir(self.root)))
        # 换了初筛模型：指纹变了，重新初筛
        it = fr.plan_items(fr.load_paper(self.root))[0][0]
        digest = fr.image_digest(fr.image_paths(fr.load_paper(self.root), it))
        api3 = fr.Api('gpt-6-astra', 1, client=object())
        api3.prescreen_model = 'gpt-6-sol'
        self.assertNotEqual(fr.prescreen_fingerprint(api, it, digest), fr.prescreen_fingerprint(api3, it, digest))

    def test_prescreen_error_still_classified(self):
        """初筛这一步出错的图不跳过，照样正式分类（宁可多花一次分类，也不漏）。"""
        comp = ScreenErrorCompletions()
        api = fr.Api('gpt-6-astra', 4, client=SimpleNamespace(chat=SimpleNamespace(completions=comp)))
        api.prescreen_model = 'gpt-6-luna'
        self.assertTrue(fr.process_paper(fr.load_paper(self.root), api))
        kinds = [c[0] for c in comp.calls]
        self.assertEqual((kinds.count('FigureClass'), kinds.count('Extraction')), (7, 2))

    def test_failure_keeps_checkpoint_and_resumes(self):
        api, comp = fake_api(fail_reads=1)
        self.assertFalse(fr.process_paper(fr.load_paper(self.root), api))
        work = fr.work_dir(self.root)
        self.assertTrue(os.path.isdir(work))
        self.assertFalse(fr.is_done(self.root))
        self.assertEqual(sorted(os.listdir(self.root)), [fr.FIGURE_DIR])        # 断点不在文章文件夹里
        # 读成功的那一遍改成"失败、子图被丢光"：断点里有原始输出，重跑时按现在的规则重算，不重花 API
        for run in ('run1', 'run2'):
            path = os.path.join(work, run + '.jsonl')
            recs = [json.loads(s) for s in open(path, encoding='utf-8')]
            with open(path, 'a', encoding='utf-8') as fh:
                for r in recs:
                    if r.get('raw'):
                        fh.write(json.dumps(dict(r, ok=False, data={'panels': []}), ensure_ascii=False) + '\n')
        api2, comp2 = fake_api()
        self.assertTrue(fr.process_paper(fr.load_paper(self.root), api2))
        kinds = [c[0] for c in comp2.calls]
        self.assertEqual((kinds.count('FigureClass'), kinds.count('Extraction')), (0, 1))   # 只重读出错的那一遍
        self.assertFalse(os.path.isdir(work))

    def test_read_retried_once_on_the_spot(self):
        """自检没过（交回了子图却一个点都没有）：当场用同样的输入再读一次，过了就照常完成，不用整篇停下重跑。"""
        api, comp = fake_api(empty_reads=1)
        self.assertTrue(fr.process_paper(fr.load_paper(self.root), api))
        self.assertEqual([c[0] for c in comp.calls].count('Extraction'), 3)
        with open(os.path.join(self.root, fr.MD_NAME), encoding='utf-8') as fh:
            md = fh.read()
        self.assertIn('子图 A**（6 点满足数值门槛', md)
        self.assertNotIn('读图失败', md)

    def test_read_gives_up_after_two_failures(self):
        """同样的输入连续两次没通过自检：不再重读，这张图记为读图失败，整篇照常完成
        （2026-10-06 afres.2026.102130 图 5 原来每次重跑都白读两遍、整篇一直停着）。"""
        api, comp = fake_api(empty_reads=99)
        self.assertTrue(fr.process_paper(fr.load_paper(self.root), api))
        self.assertEqual([c[0] for c in comp.calls].count('Extraction'), 4)     # 两遍各读两次，没有第 3 遍
        self.assertFalse(os.path.exists(fr.CHECKPOINT_DIR))
        with open(os.path.join(self.root, fr.MD_NAME), encoding='utf-8') as fh:
            md = fh.read()
        self.assertIn('图 1 子图 A，凝胶性，读图失败：同样的输入连续 2 次没通过自检（A: 该子图 0 个数据点），没有反读数值', md)
        self.assertIn('图 1 子图 B，溶解度，堆叠图，不送反读', md)
        self.assertNotIn('## Fig. 1', md)
        self.assertTrue(fr.is_done(self.root))

    def test_cli_skips_done_and_dry_run(self):
        api, _ = fake_api()
        fr.process_paper(fr.load_paper(self.root), api)
        buf = io.StringIO()
        old, sys.stdout = sys.stdout, buf
        try:
            fr.main([self.root, '--dry-run'])
            fr.main([self.root, '--status'])
            fr.main([self.root])                       # 已完成：不建客户端、不调 API
        finally:
            sys.stdout = old
        out = buf.getvalue()
        self.assertIn('已完成，跳过', out)
        self.assertIn('完成 1', out)
        self.assertIn('这次处理 0 篇', out)
        # 抓取脚本重抓过（figure_markdown.md 变了）：不再算完成
        with open(os.path.join(self.root, 'figure', 'figure_markdown.md'), 'a', encoding='utf-8') as fh:
            fh.write('\n')
        self.assertFalse(fr.is_done(self.root))

    def captured(self, fn):
        out = sys.stdout
        sys.stdout = buf = io.StringIO()
        try:
            return fn(), buf.getvalue()
        finally:
            sys.stdout = out

    def test_no_money_stops_window(self):
        """账户没钱（2026-10-08 实际碰到的 429）：整个窗口立刻停下、写清楚原因，不再一篇接一篇地失败；
        断点里不把这几张图记成失败，充值后照常接着做（用户 2026-10-08）。"""
        root2 = os.path.join(self.tmp, 'second', os.path.basename(SAMPLE))
        shutil.copytree(self.root, root2)
        comp = ErrorCompletions([openai_error('RateLimitError', 429, NO_MONEY)] * 50)
        api = api_of(comp)

        def run():
            with self.assertRaises(fr.Fatal):
                fr.run_batch([self.root, root2], api, 1, fr.Claims())
        _, out = self.captured(run)
        self.assertEqual(out.count('窗口停下了：OpenAI 账户没钱了'), 1)
        self.assertIn('充值后双击同一个 bat 接着做', out)
        self.assertLessEqual(len(comp.calls), 7)                     # 第二篇没开始，第一篇碰到就不再发请求
        self.assertNotIn('分类失败', out)
        recs = fr.Store(fr.work_dir(self.root)).load('classify')
        self.assertFalse([r for r in recs.values() if not r.get('ok')])
        self.assertFalse(os.path.isdir(fr.work_dir(root2)))
        self.assertFalse(os.path.exists(fr.Claims.path(self.root)))  # 锁放开了
        # 命令行：最后一屏再写一遍原因，退出码 3
        api2 = api_of(ErrorCompletions([openai_error('RateLimitError', 429, NO_MONEY)] * 50))
        from unittest import mock
        with mock.patch.object(fr, 'Api', lambda *a, **k: api2):
            code, out = self.captured(lambda: fr.main([self.root]))
        self.assertEqual(code, 3)
        self.assertTrue(out.rstrip().endswith('=' * 70))
        self.assertEqual(out.count('窗口停下了：OpenAI 账户没钱了'), 2)

    def test_bad_key_and_rate_limit(self):
        """key 无效：窗口停下；被限流：不算失败，按 OpenAI 给的时间等着重试，整篇照常完成；每 10 分钟显示一次限额。"""
        bad = api_of(ErrorCompletions([openai_error('AuthenticationError', 401, {
            'message': 'Incorrect API key provided', 'type': 'invalid_request_error', 'code': 'invalid_api_key'})]))
        with self.assertRaises(fr.Fatal):
            self.captured(lambda: bad.parse('s', 't', 'data:image/png;base64,', fr.FigureClass))
        self.assertIn('API key 无效或已被删除', bad.fatal)
        rate = openai_error('RateLimitError', 429, RATE, {'retry-after': '7'})
        comp = ErrorCompletions([rate, rate])
        api, slept = api_of(comp), []
        api.sleep = slept.append
        ok, out = self.captured(lambda: fr.process_paper(fr.load_paper(self.root), api))
        self.assertTrue(ok)
        self.assertEqual(slept, [7, 7])
        self.assertEqual(out.count('[限流] 被限流'), 2)
        self.assertTrue(fr.is_done(self.root))
        # 错误的种类
        self.assertEqual(fr.api_problem(openai_error('RateLimitError', 429, {'message': 'x', 'type': 'x', 'code': 'insufficient_quota'})), 'money')
        self.assertEqual(fr.api_problem(openai_error('RateLimitError', 429, {'message': 'You exceeded your current quota', 'type': None, 'code': None})), 'money')
        self.assertEqual(fr.api_problem(rate), 'rate')
        self.assertEqual(fr.api_problem(openai_error('NotFoundError', 404, {'message': 'The model does not exist', 'type': 'x', 'code': 'model_not_found'})), 'access')
        self.assertIsNone(fr.api_problem(openai_error('InternalServerError', 500, {'message': 'oops', 'type': 'x', 'code': None})))
        self.assertIsNone(fr.api_problem(ValueError('零产出')))
        self.assertEqual(fr.retry_delay(ValueError()), 30)
        # 有回复头的客户端：开头显示一次这一分钟的限额，10 分钟内不再显示
        os.remove(os.path.join(self.root, fr.MD_NAME))
        ok, out = self.captured(lambda: fr.process_paper(fr.load_paper(self.root), api_of(RawCompletions())))
        self.assertTrue(ok)
        self.assertEqual(out.count('[限额] 这一分钟还剩 token 39990000 / 40000000、请求 14990 / 15000'), 1)

    def test_openrouter(self):
        """走 OpenRouter（用户 2026-10-08）：每个请求只用 OpenAI 标准那一家；402 没钱整个窗口停下、给 OpenRouter 的充值地址；
        502/503 等着重试；403 内容审核只算这一张；断点指纹和直连的 gpt-6-astra 一样，原来的断点照用。"""
        class Kw(FakeCompletions):
            def parse(self, model, messages, response_format, **kw):
                with self.lock:
                    self.extra = kw
                return super().parse(model, messages, response_format)
        comp = Kw()
        api = fr.Api('openai/gpt-6-astra', 4, client=SimpleNamespace(chat=SimpleNamespace(completions=comp)),
                     key_env='OPENROUTER_API_KEY', base_url=fr.OPENROUTER, provider='openai')
        ok, out = self.captured(lambda: fr.process_paper(fr.load_paper(self.root), api))
        self.assertTrue(ok)
        self.assertEqual(comp.extra, {'extra_body': {'provider': {'only': ['openai'], 'allow_fallbacks': False,
                                                                  'require_parameters': True}}})
        self.assertEqual(api.where(), 'OpenRouter（只用 openai 那一家）')
        self.assertEqual(fr.Api('gpt-6-astra').extra, {})                       # 直连不带
        item = fr.load_paper(self.root)['items'][1]
        self.assertEqual(fr.classify_fingerprint(api, item, 'd'), fr.classify_fingerprint(fr.Api('gpt-6-astra'), item, 'd'))
        # 错误
        money = openai_error('APIStatusError', 402, {'message': 'Insufficient credits. Add more using https://openrouter.ai/settings/credits',
                                                      'code': 402})
        self.assertEqual(fr.api_problem(money), 'money')
        # 2026-10-08 实际碰到的：余额少时同时在路上的请求太多 → 等着重试，不是没钱
        self.assertEqual(fr.api_problem(openai_error('APIStatusError', 402, {
            'message': 'This request would exceed your available credits given your current in-flight requests. '
                       'Retry after in-flight requests complete.', 'code': 402})), 'busy')
        broke = fr.Api('openai/gpt-6-astra', 4, client=SimpleNamespace(chat=SimpleNamespace(
            completions=ErrorCompletions([money]))), base_url=fr.OPENROUTER)
        with self.assertRaises(fr.Fatal):
            self.captured(lambda: broke.parse('s', 't', 'data:image/png;base64,', fr.FigureClass))
        self.assertIn('OpenRouter 的额度不够了', broke.fatal)
        self.assertIn('https://openrouter.ai/settings/credits', broke.fatal)
        self.assertEqual(fr.api_problem(openai_error('InternalServerError', 503, {
            'message': 'There is no available model provider that meets your routing requirements', 'code': 503})), 'busy')
        self.assertIsNone(fr.api_problem(openai_error('PermissionDeniedError', 403, {
            'message': 'Input flagged by moderation', 'code': 403})))
        self.assertEqual(fr.api_problem(openai_error('PermissionDeniedError', 403, {
            'message': 'Project does not have access to model', 'code': 403})), 'access')

    def test_switch_to_gemini(self):
        """OpenRouter 没钱（402）→ gemini 改走 Google 官方接口重发（用户 2026-11-04）：模型名去掉 google/、带 flex 档、
        不带 OpenRouter 的 provider，模型名（断点指纹、回答缓存用的）不变；没设 key、不是 gemini 照旧停下；
        官方接口每分钟限额的 429「exceeded your current quota」算限流。"""
        from unittest import mock
        money = openai_error('APIStatusError', 402, {'message': 'Insufficient credits', 'code': 402})

        class Comp:
            def __init__(self, errors):
                self.errors, self.sent = list(errors), []

            def parse(self, **kw):
                self.sent.append(kw)
                if self.errors:
                    raise self.errors.pop(0)
                return SimpleNamespace(usage=None, choices=[SimpleNamespace(message=SimpleNamespace(parsed='ok'))])

        def api_with(model, comp, key_env):
            api = fr.Api(model, 4, client=SimpleNamespace(chat=SimpleNamespace(completions=comp)),
                         base_url=fr.OPENROUTER, provider='google-ai-studio/flex')
            api.gemini_key_env = key_env
            return api
        comp = Comp([money])
        api = api_with('google/gemini-3.8-flash', comp, 'TEST_GEMINI_KEY')
        with mock.patch.dict(os.environ, {'TEST_GEMINI_KEY': 'x'}):
            (parsed, _), out = self.captured(lambda: api.parse('s', 't', 'data:image/png;base64,', fr.FigureClass, '读图'))
        self.assertEqual(parsed, 'ok')
        first, second = comp.sent
        self.assertEqual(first['model'], 'google/gemini-3.8-flash')
        self.assertIn('extra_body', first)
        self.assertNotIn('service_tier', first)
        self.assertEqual(second['model'], 'gemini-3.8-flash')
        self.assertEqual(second['service_tier'], 'flex')
        self.assertNotIn('extra_body', second)
        self.assertIn('[切换] OpenRouter 的额度不够了', out)
        self.assertEqual((api.gemini, api.key_env, api.base_url, api.model),
                         (True, 'TEST_GEMINI_KEY', fr.GEMINI, 'google/gemini-3.8-flash'))
        self.assertEqual(api.where(), 'Google 官方接口（flex 档）')
        kwargs, via = fr.ed_request(api, 's', 't', fr.ed_PaperNote)          # 数据点、测定方法也跟着切
        self.assertEqual((kwargs['model'], kwargs['service_tier'], kwargs['extra_body'], via),
                         ('gemini-3.8-flash', 'flex', None, False))
        # 没设 key、不是 gemini：照旧停下
        for model, key_env in (('google/gemini-3.8-flash', 'TEST_GEMINI_KEY_UNSET'), ('openai/gpt-6-luna', 'TEST_GEMINI_KEY')):
            broke = api_with(model, Comp([money]), key_env)
            with mock.patch.dict(os.environ, {'TEST_GEMINI_KEY': 'x'}):
                with self.assertRaises(fr.Fatal):
                    self.captured(lambda: broke.parse('s', 't', 'data:image/png;base64,', fr.FigureClass, '读图'))
            self.assertIn('OpenRouter 的额度不够了', broke.fatal)
            self.assertFalse(broke.gemini)
        quota = openai_error('RateLimitError', 429, {'message': 'You exceeded your current quota, please check your plan '
                                                                'and billing details.', 'code': 429})
        self.assertEqual(fr.api_problem(quota, gemini=True), 'rate')
        self.assertEqual(fr.api_problem(quota), 'money')

    def test_cli_defaults(self):
        """不带参数就是新流程（用户 2026-10-10：「脚本也改成新的」，和 bat 一样）：经 OpenRouter，luna 初筛 → gemini 分类、读图，
        每个模型只走自己那家；--base-url openai、--prescreen-model none 回到原来的 OpenAI 直连 gpt-6-astra。"""
        from unittest import mock
        real, made = fr.Api, []

        def make(*a, **k):
            made.append(real(*a, **k))
            return made[-1]
        with mock.patch.object(fr, 'Api', make):
            self.captured(lambda: fr.main([self.root, '--status']))
            self.captured(lambda: fr.main([self.root, '--status', '--base-url', 'openai', '--model', 'gpt-6-astra',
                                           '--key-env', 'OPENAI_API_KEY', '--prescreen-model', 'none']))
        new, old = made
        self.assertEqual((new.model, new.prescreen_model, new.classify_model, new.key_env, new.base_url),
                         ('google/gemini-3.8-flash', 'openai/gpt-6-luna', None, 'OPENROUTER_API_KEY', fr.OPENROUTER))
        # 用户 2026-10-12：初筛走 OpenAI 直连（新 OpenRouter 账户每分钟只许 20 个 luna 请求），分类和读图照旧走 OpenRouter
        self.assertEqual(new.route('初筛'), ('OPENAI_API_KEY', None, False))
        self.assertEqual(new.route('分类'), ('OPENROUTER_API_KEY', fr.OPENROUTER, True))
        self.assertEqual(new.prescreen_where(), '（OpenAI 直连，key 取自 OPENAI_API_KEY）')
        # 2026-10-14 起 gemini 走 flex 档（价格一半）
        self.assertEqual(new.extra['extra_body']['provider']['only'],
                         ['openai', 'google-ai-studio/flex', 'google-vertex/global/flex'])
        self.assertEqual(new.where(), 'OpenRouter（只用 openai、google-ai-studio/flex、google-vertex/global/flex）')
        self.assertEqual((old.model, old.prescreen_model, old.key_env, old.base_url, old.extra, old.where()),
                         ('gpt-6-astra', None, 'OPENAI_API_KEY', None, {}, 'OpenAI 直连'))

    def test_prescreen_direct_openai(self):
        """初筛单独走 OpenAI 直连（用户 2026-10-12）：初筛请求发给 OpenAI 的客户端、模型名去掉 openai/、不带 OpenRouter 的
        provider 设置；分类和读图照旧发给 OpenRouter 的客户端；没钱时写明是哪边的 key。"""
        class Kw(FakeCompletions):
            def __init__(self):
                super().__init__()
                self.seen = []

            def parse(self, model, messages, response_format, **kw):
                with self.lock:
                    self.seen.append((response_format.__name__, model, kw))
                return super().parse(model, messages, response_format)
        main, direct = Kw(), Kw()
        api = fr.Api('google/gemini-3.8-flash', 4, client=SimpleNamespace(chat=SimpleNamespace(completions=main)),
                     key_env='OPENROUTER_API_KEY', base_url=fr.OPENROUTER, provider='openai,google-ai-studio')
        api.prescreen_model, api.prescreen_base_url, api.prescreen_key_env = 'openai/gpt-6-luna', '', 'OPENAI_API_KEY'
        api._clients[('OPENAI_API_KEY', None)] = SimpleNamespace(chat=SimpleNamespace(completions=direct))
        self.assertTrue(fr.process_paper(fr.load_paper(self.root), api))
        self.assertTrue(direct.seen and all(s == ('Screen', 'gpt-6-luna', {}) for s in direct.seen))
        self.assertFalse(any(s[0] == 'Screen' for s in main.seen))
        self.assertTrue(all(s[1] == 'google/gemini-3.8-flash' and s[2] == api.provider_extra for s in main.seen))
        # 初筛那边没钱：提示写 OPENAI_API_KEY（OpenAI 账户），不写 OpenRouter
        broke = fr.Api('google/gemini-3.8-flash', 4, client=object(), key_env='OPENROUTER_API_KEY', base_url=fr.OPENROUTER)
        broke.prescreen_model, broke.prescreen_base_url, broke.prescreen_key_env = 'openai/gpt-6-luna', '', 'OPENAI_API_KEY'
        broke._clients[('OPENAI_API_KEY', None)] = SimpleNamespace(chat=SimpleNamespace(
            completions=ErrorCompletions([openai_error('RateLimitError', 429, NO_MONEY)])))
        with self.assertRaises(fr.Fatal):
            self.captured(lambda: broke.parse('s', 't', 'data:image/png;base64,', fr.Screen, stage='初筛'))
        self.assertIn('OpenAI 账户没钱了', broke.fatal)
        self.assertNotIn('OpenRouter', broke.fatal)

    def test_usage_and_classify_options(self):
        """每次调用的用量按分类 / 读图分开记（用户 2026-10-09）；分类可以换模型、调低推理强度、回答瘦身，读图照旧用 --model。"""
        comp = UsageCompletions()
        api = api_of(comp)
        api.classify_model, api.classify_effort, api.classify_slim = 'gpt-6-luna', 'low', True
        ok, out = self.captured(lambda: fr.process_paper(fr.load_paper(self.root), api))
        self.assertTrue(ok)
        cls = [s for s in comp.seen if s[0] == 'FigureClassSlim']
        reads = [s for s in comp.seen if s[0] == 'Extraction']
        self.assertEqual((len(cls), len(reads)), (7, 2))
        self.assertTrue(all(s[1] == 'gpt-6-luna' and s[2] == 'low' and s[3].endswith(fr.SLIM_RULE) for s in cls))
        self.assertTrue(all(s[1] == 'gpt-6-astra' and s[2] is None for s in reads))
        self.assertIn('用量：分类 7 次：输入 7,000（缓存 4,200）、输出 2,100（思考 1,400）；'
                      '读图 2 次：输入 2,000（缓存 1,200）、输出 600（思考 400）', out)
        self.assertEqual((api.usage['分类']['calls'], api.usage['读图']['output']), (7, 600))
        with open(os.path.join(self.root, fr.MD_NAME), encoding='utf-8') as fh:
            self.assertIn('读图模型：`gpt-6-astra`，分类模型：`gpt-6-luna`', fh.read())
        self.assertEqual(list(fr.PanelSlim.model_fields)[:4], ['label', 'chart_type', 'protein_system', 'functional_property'])
        # 不设这些选项时分类指纹和原来一样（断点照用），设了就不一样
        item = fr.load_paper(self.root)['items'][1]
        plain = fr.Api('gpt-6-astra')
        old = fr.fingerprint({'stage': 'classify', 'model': 'gpt-6-astra', 'max_side': fr.MAX_SIDE, 'system': fr.SYSTEM,
                              'schema': fr.FigureClass.model_json_schema(), 'text': fr.classify_text(item)}, 'd')
        self.assertEqual(fr.classify_fingerprint(plain, item, 'd'), old)
        self.assertNotEqual(fr.classify_fingerprint(api, item, 'd'), old)
        self.assertEqual(fr.usage_of(SimpleNamespace(usage=SimpleNamespace(total_tokens=100)))['total'], 100)

    def test_only_started(self):
        """--only-started：只做有断点、还没做完的，不开始新的（用户 2026-10-08）。"""
        from unittest import mock
        code, out = self.captured(lambda: fr.main([self.root, '--only-started']))     # 没断点：不碰、不调 API
        self.assertIn('这次处理 0 篇（只做有断点的，没开始的 1 篇这次不碰）', out)
        api, comp = fake_api(fail_reads=1)                                             # 做到一半网络出错，留下断点
        self.assertFalse(fr.process_paper(fr.load_paper(self.root), api))
        self.assertTrue(os.path.isdir(fr.work_dir(self.root)))
        api2, comp2 = fake_api()
        with mock.patch.object(fr, 'Api', lambda *a, **k: api2):                      # 断点是不初筛时留下的，接着做也不初筛
            code, out = self.captured(lambda: fr.main([self.root, '--only-started', '--prescreen-model', 'none']))
        self.assertIn('这次处理 1 篇（只做有断点的，没开始的 0 篇这次不碰）', out)
        self.assertTrue(fr.is_done(self.root))
        self.assertEqual([c[0] for c in comp2.calls], ['Extraction'])                 # 只补出错的那一遍

    def test_cli_slot(self):
        """--slot K/N：开头那行写明是第几个窗口、从哪篇开始；写错了在开始前就停下。"""
        api, _ = fake_api()
        fr.process_paper(fr.load_paper(self.root), api)
        out, err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = buf = io.StringIO()
        try:
            fr.main([self.root, '--slot', '2/5'])           # 已完成：不建客户端、不调 API
            with self.assertRaises(SystemExit):
                fr.main([self.root, '--slot', '6/5'])
        finally:
            sys.stdout, sys.stderr = out, err
        self.assertIn('这次处理 0 篇（第 2/5 个窗口，从没做的第 1 篇开始，做到末尾再从头接着）', buf.getvalue())
        self.assertIn('--slot 要写成 K/N', buf.getvalue())

    def test_two_windows_do_not_double_process(self):
        """几个窗口同时跑：另一个窗口领着的文章跳过，不调 API；放开后再跑才处理。"""
        other = fr.Claims()                      # 模拟另一个窗口
        self.assertTrue(other.take(self.root))
        self.assertTrue(os.path.isfile(fr.Claims.path(self.root)))
        self.assertTrue(fr.Claims().busy(self.root))
        api, comp = fake_api()
        ok, failed, busy = fr.run_batch([self.root], api, 1, fr.Claims())
        self.assertEqual((ok, failed, busy, comp.calls), (0, [], [self.root], []))
        other.release(self.root)
        ok, failed, busy = fr.run_batch([self.root], api, 1, fr.Claims())
        self.assertEqual((ok, failed, busy), (1, [], []))
        self.assertTrue(fr.is_done(self.root))
        self.assertFalse(os.path.exists(fr.CHECKPOINT_DIR))   # 锁和断点都清掉了

    def test_redo_no_json_only_old_papers(self):
        """--redo-no-json：只重读有 反读数据.md、没有 反读数据.json 的（老脚本读的）；没读过的、已有 json 的都不碰。"""
        code, out = self.captured(lambda: fr.main([self.root, '--redo-no-json']))      # 没读过：不碰、不调 API
        self.assertIn('这次处理 0 篇（只重读有 反读数据.md、没有 反读数据.json 的老文章）', out)
        api, _ = fake_api()
        fr.process_paper(fr.load_paper(self.root), api)
        db = os.path.join(self.root, fr.DB_NAME)
        self.assertFalse(fr.no_json(self.root))
        api2, comp2 = fake_api()
        ok, _, _ = fr.run_batch([self.root], api2, 1, fr.Claims(), redo_no_json=True)
        self.assertEqual((ok, comp2.calls), (1, []))                                   # 已有 json：跳过
        from unittest import mock
        os.remove(db)                                                                  # 老脚本读的：只有 md
        self.assertTrue(fr.no_json(self.root) and fr.is_done(self.root))
        ok, _, _ = fr.run_batch([self.root], api2, 1, fr.Claims())
        self.assertEqual((ok, comp2.calls), (1, []))                                   # 不带这个选项：照旧跳过
        with mock.patch.object(fr, 'Api', lambda *a, **k: api2):
            code, out = self.captured(lambda: fr.main([self.root, '--redo-no-json', '--prescreen-model', 'none']))
        self.assertIn('这次处理 1 篇（只重读有 反读数据.md、没有 反读数据.json 的老文章）', out)
        self.assertEqual([c[0] for c in comp2.calls].count('FigureClass'), 7)          # 整篇重新分类
        self.assertTrue(os.path.isfile(db) and fr.is_done(self.root))

    def test_refresh_redoes_done_paper(self):
        """--refresh：开跑前已完成的真的重做；同一次里别的窗口刚重做完的不再做一遍。"""
        api, _ = fake_api()
        fr.process_paper(fr.load_paper(self.root), api)
        old = __import__('time').time() - 60
        os.utime(os.path.join(self.root, fr.MD_NAME), (old, old))     # 上次跑的结果
        api2, comp2 = fake_api()
        ok, failed, busy = fr.run_batch([self.root], api2, 1, fr.Claims())
        self.assertEqual((ok, comp2.calls), (1, []))                  # 不带 refresh：跳过
        ok, failed, busy = fr.run_batch([self.root], api2, 1, fr.Claims(), refresh=True)
        self.assertEqual((ok, failed, busy), (1, [], []))
        self.assertEqual([c[0] for c in comp2.calls].count('FigureClass'), 7)   # 整篇重新分类
        self.assertTrue(fr.is_done(self.root))
        api3, comp3 = fake_api()
        ok, _, _ = fr.run_batch([self.root], api3, 1, fr.Claims(), refresh=True)
        n = len(comp3.calls)
        self.assertEqual((ok, n), (1, 7 + 2))                          # 新开的一次 refresh 又会重做
        # 本次开跑之后才写好的（别的窗口刚做完）：跳过
        later = __import__('time').time() + 3600
        os.utime(os.path.join(self.root, fr.MD_NAME), (later, later))
        api4, comp4 = fake_api()
        ok, _, _ = fr.run_batch([self.root], api4, 1, fr.Claims(), refresh=True)
        self.assertEqual((ok, comp4.calls), (1, []))

    def test_stale_lock_taken_over(self):
        """窗口被关或崩了留下的锁：进程已经不在，或 15 分钟没刷新，别的窗口接手。"""
        import socket
        dead = subprocess.run([sys.executable, '-c', 'import os; print(os.getpid())'],
                              capture_output=True, text=True).stdout.strip()
        path = fr.Claims.path(self.root)
        os.makedirs(fr.CHECKPOINT_DIR, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump({'pid': int(dead), 'host': socket.gethostname()}, fh)
        self.assertFalse(fr.pid_alive(int(dead)))
        c = fr.Claims()
        self.assertFalse(c.busy(self.root))
        self.assertTrue(c.take(self.root))
        c.release(self.root)
        self.assertFalse(os.path.exists(fr.CHECKPOINT_DIR))     # 放开后空的 断点 文件夹也删了
        # 进程还在（就是本进程），但锁 20 分钟没刷新：也算没人领
        os.makedirs(fr.CHECKPOINT_DIR, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump({'pid': os.getpid(), 'host': socket.gethostname()}, fh)
        self.assertFalse(fr.Claims().take(self.root))
        old = __import__('time').time() - 20 * 60
        os.utime(path, (old, old))
        self.assertTrue(c.take(self.root))
        c.release(self.root)
        self.assertTrue(fr.pid_alive(os.getpid()))

    def test_key_env_and_log(self):
        api = fr.Api('gpt-6-astra', 4, key_env='FIGURE_READER_NO_SUCH_KEY')
        with self.assertRaises(SystemExit) as cm:
            api.client
        self.assertIn('FIGURE_READER_NO_SUCH_KEY', str(cm.exception))
        old_log, fr.LOG_DIR = fr.LOG_DIR, os.path.join(self.tmp, '日志')
        out, err = sys.stdout, sys.stderr
        buf = io.StringIO()
        sys.stdout = buf
        try:
            fr.main([self.root, '--status', '--log', '--key-env', 'FIGURE_READER_NO_SUCH_KEY'])
            sys.stdout.streams[1].close()
        finally:
            sys.stdout, sys.stderr, fr.LOG_DIR = out, err, old_log
        logs = os.listdir(os.path.join(self.tmp, '日志'))
        self.assertEqual(len(logs), 1)
        with open(os.path.join(self.tmp, '日志', logs[0]), encoding='utf-8') as fh:
            self.assertIn('共 1 篇', fh.read())
        self.assertIn('共 1 篇', buf.getvalue())


class SyntheticCompletions(FakeCompletions):
    """合成文章：图 1（两张图片拼成一张，A 两遍差 10%、B 一致）和 Table 2（图片版表格）。"""

    def parse(self, model, messages, response_format):
        text = messages[1]['content'][0]['text']
        image = messages[1]['content'][1]['image_url']['url']
        with self.lock:
            self.calls.append((response_format.__name__, text, image))
            n = sum(1 for c in self.calls if c[0] == 'Extraction' and 'Figure 1' in c[1])
        axis = dict(label='y', unit='%', scale='linear', min=0.0, max=100.0, ticks='0,50,100',
                    starts_at_zero=True, multiplier=None)
        if response_format is fr.TableClass:
            parsed = fr.TableClass(measures=[
                dict(header='WHC (g/g)', layout='column', protein_system=True, functional_property='water_holding',
                     n_values=2, has_sd=True, has_significance_letters=True),
                dict(header='Digestibility (%)', layout='column', protein_system=True, functional_property='none',
                     n_values=2, has_sd=True, has_significance_letters=False)], caption_topic='t', notes=None)
        elif response_format is fr.FigureClass:
            panels = [dict(label=lab, mark_types=['bar'], chart_type='bar', x_axis_label='Sample',
                           y_axis_label='Solubility (%)', caption_part='solubility (%s)' % lab, protein_system=True,
                           functional_property='solubility', y_tick_labels=['0', '50', '100'], n_series=1,
                           points_per_series=2, has_error_bars=False, has_significance_letters=False,
                           series_overlap_risk='low', overlap_reason=None) for lab in ('A', 'B')]
            parsed = fr.FigureClass(n_panels=2, panels=panels, caption_topic='t', notes=None)
        elif 'Table 2' in text:
            pts = [dict(series='WHC (g/g)', point_index=i + 1, x_category=x, x_value=None, y_value=0.0,
                        err_low=None, err_high=None, estimated=True, sig=None, note=note)
                   for i, (x, note) in enumerate((('WPI', '9.03±0.10a'), ('SPI', '7.5 ± 0.25b')))]
            plain = dict(axis, unit=None)
            parsed = fr.Extraction(panels=[dict(panel_id='WHC (g/g)', chart_type='bar', x_axis=plain, y_left=plain,
                                                y_right=None, series=[dict(name='WHC (g/g)', axis='left', chart_type='bar')],
                                                points=pts)], confidence='high', note=None)
        else:
            wanted = [p for p in ('A', 'B') if ('只提取它们：' in text and p in text.split('只提取它们：')[1].split('。')[0])]
            panels = []
            for p in wanted:
                k = 1.1 if (p == 'A' and n % 2) else 1.0
                panels.append(dict(panel_id=p, chart_type='bar', x_axis=axis, y_left=axis, y_right=None,
                                   series=[dict(name='WPI', axis='left', chart_type='bar')],
                                   points=[dict(series='WPI', point_index=i + 1, x_category=x, x_value=None,
                                                y_value=round(y * k, 2), err_low=None, err_high=None, estimated=True,
                                                sig=None, note=None) for i, (x, y) in enumerate((('pH 3', 40.0), ('pH 7', 80.0)))]))
            parsed = fr.Extraction(panels=panels, confidence='high', note=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))],
                               usage=SimpleNamespace(total_tokens=10))


class StuckCompletions(SyntheticCompletions):
    """图 1 每次读回来一个点都没有（自检不过）；table_error 时表 2 的读图抛网络错误。"""

    def __init__(self, table_error=False):
        super().__init__()
        self.table_error = table_error

    def parse(self, model, messages, response_format):
        text = messages[1]['content'][0]['text']
        if response_format is fr.Extraction and 'Table 2' in text and self.table_error:
            with self.lock:
                self.calls.append(('Extraction', text, None))
            raise RuntimeError('模拟网络错误')
        r = super().parse(model, messages, response_format)
        if response_format is fr.Extraction and 'Figure 1' in text:
            for p in r.choices[0].message.parsed.panels:
                p.points = []
        return r


class StuckBCompletions(StuckCompletions):
    """图 1 的 A 每次都读得一样（40、80），B 每次一个点都没有（自检不过）；table_error 时表 2 的读图抛网络错误。"""

    def parse(self, model, messages, response_format):
        text = messages[1]['content'][0]['text']
        r = SyntheticCompletions.parse(self, model, messages, response_format) \
            if not (response_format is fr.Extraction and 'Table 2' in text and self.table_error) \
            else StuckCompletions.parse(self, model, messages, response_format)
        if response_format is fr.Extraction and 'Figure 1' in text:
            for p in r.choices[0].message.parsed.panels:
                if p.panel_id == 'B':
                    p.points = []
                else:
                    for q, y in zip(p.points, (40.0, 80.0)):
                        q.y_value = y
        return r


class SyntheticPaper(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, '10.1_x')
        fig = os.path.join(self.root, fr.FIGURE_DIR)
        os.makedirs(fig)
        for name, size in (('fig1a.jpg', (300, 600)), ('fig1b.jpg', (300, 600)), ('table2.jpg', (800, 300)),
                           ('graphical_abstract.jpg', (500, 300)), ('scheme1.jpg', (400, 300))):
            Image.new('RGB', size, (200, 30, 30)).save(os.path.join(fig, name))
        with open(os.path.join(fig, 'figure_markdown.md'), 'w', encoding='utf-8') as fh:
            fh.write('\n'.join([
                '# Synthetic paper - ScienceDirect', '', 'DOI: https://doi.org/10.1/x  ', '',
                '## Graphical abstract', '', '![Graphical abstract](graphical_abstract.jpg)', '',
                '## Fig. 1', '', '![Fig. 1](fig1a.jpg)', '', '![Fig. 1](fig1b.jpg)', '',
                'Fig. 1. Protein solubility (A) and solubility (B) of WPI.', '',
                '## Scheme 1', '', '![Scheme 1](scheme1.jpg)', '', 'Scheme 1. Preparation.', '',
                '## Table 2（图片版表格）', '', '![Table 2](table2.jpg)', '', 'Functional properties.', '',
                'WHC, water holding capacity.', '',
                '## Fig. 3', '', '（图片下载失败，原图地址：https://x/gr3.jpg）', '', 'Fig. 3. Lost.', '']))
        with open(os.path.join(self.root, '全文.md'), 'w', encoding='utf-8') as fh:
            fh.write('Solubility of WPI rose sharply at neutral pH (Fig. 1A). Table 2 lists the WHC values of WPI.\n')
        self.old_ckpt, fr.CHECKPOINT_DIR = fr.CHECKPOINT_DIR, os.path.join(self.tmp, '断点')

    def tearDown(self):
        fr.CHECKPOINT_DIR = self.old_ckpt
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_parts_table_third_read_and_missing_image(self):
        comp = SyntheticCompletions()
        api = fr.Api('gpt-6-astra', 4, client=SimpleNamespace(chat=SimpleNamespace(completions=comp)))
        # 全文.md 一次都不许打开（用户 2026-10-02：只读 figure 子文件夹）
        import builtins
        from unittest import mock
        real_open = builtins.open

        def guarded(file, *args, **kw):
            if '全文.md' in str(file):
                raise AssertionError('读了全文.md：%s' % file)
            return real_open(file, *args, **kw)
        with mock.patch('builtins.open', guarded), mock.patch('io.open', guarded):
            self.assertTrue(fr.process_paper(fr.load_paper(self.root), api))
        self.assertFalse(any('rose sharply' in c[1] for c in comp.calls))
        self.assertTrue(all('正文里提到这张' in c[1] and '（未取到）' in c[1] for c in comp.calls if c[0] != 'Extraction'))
        # 分类时带上文章标题（figure_markdown.md 第一行，去掉 - ScienceDirect）
        self.assertTrue(all('文章标题（可能为空）：\nSynthetic paper\n' in c[1] for c in comp.calls if c[0] != 'Extraction'))
        # 也带上全篇所有图注原文（按页面顺序，没送分类的 Scheme、图片缺失的图 3 也在；不含图片链接和 DOI），每张都一样；
        # 读图不带（只带这张图自己的图注）
        everything = ('- Fig. 1：Fig. 1. Protein solubility (A) and solubility (B) of WPI.\n'
                      '- Scheme 1：Scheme 1. Preparation.\n'
                      '- Table 2（图片版表格）：Table 2. Functional properties. WHC, water holding capacity.\n'
                      '- Fig. 3：Fig. 3. Lost.')
        block = CAPTIONS_BLOCK.format(captions=everything)
        self.assertTrue(all(block in c[1] for c in comp.calls if c[0] != 'Extraction'))
        self.assertFalse(any('Scheme 1. Preparation' in c[1] or 'Fig. 3. Lost' in c[1]
                             for c in comp.calls if c[0] == 'Extraction'))
        # 分类：图 1 和表 2 各一次；图文摘要、Scheme 不送；图 3 图片缺失不送
        self.assertEqual(sorted(c[0] for c in comp.calls if c[0] != 'Extraction'), ['FigureClass', 'TableClass'])
        # 图 1 两张拼成一张：送出去的图是 300+24+300 = 624 宽、600 高（最长边最短的排法：并排）
        from PIL import Image
        img = [c[2] for c in comp.calls if c[0] == 'FigureClass'][0]
        with Image.open(io.BytesIO(__import__('base64').b64decode(img.split(',', 1)[1]))) as im:
            self.assertEqual(im.size, (624, 600))
        fig_reads = [c[1] for c in comp.calls if c[0] == 'Extraction' and 'Figure 1' in c[1]]
        self.assertEqual(len(fig_reads), 3)              # A 两遍差 10%：2026-10-12 起补第三遍（只读 A）
        self.assertTrue(all('只提取它们：A、B。' in r for r in fig_reads[:2]))
        self.assertIn('只提取它们：A。', fig_reads[2])
        # 前两遍完全独立（都不带名单）；第三遍沿用前两遍一致的名称，只给名字不给读数
        self.assertTrue(all(fr.GIVEN_NAMES not in r for r in fig_reads[:2]))
        self.assertIn(fr.GIVEN_NAMES + '\n- 子图 A：系列名 「WPI」；样品名 「pH 3」、「pH 7」', fig_reads[2])
        self.assertNotIn('40', fig_reads[2].split(fr.GIVEN_NAMES)[1])
        self.assertIn('图注里说明它的原文「solubility (A)」', fig_reads[0])
        table_reads = [c[1] for c in comp.calls if c[0] == 'Extraction' and 'Table 2' in c[1]]
        self.assertEqual(len(table_reads), 2)                            # 两遍抄得一样，不补
        self.assertIn('表里其余各项（「Digestibility (%)」）', table_reads[0])
        self.assertEqual(sorted(os.listdir(self.root)), sorted([fr.FIGURE_DIR, fr.MD_NAME, fr.DB_NAME, '全文.md']))
        # 反读数据.json：每个送读的子图是哪项指标、轴标题、图注片段；每个系列在哪个纵轴、轴标题、单位
        info = json.load(open(os.path.join(self.root, fr.DB_NAME), encoding='utf-8'))
        self.assertEqual(info['models'], {'prescreen': None, 'classify': 'gpt-6-astra', 'read': 'gpt-6-astra'})
        fig = next(f for f in info['figures'] if f['figure'] == 'Fig. 1')
        a = next(p for p in fig['panels'] if p['panel'] == 'A')
        self.assertEqual((a['property'], a['property_cn'], a['y_axis_title'], a['caption_part'], a['chart_type']),
                         ('solubility', '溶解度', 'Solubility (%)', 'solubility (A)', 'bar'))
        self.assertEqual(a['series'], [{'name': 'WPI', 'axis': 'left', 'axis_title': 'y', 'unit': '%', 'multiplier': None,
                                        'x_unit': '%', 'points': 2}])
        tab = next(f for f in info['figures'] if f['kind'] == 'table')
        self.assertEqual([(p['panel'], p['property'], p['layout'], p['series'][0]['points']) for p in tab['panels']],
                         [('WHC (g/g)', 'water_holding', 'column', 2)])
        with open(os.path.join(self.root, fr.MD_NAME), encoding='utf-8') as fh:
            md = fh.read()
        self.assertIn('![Fig. 1](figure/fig1a.jpg)\n![Fig. 1](figure/fig1b.jpg)', md)
        self.assertIn('**表 2：图像估读数据**（2 个点）', md)
        self.assertIn('**指标 WHC (g/g)**（2 点满足数值门槛', md)
        self.assertIn('| WHC (g/g) | WPI | 9.03 | 8.93 | 9.13 | a |', md)  # 均值、误差上下限、字母从格子原文算
        self.assertIn('| WHC (g/g) | SPI | 7.5 | 7.25 | 7.75 | b |', md)
        self.assertIn('表格图片的反读值是从表格图片上逐格抄录的', md)
        self.assertIn('以下图片没下载下来，没有分类和反读：Fig. 3（图片下载失败）', md)
        self.assertNotIn('Graphical abstract', md)
        self.assertNotIn('Scheme', md)
        # A 前两遍 44/40：相差 9.5% > 5%，补第三遍读成 44 → 三遍里两遍一致：表里给 44、写明另一遍没采用，仍需人工复核
        # （用户 2026-10-12 选 F）；B 两遍一致，high
        import re
        self.assertRegex(md, re.escape('| WPI | pH 3 | % | 44.0 | % | 3/3 | 0.0 | medium | **需人工复核** | 3 遍里 2 遍一致（44 / 44），')
                         + r'第 [12] 遍' + re.escape(' 40 和它们差得多，没采用；表中取这两遍的平均值，需人工复核。 |'))
        self.assertIn('| WPI | pH 7 | % | 88.0 | % | 3/3 | 0.0 | medium | **需人工复核** |', md)
        self.assertIn('**子图 A**（0 点满足数值门槛，2 点几遍读数相差超过 5%、取平均值待人工复核，0 点不满足要求，均列于下表）', md)
        self.assertIn('| WPI | pH 3 | % | 40.0 | % | 2/2 | 0.0 | high | 满足数值门槛 |', md)
        self.assertIn('| WPI | pH 7 | % | 80.0 | % | 2/2 | 0.0 | high | 满足数值门槛 |', md)
        self.assertIn('离散度不超过 5%，或几遍最多只差纵轴满量程的 1%', md)

    def test_given_up_figure_not_reread_after_restart(self):
        """表 2 网络出错、整篇先停时，图 1 已经连续两次没过自检：重跑不再读图 1（不再花钱），补上表 2 就完成。"""
        def api_of(comp):
            return fr.Api('gpt-6-astra', 4, client=SimpleNamespace(chat=SimpleNamespace(completions=comp)))
        comp = StuckCompletions(table_error=True)
        self.assertFalse(fr.process_paper(fr.load_paper(self.root), api_of(comp)))
        self.assertEqual(len([c for c in comp.calls if c[0] == 'Extraction' and 'Figure 1' in c[1]]), 4)
        comp2 = StuckCompletions()
        self.assertTrue(fr.process_paper(fr.load_paper(self.root), api_of(comp2)))
        self.assertEqual([c[0] for c in comp2.calls], ['Extraction', 'Extraction'])     # 只补表 2 的两遍
        self.assertTrue(all('Table 2' in c[1] for c in comp2.calls))
        with open(os.path.join(self.root, fr.MD_NAME), encoding='utf-8') as fh:
            md = fh.read()
        self.assertIn('图 1 子图 A，溶解度，读图失败：同样的输入连续 2 次没通过自检'
                      '（A: 该子图 0 个数据点；B: 该子图 0 个数据点），没有反读数值', md)
        self.assertIn('**表 2：图像估读数据**（2 个点）', md)
        self.assertNotIn('## Fig. 1', md)

    def test_only_failing_panel_dropped(self):
        """用户 2026-10-19：图 1 的 B 每次都没过自检，A 每次都读得好：只丢 B，A 照常合并（原来整张图读图失败）；
        B 两遍都丢了，不补第三遍；整篇先停（表 2 网络出错）后重跑，图 1 不再读。"""
        def api_of(comp):
            return fr.Api('gpt-6-astra', 4, client=SimpleNamespace(chat=SimpleNamespace(completions=comp)))
        comp = StuckBCompletions(table_error=True)
        self.assertFalse(fr.process_paper(fr.load_paper(self.root), api_of(comp)))
        self.assertEqual(len([c for c in comp.calls if c[0] == 'Extraction' and 'Figure 1' in c[1]]), 4)
        comp2 = StuckBCompletions()
        self.assertTrue(fr.process_paper(fr.load_paper(self.root), api_of(comp2)))
        self.assertEqual([c[0] for c in comp2.calls], ['Extraction', 'Extraction'])     # 只补表 2 的两遍
        self.assertTrue(all('Table 2' in c[1] for c in comp2.calls))
        with open(os.path.join(self.root, fr.MD_NAME), encoding='utf-8') as fh:
            md = fh.read()
        self.assertIn('## Fig. 1', md)
        self.assertIn('| WPI | pH 3 | % | 40.0 | % | 2/2 | 0.0 | high | 满足数值门槛 |', md)
        self.assertIn('| WPI | pH 7 | % | 80.0 | % | 2/2 | 0.0 | high | 满足数值门槛 |', md)
        self.assertIn('图 1 子图 B，溶解度，读图失败：同样的输入连续 2 次没通过自检（B: 该子图 0 个数据点），没有反读数值；'
                      '这张图的其余子图照常读', md)
        self.assertNotIn('子图 A，溶解度，读图失败', md)
        info = json.load(open(os.path.join(self.root, fr.DB_NAME), encoding='utf-8'))
        fig = next(f for f in info['figures'] if f['figure'] == 'Fig. 1')
        self.assertFalse(fig['read_failed'])
        a, b = (next(p for p in fig['panels'] if p['panel'] == x) for x in 'AB')
        self.assertTrue(b.get('read_failed'))
        self.assertNotIn('read_failed', a)
        self.assertEqual(a['series'][0]['points'], 2)


class SvgImages(unittest.TestCase):
    """ACS 有的图出版商只给 svg（抓取脚本原样存 .svg）：送模型前渲染成白底位图，长边 2048。"""
    SVG = ('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
           '<svg width="140pt" height="70pt" viewBox="0 0 140 70" xmlns="http://www.w3.org/2000/svg">'
           '<rect x="70" y="0" width="70" height="70" fill="#ff0000"/></svg>')
    ACS = r'D:\1.acs_papers_done\papers'          # 10-21 起 ACS 整理成 D:\1.acs_papers_done\papers\<文章>（这里只读图）

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    @staticmethod
    def sent(url):
        from PIL import Image
        im = Image.open(io.BytesIO(__import__('base64').b64decode(url.split(',', 1)[1])))
        im.load()
        return im

    def test_svg_white_background_and_long_side(self):
        wide = self.write('fig4.svg', self.SVG)                           # 单位是 pt：resvg-py 默认 dpi=0 会报错
        tall = self.write('fig5.svg', self.SVG.replace('width="140pt" height="70pt" viewBox="0 0 140 70"',
                                                       'width="70pt" height="140pt" viewBox="0 0 70 140"'))
        # resvg 先把原尺寸取整（186.67 → 187 像素）再放大，短边差几个像素（拉伸 <0.5%，不裁掉内容）
        im = self.sent(fr.data_url([wide]))
        self.assertEqual(im.width, 2048)
        self.assertAlmostEqual(im.height, 1024, delta=10)
        self.assertEqual(im.getpixel((100, 500)), (255, 255, 255))         # 透明处是白底，不是黑底
        self.assertEqual(im.getpixel((1900, 500)), (255, 0, 0))
        im = self.sent(fr.data_url([tall]))
        self.assertEqual(im.height, 2048)
        self.assertAlmostEqual(im.width, 1024, delta=10)

    def test_svg_and_bitmap_parts_packed(self):
        from PIL import Image
        jpg = os.path.join(self.tmp, 'fig6b.jpg')
        Image.new('RGB', (300, 600), (200, 30, 30)).save(jpg)
        im = self.sent(fr.data_url([self.write('fig6a.svg', self.SVG), jpg]))
        self.assertEqual(im.mode, 'RGB')
        self.assertLessEqual(max(im.size), fr.MAX_SIDE)

    def test_real_acs_svgs(self):
        found = [os.path.join(d, fr.FIGURE_DIR, f) for d in (os.listdir(self.ACS) if os.path.isdir(self.ACS) else [])
                 if os.path.isdir(os.path.join(self.ACS, d, fr.FIGURE_DIR))
                 for f in os.listdir(os.path.join(self.ACS, d, fr.FIGURE_DIR))
                 if f.endswith('.svg') and not f.startswith('._')]       # ._xxx.svg 是 Mac 附带的属性文件，不是图
        if not found:
            self.skipTest('acs_papers 里没有 svg 图')
        # acs_papers 一直在增加（10-02 已有 473 张 svg，逐张渲染要十几分钟）：按名字排序固定抽 6 张
        found = sorted(found)
        found = [found[i * len(found) // 6] for i in range(min(6, len(found)))]
        for rel in found:
            im = self.sent(fr.data_url([os.path.join(self.ACS, rel)]))
            self.assertEqual(max(im.size), fr.MAX_SIDE, rel)
            # 白底：不带底色再渲染一次，原图透明的地方送出去的图必须是白的。不看角上的颜色——真实的图角上
            # 可能就是图的内容（3c05334 图 1：左上是 A 区的浅青色底，左下压着 F 区的黑色边框）
            import resvg_py
            from PIL import Image
            path = os.path.join(self.ACS, rel)

            def bare(**size):
                with Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_path=path, dpi=96.0, **size)))) as x:
                    return x.convert('RGBA')
            raw = bare(width=fr.MAX_SIDE)
            if raw.height > raw.width:
                raw = bare(height=fr.MAX_SIDE)
            self.assertEqual(raw.size, im.size, rel)
            alpha = raw.getchannel('A')
            clear = [(x, y) for y in range(0, raw.height, 37) for x in range(0, raw.width, 37)
                     if alpha.getpixel((x, y)) == 0]
            if clear:                       # 有的 svg 自带不透明的白底页，没有透明处（铺白底另有合成图的测试）
                self.assertEqual({im.getpixel(p) for p in clear}, {(255, 255, 255)}, rel)


class Pipeline(unittest.TestCase):
    """用户 2026-10-21：五个脚本合成一个 pipeline.py；输入默认是 D:\\2.elsevier_papers 里每篇的 全文.md 和 figure\\（10-30 起
    read、all 默认是 D 盘八个总文件夹），
    输出写回每篇文件夹，报告和回答存档在 <root>\\_records，库在 <root>\\database（结构同 D:\\acs_papers_done）。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_commands_and_defaults(self):
        self.assertEqual(sorted(fr.COMMANDS), sorted(['all', 'read', 'merge', 'datapoint', 'method',
                                                      'datapoint-with-method', 'build-db', 'site']))
        self.assertIs(fr.COMMANDS['read'], fr.main)
        out = io.StringIO()
        from contextlib import redirect_stdout
        with redirect_stdout(out):
            self.assertEqual(fr.cli(['no-such-step']), 2)
        self.assertIn('不认识的命令', out.getvalue())
        for root in (fr.pc_ROOT, fr.ed_ROOT, fr.bd_OUT.rsplit(os.sep, 1)[0]):
            self.assertEqual(root, r'D:\2.elsevier_papers')
        # 用户 2026-10-30：read、all 不给文件夹时处理 D 盘 2–8 号总文件夹（ACS 已做完），建库 1–8 号合成一个库
        self.assertEqual(fr.PAPER_ROOTS, (r'D:\2.elsevier_papers', r'D:\3.wiley_papers-part', r'D:\4.RSC_papers',
                                            r'D:\5.MDPI_papers', r'D:\6.oxford_papers', r'D:\7.Taylor_papers',
                                            r'D:\8.Springer nature_papers'))
        self.assertEqual(fr.ACS_ROOT, r'D:\1.acs_papers_done')
        # 用户 2026-10-30：「wiley先跳过吧 处理后面的先」——不给文件夹时先不做 Wiley，顺序照旧按编号
        self.assertEqual(fr.SKIP_ROOTS, (r'D:\3.wiley_papers-part',))
        self.assertEqual(fr.DEFAULT_ROOTS, (r'D:\2.elsevier_papers', r'D:\4.RSC_papers', r'D:\5.MDPI_papers',
                                              r'D:\6.oxford_papers', r'D:\7.Taylor_papers', r'D:\8.Springer nature_papers'))
        self.assertEqual(fr.bd_OUT, r'D:\2.elsevier_papers\database')

    def test_layout_helpers(self):
        flat = os.path.join(self.tmp, 'elsevier_papers')
        done = os.path.join(self.tmp, 'acs_papers_done')
        os.makedirs(os.path.join(flat, '10.1016_x'))
        os.makedirs(os.path.join(done, 'papers', '10.1021_y'))
        self.assertEqual(fr.ed_papers_dir(flat), flat)
        self.assertEqual(fr.ed_papers_dir(done), os.path.join(done, 'papers'))
        self.assertEqual(fr.pc_papers_dir(done), os.path.join(done, 'papers'))
        self.assertEqual(fr.ed_records_dir(flat), os.path.join(flat, '_records', '数据点'))
        self.assertEqual(fr.ed_merged_path(done, '10.1021_y'), os.path.join(done, 'papers', '10.1021_y', '全文合并.md'))
        self.assertEqual(fr.ed_article_of(os.path.join(done, 'papers', '10.1021_y', '全文合并.md')), '10.1021_y')
        self.assertEqual(fr.ed_article_of(os.path.join(self.tmp, '10.1021_z.md')), '10.1021_z')   # 老结构的合并稿

    @unittest.skipUnless(os.path.isdir(SAMPLE), '没有样例文章')
    def test_merge_writes_into_paper_folder(self):
        """合并：全文合并.md 写进文章自己的文件夹，报告写 <root>\\_records\\全文合并；_records、database 不当文章。"""
        for layout in ('flat', 'papers'):
            root = os.path.join(self.tmp, layout)
            base = root if layout == 'flat' else os.path.join(root, 'papers')
            paper = os.path.join(base, os.path.basename(SAMPLE))
            shutil.copytree(SAMPLE, paper, ignore=shutil.ignore_patterns('*.jpg', '*.png', '*.gif', '*.svg', fr.pc_MERGED_NAME,
                                                                         'datapoint.md', 'method.json'))
            os.makedirs(os.path.join(root, '_records', '数据点'))
            os.makedirs(os.path.join(root, 'database'))
            self.assertEqual(fr.pc_all_papers(root), [paper])
            out = io.StringIO()
            from contextlib import redirect_stdout
            with redirect_stdout(out):
                self.assertEqual(fr.cli(['merge', '--root', root]), 0)
            self.assertTrue(os.path.isfile(os.path.join(paper, '全文合并.md')))
            self.assertTrue(os.path.isfile(os.path.join(root, '_records', '全文合并', '_合并报告.md')))
            self.assertFalse(fr.needs_merge(paper))
            # 读图结果比合并稿新：要重新合并
            t = os.path.getmtime(os.path.join(paper, '全文合并.md')) + 5
            os.utime(os.path.join(paper, fr.MD_NAME), (t, t))
            self.assertTrue(fr.needs_merge(paper))
            # 合并稿和原来脚本按老结构合并出来的一字不差（全文合并.md 的内容只看输入，和放在哪无关）
            text, rec = fr.pc_merge_paper(paper)
            self.assertEqual(text, open(os.path.join(paper, '全文合并.md'), encoding='utf-8').read())

    @unittest.skipUnless(os.path.isdir(SAMPLE), '没有样例文章')
    def test_all_dry_run_counts_without_writing(self):
        root = os.path.join(self.tmp, 'flat')
        paper = os.path.join(root, os.path.basename(SAMPLE))
        shutil.copytree(SAMPLE, paper, ignore=shutil.ignore_patterns('*.jpg', '*.png', '*.gif', '*.svg', fr.pc_MERGED_NAME,
                                                                     'datapoint.md', 'method.json'))
        before = sorted(os.listdir(paper))
        out = io.StringIO()
        from contextlib import redirect_stdout
        with redirect_stdout(out):
            self.assertEqual(fr.cli(['all', '--root', root, '--dry-run']), 0)
        text = out.getvalue()
        self.assertIn('文章 1 篇', text)
        self.assertIn('合并：1 篇', text)
        self.assertEqual(sorted(os.listdir(paper)), before)
        self.assertEqual(sorted(os.listdir(root)), [os.path.basename(SAMPLE)])

    def test_write_if_changed_and_combined_db(self):
        """用户 2026-10-21：datapoint.md、method.json 内容没变就不写（修改时间不动，建库看得出哪几篇变了）；
        ACS + Elsevier 合成一个库 D:\\protein_database，只重算新的、变了的文章。"""
        p = os.path.join(self.tmp, 'a', 'datapoint.md')
        self.assertTrue(fr.ed_write_if_changed(p, 'x\n'))
        t = os.path.getmtime(p) - 100
        os.utime(p, (t, t))
        self.assertFalse(fr.ed_write_if_changed(p, 'x\n'))
        self.assertEqual(os.path.getmtime(p), t)
        self.assertTrue(fr.ed_write_if_changed(p, 'y\n'))
        self.assertEqual(open(p, encoding='utf-8').read(), 'y\n')
        self.assertEqual(fr.bd_csv_row({'a': None, 'b': 3, 'c': 1.5, 'd': 'x'}), {'a': '', 'b': '3', 'c': '1.5', 'd': 'x'})
        self.assertEqual(fr.bd_DB_DIR, r'D:\protein_database')
        self.assertEqual(fr.bd_DB_ROOTS, (fr.ACS_ROOT,) + fr.PAPER_ROOTS)
        self.assertEqual(len(fr.bd_code_sig()), 16)

    def test_journal_from_fulltext(self):
        """用户 2026-10-21：建库里 Elsevier 文章的期刊名原来是空的（只认 ACS 的 DOI 前缀）→ 读 全文.md 开头 ScienceDirect 的期刊名。"""
        paper = os.path.join(self.tmp, '10.1016_j.fochx.2025.1')
        os.makedirs(paper)
        with open(os.path.join(paper, '全文.md'), 'w', encoding='utf-8') as fh:
            fh.write('[![Food Chemistry: X](https://x/cov.gif)](/journal/food-chemistry-x/vol/25)\n\n'
                     '## [Food Chemistry: X](/journal/food-chemistry-x "Go to Food Chemistry: X on ScienceDirect")\n\nDate: 1\n')
        self.assertEqual(fr.bd_journal_from_fulltext(self.tmp, '10.1016_j.fochx.2025.1'), 'Food Chemistry: X')
        self.assertEqual(fr.bd_journal_from_fulltext(self.tmp, 'no_such_paper'), '')
        self.assertIn('全文.md', fr.bd_PAPER_FILES)

    def test_organize_root(self):
        """用户 2026-10-30：2–8 号总文件夹跑完要和 D:\\1.acs_papers_done 一样（papers\\、_records\\、database\\）：直接放在总文件夹里的
        文章挪进 papers\\；papers、_records、database、不像文章的文件夹不动；papers 里已有同名的不挪。"""
        top = os.path.join(self.tmp, '9.x_papers')
        for name, files in (('10.1_a', ['全文.md']), ('10.1_b', ['figure/figure_markdown.md']), ('其他', ['说明.txt']),
                            ('_records', ['全文合并/_合并报告.md']), ('database', ['papers.csv']),
                            ('papers/10.1_old', ['全文.md']), ('papers/10.1_c', ['全文.md']), ('10.1_c', ['全文.md'])):
            for f in files:
                p = os.path.join(top, name, f)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, 'w', encoding='utf-8').write(name)
        os.utime(os.path.join(top, '10.1_a', '全文.md'), (1e9, 1e9))
        self.assertEqual(fr.organize_root(top, dry_run=True), (2, ['10.1_c']))
        self.assertTrue(os.path.isdir(os.path.join(top, '10.1_a')))
        self.assertEqual(fr.organize_root(top), (2, ['10.1_c']))
        self.assertEqual(sorted(os.listdir(top)), ['10.1_c', '_records', 'database', 'papers', '其他'])
        self.assertEqual(sorted(os.listdir(os.path.join(top, 'papers'))), ['10.1_a', '10.1_b', '10.1_c', '10.1_old'])
        self.assertEqual(os.path.getmtime(os.path.join(top, 'papers', '10.1_a', '全文.md')), 1e9)
        self.assertEqual(open(os.path.join(top, 'papers', '10.1_c', '全文.md'), encoding='utf-8').read(), 'papers/10.1_c')
        self.assertEqual(fr.organize_root(top), (0, ['10.1_c']))

    def test_doubled_figure_label(self):
        """用户 2026-10-30 八家通用：Wiley 上转过去的老文章页面上的图号是「Figure Figure 1」「Figure Scheme 1」，照样认成图 1、
        Scheme 1（标题照原样）；别的写法不受影响。"""
        text = ('# t\n\nDOI: 10.1/x\n\n## Figure Figure 1\n\n![Figure Figure 1](fig1.jpg)\n\nFigure Figure 1. Effect of pH.\n\n'
                '## Figure SCHEME 2\n\n![Figure SCHEME 2](scheme2.jpg)\n\n## FIGURE 3\n\n![FIGURE 3](fig3.jpg)\n\n'
                '## Figure Chart 1\n\n![Figure Chart 1](chart1.jpg)\n')
        items = fr.parse_figure_markdown(text)
        self.assertEqual([(it['kind'], it['label'], it['key'], it['heading']) for it in items],
                         [('figure', '1', 'fig1', 'Figure Figure 1'), ('scheme', '2', 'sc2', 'Figure SCHEME 2'),
                          ('figure', '3', 'fig3', 'FIGURE 3'), ('other', 'Figure Chart 1', 'other:Figure Chart 1', 'Figure Chart 1')])
        for head in ('Fig. 1', 'Figure 2', 'Fig. A13', 'Figure 1—', 'Figure 5 (a) RGB image', 'Scheme 1', 'figs1'):
            self.assertEqual(fr.lab(head), head)

    def test_read_in_windows(self):
        """用户 2026-10-21：调模型的几步同时开 5 个甚至更多窗口。读图开 n 个窗口，各带 --slot K/n（同 同时开5个*窗口.bat）。"""
        import subprocess
        from unittest import mock
        made = []

        class FakeProc:
            def __init__(self, cmd, **kw):
                made.append((cmd, kw))

            def wait(self):
                return 0
        with mock.patch.object(subprocess, 'Popen', FakeProc), mock.patch.object(fr.time, 'sleep', lambda s: None):
            self.assertEqual(fr.read_in_windows(r'D:\x', 3, ['--only-started']), [0, 0, 0])
        self.assertEqual([c[c.index('--slot') + 1] for c, _ in made], ['1/3', '2/3', '3/3'])
        for c, kw in made:
            self.assertEqual(c[2:6], [os.path.abspath(fr.__file__), 'read', r'D:\x', '--log'])
            self.assertEqual(c[-1], '--only-started')
        self.assertEqual(fr.READ_WINDOWS, 5)
        made.clear()                                   # 几个总文件夹（用户 2026-10-30）：都跟在 read 后面
        with mock.patch.object(subprocess, 'Popen', FakeProc), mock.patch.object(fr.time, 'sleep', lambda s: None):
            self.assertEqual(fr.read_in_windows([r'D:\x', r'D:\y z'], 2), [0, 0])
        for c, _ in made:
            self.assertEqual(c[2:7], [os.path.abspath(fr.__file__), 'read', r'D:\x', r'D:\y z', '--log'])
        with self.assertRaises(SystemExit):
            fr.all_main(['--root', self.tmp, '--windows', '0'])


class NewPublishers(unittest.TestCase):
    """用户 2026-10-30：「让那个脚本能通用的处理这八家出版商的全文 从读图到最后的数据点提取」——Wiley、RSC、MDPI、OUP 的
    全文.md 合并（照各家真实页面的写法缩短的样例）：出版商按 figure_markdown.md 的网页地址认；页面杂项删；图号认出来、
    反读数据插在图注后面；文末各节删；ACS、Elsevier 的认法不变。"""
    BLOCK = ('**子图 -**（1 点满足数值门槛，0 点不满足要求，均列于下表）\n\n'
             '| 系列 | X / 样品 | X 单位 | Y / 读数 | Y 单位 | 入库判定 |\n|---|---|---|---|---|---|\n'
             '| s1 | 1 | min | 2.5 | % | 满足数值门槛 |\n')

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def paper(self, name, url, full, heads):
        root = os.path.join(self.tmp, name)
        os.makedirs(os.path.join(root, 'figure'))
        fm = ['# t', '', 'DOI: https://doi.org/10.1/x', '网页: ' + url, '']
        rb = ['# t', '', 'DOI: 10.1/x', '']
        for h, cap in heads:
            fm += ['## ' + h, '', '![%s](fig1.png)' % h, '', cap, '']
            rb += ['## ' + h, '', cap, '', '**图 1：图像估读数据**（1 个点）', '', self.BLOCK, '']
        for path, text in (('全文.md', full), (os.path.join('figure', 'figure_markdown.md'), '\n'.join(fm)),
                           ('反读数据.md', '\n'.join(rb))):
            with open(os.path.join(root, path), 'w', encoding='utf-8') as fh:
                fh.write(text)
        return root

    def merged(self, root, pub):
        text, rec = fr.pc_merge_paper(root)
        self.assertIsNone(rec['error'])
        self.assertEqual(rec['pub'], pub)
        self.assertFalse([w for w in rec['warn'] if '没找到图注' in w], rec['warn'])
        self.assertNotIn('![', text)
        return text

    def assert_after(self, text, first, then):
        self.assertIn(first, text)
        self.assertTrue(text.index(then) > text.index(first), (first, then))

    def test_rsc(self):
        full = ('Paper| 13 August 2015\n\n# A study of proteins[†](javascript:;) _Open Access_\n\n[A Author](javascript:;)\n\n'
                'First published:\n\n13 August 2015\n\nOpen figure viewer\n\nThe abstract says solubility was 12.5 mg/mL.\n\n'
                '## Visual Abstract\n\n[![The caption](https://rscj.silverchair-cdn.com/x/m_ga.png?Expires=1)](https://x/ga.png)\n\n'
                '[View large](/view-large/figure/1/ga.tif) [Download slide](//rscj.silverchair-cdn.com/DownloadFile/x)\n\n'
                'Graphic blurb for the table of contents.\n\n## 1\\. Introduction\n\nIntro text ([Fig. 1](javascript:;)).\n\n'
                'Fig. 1\n\n[![The caption contains a description of this image.](https://rscj.silverchair-cdn.com/x/m_f1.png?E=1)]'
                '(https://x/f1.png)\n\n[View large](/view-large/figure/2/f1.tif) [Download slide](//rscj.silverchair-cdn.com/D/y)\n\n'
                'Effect of pH on solubility.\n\nTable 1\n\nComposition of samples\n\n| Sample | Protein |\n|---|---|\n| A | 12.5 |\n\n'
                '## Acknowledgements\n\nWe thank the lab.\n\n## Notes and references\n\n1. A reference.\n')
        text = self.merged(self.paper('10.1039_x', 'https://pubs.rsc.org/en/content/articlelanding/2015/ay/x', full,
                                      [('Fig. 1', 'Fig. 1 Effect of pH on solubility.')]), 'rsc')
        self.assertTrue(text.startswith('# A study of proteins\n'))
        self.assertIn('The abstract says solubility was 12.5 mg/mL.', text)          # RSC 的摘要没有标题，照样留下
        self.assert_after(text, 'Figure 1. Effect of pH on solubility.', '图 1 反读数据')
        self.assert_after(text, 'Table 1. Composition of samples', '| A | 12.5 |')
        for gone in ('View large', 'Download slide', 'Graphic blurb', 'We thank', 'A reference', 'Open figure viewer'):
            self.assertNotIn(gone, text)

    def test_wiley(self):
        full = ('[Journal X](/journal/1 "Journal X homepage")\n\nResearch Article\n\n# Wiley title\n\n'
                '[A B](/authored-by/B/A),\n\nFirst published: 1 May 2020\n\n## Abstract\n\nAbstract text.\n\n## INTRODUCTION\n\n'
                'Text with citation.[1](#x-bib-0001)\n\n'
                '[![Details are in the caption following the image](/cms/asset/a/x-fig-0001-m.png "Details are in the caption '
                'following the image")](/cms/asset/b/x-fig-0001-m.jpg)\n\n**Figure Figure 1.**\n\n[Open in figure viewer](#)'
                '[PowerPoint](/action/downloadFigures?id=x-fig-0001&partId=&doi=10.1002%2Fx)\n\nCaption of figure one.\n\n'
                '**SCHEME 1**\n\n[Open in figure viewer](#)[PowerPoint](/action/x)\n\nThe synthesis route.\n\n'
                '| Sample | ![equation image](/cms/asset/c/nueq001.gif) | Value |\n|---|---|---|\n| A | 1 | 2.5 |\n\n'
                '## ACKNOWLEDGMENTS\n\nThanks.\n\n## Recommended\n\n-   [Other article](/doi/10.1002/y)\n')
        text = self.merged(self.paper('10.1002_x', 'https://onlinelibrary.wiley.com/doi/10.1002/x', full,
                                      [('Figure Figure 1', 'Figure Figure 1. Caption of figure one.')]), 'wiley')
        self.assert_after(text, 'Figure 1. Caption of figure one.', '图 1 反读数据')
        self.assertIn('Scheme 1. The synthesis route.', text)
        self.assertIn('| A | 1 | 2.5 |', text)
        self.assertIn('Text with citation.1', text)
        for gone in ('Open in figure viewer', 'PowerPoint', 'Thanks', 'Other article', 'Journal X', 'Research Article'):
            self.assertNotIn(gone, text)

    def test_mdpi(self):
        full = ('[FoodsFoods](/journal/foods)\n\n# MDPI title\n\n## Abstract\n\nAbstract text.\n\nKeywords:\n\nprotein; gel\n\n'
                '## 1\\. Introduction\n\nIntro.\n\n**Figure 1.** Effects of heating on gel strength.\n\n'
                '| Sample | WHC (%) |\n|---|---|\n| A | 85.2 |\n\n**Table 1.** Water holding capacity of gels.\n\n'
                '## Supplementary Materials\n\nThe following supporting information can be downloaded at https://www.mdpi.com/s1.\n\n'
                '## Institutional Review Board Statement\n\nNot applicable.\n\n## Abbreviations\n\n'
                '| WHC | water holding capacity |\n|---|---|\n')
        text = self.merged(self.paper('10.3390_x', 'https://www.mdpi.com/2304-8158/12/10/1934', full,
                                      [('Figure 1', 'Figure 1. Effects of heating on gel strength.')]), 'mdpi')
        self.assert_after(text, 'Figure 1. Effects of heating on gel strength.', '图 1 反读数据')
        self.assertIn('Table 1. Water holding capacity of gels.', text)
        self.assertIn('| WHC | water holding capacity |', text)
        for gone in ('supporting information can be downloaded', 'Not applicable', 'FoodsFoods'):
            self.assertNotIn(gone, text)

    def test_oup(self):
        full = ('Journal Article\n\n# OUP title\n\n## Abstract\n\nAbstract text.\n\n'
                '![TOC image](https://oup.silverchair-cdn.com/x/ga.jpg)\n\nGraphical Abstract\n\nGraphic blurb.\n\n'
                '[Open in new tab](/view-large/figure/1/ga.jpg?itm_medium=graphical+abstract+image)'
                '[Download slide](/DownloadFile/DownloadImage.aspx?image=x)\n\n[gelation](javascript:;), [soy](javascript:;)\n\n'
                'Subject\n\n[Food and Nutrition Science](/bbb/search-results?page=1&tax=bbb/4)\n\nIssue Section:\n\nRegular Paper\n\n'
                '## Results\n\n![Gel strength of samples. \\[Colour figure can be viewed at wileyonlinelibrary.com\\]]'
                '(https://oup.silverchair-cdn.com/x/f1.jpg)\n\nFig. 1.\n\nGel strength of samples.\n\n'
                '[Open in new tab](/view-large/figure/2/f1.jpg)[Download slide](/DownloadFile/DownloadImage.aspx?image=y)\n\n'
                'Table 1.\n\n[Open in new tab](<\n                                /view-large/233456403>)\n\nGel properties.\n\n'
                '| Sample | Hardness (N) |\n|---|---|\n| A | 7.61 |\n\n## Peer review\n\nThe peer review history is online.\n\n'
                '## Footnotes\n\nA footnote.\n')
        text = self.merged(self.paper('10.1093_x', 'https://academic.oup.com/bbb/article/88/6/679/7631337', full,
                                      [('Fig. 1', 'Fig. 1. Gel strength of samples.')]), 'oup')
        self.assertIn('Abstract text.', text)
        self.assertIn('gelation, soy', text)
        self.assert_after(text, 'Figure 1. Gel strength of samples.', '图 1 反读数据')
        self.assert_after(text, 'Table 1. Gel properties.', '| A | 7.61 |')
        for gone in ('Graphic blurb', 'Food and Nutrition Science', 'Issue Section', 'Regular Paper', 'Open in new tab',
                     'view-large', 'peer review history', 'A footnote', 'Graphical Abstract'):
            self.assertNotIn(gone, text)

    def test_journal_new(self):
        """建库的期刊名：Wiley、RSC、OUP 读页面标题，MDPI 读全文第一行的期刊链接（期刊名写两遍）。"""
        cases = (('# T - Smith - 2020 - Journal of Food Science - Wiley Online Library', 'x', 'Journal of Food Science'),
                 ('# A | b | Food & Function | The Royal Society of Chemistry', 'x', 'Food & Function'),
                 ('# T | Bioscience, Biotechnology, and Biochemistry | Oxford Academic', 'x',
                  'Bioscience, Biotechnology, and Biochemistry'),
                 ('# T', '[![](https://mdpi-res.com/img/journals/foods-logo-sq.png?a8)FoodsFoods](/journal/foods)', 'Foods'),
                 ('# T', 'Journal Article', ''))
        for k, (title, line1, journal) in enumerate(cases):
            root = os.path.join(self.tmp, 'p%d' % k)
            os.makedirs(os.path.join(root, 'figure'))
            open(os.path.join(root, 'figure', 'figure_markdown.md'), 'w', encoding='utf-8').write(title + '\n\nDOI: x\n')
            open(os.path.join(root, '全文.md'), 'w', encoding='utf-8').write(line1 + '\n\n# T\n')
            self.assertEqual(fr.bd_journal_from_fulltext(self.tmp, 'p%d' % k), journal)

    def test_full_scan_cases(self):
        """10-30 全量体检查出来的：OUP 栏目名本身是链接（原来正文第一段被当成「下一行」删了）、按钮行的变体、断成两行的
        图片和链接；RSC「References and Notes」；MDPI 方法里带图表的伦理小节要留、纯声明要删，没有摘要的社论从页头后面开始。"""
        oup = ('Journal Article\n\n# T\n\n## Abstract\n\nAbstract.\n\nIssue Section:\n\n'
               '[NOTE](/bbb/search-results?f_TocHeadingTitleList=NOTE)\n\nKinesin 1 is a motor protein.\n\n'
               '![Figure 6 Binding pocket, top view (looking\nfrom the membrane).](https://oup.silverchair-cdn.com/x/f6.jpeg)\n\n'
               'Fig. 1.\n\nBinding of odorants.\n\n[Open in new tab](/view-large/figure//11198F1)Download slide\n\n'
               '[\n\nPDF](/bbb/article-pdf/68/3/685/35026548/bbb0685.pdf)\n\n## Source of funding\n\nGrant 1.\n\n'
               '## Conflict of Iinterest\n\nNone.\n')
        text = self.merged(self.paper('10.1093_y', 'https://academic.oup.com/bbb/article/1/2/3/4', oup,
                                      [('Fig. 1', 'Fig. 1. Binding of odorants.')]), 'oup')
        self.assertIn('Kinesin 1 is a motor protein.', text)
        self.assert_after(text, 'Figure 1. Binding of odorants.', '图 1 反读数据')
        for gone in ('NOTE', 'Open in new tab', 'Download slide', 'PDF', 'looking', 'Grant 1', 'None.'):
            self.assertNotIn(gone, text)
        rsc = ('# T\n\nOpen figure viewer\n\nAbstract.\n\n## 1\\. Introduction\n\nText.\n\nFig. 1\n\n'
               '[View large](/view-large/figure/1/x-f1.tif)\\[DownloadSlide\\]\n\nCaption one.\n\n## References and Notes\n\n'
               '1.  A, B. A reference. [Google Scholar](https://scholar.google.com/x)\n')
        text = self.merged(self.paper('10.1039_y', 'https://pubs.rsc.org/en/content/articlelanding/x', rsc,
                                      [('Fig. 1', 'Fig. 1 Caption one.')]), 'rsc')
        self.assert_after(text, 'Figure 1. Caption one.', '图 1 反读数据')
        for gone in ('DownloadSlide', 'View large', 'A reference', 'Google Scholar'):
            self.assertNotIn(gone, text)
        mdpi = ('# T\n\n[Order Reprints](/2304-8158/13/7/1113/reprints)\n\nEditorial text without headings.\n\n'
                '## Author Contributions\n\nX wrote it.\n')
        text = self.merged(self.paper('10.3390_y', 'https://www.mdpi.com/2304-8158/13/7/1113', mdpi, []), 'mdpi')
        self.assertIn('Editorial text without headings.', text)
        self.assertNotIn('X wrote it', text)
        mdpi = ('# T\n\n## Abstract\n\nAbstract.\n\n## 2\\. Materials and Methods\n\n### 2.1. Ethics Approval\n\n'
                'The study was approved by the board.\n\n**Table 1.** Inclusion criteria.\n\n| Criteria | Value |\n|---|---|\n'
                '| Age | 40–70 |\n\n### 2.2. Analysis\n\nMethods text.\n\n## 3\\. Results\n\nResults.\n\n## Ethics Statement\n\n'
                'Approved by committee 12.\n')
        text = self.merged(self.paper('10.3390_z', 'https://www.mdpi.com/x', mdpi, []), 'mdpi')
        self.assertIn('The study was approved by the board.', text)
        self.assertIn('| Age | 40–70 |', text)
        self.assertNotIn('committee 12', text)

    def test_old_publishers_unchanged(self):
        """ACS、Elsevier 的文章（网页是 pubs.acs.org、sciencedirect.com）照原来的 pc_publisher 认。"""
        for url, full, pub in (('https://pubs.acs.org/doi/10.1021/x', '# t\n\nSearch for other works by this author\n', 'acs'),
                               ('https://www.sciencedirect.com/science/article/pii/x',
                                '# t\n\nAuthor links open overlay panel\n', 'elsevier')):
            root = self.paper('p_' + pub, url, full, [])
            lines = full.split('\n')
            self.assertEqual(fr.pc_publisher_of(root, lines), pub)
            self.assertEqual(fr.pc_publisher_of(root, lines), fr.pc_publisher(full))


class MergeChecks(unittest.TestCase):
    """用户 2026-11-05：Elsevier 合并没写出的 14 篇里 11 篇是核对太严或链接没清干净——公式里阶乘后跟方括号不算图片、
    引用号后紧跟原文括号里的网址不算链接、缩写表原文多一个逗号算对得上、网址里带空格的自链接和套两层的网址链接清干净；
    真剩的图片、链接照旧拦。"""

    @staticmethod
    def check(line):
        clean = fr.pc_clean_inline(line)
        return fr.pc_check(clean + '\n', [line], {}, [('text', clean)])

    def test_links_cleaned(self):
        self.assertEqual(fr.pc_clean_inline('available at [https://blast.ncbi.nlm.nih.gov/ 34](https://blast.ncbi.nlm.nih.gov/ 34)^,35.'),
                         'available at https://blast.ncbi.nlm.nih.gov/ 34^,35.')
        self.assertEqual(fr.pc_clean_inline(r'(URL: [http://x.org/geo/](http://x.org/geo/)\]([http://x.org/geo/](http://x.org/geo/))). Key'),
                         '(URL: http://x.org/geo/). Key')

    def test_checks(self):
        self.assertIsNone(self.check('φ = (|S|!(M−|S|−1)!)/M![f_x (S ∪ {i}) − f_x (S)] (4)'))
        self.assertIsNone(self.check(r'database [\[39\]](#BIB39)(http://scop.org/scop) was performed.'))
        self.assertEqual(self.check('a ![x](y z) b'), '还剩图片')
        self.assertEqual(self.check('see x](http://a.org) b'), '还剩链接')
        self.assertTrue(fr.pc_in_src('SOD', {'SOD,,'}))
        self.assertFalse(fr.pc_in_src('SOD', {'SOD,,,'}))


if __name__ == '__main__':
    unittest.main(verbosity=1)
