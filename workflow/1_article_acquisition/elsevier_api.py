#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
elsevier_api.py —— 用 Elsevier 官方 API（ScienceDirect 全文 XML）抓 Elsevier 文献：全文 markdown + 原图 + 图注。
不开浏览器、不用 opencli。成品文件和 fetch_papers.py 抓网页的一样，放在同一个位置：

    D:\2.elsevier_papers\<DOI，斜杠换成下划线>\
        全文.md                  正文（标题、摘要、关键词、各节、图注、表格、公式），参考文献不要
        figure\fig1.jpg …        原图（API 给的高清图，和网页版下载的是同一个文件，逐字节相同）
        figure\figure_markdown.md 每张图 / 图片版表格的标题、本地图片和图注（写法和网页版完全一样）

    python elsevier_api.py            # 读默认清单 doi_lists\Elsevier.md（只读不改），存到
                                      # D:\2.elsevier_papers；那里已经有 全文.md 的自动跳过（不调 API）；进度记在脚本旁边的
                                      # 进度_api.db（和网页版的台账分开），中途停了重跑同一条命令接着来
    python elsevier_api.py --status   # 只看进度：完成 / 没有全文 / 失败 / 未读 各多少
    python elsevier_api.py 10.1016/j.foodhyd.2021.106593 https://doi.org/10.1016/j.aac.2022.11.003   # 只抓这几篇
    python elsevier_api.py --list 别的清单.md      # 换一个清单；--dir 某文件夹：读那个文件夹里所有 .md

API key：环境变量 ELSEVIER_API_KEY（脚本不打印它，也不写进任何文件）；有机构令牌的另放 ELSEVIER_INSTTOKEN。
全文权限按 key 和所在网络（机构 IP）认，和浏览器里的登录无关。

和网页版（fetch_papers.py）一样的地方：
    - 每篇的文件夹名、全文.md / figure\ / figure_markdown.md 的结构和写法；图片命名（fig1、scheme1、fx1、
      graphical_abstract、table4 …）、图注「Fig. 1. …」、表题「Table 1. …」都直接用 fetch_papers.py 里的同一套函数
    - 表格按原表的行、列、合并格重建成 markdown 表格（多层表头分行），放在原位；表下注放在表格下面
    - 上下标写成纯文本（Ca²⁺、10¹⁰、T_c）；公式按结构写成一行文字（分式 (分子)/分母），编号放在末尾
    - 引文、图表引用写成网页版那样的链接（[49](#bib49)、[Fig. 5](#fig5)）：网页和 XML 用的是同一套编号；一组引文
      照网页按每条自己的标签重写（Chen et al., 2019, Chiti and Dobson, 2006）
    - 表格里的空格子、缩写表、化学键符号（单键 / 双键图片链接）、附录只留完整版，都照网页版的写法
    - 参考文献不要；正文里的引文链接保留
    - 已经有 全文.md 的文章跳过（不管是网页版还是这个脚本抓的），--refresh 重抓
和网页版不同的地方（XML 和网页本来就不一样）：
    - 没有网页上的期刊横幅、作者链接、「View PDF」、主题词链接、下载原图的两行等网页杂项
    - API 的全文 XML 里没有 Highlights（Elsevier 不提供，实测换 view 参数也拿不到），全文.md 里就没有这一节
    - 图放在引用它的那一段后面（网页上有时插在一段话中间，把句子截断）
    - 个别公式里的空格和网页上不完全一样（网页的公式排版本身前后不一）；少数文章 XML 和网页正文的版本不同，
      个别措辞不一样。这些不影响后续流程（12 篇实测合并：图表题、表格、读图数据插入位置都和网页版相同）
没有全文：API 只给摘要（没有全文权限、或只有 PDF 的老文章）、只给未分节的纯文本（扫描版）的，记为「没有全文」，
不保存。API 查不到的 DOI（不是 Elsevier 的，或 DOI 有误）记为「不是 Elsevier」。

限速（Elsevier 官方：全文接口每周 50,000 次、每秒 10 次；7 天重置）：一篇一篇按顺序抓，两篇之间默认隔 1 秒
（--interval）。返回 429 时：只是太快了就等一会儿再试；周配额用完（QUOTA_EXCEEDED）就整批停下，说明什么时候
重置，重跑同一条命令接着来。返回 401（key 无效）：偶尔会无故回一次，等 30 秒再试，连着 3 次都是 401 才整批停下。

只用 Python 标准库；需要同一文件夹里的 fetch_papers.py（复用它的台账、表格、上下标、图片命名、图注文件）。
"""
import argparse
import io
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True               # 不在脚本文件夹里留 __pycache__
import fetch_papers as fp  # noqa: E402  同文件夹的通用抓取脚本

API = 'https://api.elsevier.com/content'
LEDGER_NAME = '进度_api.db'          # 和网页版的 进度.db 分开：API 的全文权限和浏览器里的不一样
# 默认的 DOI 清单（用户 2026-10-28）：只读不改；台账放在脚本旁边
DEFAULT_LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'doi_lists', 'Elsevier.md')
ARS = 'https://ars.els-cdn.com/content/image/1-s2.0-%s-%s'   # 网页上的图片地址（全文.md 里的图片行、命名用）
SD_PAGE = 'https://www.sciencedirect.com/science/article/pii/%s'
# 化学键之类的特殊符号（<ce:glyph name="sbnd"/>）：网页上是 ScienceDirect 自己的小图，网页版全文.md 里就是这个图片链接
# （D:\elsevier_papers 全部文章里统计到的就这些，地址都一样）；有 Unicode 字符的几何符号网页上直接是字符
GLYPH_URL = 'https://sdfestaticassets-us-east-1.sciencedirectassets.com/shared-assets/55/entities/%s.gif'
GLYPH_ALT = {'sbnd': 'single bond', 'dbnd': 'double bond', 'rad': 'radical dot', 'tbnd': 'triple bond',
             'dbnd6': '6-point double bond', 'tbnd6': '6-point triple bond', 'bigdot': 'big dot above (accent)',
             'lbond2': '2 bonds on the lefthand side', 'rbond2': '2 bonds on the righthand side',
             'pdbdtd': 'partial double bond, top dashed', 'qbnd': 'quadruple bond',
             'rbond3': '3 bonds on the righthand side', 'lbd2bd': '2 bonds on the lefthand side, bottom double'}
GLYPH_CHARS = {'lozf': '⧫', 'loz': '◊', 'squf': '▪', 'square': '□', 'utrif': '▴', 'utri': '▵', 'dtrif': '▾',
               'dtri': '▿', 'ltrif': '◂', 'rtrif': '▸', 'cir': '○', 'starf': '★', 'star': '☆'}
XLINK = '{http://www.w3.org/1999/xlink}'


class Fatal(SystemExit):
    pass


class NoFullText(Exception):
    pass


class NotFound(Exception):
    pass


def api_key():
    key = os.environ.get('ELSEVIER_API_KEY', '').strip()
    if not key:
        raise Fatal('没有设置环境变量 ELSEVIER_API_KEY（Elsevier 的 API key）')
    return key


def api_get(url, accept='text/xml', timeout=90):
    """带 key 的请求（key 放在请求头里，不进地址）。429：太快了就等一会儿再试，周配额用完就停下；401：等 30 秒再试，连着 3 次才停。"""
    headers = {'X-ELS-APIKey': api_key(), 'Accept': accept, 'User-Agent': 'elsevier_api.py (python urllib)'}
    token = os.environ.get('ELSEVIER_INSTTOKEN', '').strip()
    if token:
        headers['X-ELS-Insttoken'] = token
    n401 = 0
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            status = e.headers.get('X-ELS-Status') or ''
            if e.code == 429:
                if 'QUOTA' in status.upper():
                    reset = e.headers.get('X-RateLimit-Reset')
                    when = time.strftime('%Y-%m-%d %H:%M', time.localtime(int(reset))) if reset and reset.isdigit() else '7 天内'
                    raise Fatal('Elsevier API 的周配额用完了（%s），%s 重置；重置后重跑同一条命令接着来' % (status, when))
                time.sleep(2 ** attempt)              # 每秒请求太多：等一会儿再试
                continue
            if e.code == 404:
                raise NotFound(status or 'HTTP 404')
            if e.code == 401:                         # 偶尔会无故回一次 401：等半分钟再试，连着 3 次都是 401 才算 key 真不行了
                n401 += 1
                if n401 < 3:
                    print('  API 回了 HTTP 401 %s，等 30 秒再试（第 %d 次）' % (status, n401), flush=True)
                    time.sleep(30)
                    continue
                raise Fatal('API key 无效（连着 3 次 HTTP 401 %s）' % status)
            if e.code == 403:
                raise NoFullText('API 拒绝访问（HTTP 403 %s）：没有这篇的权限' % status)
            if e.code >= 500 and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError('API 返回 HTTP %d %s' % (e.code, status))
        except (urllib.error.URLError, OSError) as e:
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError('连不上 Elsevier API：%s' % e)
    raise RuntimeError('API 一直返回 429（请求太快），稍后再试')


# ---------------------------------------------------------------- XML → markdown --
def name(e):
    return e.tag.rsplit('}', 1)[-1] if isinstance(e.tag, str) else ''


def kids(e, *names):
    return [c for c in e if name(c) in names] if names else [c for c in e if isinstance(c.tag, str)]


def first(e, *names):
    return next((c for c in e.iter() if c is not e and name(c) in names), None) if e is not None else None


def esc(s):
    """opencli（turndown）对文字的转义，照它的规则写（每段文字单独转义，^ 指这段文字的开头）。"""
    s = s.replace('\\', '\\\\').replace('*', '\\*').replace('`', '\\`').replace('[', '\\[').replace(']', '\\]')
    s = s.replace('_', '\\_')
    s = re.sub(r'^-', r'\\-', s)
    s = re.sub(r'^\+ ', r'\\+ ', s)
    s = re.sub(r'^(=+)', r'\\\1', s)
    s = re.sub(r'^(#{1,6}) ', r'\\\1 ', s)
    s = re.sub(r'^~~~', r'\\~~~', s)
    s = re.sub(r'^>', r'\\>', s)
    return re.sub(r'^(\d+)\. ', r'\1\\. ', s)


def ws(s):
    """连续空白并成一个空格：只认空格、制表、换行（同 opencli 和网页版图注），不换行空格（\\xa0）照原样留着。"""
    return re.sub(r'[ \t\n\r\f]+', ' ', s or '')


def scr(kind, t):
    t = t.strip()
    if not t:
        return ''
    k = 'B' if kind == 'sub' else 'P'
    return 'XQSU%sAXQ%sXQSU%sZXQ' % (k, t, k)


def wrapped(t):
    if not (t.startswith('(') and t.endswith(')')):
        return False
    d = 0
    for i, ch in enumerate(t):
        d += (ch == '(') - (ch == ')')
        if d == 0 and i < len(t) - 1:
            return False
    return True


def operand(t):
    """分式的分子、分母：带空格或运算符的加括号（同网页版公式的写法）。"""
    t = t.strip()
    b = fp.SCRIPT_MARKS.sub('', t)
    return '(%s)' % t if re.search(r'[\s+\-−×·/=÷±]', b) and not wrapped(b) else t


ACCENTS = {'¯': '̄', '‾': '̄', 'ˉ': '̄', '^': '̂', 'ˆ': '̂', '~': '̃', '˜': '̃',
           '˙': '̇', '→': '⃗', '⃗': '⃗'}
# 公式的空格照网页版：网页上的公式是 MathJax 排的，字符之间的空白按 TeX 的原子类别和间距表加（网页版脚本把
# 「有间距」读成一个空格）。类别：ORD 普通、OP 大运算符（∑ ∏ ∫）、BIN 二元运算、REL 关系、OPEN / CLOSE 括号、
# PUNCT 标点、INNER 括号组（mfenced）。间距：1 细，2 中，3 粗；带 s 的在上下标里不加（TeX 的规则）。
REL_CHARS = set('=<>≤≥≈≠∼≡≪≫→←↔⇌⇄⇋∝⩽⩾≅≃∈∉⊂⊃:')
BIN_CHARS = set('+−×·±∓∗÷∘⋅∩∪∧∨')
OPEN_CHARS, CLOSE_CHARS, PUNCT_CHARS = set('([{⟨⌊⌈'), set(')]}⟩⌋⌉'), set(',;')
LARGE_OPS = set('∑∏∐∫∬∭∮⋃⋂⨁⨂')
# MathJax 显示 <mo> 时换掉的几个字符（网页上看到的就是换过的）
MO_REMAP = {'-': '−', '*': '∗', "'": '′', '’': '′', '"': '″', '”': '″', '∕': '/'}
OPERATOR_NAME = re.compile(r'^[a-z][a-z0-9]*$', re.I)   # 多字母的函数名（ln、log、exp …）：MathJax 当大运算符类
SPACING = {
    ('ORD', 'OP'): '1', ('ORD', 'BIN'): '2s', ('ORD', 'REL'): '3s', ('ORD', 'INNER'): '1s',
    ('OP', 'ORD'): '1', ('OP', 'OP'): '1', ('OP', 'REL'): '3s', ('OP', 'INNER'): '1s',
    ('BIN', 'ORD'): '2s', ('BIN', 'OP'): '2s', ('BIN', 'OPEN'): '2s', ('BIN', 'INNER'): '2s',
    ('REL', 'ORD'): '3s', ('REL', 'OP'): '3s', ('REL', 'OPEN'): '3s', ('REL', 'INNER'): '3s',
    ('CLOSE', 'OP'): '1', ('CLOSE', 'BIN'): '2s', ('CLOSE', 'REL'): '3s', ('CLOSE', 'INNER'): '1s',
    ('PUNCT', 'ORD'): '1s', ('PUNCT', 'OP'): '1s', ('PUNCT', 'REL'): '1s', ('PUNCT', 'OPEN'): '1s',
    ('PUNCT', 'CLOSE'): '1s', ('PUNCT', 'PUNCT'): '1s', ('PUNCT', 'INNER'): '1s',
    ('INNER', 'ORD'): '1s', ('INNER', 'OP'): '1', ('INNER', 'BIN'): '2s', ('INNER', 'REL'): '3s',
    ('INNER', 'OPEN'): '1s', ('INNER', 'PUNCT'): '1s', ('INNER', 'INNER'): '1s',
}


def mo_text(e, raw=False):
    t = re.sub(r'[⁡-⁤]', '', ''.join(e.itertext())).strip()
    return t if raw else MO_REMAP.get(t, t)


def atom(e):
    """一个 MathML 元素在 TeX 里算哪类原子。"""
    n, ks = name(e), [c for c in kids(e) if name(c) not in ('annotation', 'annotation-xml')]
    if n == 'mo':
        t = mo_text(e)
        if mo_text(e, raw=True) == '∕':        # 除号斜杠 ∕：网页上显示成 /，两边有空格（二元运算）
            return 'BIN'
        return ('REL' if t in REL_CHARS else 'BIN' if t in BIN_CHARS else 'OPEN' if t in OPEN_CHARS else
                'CLOSE' if t in CLOSE_CHARS else 'PUNCT' if t in PUNCT_CHARS else 'OP' if t in LARGE_OPS else 'ORD')
    if n == 'mi':
        t = ''.join(e.itertext()).strip()
        return 'OP' if len(t) > 1 and OPERATOR_NAME.match(t) and e.get('mathvariant', 'normal') == 'normal' else 'ORD'
    if n == 'mfenced':
        return 'INNER'
    if n in ('mrow', 'mstyle', 'mpadded') and len(ks) == 1:
        return atom(ks[0])
    if n in ('munder', 'mover', 'munderover', 'msub', 'msup', 'msubsup') and ks and atom(ks[0]) == 'OP':
        return 'OP'
    return 'ORD'


def row(ks, script):
    """一行原子：按 TeX 的间距表在需要的地方加空格（二元运算在开头、在运算符 / 左括号后面时当普通字符）。"""
    # <mspace>（作者排的空格，词与词之间常用它）：照网页版写成一个空格，不参与间距计算
    items = [(c, 'SPACE' if name(c) == 'mspace' else atom(c)) for c in ks if name(c) not in ('none', 'mprescripts')]
    spaced = [i for i, (_, cl) in enumerate(items) if cl == 'SPACE']
    items = [x for x in items if x[1] != 'SPACE'] if spaced else items
    gap_before = set()
    k = 0
    for i, (c, cl) in enumerate([(c, 'SPACE' if name(c) == 'mspace' else '') for c in ks if name(c) not in ('none', 'mprescripts')]):
        if cl == 'SPACE':
            gap_before.add(k)
        else:
            k += 1
    classes = [cl for _, cl in items]
    for i, cl in enumerate(classes):
        if cl == 'BIN' and (i == 0 or classes[i - 1] in ('BIN', 'OP', 'REL', 'OPEN', 'PUNCT')):
            classes[i] = 'ORD'
    for i, cl in enumerate(classes):
        if cl == 'BIN' and (i == len(classes) - 1 or classes[i + 1] in ('REL', 'CLOSE', 'PUNCT')):
            classes[i] = 'ORD'
    out = []
    for i, (c, _) in enumerate(items):
        if i:
            sp = SPACING.get((classes[i - 1], classes[i]), '')
            if i in gap_before or (sp and not (script and sp.endswith('s'))):
                out.append(' ')
        out.append(math(c, script))
    return ''.join(out)


def mscr(kind, t):
    """公式里的上下标：* 和 _ 先转义（网页版的公式文字经过 opencli 转义，上标里只有 * 时照样写成 ^*，
    不会被当成 markdown 的强调符号删掉）。"""
    return scr(kind, t.replace('*', '\\*').replace('_', '\\_'))


def math(e, script=False):
    """MathML → 一行文字（上下标先写成标记，最后和正文一起写成纯文本）。script：在上下标里。"""
    n, ks = name(e), [c for c in kids(e) if name(c) not in ('annotation', 'annotation-xml')]

    def sub(c):
        return math(c, True)
    if n in ('mi', 'mn', 'mtext', 'ms'):
        return re.sub(r'[⁡-⁤]', '', ''.join(e.itertext()))
    if n == 'mo':
        return mo_text(e)
    if n in ('mspace', 'mphantom', 'none', 'mprescripts'):
        return ''
    if n == 'mfrac' and len(ks) >= 2:
        return operand(math(ks[0], script)) + '/' + operand(math(ks[1], script))
    if n == 'msub' and len(ks) >= 2:
        return math(ks[0], script) + mscr('sub', sub(ks[1]))
    if n == 'msup' and len(ks) >= 2:
        return math(ks[0], script) + mscr('sup', sub(ks[1]))
    if n == 'msubsup' and len(ks) >= 3:
        return math(ks[0], script) + mscr('sub', sub(ks[1])) + mscr('sup', sub(ks[2]))
    if n in ('mover', 'munder', 'munderover') and len(ks) >= 2:
        base = math(ks[0], script)
        if n == 'mover':
            over = sub(ks[1]).strip()
            return base + ACCENTS[over] if over in ACCENTS else base + mscr('sup', over)
        if n == 'munder':
            return base + mscr('sub', sub(ks[1]))
        return base + mscr('sub', sub(ks[1])) + mscr('sup', sub(ks[2]) if len(ks) > 2 else '')
    if n == 'msqrt':
        return '√' + operand(row(ks, script))
    if n == 'mroot' and len(ks) >= 2:
        return mscr('sup', sub(ks[1])) + '√' + operand(math(ks[0], script))
    if n == 'mfenced':
        seps = (e.get('separators') if e.get('separators') is not None else ',').replace(' ', '')
        parts = [math(c, script).strip() for c in ks]
        body = ''.join(p + (seps[min(i, len(seps) - 1)] + ('' if script else ' ') if seps and i < len(parts) - 1 else '')
                       for i, p in enumerate(parts))
        return e.get('open', '(') + body.strip() + e.get('close', ')')
    if n == 'mtable':
        rows = [' '.join(math(c, script).strip() for c in kids(r) if name(c) == 'mtd')
                for r in ks if name(r) in ('mtr', 'mlabeledtr')]
        return '; '.join(rows)
    if n == 'mmultiscripts' and ks:
        out = math(ks[0], script)
        rest = ks[1:]
        for i in range(0, len(rest) - 1, 2):
            if name(rest[i]) == 'mprescripts':
                break
            out += mscr('sub', sub(rest[i])) + mscr('sup', sub(rest[i + 1]))
        return out
    if n == 'semantics':
        return math(ks[0], script) if ks else ''
    return row(ks, script)


def cite_numbers(text, count):
    """一组引文的编号：「1–15」「3, 5–7」展开成 [1, 2, …]；个数要和 refid 的个数对得上，否则 None（照原样写一个链接）。"""
    nums = []
    for part in re.split(r'\s*[,;]\s*', text.strip()):
        m = re.fullmatch(r'(\d+)\s*[–—-]\s*(\d+)', part)
        if m and int(m.group(1)) <= int(m.group(2)):
            nums += range(int(m.group(1)), int(m.group(2)) + 1)
        elif part.isdigit():
            nums.append(int(part))
        else:
            return None
    return nums if len(nums) == count else None


def math_line(e):
    """一个公式写成一行：各种宽度的空白（不换行空格、细空格等）都并成一个普通空格。"""
    t = re.sub(r'\s+', ' ', math(e)).strip()
    return re.sub(r'\(\s+', '(', re.sub(r'\s+\)', ')', t))


class Doc:
    """一篇文章的转换状态：图表（ce:floats）、正文里的锚点、已经写出的图表、给图片下载用的清单。"""

    def __init__(self, art, pii, objects):
        self.pii, self.objects = pii, objects
        floats = first(art, 'floats')
        self.floats = {f.get('id'): f for f in (kids(floats) if floats is not None else []) if f.get('id')}
        self.done = set()
        self.figures, self.tables = [], []        # 给 fetch_papers.plan_elsevier：和网页版的图表清单同一个样子
        # 每个能被引用的东西自己的标签（参考文献、图、表、公式、表注的 <ce:label>；小节是「编号 标题」），一组引用要用
        self.labels = {}
        for e in art.iter():
            if not isinstance(e.tag, str) or not e.get('id'):
                continue
            parts = [c for c in e if name(c) == 'label'] + [c for c in e if name(e) == 'section' and name(c) == 'section-title']
            text = ' '.join(re.sub(r' {2,}', ' ', self.inline(p, True)).strip() for p in parts).strip()
            if text:
                self.labels[e.get('id')] = text

    # ---- 行内
    def inline(self, e, plain=False, anchors=None):
        out = [self.text(e.text, plain)]
        for c in e:
            out.append(self.node(c, plain, anchors))
            out.append(self.text(c.tail, plain))
        return ''.join(out)

    @staticmethod
    def text(s, plain):
        """一段文字。API 返回的 XML 排过版：元素之间插了换行和缩进（「</ce:cross-ref>\\n    <ce:float-anchor/>」），
        原文里没有。排版加的都在文字段的开头或结尾、从换行开始：去掉；换行前面原本有的空格（「</ce:sup> \\n    」）
        和段中间的换行照常算空格。"""
        s = re.sub(r'\n[ \t\r\n]*$', '', re.sub(r'^\n[ \t\r\n]*', '', s or ''))
        s = ws(s)
        return s if plain else esc(s)

    def node(self, c, plain, anchors):
        n = name(c)
        if n in ('italic', 'bold'):
            x = self.inline(c, plain, anchors)
            if plain or not x.strip():
                return x
            mark = '_' if n == 'italic' else '**'
            lead, trail = x[:len(x) - len(x.lstrip())], x[len(x.rstrip()):]
            return lead + mark + x.strip() + mark + trail
        if n in ('sup', 'inf'):
            x = self.inline(c, plain, anchors)
            return scr('sup' if n == 'sup' else 'sub', x) if x.strip() else x
        if n in ('cross-ref', 'cross-refs'):
            x = self.inline(c, plain, anchors).strip()
            ref = (c.get('refid') or '').split()
            if len(ref) > 1:
                # 一组引用（cross-refs）网页上不照原文写，而是每个目标按它自己的标签各写一个链接、逗号隔开：
                # 「Chen, Xiong, & Xu, 2019; Chiti & Dobson, 2006」→ Chen et al., 2019, Chiti and Dobson, 2006；
                # 「1–3」→ [1], [2], [3]；「Figs. 1–6」→ Fig. 1, …, Fig. 6；「Sections 2.4.2 and 2.4.3」→ 2.4.2 标题, 2.4.3 标题
                labels = [self.labels.get(r) for r in ref]
                if all(labels):
                    return ', '.join(labels if plain else ['[%s](#%s)' % (esc(k), r) for k, r in zip(labels, ref)])
                t = fp.SCRIPT_MARKS.sub('', self.inline(c, True)).strip()     # 目标没有标签：数字编号自己展开
                o, cl = (t[0], t[-1]) if t[:1] in '[(' and t[-1:] in '])' else ('', '')
                nums = cite_numbers(t[len(o):len(t) - len(cl)], len(ref))
                if nums:
                    cites = ['%s%d%s' % (o, k, cl) for k in nums]
                    return ', '.join(cites if plain else ['[%s](#%s)' % (esc(k), r) for k, r in zip(cites, ref)])
            return x if plain or not (x and ref) else '[%s](#%s)' % (x, ref[0])
        if n == 'inter-ref':
            x = self.inline(c, plain, anchors)
            href = c.get(XLINK + 'href') or ''
            return x if plain or not (x.strip() and href.startswith(('http://', 'https://'))) else '[%s](%s)' % (x.strip(), href)
        if n == 'float-anchor':
            if anchors is not None and c.get('refid'):
                anchors.append(c.get('refid'))
            return ''
        if n == 'math':
            return math_line(c)
        if n in ('footnote', 'alt-text', 'inline-figure', 'display', 'list', 'def-list', 'keyword'):
            return ''
        if n == 'glyph':                            # 图片在图注文字（innerText）里没有字
            g = c.get('name') or ''
            return GLYPH_CHARS.get(g) or ('' if plain or not g else '![%s](%s)' % (GLYPH_ALT.get(g, g), GLYPH_URL % g))
        if n == 'hsp':                              # 窄空格（数字和单位之间）：网页上是不换行空格
            return '\xa0'
        if n in ('vsp', 'br'):
            return ' '
        return self.inline(c, plain, anchors)

    # ---- 段落与块
    def para(self, p):
        """一段 → [块]：段中的公式、列表、显示块单独成块，段后接上段里锚定的图表。"""
        blocks, buf, anchors = [], [self.text(p.text, False)], []

        def flush():
            t = re.sub(r' {2,}', ' ', ''.join(buf)).strip()
            if t:
                blocks.append(t)
            buf.clear()
        for c in p:
            n = name(c)
            if n in ('display', 'list', 'def-list', 'textbox'):
                flush()
                blocks += self.block(c)
            else:
                buf.append(self.node(c, False, anchors))
            buf.append(self.text(c.tail, False))
        flush()
        for ref in anchors:
            blocks += self.float_blocks(ref)
        return blocks

    def block(self, e, level=2):
        n = name(e)
        if n in ('para', 'simple-para', 'note-para'):
            return self.para(e)
        if n == 'display':
            out = []
            for c in kids(e):
                out += self.block(c, level)
            return out
        if n == 'formula':
            m = first(e, 'math')
            lab = next((c for c in e if name(c) == 'label'), None)
            if m is not None:
                t = math_line(m)
            else:                                   # 不是 MathML（<ce:chem> 等）：照原文字写出
                t = self.text(e.text, False) + ''.join(self.node(c, False, None) + self.text(c.tail, False)
                                                      for c in e if name(c) != 'label')
                t = re.sub(r' {2,}', ' ', t).strip()
            t = (t + ' ' + ws(''.join(lab.itertext())).strip()).strip() if lab is not None else t
            return [t] if t else []
        if n == 'figure':                           # 摘要里的图文摘要
            return self.figure_blocks(e)
        if n == 'table':
            return self.table_blocks(e)
        if n == 'list':
            return [self.list_md(e)]
        if n == 'def-list':
            out = []
            for c in e.iter():
                if name(c) in ('def-term', 'def-description'):
                    t = re.sub(r' {2,}', ' ', self.inline(c)).strip()
                    if t:
                        out.append(t)
            return out
        if n in ('section', 'acknowledgment', 'conflict-of-interest', 'appendices', 'textbox', 'section-title',
                 'e-component', 'data-availability', 'nomenclature'):
            return self.section(e, level)
        return []

    def list_md(self, e, indent=''):
        lines = []
        for item in kids(e, 'list-item'):
            lab = next((c for c in item if name(c) == 'label'), None)
            label = ws(''.join(lab.itertext())).strip() if lab is not None else ''
            parts = []
            for c in kids(item):
                if name(c) == 'label':
                    continue
                if name(c) == 'list':
                    parts.append(self.list_md(c, indent + '    '))
                else:
                    parts += self.block(c)
            body = ('\n\n' + indent + '    ').join(parts)
            if label:
                lines.append('%s-   %s\n\n%s    %s' % (indent, esc(label), indent, body) if body else '%s-   %s' % (indent, esc(label)))
            else:
                lines.append('%s-   %s' % (indent, body))
        return '\n'.join(lines)

    def heading(self, e, level, default=''):
        lab = next((c for c in e if name(c) == 'label'), None)
        tit = next((c for c in e if name(c) == 'section-title'), None)
        title = re.sub(r' {2,}', ' ', self.inline(tit)).strip() if tit is not None else default
        label = ws(''.join(lab.itertext())).strip() if lab is not None else ''
        if label and not label.endswith('.'):
            label += '.'
        text = (esc(label + ' ') + title).strip() if label else title
        return '#' * min(level, 6) + ' ' + text if text else ''

    def section(self, e, level):
        n = name(e)
        default = {'acknowledgment': 'Acknowledgements', 'conflict-of-interest': 'Declaration of competing interest',
                   'data-availability': 'Data availability', 'nomenclature': 'Nomenclature'}.get(n, '')
        out = []
        # 致谢里自己没标题、只装着几个小节（Acknowledgments、Abbreviations…）：网页上这些小节各自是一节，和正文各节同级
        if n == 'appendices' or (n == 'acknowledgment' and any(name(c) == 'section' for c in e)
                                 and not any(name(c) == 'section-title' for c in e)):
            for c in kids(e):
                out += self.block(c, level)
            return out
        if n == 'e-component':                      # 补充材料：只留说明文字
            cap = first(e, 'caption')
            return [t for c in (kids(cap) if cap is not None else []) for t in self.block(c)]
        h = self.heading(e, level, default)
        if h:
            out.append(h)
        for c in kids(e):
            if name(c) in ('label', 'section-title'):
                continue
            out += self.block(c, level + 1)
        return out

    # ---- 图
    def link_urls(self, f):
        """图框里每张图（ce:link 的 locator，如 gr1、fx1、sc1）：网页上的地址（小图 + 大图），给命名和下载用。"""
        out = []
        for ln in f.iter():
            if name(ln) != 'link' or not ln.get('locator'):
                continue
            loc = ln.get('locator')
            ext = self.objects.get(loc, {}).get('ext', 'jpg')
            out.append((loc, ARS % (self.pii, '%s.%s' % (loc, ext)), ARS % (self.pii, '%s_lrg.%s' % (loc, ext))))
        return out

    def caption(self, f, plain):
        cap = next((c for c in f if name(c) == 'caption'), None)
        paras = [re.sub(r' {2,}', ' ', self.inline(p, plain)).strip() for p in (kids(cap) if cap is not None else [])]
        return [p for p in paras if p]

    def label(self, f):
        lab = next((c for c in f if name(c) == 'label'), None)
        return re.sub(r' {2,}', ' ', self.inline(lab, True)).strip() if lab is not None else ''

    def figure_blocks(self, f):
        if f.get('id') in self.done:
            return []
        self.done.add(f.get('id'))
        links = self.link_urls(f)
        label = self.label(f)
        md_caps, plain_caps = self.caption(f, False), self.caption(f, True)
        alt = label or next((ws(''.join(a.itertext())).strip() for a in f if name(a) == 'alt-text'), '')
        blocks = ['![%s](%s)' % (alt, small) for _, small, _ in links]
        if md_caps:
            lab = esc(label + '. ') if label else ''
            blocks.append(lab + md_caps[0])
            blocks += md_caps[1:]
        cap_plain = '\n\n'.join(([label + '. ' + plain_caps[0]] if label and plain_caps else plain_caps[:1]) + plain_caps[1:])
        if links:
            self.figures.append({'label': label, 'caption': cap_plain,
                                 'urls': [u for _, small, big in links for u in (big, small)]})
        return blocks

    # ---- 表
    def table_blocks(self, t):
        if t.get('id') in self.done:
            return []
        self.done.add(t.get('id'))
        label = self.label(t)
        md_caps, plain_caps = self.caption(t, False), self.caption(t, True)
        blocks = []
        if md_caps or label:
            blocks.append(((esc(label + '. ') if label else '') + (md_caps[0] if md_caps else '')).strip())
            blocks += md_caps[1:]
        notes_md, notes_plain = [], []
        for c in t.iter():
            if name(c) == 'table-footnote':
                lab = next((x for x in c if name(x) == 'label'), None)
                if lab is not None:
                    notes_md.append(esc(ws(''.join(lab.itertext())).strip()))
                    notes_plain.append(ws(''.join(lab.itertext())).strip())
                for p in kids(c):
                    if name(p) != 'label':
                        notes_md += self.para(p)
                        notes_plain.append(re.sub(r' {2,}', ' ', self.inline(p, True)).strip())
            elif name(c) == 'legend':
                for p in kids(c):
                    notes_md += self.para(p)
                    notes_plain.append(re.sub(r' {2,}', ' ', self.inline(p, True)).strip())
        groups = [g for g in t.iter() if name(g) == 'tgroup']
        if groups:
            for g in groups:
                blocks.append(self.tgroup_md(g))
        else:                                       # 图片版表格（同网页版：图片存进 figure\，表题、表下注写进图注文件）
            links = self.link_urls(t)
            blocks += ['![%s](%s)' % (label or 'Table', small) for _, small, _ in links]
            if links:
                cap_plain = '\n\n'.join(([label + '. ' + plain_caps[0]] if label and plain_caps else plain_caps[:1]) + plain_caps[1:])
                self.tables.append({'label': label, 'caption': cap_plain, 'notes': [x for x in notes_plain if x],
                                    'urls': [u for _, small, big in links for u in (big, small)]})
        return blocks + [x for x in notes_md if x]

    def tgroup_md(self, g):
        """CALS 表格 → 和网页版同样的 markdown 表格（fetch_papers.table_block：跨行跨列、多层表头分行）。"""
        cols = {}
        for i, cs in enumerate(kids(g, 'colspec')):
            cols[cs.get('colname') or str(i + 1)] = int(cs.get('colnum') or i + 1) - 1
        spans = {s.get('spanname'): (s.get('namest'), s.get('nameend')) for s in kids(g, 'spanspec')}
        md, rows, occupied = [], [], set()

        def add(text):
            md.append(text)
            return len(md) - 1
        for part in kids(g, 'thead', 'tbody', 'tfoot'):
            head = name(part) == 'thead'
            for row in kids(part, 'row'):
                r, cells, c = len(rows), [], 0
                for ent in kids(row, 'entry'):
                    st, en = ent.get('namest'), ent.get('nameend')
                    if ent.get('spanname') in spans:
                        st, en = spans[ent.get('spanname')]
                    start = cols.get(ent.get('colname') or st)
                    if start is not None:
                        while c < start:                # 跳过的列：被上面的合并格占着的不补，其余补空格子
                            if (r, c) not in occupied:
                                cells.append({'i': add(''), 'cs': 1, 'rs': 1, 'head': head})
                            c += 1
                    while (r, c) in occupied:
                        c += 1
                    cs = (cols[en] - cols[st] + 1) if st in cols and en in cols else 1
                    rs = int(ent.get('morerows') or 0) + 1
                    for dr in range(1, rs):
                        for dc in range(cs):
                            occupied.add((r + dr, c + dc))
                    text = re.sub(r' {2,}', ' ', ' '.join(
                        b for p in ([ent] if not any(name(x) in ('para', 'list') for x in ent) else kids(ent))
                        for b in ([self.inline(p)] if p is ent or name(p) not in ('para', 'list') else self.block(p)))).strip()
                    # 原表里明写的空格子：表头里和行标题列（role=rowhead）的，ScienceDirect 网页上写着「Empty Cell」（给读屏
                    # 软件的），网页版成品里就是这几个字；数据区的照旧是空的。表头的空格子网页上不是 <th>，这一层表头
                    # 网页版就不算表头（不加粗，上面合并下来的格子照写）
                    label = 'Empty Cell' if head or 'rowhead' in (ent.get('role') or '').split() else ''
                    cells.append({'i': add(text or label), 'cs': cs, 'rs': rs, 'head': head and bool(text)})
                    c += cs
                rows.append(cells)
        if not rows:
            return ''
        t = {'rows': rows, 'i_html': add(' '.join(md)), 'i_caption': add(''), 'i_foot': []}
        return fp.table_block(t, md)

    # ---- 图表放到正文里
    def float_blocks(self, ref):
        f = self.floats.get(ref)
        if f is None or ref in self.done:
            return []
        return self.figure_blocks(f) if name(f) == 'figure' else self.table_blocks(f) if name(f) == 'table' else []


def objects_of(root):
    """coredata 后面的 <objects>：每个图（gr1、fx1 …）的高清图 / 标准图在 API 上的地址和扩展名。"""
    out, by_file = {}, {}
    for o in root.iter():
        if name(o) != 'object' or not (o.text or '').strip():
            continue
        url = o.text.strip()
        fname = urllib.parse.urlsplit(url).path.rsplit('/', 1)[-1]
        by_file[fname] = url
        ref = o.get('ref')
        if ref and o.get('category') in ('standard', 'high'):
            m = re.search(r'\.(\w+)$', fname)
            if o.get('category') == 'standard' or ref not in out:
                out.setdefault(ref, {})['ext'] = m.group(1) if m else 'jpg'
    return out, by_file


def convert(root):
    """全文 XML → (标题, DOI, PII, 全文 markdown, 图表清单)。没有全文时抛 NoFullText。"""
    # 外层标签有三种：article；converted-article（2004 年前后及更早、从老格式转来的）；simple-article（勘误、讨论等短文，头尾叫 simple-head / simple-tail）
    art = next((e for e in root.iter() if name(e) in ('article', 'converted-article', 'simple-article')), None)
    core = next((e for e in root if name(e) == 'coredata'), None)
    get = lambda tag: next((ws(''.join(x.itertext())).strip() for x in core.iter() if name(x) == tag), '') if core is not None else ''
    doi = get('doi').lower()
    pii = next((ws(x.text).strip() for x in root.iter() if name(x) == 'pii-unformatted' and x.text), '') or \
        re.sub(r'[^A-Z0-9]', '', get('pii').upper())
    body = next((e for e in art if name(e) == 'body'), None) if art is not None else None
    if body is None or not any(name(x) in ('para', 'simple-para') for x in body.iter()):
        # 真有一大段未分节的纯文本才是扫描版老文章（元数据清单里也会出现「rawtext」这个词，不算）
        raw = sum(len(''.join(x.itertext())) for x in root.iter() if name(x) == 'rawtext')
        if raw > 3000:
            raise NoFullText('API 只给了未分节的纯文本（%d 字符，扫描版老文章），没有结构化全文' % raw)
        oa = get('openaccess')
        raise NoFullText('API 只返回了摘要%s（没有全文权限，或这篇只有 PDF）' % ('（非开放获取）' if oa == '0' else ''))
    # 同一节有两个版本（view="extended" 完整版、"compact-standard" 精简版，附录里常见）：网页上显示的是完整版
    for p in list(root.iter()):
        for c in list(p):
            v = c.get('view') if isinstance(c.tag, str) else None
            if v and not {'all', 'extended'} & set(v.split()):
                p.remove(c)
    objects, by_file = objects_of(root)
    d = Doc(art, pii, objects)
    d.by_file = by_file
    head = next((e for e in art if name(e) in ('head', 'simple-head')), None)
    tit = first(head, 'title')
    title_md = re.sub(r' {2,}', ' ', d.inline(tit)).strip() if tit is not None else ''
    # 纯文字标题（图注文件第一行，网页上是浏览器标签页标题）：上下标压平，Pb2+
    title_plain = fp.SCRIPT_MARKS.sub('', re.sub(r' {2,}', ' ', d.inline(tit, True))).strip() if tit is not None else ''
    out = []
    journal, publisher = get('publicationName'), get('publisher')
    if journal:
        out.append('## ' + esc(journal))
    if publisher:
        out.append('## Published by: ' + esc(publisher))
    out.append('# ' + title_md)
    if doi:
        out.append('[%s](https://doi.org/%s)' % (esc(doi), doi))
    for c in (kids(head) if head is not None else []):
        n = name(c)
        if n == 'abstract':
            cls = c.get('class') or ''
            default = {'author': 'Abstract', 'graphical': 'Graphical abstract', 'author-highlights': 'Highlights'}.get(cls, '')
            if cls == 'teaser':
                continue
            h = d.heading(c, 2, default)
            if h:
                out.append(h)
            for sec in kids(c, 'abstract-sec'):
                sh = d.heading(sec, 3)
                if sh:
                    out.append(sh)
                for p in kids(sec):
                    if name(p) not in ('label', 'section-title'):
                        out += d.block(p)
        elif n == 'keywords':
            h = d.heading(c, 2, 'Keywords' if (c.get('class') or 'keyword') == 'keyword' else 'Abbreviations')
            if h:
                out.append(h)
            # 缩写表：全称是缩写下面嵌的一层 keyword，网页上写成「ACC1,」「acetyl-CoA carboxylase 1」两段
            def sq(t):
                return re.sub(r' {2,}', ' ', t).strip()
            words =['\n\n'.join([sq(d.inline(k)) + (',' if kids(k, 'keyword') else '')] + [sq(d.inline(s)) for s in kids(k, 'keyword')])
                     for k in kids(c, 'keyword')]
            out.append('\n\n;\n\n'.join(w for w in words if w.strip(',')))
    for c in kids(body):
        n = name(c)
        if n == 'sections':
            for s in kids(c):
                out += d.block(s, 2) if name(s) != 'para' else d.para(s)
        else:
            out += d.block(c, 2)
    for c in (kids(head, 'data-availability') if head is not None else []):    # 数据可用性声明：XML 放在文章头部，网页上在正文后面
        out += d.block(c, 2)
    for ref in list(d.floats):                       # 正文里没有锚点的图表放在最后
        if ref not in d.done:
            out += d.float_blocks(ref)
    tail = next((e for e in art if name(e) in ('tail', 'simple-tail')), None)
    for c in (kids(tail) if tail is not None else []):
        if name(c) not in ('bibliography', 'further-reading'):
            out += d.block(c, 2)
    md = '\n\n'.join(x for x in out if x and x.strip()) + '\n'
    # 不换行空格：网页版全文.md 里一律是普通空格（opencli 转 markdown 时换掉的），图注文件里照原样留着
    return title_plain, doi, pii, fp.scripts_readable(md.replace('\xa0', ' ')), d


# ---------------------------------------------------------------- 图 --
def download(urls, by_file):
    """候选地址按顺序：先走 API（带 key 的请求头），不行再直接下网页上的同一个文件。返回 (字节, 扩展名, 文件名) 或 (None, None, 原因)。"""
    errors = []
    for u in urls:
        fname = urllib.parse.urlsplit(u).path.rsplit('/', 1)[-1]
        tries = ([('api', by_file[fname])] if fname in by_file else []) + [('web', u)]
        for how, src in tries:
            try:
                if how == 'api':
                    data = api_get(src, accept='*/*', timeout=120)
                else:
                    req = urllib.request.Request(src, headers={'User-Agent': fp.BROWSERS['chrome']['ua'] % fp.UA_OS})
                    with urllib.request.urlopen(req, timeout=120) as r:
                        data = r.read()
                ext = fp.image_ext(data, svg=False)
                if not ext:
                    raise ValueError('下载到的不是图片（%d 字节）' % len(data))
                return data, ext, fname
            except (Fatal, KeyboardInterrupt):
                raise
            except Exception as e:
                errors.append('%s（%s）：%s' % (fname[:60], how, str(e)[:80]))
    return None, None, '；'.join(errors) or '没有图片地址'


def fetch_images(items, by_file):
    for item in items:
        for f in item['files']:
            data, ext, info = download(f['urls'], by_file)
            f.update(data=data, file=(f['name'] + ext) if data else None, source=info if data else None,
                     error=None if data else info)
            print('  %-22s %s' % (f['name'], '%7.0f KB  %s' % (len(data) / 1024, info) if data else '下载失败：' + info),
                  flush=True)


# ---------------------------------------------------------------- 一篇 --
def fetch_one(item, a):
    """返回 (状态, 文件夹, 提醒)：状态 done / no_fulltext / not_elsevier / invalid。"""
    doi, url = fp.parse_item(item)
    m = re.search(r'/pii/([A-Za-z0-9]+)', url or '')
    if not doi and not m:
        return 'invalid', '', '认不出 DOI 或 PII：%s' % item
    root_dir = os.path.join(a.out, fp.folder_name(doi, url or ''))
    if doi and os.path.exists(os.path.join(root_dir, '全文.md')) and not a.refresh:
        print('  已经有了：%s（要重抓加 --refresh）' % root_dir, flush=True)
        return 'done', root_dir, '已有，跳过'
    where = 'doi/' + urllib.parse.quote(doi, safe='/:;()._-') if doi else 'pii/' + m.group(1)
    try:
        xml = api_get('%s/article/%s?view=FULL' % (API, where))
    except NotFound as e:
        return 'not_elsevier', '', 'Elsevier API 查不到（不是 Elsevier 的文章或 DOI 有误；%s）' % e
    root = ET.fromstring(xml)
    title, doi2, pii, md, d = convert(root)
    doi = doi or doi2
    root_dir = os.path.join(a.out, fp.folder_name(doi, url or ''))
    page = {'title': title + ' - ScienceDirect', 'url': SD_PAGE % pii, 'content': md}
    media = fp.media_readable({'figures': d.figures, 'tables': d.tables})
    items = fp.plan_elsevier(media, SD_PAGE % pii)
    print('  %s' % title, flush=True)
    print('  全文 %d 字符，表格 %d 张，公式 %d 个' % (len(md), md.count('\n|---'), sum(1 for x in root.iter() if name(x) == 'formula')),
          flush=True)
    n_fig = sum(1 for i in items if i['kind'] == 'figure')
    n_tab = sum(1 for i in items if i['kind'] == 'table')
    print('  图 %d 个、图片版表格 %d 个，下载原图：' % (n_fig, n_tab), flush=True)
    fetch_images(items, d.by_file)
    fp.write_paper(root_dir, page, items, SD_PAGE % pii, doi)
    failed = [f['name'] for i in items for f in i['files'] if not f.get('data')]
    notes = ['%d 张图下载失败：%s' % (len(failed), '、'.join(failed))] if failed else []
    if not fp.BODY_HEADING.search(md):
        notes.append('没认出正文小节的标题（Introduction / Methods / Results …），请核对')
    print('  已保存 -> %s' % root_dir, flush=True)
    for n in notes:
        print('  ⚠ %s' % n, flush=True)
    return 'done', root_dir, '；'.join(notes)


# ---------------------------------------------------------------- 主流程 --
class ListLedger(fp.Ledger):
    """读一个（或几个）DOI 清单文件的台账：清单只读不改，台账 进度_api.db 放在脚本旁边。
    其余（登记、记录、--status 报告、两份同时跑不重复）和 fetch_papers.py 的台账一样。"""

    def __init__(self, files):
        super().__init__(HERE)
        self.list_files = [os.path.abspath(f) for f in files]

    def scan(self):
        known = {p: (m, s) for p, m, s in self.db.execute('SELECT path, mtime, size FROM files')}
        changed = 0
        for full in self.list_files:
            if not os.path.isfile(full):
                raise Fatal('找不到 DOI 清单：%s' % full)
            st = os.stat(full)
            if known.get(full) == (st.st_mtime_ns, st.st_size):
                continue
            with io.open(full, encoding='utf-8-sig', errors='replace') as fh:
                items = fp.parse_items(fh.read())
            rows = [(fp.item_key(item), full, i, item) for i, item in enumerate(items)]
            with self.db:
                self.db.execute('DELETE FROM sources WHERE file = ?', (full,))
                self.db.executemany('INSERT OR IGNORE INTO sources VALUES (?, ?, ?, ?)', rows)
                self.db.execute('INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?)', (full, st.st_mtime_ns, st.st_size, len(rows)))
            changed += 1
        for p in set(known) - set(self.list_files):  # 这次没读的清单：它的条目不算进进度
            with self.db:
                self.db.execute('DELETE FROM sources WHERE file = ?', (p,))
                self.db.execute('DELETE FROM files WHERE path = ?', (p,))
        return len(self.list_files), changed


def saved(item, out):
    """这篇在保存位置里已经有 全文.md 了：返回它的文件夹，没有返回 ''。"""
    doi, url = fp.parse_item(item)
    root = os.path.join(out, fp.folder_name(doi, url or '')) if (doi or url) else ''
    return root if root and os.path.exists(os.path.join(root, '全文.md')) else ''


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace', line_buffering=True)
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description='Elsevier API（全文 XML）→ 全文.md + 原图 + 图注，成品同 fetch_papers.py')
    ap.add_argument('items', nargs='*', help='DOI 链接、DOI 号或 ScienceDirect 文章网址，可以给多个（只抓这几篇，不记台账）')
    ap.add_argument('--list', '--file', dest='list', default=DEFAULT_LIST,
                    help='DOI 清单文件（默认 %s；只读不改；台账 %s 放在脚本旁边）' % (DEFAULT_LIST, LEDGER_NAME))
    ap.add_argument('--dir', help='改读一个 DOI 列表文件夹（里面所有 .md，台账 %s 放在那个文件夹里）' % LEDGER_NAME)
    ap.add_argument('--out', default=fp.papers_dir('elsevier'), help='保存位置（默认 %s）' % fp.papers_dir('elsevier'))
    ap.add_argument('--refresh', action='store_true', help='已有 全文.md 的也重新抓（同名文件覆盖）')
    ap.add_argument('--retry', action='store_true', help='台账里没有全文的、失败满 %d 次的也再试' % fp.MAX_ATTEMPTS)
    ap.add_argument('--interval', type=float, default=1.0, help='两篇之间至少间隔的秒数（默认 1）')
    ap.add_argument('--limit', type=int, default=0, help='这次最多抓多少篇（0 = 不限）')
    ap.add_argument('--status', action='store_true', help='只看台账进度')
    a = ap.parse_args()
    fp.LEDGER_NAME = LEDGER_NAME
    if a.status:
        led = fp.Ledger(a.dir) if a.dir else ListLedger([a.list])
        led.scan()
        led.report()
        return
    api_key()
    os.makedirs(a.out, exist_ok=True)
    led = None
    if a.items:
        todo = [(fp.item_key(x), x) for x in a.items]
    else:
        led = fp.Ledger(a.dir) if a.dir else ListLedger([a.list])
        files, new = led.scan()
        todo = led.pending(a.retry)
        if a.retry:                                 # 重试时先抓能补回来的；上次只给纯文本的（撤稿、扫描版，重试多半还是没有）放最后
            why = dict(led.db.execute("SELECT key, reason FROM papers WHERE status = 'no_fulltext'"))
            todo.sort(key=lambda t: '纯文本' in (why.get(t[0]) or ''))
        print('DOI 清单：%s；台账：%s' % (a.dir or a.list, os.path.join(led.folder, LEDGER_NAME)), flush=True)
        if not a.refresh:                           # 保存位置里已经有 全文.md 的（网页版或之前抓过的）：一次记成已有，不调 API
            have = [(k, it) for k, it in todo if saved(it, a.out)]
            if have:
                with led.db:
                    led.db.executemany(
                        'INSERT INTO papers (key, status, reason, folder, attempts, updated) VALUES (?, ?, ?, ?, 1, ?) '
                        'ON CONFLICT (key) DO UPDATE SET status = excluded.status, reason = excluded.reason, '
                        'folder = excluded.folder, updated = excluded.updated',
                        [(k, 'done', '已有（保存位置里已经有 全文.md）', saved(it, a.out), time.strftime('%Y-%m-%d %H:%M:%S'))
                         for k, it in have])
                done_keys = {k for k, _ in have}
                todo = [(k, it) for k, it in todo if k not in done_keys]
            print('  其中 %d 篇 %s 里已经有了，跳过' % (len(have), a.out), flush=True)
        print('  这次要抓 %d 篇' % len(todo), flush=True)
    if a.limit:
        todo = todo[:a.limit]
    print('保存到：%s' % a.out, flush=True)
    tally, last = {}, 0.0
    try:
        for i, (key, item) in enumerate(todo, 1):
            print('\n=== [%d/%d] %s ===' % (i, len(todo), item), flush=True)
            if led and not led.claim(key):
                print('  另一份正在抓这篇，或这一轮里已经抓过了：跳过', flush=True)
                continue
            time.sleep(max(0.0, a.interval - (time.time() - last)))
            last = time.time()
            try:
                status, folder, reason = fetch_one(item, a)
            except NoFullText as e:
                status, folder, reason = 'no_fulltext', '', str(e)
            except Fatal:
                raise
            except Exception as e:
                status, folder, reason = 'failed', '', '%s: %s' % (type(e).__name__, str(e)[:200])
            if status != 'done':
                print('  ✗ %s：%s' % ({'no_fulltext': '没有全文', 'not_elsevier': '不是 Elsevier', 'invalid': 'DOI 无效',
                                       'failed': '失败'}[status], reason), flush=True)
            tally[status] = tally.get(status, 0) + 1
            if led:
                led.record(key, status, reason, folder)
                led.unclaim(key)
    finally:
        if led:
            led.unclaim()
    print('\n==== 这次汇总：%d 篇 ====' % sum(tally.values()))
    names = {'done': '完成', 'no_fulltext': '没有全文', 'not_elsevier': '不是 Elsevier', 'invalid': 'DOI 无效', 'failed': '失败'}
    print('  ' + '，'.join('%s %d' % (names[k], v) for k, v in tally.items()))


if __name__ == '__main__':
    try:
        main()
    except Fatal as e:
        print('\n停下：%s' % e, flush=True)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\n已停止（已抓的都记在台账里，重跑同一条命令接着来）', flush=True)
        sys.exit(130)
