#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
fetch_papers.py（通用版）—— 论文 DOI 链接 → 网页全文原样 markdown + 图片 + 图片版表格 + 图注。
各出版商、Chrome / Edge、Windows / macOS 都用这一个脚本。

    python fetch_papers.py                    # 跑 do list 文件夹里所有 .md（台账 进度.db 也在里面）
    python fetch_papers.py --status           # 只看进度：每个文件 完成 / 没有全文 / 失败 / 未读 各多少
    python fetch_papers.py --retry            # 没有全文的、失败满 3 次的也再试
    python fetch_papers.py https://doi.org/10.1021/acs.jafc.5c12346 10.1016/j.indcrop.2026.124008 [更多 DOI ...]
    python fetch_papers.py --file doi_lists\Wiley.md

文件夹里三样东西（整个文件夹挪到哪儿、挪到 Mac 上都能用）：
    fetch_papers.py      这个脚本
    do list\             放 DOI 列表（.md，可以有子文件夹）；台账 进度.db 也在这里
    <出版商>_papers\     抓好的文献，按出版商分开：acs_papers、wiley_papers、mdpi_papers …（用到时才建）；
                         本机（Windows）有专门读法的八家放 D 盘八个总文件夹的 papers 子文件夹（PAPERS_DIRS 里改，见下）

由 chrome_elsevier / edge_elsevier / chrome_acs / edge_acs / chrome_wiley / edge_wiley 六个脚本合成（它们照旧留着，
不受影响）。抓取的流程、核对、台账和每篇的成品文件都和它们一样，只是下面三件事不用你再选：

  出版商自动认：DOI 经 doi.org 解析出的网址是哪家的，就用哪家的读法（原来各脚本里专门写的那一套），存到那家的文件夹：
      Elsevier（ScienceDirect）→ D:\2.elsevier_papers\papers（同原来的 chrome_elsevier.py）
      ACS（pubs.acs.org）→ D:\1.acs_papers_done\papers
      Wiley（Wiley Online Library，含 hindawi.com、doi.wiley.com 转过去的）→ D:\3.wiley_papers-part\papers
      RSC（pubs.rsc.org）→ D:\4.RSC_papers\papers      MDPI → D:\5.MDPI_papers\papers
      Oxford University Press（academic.oup.com）→ D:\6.oxford_papers\papers
      Taylor & Francis（tandfonline.com）→ D:\7.Taylor_papers\papers
      Springer Nature（link.springer.com、nature.com、BMC）→ D:\8.Springer nature_papers\papers
      （总文件夹的结构同 D:\1.acs_papers_done：papers\<文章>、_records\、database\，后两个由 Papers_treatment_pipeline 写）
      （Mac 上和别的出版商一样放脚本旁边：elsevier_papers、acs_papers、wiley_papers、rsc_papers、mdpi_papers、oxford_papers、
      taylor_francis_papers、springer_nature_papers）
    这五家是 2026-10-22 新写的专门读法（没有原来的脚本可对照）。还没有专门读法的出版商用通用读法，存到
    <出版商>_papers，台账里记为完成、但带提醒「通用读法」，方便以后挑出来核对；不想抓这些加 --only-known
    （不开浏览器，记为「没有专门读法」）。
    已经抓好的文献原地不动；挪到别处的（OLD_PAPERS，如 D:\acs_papers）也算抓过，不再抓。
    只抓某一家加 --publisher elsevier / acs / wiley / springer_nature / mdpi / oxford / rsc / taylor_francis
    （别家的不开浏览器，记为「不是 X」，同原来的脚本）。
    以后加出版商：在下面「出版商」一节照 Elsevier / ACS / Wiley 的样子写一个类，登记进 PUBLISHERS。

  浏览器自动选：Chrome、Edge 哪个闲着用哪个。正在被别的抓取脚本用着的浏览器不碰（这个脚本的另一份，原来的
    chrome_*.py / edge_*.py，补上下标.py 都算）；两个都被占着就停下说明。已经开着、连着 opencli 的优先。
    --browser chrome / edge 指定。每个浏览器只用它自己的 opencli 扩展实例（opencli profile list 里的编号，
    本机 Chrome 是 4d9tax8p、Edge 是 a59pjt42），每条 opencli 浏览器命令都带上编号，不改 opencli 的全局默认。
    别的电脑上编号不同：浏览器里只连着一个没认领的扩展实例时自动用它；每次接管都核对页面报的浏览器标识
    （Edge 带 Edg/），对不上就记下这个编号是另一个浏览器的、自动重新开始换一个，所以不会在别的浏览器里抓。
    认不出来时用 --profile 指定。
    同一个 DOI 列表可以同时开两份（再开一个终端跑同一条命令：一份用 Chrome、一份用 Edge）：每篇开抓前先在台账里
    登记，两份不会抓同一篇。

  Windows、macOS 都能跑：切换 / 关闭标签页在 Windows 上用 UI Automation（PowerShell），在 macOS 上用 AppleScript
    （osascript；第一次运行时 macOS 会问「终端」能不能控制 Chrome / Edge，点「好」）。macOS 上打开、关掉标签页
    都不让浏览器跳到前面。

DOI 列表文件夹 do list：里面的 .md 文件（可以有子文件夹）只读不改，同一个 DOI 在几个文件里出现只抓一次。每个 DOI
的状态记在同一文件夹的 进度.db（台账）里，每篇跑完立刻记下：完成、没有全文、DOI 无效的不再抓；失败的下次运行再试，
最多 3 次（--retry 连没有全文的一起再试）。台账记为完成的就不再抓，即使你后来把保存的文件夹删了或移走了。以后往文件夹
里加新文件，重跑同一条命令就会接上。--dir 换一个 DOI 列表文件夹（比如接着跑原来脚本的 opencli_fetch\doi list\chrome_elsevier，
台账照样用）。

每篇文献一个文件夹 <出版商>_papers\<DOI，斜杠换成下划线>\ （和原来的脚本一样）：
    全文.md              opencli extract 读到的网页全文，原样保存，不做任何清洗、整理或改动；
                         只有网页里的 HTML 表格按原表的行、列、合并格重建成 markdown 表格，放在原位
                         （opencli 自己转会把每格拆成单独一行）；ACS 每张图在页面里藏着的「点开放大」弹窗副本、
                         Wiley 页面里藏着的手机版作者列表（页面上都不显示，opencli 会再读一遍）去掉。除此以外的
                         文字和 opencli extract 逐字一致，每篇都核对，对不上就整篇按 opencli 原样保存并提醒。
                         ACS 读文章区（Silverchair 的 ArticleMainView），其余读 opencli 的默认范围。
                         新写的五家另有几处（见各自的类）：表格不在正文原位的放回原位（Springer 的「Full size
                         table」表格页、T&F 页面里按需显示的表、MDPI 放在页面最后弹窗里的表），页面上不显示的
                         重复块、正文中间的推荐文章栏去掉；其余同样逐字核对。
                         上下标：opencli 转 markdown 时会把 <sub>/<sup> 压平（Ca2+、8.0 × 1010），这里照流水线的
                         规则写成纯文本：Ca²⁺、10¹⁰、CaCl₂、s⁻¹，带字母的写成 T_c、N_{agg}；上标里只是引文链接的
                         照原样。公式（opencli 原本读不到或压平）照流水线写成一行：分式 (分子)/分母，单独成行的
                         自成一段、编号放在末尾。核对时先去掉上下标和公式再比。
                         参考文献不要：从最后一个参考文献标题起到文件末尾整段去掉（后面网页附带的推荐文章、被引、
                         统计一并去掉）；正文里的引用链接不动。--keep-refs 保留。
    figure\              图片和图注单独放在这个子文件夹里：
        fig1.jpg …           论文里的图（出版商给的最高分辨率原图，按下载到的原字节保存）
        graphical_abstract…  图文摘要（有的话）
        table4.jpg …         图片版表格（页面上是图片、没有 <table> 的表）
        figure_markdown.md   每张图 / 图片版表格的图注（页面上显示的原文）和对应的本地图片

流程（参考 paper_pipeline/fetch.py 的「打开 → 切换 → opencli 接管 → 抓取」）：
    1. DOI 经 doi.org 解析出出版商地址，认出是哪家
    2. 用选好的浏览器正常打开这个地址（和你手动打开一样，不走 opencli 的自动化打开，免得被人机验证拦下）
    3. opencli bind 接管这个标签页；它不在前台时切过去（只切这家的文章页或验证页）
    4. 等加载完、滚动一遍触发懒加载，opencli extract 读出全文
    5. 表格：用 opencli extract 自己的网页脚本和 markdown 转换器再转一遍，只是先在它复制出的页面副本里
       把每张 <table> 换成占位标记、读出行列结构（网页本身不改），转完把重建的表格填回占位处
    6. 在同一页面上读出图和图片版表格的地址与图注，下载原图（Wiley 的图由浏览器在页面里下载：脚本自己请求
       Wiley 会被 Cloudflare 拦下）

批量时：
    - 已经存过（这家的文件夹里有 全文.md）的跳过，所以中途停下后重跑同一条命令就接着来
    - 没有全文（没有权限、只有摘要、一直没加载出来）的直接跳过，不问你，汇总里单独列出（--ask 改为问你）
    - 网页打不开或显示报错（404、服务器错误、无法访问、Access denied 等）不等，直接跳过；打开 90 秒还没显示
      文章、也不是验证页，同样跳过（--load-timeout）。这些台账里记为失败，下次运行再试；人机验证页照旧等你完成（--wait）
    - 一次只开一篇：读完（成功、没有全文、失败、出错或中断都一样）立刻关掉这篇打开的那个标签页（按打开时
      记下的标签页编号认，不看标题），再读一遍标签栏确认关掉了，才开下一篇；确认不了就整批停下。
      你自己原来开着的标签页不会碰。--keep-tabs 不关
    - 中途停下也不留标签页：按 Ctrl+C 会先关掉正在处理的那篇再退出；直接关掉终端窗口时抢着先关掉它；
      万一来不及（比如在任务管理器里结束进程），下次启动时先把上次留下的那个关掉
    - 单篇失败（报错、打不开、没有全文等）不停，接着跑下一篇，直到列表里每篇都试过一次
      （--max-fails N：连续 N 篇失败就停）
    - 因故障停下（opencli 和浏览器断开、后台服务出问题、预检没过、标签页没能确认关掉、脚本意外出错）会自动
      重新开始：等 30 秒起、最长 5 分钟，重新预检，已试过的不重复，被打断的那篇重新抓；按 Ctrl+C 才真正停
    - 两篇之间默认隔 1 秒（--interval）
    - 不抢你的键盘：Windows 上打开网页、切换或关掉标签页时浏览器会跳到最前，脚本马上把焦点还给你原来在用的
      窗口（浏览器会闪一下）；你本来就在这个浏览器里时不动

全程不调用任何大模型。人机验证、机构登录都由你在浏览器里自己完成，脚本只等待，不代做。
只用 Python 标准库（3.8 及以上）；需要 Windows 或 macOS、Chrome 或 Edge、Node.js、opencli（npm 版）和装在浏览器里的
opencli 扩展。
"""
import argparse
import base64
import difflib
import glob
import html
import io
import itertools
import json
import os
import pathlib
import re
import shutil
import signal
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

IS_WIN = os.name == 'nt'
IS_MAC = sys.platform == 'darwin'
HERE = os.path.dirname(os.path.abspath(__file__))   # 总文件夹：脚本、do list、抓到的文献都在里面，整个挪走也能用
SCRIPT = os.path.basename(os.path.abspath(__file__))
FIGURE_DIR = 'figure'               # 每篇文件夹里放图片和 figure_markdown.md 的子文件夹
DOI_DIR = os.path.join(HERE, 'do list')   # 放 DOI 列表（.md）的文件夹，台账 进度.db 也在这里
# 抓好的文献按出版商分开放：默认是脚本旁边的 <出版商>_papers（elsevier_papers、acs_papers、wiley_papers、mdpi_papers …）。
# 本机有专门读法的八家放 D 盘（用户 2026-10-15 先挪了 Elsevier；10-30 八家都整理成 D 盘的 1.–8. 总文件夹，「改 抓取脚本以都默认
# 放这几个文件夹里」「2-8编号的文件夹 … 应该得到和D:\1.acs_papers_done 一样的结构」）：文章都放总文件夹的 papers 子文件夹；
# 只在 Windows 上用，Mac 上照默认。
PAPERS_DIRS = {'acs': r'D:\1.acs_papers_done\papers', 'elsevier': r'D:\2.elsevier_papers\papers',
               'wiley': r'D:\3.wiley_papers-part\papers', 'rsc': r'D:\4.RSC_papers\papers', 'mdpi': r'D:\5.MDPI_papers\papers',
               'oxford': r'D:\6.oxford_papers\papers', 'taylor_francis': r'D:\7.Taylor_papers\papers',
               'springer_nature': r'D:\8.Springer nature_papers\papers'}
# 以前抓好的文献还在别处的：原地不动，这里已经有的（文件夹里有 全文.md）不再抓。没有的位置自动忽略。
# 2–8 号总文件夹本身也算：流水线把直接放在里面的文章挪进 papers 之前，那里的也不重抓（用户 2026-10-30）
OLD_PAPERS = (r'D:\acs_papers',) + tuple(os.path.dirname(d) for k, d in sorted(PAPERS_DIRS.items()) if k != 'acs')

# ============================== 浏览器 ==============================
# opencli：本机两个浏览器里 opencli 扩展的实例编号（opencli profile list 可查）。别的电脑上编号不同，不用改这里：
# 只连着一个没认领的实例时自动用它，接管时核对浏览器标识，认错了自动记下换一个（记在系统临时文件夹的 PROFILE_FILE）。
BROWSERS = {
    'chrome': {'name': 'Chrome', 'opencli': '4d9tax8p', 'profile_dir': 'Default',
               'exe': 'chrome.exe', 'proc': 'chrome', 'tab': 'Tab', 'close': 'TabCloseButton',
               'win_paths': (r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                             r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                             os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application',
                                          'chrome.exe')),
               'mac_app': 'Google Chrome', 'bundle': 'com.google.Chrome',
               'ua': 'Mozilla/5.0 (%s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36'},
    'edge': {'name': 'Edge', 'opencli': 'a59pjt42', 'profile_dir': 'Default',
             'exe': 'msedge.exe', 'proc': 'msedge', 'tab': 'EdgeTab', 'close': 'EdgeTabCloseButton',
             'win_paths': (r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                           r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
                           os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Edge', 'Application',
                                        'msedge.exe')),
             'mac_app': 'Microsoft Edge', 'bundle': 'com.microsoft.edgemac',
             # 下载图片时报的浏览器标识：Edge 的标准标识里本来就带 Chrome 字样，结尾的 Edg/ 才表示 Edge
             'ua': ('Mozilla/5.0 (%s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 '
                    'Safari/537.36 Edg/147.0.0.0')},
}
UA_OS = 'Macintosh; Intel Mac OS X 10_15_7' if IS_MAC else 'Windows NT 10.0; Win64; x64'
B = {}                              # 这次用的浏览器：上面的一项，再加 key（chrome / edge）和 profile（opencli 扩展实例编号）
PROFILE_FILE = os.path.join(tempfile.gettempdir(), 'opencli_fetch_profiles.json')   # 认出来的 {扩展实例编号: 浏览器}
# 原来的单出版商脚本（还在跑的话，它用的浏览器不碰）：chrome_elsevier.py、edge_acs.py、补上下标.py chrome_wiley …
LEGACY = (re.compile(r'(?:^|[\\/\s"\'])(chrome|edge)_(?:elsevier|acs|wiley)(?:_mac)?\.py\b', re.I),
          re.compile(r'补上下标\.py["\']?\s+["\']?(chrome|edge)_', re.I))
# ====================================================================

APPDATA = os.environ.get('APPDATA', '')
# npm 版 opencli 的入口脚本：用 node 直接跑，网页脚本里的引号原样传到 opencli；
# 经 opencli.cmd 会过 cmd.exe，带引号的参数会被截断（2026-09-24 踩过）。
OPENCLI_CMD = os.path.join(APPDATA, 'npm', 'opencli.cmd')


def find_opencli_main():
    """npm 全局装的 opencli 的入口脚本 dist/src/main.js。Windows 上在 %APPDATA%\\npm 下；macOS 上命令 opencli 是
    指向它的链接，找不到再问 npm 装在哪（Homebrew、nvm、官方安装包装的 node，全局包的位置各不一样）。"""
    if IS_WIN:
        return os.path.join(APPDATA, 'npm', 'node_modules', '@jackwener', 'opencli', 'dist', 'src', 'main.js')
    exe = shutil.which('opencli')
    if exe:
        real = os.path.realpath(exe)
        if real.endswith('.js') and os.path.exists(real):
            return real
    npm = shutil.which('npm')
    if npm:
        try:
            root = subprocess.run([npm, 'root', '-g'], capture_output=True, text=True, timeout=60).stdout.strip()
            main_js = os.path.join(root, '@jackwener', 'opencli', 'dist', 'src', 'main.js')
            if root and os.path.exists(main_js):
                return main_js
        except (OSError, subprocess.TimeoutExpired):
            pass
    return ''


OPENCLI_MAIN = find_opencli_main()

ACTION = '【需要你操作】'
CHALLENGE = ('are you a robot', 'just a moment', '请稍候', 'checking your browser',
             'enable javascript and cookies', 'unusual traffic')
# 网页报错的样子（页面上几乎没有文字时才看标题和开头）：看到就不等了，直接跳过这篇
ERROR_SIGNS = ('page not found', '404 not found', 'error 404', '403 forbidden', 'access denied', 'bad gateway',
               'service unavailable', 'gateway timeout', 'internal server error', 'error 1020', 'error 1015',
               'problem providing the content', 'this site can’t be reached', "this site can't be reached",
               'can’t reach this page', "can't reach this page", 'this page isn’t working',
               "this page isn't working", '无法访问此网站', '无法访问此页面', '无法正常运作', '找不到页面', '页面不存在')
LOAD_TIMEOUT = 90           # 秒：打开后这么久还没显示文章、也不是验证页，就当打不开或报错，跳过（--load-timeout）
BLANK_TITLES = ('', '新标签页', '新建标签页', 'new tab', 'about:blank')
UNTITLED = ('无标题', 'untitled')     # 新标签页刚出现、网页还没给出标题时的样子（实测 Edge 约 1 秒）
MIN_PAGE_CHARS = 3000       # 低于这个数的页面不是文章（验证页、跳转页、空白页）
MIN_BODY_CHARS = 12000      # 低于这个数又没有参考文献标题：页面没加载完（ScienceDirect 半渲染时只有 Highlights + Abstract）
PAYWALL_CHARS = 30000       # 没有全文权限的 ScienceDirect 页面约 1.9–2 万字符
CHUNK = 200000              # opencli extract 单段上限：一篇通常一次读完

# 下面几句提示里的 {b} 换成这次用的浏览器（Chrome / Edge）
VERIFY_PROMPT = (ACTION + '%s 的标签页停在人机验证或还没显示全文。如有验证，请你在这个标签页里完成'
                 '（脚本不会代做）；页面显示全文后脚本自动接着抓。')
NOT_FOUND_PROMPT = (ACTION + '{b} 里没找到这篇的标签页：%s 。请在 {b} 里打开它（不用切换，脚本会自己切过去）。')
SWITCH_PROMPT = ACTION + '请在 {b} 里切到这篇的标签页：%s （脚本等你切过去后自动接管）。'
FOCUS_PROMPT = (ACTION + '脚本没能把文章所在的 {b} 窗口切到前面（Windows 有时不让后台程序这样做）。'
                '请点一下那个 {b} 窗口，脚本会接着接管。')
TAKEN_NOTE = '  已接管标签页。读完之前请不要在 {b} 里切换、关闭或刷新它（大约半分钟）。'
TRANSLATED_PROMPT = (ACTION + '%s 的页面被 {b} 自动翻译了，脚本不读译文。请在这个标签页点地址栏右边的翻译图标，'
                     '选「显示原文」；页面恢复原文后脚本接着抓，最多等 %g 分钟。')


def bn(text):
    """提示里的 {b} 换成这次用的浏览器。"""
    return text.replace('{b}', B.get('name') or '浏览器')


class Stop(Exception):
    """这一篇停下：原因给你看，接着处理下一篇。"""


class PageError(Stop):
    """网页打不开或显示报错：不等了，跳过这篇（台账记为失败，下次运行再试）。"""


class NoFullText(Stop):
    """页面上没有全文（没有权限或一直没加载出来）：跳过这篇，汇总里单独列出。"""

    def __init__(self, reason, title=''):
        super().__init__(reason)
        self.title = title


class InvalidDoi(Stop):
    """doi.org 查不到：不再重试。"""


class Skipped(Stop):
    """不开浏览器就跳过、不再重试：不是 --publisher 指定的那家（status 如 not_elsevier），或者 --only-known 时
    这家还没有专门读法（status unsupported）。"""

    def __init__(self, status, reason):
        super().__init__(reason)
        self.status = status


class Fatal(SystemExit):
    """设置上的问题（找不到浏览器、DOI 列表文件夹不存在）：自动重新开始也没用，直接停。"""


class Restart(Exception):
    """这一轮因故障停下（opencli 和浏览器断开、标签页没能确认关掉、接管到的不是选好的浏览器…）：等一会儿自动重新开始。"""


# 这次运行（含自动重新开始之前）已经试过的 DOI：重新开始时不重复；progress 用来判断这一轮有没有进展
SESSION = {'tried': set(), 'progress': 0}


class NotReady(Exception):
    """接管了，但页面这会儿不能读（验证页、被翻译）：放开标签页，稍后重新接管。"""


# ------------------------------------------------------------------ opencli --
def opencli_command():
    """npm 装的 opencli：node + 入口脚本，找不到 node 时用 npm 的 opencli.cmd（Windows），都没有才靠 PATH。"""
    node = shutil.which('node')
    if node and OPENCLI_MAIN and os.path.exists(OPENCLI_MAIN):
        return [node, OPENCLI_MAIN]
    return [OPENCLI_CMD if IS_WIN and os.path.exists(OPENCLI_CMD) else 'opencli']


def cli(*args, timeout=180):
    if args and args[0] == 'browser' and B.get('profile'):
        # 浏览器命令都发给选好的那个浏览器里的扩展实例，不动 opencli 的全局默认（别的脚本可能在用）
        args = ('--profile', B['profile']) + tuple(args)
    try:
        p = subprocess.run([*opencli_command(), *args], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError('opencli %s 超时（%d 秒）' % (' '.join(args[:3]), timeout))
    except FileNotFoundError:
        raise Fatal('找不到 opencli：请先装 Node.js（20.18.1 以上），再在终端里运行 npm install -g @jackwener/opencli@1.8.8')
    if p.returncode != 0:
        raise RuntimeError('opencli %s 失败：%s' % (' '.join(args[:3]),
                                                   ((p.stderr or '') + (p.stdout or '')).strip()[-400:]))
    return p.stdout


def parse_json(out):
    out = (out or '').strip()
    try:
        return json.loads(out)
    except ValueError:
        pass
    i, j = out.find('{'), out.rfind('}')           # 有时 JSON 前面多一行提示
    if 0 <= i < j:
        try:
            return json.loads(out[i:j + 1])
        except ValueError:
            pass
    raise RuntimeError('opencli 没有返回 JSON：%s' % out[:300])


def cli_json(*args, timeout=180):
    return parse_json(cli(*args, timeout=timeout))


def page_eval(session, js, timeout=90):
    """在页面里跑一段脚本。opencli 把字符串原样打印、其他值打印成 JSON。"""
    out = cli('browser', session, 'eval', js, timeout=timeout).strip()
    try:
        return json.loads(out)
    except ValueError:
        return out


_SEQ = itertools.count(1)


def new_session():
    # 每次都用新名字：刚绑定又放开的名字不能再绑
    return 'raw%d%03d' % (time.time_ns() // 1000000 % 10 ** 9, next(_SEQ) % 1000)


def release(session):
    """放开标签页（unbind）：标签页留在浏览器里，不关闭。"""
    if not session:
        return
    try:
        cli('browser', session, 'unbind', timeout=30)
    except Exception:
        pass


def connected_profiles():
    """opencli profile list 里「已连接」那一段的扩展实例编号（每个开着、扩展启用的浏览器配置一个）。"""
    out = cli('profile', 'list', timeout=30)
    connected = re.split(r'(?im)^\s*Disconnected', out)[0]
    return re.findall(r'(?m)^[ \t]+(\S+)[^\n]*\bconnected\b', connected)


def profile_connected(profile):
    try:
        return profile in connected_profiles()
    except RuntimeError:
        return False


def preflight():
    """opencli 后台服务和命令行版本不一致就重启它（OpenCLIApp 会拉起旧版），然后等选好的浏览器里的扩展连上。"""
    ver = re.sub(r'[^\d.]', '', cli('--version', timeout=60).strip())
    try:
        status = cli('daemon', 'status', timeout=30)
    except RuntimeError as e:
        status = str(e)
    m = re.search(r'Version:\s*v?([\d.]+)', status)
    if not m or m.group(1) != ver:
        print('  opencli 后台服务（%s）和命令行（v%s）对不上，重启后台服务'
              % ('v' + m.group(1) if m else '没在运行', ver), flush=True)
        cli('daemon', 'restart', timeout=90)
    started, deadline = False, time.time() + 45
    while True:
        try:
            doctor = cli('doctor', timeout=60)
        except RuntimeError as e:
            doctor = str(e)
        if re.search(r'\[OK\]\s*Extension: connected', doctor):
            if not B.get('profile'):
                B['profile'] = unclaimed_profile(B['key'])
                if B['profile']:
                    write_lock(B['key'])
            if B.get('profile') and profile_connected(B['profile']):
                print('  opencli 就绪（v%s，%s 里的扩展实例 %s）' % (ver, B['name'], B['profile']), flush=True)
                return
        if time.time() > deadline:
            raise SystemExit('opencli 的 %s 扩展没有连上。请确认 %s 开着、OpenCLI 扩展已启用、「OpenCLI 已开始调试此浏览器」'
                             '横幅没有被点掉，然后重跑（opencli profile list 可以看扩展实例的编号，--profile 指定）。'
                             % (B['name'], B['name']))
        if not started and not browser_running(B['key']) and browser_app(B['key']):
            print('  %s 没开，先打开 %s' % (B['name'], B['name']), flush=True)
            launch_browser()
            started = True
        time.sleep(1.5)


def bridge_ok():
    """opencli 后台服务和浏览器扩展还连着吗。出了说不清的错时查一下：断了就整个自动重新开始（会先预检），
    这篇不记成失败、之后重新抓。"""
    try:
        doctor = cli('doctor', timeout=60)
    except RuntimeError:
        return False
    return bool(re.search(r'\[OK\]\s*Extension: connected', doctor)) and profile_connected(B.get('profile'))


# ------------------------------------------------------------ 选浏览器 --
# 哪个浏览器正被别的抓取脚本用着：原来的单出版商脚本看进程的命令行；这个脚本的每一份在系统临时文件夹里放一个
# 锁文件 opencli_fetch_<浏览器>.lock（写着进程号和扩展实例编号），进程结束了锁就作废。
def scan_processes():
    """{进程号: 命令行}，只看 Python 进程；看不出来返回 {}。"""
    procs = {}
    try:
        if IS_WIN:
            ps = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'WindowsPowerShell', 'v1.0',
                              'powershell.exe')
            cmd = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; Get-CimInstance Win32_Process | "
                   "Where-Object { $_.Name -like 'py*' } | ForEach-Object { [string]$_.ProcessId + [char]9 + $_.CommandLine }")
            out = subprocess.run([ps, '-NoProfile', '-NonInteractive', '-Command', cmd], capture_output=True, timeout=60,
                                 stdin=subprocess.DEVNULL,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout.decode('utf-8', 'replace')
            rows = (line.split('\t', 1) for line in out.splitlines() if '\t' in line)
        else:
            out = subprocess.run(['ps', '-axww', '-o', 'pid=,command='], capture_output=True, text=True,
                                 errors='replace', timeout=30).stdout
            rows = (line.strip().split(None, 1) for line in out.splitlines() if line.strip())
        for row in rows:
            if len(row) == 2 and row[0].strip().isdigit():
                procs[int(row[0])] = row[1].strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return procs


def pid_alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if IS_WIN:
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL('kernel32')
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k.GetExitCodeProcess.restype = wintypes.BOOL
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        h = k.OpenProcess(0x1000, False, pid)              # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = wintypes.DWORD()
            return bool(k.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259   # STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def lock_path(key):
    return os.path.join(tempfile.gettempdir(), 'opencli_fetch_%s.lock' % key)


def read_lock(key):
    """锁文件的内容；没有锁返回 None。刚建好、还没写进内容的（10 秒内）当作有人占着：{'pid': None, 'new': True}。"""
    path = lock_path(key)
    try:
        with io.open(path, encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except ValueError:
        try:
            return {'pid': None, 'new': True} if time.time() - os.path.getmtime(path) < 10 else {}
        except OSError:
            return None
    except OSError:
        return None


def lock_alive(lock, procs):
    """锁文件还算数吗：写它的进程还在，而且（看得到命令行时）确实是这个脚本。刚启动、扫进程时还没出现的也算还在。"""
    if lock.get('new'):
        return True
    pid = lock.get('pid')
    if not pid_alive(pid):
        return False
    cmd = procs.get(int(pid))
    return cmd is None or SCRIPT in cmd


def busy_browsers(procs):
    """{浏览器: 谁在用}：原来的单出版商脚本、这个脚本的另一份。"""
    busy = {}
    for pid, cmd in procs.items():
        if pid == os.getpid():
            continue
        for pattern in LEGACY:
            m = pattern.search(cmd)
            if m:
                busy.setdefault(m.group(1).lower(), '原来的脚本在用（进程 %d：%s）'
                                % (pid, os.path.basename(cmd.split('.py')[0].strip('"\' ')) + '.py'))
    for key in BROWSERS:
        lock = read_lock(key)
        if lock and lock.get('pid') != os.getpid() and lock_alive(lock, procs):
            busy.setdefault(key, '这个脚本的另一份在用（进程 %s）' % lock.get('pid'))
    return busy


def learned_profiles():
    try:
        with io.open(PROFILE_FILE, encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def learn_profile(profile, key):
    """记下这个扩展实例是哪个浏览器的（接管时核对浏览器标识认出来的）。"""
    data = learned_profiles()
    if profile and data.get(profile) != key:
        data[profile] = key
        try:
            tmp = '%s.%d' % (PROFILE_FILE, os.getpid())
            with io.open(tmp, 'w', encoding='utf-8') as fh:
                json.dump(data, fh)
            os.replace(tmp, PROFILE_FILE)
        except OSError:
            pass


def known_profile(key, connected):
    """这个浏览器的扩展实例编号：认出来过的 > 上面 BROWSERS 里写的（没被认成别的浏览器的）。连着的优先。"""
    learned = learned_profiles()
    mine = [p for p, k in learned.items() if k == key]
    configured = BROWSERS[key]['opencli']
    if configured and learned.get(configured, key) == key and configured not in mine:
        mine.append(configured)
    return next((p for p in mine if p in connected), mine[0] if mine else None)


def unclaimed_profile(key, connected=None):
    """连着、但还认不出是哪个浏览器的扩展实例只有一个时，先当作是 key 的（接管时核对浏览器标识）。"""
    if connected is None:
        try:
            connected = connected_profiles()
        except RuntimeError:
            return None
    learned = learned_profiles()
    taken = {(read_lock(k) or {}).get('profile') for k in BROWSERS if k != key}
    others = {BROWSERS[k]['opencli'] for k in BROWSERS if k != key}
    free = [p for p in connected if learned.get(p, key) == key and p not in taken
            and (p not in others or learned.get(p) == key)]
    return free[0] if len(free) == 1 else None


def lock_text(profile):
    return json.dumps({'pid': os.getpid(), 'profile': profile, 'script': SCRIPT,
                       'since': time.strftime('%Y-%m-%d %H:%M:%S')})


def write_lock(key):
    """锁文件里补上认出来的扩展实例编号。"""
    with io.open(lock_path(key), 'w', encoding='utf-8') as fh:
        fh.write(lock_text(B.get('profile')))


def take_lock(key, procs, profile=None):
    """占上这个浏览器：建锁文件并马上写进进程号（同时启动的两份只有一份建得成）。别人占着返回 False。"""
    for _ in range(2):
        try:
            fd = os.open(lock_path(key), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            old = read_lock(key)
            if old is None:                         # 刚被删掉：再建一次
                continue
            if old.get('pid') != os.getpid() and lock_alive(old, procs):
                return False
            if read_lock(key) == old:               # 上次没删掉的旧锁（进程已经不在了）；删之前再看一眼没被换掉
                try:
                    os.remove(lock_path(key))
                except OSError:
                    pass
            continue
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(lock_text(profile))
        return True
    return False


def release_lock():
    key = B.get('key')
    if key and (read_lock(key) or {}).get('pid') == os.getpid():
        try:
            os.remove(lock_path(key))
        except OSError:
            pass


def choose_browser(a, keep=False):
    """选浏览器：没被别的抓取脚本占着、装了的；已经连着 opencli 的优先（不用新开浏览器）。占上后写进 B。
    keep=False（--which-browser）只看不占。"""
    procs = scan_processes()
    busy = busy_browsers(procs)
    try:
        connected = connected_profiles()
    except (RuntimeError, SystemExit):
        connected = []
    order = [a.browser] if a.browser in BROWSERS else list(BROWSERS)
    notes, plans = [], []
    for key in order:
        name = BROWSERS[key]['name']
        if not browser_app(key):
            notes.append('%s 没装' % name)
            continue
        if key in busy:
            notes.append('%s：%s' % (name, busy[key]))
            continue
        profile = a.profile or known_profile(key, connected)
        if not profile or profile not in connected:
            profile = unclaimed_profile(key, connected) or profile
        plans.append((profile in connected, key, profile))
    plans.sort(key=lambda p: not p[0])              # 已经连着 opencli 的优先
    for live, key, profile in plans:
        if not keep:
            print('浏览器：会用 %s（opencli 扩展实例 %s，%s）' % (BROWSERS[key]['name'], profile or '待认',
                                                     '已连着' if live else '还没连上，预检时打开它'))
            if notes:
                print('  另一个浏览器：%s' % '；'.join(notes))
            return key
        if take_lock(key, procs, profile):
            B.clear()
            B.update(BROWSERS[key], key=key, profile=profile)
            path = browser_app(key)
            print('浏览器：%s（%s）｜opencli 扩展实例：%s%s' % (B['name'], path, profile or '待认（连上后自动认）',
                                                     '' if live else '（还没连上，预检时打开它）'), flush=True)
            if notes:
                print('  没用的：%s' % '；'.join(notes), flush=True)
            return key
        notes.append('%s：刚被另一个抓取脚本占上' % BROWSERS[key]['name'])
    raise Fatal('没有空闲的浏览器可用：%s。等那边跑完再开（一个浏览器同时只跑一个抓取脚本）。'
                % ('；'.join(notes) or '一个都没找到'))


def check_browser(session, state):
    """接管到的必须是选好的浏览器：页面报的浏览器标识里，Edge 带 Edg/，Chrome 不带。对不上（这个扩展实例是另一个
    浏览器的）就记下、放开标签页，整个自动重新开始换一个，绝不在别的浏览器里抓。"""
    if 'edge' not in state:
        return
    is_edge = bool(state.get('edge'))
    if is_edge == (B.get('key') == 'edge'):
        learn_profile(B.get('profile'), B['key'])
        return
    other = 'edge' if is_edge else 'chrome'
    learn_profile(B.get('profile'), other)
    release(session)
    bad = B.get('profile')
    release_lock()
    B.clear()
    raise Restart('opencli 扩展实例 %s 接管到的是 %s 的标签页，不是选好的浏览器（已记下，重新选）'
                  % (bad, BROWSERS[other]['name']))


# ------------------------------------------------------------- 浏览器程序 --
def browser_app(key):
    """浏览器程序的位置（Windows 上是 chrome.exe / msedge.exe，macOS 上是 .app）；没装返回 None。"""
    b = BROWSERS[key]
    if IS_MAC:
        for p in ('/Applications/%s.app' % b['mac_app'], os.path.expanduser('~/Applications/%s.app' % b['mac_app'])):
            if os.path.isdir(p):
                return p
        return None
    found = list(b['win_paths'])
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\%s' % b['exe']) as k:
                    found.insert(0, winreg.QueryValue(k, None))
            except OSError:
                pass
    except ImportError:
        pass
    return next((p for p in found if p and os.path.isfile(p) and os.path.basename(p).lower() == b['exe']), None)


def browser_running(key):
    b = BROWSERS[key]
    try:
        if IS_MAC:
            return subprocess.run(['pgrep', '-x', b['mac_app']], capture_output=True, timeout=20).returncode == 0
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq %s' % b['exe'], '/NH'], capture_output=True,
                             text=True, errors='replace', timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired):
        return True                                 # 看不出来就当开着，不另起一个
    return b['exe'] in out.lower()


def launch_browser(url=None):
    """浏览器没开时用你日常的配置打开它（和你自己点开一样）。"""
    if IS_MAC:
        args = ['open', '-a', browser_app(B['key']) or B['mac_app'], '--args', '--profile-directory=' + B['profile_dir']]
    else:
        args = [browser_app(B['key']), '--profile-directory=' + B['profile_dir']]
    subprocess.Popen(args + ([url] if url else []),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_url(url):
    """在你日常用的浏览器配置里新开一个标签页打开这个地址，和你手动打开一样（没有调试器挂着）。
    Windows 上用 chrome.exe / msedge.exe 打开（浏览器跳到前面，随后把焦点还给你）；macOS 上用 AppleScript 在最前面的
    窗口里新开，浏览器不跳到前面；没开就先打开它。"""
    exe = browser_app(B['key'])
    if not exe:
        return False
    if IS_MAC:
        if not browser_running(B['key']):
            launch_browser(url)
            return True
        try:
            _tabs_script({'open': url})
        except Unavailable as e:
            print('  用 AppleScript 新开标签页失败（%s），改用 open 命令打开（%s 会跳到前面）' % (e, B['name']), flush=True)
            subprocess.Popen(['open', '-a', exe, url],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    back = your_window()
    subprocess.Popen([exe, '--profile-directory=' + B['profile_dir'], url],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    give_focus_back(back)
    return True


# -------------------------------------------------------- 焦点还给你 --
# Windows：「chrome.exe 网址」打开网页、切换或关掉标签页时，Windows 会把浏览器提到最前，你在别处打字的光标就跑进
# 浏览器（常常落在地址栏）。所以每次这样做之前记下你在用的窗口，浏览器跳到前面后马上把焦点还回去（浏览器会闪一下）。
# 不影响接管：opencli 接管的是「最后获得焦点的浏览器窗口」里的当前标签页（扩展里按 lastFocusedWindow 找），
# 焦点还给别的程序后浏览器仍记得是哪个窗口。
# 浏览器在前面时，可能是另一个抓取脚本刚把它提上来的（几个脚本同时跑：Chrome 和 Edge），也可能是你正在用它：
# 几个脚本共用一个小记录（FOCUS_FILE，和原来的单出版商脚本是同一个），写明哪个脚本（进程号）正在把哪个浏览器
# 提上来、你原来在哪个窗口。是另一个脚本刚提上来的，就还给你原来的窗口；不是，就是你在用那个浏览器：是这次用的
# 浏览器就不还（还给它的别的窗口会让接管认错窗口），是另一个浏览器就还给它。
# macOS：打开、关掉标签页都不让浏览器跳到前面；只有要把别的窗口里的标签页切过来接管时浏览器会跳上来，
# 提之前记下你在用的程序，随后还给它。
WIN_BROWSERS = tuple(b['exe'] for b in BROWSERS.values())
FOCUS_FILE = os.path.join(tempfile.gettempdir(), 'opencli_focus.json')
FOCUS = {}


def _win():
    """user32 / kernel32（只在 Windows 上有，没有返回 None）。"""
    if 'api' not in FOCUS:
        FOCUS['api'] = None
        if os.name == 'nt':
            try:
                import ctypes
                from ctypes import wintypes
                u, k = ctypes.WinDLL('user32'), ctypes.WinDLL('kernel32')
                u.GetForegroundWindow.restype = wintypes.HWND
                u.GetForegroundWindow.argtypes = []
                for name in ('SetForegroundWindow', 'BringWindowToTop', 'IsWindow', 'IsIconic'):
                    getattr(u, name).argtypes = [wintypes.HWND]
                    getattr(u, name).restype = wintypes.BOOL
                u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
                u.GetWindowThreadProcessId.restype = wintypes.DWORD
                u.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
                u.AttachThreadInput.restype = wintypes.BOOL
                k.GetCurrentThreadId.restype = wintypes.DWORD
                k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                k.OpenProcess.restype = wintypes.HANDLE
                k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                         ctypes.POINTER(wintypes.DWORD)]
                k.QueryFullProcessImageNameW.restype = wintypes.BOOL
                k.CloseHandle.argtypes = [wintypes.HANDLE]
                FOCUS['api'] = (ctypes, wintypes, u, k)
            except Exception:
                pass
    return FOCUS['api']


def window_program(hwnd):
    """窗口所属程序的文件名（小写，如 chrome.exe）；没有窗口或看不出来返回 ''。"""
    if not hwnd:
        return ''
    ctypes, wintypes, u, k = _win()
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = k.OpenProcess(0x1000, False, pid.value)          # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ''
    try:
        buf, size = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
        if not k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return ''
        return os.path.basename(buf.value).lower()
    finally:
        k.CloseHandle(h)


def your_window():
    """要做会把浏览器提到前面的事之前调用：返回之后该把焦点还给的窗口（macOS 上是程序）；不用还时返回 None。"""
    if IS_MAC:
        app = frontmost_app()
        return None if not app or app == B['bundle'] else app
    api = _win()
    if not api:
        return None
    try:
        fg = api[2].GetForegroundWindow()
        if not fg:                                   # 锁屏时没有前台窗口
            return None
        program = window_program(fg)
        if program in WIN_BROWSERS:
            s = _shared()                            # 浏览器在前面：是另一个脚本刚把它提上来的吗
            if (s.get('by') == program and s.get('pid') != os.getpid() and s.get('until', 0) > time.time()
                    and s.get('yours')):
                fg = s['yours']                      # 是：还给你原来的窗口
                program = window_program(fg)
        if program == B['exe']:                      # 你本来就在这个浏览器里
            return None
        _shared({'yours': fg, 'by': B['exe'], 'pid': os.getpid(), 'until': time.time() + 15})
        return fg
    except Exception:
        return None


def _shared(update=None):
    """两个脚本共用的记录 {yours: 你在用的窗口, by: 被提上来的浏览器, pid: 是哪个脚本（进程号）, until: 到什么时候}。
    读写不了就当没有。"""
    try:
        with io.open(FOCUS_FILE, encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    if update:
        data.update(update)
        tmp = '%s.%d' % (FOCUS_FILE, os.getpid())
        try:
            with io.open(tmp, 'w', encoding='utf-8') as fh:
                json.dump(data, fh)
            os.replace(tmp, FOCUS_FILE)
        except OSError:
            pass
    return data


def _to_front(hwnd):
    ctypes, wintypes, u, k = _win()
    if u.SetForegroundWindow(hwnd) and u.GetForegroundWindow() == hwnd:
        return
    # 后台程序一般不许换前台窗口：借一下当前前台窗口的输入队列再换
    me = k.GetCurrentThreadId()
    other = u.GetWindowThreadProcessId(u.GetForegroundWindow(), None)
    attached = bool(other and other != me and u.AttachThreadInput(me, other, True))
    try:
        u.BringWindowToTop(hwnd)
        u.SetForegroundWindow(hwnd)
    finally:
        if attached:
            u.AttachThreadInput(me, other, False)


def give_focus_back(hwnd, wait=5.0):
    """等浏览器跳到最前面（最多 wait 秒；没跳上来就不用还），再把焦点还给 hwnd。还不回去就算了，和原来一样。"""
    if not hwnd:
        return
    if IS_MAC:
        deadline = time.time() + wait
        while frontmost_app() != B['bundle']:
            if time.time() > deadline:
                return
            time.sleep(0.2)
        try:
            subprocess.run(['open', '-b', hwnd], capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return
    try:
        _give_back(hwnd, wait)
    finally:
        if _shared().get('pid') == os.getpid():      # 做完了：别的脚本不用再按记录还
            _shared({'until': 0})


def _give_back(hwnd, wait):
    try:
        ctypes, wintypes, u, k = _win()
        deadline = time.time() + wait
        while window_program(u.GetForegroundWindow()) != B['exe']:
            if time.time() > deadline:
                return
            time.sleep(0.1)
        if not u.IsWindow(hwnd) or u.IsIconic(hwnd):   # 你那个窗口关了或最小化了：不去打开它
            return
        for _ in range(3):                           # 浏览器有时被还回去后又跳上来一次
            _to_front(hwnd)
            settle = time.time() + 1.0
            while time.time() < settle and window_program(u.GetForegroundWindow()) != B['exe']:
                time.sleep(0.1)
            if window_program(u.GetForegroundWindow()) != B['exe']:
                return
    except Exception:
        pass


def frontmost_app():
    """macOS：前台程序的 bundle id（如 com.apple.Terminal）；看不出来返回 ''。lsappinfo 是系统自带的，不用授权。"""
    try:
        asn = subprocess.run(['lsappinfo', 'front'], capture_output=True, text=True, timeout=5).stdout.strip()
        if not asn:
            return ''
        info = subprocess.run(['lsappinfo', 'info', '-only', 'bundleid', asn], capture_output=True,
                              text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ''
    m = re.search(r'"CFBundleIdentifier"\s*=\s*"([^"]+)"', info)
    return m.group(1) if m else ''


# ---------------------------------------------------- 标签栏 --
# opencli bind 只能接管最后获得焦点的浏览器窗口里的活动标签页，所以要接管的标签页不在前台时，先读标签栏、把它切到
# 前面：Windows 上用 UI Automation（同 paper_pipeline/chrome_tabs.py），macOS 上用 AppleScript（osascript 的 JavaScript
# 写法）。只读标签栏上的标题，不碰网页内容；只切这家出版商的文章页或验证页的标签页。
# 每个标签页：handle 窗口编号，index 在窗口里的位置（从 0 起），name 标题，selected 是不是这个窗口的当前标签页，
# rid 标签页编号（Windows 是 UI Automation 的 RuntimeId，macOS 是浏览器给的编号；关掉之前不变）。
POWERSHELL = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'WindowsPowerShell',
                          'v1.0', 'powershell.exe')
_MEMORY = re.compile(r'\s+-\s+(?:内存用量|内存使用率|Memory usage)\s+-\s+[\d.,]+\s*[KMG]B\s*$', re.I)
_GROUP = re.compile(r'\s+-\s+(?:属于“[^”]*”群组|Part of group\b.*)\s*$', re.I)
# Windows：只看这次用的浏览器的窗口（Edge 也是 Chromium 内核，窗口类名同样是 Chrome_WidgetWin_1，按进程名分开）；
# Chrome 的标签页是 Tab、关闭按钮是 TabCloseButton，Edge 的是 EdgeTab、EdgeTabCloseButton。
_UIA_SCRIPT = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$A = [System.Windows.Automation.AutomationElement]
$scope = [System.Windows.Automation.TreeScope]
$cfg = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:OPENCLI_FETCH_TABS)) | ConvertFrom-Json
$want = $cfg.want
$windows = New-Object System.Windows.Automation.PropertyCondition($A::ClassNameProperty, 'Chrome_WidgetWin_1')
$tabs = New-Object System.Windows.Automation.AndCondition(
  (New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, [System.Windows.Automation.ControlType]::TabItem)),
  (New-Object System.Windows.Automation.PropertyCondition($A::ClassNameProperty, [string]$cfg.tab)))
$out = New-Object System.Collections.ArrayList
$selected = $false
foreach ($w in $A::RootElement.FindAll($scope::Children, $windows)) {
  try { $proc = (Get-Process -Id $w.Current.ProcessId).ProcessName } catch { continue }
  if ($proc -ne [string]$cfg.proc) { continue }
  $handle = [int64]$w.Current.NativeWindowHandle
  $i = 0
  foreach ($t in $w.FindAll($scope::Descendants, $tabs)) {
    $name = $t.Current.Name
    $on = $false
    try { $on = $t.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected } catch {}
    $rid = ($t.GetRuntimeId()) -join '.'
    if ($want -and $want.close -and [int64]$want.handle -eq $handle -and $want.rid -eq $rid) {
      $b = $t.FindFirst($scope::Descendants, (New-Object System.Windows.Automation.PropertyCondition($A::ClassNameProperty, [string]$cfg.close)))
      if ($b) {
        $b.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
        $selected = $true
        $i++
        continue
      }
    }
    if ($want -and [int64]$want.handle -eq $handle -and [int]$want.index -eq $i -and $want.name -eq $name -and -not $want.close) {
      $t.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
      try {
        $wp = $w.GetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern)
        if ($wp.Current.WindowVisualState -eq [System.Windows.Automation.WindowVisualState]::Minimized) {
          $wp.SetWindowVisualState([System.Windows.Automation.WindowVisualState]::Normal)
        }
      } catch {}
      if ($want.focus) {
        Add-Type -Namespace OpenCliTabs -Name Win -MemberDefinition @"
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr h);
[DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, System.UIntPtr e);
"@
        [OpenCliTabs.Win]::keybd_event(0x12, 0, 0, [System.UIntPtr]::Zero)
        [OpenCliTabs.Win]::keybd_event(0x12, 0, 2, [System.UIntPtr]::Zero)
        [void][OpenCliTabs.Win]::SetForegroundWindow([System.IntPtr]$handle)
      }
      $selected = $true
      $on = $true
    }
    [void]$out.Add([pscustomobject]@{handle = $handle; index = $i; name = $name; selected = $on; rid = $rid})
    $i++
  }
}
ConvertTo-Json -Compress -Depth 4 -InputObject ([pscustomobject]@{tabs = @($out); selected = $selected})
'''
# macOS：参数（JSON）里 app 是浏览器（Google Chrome / Microsoft Edge，两个的 AppleScript 写法一样）；
# {open: 地址} 在最前面的窗口新开标签页；{close: rid} 关掉这个标签页；
# {select: {handle, index, name, focus}} 切到这个标签页（标题对得上才切），focus 时再把窗口提到最前。
# 做完再读一遍所有窗口的标签页。输出的 JSON 只用 ASCII（中文写成 \uXXXX），不受终端编码影响。
OSASCRIPT = '/usr/bin/osascript'
TABS = {'ok': False, 'js': None}    # 读成功过一次没有（第一次 macOS 可能弹出「自动化」授权框，多等一会儿）；脚本文件
_TABS_JS = r'''
function pack(o) {
  return JSON.stringify(o).replace(/[\u007f-￿]/g, function (c) {
    return '\\u' + ('0000' + c.charCodeAt(0).toString(16)).slice(-4);
  });
}
function run(argv) {
  var want = argv.length ? JSON.parse(argv[0]) : {};
  var chrome = Application(want.app || 'Google Chrome');   // Google Chrome 或 Microsoft Edge
  if (!chrome.running()) return pack({tabs: [], selected: false});
  var done = false, wins, wi, i;
  if (want.open) {
    if (chrome.windows.length === 0) { chrome.Window().make(); delay(1); }
    var front = chrome.windows[0];
    front.tabs.push(chrome.Tab({url: want.open}));
    front.activeTabIndex = front.tabs.length;
    done = true;
  }
  if (want.close) {
    wins = chrome.windows;
    for (wi = 0; wi < wins.length && !done; wi++) {
      var ids = wins[wi].tabs.id();
      for (i = 0; i < ids.length; i++) {
        if (String(ids[i]) === want.close) { wins[wi].tabs[i].close(); done = true; break; }
      }
    }
  }
  if (want.select) {
    var s = want.select;
    wins = chrome.windows;
    for (wi = 0; wi < wins.length; wi++) {
      var w = wins[wi];
      if (w.id() !== s.handle) continue;
      var titles = w.tabs.title();
      if (s.index < titles.length && titles[s.index] === s.name) {
        try { if (w.minimized()) w.minimized = false; } catch (e) {}
        w.activeTabIndex = s.index + 1;
        if (s.focus) { try { w.index = 1; } catch (e) {} chrome.activate(); }
        done = true;
      }
      break;
    }
  }
  var out = [];
  wins = chrome.windows;
  for (wi = 0; wi < wins.length; wi++) {
    var wid, names, rids, active;
    try {
      wid = wins[wi].id(); names = wins[wi].tabs.title(); rids = wins[wi].tabs.id();
      active = wins[wi].activeTabIndex();
    } catch (e) { continue; }
    for (i = 0; i < names.length; i++) {
      out.push({handle: wid, index: i, name: names[i] || '', selected: active === i + 1, rid: String(rids[i])});
    }
  }
  return pack({tabs: out, selected: done});
}
'''


class Unavailable(RuntimeError):
    """读不了浏览器的标签栏（PowerShell / osascript 出错或没应答，macOS 上没有控制浏览器的权限）。"""


def clean_title(name):
    name = (name or '').strip()
    previous = None
    while previous != name:                         # 内存用量、标签组两种后缀，先后不定
        previous = name
        name = _GROUP.sub('', _MEMORY.sub('', name)).strip()
    return name


def _uia(target=None, timeout=30):
    if not IS_WIN or not os.path.exists(POWERSHELL):
        raise Unavailable('只有 Windows 能用 UI Automation 切换标签页')
    env = dict(os.environ)
    cfg = {'proc': B['proc'], 'tab': B['tab'], 'close': B['close'], 'want': target}
    env['OPENCLI_FETCH_TABS'] = base64.b64encode(json.dumps(cfg, ensure_ascii=False).encode('utf-8')).decode()
    command = base64.b64encode(_UIA_SCRIPT.encode('utf-16-le')).decode()
    try:
        # 不挂在当前终端上（CREATE_NO_WINDOW）：终端窗口被关掉或按 Ctrl+C 时，正在关标签页的这一步不会被一起打断
        p = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                            '-EncodedCommand', command], capture_output=True, env=env, timeout=timeout,
                           stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Unavailable('PowerShell 没有应答：%s' % type(e).__name__)
    text = p.stdout.decode('utf-8', 'replace').strip()
    if p.returncode != 0 or not text.startswith('{'):
        err = p.stderr.decode('utf-8', 'replace').strip().splitlines()
        raise Unavailable('读 %s 标签栏失败：%s' % (B['name'], (err or [text or '无输出'])[-1][:120]))
    data = json.loads(text)
    tabs = data.get('tabs') or []
    if isinstance(tabs, dict):                      # ConvertTo-Json 把只有一项的数组写成对象
        tabs = [tabs]
    for t in tabs:
        t['title'] = clean_title(t.get('name'))
    return tabs, bool(data.get('selected'))


def _tabs_script(target=None, timeout=None):
    if not IS_MAC or not os.path.exists(OSASCRIPT):
        raise Unavailable('只有 macOS 能用 AppleScript 切换标签页')
    if timeout is None:
        timeout = 30 if TABS['ok'] else 180         # 第一次：等你在 macOS 的授权框里点「好」
    if not TABS['js'] or not os.path.exists(TABS['js']):
        TABS['js'] = os.path.join(tempfile.gettempdir(), 'opencli_fetch_tabs_%d.js' % os.getpid())
        try:
            with io.open(TABS['js'], 'w', encoding='utf-8') as fh:
                fh.write(_TABS_JS)
        except OSError as e:
            raise Unavailable('写不了临时脚本：%s' % e)
    args = [OSASCRIPT, '-l', 'JavaScript', TABS['js'], json.dumps(dict(target or {}, app=B['mac_app']))]
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Unavailable('osascript 没有应答：%s' % type(e).__name__)
    text = p.stdout.decode('utf-8', 'replace').strip()
    if p.returncode != 0 or not text.startswith('{'):
        err = p.stderr.decode('utf-8', 'replace').strip()
        if '-1743' in err or 'not allowed' in err.lower() or 'not authorized' in err.lower():
            raise Unavailable('没有控制 %s 的权限。请到 系统设置 → 隐私与安全性 → 自动化，'
                              '在你运行脚本的终端下面打开「%s」，然后重跑' % (B['name'], B['mac_app']))
        raise Unavailable('读 %s 标签栏失败：%s' % (B['name'], (err.splitlines() or [text or '无输出'])[-1][:160]))
    data = json.loads(text)
    TABS['ok'] = True
    tabs = data.get('tabs') or []
    for t in tabs:
        t['title'] = clean_title(t.get('name'))
    return tabs, bool(data.get('selected'))


def drop_tabs_script():
    if TABS.get('js'):
        try:
            os.remove(TABS['js'])
        except OSError:
            pass


def list_tabs():
    return (_tabs_script() if IS_MAC else _uia())[0]


def check_tabs():
    """macOS：开始前先读一次标签栏，读不了（多半是没给控制浏览器的权限）就直接停下说明原因。"""
    if not IS_MAC:
        return
    print('  检查能否控制 %s 的标签页（第一次运行时 macOS 会问「终端」能不能控制「%s」，请点「好」）'
          % (B['name'], B['mac_app']), flush=True)
    try:
        list_tabs()
    except Unavailable as e:
        raise Fatal('读不了 %s 的标签栏：%s' % (B['name'], e))


def select_tab(tab, focus=False):
    if IS_MAC:                                      # 切到这个标签页；focus 时再把它的窗口提到最前（随后把焦点还给你）
        back = your_window() if focus else None
        ok = _tabs_script({'select': {'handle': tab['handle'], 'index': tab['index'], 'name': tab['name'],
                                      'focus': bool(focus)}})[1]
        give_focus_back(back, wait=1.0)
        return ok
    back = your_window()                            # 切到前面（或还原最小化的窗口）后把焦点还给你
    ok = _uia({'handle': tab['handle'], 'index': tab['index'], 'name': tab['name'], 'focus': bool(focus)})[1]
    give_focus_back(back, wait=1.0)
    return ok


def close_tab(tab):
    """关掉这个标签页：Windows 上按它的「关闭」按钮（按 UI Automation 的编号 RuntimeId 找），macOS 上按编号关
    （不会让浏览器跳到前面）。已经不在就不按，返回 False。"""
    if IS_MAC:
        return _tabs_script({'close': tab['rid']})[1]
    back = your_window()                            # 按关闭按钮也会把浏览器提到前面：按完把焦点还给你
    pressed = _uia({'handle': tab['handle'], 'rid': tab['rid'], 'close': True})[1]
    give_focus_back(back, wait=1.0)
    return pressed


def looks_like_ours(P, title):
    """脚本打开的文章标签页可能的样子：这家出版商的页面、验证页、还在加载（标题是地址）。空白页、新标签页
    不算（浏览器新开窗口时自带的启动页也是这样，不能把它当成这篇的关掉）。"""
    return P.ours((title or '').lower())


def find_new_tab(before, seconds=15):
    """刚打开网页后：标签栏上新出现的那个标签页（按标签页编号比）。浏览器新开窗口时自带的空白启动页（新建标签页）
    不算：它可能比文章标签页先出现，认错了就会关错、把文章留着。"""
    old = {t['rid'] for t in before}
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            new = [t for t in list_tabs() if t['rid'] not in old and t['title'].lower() not in BLANK_TITLES]
        except Unavailable:
            return None
        if new:
            return next((t for t in new if t['selected']), new[0])
        time.sleep(1)
    return None


def ours_now(P, before, mine, tabs, keep=(), closed=False):
    """现在还开着的、这篇打开的标签页：先按编号找；找不到就找打开后才出现、样子像文章 / 验证页 / 加载中的。
    打开前就在的标签页（你自己的）一律不算。已经按了关闭（closed）之后只按编号确认，不再找别的。"""
    if mine:
        hit = [t for t in tabs if t['rid'] == mine['rid']]
        if hit or closed:
            return hit
    old = {t['rid'] for t in before} | set(keep)
    return [t for t in tabs if t['rid'] not in old and looks_like_ours(P, t['title'])]


def close_ours(P, before, mine):
    """关掉这篇打开的标签页，再读一遍标签栏确认它没了。它是浏览器唯一窗口里唯一的标签页时，先开一个空白页
    再关（免得把整个浏览器关掉）。关掉了返回 None，没能确认返回原因。"""
    keep = set()                                    # 为此开的空白页：不算这篇的
    closed = False
    for _ in range(4):
        try:
            tabs = list_tabs()
        except Unavailable as e:
            return '读不了标签栏（%s）' % e
        targets = ours_now(P, before, mine, tabs, keep, closed)
        if not targets:
            return None
        if len(targets) > 1:
            return '打开后新出现了 %d 个像文章的标签页，分不清哪个是这篇的，没有关' % len(targets)
        t = targets[0]
        if (not keep and sum(1 for x in tabs if x['handle'] == t['handle']) < 2
                and len({x['handle'] for x in tabs}) < 2):
            rids = {x['rid'] for x in tabs}
            open_url('about:blank')
            time.sleep(2)
            try:
                keep |= {x['rid'] for x in list_tabs() if x['rid'] not in rids}
            except Unavailable:
                pass
            keep.add('')                            # 只开一次空白页
            continue
        try:
            pressed = close_tab(t)                  # False：按编号没找到它的关闭按钮，没按到
        except Unavailable as e:
            return '按关闭按钮失败（%s）' % e
        if pressed:
            mine, closed = t, True                  # 真按到了：之后只按这个编号确认它没了
        time.sleep(1)                               # 没按到：下一轮重新找这个标签页再按，不当作已关掉
    try:
        left = ours_now(P, before, mine, list_tabs(), keep, closed)
    except Unavailable as e:
        return '读不了标签栏（%s）' % e
    return None if not left else '按了关闭，标签页还在（%s）' % left[0]['title'][:60]


# 正在处理的那篇的标签页。运行被中途停掉（直接关掉终端窗口、注销、关机）时据此抢着关掉它；
# 万一来不及（比如在任务管理器里结束进程），下次启动时先把它关掉。只存在系统临时文件夹里，关掉后就删。
# 每个浏览器一个文件（这个脚本同时开两份时各管各的）；和原来单出版商脚本的文件名分开，互不去关对方的标签页。
CURRENT = {}
_CLOSE_HANDLER = []


def open_tab_file():
    return os.path.join(tempfile.gettempdir(), 'opencli_fetch_open_tab_%s.json' % B.get('key', 'x'))


def remember_open_tab(mine):
    CURRENT['mine'] = mine
    try:
        with io.open(open_tab_file(), 'w', encoding='utf-8') as fh:
            json.dump({'rid': mine['rid'], 'handle': mine['handle'], 'title': mine.get('title', ''),
                       'time': time.strftime('%Y-%m-%d %H:%M:%S')}, fh, ensure_ascii=False)
    except OSError:
        pass


def forget_open_tab():
    CURRENT.pop('mine', None)
    try:
        os.remove(open_tab_file())
    except OSError:
        pass


def close_leftover_tab():
    """上次运行在处理一篇时被停掉、没来得及关的那个标签页：启动时先关掉。按当时记下的编号找，而且标题要像
    文章、验证页或加载中，你自己的标签页不会碰。"""
    try:
        with io.open(open_tab_file(), encoding='utf-8') as fh:
            left = json.load(fh)
    except (OSError, ValueError):
        return
    try:
        for t in list_tabs():
            if (t['rid'] == left.get('rid') and any(looks_like_ours(P, t['title']) for P in PUBLISHERS + [GENERIC])
                    and close_tab(t)):
                print('  关掉了上次中途停下时留下的标签页：%s' % t['title'][:70], flush=True)
    except Unavailable:
        return
    forget_open_tab()


def install_close_handler():
    """直接关掉终端窗口（或注销、关机）时：抢着按编号关掉正在处理的那篇的标签页。Windows 上是控制台事件（只给几秒钟），
    macOS 上是 SIGHUP / SIGTERM。Ctrl+C 不在这里处理：它照常变成 KeyboardInterrupt，由 fetch_one 关掉标签页再退出。"""
    if _CLOSE_HANDLER:                              # 自动重新开始时不重复登记
        return

    def close_current():
        mine = CURRENT.get('mine')
        if mine:
            try:
                if close_tab(mine):
                    forget_open_tab()
            except BaseException:
                pass

    if IS_WIN:
        try:
            import ctypes
            from ctypes import wintypes

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
            def handler(event):
                if event in (2, 5, 6):              # CTRL_CLOSE_EVENT / CTRL_LOGOFF_EVENT / CTRL_SHUTDOWN_EVENT
                    close_current()
                return False                        # 其余照常（Ctrl+C 交给 Python）
            if ctypes.windll.kernel32.SetConsoleCtrlHandler(handler, True):
                _CLOSE_HANDLER.append(handler)      # 留着引用，免得被回收
        except Exception:
            pass
        return

    def on_signal(signum, frame):
        close_current()
        cleanup()
        os._exit(128 + signum)                      # 台账每篇跑完就写进去了，直接退出不丢进度

    for name in ('SIGHUP', 'SIGTERM'):
        try:
            signal.signal(getattr(signal, name), on_signal)
        except (ValueError, OSError, AttributeError):
            pass
    _CLOSE_HANDLER.append(on_signal)


def is_challenge(title):
    return any(s in (title or '').lower() for s in CHALLENGE)


def page_error(title, head):
    """页面几乎没有文字时，标题或开头写着的错误（404、服务器错误、无法访问…）；不是报错页返回 None。"""
    text = ('%s\n%s' % (title or '', head or '')).lower()
    return next((s for s in ERROR_SIGNS if s in text), None)


# ============================== 出版商 ==============================
# 每家出版商一个类：怎么认它的网址和标签页、读哪个范围、页面里有哪些不显示的重复块要去掉、怎么判断没有全文、
# 图表清单怎么读、图片怎么命名和下载、参考文献标题长什么样、存到哪。Elsevier / ACS / Wiley 的每一处都照原来的
# chrome_elsevier.py / chrome_acs.py / chrome_wiley.py，一字未改。以后加出版商：照样写一个类，加进 PUBLISHERS。
ACS_HOST = 'pubs.acs.org'
# ACS（Silverchair）文章页的文章区：标题、作者信息、摘要、正文、参考文献、补充材料。opencli extract 默认读
# <main>/<article>，ACS 页面上没有 <main>，<article> 是补充材料 PDF 的预览小窗（实测只读到 2804 字符）
ACS_SCOPE = '.widget-instance-Article_ArticleMainViewWrapper'
# 没有全文权限时页面上的话（ACS 同时把地址转到 …-abstract/…?redirectedFrom=fulltext）
NO_ACCESS = ('You do not currently have access to this', 'This content is only available via PDF')
WILEY_HOST = 'onlinelibrary.wiley.com'       # 也认它的学会子域名：ift.、scijournals.、aocs.、aiche.、efsa. …
# 转到 Wiley 的老 DOI 先到这些网址，由浏览器再跳到 Wiley（脚本自己请求会被 Cloudflare 拦下）
WILEY_GATEWAYS = ('doi.wiley.com', 'www.hindawi.com', 'hindawi.com')
# 有全文的 Wiley 文章页里才有这一块（正文）；老文章只有 PDF、没有全文权限时，页面上只有摘要和参考文献
WILEY_FULL = '.article-section__full'


def host_of(url):
    return (urllib.parse.urlsplit(url or '').hostname or '').lower()


def papers_dir(key):
    """这家出版商的文献放在哪：PAPERS_DIRS 里写了的（只在 Windows 上）照写的，否则脚本旁边的 <key>_papers。"""
    return (PAPERS_DIRS.get(key) if IS_WIN else None) or os.path.join(HERE, '%s_papers' % key)


def is_wiley(url):
    """Wiley Online Library（含学会子域名）上的地址，或会被浏览器转到 Wiley 的网址。"""
    host = host_of(url)
    return host == WILEY_HOST or host.endswith('.' + WILEY_HOST) or host in WILEY_GATEWAYS


def wiley_loading(title):
    """标签页还在加载、标题是地址的样子（doi.org、Wiley 或转到 Wiley 的网址）。"""
    t = (title or '').lower().strip()
    return t.startswith(('doi.org',) + WILEY_GATEWAYS) or (WILEY_HOST in t.split('/')[0] and ' ' not in t)


# ---------------------------------------------------------------- 接管 --
# doi：页面的 <meta name="citation_doi">（ACS 跳转后的地址里没有 DOI，靠它认文章）；scope：有没有 ACS 的文章区；
# full：有没有 Wiley 的正文区；edge：页面报的浏览器标识里 Edge 的版本（Chrome 是空的，核对接管到的是哪个浏览器）
PAGE_STATE_JS = (r"(() => ({href: location.href, ready: document.readyState, title: document.title, "
                 r"chars: document.body ? document.body.innerText.length : 0, "
                 r"head: document.body ? document.body.innerText.slice(0, 300) : '', "
                 r"doi: (document.querySelector('meta[name=citation_doi]') || {}).content || '', "
                 r"scope: !!document.querySelector('" + ACS_SCOPE + r"'), "
                 r"full: !!document.querySelector('" + WILEY_FULL + r"'), "
                 r"translated: /\btranslated-(ltr|rtl)\b/.test(document.documentElement.className || ''), "
                 r"edge: (navigator.userAgent.match(/\bEdg\/([\d.]+)/) || [null, ''])[1]}))()")


# 几个 CSS 选择器里页面上有的第一个（都没有是空字符串）：新写的几家选 opencli extract 的范围
SCOPE_JS = "(s => s.find(x => { try { return !!document.querySelector(x); } catch (e) { return false; } }) || '')(%s)"


def page_state(session):
    try:
        s = page_eval(session, PAGE_STATE_JS, timeout=30)
        return s if isinstance(s, dict) else {}
    except Exception:
        return {}


def article_keys(url, doi):
    """地址里认这篇文章的标识：ScienceDirect 用 PII，其他网站用 DOI 或文章路径。"""
    m = re.search(r'/pii/([A-Za-z0-9]+)', url)
    if m:
        return [m.group(1).upper()]
    keys = [doi.upper()] if doi else []
    path = urllib.parse.urlsplit(url).path.rstrip('/')
    if len(path) > 3:
        keys.append(path.upper())
    return keys


def matches(address, keys):
    address = urllib.parse.unquote(address or '').upper()
    return bool(address) and any(k in address for k in keys)


def same_article(href, doi, keys):
    """是这篇吗：地址里有它的标识，或者页面的 citation_doi 就是它的 DOI（ACS 跳转后、停在中转网址时地址里没有 DOI）。"""
    return matches(href, keys) or (bool(doi) and doi.strip().upper() in keys)


def wait_new_tab(P, url, deadline, load_timeout=LOAD_TIMEOUT, before=None):
    """刚打开时只看标签栏上的标题（不接管、不碰网页），等各窗口的当前标签页过了加载和
    「请稍候…」验证：验证期间挂上调试器，更容易被判成机器人。读不了标签栏就直接往下走。"""
    t0, said = time.time(), False
    while time.time() < deadline:
        try:
            tabs = list_tabs()
        except Unavailable:
            return
        # 打开之前就开着的空白页（比如别的窗口里 opencli 自己的 about:blank）不算「还在加载」，不然每篇白等 load_timeout
        old_blank = {t.get('rid') for t in (before or []) if (t.get('title') or '').lower() in BLANK_TITLES}
        current = [t['title'] for t in tabs if t['selected'] and not (t.get('rid') in old_blank
                                                                    and t['title'].lower() in BLANK_TITLES)]
        checking = [t for t in current if is_challenge(t)]
        # macOS 上加载中的标题带 https://
        loading = [t for t in current if t.lower() in BLANK_TITLES or t.lower() in UNTITLED
                   or P.loading(re.sub(r'^https?://', '', t.lower()) if IS_MAC else t.lower())]
        if current and not checking and not loading:
            return
        if checking and not said and time.time() - t0 > 25:
            print(VERIFY_PROMPT % url, flush=True)
            said = True
        if not checking and time.time() - t0 > load_timeout:
            return                                  # 一直在加载：交给下面的接管去看
        time.sleep(2)


def try_bind(P, keys):
    """接管浏览器的当前标签页看一眼。('taken', 会话)：就是这篇且已显示全文；('waiting', None)：是这篇，
    还在加载；('checking', None)：是这篇，停在人机验证；('error', None)：是这篇，网页报错；('other', None)：别的页面；
    ('none', None)：没接管到。只读地址、标题和文字长度。"""
    session = new_session()
    try:
        bound = cli_json('browser', session, 'bind', timeout=30)
    except Exception:
        bound = {}
    if not isinstance(bound, dict):
        bound = {}
    href = bound.get('url') or ''
    if matches(href, keys) or (P.meta_doi and P.owns(href)):
        s = page_state(session)
        if P.meta_doi and not (matches(href, keys) or same_article(s.get('href'), s.get('doi'), keys)):
            # 跳转后的地址里没有 DOI（ACS）、还停在中转网址（Wiley）时看页面的 citation_doi；还在加载、读不到时先当作在等
            release(session)
            if s.get('ready') != 'complete' and not s.get('doi'):
                return 'waiting', None, bound
            return 'other', None, bound
        check_browser(session, s)
        if is_challenge(bound.get('title')) or is_challenge(s.get('title')):
            release(session)
            return 'checking', None, bound
        if (s.get('chars') or 0) >= MIN_PAGE_CHARS or P.small_page(s):
            if B.get('key') == 'edge' and s.get('edge'):
                print('  已接管 Microsoft Edge 的标签页（Edg/%s）' % s.get('edge'), flush=True)
            return 'taken', session, bound
        release(session)
        error = page_error(s.get('title') or bound.get('title'), s.get('head'))
        if error:
            return 'error', None, dict(bound, error=error)
        return 'waiting', None, bound
    release(session)
    return ('other' if bound.get('url') else 'none'), None, bound


def try_tab(P, tab, keys, several):
    """把一个标签页切到前面再接管。多一种结果 'missed'：两次都接管到别的窗口的标签页（那个窗口有焦点）；
    'gone'：标签页已经不在了。"""
    for attempt in range(2):
        if not select_tab(tab, focus=several or attempt > 0):
            return 'gone', None
        time.sleep(0.8 + attempt)
        result, session, bound = try_bind(P, keys)
        if result in ('taken', 'waiting', 'checking'):
            return result, session
        if result == 'error':
            return 'error', bound.get('error')
        if result == 'none':
            return 'gone', None
        if clean_title(bound.get('title')) == tab['title']:
            return 'other', None
    return 'missed', None


def take_over(P, url, keys, deadline, started=None, load_timeout=LOAD_TIMEOUT, mine=None):
    """接管这篇文章的标签页，返回会话名；到 deadline 还没接管到返回 None。
    刚打开的标签页通常就是当前标签页，先直接接管；不是的话在这家出版商的标签页里找（标题认不出这家的，如通用读法、MDPI，
    只找打开时新出现的那个）。网页报错、或打开 load_timeout 秒还没显示文章也不是验证页，就抛 PageError 跳过；
    只有验证页才一直等到 deadline。"""
    known, said = set(), set()

    def say(what, message):
        if what not in said:
            print(message, flush=True)
            said.add(what)

    uia = True
    last_check = started or time.time()              # 打开的时刻，或最近一次看到验证页的时刻
    while time.time() < deadline:
        result, session, bound = try_bind(P, keys)
        if result == 'taken':
            return session
        if result == 'error':
            raise PageError('网页报错（%s）' % bound.get('error'))
        if result == 'checking' or is_challenge(bound.get('title')):
            last_check = time.time()                 # 验证页：等你完成，不算超时
            say('verify', VERIFY_PROMPT % url)
            time.sleep(5)
            continue
        if time.time() - last_check > load_timeout:
            raise PageError('打开 %g 秒还没显示文章，也不是验证页（网页打不开、报错或找不到标签页）' % load_timeout)
        if result == 'waiting':
            time.sleep(3)
            continue
        if uia:
            try:
                tabs = list_tabs()
            except Unavailable as e:
                print('  读不了 %s 的标签栏（%s），改为请你手动切换' % (B['name'], e), flush=True)
                uia = False
                continue
            several = len({t['handle'] for t in tabs}) > 1
            for t in tabs:
                if not (P.tab_title(t['title']) or (P.find_new and mine and t['rid'] == mine['rid'])) \
                        or (t['handle'], t['index'], t['name']) in known:
                    continue
                result, session = try_tab(P, t, keys, several)
                if result == 'taken':
                    return session
                if result == 'error':
                    raise PageError('网页报错（%s）' % session)
                if result == 'checking':
                    last_check = time.time()
                    say('verify', VERIFY_PROMPT % url)
                    break
                if result == 'waiting':
                    break
                if result == 'other' and is_challenge(t['title']):
                    last_check = time.time()          # 验证页的地址里可能没有这篇的编号：也当作在等验证
                    say('verify', VERIFY_PROMPT % url)
                elif result == 'other':
                    known.add((t['handle'], t['index'], t['name']))
                elif result == 'missed':
                    say('focus', bn(FOCUS_PROMPT))
            else:
                say('missing', bn(NOT_FOUND_PROMPT) % url)
        else:
            say('switch', bn(SWITCH_PROMPT) % url)
        time.sleep(4)
    return None


def wait_ready(P, session, keys, seconds=60, poll=2.0):
    """等页面加载完、文字长度稳定下来（被浏览器休眠的标签页切回前台时会重新加载）。"""
    deadline, last, s = time.time() + seconds, None, {}
    while time.time() < deadline:
        s = page_state(session)
        chars = s.get('chars') or 0
        here = same_article(s.get('href'), s.get('doi'), keys) if P.meta_doi else matches(s.get('href'), keys)
        if (here and s.get('ready') == 'complete' and (chars >= MIN_PAGE_CHARS or P.small_page(s))
                and last is not None and abs(chars - last) <= 0.01 * chars):
            return s
        last = chars
        time.sleep(poll)
    return s


def wait_original(session, url, minutes=10.0, poll=3.0):
    """页面被浏览器自动翻译时，等你点「显示原文」再读（浏览器设置归你，脚本不改）。"""
    if not page_state(session).get('translated'):
        return
    print(bn(TRANSLATED_PROMPT) % (url, minutes), flush=True)
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        time.sleep(poll)
        if not page_state(session).get('translated'):
            time.sleep(2.0)
            return
    raise Stop(bn('页面一直是 {b} 自动翻译的译文，没有恢复原文；这篇没有保存'))


# 从上往下滚一遍再回到顶部：ScienceDirect 的正文和图是懒渲染的，不滚动只有摘要（实测 3893 字符）
SCROLL_JS = (r"(async () => { const H = () => Math.max(document.body ? document.body.scrollHeight : 0, "
             r"document.documentElement.scrollHeight); const step = Math.max(400, Math.floor(window.innerHeight * 0.9)); "
             r"const t0 = Date.now(); let y = 0; while (y < H() && Date.now() - t0 < 60000) { y += step; "
             r"window.scrollTo(0, y); await new Promise(r => setTimeout(r, 150)); } window.scrollTo(0, 0); "
             r"return {height: H(), ms: Date.now() - t0}; })()")


def scroll_through(session):
    try:
        page_eval(session, SCROLL_JS, timeout=120)
    except Exception as e:
        print('  滚动页面失败（%s），按现状读' % str(e)[:80], flush=True)


# ---------------------------------------------------------------- 读全文 --
def extract_all(session, selector=None):
    """opencli extract 分段读完，原样拼接（每段是同一份 markdown 的切片，拼起来就是整份）。
    分段之间页面变了（总长度不同）就从头再读，最多三次。"""
    scope = ['--selector', selector] if selector else []
    for _ in range(3):
        parts, start, first = [], 0, None
        while len(parts) < 100:
            d = cli_json('browser', session, 'extract', *scope, '--chunk-size', str(CHUNK),
                         '--start', str(start), timeout=240)
            if not isinstance(d, dict) or d.get('error') or 'content' not in d:
                raise RuntimeError('opencli extract 出错：%s' % json.dumps(d, ensure_ascii=False)[:300])
            if first is None:
                first = d
            elif d.get('total_chars') != first.get('total_chars'):
                break
            parts.append(d['content'])
            if d.get('next_start_char') is None:
                return {'url': first.get('url') or '', 'title': first.get('title') or '',
                        'total': first.get('total_chars') or 0, 'content': ''.join(parts),
                        'chunks': len(parts), 'selector': selector}
            start = d['next_start_char']
        time.sleep(3)
    raise RuntimeError('页面在分段读取时一直在变，没读到一份前后一致的全文')


# ---------------------------------------------------------------- 表格 --
# opencli extract = 网页里跑 buildExtractHtmlJs（复制文章区域、去掉导航按钮等）+ 本机 htmlToMarkdown（turndown）。
# turndown 不认表格，每个格子成了单独一段。这里用 opencli 自己的这两样东西再转一遍，只多一步：
# 在它复制出的副本里（不是网页本身）把每张 <table> 换成一段占位文字，同时读出每格内容和跨行跨列，
# 转完再把按原表结构重建的 markdown 表格填回占位处。纯规则，不调用任何模型。
# ACS、Wiley 还多一步：页面里有 opencli 会再读一遍、网页上却不显示的块（ACS 每张图「点开放大」用的弹窗副本
# .fig-modal，Wiley 的手机版作者列表 .mobile-authors）；副本里也换成占位文字（只换在网页上确实不显示的），转完把占位删掉。
OPENCLI_SRC = os.path.dirname(OPENCLI_MAIN)
MARK = 'XQTABLE%dXQ'
DROP_MARK = 'XQDROP%dXQ'
TABLE_HOOK = r'''let __maths = 0;
  {
    const __drop = 'script, style, noscript, template, nav, header, footer, aside, iframe, svg, canvas, form, button, input, select, textarea, [role="navigation"], [role="banner"], [role="contentinfo"], [role="complementary"], [aria-hidden="true"]';
    const __live = [...root.querySelectorAll('mjx-container')].filter(c => !(c.parentElement && c.parentElement.closest(__drop)));
    const __copies = [...clone.querySelectorAll('mjx-container')];
    if (__live.length && __live.length === __copies.length) {
      const SKIP = new Set(['mjx-speech', 'mjx-assistive-mml', 'mjx-line', 'mjx-nstrut', 'mjx-dstrut', 'mjx-spacer', 'mjx-surd']);
      const ACC = {'¯': '\u0304', '‾': '\u0304', 'ˉ': '\u0304', '^': '\u0302', 'ˆ': '\u0302', '~': '\u0303', '˜': '\u0303', '˙': '\u0307', '→': '\u20d7', '\u20d7': '\u20d7'};
      const ch = s => [...s].map(c => { const k = c.codePointAt(0); if (k === 0x2062) return '\u2062'; if (k >= 0x2061 && k <= 0x2064) return ''; return (k >= 0x1D400 && k <= 0x1D7FF) || c === 'ℎ' ? c.normalize('NFKC') : c; }).join('');
      const tg = n => (n.tagName || '').toLowerCase();
      const kid = (n, name) => [...n.children].find(c => tg(c) === name) || null;
      const scr = (s, t) => { t = t.trim(); return t ? (s === 'sub' ? 'XQSUBAXQ' + t + 'XQSUBZXQ' : 'XQSUPAXQ' + t + 'XQSUPZXQ') : ''; };
      const wrapped = t => { if (!(t.startsWith('(') && t.endsWith(')'))) return false; let d = 0; for (let i = 0; i < t.length; i++) { d += (t[i] === '(') - (t[i] === ')'); if (d === 0 && i < t.length - 1) return false; } return true; };
      const operand = t => { t = t.trim(); const b = t.replace(/XQSU[BP][AZ]XQ/g, '');
        const product = b.includes('\u2062') && (/XQSU/.test(t) || /\d/.test(b));   // 看不见的乘号连着带上下标或数字的因子
        return (/[\s+\-−×·\/=÷±]/.test(b.replace(/\u2062/g, '')) || product) && !wrapped(b.replace(/\u2062/g, '')) ? '(' + t + ')' : t; };
      const walk = n => {
        if (n.nodeType === 3) return ch(n.nodeValue);
        if (n.nodeType !== 1) return '';
        const t = tg(n);
        if (SKIP.has(t)) return '';
        if (t === 'mjx-c') {
          const m = [...n.classList].map(c => /^mjx-c([0-9A-F]+)$/i.exec(c)).find(Boolean);
          return m ? ch(String.fromCodePoint(parseInt(m[1], 16))) : ch(n.textContent || '');
        }
        const lead = parseInt(n.getAttribute('space') || '0', 10) >= 2 ? ' ' : '';
        const kids = [...n.childNodes];
        if (t === 'mjx-mfrac') {
          const fr = kid(n, 'mjx-frac') || n;
          const num = kid(fr, 'mjx-num') || fr.querySelector('mjx-num');
          const den = [...fr.querySelectorAll('mjx-den')].find(d => !num || !num.contains(d));
          if (num && den) return lead + operand(walk(num)) + '/' + operand(walk(den));
        }
        if (t === 'mjx-msub' || t === 'mjx-msup' || t === 'mjx-msubsup') {
          const base = kids.filter(c => tg(c) !== 'mjx-script').map(walk).join('');
          const s = kid(n, 'mjx-script');
          const parts = [[]];
          for (const c of (s ? [...s.childNodes] : [])) { if (tg(c) === 'mjx-spacer') parts.push([]); else parts[parts.length - 1].push(c); }
          const p = parts.map(x => x.map(walk).join('')).concat(['', '']);
          if (t === 'mjx-msub') return lead + base + scr('sub', p[0]);
          if (t === 'mjx-msup') return lead + base + scr('sup', p[0]);
          return lead + base + scr('sub', p[1]) + scr('sup', p[0]);
        }
        if (t === 'mjx-msqrt' || t === 'mjx-mroot') {
          const box = n.querySelector('mjx-box'), idx = kid(n, 'mjx-root');
          return lead + (idx ? scr('sup', walk(idx)) : '') + '√' + operand(box ? walk(box) : kids.map(walk).join(''));
        }
        if (t === 'mjx-munder' || t === 'mjx-mover' || t === 'mjx-munderover') {
          const b = n.querySelector('mjx-base'), u = n.querySelector('mjx-under'), o = n.querySelector('mjx-over');
          if (b) {
            const bt = walk(b), ut = u ? walk(u).trim() : '', ot = o ? walk(o).trim() : '';
            const bar = /^[\u0305\u0304¯‾ˉ―]+$/.test(ot) ? '\u0304' : '';   /* 上横线（拉长的是一串 ̅）：写成一个 ̄，R̄、ȳ */
            if ((ACC[ot] || bar) && !ut) return lead + bt + (ACC[ot] || bar);
            return lead + bt + scr('sub', ut) + scr('sup', ot);
          }
        }
        if (t === 'mjx-mtable') {
          const rows = [...n.querySelectorAll('mjx-mtr, mjx-mlabeledtr')];
          if (rows.length) return lead + rows.map(r => [...r.children].filter(c => tg(c) === 'mjx-mtd').map(c => walk(c).trim()).join(' ')).join('; ');
        }
        if (t === 'mjx-mspace') return ' ';
        return lead + kids.map(walk).join('');
      };
      const linear = n => walk(n).replace(/\u2062/g, '').replace(/[ \t\u00a0]+/g, ' ').trim().replace(/\(\s+/g, '(').replace(/\s+\)/g, ')');
      const mkm = t => { const e = document.createElement('span'); e.textContent = t; return e; };
      __copies.forEach((cp, i) => {
        let text = '';
        try { text = linear(__live[i]); } catch (e) { text = ''; }
        if (!text) return;
        const display = __live[i].getAttribute('display') === 'true';
        let target = cp, label = '';
        if (display) {
          const w = cp.closest('span.formula, div.formula-wrap, div.inline-equation');
          if (w && w.querySelectorAll('mjx-container').length === 1) {
            const l = [...w.querySelectorAll('.label, [class*="label"]')].map(e => (e.textContent || '').replace(/\s+/g, ' ').trim()).find(x => /^\(\s*[A-Z]?\d+[a-z]?\s*\)$/.test(x));
            if (l) { target = w; label = l; }
          }
        }
        const nw = document.createElement(display ? 'div' : 'span');
        nw.textContent = label ? text + ' ' + label : text;
        target.before(mkm('XQMATHAXQ'));
        target.after(mkm('XQMATHMXQ'), nw, mkm('XQMATHZXQ'));
        __maths++;
      });
    }
  }
  let __scripts = 0;
  for (const s of [...clone.querySelectorAll('sub, sup')]) {
    if (!(s.textContent || '').trim()) continue;   /* 空的上下标不加标记：加了外面的粗体、斜体就不算空，多出 ****、_ _ */
    const k = s.tagName.toLowerCase() === 'sub' ? 'B' : 'P';
    const mk = t => { const e = document.createElement('span'); e.textContent = t; return e; };
    s.prepend(mk('XQSU' + k + 'AXQ'));
    s.append(mk('XQSU' + k + 'ZXQ'));
    __scripts++;
  }
  const __tables = [];
  /* Wiley 的表题在表格外面的 <header class="article-table-caption"> 里，opencli 把 header 当页眉删了：按外框的 id
     从网页上同一张表读回来，写成「Table N. 表题」（同 Elsevier 的写法）。只放进 caption，表格本身的 html 不变，
     核对照旧和 extract 逐字比。 */
  const __wcap = t => {
    const box = t.closest('.article-table-content');
    if (!box || !box.id) return '';
    let live = null;
    try { live = root.querySelector('#' + CSS.escape(box.id)); } catch (e) {}
    const h = live && live.querySelector('.article-table-caption');
    if (!h) return '';
    const c = h.cloneNode(true);
    for (const m of [...c.querySelectorAll('mjx-container')]) { const a = m.querySelector('mjx-assistive-mml'); m.replaceWith(a ? a.textContent : ''); }
    for (const n of [...c.querySelectorAll('script, style, button, [aria-hidden="true"]')]) n.remove();
    const lab = c.querySelector('.table-caption__label');
    const label = lab ? (lab.textContent || '').replace(/\s+/g, ' ').trim().replace(/[.:]+$/, '') : '';
    if (lab) lab.remove();
    for (const s of [...c.querySelectorAll('sub, sup')]) {
      if (!(s.textContent || '').trim()) continue;
      const k = s.tagName.toLowerCase() === 'sub' ? 'B' : 'P';
      s.prepend('XQSU' + k + 'AXQ');
      s.append('XQSU' + k + 'ZXQ');
    }
    const m = /^table\s+(\S+)$/i.exec(label);
    const head = m ? 'Table ' + m[1] + '.' : (label ? label + '.' : '');
    const body = c.innerHTML.trim();
    return head && body ? head + ' ' + body : head || body;
  };
  for (const t of [...clone.querySelectorAll('table')]) {
    if (t.parentElement && t.parentElement.closest('table')) continue;
    const rows = [], foot = [];
    for (const tr of t.rows) {
      const cells = [...tr.cells].map(c => ({html: c.innerHTML, cs: Math.max(1, c.colSpan || 1), rs: Math.max(1, c.rowSpan || 1), head: c.tagName === 'TH'}));
      if (!cells.length) continue;
      if (tr.parentElement && tr.parentElement.tagName === 'TFOOT' && cells.length === 1) foot.push(cells[0].html); else rows.push(cells);
    }
    __tables.push({rows: rows, foot: foot, caption: t.caption ? t.caption.innerHTML : __wcap(t), html: t.outerHTML});
    const p = document.createElement('p');
    p.textContent = 'XQTABLE' + __tables.length + 'XQ';
    t.replaceWith(p);
  }
  '''
# 不显示的重复块（DROP）那一步：插在换表格之前，选择器按出版商换（ACS .fig-modal、Wiley .mobile-authors）
DROP_HOOK = r'''  const __drops = [];
  const __modals = [...root.querySelectorAll('__DROP__')];
  for (const [k, m] of [...clone.querySelectorAll('__DROP__')].entries()) {
    let o = null;
    try { o = m.id ? root.querySelector('#' + CSS.escape(m.id)) : null; } catch (e) {}
    o = o || __modals[k];
    if (!o || getComputedStyle(o).display !== 'none') continue;
    __drops.push(m.outerHTML);
    const p = document.createElement('p');
    p.textContent = 'XQDROP' + __drops.length + 'XQ';
    m.replaceWith(p);
  }
'''
# 新写的几家（Springer、MDPI、T&F …）在 TABLE_HOOK 里多插的几步（ACS、Wiley、Elsevier 不插，照原样）：
# 1. 公式之后、上下标之前：把不在正文原位的表放回原位（P.pre_js，用 __place）。换下来的那一块（「Full size table」
#    链接、MDPI 的表格图标）记进 __flats；核对时这张表还原成那一块，所以表格以外的文字照样和 extract 逐字比。
# 2. 换表格之前：DROP（页面上不显示的重复块）之外再去掉 JUNK（正文中间网页插进来的推荐文章栏，页面上是显示的）。
#    同样换成 XQDROPnXQ 占位，核对时还原，写出时删掉。
# 3. 换完表格：放回原位的表记下 flat（核对时还原成的样子）。
PLACE_JS = r'''  const __flats = [], __extErr = [], __extImg = [];
  const __txt = e => {
    if (!e) return '';
    const c = e.cloneNode(true);
    for (const s of [...c.querySelectorAll('sub, sup')]) { const k = s.tagName.toLowerCase() === 'sub' ? 'B' : 'P'; s.prepend('XQSU' + k + 'AXQ'); s.append('XQSU' + k + 'ZXQ'); }
    return (c.textContent || '').replace(/\s+/g, ' ').trim();
  };
  const __live = e => {
    if (!e) return null;
    const c = e.cloneNode(true);
    for (const n of [...c.querySelectorAll('script, style, noscript, template, nav, header, footer, aside, iframe, svg, canvas, form, button, input, select, textarea, [aria-hidden="true"]')]) n.remove();
    for (const n of [c, ...c.querySelectorAll('*')]) for (const a of [...n.attributes]) if (a.name.startsWith('on') || a.name === 'style' || a.name.startsWith('data-')) n.removeAttribute(a.name);
    return c;
  };
  const __place = (slot, html, foot) => {
    const tpl = document.createElement('template');
    tpl.innerHTML = html || '';
    const tb = tpl.content.querySelector('table');
    if (!tb || !clone.contains(slot)) return false;
    for (const c of [...tb.querySelectorAll('caption')]) c.remove();
    if (foot && foot.length) {
      const tf = tb.createTFoot();
      for (const h of foot) { const tr = document.createElement('tr'); const td = document.createElement('td'); td.innerHTML = h; tr.appendChild(td); tf.appendChild(tr); }
    }
    tb.setAttribute('data-xq-flat', String(__flats.length));
    __flats.push(slot.outerHTML);
    slot.replaceWith(tb);
    return true;
  };
'''
JUNK_HOOK = r'''  for (const m of [...clone.querySelectorAll('__JUNK__')]) {
    if (!clone.contains(m) || (m.parentElement && m.parentElement.closest('__JUNK__'))) continue;
    __drops.push(m.outerHTML);
    const p = document.createElement('p');
    p.textContent = 'XQDROP' + __drops.length + 'XQ';
    m.replaceWith(p);
  }
'''
FLAT_JS = r'''  for (const t of __tables) { const m = /^<table\b[^>]*?\sdata-xq-flat="(\d+)"/.exec(t.html); if (m) t.flat = __flats[+m[1]]; }
'''
# 在 node 里调用 opencli 自带的函数：mode=js 取 extract 的网页脚本，mode=md 把 HTML 转成 markdown
NODE_HELPER = r'''
let s = '';
process.stdin.setEncoding('utf8');
for await (const c of process.stdin) s += c;
const req = JSON.parse(s);
const out = {};
if (req.mode === 'js') {
  const m = await import(req.extract);
  out.js = m.buildExtractHtmlJs(req.selector || null);
} else {
  const m = await import(req.utils);
  out.md = m.htmlToMarkdown(req.html);
  out.parts = req.parts.map(h => m.htmlToMarkdown(h));
}
process.stdout.write(JSON.stringify(out));
'''


def node_helper(request, timeout=180):
    node = shutil.which('node')
    if not node or not os.path.exists(OPENCLI_MAIN):
        raise RuntimeError('找不到 node 或 npm 版 opencli')
    p = subprocess.run([node, '--input-type=module', '-e', NODE_HELPER], input=json.dumps(request, ensure_ascii=False),
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError('node 调用 opencli 转换失败：%s' % p.stderr.strip()[-300:])
    return json.loads(p.stdout)


def file_uri(path):
    return pathlib.Path(os.path.abspath(path)).as_uri()


def publisher_hook(P):
    """新写的几家的 TABLE_HOOK：多插放回原位的表（P.pre_js）、JUNK、flat 三步。"""
    for mark in ('  let __scripts = 0;', '  const __tables = [];'):
        if TABLE_HOOK.count(mark) != 1:
            raise RuntimeError('TABLE_HOOK 和预期不一样')
    pre = PLACE_JS + P.pre_js
    drops = (DROP_HOOK.replace('__DROP__', P.drop) if P.drop else '  const __drops = [];\n') \
        + (JUNK_HOOK.replace('__JUNK__', P.junk) if P.junk else '')
    hook = TABLE_HOOK.replace('  let __scripts = 0;', pre + '  let __scripts = 0;')
    return hook.replace('  const __tables = [];', drops + '  const __tables = [];') + FLAT_JS


def table_extract_js(P, selector):
    """opencli extract 的网页脚本，只在它 return 之前插入换表格（和换不显示的重复块）的一步。脚本和预期不一样
    （opencli 升级了）就不用。"""
    js = node_helper({'mode': 'js', 'extract': file_uri(os.path.join(OPENCLI_SRC, 'browser', 'extract.js')),
                      'selector': selector})['js']
    anchor, tail = 'return { ok: true,', "html: clone.outerHTML || '' }"
    if js.count(anchor) != 1 or js.count(tail) != 1:
        raise RuntimeError('opencli 的 extract 脚本和预期不一样（版本变了？）')
    if P.pre_js or P.junk:
        if P.async_hook:                            # 放回原位的表要等网页请求（Springer 的表格页）
            if not js.startswith('(() => {'):
                raise RuntimeError('opencli 的 extract 脚本和预期不一样（版本变了？）')
            js = '(async () => {' + js[len('(() => {'):]
        return js.replace(anchor, publisher_hook(P) + anchor).replace(
            tail, "html: clone.outerHTML || '', tables: __tables, drops: __drops, scripts: __scripts, maths: __maths, "
                  "placed: __flats.length, ext_errors: __extErr, ext_images: __extImg }")
    if not P.drop:
        return js.replace(anchor, TABLE_HOOK + anchor).replace(
            tail, "html: clone.outerHTML || '', tables: __tables, scripts: __scripts, maths: __maths }")
    hook = TABLE_HOOK.replace('  const __tables = [];', DROP_HOOK.replace('__DROP__', P.drop) + '  const __tables = [];', 1)
    return js.replace(anchor, hook + anchor).replace(
        tail, "html: clone.outerHTML || '', tables: __tables, drops: __drops, scripts: __scripts, maths: __maths }")


def cell_md(md):
    """格子里的内容放进一行：换行并成空格，竖线转义（其余照 opencli 转出来的样子）。"""
    return ' '.join(re.sub(r'(?<!\\)\|', r'\\|', md or '').split())


def span_grid(rows):
    """展开跨行跨列，得到规则的格子；每格是 (内容, 是否是合并格的第一格)。同 paper_pipeline/fetch.span_grid。"""
    grid, pending = [], {}
    for r_i, cells in enumerate(rows):
        cells, row, c = list(cells), [], 0
        while True:
            while (r_i, c) in pending:
                row.append(pending.pop((r_i, c)))
                c += 1
            if not cells:
                break
            cell = cells.pop(0)
            base = c
            for dc in range(cell['cs']):
                row.append((cell['md'], dc == 0))
                for dr in range(1, cell['rs']):
                    pending[(r_i + dr, base + dc)] = (cell['md'], False)
                c += 1
        grid.append(row)
    width = max((len(r) for r in grid), default=0)
    return [r + [('', True)] * (width - len(r)) for r in grid]


def bold_cell(h):
    """多层表头第二层起的格子加粗。只有公式的格子（以前 opencli 删了公式，是空格子）粗体只加在公式文字上：
    还原成以前的样子仍是空格子，不会多出 ****。"""
    if not h:
        return ''
    if scripts_flat(h).strip():
        return '**%s**' % h
    return MATH_BLOCK.sub(lambda m: m.group(1) + 'XQMATHAXQ' + m.group(2) + 'XQMATHMXQ'
                          + ('**%s**' % m.group(3).strip() if m.group(3).strip() else '') + 'XQMATHZXQ' + m.group(4), h)


def table_block(t, md):
    """一张表的 markdown：表格自带的 <caption>、表格本身、表脚注（tfoot 里的单格行）。
    多层表头按原表分行（同流水线）：第一层作表头行，其余层紧跟分隔线、加粗；合并的表头格只写一次，
    数据区合并格的值每格都写。读不出行列的表照 opencli 原样（拆散的格子）。"""
    rows = [[dict(c, md=cell_md(md[c['i']])) for c in r] for r in t['rows']]
    grid = span_grid(rows) if rows else []
    width = len(grid[0]) if grid else 0
    if not width or width > 60:
        return md[t['i_html']]
    nh = 0
    for r in t['rows']:
        if all(c['head'] for c in r):
            nh += 1
        else:
            break
    nh = min(max(nh, 1), len(grid))
    labels = [[text if first else '' for text, first in row] for row in grid[:nh]]
    lines = ['| ' + ' | '.join(labels[0]) + ' |', '|' + '|'.join(['---'] * width) + '|']
    lines += ['| ' + ' | '.join(bold_cell(h) for h in row) + ' |' for row in labels[1:]]
    lines += ['| ' + ' | '.join(text for text, _ in row) + ' |' for row in grid[nh:]]
    parts = ([md[t['i_caption']]] if md[t['i_caption']] else []) + ['\n'.join(lines)]
    return '\n\n'.join(parts + [md[i] for i in t['i_foot'] if md[i]])


def squash(text):
    return ' '.join(text.split())


# opencli（turndown）只在一段文字的开头才加的反斜杠：= - + # > ~ 和「1.」。加了公式 / 上下标标记后，文字在哪儿
# 断开会变（「amplitude [公式]= 3 %」extract 里是 \=，表格版里是 =），核对时不算这几个反斜杠。
LEADING_ESCAPE = re.compile(r'\\([-+=#>~])|(?<=\d)\\(?=\.)')


def loose(text):
    return LEADING_ESCAPE.sub(lambda m: m.group(1) or '', text)


# 上下标（用户 2026-10-06：转成纯文本）：opencli 转 markdown 时把 <sub>/<sup> 压平了，Ca²⁺ 成了 Ca2+、S₀ 成了 S0、
# 8.0×10¹⁰ 成了 8.0 × 1010。所以在换表格的同一个页面副本里，给每个 <sub>/<sup> 里面前后各加一个只装标记的
# <span>（单独一段，不改原文字的分段，opencli 对原文字的转义照旧：上标开头的 - 照样写成 \-），转完按流水线
# finalize.readable_scripts 的规则写成纯文本：数字和 + − = ( ) 用 Unicode 上下标（CaCl₂、s⁻¹、Ca²⁺、10¹⁰、¹³C）；
# 带字母的写成 T_c、N_{agg}、ω^n；斜体符号后面的字母下标放进斜体里（_V_t_，显示为斜体的 V_t）。上标里只是引文链接的
# （ACS 的引文编号）照原样，不改写。核对「表格以外和 opencli extract 逐字一致」时先去掉标记再比。
# 图注 figure_markdown.md 从 2026-10-09 起也这样写（见下面 RICH_TEXT_JS）。以前抓的不动：读图脚本靠它判断文章
# 变没变，--refresh 重抓已经读过图的文章会让它重读一遍（重花 API）。
SCRIPT_CHARS = '0123456789+-−=()'
SUB_DIGITS = str.maketrans(SCRIPT_CHARS, '₀₁₂₃₄₅₆₇₈₉₊₋₋₌₍₎')
SUP_DIGITS = str.maketrans(SCRIPT_CHARS, '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁼⁽⁾')
SCRIPT_MARKS = re.compile(r'XQSU[BP][AZ]XQ')
SCRIPT_ONE = re.compile(r'(\*[^*\n]+\*|(?<![\\\w])_[^_\n]+_)?XQSU([BP])AXQ((?:(?!XQSU[BP][AZ]XQ).)*?)XQSU\2ZXQ', re.S)
MD_LINK = re.compile(r'\[[^\]\n]*\]\([^)\n]*\)')
SCRIPTS = {'n': 0, 'math': 0, 'marked': None, 'raw': None}   # 这一篇：上下标处数、带标记的全文、extract 原样（补上下标.py 核对用）


# 公式（用户 2026-10-06：把公式加上）：三家都用 MathJax 画公式，opencli 把画出来的那份（[aria-hidden=true]、svg）删了，
# Elsevier、Wiley 的公式整个没了（只剩编号），ACS 只剩压平的 MathML（FA\=Vfoam,t\=0Vliquid,i）。页面副本里每个公式前后
# 加标记，中间同时放「以前 opencli 读到的样子」（核对用）和「从网页上的公式结构读出的一行文字」（同流水线
# sciencedirect_snapshot.mathjax_text：分式写成 (分子)/分母，上下标同上面的规则，数学斜体字母还原成普通字母）；
# 单独成行的公式自成一段，编号放在末尾（同流水线：EE (%) = (C_{total} − C_{free})/C_{total} × 100% (7)）。
MATH_BLOCK = re.compile(r'(\n*)XQMATHAXQ(.*?)XQMATHMXQ(.*?)XQMATHZXQ(\n*)', re.S)
MATH_UNESCAPE = re.compile(r'\\([-+=.!#>()\[\]|~{}<])')   # 公式文字是脚本自己写的：opencli 加的转义去掉


def math_new(m):
    """这次读出的公式：单独成行的（前后带空行）自成一段，前后各留一个空行；句子里的留在原位。"""
    new = MATH_UNESCAPE.sub(r'\1', m.group(3))
    if '\n' in new:
        return '\n\n' + new.strip() + '\n\n'
    return m.group(1) + new + m.group(4)


def scripts_render(text, scripts=True, math=True):
    """带标记的全文 → 写出来的样子。scripts=False：上下标照以前压平；math=False：公式照以前 opencli 读到的样子。"""
    text = MATH_BLOCK.sub(math_new if math else (lambda m: m.group(1) + m.group(2) + m.group(4)), text)
    if not scripts:
        return SCRIPT_MARKS.sub('', text)

    def one(m):
        base, tag, inner = m.group(1) or '', 'sub' if m.group(2) == 'B' else 'sup', m.group(3)
        plain = re.sub(r'(?<!\\)[*_]', '', inner)
        plain = re.sub(r'\\(.)', r'\1', plain).strip()     # 去掉 markdown 转义（上标开头的 - 会写成 \-）
        if not plain or MD_LINK.search(inner):          # 空的，或者只是引文链接：照原样
            return base + inner
        if tag == 'sup' and all(ch in "′″‴'" for ch in plain):   # 撇号本来就在上面：Carr′s
            return base + plain
        if all(ch in SCRIPT_CHARS for ch in plain):
            return base + plain.translate(SUB_DIGITS if tag == 'sub' else SUP_DIGITS)
        mark = ('_' if tag == 'sub' else '^') + (plain if len(plain) == 1 else '{%s}' % plain)
        return base[0] + base[1:-1] + mark + base[-1] if base else mark
    previous = None
    while previous != text:                           # 套在一起的：从最里面的开始
        previous, text = text, SCRIPT_ONE.sub(one, text)
    return SCRIPT_MARKS.sub('', text)                  # 还剩的标记（没配上对的）去掉，里面的字照原样


def scripts_flat(text):
    """去掉上下标和公式的标记：就是以前 opencli 原样转出来的样子（核对用）。"""
    return scripts_render(text, scripts=False, math=False)


def scripts_readable(text):
    """上下标写成纯文本、公式写成一行文字。"""
    return scripts_render(text, scripts=True, math=True)


def media_readable(media):
    """图表清单里的图注、表题、表下注：上下标标记写成纯文本（同正文）。"""
    for item in media.get('figures', []) + media.get('tables', []):
        for k in ('label', 'caption'):
            if isinstance(item.get(k), str):
                item[k] = scripts_readable(item[k])
        if item.get('notes'):
            item['notes'] = [scripts_readable(x) for x in item['notes']]
    return media


# 图注、表题、表下注（用户 2026-10-09：以后新抓的图注也不要有上下标问题）：照网页上显示的字读（同 innerText：
# display:none 的不读、段落之间换行），只是 <sub>/<sup>（MathML 的 msub/msup 也算）加上下标标记，MathJax 公式用
# 正文同一套读法（TABLE_HOOK 里 const SKIP 到 linear 那几个函数，原样取出）写成一行；回到 Python 由 media_readable
# 写成纯文本。skip：不读的部分（CSS 选择器）；inside：只读 e 里面的（上下标自己已经认过了）。各出版商的图表清单脚本开头放这一段（__RICH__）。
MATH_WALK_JS = TABLE_HOOK[TABLE_HOOK.index('const SKIP = '):TABLE_HOOK.index('const mkm = ')]
RICH_TEXT_JS = ' '.join(re.sub(r'[ \t]+//[^\n]*', '', MATH_WALK_JS + r"""
  const rich = (e, skip, inside) => {
    if (!e) return '';
    const out = [];
    const visit = (n, hid) => {
      if (n.nodeType === 3) { if (!hid) out.push(n.nodeValue.replace(/[ \t\n\r\f]+/g, ' ')); return; }
      if (n.nodeType !== 1) return;
      const t = tg(n);
      if (/^(script|style|noscript|template)$/.test(t) || (typeof skip === 'string' && n.matches(skip))) return;
      const cs = getComputedStyle(n);
      if (cs.display === 'none') return;
      hid = cs.visibility !== 'visible';
      const brk = t === 'p' ? 2 : /^(inline|contents|ruby|table-cell)/.test(cs.display) ? 0 : 1;
      if (t === 'br') { if (!hid) out.push('\n'); return; }
      if (t === 'mjx-container') {
        let m = '';
        try { m = linear(n); } catch (x) { m = ''; }
        if (!hid) out.push(brk, m || n.innerText || '', brk);
        return;
      }
      if (t === 'sub' || t === 'sup') {
        const s = rich(n, skip, true).replace(/\s+/g, ' ');
        if (!hid) out.push(s.trim() ? scr(t, s) : s);
        return;
      }
      if ((t === 'msub' || t === 'msup' || t === 'msubsup') && n.children.length >= 2) {
        const k = [...n.children].map(c => rich(c, skip).trim());
        if (!hid) out.push(t === 'msup' ? k[0] + scr('sup', k[1]) : k[0] + scr('sub', k[1]) + scr('sup', k[2] || ''));
        return;
      }
      if (brk) out.push(brk);
      for (const c of n.childNodes) visit(c, hid);
      if (brk) out.push(brk);
      else if (cs.display === 'table-cell') out.push(' ');
    };
    if (inside) for (const c of e.childNodes) visit(c, false);
    else visit(e, false);
    let s = '', pend = 0;
    for (const x of out) {
      if (typeof x === 'number') { pend = Math.max(pend, x); continue; }
      let y = x;
      if (pend) {
        y = y.replace(/^ +/, '');
        if (!y) continue;
        s = s.trim() ? s.replace(/ +$/, '') + '\n'.repeat(pend) : '';
        pend = 0;
      }
      s += y;
    }
    return s.replace(/ {2,}/g, ' ').replace(/ *\n */g, '\n').trim();
  };""").splitlines())


EXTRA_MEDIA = []          # 这一篇要作为图片版表格存的表（Springer 的表格页上是图片的；with_tables 写，read_once 并进图表清单）


def with_tables(P, session, page):
    """全文里的 HTML 表格换成 markdown 表格、去掉不显示的重复块（ACS 的图弹窗副本、Wiley 的手机版作者列表），
    其余一字不动。返回 (全文, 重建的表格数, 去掉的重复块数, 提醒或 None)。
    核对：把占位处换回 opencli 对这张表 / 这块的原样转换，必须和刚才 extract 读到的全文一致（只允许空白不同），
    否则整篇按 extract 原样保存。页面在两次读取之间变了，就重读一次再核对。
    放回原位的表（Springer、T&F、MDPI）核对时还原成原位原来的那一块（t['flat']），写出时照这张表重建。"""
    ext_note = None
    try:
        js = table_extract_js(P, page['selector'])
    except Exception as e:
        return page['content'], 0, 0, '表格没有重建（%s），全文按 opencli 原样保存' % e
    SCRIPTS.update(n=0, math=0, marked=None)
    for attempt in range(2):
        SCRIPTS['raw'] = page['content']
        res = page_eval(session, js, timeout=180)
        if not isinstance(res, dict) or not res.get('ok'):
            return page['content'], 0, 0, '表格没有重建（读页面结构失败），全文按 opencli 原样保存'
        tables, drops = res.get('tables') or [], res.get('drops') or []
        EXTRA_MEDIA[:] = res.get('ext_images') or []
        ext_note = P.ext_fail % (len(res['ext_errors']), '；'.join(res['ext_errors'])) if res.get('ext_errors') else None
        if res.get('placed') and attempt == 0:
            print('  %d 张表放回正文原位（原来在%s）' % (res['placed'], P.placed_from), flush=True)
        if not tables and not drops and not res.get('scripts') and not res.get('maths'):
            SCRIPTS['marked'] = page['content']
            return page['content'], 0, 0, ext_note
        parts = []

        def add(html):
            parts.append(html or '')
            return len(parts) - 1

        for t in tables:
            t['i_html'], t['i_caption'] = add(t['flat'] if 'flat' in t else t.get('html')), add(t.get('caption'))
            if 'flat' in t:
                t['i_raw'] = add(t.get('html'))
            t['i_foot'] = [add(h) for h in t.get('foot') or []]
            for row in t['rows']:
                for c in row:
                    c['i'] = add(c.get('html'))
        i_drops = [add(h) for h in drops]
        conv = node_helper({'mode': 'md', 'utils': file_uri(os.path.join(OPENCLI_SRC, 'utils.js')),
                            'html': res.get('html') or '', 'parts': parts})
        body, md = conv['md'], conv['parts']
        marks = [MARK % (i + 1) for i in range(len(tables))]
        drop_marks = [DROP_MARK % (i + 1) for i in range(len(drops))]
        if all(body.count(m) == 1 for m in marks + drop_marks):
            flat = body
            for m, t in zip(marks, tables):
                flat = flat.replace(m, md[t['i_html']])
            for m, i in zip(drop_marks, i_drops):
                flat = flat.replace(m, md[i])
            a, b = loose(squash(scripts_flat(flat))), loose(squash(page['content']))
            if a.replace(' ', '') == b.replace(' ', ''):   # 空白落在哪儿也不算（标记会让 opencli 把粗体旁的空格挪个位置）
                for m, t in zip(marks, tables):
                    body = body.replace(m, table_block(dict(t, i_html=t['i_raw']) if 'flat' in t else t, md))
                for m in drop_marks:
                    body = re.sub(r'\n*[ \t]*%s[ \t]*\n*' % m, '\n\n', body)
                SCRIPTS.update(n=body.count('XQSUBAXQ') + body.count('XQSUPAXQ'), math=body.count('XQMATHAXQ'), marked=body)
                return scripts_readable(body), len(tables), len(drops), ext_note
            i = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            print('  核对不一致（第 %d 次）：表格版「…%s…」 / extract「…%s…」'
                  % (attempt + 1, a[max(0, i - 40):i + 40], b[max(0, i - 40):i + 40]), flush=True)
        else:
            print('  占位标记没有各出现一次（第 %d 次）' % (attempt + 1), flush=True)
        if attempt == 0:                            # 页面可能在两次读取之间又渲染了一些：重读再核对
            time.sleep(3)
            page = dict(page, **extract_all(session, page['selector']))
    return page['content'], 0, 0, P.table_fail


# 图和图片版表格（ScienceDirect）：每个 <figure> 里的图片地址（页面上的图 + 下载高清图的链接）和图注；
# .tables 里只有图片、没有 <table> 的就是图片版表格，带上表题和表下注。只读，不改页面。
SD_MEDIA_JS = ' '.join(r'''(() => {
  __RICH__
  const text = e => rich(e);
  const abs = u => { try { return u ? new URL(u, location.href).href : ''; } catch (e) { return ''; } };
  const urls = box => { const out = [];
    for (const a of box.querySelectorAll('a[href]')) out.push(abs(a.getAttribute('href')));
    for (const im of box.querySelectorAll('img')) for (const u of [im.currentSrc, im.getAttribute('src'), im.getAttribute('data-src')]) out.push(abs(u));
    return [...new Set(out.filter(u => /^https?:/i.test(u)))]; };
  const linkOnly = c => { let t = text(c); for (const a of c.querySelectorAll('a')) if (/^(download|view|open)\b/i.test(text(a))) t = t.split(text(a)).join(''); return !t.trim(); };
  const figures = [];
  for (const f of document.querySelectorAll('figure')) {
    if (f.closest('.tables')) continue;
    const im = f.querySelector('img');
    const d = im && im.getAttribute('aria-describedby');
    let cap = f.querySelector('.captions, figcaption');
    if (!cap && d) cap = document.getElementById(d);
    const lab = cap && cap.querySelector('.label');
    figures.push({id: f.id || '', label: text(lab), caption: text(cap), urls: urls(f)});
  }
  const tables = [];
  for (const t of document.querySelectorAll('.tables')) {
    if (t.querySelector('table') || !t.querySelector('img')) continue;
    const cap = t.querySelector('.captions, .caption, caption');
    const lab = cap && cap.querySelector('.label');
    const notes = [...t.children].filter(c => !(cap && (c === cap || c.contains(cap))) && c.tagName !== 'IMG' && !c.querySelector('img') && !linkOnly(c)).map(text).filter(Boolean);
    tables.push({id: t.id || '', label: text(lab), caption: text(cap), notes: notes, urls: urls(t)});
  }
  const doiLink = [...document.querySelectorAll('a[href]')].map(a => a.href).find(h => /^https?:\/\/(dx\.)?doi\.org\/10\./i.test(h));
  return {href: location.href, title: document.title, doi: doiLink || '', figures: figures, tables: tables};
})()'''.splitlines()).replace('__RICH__', RICH_TEXT_JS)

# 图、图文摘要和图片版表格（ACS / Silverchair）：文章区里每个图框（.fig.fig-section；图文摘要是 .graphical-abstract）
# 的图片地址和图注（.graphic-bottom 里的 Figure N. + 图注），按页面顺序；图的弹窗副本（.fig-modal）不算。
# .table-wrap 里只有图片、没有 <table> 的就是图片版表格，带上表题和表下注。只读，不改页面。
ACS_MEDIA_JS = ' '.join(r'''(() => {
  __RICH__
  const text = e => rich(e);
  const abs = u => { try { return u ? new URL(u, location.href).href : ''; } catch (e) { return ''; } };
  const urls = box => { const out = [];
    for (const a of box.querySelectorAll('a[href]')) out.push(abs(a.getAttribute('href')));
    for (const im of box.querySelectorAll('img')) for (const u of [im.currentSrc, im.getAttribute('src'), im.getAttribute('data-src')]) out.push(abs(u));
    return [...new Set(out.filter(u => /^https?:/i.test(u)))]; };
  const scope = document.querySelector('__SCOPE__') || document.body;
  const sel = '.graphical-abstract, .graphicalAbstract, .fig.fig-section, .table-wrap';
  const figures = [], tables = [];
  for (const b of scope.querySelectorAll(sel)) {
    if (b.closest('.fig-modal') || (b.parentElement && b.parentElement.closest(sel))) continue;
    if (b.matches('.table-wrap')) {
      if (b.querySelector('table') || !b.querySelector('img')) continue;
      const notes = [...b.querySelectorAll('.table-wrap-foot > *')].map(text).filter(Boolean);
      tables.push({id: b.id || '', label: text(b.querySelector('.table-wrap-title .label')),
                   caption: text(b.querySelector('.table-wrap-title .caption')), notes: notes, urls: urls(b)});
      continue;
    }
    const ga = b.matches('.graphical-abstract, .graphicalAbstract');
    const lab = ga ? null : (b.querySelector('.graphic-bottom .label') || b.querySelector('.fig-label'));
    const cap = ga ? null : b.querySelector('.graphic-bottom .caption, .fig-caption');
    figures.push({id: b.getAttribute('data-id') || b.id || '', ga: ga, label: text(lab), caption: text(cap), urls: urls(b)});
  }
  const meta = document.querySelector('meta[name=citation_doi]');
  return {href: location.href, title: document.title, doi: meta ? meta.content : '', figures: figures, tables: tables};
})()'''.splitlines()).replace('__RICH__', RICH_TEXT_JS).replace('__SCOPE__', ACS_SCOPE)

# 图、图文摘要和图片版表格（Wiley）：文章里每个 figure.figure（图片浏览器里的那个不算），图号在 .figure__title，
# 图注在 .figure__caption-text；摘要区里没有图号的图当作图文摘要。.article-table-content 里只有图片、没有 <table>
# 的是图片版表格：表号在 .table-caption__label，表题是表头里其余的字，表注是表下的脚注和来源。只读，不改页面。
WILEY_MEDIA_JS = ' '.join(r'''(() => {
  __RICH__
  const text = (e, skip) => rich(e, skip).replace(/\s+/g, ' ').trim();
  const abs = u => { try { return u ? new URL(u, location.href).href : ''; } catch (e) { return ''; } };
  const urls = box => { const out = [];
    for (const a of box.querySelectorAll('a[href]')) out.push(abs(a.getAttribute('href')));
    for (const im of box.querySelectorAll('img')) for (const u of [im.getAttribute('data-lg-src'), im.currentSrc, im.getAttribute('src'), im.getAttribute('data-src')]) out.push(abs(u));
    return [...new Set(out.filter(u => /^https?:/i.test(u) && /\/cms\/asset\//i.test(u)))]; };
  const scope = document.querySelector('article') || document.body;
  const figures = [], tables = [];
  for (const f of scope.querySelectorAll('figure.figure')) {
    if (f.closest('.figure-viewer')) continue;
    const label = text(f.querySelector('.figure__title'));
    const capEl = f.querySelector('.figure__caption-text');
    let caption = text(capEl);
    if (!capEl) { const fc = f.querySelector('figcaption');
      if (fc) caption = text(fc, '.figure__caption__header, .figure__title, .figure-extra'); }
    const ga = !!f.closest('.abstract-group, .article-section__abstract') && !/^(fig|figure|scheme|chart|table)\b/i.test(label);
    figures.push({id: f.id || '', ga: ga, label: label, caption: caption, urls: urls(f)});
  }
  for (const t of scope.querySelectorAll('.article-table-content')) {
    if (t.querySelector('table') || !t.querySelector('img')) continue;
    const label = text(t.querySelector('.table-caption__label'));
    let caption = text(t.querySelector('header, .article-table-caption'));
    if (label && caption.startsWith(label)) caption = caption.slice(label.length).trim();
    const notes = [...t.querySelectorAll('.article-section__table-footnotes, .article-section__table-source')].map(text).filter(Boolean);
    tables.push({id: t.id || '', label: label, caption: caption, notes: notes, urls: urls(t)});
  }
  const meta = document.querySelector('meta[name=citation_doi]');
  return {href: location.href, title: document.title, doi: meta ? meta.content : '', figures: figures, tables: tables};
})()'''.splitlines()).replace('__RICH__', RICH_TEXT_JS)

# 通用读法的图（还没有专门读法的出版商）：页面上每张在图框里、不是图标 / logo 的图片。认识的图框：<figure>、.fig、
# .figure、MDPI 的 .html-fig-wrap、Springer 的 .c-article-section__figure、Frontiers 的 .ArticleFigure、Cambridge 的
# .fig-ada，以及 id 以 fig / F 开头的块；从图片往外找，取还只包着这一张图的最外一层。候选地址按「点开放大的原图链接 →
# data-large / data-original 等懒加载的原图 → srcset 里最大的 → 页面上显示的」排。同一张图在页面里出现几次（比如 MDPI
# 另有一份隐藏的放大弹窗）只算一次，地址合在一起、图注取最长的那段。只读，不改页面。
GENERIC_MEDIA_JS = ' '.join(r'''(() => {
  __RICH__
  const abs = u => { try { return u ? new URL(u, location.href).href : ''; } catch (e) { return ''; } };
  const isImg = u => /\.(jpe?g|png|gif|tiff?|webp|svg)(\?|#|$)/i.test(u || '');
  const boxSel = 'figure, .fig, .figure, .fig-section, .fig-graphic, .figure-wrap, .html-fig_wrap, .html-fig-wrap, .c-article-section__figure, .ArticleFigure, .fig-ada, [id^="fig"], [id^="Fig"], [id^="F"]';
  const capSel = '.c-article-section__figure-description, .figure__caption-text, .ArticleFigure__caption, .html-caption, .html-fig_description, .fig-caption, figcaption, .caption, .captions';
  const labSel = '.fig-label, .label, .ArticleFigure__title, .c-article-section__figure-caption, .html-caption b, figcaption b, .figure__title';
  const icon = (img, u) => /^data:/i.test(u || '') || /logo|icon|sprite|badge|button|cover|avatar|banner|orcid|crossmark/i.test(u || '') || (img.getAttribute('width') && +img.getAttribute('width') < 60);
  const best = list => { let top = '', w = -1; for (const part of (list || '').split(',')) { const m = part.trim().split(/\s+/); const n = parseFloat(m[1]) || 1; if (m[0] && n > w) { w = n; top = m[0]; } } return top; };
  const textOf = e => { if (!e) return ''; const t = rich(e); return t || (e.textContent || '').replace(/\s+/g, ' ').trim(); };
  const real = b => [...b.querySelectorAll('img')].filter(i => !icon(i, i.getAttribute('src') || '')).length;
  const out = [], byKey = new Map();
  for (const img of document.querySelectorAll('img')) {
    if (img.closest('nav, header, footer')) continue;
    const boxes = [];
    for (let e = img.parentElement; e && e !== document.body; e = e.parentElement) {
      if (e.tagName !== 'A' && e.matches(boxSel)) boxes.push(e);
    }
    if (!boxes.length) continue;
    let box = boxes[0];
    for (const b of boxes) { if (real(b) <= real(boxes[0])) box = b; else break; }
    const pic = img.closest('picture');
    const srcset = pic ? [...pic.querySelectorAll('source')].map(s => best(s.getAttribute('srcset'))).filter(Boolean) : [];
    const inline = abs(img.dataset.large || img.dataset.original || img.getAttribute('data-original-image') || img.dataset.lsrc || img.dataset.src || img.currentSrc || img.getAttribute('src'));
    if (!inline || icon(img, inline)) continue;
    if (img.complete && img.naturalWidth && img.naturalWidth < 100) continue;
    const images = [];
    for (const a of new Set([img.closest('a'), ...box.querySelectorAll('a[href]')])) {
      if (!a) continue;
      const h = abs(a.getAttribute('href'));
      if (h && isImg(h) && !/DownloadImage\.aspx|downloadFigures/i.test(h)) { if (/_lrg|high-?res|original|large|full/i.test(h + ' ' + a.textContent)) images.unshift(h); else images.push(h); }
    }
    for (const u of [img.dataset.large, img.dataset.original, img.getAttribute('data-original-image'), img.dataset.lsrc, img.dataset.src, best(img.getAttribute('srcset')), ...srcset, img.currentSrc, img.getAttribute('src')]) {
      const x = abs(u); if (x && !/^data:/i.test(x)) images.push(x);
    }
    let caption = '';
    for (const c of box.querySelectorAll(capSel)) { const t = textOf(c); if (t.length > caption.length) caption = t; }
    const labelEl = box.querySelector(labSel);
    const label = labelEl ? textOf(labelEl) : (box.getAttribute('data-title') || '');
    const key = inline.replace(/[?#].*/, '').split('/').pop().replace(/^m_/, '').replace(/(-\d{3,4}|_HTML|-m)?\.\w+$/, '').toLowerCase();
    const old = byKey.get(key);
    if (old) {
      old.urls = [...new Set(old.urls.concat(images))];
      if (caption.length > old.caption.length) old.caption = caption;
      if (!old.label) old.label = label;
      continue;
    }
    const f = {label: label, alt: img.getAttribute('alt') || '', caption: caption, urls: [...new Set(images)]};
    byKey.set(key, f);
    out.push(f);
  }
  const meta = document.querySelector('meta[name=citation_doi], meta[name=prism\\.doi], meta[name=dc\\.identifier]');
  return {href: location.href, title: document.title, doi: meta ? meta.content : '', figures: out, tables: []};
})()'''.splitlines()).replace('__RICH__', RICH_TEXT_JS)

# ---- 新写的几家：放回原位的表（插在 TABLE_HOOK 里，见 PLACE_JS；clone 是 opencli 复制出的页面副本，data-* 属性已被它删掉）
# Springer：正文里每张表只有表题和「Full size table」链接（…/tables/1），整张表在那个表格页上：在已打开的文章页里按
# 链接读出表格页（和点开它是同一个请求，带着这个页面的登录状态），表和表下注换下「Full size table」那一格（只装着这个
# 链接的 .u-text-right，否则就是链接本身）。要等网页请求，所以这家的 extract 脚本改成 async（Springer.async_hook）。
# 没读到的记进 __extErr。表格页上是图片的（.c-article-table-image，老文章、BMC 有）记进 __extImg：作为图片版表格存进
# figure\（同 Elsevier），正文原位照旧是「Full size table」链接。
SPRINGER_PRE_JS = r'''  {
    const done = {};
    for (const a of [...clone.querySelectorAll('a[href*="/tables/"]')]) {
      if (!/full size table/i.test(a.textContent || '')) continue;
      let u = '';
      try { u = new URL(a.getAttribute('href'), location.href).href; } catch (e) { continue; }
      if (new URL(u).host !== location.host) continue;
      if (!(u in done)) {
        done[u] = null;
        try {
          const r = await fetch(u, {credentials: 'include'});
          if (!r.ok) throw new Error('HTTP ' + r.status);
          const d = new DOMParser().parseFromString(await r.text(), 'text/html');
          const tb = d.querySelector('.c-article-table-container table') || d.querySelector('main table');
          const f = d.querySelector('.c-article-table-footer');
          const im = d.querySelector('.c-article-table-image img');
          if (!tb && im) {
            const cap = __txt((a.closest('figure') || a.closest('.c-article-table') || a.parentElement).querySelector('figcaption'));
            const lab = (cap.match(/^Table\s*[A-Z]?\d+[a-z]?/i) || [''])[0];
            __extImg.push({label: lab, caption: cap.slice(lab.length).trim(), notes: f ? [...f.querySelectorAll('li')].map(__txt).filter(Boolean) : [],
                           urls: [new URL(im.getAttribute('src'), u).href]});
            continue;
          }
          if (!tb) throw new Error('表格页上没有表');
          const li = f ? [...f.querySelectorAll('li')] : [];
          done[u] = {table: tb.outerHTML, foot: li.length ? li.map(e => e.innerHTML) : (f && (f.textContent || '').trim() ? [f.innerHTML] : [])};
        } catch (e) { __extErr.push(u.replace(/\/+$/, '').split('/').pop() + '：' + String((e && e.message) || e).slice(0, 80)); }
      }
      const x = done[u];
      if (!x) continue;
      const p = a.parentElement;
      __place(p && p.matches('.u-text-right') && (p.textContent || '').trim() === (a.textContent || '').trim() ? p : a, x.table, x.foot);
    }
  }
'''
# T&F：多数文章页上每张表只有表题和「Download CSV / Display Table」两个按钮（.tableDownloadOption），点 Display Table
# 弹出的整张表（含表下注）在页面自带的数据 tandf.tfviewerdata 里（一段 <script>）：从那里取，换下这两个按钮。
TANDF_DATA_JS = r'''let tf = {};
    try {
      const s = [...document.scripts].find(x => /tfviewerdata\s*=/.test(x.textContent || ''));
      if (s) { const t = s.textContent; tf = JSON.parse(t.slice(t.indexOf('{', t.indexOf('tfviewerdata')), t.lastIndexOf('}') + 1)); }
    } catch (e) { tf = {}; }'''
TANDF_PRE_JS = r'''  {
    ''' + TANDF_DATA_JS + r'''
    const byId = {};
    for (const x of tf.tables || []) if (x && x.id) byId[x.id] = x.content || '';
    for (const slot of [...clone.querySelectorAll('.tableView .tableDownloadOption[id$="-table-wrapper"]')]) {
      const v = slot.closest('.tableView');
      const html = byId[slot.id.replace(/-table-wrapper$/, '')];
      if (!v || v.querySelector('table') || !html) continue;
      const tpl = document.createElement('template');
      tpl.innerHTML = html;
      const tb = tpl.content.querySelector('table');
      if (tb) __place(slot, tb.outerHTML, [...tpl.content.querySelectorAll('.NLM_table-wrap-foot > div, .NLM_table-wrap-foot > p')].map(n => n.innerHTML));
    }
  }
'''
# MDPI：正文里每张表（.html-table-wrap#<编号>）只有表题和一个「点开看表」的小图标（.html-table_wrap_td），整张表在
# 页面最后（参考文献后面）藏着的弹窗 #table_body_display_<编号> 里：复制一份换下小图标，表下注（.html-table_foot）
# 放在表格下面；弹窗本身作为不显示的重复块去掉（Python 那边 MDPI.drop）。MDPI 在试新版网页（2026-10 实测 Edge 拿到
# 新版、Chrome 拿到旧版）：新版把弹窗挪到了整页最后、文章区外面（页面副本里没有），就从网页本身复制（__live）。
MDPI_PRE_JS = r'''  for (const w of [...clone.querySelectorAll('.html-table-wrap[id]')]) {
    const slot = w.querySelector('.html-table_wrap_td');
    let pop = null;
    try { pop = clone.querySelector('#' + CSS.escape('table_body_display_' + w.id)); } catch (e) {}
    pop = pop || __live(document.getElementById('table_body_display_' + w.id));
    const tb = pop && pop.querySelector('table');
    if (slot && tb) __place(slot, tb.outerHTML, [...pop.querySelectorAll('.html-table_foot')].map(f => f.innerHTML));
  }
'''
# MDPI 的图（新旧两版都这样读）：正文里每个图框 .html-fig-wrap#<编号>（不算页面最后「Figures and Tables」汇总区里的
# 副本 #media_<编号>），图注 .html-fig_description（开头是「Figure 1.」）；图片取放大弹窗 #fig_body_display_<编号> 里的
# 原图（data-large，多图面板有几张取几张），再加图框里的。图文摘要（文件名 …-ag-550.jpg）单独认出：原图是去掉 -550 的
# .png。页面上显示的 …-550.jpg 是缩小的，原图排在前面。
MDPI_MEDIA_JS = ' '.join(r'''(() => {
  __RICH__
  const abs = u => { try { return u ? new URL(u, location.href).href : ''; } catch (e) { return ''; } };
  const cands = u => { if (!u) return []; const o = u.replace(/-\d{3,4}(\.\w+)(?=$|[?#])/, '$1'); return o !== u ? [o.replace(/\.jpe?g(?=$|[?#])/i, '.png'), o, u] : [u]; };
  const out = [], seen = new Set();
  const add = (f, imgs) => {
    for (const img of imgs) {
      const urls = [...new Set([img.getAttribute('data-large'), img.getAttribute('data-original')].map(abs).filter(Boolean).concat(cands(abs(img.getAttribute('data-lsrc') || img.getAttribute('src')))).filter(u => u && !/^data:/i.test(u)))];
      if (!urls.length) continue;
      const k = urls[urls.length - 1].replace(/[?#].*/, '').split('/').pop().replace(/-\d{3,4}(\.\w+)$/, '$1').replace(/\.\w+$/, '').toLowerCase();
      if (seen.has(k)) continue;
      seen.add(k);
      out.push(Object.assign({}, f, {urls: urls}));
    }
  };
  const ga = [...document.querySelectorAll('img')].filter(i => /-ag(-\d+)?\.\w+($|[?#])/.test(i.getAttribute('src') || ''));
  if (ga.length) add({label: 'Graphical abstract', caption: '', ga: true}, [ga[0]]);
  for (const w of document.querySelectorAll('.html-fig-wrap[id]')) {
    if (w.closest('#FiguresandTables') || /^media_/.test(w.id)) continue;
    const d = w.querySelector('.html-fig_description');
    const b = d && d.querySelector('b');
    const pop = document.getElementById('fig_body_display_' + w.id);
    add({label: b ? (b.textContent || '').replace(/\s+/g, ' ').trim() : '', caption: d ? rich(d) : ''},
        [...(pop ? pop.querySelectorAll('img') : []), ...w.querySelectorAll('img')]);
  }
  const meta = document.querySelector('meta[name=citation_doi]');
  return {href: location.href, title: document.title, doi: meta ? meta.content : '', figures: out, tables: []};
})()'''.splitlines()).replace('__RICH__', RICH_TEXT_JS)
# T&F 的图：.figureView（图注 .short-legend，开头是「Figure 1.」标签 .captionLabel），页面上显示的是缩略图 …_b.gif；
# 点开的大图在 tandf.tfviewerdata 里（…_b.jpg），原图是同名的 …_oc.jpg。图注里可能有小插图（…_ilg0001，也是
# a.thumbnail img.figure-image），图片只取直接在 .figureView 下的那个缩略图。摘要区（.hlFld-Abstract）里没有标签的图是图文摘要。同一张图在「Figures & data」标签页里
# 还有一份（不显示）：按编号只算一次，先取显示着的。
TANDF_MEDIA_JS = ' '.join((r'''(() => {
  __RICH__
  const abs = u => { try { return u ? new URL(u, location.href).href : ''; } catch (e) { return ''; } };
  ''' + TANDF_DATA_JS + r'''
  const big = {};
  for (const x of tf.figures || []) {
    const all = [...((x && x.content) || '').matchAll(/<img[^>]*\ssrc="([^"]+)"/g)].map(m => m[1]);
    const s = all.find(u => !/_ilg\d/i.test(u)) || all[all.length - 1];
    if (s && x.id) big[x.id] = abs(s.replace(/&amp;/g, '&'));
  }
  const orig = u => u.replace(/_b\.(jpe?g|gif|png)(?=$|[?#])/i, '_oc.jpg');
  const views = [...document.querySelectorAll('.figureView')].sort((a, b) => (b.offsetParent !== null) - (a.offsetParent !== null));
  const figures = [], seen = new Set();
  for (const v of views) {
    const own = [...v.children].find(c => c.matches('a.thumbnail'));
    const img = own ? own.querySelector('img') : [...v.querySelectorAll('img')].find(i => !i.closest('.short-legend'));
    if (!img) continue;
    const idEl = own && own.getAttribute('data-id') ? own : v.querySelector('[data-id]:not([data-id=""])');
    const id = (idEl ? idEl.getAttribute('data-id') : '') || abs(img.getAttribute('src'));
    if (seen.has(id)) continue;
    seen.add(id);
    const lab = v.querySelector('.captionLabel'), leg = v.querySelector('.short-legend');
    const ga = !lab && !!v.closest('.hlFld-Abstract');
    const urls = [];
    for (const u of [big[id], abs(img.getAttribute('src'))]) if (u) urls.push(orig(u), u);
    figures.push({label: lab ? rich(lab) : '', caption: leg ? rich(leg, 'button') : '', alt: img.getAttribute('alt') || '', ga: ga, urls: [...new Set(urls)]});
  }
  const m = decodeURIComponent(location.pathname).match(/\/doi\/(?:[a-z]+\/)?(10\.\d{4,9}\/.+)$/);
  return {href: location.href, title: document.title, doi: m ? m[1] : '', figures: figures, tables: []};
})()''').splitlines()).replace('__RICH__', RICH_TEXT_JS)


def read_once(P, session, url, keys, with_media=True):
    """已接管：读全文和图表清单（Wiley 的图片趁标签页还开着由浏览器下载）。返回 (page, media, 不完整的原因或 None)。"""
    FETCHED.clear()
    EXTRA_MEDIA.clear()
    wait_ready(P, session, keys)
    wait_original(session, url)
    scroll_through(session)
    state = wait_ready(P, session, keys, 30)
    # ACS 读文章区；页面上没有文章区（比如书的章节、摘要页）时用 opencli 的默认范围
    page = extract_all(session, P.extract_scope(session))
    if is_challenge(page['title']) or any(s in page['content'][:1500].lower() for s in CHALLENGE):
        raise NotReady('页面是人机验证')
    chars = state.get('chars') or 0
    if chars >= 10000 and page['total'] < 0.3 * chars:
        # extract 默认读 <main>/<article>；有的网站那是个小部件（ACS 的 <article> 是补充材料预览）
        print('  opencli 读到的范围只有 %d 字符（页面文字 %d）：改读整个 <body>' % (page['total'], chars), flush=True)
        page = extract_all(session, 'body')
    problem = P.incomplete(page, state)
    if problem:                                     # 懒渲染没出来：再滚一遍重读
        print('  %s —— 再滚动一遍重读' % problem, flush=True)
        scroll_through(session)
        time.sleep(3)
        wait_ready(P, session, keys, 30)
        again = extract_all(session, page['selector'])
        if len(again['content']) > len(page['content']):
            page = again
        problem = P.incomplete(page, page_state(session))
    if page_state(session).get('translated'):
        raise NotReady(bn('读取时页面被 {b} 自动翻译了，读到的是译文，已丢弃'))
    content, n_tables, n_drops, table_note = with_tables(P, session, page)
    page = dict(page, content=content, tables=n_tables, drops=n_drops, table_note=table_note)
    page['scripts'], page['maths'] = SCRIPTS['n'], SCRIPTS['math']
    if not with_media:                              # 补上下标：只要全文，不读图
        return page, {}, problem
    media = page_eval(session, P.media_js, timeout=120)
    if not isinstance(media, dict):
        raise RuntimeError('读图表清单没有返回 JSON：%s' % str(media)[:200])
    if EXTRA_MEDIA:
        media['tables'] = list(media.get('tables') or []) + list(EXTRA_MEDIA)
    media_readable(media)
    if P.browser_download and not problem:
        fetch_in_page(session, P.browser_items(P.plan(media, url), url))
    return page, media, problem


def ask(prompt):
    try:
        return input(prompt).strip().lower()
    except EOFError:                                # 没有终端可输入（后台运行）：当作跳过
        print('（没有终端输入，按跳过处理）')
        return 'k'


def read_article(P, url, keys, minutes, interactive=False, started=None, load_timeout=LOAD_TIMEOUT,
                 with_media=True, mine=None, quick=None):
    """接管并读这篇。全文不完整（没有权限或一直没加载出来）时直接跳过（NoFullText），汇总里列出；
    interactive=True（--ask）时改为问你：登录/等加载后回车重读，s 按现状保存，k 跳过。"""
    deadline = time.time() + minutes * 60
    for attempt in range(1, 6):
        session = take_over(P, url, keys, deadline, started if attempt == 1 else None, load_timeout, mine)
        if not session:
            raise Stop('等了 %g 分钟仍没有接管到这篇的标签页' % minutes)
        print(bn(TAKEN_NOTE), flush=True)
        try:
            if quick:                               # 补表题的快读：成了就不整篇读
                try:
                    got = quick(session)
                except Exception as e:
                    print('  快读出错（%s）' % str(e)[:80], flush=True)
                    got = None
                if got is not None:
                    return {'quick': got}, {}, None
                print('  快读对不上，改为整篇读', flush=True)
            page, media, problem = read_once(P, session, url, keys, with_media)
        except NotReady as e:
            print(ACTION + '%s（%s）。如有验证请在标签页里完成，脚本稍后重新接管。' % (e, url), flush=True)
            time.sleep(5)
            continue
        finally:
            release(session)
        if not problem:
            return page, media, None
        if not interactive:
            raise NoFullText(problem, page.get('title') or '')
        answer = ask(ACTION + bn('%s：%s\n  请在 {b} 的这个标签页里登录机构账号或等页面显示全文，然后按回车重读；'
                                 '输入 s 按现在读到的保存，输入 k 跳过这篇：') % (problem, url))
        if answer == 's':
            return page, media, problem
        if answer == 'k':
            raise NoFullText(problem, page.get('title') or '')
        deadline = max(deadline, time.time() + minutes * 60)
    raise Stop('反复接管都没读到全文')


# ---------------------------------------------------------------- 图 --
SD_FILE = re.compile(r'/1-s2\.0-([A-Z0-9]+)-([a-z]+)(\d+)([a-z]?)(_lrg)?\.(jpe?g|png|gif|webp|tiff?)$', re.I)


def sd_high_res(u):
    """ScienceDirect 图片的大图：…-gr1.jpg → …-gr1_lrg.jpg。"""
    if urllib.parse.urlsplit(u).hostname != 'ars.els-cdn.com' or re.search(r'_lrg\.\w+$', u):
        return u
    return re.sub(r'(\.(?:jpe?g|png|gif|webp|tiff?))$', r'_lrg\1', u, flags=re.I)


def sd_images(urls, pii):
    """一个容器里本文的图片文件：{(类别, 编号, 分图字母): [候选地址，大图在前]}。类别 gr=图、ga=图文摘要、sc=Scheme。"""
    found = {}
    for u in urls:
        if urllib.parse.urlsplit(u).hostname != 'ars.els-cdn.com':
            continue
        m = SD_FILE.search(urllib.parse.urlsplit(u).path)
        if not m or (pii and m.group(1).upper() != pii.upper()):
            continue
        found.setdefault((m.group(2).lower(), int(m.group(3)), m.group(4).lower()), []).append(u)
    plan = {}
    for k, us in found.items():
        big = [u for u in us if '_lrg.' in u]
        small = [u for u in us if '_lrg.' not in u]
        plan[k] = list(dict.fromkeys(big + [sd_high_res(u) for u in small] + small))
    return plan


def sd_name(code, num, part):
    base = {'gr': 'fig%d', 'sc': 'scheme%d'}.get(code)
    if base:
        return base % num + part
    if code == 'ga':
        return 'graphical_abstract' + ('' if num == 1 else str(num)) + part
    return '%s%d%s' % (code, num, part)


def sd_heading(code, num):
    return {'gr': 'Figure %d' % num, 'sc': 'Scheme %d' % num, 'ga': 'Graphical abstract'}.get(code, '%s%d' % (code, num))


# ACS 的图多数是 png，有的是 svg（矢量图：m_ 和原图是同一个文件，没有 png 版，原样存 .svg）
ACS_IMG = re.compile(r'/(?:m_)?([^/?#]+)\.(?:png|jpe?g|gif|webp|tiff?|svg)$', re.I)
ACS_LABEL = re.compile(r'\b(fig(?:ure)?|scheme|chart|table)\.?\s*([A-Z]?\d+[A-Za-z]?)', re.I)


def acs_high_res(u):
    """ACS（Silverchair）图片的原图：页面上显示的是 …/m_jf5c12346_0001.png?签名，原图是同一地址去掉 m_
    （签名参数原样留着，实测能下载；「Download to Slide」链接里的也是这个文件）。"""
    p = urllib.parse.urlsplit(u)
    if not (p.hostname or '').endswith('silverchair-cdn.com'):
        return u
    return urllib.parse.urlunsplit(p._replace(path=re.sub(r'/m_([^/]+)$', r'/\1', p.path)))


def acs_images(urls):
    """一个图框里本文的图片文件：{文件名（去掉 m_）: [候选地址，原图在前]}，按出现先后。只认 silverchair-cdn
    上 content_public 里的期刊图片；「Download to Slide」（DownloadImage.aspx，下载到的是 PPT）、
    「View Large」页面不算。"""
    found = {}
    for u in urls:
        p = urllib.parse.urlsplit(u)
        if not (p.hostname or '').endswith('silverchair-cdn.com') or '/content_public/' not in p.path:
            continue
        m = ACS_IMG.search(p.path)
        if m:
            found.setdefault(m.group(1).lower(), []).append(u)
    return {k: list(dict.fromkeys([acs_high_res(u) for u in us] + us)) for k, us in found.items()}


def acs_name(label, i):
    """文件名：Figure 1. → fig1、Scheme 2 → scheme2、Chart 1 → chart1；没有图号用 imageN。"""
    m = ACS_LABEL.search(label or '')
    if not m:
        return 'image%d' % i
    kind = m.group(1).lower()
    return ('fig' if kind.startswith('fig') else kind) + m.group(2).lower()


# Wiley 的图片都在 /cms/asset/<编号>/<文件名> 下：页面上显示的是缩小的 …-m.png，点开看的大图是图片链接和
# data-lg-src 指向的 …-m.jpg（编号不同、文件名相同，只差扩展名）。文件名里带着图号：jfpp12149-fig-0001-m.jpg、
# jfq1674718-fig-0005a-m.png（一个图号分成几张分别显示时带 a、b…）
WILEY_ASSET = re.compile(r'/cms/asset/.+/([^/?#]+?)\.(?:png|jpe?g|gif|webp|tiff?|svg)$', re.I)
WILEY_FILE = re.compile(r'-(fig|sch|scheme|tbl)-?0*(\d+)([a-z]?)(?:-[a-z]{1,2})?$', re.I)
FIG_LABEL = re.compile(r'\b(fig(?:ure)?|scheme|chart|table)\.?\s*([A-Z]?\d+)\s*(?:\(([a-z])\))?', re.I)


def wiley_images(urls):
    """一个图框里的图片文件：{文件名（不带扩展名）: [候选地址，大图在前]}，按出现先后。只认 /cms/asset/ 下的图片；
    「PowerPoint」（/action/downloadFigures，下载到的是 PPT）不算。页面给的顺序是图片链接、data-lg-src、页面上
    显示的小图，所以大图在前。"""
    found = {}
    for u in urls:
        m = WILEY_ASSET.search(urllib.parse.urlsplit(u).path)
        if m:
            found.setdefault(m.group(1).lower(), []).append(u)
    return {k: list(dict.fromkeys(us)) for k, us in found.items()}


def wiley_name(label, stem, i):
    """文件名：Figure 1 → fig1、Figure 5 (a) → fig5a、Scheme 2 → scheme2；图号里没写分图字母时用图片文件名里的
    （fig-0005a）；看不出图号时按文件名里的 fig / sch / tbl 编号，再不行用 imageN。"""
    m, f = FIG_LABEL.search(label or ''), WILEY_FILE.search(stem or '')
    if m:
        kind = m.group(1).lower()
        part = m.group(3) or (f.group(3) if f and f.group(2) == re.sub(r'\D', '', m.group(2)).lstrip('0') else '')
        return ('fig' if kind.startswith('fig') else kind) + m.group(2).lower() + (part or '').lower()
    if f:
        kind = {'fig': 'fig', 'sch': 'scheme', 'scheme': 'scheme', 'tbl': 'table'}[f.group(1).lower()]
        return '%s%d%s' % (kind, int(f.group(2)), f.group(3).lower())
    return 'image%d' % i


def unique_namer():
    """同一篇里文件名不重复：重名的加 _2、_3。"""
    used = set()

    def unique(name):
        n, i = name, 2
        while n in used:
            n, i = '%s_%d' % (name, i), i + 1
        used.add(n)
        return n
    return unique


def numbered(base, n):
    return [base] if n == 1 else ['%s_%d' % (base, i) for i in range(1, n + 1)]


def plan_elsevier(media, url):
    """要下载的图：[{kind, heading, caption, notes, files: [{name, urls}]}]，按页面顺序。"""
    items, unique = [], unique_namer()
    m = re.search(r'/pii/([A-Za-z0-9]+)', url)
    pii = m.group(1) if m else None
    seen, other = set(), 0
    for f in media.get('figures', []):
        imgs = {k: v for k, v in sd_images(f.get('urls', []), pii).items() if k not in seen}
        if not imgs:
            other += bool(f.get('urls')) and not sd_images(f.get('urls', []), pii)
            continue
        seen.update(imgs)
        ks = sorted(imgs)
        items.append({'kind': 'figure', 'heading': f.get('label') or sd_heading(*ks[0][:2]),
                      'caption': f.get('caption', ''), 'notes': [],
                      'files': [{'name': unique(sd_name(*k)), 'urls': imgs[k]} for k in ks]})
    if other:
        print('  跳过 %d 个 <figure>：里面不是本文的图片' % other, flush=True)
    for t in media.get('tables', []):
        imgs = {k: v for k, v in sd_images(t.get('urls', []), pii).items() if k not in seen}
        seen.update(imgs)
        groups = [imgs[k] for k in sorted(imgs)]
        if not groups:                          # 图片不按本文的文件名规则命名：取容器里的图片地址
            groups = [[sd_high_res(u), u] if sd_high_res(u) != u else [u] for u in t.get('urls', [])
                      if re.search(r'\.(jpe?g|png|gif|webp|tiff?)(\?|$)', u, re.I)]
        if not groups:
            continue
        m = re.search(r'Table\s*(\d+)', (t.get('label') or '') + ' ' + (t.get('caption') or ''), re.I)
        base = 'table%s' % m.group(1) if m else 'table'
        names = [base] if len(groups) == 1 else ['%s_%d' % (base, i) for i in range(1, len(groups) + 1)]
        items.append({'kind': 'table', 'heading': t.get('label') or ('Table %s' % m.group(1) if m else 'Table'),
                      'caption': t.get('caption', ''), 'notes': t.get('notes') or [],
                      'files': [{'name': unique(n), 'urls': g} for n, g in zip(names, groups)]})
    return items


def plan_acs(media, url, images=None):
    """images：从图框的地址里挑出本文图片的函数（默认 acs_images；Silverchair 平台的其他出版商用 sc_images）。"""
    images = images or acs_images
    items, unique = [], unique_namer()
    seen, other = set(), 0
    for i, f in enumerate(media.get('figures', []), 1):
        imgs = {k: v for k, v in images(f.get('urls', [])).items() if k not in seen}
        if not imgs:
            other += bool(f.get('urls')) and not images(f.get('urls', []))
            continue
        seen.update(imgs)
        label = ' '.join((f.get('label') or '').split())
        if f.get('ga'):                         # ACS 页面上叫 Visual Abstract；标题沿用 Elsevier 版的 Graphical abstract
            base, heading, caption = 'graphical_abstract', 'Graphical abstract', f.get('caption', '')
        else:
            base = acs_name(label, i)
            heading = label.rstrip('.').strip() or base
            caption = ' '.join(x for x in (label, f.get('caption', '')) if x)   # 页面上显示的「Figure 1. 图注」
        items.append({'kind': 'figure', 'heading': heading, 'caption': caption, 'notes': [],
                      'files': [{'name': unique(n), 'urls': u}
                                for n, u in zip(numbered(base, len(imgs)), imgs.values())]})
    if other:
        print('  跳过 %d 个图框：里面不是本文的图片' % other, flush=True)
    for t in media.get('tables', []):
        imgs = {k: v for k, v in images(t.get('urls', [])).items() if k not in seen}
        seen.update(imgs)
        if not imgs:
            continue
        label = ' '.join((t.get('label') or '').split())
        m = re.search(r'Table\s*([A-Z]?\d+)', label + ' ' + (t.get('caption') or ''), re.I)
        base = 'table%s' % m.group(1).lower() if m else 'table'
        items.append({'kind': 'table',
                      'heading': label.rstrip('.').strip() or ('Table %s' % m.group(1) if m else 'Table'),
                      'caption': ' '.join(x for x in (label, t.get('caption', '')) if x),
                      'notes': t.get('notes') or [],
                      'files': [{'name': unique(n), 'urls': u}
                                for n, u in zip(numbered(base, len(imgs)), imgs.values())]})
    return items


def plan_wiley(media, url):
    items, unique = [], unique_namer()
    seen = set()
    for i, f in enumerate(media.get('figures', []), 1):
        imgs = {k: v for k, v in wiley_images(f.get('urls', [])).items() if k not in seen}
        if not imgs:
            continue
        seen.update(imgs)
        label = ' '.join((f.get('label') or '').split())
        if f.get('ga'):
            base, heading, caption = 'graphical_abstract', 'Graphical abstract', f.get('caption', '')
        else:
            base = wiley_name(label, next(iter(imgs)), i)
            heading = label.rstrip('.').strip() or base
            caption = ' '.join(x for x in (label, f.get('caption', '')) if x)   # 页面上显示的「Figure 1 图注」
        items.append({'kind': 'figure', 'heading': heading, 'caption': caption, 'notes': [],
                      'files': [{'name': unique(n), 'urls': u}
                                for n, u in zip(numbered(base, len(imgs)), imgs.values())]})
    for t in media.get('tables', []):
        imgs = {k: v for k, v in wiley_images(t.get('urls', [])).items() if k not in seen}
        seen.update(imgs)
        if not imgs:
            continue
        label = ' '.join((t.get('label') or '').split())
        m = re.search(r'Table\s*([A-Z]?\d+)', label + ' ' + (t.get('caption') or ''), re.I)
        base = 'table%s' % m.group(1).lower() if m else 'table'
        items.append({'kind': 'table',
                      'heading': label.rstrip('.').strip() or ('Table %s' % m.group(1) if m else 'Table'),
                      'caption': ' '.join(x for x in (label, t.get('caption', '')) if x),
                      'notes': t.get('notes') or [],
                      'files': [{'name': unique(n), 'urls': u}
                                for n, u in zip(numbered(base, len(imgs)), imgs.values())]})
    return items


# Silverchair 的「Download slide」链接：…/DownloadFile/DownloadImage.aspx?image=<原图地址，带它自己的签名>&sec=…
SC_DOWNLOAD = re.compile(r'/DownloadImage\.aspx\?image=(https?://.+?)(?=&sec=|&ar=|&xsltPath=|&imagename=|&siteId=|$)', re.I)


def sc_images(urls):
    """Silverchair 平台的图片：同 acs_images，只是 content_public 不分大小写（OUP 写作 Content_public）。
    OUP、RSC 的签名连着文件名：去掉 m_ 的地址签名对不上（403），原图要用「Download slide」链接里套着的那个地址
    （实测 OUP 的 Figure 1：原图 78 KB，m_ 的 22 KB），排在最前；去掉 m_ 的、页面上显示的 m_ 留作后备。"""
    found, slides = {}, {}
    for u in urls:
        m = SC_DOWNLOAD.search(u)
        if m:
            u = m.group(1)
        p = urllib.parse.urlsplit(u)
        if not (p.hostname or '').endswith('silverchair-cdn.com') or '/content_public/' not in p.path.lower():
            continue
        k = ACS_IMG.search(p.path)
        if k:
            (slides if m else found).setdefault(k.group(1).lower(), []).append(u)
    return {k: list(dict.fromkeys(slides.get(k, []) + [acs_high_res(u) for u in us] + us)) for k, us in found.items()}


# 图注、正文里的小图（sc_images 认出的文件名，不带扩展名、去掉 m_）：图例色块 …-gra-0001（Wiley 系的 IJFS 等）、
# 公式 …_m0001（转过来的老 BBB）、插图 …_ilg0001
INLINE_IMG = re.compile(r'(?:-gra-\d{3,4}|_m\d{3,4}|_ilg\d{3,4})$', re.I)


def plan_silverchair(media, url):
    """Silverchair 平台（OUP、RSC、Emerald …）：同 ACS 的图框和命名；图文摘要只写了标题「Graphical Abstract」的也算。
    图注、正文里的小图（INLINE_IMG：图例色块、公式、插图）不算本文的图；整个图框都是这种小图的（公式编号「(1)」的
    公式图）整个不算。"""
    figures = []
    for f in media.get('figures', []):
        urls = f.get('urls') or []
        own = [u for u in urls if not any(INLINE_IMG.search(k) for k in sc_images([u]))]
        if f.get('ga') or not sc_images(urls):
            figures.append(f)
        elif sc_images(own):
            figures.append(dict(f, urls=own))
    media = dict(media, figures=figures)
    for f in media.get('figures', []):
        if not f.get('ga') and re.match(r'\s*(graphical|visual|toc)\s+abstract', f.get('label') or '', re.I):
            f['ga'] = True
    return plan_acs(media, url, sc_images)


def generic_candidates(urls):
    """通用读法的图片候选地址：常见的「缩略图 → 原图」换法排在前面，原来的地址留作后备。Springer Nature 的
    media.springernature.com/lw685/… → /full/…；Frontiers、MDPI 的缩图服务（/api/ipx/…/原图地址、/cdn-cgi/image/…/原图地址）
    → 里面套着的原图地址；Silverchair（OUP、RSC、Emerald …）去掉文件名前的 m_；去掉 ?as=webp。"""
    out = []
    for u in urls:
        p = urllib.parse.urlsplit(u)
        host = (p.hostname or '').lower()
        if host == 'media.springernature.com' and re.match(r'^/[a-z]+\d+/', p.path):
            out.append(urllib.parse.urlunsplit(p._replace(path=re.sub(r'^/[a-z]+\d+/', '/full/', p.path), query='')))
        m = re.search(r'/(?:api/ipx|cdn-cgi/image)/[^/]+/(https?://.+)$', u)
        if m:
            inner = m.group(1)
            out += ([re.sub(r'\.webp$', '.jpg', inner)] if inner.lower().endswith('.webp') else []) + [inner]
        if host.endswith('silverchair-cdn.com'):
            out.append(acs_high_res(u))
        if 'as=webp' in p.query:
            out.append(urllib.parse.urlunsplit(p._replace(query=re.sub(r'&?as=webp', '', p.query).lstrip('&'))))
        out.append(u)
    return list(dict.fromkeys(out))


def plan_generic(media, url):
    """通用读法：页面上每个图框里的图（只取图片地址，不去打开「view large」页面）。"""
    items, unique = [], unique_namer()
    for i, f in enumerate(media.get('figures', []), 1):
        if not f.get('urls'):
            continue
        m = re.search(r'\b(fig(?:ure)?|scheme|chart|table)\.?\s*(S?\d+[A-Za-z]?)', '%s %s' % (f.get('label'), f.get('alt')), re.I)
        if m:
            kind = m.group(1).lower()
            base = ('fig' if kind.startswith('fig') else kind) + m.group(2).lower()
        else:
            base = 'image%d' % i
        items.append({'kind': 'figure', 'heading': f.get('label') or base, 'caption': f.get('caption', ''),
                      'notes': [], 'files': [{'name': unique(base), 'urls': generic_candidates(f['urls'])}]})
    return items


def mdpi_candidates(urls):
    """MDPI：www.mdpi.com 上的图片不让脚本下载（403），同一张图在 pub.mdpi-res.com 上（网页自己也从那里加载）。"""
    out = []
    for u in urls:
        p = urllib.parse.urlsplit(u)
        if (p.hostname or '').lower() in ('www.mdpi.com', 'mdpi.com') and '/article_deploy/' in p.path:
            out.append(urllib.parse.urlunsplit(p._replace(netloc='pub.mdpi-res.com')))
        out.append(u)
    return generic_candidates(out)


def plan_known(media, url, candidates=generic_candidates):
    """新写的几家（Springer、MDPI、T&F）：每个图框里的图，按「Fig. 1」「Figure 2」「Scheme 1」起名（认不出的
    image1 …）；图注写成页面上显示的「Fig. 1 图注」（图注里本来就以标签开头的不再加）。candidates：候选地址排序。"""
    items, unique = [], unique_namer()
    for i, f in enumerate(media.get('figures', []), 1):
        if not f.get('urls'):
            continue
        label = ' '.join((f.get('label') or '').split())
        caption = (f.get('caption') or '').strip()
        m = re.search(r'\b(fig(?:ure)?|scheme|chart)\.?\s*(S?\d+[A-Za-z]?)',
                      '%s %s' % (label, f.get('alt') or ''), re.I) or re.match(r'\s*(fig(?:ure)?|scheme|chart)\.?\s*(S?\d+[A-Za-z]?)\b', caption, re.I)
        if f.get('ga'):
            base, label = 'graphical_abstract', 'Graphical abstract'
        elif m:
            kind = m.group(1).lower()
            base = ('fig' if kind.startswith('fig') else kind) + m.group(2).lower()
            label = label or m.group(0).strip()
        else:
            base = 'image%d' % i
        if label and not f.get('ga') and not caption.lower().startswith(label.rstrip('.').lower()):
            caption = ' '.join(x for x in (label, caption) if x)
        items.append({'kind': 'figure', 'heading': label.rstrip('.').strip() or base, 'caption': caption,
                      'notes': [], 'files': [{'name': unique(base), 'urls': candidates(f['urls'])}]})
    for t in media.get('tables', []):              # 图片版表格（同 Elsevier：table1.png，表题和表下注写进 figure_markdown.md）
        if not t.get('urls'):
            continue
        label = ' '.join((t.get('label') or '').split())
        m = re.search(r'Table\s*([A-Z]?\d+[a-z]?)', label + ' ' + (t.get('caption') or ''), re.I)
        base = 'table%s' % m.group(1).lower() if m else 'table'
        items.append({'kind': 'table', 'heading': label.rstrip('.').strip() or ('Table %s' % m.group(1) if m else 'Table'),
                      'caption': ' '.join(x for x in (label, t.get('caption', '')) if x), 'notes': t.get('notes') or [],
                      'files': [{'name': unique(base), 'urls': candidates(t['urls'])}]})
    return items


MAGIC = ((b'\xff\xd8\xff', '.jpg'), (b'\x89PNG\r\n\x1a\n', '.png'), (b'GIF8', '.gif'),
         (b'II*\x00', '.tif'), (b'MM\x00*', '.tif'))


def image_ext(data, svg=True):
    for sig, ext in MAGIC:
        if data.startswith(sig):
            return ext
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return '.webp'
    if svg:                                         # ACS 等的矢量图（Elsevier 版不收 svg）
        head = data[:2048].lstrip(b'\xef\xbb\xbf \t\r\n').lower()
        if head.startswith((b'<?xml', b'<svg')) and b'<svg' in head and b'<html' not in head:
            return '.svg'
    return None


# Wiley 的图片：读全文时趁标签页还开着，由浏览器在页面里下载好（脚本自己请求 Wiley 会被 Cloudflare 拦下，403），
# 存在这里，下面的 download 直接用；浏览器没下到的记下原因。每篇开始读时清空。
FETCHED, FETCH_ERRORS = {}, {}
BROWSER_FETCH_JS = ("(async () => { try { const r = await fetch(%s, {credentials: 'include'}); "
                    "if (!r.ok) return {status: r.status}; const b = new Uint8Array(await r.arrayBuffer()); let s = ''; "
                    "for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000)); "
                    "return {status: r.status, b64: btoa(s)}; } catch (e) { return {error: String(e)}; } })()")


def fetch_in_page(session, items):
    """在文章页里让浏览器按顺序试每张图的候选地址，下到的是图片就停。只是同一个网站上的图片请求，
    和页面自己加载图片一样，不绕过任何验证。"""
    FETCH_ERRORS.clear()
    for item in items:
        for f in item['files']:
            for u in f['urls']:
                try:
                    r = page_eval(session, BROWSER_FETCH_JS % json.dumps(u), timeout=180)
                except Exception as e:
                    r = {'error': str(e)[:100]}
                r = r if isinstance(r, dict) else {'error': str(r)[:100]}
                data = base64.b64decode(r['b64']) if r.get('b64') else b''
                if data and image_ext(data):
                    FETCHED[u] = data
                    break
                if data:
                    FETCH_ERRORS[u] = '浏览器下载到的不是图片（%d 字节）' % len(data)
                elif r.get('status'):
                    FETCH_ERRORS[u] = '浏览器下载返回 HTTP %s' % r['status']
                else:
                    FETCH_ERRORS[u] = '浏览器下载出错：%s' % (r.get('error') or '没有返回')


def download(P, urls):
    """按顺序试候选地址，返回 (字节, 扩展名, 用到的地址) 或 (None, None, 失败原因)。浏览器在页面里下好的直接用；
    Wiley 的地址只用浏览器下好的（脚本自己请求会被 Cloudflare 拦下）。"""
    errors = []
    for u in urls:
        if u in FETCHED:
            return FETCHED[u], image_ext(FETCHED[u], P.svg), u
        if P.browser_only(u):
            errors.append('%s：%s' % (u.rsplit('/', 1)[-1][:60], FETCH_ERRORS.get(u, '浏览器没有下载这个地址')))
            continue
        for attempt in range(2 if P.retry_timeout else 1):
            try:
                req = urllib.request.Request(u, headers={'User-Agent': B['ua'] % UA_OS, 'Accept': 'image/*,*/*;q=0.8'})
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
                ext = image_ext(data, P.svg)
                if not ext:
                    raise ValueError('下载到的不是图片（%d 字节）' % len(data))
                return data, ext, u
            except Exception as e:
                error = e
                if not timed_out(e):                # 超时（连接卡住）才换个新连接再试一次
                    break
        errors.append('%s：%s' % (u.rsplit('/', 1)[-1][:60], str(error)[:100]))
    return None, None, '；'.join(errors) or '没有图片地址'


def timed_out(e):
    return (isinstance(e, TimeoutError) or isinstance(getattr(e, 'reason', None), TimeoutError)
            or 'timed out' in str(e).lower())


def fetch_images(P, items):
    for item in items:
        for f in item['files']:
            data, ext, info = download(P, f['urls'])
            f.update(data=data, file=(f['name'] + ext) if data else None, source=info if data else None,
                     error=None if data else info)
            # 只显示文件名（ACS 的图片地址后面带一长串签名参数）
            print('  %-22s %s' % (f['name'], '%7.0f KB  %s' % (len(data) / 1024, info.split('?')[0].rsplit('/', 1)[-1])
                                   if data else '下载失败：' + info), flush=True)


# ---------------------------------------------------------------- 输出 --
REFS_HEADING = re.compile(r'^#{1,3} (?:References?|Reference list|Bibliography|Literature cited)[ \t]*$', re.I | re.M)


# 没有常见的参考文献标题时，「## Resources」也算（用户 2026-10-07：afres.2026.102203 的参考文献就叫这个）
REFS_FALLBACK = re.compile(r'^#{1,3} Resources[ \t]*$', re.I | re.M)

# 参考文献标题：Wiley 有三种写法——「## References」「## [References](#)」，和一行空的「##」下面（隔空行）写
# References / REFERENCES
REFS_WORDS = r'(?:References?|Reference list|Bibliography|Literature cited)'
WILEY_REFS_HEADING = re.compile(r'^#{1,3}(?: \[?%s(?:\]\([^)\n]*\))?|[ \t]*\n(?:[ \t]*\n)*%s)[ \t]*$'
                          % (REFS_WORDS, REFS_WORDS), re.I | re.M)


def drop_references(text, refs=REFS_HEADING):
    """去掉参考文献：从最后一个参考文献标题起到末尾（其后是网页附带的推荐文章、被引、统计）。
    返回 (全文, 去掉的字符数)；找不到标题、或标题前几乎没有正文时不切，返回去掉 0 字符。"""
    heads = list(refs.finditer(text)) or list(REFS_FALLBACK.finditer(text))
    if not heads or heads[-1].start() < MIN_PAGE_CHARS:
        return text, 0
    kept = text[:heads[-1].start()].rstrip() + '\n'
    return kept, len(text) - len(kept)


def plain_title(title):
    """网页标题里的标记去掉（Wiley 的标题带 <i>、<fi>、<fc>、<sub>2</sub>、&amp; 等）：上下标里只有数字和 + − = ( ) 的
    写成 Unicode（TiO₂），其余上下标照流水线写成 _x / ^x；别的标签只留文字。用户 2026-10-09。"""
    t = title or ''
    for tag, table, mark in (('sub', SUB_DIGITS, '_'), ('sup', SUP_DIGITS, '^')):
        t = re.sub(r'<%s\b[^>]*>([^<]*)</%s>' % (tag, tag),
                   lambda m: m.group(1).translate(table) if m.group(1) and all(c in SCRIPT_CHARS for c in m.group(1))
                   else mark + m.group(1), t, flags=re.I)
    t = re.sub(r'<[^>]+>', '', t)
    return html.unescape(t).strip()


def figure_markdown(page, items, url, doi):
    out = ['# ' + (plain_title(page['title']) or doi or url), '']
    if doi:
        out.append('DOI: https://doi.org/%s  ' % doi)
    out += ['网页: %s' % (page['url'] or url), '']
    if not items:
        out += ['（页面上没有找到图或图片版表格）', '']
    for item in items:
        out += ['## %s%s' % (item['heading'], '（图片版表格）' if item['kind'] == 'table' else ''), '']
        for f in item['files']:
            if f.get('file'):
                out += ['![%s](%s)' % (item['heading'], f['file']), '']
            else:
                out += ['（图片下载失败，原图地址：%s）' % f['urls'][0], '']
        if item['caption']:
            out += [item['caption'], '']
        for note in item['notes']:
            out += [note, '']
    return '\n'.join(out)


def write_paper(root, page, items, url, doi):
    os.makedirs(root, exist_ok=True)
    # newline=''：换行符原样写出，不在 Windows 上改成 \r\n
    with io.open(os.path.join(root, '全文.md'), 'w', encoding='utf-8', newline='') as fh:
        fh.write(page['content'])
    # 图片和图注单独放在子文件夹 figure 里（用户 2026-09-29）；figure_markdown.md 里的图片链接是同文件夹的相对路径
    fig_dir = os.path.join(root, FIGURE_DIR)
    os.makedirs(fig_dir, exist_ok=True)
    for item in items:
        for f in item['files']:
            if f.get('data'):
                with open(os.path.join(fig_dir, f['file']), 'wb') as fh:
                    fh.write(f['data'])
    with io.open(os.path.join(fig_dir, 'figure_markdown.md'), 'w', encoding='utf-8', newline='') as fh:
        fh.write(figure_markdown(page, items, url, doi))


# ============================== 出版商（续） ==============================
class Publisher:
    """一家出版商的读法。下面每一项都是原来那家的单出版商脚本里的写法。"""
    key = ''                # 简称：--publisher、台账状态 not_<key>
    name = ''
    known = True            # 有专门读法（False：通用读法）
    meta_doi = False        # 认文章也看页面的 citation_doi（跳转后的地址里没有 DOI）
    scope = None            # opencli extract 读的范围（页面上有这块时）
    drop = None             # 页面里不显示、opencli 却会再读一遍的块（CSS 选择器）
    drop_note = ''          # 去掉它们时的说明（%d 是块数）
    table_fail = '表格以外的文字和 opencli extract 对不上，没有重建表格，全文按 opencli 原样保存'
    media_js = ''
    refs = REFS_HEADING
    svg = True              # 图片可以是 svg
    browser_download = False   # 图片由浏览器在页面里下载
    # 下面几项是 2026-10-22 新写的几家用的（Elsevier、ACS、Wiley 都是默认值，照原样）
    find_new = False        # 标签栏上的标题认不出这家时，也认打开时新出现的那个标签页（通用读法、MDPI …）
    scopes = ()             # 按顺序取页面上有的第一个作 opencli extract 的范围（都没有用默认范围）
    junk = None             # 正文中间网页插进来的推荐栏（页面上显示；CSS 选择器）：去掉，核对时还原
    pre_js = ''             # 把不在正文原位的表放回原位（见 PLACE_JS）
    async_hook = False      # pre_js 要等网页请求（extract 脚本改成 async）
    placed_from = ''        # 放回原位的表原来在哪（屏幕上的说明）
    ext_fail = '%d 张表没能放回原位：%s'
    retry_timeout = False   # 图片地址下载超时（连接卡住）时换个新连接再试一次，再退到下一个候选（缩略图）

    def extract_scope(self, session):
        """opencli extract 读的范围：ACS 是文章区（页面上有才用），新写的几家按 scopes，其余 None（默认范围）。"""
        if self.scopes:
            try:
                found = page_eval(session, SCOPE_JS % json.dumps(list(self.scopes)), timeout=30)
            except Exception:
                found = None
            return found if isinstance(found, str) and found else None
        return self.scope if self.scope and page_state(session).get('scope') else None

    def article_url(self, url, doi):
        """在浏览器里打开的地址：默认就是 doi.org 解析出的那个。"""
        return url

    def small_page(self, state):
        """字数不到 MIN_PAGE_CHARS 也算已显示这篇（接着读、判没有全文），不当作还在加载。state 是 page_state。"""
        return False

    def owns(self, url):
        return False

    def out_dir(self, url):
        return papers_dir(self.key)

    def tab_title(self, t):
        """标签栏上这个标题是这家的文章页（或验证页）吗。t 是小写。"""
        return is_challenge(t)

    def loading(self, t):
        """还在加载、标题是地址的样子。t 是小写。"""
        return t.startswith('doi.org')

    def ours(self, t):
        """脚本打开的这篇的标签页可能的样子（关标签页时找它）。t 是小写。"""
        return self.tab_title(t) or t in UNTITLED or t.startswith(('doi.org', 'http://', 'https://'))

    def incomplete(self, page, state):
        """全文不完整的原因；看起来完整时返回 None。state 是 page_state。"""
        text, n = page['content'], len(page['content'])
        if n < MIN_BODY_CHARS and '## References' not in text:
            return '只读到 %d 字符，像是页面没加载完' % n
        return None

    def plan(self, media, url):
        return plan_generic(media, url)

    def browser_only(self, u):
        """这个图片地址只能由浏览器下载（脚本自己请求会被拦下）。"""
        return False

    def browser_items(self, items, url):
        """交给浏览器在页面里下载的图（browser_download 时）。"""
        return items

    def label(self, url):
        return self.name

    def note(self, url):
        """台账里给这家每篇都带上的提醒（有专门读法的没有）。"""
        return ''

    def extra_notes(self, text):
        """看读到的全文（切参考文献前）还要提醒什么。"""
        return []

    def extra_keys(self, url):
        """除了 DOI 和地址路径，还认这篇文章的标识（matches 按地址里有没有它们认）。"""
        return []

    def not_mine(self, url):
        return '不是 %s 的文章：%s' % (self.name, url)


class Elsevier(Publisher):
    key, name = 'elsevier', 'Elsevier'
    media_js = SD_MEDIA_JS
    svg = False

    def owns(self, url):
        return 'sciencedirect.com' in (url or '')

    def tab_title(self, t):
        return 'sciencedirect' in t or is_challenge(t)

    def loading(self, t):
        return t.startswith(('doi.org', 'linkinghub'))

    def ours(self, t):
        return (self.tab_title(t) or t in UNTITLED
                or t.startswith(('www.sciencedirect.com', 'sciencedirect.com', 'doi.org', 'linkinghub', 'http://', 'https://')))

    def incomplete(self, page, state):
        text, n = page['content'], len(page['content'])
        if '/abs/pii/' in (state.get('href') or '').lower():
            return '打开的是摘要页（/abs/），没有全文权限'
        if n < PAYWALL_CHARS and any(s in text for s in ('Get full-text access', 'institutionLogin',
                                                           'Access through your institution', 'Purchase PDF')):
            return '只读到 %d 字符，页面带「获取全文 / 通过机构访问」提示，像是没有全文权限' % n
        if n < MIN_BODY_CHARS and '## References' not in text:
            return '只读到 %d 字符，像是页面没加载完' % n
        return None

    def plan(self, media, url):
        return plan_elsevier(media, url)

    def not_mine(self, url):
        return '不是 ScienceDirect（Elsevier）的文章：%s' % url


class ACS(Publisher):
    """ACS 的期刊（J. Agric. Food Chem.、ACS Food Sci. Technol. …）在 Silverchair 平台上：DOI 先到
    pubs.acs.org/doi/10.1021/…，再跳到 pubs.acs.org/<刊名缩写>/article/卷/期/页/编号/标题，跳完的地址里没有 DOI，
    所以认文章看页面里的 <meta name="citation_doi">。没有全文权限时 ACS 会把文章页转到摘要页
    （地址带 ?redirectedFrom=fulltext，页面写着 You do not currently have access to this …）。"""
    key, name = 'acs', 'ACS'
    meta_doi = True
    scope = ACS_SCOPE
    drop = '.fig-modal'
    drop_note = '，去掉了 %d 个页面上不显示的图弹窗副本（重复的图和图注）'
    table_fail = ('表格以外的文字和 opencli extract 对不上，没有重建表格、没有去掉图的弹窗副本，'
                  '全文按 opencli 原样保存')
    media_js = ACS_MEDIA_JS

    def owns(self, url):
        return host_of(url) == ACS_HOST

    def tab_title(self, t):
        """ACS 的标签页：标题是「文章题目 | 刊名 | ACS Publications」，加载中是地址；或者验证页。"""
        return 'acs publications' in t or t.startswith(ACS_HOST) or is_challenge(t)

    def loading(self, t):
        return t.startswith(('doi.org', ACS_HOST))

    def ours(self, t):
        return self.tab_title(t) or t in UNTITLED or t.startswith((ACS_HOST, 'doi.org', 'http://', 'https://'))

    def incomplete(self, page, state):
        text, n = page['content'], len(page['content'])
        href = state.get('href')
        h = (href or '').lower()
        if 'redirectedfrom=fulltext' in h or re.search(r'/[a-z]+-abstract/', h):
            return '打开的是摘要页（ACS 没有全文权限时转到这里：%s），没有全文' % urllib.parse.urlsplit(href).path[:60]
        hit = next((s for s in NO_ACCESS if s in text), None)
        if hit:
            return '页面写着「%s…」，网页上没有全文（没有权限或只有 PDF）' % hit
        if n < MIN_BODY_CHARS and '## References' not in text:
            return '只读到 %d 字符，像是页面没加载完' % n
        return None

    def plan(self, media, url):
        return plan_acs(media, url)

    def not_mine(self, url):
        return '不是 ACS（pubs.acs.org）的文章：%s' % url


class Wiley(Publisher):
    """Wiley 的期刊都在 Wiley Online Library 上（onlinelibrary.wiley.com，有的带学会子域名：ift.、scijournals.、
    aocs.、aiche.、efsa. …）：DOI 跳到 <子域名>onlinelibrary.wiley.com/doi/<DOI>，地址里就有 DOI。转到 Wiley 的
    老 Hindawi（10.1155）和 EFSA（10.2903）的 DOI 先到 www.hindawi.com / doi.wiley.com，由浏览器再跳到 Wiley。
    Wiley 的网站对脚本自己发的请求一律回 Cloudflare 验证（403），所以图片也在已打开的文章页里由浏览器下载
    （和页面自己加载图片是同一个请求，不绕过任何验证）。网页上没有正文（页面里没有 .article-section__full：
    老文章只有 PDF，或没有全文权限、只显示摘要）记为没有全文。"""
    key, name = 'wiley', 'Wiley'
    meta_doi = True
    drop = '.mobile-authors'
    drop_note = '，去掉了 %d 处页面上不显示的手机版作者列表（重复的作者和单位）'
    table_fail = ('表格以外的文字和 opencli extract 对不上，没有重建表格、没有去掉隐藏的手机版作者列表，'
                  '全文按 opencli 原样保存')
    media_js = WILEY_MEDIA_JS
    refs = WILEY_REFS_HEADING
    browser_download = True

    def owns(self, url):
        return is_wiley(url)

    def tab_title(self, t):
        """Wiley 的标签页：标题是「文章题目 - 第一作者 - 年份 - 刊名 - Wiley Online Library」，加载中是地址；或者验证页。"""
        return 'wiley online library' in t or wiley_loading(t) or is_challenge(t)

    def loading(self, t):
        return wiley_loading(t)

    def ours(self, t):
        return self.tab_title(t) or t in UNTITLED or wiley_loading(t) or t.startswith(('http://', 'https://'))

    def incomplete(self, page, state):
        text, n = page['content'], len(page['content'])
        if state.get('full') is False:
            return '网页上只有摘要、没有正文（老文章只有 PDF，或没有全文权限）'
        if n < MIN_BODY_CHARS and not WILEY_REFS_HEADING.search(text):
            return '只读到 %d 字符，像是页面没加载完' % n
        return None

    def plan(self, media, url):
        return plan_wiley(media, url)

    def browser_only(self, u):
        return is_wiley(u)

    def not_mine(self, url):
        return '不是 Wiley（Wiley Online Library）的文章：%s' % url


# 还没有专门读法的出版商：按网址认出是哪家，存到 <简称>_papers（DOI按出版商-119334 里常见的几家先起好名字，
# 其余用网址的主域名）。
GENERIC_SITES = (('mdpi.com', 'mdpi', 'MDPI'), ('springer.com', 'springer_nature', 'Springer Nature'),
                 ('nature.com', 'springer_nature', 'Springer Nature'),
                 ('biomedcentral.com', 'springer_nature', 'Springer Nature'),
                 ('tandfonline.com', 'taylor_francis', 'Taylor & Francis'), ('frontiersin.org', 'frontiers', 'Frontiers'),
                 ('rsc.org', 'rsc', 'RSC'), ('oup.com', 'oxford', 'Oxford University Press'),
                 ('sagepub.com', 'sage', 'SAGE'), ('cambridge.org', 'cambridge', 'Cambridge University Press'),
                 ('degruyter.com', 'de_gruyter', 'De Gruyter'), ('degruyterbrill.com', 'de_gruyter', 'De Gruyter'),
                 ('emerald.com', 'emerald', 'Emerald'), ('iop.org', 'iop', 'IOP Publishing'),
                 ('jstage.jst.go.jp', 'jstage', 'J-STAGE'), ('benthamscience.com', 'bentham', 'Bentham Science'),
                 ('brill.com', 'brill', 'Brill'), ('edpsciences.org', 'edp', 'EDP Sciences'),
                 ('aimspress.com', 'aims', 'AIMS Press'), ('pensoft.net', 'pensoft', 'Pensoft'),
                 ('imrpress.com', 'imr', 'IMR Press'), ('maxapress.com', 'maxapress', 'Maximum Academic Press'),
                 ('sciopen.com', 'tsinghua', 'Tsinghua University Press'), ('akjournals.com', 'akademiai', 'Akademiai Kiado'),
                 ('agriculturejournals.cz', 'czech_academy', 'Czech Academy of Agricultural Sciences'),
                 ('codonpublications.com', 'codon', 'Codon Publications'), ('scielo', 'scielo', 'SciELO'))


# 通用读法认「有没有全文」：正文小节的标题（Introduction / Methods / Results …，常见的几种语言）。一个都没有又很短，
# 或者页面写着要买 / 要登录才能看而小节最多一个，就是只有摘要（或只给 PDF）。
BODY_WORDS = ('introduc', 'background', 'material', 'method', 'experiment', 'result', 'discuss', 'conclu',
              'einleitung', 'methode', 'ergebnis', 'diskussion', 'schlussfolger',
              'введение', 'метод', 'материал', 'результат', 'обсужден', 'заключен', 'вывод', 'вступ', 'висновк',
              'úvod', 'metod', 'výsled', 'diskus', 'závěr', 'wstęp', 'wynik', 'wnioski', 'bevezet', 'anyag', 'eredm',
              'resultad', 'discusión', 'discussão', 'conclus', 'métod', 'risultat', 'uvod', 'rezultat', 'zaključ',
              'concluzi', 'pendahuluan', 'hasil', 'kesimpulan', 'bahan',
              '引言', '前言', '材料', '方法', '结果', '讨论', '结论', 'はじめに', '緒言', '結果', '考察', '結論',
              '서론', '재료', '방법', '결과', '고찰', '결론')
BODY_HEADING = re.compile(r'^#{1,4}[ \t]+[^\n]{0,20}?(?:%s)' % '|'.join(map(re.escape, BODY_WORDS)), re.I | re.M)
GENERIC_NO_ACCESS = ('Get full-text access', 'Get full access to this article', 'institutionLogin',
                     'Access through your institution', 'Purchase PDF', 'Buy article', 'Buy this article',
                     'Purchase this article', 'Rent this article', 'Log in via your institution', 'Access options',
                     'You do not have access', 'You do not currently have access', 'Subscribe to journal')
# 通用读法的参考文献标题：Wiley 那几种写法（## References、## [References](#)、一行空的 ## 下面写 References），
# 前面可以带编号，再加几种常见语言
GENERIC_REFS_WORDS = (r'(?:References?|Reference list|Bibliography|Literature cited|Literature|Works cited|'
                      r'Referencias(?: bibliográficas)?|Referências(?: bibliográficas)?|Bibliografía|Bibliografia|'
                      r'Literatur(?:verzeichnis)?|Литература|Список литературы|Список використаних джерел|Література|'
                      r'Literatura|Seznam literatury|Daftar Pustaka|Kaynaklar|参考文献|引用文献|참고문헌)')
GENERIC_REFS_PATTERN = r'^#{1,4}(?:[ \t]+(?:\d+\.?[ \t]*)?\**\[?%s\]?(?:\([^)\n]*\))?\**:?|[ \t]*\n(?:[ \t]*\n)*\**%s\**)[ \t]*$'
GENERIC_REFS = re.compile(GENERIC_REFS_PATTERN % (GENERIC_REFS_WORDS, GENERIC_REFS_WORDS), re.I | re.M)
# 新写的几家：再加 RSC 的「Notes and references」
NEW_REFS_WORDS = r'(?:Notes and references|' + GENERIC_REFS_WORDS[len('(?:'):]
NEW_REFS = re.compile(GENERIC_REFS_PATTERN % (NEW_REFS_WORDS, NEW_REFS_WORDS), re.I | re.M)


class Generic(Publisher):
    """通用读法（还没有专门写过的出版商）：opencli 的默认范围、通用的没有全文判断、通用的图框规则，图片先由浏览器
    在页面里下载（只下同一网站上的），下不到再由脚本下载。存到 <出版商>_papers，台账里带提醒，方便以后核对、补专门读法。"""
    key, name = 'generic', '其他出版商'
    known = False
    find_new = True
    meta_doi = True
    media_js = GENERIC_MEDIA_JS
    refs = GENERIC_REFS
    browser_download = True

    def label(self, url):
        return '%s（还没有专门读法，用通用读法）' % self.site(url)[1]

    def note(self, url):
        return '通用读法（%s 还没有专门的读法），请核对' % self.site(url)[1]

    def extra_notes(self, text):
        if not BODY_HEADING.search(text):
            return ['没认出正文小节的标题（Introduction / Methods / Results …），可能只有摘要，请核对']
        return []

    def extra_keys(self, url):
        """通用读法：打开的那个网站上的页面都算这篇（不少网站跳转后的地址里没有 DOI，页面上也没写 citation_doi）。"""
        host = host_of(url)
        return ['//%s/' % host.upper()] if host and host != 'doi.org' else []

    def browser_items(self, items, url):
        """浏览器在页面里只下同一网站上的图（别的网站的图跨域，浏览器下不了，白等），其余交给脚本下载。"""
        site = '.'.join(host_of(url).split('.')[-2:])
        return [dict(item, files=[dict(f, urls=[u for u in f['urls'] if host_of(u).endswith(site)]) for f in item['files']])
                for item in items]

    def site(self, url):
        host = host_of(url)
        for domain, key, name in GENERIC_SITES:
            if host == domain or host.endswith('.' + domain) or (domain == 'scielo' and 'scielo' in host):
                return key, name
        parts = [p for p in host.split('.') if p not in ('www', 'com', 'org', 'net', 'edu', 'ac', 'co', 'gov')]
        key = re.sub(r'[^a-z0-9]+', '_', parts[-2] if len(parts) > 1 else (parts[0] if parts else 'other'))
        return key, host or '其他出版商'

    def owns(self, url):
        return True

    def out_dir(self, url):
        return papers_dir(self.site(url)[0])

    def loading(self, t):
        return t.startswith('doi.org') or (' ' not in t and '.' in t.split('/')[0] and '/' in t)

    def ours(self, t):
        return is_challenge(t) or t in UNTITLED or self.loading(t) or t.startswith(('http://', 'https://'))

    def incomplete(self, page, state):
        text, n = page['content'], len(page['content'])
        h = (state.get('href') or '').lower()
        if 'redirectedfrom=fulltext' in h:
            return '打开的是摘要页（没有全文权限时转到这里），没有全文'
        sections = len(BODY_HEADING.findall(text))
        locked = next((s for s in GENERIC_NO_ACCESS if s in text), None)
        if locked and sections <= 1:
            return '页面写着「%s」，正文小节只有 %d 个：像是没有全文权限（只有摘要）' % (locked, sections)
        if not sections and n < 15000:
            return '只读到 %d 字符，也没有正文小节（Introduction / Methods / Results …）：像是只有摘要或只给 PDF' % n
        if n < MIN_BODY_CHARS and not GENERIC_REFS.search(text):
            return '只读到 %d 字符，像是页面没加载完' % n
        return None


# Silverchair 平台上的出版商（OUP、RSC、Emerald …）：网页和 ACS 是同一套
SILVERCHAIR_HOSTS = ('academic.oup.com', 'pubs.rsc.org', 'www.emerald.com', 'emerald.com')


class Silverchair(Generic):
    """Silverchair 平台上的出版商（OUP、RSC、Emerald …）：网页和 ACS 是同一套，照 ACS 的读法：文章区范围（页面上有
    才用）、去掉图的弹窗副本、认摘要页（没有权限时转到 …-abstract/…?redirectedFrom=fulltext）、图框 .fig.fig-section、
    原图是去掉 m_ 的同一地址（由脚本下载）。没和老脚本对照过，台账里带提醒。"""
    key, name = 'silverchair', 'Silverchair 平台'
    scope = ACS_SCOPE
    drop = '.fig-modal'
    drop_note = ACS.drop_note
    table_fail = ACS.table_fail
    media_js = ACS_MEDIA_JS
    refs = REFS_HEADING
    browser_download = False

    def owns(self, url):
        return host_of(url) in SILVERCHAIR_HOSTS

    def label(self, url):
        return '%s（Silverchair 平台，照 ACS 的读法）' % self.site(url)[1]

    def note(self, url):
        return '照 ACS 的读法（%s 在 Silverchair 平台上，没和老脚本对照过），请核对' % self.site(url)[1]

    def incomplete(self, page, state):
        text, n = page['content'], len(page['content'])
        href = state.get('href')
        h = (href or '').lower()
        if 'redirectedfrom=fulltext' in h or re.search(r'/[a-z]+-abstract/', h):
            return '打开的是摘要页（没有全文权限时转到这里：%s），没有全文' % urllib.parse.urlsplit(href).path[:60]
        hit = next((s for s in NO_ACCESS if s in text), None)
        if hit:
            return '页面写着「%s…」，网页上没有全文（没有权限或只有 PDF）' % hit
        if not BODY_HEADING.search(text) and n < 15000:
            return '只读到 %d 字符，也没有正文小节（Introduction / Methods / Results …）：像是只有摘要' % n
        if n < MIN_BODY_CHARS and '## References' not in text:
            return '只读到 %d 字符，像是页面没加载完' % n
        return None

    def plan(self, media, url):
        return plan_silverchair(media, url)


# ============================== 2026-10-22 新写的几家 ==============================
# 没有原来的单出版商脚本可对照：照 Elsevier / ACS / Wiley 的同一套流程（opencli extract 原样、表格重建、逐字核对、
# 切参考文献、下载原图），各家网页不同的地方写在各自的类里。存到 <简称>_papers（和以前通用读法存的是同一个文件夹）。
class NewPublisher(Generic):
    """几家共用：有专门读法（台账里不带「通用读法」提醒）；认文章看地址里的 DOI 或页面的 citation_doi（不再像通用
    读法那样认整个网站）；标签栏上认不出时认打开时新出现的那个标签页；图片由脚本下载。"""
    known = True
    browser_download = False
    retry_timeout = True
    refs = NEW_REFS

    def label(self, url):
        return self.name

    def note(self, url):
        return ''

    def extra_keys(self, url):
        return []

    def site(self, url):
        return self.key, self.name

    def out_dir(self, url):
        return papers_dir(self.key)

    def article_url(self, url, doi):
        """doi.org 给的 http:// 地址直接开 https://（这几家都是 https；RSC 的 http://…/article-lookup/ 在 Chrome 里
        跳转时出过错，打开 90 秒还是错误页）。"""
        return 'https://' + url[len('http://'):] if url.lower().startswith('http://') else url

    def not_mine(self, url):
        return '不是 %s 的文章：%s' % (self.name, url)


SPRINGER_HOSTS = ('springer.com', 'nature.com', 'biomedcentral.com', 'springeropen.com')
# Springer 没有全文权限的页面上的话（同时只有摘要）
SPRINGER_LOCKED = ('Access this article', 'Log in via an institution', 'Buy article PDF',
                   'Instant access to the full article PDF', 'Rent this article via DeepDyve')


def body_sections(text):
    """正文小节标题的个数（BODY_HEADING），不算链接样子的标题（Springer 正文中间推荐文章栏里的文章题目）。"""
    return sum(1 for m in BODY_HEADING.finditer(text) if not re.match(r'#{1,4}[ \t]+\[', m.group(0)))


class Springer(NewPublisher):
    """Springer Nature（link.springer.com、nature.com、BMC …；DOI 跳到 link.springer.com/article/<DOI>，地址里有 DOI）。
    读 article#main（标题、作者、摘要、正文、参考文献；opencli 默认读的 <main> 里没有标题和作者），没有就用默认范围。
    表格：正文里只有表题和「Full size table」链接，整张表在单独的表格页（…/tables/1），在已打开的文章页里读出来放回
    原位，表下注放在表格下面。正文中间网页插进来的「Similar content being viewed by others」「Explore related
    subjects」两栏去掉，页面上不显示的标题栏副本（.c-context-bar）去掉。网页上只有摘要和 PDF 的（「Article PDF」，
    老文章）、要买或登录才能看的，记为没有全文。"""
    key, name = 'springer_nature', 'Springer Nature'
    scopes = ('article#main',)
    drop = '.c-context-bar'
    junk = '.c-article-recommendations, .app-explore-related-subjects'
    drop_note = '，去掉了 %d 块（正文中间的推荐文章栏、页面上不显示的标题栏副本）'
    pre_js = SPRINGER_PRE_JS
    async_hook = True
    placed_from = '各自的表格页'
    ext_fail = '%d 张表的表格页没读到（%s），原位只有「Full size table」链接'
    table_fail = ('表格以外的文字和 opencli extract 对不上，没有重建表格（表格页里的表没有放回原位）、'
                  '没有去掉推荐文章栏，全文按 opencli 原样保存')

    def owns(self, url):
        host = host_of(url)
        return any(host == h or host.endswith('.' + h) for h in SPRINGER_HOSTS)

    def tab_title(self, t):
        return ('springer' in t or 'biomed central' in t or ' | nature' in t
                or t.startswith(('link.springer.com', 'www.nature.com', 'nature.com')) or is_challenge(t))

    def incomplete(self, page, state):
        text = page['content']
        sections = body_sections(text)
        if not sections and re.search(r'^#{1,4}[ \t]+Article PDF[ \t]*$', text, re.M):
            return '网页上只有摘要和 PDF（「Article PDF」，没有网页版全文），没有全文'
        locked = next((s for s in SPRINGER_LOCKED if s in text), None)
        if locked and sections <= 1:
            return '页面写着「%s」，正文小节只有 %d 个：像是没有全文权限（只有摘要）' % (locked, sections)
        return Generic.incomplete(self, page, state)

    def plan(self, media, url):
        return plan_known(media, url)


class MDPI(NewPublisher):
    """MDPI（www.mdpi.com；DOI 跳到 www.mdpi.com/<ISSN>/<卷>/<期>/<号>，页面有 citation_doi）。读 opencli 的默认范围
    （<article>：标题、作者、摘要、正文、参考文献都在里面）。表格：正文里每张表只有表题和一个「点开看表」的小图标，
    整张表在页面最后（参考文献后面）藏着的弹窗里，不处理就会和参考文献一起被切掉：放回正文原位，表下注放在表格下面。
    页面上不显示的图、表弹窗副本和作者资料卡去掉；页首「Browse Figures」后面那串图注链接（链接的提示文字是整段
    HTML）去掉。图片：www.mdpi.com 上的不让脚本下载（403），换成 pub.mdpi-res.com 上的同一张图。
    MDPI 都是开放获取，没有全文的判断同通用读法。"""
    key, name = 'mdpi', 'MDPI'
    drop = '#FiguresandTables, .html-fig_show, .html-table_show, .profile-card-content'
    junk = '.popupgallery'
    drop_note = '，去掉了 %d 块（页面上不显示的图、表弹窗副本和图表汇总、作者资料卡，页首的图注链接串）'
    media_js = MDPI_MEDIA_JS
    pre_js = MDPI_PRE_JS
    placed_from = '页面最后的弹窗'
    table_fail = ('表格以外的文字和 opencli extract 对不上，没有重建表格（页面最后弹窗里的表没有放回正文原位，'
                  '会和参考文献一起切掉），全文按 opencli 原样保存')

    def owns(self, url):
        host = host_of(url)
        return host == 'mdpi.com' or host.endswith('.mdpi.com')

    def tab_title(self, t):
        """MDPI 的标签页标题只有文章题目（不带 MDPI）：只认加载中的地址和验证页，其余靠打开时新出现的标签页。"""
        return t.startswith(('www.mdpi.com', 'mdpi.com')) or is_challenge(t)

    def plan(self, media, url):
        return plan_known(media, url, mdpi_candidates)


class OUP(NewPublisher):
    """Oxford University Press（academic.oup.com，Silverchair 平台，网页和 ACS 是同一套）：照 ACS 的读法（图框、原图
    去掉 m_、认摘要页 …-abstract/…?redirectedFrom=fulltext），只是页面上没有 ACS 那个文章区，读 [role="main"]
    （标题、作者、摘要、正文、参考文献；页面上没有 <main>/<article>，opencli 默认会读整页）。页面上不显示的图、表
    弹窗副本和「Cite」「Gift article access」弹窗去掉，正文中间显示着的「Gift article access」栏（订阅用户分享文章用）
    也去掉（同 Springer 的推荐栏，核对时还原）。转到牛津的老 J-STAGE 期刊（BBB 等）多数只有摘要和 PDF，记为没有全文。"""
    key, name = 'oxford', 'Oxford University Press'
    meta_doi = True
    scopes = (ACS_SCOPE, '[role="main"]')
    drop = '.fig-modal, .table-modal, .js-citation-modal, .gift-access-modal-content'
    junk = '.gift-access-panel'
    drop_note = '，去掉了 %d 块（页面上不显示的弹窗：重复的图、表，引用格式、赠阅文章；正文中间的赠阅文章栏）'
    table_fail = ('表格以外的文字和 opencli extract 对不上，没有重建表格、没有去掉图表的弹窗副本，'
                  '全文按 opencli 原样保存')
    media_js = ACS_MEDIA_JS
    incomplete = Silverchair.incomplete

    def owns(self, url):
        return host_of(url) == 'academic.oup.com'

    def tab_title(self, t):
        return 'oxford academic' in t or t.startswith('academic.oup.com') or is_challenge(t)

    def plan(self, media, url):
        return plan_silverchair(media, url)


class RSC(OUP):
    """RSC（pubs.rsc.org，Silverchair 平台）：同 OUP（页面上有 ACS 那个文章区，读它）。没有全文权限时转到
    …/article-abstract/…?redirectedFrom=fulltext，记为没有全文。"""
    key, name = 'rsc', 'RSC'
    drop = '.fig-modal, .table-modal, .gift-access-modal-content'
    drop_note = '，去掉了 %d 块（页面上不显示的弹窗：重复的图注和表格、赠阅文章；正文中间的赠阅文章栏）'

    def owns(self, url):
        return host_of(url) == 'pubs.rsc.org'

    def tab_title(self, t):
        return 'royal society of chemistry' in t or t.startswith('pubs.rsc.org') or is_challenge(t)


class TandF(NewPublisher):
    """Taylor & Francis（tandfonline.com；老 DOI 先到 informaworld.com 的中转页再跳过去）。直接打开
    www.tandfonline.com/doi/full/<DOI>：doi.org 给的是 /doi/abs/（有全文权限时网页自己也会跳到 /doi/full/），
    informaworld 的中转页在标签栏上认不出来。页面上没有 citation_doi，认文章看地址里的 DOI。读 [role="main"]
    （标题、作者在 <article> 外面）。表格：多数文章页上只有表题和「Download CSV / Display Table」按钮，整张表
    （含表下注）在页面自带的数据里，放回原位；页面上直接有 <table> 的照常。图在 .figureView 里，原图是 …_oc.jpg。
    没有全文权限时停在 /doi/abs/，记为没有全文。"""
    key, name = 'taylor_francis', 'Taylor & Francis'
    scopes = ('[role="main"]',)
    pre_js = TANDF_PRE_JS
    placed_from = '页面自带的数据'
    media_js = TANDF_MEDIA_JS
    table_fail = ('表格以外的文字和 opencli extract 对不上，没有重建表格（按需显示的表没有放回原位），'
                  '全文按 opencli 原样保存')

    def owns(self, url):
        host = host_of(url)
        return any(host == h or host.endswith('.' + h) for h in ('tandfonline.com', 'informaworld.com'))

    def article_url(self, url, doi):
        if not doi:
            return url
        return 'https://www.tandfonline.com/doi/full/' + urllib.parse.quote(doi, safe="/:;()._-~<>[]")

    def tab_title(self, t):
        return (t.startswith(('full article:', 'www.tandfonline.com', 'tandfonline.com'))
                or 'taylor & francis' in t or is_challenge(t))

    def small_page(self, state):
        """只有 PDF 的老文章：停在 /doi/abs/，整页不到 3000 字（只有题目、作者和「Download PDF」）。"""
        return '/doi/abs/' in (state.get('href') or '').lower() and state.get('ready') == 'complete'

    def incomplete(self, page, state):
        h = (state.get('href') or '').lower()
        if '/doi/abs/' in h:
            return '打开的是摘要页（/doi/abs/：没有全文权限或只有 PDF），没有全文'
        return Generic.incomplete(self, page, state)

    def plan(self, media, url):
        return plan_known(media, url, lambda urls: list(dict.fromkeys(urls)))


PUBLISHERS = [Elsevier(), ACS(), Wiley(), Springer(), MDPI(), OUP(), RSC(), TandF()]
SILVERCHAIR = Silverchair()
GENERIC = Generic()


def publisher_of(url):
    return next((P for P in PUBLISHERS + [SILVERCHAIR] if P.owns(url)), GENERIC)


def out_dirs():
    """所有出版商的保存位置，加上以前单出版商脚本的（已经存过的不重抓：在哪个文件夹里都算）。"""
    dirs = [P.out_dir('') for P in PUBLISHERS] + sorted(glob.glob(os.path.join(HERE, '*_papers'))) + list(OLD_PAPERS)
    return list(dict.fromkeys(os.path.abspath(d) for d in dirs if os.path.isdir(d)))


# ---------------------------------------------------------------- 输入 --
# DOI 里可以有括号（10.1016/0308-8146(81)90018-2）：先连括号一起取，末尾多出来的「)」（如 markdown 链接的收尾）再去掉
ITEM_RE = re.compile(r'https?://[^\s<>"\'\]]+|\b10\.\d{4,9}/[^\s<>"\'\];,]+', re.I)
LINKINGHUB = re.compile(r'linkinghub\.elsevier\.com/retrieve/pii/([A-Za-z0-9]+)', re.I)


DOI_ITEM = re.compile(r'(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?(10\.\d{4,9}/\S+)$', re.I)


def parse_items(text):
    """文字里的 DOI 链接 / DOI 号 / 文章网址，按出现顺序、去重（几十万条也快：用集合判重）。"""
    out, seen = [], set()
    for m in ITEM_RE.finditer(text or ''):
        s = m.group(0).rstrip('.,;:')
        while s.endswith(')') and s.count(')') > s.count('('):
            s = s[:-1].rstrip('.,;:')
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


# ACS、Wiley 文章页的地址里带着 DOI：pubs.acs.org/doi/[abs/|full/|pdf/|epdf/]10.1021/…、
# <子域名>onlinelibrary.wiley.com/doi/[abs/|full/|pdf/|epdf/…]10.xxxx/…
ACS_DOI_URL = re.compile(r'pubs\.acs\.org/doi/(?:(?:abs|full|pdf|epdf|suppl)/)?(10\.\d{4,9}/[^?#\s]+)', re.I)
WILEY_DOI_URL = re.compile(r'onlinelibrary\.wiley\.com/doi/(?:(?:abs|full|pdf|epdf|pdfdirect|reader|suppl)/)?'
                           r'(10\.\d{4,9}/[^?#\s]+)', re.I)


def parse_item(item):
    """(DOI 或 None, 文章地址或 None)，不联网。DOI 统一小写（DOI 不分大小写），台账和文件夹名都用它。"""
    m = DOI_ITEM.match(item)
    if m:
        # 网址里的「#」是锚点，先切掉再解码；%23 解码出来的「#」是 DOI 自己的（老 SICI DOI 以「co;2-#」结尾），要留着
        s = m.group(1).split('#')[0] if re.match(r'https?://', item, re.I) else m.group(1)
        return urllib.parse.unquote(s).lower(), None
    url = item.split('#')[0]
    m = ACS_DOI_URL.search(url) or WILEY_DOI_URL.search(url)
    if m:                                           # 地址里就有 DOI：按 DOI 处理（台账、文件夹名都用它）
        return urllib.parse.unquote(m.group(1)).rstrip('/').lower(), None
    if 'sciencedirect.com' in url.lower():
        url = url.split('?')[0]
    return None, canonical(url)


def item_key(item):
    doi, url = parse_item(item)
    return doi or url


def canonical(url):
    m = LINKINGHUB.search(url) or re.search(r'sciencedirect\.com/science/article/(?:abs/)?pii/([A-Za-z0-9]+)', url, re.I)
    if m:
        return 'https://www.sciencedirect.com/science/article/pii/%s' % m.group(1).upper()
    return url


def resolve_doi(doi, timeout=30):
    """doi.org 只跟一跳，拿出版商地址（不请求出版商页面，那一步交给浏览器）。"""
    link = 'https://doi.org/' + urllib.parse.quote(doi, safe="/:;()._-~<>[]")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    try:
        urllib.request.build_opener(NoRedirect).open(
            urllib.request.Request(link, headers={'User-Agent': B.get('ua', BROWSERS['chrome']['ua']) % UA_OS}),
            timeout=timeout)
    except urllib.error.HTTPError as e:
        location = e.headers.get('Location') if 300 <= e.code < 400 else None
        if location:
            return canonical(urllib.parse.urljoin(link, location))
        if e.code == 404:
            raise InvalidDoi('doi.org 查不到这个 DOI')
        raise Stop('doi.org 返回 HTTP %d' % e.code)
    except (urllib.error.URLError, OSError) as e:
        if isinstance(getattr(e, 'reason', e), ssl.SSLCertVerificationError):
            # python.org 装的 Python 在 macOS 上默认没有根证书：每篇都会失败，不如直接停下说明
            raise Fatal('Python 连 https://doi.org 时证书校验失败（%s）。如果 Python 是从 python.org 下载安装的，'
                        '请在 访达 → 应用程序 → Python 3.x 里双击「Install Certificates.command」，然后重跑' % e)
        raise Stop('解析 DOI 失败（网络）：%s' % e)
    raise Stop('doi.org 没有给出跳转地址')


def folder_name(doi, url):
    m = re.search(r'/pii/([A-Za-z0-9]+)', url)
    s = doi or (m.group(1) if m else urllib.parse.urlsplit(url).netloc + urllib.parse.urlsplit(url).path)
    return re.sub(r'[\\/:*?"<>|\s]+', '_', s).strip('._')[:150]


def saved_root(doi, a):
    """这篇已经存过的文件夹（--out 给了就只看那里，否则看所有出版商的保存位置）；没存过返回 None。"""
    name = folder_name(doi, '')
    for d in ([a.out] if a.out else out_dirs()):
        root = os.path.join(d, name)
        if os.path.exists(os.path.join(root, '全文.md')):
            return root
    return None


# ---------------------------------------------------------------- 台账 --
# doi list 文件夹里的 .md 文件（含子文件夹）只读不改。每个 DOI 的状态记在同一文件夹的 进度.db（SQLite，
# Python 自带）里：每篇跑完立刻记下，中途停下不丢进度。同一个 DOI 在几个文件里出现只抓一次。
# claims：正在抓的那篇（进程号）。同一个清单开着两份时，每篇开抓前先登记，登记不上（另一份在抓）就跳过。
LEDGER_NAME = '进度.db'
MAX_ATTEMPTS = 3            # 失败的最多试这么多次，之后单独列出，--retry 才再试
LEDGER_SCHEMA = '''
CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, mtime INTEGER, size INTEGER, n INTEGER);
CREATE TABLE IF NOT EXISTS sources (key TEXT, file TEXT, pos INTEGER, item TEXT, PRIMARY KEY (key, file));
CREATE INDEX IF NOT EXISTS sources_file ON sources (file, pos);
CREATE TABLE IF NOT EXISTS papers (key TEXT PRIMARY KEY, status TEXT, reason TEXT, folder TEXT,
                                   attempts INTEGER DEFAULT 0, updated TEXT);
CREATE TABLE IF NOT EXISTS claims (key TEXT PRIMARY KEY, pid INTEGER, browser TEXT, since TEXT);
'''
# 台账里的状态：done 完成；no_fulltext 没有全文；invalid DOI 无效；not_<出版商> 不是 --publisher 指定的那家；
# unsupported 没有专门读法（--only-known 时）；failed 失败
LEDGER_LABELS = (('done', '完成'), ('no_fulltext', '没有全文'), ('invalid', 'DOI 无效')) \
    + tuple(('not_' + P.key, '不是 ' + P.name) for P in PUBLISHERS) \
    + (('unsupported', '没有专门读法（--only-known 跳过）'), ('retry', '失败（下次重试）'),
       ('failed', '失败（已试 %d 次，--retry 再试）' % MAX_ATTEMPTS), ('pending', '未读'))
STATE_SQL = ("CASE WHEN p.status IS NULL THEN 'pending' WHEN p.status = 'failed' AND p.attempts < %d "
             "THEN 'retry' ELSE p.status END" % MAX_ATTEMPTS)


class Ledger:
    def __init__(self, folder):
        self.folder = os.path.abspath(folder)
        self.db = sqlite3.connect(os.path.join(self.folder, LEDGER_NAME), timeout=60)
        self.db.executescript(LEDGER_SCHEMA)
        self.started = time.strftime('%Y-%m-%d %H:%M:%S')   # 这一轮开始的时刻：之后别的那份抓完的就不再抓

    def scan(self):
        """读 doi list 里新加或改过的 .md 文件，收进台账；删掉的文件，它的条目也拿掉。返回 (文件数, 新读的文件数)。"""
        found = {}
        for d, _, names in os.walk(self.folder):
            for name in names:
                if name.lower().endswith('.md'):
                    full = os.path.join(d, name)
                    found[os.path.relpath(full, self.folder)] = full
        known = {p: (m, s) for p, m, s in self.db.execute('SELECT path, mtime, size FROM files')}
        changed = 0
        for rel in sorted(found):
            st = os.stat(found[rel])
            if known.get(rel) == (st.st_mtime_ns, st.st_size):
                continue
            with io.open(found[rel], encoding='utf-8-sig', errors='replace') as fh:
                items = parse_items(fh.read())
            rows = [(item_key(item), rel, i, item) for i, item in enumerate(items)]
            with self.db:
                self.db.execute('DELETE FROM sources WHERE file = ?', (rel,))
                self.db.executemany('INSERT OR IGNORE INTO sources VALUES (?, ?, ?, ?)', rows)
                self.db.execute('INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?)',
                                (rel, st.st_mtime_ns, st.st_size, len(rows)))
            changed += 1
        for rel in set(known) - set(found):
            with self.db:
                self.db.execute('DELETE FROM sources WHERE file = ?', (rel,))
                self.db.execute('DELETE FROM files WHERE path = ?', (rel,))
        return len(found), changed

    def pending(self, retry=False):
        """要抓的 (key, 原文里的写法)：没抓过的、失败未满次数的；retry=True 时再加上没有全文的和试满次数的。
        按文件名、文件里的先后排。"""
        cond = "p.key IS NULL OR (p.status = 'failed' AND p.attempts < %d)" % MAX_ATTEMPTS
        if retry:
            cond = "p.key IS NULL OR p.status IN ('failed', 'no_fulltext')"
        q = ("SELECT s.key, s.item, MIN(s.file || printf('%%012d', s.pos)) AS first FROM sources s "
             "LEFT JOIN papers p ON p.key = s.key WHERE %s GROUP BY s.key ORDER BY first" % cond)
        return [(k, item) for k, item, _ in self.db.execute(q)]

    def record(self, key, status, reason='', folder=''):
        with self.db:
            self.db.execute(
                'INSERT INTO papers (key, status, reason, folder, attempts, updated) VALUES (?, ?, ?, ?, 1, ?) '
                'ON CONFLICT (key) DO UPDATE SET status = excluded.status, reason = excluded.reason, '
                'folder = excluded.folder, attempts = papers.attempts + 1, updated = excluded.updated',
                (key, status, reason, folder, time.strftime('%Y-%m-%d %H:%M:%S')))

    def counts(self):
        q = ('SELECT %s, COUNT(*) FROM (SELECT DISTINCT key FROM sources) s LEFT JOIN papers p ON p.key = s.key '
             'GROUP BY 1' % STATE_SQL)
        return dict(self.db.execute(q).fetchall())

    def report(self):
        """--status：总数、每个文件各状态多少、最近的失败原因。不开浏览器。"""
        def line(c):
            return '｜'.join('%s %d' % (name, c.get(key, 0)) for key, name in LEDGER_LABELS if c.get(key))

        total = self.counts()
        print('台账：%s' % os.path.join(self.folder, LEDGER_NAME))
        print('共 %d 个 DOI（去重后）：%s' % (sum(total.values()), line(total) or '无'))
        per = {}
        for f, state, n in self.db.execute('SELECT s.file, %s, COUNT(*) FROM sources s LEFT JOIN papers p '
                                           'ON p.key = s.key GROUP BY 1, 2' % STATE_SQL):
            per.setdefault(f, {})[state] = n
        print('\n按文件：')
        for f in sorted(per):
            print('  %s　共 %d：%s' % (f, sum(per[f].values()), line(per[f])))
        bad = self.db.execute("SELECT p.key, p.attempts, p.reason FROM papers p WHERE p.status = 'failed' "
                              "AND p.key IN (SELECT key FROM sources) ORDER BY p.updated DESC LIMIT 30").fetchall()
        if bad:
            print('\n最近的失败（最多 30 条）：')
            for key, n, reason in bad:
                print('  %s（试了 %d 次）\n      %s' % (key, n, reason))

    def claim(self, key):
        """开抓前登记：这篇由我（这个进程）抓。另一份正在抓（它的进程还在），或者这一轮开始后它已经抓完了，返回 False。"""
        for _ in range(3):
            try:
                with self.db:
                    self.db.execute('INSERT INTO claims (key, pid, browser, since) VALUES (?, ?, ?, ?)',
                                    (key, os.getpid(), B.get('key', ''), time.strftime('%Y-%m-%d %H:%M:%S')))
                break
            except sqlite3.IntegrityError:
                row = self.db.execute('SELECT pid FROM claims WHERE key = ?', (key,)).fetchone()
                if row and row[0] == os.getpid():
                    break
                if row and pid_alive(row[0]):
                    return False
                with self.db:                       # 上次没删掉的登记（那个进程已经不在了）
                    self.db.execute('DELETE FROM claims WHERE key = ? AND pid IS ?', (key, row[0] if row else None))
        else:
            return False
        row = self.db.execute('SELECT updated FROM papers WHERE key = ?', (key,)).fetchone()
        if row and row[0] and row[0] >= self.started:
            self.unclaim(key)
            return False
        return True

    def unclaim(self, key=None):
        """放掉登记：这一篇，或者（key=None）这个进程登记的全部。"""
        try:
            with self.db:
                if key is None:
                    self.db.execute('DELETE FROM claims WHERE pid = ?', (os.getpid(),))
                else:
                    self.db.execute('DELETE FROM claims WHERE key = ? AND pid = ?', (key, os.getpid()))
        except sqlite3.Error:
            pass


# ---------------------------------------------------------------- 主流程 --
LAST_NOTES = []                                     # 最近一篇的提醒（fetch_one 写，主循环记进台账）
LEDGERS = []                                        # 这次开着的台账（退出时放掉登记）


# --captions（只补表题）：已经抓过、表格前面没有「Table N. 表题」的文章，重开网页照现在的读法再读一遍正文，
# 和原来的 全文.md 逐行比：多出来的只有表题行（和空行）才写回 全文.md，别的一字不改，图不重下；
# 有别的不同就不改、记提醒。清单和台账放在 CAPTION_DIR，和 do list 分开。
CAPTION_DIR = os.path.join(HERE, '补表题 list')
CAPTION_LINE = re.compile(r'^Table\s+\S+\.(?:\s|$)')


GLOSSARY_HEAD = re.compile(r'^#+\s*(?:abbreviations?|nomenclature|glossary|list of (?:abbreviations|symbols))\b', re.I)


def missing_captions(text):
    """全文里 markdown 表格的个数、其中前面没有表题行的个数（表格前两行以内的非空行里找「Table N.」）。
    缩写表、符号表（紧跟在 Abbreviations / Nomenclature 小节标题下的）和附件列表（Supporting Information 的
    「Filename | Description」）本来就没有表题，不算。"""
    lines = text.splitlines()
    n = miss = 0
    for i, l in enumerate(lines):
        if l.startswith('|') and i + 1 < len(lines) and lines[i + 1].startswith('|---') and not (i and lines[i - 1].startswith('|')):
            prev = [x for x in lines[max(0, i - 3):i] if x.strip()][-2:]
            if prev and (GLOSSARY_HEAD.match(prev[-1]) or prev[-1].strip() == 'Supporting Information') \
                    or re.match(r'^\|\s*Filename\s*\|\s*Description\s*\|\s*$', l):
                continue
            n += 1
            if not any(CAPTION_LINE.match(x) for x in prev):
                miss += 1
    return n, miss


def table_starts(lines):
    """markdown 表格（表头行 + |--- 分隔行）的起始行号和整块的行。"""
    out = []
    for i, l in enumerate(lines):
        if l.startswith('|') and i + 1 < len(lines) and lines[i + 1].startswith('|---') and not (i and lines[i - 1].startswith('|')):
            j = i
            while j < len(lines) and lines[j].startswith('|'):
                j += 1
            out.append((i, lines[i:j]))
    return out


def caption_before(lines, i):
    """第 i 行那张表前面的表题行（前两行以内的非空行里的「Table N.」），没有返回 None。"""
    prev = [x for x in lines[max(0, i - 3):i] if x.strip()][-2:]
    return next((x for x in reversed(prev) if CAPTION_LINE.match(x)), None)


def merge_captions(old, new):
    """把新读到的表题插进原来的全文：表题下面那张表在原来的全文里找到一模一样的（各行一字不差、按先后顺序），
    就在它前面插上「表题 + 空行」；原来的全文别处一字不动（网页上作者栏之类变了也不影响）。
    返回 (插好的全文, 说明)；一个也没插上返回 (None, 原因)。"""
    a, b = old.split('\n'), new.split('\n')
    olds = table_starts(a)
    inserts, j, missed = {}, 0, 0
    for i, block in table_starts(b):
        cap = caption_before(b, i)
        if not cap:
            continue
        k = next((k for k in range(j, len(olds)) if olds[k][1] == block), None)
        if k is None:
            missed += 1
            continue
        if not caption_before(a, olds[k][0]):
            inserts[olds[k][0]] = cap
        j = k + 1
    if not inserts:
        return None, ('网页上读到的表题对不上原来全文里的表格（%d 个），全文.md 没改' % missed if missed
                      else '网页上也没读到表题，全文.md 没改')
    note = '补上表题 %d 个' % len(inserts) + ('（另有 %d 个对不上原来的表格，没补）' % missed if missed else '')
    return insert_captions(a, inserts), note


def insert_captions(lines, inserts):
    """在第 n 行（表格第一行）前面插上「表题 + 空行」，表题前面不是空行就先补一个空行。"""
    out = []
    for n, line in enumerate(lines):
        if n in inserts:
            if out and out[-1].strip():
                out.append('')
            out += [inserts[n], '']
        out.append(line)
    return '\n'.join(out)


# 补表题的快读：页面一显示就只读每张表的表题和第一行（不滚动、不整篇读，范围和去掉的部分同 opencli extract），
# 按先后顺序和原来 全文.md 里的表格一张张对上（张数相同、第一行的字对得上）才插表题；表题写法同整篇读法
# （同一段 __wcap、同一套转 markdown 和上下标）。对不上返回 None，退回整篇读法。
CAPTION_QUICK_JS = (
    "(() => {\n  const root = document.querySelector('main') || document.querySelector('article') || document.body;\n"
    + TABLE_HOOK[TABLE_HOOK.index('  const __wcap = '):TABLE_HOOK.index("  for (const t of [...clone.querySelectorAll('table')])")]
    + r'''  const drop = 'script, style, noscript, template, nav, header, footer, aside, iframe, svg, canvas, form, button, input, select, textarea, [role="navigation"], [role="banner"], [role="contentinfo"], [role="complementary"], [aria-hidden="true"]';
  const out = [];
  for (const t of root.querySelectorAll('table')) {
    if ((t.parentElement && t.parentElement.closest('table')) || t.closest(drop)) continue;
    const tr = t.rows[0];
    out.push({cap: __wcap(t), head: tr ? [...tr.cells].map(c => c.textContent || '').join(' ') : ''});
  }
  return {full: !!document.querySelector('.article-section__full'), tables: out};
})()''')


def table_sig(s):
    """比第一行用：只留字母数字（上下标、链接、markdown 符号都不算）。"""
    s = re.sub(r'\]\([^)]*\)', ']', unicodedata.normalize('NFKC', s or ''))
    return re.sub(r'[\W_]+', '', s).lower()


def caption_quick(P, session, keys, url, old):
    """快读补表题：返回 (插好的全文, 说明)；张数、第一行对不上或没读到表题返回 None（退回整篇读法）。"""
    wait_ready(P, session, keys)
    wait_original(session, url)
    try:
        res = page_eval(session, CAPTION_QUICK_JS, timeout=60)
    except Exception as e:
        print('  快读出错（%s）' % str(e)[:80], flush=True)
        return None
    if not isinstance(res, dict) or not res.get('full'):
        return None
    tabs, a = res.get('tables') or [], old.split('\n')
    olds = table_starts(a)
    if not tabs or len(tabs) != len(olds):
        return None
    for t, (i, block) in zip(tabs, olds):
        x, y = table_sig(t.get('head')), table_sig(block[0])
        if x != y and difflib.SequenceMatcher(None, x, y, autojunk=False).ratio() < 0.8:
            return None
    caps = [t.get('cap') or '' for t in tabs]
    if not any(caps):
        return None
    conv = node_helper({'mode': 'md', 'utils': file_uri(os.path.join(OPENCLI_SRC, 'utils.js')), 'html': '', 'parts': caps})
    md = [scripts_readable(m).strip() if m else '' for m in conv['parts']]
    inserts = {i: m for m, (i, _) in zip(md, olds) if m and CAPTION_LINE.match(m) and not caption_before(a, i)}
    if not inserts:
        return None
    return insert_captions(a, inserts), '补上表题 %d 个（快读）' % len(inserts)


def fetch_one(item, a):
    doi, url = parse_item(item)
    if doi and a.captions:
        root = saved_root(doi, a)
        if not root:
            print('  没抓过这篇（没有 全文.md），跳过', flush=True)
            return 'skipped', ''
        with io.open(os.path.join(root, '全文.md'), encoding='utf-8', newline='') as fh:
            old_text = fh.read()
        n, miss = missing_captions(old_text)
        if not miss:
            print('  %s，跳过' % ('表格都有表题了' if n else '全文里没有表格'), flush=True)
            return 'skipped', root
        print('  %d 张表里 %d 张没有表题' % (n, miss), flush=True)
        cap_root = root
        url = resolve_doi(doi)
        print('  出版商地址：%s' % url, flush=True)
    elif doi:
        root = saved_root(doi, a)
        if root and not a.refresh:
            print('  已经有了：%s（要重抓加 --refresh）' % root, flush=True)
            return 'skipped', root
        url = resolve_doi(doi)
        print('  出版商地址：%s' % url, flush=True)
    P = publisher_of(url)
    if a.publisher and P.key != a.publisher:        # 只抓 --publisher 指定的那家：不开浏览器
        only = next(x for x in PUBLISHERS if x.key == a.publisher)
        raise Skipped('not_' + only.key, only.not_mine(url))
    opened_url = P.article_url(url, doi)
    if opened_url != url:
        print('  改为打开：%s' % opened_url, flush=True)
        url = opened_url
    if not P.known:
        site = P.site(url)[1]
        if a.only_known:
            raise Skipped('unsupported', '%s 还没有专门的读法（--only-known），没抓：%s' % (site, url))
        print('  出版商：%s' % P.label(url), flush=True)
    keys = article_keys(url, doi) + P.extra_keys(url)
    if not keys:
        raise Stop('从地址里认不出这篇文章：%s' % url)
    deadline = time.time() + a.wait * 60
    before = mine = None                            # 打开前的标签栏 / 这篇打开的标签页：读完按它关掉
    if not a.keep_tabs:
        try:
            before = list_tabs()
        except Unavailable as e:
            a.stop_reason = '读不了浏览器的标签栏（%s），没法保证读完关掉标签页' % e
            raise Stop(a.stop_reason)
    opened_at = time.time()
    opened = open_url(url)
    if opened:
        print('  已在 %s 里打开，等页面加载' % B['name'], flush=True)
        if before is not None:
            mine = find_new_tab(before)
            if mine:
                remember_open_tab(mine)             # 中途被停时据此关掉它
        time.sleep(1 if mine else 3)
        wait_new_tab(P, url, deadline, a.load_timeout, before)
    else:
        print(ACTION + '找不到 %s，请你在 %s 里打开：%s' % (B['exe'] if IS_WIN else B['mac_app'] + '.app', B['name'], url),
              flush=True)

    def close_now():
        """读完（成功、没有全文、失败、出错或中断都一样）立刻关掉这篇的标签页，确认关掉了才开下一篇。"""
        if opened and not a.keep_tabs:
            why = close_ours(P, before, mine)
            if why:
                a.stop_reason = '这篇的标签页没能确认关掉：%s' % why
                print('  ✗ %s' % a.stop_reason, flush=True)
            else:
                forget_open_tab()
                print('  已关掉这篇的标签页（已确认）', flush=True)

    try:
        quick = (lambda s: caption_quick(P, s, keys, url, old_text)) if a.captions else None
        page, media, problem = read_article(P, url, keys, a.wait, a.ask, opened_at, a.load_timeout,
                                            with_media=not a.captions, mine=mine, quick=quick)
    except BaseException:
        close_now()
        raise
    close_now()
    if page.get('quick'):                           # 补表题快读成了：只写 全文.md
        merged, info = page['quick']
        with io.open(os.path.join(cap_root, '全文.md'), 'w', encoding='utf-8', newline='') as fh:
            fh.write(merged)
        print('  %s -> %s' % (info, cap_root), flush=True)
        return 'ok', cap_root
    extra = P.extra_notes(page['content'])          # 切参考文献之前看
    if not doi:                                     # 给的是网址：用页面上的 DOI 起文件夹名
        m = re.search(r'10\.\d{4,9}/[^\s?#]+', urllib.parse.unquote(media.get('doi') or ''))
        doi = m.group(0).lower() if m else None
    root = os.path.join(a.out or P.out_dir(url), folder_name(doi, url))
    print('  %s' % (plain_title(page['title']) or '（无标题）'), flush=True)
    print('  全文 %d 字符（opencli extract %d 段），%s'
          % (len(page['content']), page['chunks'],
             'HTML 表格 %d 张已按原表结构放回原位' % page['tables'] if page.get('tables') else '没有 HTML 表格')
          + (P.drop_note % page['drops'] if page.get('drops') else ''), flush=True)
    if page.get('scripts'):
        print('  上下标 %d 处写成纯文本（如 Ca²⁺、10¹⁰、T_c）' % page['scripts'], flush=True)
    if page.get('maths'):
        print('  公式 %d 个写成一行文字' % page['maths'], flush=True)
    refs_note = None
    if not a.keep_refs:
        content, cut = drop_references(page['content'], P.refs)
        page = dict(page, content=content)
        if cut:
            print('  参考文献及其后的网页内容去掉 %d 字符，保存 %d 字符' % (cut, len(content)), flush=True)
        else:
            refs_note = '没找到参考文献标题（## References），全文没有切'
    if a.captions:                                  # 只补表题：只写 全文.md，图不重下
        merged, info = merge_captions(old_text, page['content'])
        if merged is None:
            print('  ⚠ %s' % info, flush=True)
            LAST_NOTES[:] = [info]
            return 'warning', cap_root
        with io.open(os.path.join(cap_root, '全文.md'), 'w', encoding='utf-8', newline='') as fh:
            fh.write(merged)
        print('  %s -> %s' % (info, cap_root), flush=True)
        if '没补' in info:                          # 有的表题没插上：记提醒，以后挑出来看
            LAST_NOTES[:] = [info]
            return 'warning', cap_root
        return 'ok', cap_root
    items = P.plan(media, url)
    n_fig = sum(1 for i in items if i['kind'] == 'figure')
    n_tab = sum(1 for i in items if i['kind'] == 'table')
    print('  图 %d 个、图片版表格 %d 个，下载原图：' % (n_fig, n_tab), flush=True)
    fetch_images(P, items)
    write_paper(root, page, items, url, doi)
    failed = [f['name'] for i in items for f in i['files'] if not f.get('data')]
    notes = ([problem] if problem else []) + ([page['table_note']] if page.get('table_note') else []) \
        + ([refs_note] if refs_note else []) \
        + (['%d 张图下载失败：%s' % (len(failed), '、'.join(failed))] if failed else []) \
        + extra + ([P.note(url)] if P.note(url) else [])
    print('  已保存 -> %s' % root, flush=True)
    for n in notes:
        print('  ⚠ %s' % n, flush=True)
    LAST_NOTES[:] = notes                          # 带提醒的也记进台账（status 仍是 done），方便事后找出来补
    return ('warning' if notes else 'ok'), root


def cleanup():
    """退出时：放掉台账里的登记、浏览器的锁，删掉临时的标签栏脚本。"""
    for ledger in LEDGERS:
        ledger.unclaim()
    release_lock()
    drop_tabs_script()


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace', line_buffering=True)
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description='（通用版）论文 DOI 链接 → 网页全文原样 markdown + 图 + 图片版表格 + 图注'
                                             '（各出版商、Chrome / Edge 自动选，opencli，不调用大模型）')
    ap.add_argument('items', nargs='*', help='DOI 链接（https://doi.org/10.…）、DOI 号或文章网址，可以给多个')
    ap.add_argument('--file', help='从文件里读 DOI 链接（如 DOI按出版商-119334\\ACS.md），按出现顺序')
    ap.add_argument('--out', help='保存位置（默认按出版商分开放在脚本旁边：elsevier_papers、acs_papers、wiley_papers、'
                                  '<出版商>_papers）；给了就全都存这里')
    ap.add_argument('--refresh', action='store_true', help='文件夹里已有 全文.md 也重新抓（同名文件覆盖）')
    ap.add_argument('--captions', action='store_true',
                    help='只补表题：已经抓过、表格没有表题的文章重开网页，只在 全文.md 里插上「Table N. 表题」'
                         '（其余一字不变才写，图不重下）；清单和台账默认在 %s' % CAPTION_DIR)
    ap.add_argument('--keep-refs', action='store_true', help='保留参考文献（默认从参考文献标题起到末尾去掉）')
    ap.add_argument('--wait', type=float, default=15.0, help='每篇等人机验证（你来完成）的分钟数（默认 15）')
    ap.add_argument('--load-timeout', type=float, default=LOAD_TIMEOUT,
                    help='打开后这么多秒还没显示文章、也不是验证页，就当打不开或报错，跳过（默认 %(default)g）')
    ap.add_argument('--interval', type=float, default=1.0, help='两篇之间至少间隔的秒数（默认 1）')
    ap.add_argument('--ask', action='store_true',
                    help='没有全文时在终端里问你（回车重读 / s 按现状保存 / k 跳过）；默认直接跳过，汇总里列出')
    ap.add_argument('--keep-tabs', action='store_true', help='读完不关标签页（默认读完立刻关掉这篇打开的那个，确认关掉才开下一篇）')
    ap.add_argument('--browser', choices=('auto',) + tuple(BROWSERS), default='auto',
                    help='用哪个浏览器（默认 auto：哪个闲着用哪个）')
    ap.add_argument('--which-browser', action='store_true', help='只看会用哪个浏览器、另一个为什么不用，不抓')
    ap.add_argument('--profile', help='opencli 里这个浏览器的扩展实例编号（opencli profile list 可查；默认自动认）')
    ap.add_argument('--publisher', choices=tuple(P.key for P in PUBLISHERS),
                    help='只抓这一家（别家的不开浏览器，台账记为「不是 X」）')
    ap.add_argument('--only-known', action='store_true',
                    help='只抓有专门读法的出版商（Elsevier、ACS、Wiley、Springer Nature、MDPI、OUP、RSC、T&F），'
                         '其余不开浏览器，台账记为「没有专门读法」')
    ap.add_argument('--no-preflight', action='store_true', help='跳过 opencli 预检')
    ap.add_argument('--dir', help='DOI 列表文件夹（默认 %s；什么都不给时就用它）' % DOI_DIR)
    ap.add_argument('--status', action='store_true', help='只看台账进度（每个文件完成 / 没有全文 / 失败 / 未读各多少），不抓')
    ap.add_argument('--retry', action='store_true', help='台账里没有全文的、失败满 %d 次的也再试' % MAX_ATTEMPTS)
    ap.add_argument('--limit', type=int, default=0, help='这次最多抓多少篇（0 = 不限）')
    ap.add_argument('--max-fails', type=int, default=0,
                    help='连续失败这么多篇就停下（默认 0 = 不停：每篇都试一次）')
    a = ap.parse_args()
    a.stop_reason = None
    a.restart_reason = None
    if a.which_browser:
        choose_browser(a, keep=False)
        return 0

    # 两种用法：给了 DOI / --file 就只跑这些；否则跑 DOI 列表文件夹（do list），进度记在台账里
    ledger = None
    if a.status or a.dir or not (a.items or a.file):
        folder = a.dir or (CAPTION_DIR if a.captions else DOI_DIR)
        if not os.path.isdir(folder):
            if a.dir:
                raise Fatal('没有这个文件夹：%s' % folder)
            os.makedirs(folder)
            print('DOI 列表文件夹 %s 还没有，已建好：把 DOI 列表（.md）放进去再跑。' % folder)
            return 0
        ledger = Ledger(folder)
        LEDGERS.append(ledger)
        n_files, changed = ledger.scan()
        if a.status:
            ledger.report()
            return 0
        work = ledger.pending(a.retry)
        c = ledger.counts()
        print('DOI 列表：%s（%d 个 .md 文件，这次新读 %d 个）' % (folder, n_files, changed))
        print('  共 %d 个 DOI（去重后）：完成 %d，这次要抓 %d' % (sum(c.values()), c.get('done', 0), len(work)))
    else:
        text = ' '.join(a.items)
        if a.file:
            with io.open(a.file, encoding='utf-8-sig') as fh:
                text += '\n' + fh.read()
        work = [(item_key(item), item) for item in parse_items(text)]
    work = [(k, i) for k, i in work if k not in SESSION['tried']]   # 自动重新开始前已试过的不重复
    if not work:
        print('列表里的 DOI 这次都试过了。' if SESSION['tried'] else '没有要抓的 DOI。')
        return 0
    if not B:
        choose_browser(a, keep=True)
        check_tabs()
    if not a.keep_tabs:
        install_close_handler()                     # 直接关终端窗口时也先关掉正在处理的那篇
        close_leftover_tab()                        # 上次中途停下留下的标签页，先关掉
    if not a.no_preflight:
        print('opencli 预检…', flush=True)
        preflight()

    results, last, streak, tried = [], None, 0, 0
    for n, (key, item) in enumerate(work, 1):
        if a.limit and tried >= a.limit:
            print('\n已抓满 --limit %d 篇，先停下' % a.limit, flush=True)
            break
        if ledger is not None and not ledger.claim(key):
            print('\n=== [%d/%d] %s ===\n  另一份正在抓这篇，或这一轮里已经抓过了：跳过' % (n, len(work), item), flush=True)
            SESSION['tried'].add(key)
            continue
        print('\n=== [%d/%d] %s ===' % (n, len(work), item), flush=True)
        if last is not None and time.time() - last < a.interval:
            time.sleep(a.interval - (time.time() - last))
        folder = ''
        try:
            status, where = fetch_one(item, a)
            folder = where
        except PageError as e:
            status, where = 'page_error', str(e)
            print('  ✗ 打不开或报错，跳过：%s' % e, flush=True)
        except NoFullText as e:
            status, where = 'no_fulltext', str(e)
            print('  ✗ 没有全文，跳过：%s' % e, flush=True)
        except InvalidDoi as e:
            status, where = 'invalid', str(e)
            print('  ✗ DOI 无效，跳过：%s' % e, flush=True)
        except Skipped as e:
            status, where = e.status, str(e)
            print('  ✗ %s，跳过' % e, flush=True)
        except Stop as e:
            status, where = 'failed', str(e)
            print('  ✗ 这篇停下：%s' % e, flush=True)
        except (KeyboardInterrupt, Restart):
            if ledger is not None:
                ledger.unclaim(key)
            raise
        except Exception as e:
            status, where = 'failed', '%s: %s' % (type(e).__name__, str(e)[:300])
            print('  ✗ 出错：%s' % where, flush=True)
            if not bridge_ok():                     # opencli 和浏览器断开了：不是这篇的问题，不记失败，整个重新开始
                a.restart_reason = 'opencli 和浏览器的连接断了（%s）' % where[:120]
                if ledger is not None:
                    ledger.unclaim(key)
                break
        if status not in ('skipped', 'invalid', 'unsupported') and not status.startswith('not_'):   # 这几种没开浏览器
            last, tried = time.time(), tried + 1
        if ledger is not None:
            ledger.record(key, 'done' if status in ('ok', 'warning', 'skipped')
                          else 'failed' if status == 'page_error' else status,
                          '；'.join(LAST_NOTES) if status == 'warning'
                          else '' if status in ('ok', 'skipped') else where, folder)
            ledger.unclaim(key)
        results.append((item, status, where))
        SESSION['tried'].add(key)
        SESSION['progress'] += 1
        if a.stop_reason:
            a.restart_reason = a.stop_reason        # 比如标签页没能确认关掉：重新开始时先把它关掉
            break
        streak = streak + 1 if status in ('failed', 'page_error') else 0
        if a.max_fails and streak >= a.max_fails:
            print('\n连续 %d 篇失败，按 --max-fails 停下（最近一篇：%s）。'
                  '重跑同一条命令会从没抓到的接着来。' % (streak, where), flush=True)
            break

    # 汇总：先计数，再只列出没顺利完成的（完成的都在保存位置里）。重跑同一条命令会跳过已保存的，补抓其余的。
    order = (('ok', '完成'), ('warning', '完成（有提醒）'), ('skipped', '已有，跳过'),
             ('no_fulltext', '没有全文，跳过'), ('invalid', 'DOI 无效'),
             ('not_elsevier', '不是 Elsevier，跳过'), ('not_acs', '不是 ACS，跳过'), ('not_wiley', '不是 Wiley，跳过'),
             ('unsupported', '没有专门读法，跳过'),
             ('page_error', '打不开或报错，跳过（下次再试）'), ('failed', '失败'))
    print('\n==== 这次汇总：%d 篇 ====' % len(results))
    print('  ' + '，'.join('%s %d' % (name, sum(1 for r in results if r[1] == key)) for key, name in order
                          if any(r[1] == key for r in results)))
    for key, name in order[1:]:
        if key == 'skipped':
            continue
        rows = [r for r in results if r[1] == key]
        if rows:
            print('\n%s（%d）：' % (name, len(rows)))
            for item, _, where in rows[:30]:
                print('  %s\n      %s' % (item, where))
            if len(rows) > 30:
                print('  ……另有 %d 条%s' % (len(rows) - 30, '，全部见 --status' if ledger is not None else ''))
    if ledger is not None:
        c = ledger.counts()
        print('\n台账：共 %d 个 DOI，完成 %d，还没抓的 %d（--status 看每个文件的进度）'
              % (sum(c.values()), c.get('done', 0), c.get('pending', 0) + c.get('retry', 0)))
    if any(r[1] in ('no_fulltext', 'failed', 'page_error') for r in results):
        print('没抓到的重跑同一条命令即可：已保存的会自动跳过。')
    if a.restart_reason:
        raise Restart(a.restart_reason)
    return 1 if any(s in ('failed', 'no_fulltext', 'page_error') for _, s, _ in results) else 0


def supervise():
    """跑 main；因故障停下（opencli 和浏览器断开、后台服务出问题、预检没过、标签页没能确认关掉、接管到的不是选好的
    浏览器、脚本意外出错）就等一会儿自动重新开始，已试过的不重复。等待从 30 秒起每次翻倍，最长 5 分钟；某一轮有
    进展就回到 30 秒。设置问题（Fatal、命令行写错）和 Ctrl+C 才真正停。"""
    restarts, pause = 0, 30
    while True:
        progress = SESSION['progress']
        try:
            return main()
        except (KeyboardInterrupt, Fatal):
            raise
        except Restart as e:
            reason = str(e)
        except SystemExit as e:
            if e.code is None or isinstance(e.code, int):    # --help、命令行写错：照常退出
                raise
            reason = str(e.code)                             # 预检没过等
        except Exception as e:
            reason = '%s: %s' % (type(e).__name__, str(e)[:300])
        finally:
            for ledger in LEDGERS:
                ledger.unclaim()
            LEDGERS.clear()
        if SESSION['progress'] > progress:
            pause = 30
        restarts += 1
        print('\n【自动重新开始】这一轮因故障停下：%s\n  %d 秒后自动重新开始（第 %d 次），已试过的不重复；按 Ctrl+C 才真正停。'
              % (reason, pause, restarts), flush=True)
        time.sleep(pause)
        pause = min(pause * 2, 300)


if __name__ == '__main__':
    try:
        sys.exit(supervise())
    except KeyboardInterrupt:
        sys.exit('\n已中断。')
    finally:
        cleanup()
