#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
pipeline.py —— 论文 → 蛋白质功能特性数据库，整条流程一个脚本（用户 2026-10-21：「整理合并这几个文件夹，最终合并成一个长脚本，
包括以上这些流程……简化文件夹，但是不简化流程」）。

原来分在五个文件夹的脚本原样合在这里，规则、核对一条不少（每一部分前面的说明就是原脚本的说明）：
    第一部分  读图          原 figure_reader\figure_reader.py      figure\ → 反读数据.md、反读数据.json（调模型）
    第二部分  全文合并      原 paper_clean\paper_clean.py          全文.md + 反读数据 → 全文合并.md（纯规则）
    第三部分  数据点提取    原 extract_datapoint\extract_datapoint.py  全文合并.md → datapoint.md（调模型）
    第四部分  测定方法提取  原 extract_method\extract_method.py    → method.json（有进库数值的文章才有；调模型）
    第五部分  一条命令      原 extract_datapoint\datapoint_with_method.py  数据点 → 测定方法 → 带方法的 datapoint.md
    第六部分  建库          原 build_database\build_database.py    datapoint.md → D:\protein_database（不调模型）
合并时读图部分的名字一个不改；其余每部分的函数和常量都加了前缀，看名字就知道出自哪一部分：全文合并 pc_、数据点 ed_、
测定方法 em_、一条命令 dw_、建库 bd_（pydantic 的类照原名定义、另有带前缀的名字：类名在发给模型的 schema 里，
回答存档的指纹带它，改了旧存档会作废）。别的一个字没改。这个文件由 build_pipeline.py 从原脚本逐字生成。

用法（都在这个文件夹里跑）：
    python pipeline.py all                              整条流程：读图 → 合并 → 数据点 → 测定方法 → 带方法的 datapoint → 建库
                                                        （输入默认是 D 盘 2–8 号七个总文件夹 2.elsevier_papers …
                                                        8.Springer nature_papers 里每篇的 全文.md 和 figure\，用户 2026-10-30；
                                                        见 PAPER_ROOTS；ACS 已做完，只进合成的库；3 号 Wiley 先跳过，
                                                        见 SKIP_ROOTS）
    python pipeline.py all --root D:\2.elsevier_papers    只做这一个总文件夹（可以给几个 --root）
    python pipeline.py all --windows 8                  调模型的几步开得更多：读图 8 个窗口，数据点、测定方法同时 32 个请求
                                                        （默认读图 5 个窗口、数据点和测定方法同时 20 个请求；--windows 1 = 不另开窗口）
    python pipeline.py all --skip-read                  不读图（读图另开 5 个窗口跑时用），其余照做
    python pipeline.py all --dry-run                    只数每一步要做多少篇，不调模型、不写文件
    python pipeline.py read [读图的参数]                只读图（同原 figure_reader.py；双击 跑读图_*.bat 就是它）
    python pipeline.py merge [合并的参数]               只合并（同原 paper_clean.py）
    python pipeline.py datapoint [参数]                 只提取数据点（同原 extract_datapoint.py，--build-only 不调模型）
    python pipeline.py method [参数]                    只提取测定方法（同原 extract_method.py）
    python pipeline.py datapoint-with-method [参数]     数据点 → 测定方法 → 带方法的 datapoint.md（同原 datapoint_with_method.py）
    python pipeline.py build-db [参数]                  只建库：1–8 号总文件夹合成一个库 D:\protein_database，只重算新的、
                                                        变了的文章（--full 整库重算；--root X 只建这个总文件夹，写到 X\database）
    python pipeline.py site [参数]                      建库 + 更新网站数据（同原 build_db_and_site.py，不在 all 里）
    python pipeline.py <命令> -h                        看这一步的全部参数
花钱的是读图、数据点、测定方法三步（有回答存档、输入没变的不重问）；花钱前先问用户。

文件夹结构（用户 2026-10-21 定，和 D:\acs_papers_done 一致；10-30 起 2–8 号总文件夹都是这样，all 开头把直接放在总文件夹里的
文章挪进 papers\，跑完每个总文件夹里另有它自己的 database\）：
    <root>\papers\<文章名>\      全文.md、figure\（抓取脚本的产物）；反读数据.md、反读数据.json（读图）；全文合并.md（合并）；
                                 datapoint.md（数据点）；method.json（测定方法，有进库数值的文章才有）
    <root>\_records\             全文合并\_合并报告.md；数据点\（报告、格式说明、待重读、_模型输出 回答存档）；测定方法\（同）
    <root>\database\             这个总文件夹自己的库（和合成的库同样的表，只重算新的、变了的文章）
    D:\protein_database\         1–8 号总文件夹合成的库（用户 2026-10-21「以 ACS 已经有的库为基础，Elsevier 的新数据点出来之后
                                 往数据库里更新」；10-30 起 Wiley、RSC、MDPI、OUP、T&F、Springer Nature 也进这个库）：
                                 CSV、README.md、_建库报告.md、_建库清单.json（每篇的输入指纹，增量更新用）；
                                 D:\1.acs_papers_done\database 是 ACS 单独的存档，不再更新
    没有 papers 子文件夹的总文件夹（如 D:\2.elsevier_papers），文章直接放在 <root> 下，其余一样。
这个文件夹里：pipeline.py、test_pipeline.py（离线测试）、跑全流程.bat（双击 = all，一直做到建库）、
不用重读.tsv、人工排除.tsv、不再问.tsv（数据点这一步不发给模型的文章）（只读图的 bat 10-21 用户删了：all 自己开读图窗口；只读图用 pipeline.py read）、
断点\（读图的中间结果，整篇成功后删）、日志\（读图 --log 的屏幕输出）。
"""
import argparse
import base64
import collections
import csv
import glob
import hashlib
import importlib.util
import io
import itertools
import json
import math
import os
import random
import re
import shutil
import statistics
import sys
import tempfile
import threading
import time
import types
import unicodedata
import urllib.parse
from PIL import Image
from concurrent import futures
from pydantic import BaseModel, Field, create_model
from typing import List, Literal, Optional


# ====================================================================================================
# 读图（原 figure_reader\figure_reader.py）
# ====================================================================================================
r"""
figure_reader.py —— 论文的图和图片版表格 → 蛋白质功能特性数据反读
                    （经 OpenRouter：gpt-6-luna 初筛 → gemini-3.8-flash 分类、读图）

把 paper_pipeline 里图片处理的整条流程单独拿出来写成一个脚本：
    分类闸门（classify.py）→ 两遍独立读图，有分歧的子图补第三遍（read.py / read_runs.py）
    → 多遍合并和数值门槛（merge.py / pipeline_data.py）→ 反读表和没读清单（backfill.py / finalize.py）
读图提示词、schema、图片长边上限直接 import 自 PDF_project\2_vlm_benchmark\extract.py（与流水线同一份），
闸门和门槛与流水线逐字一致，另外修了流水线里的两处问题：
    1. 堆叠图漏挡：模型把图型写成清单外的名字（stacked_column、percent_stacked_bar …）、记号又只有柱时，
       流水线按记号回推成 bar，绕过堆叠闸门送去读。这里图型名里带 stack 的一律按堆叠图不读。
    2. 第三遍补读：流水线整图模式下补第三遍会把整张图要读的子图全部重读一遍；这里只读有问题的子图。
       只画了线、每一遍都没读出点的子图，也不再被当成"缺失"去触发第三遍（流水线只在整张图都是这种
       子图时才不补读）。2026-10-09 起图只为某一遍漏读的点补第三遍，见 12。
之后按用户要求和实际跑出来的问题又改了几处（2026-10-05）：
    3. 蛋白质体系也包括蛋白质被包埋、负载在载体里的体系（如包埋藻蓝蛋白的海藻酸盐纳米凝胶）；分类时把文章标题
       （figure_markdown.md 第一行）一起交给模型，因为图注常常只写载体名。
    4. 分类模型把一个字母下的几张小图都标成同一个字母时，逐个子图过闸门、要读的名单去重，读图指令交代系列名带上
       小标题（只有这种情况才加这句），免得几张小图的同名系列合并成「同键多值」。
    5. 要读的指标从 12 项加到 17 项：加浊度、水解度、游离氨基含量、包埋率和负载率、抗氧化活性（同样只算蛋白质体系）。
    6. 每张图分类时附上全篇所有图注的原文（figure_markdown.md 里的，按页面顺序，不经模型总结），好前后对照缩写、
       样品名和整篇研究的体系（2026-10-06）。每张图仍然单独分类；读图不变，只带这张图自己的图注。
    7. 子图没有字母编号、图里又不止一个子图时，给要读的子图起名「未编号1」…，读图指令里按图型和坐标轴点名，
       不再整图送读（2026-10-06，afres.2026.102130 图 5）。只有一个子图的图照旧整图读。
    8. 读图自检没过，当场用同样的输入再读一次；连续两次不过就不再重读，这张图在评价里写明读图失败，整篇照常完成
       （原来整篇停下，每次重跑都白花一遍）。网络或接口报错不算，照旧整篇先停、重跑接着做（2026-10-06）。
    9. 账户没钱、key 无效、没有模型权限：整个窗口立刻停下，屏幕上写清楚原因和怎么接着做，不再一篇接一篇地失败；
       被限流：不算失败，按 OpenAI 给的时间等着重试（最多 30 分钟）；每 10 分钟显示一次这一分钟的限额还剩多少（2026-10-08）。
   10. 可以走 OpenRouter（--base-url https://openrouter.ai/api/v1 --model openai/gpt-6-astra --key-env OPENROUTER_API_KEY）：
       模型照旧 gpt-6-astra，只用 OpenAI 标准那一家（provider only=openai、不切别家）；OpenRouter 的 402 没钱同样整个窗口停下，
       502 / 503 暂时没有可用的服务器等着重试，403 内容审核只算这一张；断点指纹里 openai/gpt-6-astra 和 gpt-6-astra 算同一个模型
       （2026-10-08，OpenAI 账户没钱后转 OpenRouter）。
   11. 一个子图里又分成几格、各格坐标轴不同的（散点矩阵、配对图、边际图）不读：分类填 scatter_matrix，闸门挡下、
       评价里写明（2026-10-08，acsfoodscitech.2c00342 图 3c 两遍 333 个点全对不上）。坐标轴相同、只是样品不同的几张小图照常读。
   12. 图分开独立读两遍，读数相差超过 5% 的点不再补第三遍（离散度按各遍最大最小值算，补了也过不了门槛），表里取两遍的
       平均值、写出两遍读数和相差多少、判定为「需人工复核」；第三遍只补某一遍漏读的点。图片版表格照旧（两遍抄得不一样时
       第三遍按多数采用）（2026-10-09）。2026-10-12 起相差超过 5% 的又补第三遍、三遍两遍一致就采用，见 18。
   13. 每次调用的用量（输入、其中缓存命中、输出、其中思考）按分类 / 读图分开记：每篇完成后在日志里写一行，窗口结束时写合计；
       可选：分类用另一个模型（--classify-model）、分类时调低推理强度（--classify-effort）、分类回答瘦身（--classify-slim），
       读图一律用 --model。
   14. 两段式（--prescreen-model，2026-10-09）：先用便宜模型宽松初筛，只问每张图有没有子图可能是 17 项之一（沾边、拿不准
       都算，不管是不是蛋白质体系），判成没有的不做正式分类；初筛出错的照样正式分类。用户 2026-10-09 起用不起 gpt-6-astra，
       bat 改成 gpt-6-luna 初筛 + google/gemini-3.8-flash 分类和读图，都走 OpenRouter（--provider openai,google-ai-studio）。
       2026-10-10 起脚本的默认值也是这一套（用户：「脚本也改成新的」），不带参数直接跑就是这个流程；
       要回到原来的 OpenAI 直连 gpt-6-astra，见下面用法最后一条。
   15. 合并时同一个意思的不同写法不算冲突：轴倍率空着 / 1 / ×1，10^5 / x10^5 / ×10⁵，单位 ℃ / °C、µ / μ，一遍没写单位
       （gemini 两遍常常这样，原来整组转人工）；表里照旧显示原来的写法（2026-10-09）。
   16. 分类提示写明哪些算蛋白质（明胶 / GelMA、胶原、丝素、zein、乳清和大豆等植物蛋白、酶、肽和多肽，以及主要成分里
       有它们的复合体系），拿不准填 true（2026-10-09，便宜模型最常在这里判错漏读）。
   17. 用户 2026-10-09 定的不读：粒径只读平均粒径的柱状图、点图，粒径分布曲线和分布直方图不读（「太多了没必要」）；
       温度、应变（振幅）、应力扫描曲线和成胶时间扫描、蠕变或应力松弛模型拟合出的模量参数、纤维的长度和直径一律不读。
       分类提示写明；代码闸门另外挡粒径分布（粒径或乳滴大小在 X 轴、Y 轴不是粒径）和温度 / 应变 / 应力扫描（X 轴是这些、
       Y 轴是模量），和频率扫描一样不列进「没读的功能特性子图」。时间扫描只靠提示（G′ 随储存天数变化的图代码分不清）。
   18. 合并和门槛（用户 2026-10-12，按现有 135 篇结果里没过门槛的原因改）：
       - 配对：各遍对同一条系列的写法不同（全角半角、破折号和冒号、大小写、模型自己加的「[bar]」「（点线）」）统一后再配；
         哪一遍里有两条系列写法统一后一样，就不统一。没写 X 的点每遍最多一个时配成同一个点（原来各自成簇、都算一遍读出）。
       - 一致：离散度不超过 5%，或几遍最多只差纵轴满量程（读图自报的最大减最小刻度）的 1%，都算一致；后一种在表里写明。
       - 图两遍不一致的点也补第三遍：三遍里两遍一致的，表里给这两遍的平均值、写明没采用的那遍，仍转人工复核（实测 16 篇，
         这样凑出来的点只有约三成和 astra 差在 5% 以内，用户选「F」）；三遍两两都不一致取中位数转人工复核。
         第三遍按子图补读：同一子图里前两遍本来就一致的点只用前两遍，第三遍读偏了也不影响它。
       - 单位前面多写了指标名的（「FS %」和「%」）不算单位冲突；只在第三遍里出现的点照样列出（用户 2026-10-12）。
       - 第三遍沿用前两遍的名称：读图指令末尾给出前两遍写法统一后一致的系列名和样品名（第一遍的写法），只给名字、不给读数；
         第一遍和第二遍仍完全独立（用户 2026-10-12；实测第三遍常给系列另起名，配不上对、白读）。
   19. 用户 2026-10-12 看了全量测试（astra 处理过的 407 篇）后定：模型预测值对实验值的验证图明确不读；压缩 / 拉伸强度、
       杨氏模量、韧性等力学性能不算凝胶性，水凝胶、膜、微球的溶胀率不算持水性（面粉、淀粉的溶胀力仍算）。分类和初筛提示写明，
       代码闸门另外按轴标题挡（和频率扫描一样不列进「没读的功能特性子图」）。配对时系列名用词一样、只是顺序不同的算同一条。
       看了 ACS 100 篇新文章后又定：只有一遍读出的点照样列在表里，入库判定一栏标「只有一遍读出」（不入库，原因一栏不另写）；
       单位中间多写了被测物名的（mol free thiol / mol protein 和 mol/mol protein）、倍率写进单位的（10^-6 mol L^-1 和
       x 10⁻⁶ mol L⁻¹、mol L^-1 加倍率 10^-6）都不算冲突。纵轴倒过来画（ζ-电位越往上越负）时模型常把误差棒两端对调：
       自检和合并都按大小排一下两端再比（jafc.0c01250 图 5A 原来两遍都因「误差棒范围异常」判读图失败）。
       分类给没印编号的子图起的泛称（inset、main 等，jafc.0c05792 图 1 色谱图里嵌的小柱图）当作没有编号，走「未编号N」。
       读完每篇另写 反读数据.json（建库用，和 反读数据.md 放在一起），见输出一节。
   20. 用户 2026-10-13 看了全量 ACS 的结果后定：名字配不上的系列按数值配。同一子图、同一纵轴上只在一遍里出现的系列，
       和这一遍里没有的另一个系列，相同 X 至少 2 个、不少于较短那条的一半，其中至少八成读数按上面的标准一致，就算同一条
       （一对一，配上同一遍两条的不配；没认出系列的 UNRESOLVED 不参与）。实测 jf0607866 三遍把同一条浊度线写成「Turbidity」
       「Turbidity (A600)」「Turbidity (A600, RU)」，原来各自只算一遍读出；全量里只有一遍读出的点约三成是这种。
       --redo-no-json：只重读老脚本读过、没有 反读数据.json 的文章（用户 2026-10-12）。
   21. 用户 2026-10-13 看了全量 ACS 里读图失败的 11 张图后定「全都改」，提升泛化能力：
       - 第三条纵轴：读图 schema 在 extract.py 的基础上加 y_third，系列 axis 可填 third（三条纵轴的图原来第三条轴的
         系列只能挂到左右轴上，读数和刻度对不上，整张图失败）；同一图例系列在不同样品上对不同纵轴的，按纵轴拆成两个系列；
         两层横轴把两层都写进样品名、系列只用图例。读图指令写明（AXIS_NOTE）。
       - 对数纵轴的刻度自检按一个数量级算（原来按线性刻度，只许超出 0.09）。
       - 少数点超出自报刻度（图上文字标出的冲出坐标轴的数、放错纵轴的一条系列）只丢这几个点，不让整张图失败；
         超出的过半照旧判失败。丢了什么写进「反读数据评价」。
       - 点上的系列名不在系列列表里：子图只有一条系列时就是它；多条系列时只丢这些点（不过半），过半照旧判失败。
       - 子图名多了括号说明（「A (lower panel)」）去掉后唯一对得上，认作同一个。
       - 质构（TPA）的硬度、弹性、咀嚼性、内聚性、回复性等不算凝胶性（原来的凝胶性定义里写了「硬度和弹性等质构指标」，
         用户定不算）：分类、初筛提示写明，代码闸门按纵轴标题另外挡。凝胶强度、储能模量、最小凝胶浓度照旧算。
       - 单位里有读图模型吐出的坏字符（\\x00、单独的组合附加符号）的，当作这一遍没写单位，不算单位冲突。
       - 同一系列里样品名写法不同的配成同一个点（cat_key：全半角、标点、大小写、• 分隔、数字和单位间的空格、
         h / hr / hrs 等单位写法都不分，每个词都带字母时词序也不分）；同一遍里有两个样品名统一后一样的不统一。不按读数配（不同样品读数相近的多）。
   22. 用户 2026-10-19 看了 Elsevier 结果里读图失败的 18 篇、52 个子图后定：
       - 一张图同样的输入连续两次没过自检时，只把没过自检的子图记读图失败，过了的子图照常合并（salvage；原来整张图
         全丢：foodchem.2025.143276 图 7 只有 I 刻度对不上，A–J 九个子图都没数）。每一遍都没过的子图不再补第三遍。
       - 读图指令补四条（AXIS_NOTE、MULTI_PLOT_NOTE）：横向柱状图数值照样填 y_value、y_left 填横轴那条数值刻度
         （jfoodeng.2026.113076 图 5B 把 pH 2–8 当成数值刻度）；系列对哪条纵轴看纵轴颜色和标题、读数要落在那条轴的
         刻度里（carbpol.2026.125601 图 4B 把 ζ-电位挂到 PDI 轴上）；刻度漏印负号时刻度和读数都写成负数（foodchem.2025.143276
         图 7I）；一个字母下并排几张小图时 panel_id 都填这个字母、系列名带小图标题（foodhyd.2024.110612 图 9d）。
   23. 用户 2026-10-21 把 ACS 整理成 D:\acs_papers_done\papers\<文章>（旁边 _records、database）：给总文件夹也能找到文章；
       文章换了位置，断点按文章文件夹名接着用（路径指纹变了也不白读）。ACS 的 bat 改成 D:\acs_papers_done。
       用户同日：「脚本优先有跑断点的文章」——停在断点的先接着做完，再开没开始的（开几个窗口时两段各自错开起点）。
不包括：抓取（输入是 opencli_fetch 里抓取脚本的产物）、子图裁切（流水线默认也不裁）、条件关联、原文校正。

用法（用 miniconda 的 python；默认 luna 初筛走 OpenAI 直连、key 取自 OPENAI_API_KEY，gemini 分类、读图走 OpenRouter、
key 取自 OPENROUTER_API_KEY。2026-10-12 新 OpenRouter 账户每分钟只许 20 个 luna 请求，初筛改成直连）：
    python figure_reader.py                         处理 D:\2.elsevier_papers 下的全部文章（10-15 起 Elsevier 放在 D 盘）
    python figure_reader.py D:\1.acs_papers_done      处理 ACS 的全部文章（10-21 起整理成 D:\1.acs_papers_done\papers\<文章>）
    python figure_reader.py <文章文件夹> [...]       只处理这几篇
    python figure_reader.py --dry-run [...]         只列出每篇要送分类的图，不调 API
    python figure_reader.py --status                看每篇的进度
    python figure_reader.py --refresh <文章文件夹>   已经做完的也重做（会重新调 API）
    python figure_reader.py --limit 5               这次最多处理 5 篇
    python figure_reader.py --only-started [...]    只做有断点、还没做完的文章，不开始新的
    python figure_reader.py --redo-no-json [...]    只重读老脚本读过、没有 反读数据.json 的文章（补上 json），别的不碰
    python figure_reader.py --log                   屏幕输出同时存进 figure_reader\日志\
    python figure_reader.py --key-env OPENROUTER_API_KEY_2   用另一个环境变量里的 API key
    python figure_reader.py --slot 2/5              同时开 5 个窗口时这是第 2 个：从五分之一处开始做，到末尾再从头接着
                                                    （跑读图_ACS_1.bat 到 _5.bat 各带一个；不重复靠领取，和它无关）
    python figure_reader.py --prescreen-model none  不初筛，每张图都正式分类
    python figure_reader.py --base-url openai --key-env OPENAI_API_KEY --model gpt-6-astra --prescreen-model none
                                                    原来的流程：OpenAI 直连，gpt-6-astra 分类、读图，不初筛
或者双击 跑全流程.bat（10-21 起只留这一个 bat，读图之后接着做到建库；原来的 跑读图_*.bat 删了）（处理 D:\2.elsevier_papers / D:\acs_papers_done 下的全部文章、
存日志；规则完全一样，只是文章文件夹不同）；拖一个文章文件夹到它上面只跑那一篇。

可以开几个窗口同时跑同一条命令（每个窗口可以用不同的 key）：每篇开始前先在 断点\ 里「领取」，别的窗口看到就跳过，
同一篇不会被重复处理、重复花钱。窗口被关或中断后，它领着的文章别的窗口可以接手（锁 15 分钟没刷新或进程已不在）。

文章文件夹可以直接放在上级目录里（D:\2.elsevier_papers\<文章>），也可以放在整理过的总文件夹的 papers 里
（D:\acs_papers_done\papers\<文章>，旁边的 _records、database 不是文章；用户 2026-10-21），每篇里面的结构一样。
输入（抓取脚本的产物，只读 figure 子文件夹，不读 全文.md；脚本只读不改）：
    <文章>\figure\figure_markdown.md   每张图 / 图片版表格的标题、本地图片和图注
    <文章>\figure\fig1.jpg …           图片（一张图拆成几个文件的，按顺序拼成一张再读；.svg 矢量图先渲染成白底位图，
                                       长边 2048，原文件不动）
输出（两个文件，直接放在文章文件夹里，和 全文.md、figure\ 并列）：
    <文章>\反读数据.md                  读了数的每张图：原图、图注、按子图分的反读表（没过门槛的点也列出并写明原因）；
                                       末尾「反读数据评价」逐个写明没读的蛋白质功能特性子图和原因
    <文章>\反读数据.json                给后面的清理建库用（用户 2026-10-12）：每个送读的子图测的是 17 项里的哪一项、X/Y 轴
                                       标题、图注片段；每个系列在哪个纵轴、那个纵轴的标题、单位和倍率。只给程序读，人看 .md
断点（不放在文章文件夹里）：
    figure_reader\断点\<文章文件夹名>_<路径指纹>\
                                       分类和每一遍读图的原始结果，中断后重跑同一条命令从这里接着来；
                                       整篇成功后直接删除（不存档、不备份）
不读的图：图文摘要、Scheme、流程图、三维响应面，以及不是正文图或表格图片的文件（补充材料 figs、无标题的 fx 图）。

需要：环境变量 OPENROUTER_API_KEY；pip install openai pydantic pillow resvg-py（resvg-py 只在遇到 .svg 图时用）；
      PDF_project\2_vlm_benchmark\extract.py（它另外要 numpy / pandas / tqdm，miniconda 里都有）
同一时间最多 4 个 API 请求（--api-workers），同时处理 3 篇（--paper-workers）。
"""


# 读图的提示词、schema、图片长边上限和 detail 都直接取自评测项目的 extract.py（paper_pipeline\read.py 也 import
# 这一份），不在这里另抄：那边改了，这里自动跟着变（用户 2026-10-05：「让它改成直接调用 extract.py」）。
VE_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, '2_vlm_benchmark', 'extract.py'))


def _load_ve():
    if not os.path.exists(VE_PATH):
        raise SystemExit('找不到 %s —— 读图的提示词和 schema 从它 import，不另写。' % VE_PATH)
    old = sys.modules.get('ve_extract')
    if old is not None and os.path.normcase(os.path.abspath(getattr(old, '__file__', ''))) == os.path.normcase(VE_PATH):
        return old                    # 流水线的 read.load_ve() 已经加载过同一个文件
    import importlib.util
    spec = importlib.util.spec_from_file_location('ve_extract', VE_PATH)
    m = importlib.util.module_from_spec(spec)
    sys.modules['ve_extract'] = m
    spec.loader.exec_module(m)
    return m


VE = _load_ve()

# 用户 2026-10-30：「改 抓取脚本以都默认放这几个文件夹里 这个脚本也改成读取这些文件夹里的内容 和爱斯维尔一样处理」
# 「让那个脚本能通用的处理这八家出版商的全文 从读图到最后的数据点提取 （acs已经处理结束了）」——抓取脚本
# （opencli_fetch\fetch_papers.py）按出版商放在 D 盘 1–8 号总文件夹；read、all 不给文件夹时处理 2–8 号这七个，
# ACS（1 号）已经做完，只进合成的库。「2-8编号的文件夹 经过流水线脚本跑完 应该得到和D:\1.acs_papers_done 一样的结构和内容」：
# 每个总文件夹里 papers\<文章>\、_records\、database\（all 开头把直接放在总文件夹里的文章挪进 papers\，见 organize_root）
ACS_ROOT = r'D:\1.acs_papers_done'
PAPER_ROOTS = (r'D:\2.elsevier_papers', r'D:\3.wiley_papers-part', r'D:\4.RSC_papers', r'D:\5.MDPI_papers',
               r'D:\6.oxford_papers', r'D:\7.Taylor_papers', r'D:\8.Springer nature_papers')
# 用户 2026-10-30：「wiley先跳过吧 处理后面的先」「后面我再看要不要补表题」（Wiley 的 全文.md 几乎都没有表题）——read、all
# 不给文件夹时先不做这几个；要做时 all --root D:\3.wiley_papers-part，或者从这里去掉。建库的合成库照样包括它们
SKIP_ROOTS = (r'D:\3.wiley_papers-part',)
DEFAULT_ROOTS = tuple(r for r in PAPER_ROOTS if r not in SKIP_ROOTS)
FIGURE_DIR = 'figure'                 # 抓取脚本放图片和 figure_markdown.md 的子文件夹
PAPERS_SUBDIR = 'papers'              # 整理过的总文件夹（D:\acs_papers_done）里，文章都在 <根>\papers\<文章>（用户 2026-10-21）
MD_NAME = '反读数据.md'                # 结果（用户 2026-10-02：不要 csv、不要子文件夹）
DB_NAME = '反读数据.json'              # 建库用的分类和轴标题，和 反读数据.md 放在一起（用户 2026-10-12）
CHECKPOINT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '断点')   # 断点放脚本旁边，成功后删
DONE_MARK = '<!-- figure-reader:v1 input=%s -->'   # 记下 figure_markdown.md 的指纹：重抓过的文章自动重做

# 默认流程（用户 2026-10-10：「脚本也改成新的」，和 bat 一样）：经 OpenRouter，luna 宽松初筛 → gemini 正式分类、读图
MODEL = 'google/gemini-3.8-flash'     # 正式分类和读图都用它
PRESCREEN_MODEL = 'openai/gpt-6-luna' # 初筛用它（--prescreen-model none = 不初筛）
# 初筛走 OpenAI 直连、key 取自 OPENAI_API_KEY（用户 2026-10-12：新 OpenRouter 账户每分钟只许 20 个 luna 请求，5 个窗口跑不动；
# 分类和读图照旧走 OpenRouter）。--prescreen-base-url same = 和别的步骤走同一个接口
PRESCREEN_BASE_URL = 'openai'
PRESCREEN_KEY_ENV = 'OPENAI_API_KEY'
KEY_ENV = 'OPENROUTER_API_KEY'        # 从哪个环境变量取 API key；几个 key 各开一个窗口时用 --key-env 换
OPENROUTER = 'https://openrouter.ai/api/v1'
BASE_URL = OPENROUTER                 # --base-url openai = OpenAI 直连
# 走 OpenRouter 时每个模型只用自己那家（用户 2026-10-08 起；不切 fast / Azure / 别家）。gemini 走 flex 档（用户 2026-10-14：
# 同一个模型 gemini-3.8-flash-20260902，价格是标准档的一半；排队、单个请求慢一些，偶尔排满时报 502/503，照常等着重试）。
# Google AI Studio 和 Vertex 的 flex 同价，两家都列上，一家排满时走另一家
OPENROUTER_PROVIDER = 'openai,google-ai-studio/flex,google-vertex/global/flex'
# OpenRouter 没钱了（402）：gemini 的请求自动改走 Google 官方接口（OpenAI 兼容），key 取自 GEMINI_API_KEY，照旧 flex 档
# （用户 2026-11-04：「当现在用的key没有余额了 自动切换到这个key 依旧用gemini-3.8 flash flex版跑」）；初筛的 luna 不受影响。
# 没设这个环境变量就照旧停下。官方 flex 排满时回 503（「high demand」），照常等着重试
GEMINI = 'https://generativelanguage.googleapis.com/v1beta/openai/'
GEMINI_KEY_ENV = 'GEMINI_API_KEY'
GEMINI_TIER = 'flex'
MAX_SIDE = VE.MAX_SIDE               # 送给模型的图片长边上限（取自 extract.py，与流水线和评测基准一致）
DETAIL = VE.DETAIL
API_WORKERS = 4                       # 同时进行的 API 请求上限（用户 2026-09-29：名额维持 4）
PAPER_WORKERS = 3
RUNS = 2                              # 先独立读两遍
READ_TRIES = 2                        # 同样的输入，读图自检连续两次不过就不再重读（用户 2026-10-06）
ESCALATE = 5.0                        # 两遍离散度超过 5% 的子图补读第三遍
SPREAD_OK = 1.0                       # 离散度 ≤1% 且每遍都读出值才算 high
MIN_CONF, MAX_SPREAD = 'medium', 5.0  # 数值门槛：一致性不低于 medium，离散度不超过 5%
FS_TOL = 1.0                          # 或者几遍读数最多只差纵轴满量程的 1%，也算一致（小数值、矮柱；用户 2026-10-12）
DENSE_LIMIT = 40                      # 每个子图预估总点数超过 40 的不读
MATCH_TOL = 0.25                      # 数值 X 配对容差 = 本遍相邻点距 × 0.25


# =============================================================== 子图编号 ==
def panel_key(value, case=False):
    """(a)、a、A 是同一个子图；一张图里同一字母大小写各是一个子图时（A–D 和 a–d，case=True）保留大小写。"""
    if value is None:
        return None
    text = str(value).strip()
    bare = text.strip('()（）[] ').strip()
    if not re.fullmatch(r'[A-Za-z]\d*|\d+', bare):
        return text
    return bare if case else bare.upper()


def case_distinct(labels):
    """True when a figure's labels use the same letter in both cases (A and a)."""
    bare = {str(x).strip().strip('()（）[] ').strip() for x in labels if x}
    letters = {b for b in bare if re.fullmatch(r'[A-Za-z]\d*', b)}
    return any(b.lower() != b.upper() and b.lower() in letters and b.upper() in letters for b in letters)


def label_cn(t):
    return ('表 %s' if t['kind'] == 'table' else '图 %s') % t['label']


def part_cn(t):
    return '指标' if t['kind'] == 'table' else '子图'


# =============================================================== 输入 ==
# 抓取脚本的 figure_markdown.md：「## 标题」一项一节，节里是本地图片行、下载失败行、图注和表注段落
HEAD_LINE = re.compile(r'^##\s+(.+?)\s*$')
IMAGE_LINE = re.compile(r'^!\[[^\]]*\]\(([^)\s]+)\)$')
FAILED_LINE = re.compile(r'^（图片下载失败，原图地址：(.*)）$')
TABLE_MARK = '（图片版表格）'
FIG_LABEL = re.compile(r'^(?i:fig(?:ure|\.e|\.)?)\s*([A-Z]?\d+)\b')     # Fig. 1、Figure 2、Fig. A13；figs1 不算
TABLE_LABEL = re.compile(r'\bTable\s*([A-Z]?\d+)\b', re.I)
SCHEME_LABEL = re.compile(r'^Scheme\s*(\d+)\b', re.I)


def lab(head):
    """认图号用的标题：Wiley 上从别家转过去的老文章（Biotechnology Progress 等 288 篇），页面上的图号就写成「Figure Figure 1」
    「Figure Scheme 1」，前面多的那个 Figure 去掉再认（用户 2026-10-30 八家通用；标题本身照原样，反读数据.md 的块名还是页面上的写法）。"""
    return re.sub(r'^(?i:figure)\s+(?=(?i:fig(?:ure|\.)?|scheme)\s*[A-Z]?\d)', '', head)


def parse_figure_markdown(text):
    """[{key, kind, label, heading, files, failed, caption}]，按页面顺序。
    kind：figure 正文图（Fig. 1、Fig. A13）、table 图片版表格、graphical_abstract、scheme、other（figs1、fx3 …）。"""
    raw, cur = [], None
    for line in text.replace('\r\n', '\n').split('\n'):
        m = HEAD_LINE.match(line)
        if m:
            cur = {'heading': m.group(1), 'files': [], 'failed': [], 'lines': []}
            raw.append(cur)
            continue
        if cur is None:
            continue
        s = line.strip()
        im, fm = IMAGE_LINE.match(s), FAILED_LINE.match(s)
        if im:
            cur['files'].append(urllib.parse.unquote(im.group(1)))
        elif fm:
            cur['failed'].append(fm.group(1))
        else:
            cur['lines'].append(s)
    items, used = [], set()
    for r in raw:
        head = r['heading']
        paras = [' '.join(p.split()) for p in '\n'.join(r['lines']).split('\n\n') if p.strip()]
        caption = ' '.join(paras)
        if head.endswith(TABLE_MARK):
            name = head[:-len(TABLE_MARK)].strip()
            m = TABLE_LABEL.search(name) or TABLE_LABEL.search(caption)
            label = m.group(1).upper() if m else str(len(items) + 1)
            # 「Table N. 表题」加表注，表注里有表内缩写的全称（流水线 classify.table_caption）
            title = paras[0] if paras else ''
            if not re.match(r'(?i)table\s*%s\b' % re.escape(label), title):
                title = ('Table %s. %s' % (label, title)).strip()
            caption = ' '.join([title] + paras[1:])[:1600]
            kind, key = 'table', 'tab' + label
        elif re.search(r'(?i)graphical abstract', head):
            kind, label, key = 'graphical_abstract', '', 'ga'
        elif SCHEME_LABEL.match(lab(head)):
            label = SCHEME_LABEL.match(lab(head)).group(1)
            kind, key = 'scheme', 'sc' + label
        elif FIG_LABEL.match(lab(head)):
            label = FIG_LABEL.match(lab(head)).group(1).upper()
            kind, key = 'figure', 'fig' + label
        else:
            kind, label, key = 'other', head, 'other:' + head
        base, i = key, 2
        while key in used:
            key, i = '%s#%d' % (base, i), i + 1
        used.add(key)
        items.append({'key': key, 'kind': kind, 'label': label, 'heading': head,
                      'files': r['files'], 'failed': r['failed'], 'caption': caption})
    return items


def load_paper(root):
    """读一篇抓取脚本产物的 figure 子文件夹（figure_markdown.md；图片用到时再读）；不是这种目录返回 None。
    全文.md 不读（用户 2026-10-02）：分类时「正文里提到这张图的地方」一栏填（未取到）。"""
    fm = os.path.join(root, FIGURE_DIR, 'figure_markdown.md')
    if not os.path.isfile(fm):
        return None
    with open(fm, encoding='utf-8') as fh:
        text = fh.read()
    title = ''
    m = re.search(r'(?m)^# (.+)$', text)
    if m:
        title = re.sub(r'\s+-\s+ScienceDirect\s*$', '', m.group(1)).strip()
    doi = re.search(r'(?m)^DOI:\s*(\S+)', text)
    items = parse_figure_markdown(text)
    # 全篇所有图注原文，按页面顺序（不含图片链接、DOI、网址）；每张图分类时都附上（用户 2026-10-06）
    captions = '\n'.join('- %s：%s' % (it['heading'], it['caption']) for it in items if it['caption'])
    for it in items:
        it['paper_title'] = title          # 分类时交给模型（classify_text）
        it['paper_captions'] = captions
    return {'root': root, 'name': os.path.basename(os.path.normpath(root)), 'title': title,
            'doi': doi.group(1) if doi else '', 'items': items}


# =============================================================== 图片 ==
def pack_parts(images, gap=24):
    """一张图拆成几个文件时（fig6a、fig6b …）按阅读顺序拼成一张：从左到右排满一行再换行，列数取拼完最长边
    最短的那种（送模型时会缩到 2048，四张竖图叠成一列会糊）。不缩放，不在图上加任何东西。"""
    best = None
    for cols in range(1, len(images) + 1):
        rows = [images[i:i + cols] for i in range(0, len(images), cols)]
        width = max(sum(im.width for im in row) + gap * (len(row) - 1) for row in rows)
        height = sum(max(im.height for im in row) for row in rows) + gap * (len(rows) - 1)
        if best is None or max(width, height) < best[0]:
            best = (max(width, height), rows, width, height)
    _, rows, width, height = best
    canvas = Image.new('RGB', (width, height), 'white')
    y = 0
    for row in rows:
        x = 0
        for im in row:
            canvas.paste(im, (x, y))
            x += im.width + gap
        y += max(im.height for im in row) + gap
    return canvas


def image_paths(paper, item):
    return [os.path.join(paper['root'], FIGURE_DIR, f) for f in item['files']]


def image_digest(paths):
    h = hashlib.sha256()
    for p in paths:
        h.update(os.path.basename(p).encode('utf-8'))
        with open(p, 'rb') as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b''):
                h.update(chunk)
    return h.hexdigest()


def open_image(path, max_side=MAX_SIDE):
    """打开一张图。svg（ACS 有的图出版商只给矢量图，抓取脚本原样存 .svg）PIL 打不开，先用 resvg 渲染成位图：
    白底（透明底转 RGB 会变成黑底），长边直接渲染到 max_side；dpi 给 96（resvg-py 默认 0，
    以 pt 为单位的 svg 会报 SVG has an invalid size）。"""
    if os.path.splitext(path)[1].lower() != '.svg':
        with Image.open(path) as im:
            im.load()
            return im.copy()
    try:
        import resvg_py
    except ImportError:
        raise RuntimeError('读 svg 图需要 resvg-py：pip install resvg-py（%s）' % os.path.basename(path))

    def render(**size):
        png = resvg_py.svg_to_bytes(svg_path=path, background='#ffffff', dpi=96.0, **size)
        im = Image.open(io.BytesIO(bytes(png)))
        im.load()
        return im

    im = render(width=max_side)
    return render(height=max_side) if im.height > im.width else im


def data_url(paths, max_side=MAX_SIDE):
    """图表用 PNG 无损编码，避免压缩糊掉刻度线；长边超过 max_side 按 LANCZOS 缩小。"""
    ims = [open_image(p, max_side) for p in paths]
    if len(ims) == 1:
        im = ims[0]
        if im.mode not in ('RGB', 'L'):
            im = im.convert('RGB')
    else:
        im = pack_parts([x.convert('RGB') for x in ims])
    if max(im.size) > max_side:
        r = max_side / max(im.size)
        im = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format='PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


def fingerprint(context, digest=''):
    return hashlib.sha256((json.dumps(context, sort_keys=True, ensure_ascii=False, default=str)
                           + digest).encode('utf-8')).hexdigest()


# =============================================================== 排除规则 ==
# 图文摘要、流程图、三维响应面不读（用户要求；流水线 figure_policy.py）
FLOW = {'flowchart', 'flow_chart', 'workflow', 'flow_diagram', 'process_diagram'}
SURFACE = {'surface', '3d_surface', 'response_surface', '3d', 'surface_plot'}


def exclusion_reason(caption='', kind='', panels=None):
    if kind == 'graphical_abstract':
        return '图文摘要'
    text = re.sub(r'^(?:\*\*)?(?:fig(?:ure)?\.?|scheme)\s*[a-z]?\d+[.:]?(?:\*\*)?\s*', '', (caption or '').lower()).strip()
    if re.search(r'\bgraphical abstract\b|图文摘要', text):
        return '图文摘要'
    if re.search(r'^(?:flow\s*chart\b|workflow\b|flow diagram\b|流程图)', text):
        return '流程图'
    if (re.search(r'^(?:(?:3d|3-d|three-dimensional)\s+(?:response\s+)?surfaces?\b|三维响应面)', text)
            or (re.search(r'^response surface plots?\b', text) and re.search(r'\b(?:3d|3-d|three-dimensional)\b', text))):
        return '三维响应面图'
    types = {(p.get('chart_type') or '').lower() for p in panels or []}
    if types and types <= FLOW:
        return '流程图'
    if types and types <= SURFACE:
        return '三维响应面图'
    if types and types <= FLOW | SURFACE:
        return '流程图/三维响应面图'
    return ''


# =============================================================== 分类（classify.py） ==
NON_QUANT = {'schematic', 'diagram', 'flowchart', 'workflow', 'architecture',
             'photograph', 'micrograph', 'gel', 'map', 'illustration',
             'tsne', 'umap', 'pca_embedding', 'network_graph', 'chemical_structure'}

# 只读蛋白质的六类功能特性（用户 2026-09-24），2026-09-28 起加六项理化指标；
# 2026-10-05 用户再加：浊度、水解度、游离氨基含量、包埋率和负载率、抗氧化活性
FUNCTIONAL = {'solubility': '溶解度', 'emulsifying': '乳化性', 'foaming': '起泡性',
              'gelling': '凝胶性', 'water_holding': '持水性', 'oil_holding': '持油性',
              'particle_size': '粒径', 'zeta_potential': 'ζ-电位', 'pdi': 'PDI',
              'sulfhydryl': '巯基含量', 'disulfide': '二硫键含量', 'surface_hydrophobicity': '表面疏水性',
              'turbidity': '浊度', 'degree_of_hydrolysis': '水解度', 'free_amino': '游离氨基含量',
              'encapsulation': '包埋率/负载率', 'antioxidant': '抗氧化活性'}
PROPERTY_CODES = ('solubility 溶解度 / emulsifying 乳化性 / foaming 起泡性 / gelling 凝胶性 / '
                  'water_holding 持水性 / oil_holding 持油性 / particle_size 粒径 / zeta_potential ζ-电位 / '
                  'pdi 多分散指数 / sulfhydryl 巯基含量 / disulfide 二硫键含量 / surface_hydrophobicity 表面疏水性 / '
                  'turbidity 浊度 / degree_of_hydrolysis 水解度 / free_amino 游离氨基含量 / '
                  'encapsulation 包埋率和负载率 / antioxidant 抗氧化活性')
Property = Literal['solubility', 'emulsifying', 'foaming', 'gelling', 'water_holding', 'oil_holding',
                   'particle_size', 'zeta_potential', 'pdi', 'sulfhydryl', 'disulfide',
                   'surface_hydrophobicity', 'turbidity', 'degree_of_hydrolysis', 'free_amino',
                   'encapsulation', 'antioxidant', 'none']
# 频率扫描不读：X 轴是频率、Y 轴是模量或损耗角正切两个都中才算
FREQUENCY_X = ('frequency', 'rad/s', 'rad s', 'rad·s', 'hz', 'ω', '频率')
RHEOLOGY_Y = ("g'", 'g′', 'g"', 'g″', 'modulus', 'tan δ', 'tanδ', 'tan delta', 'loss tangent',
              'loss factor', 'η*', 'complex viscosity', '模量', '损耗')


class Panel(BaseModel):
    label: Optional[str] = Field(description='图中标注的子图编号（A/B/C…），没有标注填 null')
    mark_types: List[Literal['bar', 'point', 'line', 'box', 'area', 'other']] = Field(
        default_factory=list, description=(
            '这个子图里画了哪几种数据记号，逐个写：bar 柱，point 点或标记符，line 折线或曲线，'
            'box 箱线，area 面积，other 其他。柱子上还叠着点或线的，bar 和 point/line 都写；'
            '没有数据记号（照片、示意图、结构式）写空列表'))
    chart_type: str = Field(description=(
        'bar / grouped_bar / stacked_bar / line / scatter / combo / box / violin / histogram / '
        'heatmap / pie / schematic / diagram / flowchart / architecture / photograph / '
        'micrograph / tsne / umap / network_graph / chemical_structure / surface / contour / bar_3d / '
        'scatter_matrix / other。'
        'combo = 柱子和点或折线画在同一个子图里（常见左右双纵轴，如 EAI 柱 + ESI 点、FC 柱 + FS 点）；'
        'bar_3d = 立体（三维透视）画法的柱状图；'
        'scatter_matrix = 一个子图里又分成几格、各格坐标轴不同的小图（散点矩阵、配对图、边际图）'))
    x_axis_label: Optional[str] = Field(description='X 轴标题原文，无轴填 null')
    y_axis_label: Optional[str] = Field(description='Y 轴标题原文，无轴填 null')
    caption_part: Optional[str] = Field(description=(
        '作者图注里说明这个子图的那一段，照抄原文（例如图注写「… contact angle (B) …」，'
        '子图 B 填「contact angle (B)」）；图注没有单独说明这个子图填 null'))
    protein_system: bool = Field(description=(
        '结合文章标题和图注判断：这个子图测的对象是不是蛋白质，或以蛋白质为主要功能成分的体系'
        '（蛋白稳定的乳液和泡沫、蛋白凝胶、蛋白-多糖复合物），或蛋白质被包埋、负载在载体里的体系'
        '（如包埋蛋白质的海藻酸盐纳米凝胶、负载蛋白质的脂质体；图注常常只写载体名）。'
        '明胶/GelMA、胶原、丝素、zein、乳清和大豆等植物蛋白、酶、肽和多肽都算蛋白质，主要成分里有它们的复合体系也算；'
        '拿不准填 true。淀粉、多糖、膳食纤维、油脂等本身（不含蛋白质）填 false'))
    functional_property: Property = Field(description=(
        '根据上面两个轴标题和作者图注判断：这个子图画的量是哪一类要读的指标（功能特性或几项理化指标）。'
        + PROPERTY_CODES + '；都不是，或是流变扫描曲线（G′、G″ 随频率、温度、应变、应力或时间变化）、粒径分布曲线、'
        '压缩 / 拉伸强度和杨氏模量等力学性能、质构（TPA）的硬度 / 弹性 / 咀嚼性等指标、水凝胶的溶胀率、'
        '模型预测值对实验值的图，填 none'))
    y_tick_labels: Optional[List[str]] = Field(description=(
        'Y 轴刻度标签，按图上原样逐个抄下来（如 ["0","10","20"]）。无数值轴填 null。'
        '这一项是后续校验用的证据，不要凭印象编。'))
    x_tick_labels: Optional[List[str]] = Field(default=None, description='X 轴原样刻度；横向柱状图必须抄录数值刻度')
    n_series: Optional[int] = Field(description='该子图里的数据系列数，无法判断填 null')
    points_per_series: Optional[int] = Field(description=(
        '**单个系列**上可辨认的数据点/标记个数（折线数其标记，柱状数其柱，'
        '箱线数其箱）。密集到数不清就给一个估计值。无数据点填 null'))
    has_error_bars: bool
    has_significance_letters: bool = Field(description='柱子上方有 a/b/c 或 */** 之类的显著性标注')
    series_overlap_risk: str = Field(description=(
        'low / medium / high —— 系列之间是否互相遮挡到难以分离的程度。'
        '半透明叠加的多组直方图、或系列上面还压着密度曲线，算 high。'))
    overlap_reason: Optional[str] = Field(description='overlap_risk 不是 low 时说明原因，否则 null')


class FigureClass(BaseModel):
    n_panels: int = Field(description='子图数量，整图只有一个就填 1')
    panels: List[Panel] = Field(min_length=1)
    caption_topic: str = Field(description='用一句中文说这张图在讲什么')
    notes: Optional[str] = Field(description='其他需要提醒的，没有填 null')


# 分类回答瘦身（--classify-slim，用户 2026-10-09 同意试）：字段顺序改成先判断要不要读（蛋白质体系、属于哪项指标），
# 不用读的子图其余各栏填 null / 默认值，不再逐栏细看。字段名和类型都不变，闸门照用 FigureClass 解析。
SLIM_ORDER = ('label', 'chart_type', 'protein_system', 'functional_property', 'mark_types', 'x_axis_label',
              'y_axis_label', 'caption_part', 'y_tick_labels', 'x_tick_labels', 'n_series', 'points_per_series',
              'has_error_bars', 'has_significance_letters', 'series_overlap_risk', 'overlap_reason')
assert set(SLIM_ORDER) == set(Panel.model_fields)

PanelSlim = create_model('PanelSlim', **{n: (Panel.model_fields[n].annotation, Panel.model_fields[n])
                                          for n in SLIM_ORDER})
FigureClassSlim = create_model(
    'FigureClassSlim', **{n: (FigureClass.model_fields[n].annotation, FigureClass.model_fields[n])
                          for n in FigureClass.model_fields if n != 'panels'},
    panels=(List[PanelSlim], Field(min_length=1)))
SLIM_RULE = """
- 每个子图先填 chart_type、protein_system、functional_property，判断它要不要读。不是蛋白质体系、或
  functional_property 是 none 的子图，后面各栏从简，不用细看：mark_types 填空列表，x_axis_label、y_axis_label、
  caption_part、y_tick_labels、x_tick_labels、n_series、points_per_series、overlap_reason 都填 null，
  has_error_bars、has_significance_letters 填 false，series_overlap_risk 填 low。要读的子图照常逐栏认真填。"""


SYSTEM = """你是科研插图的分类员。你的任务**不是**读出数据点，而是判断这张图
是否值得交给更贵的模型去反读数值。每个子图按顺序判断两件事。

一、要读的指标（只反读这些）：蛋白质的功能特性，以及粒径、ζ-电位、PDI、巯基和二硫键含量、表面疏水性
这几项理化指标，还有浊度、水解度、游离氨基含量、包埋率和负载率、抗氧化活性。先读这个子图的 X 轴、Y 轴标题，再在作者图注里找到说明
这个子图的那一段，照抄进 caption_part（读图阶段会把它和子图一起交给读数模型）。然后判断：
1. protein_system：测的对象是不是蛋白质，或以蛋白质为主要功能成分的体系（蛋白稳定的
   乳液和泡沫、蛋白凝胶、蛋白-多糖复合物），或蛋白质被包埋、负载在载体里的体系（如包埋蛋白质的
   海藻酸盐纳米凝胶、负载蛋白质的脂质体）。图注常常只写载体名、不写里面包的蛋白质，要结合文章标题判断。
   这些都是蛋白质：明胶（gelatin，包括 GelMA 等明胶衍生物）、胶原、丝素蛋白、玉米醇溶蛋白（zein）、乳清蛋白、
   酪蛋白、大豆/豌豆/米糠等植物蛋白、肌原纤维蛋白、卵清蛋白、乳铁蛋白、肌红蛋白、溶菌酶等各种酶、蛋白水解物和肽、
   聚赖氨酸等多肽；主要成分里有这些的复合体系（如明胶-壳聚糖水凝胶、含明胶微球的水凝胶、蛋白-多酚复合物）也填 true。
   拿不准是不是蛋白质体系时填 true。
   淀粉、多糖、膳食纤维、油脂等本身（不含蛋白质）填 false。
2. functional_property：图上画的量本身是不是下面某一类要读的指标，填对应代号。
- solubility 溶解度：溶解度、可溶性蛋白含量、氮溶解指数（NSI）、蛋白分散指数（PDI，溶解性指标）
- emulsifying 乳化性：乳化活性（EAI）、乳化稳定性（ESI）、乳液稳定性、乳析指数、离心稳定性、析油率
- foaming 起泡性：起泡能力、泡沫稳定性
- gelling 凝胶性：凝胶强度、各样品凝胶的储能模量数值、最小凝胶浓度；压缩强度、拉伸强度、杨氏模量、韧性、
  断裂应变等力学性能，和质构（TPA）的硬度、弹性、咀嚼性、胶黏性、内聚性、回复性、黏附性都不算，填 none
- water_holding 持水性：持水力、吸水性（WHC、WAC、WBC）、溶胀力、膨胀力；水凝胶、膜、微球的溶胀率（溶胀比）不算，填 none
- oil_holding 持油性：持油力、吸油性（OHC、OAC、OBC）
- particle_size 粒径：平均粒径、Z-均粒径、D[4,3]、D[3,2] 等粒径数值（画成柱状图或点图的）
- zeta_potential ζ-电位：ζ-电位（zeta potential）
- pdi 多分散指数：粒径测定给出的多分散指数（PDI，polydispersity index）；溶解性指标「蛋白分散指数」仍填 solubility
- sulfhydryl 巯基含量：游离巯基、总巯基（SH）含量
- disulfide 二硫键含量：二硫键（S–S）含量
- surface_hydrophobicity 表面疏水性：表面疏水性指数（H₀、S₀），包括 ANS 等荧光探针法测得的
- turbidity 浊度：浊度，以及用某一个波长的吸光度（如 A600、A350）表示的浑浊或聚集程度
- degree_of_hydrolysis 水解度：水解度（DH）
- free_amino 游离氨基含量：游离氨基（–NH₂）含量，包括 OPA、TNBS、茚三酮等方法测得的
- encapsulation 包埋率和负载率：包埋率（包封率，EE）、负载率（载药量，LC）
- antioxidant 抗氧化活性：DPPH、ABTS、羟自由基等自由基清除率，还原力、FRAP、ORAC，金属离子螯合能力
凝胶或乳液的频率扫描曲线（G′、G″ 随频率变化）不读，填 none。温度扫描、应变（振幅）扫描、应力扫描和
成胶时间扫描曲线（G′、G″ 随温度、应变、应力或时间变化），用蠕变或应力松弛模型（Burgers、Maxwell 等）拟合出的
模量参数，也都不读，填 none。
粒径分布曲线和粒径分布直方图（横轴是粒径、纵轴是强度 / 体积 / 数量占比）不读，填 none；纤维（如淀粉样纤维）的
长度和直径不算粒径，填 none。
模型预测值对实验值（实测值）的图（响应面、机器学习等模型的验证图，横轴、纵轴是同一个指标的实验值和预测值）不是测定数据，
不读，填 none。
只用来解释上面这些指标为什么变化的其他结构或理化表征填 none，例如接触角、界面张力、
荧光/紫外/红外/圆二色光谱、二级结构、X 射线衍射或小角散射（含 Guinier、Kratky 图）、热分析、
分子量和电泳、微观形貌、低场核磁、消化特性、成分或元素含量（巯基、二硫键、游离氨基含量除外）。
示意图、照片这类没有测定数据的也填 none。

二、能不能反读：图上是否存在**带刻度的数值坐标轴**，使得图形元素（柱端、点中心、
线的转折）可以被换算成数字。

要点：
- 架构示意图、流程图、实验流程、化学结构、照片、显微照片、凝胶电泳图、地图：
  没有可反读的数值，chart_type 按实际填，y_tick_labels 填 null。
- t-SNE / UMAP / PCA 散点：虽然有坐标轴，但坐标本身无物理含义，
  chart_type 填 tsne / umap / pca_embedding。
- 三维响应面填 surface；不反读三维响应面，保留原图即可。
- 立体（三维透视）画法的柱状图填 bar_3d：柱顶和坐标刻度不在同一个平面上，读不准，保留原图即可。
  普通的平面柱状图，柱子带一点阴影或渐变色的，照常填 bar / grouped_bar。
- 一个子图里又分成好几格小图、各格用不同的坐标轴（散点矩阵、配对图、边际图，例如四格分别是吸水性对蛋白、
  吸油性对糖……）的，填 scatter_matrix：点多、各格的轴又不一样，读不准，保留原图即可。
  几张小图用同样的坐标轴、只是样品或条件不同（各有自己的小标题）的不算，照常判断。
- 先在 mark_types 里写出这个子图画了哪几种数据记号（柱、点、线……），再定 chart_type。
- 柱子和点（或折线）画在同一个子图里、常带左右两个纵轴的，填 combo，不要填 other；
  mark_types 里 bar 和 point/line 都写上。
  other 只留给真的没法按坐标读数的图型（雷达图、桑基图等）。
- 热图（heatmap）：如果有色标而不是数值轴，y_tick_labels 填 null。
- y_tick_labels 必须是你在图上真实看到的刻度文字，原样抄写。这项会被交叉校验，
  编造会被查出来。
- 一张图有多个子图时，逐个子图分别判断，不要用整图一个结论盖过去。
- points_per_series 要数**一个系列**上的标记数，不是全部系列的总和。
  这个数字下游用来判断该子图值不值得反读，估偏了会直接影响决策。"""

FUNCTIONAL_RULES = SYSTEM[SYSTEM.index('- solubility'):SYSTEM.index('\n\n二、')]


class Measure(BaseModel):
    header: str = Field(description=(
        '这项测定指标在表里的表头，照抄原文（含单位和符号）；多级表头从上到下用空格连起来，'
        '例如上层「EAI (m²/g)」、下层「pH 7」写成「EAI (m²/g) pH 7」'))
    layout: Literal['column', 'row'] = Field(description='这项指标在表里占一列填 column；指标排在行上、占一行的填 row')
    protein_system: bool = Field(description=(
        '结合文章标题、表题和表注判断：这项指标测的对象是不是蛋白质，或以蛋白质为主要功能成分的体系'
        '（蛋白稳定的乳液和泡沫、蛋白凝胶、蛋白-多糖复合物），或蛋白质被包埋、负载在载体里的体系'
        '（如包埋蛋白质的海藻酸盐纳米凝胶、负载蛋白质的脂质体；表题常常只写载体名）。'
        '明胶/GelMA、胶原、丝素、zein、乳清和大豆等植物蛋白、酶、肽和多肽都算蛋白质，主要成分里有它们的复合体系也算；'
        '拿不准填 true。淀粉、多糖、膳食纤维、油脂等本身（不含蛋白质）填 false'))
    functional_property: Property = Field(description=(
        '根据表头和作者表题、表注判断：这项指标是哪一类要读的指标（功能特性或几项理化指标）。'
        + PROPERTY_CODES + '；都不是填 none'))
    n_values: int = Field(description='这项指标下印了数值的格子有几个；没有数值（全是文字或空格子）填 0')
    has_sd: bool = Field(description='数值带 ± 标准差或标准误')
    has_significance_letters: bool = Field(description='数值后面带 a/b/c 之类的显著性字母')


class TableClass(BaseModel):
    measures: List[Measure] = Field(min_length=1, description=(
        '表里的每一项测定指标，按表里的顺序逐项列出；样品名、处理条件这类说明列不算。'
        '整张表都没有测定数值（只有样品编号、配方、处理条件的文字）时，照样列出各列表头，'
        'functional_property 填 none，n_values 填 0'))
    caption_topic: str = Field(description='用一句中文说这张表在讲什么')
    notes: Optional[str] = Field(description='其他需要提醒的，没有填 null')


TABLE_SYSTEM = """你是科研表格的分类员。这张图片是论文里作者排成图片的一张表格。你的任务**不是**抄数，
而是判断表里哪些测定指标值得交给更贵的模型去反读数值。逐项列出表里的测定指标（通常一列一项；
指标排在行上的表，一行一项），每项判断两件事：
1. protein_system：测的对象是不是蛋白质，或以蛋白质为主要功能成分的体系（蛋白稳定的
   乳液和泡沫、蛋白凝胶、蛋白-多糖复合物），或蛋白质被包埋、负载在载体里的体系（如包埋蛋白质的
   海藻酸盐纳米凝胶、负载蛋白质的脂质体）。表题常常只写载体名、不写里面包的蛋白质，要结合文章标题判断。
   这些都是蛋白质：明胶（gelatin，包括 GelMA 等明胶衍生物）、胶原、丝素蛋白、玉米醇溶蛋白（zein）、乳清蛋白、
   酪蛋白、大豆/豌豆/米糠等植物蛋白、肌原纤维蛋白、卵清蛋白、乳铁蛋白、肌红蛋白、溶菌酶等各种酶、蛋白水解物和肽、
   聚赖氨酸等多肽；主要成分里有这些的复合体系（如明胶-壳聚糖水凝胶、含明胶微球的水凝胶、蛋白-多酚复合物）也填 true。
   拿不准是不是蛋白质体系时填 true。
   淀粉、多糖、膳食纤维、油脂等本身（不含蛋白质）填 false。
2. functional_property：这项指标本身是不是下面某一类要读的指标，填对应代号。
""" + FUNCTIONAL_RULES + """

要点：
- header 照抄表头原文，含单位和符号；多级表头从上到下用空格连起来。
- 结合作者表题和表注判断测的是什么、对象是什么；表头只写了缩写的（如 WHC、EAI），按表注里的全称判断。
- n_values 数这项指标下印了数值的格子；has_sd、has_significance_letters 按格子里实际印的填。"""

# 用户 2026-10-06：每张图分类时都附上全篇所有图注的原文（不经模型总结），好前后对照缩写、样品名和整篇研究的体系
CAPTIONS_BLOCK = """全篇所有图和表格的图注（figure_markdown.md 原文，按页面顺序；可能为空）。只用来前后对照，比如缩写和
样品名的全称、整篇研究的是什么体系；要判断的是**这一张**，以它自己的图注和图像为准：
{captions}

"""

TABLE_USER = """判断这张表格图片（论文 Table {n}）。逐项列出测定指标：先抄表头，结合表题和表注判断
测的是不是蛋白质、属于哪类要读的指标。

文章标题（可能为空）：
{title}

""" + CAPTIONS_BLOCK + """这张表的表题和表注（可能为空）：
{caption}

正文里提到这张表的地方（可能为空）：
{mentions}"""

USER = """判断这张科研插图。逐个子图填写：先抄 X 轴、Y 轴标题，结合图注判断测的是不是蛋白质、
属于哪类要读的指标，再判断能不能反读；y_tick_labels 按图上原样抄。

文章标题（可能为空）：
{title}

""" + CAPTIONS_BLOCK + """这张图的图注（可能为空）：
{caption}

正文里提到这张图的地方（可能为空）：
{mentions}

注意：图注有时会骗人 —— 机理示意图的标题也可能写成
「Effect of X and Y on Z」。以**图像本身**为准，图注和正文只作旁证。"""

# 宽松初筛（--prescreen-model，用户 2026-10-09）：17 项编上 1–17 号、提示词压短，只问这张图里有没有子图画的量**可能**是
# 其中之一（沾边、拿不准都算，不管是不是蛋白质体系、好不好读），模型只回编号；回了编号的送正式分类，回 0 的跳过不处理。
# 用户原话「只回复是或不是」——回编号和回「是」一样短，判定一样，多送的时候还能看出它认成了哪一项。
# 实测（分类对比，gpt-6-luna 经 OpenRouter，下面这版说法）：astra 送读的 223 张抓到 222 张（漏的 1 张是凝胶化时间，
# 不在 17 项里），没读的多送 14%；按全部图推算约 22% 的图送正式分类；每张约 $0.0004。之后用户又定粒径分布曲线、
# 温度 / 应变 / 应力 / 时间扫描、模型拟合的模量、纤维长度和直径不读，加进了「这些不算」。
# 用户 2026-10-09：只用 17 项原来定义里的说法（原先加的凝胶化时间、屈服应力、脱水收缩、TBARS、ROS 等沾边说法删掉）
SCREEN_HINTS = {
    'solubility': '溶解度、可溶性蛋白含量、氮溶解指数 NSI、蛋白分散指数',
    'emulsifying': '乳化活性 EAI、乳化稳定性 ESI、乳液稳定性、乳析指数、离心稳定性、析油率',
    'foaming': '起泡能力、泡沫稳定性',
    'gelling': '凝胶强度，储能模量，最小凝胶浓度',      # 质构（TPA）不算（用户 2026-10-13）
    'water_holding': '持水力、吸水性（WHC、WAC、WBC），溶胀力、膨胀力',
    'oil_holding': '持油力、吸油性（OHC、OAC、OBC）',
    'particle_size': '平均粒径、Z-均粒径、D[4,3]、D[3,2]',
    'zeta_potential': 'zeta potential、表面电荷',
    'pdi': '多分散指数',
    'sulfhydryl': '游离巯基、总巯基（SH）',
    'disulfide': 'S–S',
    'surface_hydrophobicity': 'H₀、S₀，ANS 等荧光探针法',
    'turbidity': '浊度，用单一波长吸光度（A600、A350 等）表示的浑浊或聚集',
    'degree_of_hydrolysis': 'DH',
    'free_amino': '–NH₂，OPA、TNBS、茚三酮法',
    'encapsulation': '包埋率（包封率，EE）、负载率（载药量，LC）',
    'antioxidant': 'DPPH、ABTS、羟自由基等自由基清除率，还原力、FRAP、ORAC，金属离子螯合',
}
assert list(SCREEN_HINTS) == list(FUNCTIONAL)
SCREEN_ITEMS = tuple(FUNCTIONAL.values())
SCREEN_SYSTEM = """你是科研插图的初筛员：看这张图（或表格图片）里有没有哪个子图画的量**可能**是下面 17 项指标之一。
有的图交给更细的模型复核，没有的直接跳过、再也没人看，所以宁可多送，不要漏：沾边的、拿不准的都算；
不管测的是不是蛋白质（多糖、水凝胶、膜、颗粒、肉制品……照样判），也不管图好不好读。

""" + '\n'.join('%d %s：%s' % (i + 1, FUNCTIONAL[k], v) for i, (k, v) in enumerate(SCREEN_HINTS.items())) + """

这些不算：照片、显微照片、示意图、流程图、化学结构、电泳胶图；各种谱图（红外、拉曼、紫外、荧光发射谱、圆二色、
XRD、XPS、核磁、质谱）；DSC、TGA；分子量分布；粒径分布曲线和分布直方图；流变扫描曲线（G′、G″ 随频率、温度、
应变、应力或时间变化）和模型拟合出的模量参数；纤维的长度和直径；颜色、接触角、界面张力、细胞存活率、抑菌、
动物实验、感官评分；压缩 / 拉伸强度、杨氏模量、韧性等力学性能；质构（TPA）的硬度、弹性、咀嚼性、内聚性、
回复性等指标；水凝胶、膜、微球的溶胀率；模型预测值对实验值的图。

只回答编号：可能是哪几项就写哪几项（如 4, 5），一项都不是写 0。"""


class Screen(BaseModel):
    indicators: List[int] = Field(description='可能是哪几项的编号（1–17）；一项都不是写 0')


def screen_text(item):
    """初筛时 user 消息里的文字：文章标题和这张图自己的图注（不附全篇图注，提示词尽量短）。"""
    what = '表格图片（论文 Table %s）的表题和表注' % item['label'] if item['kind'] == 'table' else '图的图注'
    return '文章标题（可能为空）：\n%s\n\n这张%s（可能为空）：\n%s' % (
        item.get('paper_title') or NO_MENTIONS, what, item['caption'] or NO_MENTIONS)


def screen_hits(parsed):
    """初筛回答里的有效编号（1–17）；回 0、空列表或别的数都算没有。"""
    return sorted({n for n in parsed.indicators if 1 <= n <= len(SCREEN_ITEMS)})

# 谱图 / 一级结构图不读，判别只看 X 轴（按 Y 判会误杀 Turbidity A600 这类随处理时间变化的曲线）
SPECTRAL_X = (
    'wavenumber', 'wave number', 'wavelength', 'raman shift', 'chemical shift',
    'm/z', 'mass-to-charge', '2theta', '2θ', 'diffraction angle',
    'binding energy', 'retention time', 'elution', 'migration distance',
    '2-theta', 'scattering vector', 'q (', 'energy (ev',
)
PPM_SPECTRAL_CTX = ('chemical shift', 'nmr', '1h', '13c', 'δ', 'delta',
                    'shift (ppm', 'ppm)')
PPM_CONC_CTX = ('concentration', 'conc.', 'dose', 'dosage', 'level',
                'content', 'addition', 'loading')
PRIMARY_STRUCTURE_X = (
    'amino acid', 'residue', 'sequence position', 'molecular weight marker',
    'lane', 'sds-page', 'electrophoresis',
)
# 文献计量图（每年多少篇论文）不是本文实验数据：按 Y 轴或图注主题判
BIBLIOMETRIC_Y = (
    'number of papers', 'number of studies', 'number of publications',
    'number of articles', 'number of documents', 'publication count',
    'paper count', 'document count', 'n of publications', 'citations',
    '论文数', '文献数', '发文量',
)
BIBLIOMETRIC_CTX = (
    'scopus', 'web of science', 'pubmed', 'bibliometric', 'bibliometrics',
    'scientific production', 'literature search', 'search results',
    '文献计量',
)
# 堆叠图：分段高度和累计边界两种读法都说得通，实测同一子图三遍离散度 68%–203%，不读
STACKED = {'stacked_bar', 'stacked_column', 'stacked_area', 'stacked_line',
           'percent_stacked_bar', '100% stacked bar'}
# 并排画的系列（分类轴上各占一格）不互相压盖，报了重叠 high 也照读
SIDE_BY_SIDE = {'bar', 'grouped_bar', 'combo'}
CHART_TYPES = {'bar', 'grouped_bar', 'stacked_bar', 'line', 'scatter', 'combo', 'box', 'violin',
               'histogram', 'heatmap', 'pie', 'schematic', 'diagram', 'flowchart', 'architecture',
               'photograph', 'micrograph', 'tsne', 'umap', 'network_graph', 'chemical_structure',
               'surface', 'contour', 'bar_3d'}
PLAIN_MARKS = {'bar', 'point', 'line'}
# 三维透视柱状图：柱顶和刻度不在同一个平面上，两遍读数差 9–22%，不读
THREE_D_BARS = {'bar_3d', '3d_bar', 'bar3d', '3d_bar_chart', 'bar_chart_3d', '3d_bar_plot'}
MARK_NAMES = {'bar': '柱', 'point': '点', 'line': '线'}


def is_frequency_sweep(p):
    xl, yl = (p.x_axis_label or '').lower(), (p.y_axis_label or '').lower()
    return any(w in xl for w in FREQUENCY_X) and any(w in yl for w in RHEOLOGY_Y)


# 温度、应变（振幅）、应力扫描曲线也不读（用户 2026-10-09「一律不读」）：X 轴是温度 / 应变 / 应力、Y 轴是模量或损耗角正切。
# 成胶时间扫描（X 轴是时间）也不读，但只写在分类提示里：G′ 随储存天数变化的图 X 轴也是时间，代码分不清
SWEEP_X = ('temperature', '°c', '℃', 'strain', 'stress', 'amplitude', '温度', '应变', '应力')


def is_rheology_sweep(p):
    xl, yl = (p.x_axis_label or '').lower(), (p.y_axis_label or '').lower()
    return any(w in xl for w in SWEEP_X) and any(w in yl for w in RHEOLOGY_Y)


# 粒径分布曲线不读（用户 2026-10-09：「关于粒径只读平均粒径柱状图或者点图 粒径分布曲线图不读 因为太多了没必要」）：
# 粒径（或乳滴大小）画在 X 轴上、Y 轴是强度 / 体积 / 数量占比的，连分布直方图一起不读；粒径画在 Y 轴上的照读
SIZE_AXIS = ('size', 'diameter', 'radius', '粒径', '直径', '半径')


def is_size_distribution(p):
    if p.functional_property not in ('particle_size', 'emulsifying'):
        return False
    xl, yl = (p.x_axis_label or '').lower(), (p.y_axis_label or '').lower()
    return any(w in xl for w in SIZE_AXIS) and not any(w in yl for w in SIZE_AXIS)


# 用户 2026-10-12 定的不读（全量测试里 gemini 时判时不判）：模型预测值对实验值的验证图；压缩 / 拉伸强度、杨氏模量、韧性等
# 力学性能不算凝胶性；水凝胶、膜、微球的溶胀率不算持水性（面粉、淀粉的溶胀力 swelling power 仍算）
PREDICTED = ('predict', '预测')
OBSERVED = ('experiment', 'actual', 'observed', 'measured', '实验', '实测')
MECHANICAL_Y = ('compressive', 'compression strength', 'tensile', "young's", 'young’s', 'young modulus', 'toughness',
                'elongation', 'fracture strain', 'strain at break', 'maximum strain', 'max strain', 'maximum stress',
                '压缩强度', '拉伸', '杨氏', '韧性', '断裂')
# 用户 2026-10-13：质构（TPA）的硬度、弹性、咀嚼性、内聚性、回复性等也不算凝胶性（jafc.3c05352 图 2：分类判成凝胶性，
# 读图两遍都按「力学性能不算」什么都没给，记成读图失败）。中文「弹性」不放：弹性模量（G′）照旧算凝胶性
TEXTURE_Y = ('hardness', 'springiness', 'chewiness', 'gumminess', 'cohesiveness', 'resilience', 'adhesiveness',
             'texture profile', 'tpa', '硬度', '咀嚼性', '胶黏性', '胶着性', '内聚性', '黏聚性', '回复性', '恢复性',
             '黏附性', '粘附性', '质构')
SWELLING_RATIO_Y = ('swelling ratio', 'swelling rate', 'swelling degree', 'degree of swelling', 'swelling index',
                    '溶胀率', '溶胀比', '溶胀度')
# 用户 2026-10-15：力学、质构的词补全（ACS 全量提取时 22 张这类图被分成凝胶性、读了，提取才判出不在 17 项：剪切力、断裂应力、
# 断裂形变、易碎性、firmness、黏性、剪切功、屈服应力、最大力）；只对以后读的图生效，已经读完的不管。
# 凝胶断裂强度（breaking strength / breaking force）按定义算凝胶强度，不加；纵轴写明是凝胶强度、凝乳硬度（curd firmness，
# 凝乳仪测的凝胶性，测试里的 ijfoodmicro.2026.111637 图 1A 照读）的，这几个新词不算数
MECHANICAL_Y_MORE = ('shear force', 'breaking stress', 'fracture stress', 'deformation', 'yield stress', 'work of shear',
                     'maximum force', 'max force', '剪切力', '断裂应力', '形变', '屈服应力', '剪切功', '最大力')
TEXTURE_Y_MORE = ('firmness', 'fracturability', 'stickiness', 'adhesive force', '易碎性', '脆性', '黏性', '粘性')
GEL_STRENGTH_Y = ('gel strength', 'breaking strength', 'breaking force', 'rupture strength', 'rupture force', 'gel firmness',
                  'curd', 'coagul', '凝胶强度', '凝乳', '凝块')


def is_model_fit(p):
    labels = ((p.x_axis_label or '') + ' | ' + (p.y_axis_label or '')).lower()
    return any(w in labels for w in PREDICTED) and any(w in labels for w in OBSERVED)


def _more_words(y, more):
    """2026-10-15 补的新词：纵轴写明是凝胶强度的不算。"""
    return any(w in y for w in more) and not any(w in y for w in GEL_STRENGTH_Y)


def is_mechanical(p):
    y = (p.y_axis_label or '').lower()
    return p.functional_property == 'gelling' and (any(w in y for w in MECHANICAL_Y) or _more_words(y, MECHANICAL_Y_MORE))


def is_texture(p):
    y = (p.y_axis_label or '').lower()
    return p.functional_property == 'gelling' and (any(w in y for w in TEXTURE_Y) or _more_words(y, TEXTURE_Y_MORE))


def is_swelling_ratio(p):
    return p.functional_property == 'water_holding' and any(w in (p.y_axis_label or '').lower() for w in SWELLING_RATIO_Y)


def skip_reason(p):
    """按用户要求不读的原因；要读的子图返回 None。"""
    if not p.protein_system:
        return '研究对象不是蛋白质'
    if p.functional_property not in FUNCTIONAL:
        return '与蛋白质功能特性无关'
    if is_frequency_sweep(p):
        return '频率扫描'
    if is_rheology_sweep(p):
        return '温度、应变或应力扫描曲线'
    if is_size_distribution(p):
        return '粒径分布曲线'
    if is_model_fit(p):
        return '模型预测值对实验值'
    if is_mechanical(p):
        return '力学性能（不算凝胶性）'
    if is_texture(p):
        return '质构（TPA）指标（不算凝胶性）'
    if is_swelling_ratio(p):
        return '溶胀率（不算持水性）'
    return None


# 一个子图里又分几格、各格坐标轴不同（散点矩阵、配对图、边际图）：不读（用户 2026-10-08；acsfoodscitech.2c00342
# 图 3c：分类把点数估少了，两遍读出的 333 个点全部对不上、全转人工，钱白花）
MATRIX_PLOTS = {'scatter_matrix', 'pair_plot', 'pairplot', 'pairs_plot', 'splom', 'marginal_plot', 'matrix_plot'}


def is_matrix(ctype):
    return ctype in MATRIX_PLOTS or 'matrix' in ctype


def is_stacked(ctype):
    """修正（流水线遗留问题 ③）：堆叠图的各种写法。流水线只认 STACKED 里的几个名字，而且清单外的名字
    （stacked_column、percent_stacked_bar）记号只有柱时会先被按记号回推成 bar，绕过堆叠闸门。"""
    return ctype in STACKED or 'stack' in ctype


def chart_type_of(p):
    """闸门按它判的图型。一般就是分类模型填的；填了 other、没填或清单外的名字，而子图只画了柱、点、线的，
    按记号定：柱加点或线算 combo，只有柱算 bar，有线算 line，其余算 scatter；填了 scatter / line 却画着柱的
    也算 combo。三维透视柱和堆叠图的名字在记号规则之前认出来，免得被改成普通柱。"""
    ctype = (p.chart_type or '').strip().lower()
    marks = set(p.mark_types or [])
    if ctype in THREE_D_BARS:
        return 'bar_3d'
    if is_stacked(ctype):
        return ctype
    if is_matrix(ctype):
        return 'scatter_matrix'
    if ctype in ('scatter', 'line') and 'bar' in marks and marks <= PLAIN_MARKS:
        return 'combo'
    if ctype in CHART_TYPES or not marks or not marks <= PLAIN_MARKS:
        return ctype
    if 'bar' in marks and marks & {'point', 'line'}:
        return 'combo'
    return 'bar' if marks == {'bar'} else 'line' if 'line' in marks else 'scatter'


def verdict_detail(fc, dense_limit=DENSE_LIMIT):
    """(要读的子图, 密集子图, 谱图子图, 提示, {没读的功能特性子图: 原因})。每个子图先过功能特性闸门，
    不是蛋白质、与要读的指标无关、频率扫描的直接不读，不再往下判图型。"""
    flags, quant_panels, dense_panels, spectral_panels, why_not = [], [], [], [], {}
    topic = (fc.caption_topic or '').lower()
    ylabs = ' '.join((p.y_axis_label or '') for p in fc.panels).lower()
    biblio = ([w for w in BIBLIOMETRIC_Y if w in ylabs or w in topic]
              + [w for w in BIBLIOMETRIC_CTX if w in topic])
    if biblio:
        flags.append('整图: 命中文献计量特征「%s」（Y 轴「%s」/主题「%s」）—— '
                     '这是发文量统计，不是本文实验数据，不送反读'
                     % (biblio[0], ylabs[:40], (fc.caption_topic or '')[:40]))
        return [], [], [], flags, {p.label or '-': '文献计量图' for p in fc.panels if skip_reason(p) is None}

    for p in fc.panels:
        lab = p.label or '-'
        why = skip_reason(p)
        if why:
            flags.append('%s: %s（X 轴「%s」，Y 轴「%s」），按用户要求不反读'
                         % (lab, why, p.x_axis_label or '-', p.y_axis_label or '-'))
            continue
        ticks = p.y_tick_labels or []
        numeric_axis = len([t for t in ticks if re.search(r'\d', str(t))]) >= 2
        ctype = chart_type_of(p)
        written = (p.chart_type or '').strip().lower()
        if ctype != written:
            flags.append('%s: 图型填的是「%s」，但子图里画的是%s —— 按 %s 处理'
                         % (lab, written or '空', '、'.join(MARK_NAMES[m] for m in ('bar', 'point', 'line')
                                                          if m in (p.mark_types or [])), ctype))
        if ctype in SURFACE:
            flags.append('%s: 三维响应面按用户要求不反读，保留原图' % lab)
            why_not[lab] = '三维响应面，按用户要求不读'
            continue
        if ctype == 'bar_3d':
            flags.append('%s: 三维透视柱状图，柱顶和刻度不在同一个平面上，读数不可靠，不送反读（保留原图）' % lab)
            why_not[lab] = '三维透视柱状图，读数不可靠'
            continue
        if ctype in {'box', 'violin', 'heatmap', 'other', 'contour'}:
            flags.append('%s: 待复核，%s 需要专用统计量/色标提取，不能用通用 Y 值代替' % (lab, ctype))
            why_not[lab] = '图型 %s，待复核' % ctype
            continue
        if is_stacked(ctype):
            flags.append('%s: 图型 %s —— 分段高度与累计边界两种读法都合理，'
                         '实测三跑离散度 68%%-203%%，不送反读（图已下载，可人工读）' % (lab, ctype))
            why_not[lab] = '堆叠图，不送反读'
            continue
        if ctype == 'scatter_matrix':
            flags.append('%s: 一个子图里分成几格、各格坐标轴不同（散点矩阵等），读不准，不送反读（保留原图）' % lab)
            why_not[lab] = '一个子图里分成几格、各格坐标轴不同（散点矩阵等），不读'
            continue
        if ctype in NON_QUANT:
            if numeric_axis:
                flags.append('%s: 图型 %s 属于无可反读数据，但报了 %d 个数值刻度，存疑' % (lab, ctype, len(ticks)))
            why_not[lab] = '图上没有可反读的数值（%s）' % ctype
            continue
        if not numeric_axis:
            flags.append('%s: 待复核：%s 未确认数值 Y 轴；可能是横向图或刻度不清，不能判为无信息' % (lab, ctype))
            why_not[lab] = '未确认数值 Y 轴（可能是横向图或刻度不清），待复核'
            continue
        xl = (p.x_axis_label or '').lower()
        hit = [w for w in SPECTRAL_X if w in xl] + [w for w in PRIMARY_STRUCTURE_X if w in xl]
        if 'ppm' in xl and not hit:
            if any(k in xl for k in PPM_CONC_CTX):
                pass
            elif any(k in xl for k in PPM_SPECTRAL_CTX):
                hit.append('ppm(化学位移语境)')
            else:
                flags.append('%s: X 轴含 ppm 但无法判定是化学位移还是浓度（轴标题「%s」）—— 按可反读处理，请人工确认'
                             % (lab, p.x_axis_label))
        if hit:
            spectral_panels.append(lab)
            flags.append('%s: X 轴为「%s」（命中 %s），属谱图/一级结构图，按用户要求不送反读'
                         % (lab, p.x_axis_label, hit[0]))
            why_not[lab] = '谱图或一级结构图，按用户要求不读'
            continue
        if (p.series_overlap_risk or '').lower() == 'high':
            if ctype in SIDE_BY_SIDE:
                flags.append('%s: 报了重叠 high，但 %s 的系列是并排画的，不构成遮挡 —— 按可反读处理（%s）'
                             % (lab, ctype, (p.overlap_reason or '未说明')[:40]))
            else:
                flags.append('%s: 系列重叠 high（%s），像素上无法分离，不送' % (lab, p.overlap_reason or '未说明'))
                why_not[lab] = '系列重叠严重，无法分离'
                continue
        est = (p.n_series or 1) * (p.points_per_series or 0)
        if est > dense_limit:
            dense_panels.append(lab)
            flags.append('%s: 预估 %d 点（%s 系列 × %s 点）超过 %d，属密集图，'
                         '三跑也有 2/3 的点只能读到一次 —— 不送，标为不适合反读'
                         % (lab, est, p.n_series, p.points_per_series, dense_limit))
            why_not[lab] = '密集图（预估 %d 点）' % est
            continue
        quant_panels.append(lab)
    if len(fc.panels) != fc.n_panels:
        flags.append('n_panels=%d 但只给了 %d 个 panel，内部不一致' % (fc.n_panels, len(fc.panels)))
    return quant_panels, dense_panels, spectral_panels, flags, why_not


def functional_unread(fc, why_not):
    """过了功能特性闸门、却被后面的闸门挡下的子图：{panel, property, reason}，定稿时在末尾逐个写明。"""
    return [{'panel': p.label or '-', 'property': FUNCTIONAL[p.functional_property],
             'reason': why_not[p.label or '-']}
            for p in fc.panels if skip_reason(p) is None and (p.label or '-') in why_not]


def table_labels(tc):
    """每项指标读和显示用的名字：表头原文，重名的加 #2；* | ` 会弄坏粗体和表格，换成空格。"""
    out, seen = [], {}
    for m in tc.measures:
        base = ' '.join(re.sub(r'[*|`]', ' ', m.header or '').split()) or '-'
        seen[base] = seen.get(base, 0) + 1
        out.append(base if seen[base] == 1 else '%s #%d' % (base, seen[base]))
    return out


def table_verdict(tc):
    """(要读的指标, 提示, 无关指标, 没读的功能特性指标)：和图一样的功能特性闸门，看图的闸门不用。"""
    send, flags, unrelated, unread = [], [], [], []
    for lab, m in zip(table_labels(tc), tc.measures):
        why = None if m.protein_system else '研究对象不是蛋白质'
        if why is None and m.functional_property not in FUNCTIONAL:
            why = '与蛋白质功能特性无关'
        if why:
            flags.append('%s: %s，按用户要求不反读' % (lab, why))
            unrelated.append(lab)
        elif m.n_values < 1:
            flags.append('%s: 表里没有这项的数值' % lab)
            unread.append({'panel': lab, 'property': FUNCTIONAL[m.functional_property],
                           'reason': '表里没有这项的数值'})
        else:
            send.append(lab)
    return send, flags, unrelated, unread


def _plain(text):
    """比对用的图注形式：去掉标签和 Markdown 记号，上下标数字改普通数字，空白合一，不分大小写。"""
    text = re.sub(r'<[^>]+>', '', text or '')
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = text.translate(str.maketrans('₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹', '01234567890123456789'))
    text = re.sub(r'[*_`]', '', text)
    return ' '.join(text.split()).casefold()


def caption_part(p, caption):
    """模型抄的子图图注片段，只有真在图注里才交给读图；对不上就不给，免得带偏系列名。"""
    part = ' '.join((p.get('caption_part') or '').split())
    return part if part and _plain(part) in _plain(caption) else None


# 分类模型给没印编号的子图起的泛称（用户 2026-10-12，jafc.0c05792 图 1：色谱图里嵌的小柱图被叫作「inset」，读图交回的
# 编号对不上、两遍零产出）：当作没有编号，走「未编号N」+ 按图型和坐标轴点名
GENERIC_LABELS = {'inset', 'insert', 'insets', 'main', 'main panel', 'main plot', 'main figure', 'left', 'right', 'top',
                  'bottom', 'upper', 'lower', 'whole', 'overall', 'full', 'none', 'null', 'n/a', '插图', '内嵌图', '小图',
                  '主图', '左图', '右图', '上图', '下图'}


def plain_labels(data):
    """分类结果里泛称的子图编号改成 null（见 GENERIC_LABELS）；别的照旧。"""
    panels = [dict(p, label=None) if str(p.get('label') or '').strip().strip('()[]').casefold() in GENERIC_LABELS else p
              for p in data.get('panels') or []]
    return dict(data, panels=panels)


def figure_target(item, rec):
    """分类结果 → 读图目标（只列要读的子图，附分类阶段的观察）。不送读时 read_panels 为空。"""
    fc = FigureClass(**plain_labels(rec['data']))
    send, dense, spectral, flags, why_not = verdict_detail(fc)
    panels = [p.model_dump() for p in fc.panels]
    # 同一个字母分类模型可能给好几个子图：一个字母下画了几张小图（2026-10-05 afres.2026.102097 图 1A：0% / 25% / 45% /
    # 65% sucrose / Egg white 五张小图都标成 A）。逐个子图看它本身过不过闸门，不按名字一刀切——原来同名里有一张与功能特性
    # 无关的也被带进要读的名单，FUNCTIONAL['none'] 报错（afres.2026.102130）。
    keep = [p for p in panels if (p['label'] or '-') in send
            and verdict_detail(FigureClass(n_panels=1, panels=[Panel(**p)], caption_topic=fc.caption_topic,
                                           notes=None))[0]]
    # 图上没有字母编号、又不止一个子图（2026-10-06 afres.2026.102130 图 5：示意图里嵌了红外、XRD、两条热重和一张持水
    # 柱状图，都没编号）：原来只能整图送读，模型把曲线小图也交回来、0 个点，自检判失败，每次重跑都一样。改成给要读的
    # 子图起名「未编号1」「未编号2」…，读图指令里按图型和坐标轴点名；只有一个子图的图照旧整图读（与流水线一致）。
    unnamed, others = {}, []
    if len(panels) > 1:
        for p in keep:
            if not p['label']:
                p['label'] = UNLABELED % (len(unnamed) + 1)
                unnamed[p['label']] = describe_panel(p)
        if unnamed:
            others = list(dict.fromkeys(describe_panel(p) for p in panels if not p['label']))
    same = {}
    for lab, desc in unnamed.items():
        same.setdefault(desc, []).append(lab)
    nth = {lab: i + 1 for labs in same.values() if len(labs) > 1 for i, lab in enumerate(labs)}
    read = list(dict.fromkeys(p['label'] for p in keep))
    count = {}
    for p in panels:
        count[p['label']] = count.get(p['label'], 0) + 1
    hints, seen = [], set()
    for p in keep:
        if p['label'] in seen:
            continue
        seen.add(p['label'])
        hints.append(p)
    keep = hints
    t = {'key': item['key'], 'kind': 'figure', 'label': item['label'], 'heading': item['heading'],
         'files': item['files'], 'caption': item['caption'],
         'excluded': exclusion_reason(panels=panels),
         'read_panels': read,
         'ignore_panels': [lab for lab in dict.fromkeys(p['label'] for p in panels) if lab not in read],
         # 要读的字母下有几张小图：读图指令里交代每张小图的系列名带上小标题，免得几张小图的同名系列混成一个
         'multi': {lab: n for lab, n in count.items() if lab and lab in read and n > 1},
         # 没编号的子图：起的名字 → 怎么认（图型和坐标轴）；图上其余没编号、不读的子图
         'unlabeled': unnamed, 'unlabeled_other': others,
         'dense_panels': dense, 'spectral_panels': spectral,
         'unrelated_panels': [p.label or '-' for p in fc.panels if skip_reason(p)],
         'functional_unread': functional_unread(fc, why_not),
         'review': any('待复核' in f for f in flags), 'flags': flags,
         'hints': [{'panel': p['label'], 'chart_type': chart_type_of(Panel(**p)),
                    'property': FUNCTIONAL.get(p['functional_property']),
                    'mark_types': p.get('mark_types') or [], 'n_series': p['n_series'],
                    'y_axis': p['y_axis_label'], 'x_axis': p['x_axis_label'],
                    'caption_part': caption_part(p, item['caption']),
                    'has_error_bars': p['has_error_bars'],
                    'has_significance_letters': p['has_significance_letters'],
                    'overlap_risk': p['series_overlap_risk']} for p in keep]}
    for h in t['hints']:
        if h['panel'] in unnamed:
            h.update(unlabeled=True, nth=nth.get(h['panel']))
    t['case'] = case_distinct(t['read_panels'] + t['ignore_panels'])
    return t


def describe_panel(p):
    """没有编号的子图怎么认：图型和分类阶段抄的坐标轴标题原文。"""
    bits = [chart_type_of(Panel(**p)) or '?']
    if p.get('y_axis_label'):
        bits.append('Y 轴「%s」' % p['y_axis_label'])
    if p.get('x_axis_label'):
        bits.append('X 轴「%s」' % p['x_axis_label'])
    return '，'.join(bits)


def table_target(item, rec):
    tc = TableClass(**rec['data'])
    labels = table_labels(tc)
    send, flags, unrelated, unread = table_verdict(tc)
    keep = [(lab, m) for lab, m in zip(labels, tc.measures) if lab in send]
    return {'key': item['key'], 'kind': 'table', 'label': item['label'], 'heading': item['heading'],
            'files': item['files'], 'caption': item['caption'], 'excluded': '',
            'read_panels': [lab for lab, _ in keep],
            'ignore_panels': [lab for lab in labels if lab not in send],
            'dense_panels': [], 'spectral_panels': [], 'unrelated_panels': unrelated,
            'functional_unread': unread, 'review': False, 'flags': flags, 'case': False,
            'hints': [{'panel': lab, 'chart_type': 'table', 'property': FUNCTIONAL[m.functional_property],
                       'mark_types': [], 'n_series': 1, 'layout': m.layout, 'n_values': m.n_values,
                       'y_axis': m.header, 'x_axis': None, 'caption_part': None,
                       'has_error_bars': m.has_sd, 'has_significance_letters': m.has_significance_letters,
                       'overlap_risk': 'low'} for lab, m in keep]}


# =============================================================== 读图（read.py） ==
# 系统提示和 schema 直接用 vlm_chart_benchmark/extract.py 的（流水线 import 的也是那一份，见文件开头 VE）：
# 那边 0.275% 的中位误差是在这套提示词下测出来的，这里不另抄一份。
SYSTEM_PROMPT = VE.SYSTEM_PROMPT


# 第三条纵轴（用户 2026-10-13）：extract.py 的 schema 只有左右两条纵轴，三条纵轴的图（粒径、ζ-电位、PDI 各一条轴）
# 第三条轴上的系列只能挂到左轴或右轴上，读数和那条轴的刻度对不上，整张图判读图失败（jafc.7b01848 图 2、
# jafc.9b02003 图 2a、acsfoodscitech.5c01187 图 3c、jf300409y 图 9）。这里在它的基础上加 y_third；extract.py 本身
# 不动（流水线和评测还用它），它改了这里照样跟着变。
class ReadSeries(VE.Series):
    axis: str = Field(description="left、right 或 third（对应 y_third 那条纵轴）")


class ReadPanel(VE.Panel):
    series: List[ReadSeries]
    # default=None：断点里存的、以前读的结果没有这一项也照样认；发给模型的 schema 里照旧是必填、可为 null
    y_third: Optional[VE.Axis] = Field(default=None, description="第三条纵轴（子图有三条纵轴时，离绘图区最远或另外"
                                                                  "单独画出的那条），只有一两条纵轴则 null")


class Extraction(VE.Extraction):     # 名字不变：发给模型的 schema 名、断点里记的调用名都还是 Extraction
    panels: List[ReadPanel]

# 读子图一定带图注（用户 2026-09-24）；无图例单系列照抄图注；双纵轴无图例按纵轴标题命名（2026-09-28）
SERIES_POLICY = """系列身份可由图内图例或作者图注明确确认。没有图内图例不等于没有系列身份：
- 先在图注里找到说明这个子图的那一段，确认它测的是什么量、是哪些样品，再读图。
- 单系列子图没有图内图例时，系列名照抄那一段里的样品名原文；那一段没有样品名，就照抄其中的测量量原文；两者都没有，才用该子图 Y 轴标题原文（不带单位）。照抄时大小写和用词都不改。不得仅因没有图内图例而填 UNRESOLVED。
- 图注只用于确认身份、单位和实验含义；X/Y 数值和误差棒仍须从图中读取，不用图注数字替代估读。
- 左右双纵轴的子图没有图内图例、图注也没逐一说明各系列时，如果每个系列各对应一个纵轴（例如柱对左轴、点线对右轴），系列名照抄它所对应纵轴的标题原文（不带单位），例如左轴「Size (nm)」的柱叫 Size、右轴「PDI」的点线叫 PDI；这样确认的系列不填 UNRESOLVED。两个以上系列共用同一个纵轴的，按下一条处理。
- 其余多系列子图须能将图例颜色/符号或图注明确标识逐一对应。图文仍不能唯一确认时，才填 UNRESOLVED_加颜色或符号描述，不猜处理组。
- 连续曲线无离散标记时，只读明确的峰、拐点或可靠刻度处的曲线位置，注明估读及取点方式；无法可靠读取就保留空值和原因，不编造采样点。"""

TABLE_RULES = """表格里的数值是印出来的，逐格照抄，不估读、不换算：
- 每个 panel 只有一个系列：series 的 name 和每个点的 series 都填这一项的表头（与 panel_id 相同），axis 填 left，chart_type 填 bar。
- 每个印了数值的格子输出一个点。x_category 填这个格子所属样品的名称（指标占一列时是这一行的行名，指标占一行时是这一列的列名）；样品名分几级的（如 NUT 下面又分 0 和 4），从外到里用一个空格连起来，写成「NUT 0」；x_value 填 null。
- y_value 填格子里的均值；格子写成「均值 ± 标准差」的，err_low 填均值减标准差、err_high 填均值加标准差，否则两项都填 null；显著性字母抄进 sig；estimated 一律填 false。
- note 原样照抄这个格子里印的全部文字（如「9.03±0.10a」，上标的字母照写成普通字母），不改写、不补字。
- 空格子，或写着「–」「ND」「nd」之类没有数值的格子，不输出。
- x_axis 的 label 填样品名那一栏的表头，y_left 的 label 填这一项的表头、unit 填单位；两者的 min、max、ticks 都填 null，scale 填 linear。
- point_index 按表里从上到下的顺序（指标占一行时从左到右），从 1 开始。"""

TABLE_NOTE = ('作者表题和表注（用来确认样品名称和缩写的含义；数值只从表格图片上抄，'
              '不用这里的数字代替）：')

REPLICATE_NOTE = ('柱子上叠画的一个个小点（同一根柱子上好几个散点，落在柱顶上下，是每次重复测定的单个值）'
                  '不是单独的数据点：每根柱子只输出一个点，读柱顶（均值）和误差棒，这些散点不输出。'
                  '和柱子分开画、对着另一个纵轴、每个样品一个点的点线系列，照常读。')

# 用户 2026-10-13：三条纵轴、同一系列不同样品对不同纵轴、两层横轴（读图失败的 11 张图里看出来的）
AXIS_NOTE = ('纵轴和横轴：\n'
             '- 子图有三条纵轴时（例如左边一条、右边两条，或左边两条、右边一条），离绘图区最远（或另外单独画出）的那条'
             '填进 y_third，对应它的系列 axis 填 third；每个系列的 axis 必须是它的数值所对的那条纵轴。只有一两条纵轴时 '
             'y_third 填 null。\n'
             '- 同一个图例系列在不同样品上对着不同的纵轴时（例如第一组样品看左轴、其余几组看右轴），按纵轴拆成两个系列，'
             '名字写成「图例名（该纵轴标题）」，各自填对应的 axis。\n'
             '- 横轴有两层标签时（例如每根柱下面是条件、下面一层是样品组），x_category 把两层都写上、外层在前，'
             '用一个空格连起来（如「CX@Lut SGF」）；系列名只用图例里的名字，不要把样品组当成系列。\n'
             # 用户 2026-10-19：Elsevier 读图失败的图里看出来的三条（见文件开头 22）
             '- 横向柱状图、横向点线图（柱子横着画，数值刻度在横轴上，纵轴上是一个个样品或条件）：数值照样填 y_value、'
             '误差棒照样填 err_low / err_high；y_left 填横轴那条数值刻度（标题、单位、最小最大刻度和刻度值），x_axis 填'
             '纵轴（样品或条件那条）的标题，x_category 照抄纵轴上这一根的标签（是数字的也照抄，如 pH 的 2、3、4）。\n'
             '- 判断一个系列对哪条纵轴：看图例和纵轴标题对应的量（如 PDI、Zeta potential），以及纵轴的颜色（作者常把纵轴'
             '画成和对应系列同一种颜色）；每个读数都要落在它所对那条纵轴的刻度范围里，落不进去就是轴对错了。\n'
             '- 刻度数字漏印了负号时（例如 ζ-电位的柱子从 0 往下画，往下的刻度却印成 2、4、6），按图上的方向把这条纵轴的'
             '刻度（min、max、ticks）和读数都写成负数，不要只把读数写成负数、刻度照抄成正数。')

# 用户 2026-10-19（foodhyd.2024.110612 图 9d：d 下面并排四张柱状图，读图回来不叫 d，整张图「缺少要求的子图」）。
# 分类已经看出一个字母下有几张小图时用 MULTI_NOTE，不再加这句
MULTI_PLOT_NOTE = ('一个子图字母下面并排画了几张坐标图时（例如 d 下面左右四张柱状图），panel_id 都填这个字母，'
                   '不要写成 d1、d2 或「d (…)」；每张小图里的系列名后面加上这张小图的小标题原文，写成「系列名（小标题）」；'
                   '小图没有小标题的，用图上或图注里说明它是哪组样品的文字，再没有就写「系列名（第 N 张）」，'
                   'N 从左到右、从上到下数。')

CAPTION_NOTE = ('作者图注（先用它确认子图测的是什么、是哪些样品和系列；'
                'X/Y 数值只从图上读，不用图注里的数字代替，也不能据此编造图中不可读的点）：')

# 用户 2026-10-15：图注写「Symbols as in Figure 6」时把图 6 的图注也交给读图（jf0581271 图 7：系列符号的说明只在图 6 图注里，
# 读出来的系列名只有「Filled circle」之类，对不上样品）
REF_CAPTION_NOTE = '上面图注说符号、样品或条件同 Figure %s，它的图注原文（只用来认系列和样品，数值仍从本图读）：'
REF_CAPTION_RE = re.compile(
    r'\b(?:as\s+(?:in|for|described\s+in|shown\s+in|indicated\s+in|defined\s+in|given\s+in)|same\s+as(?:\s+(?:in|for))?'
    r'|identical\s+to(?:\s+those\s+(?:in|of))?|see|cf\.?|refer\s+to)\s+(?:the\s+)?(?:legend\s+(?:of|to|in)\s+)?'
    r'(?:Figures?|Figs?\.)\s*(\d+)\b|(?:同|见|参见|如)\s*图\s*(\d+)', re.I)

# 用户 2026-10-15：散点旁边印着点名时读进 x_category（jf034744i 图 8 的肽编号、jf035375t 图 3 的蛋白名，原来没读出来，
# 点对不上样品）
POINT_LABEL_NOTE = ('散点图里，数据点旁边直接印着识别这个点的名称或编号（样品名、肽或化合物编号、蛋白名等）时，'
                    '这个点的 x_category 照抄这个标签，x_value 照常填横坐标读数；点旁边印的是数值本身'
                    '（如柱顶标的 12.5）的不算标签。')


def referenced_captions(caption, items, label):
    """图注里「as in Figure N」「同图 N」引用到的本文其他图的图注：[(N, 图注)]。"""
    found = []
    for m in REF_CAPTION_RE.finditer(caption or ''):
        n = m.group(1) or m.group(2)
        if n and n != str(label) and n not in [f[0] for f in found]:
            cap = next((it['caption'] for it in items
                        if it['kind'] == 'figure' and str(it['label']) == n and it['caption']), None)
            if cap:
                found.append((n, cap))
    return found


# 第三遍沿用前两遍的名称（用户 2026-10-12）：第三遍只是给漏读、不一致的点补读和裁决，不是独立的一遍；实测它常给系列另起名
# （afres.2026.102097 前两遍「18℃」、第三遍「18℃ - Air phase fraction」），配不上对、白读。只给前两遍写法统一后一致的名字，
# 不给读数；前两遍仍完全独立。
GIVEN_NAMES = ('下面这些系列名和样品名前两遍已经读得一致，这一遍照抄、一字不改（series 的 name、每个点的 series 和 x_category '
               '都用这些写法）；图上其余的系列和样品仍按上面的规则命名：')


def is_number_label(text):
    try:
        float(str(text).strip().replace(',', ''))
        return True
    except ValueError:
        return False


def agreed_names(t, recs):
    """前几遍都读出、写法统一后一致的系列名（用词一样，name_words）和样品名（cat_key），用第一遍的写法：
    {子图: {'series': [(名, 纵轴)], 'cats': [样品]}}。
    数字标签（储藏天数 0/6/12…）按数值 X 照图读，不进名单。"""
    per_run = []
    for rec in recs:
        panels = {}
        for p in ((rec or {}).get('data') or {}).get('panels') or []:
            series = {}
            for s in p.get('series') or []:
                if (s.get('name') or '').strip():
                    k = (name_words(s['name']), (s.get('axis') or 'left').strip().lower())
                    series.setdefault(k, (s['name'].strip(), k[1]))
            cats = {}
            for q in p.get('points') or []:
                c = q.get('x_category')
                if c is not None and str(c).strip() and not is_number_label(c):
                    cats.setdefault(cat_key(str(c)), str(c).strip())
            panels[panel_key(p.get('panel_id'), t['case']) or ''] = (series, cats)
        per_run.append(panels)
    if not per_run or not all(per_run):
        return {}
    out = {}
    for key, (series, cats) in per_run[0].items():
        others = [r.get(key) for r in per_run[1:]]
        if any(o is None for o in others):
            continue
        s = [v for k, v in series.items() if all(k in o[0] for o in others)]
        c = [v for k, v in cats.items() if all(k in o[1] for o in others)]
        if s or c:
            out[key] = {'series': s, 'cats': c}
    return out


def names_block(t):
    """第三遍读图指令末尾的名单：只列这一遍要读的子图；表格的系列名就是表头，只列样品名。"""
    names = t.get('names') or {}
    two_axes = any(ax == 'right' for v in names.values() for _, ax in v['series'])
    lines = []
    for p in t['read_panels']:
        given = names.get(panel_key(p, t['case']) or '')
        if not given:
            continue
        bits = []
        if given['series'] and t['kind'] != 'table':
            bits.append('系列名 ' + '、'.join('「%s」%s' % (n, ('（右轴）' if ax == 'right' else '（左轴）') if two_axes else '')
                                           for n, ax in given['series']))
        if given['cats']:
            bits.append('样品名 ' + '、'.join('「%s」' % c for c in given['cats']))
        if bits:
            lines.append('- %s %s：%s' % ('指标' if t['kind'] == 'table' else '子图', p or '（整图）', '；'.join(bits)))
    return GIVEN_NAMES + '\n' + '\n'.join(lines) if lines else ''


def table_instruction(t):
    hints = {h.get('panel'): h for h in t.get('hints', [])}
    read = [p for p in t['read_panels'] if p]
    ign = [p for p in t['ignore_panels'] if p]
    lines = ['这是论文 Table %s 的图片：作者把这张表格排成了图片。**只读以下几项指标**（蛋白质功能特性和理化指标的测定数据），'
             '每项输出一个 panel，panel_id 原样照抄下面给的表头：' % t['label']]
    for p in read:
        h = hints.get(p) or {}
        bits = ['「%s」' % p]
        if h.get('property'):
            bits.append('测的是%s' % h['property'])
        bits.append('在表里占一%s' % ('行' if h.get('layout') == 'row' else '列'))
        if h.get('n_values'):
            bits.append('约 %d 个数值' % h['n_values'])
        lines.append('- ' + '，'.join(bits))
    if ign:
        lines.append('表里其余各项（%s）不是这次要读的数据，一律不要输出。' % '、'.join('「%s」' % x for x in ign))
    lines.append(TABLE_RULES)
    if t.get('names') and names_block(t):          # 第三遍：沿用前两遍一致的样品名
        lines.append(names_block(t))
    if t.get('caption'):
        lines.append(TABLE_NOTE + '\n' + t['caption'])
    return '\n'.join(lines)


# 一个字母下画了几张小图（分类时同一个字母出现了几次）才加这句，其余情况读图指令与流水线逐字一致
MULTI_NOTE = ('子图 %s 里画了 %d 张小图（各有自己的小标题）：panel_id 都填「%s」；每张小图里的每个系列，系列名后面都加上'
              '这张小图的小标题原文，写成「系列名（小标题）」，例如「Overrun（0%% sucrose）」，'
              '不同小图里的同名系列不要混成一个。')

# 图上没有字母编号、又不止一个子图时才加（figure_target 的 unlabeled），其余情况读图指令不变
UNLABELED = '未编号%d'
UNLABELED_NOTE = ('这张图的子图没有字母编号：%s是这里起的名字，各指哪个子图看下面写的图型和坐标轴；'
                  '输出时 panel_id 就填这个名字。')
UNLABELED_OTHER = '图上其余没有编号的子图（%s）不是这次要读的数据，一律不要输出。'
NTH_NOTE = '图型和坐标轴一样的子图不止一个，它是从左到右、从上到下数的第 %d 个'


def panel_instruction(t):
    """读图指令：只读哪些子图（其余点名不要输出）、分类阶段的观察、子图图注片段、整段图注、系列规则。"""
    if t['kind'] == 'table':
        return table_instruction(t)
    read = [p for p in t['read_panels'] if p]
    ign = [p for p in t['ignore_panels'] if p]
    head = '这是论文 Figure %s。' % t['label']
    if not read:
        return head + '提取这张图片中所有子图的全部数据点。'
    lines = [head + '这张图里**只读以下子图**（蛋白质功能特性和理化指标的测定数据），只提取它们：%s。'
             % '、'.join(read)]
    if ign:
        lines.append('其余子图（%s）不是这次要读的数据（与要读的指标无关，或按用户要求不读），'
                     '一律不要输出，也不要为它们编造 panel。' % '、'.join(ign))
    unnamed = [p for p in read if p in (t.get('unlabeled') or {})]
    if unnamed:
        lines.append(UNLABELED_NOTE % '、'.join('「%s」' % p for p in unnamed))
        if t.get('unlabeled_other'):
            lines.append(UNLABELED_OTHER % '；'.join(t['unlabeled_other']))
    for h in t.get('hints', []):
        if not h.get('panel'):
            continue
        bits = ['子图 %s：%s' % (h['panel'], h.get('chart_type') or '?')]
        if h.get('property'):
            bits.append('测的是%s' % h['property'])
        if h.get('n_series'):
            bits.append('约 %d 个系列' % h['n_series'])
        if h.get('y_axis'):
            bits.append('Y 轴「%s」' % h['y_axis'])
        if h.get('unlabeled'):
            if h.get('x_axis'):
                bits.append('X 轴「%s」' % h['x_axis'])
            if h.get('nth'):
                bits.append(NTH_NOTE % h['nth'])
        if h.get('has_error_bars'):
            bits.append('有误差棒')
        if h.get('has_significance_letters'):
            bits.append('有显著性字母')
        if (h.get('overlap_risk') or '').lower() == 'medium':
            bits.append('系列有部分重叠，严格按图例颜色配对')
        if h.get('caption_part'):
            bits.append('图注里说明它的原文「%s」' % h['caption_part'])
        lines.append('- ' + '，'.join(bits))
    for lab, n in (t.get('multi') or {}).items():
        if lab in read:
            lines.append(MULTI_NOTE % (lab, n, lab))
    lines.append('以上是分类阶段的初步观察，**仅供定位子图**；'
                 '坐标轴和数值一律以你自己在图上看到的为准，有冲突以图为准；系列名按下面的系列规则。')
    if t.get('caption'):
        lines.append(CAPTION_NOTE + '\n' + t['caption'])
    for n, cap in t.get('ref_captions') or []:
        lines.append(REF_CAPTION_NOTE % n + '\n' + cap)
    lines.append(REPLICATE_NOTE)
    lines.append(AXIS_NOTE)
    if not any(lab in read for lab in (t.get('multi') or {})):
        lines.append(MULTI_PLOT_NOTE)
    # 只加在要读散点图的指令里：别的图指令不变，断点里已经读完的图不用重读
    if any('scatter' in (h.get('chart_type') or '') for h in t.get('hints', []) if h.get('panel') in read):
        lines.append(POINT_LABEL_NOTE)
    lines.append(SERIES_POLICY)
    if t.get('names') and names_block(t):          # 第三遍：沿用前两遍一致的系列名、样品名
        lines.append(names_block(t))
    return '\n'.join(lines)


def narrowed(t, selection):
    """第三遍只读有分歧的子图（修正流水线遗留问题 ④）：要读的只留选中的，其余挪进"不要输出"。"""
    if selection is None:
        return t
    keep = [p for p in t['read_panels'] if (panel_key(p, t['case']) or '') in selection]
    return dict(t, read_panels=keep,
                ignore_panels=t['ignore_panels'] + [p for p in t['read_panels'] if p not in keep],
                hints=[h for h in t['hints'] if (panel_key(h.get('panel'), t['case']) or '') in selection])


CELL = re.compile(r'^([-+]?\d+(?:\.\d+)?)\s*%?\s*(?:(?:±|\+/-|\+-)\s*(\d+(?:\.\d+)?)\s*%?)?\s*([A-Za-z]{0,5})$')


def _places(text):
    return len(text.split('.')[1]) if '.' in text else 0


def printed_cells(data):
    """表格图片：均值、误差上下限和字母从模型抄下的格子原文算（「9.03±0.10a」→ 9.03、8.93/9.13、a），
    不用模型自己的算术。原文不是这种样子的格子保留模型自己填的数，记一条提示。"""
    flags = []
    for p in data.get('panels') or []:
        odd = 0
        for q in p.get('points') or []:
            text = unicodedata.normalize('NFKC', q.get('note') or '').replace('−', '-').replace('^', '')
            m = CELL.match(' '.join(text.split()))
            if not m:
                odd += 1
                continue
            y = float(m.group(1))
            q['y_value'], q['estimated'] = y, False
            if m.group(2):
                sd, places = float(m.group(2)), max(_places(m.group(1)), _places(m.group(2)))
                q['err_low'], q['err_high'] = round(y - sd, places), round(y + sd, places)
            else:
                q['err_low'] = q['err_high'] = None
            q['sig'] = m.group(3) or None
        if odd:
            flags.append('%s: %d 个格子的原文没有抄成「均值±标准差+字母」的样子，这几格用读图模型自己填的数'
                         % (p.get('panel_id') or '-', odd))
    return flags


def _loose(label, case=False, table=False):
    key = panel_key(label, case)
    if key in (None, '', '-'):
        return ''
    if table:   # 表格的指标按表头认：「EAI (m²/g)」和「EAI (m2/g)」是同一项
        return re.sub(r'[\W_]+', '', unicodedata.normalize('NFKC', str(key))).upper()
    text = re.sub(r'[\s()（）\[\].,:;]', '', str(key))
    return text if case else text.upper()


def _tail(label, case=False):
    """组图编号的最后一级：「(c) C」「c-C」→ C。"""
    parts = re.findall(r'[A-Za-z]+\d*|\d+', str(label or ''))
    if not parts:
        return ''
    return parts[-1] if case else parts[-1].upper()


def _core(label):
    """去掉子图名里括号中的文字说明：「A (lower panel)」「B（下图）」→ A、B；「(c) C」括号里只有编号，不动。"""
    text = re.sub(r'\s*[(（][^)）]*?[A-Za-z\u4e00-\u9fff]{2,}[^)）]*[)）]', ' ', str(label or ''))
    return ' '.join(text.split())


def only_requested(data, read_panels, case=False, table=False):
    """(data, 丢掉的子图)：只留要读的子图；模型自己多读的丢掉（不让整张图失败）；
    d(i) 和 d i 这类写法不同的编号改成分类阶段的写法。
    组图（一张图分 (a)(b)(c) 几组、每组又有 A–F）的编号，分类模型写成「(c) C」，读图模型常常只写「C」
    （2026-10-02 试跑 foodchem.2025.147510 图 7：读对了游离巯基那个子图，却因编号对不上被丢掉，两遍都成了零产出）。
    精确对不上的，最后一级编号只和一个还没对上的要读子图、一个多出来的返回子图相同时，认作同一个；有歧义照旧丢掉。"""
    wanted = {}
    for w in read_panels or []:
        wanted.setdefault(_loose(w, case, table), w)
    if set(wanted) <= {''}:
        return data, []
    panels = data.get('panels') or []
    keys = [_loose(p.get('panel_id'), case, table) for p in panels]
    alias = {}
    if not table:
        left, extra = {}, {}
        for k, w in wanted.items():
            if k and k not in keys:
                left.setdefault(_tail(w, case), []).append(w)
        for i, k in enumerate(keys):
            if k not in wanted:
                extra.setdefault(_tail(panels[i].get('panel_id'), case), []).append(i)
        for tail, ws in left.items():
            if tail and len(ws) == 1 and len(extra.get(tail, [])) == 1:
                alias[extra[tail][0]] = ws[0]
        # 用户 2026-10-13：分类把上面是照片、下面是柱状图的子图叫成「A (lower panel)」，读图回来叫「A」，被当成
        # 没要求的子图丢掉，两遍都成了零产出（jafc.7b05889 图 3）。去掉括号里的说明后两边都唯一对得上，认作同一个
        done = set(alias.values())
        left2, extra2 = {}, {}
        for k, w in wanted.items():
            if k and k not in keys and w not in done:
                left2.setdefault(_loose(_core(w), case), []).append(w)
        for i, k in enumerate(keys):
            if k not in wanted and i not in alias:
                extra2.setdefault(_loose(_core(panels[i].get('panel_id')), case), []).append(i)
        for core, ws in left2.items():
            if core and len(ws) == 1 and len(extra2.get(core, [])) == 1:
                alias[extra2[core][0]] = ws[0]
    keep, dropped = [], []
    for i, p in enumerate(panels):
        label = wanted.get(keys[i]) if keys[i] in wanted else alias.get(i)
        if keys[i] not in wanted and i not in alias:
            dropped.append(p.get('panel_id') or '-')
            continue
        if label and p.get('panel_id') != label:
            p = dict(p, panel_id=label)
        keep.append(p)
    return dict(data, panels=keep), dropped


SMOOTH_NOTE = '%s: 只有光滑曲线、没有可读的数据点（分类判为只画了线），没读出数值，不算失败'
UNRESOLVED_NOTE = '%s: %d 条系列在图例和图注里都对应不上（%s），没读，不猜是哪一组'
UNRESOLVED_EMPTY = '%s: 全部系列在图例和图注里都对应不上，这个子图没读，不猜是哪一组'


def smooth_panels(t):
    """分类判为只画了线（没有点、没有柱）的子图：读出 0 个点不算失败。"""
    return {panel_key(h.get('panel'), t['case']) or '' for h in t.get('hints') or []
            if set(h.get('mark_types') or []) == {'line'}}


def smooth_empty(data, smooth, case=False):
    return sorted({panel_key(p.get('panel_id'), case) or '' for p in data.get('panels') or []
                   if not p.get('points') and (panel_key(p.get('panel_id'), case) or '') in smooth})


def unresolved(name):
    return not name or str(name).startswith('UNRESOLVED')


def drop_unresolved(data, case=False):
    """丢掉图例和图注都对应不上的系列（UNRESOLVED_颜色），认得出的照读。
    返回 ({子图: [丢掉的系列]}, [因此一个点都不剩的子图])。"""
    dropped, emptied = {}, []
    for p in data.get('panels') or []:
        names = ({q.get('series') or '' for q in p.get('points') or [] if unresolved(q.get('series'))}
                 | {s.get('name') or '' for s in p.get('series') or [] if unresolved(s.get('name'))})
        if not names:
            continue
        key = panel_key(p.get('panel_id'), case) or ''
        had = bool(p.get('points'))
        p['points'] = [q for q in p.get('points') or [] if not unresolved(q.get('series'))]
        p['series'] = [s for s in p.get('series') or [] if not unresolved(s.get('name'))]
        dropped[key] = sorted(re.sub(r'^UNRESOLVED_?', '', n) or '未命名' for n in names)
        if had and not p['points']:
            emptied.append(key)
    return dropped, emptied


def unresolved_flags(dropped, emptied):
    return [UNRESOLVED_NOTE % (k or '-', len(v), '、'.join(v)) for k, v in sorted(dropped.items()) if k not in emptied]


def tick_step(ticks):
    if not ticks:
        return None
    vals = []
    for x in re.split(r'[,;\s]+', str(ticks)):
        try:
            vals.append(float(x))
        except ValueError:
            pass
    if len(vals) < 2:
        return None
    vals.sort()
    d = [b - a for a, b in zip(vals, vals[1:]) if b > a]
    return min(d) if d else None


BLOCKING = ('零产出', '超出自报刻度', '所有 Y 值都是 null',
            '点引用了图例里没有的系列', '0 个数据点', '缺少要求的子图',
            '多出未要求的子图', '系列归属未确认', '误差棒范围异常')


def is_blocking(flag):
    return any(k in flag for k in BLOCKING)


def error_bars_ok(y, lo, hi):
    """误差棒两端夹住读数就算正常。纵轴倒过来画的（ζ-电位越往上越负）画面上的上端数值反而小，模型常把两端对调
    （用户 2026-10-12，jafc.0c01250 图 5A 两遍都因此判读图失败）：两端都有时按大小排一下再比；只有一端、读数是负数时
    分不清哪头朝上，不比。读数在两端之外的照旧判异常。"""
    if lo is not None and hi is not None:
        return min(lo, hi) <= y <= max(lo, hi)
    if y < 0:
        return True
    return not ((lo is not None and lo > y) or (hi is not None and hi < y))


AXES = (('left', 'y_left', '左'), ('right', 'y_right', '右'), ('third', 'y_third', '第三'))


def axis_of_series(p):
    return {s.get('name'): (s.get('axis') or 'left').strip().lower() for s in p.get('series') or []}


def outside_axis(ya, y):
    """读数是不是超出这条纵轴自报的刻度一个刻度间距以上（对数轴按一个数量级算：jafc.6b02966 图 6A 对数轴最高标到
    1000，线上的点确实画在 1000 上面一点，原来按线性刻度只许超出 0.09，两遍都判失败）。刻度没报全的不比。"""
    lo, hi = ya.get('min'), ya.get('max')
    if lo is None or hi is None or y is None:
        return False
    if (ya.get('scale') or '').strip().lower().startswith('log') and min(lo, hi) > 0:
        if y <= 0:
            return True
        return not (math.log10(min(lo, hi)) - 1 <= math.log10(y) <= math.log10(max(lo, hi)) + 1)
    tol = tick_step(ya.get('ticks')) or 0.15 * (abs(hi - lo) or 1.0)
    return y < min(lo, hi) - tol or y > max(lo, hi) + tol


def axis_tol_text(ya):
    if (ya.get('scale') or '').strip().lower().startswith('log') and min(ya['min'], ya['max']) > 0:
        return '一个数量级'
    return '一个刻度间距（%.4g）' % (tick_step(ya.get('ticks')) or 0.15 * (abs(ya['max'] - ya['min']) or 1.0))


def drop_out_of_range(data, case=False):
    """少数点超出自报刻度时只丢这几个点、记下来（用户 2026-10-13「全都改吧」）：图上用文字标出的冲出坐标轴的数
    （jafc.1c00432 图 2「167±15 μm」）、放错纵轴的一条系列，不再让整张图失败。一个子图里超出的点过半时不动，
    交给自检判失败（多半是刻度读错了）。返回 {子图: ['系列 X=… Y=…', …]}。"""
    dropped = {}
    for p in data.get('panels') or []:
        pts = p.get('points') or []
        axis_of = axis_of_series(p)
        axes = {name: p.get(field) or {} for name, field, _ in AXES}
        # 和自检一样：系列标的那条纵轴没给刻度的，不比
        bad = [q for q in pts if q.get('y_value') is not None
               and outside_axis(axes.get(axis_of.get(q.get('series'), 'left')) or {}, q['y_value'])]
        if not bad or len(bad) * 2 > len(pts):
            continue
        ids = {id(q) for q in bad}
        p['points'] = [q for q in pts if id(q) not in ids]
        key = panel_key(p.get('panel_id'), case) or ''
        dropped[key] = ['%s %s=%s' % (q.get('series') or '-', q.get('x_category') or q.get('x_value'), q['y_value'])
                        for q in bad]
    return dropped


def fix_series_names(data, case=False):
    """点上的系列名不在系列列表里（用户 2026-10-13）：子图只有一条系列时就是它（acsfoodscitech.1c00288 图 2：没有图例的
    单系列柱，点上写了图注里的名字，列表里却是另一个或没有）；多条系列时，引用列表外名字的点不超过一半就只丢这些点、
    记下来（jafc.5c17360 图 8a 把两层横轴的样品组「CX@Lut」当成了系列），过半照旧交给自检判失败。
    返回 {子图: [丢掉的系列名]}。"""
    dropped = {}
    for p in data.get('panels') or []:
        pts = p.get('points') or []
        declared = [s.get('name') for s in p.get('series') or [] if s.get('name')]
        used = {q.get('series') for q in pts if q.get('series') and not unresolved(q.get('series'))}
        orphan = used - set(declared)
        if not orphan:
            continue
        if len(used) == 1 and len(declared) <= 1:
            name = next(iter(used))
            if declared:
                p['series'] = [dict(s, name=name) if s.get('name') == declared[0] else s for s in p['series']]
            else:
                p['series'] = list(p.get('series') or []) + [{'name': name, 'axis': 'left',
                                                              'chart_type': p.get('chart_type') or 'bar'}]
            continue
        bad = [q for q in pts if q.get('series') in orphan]
        if len(bad) * 2 > len(pts):
            continue
        p['points'] = [q for q in pts if q.get('series') not in orphan]
        dropped[panel_key(p.get('panel_id'), case) or ''] = sorted(orphan)
    return dropped


def dropped_flags(out_of_range, orphan):
    return (['%s: %d 个点比纵轴刻度大或小得多，只丢这几个点（%s）' % (k or '-', len(v), '；'.join(v[:5]))
             for k, v in sorted(out_of_range.items())]
            + ['%s: 系列 %s 不在图例里，只丢它们的点' % (k or '-', '、'.join(v)) for k, v in sorted(orphan.items())])


def gates(data, want_panels, case=False, smooth=(), unresolved_empty=()):
    """读完的自检，只用模型自己的输出交叉校验。命中 BLOCKING 的这一遍判失败，其余只是提示。"""
    flags = []
    panels = data.get('panels') or []
    if not panels:
        return ['零产出：panels 为空']
    want = [panel_key(p, case) for p in want_panels]
    got = [panel_key(p.get('panel_id'), case) for p in panels]
    if want:
        extra = [g for g in got if g and g not in want]
        missing = [w for w in want if w not in got]
        if extra:
            flags.append('多出未要求的子图 %s（分类阶段判定其无数值轴）' % extra)
        if missing:
            flags.append('缺少要求的子图 %s' % missing)
    for p in panels:
        pid = p.get('panel_id') or '-'
        pts = p.get('points') or []
        key = panel_key(p.get('panel_id'), case) or ''
        if not pts:
            if key in set(smooth or ()):
                flags.append(SMOOTH_NOTE % pid)
            elif key in set(unresolved_empty or ()):
                flags.append(UNRESOLVED_EMPTY % pid)
            else:
                flags.append('%s: 该子图 0 个数据点' % pid)
            continue
        axis_of = axis_of_series(p)
        ys = [q.get('y_value') for q in pts if q.get('y_value') is not None]
        for ax_name, field, cn in AXES:
            ya = p.get(field) or {}
            if not ya:
                continue
            lo, hi = ya.get('min'), ya.get('max')
            sub = [q.get('y_value') for q in pts
                   if q.get('y_value') is not None and axis_of.get(q.get('series'), 'left') == ax_name]
            if lo is None or hi is None or not sub:
                continue
            out = [y for y in sub if outside_axis(ya, y)]
            if out:
                flags.append('%s: %s轴 %d 个 Y 值超出自报刻度 [%s, %s] 逾%s，例如 %s'
                             % (pid, cn, len(out), lo, hi, axis_tol_text(ya), out[:3]))
        if not ys:
            flags.append('%s: 所有 Y 值都是 null' % pid)
        elif len(pts) > 3 and len(set(ys)) == 1:
            flags.append('%s: %d 个点 Y 值全部相同（%s），疑似敷衍' % (pid, len(pts), ys[0]))
        if any(not q.get('series') or str(q['series']).startswith('UNRESOLVED') for q in pts):
            flags.append('%s: 系列归属未确认' % pid)
        for q in pts:
            y, lo, hi = q.get('y_value'), q.get('err_low'), q.get('err_high')
            if y is not None and not error_bars_ok(y, lo, hi):
                flags.append('%s: 误差棒范围异常' % pid)
        for s in {q.get('series') for q in pts}:
            xs = [(q.get('x_category'), q.get('x_value')) for q in pts if q.get('series') == s]
            if len(xs) != len(set(xs)):
                flags.append('%s/%s: 同系列内 X 有重复' % (pid, s))
        cnt = {}
        for q in pts:
            cnt[q.get('series')] = cnt.get(q.get('series'), 0) + 1
        if len(cnt) > 1 and len(set(cnt.values())) > 1:
            flags.append('%s: 各系列点数不齐 %s，疑似漏读标记点'
                         % (pid, dict(sorted(cnt.items(), key=lambda kv: -kv[1]))))
        orphan = {q.get('series') for q in pts} - {s.get('name') for s in (p.get('series') or [])}
        if orphan:
            flags.append('%s: 点引用了图例里没有的系列 %s' % (pid, sorted(orphan)))
    return flags


def check_reading(t, raw):
    """一遍读图结果的后处理：只留要读的子图 → 表格按格子原文重算 → 丢掉对不上的系列 → 自检。"""
    table = t['kind'] == 'table'
    data, dropped = only_requested(raw, t['read_panels'], t['case'], table)
    copied = printed_cells(data) if table else []
    lost, emptied = drop_unresolved(data, t['case'])
    orphan = fix_series_names(data, t['case'])
    outside = drop_out_of_range(data, t['case'])
    smooth = smooth_panels(t)
    want = [p for p in t['read_panels'] if p]
    fl = (gates(data, want, t['case'], smooth, emptied) + copied + unresolved_flags(lost, emptied)
          + dropped_flags(outside, orphan))
    if dropped:
        fl.append('已丢弃未要求的子图 %s（不是这次要读的数据）' % dropped)
    hard = [x for x in fl if is_blocking(x)]
    return {'ok': not hard, 'flags': fl, 'blocking_flags': hard, 'data': data,
            'smooth_empty': smooth_empty(data, smooth, t['case']),
            'unresolved_series': lost, 'unresolved_empty': emptied,
            'out_of_range': outside, 'orphan_series': orphan,
            'scope': [panel_key(x, t['case']) or '' for x in t['read_panels']]}


def salvage(t, rec):
    """同样的输入连续 READ_TRIES 次没过自检、这一遍放弃（gave_up）时：只丢没过自检的子图，过了的照常用（用户 2026-10-19：
    foodchem.2025.143276 图 7 只有 I 刻度对不上，A–J 九个子图全成了读图失败）。按最后一次读的结果逐个子图重新自检：
    要读的子图没读回来、或自己的自检有挡路的问题，记进 salvaged {子图: 原因}，从 data 和 scope 里去掉；剩下的这一遍算读成。
    一个子图都不剩、或整图只有一个没编号的子图时原样返回（照旧整张图读图失败）。"""
    data = rec.get('data')
    want = [p for p in t['read_panels'] if p]
    if not rec.get('gave_up') or not data or not want:
        return rec
    case = t['case']
    smooth = smooth_panels(t)
    emptied = rec.get('unresolved_empty') or []
    by_key = {}
    for p in data.get('panels') or []:
        by_key.setdefault(panel_key(p.get('panel_id'), case) or '', []).append(p)
    keep, bad = [], {}
    for w in want:
        k = panel_key(w, case) or ''
        if k in bad or any(panel_key(p.get('panel_id'), case) == k for p in keep):
            continue
        ps = by_key.get(k)
        if not ps:
            bad[k] = '缺少这个子图'
            continue
        hard = [f for f in gates(dict(data, panels=ps), [w], case, smooth, emptied) if is_blocking(f)]
        if hard:
            bad[k] = '；'.join(dict.fromkeys(hard))[:200]
        else:
            keep.extend(ps)
    if not keep:
        return rec
    return dict(rec, ok=True, gave_up=False, salvaged=bad, data=dict(data, panels=keep),
                scope=[k for k in rec.get('scope') or [] if k not in bad])


# =============================================================== 合并（merge.py） ==
def garbled(text):
    """读图模型偶尔吐出坏字符：「°C」成了 \\x00C、「μM」成了单独的组合附加符号（jf300409y 图 9 三遍里一遍这样，
    整张图因「单位冲突」不入库）。控制字符、替换符 �、合成后仍单独留着的组合附加符号都算。"""
    text = unicodedata.normalize('NFC', text or '')
    return any(unicodedata.category(c) in ('Cc', 'Cs', 'Co') or c == '\ufffd'
               or (unicodedata.category(c) == 'Mn' and (i == 0 or not text[i - 1].isalpha()))
               for i, c in enumerate(text))


def canonical_unit(value):
    value = (value or '').strip()
    if garbled(value):
        return ''        # 当作这一遍没写单位（用户 2026-10-13）：不算冲突，显示时用别的几遍写对的
    return {'rad/sec': 'rad/s', 'rad s−1': 'rad/s', 'rad s-1': 'rad/s'}.get(value, value)


def _decimals(value):
    text = repr(float(value))
    if 'e' in text or 'E' in text or text in ('inf', '-inf', 'nan'):
        return None
    return len(text.split('.')[1]) if '.' in text else 0


def median_of(readings):
    """各遍读数的中位数（两遍就是平均），比读数多留一位小数，不出 6.949999999999999 这类浮点尾巴。"""
    if not readings:
        return None
    value = statistics.median(readings)
    places = [_decimals(r) for r in readings]
    if any(p is None for p in places):
        return value
    return round(value, min(max(places) + 1, 12))


def run_index(name):
    m = re.search(r'(\d+)$', name or '')
    return int(m.group(1)) if m else 1


def load_points(targets, run_name, records):
    """一遍读图结果里要读的子图上的点（每遍的读图范围 scope 之外的子图不算）。"""
    pts = []
    for key, r in records.items():
        t = targets.get(key)
        if not t or not r.get('ok'):
            continue
        allow = {panel_key(v, t['case']) or '' for v in t['read_panels']}
        scope = set(r.get('scope') or [])
        for pan in r['data']['panels']:
            pid = panel_key(pan.get('panel_id'), t['case']) or ''
            if pid not in allow or pid not in scope:
                continue
            yl = pan.get('y_left') or {}
            other = {'right': pan.get('y_right') or {}, 'third': pan.get('y_third') or {}}
            xu = (pan.get('x_axis') or {}).get('unit') or ''
            axis_of = axis_of_series(pan)
            for q in pan.get('points') or []:
                ax = axis_of.get(q.get('series'), 'left')
                ya = other.get(ax) or yl
                y = q.get('y_value')
                lo, hi = finite_number(ya.get('min')), finite_number(ya.get('max'))
                pts.append({'fig': key, 'panel': pid, 'series': q.get('series'),
                            'xc': q.get('x_category'), 'xv': q.get('x_value'),
                            'y': y if y is not None and math.isfinite(y) else None,
                            # 这一遍自报的纵轴满量程（最大刻度 - 最小刻度），判小数值几遍读数一不一致用
                            'span': abs(hi - lo) if lo is not None and hi is not None and hi != lo else None,
                            'xu': canonical_unit(xu), 'yu': canonical_unit(ya.get('unit')),
                            'axis': ax, 'mul': ya.get('multiplier') or '', 'sig': q.get('sig') or '',
                            'est': '是' if q.get('estimated') else '',
                            # 误差棒两端按大小排好（纵轴倒过来画时模型常把两端对调，见 error_bars_ok）
                            'el': min_or_none(q.get('err_low'), q.get('err_high'), min),
                            'eh': min_or_none(q.get('err_low'), q.get('err_high'), max),
                            'note': q.get('note') or '', 'run': run_name})
    return pts


def min_or_none(lo, hi, pick):
    """误差棒的下端（pick=min）或上端（pick=max）：两端都有时按大小取，只有一端时照原样。"""
    if lo is not None and hi is not None:
        return pick(lo, hi)
    return lo if pick is min else hi


def canon_x(q):
    """X 统一口径：分类标签能解析成数字就当数值（一遍写 "0"、一遍写 0.0 是同一个点）。"""
    xc, xv = q.get('xc'), q.get('xv')
    if xc is not None and str(xc).strip() != '':
        s = str(xc).strip().replace(',', '')
        try:
            return ('num', float(s))
        except ValueError:
            return ('cat', s)
    if xv is not None:
        return ('num', float(xv))
    return ('cat', '')


def _point_tolerances(points, tol_frac):
    xs = sorted({q['xv'] for q in points})
    limits = {}
    for i, x in enumerate(xs):
        gaps = []
        if i:
            gaps.append(x - xs[i - 1])
        if i + 1 < len(xs):
            gaps.append(xs[i + 1] - x)
        limits[x] = max(min(gaps) * tol_frac if gaps else abs(x) * .01, 1e-12)
    return limits


def dedupe_within_run(points):
    out, seen = [], set()
    for q in points:
        kind, val = canon_x(q)
        y = q.get('y')
        key = (q['run'], q['fig'], q['panel'], q['series'], kind,
               round(val, 12) if kind == 'num' else val,
               None if y is None else round(float(y), 12),
               q.get('xu'), q.get('yu'), q.get('axis'), q.get('mul'))
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out


# 系列名比对前去掉的记号说明：读图模型给柱、线两条同名系列自己加的「[bar]」「（点线）」之类
SERIES_MARK_NOTE = re.compile(r'\s*[\[(]\s*(?:bar|line|point|points|scatter|dot|柱|柱状|点|点线|线|折线|曲线)\s*[\])]',
                              re.I)


def series_key(name):
    """系列名的比对形式：全角半角统一，去掉记号说明，各种破折号、连字符、冒号、逗号、分号、空格都当一个空格，不分大小写。
    2026-10-12：两遍把同一条系列写成「Chickpea—暗红色圆点」和「Chickpea：暗红色圆点」、「0 U [bar]」和「0 U（柱）」，
    配不上对、各自只算一遍读出，整组不通过（afres.2026.101699、afres.2025.101637）。"""
    s = SERIES_MARK_NOTE.sub('', unicodedata.normalize('NFKC', name or ''))
    s = re.sub(r'[\s‐-―\-:;,·_]+', ' ', s)
    return s.strip().casefold()


def name_words(name):
    """系列名用了哪些词（不分顺序）：series_key 之后去掉括号、按空格拆开排好。用词一样、只是顺序不同的写法算同一条
    （用户 2026-10-12：「0% sucrose - Air phase fraction」和「Air phase fraction (0% sucrose)」算同一条，afres.2026.102097）。"""
    return ' '.join(sorted(re.findall(r'[^\s()\[\]{}]+', series_key(name))))


def unify_written_names(points):
    """同一子图里各遍对同一条系列的不同写法统一成一个名字：先按 series_key（全半角、标点、大小写、记号说明），再按
    name_words（用词一样、顺序不同）；都要在同一个纵轴上。用最多几遍的写法，一样多用最早那遍的。哪一遍里有两条不同的系列
    比对形式一样（如真有「WPI」和「wpi」两组、「WPI-CS」和「CS-WPI」两组），这一步就不统一这个形式，照旧按原名。
    名字还是配不上的，最后按数值配（unify_by_values，用户 2026-10-13）。"""
    for keyfn in (series_key, name_words):
        _unify_by(points, keyfn)
    unify_by_values(points)


def _unify_by(points, keyfn):
    by_panel = {}
    for q in points:
        k = (keyfn(q['series']), q.get('axis') or 'left')
        by_panel.setdefault((q['fig'], q['panel'] or ''), {}).setdefault(k, {}).setdefault(q['run'], set()).add(q['series'])
    rename = {}
    for panel, keys in by_panel.items():
        for k, by_run in keys.items():
            if any(len(names) > 1 for names in by_run.values()):
                continue
            order = [next(iter(by_run[r])) for r in sorted(by_run, key=run_index)]
            if len(set(order)) < 2:
                continue
            keep = min(dict.fromkeys(order), key=lambda s: (s.startswith('UNRESOLVED'), -order.count(s), order.index(s)))
            for name in order:
                rename[panel + (name, k[1])] = keep
    for q in points:
        new = rename.get((q['fig'], q['panel'] or '', q['series'], q.get('axis') or 'left'))
        if new:
            q['series'] = new


# 名字配不上的系列按数值配（用户 2026-10-13）：至少几个相同 X、至少占较短那条的几成、其中几成读数一致
VALUE_MATCH_MIN, VALUE_MATCH_COVER, VALUE_MATCH_AGREE = 2, 0.5, 0.8


def same_curve(pa, pb, scale):
    """两遍各一条系列的点（同一子图、同一纵轴）读的是不是同一条线：相同 X（分类按标签、数值按配点容差，一对一）
    至少 VALUE_MATCH_MIN 个、不少于较短那条点数的 VALUE_MATCH_COVER，这些 X 上至少 VALUE_MATCH_AGREE 的读数按 agree 一致。"""
    def index(pts):
        cats, nums = {}, []
        for q in pts:
            kind, val = canon_x(q)
            if kind == 'num':
                nums.append(dict(q, xv=val))
            elif val != '':
                cats.setdefault(val, q)
        return cats, nums
    ca, na = index(pa)
    cb, nb = index(pb)
    pairs = [(ca[c]['y'], cb[c]['y']) for c in ca if c in cb]
    if na and nb:
        ta, tb = _point_tolerances(na, MATCH_TOL), _point_tolerances(nb, MATCH_TOL)
        cand = sorted((abs(p['xv'] - q['xv']), i, j) for i, p in enumerate(na) for j, q in enumerate(nb)
                      if abs(p['xv'] - q['xv']) <= min(ta[p['xv']], tb[q['xv']]))
        used_i, used_j = set(), set()
        for _, i, j in cand:
            if i not in used_i and j not in used_j:
                used_i.add(i)
                used_j.add(j)
                pairs.append((na[i]['y'], nb[j]['y']))
    shorter = min(len(ca) + len(na), len(cb) + len(nb))
    if len(pairs) < VALUE_MATCH_MIN or len(pairs) < VALUE_MATCH_COVER * shorter:
        return False
    return sum(agree([a, b], scale) for a, b in pairs) >= VALUE_MATCH_AGREE * len(pairs)


# 样品名里的单位写法（用户 2026-10-13）：「1 hr」「1 hrs」「1 hour」都是 1h，「60 sec」是 60s
CAT_UNITS = ((r'(?:hrs?|hours?)', 'h'), (r'(?:secs?|seconds?)', 's'), (r'(?:mins|minutes?)', 'min'), (r'(?:days?)', 'd'))


def cat_key(label):
    """样品名（分类 X）的比对形式（用户 2026-10-13「加一条规则」）：在 series_key 的基础上，• ・ 也当分隔符，数字和后面的
    单位之间的空格去掉（「60 s」「60s」），h / hr / hrs / hour、s / sec、min / minutes、d / day 统一；每个词都带字母时不分词序
    （「3R 5P」「5P 3R」）。实测两遍把同一个样品写成「45% sucrose 60 s」和「45% sucrose 60s」、「I • IIb」和「I·IIb」、
    「YKY + δ -Tocopherol」和「YKY + δ-Tocopherol」，各自只算一遍读出。不按读数配：同一系列里不同样品读数相近的很多
    （「1% CS」和「14% LF」），按读数配会张冠李戴。"""
    text = series_key(re.sub(r'[•・∙]', ' ', unicodedata.normalize('NFKC', label or '')))
    text = re.sub(r'(?<=\d)\s+(?=[a-zμ%°])', '', text)
    for pat, unit in CAT_UNITS:
        text = re.sub(r'(?<=\d)' + pat + r'\b', unit, text)
    tokens = re.sub(r'\s*([+/×])\s*', r' \1 ', text).split()
    # 词序：每个词都带字母时才不分（「3R 5P」「5P 3R」）；有单独的数字、百分数时分（「1% CS 2% LF」和「2% CS 1% LF」不是一个样品）
    if all(re.search(r'[a-z一-鿿]', t) for t in tokens):
        tokens = sorted(tokens)
    return ' '.join(tokens)


def unify_categories(points):
    """同一子图、同一系列里，各遍写法不同、cat_key 一样的样品名统一成一个（用出现遍数最多的写法，一样多用最早那遍的）。
    哪一遍里有两个不同的样品名 cat_key 一样，就不统一这个形式。能当数字读的标签（0、5、10）不动，照数值 X 配。"""
    groups = {}
    for q in points:
        kind, val = canon_x(q)
        if kind != 'cat' or val == '':
            continue
        groups.setdefault((q['fig'], q['panel'] or '', q['series']), {}).setdefault(cat_key(val), {}) \
            .setdefault(q['run'], set()).add(val)
    rename = {}
    for g, keys in groups.items():
        for k, by_run in keys.items():
            if any(len(v) > 1 for v in by_run.values()):
                continue
            order = [next(iter(by_run[r])) for r in sorted(by_run, key=run_index)]
            if len(set(order)) < 2:
                continue
            keep = min(dict.fromkeys(order), key=lambda v: (-order.count(v), order.index(v)))
            for v in order:
                rename[g + (v,)] = keep
    for q in points:
        kind, val = canon_x(q)
        if kind == 'cat' and val:
            new = rename.get((q['fig'], q['panel'] or '', q['series'], val))
            if new and new != val:
                q['xc'] = new


def unify_by_values(points):
    """写法统一后仍配不上名字的系列按数值配（用户 2026-10-13「加上按照数值配对」）：同一子图、同一纵轴上，只在一遍里
    出现的系列名（没和别的遍配上），和这一遍里没有的另一个系列名，数值是同一条线（same_curve）就算同一条，用出现遍数
    最多的写法（一样多用最早那遍的）。必须一对一：一条配上同一遍里的两条的不配，同一遍有两条配上同一个名字的也不配；
    连起来以后同一遍有两条、或这个名字在这一遍别的纵轴上已经有了，也不配。UNRESOLVED（系列归属没认出）的不参与。
    实测 jf0607866：三遍把同一条浊度线写成「Turbidity」「Turbidity (A600)」「Turbidity (A600, RU)」，读数几乎一样，
    却各自只算一遍读出。"""
    groups, tops, in_panel = {}, {}, {}
    for q in points:
        in_panel.setdefault((q['fig'], q['panel'] or '', q['run']), set()).add(q.get('series'))
        if q.get('y') is None or not q.get('series') or str(q['series']).startswith('UNRESOLVED'):
            continue
        k = (q['fig'], q['panel'] or '', q.get('axis') or 'left')
        tops[k] = max(tops.get(k, 0.0), abs(q['y']))
        groups.setdefault(k, {}).setdefault(q['series'], {}).setdefault(q['run'], []).append(q)
    rename = {}
    for k, by_name in groups.items():
        orphans = [(name, next(iter(by_run))) for name, by_run in by_name.items() if len(by_run) == 1]
        if not orphans or len(by_name) < 2:
            continue
        spans = [q['span'] for by_run in by_name.values() for pts in by_run.values() for q in pts if q.get('span')]
        scale = statistics.median(spans) if spans else tops.get(k) or None
        target = {}
        for a, run in orphans:
            hits = [b for b, by_run in by_name.items() if b != a and run not in by_run
                    and any(same_curve(by_name[a][run], pb, scale) for pb in by_run.values())]
            hit_runs = [r for b in hits for r in by_name[b]]
            if hits and len(hit_runs) == len(set(hit_runs)):      # 配上的几个名字在不同的遍里（三遍三个名字）才算数
                target[(a, run)] = hits
        claims = {}
        for (a, run), hits in target.items():
            for b in hits:
                claims.setdefault((b, run), []).append(a)
        parent = {}

        def root(n):
            while parent.get(n, n) != n:
                n = parent[n]
            return n
        for (a, run), hits in target.items():
            for b in hits:
                if len(claims[(b, run)]) == 1 and root(a) != root(b):
                    parent[root(a)] = root(b)
        comps = {}
        for name in by_name:
            comps.setdefault(root(name), []).append(name)
        for names in comps.values():
            if len(names) < 2:
                continue
            runs = [run for name in names for run in by_name[name]]
            if len(runs) != len(set(runs)):
                continue
            keep = min(names, key=lambda n: (-len(by_name[n]), min(run_index(r) for r in by_name[n])))
            if any(keep in in_panel.get((k[0], k[1], run), set()) for name in names if name != keep
                   for run in by_name[name]):
                continue
            for name in names:
                if name != keep:
                    for run in by_name[name]:
                        rename[k + (run, name)] = keep
    for q in points:
        new = rename.get((q['fig'], q['panel'] or '', q.get('axis') or 'left', q['run'], q['series']))
        if new:
            q['series'] = new


def unify_series(points, single_panels=frozenset()):
    """分类判为只有一条系列、每一遍也都只读出一条的子图：各遍叫法不同也是同一条线，统一用多数几遍的叫法
    （一样多用最早那遍的）。别的情况只统一写法（unify_written_names），写法统一后仍不同就是不同系列。"""
    for q in points:
        q['series'] = ' '.join((q.get('series') or '').split())
    unify_written_names(points)
    names = {}
    for q in points:
        key = (q['fig'], q['panel'] or '')
        if key in single_panels:
            names.setdefault(key, {}).setdefault(q['run'], set()).add(q['series'])
    for key, by_run in names.items():
        if any(len(s) != 1 for s in by_run.values()):
            continue
        order = [next(iter(by_run[r])) for r in sorted(by_run, key=run_index)]
        if len(set(order)) < 2:
            continue
        keep = min(dict.fromkeys(order), key=lambda s: (s.startswith('UNRESOLVED'), -order.count(s), order.index(s)))
        for q in points:
            if (q['fig'], q['panel'] or '') == key:
                q['series'] = keep


TABLE_DISAGREE = '表格图片里各遍抄出的格子不一样（%s），不能确定哪一遍对，需对照原表核对'


def printed_agreement(lst):
    """表格图片：几遍抄的是同一个印出来的格子，必须一字不差（均值、误差上下限、字母）。三遍里有一种抄法
    多于别的就按多数采用；否则全部保留、转人工，并写明各遍抄成了什么。"""
    groups = {}
    for q in lst:
        if q['y'] is not None:
            groups.setdefault((q['y'], q.get('el'), q.get('eh'), q.get('sig') or ''), []).append(q)
    if len(groups) <= 1:
        return lst, '', ''
    ranked = sorted(groups.values(), key=len, reverse=True)
    copies = '，'.join('第 %d 遍抄成「%s」' % (run_index(q['run']), q.get('note') or q['y'])
                      for q in sorted(lst, key=lambda q: run_index(q['run'])) if q['y'] is not None)
    if len(ranked[0]) >= 2 and len(ranked[0]) > len(ranked[1]):
        return ranked[0], '', '多数遍一致，按多数采用（%s）' % copies
    return lst, TABLE_DISAGREE % copies, ''


# 同一个意思的不同写法不算冲突（用户 2026-10-09；gemini 读图时两遍常常一遍倍数空着、一遍写 1，单位 ℃ / °C、µ / μ 混用，
# 整组被转人工）。只用于比对，表里照旧显示原来的写法。
_SUPERSCRIPT = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺', '0123456789-+')


def unit_key(value):
    """单位的比对写法：兼容字符统一（℃ → °C、µ → μ、全角 → 半角），去掉空白。"""
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(value or '')))


def mul_key(value):
    """轴倍率的比对写法：空、1、×1 一样；10^5、x10^5、×10⁵、1e5 一样。"""
    s = re.sub(r'10([⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+)', lambda m: '10^' + m.group(1).translate(_SUPERSCRIPT), str(value or ''))
    s = re.sub(r'\s+', '', unicodedata.normalize('NFKC', s)).lower()
    s = re.sub(r'^[x×*]', '', s)
    m = re.fullmatch(r'10\^\(?([-+]?\d+)\)?', s)
    if m:
        s = '1e%d' % int(m.group(1))
    try:
        return repr(float(s)) if s else repr(1.0)
    except ValueError:
        return s


def same_key(field, value):
    if field == 'mul':
        return mul_key(value)
    if field in ('xu', 'yu', 'X单位', 'Y单位'):
        return unit_key(value)
    return str(value or '').strip()


# 单位里多写的指标名、被测物名不算另一个单位（用户 2026-10-12）；但多出来的是单位的（mg %、mL %）照旧算不一样
UNIT_WORDS = {'ml', 'l', 'μl', 'ul', 'dl', 'mm', 'cm', 'μm', 'um', 'nm', 'm', 'mg', 'g', 'kg', 'μg', 'ug', 'ng', 'da',
              'kda', 'u', 'iu', 'cfu', 'pa', 'kpa', 'mpa', 'mol', 'mmol', 'μmol', 'umol', 'nmol', 'mv', 'v', 's', 'min',
              'h', 'd', 'w', 'kj', 'j', 'ppm', 'ppb', 'rpm', 'cp', 'au', 'a.u.', 'nm', 'mpa·s', 'pa·s'}
# 单位里写的倍率（10^-6 mol L^-1、x 10⁻⁶ mol L⁻¹、×10^3 g）：摘出来按倍率比（用户 2026-10-12，jf402159a）
_MUL_IN_UNIT = re.compile(r'[x×*]?\s*10\s*\^\s*\(?\s*([-+]?\d+)\s*\)?')


def unit_parts(value):
    """单位的比对形式：(词的列表, 单位里写的倍率或 None)。上标的 10⁻⁶ 先改写成 10^-6，兼容字符统一
    （℃ → °C、µ → μ、全角 → 半角、上标 → 普通字符），减号统一，^ 去掉（L^-1 和 L⁻¹ 一样），按空格和 / 拆开。"""
    s = re.sub(r'10([⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+)', lambda m: '10^' + m.group(1).translate(_SUPERSCRIPT), str(value or ''))
    s = unicodedata.normalize('NFKC', s).replace('−', '-').replace('–', '-')
    mul = None
    m = _MUL_IN_UNIT.search(s)
    if m:
        mul = mul_key('1e%d' % int(m.group(1)))
        s = s[:m.start()] + ' ' + s[m.end():]
    return re.findall(r'[^\s/]+|/', s.replace('^', '')), mul


def unit_key(value):
    """单位的比对写法（不含单位里写的倍率）：兼容字符统一、去掉空白。"""
    return ''.join(unit_parts(value)[0])


def eff_mul(unit, mul):
    """实际的轴倍率：单位里写了倍率的按单位里的（这时轴倍率一栏常常重复写了一遍），否则按轴倍率一栏。"""
    inside = unit_parts(unit)[1]
    return inside if inside is not None else mul_key(mul)


def _is_label(word):
    """单位里多出来的词是不是指标名、被测物名（FS、LD、Ser-NH₂、free、thiol、protein），而不是单位。"""
    return len(re.findall(r'[^\W\d_]', word)) >= 2 and word.casefold() not in UNIT_WORDS


def _subsequence(short, long):
    it = iter(long)
    return all(any(w == x for x in it) for w in short)


def unit_same(a, b):
    """两遍写的单位是不是同一个（不比单位里的倍率，倍率另比，见 eff_mul）：比对写法一样；有一遍没写；或者一遍多写了
    指标名、被测物名，如「FS %」和「%」、「Ser-NH₂ equiv/g soluble protein」和「equiv/g soluble protein」、
    「mol free thiol / mol protein」和「mol/mol protein」（2026-10-12 实测，整组按单位冲突转人工）。"""
    ta, tb = unit_parts(a)[0], unit_parts(b)[0]
    if not ta or not tb or ''.join(ta) == ''.join(tb):
        return True
    short, long = (ta, tb) if len(ta) < len(tb) else (tb, ta)
    if not _subsequence(short, long):
        return False
    extra = list(long)
    for w in short:
        extra.remove(w)
    return all(_is_label(w) for w in extra)


def semantic_conflicts(points):
    problems = []
    for field in ('xu', 'yu', 'axis', 'mul'):
        if field in ('xu', 'yu'):
            # 一遍没写单位、一遍写了，或一遍在单位前面多写了指标名，不算冲突（显示时取多数几遍的写法）
            raw = list(dict.fromkeys(str(q.get(field) or '').strip() for q in points))
            clash = any(not unit_same(a, b) for a, b in itertools.combinations(raw, 2))
        elif field == 'mul':
            # 倍率写在单位里（10^-6 mol L^-1）和写在倍率一栏（mol L^-1，×10^-6）一样
            clash = len({eff_mul(q.get('yu'), q.get('mul')) for q in points}) > 1
        else:
            clash = len({same_key(field, q.get(field)) for q in points}) > 1
        if clash:
            problems.append('%s 冲突: %s' % (field, sorted({str(q.get(field) or '').strip() for q in points})))
    if any(not q.get('series') or str(q['series']).startswith('UNRESOLVED') for q in points):
        problems.append('系列归属未确认')
    by_run = {}
    for q in points:
        by_run.setdefault(q['run'], set()).add(q.get('y'))
    if any(len(v) > 1 for v in by_run.values()):
        problems.append('同一遍同一分类点有多个读数')
    return problems


def cluster(points, tol_frac=MATCH_TOL, single_panels=frozenset()):
    """同（图, 子图, 系列）里把各遍的同一个点归成一簇：分类 X 按标签精确匹配；数值 X 以点最多的那遍为基准
    做一对一最近邻匹配，容差 = 本遍相邻点距 × tol_frac；同一遍在一簇里最多一个点，配不上的自成一簇。"""
    unify_series(points, single_panels)
    unify_categories(points)
    groups = {}
    for q in points:
        groups.setdefault((q['fig'], q['panel'], q['series']), []).append(q)
    out = []
    for key, qs in groups.items():
        cats, nums, blank = {}, [], []
        for q in qs:
            kind, val = canon_x(q)
            if kind == 'cat':
                if val == '':
                    blank.append(q)
                else:
                    cats.setdefault(val, []).append(q)
            else:
                q = dict(q)
                q['xv'] = val
                nums.append(q)
        # 没写 X 的点：每一遍最多一个时就是同一个点（每条系列只画了一根柱，2026-10-12 afres.2026.102246：三遍读数一样，
        # 原来各自成簇、都只算一遍读出）；某一遍有好几个就分不清谁对谁，照旧各自成簇
        runs_blank = [q['run'] for q in blank]
        if blank and len(runs_blank) == len(set(runs_blank)):
            out.append((key, None, blank))
        else:
            out.extend((key, None, [q]) for q in blank)
        for c, lst in cats.items():
            out.append((key, c, lst))
        if not nums:
            continue
        by_run = {}
        for q in nums:
            by_run.setdefault(q['run'], []).append(q)
        for run_points in by_run.values():
            limits = _point_tolerances(run_points, tol_frac)
            for q in run_points:
                q['_match_tol'] = limits[q['xv']]
        base_run = max(by_run, key=lambda r: (len(by_run[r]), -len(str(r))))
        base = sorted(by_run.pop(base_run), key=lambda q: q['xv'])
        clusters = [[q] for q in base]
        for run, lst in by_run.items():
            cand = []
            for q in lst:
                for i, c0 in enumerate(clusters):
                    d = abs(q['xv'] - c0[0]['xv'])
                    if d <= min(q['_match_tol'], c0[0]['_match_tol']):
                        cand.append((d, i, q))
            cand.sort(key=lambda z: z[0])
            used_i, used_q = set(), set()
            for d, i, q in cand:
                if i in used_i or id(q) in used_q:
                    continue
                clusters[i].append(q)
                used_i.add(i)
                used_q.add(id(q))
            for q in lst:
                if id(q) not in used_q:
                    clusters.append([q])
        for c0 in clusters:
            out.append((key, c0[0]['xv'], c0))
    return out


def spread_of(ys):
    """几遍读数的离散度 %：(最大 - 最小) / |中位数|；不到两个读数为 None。"""
    if len(ys) < 2:
        return None
    med = median_of(ys)
    if med not in (None, 0):
        return (max(ys) - min(ys)) / abs(med) * 100
    return 0.0 if max(ys) == min(ys) else float('inf')


def agree(ys, scale, max_spread=MAX_SPREAD):
    """几遍读数算不算一致（用户 2026-10-12）：离散度不超过 max_spread%，或者最多只差纵轴满量程的 FS_TOL%。
    后一条给小数值、矮柱：0–100 的轴上 0.5 和 0.6 只差一根线粗，按这个点本身算却是 20% 的离散度。"""
    sp = spread_of(ys)
    if sp is None:
        return True
    if sp <= max_spread:
        return True
    return bool(scale) and (max(ys) - min(ys)) <= FS_TOL / 100 * scale


def majority(lst, scale):
    """图三遍以上、整体不一致时：找读数一致的最多几遍（至少两遍；一样多取离散度最小的）。
    返回 (采用的点, 没采用的点)；找不到为 None（用户 2026-10-12：三遍里两遍一致就采用这两遍）。"""
    valid = [q for q in lst if q['y'] is not None]
    for size in range(len(valid) - 1, 1, -1):
        best = None
        for combo in itertools.combinations(valid, size):
            ys = [q['y'] for q in combo]
            if agree(ys, scale):
                sp = spread_of(ys)
                if best is None or sp < best[0]:
                    best = (sp, combo)
        if best:
            kept = list(best[1])
            return kept, [q for q in valid if q not in kept]
    return None


def merge(targets, runs, min_runs=2, spread_ok=SPREAD_OK):
    """runs：[(遍名, {图 key: 记录})]。返回合并后的点（与流水线 merged.csv 同样的字段，另加 y_diff_fs_pct、说明）。"""
    pts = []
    for name, records in runs:
        pts += load_points(targets, name, records)
    pts = dedupe_within_run(pts)
    single = {(k, panel_key(h.get('panel'), t['case']) or '') for k, t in targets.items()
              for h in t.get('hints', []) if h.get('n_series') == 1}
    # 读图模型没报纵轴刻度范围时，满量程按这个子图同一纵轴上的最大读数算
    tops = {}
    for q in pts:
        if q['y'] is not None:
            k = (q['fig'], q['panel'], q['axis'])
            tops[k] = max(tops.get(k, 0.0), abs(q['y']))
    rows = []
    for (fig, panel, series), x, lst in cluster(pts, MATCH_TOL, single):
        seen = {q['run'] for q in lst}
        every = lst
        figure = targets[fig]['kind'] != 'table'
        printed_review = printed_note = note = ''
        if not figure:
            lst, printed_review, printed_note = printed_agreement(lst)
        valid_runs = {q['run'] for q in lst if q['y'] is not None}

        def vote(field):
            vals = [q.get(field) for q in lst if q.get(field)]
            return max(dict.fromkeys(vals), key=vals.count) if vals else ''
        scale = None
        if figure:
            spans = [q['span'] for q in lst if q.get('span')]
            scale = statistics.median(spans) if spans else tops.get((fig, panel, vote('axis') or 'left')) or None
        ys = [q['y'] for q in lst if q['y'] is not None]
        outvoted = False
        # 三遍以上、每遍一个读数（同一遍读出两个的是冲突，照旧转人工）时才按多数
        if figure and len(ys) >= 3 and len(ys) == len(valid_runs) and not agree(ys, scale):
            first = [q for q in lst if q['y'] is not None and run_index(q['run']) <= RUNS]
            blank = [q for q in lst if q['y'] is None]
            if len(first) >= 2 and agree([q['y'] for q in first], scale):
                # 第三遍是按子图补读的，这个点前两遍本来就一致：只用前两遍（一致性照两遍算），第三遍不采用
                note = '前两遍一致（%s），%s 和它们差得多，没采用' % (
                    ' / '.join('%.6g' % q['y'] for q in first),
                    '、'.join('第 %d 遍 %.6g' % (run_index(q['run']), q['y']) for q in lst
                             if q['y'] is not None and q not in first))
                lst, ys = first + blank, [q['y'] for q in first]
            else:
                # 前两遍不一致：第三遍裁决，三遍里两遍一致就采用那两遍
                found = majority(lst, scale)
                if found:
                    kept, dropped = found
                    note = '%d 遍里 %d 遍一致（%s），%s 和它们差得多，没采用' % (
                        len(ys), len(kept), ' / '.join('%.6g' % q['y'] for q in kept),
                        '、'.join('第 %d 遍 %.6g' % (run_index(q['run']), q['y']) for q in dropped))
                    lst, ys, outvoted = kept + blank, [q['y'] for q in kept], True
        med = median_of(ys)
        spread = spread_of(ys)
        diff_fs = None
        if figure and len(ys) > 1 and scale:
            diff_fs = (max(ys) - min(ys)) / scale * 100
            if not note and spread is not None and spread > MAX_SPREAD and diff_fs <= FS_TOL:
                note = '数值小：几遍最多只差纵轴满量程的 %.2g%%，按满量程判为一致' % diff_fs
        expected = sum(1 for _, records in runs
                       if fig in records and (panel or '') in set(records[fig].get('scope') or []))
        conflicts = semantic_conflicts(lst)
        if conflicts or not ys:
            conf = 'invalid'
        elif (len(valid_runs) >= min_runs and len(valid_runs) == expected and spread is not None and spread <= spread_ok
              and not outvoted):
            conf = 'high'
        elif len(valid_runs) >= min_runs and spread is not None:
            conf = 'medium'
        else:
            conf = 'low'

        def pick(f):
            return median_of([q[f] for q in lst if q[f] is not None])

        rows.append({'图片名': fig, '子图': panel or '', '系列': series or '', 'X类别/数值': x,
                     'X单位': vote('xu'), 'Y值': med, 'Y单位': vote('yu'),
                     'Y轴': vote('axis') or 'left', '轴倍率': vote('mul'),
                     '显著性': vote('sig'), '估读': vote('est'),
                     '误差棒下限': pick('el'), '误差棒上限': pick('eh'),
                     'n_runs_expected': expected,
                     'review_reason': '; '.join(conflicts + ([printed_review] if printed_review else [])),
                     'n_runs_seen': len(seen), 'n_runs_valid': len(valid_runs),
                     'y_spread_pct': None if spread is None else round(spread, 3),
                     'y_diff_fs_pct': None if diff_fs is None else round(diff_fs, 3),
                     'confidence': conf,
                     # 前两遍不一致、靠第三遍凑出两遍一致的：表里给这两遍的平均值，仍转人工复核（用户 2026-10-12 选 F）
                     '三遍取多数': outvoted,
                     '说明': note,
                     '各次读数': ';'.join('%s=%s' % (q['run'], q['y']) for q in every),
                     '备注': ' '.join(sorted({q['note'] for q in lst if q['note']}
                                            | ({printed_note} if printed_note else set())))})
    rows.sort(key=lambda r: (r['图片名'], str(r['子图']), str(r['系列']), str(r['X类别/数值'])))
    return rows


# =============================================================== 补读第三遍（read_runs.py） ==
def always(records_by_run, field):
    """{图: 每一遍都在 field 里的子图}（smooth_empty：只画了线、没读出点；unresolved_empty：系列全对不上）。"""
    out = {}
    for key in set.intersection(*[set(r) for r in records_by_run]) if records_by_run else set():
        sets = [set(r[key].get(field) or []) for r in records_by_run]
        common = set.intersection(*sets)
        if common:
            out[key] = common
    return out


def always_empty(records_by_run):
    """{图: 每一遍都没读出点、而且不算失败的子图}：只画了线（smooth_empty）或系列全对不上（unresolved_empty）。
    同一个子图这一遍是前者、那一遍是后者也算。"""
    out = {}
    for key in set.intersection(*[set(r) for r in records_by_run]) if records_by_run else set():
        sets = [set(r[key].get('smooth_empty') or []) | set(r[key].get('unresolved_empty') or [])
                for r in records_by_run]
        common = set.intersection(*sets)
        if common:
            out[key] = common
    return out


def empty_figures(targets, records_by_run):
    """要读的子图全都每遍没读出点（只有光滑曲线或系列对不上）的图：没有可合并的数，也不算失败。"""
    empty = always_empty(records_by_run)
    return {t['key'] for t in targets if t['read_panels']
            and {panel_key(x, t['case']) or '' for x in t['read_panels']} <= empty.get(t['key'], set())}


def retry_plan(targets, runs, threshold=ESCALATE):
    """{图: 要补读的子图（None = 整图）}。两遍试合并后，有效遍数不足、有冲突、一致性 low/invalid、
    离散度超过 threshold 的子图，以及整个没读出来的子图，补读第三遍。
    每一遍都只读出光滑曲线（0 点）或系列全对不上的子图不补：再读一遍也是一样（修正流水线遗留问题 ④：
    流水线只在整张图都是这种子图时才跳过，图里还有别的子图时会把它当"缺失"补读）。"""
    n_runs = len(runs)
    skip = always_empty([r for _, r in runs])
    rows = merge(targets, runs)
    expected = {}
    for key, t in targets.items():
        wanted = {panel_key(x, t['case']) or '' for x in t['read_panels']}
        wanted -= skip.get(key, set())
        if wanted:
            expected[key] = wanted
    chosen, seen_panels, seen = {}, {}, {}
    for r in rows:
        fig = r['图片名']
        if fig not in expected:
            continue
        panel = r['子图'] or ''
        if panel not in expected[fig]:
            continue
        seen[fig] = seen.get(fig, 0) + 1
        seen_panels.setdefault(fig, set()).add(panel)
        spread = r.get('y_spread_pct')
        spread = float('inf') if spread is None else spread
        if targets[fig]['kind'] == 'table':
            # 表格是逐格抄印出来的字：两遍抄得不一样时第三遍按多数采用，照旧
            bad = (r['n_runs_valid'] < n_runs or r.get('review_reason') or r['confidence'] in {'invalid', 'low'}
                   or not math.isfinite(spread) or spread > threshold)
        else:
            # 图：某一遍漏读的点补第三遍；两遍都读到、相差超过 5%（又超过满量程 1%）的也补（用户 2026-10-12），
            # 三遍里两遍一致就采用那两遍（merge 里的 majority）。10-09 到 10-12 之间这种不补、直接取平均转人工复核
            fs = r.get('y_diff_fs_pct')
            bad = r['n_runs_valid'] < n_runs or (spread > threshold and not (fs is not None and fs <= FS_TOL))
        if bad:
            chosen.setdefault(fig, set()).add(panel)
    plan = {}
    for fig, wanted in expected.items():
        missing = wanted - seen_panels.get(fig, set())
        if missing:
            chosen.setdefault(fig, set()).update(missing)
        if chosen.get(fig):
            plan[fig] = None if '' in chosen[fig] else sorted(chosen[fig])
    return plan


# =============================================================== 门槛和输出（pipeline_data / backfill / finalize） ==
RANK = {'invalid': -1, 'low': 0, 'medium': 1, 'high': 2, 'exact': 3}


def finite_number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def point_key(row):
    return (row.get('图片名') or '', row.get('子图') or '', row.get('系列') or '', str(row.get('X类别/数值') or ''))


def admissible(row, min_conf=MIN_CONF, max_spread=MAX_SPREAD):
    if row.get('review_reason'):
        return False, row['review_reason']
    conf = row.get('confidence') or 'low'
    if conf not in RANK or conf == 'invalid':
        return False, 'confidence=%s，不接受无效或未知置信度' % conf
    if RANK[conf] < RANK[min_conf]:
        return False, 'confidence=%s < %s' % (conf, min_conf)
    if finite_number(row.get('Y值')) is None:
        return False, 'Y 值为空或不是有限数值'
    raw = row.get('y_spread_pct')
    if row.get('三遍取多数'):
        # 前两遍不一致、第三遍凑出两遍一致：给这两遍的平均值，不算通过、转人工复核（用户 2026-10-12）
        return False, 'y_spread_pct=%s（前两遍不一致，三遍里两遍一致）' % raw
    if raw not in (None, ''):
        spread = finite_number(raw)
        fs = finite_number(row.get('y_diff_fs_pct'))
        # 离散度超了、但几遍最多只差纵轴满量程的 FS_TOL% 的也算一致（用户 2026-10-12）
        if (spread is None or spread > max_spread) and not (fs is not None and fs <= FS_TOL):
            return False, 'y_spread_pct=%s > %s 或不是有限数值' % (raw, max_spread)
    return True, ''


def select_rows(rows, min_conf=MIN_CONF, max_spread=MAX_SPREAD):
    """(通过的点, [(没通过的点, 原因)])。同一个点有几个通过的值、数值或单位坐标轴又对不上的，全部转人工。"""
    groups, rejected = {}, []
    for row in rows:
        ok, reason = admissible(row, min_conf, max_spread)
        if ok:
            groups.setdefault(point_key(row), []).append(row)
        else:
            rejected.append((row, reason))
    accepted = []

    def differ(a, b):
        """两行的单位、轴倍率是不是真的不一样（写法不同、或一行没写单位的不算）。"""
        for k in ('X单位', 'Y单位'):
            if not unit_same(a.get(k), b.get(k)):
                return True
        return eff_mul(a.get('Y单位'), a.get('轴倍率')) != eff_mul(b.get('Y单位'), b.get('轴倍率'))
    for group in groups.values():
        first = group[0]
        y = finite_number(first.get('Y值'))
        axis = first.get('Y轴') or 'left'
        conflict = any(
            abs(finite_number(row.get('Y值')) - y) >= 1e-9
            or differ(first, row)
            or (row.get('Y轴') or 'left') != axis for row in group[1:])
        if conflict:
            rejected.extend((row, '同键多值或单位/坐标轴冲突，全部转人工') for row in group)
        else:
            accepted.append(first)
    return accepted, rejected


def fmt(v):
    if v is None:
        return ''
    if isinstance(v, float):
        return '%.6g' % v if ('e' in repr(v) or not math.isfinite(v)) else repr(v)
    return str(v)


def display_reason(row, reason):
    if 'y_spread_pct=' in reason:
        return '多次读数离散度为 %s%%，超过入库阈值；可能存在取点偏差、曲线重叠或图像辨识差异。' % fmt(row.get('y_spread_pct'))
    if 'confidence=low' in reason:
        return '重复读取的有效覆盖不足；可能漏读或各遍选取的位置不一致。'
    if 'confidence=invalid' in reason:
        return '没有可用的一致读数或有效数值，需核对图像与各遍结果。'
    if '冲突' in reason or '重复' in reason:
        return reason + '；需核对坐标单位、系列身份或重复读数。'
    return reason


OVERLAP_REASON = '这个位置几条线的点重合，这个系列的标记被压在下面，没读出数值（同一位置其他系列有读数）。'


def hidden_by_overlap(row, rows):
    """本系列各遍都没读出值，同一 X 上至少另两条线读数相差不超过 5%：标记被压在下面。只改说明，不补数值。"""
    if finite_number(row.get('Y值')) is not None:
        return False
    x = str(row.get('X类别/数值') or '')
    ys = [finite_number(o.get('Y值')) for o in rows
          if (o.get('系列') or '') != (row.get('系列') or '') and str(o.get('X类别/数值') or '') == x]
    ys = [y for y in ys if y is not None]
    if len(ys) < 2:
        return False
    mid = statistics.median(ys)
    return max(ys) - min(ys) <= 0.05 * abs(mid) if mid else max(ys) == min(ys)


def is_deviation(reason):
    """没过门槛只是因为几遍读数相差超过 MAX_SPREAD（其余都对得上）。"""
    return 'y_spread_pct=' in (reason or '')


def is_single(row, reason):
    """没过门槛只是因为只有一遍读出这个点（别的遍没读到）。用户 2026-10-12：这种点也写进表里、单独标注出来，不入库。"""
    return 'confidence=low' in (reason or '') and row.get('n_runs_valid') == 1 and not row.get('review_reason')


def single_reason(row):
    """只有一遍读出的点：入库判定一栏标「只有一遍读出」就够了，原因一栏不另写（用户 2026-10-12）。"""
    return ''


def deviation_reason(row, rows):
    """几遍读数相差超过门槛（用户 2026-10-09）：表里两遍时是平均值、三遍时是中位数，写出各遍读数和相差多少，转人工复核。
    2026-10-12 起超过 5% 又超过满量程 1% 的才到这里，写出相差约为满量程的多少；图会先补第三遍，三遍两两都不一致才到这里。"""
    if row.get('三遍取多数') and row.get('说明'):
        return '%s；表中取这两遍的平均值，需人工复核。' % row['说明']
    reads = [finite_number(part.split('=', 1)[1]) for part in (row.get('各次读数') or '').split(';') if '=' in part]
    reads = [y for y in reads if y is not None]
    how = '平均值' if len(reads) == 2 else '中位数'
    fs = finite_number(row.get('y_diff_fs_pct'))
    return '%s遍读数 %s，%s相差 %s%%%s，超过 %g%%%s；表中取%s，需人工复核。' % (
        {2: '两', 3: '三'}.get(len(reads), str(len(reads))), ' / '.join('%.6g' % y for y in reads),
        '两两都不一致，' if len(reads) > 2 else '', fmt(row.get('y_spread_pct')),
        '（约为纵轴满量程的 %.2g%%）' % fs if fs is not None else '', MAX_SPREAD,
        '，也超过满量程的 %g%%' % FS_TOL if fs is not None else '', how)


def why_rejected(row, reason, rows):
    if not reason:
        return ''
    if 'confidence=invalid' in reason and hidden_by_overlap(row, rows):
        return OVERLAP_REASON
    if is_deviation(reason):
        return deviation_reason(row, rows)
    if is_single(row, reason):
        return single_reason(row)
    return display_reason(row, reason)


def escape_cell(value):
    text = '' if value is None else str(value)
    return text.replace('\\', '\\\\').replace('|', '\\|').replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')


def ordered(rows, min_conf=MIN_CONF, max_spread=MAX_SPREAD):
    """[(点, 没通过的原因 或 '')]，按系列、X 排（数值 X 按大小在前，分类 X 按字符串在后）。"""
    keep, dropped = select_rows(rows, min_conf, max_spread)
    display = [(r, '') for r in keep] + list(dropped)

    def order(item):
        x = item[0].get('X类别/数值')
        try:
            key = (0, float(x))
        except (ValueError, TypeError):
            key = (1, str(x or ''))
        return (item[0].get('系列') or '', key)
    display.sort(key=order)
    return display, len(keep), len(dropped)


def panel_table(rows):
    """一个子图的反读表：中文表头，整列为空的不显示（全部通过时没有"原因"一列）。"""
    display, n_ok, n_bad = ordered(rows)
    cols = [('系列', lambda r, why: r.get('系列') or ''),
            ('X / 样品', lambda r, why: fmt(r.get('X类别/数值'))),
            ('X 单位', lambda r, why: r.get('X单位') or ''),
            ('Y / 读数', lambda r, why: fmt(r.get('Y值'))),
            ('Y 单位', lambda r, why: r.get('Y单位') or ''),
            ('Y轴', lambda r, why: (r.get('Y轴') or 'left') if len({x.get('Y轴') or 'left' for x in rows}) > 1 else ''),
            ('轴倍率', lambda r, why: r.get('轴倍率') or ''),
            ('误差下限', lambda r, why: fmt(r.get('误差棒下限'))),
            ('误差上限', lambda r, why: fmt(r.get('误差棒上限'))),
            ('显著性', lambda r, why: r.get('显著性') or ''),
            ('有效/出现次数', lambda r, why: '%s/%s' % (r.get('n_runs_valid'), r.get('n_runs_seen'))),
            ('离散度 %', lambda r, why: fmt(r.get('y_spread_pct'))),
            ('一致性', lambda r, why: r.get('confidence') or ''),
            ('入库判定', lambda r, why: '**需人工复核**' if is_deviation(why) else '**只有一遍读出**' if is_single(r, why) else
             '**不满足入库要求**' if why else '满足数值门槛'),
            ('不满足要求或需复核的原因', lambda r, why: why_rejected(r, why, rows)),
            # 通过的点里，按「三遍两遍一致」或「只差满量程 1%」判为一致的写明（用户 2026-10-12）
            ('说明', lambda r, why: '' if why else r.get('说明') or '')]
    body = [[f(r, why) for _, f in cols] for r, why in display]
    keep = [i for i in range(len(cols)) if any(b[i] for b in body)]
    out = ['| ' + ' | '.join(cols[i][0] for i in keep) + ' |', '| ' + ' | '.join('---' for _ in keep) + ' |']
    out += ['| ' + ' | '.join(escape_cell(b[i]) for i in keep) + ' |' for b in body]
    return '\n'.join(out), n_ok, n_bad, sum(1 for _, why in display if is_deviation(why))


def panel_name(t, label):
    """子图名；起了「未编号N」的写明它是哪张图。"""
    desc = (t.get('unlabeled') or {}).get(label)
    return '%s（图上没有编号：%s）' % (label, desc) if desc else label


def functional_gaps(targets, rows, readings, failed=None):
    """没有反读数值的蛋白质功能特性子图：分类阶段没送读的（附原因），和送读了却没有数的。
    failed：{图: 原因}，同样的输入连续两次没通过自检、不再重读的图。"""
    failed = failed or {}
    got = {(r['图片名'], r['子图'] or '') for r in rows}
    smooth = always(readings, 'smooth_empty')
    lost_empty = always(readings, 'unresolved_empty')
    lost, part, given_up = {}, {}, {}
    for rec_by_key in readings:
        for key, r in rec_by_key.items():
            # 用户 2026-10-19：放弃的那一遍只丢了没过自检的子图（salvage），记下原因
            if r.get('ok'):
                for panel, why in (r.get('salvaged') or {}).items():
                    given_up.setdefault(key, {}).setdefault(panel, why)
            for panel, names in (r.get('unresolved_series') or {}).items():
                cur = lost.setdefault(key, {}).setdefault(panel, [])
                cur.extend(n for n in names if n not in cur)
            # 用户 2026-10-13：超出刻度的点、不在图例里的系列只丢它们，写明丢了什么
            for panel, items in (r.get('out_of_range') or {}).items():
                cur = part.setdefault(key, {}).setdefault(panel, [])
                cur.extend(x for x in ('超出纵轴刻度：%s' % i for i in items) if x not in cur)
            for panel, names in (r.get('orphan_series') or {}).items():
                cur = part.setdefault(key, {}).setdefault(panel, [])
                cur.extend(x for x in ('系列不在图例里：%s' % n for n in names) if x not in cur)
    gaps = []
    for t in targets:
        for u in t['functional_unread']:
            gaps.append('%s %s %s，%s，%s' % (label_cn(t), part_cn(t), u['panel'], u['property'], u['reason']))
        prop = {panel_key(h.get('panel'), t['case']) or '': h.get('property') for h in t.get('hints', [])}
        for p in t['read_panels']:
            key = panel_key(p, t['case']) or ''
            head = '%s %s %s，%s' % (label_cn(t), part_cn(t), panel_name(t, p) if p else '未标注',
                                     (prop.get(key) + '，') if prop.get(key) else '')
            names = lost.get(t['key'], {}).get(key)
            if (t['key'], key) not in got:
                if t['key'] in failed:
                    why = '读图失败：同样的输入连续 %d 次没通过自检（%s），没有反读数值' % (READ_TRIES, failed[t['key']])
                elif key in given_up.get(t['key'], {}):
                    why = ('读图失败：同样的输入连续 %d 次没通过自检（%s），没有反读数值；这张图的其余子图照常读'
                           % (READ_TRIES, given_up[t['key']][key]))
                elif key in lost_empty.get(t['key'], set()):
                    why = '系列在图例和图注里都对应不上，没读' + ('（%s）' % '、'.join(names) if names else '')
                elif key in smooth.get(t['key'], set()):
                    why = '只有光滑曲线，没有可读的数据点'
                else:
                    why = '送读后没读出数值'
                gaps.append(head + why)
            elif names:
                gaps.append(head + '其中 %d 条系列在图例和图注里对应不上，没读（%s）' % (len(names), '、'.join(names)))
            some = part.get(t['key'], {}).get(key)
            if some and (t['key'], key) in got:
                gaps.append(head + '有的遍里个别点没入库，请对照原图（%s）' % '；'.join(some[:6]))
    out = []
    for g in gaps:
        if g not in out:
            out.append(g)
    return out


def gaps_line(gaps):
    tables = sum(g.startswith('表 ') for g in gaps)
    what = '子图' if not tables else '表格指标' if tables == len(gaps) else '子图和表格指标'
    return '- 以下蛋白质功能特性%s没有反读数值：%s。' % (what, '；'.join(gaps))


def review_line(accepted, rejected):
    n_review = sum(1 for _, why in rejected if is_deviation(why))
    n_single = sum(1 for row, why in rejected if is_single(row, why))
    if not n_review and not n_single:
        return '- 反读表含 %d 个通过数值筛选的点和 %d 个未满足要求的点，后者已在对应表内标注。' % (len(accepted), len(rejected))
    parts = ['%d 个通过数值筛选的点' % len(accepted)]
    if n_review:
        parts.append('%d 个几遍读数相差超过 %g%% 的点（表中取平均值，需人工复核）' % (n_review, MAX_SPREAD))
    if n_single:
        parts.append('%d 个只有一遍读出的点' % n_single)
    return '- 反读表含 %s和 %d 个未满足要求的点，均已在对应表内标注。' % ('、'.join(parts), len(rejected) - n_review - n_single)


def appendix(model, targets, rows, accepted, rejected, readings, missing_images, failed=None, retry_failed=None):
    """「## 反读数据评价」：只写对反读数据的评价。一个点都没读、也没有没读的功能特性子图时不加。
    failed / retry_failed：{图: 原因}，前两遍 / 第三遍同样的输入连续两次没通过自检、不再重读的图。"""
    gaps = functional_gaps(targets, rows, readings, failed)
    extra = []
    if missing_images:
        extra.append('- 以下图片没下载下来，没有分类和反读：%s。' % '；'.join(missing_images))
    if retry_failed:
        names = {t['key']: label_cn(t) for t in targets}
        extra.append('- 以下图第 3 遍补读同样的输入连续 %d 次没通过自检，没再重读，按前两遍的结果合并：%s。'
                     % (READ_TRIES, '；'.join('%s（%s）' % (names.get(k, k), why) for k, why in retry_failed.items())))
    empty = empty_figures(targets, readings)
    numeric = [t for t in targets if t['read_panels'] and t['key'] not in empty]
    if not (accepted or rejected or numeric):
        if not gaps and not extra:
            return ''
        return '\n'.join(['---', '', '## 反读数据评价', ''] + ([gaps_line(gaps)] if gaps else []) + extra) + '\n'
    lines = ['---', '', '## 反读数据评价', '',
             '- 图像估读数据是读图估读值，不是原文给出的数值；用于发表或入库前请核对关键值（读图模型：`%s`）。' % model,
             review_line(accepted, rejected),
             '- 一致性等级 high / medium 表示重复读取的一致程度，不等于实验真值准确率；误差上下限为图中误差棒端点。']
    kinds = {t['key']: t['kind'] for t in targets}
    if any(kinds.get(r['图片名']) == 'table' for r in rows):
        lines.append('- 表格图片的反读值是从表格图片上逐格抄录的，误差上下限为表中的均值 ± 标准差。')
    if any(not t['read_panels'] or t['dense_panels'] or t['spectral_panels'] or t['unrelated_panels'] or t['review']
           for t in targets):
        lines.append('- 部分图未提取数值，这里的图像估读表不代表原图信息的完整覆盖。')
    if gaps:
        lines.append(gaps_line(gaps))
    if rejected:
        lines.append('- 未满足入库要求的数据点已列在对应子图的反读表内，并逐行注明判定与可能原因。')
    return '\n'.join(lines + extra) + '\n'


def input_digest(root):
    with open(os.path.join(root, FIGURE_DIR, 'figure_markdown.md'), 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


CODE_OF = {v: k for k, v in FUNCTIONAL.items()}


def db_info(paper, api, targets, rows, runs, failed=None):
    """反读数据.json 的内容（用户 2026-10-12：为了后面的清理流程，放在文章文件夹里、和 反读数据.md 一起）。
    只记送读了的子图：17 项里的哪一项（代号和中文名）、分类阶段抄的 X/Y 轴标题和图注片段、图型；读出了数的，
    每个系列在哪个纵轴、那个纵轴的标题（各遍读图投票取多数）、单位和倍率（和反读表里一样），以及 X 单位和点数。
    系列名和子图编号和 反读数据.md 表里的一致。"""
    def vote(vals):
        vals = [v for v in vals if v]
        return max(dict.fromkeys(vals), key=vals.count) if vals else None
    figures = []
    for t in targets:
        if not t['read_panels']:
            continue
        hints = {panel_key(h.get('panel'), t['case']) or '': h for h in t.get('hints', [])}
        titles, given_up = {}, set()
        for _, records in runs:
            rec = records.get(t['key'])
            if not rec or not rec.get('ok'):
                continue
            given_up |= set(rec.get('salvaged') or ())
            for p in (rec.get('data') or {}).get('panels') or []:
                d = titles.setdefault(panel_key(p.get('panel_id'), t['case']) or '',
                                      {'x': [], 'left': [], 'right': [], 'third': []})
                for side, ax in (('x', p.get('x_axis')), ('left', p.get('y_left')), ('right', p.get('y_right')),
                                 ('third', p.get('y_third'))):
                    d[side].append(((ax or {}).get('label') or '').strip())
        panels = []
        for label in t['read_panels']:
            k = panel_key(label, t['case']) or ''
            h = hints.get(k, {})
            mine = [r for r in rows if r['图片名'] == t['key'] and (r['子图'] or '') == k]
            by_series = {}
            for r in mine:
                by_series.setdefault(r['系列'], []).append(r)
            got = titles.get(k, {})
            series = []
            for name, rs in by_series.items():
                axis = vote([r.get('Y轴') for r in rs]) or 'left'
                series.append({'name': name, 'axis': axis, 'axis_title': vote(got.get(axis, [])),
                               'unit': vote([r.get('Y单位') for r in rs]), 'multiplier': vote([r.get('轴倍率') for r in rs]),
                               'x_unit': vote([r.get('X单位') for r in rs]), 'points': len(rs)})
            entry = {'panel': label, 'property': CODE_OF.get(h.get('property')), 'property_cn': h.get('property'),
                     'caption_part': h.get('caption_part'), 'series': series}
            if not mine and k in given_up:      # 只有这个子图读图失败，同图其余子图照常（用户 2026-10-19）
                entry['read_failed'] = True
            if t['kind'] == 'table':
                entry.update(header=label, layout=h.get('layout'))
            else:
                entry.update(chart_type=h.get('chart_type'), x_axis_title=h.get('x_axis'), y_axis_title=h.get('y_axis'),
                             x_axis_title_read=vote(got.get('x', [])))
            panels.append(entry)
        figures.append({'figure': t['heading'], 'kind': t['kind'], 'label': t['label'],
                        'read_failed': t['key'] in (failed or {}), 'panels': panels})
    return {'version': 1, 'article': os.path.basename(paper['root']),
            'models': {'prescreen': getattr(api, 'prescreen_model', None),
                       'classify': getattr(api, 'classify_model', None) or api.model, 'read': api.model},
            'figures': figures}


def model_note(api):
    """评价里写的模型：读图模型；分类用了别的模型、或先用初筛模型筛过时一起写明。"""
    note = api.model
    if api.classify_model and model_key(api.classify_model) != model_key(api.model):
        note += '`，分类模型：`%s' % api.classify_model
    if getattr(api, 'prescreen_model', None):
        note += '`，初筛模型：`%s' % api.prescreen_model
    return note


def render(paper, targets, rows, readings, model, missing_images, failed=None, retry_failed=None):
    """反读数据.md 的全文（放在文章文件夹里，图片链接指向同级的 figure\\）。"""
    accepted, rejected = select_rows(rows)
    md = ['# ' + (paper['title'] or paper['name']), '']
    if paper['doi']:
        md += ['DOI: ' + paper['doi'], '']
    grouped = {}
    for r in rows:
        grouped.setdefault(r['图片名'], {}).setdefault(r['子图'] or '-', []).append(r)
    for t in targets:
        if t['key'] not in grouped:
            continue
        md += ['## ' + t['heading'], '']
        md += ['![%s](%s/%s)' % (t['heading'], FIGURE_DIR, urllib.parse.quote(f)) for f in t['files']]
        md += ['']
        if t['caption']:
            md += [t['caption'], '']
        n = sum(map(len, grouped[t['key']].values()))
        md += ['**%s：图像估读数据**（%d 个点）' % (label_cn(t), n), '']
        for label, values in sorted(grouped[t['key']].items()):
            table, n_ok, n_bad, n_review = panel_table(values)
            n_single = sum(1 for r, why in ordered(values)[0] if why and is_single(r, why))
            parts = ['%d 点满足数值门槛' % n_ok]
            if n_review:
                parts.append('%d 点几遍读数相差超过 %g%%、取平均值待人工复核' % (n_review, MAX_SPREAD))
            if n_single:
                parts.append('%d 点只有一遍读出' % n_single)
            parts.append('%d 点不满足要求' % (n_bad - n_review - n_single))
            counts = '，'.join(parts) + '，均列于下表'
            md += ['**%s %s**（%s）' % (part_cn(t), panel_name(t, label), counts), '', table, '']
        md += ['*反读值不是原文给出的数值（入库数值门槛：一致性不低于 `%s`，离散度不超过 %g%%，'
               '或几遍最多只差纵轴满量程的 %g%%）。用于发表或入库前请核对关键值。*' % (MIN_CONF, MAX_SPREAD, FS_TOL), '']
    if not grouped:
        md += ['（这篇没有读出蛋白质功能特性和理化指标的数值。）', '']
    tail = appendix(model, targets, rows, accepted, rejected, readings, missing_images, failed, retry_failed)
    if tail:
        md += [tail]
    md += [DONE_MARK % input_digest(paper['root']), '']
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(md))


# =============================================================== API ==
class Api:
    """共享的 OpenAI 客户端和请求名额（所有文章、所有遍一起最多 workers 个请求同时进行）。
    base_url 是 OpenRouter 时（用户 2026-10-08：OpenAI 账户没钱，转 OpenRouter），每个请求带上 provider 只用列出的那几家
    （命令行默认 openai,google-ai-studio/flex,google-vertex/global/flex：gemini 走 Google 的 flex 档，价格一半；不切到 fast / Azure / Bedrock）。
    这里 base_url 不写就是 OpenAI 直连；命令行的默认（OpenRouter）在 main 里给。"""

    def __init__(self, model=MODEL, workers=API_WORKERS, client=None, key_env=KEY_ENV, base_url=None,
                 provider=OPENROUTER_PROVIDER):
        self.model = model
        self.base_url = base_url or None
        self.openrouter = 'openrouter.ai' in (base_url or '')
        # 几家用逗号隔开（用户 2026-10-09 起 openai,google-ai-studio，各模型只走自己那家；2026-10-14 起 gemini 走 flex 档）
        only = [p.strip() for p in (provider or '').split(',') if p.strip()]
        self.provider_extra = ({'extra_body': {'provider': {'only': only, 'allow_fallbacks': False,
                                                            'require_parameters': True}}} if only else {})
        self.extra = self.provider_extra if self.openrouter else {}
        self.slots = threading.BoundedSemaphore(workers)
        self.key_env = key_env
        self._client = client
        # 外面直接给了客户端（测试里的假客户端）：别的步骤也用它，不再用环境变量里的 key 另建真客户端（2026-10-13：初筛改走
        # OpenAI 直连后，测试里的初筛请求真发到了 OpenAI，测试结果随 luna 当次的判断变）
        self._injected = client is not None
        # OpenRouter 没钱后改走的 Google 官方 key（switch_to_gemini）；测试里的假客户端不切，要测切换时自己设
        self.gemini_key_env = None if self._injected else GEMINI_KEY_ENV
        self.gemini = False                  # 已经切到 Google 官方接口
        self._clients = {}                  # 初筛单独走别的接口 / key 时的客户端（{(key 环境变量, base_url): 客户端}）
        # 初筛单独走哪个接口（用户 2026-10-12：新 OpenRouter 账户每分钟只许 20 个 luna 请求，初筛改走 OpenAI 直连）：
        # None = 和 base_url 一样；'' = OpenAI 直连；其余是接口地址。prescreen_key_env：None = 和 key_env 一样
        self.prescreen_base_url = None
        self.prescreen_key_env = None
        self._lock = threading.Lock()
        self.stop = threading.Event()        # 没钱 / key 无效：这个窗口不再发请求、不再领新文章
        self.fatal = ''
        self.usage = {}                      # {分类 / 读图: 用量合计}，窗口结束时打印
        self.prescreen_model = None          # 初筛用的模型（--prescreen-model；None = 不初筛，每张都正式分类）
        self.classify_model = None           # 分类用的模型（--classify-model；None = 和读图同一个）
        self.classify_effort = None          # 分类时的推理强度（--classify-effort；None = 模型默认）
        self.classify_slim = False           # 分类回答瘦身（--classify-slim）
        self.sleep = time.sleep              # 被限流时等待（测试里换掉，不真等）
        self._limits_at = 0.0

    @staticmethod
    def _make_client(key_env, base_url):
        key = os.environ.get(key_env)
        if not key:
            raise SystemExit('没读到环境变量 %s（里面放 API key）。\n'
                             '  永久设置: setx %s "sk-..."  (之后要重开 PowerShell 窗口才生效)' % (key_env, key_env))
        from openai import OpenAI
        # Google 官方 flex 建议客户端至少等 10 分钟
        return OpenAI(api_key=key, base_url=base_url, max_retries=5, timeout=900 if base_url == GEMINI else 300)

    @property
    def client(self):
        """key 从环境变量 key_env 里取（用户 2026-10-02：几个 key 各开一个窗口跑，--key-env 指定用哪个）。"""
        with self._lock:
            if self._client is None:
                self._client = self._make_client(self.key_env, self.base_url)
            return self._client

    def route(self, stage):
        """这一步的 (key 环境变量, base_url, 是否经 OpenRouter)：初筛可以单独走（prescreen_base_url / prescreen_key_env）。"""
        if stage == '初筛' and (self.prescreen_base_url is not None or self.prescreen_key_env):
            base = self.base_url if self.prescreen_base_url is None else (self.prescreen_base_url or None)
            return self.prescreen_key_env or self.key_env, base, 'openrouter.ai' in (base or '')
        return self.key_env, self.base_url, self.openrouter

    def client_for(self, stage):
        key_env, base, _ = self.route(stage)
        if (key_env, base) == (self.key_env, self.base_url):
            return self.client
        with self._lock:
            if (key_env, base) not in self._clients:
                if self._injected:
                    return self._client
                self._clients[(key_env, base)] = self._make_client(key_env, base)
            return self._clients[(key_env, base)]

    def prescreen_where(self):
        """开头那行写的初筛走哪里：和别的步骤一样时不写。"""
        key_env, base, via = self.route('初筛')
        if (key_env, base) == (self.key_env, self.base_url):
            return ''
        return '（%s，key 取自 %s）' % ('OpenRouter' if via else base or 'OpenAI 直连', key_env)

    def switch_to_gemini(self, model, why):
        """OpenRouter 回了没钱：gemini 模型改走 Google 官方接口（GEMINI_TIER 档，key 取自 gemini_key_env），这个窗口以后都走它。
        返回 True = 这次请求换接口重发（别的请求先切过了也是 True）；False = 切不了（不是 gemini、没设 key），照旧停下。
        只在请求确实是经 OpenRouter 发出去时调：官方接口自己报没钱不会再来这里。"""
        with self._lock:
            if self.gemini:
                return True
            if not (self.openrouter and (model or '').startswith('google/') and self.gemini_key_env
                    and os.environ.get(self.gemini_key_env)):
                return False
            self.base_url, self.key_env, self.openrouter, self.extra = GEMINI, self.gemini_key_env, False, {}
            if not self._injected:
                self._client = None
            self.gemini = True
        with PRINT_LOCK:
            print('\n[切换] OpenRouter 的额度不够了（%s）：gemini 改走 Google 官方接口（%s 档，key 取自 %s），'
                  '没跑完的请求照常重发\n' % (why, GEMINI_TIER, self.key_env), flush=True)
        return True

    def where(self):
        if self.gemini:
            return 'Google 官方接口（%s 档）' % GEMINI_TIER
        only = self.extra['extra_body']['provider']['only'] if self.extra else []
        if only:
            return 'OpenRouter（只用 %s）' % (only[0] + ' 那一家' if len(only) == 1 else '、'.join(only))
        return 'OpenRouter' if self.openrouter else self.base_url or 'OpenAI 直连'

    def halt(self, message):
        """没钱 / key 无效：第一次碰到时在屏幕上写清楚原因，之后这个窗口里的请求都不再发出（用户 2026-10-08）。"""
        with self._lock:
            first = not self.stop.is_set()
            if first:
                self.fatal = message
                self.stop.set()
        if first:
            with PRINT_LOCK:
                print('\n%s\n窗口停下了：%s\n%s' % ('=' * 70, message, '=' * 70), flush=True)
        raise Fatal(self.fatal)

    def show_limits(self, headers):
        """每 10 分钟在窗口里显示一次这一分钟的限额还剩多少（取自 OpenAI 回复头；是限速，不是账户余额）。"""
        now = time.time()
        with self._lock:
            if now - self._limits_at < LIMITS_EVERY:
                return
            self._limits_at = now
        lt, lr = headers.get('x-ratelimit-limit-tokens'), headers.get('x-ratelimit-limit-requests')
        if lt or lr:
            with PRINT_LOCK:
                print('[限额] 这一分钟还剩 token %s / %s、请求 %s / %s（每分钟的限速，不是账户余额）'
                      % (headers.get('x-ratelimit-remaining-tokens'), lt,
                         headers.get('x-ratelimit-remaining-requests'), lr), flush=True)

    def parse(self, system, text, image, schema, stage='其他'):
        """一次结构化调用，返回 (解析结果, 用量)。用量 = {total, input, cached, output, reasoning, calls}，
        按 stage（分类 / 读图）累计在 self.usage 里（用户 2026-10-09：查清钱花在输入还是输出）。
        没钱、key 无效、没有模型权限 → Fatal，整个窗口停下；
        被限流 → 程序库自己的 5 次重试之后再按 OpenAI 给的时间等着重试，最多一共等 30 分钟，不让文章停在半路。"""
        name = (self.prescreen_model if stage == '初筛' and self.prescreen_model else
                self.classify_model if stage == '分类' and self.classify_model else self.model)
        waited = 0.0
        while True:
            if self.stop.is_set():
                raise Fatal(self.fatal)
            key_env, base, via_openrouter = self.route(stage)    # 每次重取：OpenRouter 没钱后会切到 Google 官方接口
            client = self.client_for(stage)
            model = name if via_openrouter else direct_model(name, base)   # 直连：openai/gpt-6-luna → gpt-6-luna
            kwargs = dict(model=model,
                          messages=[{'role': 'system', 'content': system},
                                    {'role': 'user', 'content': [
                                        {'type': 'text', 'text': text},
                                        {'type': 'image_url', 'image_url': {'url': image, 'detail': DETAIL}}]}],
                          response_format=schema, **(self.provider_extra if via_openrouter else {}))
            if stage == '分类' and self.classify_effort:
                kwargs['reasoning_effort'] = self.classify_effort
            if base == GEMINI:
                kwargs['service_tier'] = GEMINI_TIER
            try:
                with self.slots:
                    raw_api = getattr(client.chat.completions, 'with_raw_response', None)
                    if raw_api is not None:
                        raw = raw_api.parse(**kwargs)
                        r = raw.parse()
                        self.show_limits(raw.headers)
                    else:
                        r = client.chat.completions.parse(**kwargs)
                break
            except SystemExit:
                raise
            except Exception as e:
                kind = api_problem(e, gemini=base == GEMINI)
                # 经 OpenRouter 发的：没钱就切到 Google 官方接口重发；别的请求已经切过了（这次可能拿新客户端发了旧参数）也重发
                if via_openrouter and (self.gemini or kind == 'money' and self.switch_to_gemini(name, short_error(e))):
                    continue
                if kind in ('money', 'key', 'access'):
                    msg = FATAL_MESSAGES[kind + ('_openrouter' if via_openrouter and kind == 'money' else '')]
                    self.halt(msg % {'why': short_error(e), 'key': key_env, 'model': model})
                if kind not in ('rate', 'busy') or waited >= RATE_WAIT_MAX:
                    raise
                delay = retry_delay(e)
                with PRINT_LOCK:
                    what = ('限流', '被限流') if kind == 'rate' else ('服务器忙', '暂时没有可用的服务器')
                    print('[%s] %s（%s），等 %d 秒再试' % (what + (short_error(e), delay)), flush=True)
                self.sleep(delay)
                waited += delay
        use = usage_of(r)
        with self._lock:
            add_usage(self.usage.setdefault(stage, {}), use)
        parsed = r.choices[0].message.parsed
        if parsed is None:
            raise ValueError('模型没有返回可解析的结果（parsed 为 None）')
        return parsed, use


USAGE_KEYS = ('calls', 'input', 'cached', 'output', 'reasoning', 'total')


def usage_of(r):
    """回复里的用量：输入（其中缓存命中）、输出（其中思考）、合计。没有的项记 0。"""
    u = getattr(r, 'usage', None)

    def get(obj, name):
        try:
            return int(getattr(obj, name, 0) or 0) if obj is not None else 0
        except (TypeError, ValueError):
            return 0
    use = {'calls': 1, 'input': get(u, 'prompt_tokens'), 'output': get(u, 'completion_tokens'),
           'cached': get(getattr(u, 'prompt_tokens_details', None), 'cached_tokens'),
           'reasoning': get(getattr(u, 'completion_tokens_details', None), 'reasoning_tokens'),
           'total': get(u, 'total_tokens')}
    use['total'] = use['total'] or use['input'] + use['output']
    return use


def add_usage(acc, use):
    for k in USAGE_KEYS:
        acc[k] = acc.get(k, 0) + use.get(k, 0)


def usage_text(by_stage):
    """「分类 7 次：输入 52,301（缓存 24,780）、输出 13,020（思考 9,880）；读图 2 次：……」"""
    parts = []
    order = ('初筛', '分类', '读图')
    for stage in sorted(by_stage, key=lambda s: order.index(s) if s in order else 9):
        u = by_stage[stage]
        if not u.get('calls'):
            continue
        parts.append('%s %d 次：输入 %s（缓存 %s）、输出 %s（思考 %s）' % (
            stage, u['calls'], format(u.get('input', 0), ','), format(u.get('cached', 0), ','),
            format(u.get('output', 0), ','), format(u.get('reasoning', 0), ',')))
    return '；'.join(parts)


class Fatal(SystemExit):
    """整个窗口都该停下的错误：账户没钱、key 无效、没有模型权限（用户 2026-10-08）。继承 SystemExit：分类、读图、
    每篇外面的 except SystemExit: raise 原样往外抛，不会被记成这张图失败、也不会接着做下一篇。"""


MONEY_HINTS = ('insufficient_quota', 'no credits remaining', 'exceeded your current quota', 'billing_hard_limit',
               'insufficient credits', 'requires more credits')
# OpenRouter 的 403 也可能只是这一张图被内容审核 / 防护规则拦了（不是整个窗口的问题）
BLOCKED_HINTS = ('moderation', 'flagged', 'guardrail', 'request blocked')
FATAL_MESSAGES = {
    'money': ('OpenAI 账户没钱了（%(why)s）。\n充值后双击同一个 bat 接着做：已经拿到的分类和读图结果都在断点里，不会重花钱。\n'
              '充值：https://platform.openai.com/settings/organization/billing/'),
    'money_openrouter': ('OpenRouter 的额度不够了（%(why)s）。\n充值后双击同一个 bat 接着做：已经拿到的分类和读图结果都在断点里，'
                         '不会重花钱。\n充值：https://openrouter.ai/settings/credits'
                         '（给这个 key 设过额度上限的话，也可能是上限到了：https://openrouter.ai/settings/keys）'),
    'key': ('API key 无效或已被删除（%(why)s）。\n换好 key（PowerShell 里 setx %(key)s "新key"，然后重开窗口）后'
            '双击同一个 bat 接着做。'),
    'access': ('这个 key 用不了模型 %(model)s（%(why)s）。\n去 OpenAI 网站看这个项目的模型权限，改好后双击同一个 bat 接着做。'),
}
RATE_WAIT_MAX = 30 * 60       # 被限流时自己再等，最多一共等 30 分钟；还不行这篇照旧先停下
LIMITS_EVERY = 10 * 60        # 每 10 分钟显示一次每分钟限额还剩多少


def api_problem(e, gemini=False):
    """money 没钱 / key key 无效 / access 没有模型权限 → 整个窗口停下；rate 限流 / busy 暂时没有可用的服务器 → 等着重试；
    None 其他错误（照旧这篇先停下）。OpenRouter：402 没钱、502 模型挂了、503 没有符合要求的提供方。
    gemini = 请求发给了 Google 官方接口：它每分钟限额到了的 429 也写「You exceeded your current quota」，算限流不算没钱。"""
    status = getattr(e, 'status_code', None)
    if gemini and status == 429:
        return 'rate'
    text = ' '.join(str(x) for x in (getattr(e, 'code', None), getattr(e, 'type', None), e) if x).lower()
    # OpenRouter 每个请求先按最多可能输出的量冻结一笔钱（gpt-6-astra 约 $6.4）：余额少时同时在路上的请求一多，后来的就报 402
    # 「would exceed your available credits given your current in-flight requests」——等前面的跑完再试，不是没钱（2026-10-08）
    if status == 402 and ('in-flight' in text or 'in flight' in text):
        return 'busy'
    if status == 402 or any(h in text for h in MONEY_HINTS):
        return 'money'
    if status == 401 or 'invalid_api_key' in text:
        return 'key'
    if status == 403 and any(h in text for h in BLOCKED_HINTS):
        return None
    if status in (403, 404):
        return 'access'
    if status == 429:
        return 'rate'
    if status in (502, 503):
        return 'busy'
    return None


def short_error(e):
    return ' '.join(str(getattr(e, 'message', None) or e).split())[:160]


def retry_delay(e):
    """OpenAI 回复头里让等多久（retry-after-ms / retry-after），没给就等 30 秒；限在 5 到 300 秒之间。"""
    headers = getattr(getattr(e, 'response', None), 'headers', None) or {}
    for name, scale in (('retry-after-ms', 0.001), ('retry-after', 1.0)):
        try:
            return int(min(300, max(5, float(headers.get(name)) * scale)))
        except (TypeError, ValueError):
            pass
    return 30


# =============================================================== 每篇的处理 ==
PRINT_LOCK = threading.Lock()


def say(paper, text):
    with PRINT_LOCK:
        print('[%s] %s' % (paper['name'], text), flush=True)


class Store:
    """断点文件夹里的 jsonl：每条记录一行，同一 key 以最后一行为准；失败也写，重跑时只重做失败或输入变了的。"""

    def __init__(self, work):
        self.work = work
        self.lock = threading.Lock()

    def load(self, name):
        path = os.path.join(self.work, name + '.jsonl')
        out = {}
        if os.path.exists(path):
            with open(path, encoding='utf-8') as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                        out[r['key']] = r
                    except (ValueError, KeyError):
                        pass
        return out

    def add(self, name, rec):
        with self.lock:
            os.makedirs(self.work, exist_ok=True)
            with open(os.path.join(self.work, name + '.jsonl'), 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + '\n')


NO_MENTIONS = '（未取到）'     # 不读全文，分类提示里「正文里提到这张图的地方」一栏照流水线取不到时的写法填


def classify_text(item):
    """分类时 user 消息里的文字：文章标题、全篇所有图注、这张图的图注（或表题表注），正文引用一栏填（未取到）。
    文章标题（figure_markdown.md 第一行）是用户 2026-10-05 加的：图注常常只写载体名、不写里面包的蛋白质
    （afres.2026.102059 图 5：只写 alginate nanogels，标题才说是 phycocyanin encapsulation）。
    全篇图注是用户 2026-10-06 加的：缩写、样品名常常只在某一张图的图注里写了全称。"""
    caption = item['caption'] or NO_MENTIONS
    title = item.get('paper_title') or NO_MENTIONS
    captions = item.get('paper_captions') or NO_MENTIONS
    if item['kind'] == 'table':
        return TABLE_USER.format(n=item['label'], title=title, captions=captions, caption=caption,
                                 mentions=NO_MENTIONS)
    return USER.format(title=title, captions=captions, caption=caption, mentions=NO_MENTIONS)


def model_key(model):
    """断点指纹里的模型名：经 OpenRouter 的 openai/gpt-6-astra 和直连的 gpt-6-astra 是同一个模型，断点照用。"""
    return model[len('openai/'):] if (model or '').startswith('openai/') else model


def direct_model(model, base_url):
    """直连时发给接口的模型名：OpenAI 直连 openai/gpt-6-luna → gpt-6-luna，Google 官方接口 google/gemini-3.8-flash →
    gemini-3.8-flash。断点指纹、回答缓存照旧用 model_key / 原名，切到官方接口后已有的都照用、不重花钱。"""
    if base_url == GEMINI and (model or '').startswith('google/'):
        return model[len('google/'):]
    return model_key(model)


def classify_spec(api, item):
    """(系统提示, schema)：表格用表格的；图在 --classify-slim 时用瘦身版。"""
    if item['kind'] == 'table':
        return TABLE_SYSTEM, TableClass
    if getattr(api, 'classify_slim', False):
        return SYSTEM + SLIM_RULE, FigureClassSlim
    return SYSTEM, FigureClass


def classify_fingerprint(api, item, digest):
    system, schema = classify_spec(api, item)
    ctx = {'stage': 'classify', 'model': model_key(getattr(api, 'classify_model', None) or api.model),
           'max_side': MAX_SIDE, 'system': system,
           'schema': schema.model_json_schema(), 'text': classify_text(item)}
    if getattr(api, 'classify_effort', None):         # 不设时指纹和原来一样，断点照用
        ctx['effort'] = api.classify_effort
    return fingerprint(ctx, digest)


def prescreen_fingerprint(api, item, digest):
    return fingerprint({'stage': 'prescreen', 'model': model_key(api.prescreen_model), 'max_side': MAX_SIDE,
                        'system': SCREEN_SYSTEM, 'schema': Screen.model_json_schema(), 'text': screen_text(item)},
                       digest)


def read_fingerprint(api, t, digest):
    return fingerprint({'stage': 'read', 'model': model_key(api.model), 'max_side': MAX_SIDE, 'system': SYSTEM_PROMPT,
                        'schema': Extraction.model_json_schema(), 'instruction': panel_instruction(t)}, digest)


def write_atomic(path, text):
    fd, tmp = tempfile.mkstemp(prefix='.fr-', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _checkpoints_named(name):
    """断点文件夹里这篇文章（文章文件夹名 name）现有的断点文件夹。每次现列：不按修改时间缓存（Windows 上接连新建的
    文件夹，断点文件夹的修改时间可能不变，缓存会过期）。"""
    try:
        entries = os.listdir(CHECKPOINT_DIR)
    except OSError:
        return []
    pre = name + '_'
    return [os.path.join(CHECKPOINT_DIR, n) for n in entries
            if n.startswith(pre) and re.fullmatch(r'[0-9a-f]{8}', n[len(pre):])
            and os.path.isdir(os.path.join(CHECKPOINT_DIR, n))]


def work_dir(root):
    """这篇的断点文件夹：脚本旁边的 断点\\<文章文件夹名>_<路径指纹>（不同上级目录里同名的文章不会混用）。
    文章换了位置（用户 2026-10-21 把 ACS 整理进 D:\\acs_papers_done\\papers；10-15 Elsevier 挪到 D 盘时是手动改的名），
    路径指纹跟着变：这个路径下还没有断点、断点里正好有一个同名文章的断点时，就接着用它。断点里每条记录都带输入指纹，
    图或图注变了的照旧重做，不会用错。"""
    root = os.path.abspath(root)
    name = os.path.basename(os.path.normpath(root))
    tag = hashlib.sha256(os.path.normcase(root).encode('utf-8')).hexdigest()[:8]
    exact = os.path.join(CHECKPOINT_DIR, '%s_%s' % (name, tag))
    if os.path.isdir(exact) or os.path.exists(exact + '.lock'):
        return exact
    moved = _checkpoints_named(name)
    return moved[0] if len(moved) == 1 else exact


def drop_work(root):
    shutil.rmtree(work_dir(root), ignore_errors=True)
    try:
        os.rmdir(CHECKPOINT_DIR)          # 没有别的断点了就把 断点 文件夹也删掉
    except OSError:
        pass


# ---------------------------------------------------------------- 多个窗口同时跑 --
# 用户 2026-10-02：「可以打开多个powershell窗口运行这个命令加快速度吗」。每个窗口处理一篇之前先「领取」：在 断点\ 里
# 建一个 <文章>.lock（原子创建，谁先建成谁处理），别的窗口看到就跳过这篇，所以同一篇不会被两个窗口重复花钱。
# 处理期间每分钟刷新一次锁文件的时间；窗口被关、程序崩了，锁的主人进程不在了（或锁超过 15 分钟没刷新），别的窗口可以接手。
LOCK_STALE = 15 * 60
LOCK_BEAT = 60


def pid_alive(pid):
    """这台机器上这个进程还在不在。Windows 上不能用 os.kill(pid, 0)：它会直接结束那个进程。"""
    if pid == os.getpid():
        return True
    if os.name == 'nt':
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, int(pid))            # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return k32.GetLastError() == 5                       # 拒绝访问：进程在，只是不让看
        code = ctypes.c_ulong()
        try:
            return bool(k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259   # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class Claims:
    """这个进程领取的文章（断点\\<文章>.lock）。"""

    def __init__(self):
        import socket
        self.host = socket.gethostname()
        self.held = set()
        self.lock = threading.Lock()
        threading.Thread(target=self._beat, daemon=True).start()

    @staticmethod
    def path(root):
        return work_dir(root) + '.lock'

    def _mine(self):
        return json.dumps({'pid': os.getpid(), 'host': self.host, 'id': id(self), 'since': time.time()})

    def _stale(self, path):
        try:
            age = time.time() - os.path.getmtime(path)
            with open(path, encoding='utf-8') as fh:
                info = json.loads(fh.read() or '{}')
        except (OSError, ValueError):
            return True
        if age > LOCK_STALE:
            return True
        return info.get('host') == self.host and not pid_alive(info.get('pid', -1))

    def take(self, root):
        """领到了返回 True；另一个窗口正在处理返回 False。"""
        path, mine = self.path(root), self._mine()
        for _ in range(3):
            try:
                os.makedirs(CHECKPOINT_DIR, exist_ok=True)
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if not self._stale(path):
                    return False
                # 旧锁的主人不在了：写进自己的，稍等再读回来，最后写进去的那个窗口才算领到（两个窗口同时接手时只留一个）
                tmp = '%s.%d.tmp' % (path, os.getpid())
                try:
                    with open(tmp, 'w', encoding='utf-8') as fh:
                        fh.write(mine)
                    os.replace(tmp, path)
                except PermissionError:        # 另一个窗口这一刻正开着/删着这个锁（见下面 PermissionError 的说明）→ 当它在处理，这篇这次跳过
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
                    return False
                time.sleep(0.5)
                try:
                    with open(path, encoding='utf-8') as fh:
                        got = fh.read()
                except OSError:
                    got = ''
                if got != mine:
                    return False
                break
            except FileNotFoundError:          # 另一个窗口刚好把空的 断点 文件夹删了：重建再试
                continue
            except PermissionError:
                # 2026-11-09 夜 30 个读图窗口时崩过 4 个窗口：Windows 上另一个窗口刚删掉这个锁（还在「删除中」）或正开着它时，
                # 新建会报拒绝访问而不是 FileExistsError。稍等再试；三次都这样就当另一个窗口在处理，这篇这次跳过（之后照常再领）
                time.sleep(0.3)
                continue
            else:
                with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                    fh.write(mine)
                break
        else:
            return False
        with self.lock:
            self.held.add(path)
        return True

    def release(self, root):
        path = self.path(root)
        with self.lock:
            self.held.discard(path)
        try:
            os.remove(path)
        except OSError:
            pass
        try:
            os.rmdir(CHECKPOINT_DIR)
        except OSError:
            pass

    def release_all(self):
        with self.lock:
            held = list(self.held)
            self.held.clear()
        for path in held:
            try:
                os.remove(path)
            except OSError:
                pass

    def busy(self, root):
        """另一个还活着的窗口正领着这篇。"""
        path = self.path(root)
        return os.path.exists(path) and path not in self.held and not self._stale(path)

    def _beat(self):
        while True:
            time.sleep(LOCK_BEAT)
            with self.lock:
                held = list(self.held)
            for path in held:
                try:
                    os.utime(path)
                except OSError:
                    pass


def is_done(root):
    """结果文件写完了，而且之后 figure_markdown.md 没变过（用抓取脚本 --refresh 重抓过的要重做）。"""
    path = os.path.join(root, MD_NAME)
    if not os.path.isfile(path):
        return False
    with open(path, encoding='utf-8') as fh:
        return (DONE_MARK % input_digest(root)) in fh.read()


def no_json(root):
    """老脚本读过（有 反读数据.md）、还没有 反读数据.json 的。"""
    return os.path.isfile(os.path.join(root, MD_NAME)) and not os.path.isfile(os.path.join(root, DB_NAME))


def plan_items(paper):
    """(送分类的图表, 排除的 {标题: 原因}, 图片缺失的标题, 不处理的标题)。"""
    send, excluded, missing, other = [], {}, [], []
    for it in paper['items']:
        if it['kind'] not in ('figure', 'table'):
            reason = {'graphical_abstract': '图文摘要', 'scheme': 'Scheme 不送读'}.get(it['kind'])
            if reason:
                excluded[it['heading']] = reason
            else:
                other.append(it['heading'])
            continue
        why = exclusion_reason(it['caption'], it['kind']) if it['kind'] == 'figure' else ''
        if why:
            excluded[it['heading']] = why
            continue
        paths = image_paths(paper, it)
        if not it['files'] or it['failed'] or not all(os.path.isfile(p) for p in paths):
            missing.append('%s（%s）' % (it['heading'], '、'.join(it['files']) or '图片下载失败'))
            continue
        send.append(it)
    return send, excluded, missing, other


def process_paper(paper, api, runs=RUNS, escalate=ESCALATE):
    """一篇：分类 → 两遍读图 → 必要时第三遍 → 合并 → 写 反读数据.md → 删断点。返回 True 表示整篇完成。"""
    root = paper['root']
    store = Store(work_dir(root))
    send, excluded, missing, other = plan_items(paper)
    say(paper, '送分类 %d 张%s%s%s' % (
        len(send),
        '；不读 %s' % '、'.join('%s（%s）' % kv for kv in excluded.items()) if excluded else '',
        '；图片缺失 %s' % '、'.join(missing) if missing else '',
        '；不处理 %s' % '、'.join(other) if other else ''))
    images, digests = {}, {}
    img_lock = threading.Lock()

    def image_of(it):
        with img_lock:
            if it['key'] not in images:
                paths = image_paths(paper, it)
                images[it['key']] = data_url(paths)
            return images[it['key']]

    for it in send:
        digests[it['key']] = image_digest(image_paths(paper, it))
    tokens = [0]
    tok_lock = threading.Lock()
    paper_usage = {}

    def add_tokens(stage, use):
        with tok_lock:
            tokens[0] += use['total']
            add_usage(paper_usage.setdefault(stage, {}), use)

    # ---- 初筛（--prescreen-model，用户 2026-10-09）：便宜模型只问有没有可能是 17 项之一，判成没有的不做正式分类。
    # 初筛这一步出错的图不跳过、照样正式分类（宁可多花一次分类，也不漏）。
    if getattr(api, 'prescreen_model', None) and send:
        shot = store.load('prescreen')
        ssig = {it['key']: prescreen_fingerprint(api, it, digests[it['key']]) for it in send}

        def screen_one(it):
            try:
                parsed, use = api.parse(SCREEN_SYSTEM, screen_text(it), image_of(it), Screen, stage='初筛')
                add_tokens('初筛', use)
                rec = {'key': it['key'], 'ok': True, 'hits': screen_hits(parsed), 'tokens': use['total'],
                       'usage': use}
            except SystemExit:
                raise
            except Exception as e:
                rec = {'key': it['key'], 'ok': False, 'error': '%s: %s' % (type(e).__name__, e)}
            rec.update(fingerprint=ssig[it['key']], model=api.prescreen_model)
            store.add('prescreen', rec)
            return rec

        todo = [it for it in send if not shot.get(it['key'], {}).get('ok')
                or shot[it['key']].get('fingerprint') != ssig[it['key']]]
        with futures.ThreadPoolExecutor(max_workers=max(1, len(todo))) as pool:
            for rec in pool.map(screen_one, todo):
                shot[rec['key']] = rec
        for it in send:
            if not shot[it['key']].get('ok'):
                say(paper, '初筛出错 %s（照样正式分类）：%s' % (it['heading'], shot[it['key']].get('error', '')[:200]))
        screened = [it for it in send if shot[it['key']].get('ok') and not shot[it['key']]['hits']]
        out = {it['key'] for it in screened}
        send = [it for it in send if it['key'] not in out]
        say(paper, '初筛：%d 张可能有 17 项指标、送正式分类；%d 张判成没有，不分类%s' % (
            len(send), len(screened), '（%s）' % '、'.join(it['heading'] for it in screened) if screened else ''))

    # ---- 分类
    done = store.load('classify')
    sigs = {it['key']: classify_fingerprint(api, it, digests[it['key']]) for it in send}

    def classify_one(it):
        text = classify_text(it)
        system, schema = classify_spec(api, it)
        try:
            parsed, use = api.parse(system, text, image_of(it), schema, stage='分类')
            if it['kind'] == 'table' and not parsed.measures:
                raise ValueError('零产出：measures 为空')
            if it['kind'] != 'table' and not parsed.panels:
                raise ValueError('零产出：panels 为空')
            add_tokens('分类', use)
            rec = {'key': it['key'], 'ok': True, 'tokens': use['total'], 'usage': use, 'data': parsed.model_dump()}
        except SystemExit:
            raise
        except Exception as e:
            rec = {'key': it['key'], 'ok': False, 'error': '%s: %s' % (type(e).__name__, e)}
        rec.update(fingerprint=sigs[it['key']], model=api.classify_model or api.model)
        store.add('classify', rec)
        return rec

    todo = [it for it in send if not done.get(it['key'], {}).get('ok')
            or done[it['key']].get('fingerprint') != sigs[it['key']]]
    with futures.ThreadPoolExecutor(max_workers=max(1, len(todo))) as pool:
        for rec in pool.map(classify_one, todo):
            done[rec['key']] = rec
    failed = [it['heading'] for it in send if not done[it['key']].get('ok')]
    if failed:
        for it in send:
            if not done[it['key']].get('ok'):
                say(paper, '分类失败 %s：%s' % (it['heading'], done[it['key']].get('error', '')[:200]))
        say(paper, '有 %d 张分类失败，这篇先停下；重跑同一条命令会接着做' % len(failed))
        return False

    targets = []
    for it in send:
        t = (table_target if it['kind'] == 'table' else figure_target)(it, done[it['key']])
        if t['kind'] == 'figure':
            t['ref_captions'] = referenced_captions(t.get('caption'), paper['items'], t['label'])
        if t['excluded']:
            excluded[it['heading']] = t['excluded']
            continue
        targets.append(t)
        mark = '送读 %s' % '、'.join(str(p or '整图') for p in t['read_panels']) if t['read_panels'] else '不读'
        say(paper, '  %-10s %s%s' % (it['heading'], mark,
                                     '；功能特性子图没读 %s' % '、'.join('%s（%s）' % (u['panel'], u['reason'])
                                                                for u in t['functional_unread'])
                                     if t['functional_unread'] else ''))
    readable = {t['key']: t for t in targets if t['read_panels']}

    # ---- 读图：先两遍独立读，再按分歧补第三遍
    by_key = {it['key']: it for it in send}

    def salvaged(run, t, rec):
        """放弃的这一遍只丢没过自检的子图（salvage，用户 2026-10-19），丢了哪些写进日志。"""
        out = salvage(t, rec)
        if out is not rec:
            say(paper, '%s 第 %s 遍同样的输入连续 %d 次没通过自检：只丢子图 %s，其余子图照常用'
                % (t['heading'], run[3:], READ_TRIES,
                   '；'.join('%s（%s）' % (k or '未标注', why) for k, why in out['salvaged'].items())[:300]))
        return out

    def read_one(run, t, prev):
        """读一遍。自检没过当场用同样的输入再读一次；同样的输入累计 READ_TRIES 次没过（中断后重跑也接着数），
        这一遍就放弃（gave_up），不再花钱（用户 2026-10-06）。网络或接口报错（error）不算次数，照旧整篇先停。"""
        sig = read_fingerprint(api, t, digests[t['key']])
        fails = 0
        if prev.get('fingerprint') == sig:
            # 这个改动之前的断点没记次数：自检没过的那条算一次
            fails = prev.get('fails', 1 if prev.get('raw') is not None and not prev.get('ok') else 0)
            if prev.get('raw') is not None:
                # 同样的输入读过：用存下的模型原始输出按现在的规则重算，自检规则改了也不用重花 API；仍不过才重读
                again = dict(prev, **check_reading(t, json.loads(json.dumps(prev['raw']))))
                if again['ok']:
                    return again
                if fails >= READ_TRIES:
                    return salvaged(run, t, dict(again, gave_up=True))
            elif prev.get('ok'):
                return prev
        while True:
            try:
                parsed, use = api.parse(SYSTEM_PROMPT, panel_instruction(t), image_of(by_key[t['key']]), Extraction,
                                        stage='读图')
                add_tokens('读图', use)
                raw = parsed.model_dump()
                rec = dict(check_reading(t, json.loads(json.dumps(raw))), raw=raw, tokens=use['total'], usage=use)
            except SystemExit:
                raise
            except Exception as e:
                rec = {'ok': False, 'error': '%s: %s' % (type(e).__name__, e)}
            if not rec['ok'] and 'raw' in rec:
                fails += 1
                if fails >= READ_TRIES:
                    rec['gave_up'] = True
            rec.update(key=t['key'], run=run, fingerprint=sig, model=api.model, fails=fails)
            rec = salvaged(run, t, rec)
            store.add(run, rec)
            if rec['ok'] or 'error' in rec or rec.get('gave_up'):
                return rec
            say(paper, '%s 第 %s 遍自检没过（%s），用同样的输入当场再读一次'
                % (t['heading'], run[3:], '；'.join(dict.fromkeys(rec['blocking_flags']))[:200]))

    def read_runs(jobs):
        """jobs：[(遍名, 读图目标)]；返回 {遍名: {图 key: 记录}}。"""
        cache = {run: store.load(run) for run in {r for r, _ in jobs}}
        out = {run: {} for run in cache}
        with futures.ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
            got = list(pool.map(lambda j: read_one(j[0], j[1], cache[j[0]].get(j[1]['key'], {})), jobs))
        for (run, t), rec in zip(jobs, got):
            out[run][t['key']] = rec
        return out

    names = ['run%d' % i for i in range(1, runs + 1)]
    results = read_runs([(run, t) for run in names for t in readable.values()]) if readable else {}
    bad = [(run, k, r) for run in results for k, r in results[run].items() if not r.get('ok')]
    for run, k, r in bad:
        say(paper, '读图失败 %s 第 %s 遍：%s' % (readable[k]['heading'], run[3:],
                                            (r.get('error') or '；'.join(r.get('blocking_flags') or []))[:200]))
    stop = [b for b in bad if not b[2].get('gave_up')]
    if stop:
        say(paper, '有 %d 次读图失败，这篇先停下；重跑同一条命令只重读失败的' % len(stop))
        return False
    # 同样的输入连续两次没通过自检的图：记为读图失败，不再重读，不进合并；其余照常完成（用户 2026-10-06）
    failed = {}
    for run, k, r in bad:
        failed.setdefault(k, []).extend(r.get('blocking_flags') or [])
    failed = {k: '；'.join(dict.fromkeys(v))[:200] for k, v in failed.items()}
    for k in failed:
        say(paper, '%s 同样的输入连续 %d 次没通过自检，不再重读，记为读图失败' % (readable[k]['heading'], READ_TRIES))
    readable = {k: t for k, t in readable.items() if k not in failed}
    run_list = [(run, results.get(run, {})) for run in names]
    retry_failed = {}
    # 每一遍都只能丢掉的子图（salvage）：第三遍再读也是一样，不补（用户 2026-10-19）
    dead = {}
    for k in readable:
        sets = [set((results.get(run, {}).get(k) or {}).get('salvaged') or ()) for run in names]
        common = set.intersection(*sets) if sets else set()
        if common:
            dead[k] = common
    if readable and escalate > 0:
        plan = retry_plan({k: dict(t, read_panels=[p for p in t['read_panels']
                                                   if (panel_key(p, t['case']) or '') not in dead.get(k, ())])
                           for k, t in readable.items()}, run_list, escalate)
        if plan:
            third = 'run%d' % (runs + 1)
            # 第三遍沿用前两遍一致的名称（只给名字、不给读数，用户 2026-10-12）
            jobs = [(third, narrowed(dict(readable[k], names=agreed_names(readable[k], [results[run].get(k) for run in names])),
                                     None if sel is None else set(sel))) for k, sel in plan.items()]
            say(paper, '两遍有分歧或缺失，补读第 %d 遍：%s' % (runs + 1, '；'.join(
                '%s %s' % (readable[k]['heading'], '整图' if sel is None else '、'.join(s or '未标注' for s in sel))
                for k, sel in plan.items())))
            extra = read_runs(jobs)[third]
            bad = [(k, r) for k, r in extra.items() if not r.get('ok')]
            for k, r in bad:
                say(paper, '第 %d 遍读图失败 %s：%s' % (runs + 1, readable[k]['heading'],
                                                    (r.get('error') or '；'.join(r.get('blocking_flags') or []))[:200]))
            if any(not r.get('gave_up') for _, r in bad):
                return False
            for k, r in bad:          # 第三遍同样的输入连续两次没过：不再重读，按前两遍合并
                retry_failed[k] = '；'.join(dict.fromkeys(r.get('blocking_flags') or []))[:200]
                say(paper, '%s 第 %d 遍补读同样的输入连续 %d 次没通过自检，不再重读，按前两遍的结果合并'
                    % (readable[k]['heading'], runs + 1, READ_TRIES))
            run_list.append((third, {k: r for k, r in extra.items() if r.get('ok')}))
    rows = merge(readable, run_list) if readable else []

    # ---- 输出
    readings = [records for _, records in run_list[:runs]] if (readable or failed) else []
    write_atomic(os.path.join(root, DB_NAME),
                 json.dumps(db_info(paper, api, targets, rows, run_list, failed), ensure_ascii=False, indent=1) + '\n')
    write_atomic(os.path.join(root, MD_NAME),
                 render(paper, targets, rows, readings, model_note(api), missing, failed, retry_failed))
    drop_work(root)
    accepted, rejected = select_rows(rows)
    n_review = sum(1 for _, why in rejected if is_deviation(why))
    n_single = sum(1 for row, why in rejected if is_single(row, why))
    sub = (['%d 点读数相差超过 %g%%、需人工复核' % (n_review, MAX_SPREAD)] if n_review else []) + \
          (['%d 点只有一遍读出' % n_single] if n_single else [])
    say(paper, '完成：%d 点通过、%d 点不满足要求%s%s；本次用了 %d token → %s'
        % (len(accepted), len(rejected), '（其中 %s）' % '、'.join(sub) if sub else '',
           '，%d 张读图失败' % len(failed) if failed else '', tokens[0], os.path.join(root, MD_NAME)))
    if paper_usage:
        say(paper, '用量：' + usage_text(paper_usage))
    return True


# =============================================================== 命令行 ==
def find_papers(paths):
    """文章文件夹：给的可以是文章文件夹本身、放文章文件夹的上级目录（<根>\\<文章>，如 D:\\2.elsevier_papers），
    或整理过的总文件夹（<根>\\papers\\<文章>，如 D:\\acs_papers_done；用户 2026-10-21）。旁边的 _records、database
    里没有 figure\\figure_markdown.md，不当文章。"""
    roots = []
    for p in paths or DEFAULT_ROOTS:
        p = os.path.abspath(p)
        if os.path.isfile(os.path.join(p, FIGURE_DIR, 'figure_markdown.md')):
            roots.append(p)
        elif os.path.isdir(p):
            for base in (p, os.path.join(p, PAPERS_SUBDIR)):
                if not os.path.isdir(base):
                    continue
                for name in sorted(os.listdir(base)):
                    sub = os.path.join(base, name)
                    if os.path.isfile(os.path.join(sub, FIGURE_DIR, 'figure_markdown.md')):
                        roots.append(sub)
        else:
            print('找不到：%s' % p)
    return list(dict.fromkeys(roots))


def status(roots):
    claims = Claims()
    done = started = running = 0
    for root in roots:
        if is_done(root):
            done += 1
        elif claims.busy(root):
            running += 1
            print('  正在处理（某个窗口领着）：%s' % root)
        elif os.path.isdir(work_dir(root)):
            started += 1
            print('  未完成（有断点）：%s' % root)
    print('共 %d 篇：完成 %d，正在处理 %d，有断点 %d，未开始 %d'
          % (len(roots), done, running, started, len(roots) - done - running - started))


def dry_run(roots, api):
    calls = 0
    for root in roots:
        paper = load_paper(root)
        send, excluded, missing, other = plan_items(paper)
        done = '（已完成，跳过）' if is_done(root) else ''
        if getattr(api, 'prescreen_model', None):       # 先初筛：要新做的是初筛调用，判成有的才再分类
            cached = Store(work_dir(root)).load('prescreen')
            new = [it for it in send if not cached.get(it['key'], {}).get('ok') or cached[it['key']].get('fingerprint')
                   != prescreen_fingerprint(api, it, image_digest(image_paths(paper, it)))]
        else:
            cached = Store(work_dir(root)).load('classify')
            new = [it for it in send if not cached.get(it['key'], {}).get('ok') or cached[it['key']].get('fingerprint')
                   != classify_fingerprint(api, it, image_digest(image_paths(paper, it)))]
        if not done:
            calls += len(new)
        print('%s %s' % (paper['name'], done))
        print('  送分类：%s' % ('、'.join(it['heading'] for it in send) or '无'))
        if excluded:
            print('  不读：%s' % '、'.join('%s（%s）' % kv for kv in excluded.items()))
        if missing:
            print('  图片缺失：%s' % '、'.join(missing))
        if other:
            print('  不处理：%s' % '、'.join(other))
    if getattr(api, 'prescreen_model', None):
        print('\n合计要新做的初筛调用 %d 次（初筛判成有的才正式分类，约四分之一；读图要等分类后才知道：每张要读的图至少 2 次）；'
              '没有调用 API。' % calls)
    else:
        print('\n合计要新做的分类调用 %d 次（读图调用要等分类后才知道：每张要读的图至少 2 次）；没有调用 API。' % calls)


def parse_slot(text):
    """「K/N」→ (K, N)，1 ≤ K ≤ N。"""
    m = re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*', text or '')
    if not m or not 1 <= int(m.group(1)) <= int(m.group(2)):
        raise ValueError('--slot 要写成 K/N（1 ≤ K ≤ N），例如 2/5，现在是「%s」' % text)
    return int(m.group(1)), int(m.group(2))


def rotate(todo, slot):
    """(轮转后的待做列表, 起点下标)。同时开 N 个窗口时第 K 个从 (K-1)/N 处开始、到末尾再从头接着
    （用户 2026-10-08：五个窗口互不打扰）。每个窗口最终都走遍全部，少开几个窗口也不会漏。"""
    k, n = slot
    i = (k - 1) * len(todo) // n
    return todo[i:] + todo[:i], i


def started_first(todo, slot=None):
    """(待做列表, 起点下标, 有断点的篇数)。用户 2026-10-21「脚本优先有跑断点的文章」：停在断点的文章（分类、读图已经
    花过钱的）先接着做完，再开没开始的；开几个窗口（slot）时，两段各自按窗口错开起点（rotate）。起点下标是没开始的那段的
    （全都有断点时是有断点那段的）。"""
    begun = {r for r in todo if os.path.isdir(work_dir(r))}
    started = [r for r in todo if r in begun]
    fresh = [r for r in todo if r not in begun]
    first = 0
    if slot:
        started, i = rotate(started, slot)
        fresh, first = rotate(fresh, slot)
        if not fresh:
            first = i
    return started + fresh, first, len(started)


def main(argv=None):
    ap = argparse.ArgumentParser(description='论文图片和图片版表格的蛋白质功能特性数据反读'
                                             '（默认经 OpenRouter：%s 初筛 → %s 分类、读图）' % (PRESCREEN_MODEL, MODEL))
    ap.add_argument('papers', nargs='*', help='文章文件夹，或放文章文件夹的上级目录；默认 %s' % '、'.join(DEFAULT_ROOTS))
    ap.add_argument('--model', default=MODEL, help='正式分类和读图用的模型（默认 %s）' % MODEL)
    ap.add_argument('--api-workers', type=int, default=API_WORKERS, help='同时进行的 API 请求上限（默认 4）')
    ap.add_argument('--paper-workers', type=int, default=PAPER_WORKERS, help='同时处理几篇（默认 3）')
    ap.add_argument('--refresh', action='store_true', help='已经完成的也重做（会重新调用 API）')
    ap.add_argument('--limit', type=int, default=0, help='这次最多处理几篇（0 = 不限）')
    ap.add_argument('--only-started', action='store_true',
                    help='只做有断点、还没做完的文章，不开始新的（用户 2026-10-08：把断点的跑完，别跑新的）')
    ap.add_argument('--redo-no-json', action='store_true',
                    help='只重读有 %s、没有 %s 的文章（老脚本读的，用户 2026-10-12：补上 json），别的不碰' % (MD_NAME, DB_NAME))
    ap.add_argument('--dry-run', action='store_true', help='只列出要处理的图，不调用 API')
    ap.add_argument('--status', action='store_true', help='只看进度')
    ap.add_argument('--log', action='store_true', help='屏幕上的输出同时存一份到 %s' % LOG_DIR)
    ap.add_argument('--key-env', default=KEY_ENV,
                    help='从哪个环境变量取 API key（默认 %s）；几个 key 各开一个窗口，例如 --key-env %s_2' % (KEY_ENV, KEY_ENV))
    ap.add_argument('--base-url', default=BASE_URL,
                    help='接口地址（默认 OpenRouter %s）；写 openai 就是 OpenAI 直连（同时 --model gpt-6-astra、'
                         '--key-env OPENAI_API_KEY、--prescreen-model none）' % OPENROUTER)
    ap.add_argument('--provider', default=OPENROUTER_PROVIDER,
                    help='经 OpenRouter 时只用这几家，逗号隔开（默认 %s：gemini 走 Google 的 flex 档，价格一半）'
                         % OPENROUTER_PROVIDER)
    ap.add_argument('--prescreen-model', default=PRESCREEN_MODEL,
                    help='先用这个便宜模型宽松初筛（默认 %s）：只问有没有可能是 17 项之一，判成没有的图不做正式分类；'
                         '写 none 就不初筛、每张都正式分类' % PRESCREEN_MODEL)
    ap.add_argument('--prescreen-base-url', default=PRESCREEN_BASE_URL,
                    help='初筛走哪个接口（默认 openai = OpenAI 直连；same = 和 --base-url 一样；或写接口地址）')
    ap.add_argument('--prescreen-key-env', default=PRESCREEN_KEY_ENV,
                    help='初筛的 key 从哪个环境变量取（默认 %s；写 same 就和 --key-env 一样）' % PRESCREEN_KEY_ENV)
    ap.add_argument('--classify-model', default='',
                    help='正式分类用的模型（默认和 --model 一样）；读图一律用 --model')
    ap.add_argument('--classify-effort', default='', choices=['', 'minimal', 'low', 'medium', 'high'],
                    help='分类时的推理强度（默认不设 = 模型自己的默认）；调低能少花输出 token，先测再用')
    ap.add_argument('--classify-slim', action='store_true',
                    help='分类回答瘦身：先判断要不要读，不用读的子图其余各栏从简（先测再用）')
    ap.add_argument('--slot', default='', metavar='K/N',
                    help='同时开 N 个窗口时这是第 K 个（例如 2/5）：从全部文章的 (K-1)/N 处开始做，做到末尾再从头接着做，'
                         '几个窗口一开始就不挤在同一批文章上。不重复靠每篇开始前的领取，和这个无关')
    a = ap.parse_args(argv)
    slot = None
    if a.slot:
        try:
            slot = parse_slot(a.slot)
        except ValueError as e:
            ap.error(str(e))
    try:
        sys.stdout.reconfigure(errors='replace')      # 输出重定向到文件时，GBK 编不了的字符不报错
    except (AttributeError, ValueError):
        pass
    if a.log:
        path = start_log()
        print('日志：%s' % path)
    if a.api_workers < 1 or a.paper_workers < 1:
        ap.error('--api-workers 和 --paper-workers 至少 1')
    roots = find_papers(a.papers)
    if not roots:
        print('没有找到抓取脚本的产物（文章文件夹里要有 %s\\figure_markdown.md）' % FIGURE_DIR)
        return 1
    base_url = '' if a.base_url.strip().lower() in ('', 'openai', 'none') else a.base_url
    api = Api(a.model, a.api_workers, key_env=a.key_env, base_url=base_url, provider=a.provider)
    api.prescreen_model = a.prescreen_model if a.prescreen_model.strip().lower() not in ('', 'none', '0') else None
    pb = a.prescreen_base_url.strip()
    api.prescreen_base_url = None if pb.lower() == 'same' else '' if pb.lower() in ('', 'openai', 'none') else pb
    pk = a.prescreen_key_env.strip()
    api.prescreen_key_env = None if pk.lower() in ('', 'same') else pk
    api.classify_model = a.classify_model or None
    api.classify_effort = a.classify_effort or None
    api.classify_slim = a.classify_slim
    if a.status:
        status(roots)
        return 0
    if a.dry_run:
        dry_run(roots, api)
        return 0
    if a.redo_no_json:
        todo = [r for r in roots if no_json(r)]
        where = '（只重读有 %s、没有 %s 的老文章）' % (MD_NAME, DB_NAME)
    else:
        todo = [r for r in roots if a.refresh or not is_done(r)]
        where = ''
    skipped = len(roots) - len(todo)
    if a.only_started:
        todo = [r for r in todo if os.path.isdir(work_dir(r))]
        where = '（只做有断点的，没开始的 %d 篇这次不碰）' % (len(roots) - skipped - len(todo))
    todo, first, n_started = started_first(todo, slot)
    if slot:
        where += '（第 %d/%d 个窗口，从没做的第 %d 篇开始，做到末尾再从头接着）' % (slot + (first + 1,))
    if n_started and n_started < len(todo):
        where += '（停在断点的 %d 篇先做）' % n_started
    if a.limit:
        todo = todo[:a.limit]
    extra = '；初筛：%s%s' % (api.prescreen_model, api.prescreen_where()) if api.prescreen_model else ''
    if api.classify_model or api.classify_effort or api.classify_slim:
        extra += '；分类：%s%s%s' % (api.classify_model or a.model,
                                   '，推理强度 %s' % api.classify_effort if api.classify_effort else '',
                                   '，回答瘦身' if api.classify_slim else '')
    print('共 %d 篇，已完成跳过 %d 篇，这次处理 %d 篇%s；模型 %s，接口 %s，key 取自 %s，API 名额 %d，同时 %d 篇%s'
          % (len(roots), skipped, len(todo), where, a.model, api.where(), a.key_env, a.api_workers, a.paper_workers,
             extra), flush=True)
    if todo:
        api.client      # 没有 API key 时在开始前就停下
        if api.prescreen_model:
            api.client_for('初筛')
    claims = Claims()
    t0 = time.time()

    def total_usage():
        if api.usage:
            print('这个窗口合计用量：' + usage_text(api.usage), flush=True)
    try:
        ok, failed, busy = run_batch(todo, api, a.paper_workers, claims, refresh=a.refresh,
                                     redo_no_json=a.redo_no_json)
    except KeyboardInterrupt:
        claims.release_all()                           # 别的窗口马上就能接手这几篇
        print('\n中断。已经拿到的分类和读图结果都在 %s 里，重跑同一条命令接着做。' % CHECKPOINT_DIR, flush=True)
        total_usage()
        os._exit(130)                                   # 不等正在进行的请求（最长 5 分钟）
    except Fatal:
        claims.release_all()
        total_usage()
        print('\n%s\n窗口停下了：%s\n%s' % ('=' * 70, api.fatal, '=' * 70), flush=True)   # 最后一屏再写一遍原因
        return 3
    print('\n完成 %d 篇，未完成 %d 篇，另一个窗口在处理而跳过 %d 篇，用时 %.0f 秒'
          % (ok, len(failed), len(busy), time.time() - t0))
    total_usage()
    for root in failed:
        print('  未完成：%s' % root)
    return 0 if not failed else 2


def run_batch(todo, api, paper_workers=PAPER_WORKERS, claims=None, refresh=False, redo_no_json=False):
    """逐篇领取 → 处理 → 放开。返回 (完成篇数, 未完成的, 另一个窗口在处理而跳过的)。
    refresh：这次开跑之前就完成的也重做；开跑之后才完成的（别的窗口刚重做完）照样跳过。
    redo_no_json：有 反读数据.md、没有 反读数据.json 的也重做（别的窗口刚补上 json 的跳过）。"""
    claims = claims or Claims()
    started = time.time()

    def one(root):
        if api.stop.is_set():                          # 没钱 / key 无效：不再领新文章（用户 2026-10-08）
            return root, 'stopped'
        if not claims.take(root):
            print('[%s] 另一个窗口正在处理，跳过' % os.path.basename(root), flush=True)
            return root, 'busy'
        try:
            if is_done(root) and not (refresh and os.path.getmtime(os.path.join(root, MD_NAME)) < started)                     and not (redo_no_json and no_json(root)):
                return root, True                      # 领取前刚被另一个窗口做完
            paper = load_paper(root)
            try:
                return root, process_paper(paper, api)
            except SystemExit:
                raise
            except Exception as e:
                say(paper, '出错：%s: %s（中间结果保留在 %s，重跑接着做）' % (type(e).__name__, e, work_dir(root)))
                return root, False
        finally:
            claims.release(root)

    ok, failed, busy = 0, [], []
    with futures.ThreadPoolExecutor(max_workers=paper_workers) as pool:
        for root, good in pool.map(one, todo):
            if good == 'busy':
                busy.append(root)
            elif good == 'stopped':
                continue
            elif good:
                ok += 1
            else:
                failed.append(root)
    if api.stop.is_set():
        raise Fatal(api.fatal)
    return ok, failed, busy


LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '日志')


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for s in self.streams:
            s.write(text)
        return len(text)

    def flush(self):
        for s in self.streams:
            s.flush()

    def __getattr__(self, name):
        return getattr(self.streams[0], name)


def start_log():
    """屏幕上的输出同时写进 日志\\运行_时间_进程号.txt（几个窗口各写各的）。"""
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, '运行_%s_%d.txt' % (time.strftime('%Y%m%d_%H%M%S'), os.getpid()))
    fh = open(path, 'a', encoding='utf-8', buffering=1)
    sys.stdout, sys.stderr = _Tee(sys.stdout, fh), _Tee(sys.stderr, fh)
    return path


# ====================================================================================================
# 全文合并（原 paper_clean\paper_clean.py）
# ====================================================================================================
r"""
paper_clean.py —— 全文.md + 反读数据.md → 合并、精简后的全文（第三步，纯规则，不调用任何模型）

    python paper_clean.py                            # D:\2.elsevier_papers 下全部文章 → 每篇文件夹里的 全文合并.md
    python paper_clean.py 10.1021_acs.jafc.0c00025 [更多文章名或文件夹 ...]
    python paper_clean.py --sample 25                # 从有反读数据的文章里固定抽 25 篇试跑
    python paper_clean.py --root D:\1.acs_papers_done  # 别的总文件夹（ACS：文章在它的 papers 子文件夹里）

文件夹结构（用户 2026-10-21 定，和 D:\acs_papers_done 一致）：
    <root>\papers\<文章名>\全文.md、反读数据.md、反读数据.json、figure\figure_markdown.md   输入（只读，一个字不改）
    <root>\papers\<文章名>\全文合并.md                                                      输出（同名覆盖；纯规则，随时可以重跑）
    <root>\_records\全文合并\_合并报告.md                                                   报告（每次运行覆盖）
没有 papers 子文件夹的总文件夹（如 D:\2.elsevier_papers），文章文件夹直接放在 <root> 下面，其余一样。

用户 2026-10-13 定的口径：先合并清理、后数据提取；全文不需要显示图，只把反读数据表回插到合适位置；
不是关键信息都可以不要，杂七杂八的格式全部丢掉，尽可能简化。规则：
  1 页头只留「# 标题」和「DOI: …」；标题前后、## Abstract 之前的期刊日期、作者、单位、邮箱、ORCID、COI 声明全删
  2 删整节：Visual Abstract（图文摘要）、致谢、作者贡献、资助、数据可得性、竞争利益、Notes、勘误说明、Safety、
    Dedication、Special Issue、Accession Codes、Supporting Information。缩写表保留（哪怕挂在致谢下面，提到同级），
    整理成一行一条「缩写: 全称」；Introduction 保留（缩写常在摘要和引言里第一次定义）。
    文章顶部的 Visual Abstract、Special Issue、勘误说明只删图片、主题标签和一段说明，后面没有标题的正文不动；
    文末的节下面挂着的非删除小节（缩写表、术语表、错放的结果小节）留下。被删的一节超过 3000 字、或合并后正文
    不到原文正文一半的，写进报告提醒抽查
  3 所有图片删掉；图片前单独一行的图号、[View Large] / [Download to Slide] 行删掉；「Figure N.」和图注并成一行
  4 反读数据表插在这张图的图注后面（图片版表格插在表的位置），精简成 系列 / X / Y / 单位 / 误差 / 显著性 / 判定 几列；
    文末接「## 反读数据评价」（「反读值不是原文数值」这句提示只在这里出现一次）。
    每个子图的标题行补上同一文件夹 反读数据.json 里的读图分类（17 项里的哪一项）、X/Y 轴标题，双纵轴的写明左右轴各是什么
    （用户 2026-10-13：下一步数据点提取只读合并稿，判断系列属于哪项指标要用）：
      子图 A｜读图分类：粒径｜X 轴：…｜Y 轴：…｜左轴：Size；右轴：PDI      没有子图编号的写「整图｜…」
  5 链接一律只留文字（引文 ([1](javascript:;),[2](javascript:;)) → (1,2)）；粗体、斜体去掉；markdown 转义的反斜杠去掉
    （表格里的 \| 除外）；软连字符去掉；标题保留 # 层级；空标题删掉；多余空行压成一个
  6 爱思唯尔（ScienceDirect）文章（用户 2026-10-16：在这个脚本基础上兼容 ACS 和爱思唯尔，原有功能不删）：每篇先认出版商，
    ACS 照上面原样处理；Elsevier 另外——页头只留标题和 DOI（一级标题是空「#」的，标题从 figure_markdown.md 取），正文从
    Highlights / Abstract 开始；删下载原图的两行、Highlights 前的「•」、上一篇/下一篇、Graphical abstract；另删生成式 AI 声明、
    伦理声明、知情同意、各种 Declaration / Author statement / Disclosure、ORCID、Chemical compounds、视频控件、
    Appendix A. Supplementary data、没切干净的参考文献和网页尾部（推荐文章、被引、指标连同下面的小节）；图注「Fig. 5. …」、
    表题「Table 1. …」照原文一行，反读数据插在后面（图片版表格插在表格图片后面）；关键词并成一行，缩写表（另认
    List of abbreviations、Nomenclature、Glossary 等写法）去掉分隔的「;」和表头，并成「缩写: 全称」。
    python paper_clean.py --root D:\2.elsevier_papers（每篇的 全文合并.md 写在它自己的文件夹里）
核对（不过就不写这篇，列进报告）：反读表每一行都插进去了；作者表格里的数字一个不少；不剩图片、链接、上下标标记；
留下的每段作者原文都能在原文件里找到。规则判不了的（找不到图注的反读数据）照样写，附在文末，列进报告。
只用 Python 标准库。
"""


# 用户 2026-10-21：各步脚本都按 D:\acs_papers_done 的结构（papers\<文章>\、_records\、database\）；默认输入是
# D:\2.elsevier_papers（「这个脚本的输入是 D:\elsevier_papers 这里的全文 markdown 及图」，文章直接放在它下面），
# ACS 用 --root D:\acs_papers_done（原来的 D:\acs_papers-已齐全 全部 → D:\acs_papers_全文合并-已齐全 全部完成 已经不在了）
pc_ROOT = r'D:\2.elsevier_papers'   # 用户 2026-10-30 把 Elsevier 总文件夹改名为 2.elsevier_papers
pc_PAPERS_SUBDIR = 'papers'            # <root>\papers\<文章>\；没有这个子文件夹的总文件夹，文章直接放在 <root> 下
pc_RECORDS_SUBDIR = '_records'
pc_STEP_DIR = '全文合并'               # 报告放 <root>\_records\全文合并\
pc_MERGED_NAME = '全文合并.md'         # 每篇的输出，写在文章文件夹里（下一步 extract_datapoint.py 读它）
pc_REPORT_NAME = '_合并报告.md'
pc_SAMPLE_SEED = 20261013


def pc_papers_dir(root):
    sub = os.path.join(root, pc_PAPERS_SUBDIR)
    return sub if os.path.isdir(sub) else root

# ---------------------------------------------------------------- 节 --
pc_HEAD = re.compile(r'^(#{1,6})\s+(.*?)\s*$')
pc_NUMBERING = re.compile(r'^(?:\d+(?:\\?\.\d+)*\\?\.?|[IVX]+\\?\.|[A-Z]\\?\.)\s+')
pc_DROP_SECTIONS = re.compile(
    r'^(?:visual abstract|graphical abstract|toc graphic|table of contents graphic|'
    r'acknowledge?ments?|author contributions?|credit authorship contribution statement|'
    r'funding(?: sources?| information| statement)?|data availability(?: statement)?|'
    r'availability of data(?: and materials?)?|declaration of competing interests?|competing interests?|'
    r'conflicts? of interests?|notes?|additional notes|note added after asap publication|safety|dedication|'
    r'special issue|accession codes|supporting information(?: data| available| description)?|associated content|'
    r'author information)$')
pc_KEEP_SECTIONS = re.compile(r'^(?:abbreviations?|abbrevations?|abbreviation)\b')
# 文章顶部的这几节只有图片、主题标签或一句说明；后面常常紧跟着没有标题的正文（cc0501413 这类短报告 Visual Abstract
# 后面就是正文、2c07270 勘误说明后面就是引言），不能「删到下一个标题」，只删紧跟着的图片、View Large、Subjects/Keywords
# 和（专刊、勘误）那一段说明
pc_TOP_SECTIONS = re.compile(r'^(?:visual abstract|graphical abstract|toc graphic|table of contents graphic|'
                          r'special issue|note added after asap publication)$')
pc_TOPIC_LINE = re.compile(r'^\*\*(?:Subjects|Keywords)\*\*')
# 文末被删的节里出现文献引用（([1](javascript:;))）或图表编号，说明后面已经是没有标题的正文（co2001718：「作者贡献」
# 标题下一句「These authors contributed equally」之后直接是引言和图 1），到这里停下不删
pc_BODY_SIGN = re.compile(r'\(\[\d+(?:\s*[−–-]\s*\d+)?\]\(javascript:;\)|^(?:Figure|Scheme|Chart|Table) \d+[A-Za-z]?\.?$')
pc_BIG_SECTION = 3000                       # 文末被删的一节超过这么多字，报告里提醒抽查（多半是连着没切掉的参考文献）

# ---------------------------------------------------------------- Elsevier --
# 用户 2026-10-16：在这个脚本的基础上兼容爱思唯尔（ScienceDirect）的文章，ACS 原有的功能不动。每篇先认出版商，
# 下面这些规则只对认成 Elsevier 的文章生效，ACS 文章走原来的路径（改完拿 ACS 全部 7375 篇和改之前逐字比过）。
pc_ELS_MARK = re.compile(r'Author links open overlay panel|ars\.els-cdn\.com|^## Published by: Elsevier', re.M)
pc_ACS_MARK = re.compile(r'silverchair-cdn\.com|Search for other works by this author')
# Elsevier 文末另有的节：生成式 AI 声明、伦理声明、发表同意、视频控件、补充材料（Appendix A. Supplementary data），
# 以及抓取时没切干净的参考文献和网页尾部（用户 10-10：最后合并清理统一删）
pc_ELS_DROP = re.compile(
    r'^(?:declarations?\b.*|ethic\w*\b.*|(?:compliance with|animals?(?: and)?) ethic\w*\b.*|(?:informed )?consent\b.*|'
    r'institutional review board\b.*|statement (?:for|of) (?:studies in )?(?:humans?|animals?)\b.*|statement|'
    r'disclosure\b.*|submission declaration\b.*|financial interests?\b.*|(?:generative )?ai (?:declaration|in scientific writing)\b.*|'
    r'generative a[il]\b.*|credit\b.*|authorship\b.*|authors?(?:[\'’]s?)? (?:contributions?|statement|agreement|declaration)\b.*|'
    r'competing interests?\b.*|conflicts? of interests?\b.*|'
    r'(?:data|code|materials?|software)\b.{0,30}\bavailability\b.*|data statement|'
    r'fundings?\b.*|formatting of funding sources|ac?knowledg\w*\b.*|chemical compounds\b.*|graphical abstracts\b.*|orcid\b.*|'
    r'media player|appendix\b.*supplementary\b.*|supplementary (?:data|materials?)|'
    r'part of special issue|references?|refrences?|reference list|resources|bibliography|literature cited|recommended articles|'
    r'cited by(?: \(\d+\))?|(?:article )?metrics)$')
# 参考文献及其后面的网页尾部（推荐文章 / 被引 / 指标）：下面挂着的小节（Based on reading popularity、Citations、Captures）一起删
pc_ELS_TAIL = re.compile(r'^(?:references?|refrences?|reference list|bibliography|literature cited|recommended articles|'
                      r'cited by(?: \(\d+\))?|(?:article )?metrics)$')
# Elsevier 缩写表标题的其他写法（List of abbreviations / Abbreviations used / Nomenclature / Glossary …），
# 缩写表第一对是表头「Abbreviation, Full form」的去掉
pc_ELS_ABBR = re.compile(r'^(?:(?:list|table|key) (?:of|to) (?:frequently used |common )?)?(?:(?:non-?standard|general|main) )?'
                      r'(?:abbreviat\w*|abbrevations?|acronyms?)(?: used| list| and (?:symbols|acronyms))?$|'
                      r'^(?:nomenclature|glossary|abbreviate list)$')
pc_ABBR_HEADER = re.compile(r'^(?:abbreviations?|abbr\.?|acronyms?)[\s,，:：]*$', re.I)
pc_ABBR_HEADER2 = re.compile(r'^(?:full (?:forms?|names?|terms?)|definitions?|descriptions?|meanings?|explanations?)[\s.:：]*$', re.I)
# 页面杂项行：下载原图的两行（链接带标题属性："Download high-res image (2MB)"）、Highlights 每条前面单独一行的「•」、
# 上一篇 / 下一篇、补充材料的引导句，以及整行只有一个指向图表的链接（「[Table 3](#tbl0003).」，句子被抓取拆断剩下的半截）
pc_ELS_JUNK = re.compile(r'^(?:\d+\.\s+)?\[Download: Download[^\]]*\]\([^)\s]*(?:\s+"[^"]*")?\)\s*$|^[-*]\s+•\s*$|'
                      r'^[-*]\s+\[(?:Previous|Next) article in (?:this )?issue\]\([^)\s]*(?:\s+"[^"]*")?\)\s*$|'
                      r'^The following (?:are|is) the supplementary (?:data|materials?) related to this article\b.*$|'
                      r'^\[(?:Fig\.?|Figure|Table|Scheme|Chart)\s*[^\]]*\]\(#[^)\s]*\)\s*[.,;]?\s*$')
# Highlights 的「•」和文字写在同一行（「- •Interactions of …」）：去掉记号
pc_ELS_BULLET = re.compile(r'^[-*]\s*•\s*(?=\S)')
# 图注、表题：「Fig. 5. 图注」「Table 1. 表题」写在同一行（个别是单独一行的「Fig. 5.」，图注在下一段；个别写成「Fig 2.」）。
# 同一行带文字的必须有句点，免得把正文里「Figure 3 shows …」开头的句子当成图注
pc_ELS_LABEL = re.compile(r'^(Fig\.?|Figure|Scheme|Chart|Table)\s*([A-Z]?\d+(?:[-–]\d+)?[A-Za-z]?)(?:\.\s+(\S.*)|\.?)$')
# （个别学位论文式编号「Fig. 3-4.」「Fig. 3–11.」，反读数据.md 的块名也是「Fig. 3-4」）
# 正文句子写成「Fig. 5. shows …」「Table 2. presents …」、同一图号另有正常图注的，这一行不算图注（fufo.2026.101089）；
# 没有别的图注的照样算图注（ijbiomac.2026.151448 的图注本身就写成「Fig. 6. depicts …」）
pc_ELS_BODY_VERB = re.compile(r'^(?:summari[sz]es|shows|showed|depicts|presents|presented|lists|illustrates|displays|indicates|'
                           r'reveals|demonstrates|provides|reports|gives|contains|compares|describes|represents|exhibits|'
                           r'highlights)\b')
# 文末被删的节里出现文献引用（[Yuan et al., 2024](#bb0250)）或图注，说明后面已经是正文
pc_ELS_BODY_SIGN = re.compile(r'\]\(#(?:bb|bib|b)\d+\)|^(?:Fig\.|Figure) [A-Z]?\d+[A-Za-z]?\.\s')
pc_ELS_CHROME_HEAD = re.compile(r'^## (?:\[|Published by|Outline|Figures \(\d+\)|Tables \(\d+\)|Part of special issue)')
pc_KEYWORD_SECTIONS = re.compile(r'^(?:keywords?|key ?words?|key worlds)$')
pc_LIST_SEPARATOR = (';', '；', ',', '，')


def pc_publisher(text):
    """'elsevier' 或 'acs'（其余按 ACS 原规则处理）。"""
    return 'elsevier' if pc_ELS_MARK.search(text) and not pc_ACS_MARK.search(text) else 'acs'


# ---------------------------------------------------------------- 其他几家 --
# 用户 2026-10-30：「让那个脚本能通用的处理这八家出版商的全文 从读图到最后的数据点提取」。Wiley、RSC、MDPI、OUP、
# Taylor & Francis、Springer Nature 的 全文.md 各有各的页面杂项和图注写法。出版商看 figure_markdown.md 里记的网页地址
# （抓取脚本写的「网页: https://…」，几家的文章每篇都有）；下面这些规则只对这几家生效，ACS、Elsevier 走原来的路径（逐字节不变）。
pc_NEW_HOSTS = (('wiley.com', 'wiley'), ('hindawi.com', 'wiley'), ('rsc.org', 'rsc'), ('oup.com', 'oup'),
                ('mdpi.com', 'mdpi'), ('tandfonline.com', 'tandf'), ('springer.com', 'springer'),
                ('nature.com', 'springer'), ('biomedcentral.com', 'springer'), ('springeropen.com', 'springer'))
pc_NEW_PUBS = ('wiley', 'rsc', 'mdpi', 'oup', 'tandf', 'springer')
pc_NEW_NAMES = (('wiley', 'Wiley'), ('rsc', 'RSC'), ('mdpi', 'MDPI'), ('oup', 'OUP'), ('tandf', 'Taylor & Francis'),
                ('springer', 'Springer Nature'))
pc_PAGE_URL = re.compile(r'(?m)^网页:\s*https?://([^/\s]+)')
# 图片（带不带标题属性、地址带不带尖括号）：这几家的图片行、公式图片、表格里的公式图片都去掉（图片本来就留不下来）
# （OUP 的图片说明文字里有转义的方括号「\[Colour figure can be viewed at …\]」）
pc_NEW_IMG = re.compile(r'\[!\[(?:\\.|[^\]\\\n])*\]\((?:<[^>\n]*>|[^)\s]*)(?:\s+"[^"\n]*")?\)\]\((?:<[^>\n]*>|[^)\s]*)(?:\s+"[^"\n]*")?\)|'
                        r'!\[(?:\\.|[^\]\\\n])*\]\((?:<[^>\n]*>|[^)\s]*)(?:\s+"[^"\n]*")?\)')
pc_NEW_FORMULA = re.compile(r'(?i)!\[(?:\\.|[^\]\\\n])*?(?:math|equation|formula|urn:x-wiley)(?:\\.|[^\]\\\n])*\]')
pc_NEW_ANGLE_LINK = re.compile(r'(?<!!)\[([^\[\]\n]*)\]\(<[^>\n]*>\)')          # [Google Scholar](<http://… …>)：只留文字
# 地址里有空格的链接（OUP 表格里的「[NM\_002 016](https://www.ncbi.nlm.nih.gov/nuccore/NM_002 016)」）：只留文字
pc_NEW_SPACE_LINK = re.compile(r'(?<!!)\[((?:\\.|[^\[\]\\\n])*)\]\((?:https?://|/)[^()\s]*(?: [^()\s]+)+\)')
# 图旁边的按钮行：RSC「[View large](…) [Download slide](…)」、OUP「[Open in new tab](…)[Download slide](…)」
# （有的断成「[Open in new tab](<」和「/view-large/…>)」两行）、Wiley「[Open in figure viewer](#)[PowerPoint](…)」等
# （一行全是按钮：带链接的、只有文字的、方括号转义的都算，如 OUP「[Open in new tab](…)Download slide」、
# RSC「[View large](…)\[DownloadSlide\]」）；断开的链接：单独一行的「[」、只剩后半截的「PDF](/bbb/article-pdf/….pdf)」
pc__BUTTON = (r'(?:View large|Download ?slide|Open in new tab|Open in figure viewer|Open figure viewer|PowerPoint|Download figure|'
              r'Full size image|Display full size|Enlarge|Click here to enlarge figure|'
              r'Download (?:high-res |full-size |full size )?image[^\]\\]*)')
pc_NEW_BUTTONS = re.compile(
    r'^(?:(?:\[%s\]\((?:<[^>\n]*>|[^)\n]*)\)|\\?\[%s\\?\]|%s)\s*)+$|^\[Open in new tab\]\(<$|^/view-large/\S*>\)$|'
    r'^\[$|^[^\[\]\n]{0,40}\]\([^)\s]*\)$' % (pc__BUTTON, pc__BUTTON, pc__BUTTON), re.I)
# 摘要和正文之间的页面杂项：OUP 的「Subject」+ 学科链接、「Issue Section:」+ 栏目名，各家的「Graphical Abstract」+ 一段目录说明
pc_NEW_SUBJECT_LINK = re.compile(r'^\[[^\]]+\]\([^)]*search-results[^)]*\)$')
pc_NEW_SKIP_NEXT = re.compile(r'^(?:Issue Section:|Subjects?:?|Graphical Abstract|Graphical abstract|Visual Abstract)$')
# 图号、表号：整行是图号（可带粗体、句点、破折号、子图号「(a)」，Wiley 老文章「Figure Figure 1.」），或者图号后面跟句点再跟图注
# （MDPI「**Figure 1.** 图注」）。正文句子「Figure 3 shows …」「Fig. S1[†] shows …」不算
pc_NEW_LABEL = re.compile(
    r'^(?P<b>\*\*)?(?P<kind>Fig(?:ure)?s?\.?|FIGURE|FIG\.?|Scheme|SCHEME|Chart|CHART|Graph|GRAPH|Plate|PLATE|Table|TABLE)\s*'
    r'(?:(?:Figure|Fig\.|Scheme|SCHEME|Table)\s+)?(?P<num>[A-Z]?\d+[A-Za-z]?)(?P<sub>\s*\([a-zA-Z]\))?'
    r'(?P<sep>\s*[.:—–-])?(?(b)(?P<inner>[^*]*)\*\*)(?P<rest>.*)$')
pc_NEW_KIND = {'fig': 'Figure', 'sch': 'Scheme', 'cha': 'Chart', 'gra': 'Graph', 'pla': 'Plate', 'tab': 'Table'}
pc_NEW_DROP = re.compile(r'^(?:(?:transparent )?peer review\b.*|footnotes?|endnotes?|recommended|related articles?|citing literature|'
                         r'corrections? (?:for this article|statement)|correction\(s\) for this article|supplemental\b.*|'
                         r'supplementary files?|sample availability|live subject statement|'
                         r'electronic supplementary information\b.*|notes and references|references? and notes|'
                         r'references cited|bibliographic references|open research\b.*|copyright\b.*|patents?|'
                         r'sources? of funding\b.*|'
                         r'conflicts? of \w*interests?\b.*)$')
# 这些节名在方法里也会有（Elsevier 那套规则整节删）：这几家的有表格、图号或超过 1500 字的照正文留下
pc_NEW_MAYBE_BODY = re.compile(r'^(?:ethic\w*\b.*|(?:compliance with|animals?(?: and)?) ethic\w*\b.*|(?:informed )?consent\b.*|'
                               r'institutional review board\b.*|statement (?:for|of) (?:studies in )?(?:humans?|animals?)\b.*|'
                               r'chemical compounds\b.*)$')
pc_NEW_TAIL = re.compile(r'^(?:recommended|citing literature|notes and references|references? and notes|references cited|'
                         r'bibliographic references|related articles?)$')
# 被删的节里出现正文的引文链接（Wiley「[12](#jsfa8336-bib-0012)」、RSC / OUP「[³¹](javascript:;)」），说明后面已经是正文
pc_NEW_BODY_SIGN = re.compile(r'\]\(#[\w.-]*bib-?\d+\)|\[[\d⁰¹²³⁴-⁹,–-]+\]\(javascript:;\)')


def pc_publisher_of(root, lines):
    """出版商：这几家看 figure_markdown.md 里记的网页地址；其余照原来的 pc_publisher（'elsevier' 或 'acs'）。"""
    fm = os.path.join(root, 'figure', 'figure_markdown.md')
    if os.path.exists(fm):
        m = pc_PAGE_URL.search(pc_read(fm)[:3000])
        if m:
            host = m.group(1).lower()
            for dom, pub in pc_NEW_HOSTS:
                if host == dom or host.endswith('.' + dom):
                    return pub
    return pc_publisher('\n'.join(lines))


def pc_new_prepare(lines):
    """这几家：图片（含公式图片）去掉，尖括号地址的链接只留文字。返回 (行, 去掉的公式图片数)。
    图片说明文字换了行的（OUP 老文章「![Figure 6 Binding pocket … (looking⏎ … text.](https://…)」）：和后面几行并起来认，
    认出来的图片连同占的几行一起去掉（行数不变，后面的行号照旧）。"""
    out, formulas = list(lines), 0
    for i in range(len(out)):
        if re.fullmatch(r'#{1,6}', out[i].strip()):
            j = next((k for k in range(i + 1, min(i + 4, len(out))) if out[k].strip()), None)
            if j is not None and len(out[j].strip()) <= 80 and not out[j].lstrip().startswith(('#', '|', '!', '[', '-', '*')):
                out[i], out[j] = out[i].strip() + ' ' + out[j].strip(), ''
        line = out[i]
        if '![' in line and re.search(r'!\[(?:\\.|[^\]\\\n])*$', pc_NEW_IMG.sub('', line)):
            # 这一行的图片说明没写完（换了行，OUP 老文章有折成十几行的）：往后找到图片收尾的「](地址)」，并起来再认；
            # 碰到标题、隔了 60 行还没找到，或者并起来也认不出，照原样
            for k in range(i + 1, min(i + 60, len(out))):
                if out[k].lstrip().startswith('#'):
                    break
                if re.search(r'\]\((?:<[^>\n]*>|[^)\s]*)(?:\s+"[^"\n]*")?\)', out[k]):
                    joined = ' '.join(x.strip() for x in out[i:k + 1] if x.strip())
                    if pc_NEW_IMG.search(joined) and not re.search(r'!\[(?:\\.|[^\]\\])*$', pc_NEW_IMG.sub('', joined)):
                        line = joined
                        for j in range(i + 1, k + 1):
                            out[j] = ''
                    break
        if '![' in line:
            formulas += len(pc_NEW_FORMULA.findall(line))
            rest = pc_NEW_IMG.sub('', line)
            line = '' if not rest.strip() else rest
        if '](<' in line:
            line = pc_NEW_ANGLE_LINK.sub(r'\1', line)
        if '](' in line and ' ' in line:
            line = pc_NEW_SPACE_LINK.sub(r'\1', line)
        out[i] = line
    return out, formulas


def pc_new_has_body(lines, i):
    """第 i 行标题这一节（到下一个同级或更高级标题）里有表格、图号，或者文字超过 1500 字：是正文，不当声明删。"""
    level = len(pc_HEAD.match(lines[i]).group(1))
    size = 0
    for line in lines[i + 1:]:
        m = pc_HEAD.match(line)
        if m and len(m.group(1)) <= level:
            break
        s = line.strip()
        if s.startswith('|') or pc_new_label(s):
            return True
        size += len(s)
    return size > 1500


def pc_new_junk(s):
    return bool(pc_NEW_BUTTONS.match(s) or pc_NEW_SUBJECT_LINK.match(s)) or pc_is_junk_line(s)


def pc_new_label(s):
    """这一行是图号 / 表号：返回 (('Figure', '3'), 图号写法「Figure 3 (a)」, 同一行的图注或 '')；不是返回 None。
    句点单独加粗的（OUP「Figure 1**.**」）当普通句点。"""
    m = pc_NEW_LABEL.match(re.sub(r'\*\*([.:—–-])\*\*', r'\1', s))
    if not m:
        return None
    inner, rest = (m.group('inner') or '').strip(), m.group('rest').strip()
    if m.group('b'):
        if rest and not (m.group('sep') or inner):         # 「**Figure 1** shows …」：正文句子
            return None
    elif (rest and not m.group('sep')) or rest.startswith(('[', '*')):    # 「Figure 3 shows …」「Fig. S1[†] …」
        return None
    rest = ' '.join(x for x in (inner, rest) if x)          # 粗体里的子图说明（Hindawi「**Figure 5 (a) RGB image**」）也算同一行的图注
    kind = pc_NEW_KIND[m.group('kind')[:3].lower()]
    num = m.group('num')
    label = '%s %s%s' % (kind, num, (' ' + m.group('sub').strip()) if m.group('sub') else '')
    return (kind, re.sub(r'[A-Za-z]$', '', num).upper() if not num[:1].isalpha() else num.upper()), label, rest


def pc_new_block_key(heading):
    """反读数据.md 的块名（figure_markdown.md 的标题，如「FIGURE 1」「Figure Figure 2」「Fig. 3」「Figure 5 (a) RGB image」）
    → 和图号比对用的 ('Figure', '1')。"""
    m = re.match(r'^(?i:(fig(?:ure)?s?\.?|scheme|chart|graph|plate|table))\s*([A-Z]?\d+)', lab(heading.strip()))
    if not m:
        return None
    return pc_NEW_KIND[m.group(1)[:3].lower()], m.group(2).upper()


def pc_new_header(lines, pub):
    """这几家的页头 → (标题, 正文开始的行号, 提醒)。RSC 的摘要没有标题，在唯一一行「Open figure viewer」后面；
    别的从「## Abstract」开始，没有的从一级标题后第一个二级标题开始。"""
    h1 = next((i for i, l in enumerate(lines) if l.startswith('# ')), None)
    if h1 is None:
        return '', None, None
    title = pc_clean_inline(lines[h1][2:].strip())
    title = re.sub(r'(?:\s*[†‡§¶]+)+(?=\s|$)', '', title)
    title = re.sub(r'\s+(?:Open Access|Available|Free|Free Access)$', '', title).strip()
    if pub == 'rsc':
        ofv = next((i for i in range(h1 + 1, len(lines)) if lines[i].strip() == 'Open figure viewer'), None)
        if ofv is not None:
            return title, ofv + 1, None
    start = next((i for i in range(h1 + 1, len(lines)) if re.match(r'(?i)^#{2,3}\s*(?:visual )?abstract\b', lines[i])), None)
    if start is not None:
        return title, start, None
    if pub == 'mdpi':                                # 没有摘要的特刊社论：正文紧跟在页头最后一行「[Order Reprints](…)」后面
        head2 = next((i for i in range(h1 + 1, len(lines)) if lines[i].startswith('## ')), len(lines))
        orr = next((i for i in range(head2 - 1, h1, -1) if lines[i].startswith('[Order Reprints](')), None)
        if orr is not None:
            return title, orr + 1, '没有 ## Abstract，从页头后面开始'
    start = next((i for i in range(h1 + 1, len(lines)) if lines[i].startswith('## ')), h1 + 1)
    return title, start, '没有 ## Abstract，从第一个二级标题开始'


def pc_els_key(kind, num):
    """Elsevier 图表的比对键：Fig. 5 / Figure 5 都算 Fig. 5（反读数据.md 的块名是页面上的写法「Fig. 5」）。"""
    kind = 'Fig.' if kind.lower().startswith('fig') else kind
    return '%s %s' % (kind, num)


def pc_els_title(root):
    """一级标题是空的「#」时（444 篇，标题写在下面一行普通文字里）：标题从 figure_markdown.md 第一行取，再不行取反读数据.md。"""
    for p in (os.path.join(root, 'figure', 'figure_markdown.md'), os.path.join(root, '反读数据.md')):
        if os.path.exists(p):
            m = re.search(r'(?m)^# (.+?)\s*$', pc_read(p))
            if m:
                return pc_clean_inline(re.sub(r'\s+[-|]\s+ScienceDirect\s*$', '', m.group(1)))
    return ''


def pc_els_header(lines, root):
    """Elsevier 的页头 → (标题, 正文开始的行号或 None)。期刊横幅、出版信息在一级标题之前；一级标题和第一个二级标题之间是
    View PDF、DOI 链接、Author links、许可证——正文从一级标题后第一个不是页面杂项的二级标题（Highlights / Abstract …）开始。"""
    h1 = next((i for i, l in enumerate(lines) if re.match(r'^#(?:\s|$)', l)), None)
    title = pc_clean_inline(lines[h1][1:].strip()) if h1 is not None else ''
    title = re.sub(r'\s+[-|]\s+ScienceDirect\s*$', '', title).strip() or pc_els_title(root)
    begin = h1 + 1 if h1 is not None else 0
    start = next((i for i in range(begin, len(lines)) if lines[i].startswith('## ') and not pc_ELS_CHROME_HEAD.match(lines[i])),
                 None)
    return title, start


def pc_els_lists(out):
    """Elsevier 的关键词和缩写表一项一行，中间夹着单独一行的「;」：关键词并成一行（'kw'）；缩写表去掉分隔行和缩写后面的逗号
    （「YFWM,」「Yogurt fortified with microcapsules」「;」…）和表头那一对，再交给 pair_abbreviations 并成「缩写: 全称」。
    缩写表标题另认 ELS_ABBR 里的写法（List of abbreviations、Nomenclature …）。"""
    res, i = [], 0
    while i < len(out):
        kind, val = out[i]
        res.append(out[i])
        i += 1
        if kind != 'head':
            continue
        name = pc_heading_text(val)
        kw, abbr = pc_KEYWORD_SECTIONS.match(name), pc_KEEP_SECTIONS.match(name) or pc_ELS_ABBR.match(name)
        if not (kw or abbr):
            continue
        j = i
        while j < len(out) and out[j][0] == 'text':
            j += 1
        items = [v for _, v in out[i:j] if v.strip() not in pc_LIST_SEPARATOR]
        if kw:
            # 只并关键词本身：有分隔行的取「词 ; 词 ; 词」这一串，没有的取开头连着的短行。后面没有标题的摘要
            # （fochx.2025.103336、jbiosc.2026.03.008）照原样留下；关键词一条很短，长段落不算（foohum.2026.101264
            # 文献计量综述的正文小节「3.2. Keywords」一条都不并）
            sep = len(items) < j - i
            words, k = [], i
            while k < j and len(out[k][1]) <= 150 and out[k][1].strip() not in pc_LIST_SEPARATOR:
                words.append(out[k][1])
                k += 1
                if sep:
                    if k < j and out[k][1].strip() in pc_LIST_SEPARATOR:
                        k += 1
                    else:
                        break
            if words:
                res.append(('kw', [x.rstrip(' ;；,，') for x in words]))
                i = k
        elif abbr and items:
            sep = len(items) < j - i                     # 有分隔行的排法：缩写后面的逗号去掉
            if sep:
                items = [x.rstrip(',，') if k % 2 == 0 else x for k, x in enumerate(items)]
            head = len(items) >= 2 and bool(pc_ABBR_HEADER.match(items[0]) and pc_ABBR_HEADER2.match(items[1]))
            if head:                                     # 表头「Abbreviation, Full form」
                items = items[2:]
            if sep or head:
                res += [('text', x) for x in items]
                i = j
    return res


def pc_heading_text(line):
    """标题文字：去 # 、编号、链接（jf0712402 的标题是 [Supporting Information](http://…)）、格式和转义、结尾标点，小写。"""
    m = pc_HEAD.match(line)
    text = m.group(2) if m else line
    text = pc_NUMBERING.sub('', pc_clean_inline(text.strip()))
    return text.strip(' .:：').lower()


def pc_drop_sections(lines, pub='acs'):
    """删整节。返回 (留下的行, 删掉的节名, 提醒)。
    文末的节删到下一个标题为止：同级或更高级的标题停；下面挂着的小节只有也是要删的（致谢下的 Funding）才一起删，
    别的小节（缩写表、术语表、网页上错放在作者贡献下面的结果小节）留下，提到被删那一节的级别。
    文章顶部的几节（TOP_SECTIONS）只删紧跟着的图片、View Large、Subjects/Keywords 和一段说明。
    pub='elsevier' 时另外删 ELS_DROP 里的节，下载链接等杂项行也算图片行；参考文献和网页尾部（ELS_TAIL）连下面的小节一起删。"""
    new = pub in pc_NEW_PUBS                       # 其他几家（用户 2026-10-30）：同 Elsevier，另加几家自己的节名
    els = pub == 'elsevier' or new

    def is_drop(name):
        return bool(pc_DROP_SECTIONS.match(name) or (els and pc_ELS_DROP.match(name)) or (new and pc_NEW_DROP.match(name)))

    def junk(s):
        return pc_is_junk_line(s) or (els and bool(pc_ELS_JUNK.match(s))) or (new and pc_new_junk(s))

    out, dropped, warns, i = [], [], [], 0
    while i < len(lines):
        m = pc_HEAD.match(lines[i])
        name = pc_heading_text(lines[i]) if m else ''
        if not (m and is_drop(name)) or (new and pc_NEW_MAYBE_BODY.match(name) and pc_new_has_body(lines, i)):
            out.append(lines[i])
            i += 1
            continue
        level = len(m.group(1))
        dropped.append(name)
        i += 1
        if pc_TOP_SECTIONS.match(name):
            note = name in ('special issue', 'note added after asap publication') or (new and 'abstract' in name)
            while i < len(lines):
                s = lines[i].strip()
                if pc_HEAD.match(lines[i]):
                    break
                if not s or junk(s) or pc_TOPIC_LINE.match(s):
                    i += 1
                    continue
                if note:                                 # 专刊、勘误：只删一段说明
                    note = False
                    i += 1
                    continue
                break
            continue
        size, tail = 0, els and bool(pc_ELS_TAIL.match(name) or (new and pc_NEW_TAIL.match(name)))
        while i < len(lines):
            m2 = pc_HEAD.match(lines[i])
            if m2 and (len(m2.group(1)) <= level or not (tail or is_drop(pc_heading_text(lines[i])))):
                if len(m2.group(1)) > level:
                    lines[i] = '#' * level + ' ' + m2.group(2)
                break
            s = lines[i].strip()
            if not m2 and (pc_BODY_SIGN.search(s) or (els and pc_ELS_BODY_SIGN.search(s)) or (new and not tail and
                                                                                        pc_NEW_BODY_SIGN.search(s))):
                break
            if s and not m2 and not pc_is_image_line(s) and not pc_VIEW.match(s) and not (els and pc_ELS_JUNK.match(s)):
                size += len(s)
            i += 1
        if size > pc_BIG_SECTION and not tail:              # 参考文献和网页尾部本来就长，不提醒
            warns.append('删掉的「%s」一节有 %d 字（多半连着没切掉的参考文献），请抽查' % (name, size))
    return out, dropped, warns


# ---------------------------------------------------------------- 行内清理 --
pc_IMG = re.compile(r'\[!\[[^\]\n]*\]\([^)\s]*\)\]\([^)\s]*\)|!\[[^\]\n]*\]\([^)\s]*\)')
# 链接文字里可以有转义字符和一层方括号（老 jf 关键词：[Sweet potato (Ipomoea batatas \[L.\] Lam)]），
# 网址里可以有转义字符和一层括号（/search-results?qb={"Keywords1":"…+\(Ipomoea…\)"}）
pc_LINK = re.compile(r'(?<!!)\[((?:\\.|[^\[\]\\\n]|\[[^\[\]\n]*\])*)\]\((?:\\.|[^()\s\\]|\([^()\s]*\))*(?:\s+"[^"\n]*")?\)')
# 文字就是网址本身的链接，网址里可以有空格（用户 2026-11-05：afres.2026.102457「[https://blast.ncbi.nlm.nih.gov/ 34](同左)」）
pc_SELF_LINK = re.compile(r'(?<!!)\[([^\[\]\n]+)\]\(\1\)')
# 网页里套了两层的网址链接，清完剩下的「网址](同一网址)」（ijbiomac.2026.153144「(URL: [网址](网址)\](…))」）
pc_URL_RESIDUE = re.compile(r'(https?://[^\s\[\]()]+)\]\(\1\)')
pc_VIEW = re.compile(r'^\s*(?:\[View Large\]\([^)]*\)|\[Download to Slide\]\([^)]*\))+\s*$')
pc_BOLD = re.compile(r'\*\*(?=\S)(.+?)(?<=\S)\*\*')
# 斜体记号和字母下标都用下划线（上下标转纯文本时字母下标写成 α_{S1}、m_s，斜体符号带下标写成 _c_{protein}_）：
# 斜体的开头前面不能是字母数字（含希腊字母）或右括号，结尾后面不能跟 { 或字母数字（Unicode 上下标数字可以：_d_₉₀）
pc__SCRIPT_DIGITS = '₀-₉⁰¹²³⁴-⁹₊₋⁺⁻'
pc_ITALIC_U = re.compile(r'(?<![\w\\)\]}])_(?=[^\s_{])(.+?)(?<=[^\s\\])_(?!\{)(?![^\W%s])' % pc__SCRIPT_DIGITS)
pc_ITALIC_S = re.compile(r'(?<![\w\\*)\]}])\*(?=[^\s*])(.+?)(?<=[^\s\\*])\*(?!\*)(?![^\W%s])' % pc__SCRIPT_DIGITS)
# \u53bb\u5b8c\u659c\u4f53\u8fd8\u5269\u7684\u96f6\u6563\u4e0b\u5212\u7ebf\uff08\u8001\u6587\u7ae0\u659c\u4f53\u6328\u7740\u7a7a\u683c\u548c\u5f15\u7528\uff1a\u300c( _(31))\u300d\u300ccis-_9,_trans-_11\u300d\u300c(_ _S_ samples)\u300d\uff09\uff1a
# \u5b57\u6bcd\u4e0b\u6807\u7684\u4e0b\u5212\u7ebf\u524d\u9762\u4e00\u5b9a\u6328\u7740\u5b57\u6bcd\u6570\u5b57\u6216\u53f3\u62ec\u53f7\u3001\u540e\u9762\u4e00\u5b9a\u8ddf\u5b57\u6bcd\u6570\u5b57\u6216 {\uff0c\u4e0d\u662f\u8fd9\u6837\u7684\u5c31\u662f\u659c\u4f53\u6b8b\u7559
pc_STRAY_U = re.compile(r'(?<![\\\w)\]}])_|(?<!\\)_(?![\w{])')
pc_ESCAPE = re.compile(r'\\([\\`*_{}\[\]()#+\-.!<>~=^|])')
pc_MARKERS = re.compile(r'XQ(?:SUB|BUS|SUP|PUS|MATH)[A-Z]*XQ')
pc_INVISIBLE = dict.fromkeys(map(ord, '\u00ad\u200b\u200c\u200d\u2060\ufeff'), None)


def pc_clean_inline(line, table=False):
    """一行作者原文的精简版：去图片、链接只留文字、去粗体斜体、去转义（表格行保留 \\|）。"""
    s = pc_IMG.sub('', line).translate(pc_INVISIBLE)
    s = re.sub(r'</?(?:i|b|em|strong|u|sub|sup)>', '', s)        # 原文里残留的网页格式标签（Elsevier 个别文章有 <i>、<sup>）
    s = pc_SELF_LINK.sub(r'\1', s)
    prev = None
    while prev != s:
        prev, s = s, pc_LINK.sub(r'\1', s)
    # 字面下划线后面紧跟的下划线是斜体开头（OTU100\__Dehalobacterium_ = OTU100_ + 斜体 Dehalobacterium）
    s = re.sub(r'(?<=\\_)_', '', s)
    for _ in range(2):
        s = pc_BOLD.sub(r'\1', s)
        s = pc_ITALIC_U.sub(r'\1', s)
        s = pc_ITALIC_S.sub(r'\1', s)
    # 两层斜体叠在一起写成的 __Morchella esculenta__：字母下标的写法里不会有连续两个下划线，直接去掉
    s = re.sub(r'(?<!\\)_{2,}', '', s)
    s = pc_ITALIC_U.sub(r'\1', s)
    s = pc_STRAY_U.sub('', s)
    if table:
        s = re.sub(r'\\([\\`*_{}\[\]()#+\-.!<>~=^])', r'\1', s)
    else:
        s = re.sub(r'(?<=\S)[ \t]{2,}', ' ', pc_ESCAPE.sub(r'\1', s))
    s = pc_URL_RESIDUE.sub(r'\1', s)
    return s.rstrip()


def pc_is_image_line(line):
    s = line.strip()
    return bool(s) and not pc_IMG.sub('', s).strip() and bool(pc_IMG.search(s))


def pc_is_junk_line(line):
    """图片行、View Large 行，以及清理后一个字都不剩的行（老文章图片没加载出来时只剩空链接 [](/view-large/figure/…tif)）。"""
    s = line.strip()
    return bool(s) and (pc_is_image_line(s) or bool(pc_VIEW.match(s)) or not pc_clean_inline(s).strip())


# ---------------------------------------------------------------- 反读数据 --
pc_COLS = (('系列', '系列'), ('X / 样品', 'X'), ('X 单位', 'X单位'), ('Y / 读数', 'Y'), ('Y 单位', 'Y单位'),
        ('Y轴', 'Y轴'), ('轴倍率', '倍率'), ('误差下限', '误差下限'), ('误差上限', '误差上限'),
        ('显著性', '显著性'), ('入库判定', '判定'))
pc_VERDICT = {'满足数值门槛': '通过', '只有一遍读出': '只有一遍', '需人工复核': '待复核', '不满足入库要求': '不通过'}
pc_BLOCK_HEAD = re.compile(r'^\*\*([图表]) (\S+?)：图像估读数据\*\*')
pc_PANEL_HEAD = re.compile(r'^\*\*(子图|指标) (.+?)\*\*（.*）\s*$')


def pc_cells(line):
    text = line.strip()
    if text.startswith('|'):
        text = text[1:]
    if text.endswith('|') and not text.endswith('\\|'):
        text = text[:-1]
    return [c.strip() for c in re.split(r'(?<!\\)\|', text)]


def pc_simple_table(rows):
    """反读表 → 精简表：只留 COLS 里的列，判定写短，整列为空（倍率全是 1 也算空）的列去掉。"""
    head, body = rows[0], rows[2:]
    picked = [(head.index(src), dst) for src, dst in pc_COLS if src in head]
    out = []
    for r in body:
        vals = []
        for i, dst in picked:
            v = r[i] if i < len(r) else ''
            if dst == '判定':
                v = pc_VERDICT.get(v.strip('*'), v.strip('*'))
            vals.append(v)
        out.append(vals)
    keep = [k for k, (_, dst) in enumerate(picked)
            if any(v[k] not in ('', '1', '×1', 'x1') if dst == '倍率' else v[k] for v in out)]
    lines = ['', '| ' + ' | '.join(picked[k][1] for k in keep) + ' |', '|' + '|'.join('---' for _ in keep) + '|']
    lines += ['| ' + ' | '.join(v[k] for k in keep) + ' |' for v in out]
    return lines, len(body)


def pc_source_rows(text):
    """反读数据.md 里各张反读表的数据行数合计（独立数一遍，核对用；评价一节不算）。"""
    text = text.split('\n## 反读数据评价', 1)[0]
    n = 0
    for m in re.finditer(r'(?m)^(?:\|.*\n?)+', text):
        rows = [l for l in m.group(0).split('\n') if l.startswith('|')]
        if len(rows) >= 2 and re.match(r'^\|[\s:|-]+\|?\s*$', rows[1]):
            n += len(rows) - 2
    return n


pc_AXIS_CN = {'left': '左轴', 'right': '右轴', 'third': '第三轴'}
pc_BARE_LABEL = re.compile(r'^[(（\[]?\s*([A-Za-z]\d*|\d+)\s*[)）\]]?$')
pc_DASH_SAME = dict.fromkeys(map(ord, '‐‑‒–—―−'), '-')


def pc_panel_names(value):
    """子图名的两种比对写法：(原样, 不分大小写)。反读数据.md 表里是「A」，json 里是分类时的「(a)」；
    一张图里 A 和 a 各是一个子图时 md 保留大小写，所以先比原样、再比不分大小写。"""
    if value is None or str(value).strip() in ('', '-'):
        return '-', '-'
    # md 里没编号的子图带说明「未编号1（图上没有编号：line，Y 轴「…」…）」，json 里只有「未编号1」；
    # 破折号写法不同（md「α-La, LT」、json「α–La, LT」）也算同一个
    text = re.sub(r'（图上没有编号.*）$', '', str(value).strip())
    text = ' '.join(unicodedata.normalize('NFKC', text).translate(pc_DASH_SAME).split())
    m = pc_BARE_LABEL.match(text)
    if m:
        return m.group(1), m.group(1).upper()
    return text, text.casefold()


def pc_json_figures(info):
    """反读数据.json → {'Figure 3': {(原样子图名): 子图, ...}}，键和 parse_readback 的块名一致。"""
    out = {}
    for f in (info or {}).get('figures') or []:
        key = re.sub(r'（图片版表格）$', '', (f.get('figure') or '').strip()).strip()
        out[key] = f.get('panels') or []
    return out


def pc_find_panel(panels, name):
    exact, loose = pc_panel_names(name)
    hits = [p for p in panels if pc_panel_names(p.get('panel'))[0] == exact]
    if len(hits) != 1:
        hits = [p for p in panels if pc_panel_names(p.get('panel'))[1] == loose]
    if len(hits) != 1 and exact == '-' and len(panels) == 1:
        hits = panels
    return hits[0] if len(hits) == 1 else None


def pc_plain(text):
    """json 里的轴标题：压成一行，竖线换成斜线（标题行用「｜」分隔）。"""
    return ' '.join(str(text).replace('｜', '/').replace('|', '/').split()) if text else ''


def pc_panel_info(p):
    """子图标题行后面补的部分：｜读图分类：粒径｜X 轴：…｜Y 轴：…｜左轴：…；右轴：…（没有的项不写）。"""
    if not p:
        return ''
    parts = []
    if p.get('property_cn'):
        parts.append('读图分类：%s' % pc_plain(p['property_cn']))
    x = pc_plain(p.get('x_axis_title') or p.get('x_axis_title_read'))
    y = pc_plain(p.get('y_axis_title'))
    if x:
        parts.append('X 轴：%s' % x)
    if y:
        parts.append('Y 轴：%s' % y)
    axes = {}
    for s in p.get('series') or []:
        if s.get('axis_title'):
            axes.setdefault(s.get('axis') or 'left', pc_plain(s['axis_title']))
    if len({s.get('axis') or 'left' for s in p.get('series') or []}) > 1 and axes:
        parts.append('；'.join('%s：%s' % (pc_AXIS_CN.get(a, a), t) for a, t in
                               sorted(axes.items(), key=lambda kv: list(pc_AXIS_CN).index(kv[0]) if kv[0] in pc_AXIS_CN else 9)))
    return ''.join('｜' + x for x in parts)


def pc_parse_readback(text, info=None):
    """反读数据.md → ({'Figure 3': {'caption': 图注, 'lines': 精简块, 'rows': 行数}}, 评价行列表, 总行数)。
    info 是同一文件夹的 反读数据.json：子图标题行补上读图分类和轴标题（对不上的子图照旧只写编号）。"""
    blocks, total = {}, 0
    appendix = []
    figs = pc_json_figures(info)
    for sec in re.split(r'(?m)^## ', text)[1:]:
        head, _, body = sec.partition('\n')
        head = head.strip()
        if head.startswith('反读数据评价'):
            for l in body.split('\n'):
                if l.startswith('<!--'):
                    break
                if l.strip() and l.strip() != '---':
                    appendix.append(pc_clean_inline(l.replace('`', '')))
            continue
        key = re.sub(r'（图片版表格）$', '', head).strip()
        lines = body.split('\n')
        caption = next((l for l in lines if l.strip() and not l.startswith(('!', '**', '*', '|'))), '')
        out, n_rows, label = [], 0, None
        n_panels = n_info = 0
        i = 0
        while i < len(lines):
            m = pc_BLOCK_HEAD.match(lines[i])
            if m:
                label = '%s %s' % (m.group(1), m.group(2))
                out.append('%s 反读数据' % label)
                i += 1
                continue
            m = pc_PANEL_HEAD.match(lines[i])
            if not m and lines[i].startswith(('**子图 ', '**指标 ')):
                # 子图名里带的轴标题本身有换行（jf981098s「Foaming Capacity⏎…」），标题跨了几行：并起来再认
                for k in range(i + 1, min(i + 6, len(lines))):
                    if lines[k].startswith('|') or not lines[k].strip():
                        break
                    joined = ' '.join(x.strip() for x in lines[i:k + 1])
                    m = pc_PANEL_HEAD.match(joined)
                    if m:
                        i = k
                        break
            if m:
                j = i + 1
                while j < len(lines) and not lines[j].startswith('|'):
                    j += 1
                k = j
                while k < len(lines) and lines[k].startswith('|'):
                    k += 1
                rows = [pc_cells(l) for l in lines[j:k]]
                if len(rows) >= 3:
                    extra = pc_panel_info(pc_find_panel(figs.get(key, []), m.group(2)))
                    n_panels += 1
                    n_info += bool(extra)
                    if m.group(2) != '-':
                        out += ['', '%s %s%s' % (m.group(1), pc_clean_inline(m.group(2)), extra)]
                    elif extra:
                        out += ['', '整图' + extra]
                    tl, n = pc_simple_table(rows)
                    out += tl
                    n_rows += n
                i = k
                continue
            i += 1
        if label and n_rows:
            blocks[key] = {'caption': caption.strip(), 'lines': out, 'rows': n_rows,
                           'panels': n_panels, 'panels_info': n_info}
            total += n_rows
    return blocks, appendix, total


# ---------------------------------------------------------------- 一篇 --
pc_LABEL_SHORT = re.compile(r'^(Figure|Scheme|Chart) (\d+[A-Za-z]?)$')
# 图注前的图号：一般是「Figure 2.」，个别文章没有句点（6b00314）；图片前那个不带句点的图号先按 LABEL_SHORT 删掉
pc_LABEL = re.compile(r'^(Figure|Scheme|Chart|Table) (\d+[A-Za-z]?)\.?$')
pc_NUMERIC = re.compile(r'^[-+−]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?$')


def pc_read(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read().replace('\r\n', '\n').replace('\r', '\n').lstrip('\ufeff')


def pc_find_doi(root, name):
    for p in (os.path.join(root, 'figure', 'figure_markdown.md'), os.path.join(root, '反读数据.md')):
        if os.path.exists(p):
            m = re.search(r'(?m)^DOI:\s*(?:https?://(?:dx\.)?doi\.org/)?(10\.\S+?)\s*$', pc_read(p))
            if m:
                return m.group(1)
    return name.replace('_', '/', 1)


def pc_table_numbers(lines):
    return collections.Counter(c for l in lines if l.startswith('|') for c in pc_cells(l) if pc_NUMERIC.match(c))


def pc_merge_paper(root):
    """返回 (合并后的文字 或 None, 记录)。"""
    name = os.path.basename(os.path.normpath(root))
    rec = {'name': name, 'warn': [], 'error': None}
    full = os.path.join(root, '全文.md')
    if not os.path.exists(full):
        rec['error'] = '没有 全文.md'
        return None, rec
    lines = pc_read(full).split('\n')
    rb_path = os.path.join(root, '反读数据.md')
    rb_text = pc_read(rb_path) if os.path.exists(rb_path) else ''
    info = None
    js_path = os.path.join(root, '反读数据.json')
    if os.path.exists(js_path):
        try:
            info = json.loads(pc_read(js_path))
        except ValueError:
            rec['warn'].append('反读数据.json 读不出来，子图标题行没补读图分类和轴标题')
    blocks, appendix, n_rows = pc_parse_readback(rb_text, info)
    rec['rows'] = n_rows
    rec['panels'] = sum(b['panels'] for b in blocks.values())
    rec['panels_info'] = sum(b['panels_info'] for b in blocks.values())
    if rec['panels_info'] < rec['panels']:
        rec['warn'].append('%d 个子图在 反读数据.json 里没对上，标题行只写了编号' % (rec['panels'] - rec['panels_info']))
    if n_rows != pc_source_rows(rb_text):
        rec['error'] = '反读数据.md 里有反读表没认出来（认出 %d 行，表里共 %d 行）' % (n_rows, pc_source_rows(rb_text))
        return None, rec

    pub = pc_publisher_of(root, lines)
    rec['pub'] = pub
    new = pub in pc_NEW_PUBS                        # Wiley、RSC、MDPI、OUP、T&F、Springer Nature（用户 2026-10-30）
    n_formula = 0
    if new:
        lines, n_formula = pc_new_prepare(lines)
    # 1 页头
    if new:
        title, start, why = pc_new_header(lines, pub)
        if start is None:
            rec['error'] = '全文.md 没有一级标题'
            return None, rec
        if why:
            rec['warn'].append(why)
        if not title:
            rec['warn'].append('没找到标题')
    elif pub == 'elsevier':
        title, start = pc_els_header(lines, root)
        if start is None:
            rec['error'] = '全文.md 里找不到正文开头（一级标题之后没有二级标题）'
            return None, rec
        if not title:
            rec['warn'].append('没找到标题')
    else:
        h1 = next((i for i, l in enumerate(lines) if l.startswith('# ')), None)
        if h1 is None:
            rec['error'] = '全文.md 没有一级标题'
            return None, rec
        title = pc_clean_inline(lines[h1][2:].strip())
        start = next((i for i in range(h1 + 1, len(lines)) if re.match(r'^## (?:Visual Abstract|Abstract)\s*$', lines[i])), None)
        if start is None:
            start = next((i for i in range(h1 + 1, len(lines)) if lines[i].startswith('## ')), h1 + 1)
            rec['warn'].append('没有 ## Abstract，从第一个二级标题开始')
    body, dropped, warns = pc_drop_sections(lines[start:], pub)
    rec['dropped'] = dropped
    rec['warn'] += warns
    src_chars = sum(len(pc_clean_inline(l.strip())) for l in lines[start:] if l.strip() and not pc_is_image_line(l))
    rec['formula_images'] = sum(len(re.findall(r'!\[Formula\.', l)) for l in body) + n_formula

    # 2 逐行：图、表、图片、链接、格式
    out, placed, pending_table = [], [], None   # out 里 ('text'|'table'|'block'|'head'|'cap', 内容)

    def put_block(key):
        out.append(('block', key))
        placed.append(key)

    def next_nonempty(i):
        j = i + 1
        while j < len(body) and not body[j].strip():
            j += 1
        return j if j < len(body) else None

    # 块名照抄网页图号，有的是「Fig.」+ 不换行空格 +「8」（ijbiomac.2025.147944）：按任意空白拆
    els_blocks = {pc_els_key(*k.split(None, 1)): k for k in blocks if len(k.split(None, 1)) == 2} if pub == 'elsevier' else {}
    odd_keys = [k for k in blocks if not (pc_ELS_LABEL.match(k) and not pc_ELS_LABEL.match(k).group(3))] if pub == 'elsevier' else []
    new_blocks = collections.OrderedDict()   # 这几家：('Figure', '1') → 反读数据.md 里这张图的块（Wiley 一张图分子图的有几块）
    if new:
        for k in blocks:
            nk = pc_new_block_key(k)
            if nk:
                new_blocks.setdefault(nk, []).append(k)
    skip_next = False
    plain_caps = set()                       # 不以 shows / presents … 开头的图注
    if pub == 'elsevier':
        for x in body:
            mm = pc_ELS_LABEL.match(x.strip())
            if mm and mm.group(3) and not pc_ELS_BODY_VERB.match(mm.group(3)):
                plain_caps.add(pc_els_key(mm.group(1), mm.group(2)))
    i = 0
    while i < len(body):
        line = body[i]
        s = line.strip()
        if not s:
            if out and out[-1][0] == 'table':        # 表格后的空行：两张挨着的表不能拼成一张
                out.append(('gap', None))
            i += 1
            continue
        if new:
            # 其他几家（用户 2026-10-30）：图片按钮行（View large / Download slide、Open in figure viewer / PowerPoint …）删；
            # 摘要后面的「Graphical Abstract」「Issue Section:」「Subject」连同下一行删；图号单独一行（Fig. 1、**FIGURE 1**、
            # Table 1.）的，隔着按钮行的下一段是图注，写成「Figure 1. 图注」；图号和图注同一行的（**Figure 1.** 图注）照原样一行。
            # 反读数据插在图注后面（表的插在表格后面）；其余交给下面的通用处理
            if skip_next:                             # 「Issue Section:」等的下一行（栏目名有的本身是链接）
                skip_next = False
                if not (pc_HEAD.match(s) or pc_new_label(s) or pc_NEW_SKIP_NEXT.match(s)):
                    i += 1
                    continue
            if pc_new_junk(s):
                i += 1
                continue
            if pc_NEW_SKIP_NEXT.match(s):
                skip_next = True
                i += 1
                continue
            lab_ = pc_new_label(s)
            if lab_ or pc_HEAD.match(s):
                if pending_table:
                    for k in pending_table:
                        put_block(k)
                    pending_table = None
            if lab_:
                nk, label, rest = lab_
                if rest:
                    out.append(('text', pc_clean_inline(s)))
                    i += 1
                else:
                    j = i + 1
                    while j < len(body) and (not body[j].strip() or pc_new_junk(body[j].strip())):
                        j += 1
                    nxt = body[j].strip() if j < len(body) else ''
                    if nxt and not (pc_HEAD.match(nxt) or nxt.startswith('|') or pc_new_label(nxt) or pc_NEW_SKIP_NEXT.match(nxt)):
                        out.append(('cap', (label, pc_clean_inline(nxt))))
                        i = j + 1
                    else:
                        out.append(('cap', (label, '')))
                        i += 1
                todo = [k for k in new_blocks.get(nk, []) if k not in placed]
                if nk[0] == 'Table':
                    pending_table = todo or None
                else:
                    for k in todo:
                        put_block(k)
                continue
        elif pub == 'elsevier':
            # Elsevier：图片、下载原图的两行、Highlights 前的「•」、上一篇/下一篇都删；图注和表题跟原文一样写成一行，
            # 反读数据插在图注后面（图片版表格插在表格图片后面）；其余交给下面的通用处理
            if pc_ELS_JUNK.match(s) or pc_is_junk_line(s):
                if pending_table and pc_is_image_line(s):
                    put_block(pending_table)
                    pending_table = None
                i += 1
                continue
            m = pc_ELS_LABEL.match(s)
            if m and m.group(3) and pc_ELS_BODY_VERB.match(m.group(3)) and pc_els_key(m.group(1), m.group(2)) in plain_caps:
                m = None
            key = els_blocks.get(pc_els_key(m.group(1), m.group(2))) if m else None
            if not key:
                # 反读数据.md 的块名是原文图号的怪写法（「Fig. 4:」「Fig. 3.1」「Fig. 12. A」「Fig. 7 -FSH」）：以它开头的那一行是图注
                key = next((k for k in odd_keys if k not in placed and s.startswith(k)), None)
            if pending_table and (pc_HEAD.match(s) or m or key):
                put_block(pending_table)
                pending_table = None
            if m or key:
                out.append(('text', pc_clean_inline(s)))
                i += 1
                if m and not m.group(3):             # 单独一行的「Fig. 5.」：图注在下一段
                    j = next_nonempty(i - 1)
                    nxt = body[j].strip() if j is not None else ''
                    if nxt and not (pc_is_junk_line(nxt) or pc_ELS_JUNK.match(nxt) or nxt.startswith('|') or pc_HEAD.match(nxt)
                                    or pc_ELS_LABEL.match(nxt)):
                        out.append(('text', pc_clean_inline(nxt)))
                        i = j + 1
                if key and key not in placed:
                    if (m.group(1) if m else key).startswith('Table'):
                        pending_table = key
                    else:
                        put_block(key)
                continue
        else:
            if pc_VIEW.match(s):
                if pending_table:
                    put_block(pending_table)
                    pending_table = None
                i += 1
                continue
            if pc_is_junk_line(s):
                i += 1
                continue
            m = pc_LABEL_SHORT.match(s)
            if m:
                j = next_nonempty(i)
                if j is not None and pc_is_junk_line(body[j]):
                    i += 1
                    continue
            if pending_table and (pc_HEAD.match(s) or pc_LABEL.match(s)):
                put_block(pending_table)
                pending_table = None
            m = pc_LABEL.match(s)
            if m:
                kind, num = m.groups()
                key = '%s %s' % (kind, num)
                j = next_nonempty(i)
                nxt = body[j].strip() if j is not None else ''
                if nxt and not (pc_is_junk_line(nxt) or nxt.startswith('|') or pc_HEAD.match(nxt) or pc_LABEL.match(nxt)
                                or pc_LABEL_SHORT.match(nxt)):
                    out.append(('cap', (key, pc_clean_inline(nxt))))
                    i = j + 1
                else:
                    out.append(('cap', (key, '')))
                    i += 1
                if key in blocks and key not in placed:
                    if kind == 'Table':
                        pending_table = key
                    else:
                        put_block(key)
                continue
        if pc_HEAD.match(s):
            out.append(('head', pc_clean_inline(s)))
        elif s.startswith('|') and (pub != 'elsevier' or s.endswith('|')):
            # Elsevier 的表格行都以「|」结尾；以「|」开头而不以它结尾的是正文（缩写表里的「|K∗|,」）
            out.append(('table', pc_clean_inline(s, table=True)))
        else:
            c = pc_clean_inline(s)
            if pub == 'elsevier':
                c = pc_ELS_BULLET.sub('', c)
            if c.strip():
                out.append(('text', c))
        i += 1
    if pending_table:
        for k in (pending_table if isinstance(pending_table, list) else [pending_table]):
            put_block(k)

    # 3 缩写表：一行一条「缩写: 全称」（Elsevier 先去掉关键词和缩写表里单独一行的「;」，关键词并成一行）
    if pub == 'elsevier':
        out = pc_els_lists(out)
    out = pc_pair_abbreviations(out, pc_ELS_ABBR if pub == 'elsevier' or new else None)
    # 4 空标题删掉（后面紧跟同级或更高级标题，或文末）
    out = pc_drop_empty_headings(out)

    # 5 拼文字
    parts = ['# ' + title, '', 'DOI: ' + pc_find_doi(root, name), '']
    prev_kind = None
    for kind, val in out:
        if kind == 'gap':
            parts.append('')
        elif kind == 'table':
            if prev_kind != 'table':
                parts.append('')
            parts.append(val)
        elif kind == 'block':
            parts += [''] + blocks[val]['lines']
        elif kind == 'cap':
            key, cap = val
            parts += ['', ('%s. %s' % (key, cap)).strip()]
        elif kind == 'abbr':
            parts += ['', '%s: %s' % val]
        elif kind == 'kw':
            parts += ['', '; '.join(val)]
        else:
            parts += ['', val]
        prev_kind = kind
    missing = [k for k in blocks if k not in placed]
    for key in missing:                          # 全文里没找到这张图的图注：用反读数据.md 里的作者图注，附在文末
        cap = blocks[key]['caption']
        cap = re.sub(r'^%s\.?\s*' % re.escape(key), '', cap)
        parts += ['', ('%s. %s' % (key, pc_clean_inline(cap))).strip(), ''] + blocks[key]['lines']
        rec['warn'].append('%s 在全文里没找到图注，附在文末' % key)
    if appendix:
        parts += ['', '## 反读数据评价', ''] + appendix
    text = re.sub(r'\n{3,}', '\n\n', '\n'.join(parts)).strip() + '\n'

    # 6 核对
    err = pc_check(text, body, blocks, out)
    if err:
        rec['error'] = err
        return None, rec
    kept = sum(len(v) if isinstance(v, str) else len(' '.join(x for x in v if x)) for k, v in out
               if k in ('text', 'head', 'table', 'cap', 'abbr', 'kw'))
    if src_chars and kept < 0.5 * src_chars:
        rec['warn'].append('合并后正文只剩原文正文的 %.0f%%，请抽查' % (kept / src_chars * 100))
    rec['placed'] = len(placed)
    rec['blocks'] = len(blocks)
    rec['chars_in'] = sum(len(l) + 1 for l in lines)
    rec['chars_out'] = len(text)
    return text, rec


pc_ABBR_TERM = re.compile(r'^\S.{0,40}$')


def pc_pair_abbreviations(out, extra=None):
    """缩写表里一行缩写、一行全称交替排的，并成「缩写: 全称」。排法不是这样的照原样。
    extra：另外也算缩写表的标题写法（Elsevier 传 ELS_ABBR；ACS 不传，照原样）。"""
    res, i = [], 0
    while i < len(out):
        kind, val = out[i]
        res.append(out[i])
        i += 1
        if kind != 'head' or not (pc_KEEP_SECTIONS.match(pc_heading_text(val)) or (extra and extra.match(pc_heading_text(val)))):
            continue
        j = i
        while j < len(out) and out[j][0] == 'text':
            j += 1
        items = [v for _, v in out[i:j]]
        if len(items) >= 2 and len(items) % 2 == 0 and all(pc_ABBR_TERM.match(t) for t in items[0::2]):
            res += [('abbr', (a, b)) for a, b in zip(items[0::2], items[1::2])]
            i = j
    return res


def pc_drop_empty_headings(out):
    """删因为删节、删图而变空的标题：后面紧跟更高一级的标题，或者已经到文末。
    后面紧跟同级标题的不删——那多半是原文自带的空标题（8b02183「### Materials and Methods」下面直接是「### Materials」），
    留着它，章节结构才不丢。"""
    res = []
    for k, (kind, val) in enumerate(out):
        if kind == 'head':
            level = len(pc_HEAD.match(val).group(1))
            nxt = next((x for x in out[k + 1:] if x[0] != 'gap'), None)
            if nxt is None or (nxt[0] == 'head' and len(pc_HEAD.match(nxt[1]).group(1)) < level):
                continue
        res.append((kind, val))
    return res


def pc_check(text, body, blocks, out):
    """核对，返回错误说明或 None。"""
    # 反读表每一块都整块插进去了，行数和反读数据.md 一样
    for key, b in blocks.items():
        if '\n'.join(b['lines']) not in text:
            return '%s 的反读表没有整块插进去' % key
        n = sum(1 for l in b['lines'] if l.startswith('|')) - 2 * sum(1 for l in b['lines'] if l.startswith('|---'))
        if n != b['rows']:
            return '%s 的反读表行数对不上（%d / %d）' % (key, n, b['rows'])
    block_lines = {l for b in blocks.values() for l in b['lines']}
    author = [l for l in text.split('\n') if l not in block_lines]
    # 作者表格里的数字一个不少
    src_tables = [pc_clean_inline(l.strip(), table=True) for l in body if l.strip().startswith('|')]
    if pc_table_numbers(src_tables) != pc_table_numbers([l for l in author if l.startswith('|')]):
        return '作者表格里的数字前后对不上'
    # 不剩图片、链接、标记。图片要整个「![…](」才算：公式里阶乘后面跟方括号「M![f_…]」不算（用户 2026-11-05，3 篇 SHAP 公式）；
    # 引用号后面紧跟原文括号里的网址「[39](http://…)」不算链接（原文「[\[39\]](#BIB39)(http://…)」，s0141-8130(98)00015-4）
    joined = '\n'.join(author)
    for what, rx in (('图片', r'!\[[^\]\n]*\]\('), ('链接', r'\]\((?:https?:|/|#|javascript:)'), ('上下标或公式标记', pc_MARKERS.pattern),
                     ('[View Large]', r'\[View Large\]')):
        for m in re.finditer(rx, joined):
            if what == '链接' and re.search(r'\[\d+(?:[,–-]\d+)*$', joined[max(0, m.start() - 20):m.start()]):
                continue
            return '还剩%s' % what
    # 留下的作者原文都能在原文件里找到
    src = {pc_clean_inline(l.strip()) for l in body if l.strip()} | {pc_clean_inline(l.strip(), table=True) for l in body}
    src |= {pc_ELS_BULLET.sub('', x) for x in src if pc_ELS_BULLET.match(x)}       # Elsevier Highlights 去掉了「- •」
    for kind, val in out:
        if kind == 'cap':
            if val[1] and val[1] not in src:
                return '图注对不上原文：%s' % val[1][:60]
        elif kind == 'abbr':
            if not pc_in_src(val[0], src) or not pc_in_src(val[1], src):
                return '缩写表对不上原文：%s' % val[0][:40]
        elif kind == 'kw':
            bad = next((x for x in val if not pc_in_src(x, src)), None)
            if bad is not None:
                return '关键词对不上原文：%s' % bad[:40]
        elif kind in ('text', 'head', 'table'):
            if not pc_in_src(val, src):
                return '有一段不是原文：%s' % val[:60]
    return None


def pc_in_src(val, src):
    """这段在原文里：原样，或者原文多一两个分隔符（Elsevier 缩写表「YFWM,」、关键词「Crab;」去掉了逗号分号；
    个别缩写表原文多写一个逗号「SOD,,」「**EF,**,」，用户 2026-11-05）。"""
    return val in src or any(val + sep in src or val + sep + sep in src for sep in pc_LIST_SEPARATOR)


# ---------------------------------------------------------------- 批量 --
def pc_atomic_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.merge-', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def pc_has_points(root):
    p = os.path.join(root, '反读数据.md')
    return os.path.exists(p) and '图像估读数据' in pc_read(p)


def pc_all_papers(root):
    """总文件夹里的全部文章文件夹（有 全文.md 的；_records、database 不算）。"""
    base = pc_papers_dir(root)
    return [p for p in sorted(glob.glob(os.path.join(base, '*')))
            if os.path.isdir(p) and os.path.exists(os.path.join(p, '全文.md'))]


def pc_pick(args):
    roots = []
    for x in args.papers:
        p = x if os.path.isdir(x) else os.path.join(pc_papers_dir(args.root), x)
        if not os.path.isdir(p):
            raise SystemExit('找不到文章文件夹：%s' % x)
        roots.append(p)
    if args.sample:
        pool = [p for p in pc_all_papers(args.root) if pc_has_points(p)]
        roots += random.Random(pc_SAMPLE_SEED).sample(pool, min(args.sample, len(pool)))
    if not roots:
        roots = pc_all_papers(args.root)
    roots = list(dict.fromkeys(roots))
    return roots[:args.limit] if args.limit else roots


def pc_main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass
    ap = argparse.ArgumentParser(description='全文.md + 反读数据.md → 合并、精简后的全文（纯规则，不调用模型）')
    ap.add_argument('papers', nargs='*', help='文章文件夹名或路径；不给就是 --root 下全部')
    ap.add_argument('--root', default=pc_ROOT, help='总文件夹（文章在 <root>\\papers\\<文章>，没有 papers 子文件夹时直接在 <root> 下），'
                                                 '默认 %s；每篇写 全文合并.md，报告写 <root>\\_records\\全文合并' % pc_ROOT)
    ap.add_argument('--sample', type=int, default=0, help='从有反读数据的文章里固定抽 N 篇')
    ap.add_argument('--limit', type=int, default=0, help='最多处理 N 篇')
    args = ap.parse_args(argv)
    if not os.path.isdir(args.root):
        raise SystemExit('找不到总文件夹：%s' % args.root)
    roots = pc_pick(args)
    t0 = time.time()
    recs, ok = [], 0
    for k, root in enumerate(roots, 1):
        try:
            text, rec = pc_merge_paper(root)
        except Exception as e:                       # 一篇出意外不影响别的篇，记进报告
            text, rec = None, {'name': os.path.basename(root), 'warn': [], 'error': '脚本出错：%r' % e}
        if text is not None:
            pc_atomic_write(os.path.join(root, pc_MERGED_NAME), text)
            ok += 1
        recs.append(rec)
        if k % 500 == 0:
            print('  %d / %d' % (k, len(roots)), flush=True)
    report = os.path.join(args.root, pc_RECORDS_SUBDIR, pc_STEP_DIR, pc_REPORT_NAME)
    pc_write_report(recs, args, time.time() - t0, report)
    bad = [r for r in recs if r['error']]
    print('合并 %d 篇：写出 %d 篇，没写 %d 篇，有提醒 %d 篇（%.0f 秒）-> 每篇文件夹里的 %s'
          % (len(recs), ok, len(bad), sum(1 for r in recs if r['warn']), time.time() - t0, pc_MERGED_NAME))
    print('报告：%s' % report)
    return 1 if bad else 0


def pc_write_report(recs, args, seconds, report):
    done = [r for r in recs if not r['error']]
    lines = ['# 合并报告', '',
             '时间：%s；文章 %s（每篇写 %s）；%d 篇，写出 %d 篇，用时 %.0f 秒。' % (
                 time.strftime('%Y-%m-%d %H:%M'), pc_papers_dir(args.root), pc_MERGED_NAME, len(recs), len(done), seconds), '']
    if done:
        cin = sum(r.get('chars_in', 0) for r in done)
        cout = sum(r.get('chars_out', 0) for r in done)
        pubs = collections.Counter(r.get('pub', 'acs') for r in done)
        lines += ['- 出版商：ACS %d 篇，Elsevier %d 篇' % (pubs['acs'], pubs['elsevier']) +
                  ''.join('，%s %d 篇' % (name, pubs[k]) for k, name in pc_NEW_NAMES if pubs[k]),
                  '- 字数：原文 %d → 合并后 %d（%.0f%%）' % (cin, cout, cout / cin * 100 if cin else 0),
                  '- 反读数据：%d 块插进图注后面，%d 块没找到图注附在文末，反读表 %d 行' % (
                      sum(r.get('placed', 0) for r in done), sum(r.get('blocks', 0) - r.get('placed', 0) for r in done),
                      sum(r.get('rows', 0) for r in done)),
                  '- 子图标题行补上读图分类和轴标题：%d / %d 个子图' % (
                      sum(r.get('panels_info', 0) for r in done), sum(r.get('panels', 0) for r in done)),
                  '- 删掉的公式图片：%d 处（%d 篇）' % (sum(r.get('formula_images', 0) for r in done),
                                              sum(1 for r in done if r.get('formula_images')))]
        dropped = collections.Counter(d for r in done for d in r.get('dropped', []))
        lines += ['- 删掉的节：' + '，'.join('%s %d' % (k, v) for k, v in dropped.most_common())]
    bad = [r for r in recs if r['error']]
    if bad:
        lines += ['', '## 没写出的（%d 篇）' % len(bad), '']
        lines += ['- %s：%s' % (r['name'], r['error']) for r in bad]
    warn = [r for r in recs if r['warn'] and not r['error']]
    if warn:
        lines += ['', '## 有提醒的（%d 篇）' % len(warn), '']
        lines += ['- %s：%s' % (r['name'], '；'.join(r['warn'])) for r in warn]
    pc_atomic_write(report, '\n'.join(lines) + '\n')


# ====================================================================================================
# 数据点提取（原 extract_datapoint\extract_datapoint.py）
# ====================================================================================================
r"""
extract_datapoint.py —— 全文合并 markdown → 建库数据点（第四步）

    python extract_datapoint.py --sample 20                # 固定抽 20 篇试跑（调模型，花钱）
    python extract_datapoint.py 10.1021_acs.jafc.0c00128   # 指定文章（文章名或合并稿路径，可以多个）
    python extract_datapoint.py --dry-run --sample 20      # 只写出要发给模型的文字，不调模型、不花钱
    python extract_datapoint.py --build-only               # 不调模型，用已有的模型回答重新生成 markdown
    python extract_datapoint.py                            # 全部 7375 篇（花钱，先问用户）
    python extract_datapoint.py --only-with-data           # 只发有反读表、或作者表格提到 17 项的（原来的筛法，约 2508 篇）
    python extract_datapoint.py --model anthropic/claude-sonnet-5.5 --sample 20   # 换模型测试

文件夹结构（用户 2026-10-21 定，和 D:\acs_papers_done 一致；--root 换总文件夹，没有 papers 子文件夹的文章直接放在 <root> 下）：
    <root>\papers\<文章名>\全文合并.md        输入（paper_clean.py 写的合并稿，只读）
    <root>\papers\<文章名>\method.json        extract_method.py 写的测定方法（有的文章在 datapoint.md 里写上方法）
    <root>\papers\<文章名>\datapoint.md       输出（用户 2026-10-13 晚定：每篇文章单独一个文件、不合并；格式统一，方便以后建库）：
                                              # 论文题目、DOI，然后一张表——一列一个样品（样品1、样品2…），
                                              行固定：样品名称…体系（组成、处理条件）+ 17 项性质；格式见 _格式说明.md
    <root>\_records\数据点\_格式说明.md、_提取报告.md、_待重读.md
    <root>\_records\数据点\_模型输出\<模型名>\<文章名>.json   模型回答缓存（带输入指纹，只看文字、不看路径）；
                                              只改输出格式不用重新问模型（--build-only）
模型不写死（用户 2026-10-13：后面要测不同模型的效果）：--model 换模型；默认模型以外的结果（<文章名>_datapoint.md 和报告）放
<root>\_records\数据点\_模型对比\<模型名>\，不覆盖正式结果，可以拿同一批文章对比。走 OpenRouter 时默认只用模型自己那一家
（google/ → Google 的 flex 档 google-ai-studio/flex、google-vertex/global/flex，openai/ → openai…），--provider 可改；--base-url openai = OpenAI 直连。

输入只有合并稿（paper_clean.py 的产物，只读）：反读表在图注后面，子图标题行带读图分类和轴标题；作者表格在原位。
用户 2026-10-13 定的口径：
  - 数据点取实验结果：图 = 合并稿里的反读表；表 = 作者表格的单元格；正文 = 正文里写明的数值（10-13 晚用户加：
    原定不取正文句子里的数，后改为要取）
  - 只要 17 项指标（与读图同一份定义，直接取 figure_reader.py 里的）；反读表全部行都用，不写判定标签
    （用户 10-13 晚：「数据全部可以用」）
  - 不同处理、不同条件下的数值要和样品、条件严格一一对应，不可乱匹配；样品写全构成（蛋白来源和类别、形态、浓度、
    复配物及用量）和处理（逐步写方法、物理法 / 化学法 / 生物法、温度、pH、时间等全部参数）
  - 样品和条件从原文的方法、图注、结果里找，用 gemini-3.8-flash（OpenRouter）每篇一次；一遍，每条附原文句子，代码核对
  - 输出每篇一个 markdown（原定 CSV，用户随后改）；10-13 晚定最终形式：每篇单独一张表，最上面论文题目和 DOI，
    一列一个样品，行 = 样品组成、处理条件、17 项性质（格里写详细数值），所有文章格式统一（见 out\\_格式说明.md）
做法：
  1 数值一律由代码从反读表、作者表格单元格里搬，模型不写任何读数；发给模型的全文里反读表只留编号、系列名和 X 取值，
    作者表格加行号 r1…、列号 c1…
  2 模型按编号回答：样品清单；每个图面板的每个系列属于 17 项里的哪一项、每个点（系列 × X）对应哪个样品、什么条件；
    每张表哪几行（列）是 17 项指标、哪几列（行）是哪个样品。图和表可以结合上下文推断（用户 10-13：能推断对上的也算），
    完全找不到依据的写进 unresolved；正文数值必须原句明确点名样品（用户 10-13：没有明确指向的、模糊的不用）
  3 代码逐点核对：恰好对应一个样品才算「已对应」，否则「条件未确定」或「对应冲突」；原文句子要在原文里找得到；
    表格行列编号要和那一行（列）的表头对得上；系列指标按读图分类（单纵轴）或模型判断（双纵轴）定，
    再按 figure_reader 现行的不读规则（质构、力学性能、溶胀率、分布曲线、扫描曲线…）筛，筛掉的列在「排除的点」一节
  4 一一对应硬核对：同一个面板（同一组表格）里，同一样品、同一指标、同一组条件下出现两个数 → 全部判「对应冲突」
    （jf020952j：表里 1 h / 48 h / 96 h 三行，模型没写储藏时间，三个数分不开）
  5 模型回答存在 _records\数据点\_模型输出\<模型名>\<文章>.json（带输入指纹）：输入没变就不重问、不重花钱；
    输入或提示词变了旧回答作废
"""


# 用户 2026-10-21：各步脚本都按 D:\acs_papers_done 的结构（papers\<文章>\、_records\、database\）；默认输入是
# D:\2.elsevier_papers（文章直接放在它下面），ACS 用 --root D:\acs_papers_done
# （原来的 D:\acs_papers_全文合并-已齐全 全部完成 → D:\acs_papers_数据点 已经不在了）
ed_ROOT = r'D:\2.elsevier_papers'   # 用户 2026-10-30 把 Elsevier 总文件夹改名为 2.elsevier_papers
ed_PAPERS_SUBDIR = 'papers'                # <root>\papers\<文章>\；没有这个子文件夹的总文件夹，文章直接放在 <root> 下
ed_RECORDS_SUBDIR = '_records'
ed_STEP_DIR = '数据点'                      # 报告、格式说明、待重读、模型回答缓存：<root>\_records\数据点\
ed_MERGED_NAME = '全文合并.md'              # 输入：paper_clean.py 写在每篇文件夹里的合并稿
ed_DATAPOINT_NAME = 'datapoint.md'          # 输出：每篇文件夹里一个
ed_METHOD_NAME = 'method.json'              # extract_method.py 写在每篇文件夹里的测定方法
ed_REREAD_NAME = '_待重读.md'

ed_MODEL = 'google/gemini-3.8-flash'      # 默认模型；--model 换
ed_KEY_ENV = 'OPENROUTER_API_KEY'
# 走 OpenRouter 时每个模型只用自己那一家（和读图脚本同一做法）；没列的前缀不限定。gemini 走 Google 的 flex 档（用户 2026-10-14：
# 同一个模型，价格是标准档的一半；排队、单个请求慢一些，偶尔排满报 502/503 照常等着重试）；AI Studio 和 Vertex 的 flex 同价，
# 两家都列上，一家排满走另一家（与读图脚本的 OPENROUTER_PROVIDER 相同）
ed_PROVIDERS = {'google': 'google-ai-studio/flex,google-vertex/global/flex', 'openai': 'openai', 'anthropic': 'anthropic', 'x-ai': 'xai',
             'deepseek': 'deepseek', 'qwen': 'alibaba', 'mistralai': 'mistral'}
ed_WORKERS = 4
ed_SAMPLE_SEED = 20261013
ed_CACHE_DIR = '_模型输出'                 # 模型回答缓存：_records\数据点\_模型输出\<模型名>\<文章>.json
ed_COMPARE_DIR = '_模型对比'               # 换别的模型测试时，markdown 放 _records\数据点\_模型对比\<模型名>，不覆盖正式结果
ed_PREVIEW_DIR = '_发给模型的文字'
ed_REPORT_NAME = '_提取报告.md'
# extract_method.py 核对过的每篇测定方法（用户 2026-10-19：提取方法后 datapoint.md 要体现对应的方法）；没有这篇的文件就不写方法。
# None = 每篇文件夹里的 method.json（用户 2026-10-21）；给了目录就读 <目录>\<文章名>.json（老结构）
ed_METHOD_DIR = None


def ed_papers_dir(root):
    """放文章文件夹的地方：<root>\\papers；没有 papers 子文件夹的总文件夹（如 D:\\2.elsevier_papers）就是 <root> 本身。"""
    sub = os.path.join(root, ed_PAPERS_SUBDIR)
    return sub if os.path.isdir(sub) else root


def ed_records_dir(root, step=ed_STEP_DIR):
    return os.path.join(root, ed_RECORDS_SUBDIR, step)


def ed_merged_path(root, article):
    return os.path.join(ed_papers_dir(root), article, ed_MERGED_NAME)


def ed_article_of(path):
    """合并稿路径 → 文章名：<文章名>\\全文合并.md 取文件夹名（老结构的 <文章名>.md 取文件名）。"""
    if os.path.basename(path) == ed_MERGED_NAME:
        return os.path.basename(os.path.dirname(os.path.abspath(path)))
    return os.path.splitext(os.path.basename(path))[0]


ed_PAPERS = ed_papers_dir(ed_ROOT)                # 这次处理的文章文件夹的上级（main 里按 --root 改）


ed_CODE_OF_CN = {v: k for k, v in FUNCTIONAL.items()}
ed__s = SYSTEM
ed_DEFS = ed__s[ed__s.index('- solubility'):ed__s.index('二、能不能反读')].strip()   # 17 项定义和不读的情形，与读图分类逐字相同
# 「是不是蛋白质体系」的标准，与读图分类判 protein_system 逐字相同（用户 2026-10-13：不含蛋白质的样品不收）
ed_PROTEIN_DEF = ed__s[ed__s.index('1. protein_system：') + len('1. protein_system：'):ed__s.index('2. functional_property')].strip()

# ================================================================ 模型回答的结构 ==

ed_Property17 = Literal[tuple(FUNCTIONAL)]


class Param(BaseModel):
    name: str = Field(description='参数名。常用的写标准名：temperature、time、pH、ionic strength、concentration、ratio、'
                                  'power、frequency、amplitude、pressure、cycles、speed、enzyme、enzyme dosage、reagent、'
                                  'reagent concentration、storage time；其他照抄原文')
    value: str = Field(description='数值，照抄原文写法，如 "90"、"4–6"、"1:2"')
    unit: Optional[str] = Field(description='单位，照抄原文；没有单位填 null')
ed_Param = Param                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class Ingredient(BaseModel):
    name: str = Field(description='成分名称，照抄原文')
    category: Literal['多糖', '多酚', '油脂', '其他蛋白', '肽', '糖', '盐或离子', '表面活性剂或乳化剂', '交联剂',
                      '活性物质', '其他'] = Field(description='成分类别')
    amount: Optional[str] = Field(description='浓度、添加量或与蛋白的比例，照抄原文（连单位）；原文没写填 null')
ed_Ingredient = Ingredient                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class Step(BaseModel):
    method: str = Field(description='处理方法，照抄原文说法（如 ultrasound treatment、heating、pH-shifting、'
                                    'glycation with dextran、Alcalase hydrolysis、high-pressure homogenization）')
    category: Literal['物理法', '化学法', '生物法', '复合法', '其他'] = Field(description='方法类别')
    params: List[ed_Param] = Field(description='这一步的全部参数（温度、时间、pH、功率、频率、压力、次数、酶和加酶量、'
                                            '试剂和浓度、比例…）；原文没写参数填空列表')
ed_Step = Step                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class Sample(BaseModel):
    sample_id: str = Field(description='样品编号：S1、S2、S3…')
    labels: List[str] = Field(description='这个样品在图、表、图注、正文里用到的名字或缩写，逐字照抄（图里的系列名、X 取值、'
                                           '表里的行列名都要列上）')
    description: str = Field(description='一句话说明这个样品是什么，用原文措辞')
    contains_protein: bool = Field(description='这个样品算不算蛋白质体系（标准见第一节）；不含蛋白质的填 false，'
                                               '它的数值程序不收')
    protein_source: Optional[str] = Field(description='蛋白质来源，照抄原文（如 soybean、pea、whey、egg white、rapeseed）')
    protein_category: Literal['植物蛋白', '乳蛋白', '蛋类蛋白', '肉类或水产蛋白', '其他动物蛋白', '微生物蛋白',
                              '藻类蛋白', '昆虫蛋白', '多种来源', '不明'] = Field(description='蛋白质类别')
    protein_form: Optional[str] = Field(description='蛋白质形态或组分，照抄原文（如 protein isolate、concentrate、'
                                                    '7S globulin、β-lactoglobulin、hydrolysate、flour）')
    protein_concentration: Optional[str] = Field(description='样品里蛋白质的浓度或用量，照抄原文（连单位）；原文没写填 null')
    ingredients: List[ed_Ingredient] = Field(description='和蛋白质一起构成样品的复配物和其他成分（多糖、多酚、油相、盐、糖、'
                                                      '表面活性剂…）；没有填空列表')
    processing: List[ed_Step] = Field(description='样品经过的处理，按先后顺序；未处理的对照填空列表')
    system: Literal['溶液或分散液', '乳液', '泡沫', '凝胶', '颗粒或纳米颗粒', '复合物', '膜', '粉末或固体', '其他',
                    '不明'] = Field(description='测定时样品的体系形态')
    evidence: List[str] = Field(description='原文里描述这个样品构成和处理的句子，逐字照抄（每条一段连续原文，不加省略号、'
                                             '不改写、不翻译）')
ed_Sample = Sample                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class SeriesNote(BaseModel):
    series_id: str = Field(description='系列编号，如 F2.p1.s1')
    property: Property = Field(description='这个系列属于 17 项里的哪一项（按它所在那条纵轴判）；不在 17 项里填 none')
    measure: Optional[str] = Field(description='测的是什么，照抄轴标题或原文说法')
ed_SeriesNote = SeriesNote                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class Assignment(BaseModel):
    series_id: str = Field(description='系列编号；写 * 表示本面板全部系列')
    x: str = Field(description='X 取值，照抄清单里的写法；写 * 表示全部 X')
    sample_id: Optional[str] = Field(description='对应的样品编号；这条只补充条件、不指定样品时填 null')
    conditions: List[ed_Param] = Field(description='这条对应关系附带的条件（例如系列名是 pH 3 → pH=3）；没有填空列表')
ed_Assignment = Assignment                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class PanelNote(BaseModel):
    panel_id: str = Field(description='面板编号，如 F2.p1')
    series: List[ed_SeriesNote] = Field(description='面板里每个系列一条，一个都不能漏')
    x_role: Literal['条件', '样品', '无'] = Field(description='X 是条件取值（pH、时间、温度、浓度…）写「条件」；'
                                                         'X 是样品名写「样品」；没有 X 写「无」')
    x_variable: Optional[str] = Field(description='X 是条件时，条件的名称（如 pH、storage time、NaCl concentration）；否则 null')
    x_variable_unit: Optional[str] = Field(description='X 条件的单位；没有填 null')
    measurement_conditions: List[ed_Param] = Field(description='这个面板所有点共同的测定条件（测定时的蛋白浓度、pH、温度、'
                                                            '储藏时间…）；已写进样品处理的不要重复')
    assignments: List[ed_Assignment] = Field(description='每个点（系列 × X）对应哪个样品')
    evidence: List[str] = Field(description='说明这个面板的图注片段或正文句子，逐字照抄')
ed_PanelNote = PanelNote                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class MeasureLine(BaseModel):
    line: str = Field(description='17 项指标所在的行号或列号，如 r5、c3')
    property: ed_Property17 = Field(description='属于 17 项里的哪一项')
    measure: str = Field(description='这一行（列）的表头，照抄')
    unit: Optional[str] = Field(description='单位，照抄表头或表注；没有填 null')
    conditions: List[ed_Param] = Field(description='这一行（列）附带的条件（如表头 solubility at pH 3 → pH=3）；没有填空列表')
    part: Optional[int] = Field(description='格子里并列写了几个数（如「3.63−6.81」，表注说左边 0 h、右边 24 h）时取第几个'
                                            '（1 起算），各自的条件写进 conditions；格子里只有一个数填 null')
ed_MeasureLine = MeasureLine                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class SampleLine(BaseModel):
    line: str = Field(description='样品所在的行号或列号，如 c2、r4（和指标方向垂直）')
    sample_id: str = Field(description='对应的样品编号')
    conditions: List[ed_Param] = Field(description='这一行（列）附带的条件；没有填空列表')
    only_lines: List[str] = Field(description='同一行（列）在不同的指标列（行）属于不同样品时，这个样品只管哪几个指标行列'
                                              '（如 ["c2", "c3"]）；整行（列）都是这个样品的填空列表')
ed_SampleLine = SampleLine                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class CellNote(BaseModel):
    cell: str = Field(description='格子编号，如 r3.c4')
    part: Optional[int] = Field(description='格子里并列写了几个数时取第几个（1 起算）；只有一个数填 null')
    sample_id: str = Field(description='这一格属于哪个样品')
    property: ed_Property17 = Field(description='属于 17 项里的哪一项')
    measure: str = Field(description='测的是什么，照抄这一格所在行或列的表头')
    unit: Optional[str] = Field(description='单位，照抄表头或表注；没有填 null')
    conditions: List[ed_Param] = Field(description='这一格的测定条件（如贮藏 30 天、4 °C）；没有填空列表')
ed_CellNote = CellNote                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class TableNote(BaseModel):
    table_id: str = Field(description='表格编号，如 T1')
    measures: List[ed_MeasureLine] = Field(description='表里属于 17 项的每一行或每一列')
    sample_lines: List[ed_SampleLine] = Field(description='每个样品所在的行或列')
    cells: List[ed_CellNote] = Field(description='表格不是「一边样品、一边指标」时逐格写（见第三节）；'
                                             '能用 measures × sample_lines 表达的填空列表')
    evidence: List[str] = Field(description='表题或表注里说明样品、条件的句子，逐字照抄')
ed_TableNote = TableNote                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class TextValue(BaseModel):
    sample_id: str = Field(description='这个数值属于哪个样品')
    sample_mention: str = Field(description='原句里点名这个样品的词，逐字照抄，要能单独区分出这个样品（样品名称或缩写、'
                                            '区分样品的处理参数如 2.5 MPa、4 h，或 control、untreated 这类明确说法）；'
                                            '分在原句几处的用 … 连起来')
    property: ed_Property17 = Field(description='属于 17 项里的哪一项')
    measure: str = Field(description='测的是什么，照抄原文说法（如 EAI、solubility、DH、particle size）')
    value: str = Field(description='数值，逐字照抄原句里的数字（如 "26.70"），只写一个数')
    sd: Optional[str] = Field(description='原句里紧跟在 ± 后面的标准差，照抄；没有填 null')
    unit: Optional[str] = Field(description='单位，照抄原句；没有填 null')
    conditions: List[ed_Param] = Field(description='测定条件（测定时的 pH、温度、储藏时间…）；没有填空列表')
    quote: str = Field(description='含这个数值的那一句原文，逐字照抄，不加省略号')
ed_TextValue = TextValue                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class Unresolved(BaseModel):
    item_id: str = Field(description='判断不了的编号：面板 F2.p1、系列 F2.p1.s3、表格 T1 或表格的一行一列 T1.r5')
    reason: str = Field(description='为什么判断不了')
ed_Unresolved = Unresolved                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class PaperNote(BaseModel):
    samples: List[ed_Sample] = Field(description='样品清单')
    panels: List[ed_PanelNote] = Field(description='每个图面板一条，一个都不能漏')
    tables: List[ed_TableNote] = Field(description='含 17 项指标的作者表格，每张一条；不含的不列')
    text_values: List[ed_TextValue] = Field(description='正文里写明的、本研究某个样品的 17 项数值；没有填空列表')
    unresolved: List[ed_Unresolved] = Field(description='判断不了的编号和原因；没有填空列表')
ed_PaperNote = PaperNote                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


ed_SYSTEM = """你是食品蛋白质论文的数据整理员。论文里图和表上的数值已经由程序取好（图的数值是读图得到的，表的数值是作者原值），
你**不写**图和表的数值，而是给每个数据点找到它对应的**样品**（构成和处理）和**条件**；正文里写明的数值由你照抄出来
（第四节），程序会逐条核对。要求严格一一对应：图和表可以结合上下文推断，完全找不到依据的如实说判断不了；
正文数值必须原句明确点名样品。

一、样品清单 samples
- 一个样品 = 一种具体的材料：蛋白质来源、类别、形态、浓度 + 复配物及用量 + 经过的全部处理及参数。同一种蛋白经过不同的处理、
  不同的处理参数（如超声 10 min 和 20 min）、不同的复配比例，都是不同的样品；未处理的对照也是一个样品。
- 只列图、表、正文数值用到的样品。
- contains_protein：这个样品算不算蛋白质体系，标准与读图时相同——是不是蛋白质，{protein_def}
  不含蛋白质的样品（如只用淀粉、阿拉伯胶、Tween 做的乳液或微胶囊对照）也照样列出、填 false，程序不收它的数值。
- 从原文里找全：材料与方法里的样品制备、图注、表注、结果描述、缩写表（缩写常在摘要、引言或缩写表里定义）。
  名称、数值、单位一律照抄原文写法（英文就写英文），不翻译、不换算；原文没写的填 null 或空列表。
- processing 只放改变样品本身的处理（提取、纯化、加热、超声、高压、微波、pH 偏移、酶解、发酵、糖基化、交联、复合、
  制备乳液或凝胶…），按先后顺序；每一步写方法名、类别和全部参数（温度、时间、pH、功率、频率、压力、次数、酶和加酶量、
  试剂和浓度、比例…）。类别：物理法（热、超声、高压、微波、辐照、冷等离子体、球磨、均质、冻融、冻干…）；化学法（酸碱或 pH 偏移、
  糖基化 / 美拉德、磷酸化、酰化、氧化、还原、化学交联…）；生物法（酶解、酶交联如转谷氨酰胺酶、发酵…）；
  一步里同时用了几类写复合法。
- ingredients 是和蛋白质一起构成样品的其他成分（多糖、多酚、油相、盐、糖、表面活性剂…），写名称、类别、浓度或比例。
- evidence 照抄原文里描述这个样品构成和处理的句子：每条是一段连续的原文，逐字照抄，不加省略号，不改写。程序会逐条核对。

二、图：每个面板都要标注（panels）
- 全文里「［图 N 读图结果的编号清单（读数已略去）］」这样的段落列出了要标注的面板和系列：面板编号如 F2.p1，系列编号如 F2.p1.s1，
  后面是系列名、所在纵轴和 X 取值；面板行里的「读图分类」是读图时按整个子图判的指标，「左轴 / 右轴」是两条纵轴的标题。
  清单里的每个面板、每个系列都要标注，一个都不能漏。
- series：每个系列写 property（17 项代号，按这个系列所在那条纵轴的标题判；双纵轴的两条轴各判各的，不在 17 项里的写 none）
  和 measure（测的是什么）。
- x_role：X 是条件取值（pH、时间、温度、浓度、离子强度、储藏天数…）写「条件」，并写 x_variable 和 x_variable_unit；
  X 是样品名写「样品」；没有 X 写「无」。
- measurement_conditions：这个面板所有点共同的测定条件（图注、方法里写的，如测定时的蛋白质浓度、pH、温度），
  已经写进样品 processing 的不要重复。
- assignments：说明每个点对应哪个样品。每条写 series_id（* = 本面板全部系列）、x（* = 全部 X，否则照抄清单里的 X 取值）、
  sample_id，以及这条附带的条件 conditions（例如系列名「pH 3」→ pH=3）。例：
  · 系列是样品、X 是储藏时间 → 每个系列一条，x 写 *；
  · 系列是指标名（Size、PDI）、X 是样品名 → 每个 X 一条，series_id 写 *；
  · 系列是指标名、X 是 pH、整个面板是同一个样品 → 一条，series_id 和 x 都写 *；
  · X 是蛋白种类、系列是处理时间 → 每个（系列, X）组合一条。
  要求：面板里每个系列、每个 X 都恰好能找到一个样品；同一个点不能对应两个样品。
- 图里的每个数据都属于本研究的某个样品，一定要对上（用户：出现在文章的图表里，不可能对不上）。系列名和图注的写法常不一样，
  按符号、颜色、线型、顺序和方法推断：Filled / Solid / Closed / Black square 都是实心方块（■ ▪），Open / Hollow / White square
  是空心方块（□ ▫），三角（▲ ▴ △ ▵）、圆（● ○）、菱形（◆ ◇）同理。同一个符号在清单里有两个名字（如 Filled square 和
  Solid square），是同一条曲线被读了两遍，两个都对到同一个样品。
- 一一对应：同一个样品、同一项指标的几个数值，必须能靠 X 或 conditions 区分开（不同储藏时间、不同 pH、不同测定温度…）；
  区分不开就说明对应错了或条件漏写了。程序会逐点核对：同一样品、同一指标、同一组条件下只能有一个数值。
- evidence：照抄说明这个面板的图注片段或正文句子。

三、作者表格（tables）
- 全文里的作者表格加了编号：表格编号如 T1，行号 r1、r2…（最左列），列号 c1、c2…（最上一行），都是程序加的。
- 只标含 17 项指标的表；不含的不列。
- measures：表里属于 17 项的每一行或每一列（line 写 r5 或 c3），写 property、measure（照抄表头）、unit、
  这一行（列）附带的条件（如表头「solubility at pH 3」→ pH=3）。不在 17 项里的行列（水分、灰分、氨基酸组成、色度…）不要列。
- sample_lines：和指标方向垂直的每一行或每一列对应哪个样品（line、sample_id、附带条件）。表头所在的行和列不是样品。
  程序取「指标行 × 样品列」或「指标列 × 样品行」交叉处的单元格作为数据点。
- 同一行（列）在不同的指标列（行）属于不同样品时（如表头分两层：上层 rapeseed meal / sesame seed meal，下层 fatted / defatted；
  或左半是单酶水解物、右半是与 Alcalase 复合的水解物），把这一行在 sample_lines 里写几遍，每遍一个样品，
  用 only_lines 写清它只管哪几个指标列。不要因此放弃这张表。
- 一个格子里并列写了几个数（如「3.63−6.81」，表注说左边是 0 h、右边是 24 h）：同一个指标行（列）在 measures 里写几遍，
  用 part 指第几个数（1 起算），各自的条件写进 conditions。
- 表格不是「一边是样品、一边是指标」的（如每行是「指标 × 样品」、列是贮藏条件的堆叠表）：用 cells 逐格写——格子编号 r#.c#、
  样品、指标、条件；数值程序自己从格子里读。能用 measures × sample_lines 表达的就不要用 cells（两种写法不要重复写同一格）。
- 同一项指标占了好几行（列）时，这几行（列）之间的区别（如储藏时间 1 h、48 h、96 h，测定 pH 3、7）一定要写进各自的 conditions；
  同一个样品、同一项指标、同一组条件下只能有一个数值，程序会逐格核对。
- 网页上的一张表有时被拆成几张挨着的表（表头一张、分组名一张、数据一张），说明里会写「和上面的 T1 是被拆开的同一张表」：
  要连起来看，表头和分组名在前面那几张里；每张数据表各自标注（table_id 写数据所在的那张）。
- evidence：照抄表题或表注里说明样品、条件的句子。

四、正文里的数值（text_values）
- 只取本研究自己测的结果（摘要、结果与讨论、结论里写的），引言或讨论里引用别人文献的数不要。
- 只取某个样品某项指标（17 项）的具体测定值；「提高了 20%」「增加 2 倍」这类变化量、几个样品笼统的范围（如 between 2.1 and 3.5 nm）
  不取；「从 A 增加到 B」两端各自对应得上样品的，拆成两条。
- 原句必须明确写出这个数属于哪个样品：样品名称或缩写、区分样品的处理参数（如 2.5 MPa、4 h、pH 9），或 control、untreated、
  native 这类明确说法；把点名样品的词照抄进 sample_mention，要抄全、能单独区分出这个样品（分在原句几处的用 … 连起来，
  如「Protein isolate F … hexane-deoiled protein」），程序会核对。「在较高压力下」「随着处理时间延长」「处理后」
  这类没有点名具体样品、要靠推断才能对上的，一律不取；同一种说法对得上几个样品的（如几个浓度的 WPI 只写了 WPI）也不取。
- 图、表里已经有的数，正文又写了一遍的照样列出（正文常写作者的原值，比读图准）。同一个数在正文里写了好几遍的只列一次。
- value 照抄原句里的数字，sd 照抄 ± 后面的数，quote 照抄含这个数的那一句原文；程序核对数字在这句里、这句在原文里，核对不过不进表。
- 测定条件写进 conditions；同一样品、同一指标、同一组条件下只能有一个数值。

五、17 项指标（代号和定义，与读图时的口径相同；写 none 的情形也照这里）
{defs}
补充：游离氨基酸总量（氨基酸分析测得的 total free amino acids）也算 free_amino 游离氨基含量；单个氨基酸的组成仍是成分含量，
填 none。

六、判断不了怎么办
- 图和表：图表里的数据都属于本研究的样品，没有对不上的。结合材料与方法、图注、表注、正文和缩写表推断对应关系（例如图例
  名称和方法里的样品对得上、表里样品的排列和方法里的顺序一致），全部标注。只有读图结果本身缺了信息时（例如两层横轴被压成了
  一层、看不出某根柱子属于哪个样品），才把编号写进 unresolved，原因里写明读图结果缺了什么。
- 正文数值：原句必须明确点名样品（见第四节），没点名、要靠推断才能对上的不取；也可以写进 unresolved（写「正文」加原句开头几个词）。
""".format(defs=ed_DEFS, protein_def=ed_PROTEIN_DEF.replace('测的对象是不是蛋白质，', ''))

ed_USER = """文章标题：{title}
DOI：{doi}

要标注的图面板（{n_panels} 个）：{panel_ids}
作者表格（{n_tables} 张，只标含 17 项指标的）：{table_ids}

下面是全文。图的读图结果只列出编号、系列名和 X 取值，读数已略去；作者表格加了行号和列号。
==========
{text}
=========="""


# ================================================================ 读合并稿 ==
ed_BLOCK = re.compile(r'^([图表]) (\S+) 反读数据$')
ed_SEPARATOR = re.compile(r'^\|[\s:|-]+\|?\s*$')
ed_TABLE_CAP = re.compile(r'^Table ([A-Za-z]?\d+[A-Za-z]?)\.(?:\s|$)')
ed_AXIS_PART = re.compile(r'(左轴|右轴|第三轴)：')
ed_AXIS_EN = {'左轴': 'left', '右轴': 'right', '第三轴': 'third'}
ed_AXIS_CN = {v: k for k, v in ed_AXIS_EN.items()}
ed_EVAL_HEAD = '## 反读数据评价'


def ed_read(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read().replace('\r\n', '\n').lstrip('\ufeff')


def ed_cells(line):
    text = line.strip()
    if text.startswith('|'):
        text = text[1:]
    if text.endswith('|') and not text.endswith('\\|'):
        text = text[:-1]
    return [c.strip().replace('\\|', '|') for c in re.split(r'(?<!\\)\|', text)]


def ed_is_panel_head(line):
    return line.startswith(('子图 ', '指标 ')) or line == '整图' or line.startswith('整图｜')


def ed_parse_panel_head(line):
    """「子图 A｜读图分类：粒径｜X 轴：…｜Y 轴：…｜左轴：Size；右轴：PDI」→ (名, 信息)。"""
    head, *parts = line.split('｜')
    name = '-' if head == '整图' else head.split(' ', 1)[1].strip()
    info = {'axes': {}}
    for part in parts:
        if ed_AXIS_PART.match(part):
            for seg in re.split(r'；(?=(?:左轴|右轴|第三轴)：)', part):
                k, _, v = seg.partition('：')
                info['axes'][ed_AXIS_EN.get(k, k)] = v.strip()
            continue
        k, _, v = part.partition('：')
        info[{'读图分类': 'property_cn', 'X 轴': 'x_title', 'Y 轴': 'y_title'}.get(k.strip(), k.strip())] = v.strip()
    info['property'] = ed_CODE_OF_CN.get(info.get('property_cn'))
    return name, info


def ed_parse_doc(path):
    """合并稿 → 文章信息、反读面板、作者表格、发给模型的文字、核对用的作者原文。"""
    text = ed_read(path)
    lines = text.split('\n')
    end = next((i for i, l in enumerate(lines) if l.strip() == ed_EVAL_HEAD), len(lines))
    lines = lines[:end]
    title = next((l[2:].strip() for l in lines if l.startswith('# ')), '')
    doi = next((l[4:].strip() for l in lines if l.startswith('DOI: ')), '')
    doc = {'article': ed_article_of(path), 'path': path, 'title': title, 'doi': doi,
           'panels': collections.OrderedDict(), 'tables': collections.OrderedDict(), 'rows': 0}
    model_lines, author_lines, intro_lines = [], [], []
    intro_level = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        h = re.match(r'^(#{1,6})\s+(.*)$', line)
        if h:
            level = len(h.group(1))
            if re.search(r'\bintroduction\b', h.group(2), re.I):
                intro_level = level
            elif intro_level and level <= intro_level:
                intro_level = 0
        m = ed_BLOCK.match(line.strip())
        if m:
            i = ed_parse_block(doc, lines, i, m, model_lines)
            continue
        if line.startswith('|') and i + 1 < len(lines) and ed_SEPARATOR.match(lines[i + 1]):
            j = i
            while j < len(lines) and lines[j].startswith('|'):
                j += 1
            ed_add_table(doc, lines, i, j, model_lines)
            author_lines += lines[i:j]
            i = j
            continue
        model_lines.append(line)
        (intro_lines if intro_level else author_lines).append(line)
        i += 1
    doc['model_text'] = re.sub(r'\n{3,}', '\n\n', '\n'.join(model_lines)).strip()
    doc['body_text'] = ed_norm_text('\n'.join(author_lines))          # 引言以外的作者原文（正文数值只认这里的）
    doc['intro_text'] = ed_norm_text('\n'.join(intro_lines))
    doc['author_text'] = doc['body_text'] + ' ' + doc['intro_text']
    doc['author_cells'] = ed_norm_text(' '.join(' '.join(c for row in t['grid'] for c in row) for t in doc['tables'].values()))
    return doc


def ed_parse_block(doc, lines, i, m, model_lines):
    """「图 2 反读数据」整块：子图标题行 + 反读表，直到下一段不是这两样的文字。返回块后面那一行的行号。"""
    kind, label = m.groups()
    prefix = ('F' if kind == '图' else 'IT') + re.sub(r'\W', '', label)
    item = ('Figure %s' if kind == '图' else 'Table %s') % label
    source = '图反读' if kind == '图' else '图片表格反读'
    listing = ['［%s %s%s 读图结果的编号清单（读数已略去）］' % (kind, label, '（图片版表格）' if kind == '表' else '')]
    j = i + 1
    name, info = '-', {'axes': {}}
    while j < len(lines):
        s = lines[j].strip()
        if not s:
            j += 1
            continue
        if ed_is_panel_head(s):
            name, info = ed_parse_panel_head(s)
            j += 1
            continue
        if s.startswith('|'):
            k = j
            while k < len(lines) and lines[k].startswith('|'):
                k += 1
            rows = [ed_cells(l) for l in lines[j:k]]
            head = rows[0]
            body = [dict(zip(head, r)) for r in rows[2:]]
            pid = '%s.p%d' % (prefix, sum(1 for p in doc['panels'] if p.startswith(prefix + '.')) + 1)
            panel = {'pid': pid, 'item': item, 'source': source, 'kind': kind, 'label': label, 'name': name,
                     'info': info, 'series': collections.OrderedDict()}
            for r in body:
                sname = r.get('系列', '')
                sk = next((x for x, v in panel['series'].items() if v['name'] == sname), None)
                if sk is None:
                    sk = '%s.s%d' % (pid, len(panel['series']) + 1)
                    panel['series'][sk] = {'sid': sk, 'name': sname, 'rows': []}
                panel['series'][sk]['rows'].append(r)
                doc['rows'] += 1
            doc['panels'][pid] = panel
            listing += ['', ed_panel_listing(panel)]
            name, info = '-', {'axes': {}}
            j = k
            continue
        break
    model_lines += [''] + listing + ['']
    return j


def ed_panel_listing(panel):
    info = panel['info']
    head = '面板 %s｜%s' % (panel['pid'], ('整图' if panel['name'] == '-' else
                                           ('子图 ' if panel['kind'] == '图' else '指标 ') + panel['name']))
    if info.get('property_cn'):
        head += '｜读图分类：%s' % info['property_cn']
    if info.get('x_title'):
        head += '｜X 轴：%s' % info['x_title']
    if info.get('y_title'):
        head += '｜Y 轴：%s' % info['y_title']
    if info['axes']:
        head += '｜' + '；'.join('%s：%s' % (ed_AXIS_CN.get(a, a), t) for a, t in info['axes'].items())
    out = [head]
    for s in panel['series'].values():
        rows = s['rows']
        axis = next((r.get('Y轴') for r in rows if r.get('Y轴')), '')
        yu = next((r.get('Y单位') for r in rows if r.get('Y单位')), '')
        xu = next((r.get('X单位') for r in rows if r.get('X单位')), '')
        xs = list(dict.fromkeys(r.get('X', '') for r in rows))
        line = '- %s｜系列「%s」' % (s['sid'], s['name'])
        if axis:
            line += '｜%s' % ed_AXIS_CN.get(axis, axis)
        if yu:
            line += '｜Y 单位 %s' % yu
        line += '｜X：%s' % ' | '.join(x if x else '（空）' for x in xs)
        if xu:
            line += '（X 单位 %s）' % xu
        out.append(line)
    return '\n'.join(out)


def ed_add_table(doc, lines, i, j, model_lines):
    rows = [ed_cells(l) for k, l in enumerate(lines[i:j]) if k != 1]
    width = max(len(r) for r in rows)
    grid = [r + [''] * (width - len(r)) for r in rows]
    tid = 'T%d' % (len(doc['tables']) + 1)
    cap = None
    k = len(model_lines) - 1
    while k >= 0 and len(model_lines) - k <= 6:
        s = model_lines[k].strip()
        if s:
            m = ed_TABLE_CAP.match(s)
            if m:
                cap = s
                break
            if not s.startswith('［') and not s.startswith('|'):
                break
        k -= 1
    label = ed_TABLE_CAP.match(cap).group(1) if cap else None
    # 网页上的一张表常被拆成几张挨着的表（表头一张、分组名一张、数据一张，jf020952j）：中间只隔空行的算同一组，
    # 后面几张沿用第一张的表题；核对表头时整组一起看
    last = doc.get('_last_table')
    group = tid
    if last and all(not x.strip() for x in model_lines[last[1]:]):
        first = doc['tables'][last[0]]
        group = first['group']
        if not cap:
            cap, label = first['caption'], first['label'] and first['label'].split(' ', 1)[1]
    doc['tables'][tid] = {'tid': tid, 'label': ('Table %s' % label) if label else None, 'caption': cap, 'grid': grid,
                          'group': group}
    note = '［作者表格 %s%s%s：最左列的 r1、r2… 是行号，最上一行的 c1、c2… 是列号，都是程序加的］' % (
        tid, '（原文 Table %s）' % label if label else '',
        '，和上面的 %s 是网页上被拆开的同一张表，要连起来看' % group if group != tid else '')
    out = ['', note, '| | ' + ' | '.join('c%d' % (c + 1) for c in range(width)) + ' |',
           '|' + '---|' * (width + 1)]
    out += ['| r%d | %s |' % (r + 1, ' | '.join(c.replace('|', '\\|') for c in row)) for r, row in enumerate(grid)]
    model_lines += out + ['']
    doc['_last_table'] = (tid, len(model_lines))


# ================================================================ 规范化 ==
ed_DASHES = dict.fromkeys(map(ord, '\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uff0d'), '-')
ed_QUOTES = {ord('\u2018'): "'", ord('\u2019'): "'", ord('\u201c'): '"', ord('\u201d'): '"', ord('\u2032'): "'"}


def ed_norm_text(s):
    s = unicodedata.normalize('NFKC', str(s or '')).translate(ed_DASHES).translate(ed_QUOTES)
    s = s.replace('\\', '').replace('*', '').replace('^', '').replace('{', '').replace('}', '')
    s = s.replace('_', ' ')          # 合并稿里偶有去斜体留下的下划线（jf960867+「Log_G‘」），模型抄成空格；两边同样处理
    return ' '.join(s.split()).casefold()


def ed_norm_x(s):
    t = re.sub(r'\s+', '', ed_norm_text(s))
    try:
        return repr(float(t))
    except ValueError:
        return t


ed_SUPS = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺', '0123456789-+')
ed_SCI = r'(%s)\s*[×xX*·]\s*10\s*\^?\s*\(?([-+]?\d+)\)?'


def ed_sup_caret(t):
    """上标指数先写成 ^n 再做 NFKC（不然「10⁵」会变成「105」）。"""
    return re.sub(r'[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+', lambda m: '^' + m.group(0).translate(ed_SUPS), t)


def ed_num_text(v):
    """模型抄的正文数值 → 规范写法（Unicode 减号换成 -、去千分位；「4.75 × 10⁵」→ 4.75e5）；不是单个数字返回 None。"""
    t = unicodedata.normalize('NFKC', ed_sup_caret(str(v or ''))).translate(ed_DASHES).strip()
    t = re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))', '', t)
    t = re.sub(r'^([-+])\s+(?=\d)', r'\1', t)
    m = re.fullmatch(ed_SCI % ed_NUM, t)
    if m:
        return '%se%d' % (m.group(1), int(m.group(2)))
    return t if re.fullmatch(ed_NUM, t) else None


def ed_num_key(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def ed_number_in(val, quote):
    """数字在原句里：前后不能紧挨着别的数字或小数点（26.7 不能认成 126.70 的一部分）。"""
    q = re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))', '', unicodedata.normalize('NFKC', ed_sup_caret(quote)).translate(ed_DASHES))
    m = re.fullmatch(r'([-+]?\d+(?:\.\d+)?)e([-+]?\d+)', val)
    if m and any(int(e) == int(m.group(2)) for e in
                   re.findall(r'(?<![\d.])%s\s*[×xX*·]\s*10\s*\^?\s*\(?([-+]?\d+)' % re.escape(m.group(1).lstrip('+')), q)):
        return True                                           # 科学计数法：原句里写的是「4.75 × 10^5」
    v = val.lstrip('+')
    pats = [v] + ([v[1:]] if v.startswith('-') else [])     # 原句写「−5.2」或「negative 5.2」都算
    return any(re.search(r'(?<![\d.])%s(?![\d])' % re.escape(x), q) for x in pats)


ed_CONTROL_WORDS = re.compile(r'\b(?:control|controls|untreated|native|original|unmodified|non-?treated|raw|blank|'
                           r'unheated|without (?:any )?treatment)\b')


def ed_mention_pieces(mention):
    return [p for p in (ed_norm_text(x) for x in re.split(r'\.{3,}|…', mention or '')) if p]


def ed_mention_in_quote(mention, quote):
    """点名样品的词（可以是用 … 连起来的几段）每一段都在原句里。"""
    q = ed_norm_text(quote)
    pieces = ed_mention_pieces(mention)
    if not pieces:
        return False
    if all(p in q for p in pieces):
        return True
    words = [w for p in pieces for w in p.split()]
    return all(re.search(r'(?<![\w.])%s(?![\w])' % re.escape(w), q) for w in words)


def ed_explicit_mention(mention, sample, samples=None):
    """正文数值点名样品的词是不是明确的指向（用户 2026-10-13：「没有明确指向的不用 模糊的不用」）：
    含数字（区分样品的处理参数，如 2.5 MPa、4 h），或是 control、untreated 这类明确说法，或对得上这个样品的名称、缩写
    （这个样品某个名称的词全部在里面，而且比别的样品对得更具体）——同一种说法对得上几个样品的（几个浓度的 WPI 只写 WPI、
    E 和 F 两种分离蛋白只写 hexane-deoiled protein）不算。「higher steam pressures」这类只给方向、没点名的不算。"""
    m = ' '.join(ed_mention_pieces(mention))
    if re.search(r'\d', m) or ed_CONTROL_WORDS.search(m):
        return True
    words = set(re.findall(r'[\w.%+-]+', m))

    def score(s):
        """这个样品的名称里，词全部出现在点名词里的、最长的那个有几个词（单字母也算：isolate E / F 靠它区分）。"""
        best = 0
        for lb in (s or {}).get('labels') or []:
            lw = set(re.findall(r'[\w.%+-]+', ed_norm_text(lb)))
            if lw and lw <= words:
                best = max(best, len(lw))
        return best
    mine = score(sample)
    return mine > 0 and all(score(o) < mine for o in (samples or {}).values() if o is not sample)


def ed_quote_found(quote, text):
    """原文句子核对：照抄的句子（省略号隔开的每段都算）要在原文里找得到。
    模型常把图注开头和子图那段接起来抄（「Figure 6. Purification … strategy. (c) phase transition …」，
    acs.jafc.1c00109），还会把图注里隔开的几句接在一起（acs.jafc.2c07799）：子图标记「(c)」前、句号后也断开，逐段核对。
    原文的下标写成「ZL_{1:1}」「R_h」、模型抄成「ZL1:1」「Rh」（acsfoodscitech.5c00893）：逐段找不到的，去掉空格再找一遍。"""
    pieces = [p.strip() for p in re.split(r'\.{3,}|…|\s(?=\([a-z]\)\s)|(?<=\.)\s+', ed_norm_text(quote)) if len(p.strip()) >= 8]
    if not pieces:
        return False
    squash = None
    for p in pieces:
        if p in text:
            continue
        if squash is None:
            squash = re.sub(r'\s+', '', text)
        if re.sub(r'\s+', '', p) not in squash:
            return False
    return True


# ================================================================ 表格单元格 ==
ed_NA_CELLS = {'', '-', '--', '—', '–', '/', 'nd', 'n.d.', 'n.d', 'na', 'n.a.', 'n/a', 'nm', 'n.m.', 'ns', 'n.s.',
            'not detected', 'tr', 'trace', 'none'}
ed_NUM = r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?'
ed_CELL = re.compile(r'^(?P<q>[<>≤≥~≈]?)\s*(?P<v>%s)\s*%%?\s*(?:(?:±|\+/-|\+-)\s*(?P<sd>%s)\s*%%?|\(\s*(?P<pm>±\s*)?(?P<sd2>%s)\s*%%?\s*\))?\s*'
                  r'(?:\((?P<mark>[A-Za-z]{1,3})\))?\s*'          # 表注标记「0.29 ± 0.17(m)」（jf020952j），原文照留在 原始单元格
                  r'(?P<sig>(?:[A-Za-z*]{1,4}\d{0,2}[,\s]*){0,4})$' % (ed_NUM, ed_NUM, ed_NUM))   # 「a1」「b2」（acs.jafc.7b02985）


def ed_parse_cell(raw):
    """「8.7 ± 0.0^a」→ {'value': '8.7', 'sd': '0.0', 'sig': 'a'}；空格、nd 之类 → None；认不出 → value 为空、照留原文。"""
    s = unicodedata.normalize('NFKC', ed_sup_caret(raw)).translate(ed_DASHES).strip()
    s = re.sub(r'(\d+(?:\.\d+)?)\s*[×xX*·]\s*10\s*\^\s*([-+]?\d+)', r'\1e\2', s)     # 「8.1 × 10⁶」→ 8.1e6
    s = re.sub(r'\^[-+]?\d+|\^\{[\d,.\s]+\}', '', s)          # 上标数字是表注记号（「29.8¹」「22.8^{1,2}」，jf9503927），不是数的一部分
    if s.casefold() in ed_NA_CELLS or not re.search(r'\d', s):   # 没有数字的格（ND/ND、样品名）不是数值
        return None
    m = re.match(r'^(.*?\d)\s*\^\{?([A-Za-z*]{1,4})\}?\s*((?:±|\+/-|\+-).*)$', s)
    if m:                                                     # 显著性字母写在 ± 前面「97.25^b ± 0.82」（jf981003m）
        s = '%s %s %s' % (m.group(1), m.group(3), m.group(2))
    t = re.sub(r'\^\{([^}]*)\}', r' \1', s)
    t = re.sub(r'\^([A-Za-z*]+)', r' \1', t)
    t = re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))', '', t)            # 千分位
    t = re.sub(r'(?<=\d),(?=\d{1,2}(?:\D|$))', '.', t)         # 小数点写成逗号「8.13 ± 0,82」（jf053178j）
    m = ed_CELL.match(t)
    if not m:
        return {'value': '', 'sd': '', 'sig': '', 'qual': '', 'ok': False}
    sig = re.sub(r'[\s,]+', '', m.group('sig') or '')
    q = m.group('q')
    # 「<0.1」「>100」这类只给了界限，数值栏留空（原文照留在 原始单元格），免得当成 0.1 用
    sd = m.group('sd') or ('' if m.group('pm') else m.group('sd2')) or ''
    return {'value': '' if q in ('<', '>', '≤', '≥') else m.group('v'), 'sd': sd,
            'sig': sig, 'qual': q, 'ok': not q}


# ================================================================ 调模型 ==
def ed_fingerprint(doc, model):
    schema = json.dumps(ed_PaperNote.model_json_schema(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(json.dumps([model_key(model), ed_SYSTEM, schema, ed_user_text(doc)],
                                     ensure_ascii=False).encode('utf-8')).hexdigest()[:16]


def ed_model_slug(model):
    """文件夹名：google/gemini-3.8-flash → google_gemini-3.8-flash"""
    return re.sub(r'[\\/:*?"<>|\s]+', '_', model_key(model))


def ed_user_text(doc):
    tables = list(doc['tables'])
    return ed_USER.format(title=doc['title'], doi=doc['doi'], n_panels=len(doc['panels']),
                       panel_ids='、'.join(doc['panels']) or '（无）', n_tables=len(tables),
                       table_ids='、'.join(tables) or '（无）', text=doc['model_text'])


def ed_empty_reason(raw):
    """空回答（没有 choices）里 OpenRouter 写的出错原因，打印出来看得清是什么问题。"""
    try:
        body = json.loads(raw.text)
    except Exception:
        return '回答不是 JSON：%s' % ' '.join(str(getattr(raw, 'text', '') or '').split())[:160]
    err = body.get('error') if isinstance(body, dict) else None
    if isinstance(err, dict):
        meta = err.get('metadata') or {}
        bits = [err.get('code'), err.get('message'), meta.get('provider_name'), meta.get('raw')]
        return ' '.join(' '.join(str(x).split()) for x in bits if x)[:240]
    return '没有 choices：%s' % json.dumps(body, ensure_ascii=False)[:200]


def ed_request(api, system, text, schema):
    """(一次请求的参数, 是否经 OpenRouter)。每次重发都重取：OpenRouter 没钱后会切到 Google 官方接口（用户 2026-11-04）。"""
    via = api.openrouter
    extra = {}
    if via:
        extra = json.loads(json.dumps(api.provider_extra.get('extra_body', {})))
        extra['usage'] = {'include': True}
    kwargs = dict(model=api.model if via else direct_model(api.model, api.base_url),
                  messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': text}],
                  response_format=schema, extra_body=extra or None)
    if not via and api.gemini:
        kwargs['service_tier'] = GEMINI_TIER
    return kwargs, via


def ed_call_model(api, system, text):
    """一次结构化调用（只发文字）。出错处理和读图脚本相同：没钱、key 无效 → 整个窗口停下；限流、服务器忙 → 等着重试。
    OpenRouter 有时回一个没有 choices 的空回答（2026-10-14 flex 档忙时约三分之一，SDK 报 TypeError: 'NoneType' object
    is not iterable）：当作服务器忙，等 30 秒再问，和限流共用最多 30 分钟的等待；打印回答里写的出错原因（用户 2026-10-14 同意）。"""
    waited = 0.0
    while True:
        if api.stop.is_set():
            raise Fatal(api.fatal)
        kwargs, via_openrouter = ed_request(api, system, text, ed_PaperNote)
        raw = None
        try:
            with api.slots:
                raw = api.client.chat.completions.with_raw_response.parse(**kwargs)
                r = raw.parse()
            break
        except SystemExit:
            raise
        except TypeError as e:
            if raw is None or 'NoneType' not in str(e):
                raise
            why = ed_empty_reason(raw)
            if waited >= RATE_WAIT_MAX:
                raise ValueError('模型连续回空回答、已等 %d 分钟（%s）' % (waited // 60, why))
            print('[空回答] 等 30 秒再试（%s）' % why, flush=True)
            api.sleep(30)
            waited += 30
        except Exception as e:
            kind = api_problem(e, gemini=not via_openrouter and api.gemini)
            if via_openrouter and (api.gemini or kind == 'money' and api.switch_to_gemini(api.model, short_error(e))):
                continue                     # 同读图：切到 Google 官方接口重发
            if kind in ('money', 'key', 'access'):
                msg = FATAL_MESSAGES[kind + ('_openrouter' if via_openrouter and kind == 'money' else '')]
                api.halt(msg % {'why': short_error(e), 'key': api.key_env, 'model': api.model})
            if kind not in ('rate', 'busy') or waited >= RATE_WAIT_MAX:
                raise
            delay = retry_delay(e)
            print('[%s] 等 %d 秒再试（%s）' % ('限流' if kind == 'rate' else '服务器忙', delay, short_error(e)), flush=True)
            time.sleep(delay)
            waited += delay
    use = usage_of(r)
    u = getattr(r, 'usage', None)
    cost = getattr(u, 'cost', None)
    if cost is None and getattr(u, 'model_extra', None):
        cost = u.model_extra.get('cost')
    use['cost'] = float(cost) if cost is not None else None
    choice = r.choices[0]
    parsed = choice.message.parsed
    if parsed is None:
        raise ValueError('模型没有返回可解析的结果（finish_reason=%s）' % choice.finish_reason)
    return parsed, use, choice.finish_reason


def ed_cache_path(cdir, article):
    return os.path.join(cdir, article + '.json')


def ed_load_cache(cdir, doc, model):
    p = ed_cache_path(cdir, doc['article'])
    if not os.path.exists(p):
        return None
    try:
        c = json.loads(ed_read(p))
    except ValueError:
        return None
    return c if c.get('fingerprint') == ed_fingerprint(doc, model) else None


def ed_atomic_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.x-', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def ed_write_if_changed(path, text):
    """内容和磁盘上的一样就不写（用户 2026-10-21：每天都有新的 datapoint，没变的文件不要每次都重写一遍；
    修改时间不变，建库也看得出哪几篇真的变了）。返回这次写没写。"""
    try:
        with open(path, encoding='utf-8', newline='') as fh:
            if fh.read() == text:
                return False
    except OSError:
        pass
    ed_atomic_write(path, text)
    return True


ed_PRINT_LOCK = threading.Lock()


def ed_say(text):
    with ed_PRINT_LOCK:
        print(text, flush=True)


def ed_ask_one(api, cdir, doc):
    t0 = time.time()
    for attempt in range(3):
        try:
            parsed, use, finish = ed_call_model(api, ed_SYSTEM, ed_user_text(doc))
            break
        except ValueError as e:                  # 模型中途出错、没有可解析的结果（jf063211h finish_reason=error）：再问，最多三次
            if attempt == 2:
                raise
            ed_say('[%s] %s，再问一次' % (doc['article'], e))
    rec = {'fingerprint': ed_fingerprint(doc, api.model), 'model': api.model, 'at': time.strftime('%Y-%m-%d %H:%M:%S'),
           'seconds': round(time.time() - t0, 1), 'usage': use, 'finish_reason': finish,
           'output': parsed.model_dump()}
    ed_atomic_write(ed_cache_path(cdir, doc['article']), json.dumps(rec, ensure_ascii=False, indent=1))
    ed_say('[%s] 模型回答：样品 %d、面板 %d、表格 %d、判断不了 %d；输入 %s、输出 %s token%s，%.0f 秒' % (
        doc['article'], len(parsed.samples), len(parsed.panels), len(parsed.tables), len(parsed.unresolved),
        format(use.get('input', 0), ','), format(use.get('output', 0), ','),
        '，$%.4f' % use['cost'] if use.get('cost') is not None else '', rec['seconds']))
    return rec


# ================================================================ 组装数据点 ==
def ed_param_text(params):
    out = []
    for p in params or []:
        v = '%s %s' % (p.get('value', ''), p.get('unit') or '')
        out.append('%s=%s' % (p.get('name', ''), v.strip()))
    return '; '.join(out)


def ed_pick_params(sample, names):
    vals = []
    for st in sample.get('processing') or []:
        for p in st.get('params') or []:
            n = (p.get('name') or '').strip().casefold()
            if any(n == x or n.startswith(x + ' ') for x in names):
                vals.append(('%s %s' % (p.get('value', ''), p.get('unit') or '')).strip())
    return ' | '.join(vals)


def ed_sample_fields(s):
    if not s:
        return {k: '' for k in ('样品名称', '样品说明', '蛋白来源', '蛋白类别', '蛋白形态', '蛋白浓度', '复配物', '处理',
                                '处理类别', '处理温度', '处理时间', '处理pH', '体系')}
    ing = '; '.join('%s（%s%s）' % (x.get('name', ''), x.get('category', ''), '，' + x['amount'] if x.get('amount') else '')
                    for x in s.get('ingredients') or [])
    steps = ' → '.join('%s（%s%s）' % (st.get('method', ''), st.get('category', ''),
                                      '：' + ed_param_text(st.get('params')) if st.get('params') else '')
                       for st in s.get('processing') or [])
    cats = '、'.join(dict.fromkeys(st.get('category', '') for st in s.get('processing') or []))
    return {'样品名称': ' / '.join(s.get('labels') or []), '样品说明': s.get('description') or '',
            '蛋白来源': s.get('protein_source') or '', '蛋白类别': s.get('protein_category') or '',
            '蛋白形态': s.get('protein_form') or '', '蛋白浓度': s.get('protein_concentration') or '',
            '复配物': ing, '处理': steps or '（未处理）', '处理类别': cats,
            '处理温度': ed_pick_params(s, ('temperature', 'temp')), '处理时间': ed_pick_params(s, ('time', 'duration')),
            '处理pH': ed_pick_params(s, ('ph',)), '体系': s.get('system') or ''}


# 整张子图都被模型说成不在 17 项（jf011164h 图 3：没编号的 8 张小图长得一样，读图读错了张，糖和有机酸的浓度贴上了
# 「游离氨基含量」）：用户 2026-10-14 定先不收，记进 _待重读.md，统一重读时重新分类、读图
ed_WHOLE_NONE = '文字解读判为不在 17 项（整张子图，记进待重读）'


ed_RULE_EXTRA = ('质构', '力学性能', '溶胀率')


def ed_rule_skip(prop, x_title, y_title, extra=''):
    """按读图脚本现行规则不读的原因（fr.skip_reason）。纵轴标题看不出来时（纵轴写「Force (g)」、系列叫 Chewiness /
    Adhesiveness，acsfoodscitech.5c00061 图 5），再带上系列名和模型写的测量名称判一次，只认质构、力学性能、溶胀率这三条。
    读图脚本 2026-10-15 补的力学、质构新词（剪切力、firmness…）这里一样用：用户「质构力学数据也不要」，已经提取过的也排除。"""
    if prop not in FUNCTIONAL:
        return None
    ns = lambda y: types.SimpleNamespace(protein_system=True, functional_property=prop, x_axis_label=x_title or '',
                                         y_axis_label=y or '')
    why = skip_reason(ns(y_title))
    if not why and extra:
        w2 = skip_reason(ns('%s %s' % (y_title or '', extra)))
        if w2 and any(k in w2 for k in ed_RULE_EXTRA):
            why = w2
    return why


# 人工排除（用户 2026-10-19：全量检查查出的误收，「这三条都不要」）：人工排除.tsv 每行「文章 <Tab> 指标 <Tab> 测量名称 <Tab> 原因」，
# 指标写中文名或代号，空 = 整篇；测量名称空 = 这一项全部。命中的数值移到「排除的数据」，原因写「人工排除：…」，建库不收。
# 以后再发现同类问题往这个文件里加一行就行，不用改代码、不调模型
ed_MANUAL_EXCLUDE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '人工排除.tsv')


def ed_load_manual_exclude(path=None):
    """{文章: [(指标代号或 '', 测量名称或 '', 原因)]}"""
    path = path or ed_MANUAL_EXCLUDE
    out = collections.defaultdict(list)
    if os.path.exists(path):
        for line in io.open(path, encoding='utf-8-sig'):
            if not line.strip() or line.startswith('#'):
                continue
            parts = (line.rstrip('\n').split('\t') + ['', '', '', ''])[:4]
            art, prop, name, why = (x.strip() for x in parts)
            out[art].append((ed_CODE_OF_CN.get(prop, prop), name, why))
    return out


def ed_manual_reason(rules, row):
    for prop, name, why in rules:
        if (not prop or prop == row.get('指标代号')) and \
                (not name or ed_norm_text(name) == ed_norm_text(row.get('测量名称') or row.get('系列') or '')):
            return '人工排除：%s' % why
    return None


def ed_build_paper(doc, note):
    """一篇 → (数据点, 排除的点, 样品行, 统计)。note 是模型回答（没有就是 None：图的点照出、条件未确定，表格不出点）。"""
    note = note or {'samples': [], 'panels': [], 'tables': [], 'unresolved': []}
    samples = {}
    dup_ids = set()
    for s in note['samples']:
        if s['sample_id'] in samples:
            dup_ids.add(s['sample_id'])
        samples[s['sample_id']] = s
    unresolved = {}
    for u in note['unresolved']:
        unresolved.setdefault(u['item_id'].strip(), u['reason'])
    pnotes = {}
    for p in note['panels']:
        pnotes.setdefault(p['panel_id'].strip(), p)
    used = collections.Counter()
    points, excluded = [], []
    base = {'文章': doc['article'], 'DOI': doc['doi']}

    manual = ed_load_manual_exclude().get(doc['article'], [])

    def finish(row, sid, conds, status, flags, reason=None):
        s = samples.get(sid) if sid else None
        if not reason and s and s.get('contains_protein') is False:
            reason = '样品不含蛋白质'                 # 用户 2026-10-13：不含蛋白质的不收
        if not reason and manual:
            reason = ed_manual_reason(manual, row)
        row.update(ed_sample_fields(s))
        row['样品编号'] = sid or ''
        row['_conds'] = list(conds or [])
        row['测定条件'] = ed_param_text(conds)
        row['对应状态'] = status
        row['提醒'] = '；'.join(dict.fromkeys(f for f in flags if f))
        if reason:
            row['排除原因'] = reason
            excluded.append(row)
        else:
            points.append(row)

    # ---- 图（反读表）
    for pid, panel in doc['panels'].items():
        info = panel['info']
        pn = pnotes.get(pid)
        snotes = {x['series_id'].strip(): x for x in (pn or {}).get('series') or []}
        multi = len({r.get('Y轴') or 'left' for s in panel['series'].values() for r in s['rows']}) > 1 or \
            len(info['axes']) > 1
        pflags = []
        if pn and pn.get('evidence') and not any(ed_quote_found(q, doc['author_text']) for q in pn['evidence']):
            pflags.append('面板依据的原文句子没找到')
        finals = {}
        for sid, s in panel['series'].items():
            sn = snotes.get(sid)
            mp = sn['property'] if sn else None
            ip = info.get('property')
            flags, reason = list(pflags), None
            if not multi and ip:
                final = ip
                if mp and mp != ip:
                    flags.append('文字解读判为%s' % (FUNCTIONAL.get(mp, '不在 17 项')))
            elif mp in FUNCTIONAL:
                final = mp
            elif mp == 'none':
                final, reason = None, '文字解读判为不在 17 项'
            elif ip:
                final = ip
                flags.append('双纵轴系列的指标没经文字核对' if multi else '')
            else:
                final, reason = None, '没有指标判断'
            if not sn:
                flags.append('模型没有标注这个系列')
            finals[sid] = (final, reason, flags, sn)
        noted = [f for f in finals.values() if f[3]]
        if noted and all(f[3]['property'] == 'none' for f in noted):
            for k, (final, reason, flags, sn) in list(finals.items()):
                finals[k] = (None, ed_WHOLE_NONE, flags, sn)
        elif not multi and info.get('property') and any(f[3] and f[3]['property'] == info['property']
                                                         for f in finals.values()):
            # jf011164h 图 7：读图分类是游离氨基含量，子图里 lysine residues 是、Amadori compound 不是；
            for k, (final, reason, flags, sn) in list(finals.items()):
                if sn and sn['property'] == 'none':
                    finals[k] = (None, '文字解读判为不在 17 项（同一子图里别的系列才是%s）' % info.get('property_cn'),
                                 flags, sn)
        if multi and info.get('property') and not any(f[0] == info['property'] for f in finals.values()):
            for f in finals.values():
                f[2].append('读图分类（%s）和文字解读不一致' % info.get('property_cn'))
        for sid, s in panel['series'].items():
            final, reason, flags, sn = finals[sid]
            axis = next((r.get('Y轴') for r in s['rows'] if r.get('Y轴')), '') or 'left'
            y_title = info['axes'].get(axis) or info.get('y_title') or ''
            extra = '%s %s' % (s['name'], (sn or {}).get('measure') or '')
            if final and not reason:
                why = ed_rule_skip(final, info.get('x_title'), y_title, extra)
                if why:
                    reason = '按现行读图规则不读：%s' % why
            elif reason == ed_WHOLE_NONE:
                # 读图时还没有「质构不算凝胶性」这条（用户 2026-10-13 才加）的图：读图分成凝胶性，提取说不在 17 项，
                # 按现行规则排除就对了，不进待重读（acs.jafc.4c01551 图 2 硬度、弹性、咀嚼性、内聚性）
                why = ed_rule_skip(info.get('property'), info.get('x_title'), y_title, extra)
                if why:
                    reason = '按现行读图规则不读：%s' % why
            for r in s['rows']:
                row = dict(base)
                row['_scope'] = pid
                row['_mkey'] = (sn or {}).get('measure') or ('系列 ' + s['name'])
                row.update({'来源': panel['source'], '图表': panel['item'],
                            '子图或指标': '' if panel['name'] == '-' else panel['name'], '面板编号': pid,
                            '系列': s['name'], 'X': r.get('X', ''), 'X单位': r.get('X单位', ''),
                            '数值': r.get('Y', ''), '单位': r.get('Y单位', ''), '倍率': r.get('倍率', ''),
                            '误差下限': r.get('误差下限', ''), '误差上限': r.get('误差上限', ''), 'SD': '',
                            '显著性': r.get('显著性', ''), '原始单元格': '', '判定': r.get('判定', ''),
                            '指标代号': final or (sn['property'] if sn else ''),
                            '指标': FUNCTIONAL.get(final, ''),
                            '测量名称': (sn or {}).get('measure') or y_title})
                sample_id, conds, status, f2 = ed_resolve_figure_point(pn, sid, r.get('X', ''), unresolved, samples,
                                                                    r.get('X单位', ''))
                row['X含义'] = (pn or {}).get('x_variable') or ('样品' if (pn or {}).get('x_role') == '样品' else '')
                row['_xrole'] = (pn or {}).get('x_role') or ""
                finish(row, sample_id, conds, status, flags + f2, reason)

    # ---- 作者表格
    tnotes = {}
    for t in note['tables']:
        tnotes.setdefault(t['table_id'].strip(), t)
    for tid, tn in tnotes.items():
        table = doc['tables'].get(tid)
        if not table:
            continue
        grid = table['grid']
        tflags = []
        if tn.get('evidence') and not any(ed_quote_found(q, doc['author_text']) for q in tn['evidence']):
            tflags.append('表格依据的原文句子没找到')
        seen = set()

        def table_point(r, c, part, sid, prop, measure, unit, conds, status, flags, series):
            """一格（或格子里第 part 个数）→ 一个数据点；数值程序自己从格子里读。"""
            raw = grid[r][c]
            text = raw
            if part:
                pieces = ed_cell_parts(raw)
                if part > len(pieces):
                    return
                text = pieces[part - 1]
            cell = ed_parse_cell(text)
            if cell is None:
                return
            flags = list(flags)
            if not cell['ok']:
                flags.append('单元格不是单个数值' if not cell['value'] else '单元格带%s' % cell['qual'])
            s = samples.get(sid) if sid else None
            if status == '已对应':
                if not s:
                    status = '条件未确定：样品编号 %s 不在样品清单里' % sid
                elif sid in dup_ids:
                    status = '对应冲突：样品编号 %s 在样品清单里出现了两次' % sid
            reason = None
            why = skip_reason(types.SimpleNamespace(protein_system=True, functional_property=prop,
                                                       x_axis_label='', y_axis_label=measure))
            if why:
                reason = '按现行读图规则不读：%s' % why
            row = dict(base)
            row['_scope'] = table['group']
            row['_mkey'] = measure
            row.update({'来源': '作者表格', '图表': table['label'] or tid, '子图或指标': measure,
                        '面板编号': '%s.r%d.c%d%s' % (tid, r + 1, c + 1, '#%d' % part if part else ''), '系列': series,
                        'X': '', 'X单位': '', 'X含义': '', '数值': cell['value'], '单位': unit or '',
                        '倍率': '', '误差下限': '', '误差上限': '', 'SD': cell['sd'], '显著性': cell['sig'],
                        '原始单元格': raw, '判定': '作者原值', '指标代号': prop,
                        '指标': FUNCTIONAL.get(prop, ''), '测量名称': measure})
            finish(row, sid if s else '', conds, status, flags, reason)

        def pick_sample(sls, mctx):
            """一行（列）对了几个样品，挑这一格的：先看 only_lines 已经筛过；剩几个的，按这一格所在指标列自己的分组表头——
            样品名称整个出现在表头里、且只有一个的（jf071117a「HPI」/「SPI」）；否则比表头的词和「样品名称 + 这一行附带条件」
            重合几个，唯一最多的（jf981003m「rapeseed meal / fatted」→ 条件写的 rapeseed meal fatted）。分不出返回 None。"""
            if len({x['sample_id'] for x in sls}) == 1:
                return sls[0], None
            hit = [x for x in sls if any(ed_word_in(lb, mctx) for lb in (samples.get(x['sample_id']) or {}).get('labels') or [])]
            if len({x['sample_id'] for x in hit}) == 1:
                return hit[0], '「%s」对了几个样品，按分组表头定为「%s」' % (hit[0]['line'], hit[0]['sample_id'])
            words = set(re.findall(r'\w+', mctx))
            scored = []
            for x in sls:
                txt = ' '.join(list((samples.get(x['sample_id']) or {}).get('labels') or []) +
                               [str(c.get('value') or '') for c in x.get('conditions') or []])
                scored.append((len(words & set(re.findall(r'\w+', ed_norm_text(txt)))), x))
            scored.sort(key=lambda z: -z[0])
            if scored[0][0] > 0 and scored[0][0] > scored[1][0]:
                x = scored[0][1]
                return x, '「%s」对了几个样品，按分组表头定为「%s」' % (x['line'], x['sample_id'])
            return None, None

        for ml in tn['measures']:
            orig = ed_parse_line(ml['line'], grid)
            mline = orig
            if not mline:
                continue
            mtext = ed_group_text(doc, table, mline) + ' ' + ed_line_context(grid, mline)
            mflags = list(tflags)
            if not ed_label_in(ml['measure'], mtext):
                # 模型的行列号差了一格（jf0601923 表 1 把第一个指标列写成 c1，c1 其实是样品名）：相邻一行（列）的表头
                # 恰好是模型写的指标名、且只有一个相邻的对得上，就按表头改过去。只在模型写的那一行（列）里根本没有数值时才改
                # （两层表头的 jf010549x：c5「peptic hydrolysates IC₅₀」核对不过时曾被挪到 c4，IC₅₀ 的格子差点算成 IC₁₀）
                size = len(grid) if mline[0] == 'r' else len(grid[0])
                vals = grid[mline[1]] if mline[0] == 'r' else [row[mline[1]] for row in grid]
                alt = [] if any((ed_parse_cell(v) or {}).get('value') for v in vals) else [
                    (mline[0], k) for k in (mline[1] - 1, mline[1] + 1)
                    if 0 <= k < size and ed_label_in(ml['measure'], ed_line_text(grid, (mline[0], k)))]
                if len(alt) == 1:
                    mflags.append('模型写的指标「%s」差了一格，按表头改成「%s%d」' % (ml['line'], alt[0][0], alt[0][1] + 1))
                    mline = alt[0]
                else:
                    mflags.append('指标「%s」的表头和模型写的「%s」对不上' % (ml['line'], ml['measure']))
            mctx = ed_line_context(grid, mline)
            part = ml.get('part') or None
            lines_u = unresolved.get('%s.%s' % (tid, ml['line'])) or unresolved.get(tid)
            by_line = collections.defaultdict(list)
            for sl in tn['sample_lines']:
                sline = ed_parse_line(sl['line'], grid)
                if not sline or sline[0] == mline[0]:
                    continue
                only = [ed_parse_line(x, grid) for x in sl.get('only_lines') or []]
                if only and orig not in only and mline not in only:
                    continue
                by_line[sline].append(sl)
            for sline, sls in by_line.items():
                r, c = (mline[1], sline[1]) if mline[0] == 'r' else (sline[1], mline[1])
                if (r, c, part) in seen:
                    continue
                seen.add((r, c, part))
                flags = list(mflags)
                sl, note_pick = pick_sample(sls, mctx)
                if sl:
                    status = '已对应'
                    if note_pick:
                        flags.append(note_pick)
                    stext = ed_group_text(doc, table, sline) + ' ' + ed_line_context(grid, sline)
                    s = samples.get(sl['sample_id'])
                    if s and not note_pick and not any(ed_label_in(lb, stext) for lb in s.get('labels') or []):
                        flags.append('样品「%s」的表头里没有样品「%s」的名称' % (sl['line'], sl['sample_id']))
                    su = unresolved.get('%s.%s' % (tid, sl['line'])) or lines_u
                    if su:
                        status = '条件未确定：%s' % su
                    sid, conds = sl['sample_id'], list(ml.get('conditions') or []) + list(sl.get('conditions') or [])
                else:
                    status = '对应冲突：%s对了几个样品（%s），分不出这一格是哪个' % (
                        sls[0]['line'], '、'.join(dict.fromkeys(x['sample_id'] for x in sls)))
                    sid, conds = '', list(ml.get('conditions') or [])
                table_point(r, c, part, sid, ml['property'], ml['measure'], ml.get('unit'), conds, status, flags,
                            ed_header_of(grid, sline))

        # 逐格写的（堆叠表等，acsfoodscitech.5c00893 表 2：每行是「指标 × 样品」、列是贮藏条件）
        for cn in tn.get('cells') or []:
            m = re.fullmatch(r'\s*(?:T\d+\.)?r(\d+)\.?c(\d+)\s*', cn.get('cell') or '')
            if not m:
                continue
            r, c = int(m.group(1)) - 1, int(m.group(2)) - 1
            part = cn.get('part') or None
            if not (0 <= r < len(grid) and 0 <= c < len(grid[0])) or (r, c, part) in seen:
                continue
            seen.add((r, c, part))
            flags = list(tflags)
            above = next((grid[r2][c] for r2 in range(r - 1, -1, -1)
                          if grid[r2][c].strip() and not (ed_parse_cell(grid[r2][c]) or {}).get('value')), '')
            ctx = ' '.join((ed_line_text(grid, ('r', r)), ed_line_context(grid, ('c', c)), ed_norm_text(above),
                            ed_norm_text(table['caption'] or '')))
            if not ed_label_in(cn['measure'], ctx):
                flags.append('格子「%s」的行列表头和模型写的「%s」对不上' % (cn['cell'], cn['measure']))
            s = samples.get(cn['sample_id'])
            if s and not any(ed_label_in(lb, ed_line_text(grid, ('r', r)) + ' ' + ed_line_text(grid, ('c', c)))
                             for lb in s.get('labels') or []):
                flags.append('格子「%s」所在的行列里没有样品「%s」的名称' % (cn['cell'], cn['sample_id']))
            status = '已对应'
            su = unresolved.get('%s.%s' % (tid, cn['cell'].strip()))
            if su:
                status = '条件未确定：%s' % su
            table_point(r, c, part, cn['sample_id'], cn['property'], cn['measure'], cn.get('unit'),
                        list(cn.get('conditions') or []), status, flags, ed_header_of(grid, ('r', r)))

    # ---- 正文数值：数字在原句里、原句在原文里（不在引言里）才算；数值是模型抄的，所以每条都要核对
    for tv in note.get('text_values') or []:
        flags, problem = [], None
        quote = tv.get('quote') or ''
        val = ed_num_text(tv.get('value'))
        sd = ed_num_text(tv.get('sd')) if tv.get('sd') else ''
        if val is None:
            problem = '核对不过：数值「%s」不是单个数字' % tv.get('value')
        elif not ed_quote_found(quote, doc['body_text']):
            problem = ('核对不过：原句在引言里（引用的文献数据，不是本研究的）' if ed_quote_found(quote, doc['intro_text'])
                       else '核对不过：原句在原文里没找到')
        elif not ed_number_in(val, quote):
            problem = '核对不过：原句里没有数字 %s' % val
        elif tv.get('sd') and (sd is None or not ed_number_in(sd, quote)):
            problem = '核对不过：原句里没有 SD %s' % tv.get('sd')
        elif not ed_mention_in_quote(tv.get('sample_mention'), quote):
            problem = '核对不过：原句里找不到点名样品的词「%s」' % (tv.get('sample_mention') or '')
        elif not ed_explicit_mention(tv['sample_mention'], samples.get(tv.get('sample_id') or ''), samples):
            problem = '核对不过：原句没有明确指向哪个样品（「%s」）' % tv['sample_mention']
        sid = tv.get('sample_id') or ''
        status = problem or '已对应'
        if not problem and sid not in samples:
            status = '条件未确定：样品编号 %s 不在样品清单里' % sid
        elif not problem and sid in dup_ids:
            status = '对应冲突：样品编号 %s 在样品清单里出现了两次' % sid
        reason = None
        why = skip_reason(types.SimpleNamespace(protein_system=True, functional_property=tv['property'],
                                                   x_axis_label='', y_axis_label=tv.get('measure') or ''))
        if why:
            reason = '按现行读图规则不读：%s' % why
        row = dict(base)
        row['_scope'] = '正文'
        row['_mkey'] = tv.get('measure') or ''
        row.update({'来源': '正文', '图表': '正文', '子图或指标': '', '面板编号': '', '系列': '', 'X': '', 'X单位': '',
                    'X含义': '', '数值': val if val is not None else (tv.get('value') or ''), '单位': tv.get('unit') or '',
                    '倍率': '', '误差下限': '', '误差上限': '', 'SD': sd or '', '显著性': '', '原始单元格': quote,
                    '判定': '作者原值', '指标代号': tv['property'], '指标': FUNCTIONAL.get(tv['property'], ''),
                    '测量名称': tv.get('measure') or ''})
        finish(row, sid if sid in samples else '', tv.get('conditions') or [], status, flags, reason)

    # ---- 一一对应核对：同一个面板（同一组表格）里，同一样品、同一指标、同一组条件只能有一个数
    # 同一条曲线被读成了几个名字（jf049583c 图 1：Filled square / Solid square，数值几乎一样）、又都对到同一个样品的，
    # 是重复读数，只留一个；名字不同、数值差得多的照旧判对应冲突
    by_series, yvals, xvals = collections.defaultdict(dict), collections.defaultdict(list), collections.defaultdict(list)
    for p in points:
        v = ed_num_key(p['数值'])
        if p['来源'] in ('图反读', '图片表格反读') and isinstance(v, float):
            by_series[(p['_scope'], p['系列'])][ed_norm_x(p['X'])] = v
            yvals[p['_scope']].append(v)
            if isinstance(ed_num_key(ed_norm_x(p['X'])), float):
                xvals[p['_scope']].append(ed_num_key(ed_norm_x(p['X'])))

    def x_close(scope, x1, x2):
        """两遍读同一个点，X 也会差一点（0.73 / 0.72、3.63 / 3.6）：差 3% 以内或不到 X 范围的 1% 算同一个 X。"""
        if x1 == x2:
            return True
        a, b = ed_num_key(x1), ed_num_key(x2)
        if not (isinstance(a, float) and isinstance(b, float)):
            return False
        xs = xvals[scope]
        rng = max(xs) - min(xs) if xs else 0
        return abs(a - b) <= max(0.03 * max(abs(a), abs(b)), 0.01 * rng)

    def same_curve(scope, s1, s2):
        a, b = by_series[(scope, s1)], by_series[(scope, s2)]
        pairs = []
        for x, y in a.items():
            m = [x2 for x2 in b if x_close(scope, x, x2)]
            if len(m) == 1:
                pairs.append((y, b[m[0]]))
        rng = max(yvals[scope]) - min(yvals[scope]) if yvals[scope] else 0
        return bool(pairs) and len(pairs) >= 0.8 * min(len(a), len(b)) and all(
            abs(y1 - y2) <= max(0.05 * max(abs(y1), abs(y2)), 0.02 * rng) for y1, y2 in pairs)
    dup_reads = 0
    clash = collections.defaultdict(list)
    for p in points:
        if p['对应状态'] == '已对应' and p['数值'] != '':
            clash[(p['_scope'], p['样品编号'], p['指标代号'], ed_norm_text(p['_mkey']), ed_norm_text(p['单位']),
                   ed_norm_text(p['测定条件']))].append(p)
    for group in clash.values():
        if len(group) > 1:
            vals = '、'.join(p['数值'] for p in group)
            if group[0]['来源'] == '正文' and len({ed_num_key(p['数值']) for p in group}) == 1:
                for p in group[1:]:                   # 正文里同一个数写了几遍（摘要、结果、结论）：只留一个
                    p['_drop'] = True
                continue
            if group[0]['来源'] == '作者表格' and len({(ed_num_key(p['数值']), p['SD']) for p in group}) == 1:
                for p in group[1:]:                   # 作者表格里同一样品的同一个数列了两遍（acsfoodscitech.2c00082）
                    p['_drop'] = True
                group[0]['提醒'] = '；'.join(x for x in (group[0]['提醒'], '表格里同一个数出现了 %d 次（%s），只留一个' % (
                    len(group), '、'.join(p['面板编号'] for p in group))) if x)
                continue
            first = group[0]
            if first['来源'] in ('图反读', '图片表格反读') \
                    and all(x_close(first['_scope'], ed_norm_x(q['X']), ed_norm_x(first['X'])) for q in group) \
                    and len({q['系列'] for q in group}) > 1 \
                    and all(same_curve(first['_scope'], first['系列'], q['系列']) for q in group if q['系列'] != first['系列']):
                rank = {'通过': 0, '待复核': 1, '只有一遍': 2, '不通过': 3}
                keep = min(group, key=lambda q: rank.get(q['判定'], 9))
                for q in group:
                    if q is not keep:
                        q['_drop'] = True
                        dup_reads += 1
                continue
            if first['来源'] in ('图反读', '图片表格反读') and len({q['系列'] for q in group}) == 1 and \
                    (first.get('_xrole') == '样品' or len({ed_norm_x(q['X']) for q in group}) == 1) and \
                    all(isinstance(ed_num_key(q['数值']), float) for q in group):
                ys = [ed_num_key(q['数值']) for q in group]
                rng = max(yvals[first['_scope']]) - min(yvals[first['_scope']]) if yvals[first['_scope']] else 0
                if max(ys) - min(ys) <= max(0.10 * max(abs(max(ys)), abs(min(ys))), 0.05 * rng):
                    rank = {'通过': 0, '待复核': 1, '只有一遍': 2, '不通过': 3}
                    keep = min(group, key=lambda q: rank.get(q['判定'], 9))
                    keep['提醒'] = '；'.join(x for x in (keep['提醒'], '同一根柱子被读了几遍（横轴写法不同）：读数「%s」（%s），取「%s」' % (
                        vals, '、'.join(q['X'] for q in group), keep['数值'])) if x)
                    for q in group:
                        if q is not keep:
                            q['_drop'] = True
                            dup_reads += 1
                    continue
            if first['来源'] in ('图反读', '图片表格反读') and len({q['系列'] for q in group}) == len(group) \
                    and all(x_close(first['_scope'], ed_norm_x(q['X']), ed_norm_x(first['X'])) for q in group) \
                    and all(isinstance(ed_num_key(q['数值']), float) for q in group):
                # 几条曲线共用一个点（jf063211h 图 1：HMP、SSPS 两条线在 0% 处都画了同一个对照乳液，读成 -49.9 / -45.7）：
                # 读数相差 10% 以内或不到这张图数值范围的 5%，当同一个点——取判定更好的（一样取第一条曲线的），提醒里写上
                # 其余读数；差得多的照旧判冲突（用户 2026-10-14 定）
                ys = [ed_num_key(q['数值']) for q in group]
                rng = max(yvals[first['_scope']]) - min(yvals[first['_scope']]) if yvals[first['_scope']] else 0
                if max(ys) - min(ys) <= max(0.10 * max(abs(max(ys)), abs(min(ys))), 0.05 * rng):
                    rank = {'通过': 0, '待复核': 1, '只有一遍': 2, '不通过': 3}
                    keep = min(group, key=lambda q: rank.get(q['判定'], 9))
                    keep['提醒'] = '；'.join(x for x in (keep['提醒'], '几条曲线共用这个点（如对照）：读数「%s」（%s），取「%s」' % (
                        vals, '、'.join(q['系列'] for q in group), keep['数值'])) if x)
                    for q in group:
                        if q is not keep:
                            q['_drop'] = True
                            dup_reads += 1
                    continue
            if group[0]['来源'] not in ('作者表格', '正文') and len({(q['系列'], ed_norm_x(q['X'])) for q in group}) == 1:
                # 读图结果本身在同一系列、同一 X 上有几个读数（jf502412f 滴定曲线 pH 3.35 两个点）：样品和条件没对错，
                # 照旧算已对应，提醒一句，用的时候按判定栏筛
                for p in group:
                    p['提醒'] = '；'.join(x for x in (p['提醒'], '读图结果里同一系列同一 X 有 %d 个读数（%s）'
                                                    % (len(group), vals)) if x)
                continue
            for p in group:
                p['对应状态'] = '对应冲突：同一样品、同一指标、同一条件下有 %d 个数值（%s），条件没区分开' % (len(group), vals)
    in_table = {(p['样品编号'], p['指标代号'], ed_num_key(p['数值'])) for p in points
                if p['来源'] == '作者表格' and p['对应状态'] == '已对应'}
    for p in points:
        if p['来源'] == '正文' and p['对应状态'] == '已对应' and \
                (p['样品编号'], p['指标代号'], ed_num_key(p['数值'])) in in_table:
            p['_drop'] = True                         # 正文复述作者表格里的同一个数（acs.jafc.5c06047 DH 40.9）
    points = [p for p in points if not p.get('_drop')]
    for p in points:
        if p['样品编号'] and p['对应状态'] == '已对应':
            used[p['样品编号']] += 1

    # ---- 样品表
    sample_rows = []
    for sid, s in samples.items():
        ev = s.get('evidence') or []
        ok = sum(1 for q in ev if ed_quote_found(q, doc['author_text']))
        names = s.get('labels') or []
        known = doc['author_text'] + ' ' + doc['author_cells'] + ' ' + ed_norm_text(
            ' '.join(sr['name'] + ' ' + ' '.join(r.get('X', '') for r in sr['rows'])
                     for p in doc['panels'].values() for sr in p['series'].values()))
        miss = [n for n in names if ed_norm_text(n) and ed_norm_text(n) not in known]
        row = {'文章': doc['article'], 'DOI': doc['doi'], '样品编号': sid, '名称或缩写': ' / '.join(names)}
        f = ed_sample_fields(s)
        row.update({k: f[k] for k in ('样品说明', '蛋白来源', '蛋白类别', '蛋白形态', '蛋白浓度', '复配物', '处理', '处理类别',
                                     '处理温度', '处理时间', '处理pH', '体系')})
        row['原文依据'] = ' ‖ '.join(ev)
        row['原文核对'] = ('全部找到' if ok == len(ev) else '%d / %d 条找到' % (ok, len(ev))) if ev else '没给原文句子'
        row['名称核对'] = '全部找到' if not miss else '原文里没有：' + ' / '.join(miss)
        row['数据点数'] = used.get(sid, 0)
        sample_rows.append(row)
    stats = {'重复读数': dup_reads,
             '图的点': sum(1 for p in points if p['来源'] not in ('作者表格', '正文')),
             '正文的点': sum(1 for p in points if p['来源'] == '正文'),
             '表格的点': sum(1 for p in points if p['来源'] == '作者表格'),
             '已对应': sum(1 for p in points if p['对应状态'] == '已对应'),
             '条件未确定': sum(1 for p in points if p['对应状态'] != '已对应'),
             '排除的点': len(excluded), '样品数': len(samples),
             '没标注的面板': [pid for pid in doc['panels'] if pid not in pnotes],
             '对不上的编号': [x for x in pnotes if x not in doc['panels']] + [x for x in tnotes if x not in doc['tables']]}
    return points, excluded, sample_rows, stats


def ed_resolve_figure_point(pn, sid, x, unresolved, samples, x_unit):
    """一个图上的点（系列 × X）→ (样品编号, 测定条件列表, 对应状态, 提醒)。
    规则：匹配这个点的 assignments 里取最具体的一层（系列和 X 都写明 > 只写明一个 > 都是 *），这一层的样品编号必须恰好一个。
    X 是条件、但各个 X 分别对应不同样品时（jf405498k：蒸汽压力 0.5、1.0 MPa… 各是一个样品），X 已经是样品处理的一部分，
    不再重复写进测定条件。"""
    if not pn:
        return '', [], '条件未确定：模型没有标注这个面板', []
    pid = pn['panel_id'].strip()
    for key in (sid, pid):
        if key in unresolved:
            return '', [], '条件未确定：%s' % unresolved[key], []
    nx = ed_norm_x(x)
    hits = [a for a in pn.get('assignments') or []
            if a['series_id'].strip() in ('*', sid) and (a['x'].strip() == '*' or ed_norm_x(a['x']) == nx)]
    flags = []
    conds = list(pn.get('measurement_conditions') or [])
    for a in hits:
        conds += a.get('conditions') or []
    x_samples = {a['sample_id'] for a in pn.get('assignments') or [] if a['x'].strip() != '*' and a.get('sample_id')}
    with_sample = [a for a in hits if a.get('sample_id')]
    spec = lambda a: (a['series_id'].strip() != '*') + (a['x'].strip() != '*')
    top = max(spec(a) for a in with_sample) if with_sample else 0
    ids = list(dict.fromkeys(a['sample_id'] for a in with_sample if spec(a) == top))
    if pn.get('x_role') == '条件' and pn.get('x_variable') and x != '':
        # 各个 X 分别是不同样品时 X 已经是处理的一部分、不重复写；同一个样品在这条曲线上占了好几个 X（或 X 写 *）时，
        # X 就是区分这些点的测定条件，要写进去（jf047944i 图 1、acs.jafc.8b06679 图 2A）
        # 但同一个样品的几个 X 挨得很近（相差 3% 以内，jf001460e 图 8：横轴是平均分子量 7.0、7.1，读图多读出了点）不算条件，
        # 照旧判冲突、进待重读
        # X 写 * 要单独认：norm_x 会把 * 去掉（jf034563g 图 5A：系列 10 sec 的 X 写 *，原来没写进条件、5 个 pH 判成冲突）
        mine = {'*' if a['x'].strip() == '*' else ed_norm_x(a['x']) for a in pn.get('assignments') or []
                if len(ids) == 1 and a.get('sample_id') == ids[0] and a['series_id'].strip() in ('*', sid)}
        nums = sorted(v for v in (ed_num_key(m) for m in mine) if isinstance(v, float))
        crowded = any(b - a <= 0.03 * max(abs(a), abs(b)) for a, b in zip(nums, nums[1:]))
        if len(x_samples) <= 1 or ((len(mine) > 1 or '*' in mine) and not crowded):
            unit = pn.get('x_variable_unit') or x_unit or None
            if unit and re.sub(r'\s+', '', ed_norm_text(x)).endswith(re.sub(r'\s+', '', ed_norm_text(unit))):
                unit = None
            conds.append({'name': pn['x_variable'], 'value': x, 'unit': unit})
    ctext = conds
    if not with_sample:
        return '', ctext, '条件未确定：没有对应的样品', flags
    if len(ids) > 1:
        return '', ctext, '对应冲突：同一个点对应了 %s' % '、'.join(ids), flags
    if ids[0] not in samples:
        return '', ctext, '条件未确定：样品编号 %s 不在样品清单里' % ids[0], flags
    return ids[0], ctext, '已对应', flags


def ed_parse_line(text, grid):
    m = re.fullmatch(r'\s*(?:T\d+\.)?([rc])(\d+)\s*', text or '')
    if not m:
        return None
    kind, n = m.group(1), int(m.group(2)) - 1
    if n < 0 or n >= (len(grid) if kind == 'r' else len(grid[0])):
        return None
    return kind, n


def ed_group_text(doc, table, line):
    """核对表头用的文字：这一行（列）+ 表题；列再加上同一组拆开的表格里同一列（表头常在组里第一张表）；
    行再加上它上面最近的分组标题行（除第一格外全空，jf402221m「6. ANS」下面是「S₀」「S₀ in %」两行）。"""
    kind, n = line
    grid = table['grid']
    parts = [ed_line_text(grid, line), ed_norm_text(table['caption'] or '')]
    if kind == 'c':
        for t in doc['tables'].values():
            if t['group'] == table['group'] and t is not table and n < len(t['grid'][0]):
                parts.append(ed_line_text(t['grid'], line))
    else:
        for r in range(n - 1, -1, -1):
            if grid[r][0].strip() and not any(c.strip() for c in grid[r][1:]):
                parts.append(ed_norm_text(grid[r][0]))
                break
    return ' '.join(parts)


def ed_line_text(grid, line):
    kind, n = line
    return ed_norm_text(' '.join(grid[n] if kind == 'r' else [row[n] for row in grid]))


def ed_cell_parts(raw):
    """格子里并列的几个数（「3.63−6.81」「73.9/72.7」）拆开；数字（或显著性字母）和数字之间的横线、斜线、分号算分隔，
    开头的负号不算。"""
    t = unicodedata.normalize('NFKC', raw).translate(ed_DASHES)
    return [x.strip() for x in re.split(r'(?<=[\w*])\s*-\s*(?=\d)|\s*[/;]\s*', t) if x.strip()]


def ed_line_context(grid, line):
    """一行（列）自己的分组表头（不含表题）：列取数据以上各行，合并单元格留下的空格向左补齐
    （jf071117a 表 1「| | HPI | | SPI | |」下面是 MC TSM MC TSM）；行取第一格（空的向上补齐）和上面最近的分组标题行。"""
    kind, n = line
    out = []
    if kind == 'c':
        for r in range(len(grid)):
            if (ed_parse_cell(grid[r][n]) or {}).get('value'):
                break
            k = n
            while k > 1 and not grid[r][k].strip():
                k -= 1
            out.append(grid[r][k])
    else:
        r = n
        while r > 0 and not grid[r][0].strip():
            r -= 1
        out.append(grid[r][0])
        for r2 in range(n - 1, -1, -1):
            if grid[r2][0].strip() and not any(c.strip() for c in grid[r2][1:]):
                out.append(grid[r2][0])
                break
    return ed_norm_text(' '.join(out))


def ed_word_in(label, text):
    lab = ed_norm_text(label)
    return bool(lab) and re.search(r'(?<!\w)%s(?!\w)' % re.escape(lab), text) is not None


def ed_header_of(grid, line):
    """样品那一行（列）的表头：行取前几格里第一个不是数的，列取前几行里不是数的拼起来。"""
    kind, n = line
    vals = grid[n][:3] if kind == 'r' else [row[n] for row in grid[:4]]
    vals = [v for v in vals if v and not (ed_parse_cell(v) or {}).get('value')]
    return ' / '.join(dict.fromkeys(vals))


def ed_label_in(label, text):
    """模型写的表头 / 样品名能不能在那一行（列）里找到：整串找到，或者 ≥60% 的词找到。"""
    lab = ed_norm_text(label)
    if not lab:
        return False
    if lab in text:
        return True
    words = [w for w in re.findall(r'[\w.%-]+', lab) if len(w) > 1]
    return bool(words) and sum(1 for w in words if w in text) >= 0.6 * len(words)


# ================================================================ 选文章 ==
ed_TABLE_HINT = re.compile(
    r'solubilit|soluble protein|\bNSI\b|emulsif|\bEAI\b|\bESI\b|emulsion stabilit|creaming|foam|overrun|gel strength|'
    r'gelation|\bLGC\b|water[- ](?:holding|binding|absorption)|\bWHC\b|\bWAC\b|\bWBC\b|swelling|oil[- ](?:holding|binding|'
    r'absorption)|\bOHC\b|\bOAC\b|\bOBC\b|fat absorption|particle size|droplet size|D\[4,3\]|D\[3,2\]|z-average|'
    r'hydrodynamic|mean diameter|zeta|ζ|\bPDI\b|polydispersity|sulfhydryl|sulphydryl|\bSH\b|thiol|disulfide|disulphide|'
    r'S[-–]S|hydrophobicity|\bH0\b|H₀|\bS0\b|turbidity|degree of hydrolysis|\bDH\b|free amino|amino group|'
    r'encapsulation|loading capacity|entrapment|\bEE\b|antioxid|DPPH|ABTS|FRAP|ORAC|scaveng|reducing power|chelat', re.I)


def ed_candidates(doc):
    """有反读表、或有作者表格的表题 / 表头 / 首列提到 17 项的，才值得发给模型。"""
    if doc['panels']:
        return True
    for t in doc['tables'].values():
        probe = ' '.join([t['caption'] or ''] + t['grid'][0] + [row[0] for row in t['grid']] +
                         (t['grid'][1] if len(t['grid']) > 1 else []))
        if ed_TABLE_HINT.search(probe):
            return True
    return False


def ed_all_merged(root):
    """总文件夹里全部合并稿（<文章>\\全文合并.md），按文章名排（和原来按 <文章名>.md 排的顺序一样，--sample 抽到的照旧）。"""
    base = ed_papers_dir(root)
    found = [os.path.join(base, n, ed_MERGED_NAME) for n in os.listdir(base)] if os.path.isdir(base) else []
    return sorted((p for p in found if os.path.isfile(p)), key=lambda p: ed_article_of(p) + '.md')


def ed_pick(args):
    paths = []
    for x in args.papers:
        if os.path.isfile(x):
            p = x
        elif os.path.isdir(x):
            p = os.path.join(x, ed_MERGED_NAME)
        else:
            p = ed_merged_path(args.root, x[:-3] if x.endswith('.md') else x)
        if not os.path.isfile(p):
            raise SystemExit('找不到合并稿：%s' % x)
        paths.append(p)
    every = ed_all_merged(args.root)
    if args.sample and not args.only_with_data:
        # 全量是 7375 篇全发（用户 2026-10-13），试跑也从全部文章里按实际比例随机抽，才代表得了全量
        paths += random.Random(ed_SAMPLE_SEED).sample(every, min(args.sample, len(every)))
    elif args.sample:
        docs = [ed_parse_doc(p) for p in every]
        fig = [d['path'] for d in docs if d['panels']]
        tab = [d['path'] for d in docs if not d['panels'] and ed_candidates(d)]
        rnd = random.Random(ed_SAMPLE_SEED)
        n_tab = args.sample * 2 // 5
        paths += rnd.sample(fig, min(args.sample - n_tab, len(fig))) + rnd.sample(tab, min(n_tab, len(tab)))
    if not paths and not args.build_only:
        paths = every
    paths = list(dict.fromkeys(paths))
    return paths[:args.limit] if args.limit else paths


# ================================================================ 每篇的数据表 ==
# 用户 2026-10-13 晚：每篇文章单独一个文件、不合并；回到「一行一个样品」的宽表，但行列对调——最上面是论文题目和 DOI，
# 表头是 样品1、样品2…（一个样品一列），每一行是一项：样品组成、处理条件、17 项性质。所有文章格式统一：
# 行的名称和顺序固定，17 项每篇都有（没有数值的格子空着）
ed_SRC_RANK = {'作者表格': 0, '正文': 1, '图片表格反读': 2, '图反读': 3}
# 用户 2026-10-19：样品处理和 17 项的测试方法要分清楚、不让人混淆 → 处理相关的行都叫「样品处理…」，测定方法叫「测试方法」
ed_INFO_ROWS = ['样品名称', '样品说明', '蛋白来源', '蛋白类别', '蛋白形态', '蛋白浓度', '复配物', '样品处理方法',
             '样品处理类别', '样品处理温度', '样品处理时间', '样品处理pH', '体系']
ed_PROP_ROWS = list(FUNCTIONAL.values())                 # 17 项，顺序同 figure_reader.FUNCTIONAL
ed_ENTRY_SEP = '<br>'

ed_FORMAT_DOC = """# 每篇数据文件的格式

每篇文章的文件夹 `papers\\<文章名>\\` 里一个 `datapoint.md`（文章名 = DOI 里的 / 换成 _），结构固定、所有文章都一样：

1. 第一行 `# 论文题目`，第三行 `DOI: …`
2. `## 样品数据`：一张表，**一列一个样品**（表头 `项目 | 样品1 | 样品2 | …`；组成或处理有任何不同就是不同的样品；
   **只收含蛋白质的样品**，标准与读图相同，不含蛋白质的样品的数值列在「排除的数据」），
   **行固定、顺序固定**：
   {rows}
   - 没有的项留空，行一定在；17 项性质每篇都有
   - 样品处理方法：`方法（参数, 参数）→ 下一步`，按先后顺序。参数只写数值和单位（温度、时间、压力、功率、频率、酶、试剂这类
     看单位就知道，不写名称；pH 写成 `pH 9`；其他写 `名称 数值 单位`）。各步属于物理法 / 化学法 / 生物法 / 复合法见「样品处理类别」行。
     样品处理是样品在测定之前经过的制备和改性（超声、加热、酶解、糖基化…），和下面 17 项性质的「测试方法」是两回事
   - 所有样品都经过的相同步骤只在表格上方写一次：`所有样品共同的样品前处理：…`（在各列的处理之前）、
     `所有样品共同的样品后处理：…`（之后）；各列只写自己的步骤。一个样品的完整样品处理 = 共同前处理 → 本列 → 共同后处理；
     本列没有自己的步骤写「（仅共同处理）」，完全没处理写「未处理」
   - 样品处理温度、样品处理时间、样品处理pH：从完整样品处理里摘出来的（含共同处理）；几步都有时写 `方法: 值`，用 ` | ` 分开
   - 复配物：`名称（类别，用量）; …`
   - 17 项性质每格可以有多个数值，用 `<br>` 分开；每个数值的写法固定为
     `测量名称 = 数值 ± SD 单位（轴倍率 …）（误差棒 低–高） 显著性｜测定条件`
     · **数值后面带 `*` 的是读图得到的（数据来源于模型推断）**；不带 `*` 的是作者表格或正文里的原值
     · ± SD、单位、轴倍率、误差棒、显著性：原文没有就不写；测定条件写成 `名称=值 单位; …`，没有测定条件就不写「｜」那一段
     · 同一格里按来源排：作者表格 → 正文 → 读图
     · 已经提取过测试方法的文章（extract_method.py，用户 2026-10-19 加），每个数值最后再加一段 `｜测试方法 M1 Bradford 法`
       （测试方法编号 + 名称，详见下面「测试方法」一节）；原文没写的写 `｜测试方法 原文未写明`，这一项用了几种测试方法、
       分不清这个数用的哪种的写 `｜测试方法 不确定`
   - 表格下面一节 `## 测试方法`（提取过测试方法的文章才有）：17 项性质各是怎么测的（不是样品处理）。每种测试方法一行——
     编号、性质、测试方法、原文叫法、关键参数（离心力、测定时蛋白浓度、波长、探针…）、出处、仪器、对应图表、数值个数；
     然后是原文没写测试方法的性质、测试方法的原文依据句子
3. `## 样品原文依据`：每个样品的组成、处理在原文里的依据句子，以及正文数值的原句
4. `## 未进表的数据`：对应不上样品、或核对不过的数值；没有写「（无）」
5. `## 排除的数据`：不在 17 项、或按现行读图规则不读的；没有写「（无）」
6. `## 模型判断不了的编号`：没有写「（无）」
7. `## 说明`：解读模型、时间、统计

表里的每个数值都满足：恰好对应一个样品；同一样品、同一指标、同一组测定条件下只有一个数（来源不同的各留一个）；
正文数值的数字在原句里、原句在原文里（不在引言里），而且原句明确点名了样品（名称、缩写、处理参数或 control 这类说法），
「在较高压力下」这类模糊的不收。
""".format(rows='、'.join(ed_INFO_ROWS + ed_PROP_ROWS))


def ed_vu(p):
    return ('%s %s' % (p.get('value', ''), p.get('unit') or '')).strip()


def ed_param_key(name):
    """处理参数名 → 摘到哪一行（温度 / 时间 / pH），其余只留在处理方法里。"""
    n = ' '.join((name or '').casefold().split())
    if n == 'ph' or n.startswith('ph ') or n.endswith(' ph'):
        return 'ph'
    if 'temperature' in n or n == 'temp':
        return 'temperature'
    if n == 'time' or n.endswith(' time') or n.startswith('time ') or 'duration' in n:
        return 'time'
    return ''


def ed_step_values(s, key):
    """处理温度 / 时间 / pH：几步都有时写「方法: 值」。"""
    found = [(st.get('method', ''), ed_vu(p)) for st in s.get('processing') or [] for p in st.get('params') or []
             if ed_param_key(p.get('name')) == key]
    if len({m for m, _ in found}) > 1:
        return ' | '.join('%s: %s' % mv for mv in found)
    return ' | '.join(v for _, v in found)


ed_PLAIN_PARAMS = ('temperature', 'temp', 'time', 'duration', 'pressure', 'power', 'frequency', 'amplitude', 'speed',
                'enzyme', 'enzyme dosage', 'reagent', 'reagent concentration', 'dose', 'dosage')


def ed_param_short(p):
    """一个处理参数的简写：看单位就知道的只写数值和单位；pH 写成「pH 9」；其他写「名称 数值 单位」。"""
    n = ' '.join((p.get('name') or '').casefold().split())
    v = ed_vu(p)
    if n in ed_PLAIN_PARAMS:
        return v
    if n == 'ph' or n.startswith('ph ') or n.endswith(' ph'):
        return 'pH %s' % v
    return '%s %s' % (p.get('name', ''), v)


def ed_step_text(st):
    """一步处理的简写：方法（参数, 参数）；类别不写（在「处理类别」行）。"""
    params = ', '.join(ed_param_short(p) for p in st.get('params') or [])
    return '%s（%s）' % (st.get('method', ''), params) if params else st.get('method', '')


def ed_common_steps(chains):
    """所有样品都相同的前几步和后几步（按简写比）：返回 (前几步, 后几步)。只有一个样品、或有样品没处理时不提取。"""
    if len(chains) < 2 or not all(chains):
        return 0, 0
    n = min(len(c) for c in chains)
    k = 0
    while k < n and all(c[k] == chains[0][k] for c in chains):
        k += 1
    j = 0
    while j < n - k and all(c[len(c) - 1 - j] == chains[0][len(chains[0]) - 1 - j] for c in chains):
        j += 1
    return k, j


def ed_sample_info(s):
    ing = s.get('ingredients') or []
    steps = s.get('processing') or []
    return {'样品名称': ' / '.join(s.get('labels') or []), '样品说明': s.get('description') or '',
            '蛋白来源': s.get('protein_source') or '', '蛋白类别': s.get('protein_category') or '',
            '蛋白形态': s.get('protein_form') or '', '蛋白浓度': s.get('protein_concentration') or '',
            '复配物': '; '.join('%s（%s%s）' % (x.get('name', ''), x.get('category', ''),
                                             '，' + x['amount'] if x.get('amount') else '') for x in ing),
            '样品处理方法': ' → '.join(ed_step_text(st) for st in steps) or '未处理',
            '样品处理类别': '、'.join(dict.fromkeys(st.get('category', '') for st in steps)),
            '样品处理温度': ed_step_values(s, 'temperature'), '样品处理时间': ed_step_values(s, 'time'),
            '样品处理pH': ed_step_values(s, 'ph'), '体系': s.get('system') or ''}


def ed_source_label(p):
    """未进表、排除两节里的来源位置（样品数据表里不写来源，读图的数值打 *）。"""
    if p['来源'] == '作者表格':
        return '表 %s' % p['图表']
    if p['来源'] == '正文':
        return '正文'
    where = p['图表'] + (' ' + p['子图或指标'] if p['子图或指标'] else '')
    if p['来源'] == '图反读':
        return '图 %s*' % where
    return '表 %s（图片版）*' % where


def ed_entry_text(p, method=None):
    """一个数值的写法：测量名称 = 数值 ± SD 单位（轴倍率）（误差棒） 显著性｜测定条件｜方法 M1 …。
    读图得到的数值后面打 *（数据来源于模型推断），作者表格、正文的原值不打（用户 2026-10-13）；没有测定条件不写「｜」那段；
    method 是这个数的方法标注（method_tag），这篇还没提取方法时为 None、不写。"""
    val = p['数值'] if p['数值'] != '' else (p['原始单元格'] if p['来源'] == '作者表格' else '')
    star = '*' if p['来源'] in ('图反读', '图片表格反读') else ''
    text = '%s = %s%s' % (p['测量名称'] or p['系列'] or p['指标'], val, star)
    if p.get('SD'):
        text += ' ± %s' % p['SD']
    if p.get('单位'):
        text += ' %s' % p['单位']
    if p.get('倍率') and p['倍率'] not in ('1', '×1', 'x1'):
        text += '（轴倍率 %s）' % p['倍率']
    if p.get('误差下限') or p.get('误差上限'):
        text += '（误差棒 %s–%s）' % (p.get('误差下限') or '?', p.get('误差上限') or '?')
    if p.get('显著性'):
        text += ' %s' % p['显著性']
    return text + ('｜' + p['测定条件'] if p['测定条件'] else '') + ('｜测试方法 ' + method if method else '')


# ================================================================ 测定方法（用户 2026-10-19） ==
# extract_method.py 从方法部分提取每项性质的测定方法、核对原文后写每篇文件夹里的 method.json；这里把方法挂到每个数值上。
# 挂法只写这一份，datapoint.md、建库（build_database.py）、方法提取的报告都用它
ed_METHOD_KEYWORDS = {'dpph', 'abts', 'frap', 'orac', 'tbars', 'eai', 'esi', 'opa', 'tnbs', 'ans', 'prodan', 'cpa', 'dls',
                   'nta', 'bradford', 'lowry', 'bca', 'kjeldahl', 'dumas', 'biuret', 'hydroxyl', 'chelating', 'reducing',
                   'ellman', 'dtnb', 'ninhydrin'}
ed_NO_METHOD = '原文未写明方法'


def ed_method_file(article, mdir=None):
    """这篇的测定方法文件：默认每篇文件夹里的 method.json；给了目录（老结构）是 <目录>\\<文章名>.json。"""
    mdir = mdir or ed_METHOD_DIR
    return os.path.join(mdir, article + '.json') if mdir else os.path.join(ed_PAPERS, article, ed_METHOD_NAME)


def ed_load_paper_methods(article, mdir=None):
    p = ed_method_file(article, mdir)
    if not os.path.exists(p):
        return None
    try:
        return json.loads(ed_read(p))
    except ValueError:
        return None


def ed_assign_methods(items, methods):
    """items：[(性质代号, 图表, 测量名称)] → [(方法编号或 '', 状态)]。这一项只有一种方法就挂它；有几种时依次按图表、
    测量名称、测量名称里的方法关键词（DPPH、EAI…）分，只剩一种才挂，分不清标「方法不确定」；没有方法标「原文未写明方法」。"""
    by_prop = collections.defaultdict(list)
    for m in methods:
        by_prop[m['property']].append(m)
    out = []
    for prop, item, name in items:
        cands = by_prop.get(prop, [])
        if not cands:
            out.append(('', ed_NO_METHOD))
            continue
        if len(cands) == 1:
            out.append((cands[0]['method_id'], '已对应'))
            continue
        c1 = [m for m in cands if item in (m.get('applies_to') or [])]
        if len(c1) == 1:
            out.append((c1[0]['method_id'], '已对应'))
            continue
        pool = c1 or cands
        n = ed_norm_text(name)
        c2 = [m for m in pool if any(ed_norm_text(x) == n for x in m.get('measure_names') or [])]
        if len(c2) == 1:
            out.append((c2[0]['method_id'], '已对应'))
            continue
        words = set(re.findall(r'[a-z0-9]+', n)) & ed_METHOD_KEYWORDS
        c3 = [m for m in pool if set(re.findall(r'[a-z0-9]+', ed_norm_text(m['method'] + ' ' + m.get('method_raw', ''))))
              & words]
        if len(c3) == 1:
            out.append((c3[0]['method_id'], '已对应'))
            continue
        out.append(('', '方法不确定：这一项有 %d 种方法，分不清这个数用的哪种' % len(cands)))
    return out


def ed_method_tag(m, status):
    """数值后面的方法标注：「M1 Bradford 法」/「原文未写明」/「不确定」。"""
    if m:
        return '%s %s' % (m['method_id'], m['method'])
    return '原文未写明' if status == ed_NO_METHOD else '不确定'


def ed_point_methods(article, points, mdir=None):
    """这篇的方法 + 每个数值（按 points 的顺序）的 (方法编号, 状态)；还没提取方法返回 (None, None)。"""
    pm = ed_load_paper_methods(article, mdir)
    if pm is None:
        return None, None
    return pm, ed_assign_methods([(p['指标代号'], p['图表'], p['测量名称'] or p['系列'] or p['指标']) for p in points],
                              pm['methods'])


def ed_method_params_text(m):
    return '; '.join('%s=%s' % (x.get('name', ''), ('%s %s' % (x.get('value', ''), x.get('unit') or '')).strip())
                     for x in m.get('params') or [])


def ed_md_cell(v):
    return ' '.join(str(v if v is not None else '').split()).replace('|', '\\|')


def ed_md_table(header, rows):
    out = ['| ' + ' | '.join(ed_md_cell(h) for h in header) + ' |', '|' + '---|' * len(header)]
    out += ['| ' + ' | '.join(ed_md_cell(x) for x in r) + ' |' for r in rows]
    return out


def ed_method_section(pm, asg):
    """「## 测试方法」一节：17 项性质怎么测的（不是样品处理）。每种一行（参数、出处、仪器、对应图表、数值个数），
    原文没写测试方法的性质，原文依据。"""
    n_by = collections.Counter(mid for mid, _ in asg)
    lines = ['## 测试方法', '', '17 项性质各是怎么测的（不是样品处理方法；样品处理见上表「样品处理方法」行）。', '']
    if pm['methods']:
        lines += ed_md_table(['编号', '性质', '测试方法', '原文叫法', '关键参数', '出处', '仪器', '对应图表', '数值个数'],
                          [[m['method_id'], FUNCTIONAL.get(m['property'], m['property']), m['method'],
                            m.get('method_raw') or '', ed_method_params_text(m), m.get('reference') or '',
                            m.get('instrument') or '', '、'.join(m.get('applies_to') or []), n_by.get(m['method_id'], 0)]
                           for m in pm['methods']])
    else:
        lines.append('（原文里没找到测试方法）')
    notes = ['- 原文没写测试方法的性质：%s' % '；'.join('%s（%s）' % (FUNCTIONAL.get(x['property'], x['property']), x['reason'])
                                              for x in pm['not_described'])] if pm['not_described'] else []
    n_none = sum(1 for _, st in asg if st == ed_NO_METHOD)
    n_amb = sum(1 for _, st in asg if st.startswith('方法不确定'))
    if n_none:
        notes.append('- 标「测试方法 原文未写明」的数值 %d 个' % n_none)
    if n_amb:
        notes.append('- 标「测试方法 不确定」的数值 %d 个（这一项用了几种测试方法，分不清这个数用的哪种）' % n_amb)
    if notes:
        lines += [''] + notes
    ev = [(m['method_id'], q, ok) for m in pm['methods'] for q, ok in zip(m.get('evidence') or [],
                                                                        m.get('evidence_found') or [])]
    if ev:
        lines += ['', '测试方法的原文依据：', '']
        lines += ['- %s：「%s」%s' % (mid, ' '.join(q.split()), '' if ok else '（原文里没找到）') for mid, q, ok in ev]
    return lines


def ed_render_md(doc, c, points, excluded, stats):
    """每篇一个文件：题目、DOI，然后样品数据表（一列一个样品，行固定），再是原文依据和核对用的几节。"""
    note = c['output']
    samples = collections.OrderedDict((s['sample_id'], s) for s in note['samples'])
    ok = [p for p in points if p['对应状态'] == '已对应' and p['样品编号'] in samples]
    left = [p for p in points if not (p['对应状态'] == '已对应' and p['样品编号'] in samples)]
    shown = [sid for sid in samples if any(p['样品编号'] == sid for p in ok)]       # 有数值的样品才占一列
    col = {sid: '样品%d' % k for k, sid in enumerate(shown, 1)}
    pm, asg = ed_point_methods(doc['article'], ok) if ok else (None, None)     # 没有数值的文章不写测试方法
    tags = {}
    if pm is not None:
        mm = {m['method_id']: m for m in pm['methods']}
        tags = {id(p): ed_method_tag(mm.get(mid), st) for p, (mid, st) in zip(ok, asg)}
    infos = {sid: ed_sample_info(samples[sid]) for sid in shown}
    chains = [[ed_step_text(st) for st in samples[sid].get('processing') or []] for sid in shown]
    k, j = ed_common_steps(chains)
    if k or j:
        for sid, chain in zip(shown, chains):
            own = chain[k:len(chain) - j]
            infos[sid]['样品处理方法'] = ' → '.join(own) if own else '（仅共同处理）'
    rows = [[label] + [infos[sid][label] for sid in shown] for label in ed_INFO_ROWS]
    for code, cn in FUNCTIONAL.items():
        ed_cells = []
        for sid in shown:
            mine = sorted((p for p in ok if p['样品编号'] == sid and p['指标代号'] == code),
                          key=lambda p: ed_SRC_RANK.get(p['来源'], 9))
            ed_cells.append(ed_ENTRY_SEP.join(ed_entry_text(p, tags.get(id(p))) for p in mine))
        rows.append([cn] + ed_cells)
    lines = ['# %s' % doc['title'], '', 'DOI: %s' % doc['doi'], '', '## 样品数据', '']
    if k:
        lines.append('- 所有样品共同的样品前处理：%s' % ' → '.join(chains[0][:k]))
    if j:
        lines.append('- 所有样品共同的样品后处理：%s' % ' → '.join(chains[0][len(chains[0]) - j:]))
    if k or j:
        lines.append('')
    lines += ed_md_table(['项目'] + [col[sid] for sid in shown], rows)
    if pm is not None:
        lines += [''] + ed_method_section(pm, asg)

    lines += ['', '## 样品原文依据', '']
    if not shown:
        lines.append('（无）')
    for sid in shown:
        s = samples[sid]
        lines.append('### %s（模型编号 %s）' % (col[sid], sid))
        ev = s.get('evidence') or []
        lines += ['- 组成和处理：「%s」%s' % (' '.join(q.split()), '' if ed_quote_found(q, doc['author_text'])
                                             else '（原文里没找到）') for q in ev] or ['- 组成和处理：（模型没给原文句子）']
        for p in ok:
            if p['样品编号'] == sid and p['来源'] == '正文':
                lines.append('- 正文数值 %s = %s 的原句：「%s」' % (p['测量名称'], p['数值'],
                                                             ' '.join(p['原始单元格'].split())))
        lines.append('')

    lines += ['## 未进表的数据', '']
    if left:
        lines += ed_md_table(['指标', '测量名称', '数值', '单位', '测定条件', '来源', '原因'],
                          [[p['指标'], p['测量名称'], p['数值'] or p.get('原始单元格', ''), p['单位'], p['测定条件'],
                            ed_source_label(p) + ('，系列 %s，X=%s' % (p['系列'], p['X']) if p['来源'] in ('图反读', '图片表格反读')
                                               else ''), p['对应状态']] for p in left])
    else:
        lines.append('（无）')
    lines += ['', '## 排除的数据', '']
    if excluded:
        agg = collections.OrderedDict()
        for p in excluded:
            k = (ed_source_label(p), p['测量名称'] or p['系列'], p['排除原因'])
            agg[k] = agg.get(k, 0) + 1
        lines += ed_md_table(['来源', '测量名称', '点数', '原因'], [[k[0], k[1], v, k[2]] for k, v in agg.items()])
    else:
        lines.append('（无）')
    lines += ['', '## 模型判断不了的编号', '']
    notes = ['- %s：%s' % (u['item_id'], u['reason']) for u in note['unresolved']]
    if stats['没标注的面板']:
        notes.append('- （程序核对）模型没标注的面板：' + '、'.join(stats['没标注的面板']))
    if stats['对不上的编号']:
        notes.append('- （程序核对）模型回答里有不存在的编号：' + '、'.join(stats['对不上的编号']))
    if c.get('finish_reason') not in (None, 'stop'):
        notes.append('- （程序核对）模型回答结束原因：%s' % c.get('finish_reason'))
    lines += notes or ['（无）']
    n_src = collections.Counter(p['来源'] for p in ok)
    no_protein = [sid for sid in samples if samples[sid].get('contains_protein') is False]
    no_data = [sid for sid in samples if sid not in col and sid not in no_protein]
    lines += ['', '## 说明', '',
              '- 合并稿：%s.md' % doc['article'],
              '- 样品和条件由 %s 从原文解读（%s）；数值由程序从反读表、作者表格、正文原句搬来并核对' % (c.get('model'), c.get('at')),
              '- 样品 %d 个（模型列出 %d 个%s）；进表数值 %d（作者表格 %d、正文 %d、图反读 %d）；未进表 %d；排除 %d' % (
                  len(shown), len(samples), ''.join(x for x in (
                      '，不含蛋白质、没收的：' + '、'.join('%s（%s）' % (sid, ' / '.join(samples[sid].get('labels') or [])[:60])
                                                     for sid in no_protein) if no_protein else '',
                      '，没有数值的：' + '、'.join(no_data) if no_data else '')), len(ok),
                  n_src['作者表格'], n_src['正文'], n_src['图反读'] + n_src['图片表格反读'], len(left), len(excluded))]
    if stats.get('重复读数'):
        lines.append('- 图里同一条曲线被读成了几个名字（如 Filled square / Solid square）的重复读数 %d 个，已合并只留一个'
                     % stats['重复读数'])
    return '\n'.join(lines).rstrip() + '\n'


# 用户 2026-11-10「下次运行别再问这三篇了」：不再问.tsv 里列的文章，数据点这一步不发给模型（问了也答不出：Gemini 安全过滤
# 每次回空、或回答长到写不完，每次跑都白等最多半小时），也不算出错，报告里单列一节。删掉那一行就照常再问。
ed_NO_ASK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '不再问.tsv')


def ed_load_no_ask(path=ed_NO_ASK):
    """不再问.tsv：{文章名: 原因}。每行「文章<Tab>原因」，# 开头的是说明。"""
    out = {}
    if os.path.exists(path):
        for line in io.open(path, encoding='utf-8'):
            line = line.rstrip('\r\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            name, _, why = line.partition('\t')
            if name.strip():
                out[name.strip()] = why.strip()
    return out


# ================================================================ 主程序 ==
def ed_main(argv=None):
    global ed_METHOD_DIR, ed_PAPERS
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    ap = argparse.ArgumentParser(description='全文合并 markdown → 每篇文件夹里一个 datapoint.md')
    ap.add_argument('papers', nargs='*', help='文章名、文章文件夹或合并稿路径；不给就是 --root 下全部文章')
    ap.add_argument('--root', default=ed_ROOT, help='总文件夹（文章在 <root>\\papers\\<文章>，没有 papers 子文件夹时直接在 <root> 下），'
                                                 '默认 %s；报告和模型回答缓存在 <root>\\_records\\数据点' % ed_ROOT)
    ap.add_argument('--sample', type=int, default=0, help='固定随机抽 N 篇试跑（从全部文章里抽；加 --only-with-data 时 3/5 有反读表、2/5 只有作者表格）')
    ap.add_argument('--limit', type=int, default=0, help='最多处理 N 篇')
    ap.add_argument('--only-with-data', action='store_true',
                    help='只发有反读表、或作者表格的表题/表头提到 17 项的文章（默认全部都发：用户 2026-10-13 定，'
                         '文章都是筛选过的，17 项数值也可能只写在正文里）')
    ap.add_argument('--dry-run', action='store_true', help='只写出要发给模型的文字，不调模型')
    ap.add_argument('--build-only', action='store_true', help='不调模型，用已有回答重新生成每篇的文件')
    ap.add_argument('--model', default=ed_MODEL, help='默认 %s；换别的模型时结果放 <root>\\_records\\数据点\\_模型对比\\<模型名>' % ed_MODEL)
    ap.add_argument('--provider', default='auto', help='OpenRouter 上限定哪一家（逗号隔开）；auto = 按模型名前缀，none = 不限定')
    ap.add_argument('--base-url', default='openrouter', help='openrouter（默认）/ openai（OpenAI 直连）/ 其他接口地址')
    ap.add_argument('--workers', type=int, default=ed_WORKERS, help='同时进行的请求数，默认 %d' % ed_WORKERS)
    ap.add_argument('--key-env', default=ed_KEY_ENV, help='放 API key 的环境变量，默认 %s' % ed_KEY_ENV)
    args = ap.parse_args(argv)
    if not os.path.isdir(args.root):
        raise SystemExit('找不到总文件夹：%s' % args.root)
    ed_PAPERS = ed_papers_dir(args.root)
    ed_METHOD_DIR = None                      # 测定方法读每篇文件夹里的 method.json
    rec_dir = ed_records_dir(args.root)
    t0 = time.time()
    paths = ed_pick(args)
    docs = {}
    n_data = 0
    for p in paths:
        d = ed_parse_doc(p)
        has = bool(d['panels'] or ed_candidates(d))
        n_data += has
        if has or not args.only_with_data:
            docs[d['article']] = d
    print('合并稿 %d 篇（有图反读表或含 17 项的作者表格的 %d 篇）；这次发给模型的 %d 篇%s' % (
        len(paths), n_data, len(docs), '（--only-with-data）' if args.only_with_data else '（全部）'), flush=True)
    cdir = os.path.join(rec_dir, ed_CACHE_DIR, ed_model_slug(args.model))
    # 默认模型：datapoint.md 写进每篇文件夹，格式说明、报告、待重读写 _records\数据点；别的模型全放 _模型对比\<模型名>
    official = model_key(args.model) == model_key(ed_MODEL)
    mdir = rec_dir if official else os.path.join(rec_dir, ed_COMPARE_DIR, ed_model_slug(args.model))

    def dp_path(name):
        return os.path.join(ed_PAPERS, name, ed_DATAPOINT_NAME) if official else os.path.join(mdir, name + '_datapoint.md')

    if args.dry_run:
        n_chars = 0
        for d in docs.values():
            text = ed_SYSTEM + '\n\n' + ed_user_text(d)
            n_chars += len(text)
            ed_atomic_write(os.path.join(rec_dir, ed_PREVIEW_DIR, d['article'] + '.txt'), text)
        print('已写出 %d 篇要发给模型的文字 -> %s（共 %s 字符，约 %s token）' % (
            len(docs), os.path.join(rec_dir, ed_PREVIEW_DIR), format(n_chars, ','), format(n_chars // 4, ',')))
        return 0

    errors = {}
    no_ask = ed_load_no_ask()
    full = not (args.papers or args.sample or args.limit)

    def no_answer(n):                         # --build-only 时 docs 是空的：看有没有这篇的回答存档
        if n in docs:
            return ed_load_cache(cdir, docs[n], args.model) is None
        return full and os.path.isfile(os.path.join(ed_PAPERS, n, ed_MERGED_NAME)) \
            and not os.path.isfile(os.path.join(cdir, n + '.json'))
    skipped = {n: why for n, why in no_ask.items() if no_answer(n)}
    if not args.build_only:
        todo = [d for d in docs.values() if d['article'] not in skipped and ed_load_cache(cdir, d, args.model) is None]
        print('要问模型的 %d 篇（其余 %d 篇已有回答、输入没变%s）' % (
            len(todo), len(docs) - len(todo) - len(skipped),
            '；%s 里的 %d 篇不问' % (os.path.basename(ed_NO_ASK), len(skipped)) if skipped else ''), flush=True)
        if todo:
            base = {'openrouter': OPENROUTER, 'openai': None}.get(args.base_url, args.base_url)
            prov = args.provider
            if prov == 'auto':
                prov = ed_PROVIDERS.get(args.model.split('/', 1)[0], '') if '/' in args.model else ''
            elif prov == 'none':
                prov = ''
            api = Api(model=args.model, workers=args.workers, key_env=args.key_env, base_url=base, provider=prov)
            print('模型 %s，经 %s；结果放 %s' % (args.model, api.where(), mdir), flush=True)
            with futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
                jobs = {ex.submit(ed_ask_one, api, cdir, d): d for d in todo}
                for job in futures.as_completed(jobs):
                    d = jobs[job]
                    try:
                        job.result()
                    except Fatal:
                        errors[d['article']] = '窗口停下：' + api.fatal
                    except Exception as e:
                        errors[d['article']] = '%s: %s' % (type(e).__name__, short_error(e))
                        ed_say('[%s] 出错：%s' % (d['article'], errors[d['article']]))

    # 写每篇的文件：这个模型所有有效回答的文章（分批跑也会累积，每篇各自一个文件）
    cached = sorted(os.path.splitext(f)[0] for f in os.listdir(cdir) if f.endswith('.json')) \
        if os.path.isdir(cdir) else []
    stale, totals = [], collections.Counter()
    status_count, prop_count, reason_count, flag_count = (collections.Counter() for _ in range(4))
    left_by_paper, reread = [], []
    for name in dict.fromkeys(cached + list(docs)):
        src_path = os.path.join(ed_PAPERS, name, ed_MERGED_NAME)
        d = docs.get(name) or (ed_parse_doc(src_path) if os.path.exists(src_path) else None)
        c = ed_load_cache(cdir, d, args.model) if d else None
        if c is None:
            if name in cached:
                stale.append(name)
            continue
        pts, exc, srows, st = ed_build_paper(d, c['output'])
        if ed_write_if_changed(dp_path(name), ed_render_md(d, c, pts, exc, st)):
            totals['改写'] += 1
        ok = [p for p in pts if p['对应状态'] == '已对应']
        totals.update({'文章': 1, '样品': len({p['样品编号'] for p in ok}), '数值': len(ok),
                       '未进表': len(pts) - len(ok), '排除': len(exc)})
        totals['费用'] += (c.get('usage') or {}).get('cost') or 0
        for p in ok:
            totals['来源:' + p['来源']] += 1
            prop_count[p['指标']] += 1
        for p in pts:
            status_count[re.sub(r'：.*', '', p['对应状态'])] += 1
            for f in p['提醒'].split('；'):
                if f:
                    flag_count[re.sub(r'「[^」]*」|（[^）]*）|\b[rc]\d+\b|\bS\d+\b', '…', f)] += 1
        for p in exc:
            reason_count[p['排除原因']] += 1
        if len(pts) > len(ok):
            left_by_paper.append((name, len(pts) - len(ok), len(ok)))
        listed = set()
        for u in c['output']['unresolved']:
            pid = '.'.join(u['item_id'].strip().split('.')[:2])
            if pid in d['panels']:
                panel = d['panels'][pid]
                listed.add(pid)
                reread.append((name, panel['item'], '' if panel['name'] == '-' else panel['name'], u['item_id'].strip(),
                               u['reason'], sum(1 for p in pts if p['面板编号'] == pid and p['对应状态'] != '已对应')))
        clash_pids = collections.Counter(p['面板编号'] for p in pts if p['面板编号'] in d['panels']
                                         and p['对应状态'].startswith('对应冲突：同一样品'))
        for pid, k in clash_pids.items():
            if pid not in listed:
                panel = d['panels'][pid]
                listed.add(pid)
                reread.append((name, panel['item'], '' if panel['name'] == '-' else panel['name'], pid,
                               '同一样品、同一条件下有几个不同的读数，又不像同一条曲线读了两遍（可能横轴或系列读错了）', k))
        none_pids = collections.Counter(p['面板编号'] for p in exc if p.get('排除原因') == ed_WHOLE_NONE)
        for pid, k in none_pids.items():
            if pid not in listed and pid in d['panels']:
                panel = d['panels'][pid]
                reread.append((name, panel['item'], '' if panel['name'] == '-' else panel['name'], pid,
                               '提取时看图注和系列名，整张子图都不是读图分类的「%s」（可能读错了子图，或分类错了）；'
                               '这些数先没收' % (panel['info'].get('property_cn') or ''), k))
    ed_atomic_write(os.path.join(mdir, '_格式说明.md'), ed_FORMAT_DOC)
    ed_atomic_write(os.path.join(mdir, ed_REREAD_NAME), ed_reread_text(reread, root=args.root))
    ed_write_report(args, mdir, totals, status_count, prop_count, reason_count, flag_count, left_by_paper, errors, stale,
                 time.time() - t0, skipped=skipped)
    print('datapoint.md %d 篇（内容有变、这次改写的 %d 篇，其余没动）：样品 %d、数值 %d（未进表 %d、排除 %d）；出错 %d 篇%s -> %s' % (
        totals['文章'], totals['改写'], totals['样品'], totals['数值'], totals['未进表'], totals['排除'], len(errors),
        '；不再问 %d 篇' % len(skipped) if skipped else '', '每篇文件夹（报告在 %s）' % mdir if official else mdir))
    return 1 if errors else 0


ed_SKIP_REREAD = os.path.join(os.path.dirname(os.path.abspath(__file__)), '不用重读.tsv')


def ed_load_skip_reread(path=ed_SKIP_REREAD):
    """不用重读.tsv：重读也没用的图（相关性散点图、方差分析主效应、力学质构类…），{(文章, 编号): 原因}。"""
    out = {}
    if os.path.exists(path):
        for line in io.open(path, encoding='utf-8'):
            parts = line.rstrip('\n').split('\t')
            if len(parts) >= 3 and not line.startswith('#'):
                out[(parts[0].strip(), parts[1].strip())] = parts[2].strip()
    return out


def ed_reread_text(rows, skip=None, root=ed_ROOT):
    """_待重读.md：模型说读图结果本身缺了信息、对不上样品的图（用户 2026-10-13：「你记住这一类文章 最后统一重读」）。
    每次运行按这个模型的全部回答重新汇总；全量跑完后照着它统一重读：读图 → 合并 → 提取。
    不用重读.tsv 里列的（重读也对不上的，用户 2026-10-15「按你的想法来」）单列一节，不进重读命令。"""
    skip = ed_load_skip_reread() if skip is None else skip

    def why_skip(a, iid):
        return next((r for (sa, sid), r in skip.items() if sa == a and (iid == sid or iid.startswith(sid + '.'))), None)
    todo = [r for r in rows if not why_skip(r[0], r[3])]
    skipped = [r + (why_skip(r[0], r[3]),) for r in rows if why_skip(r[0], r[3])]
    names = list(dict.fromkeys(r[0] for r in todo))
    lines = ['# 待重读的图', '',
             '模型说这些图的读图结果本身缺了信息（例如两层横轴被压成一层、看不出某根柱子属于哪个样品），数据对不上样品；'
             '或者同一样品、同一条件下读出了几个不同的数；或者整张子图都不是读图分类的那一项（这类的数先没收，列在排除的数据里）。',
             '用户 2026-10-13 定：记下来，全量跑完后统一重读。每次运行 extract_datapoint.py 自动重新汇总。',
             '重读也没用的（相关性散点图、力学质构类等，名单在 PDF_project\\3_processing_pipeline\\不用重读.tsv）列在最后一节，不进重读命令。', '',
             '要重读：%d 篇、%d 处；不用重读：%d 处。' % (len(names), len(todo), len(skipped)), '']
    if todo:
        lines += ['| 文章 | 图 | 子图 | 编号 | 涉及的点 | 原因 |', '|---|---|---|---|---|---|']
        lines += ['| %s | %s | %s | %s | %d | %s |' % (a, it, pn, iid, n, ' '.join(r.split()).replace('|', '\\|'))
                  for a, it, pn, iid, r, n in todo]
        lines += ['', '## 统一重读的步骤', '',
                  '1. 读图（按读图脚本现行规则重读整篇；重读后逐张和旧结果比对，变差的恢复旧的）：', '']
        for k in range(0, len(names), 100):
            lines.append('   python pipeline.py read --refresh ' +
                         ' '.join('"%s"' % os.path.join(ed_papers_dir(root), n) for n in names[k:k + 100]))
        lines += ['', '2. 合并（只重做这几篇）：', '']
        for k in range(0, len(names), 100):
            lines.append('   python pipeline.py merge --root "%s" %s'
                         % (root, ' '.join(names[k:k + 100])))
        lines += ['', '3. 提取（合并稿变了，旧的模型回答自动作废、重新问）：', '']
        for k in range(0, len(names), 100):
            lines.append('   python pipeline.py datapoint --root "%s" %s'
                         % (root, ' '.join(names[k:k + 100])))
    else:
        lines.append('（无）')
    if skipped:
        lines += ['', '## 不用重读（重读也对不上，或按规则本来不收）', '',
                  '| 文章 | 图 | 子图 | 编号 | 涉及的点 | 为什么不用重读 |', '|---|---|---|---|---|---|']
        lines += ['| %s | %s | %s | %s | %d | %s |' % (a, it, pn, iid, n, w.replace('|', '\\|'))
                  for a, it, pn, iid, r, n, w in skipped]
    return '\n'.join(lines) + '\n'


def ed_write_report(args, mdir, totals, status_count, prop_count, reason_count, flag_count, left_by_paper, errors, stale,
                 seconds, skipped=None):
    lines = ['# 数据点提取报告', '',
             '时间：%s；模型 %s；文章 %s（读每篇的 %s）→ %s；用时 %.0f 秒。' % (
                 time.strftime('%Y-%m-%d %H:%M'), args.model, ed_papers_dir(args.root), ed_MERGED_NAME,
                 '每篇的 ' + ed_DATAPOINT_NAME if mdir == ed_records_dir(args.root) else mdir, seconds), '',
             '- 文章：%d 篇（每篇一个 datapoint.md），出错 %d 篇；模型回答累计费用 $%.4f（OpenRouter 报的）' % (
                 totals['文章'], len(errors), totals['费用']),
             '- 进表：样品 %d、数值 %d（作者表格 %d、正文 %d、图反读 %d）；未进表 %d；排除 %d' % (
                 totals['样品'], totals['数值'], totals['来源:作者表格'], totals['来源:正文'],
                 totals['来源:图反读'] + totals['来源:图片表格反读'], totals['未进表'], totals['排除']),
             '- 对应状态：' + '，'.join('%s %d' % kv for kv in status_count.most_common()),
             '- 指标：' + '，'.join('%s %d' % kv for kv in prop_count.most_common())]
    if reason_count:
        lines += ['', '## 排除原因', ''] + ['- %s：%d' % kv for kv in reason_count.most_common()]
    if flag_count:
        lines += ['', '## 提醒（按出现次数）', ''] + ['- %s：%d' % kv for kv in flag_count.most_common(40)]
    if left_by_paper:
        lines += ['', '## 有未进表数值的文章', ''] + ['- %s：%d 个（进表 %d）' % x
                                                   for x in sorted(left_by_paper, key=lambda x: -x[1])]
    if errors:
        lines += ['', '## 出错的文章', ''] + ['- %s：%s' % kv for kv in errors.items()]
    if skipped:
        lines += ['', '## 不再问的文章（%s 里列的，不发给模型、没有 datapoint.md）' % os.path.basename(ed_NO_ASK), ''] + \
            ['- %s：%s' % kv for kv in sorted(skipped.items())]
    if stale:
        lines += ['', '## 回答已过期（合并稿或提示词变了，要重新问）', ''] + ['- %s' % s for s in stale]
    ed_atomic_write(os.path.join(mdir, ed_REPORT_NAME), '\n'.join(lines) + '\n')


# ====================================================================================================
# 测定方法提取（原 extract_method\extract_method.py）
# ====================================================================================================
r"""
extract_method.py —— 给数据库里的每个数值补上测定方法（第五步的补充）

    python extract_method.py --dry-run                # 只写出要发给模型的文字、估算花费，不调模型、不花钱
    python extract_method.py --sample 20              # 固定抽 20 篇试跑（调模型，花钱）
    python extract_method.py 10.1021_acs.jafc.0c00745 # 指定文章
    python extract_method.py                          # 数据点里有数值的全部文章（花钱，先问用户；已有回答的跳过）
    python extract_method.py --build-only             # 不调模型，用已有回答重新写方法文件和报告

用户 2026-10-19 定：数据库原来没有测定方法 → 单独加这一步（不重跑数据点提取、不动它的缓存）；17 项一起提取；
先在 ACS 这批上试，以后推广到所有数据（输入目录都能用参数换）；提取后 datapoint.md 要体现对应的方法，
以后再生成 datapoint.md 也要保留方法。
做法：
  1 每篇只发：这篇进了数据库的性质清单（每项的数值来自哪张图、哪张表、正文，测量名称）+ 方法部分原文 +
    这些图表的图注 / 表题 + 缩写表；反读数据块不发
  2 模型按性质列出测定方法（标准名称 + 原文叫法 + 关键参数 + 方法出处 + 对应哪些图表 / 测量名称 + 原文句子）；
    原文没写方法的性质列进 not_described，不猜
  3 程序核对：原文句子在原文里找得到；对应的图表编号在清单里；核对后的方法按 17 项的顺序重新编号 M1、M2…，
    写每篇文件夹里的 method.json（有进库数值的文章才有）
  4 挂到每个数值上（extract_datapoint.assign_methods，只有这一份）：这一项只有一种方法就全挂；有几种时按图表编号、
    测量名称分，分不清标「方法不确定」。extract_datapoint.py 生成 datapoint.md 时读 method.json 写上方法，
    build_database.py 建库时同样读它
一般不单独跑：用 Desktop\extract_datapoint\datapoint_with_method.py 一条命令完成「提取数据点 → 本脚本 → 重新生成
带方法的 datapoint.md」，再用 Desktop\build_database\build_db_and_site.py 建库、更新网站（用户 2026-10-19 定）。
清单直接从数据点的底稿算（load_from_datapoint），不用先建库。
文件夹结构（用户 2026-10-21 定，和 D:\acs_papers_done 一致；--root 换总文件夹，没有 papers 子文件夹的文章直接放在 <root> 下）：
    <root>\papers\<文章名>\全文合并.md                          输入（合并稿，只读）
    <root>\_records\数据点\_模型输出\<模型名>\<文章名>.json      输入（数据点的模型回答，只读：每篇哪些性质有数值、来自哪张图表）
    <root>\papers\<文章名>\method.json                          输出：核对后的方法
    <root>\_records\测定方法\_提取报告.md、_模型输出\<模型名>\    报告、回答缓存（带指纹，只看文字、不看路径）
"""


# 用户 2026-10-21：ACS 全部数据统一在 D:\acs_papers_done（原来输出在 D:\acs_papers_测定方法，已经不在了）

em_STEP_DIR = '测定方法'                         # 报告、回答缓存：<root>\_records\测定方法\

em_CACHE_DIR = '_模型输出'
em_PREVIEW_DIR = '_发给模型的文字'
em_REPORT_NAME = '_提取报告.md'
em_SAMPLE_SEED = 20261019
# flex 档单价（用户 2026-10-14 实测：gemini-3.8-flash flex 输入 $0.375/M、输出 $1.875/M），只用来估算
em_PRICE_IN, em_PRICE_OUT = 0.375e-6, 1.875e-6

# ================================================================ 模型回答的结构 ==


class Param(BaseModel):
    name: str = Field(description='参数名，如 centrifugation、time、protein concentration、buffer、pH、wavelength、'
                                  'standard、oil phase、homogenization speed、probe、excitation/emission wavelength')
    value: str = Field(description='数值或内容，照抄原文写法，如 "10000"、"0.1 M phosphate buffer"、"BSA"')
    unit: Optional[str] = Field(description='单位，照抄原文（如 ×g、rpm、min、mg/mL、nm）；没有单位填 null')
em_Param = Param                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class MethodItem(BaseModel):
    method_id: str = Field(description='方法编号：M1、M2、M3…')
    property: ed_Property17 = Field(description='测的是 17 项里的哪一项（只写清单里列出的）')
    method: str = Field(description='方法的标准名称，从第三节这一项的常用名称里选（照写中文名）；都不合适时写「其他：简短名称」；'
                                    '原文只说按某文献方法、没说是什么方法时写「未说明（按文献方法）」')
    method_raw: str = Field(description='原文对这个方法的叫法，照抄一个短语（如 "Bradford method"、"dynamic light scattering"）')
    reference: Optional[str] = Field(description='原文写的方法出处（如 "Pearce and Kinsella (1978)"、"AOCS Ba 11-65"）；没有填 null')
    instrument: Optional[str] = Field(description='仪器名称和型号，照抄（如 "Zetasizer Nano ZS, Malvern"）；没写填 null')
    params: List[em_Param] = Field(description='关键参数（第三节列了各项要记哪些），原文写了的都记上；没写的不写、不猜')
    applies_to: List[str] = Field(description='用这个方法得到的数在哪些图、表：照抄清单里的写法（"Figure 2"、"Table 1"），'
                                              '正文里的数写 "正文"；看不出来填空列表')
    measure_names: List[str] = Field(description='这个方法对应清单里的哪些测量名称（照抄清单）；看不出来填空列表')
    evidence: List[str] = Field(description='原文里描述这个方法的句子，逐字照抄（每条一段连续原文，不加省略号、不改写、不翻译）')
em_MethodItem = MethodItem                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class Missing(BaseModel):
    property: ed_Property17 = Field(description='清单里有数值、但给出的原文里找不到测定方法的那一项')
    reason: str = Field(description='为什么找不到（例如方法部分没写这一项、写在补充材料里）')
em_Missing = Missing                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


class MethodNote(BaseModel):
    methods: List[em_MethodItem] = Field(description='清单里每一项性质的测定方法；同一项用了几种方法就各写一条')
    not_described: List[em_Missing] = Field(description='清单里有、但原文里没写测定方法的性质；没有填空列表')
em_MethodNote = MethodNote                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


# ================================================================ 提示词 ==
em_VOCAB = """- 溶解度：Bradford 法（考马斯亮蓝）/ Lowry 法（福林酚）/ BCA 法 / 双缩脲法 / 凯氏定氮法 / 杜马斯燃烧法 / 紫外吸收法（A280 等）/ 重量法。
  参数：离心力或转速和时间、测定时的蛋白浓度、溶剂或缓冲液（种类、pH、离子强度）、搅拌或溶解时间、标准品、分母（总蛋白还是初始蛋白含量）
- 乳化性：浊度法（EAI/ESI，Pearce & Kinsella）/ 离心法（乳化活性 %，Yasumatsu 等）/ 乳析指数法 / 乳液粒径法。
  参数：油相种类和比例、蛋白浓度、均质方式和转速、时间、稀释液（如 0.1% SDS）和稀释倍数、波长、静置时间
- 起泡性：搅打或均质法（泡沫体积）/ 鼓气法。参数：蛋白浓度、溶液体积、转速和时间、读数的时间点
- 凝胶性：质构仪穿刺或压缩法（凝胶强度、破断力）/ 流变仪法（G′ 等）/ 最小凝胶浓度法。参数：蛋白浓度、成胶的加热温度和时间、探头和速度
- 持水性：离心法 / 滤纸法 / 蒸煮损失法 / 低场核磁法。参数：离心力和时间、样品量
- 持油性：离心法。参数：油的种类、离心力和时间
- 粒径：动态光散射（DLS）/ 激光衍射 / 纳米颗粒跟踪分析（NTA）/ 显微图像分析。参数：仪器、稀释倍数、折射率、报告的径（Z-average、D[4,3]、D[3,2]、中位径）
- ζ-电位：电泳光散射。参数：仪器、测定时的浓度、pH、稀释液
- PDI：动态光散射（DLS）。参数：仪器、稀释倍数
- 巯基含量：Ellman 法（DTNB）。参数：测的是游离巯基还是总巯基（是否加尿素、SDS、盐酸胍变性）、缓冲液、波长、消光系数
- 二硫键含量：Ellman 法加还原剂（NTSB、亚硫酸钠等）/ 由总巯基推算 / 拉曼光谱法。参数同上
- 表面疏水性：ANS 荧光探针法 / PRODAN 荧光探针法 / CPA 荧光探针法 / 溴酚蓝结合法 / 疏水作用色谱法。参数：探针、激发和发射波长、蛋白浓度范围、计算方式（初始斜率等）
- 浊度：吸光度法（记下波长）/ 浊度计法（NTU）
- 水解度：OPA 法 / TNBS 法 / pH-stat 法 / 甲醛滴定法 / TCA 可溶氮法
- 游离氨基含量：OPA 法 / TNBS 法 / 茚三酮法
- 包埋率/负载率：直接法（测包埋的量）/ 间接法（测游离、未包埋的量），并在参数里写测定手段（紫外、荧光、HPLC…）
- 抗氧化活性：DPPH 自由基清除法 / ABTS 自由基清除法 / FRAP 法（铁离子还原能力）/ ORAC 法 / 还原力法 / 羟基自由基清除法 /
  金属离子螯合法 / 脂质氧化抑制法（TBARS 等）；每种测定各写一条"""

em_SYSTEM = """你是食品蛋白质论文的数据整理员。这篇论文里的 17 项功能特性数值已经进了数据库，你的任务是从原文里找出**每一项是用什么
测试方法测的**（测试方法 = 测这项性质的分析方法，例如溶解度用 Bradford 法、粒径用动态光散射）。

**测试方法和样品处理是两回事，不能混**：样品在测定之前经过的制备和改性（超声、加热、高压、酶解、糖基化、pH 偏移、
冻干、复配…）是样品处理，数据库里另有记录，这里**一律不写**；参数也只记测定这一步的（如溶解度测定时的离心力、
测定时的蛋白浓度），不记样品处理的温度、时间、功率。

一、给你的材料
- 清单：这篇进了数据库的性质，每项的数来自哪张图、哪张表、正文，以及测量名称
- 原文：方法部分（Materials and Methods 等）、上面这些图表的图注或表题、缩写表

二、要求
1. 只依据给你的原文，不猜、不用常识补。原文没写测试方法的性质（例如方法写在补充材料里、方法部分漏写）列进 not_described
2. 原文只写「按某某文献的方法测定」、没说是什么方法的：method 写「未说明（按文献方法）」，reference 写出处
3. 同一项性质用了几种方法（例如溶解度既用 Bradford 法又用凯氏定氮），各写一条，并在 applies_to、measure_names 里写清
   各对应哪些图表、哪些测量名称；只有一种方法的也尽量写上
4. 参数只记原文写了的，照抄数值和单位；evidence 逐字照抄原文句子，程序会核对
5. 只写清单里列出的性质；不在清单里的不写

三、各项常用的测试方法名称（method 照写中文名；都不合适写「其他：简短名称」）和要记的测定参数
""" + em_VOCAB

em_USER = """文章标题：{title}
DOI：{doi}

【清单：这篇进了数据库的性质】
{listing}

【原文】
{text}"""


# ================================================================ 读数据点和合并稿 ==
def em_load_from_datapoint(root, names=None, model=ed_MODEL):
    """{文章名: {'doi', 'title', 'props': {代号: {'items': Counter(图表), 'names': Counter(测量名称)}}, 'rows': [数值行]}}。
    直接从数据点的底稿算（合并稿 + 数据点的模型回答 → ed.build_paper），不用先建库（用户 2026-10-19：
    提取数据点和测试方法合成一个流程；原来从数据库读，2340 篇逐篇核对过两种读法发给模型的文字完全相同，旧缓存照用）。
    只算 datapoint.md 样品表里的数（已对应、含蛋白的样品），顺序和 build_database 写库的顺序一样（样品 → 17 项 →
    作者表格、正文、读图）。"""
    cdir = os.path.join(ed_records_dir(root), ed_CACHE_DIR, ed_model_slug(model))
    if names is None:
        names = sorted(os.path.splitext(f)[0] for f in os.listdir(cdir) if f.endswith('.json')) \
            if os.path.isdir(cdir) else []
    out = collections.OrderedDict()
    for article in names:
        path = ed_merged_path(root, article)
        if not os.path.exists(path):
            continue
        d = ed_parse_doc(path)
        c = ed_load_cache(cdir, d, model)
        if c is None:
            continue
        pts = ed_build_paper(d, c['output'])[0]
        samples = collections.OrderedDict((s['sample_id'], s) for s in c['output']['samples'])
        ok = [p for p in pts if p['对应状态'] == '已对应' and p['样品编号'] in samples]
        rows = []
        for sid in samples:
            for code in FUNCTIONAL:
                mine = sorted((p for p in ok if p['样品编号'] == sid and p['指标代号'] == code),
                              key=lambda p: ed_SRC_RANK.get(p['来源'], 9))
                rows += [{'measurement_id': '%s#%d' % (article, len(rows) + k), 'property': code,
                          'source_item': p['图表'], 'measure_name': p['测量名称'] or p['系列'] or p['指标']}
                         for k, p in enumerate(mine)]
        if not rows:
            continue
        a = {'doi': d['doi'] or article, 'title': d['title'], 'props': collections.OrderedDict(), 'rows': rows}
        for r in rows:
            p = a['props'].setdefault(r['property'], {'items': collections.Counter(), 'names': collections.Counter()})
            p['items'][r['source_item']] += 1
            p['names'][r['measure_name']] += 1
        a['props'] = collections.OrderedDict((k, a['props'][k]) for k in FUNCTIONAL if k in a['props'])
        out[article] = a
    return out


em_HEAD = re.compile(r'^(#{1,6})\s+(.*)$')
em_METHOD_HEAD = re.compile(r'method|experimental|materials|procedure', re.I)
em_RESULT_HEAD = re.compile(r'result|discussion|conclusion', re.I)
em_ABBR_HEAD = re.compile(r'abbreviat|abreviat|abbrevat|nomenclature', re.I)
em_CAPTION = re.compile(r'^(?:\*\*)?(Figure|Table|Scheme)\s+([A-Za-z]?\d+[A-Za-z]?)\.')


def em_strip_blocks(lines):
    """去掉反读数据块（「图 N 反读数据」+ 子图标题行 + 反读表），其余照留。"""
    out, i = [], 0
    while i < len(lines):
        if ed_BLOCK.match(lines[i].strip()):
            j = i + 1
            while j < len(lines):
                s = lines[j].strip()
                if not s or ed_is_panel_head(s) or s.startswith('|'):
                    j += 1
                    continue
                break
            i = j
            continue
        out.append(lines[i])
        i += 1
    return out


em_STOP_HEAD = re.compile(r'result|discussion|conclusion|abbreviat|abreviat|abbrevat|nomenclature', re.I)


def em_method_region(lines, level):
    """方法部分：从第一个方法类 level 级标题开始，到 Results / Discussion / Conclusion / 缩写表这类同级标题为止，
    中间别的同级标题一并收。2026-10-19 全量检查发现：网页标题层级不规整，测定方法常写在方法部分后面另起的二级标题下
    （acsfoodscitech.0c00114「## Experimental Section」后面接「## Antioxidant Activity」），原来遇到下一个同级标题就停，
    方法没发给模型、被判成原文未写明（14 篇）。"""
    out, on = [], False
    for line in lines:
        h = em_HEAD.match(line)
        if h and len(h.group(1)) <= level:
            t = h.group(2)
            if not on and len(h.group(1)) == level and em_METHOD_HEAD.search(t) and not em_RESULT_HEAD.search(t):
                on = True
            elif on and (len(h.group(1)) < level or em_STOP_HEAD.search(t)):
                break
        if on:
            out.append(line)
    return out


def em_sections(lines, pattern, level):
    """标题是 level 级、匹配 pattern 的节（到下一个同级或更高级标题为止）。"""
    out, keep = [], False
    for line in lines:
        h = em_HEAD.match(line)
        if h and len(h.group(1)) <= level:
            keep = len(h.group(1)) == level and bool(pattern.search(h.group(2))) and not \
                (pattern is em_METHOD_HEAD and em_RESULT_HEAD.search(h.group(2)))
        if keep:
            out.append(line)
    return out


def em_parse_paper(article, root, info):
    text = ed_read(ed_merged_path(root, article))
    lines = text.split('\n')
    end = next((i for i, l in enumerate(lines) if l.strip() == ed_EVAL_HEAD), len(lines))
    lines = em_strip_blocks(lines[:end])
    methods = em_method_region(lines, 2) or em_method_region(lines, 3)
    where = '方法部分'
    if not methods:                             # 没有方法类标题（全库 1 篇）：发引言以后的全文
        where = '全文（没有方法部分标题）'
        start = next((i for i, l in enumerate(lines) if em_HEAD.match(l) and re.search(r'introduction', l, re.I)), 0)
        methods = lines[start:]
    items = {it for d in info['props'].values() for it in d['items']}
    caps = []
    for line in lines:
        m = em_CAPTION.match(line.strip())
        if m and ('%s %s' % ('Table' if m.group(1) == 'Table' else 'Figure', m.group(2))) in items:
            caps.append(line.strip())
    abbr = em_sections(lines, em_ABBR_HEAD, 2)
    body = '\n'.join(methods).strip()
    if caps:
        body += '\n\n【图注和表题】\n' + '\n\n'.join(caps)
    if abbr:
        body += '\n\n' + '\n'.join(abbr).strip()
    body = re.sub(r'\n{3,}', '\n\n', body)
    listing = []
    for code, d in info['props'].items():
        parts = ['%s（%d 个数）' % (it, n) for it, n in d['items'].most_common()]
        names = [n for n, _ in d['names'].most_common(8)]
        listing.append('- %s（%s）：%s；测量名称：%s' % (FUNCTIONAL[code], code, '、'.join(parts),
                                                      '、'.join('「%s」' % n for n in names)))
    return {'article': article, 'doi': info['doi'], 'title': info['title'], 'where': where,
            'items': items | {'正文'}, 'props': list(info['props']),
            'user': em_USER.format(title=info['title'], doi=info['doi'], listing='\n'.join(listing), text=body),
            'source_norm': ed_norm_text('\n'.join(lines))}


# ================================================================ 调模型 ==
def em_fingerprint(doc, model):
    schema = json.dumps(em_MethodNote.model_json_schema(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(json.dumps([model_key(model), em_SYSTEM, schema, doc['user']],
                                     ensure_ascii=False).encode('utf-8')).hexdigest()[:16]


def em_call_model(api, text):
    """同 ed.call_model（出错处理、空回答、限流等待、切到 Google 官方接口一样），只是回答结构换成 MethodNote。"""
    waited = 0.0
    while True:
        if api.stop.is_set():
            raise Fatal(api.fatal)
        kwargs, via_openrouter = ed_request(api, em_SYSTEM, text, em_MethodNote)
        raw = None
        try:
            with api.slots:
                raw = api.client.chat.completions.with_raw_response.parse(**kwargs)
                r = raw.parse()
            break
        except SystemExit:
            raise
        except TypeError as e:
            if raw is None or 'NoneType' not in str(e):
                raise
            why = ed_empty_reason(raw)
            if waited >= RATE_WAIT_MAX:
                raise ValueError('模型连续回空回答、已等 %d 分钟（%s）' % (waited // 60, why))
            ed_say('[空回答] 等 30 秒再试（%s）' % why)
            api.sleep(30)
            waited += 30
        except Exception as e:
            kind = api_problem(e, gemini=not via_openrouter and api.gemini)
            if via_openrouter and (api.gemini or kind == 'money' and api.switch_to_gemini(api.model, short_error(e))):
                continue
            if kind in ('money', 'key', 'access'):
                msg = FATAL_MESSAGES[kind + ('_openrouter' if via_openrouter and kind == 'money' else '')]
                api.halt(msg % {'why': short_error(e), 'key': api.key_env, 'model': api.model})
            if kind not in ('rate', 'busy') or waited >= RATE_WAIT_MAX:
                raise
            delay = retry_delay(e)
            ed_say('[%s] 等 %d 秒再试（%s）' % ('限流' if kind == 'rate' else '服务器忙', delay, short_error(e)))
            time.sleep(delay)
            waited += delay
    use = usage_of(r)
    u = getattr(r, 'usage', None)
    cost = getattr(u, 'cost', None)
    if cost is None and getattr(u, 'model_extra', None):
        cost = u.model_extra.get('cost')
    use['cost'] = float(cost) if cost is not None else None
    choice = r.choices[0]
    if choice.message.parsed is None:
        raise ValueError('模型没有返回可解析的结果（finish_reason=%s）' % choice.finish_reason)
    return choice.message.parsed, use, choice.finish_reason


def em_cache_path(out, model, article):
    return os.path.join(out, em_CACHE_DIR, ed_model_slug(model), article + '.json')


def em_load_cache(out, doc, model):
    p = em_cache_path(out, model, doc['article'])
    if not os.path.exists(p):
        return None
    try:
        c = json.loads(ed_read(p))
    except ValueError:
        return None
    return c if c.get('fingerprint') == em_fingerprint(doc, model) else None


def em_ask_one(api, out, doc):
    t0 = time.time()
    for attempt in range(3):
        try:
            parsed, use, finish = em_call_model(api, doc['user'])
            break
        except ValueError as e:
            if attempt == 2:
                raise
            ed_say('[%s] %s，再问一次' % (doc['article'], e))
    rec = {'fingerprint': em_fingerprint(doc, api.model), 'model': api.model, 'at': time.strftime('%Y-%m-%d %H:%M:%S'),
           'seconds': round(time.time() - t0, 1), 'usage': use, 'finish_reason': finish, 'output': parsed.model_dump()}
    ed_atomic_write(em_cache_path(out, api.model, doc['article']), json.dumps(rec, ensure_ascii=False, indent=1))
    ed_say('[%s] 方法 %d 条、没写方法的性质 %d；输入 %s、输出 %s token%s，%.0f 秒' % (
        doc['article'], len(parsed.methods), len(parsed.not_described), format(use.get('input', 0), ','),
        format(use.get('output', 0), ','), '，$%.4f' % use['cost'] if use.get('cost') is not None else '',
        rec['seconds']))
    return rec


# ================================================================ 核对，写方法文件 ==
def em_norm_item(s):
    return ' '.join((s or '').replace('图', 'Figure ').replace('表', 'Table ').split()).casefold()


# 测试方法的标准名称（500 篇试跑发现模型会把提示词里的括号说明一起抄进名字：「吸光度法（记下波长）」「直接法（测包埋的量）」，
# 同一种方法几种写法，没法筛）。去掉括号说明后和这里对上的统一成这里的写法，对不上的（「其他：…」等）照原样
em_CANON = {
    'solubility': ['Bradford 法', 'Lowry 法', 'BCA 法', '双缩脲法', '凯氏定氮法', '杜马斯燃烧法', '紫外吸收法', '重量法'],
    'emulsifying': ['浊度法（EAI/ESI）', '离心法', '乳析指数法', '乳液粒径法'],
    'foaming': ['搅打或均质法', '鼓气法'],
    'gelling': ['质构仪穿刺或压缩法', '流变仪法', '最小凝胶浓度法'],
    'water_holding': ['离心法', '滤纸法', '蒸煮损失法', '低场核磁法'],
    'oil_holding': ['离心法'],
    'particle_size': ['动态光散射（DLS）', '激光衍射', '纳米颗粒跟踪分析（NTA）', '显微图像分析'],
    'zeta_potential': ['电泳光散射'],
    'pdi': ['动态光散射（DLS）', '激光衍射'],
    'sulfhydryl': ['Ellman 法（DTNB）'],
    'disulfide': ['Ellman 法加还原剂', '由总巯基推算', '拉曼光谱法'],
    'surface_hydrophobicity': ['ANS 荧光探针法', 'PRODAN 荧光探针法', 'CPA 荧光探针法', '溴酚蓝结合法', '疏水作用色谱法'],
    'turbidity': ['吸光度法', '浊度计法'],
    'degree_of_hydrolysis': ['OPA 法', 'TNBS 法', 'pH-stat 法', '甲醛滴定法', 'TCA 可溶氮法', '荧光胺法'],
    'free_amino': ['OPA 法', 'TNBS 法', '茚三酮法', '荧光胺法', '氨基酸分析仪法'],
    'encapsulation': ['直接法', '间接法'],
    'antioxidant': ['DPPH 自由基清除法', 'ABTS 自由基清除法', 'FRAP 法', 'ORAC 法', '还原力法', '羟基自由基清除法',
                    '金属离子螯合法', '脂质氧化抑制法', '超氧阴离子自由基清除法', '过氧化氢清除法'],
}
# 同一种方法的别的叫法（全量检查时看到的）：去掉括号和末尾「法」后的写法 → 标准名称
em_ALIASES = {'antioxidant': {'超氧自由基清除': '超氧阴离子自由基清除法', '超氧阴离子清除': '超氧阴离子自由基清除法',
                           '超氧阴离子自由基清除能力': '超氧阴离子自由基清除法'}}


def em_name_base(s):
    """比较用：去掉括号说明、空格、末尾的「法」（「激光衍射法」=「激光衍射」）。"""
    b = re.sub(r'\s+', '', re.split(r'[（(]', s or '', maxsplit=1)[0]).casefold()
    return b[:-1] if b.endswith('法') and len(b) > 1 else b


def em_canon_method(prop, name):
    """模型写的测试方法名 → 标准名称（同一项性质里，去掉括号说明后对得上的、或是表里列的别名）；「其他：标准名」也认。
    对不上的照原样，只把「SE-HPLC 法」这种法字前的空格去掉（同一个名字两种写法）。"""
    name = ' '.join((name or '').split())
    for b in (em_name_base(name), em_name_base(name[3:]) if name.startswith('其他：') else None):
        if b:
            hit = next((c for c in em_CANON.get(prop, []) if em_name_base(c) == b), None) or em_ALIASES.get(prop, {}).get(b)
            if hit:
                return hit
    return re.sub(r'\s+法', '法', name) if name.startswith('其他：') else name


def em_check_methods(doc, c):
    """模型回答 → 核对后的方法文件内容：只留清单里的性质；图表编号对回清单写法、记下清单里没有的；原文句子逐条核对；
    按 17 项的顺序重新编号 M1、M2…（模型给的编号可能重复或跳号）。返回 (记录, 丢掉的条数)。"""
    note = c['output']
    items = {em_norm_item(x): x for x in doc['items']}
    rank = {code: k for k, code in enumerate(FUNCTIONAL)}
    kept, dropped = [], 0
    for k, m in enumerate(note['methods']):
        if m['property'] not in doc['props']:
            dropped += 1                        # 清单里没有的性质（这篇没有这一项的数值）
            continue
        kept.append((rank[m['property']], k, m))
    methods = []
    for n, (_, _, m) in enumerate(sorted(kept, key=lambda x: x[:2]), 1):
        applies = [items.get(em_norm_item(x), x) for x in m.get('applies_to') or []]
        methods.append({'method_id': 'M%d' % n, 'property': m['property'],
                        'method': em_canon_method(m['property'], m['method']), 'method_model': m['method'],
                        'method_raw': m.get('method_raw') or '', 'reference': m.get('reference') or '',
                        'instrument': m.get('instrument') or '', 'params': m.get('params') or [],
                        'applies_to': applies, 'measure_names': m.get('measure_names') or [],
                        'bad_items': [x for x in applies if em_norm_item(x) not in items],
                        'evidence': m.get('evidence') or [],
                        'evidence_found': [bool(ed_quote_found(q, doc['source_norm'])) for q in m.get('evidence') or []]})
    not_desc = [x for x in note['not_described'] if x['property'] in doc['props']]
    rec = {'article': doc['article'], 'doi': doc['doi'], 'model': c.get('model'), 'at': c.get('at'),
           'sent': doc['where'], 'methods': methods, 'not_described': not_desc}
    return rec, dropped


def em_method_path(root, article):
    return os.path.join(ed_papers_dir(root), article, ed_METHOD_NAME)


def em_write_report(args, totals, prop_status, method_count, no_method, errors, cost, seconds):
    lines = ['# 测定方法提取报告', '',
             '时间：%s；模型 %s；数据点（%s 的回答）+ 每篇的 %s → 每篇的 %s（文章在 %s）；用时 %.0f 秒。' % (
                 time.strftime('%Y-%m-%d %H:%M'), args.model, args.dp_model, ed_MERGED_NAME, ed_METHOD_NAME,
                 ed_papers_dir(args.root), seconds), '',
             '- 文章：%d 篇有回答，出错 %d 篇；回答累计费用 $%.4f' % (totals['文章'], len(errors), cost),
             '- 方法 %d 条（原文句子全部找到的 %d 条）；回答里不在清单的性质丢掉 %d 条；对应图表写错的 %d 条' % (
                 totals['方法'], totals['依据全找到'], totals['丢掉'], totals['图表写错']),
             '- 数值 %d 个：' % totals['数值'] + '，'.join('%s %d' % kv for kv in totals['状态'].most_common()), '',
             '## 各项挂上方法的比例', '', '| 性质 | 数值 | 已对应 | 原文未写明方法 | 方法不确定 |', '|---|---|---|---|---|']
    for code in FUNCTIONAL:
        s = prop_status.get(code)
        if s:
            n = sum(s.values())
            lines.append('| %s | %d | %d（%.0f%%） | %d | %d |' % (
                FUNCTIONAL[code], n, s['已对应'], 100.0 * s['已对应'] / n, s[ed_NO_METHOD], s['方法不确定']))
    lines += ['', '## 各项用到的方法（按条数）', '']
    for code in FUNCTIONAL:
        if method_count.get(code):
            lines.append('- %s：%s' % (FUNCTIONAL[code], '，'.join('%s %d' % kv for kv in method_count[code].most_common(12))))
    lines += ['', '## 原文没写方法的性质（按篇）', '']
    lines += ['- %s：%s' % kv for kv in no_method[:200]] or ['（无）']
    if errors:
        lines += ['', '## 出错', ''] + ['- %s：%s' % kv for kv in errors.items()]
    ed_atomic_write(os.path.join(ed_records_dir(args.root, em_STEP_DIR), em_REPORT_NAME), '\n'.join(lines) + '\n')


# ================================================================ 主程序 ==
def em_main(argv=None, show_next=True):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    ap = argparse.ArgumentParser(description='数据库里的数值 → 补测定方法')
    ap.add_argument('papers', nargs='*', help='文章名；不给就是数据点里有数值的全部文章')
    ap.add_argument('--root', default=ed_ROOT, help='总文件夹（文章在 <root>\\papers\\<文章>，没有 papers 子文件夹时直接在 <root> 下），'
                                                 '默认 %s；每篇写 method.json，报告和回答缓存在 <root>\\_records\\测定方法' % ed_ROOT)
    ap.add_argument('--dp-model', default=ed_MODEL, help='数据点是哪个模型提取的（读它的缓存），默认 %s' % ed_MODEL)
    ap.add_argument('--sample', type=int, default=0, help='固定随机抽 N 篇')
    ap.add_argument('--dry-run', action='store_true', help='只写出要发给模型的文字、估算花费，不调模型')
    ap.add_argument('--build-only', action='store_true', help='不调模型，用已有回答重新生成文件和报告')
    ap.add_argument('--model', default=ed_MODEL, help='默认 %s' % ed_MODEL)
    ap.add_argument('--provider', default='auto', help='OpenRouter 上限定哪一家；auto = 按模型名前缀（gemini 走 flex 档）')
    ap.add_argument('--base-url', default='openrouter', help='openrouter（默认）/ openai / 其他接口地址')
    ap.add_argument('--workers', type=int, default=4, help='同时进行的请求数，默认 4')
    ap.add_argument('--key-env', default=ed_KEY_ENV, help='放 API key 的环境变量，默认 %s' % ed_KEY_ENV)
    args = ap.parse_args(argv)
    if not os.path.isdir(args.root):
        raise SystemExit('找不到总文件夹：%s' % args.root)
    global ed_PAPERS
    ed_PAPERS = ed_papers_dir(args.root)          # assign_methods 等读 method.json 的地方跟着这个总文件夹
    rec_dir = ed_records_dir(args.root, em_STEP_DIR)
    t0 = time.time()
    info = em_load_from_datapoint(args.root, names=args.papers or None, model=args.dp_model)
    names = args.papers or list(info)
    missing = [n for n in names if n not in info]
    if missing:
        raise SystemExit('这些文章还没有数据点、或没有数值：%s' % '、'.join(missing[:10]))
    if args.sample:
        names = sorted(random.Random(em_SAMPLE_SEED).sample(sorted(names), min(args.sample, len(names))))
    docs = {n: em_parse_paper(n, args.root, info[n]) for n in names}
    print('文章 %d 篇（数据点里有数值的共 %d 篇）' % (len(docs), len(info)), flush=True)

    if args.dry_run:
        n_in = 0
        for d in docs.values():
            text = em_SYSTEM + '\n\n' + d['user']
            n_in += len(text)
            ed_atomic_write(os.path.join(rec_dir, em_PREVIEW_DIR, d['article'] + '.txt'), text)
        tok_in = n_in / 3.5
        print('已写出要发给模型的文字 -> %s；共 %s 字符，约 %s 输入 token' % (
            os.path.join(rec_dir, em_PREVIEW_DIR), format(n_in, ','), format(int(tok_in), ',')))
        print('估算：输入约 $%.3f；输出（含思考）按每篇 1500–3000 token 算约 $%.3f–%.3f；合计约 $%.2f–%.2f（flex 档）' % (
            tok_in * em_PRICE_IN, len(docs) * 1500 * em_PRICE_OUT, len(docs) * 3000 * em_PRICE_OUT,
            tok_in * em_PRICE_IN + len(docs) * 1500 * em_PRICE_OUT, tok_in * em_PRICE_IN + len(docs) * 3000 * em_PRICE_OUT))
        return 0

    errors = {}
    if not args.build_only:
        todo = [d for d in docs.values() if em_load_cache(rec_dir, d, args.model) is None]
        print('要问模型的 %d 篇（其余 %d 篇已有回答、输入没变）' % (len(todo), len(docs) - len(todo)), flush=True)
        if todo:
            base = {'openrouter': OPENROUTER, 'openai': None}.get(args.base_url, args.base_url)
            prov = args.provider
            if prov == 'auto':
                prov = ed_PROVIDERS.get(args.model.split('/', 1)[0], '') if '/' in args.model else ''
            elif prov == 'none':
                prov = ''
            api = Api(model=args.model, workers=args.workers, key_env=args.key_env, base_url=base, provider=prov)
            print('模型 %s，经 %s' % (args.model, api.where()), flush=True)
            with futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
                jobs = {ex.submit(em_ask_one, api, rec_dir, d): d for d in todo}
                for job in futures.as_completed(jobs):
                    d = jobs[job]
                    try:
                        job.result()
                    except Fatal:
                        errors[d['article']] = '窗口停下：' + api.fatal
                    except Exception as e:
                        errors[d['article']] = '%s: %s' % (type(e).__name__, short_error(e))
                        ed_say('[%s] 出错：%s' % (d['article'], errors[d['article']]))

    # 每篇的方法文件 + 报告：这个模型所有有效回答的文章（分批跑会累积）
    cdir = os.path.join(rec_dir, em_CACHE_DIR, ed_model_slug(args.model))
    cached = sorted(os.path.splitext(f)[0] for f in os.listdir(cdir) if f.endswith('.json')) \
        if os.path.isdir(cdir) else []
    totals = collections.Counter()
    totals['状态'] = collections.Counter()
    prop_status = collections.defaultdict(collections.Counter)
    method_count = collections.defaultdict(collections.Counter)
    no_method, cost = [], 0.0
    for name in cached:
        if name not in info:
            continue
        d = docs.get(name) or em_parse_paper(name, args.root, info[name])
        c = em_load_cache(rec_dir, d, args.model)
        if c is None:
            continue
        rec, dropped = em_check_methods(d, c)
        if ed_write_if_changed(em_method_path(args.root, name), json.dumps(rec, ensure_ascii=False, indent=1)):
            totals['改写'] += 1
        methods = rec['methods']
        rows = info[name]['rows']
        asg = ed_assign_methods([(r['property'], r['source_item'], r['measure_name']) for r in rows], methods)
        totals['文章'] += 1
        totals['方法'] += len(methods)
        totals['丢掉'] += dropped
        totals['依据全找到'] += sum(1 for m in methods if m['evidence_found'] and all(m['evidence_found']))
        totals['图表写错'] += sum(1 for m in methods if m['bad_items'])
        cost += (c.get('usage') or {}).get('cost') or 0
        for m in methods:
            method_count[m['property']][m['method']] += 1
        for r, (_, st) in zip(rows, asg):
            st_key = '方法不确定' if st.startswith('方法不确定') else st
            totals['数值'] += 1
            totals['状态'][st_key] += 1
            prop_status[r['property']][st_key] += 1
        for x in rec['not_described']:
            no_method.append((name, '%s（%s）' % (FUNCTIONAL.get(x['property'], x['property']), x['reason'])))
    # 全量运行时：已经没有数值的文章（人工排除、重新提取后没数了）留下的方法文件删掉，免得 datapoint.md 和库读到旧的
    pdir = ed_papers_dir(args.root)
    if not args.papers and not args.sample and os.path.isdir(pdir):
        stale = [n for n in sorted(os.listdir(pdir))
                 if n not in info and os.path.isfile(os.path.join(pdir, n, ed_METHOD_NAME))]
        for n in stale:
            os.remove(os.path.join(pdir, n, ed_METHOD_NAME))
        if stale:
            print('删掉已经没有数值的文章的方法文件 %d 个：%s' % (len(stale), '、'.join(stale[:10])))
    em_write_report(args, totals, prop_status, method_count, no_method, errors, cost, time.time() - t0)
    print('方法文件 %d 篇（每篇文件夹里的 %s；内容有变、这次改写的 %d 篇）：方法 %d 条；数值 %d 个（%s）；出错 %d 篇；回答累计 $%.4f' % (
        totals['文章'], ed_METHOD_NAME, totals['改写'], totals['方法'], totals['数值'],
        '，'.join('%s %d' % kv for kv in totals['状态'].most_common()), len(errors), cost))
    if totals['文章'] and show_next:
        print('下一步：python %s datapoint --root "%s" --build-only（datapoint.md 写上方法），再 build-db' % (__file__, args.root))
    return 1 if errors else 0


# ====================================================================================================
# 数据点 + 测定方法一条命令（原 extract_datapoint\datapoint_with_method.py）
# ====================================================================================================
r"""
datapoint_with_method.py —— 一条命令：提取数据点 → 提取测试方法 → 生成带测试方法的 datapoint.md（用户 2026-10-19 定）

    python datapoint_with_method.py 10.1021_acs.jafc.0c00745 ...    # 指定文章（文章名、文章文件夹或合并稿路径）
    python datapoint_with_method.py --sample 20                     # 固定抽 20 篇试跑（调模型，花钱）
    python datapoint_with_method.py                                  # 全部文章（花钱，先问用户）
    python datapoint_with_method.py --build-only                     # 不调模型，用已有回答重新生成全部 datapoint.md
    python datapoint_with_method.py --dry-run --sample 20            # 只写出要发给模型的文字，不调模型
    python datapoint_with_method.py --provider google-ai-studio      # 临时改用标准档（默认 flex 档，用户：以后用 flex）
    python datapoint_with_method.py --root D:\1.acs_papers_done        # 别的总文件夹（默认 D:\2.elsevier_papers）

三步（两次调模型用同一个 --model / --provider / --workers；有回答缓存、输入没变的文章都不重问、不重花钱）：
  1 extract_datapoint.py：提取数据点（样品、条件，数值由程序搬）
  2 Desktop\extract_method\extract_method.py：有数值的文章，从方法部分提取 17 项性质的测试方法
     （不是样品处理；清单直接从第 1 步的结果算，不用先建库）
  3 extract_datapoint.py --build-only：重新生成 datapoint.md，每个数值后面写「｜测试方法 M1 …」，表下一节「## 测试方法」
文件夹结构（用户 2026-10-21 定，和 D:\acs_papers_done 一致）：每篇的 全文合并.md（输入）、datapoint.md、method.json（输出）
都在 <root>\papers\<文章名>\ 里；报告和模型回答存档在 <root>\_records\数据点、<root>\_records\测定方法。
从读图到建库的整条流程：pipeline.py all。
"""


def dw_main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    ap = argparse.ArgumentParser(description='提取数据点 → 提取测试方法 → 带测试方法的 datapoint.md')
    ap.add_argument('papers', nargs='*', help='文章名、文章文件夹或合并稿路径；不给就是 --root 下全部文章')
    ap.add_argument('--root', default=ed_ROOT, help='总文件夹（文章在 <root>\\papers\\<文章>），默认 %s' % ed_ROOT)
    ap.add_argument('--sample', type=int, default=0, help='固定随机抽 N 篇（同 extract_datapoint.py）')
    ap.add_argument('--limit', type=int, default=0, help='最多处理 N 篇')
    ap.add_argument('--only-with-data', action='store_true', help='同 extract_datapoint.py')
    ap.add_argument('--dry-run', action='store_true', help='只写出要发给模型的文字，不调模型')
    ap.add_argument('--build-only', action='store_true', help='不调模型，用已有回答重新生成 datapoint.md')
    ap.add_argument('--model', default=ed_MODEL, help='两步用的模型，默认 %s' % ed_MODEL)
    ap.add_argument('--provider', default='auto', help='OpenRouter 上限定哪一家；auto = 按模型名（gemini 走 flex 档）')
    ap.add_argument('--base-url', default='openrouter', help='openrouter（默认）/ openai / 其他接口地址')
    ap.add_argument('--workers', type=int, default=ed_WORKERS, help='同时进行的请求数，默认 %d' % ed_WORKERS)
    ap.add_argument('--key-env', default=ed_KEY_ENV, help='放 API key 的环境变量，默认 %s' % ed_KEY_ENV)
    args = ap.parse_args(argv)
    t0 = time.time()
    common = ['--root', args.root, '--model', args.model, '--provider', args.provider, '--base-url', args.base_url,
              '--workers', str(args.workers), '--key-env', args.key_env]
    flags = (['--build-only'] if args.build_only else []) + (['--dry-run'] if args.dry_run else [])

    # 这次处理哪些文章：和 extract_datapoint.py 挑法一样（--sample 固定种子），两步处理同一批，
    # 免得抽样试跑时第 2 步把别的还没提取方法的文章也一起问了
    explicit = bool(args.papers or args.sample or args.limit)
    names = []
    if explicit:
        ns = types.SimpleNamespace(papers=args.papers, root=args.root, sample=args.sample, limit=args.limit,
                                   only_with_data=args.only_with_data, build_only=args.build_only)
        names = [ed_article_of(p) for p in ed_pick(ns)]

    print('==== 第 1 步：提取数据点 ====', flush=True)
    rc1 = ed_main(common + flags + (['--only-with-data'] if args.only_with_data else []) + names)

    print('\n==== 第 2 步：提取测试方法 ====', flush=True)
    rc2 = 0
    if explicit:
        info = em_load_from_datapoint(args.root, names=names, model=args.model)
        todo = list(info)
        print('这批 %d 篇里有数值的 %d 篇' % (len(names), len(todo)), flush=True)
    else:
        todo = None
    if todo == []:
        print('没有有数值的文章，跳过', flush=True)
    else:
        rc2 = em_main(common + ['--dp-model', args.model] + flags + (todo or []), show_next=False)

    rc3 = 0
    if not args.dry_run:
        print('\n==== 第 3 步：重新生成 datapoint.md（带测试方法，不调模型） ====', flush=True)
        rc3 = ed_main(['--build-only', '--root', args.root, '--model', args.model])
    print('\n全部完成，用时 %.0f 秒；datapoint.md、method.json 在 %s 的每篇文件夹里。' % (
        time.time() - t0, ed_papers_dir(args.root)))
    if rc1 or rc2 or rc3:
        print('（有出错的文章：第 1 步 %s、第 2 步 %s、第 3 步 %s；同一条命令再跑一次会接着补，已完成的不重问）' % (
            '有' if rc1 else '无', '有' if rc2 else '无', '有' if rc3 else '无'))
    return 1 if (rc1 or rc2 or rc3) else 0


# ====================================================================================================
# 建库（原 build_database\build_database.py）
# ====================================================================================================
r"""
build_database.py —— 每篇 datapoint.md 的数据 → 蛋白质功能特性数据库（第五步）

    python build_database.py                                  # 全部，写到 D:\2.elsevier_papers\database
    python build_database.py --root D:\1.acs_papers_done        # 别的总文件夹（写到它的 database）
    python build_database.py --out <目录>                      # 写到别处（测试用）
    python build_database.py 10.1021_acs.jafc.0c00745 ...     # 只建这几篇（测试用，配 --out）

文件夹结构（用户 2026-10-21 定，和 D:\acs_papers_done 一致；没有 papers 子文件夹的总文件夹，文章直接放在 <root> 下）：
输入（只读，不调模型、不花钱）：<root>\papers\<文章名>\datapoint.md，以及生成它的底稿——同一文件夹的 全文合并.md、
method.json 和 <root>\_records\数据点\_模型输出\<模型名>\ 的模型回答。用 extract_datapoint.py 生成 md 的
同一段程序（parse_doc → build_paper）取出结构化的数据点，所以处理参数、测定条件、来源位置都是分开的字段。
输出：<root>\database\（几张 CSV、README.md、_建库报告.md）。
用户 2026-10-21 起默认把 ACS + Elsevier 合成一个库 D:\protein_database，只重算新的、变了的文章（见本部分末尾 bd_DB_DIR）。

用户 2026-10-15 定：
  - 主表一行一个数值；几张 CSV 用编号相连 + 一张平铺总表（GitHub 建库，不要 SQLite）
  - 数据从生成 datapoint 的结构化底稿读
  - 只收 datapoint.md「样品数据」表里的数（已对应、含蛋白质的样品）；未进表、排除、模型判断不了的不进库
  - 列名英文、类别值中文（沿用 10-13 定的写法）

核对（每次运行都做，结果写进 _建库报告.md）：
  1 每篇按底稿重新生成 md，和磁盘上的 datapoint.md 逐字比——一致才说明库和 md 出自同一份数据
  2 用库里的列把每个格子的写法拼回去（测量名称 = 数值* ± SD 单位…｜测定条件），和 md 样品表逐格、逐个数值比；
    样品名称…体系这几行也逐格比
  3 编号不重复、每个数值挂到存在的样品上、样品挂到存在的文章上
"""


bd_DB_SUBDIR = 'database'               # 用户 2026-10-21：库写在 <root>\database（原来是 D:\acs_papers_数据库，已经不在了）
bd_REPORT_NAME = '_建库报告.md'


bd_OUT = os.path.join(ed_ROOT, bd_DB_SUBDIR)

bd_PROP_RANK = {c: k for k, c in enumerate(FUNCTIONAL)}
bd_JOURNALS = (('10.1021/acs.jafc.', 'Journal of Agricultural and Food Chemistry'),
            ('10.1021/jf', 'Journal of Agricultural and Food Chemistry'),
            ('10.1021/acsfoodscitech.', 'ACS Food Science & Technology'),
            ('10.1021/acsagscitech.', 'ACS Agricultural Science & Technology'),
            ('10.1021/acscombsci.', 'ACS Combinatorial Science'),
            ('10.1021/co', 'ACS Combinatorial Science'),
            ('10.1021/cc', 'Journal of Combinatorial Chemistry'),
            ('10.1021/acs.oprd.', 'Organic Process Research & Development'),
            ('10.1021/op', 'Organic Process Research & Development'))
bd_NO_MUL = ('', '1', '×1', 'x1')

# ================================================================ 表和列 ==
bd_PAPER_COLS = ['doi', 'article', 'title', 'journal', 'n_samples', 'n_measurements', 'n_from_table', 'n_from_text',
              'n_from_figure', 'extracted_by', 'extracted_at']
bd_SAMPLE_COLS = ['sample_id', 'doi', 'sample_no', 'sample_name', 'description', 'protein_source', 'protein_category',
               'protein_form', 'protein_source_std', 'protein_form_std', 'protein_conc', 'ingredients_summary',
               'treatment_summary', 'treatment_categories', 'treatment_types', 'treat_temperature', 'treat_time',
               'treat_ph', 'system', 'n_measurements', 'evidence']
bd_INGREDIENT_COLS = ['sample_id', 'doi', 'ingredient_no', 'name', 'category', 'amount']
bd_TREATMENT_COLS = ['sample_id', 'doi', 'step_no', 'treatment_method', 'category', 'treatment_type', 'params',
                  'temperature_raw', 'temperature_c',
                  'time_raw', 'time_min', 'ph', 'pressure_raw', 'pressure_mpa', 'power_raw', 'power_w', 'frequency_raw',
                  'frequency_khz', 'enzyme', 'enzyme_dosage', 'reagent', 'reagent_conc', 'other_params']
bd_TREATMENT_PARAM_COLS = ['sample_id', 'doi', 'step_no', 'param_no', 'name', 'value', 'unit']
bd_COND_COLS = ['cond_ph', 'cond_temperature_raw', 'cond_temperature_c', 'cond_time_raw', 'cond_time_min',
             'cond_ionic_strength', 'cond_concentration', 'cond_other', 'conditions_all']
bd_METHOD_COLS = ['method_id', 'test_method', 'test_method_en', 'method_params', 'method_status']   # 用户 2026-10-19 加：测定方法
bd_MEASURE_COLS = (['measurement_id', 'sample_id', 'doi', 'sample_no', 'property', 'property_cn', 'measure_name', 'value',
                 'value_text', 'sd', 'err_low', 'err_high', 'unit', 'multiplier', 'significance', 'value_std',
                 'unit_std'] + bd_COND_COLS + bd_METHOD_COLS +
                ['source_type', 'model_estimated', 'source_item', 'source_panel', 'series', 'x', 'x_unit', 'x_variable',
                 'source_text', 'check_note'])
bd_METHODS_TABLE_COLS = ['doi', 'method_id', 'property', 'property_cn', 'test_method', 'test_method_en', 'method_raw',
                      'reference', 'instrument', 'method_params', 'method_summary', 'applies_to', 'n_measurements',
                      'evidence_check']
bd_CONDITION_COLS = ['measurement_id', 'sample_id', 'doi', 'cond_no', 'name', 'value', 'unit']
bd_FLAT_SAMPLE_KEYS = ('sample_name', 'description', 'protein_source', 'protein_category', 'protein_form',
                       'protein_source_std', 'protein_form_std', 'protein_conc', 'ingredients_summary',
                       'treatment_summary', 'treatment_categories', 'treatment_types', 'system')
bd_FLAT_COLS = (['measurement_id', 'sample_id', 'doi', 'title', 'journal', 'sample_no'] + list(bd_FLAT_SAMPLE_KEYS[:-1]) +
             ['treat_temperature_c', 'treat_time_min', 'treat_ph', 'treat_pressure_mpa', 'treat_power_w',
              'treat_frequency_khz', 'treat_enzyme', 'system'] + bd_MEASURE_COLS[4:])
bd_TABLES = (('papers', bd_PAPER_COLS), ('samples', bd_SAMPLE_COLS), ('ingredients', bd_INGREDIENT_COLS),
          ('treatments', bd_TREATMENT_COLS), ('treatment_params', bd_TREATMENT_PARAM_COLS),
          ('measurements', bd_MEASURE_COLS), ('measurement_conditions', bd_CONDITION_COLS),
          ('methods', bd_METHODS_TABLE_COLS), ('flat_measurements', bd_FLAT_COLS))

# ================================================================ 单位换算 ==
# 原值照留（*_raw、value、unit），另给标准单位的数；换不了的留空（同类参数有几个时也留空，免得挑错）
bd_UNIT_FACTORS = {
    'nm': {'nm': 1, 'um': 1e3, 'micrometer': 1e3, 'micrometers': 1e3, 'micron': 1e3, 'microns': 1e3, 'mm': 1e6},
    'min': {'s': 1 / 60, 'sec': 1 / 60, 'secs': 1 / 60, 'second': 1 / 60, 'seconds': 1 / 60, 'min': 1, 'mins': 1,
            'minute': 1, 'minutes': 1, 'h': 60, 'hr': 60, 'hrs': 60, 'hour': 60, 'hours': 60, 'd': 1440,
            'day': 1440, 'days': 1440, 'week': 10080, 'weeks': 10080},
    'MPa': {'mpa': 1, 'kpa': 1e-3, 'pa': 1e-6, 'gpa': 1e3, 'bar': 0.1, 'psi': 0.00689476, 'atm': 0.101325},
    'W': {'w': 1, 'kw': 1e3},
    'kHz': {'khz': 1, 'hz': 1e-3, 'mhz': 1e3},
    'mV': {'mv': 1, 'v': 1e3},
}
bd_CELSIUS = {'°c', 'c', 'oc', 'degc', 'deg c', 'degreesc', 'degree c', 'degrees c'}
bd_NUM_UNIT = re.compile(r'^\s*(%s)\s*(.*?)\s*$' % ed_NUM)

# 数值的标准单位（用户 2026-10-27「单位统一更多性质」；原来只换粒径、ζ-电位）：每项性质能换的单位族，前面的先试。
# 同一个写法在不同性质里意思不同（mm：泡沫高度是毫米，游离氨基是毫摩尔每升），所以按性质给单位族。
bd_VALUE_UNITS = {
    'nm': {'nm': 1, 'd.nm': 1, 'dnm': 1, 'um': 1e3, 'micrometer': 1e3, 'micrometers': 1e3, 'micron': 1e3,
           'microns': 1e3, 'mm': 1e6, '10-6m': 1e3},
    'mV': {'mv': 1, 'v': 1e3},
    'min': {'s': 1 / 60, 'sec': 1 / 60, 'secs': 1 / 60, 'second': 1 / 60, 'seconds': 1 / 60, 'min': 1, 'mins': 1,
            'minute': 1, 'minutes': 1, 'h': 60, 'hr': 60, 'hrs': 60, 'hour': 60, 'hours': 60, 'd': 1440, 'day': 1440,
            'days': 1440},
    '%': {'%': 1, 'percent': 1, '%dh': 1, 'dh,%': 1, 'dh(%)': 1, '(%)': 1},
    'm²/g': {'m2/g': 1, 'cm2/g': 1e-4, 'm2/mg': 1e3},
    'mL': {'ml': 1, 'l': 1e3, 'ul': 1e-3, 'cm3': 1},
    'Pa': {'pa': 1, 'kpa': 1e3, 'mpa': 1e6, 'dyne/cm2': 0.1, 'dyn/cm2': 0.1, 'n/m2': 1},
    'N': {'n': 1, 'mn': 1e-3, 'kn': 1e3, 'g': 0.00980665, 'gf': 0.00980665, 'kgf': 9.80665, 'kg': 9.80665},
    'mg/mL': {'mg/ml': 1, 'g/l': 1, 'ug/ml': 1e-3, 'mg/l': 1e-3, 'ug/ul': 1, 'g/ml': 1e3, 'g/100ml': 10, 'mg/dl': 0.01},
    'g/g': {'g/g': 1, 'g/gram': 1, 'g/100g': 0.01, 'kg/kg': 1},
    'mL/g': {'ml/g': 1, 'ml/100g': 0.01, 'l/kg': 1},
    'mg/g': {'mg/g': 1, 'ug/mg': 1, 'g/100g': 10, 'g/kg': 1, 'mg/100mg': 10},
    'µmol/g': {'umol/g': 1, 'nmol/mg': 1, 'mmol/g': 1e3, 'nmol/g': 1e-3, 'mol/g': 1e6, 'umol/mg': 1e3, 'pmol/mg': 1e-3,
               'mol/105g': 10, 'moles/105g': 10},
    'mM': {'mm': 1, 'mmol/l': 1, 'um': 1e-3, 'umol/l': 1e-3, 'mol/l': 1e3, 'm': 1e3, 'nmol/ml': 1e-3, 'umol/ml': 1},
    'µM': {'um': 1, 'umol/l': 1, 'mm': 1e3, 'mmol/l': 1e3, 'nm': 1e-3, 'nmol/l': 1e-3, 'nmol/ml': 1},
}
bd_PROP_UNITS = {
    'particle_size': ('nm',), 'zeta_potential': ('mV',), 'solubility': ('%', 'mg/mL'),
    'emulsifying': ('m²/g', 'min', '%'), 'foaming': ('%', 'min', 'mL'), 'gelling': ('Pa', 'N'),
    'water_holding': ('g/g', 'mL/g', '%'), 'oil_holding': ('g/g', 'mL/g', '%'), 'sulfhydryl': ('µmol/g',),
    'disulfide': ('µmol/g', '%'), 'free_amino': ('mM', '%'), 'antioxidant': ('%', 'µM', 'mg/mL'),
    'degree_of_hydrolysis': ('%',), 'encapsulation': ('%', 'mg/g'),
}
# 不影响换算的说明字（g H2O/g sample → g/g；nmol/mg of protein → nmol/mg）；基准不同的（per g flour）不去，换不了照留
bd_UNIT_NOISE = re.compile(r'\b(?:of|per|water|h2o|oil|sample|protein|prot|soluble|dry|matter|dm|db|dw|basis|base|'
                           r'isolate|powder|bound|absorbed|retained|wet)\b')


def bd_unit_key(u):
    u = unicodedata.normalize('NFKC', u or '').strip().casefold().replace('µ', 'u').replace('μ', 'u')
    u = u.replace('℃', '°c').replace('º', '°')
    return re.sub(r'\s+', ' ', u).strip(' .')


def bd_split_value(value, unit):
    """(数, 单位)：值里带着单位（「90 °C」、单位栏空）也拆得开；不是单个数返回 (None, 单位)。"""
    v = ed_num_text(value)
    if v is not None:
        return float(v), unit or ''
    m = bd_NUM_UNIT.match(unicodedata.normalize('NFKC', str(value or '')).translate(ed_DASHES))
    if m and m.group(2) and not unit:
        return float(m.group(1)), m.group(2)
    return None, unit or ''


def bd_fmt_num(x):
    return '' if x is None else ('%.6g' % x)


def bd_to_std(value, unit, target):
    """换成标准单位：target = nm / min / MPa / W / kHz / mV / °C；换不了返回 ''。"""
    x, u = bd_split_value(value, unit)
    if x is None:
        return ''
    k = bd_unit_key(u)
    if target == '°C':
        if k in bd_CELSIUS:
            return bd_fmt_num(x)
        if k == 'k':
            return bd_fmt_num(x - 273.15)
        if k in ('°f', 'f'):
            return bd_fmt_num((x - 32) * 5 / 9)
        return ''
    f = bd_UNIT_FACTORS[target].get(k.replace(' ', ''))
    return bd_fmt_num(x * f) if f is not None else ''


def bd_unit_compact(u):
    """单位写法压缩成查表用的样子：m² g⁻¹ → m2/g，mg mL^-1 → mg/ml，µmol/g protein → umol/g。"""
    s = unicodedata.normalize('NFKC', u or '').casefold().replace('µ', 'u').replace('μ', 'u')
    s = bd_UNIT_NOISE.sub(' ', s.translate(ed_DASHES))
    s = re.sub(r'[\s^·*{}×]', '', s)
    s = re.sub(r'(?<=[a-z0-9])(g|ml|l|s|min|mg|kg)-1', r'/\1', s)
    return s.strip('.,;')


def bd_value_std(prop, value, unit):
    """数值 → (标准单位的数, 标准单位)；这项性质没有能换的单位族、或单位认不出 → ('', '')。"""
    fams = bd_PROP_UNITS.get(prop)
    x, u = bd_split_value(value, unit) if fams else (None, '')
    if x is None:
        return '', ''
    k = bd_unit_compact(u)
    if prop == 'particle_size':
        k = re.sub(r'^d[.,]?(?=nm|um)', '', k).split(',')[0]       # d.nm、μm, d43 → nm、um
    for fam in fams:
        f = bd_VALUE_UNITS[fam].get(k)
        if f is not None:
            return bd_fmt_num(x * f), fam
    return '', ''


def bd_param_slot(name, measuring=False):
    """参数名 → 归到哪一列。处理参数（measuring=False）和测定条件（True）共用。"""
    n = ' '.join((name or '').casefold().split())
    if not measuring and ('enzyme' in n or 'protease' in n):
        if any(w in n for w in ('dos', 'concentration', 'amount', 'e/s', 'ratio', 'activity', 'unit', 'loading',
                                'level', 'addition')):
            return 'enzyme_dosage'
        return 'enzyme'
    if not measuring and 'reagent' in n:
        return 'reagent_conc' if any(w in n for w in ('conc', 'amount', 'ratio', 'dos')) else 'reagent'
    if n == 'ph' or n.startswith('ph ') or n.endswith(' ph') or n == 'p h':
        return 'ph'
    if 'temperature' in n or n == 'temp':
        return 'temperature'
    if n == 'time' or n.endswith(' time') or n.startswith('time ') or 'duration' in n:
        return 'time'
    if measuring:
        if any(w in n for w in ('ionic', 'nacl', 'kcl', 'cacl', 'mgcl', 'salt')):
            return 'ionic'
        if any(w in n for w in ('concentration', 'content', 'ratio', 'fraction')):
            return 'concentration'
        return 'other'
    for key in ('pressure', 'power', 'frequency'):
        if key in n:
            return key
    return 'other'


def bd_nvu(p):
    return '%s=%s' % (p.get('name', ''), ed_vu(p))


def bd_one_std(params, target):
    return bd_to_std(params[0].get('value'), params[0].get('unit'), target) if len(params) == 1 else ''


def bd_treatment_row(sample_id, doi, k, st):
    b = collections.defaultdict(list)
    for p in st.get('params') or []:
        b[bd_param_slot(p.get('name'))].append(p)
    return {'sample_id': sample_id, 'doi': doi, 'step_no': k, 'treatment_method': st.get('method', ''),
            'category': st.get('category', ''), 'treatment_type': bd_treatment_types(st.get('method', '')),
            'params': ed_param_text(st.get('params')),
            'temperature_raw': ' | '.join(ed_vu(p) for p in b['temperature']),
            'temperature_c': bd_one_std(b['temperature'], '°C'),
            'time_raw': ' | '.join(ed_vu(p) for p in b['time']), 'time_min': bd_one_std(b['time'], 'min'),
            'ph': ' | '.join(str(p.get('value', '')) for p in b['ph']),
            'pressure_raw': ' | '.join(ed_vu(p) for p in b['pressure']), 'pressure_mpa': bd_one_std(b['pressure'], 'MPa'),
            'power_raw': ' | '.join(ed_vu(p) for p in b['power']), 'power_w': bd_one_std(b['power'], 'W'),
            'frequency_raw': ' | '.join(ed_vu(p) for p in b['frequency']),
            'frequency_khz': bd_one_std(b['frequency'], 'kHz'),
            'enzyme': ' | '.join(ed_vu(p) for p in b['enzyme']),
            'enzyme_dosage': ' | '.join(ed_vu(p) for p in b['enzyme_dosage']),
            'reagent': ' | '.join(ed_vu(p) for p in b['reagent']),
            'reagent_conc': ' | '.join(ed_vu(p) for p in b['reagent_conc']),
            'other_params': '; '.join(bd_nvu(p) for p in b['other'])}


def bd_cond_fields(conds):
    b = collections.defaultdict(list)
    for p in conds or []:
        b[bd_param_slot(p.get('name'), measuring=True)].append(p)
    return {'cond_ph': ' | '.join(str(p.get('value', '')) for p in b['ph']),
            'cond_temperature_raw': ' | '.join(ed_vu(p) for p in b['temperature']),
            'cond_temperature_c': bd_one_std(b['temperature'], '°C'),
            'cond_time_raw': ' | '.join(bd_nvu(p) for p in b['time']), 'cond_time_min': bd_one_std(b['time'], 'min'),
            'cond_ionic_strength': '; '.join(bd_nvu(p) for p in b['ionic']),
            'cond_concentration': '; '.join(bd_nvu(p) for p in b['concentration']),
            'cond_other': '; '.join(bd_nvu(p) for p in b['other'])}


# ================================================================ 规范化（建模、网站筛选用；原文列照留） ==
# 用户 2026-10-27：「蛋白来源和处理方法规范化」「单位统一更多性质」「支持实验方法的筛选」。全用程序规则，不调模型。
# 认不出来的留空（原文还在 protein_source / protein_form / treatment_method / unit 里）。


def bd_norm_text(s):
    s = unicodedata.normalize('NFKC', s or '').casefold()
    return re.sub(r'\s+', ' ', s.replace('’', "'").replace('‘', "'").replace('`', "'")).strip()


# ---------------------------------------------------------------- 蛋白来源 → 标准名称 --
# 一条 = (标准名称, 正则)；在「蛋白来源 ; 蛋白形态」里找，命中几条就记几条（复配样品有几种来源，| 隔开）。
# 前面的先认；后面的规则碰到已经认过的字不再认（chickpea 认过以后 pea 不再认，鸡蛋认过以后鸡不再认）。
bd_EGG_HOST = r"(?:(?:hens?|chicken|domestic fowl|laying hens?)'?s? )?"
bd_SOURCE_RULES = (
    # 乳：先认别的物种（不带乳的说法后面改成肉），剩下的乳都算牛乳
    ('Milk (human)', r'human (?:breast )?milk|breast milk|母乳|人乳'),
    ('Milk (goat)', r'goat|caprine|山羊'),
    ('Milk (sheep)', r'\bewes?\b|\bovine milk|\bsheep\'?s? milk|绵羊乳'),
    ('Milk (camel)', r'camel|骆驼'),
    ('Milk (buffalo)', r'buffalo|水牛'),
    ('Milk (yak)', r'yak milk|yak casein|牦牛乳|牦牛奶'),
    ('Milk (donkey / mare)', r'donkey|mare\'?s? milk|驴乳|马乳'),
    ('Milk (bovine)', r'\bmilks?\b|buttermilk|\bwhey|\bcasein|caseinate|lactoglobulin|lactalbumin|lactoferrin|colostrum|\bcheese|'
                      r'\bdairy|\bmfgm\b|\bwpi\b|\bwpc\b|\bβ-lg\b|\bblg\b|glycomacropeptide|\bcream\b|yogh?urt|kefir|'
                      r'牛乳|牛奶|乳清|酪蛋白|乳蛋白|脱脂乳|全脂乳|乳铁蛋白|乳球蛋白|乳白蛋白|奶酪|酸奶|乳粉|奶粉'),
    # 蛋：先认别的禽蛋，剩下的都算鸡蛋
    ('Egg (duck)', r'duck eggs?(?: white| yolk)?|鸭蛋'),
    ('Egg (quail)', r'quail|鹌鹑'),
    ('Egg (goose)', r'goose eggs?|鹅蛋'),
    ('Egg (hen)', bd_EGG_HOST + r'(?:eggs?\b(?: white| yolk)?|egg white|egg yolk|albumen|yolk)|ovalbumin|ovotransferrin|'
                  r'ovomucoid|ovomucin|lysozyme|eggshell|\bhewl?\b|phosvitin|livetin|鸡蛋|鸡卵|蛋清|蛋黄|卵清|卵白|溶菌酶|全蛋'),
    # 豆类
    ('Chickpea', r'chick ?peas?|garbanzo|cicer arietinum|鹰嘴豆'),
    ('Cowpea', r'cow ?peas?|vigna unguiculata|豇豆'),
    ('Pigeon pea', r'pigeon ?peas?|cajanus|木豆'),
    ('Grass pea', r'grass ?peas?|lathyrus'),
    ('Pea', r'\bpeas?\b|pisum|豌豆'),
    ('Peanut', r'peanuts?|groundnuts?|arachis|花生'),
    ('Soybean', r'\bsoy|soya|glycine ?max|glycinin|conglycinin|okara|tofu|natto|douchi|miso\b|大豆|黄豆|豆粕|豆乳|豆浆|'
                r'腐竹|豆腐'),
    ('Faba bean', r'faba|fava|broad beans?|vicia faba|蚕豆'),
    ('Mung bean', r'mung ?beans?|vigna radiata|绿豆'),
    ('Adzuki bean', r'adzuki|azuki|vigna angularis|红小豆|赤小豆'),
    ('Lentil', r'lentils?|lens culinaris|兵豆|小扁豆'),
    ('Lupin', r'lupin|lupinus|羽扇豆'),
    ('Common bean', r'phaseolus|kidney beans?|black beans?|navy beans?|pinto|common beans?|red beans?|white beans?|'
                    r'great northern|haricot|phaseolin|菜豆|芸豆|黑豆|红豆'),
    ('Bean (other)', r'\bbeans?\b|\bguar\b|cyamopsis|carob|ceratonia|fenugreek|trigonella|canavalia|mucuna|bambara|lablab|psophocarpus|豆'),
    # 谷物
    ('Wheat', r'wheat|gluten|gliadin|glutenin|durum|semolina|triticum|spelt|einkorn|emmer|aegilops|seitan|小麦|面筋|'
              r'麦醇溶|面粉|面团'),
    ('Corn', r'\bcorn|maize|zea mays|\bzein|ddgs|distillers|玉米'),
    ('Rice', r'\brice|oryza|米糠|大米|稻'),
    ('Barley', r'barley|hordeum|hordein|\bmalt|brewers?\'?s? spent grain|\bbsg\b|\bwort\b|\bbeer|大麦|麦芽|啤酒'),
    ('Oat', r'\boats?\b|avena|avenin|燕麦'),
    ('Rye', r'\brye\b|secale|secalin|黑麦'),
    ('Triticale', r'triticale|小黑麦'),
    ('Sorghum', r'sorghum|kafirin|高粱'),
    ('Millet', r'millet|setaria|eleusine|pennisetum|panicum|\bteff\b|eragrostis|fonio|小米|谷子|粟|黍|稷'),
    ('Buckwheat', r'buckwheat|fagopyrum|荞麦'),
    ('Quinoa', r'quinoa|chenopodium|藜麦'),
    ('Amaranth', r'amaranth|苋'),
    # 油料、坚果、种子
    ('Rapeseed / canola', r'rapeseed|canola|brassica napus|brassica campestris|brassica rapa|cruciferin|napin|油菜|菜籽'),
    ('Mustard', r'mustard|brassica juncea|brassica carinata|sinapis|crambe|芥'),
    ('Sunflower', r'sunflower|helianthus|向日葵|葵花'),
    ('Sesame', r'sesame|sesamum|芝麻'),
    ('Cottonseed', r'cotton ?seed|gossypium|棉籽'),
    ('Flaxseed', r'flax|linseed|linum|亚麻'),
    ('Hemp', r'hemp|cannabis|edestin|火麻|大麻'),
    ('Chia', r'\bchia\b|salvia hispanica|奇亚'),
    ('Pumpkin seed', r'pumpkin|cucurbita|南瓜'),
    ('Watermelon / melon seed', r'watermelon|melon seeds?|citrullus|西瓜'),
    ('Almond', r'almonds?|prunus dulcis|杏仁'),
    ('Apricot kernel', r'apricot|杏'),
    ('Walnut', r'walnuts?|juglans|核桃'),
    ('Hazelnut', r'hazelnuts?|corylus|榛'),
    ('Cashew', r'cashews?|anacardium|腰果'),
    ('Pistachio', r'pistachios?|开心果'),
    ('Pecan', r'pecans?|carya'),
    ('Macadamia', r'macadamia|澳洲坚果'),
    ('Pine nut', r'pine nuts?|pinus|松子'),
    ('Chestnut', r'chestnuts?|castanea|板栗'),
    ('Coconut', r'coconut|cocos|椰'),
    ('Oil palm', r'palm kernel|oil palm|elaeis'),
    ('Jatropha', r'jatropha|麻疯树'),
    ('Moringa', r'moringa|辣木'),
    ('Perilla', r'perilla|紫苏'),
    ('Camellia / tea seed', r'camellia oleifera|tea seeds?|油茶'),
    ('Grape seed', r'grape ?seeds?|葡萄籽'),
    ('Tomato seed', r'tomato seeds?|番茄籽'),
    ('Tiger nut', r'tiger ?nuts?|cyperus esculentus|油莎豆'),
    # 块茎、蔬果、叶
    ('Sweet potato', r'sweet ?potato|ipomoea batatas|sporamin|甘薯|红薯|地瓜'),
    ('Potato', r'potato|solanum tuberosum|patatin|马铃薯|土豆'),
    ('Yam', r'\byams?\b|dioscorea|山药|薯蓣'),
    ('Taro', r'\btaro\b|colocasia|芋'),
    ('Cassava', r'cassava|manihot|木薯'),
    ('Grape / wine', r'grapes?|vitis|\bwines?\b|葡萄'),
    ('Coffee', r'coffee|coffea|咖啡'),
    ('Cocoa', r'cocoa|cacao|theobroma|可可'),
    ('Tea', r'\btea\b|camellia sinensis|茶'),
    ('Leaf protein (RuBisCO)', r'rubisco|leaf protein|alfalfa|lucerne|medicago|spinach|duckweed|\blemna|water lentil|'
                              r'mulberry leaves|beet leaves|苜蓿|菠菜|浮萍|桑叶'),
    ('Fruit / vegetable (other)', r'\bapples?\b|tomato|cucumber|jujube|kiwi|banana|mango|okra|\bpeppers?\b|sugarcane|'
                                  r'cabbage|\bkale\b|broccoli|carrot|daucus|papaya|litchi|lychee|\bpeach|guava|psidium|eggplant|cauliflower|'
                                  r'sugar beet|\bbeets?\b|苹果|番茄|黄瓜|枣|甘蔗|胡萝卜|荔枝|桃'),
    # 微生物、藻类、菌菇
    ('Yeast', r'yeast|saccharomyces|mannoprotein|pichia|candida|torula|酵母'),
    ('Mushroom / fungi', r'mushroom|agaricus|pleurotus|lentinula|lentinus|ganoderma|flammulina|hericium|tremella|'
                         r'auricularia|cordyceps|mycoprotein|fusarium venenatum|aspergillus|rhizopus|neurospora|'
                         r'mycelium|fungal|fungi|蘑菇|香菇|平菇|灵芝|金针菇|菌丝|真菌'),
    ('Bacteria', r'bacillus|lactobacillus|lactococcus|lacticaseibacillus|lactiplantibacillus|streptococcus|'
                 r'escherichia|e\. ?coli|klebsiella|bacteria|bacterial|corynebacterium|methylococcus|cupriavidus|'
                 r'pseudomonas|streptomyces|细菌|乳酸菌|大肠杆菌|芽孢杆菌'),
    ('Microalgae', r'spirulina|arthrospira|chlorella|nannochloropsis|microalga|tetraselmis|euglena|haematococcus|'
                   r'dunaliella|phaeodactylum|isochrysis|scenedesmus|螺旋藻|小球藻|微藻'),
    ('Seaweed', r'seaweed|macroalga|laminaria|saccharina|undaria|porphyra|pyropia|\bulva\b|palmaria|gracilaria|'
                r'sargassum|halopteris|\bkelp|\bnori\b|海藻|紫菜|海带|裙带菜'),
    # 昆虫
    ('Cricket', r'cricket|gryllus|acheta|gryllodes|蟋蟀'),
    ('Mealworm', r'mealworm|tenebrio|alphitobius|zophobas|黄粉虫'),
    ('Black soldier fly', r'black soldier fly|hermetia|黑水虻'),
    ('Silkworm', r'silkworm|bombyx|\bsilk|fibroin|sericin|蚕|丝素|丝胶'),
    ('Locust / grasshopper', r'locust|grasshopper|schistocerca|蝗'),
    ('Insect (other)', r'insect|caterpillar|gonimbrasia|mopane|gynanisa|palm weevil|rhynchophorus|termite|\bapis\b|'
                       r'\bbees?\b|昆虫'),
    # 水产
    ('Krill', r'krill|euphausia|euphasia|磷虾'),
    ('Shrimp / prawn', r'shrimp|prawn|\bacetes|litopenaeus|penaeus|pandalus|crangon|macrobrachium|虾'),
    ('Crab / lobster / crayfish', r'\bcrabs?\b|eriocheir|portunus|callinectes|lobster|crayfish|procambarus|蟹'),
    ('Squid / octopus / cuttlefish', r'squid|octopus|cuttlefish|loligo|dosidicus|todarodes|todaropsis|\billex|'
                                     r'\bsepia|eledone|ommastrephes|\bpota\b|鱿鱼|章鱼|乌贼|墨鱼'),
    ('Mollusc / shellfish', r'mussel|mytilus|oyster|crassostrea|scallop|pecten|patinopecten|chlamys|argopecten|'
                            r'\bclams?\b|ruditapes|tegillarca|\bark shell|limpet|patella|abalone|haliotis|snail|whelk|贻贝|牡蛎|扇贝|蛤|鲍|螺'),
    ('Sea cucumber', r'sea cucumber|stichopus|apostichopus|holothuria|海参'),
    ('Jellyfish', r'jellyfish|rhopilema|海蜇|水母'),
    ('Fish', r'\bfish|\bcod\b|gadus|salmon|\bsalmo\b|oncorhynchus|trout|tilapia|oreochromis|\bcarp\b|cyprinus|'
             r'hypophthalmichthys|ctenopharyngodon|aristichthys|pollo[c]?k|pollack|theragra|mackerel|scomber|'
             r'scomer|\btuna|thunnus|katsuwonus|herring|clupea|sardin|anchov|engraulis|\bhake\b|merluccius|'
             r'urophycis|catfish|ictalurus|pangasius|silurus|sea bass|dicentrarchus|lateolabrax|bream|sparus|'
             r'croaker|micropog|larimichthys|pseudosciaena|\beels?\b|anguilla|conger|whiting|micromesistius|'
             r'haddock|melanogrammus|saithe|pollachius|\bhoki\b|macruronus|johnius|codling|physiculus|\bling\b|'
             r'ophiodon|molva|rockfish|sebastes|snapper|lutjanus|grouper|epinephelus|\bperch|flounder|halibut|'
             r'hippoglossus|plaice|\bsole\b|turbot|mullet|mugil|capelin|\bsprat|menhaden|sturgeon|acipenser|'
             r'\bpike\b|\bloach|misgurnus|\bscad\b|collichthys|fugu|takifugu|threadfin|nemipterus|lizardfish|saurida|surimi|swordfish|shark|\bskate\b|pterothrissus|'
             r'鱼|鳕|鲑|鳟|罗非|鲤|鲢|鳙|鲭|金枪|鲱|沙丁|鳀|鳗|鲈|鲷|鱿'),
    # 畜禽及其副产物（乳、蛋已经认过）
    ('Chicken', r'chicken|broiler|\bhens?\b|gallus|poultry|鸡'),
    ('Duck', r'\bducks?\b|anas platyrhynchos|鸭'),
    ('Goose', r'\bgoose|鹅'),
    ('Turkey', r'\bturkey|meleagris|火鸡'),
    ('Pork / porcine', r'\bpork|porcine|\bpigs?\b|piglet|swine|sus scrofa|\bhogs?\b|\blard\b|\bham\b|猪'),
    ('Beef / bovine', r'\bbeef|bovine|cattle|\bcows?\b|\bcow\'s|\bcalf|calves|calfskin|\bveal|\bbsa\b|bos taurus|'
                      r'\box\b|\byak|bison|牛'),
    ('Sheep / goat (meat)', r'\blambs?\b|mutton|\bsheep|ovine|\bovis\b|羊'),
    ('Horse', r'\bhorse|equine|\bequus|马'),
    ('Rabbit', r'rabbit|oryctolagus|兔'),
    ('Deer', r'\bdeer|venison|\bcervus|鹿'),
    ('Frog', r'\bfrogs?\b|\brana\b|lithobates|蛙'),
    ('Human', r'\bhuman|homo sapiens|saliva|人血|人源|人体'),
    ('Laboratory animal', r'\bmouse|\bmice\b|\brats?\b|murine|guinea pig|小鼠|大鼠'),
    ('Gelatin / collagen (species not stated)', r'gelatin|collagen|明胶|胶原'),
    ('Meat (species not stated)', r'\bmeats?\b|muscle|myofibril|myosin|sarcoplasm|\bmince|肉|肌原纤维|肌球'),
    ('Blood / plasma (species not stated)', r'\bblood|plasma|serum|hemoglobin|haemoglobin|血'),
    ('Plant (other)', r'\bseeds?\b|\bplants?\b|\bleaves\b|\bleaf\b|kernels?|\bnuts?\b|legume|pulse|cereal|grain|植物|种子'),
)
bd_SOURCE_RES = tuple((name, re.compile(rx)) for name, rx in bd_SOURCE_RULES)
bd_SOURCE_GENERIC = ('Gelatin / collagen (species not stated)', 'Meat (species not stated)',
                     'Blood / plasma (species not stated)', 'Plant (other)', 'Bean (other)')
bd_MILK_CUES = re.compile(r'milk|whey|casein|lacto|dairy|cheese|colostrum|cream|curd|乳|奶')
bd_OTHER_MILK = {'Milk (goat)': 'Sheep / goat (meat)', 'Milk (sheep)': 'Sheep / goat (meat)',
                 'Milk (buffalo)': 'Beef / bovine', 'Milk (yak)': 'Beef / bovine'}
bd_PLANT_MILK = re.compile(r'\b(soy|soya|soybean|coconut|almond|oat|rice|peanut|walnut|hemp|cashew|plant|pea)[- ]?'
                           r'(milk|whey)')            # 植物「奶」不是乳（\b：goat milk 里的 oat milk 不算）


def bd_source_std(source, form=''):
    """蛋白来源（+ 蛋白形态）→ 标准名称，几种用 | 隔开；认不出来的留空。"""
    text = bd_PLANT_MILK.sub(r'\1 drink', bd_norm_text('%s ; %s' % (source, form)))
    found, used = [], []
    for name, rx in bd_SOURCE_RES:
        for m in rx.finditer(text):
            a, b = m.span()
            if any(x < b and a < y for x, y in used):
                continue
            used.append((a, b))
            if name not in found:
                found.append(name)
    if not bd_MILK_CUES.search(text):            # 「goat」「buffalo」没说是乳 → 肉
        found = [bd_OTHER_MILK.get(f, f) for f in found]
    if any(f.startswith('Milk (') and f != 'Milk (bovine)' for f in found) and 'Milk (bovine)' in found \
            and not re.search(r'bovine|\bcows?\b|cow\'s|cattle|牛', text):
        found.remove('Milk (bovine)')           # 「goat milk」的 milk 不是牛乳
    if 'Milk (bovine)' in found and 'Beef / bovine' in found and not re.search(
            r'beef|meat|muscle|serum|blood|plasma|skin|hide|bone|\bbsa\b|collagen|gelatin|tendon|ligament|牛肉', text):
        found.remove('Beef / bovine')            # 「bovine milk」的 bovine 不是牛肉
    if any(f not in bd_SOURCE_GENERIC for f in found):
        found = [f for f in found if f not in bd_SOURCE_GENERIC]
    return ' | '.join(dict.fromkeys(found))


# ---------------------------------------------------------------- 蛋白形态 → 标准类别 --
bd_FORM_RULES = (
    ('Hydrolysate', r'hydroly|digest|水解|酶解|消化'),
    ('Peptide', r'peptide|\bpeptides?\b|肽'),
    ('Muscle / myofibrillar protein', r'myofibril|sarcoplasm|actomyosin|\bmyosin|surimi|\bmince|muscle|fillet|'
                                      r'\bmeats?\b|meat batter|tissue|肌原纤维|肌球|肌肉|鱼糜|肉'),
    ('Isolate', r'isolate|\bspi\b|\bwpi\b|\bppi\b|分离蛋白|分离物|蛋白分离'),
    ('Concentrate', r'concentrate|\bwpc\b|\bspc\b|浓缩'),
    ('Caseinate', r'caseinate|酪蛋白酸'),
    ('Gelatin / collagen', r'gelatin|collagen|明胶|胶原'),
    ('Single purified protein', r'lactoglobulin|lactalbumin|lactoferrin|ovalbumin|lysozyme|ovotransferrin|ovomucin|'
                                r'\bbsa\b|serum albumin|myoglobin|h(a)?emoglobin|tropomyosin|ferritin|crystallin|'
                                r'synuclein|insulin|[αβκγ]s?\d?-casein|\bβ-lg\b|inhibitor|glycoprotein|phosphoprotein|phosvitin|keratin|enzyme|amylase|protease|proteinase|lipase|'
                                r'recombinant|fusion protein|purified|纯化|单体|重组|乳铁蛋白|乳球蛋白|溶菌酶|酶'),
    ('Protein fraction', r'globulin|albumin|glutelin|prolamin|\bzein|gliadin|glutenin|gluten|hordein|kafirin|secalin|'
                         r'avenin|\b7s\b|\b11s\b|\b12s\b|glycinin|conglycinin|legumin|vicilin|cruciferin|napin|patatin|'
                         r'phaseolin|\bcasein|lipoprotein|\bldl\b|\bhdl\b|mannoprotein|fraction|组分|球蛋白|清蛋白|醇溶|'
                         r'谷蛋白|面筋|酪蛋白|脂蛋白'),
    ('Flour / meal / whole seed', r'flour|\bmeal\b|wholemeal|whole ?grain|semolina|\bbran\b|\bgrits?\b|\bseeds?\b|'
                                  r'\bgrains?\b|flakes|okara|ddgs|\bcake\b|\bmalt|endosperm|\bgerm\b|sprout|whole soy|soybeans|'
                                  r'全粉|粉|粕|全豆|全大豆|种子|籽|全料'),
    ('Whole food / raw material', r'\bmilk|egg white|egg yolk|whole egg|albumen|\byolk|soymilk|soy milk|dough|cheese|'
                                  r'cream|juice|\bwine|\bbeer|\bwort|\bwhey\b|plasma|serum|h(a)?emolysate|\bblood|乳|蛋清|蛋黄|全蛋|豆浆|豆乳|面团'),
    ('Particles / aggregates / complexes', r'particle|fibril|microgel|nanogel|aggregate|complex|conjugate|nanofib|'
                                           r'\bfilms?\b|\bgels?\b|micelle|oil bod|颗粒|微凝胶|复合|纤维|油体|聚集'),
    ('Extract (crude)', r'extract|soluble proteins?|粗提|提取|初提'),
    ('Powder (unspecified)', r'powder|粉末'),
)
bd_FORM_RES = tuple((name, re.compile(rx)) for name, rx in bd_FORM_RULES)


def bd_form_std(form):
    text = bd_norm_text(form)
    if not text or text in ('其他', '不明', 'other', 'unknown', 'n/a'):
        return ''
    return next((name for name, rx in bd_FORM_RES if rx.search(text)), 'Other')


# ---------------------------------------------------------------- 样品处理步骤 → 处理类型 --
# 一步可以有几类（「dialysis and lyophilization」= 分离纯化 + 干燥）。前面的先认，认过的字不再认。
# 改性处理在前、常规制样步骤（溶解、离心、干燥…）在后；网站按类型筛选样品。
bd_TREAT_RULES = (
    ('Separation / purification', r'gel (?:filtration|permeation)|silica gel|sephadex|sephacryl|superdex|'
                                  r'ion[- ]exchange|affinity|chromatograph|\bfplc\b|\bhplc\b|\brp-?lc\b|\brplc\b|'
                                  r'层析|色谱'),
    ('In vitro digestion', r'in vitro (?:oral |gastro|gastric|intestinal|digest|simulated)|simulated (?:gastro|gastric|'
                           r'intestinal|digest|saliva)|gastrointestinal digestion|infogest|消化'),
    ('Enzymatic hydrolysis', r'hydroly[sz]|alcalase|trypsin|tryptic|pepsin|peptic|papain|flavou?rzyme|neutrase|'
                             r'bromelain|thermolysin|protamex|chymotrypsin|pancreatin|proteinase|protease|pronase|'
                             r'peptidase|subtilisin|corolase|actinidin|digest|水解|酶解'),
    ('Enzymatic cross-linking', r'transglutaminase|\bm?tgase\b|\btg\b|laccase|tyrosinase|peroxidase|酶交联|谷氨酰胺转氨酶'),
    ('Enzyme treatment (other)', r'enzym|amylase|cellulase|celluclast|xylanase|phytase|lipase|glucosidase|deamidase|'
                                 r'glutaminase|pectinase|\bpngase|autolys|mashing|saccharif|liquefac|酶'),
    ('Fermentation', r'ferment|lactic acid bacteria|lactobacill|inoculat|\bbrewing|starter culture|sourdough|proof|'
                     r'vinific|cultivation|culture|发酵'),
    ('Germination / malting', r'germinat|sprout|malting|steeping|kiln|发芽|萌发'),
    ('Genetic modification / breeding', r'mutagen|mutant|transgen|breeding|backcross|introgress|knock-?out|'
                                        r'gene editing|crispr|突变|育种|转基因'),
    ('Glycation (Maillard)', r'maillard|glycat|glycosyl|conjugat\w* with (?:dextran|maltodextrin|glucose|lactose|'
                             r'polysaccharide|sugar|pectin|chitosan|galactomannan|gum)|糖基化|美拉德'),
    ('Acylation', r'acylat|acetylat|succinylat|anhydride|酰化|琥珀酰'),
    ('Phosphorylation', r'phosphorylat|polyphosphate|tripolyphosphate|\bstmp\b|\bstpp\b|磷酸化'),
    ('Deamidation', r'deamidat|脱酰胺'),
    ('Oxidation', r'oxidi[sz]|oxidat|fenton|hydroxyl radical|\baaph\b|hydrogen peroxide|\bh2o2\b|peroxyl|'
                  r'malondialdehyde|\bmda\b|acrolein|氧化'),
    ('Reduction / disulfide cleavage', r'electroreduc|reduction (?:reaction|with|by)|reduc(?:ing|ed|tive) '
                                       r'(?:treatment|agent|condition)|chemical reduction|\bdtt\b|dithiothreitol|'
                                       r'mercaptoethanol|\b2-me\b|\bβ-me\b|cysteine|sulfite|sulphite|glutathione|'
                                       r'\bgsh\b|还原'),
    ('Chemical denaturation', r'\burea\b|guanidin|\bsds\b|denatur|unfold|ethanol treat|变性'),
    ('Chemical cross-linking', r'glutaraldehyde|genipin|formaldehyde|cross-?link|交联'),
    ('Chemical modification (other)', r'graft|carbodiimide|\bedc\b|glyoxal|alkylat|cationiz|thiolat|seleni|'
                                      r'esterif|amidat|guanidinat|pegylat|chemical modif|covalent|conjugat|接枝|共价'),
    ('Polyphenol binding', r'polyphenol|phenolic|tannic|tannin|\begcg\b|catechin|epigallocatechin|chlorogenic|'
                           r'gallic|quercetin|rutin|resveratrol|anthocyanin|proanthocyanidin|ferulic|caffeic|'
                           r'procyanidin|flavonoid|多酚|单宁|儿茶素'),
    ('Polysaccharide complexation', r'polysaccharide|pectin|chitosan|carrageenan|alginate|xanthan|gum arabic|'
                                    r'arabic gum|acacia|guar|locust bean|gellan|dextran|maltodextrin|cellulose|\bcmc\b|'
                                    r'starch|inulin|beta-glucan|β-glucan|hyaluron|coacervat|多糖|果胶|壳聚糖|卡拉胶|海藻酸|'
                                    r'黄原胶|阿拉伯胶|淀粉'),
    ('pH shifting', r'ph[- ]?shift|ph[- ]?cycl|alkaline treatment|acid treatment|alkali treatment|alkaline ph|'
                    r'acidic ph|酸碱|ph偏移'),
    ('High-pressure homogenization', r'high[- ]pressure homogeni|ultra[- ]?high[- ]pressure homogeni|\bhph\b|\buhph\b|'
                                     r'microflui|dynamic high[- ]pressure|\bdhpm\b|high[- ]pressure valve|'
                                     r'two[- ]stage homogeni|高压均质|微射流'),
    ('High hydrostatic pressure', r'high hydrostatic|hydrostatic pressure|\bhhp\b|high[- ]pressure processing|\bhpp\b|'
                                  r'high[- ]pressure treat|ultra[- ]?high[- ]pressure treat|uhp treat|'
                                  r'\bhigh[- ]pressure\b|\bhp treat|pressuri[sz]|超高压'),
    ('Ultrasound', r'ultrason|sonicat|ultrasound|\bsonic|超声'),
    ('Pulsed electric field', r'pulsed electric|\bpef\b|电场'),
    ('Cold plasma', r'plasma treat|cold plasma|atmospheric plasma|dielectric barrier|等离子'),
    ('Irradiation / UV / light', r'irradiat|γ-ray|gamma|electron beam|\buv\b|ultraviolet|pulsed light|x-ray|'
                                 r'radiation|辐照|紫外'),
    ('Ozone', r'ozone|臭氧'),
    ('Microwave / radio frequency', r'microwave|radio[- ]?frequency|微波|射频'),
    ('Ohmic heating', r'ohmic'),
    ('Extrusion', r'extru|挤压'),
    ('Fibrillation', r'fibril|amyloid|纤维化'),
    ('Particle formation / encapsulation', r'nanoparticle|microparticle|encapsulat|loading|load(?:ed)? with|'
                                          r'anti-?solvent|desolvation|coprecipitat|co-precipitat|spray[- ]?chill|'
                                          r'electrospray|nanocomplex|complexation|self-assembl|liposome|pickering|'
                                          r'curcumin|corona|immobili[sz]|layer-by-layer|coating|包埋|纳米颗粒|自组装|复合'),
    ('Emulsification', r'emulsi|乳化|乳液'),
    ('Gelation', r'gelation|gelling|\bgels?\b|gel formation|coagulat|curdling|tofu|rennet|\bgdl\b|glucono|'
                 r'jellif|\bsetting\b|凝胶|凝固|点浆'),
    ('Forming / film / fibre', r'\bfilms?\b|casting|electrospin|electrostatic deposition|compression mold|mold|mould|'
                               r'stuff|casing|forming|shaping|punch|成膜|静电纺|成型'),
    ('Salt / ion addition', r'\bnacl\b|\bkcl\b|\bcacl|\bmgcl|\bzncl|\bfeso|sodium chloride|calcium chloride|\bsalt|'
                            r'brin(?:e|ing)|ionic strength|\bions?\b|calcium|magnesium|zinc|\biron\b|metal|citrate|'
                            r'加盐|盐'),
    ('Heating', r'heat|therm|\bboil|cook|autoclav|pasteuri|steril|steam|bak(?:e|ing)|roast|blanch|\bfry|frying|'
                r'temper(?:ing|ed)|water bath|warm|retort|\buht\b|\bhtst\b|scald|toast|infrared|melt|gelatini[sz]|'
                r'加热|热处理|蒸煮|煮|烘烤|焙烤|巴氏|杀菌|灭菌|蒸|烤|炒'),
    ('High-shear mixing / homogenization', r'homogeni|turrax|high[- ]speed|high[- ]shear|shear|'
                                           r'colloid mill|blend|均质|剪切'),
    ('Milling / cutting / dehulling', r'mill|grind|comminut|pulveri|micron|siev|sift|crush|chop|minc|hull|decortic|'
                                      r'cut|slic|peel|thresh|clean|flak|crack|screen|depulp|粉碎|研磨|磨|过筛|绞|切'),
    ('Freezing / thawing', r'freez(?!e[- ]?dr)|frozen|thaw|冷冻(?!干燥)|冻融|解冻'),
    ('Drying', r'freeze[- ]?dr|lyophili[sz]|spray[- ]?dr|oven[- ]?dr|vacuum[- ]?dr|air[- ]?dr|drum[- ]?dr|'
               r'\bdry(?:ing)?\b|\bdried\b|dehydrat|evaporat|concentrat|冻干|干燥|喷雾|浓缩'),
    ('Extraction / isolation', r'extract|isolat|precipitat|isoelectric|defat|delipid|deoil|salting[- ]out|'
                               r'ammonium sulfate|fractionat|solubili[sz]|提取|沉淀|脱脂|分离'),
    ('Separation / purification', r'centrifug|filtrat|filter|ultrafiltr|diafiltr|microfiltr|dialy|'
                                  r'purif|desalt|washing|\bwash|rins|decant|skimm|membrane|adsorp|bentonite|charcoal|'
                                  r'decolo|depigment|clarif|fining|flotation|air[- ]classif|aspirat|press|dewater|'
                                  r'drain|phase separation|supernatant|elut|离心|过滤|透析|超滤|纯化|洗'),
    ('Peptide synthesis / expression', r'synthes|fmoc|recombinant|express|refold|transform|克隆|表达|合成'),
    ('Storage / aging', r'storage|\bstored|aging|ageing|\bage\b|ripen|incubat|standing|holding|equilibrat|'
                        r'refrigerat|chill|resting|\brest\b|maturation|储藏|贮藏|陈化|孵育|放置|静置'),
    ('Dissolution / mixing / pH adjustment', r'dissol|mix|stir|disper|hydrat|dilut|reconstitut|soak|\bph\b|'
                                             r'adjust|neutrali[sz]|acidif|alkali|buffer|suspen|vortex|shak|add|'
                                             r'fortif|condition|wett|swell|solution|溶解|混合|搅拌|分散|水合|稀释|浸泡|'
                                             r'调|加入|添加'),
    ('Cooling', r'cool|\bice\b|冷却'),
)
bd_TREAT_RES = tuple((name, re.compile(rx)) for name, rx in bd_TREAT_RULES)


def bd_treatment_types(method):
    """一步样品处理（原文写法）→ 处理类型，几类用 | 隔开；认不出来的写 Other。"""
    text = bd_norm_text(method)
    if not text:
        return ''
    found, used = [], []
    for name, rx in bd_TREAT_RES:
        for m in rx.finditer(text):
            a, b = m.span()
            if any(x < b and a < y for x, y in used):
                continue
            used.append((a, b))
            if name not in found:
                found.append(name)
    return ' | '.join(found) or 'Other'


# ---------------------------------------------------------------- 测试方法：英文名、可复现的方法概述 --
# 用户 2026-10-27：网站要能按测试方法筛选、显示「某项指标测定所使用的方法概述，可以让使用者依据方法复现实验」，英文。
# 概述由提取方法时已经存下的字段拼出来（原文叫法、出处、参数、仪器），不再调模型；不放原文句子。
bd_METHOD_EN = {
    'Bradford 法': 'Bradford assay', 'Lowry 法': 'Lowry assay', 'BCA 法': 'BCA assay', '双缩脲法': 'Biuret assay',
    '凯氏定氮法': 'Kjeldahl method', '杜马斯燃烧法': 'Dumas combustion', '紫外吸收法': 'UV absorbance',
    '重量法': 'Gravimetric method', '浊度法（EAI/ESI）': 'Turbidimetric method (EAI/ESI)', '离心法': 'Centrifugation method',
    '乳析指数法': 'Creaming index', '乳液粒径法': 'Emulsion droplet size', '搅打或均质法': 'Whipping / homogenization',
    '鼓气法': 'Gas sparging', '质构仪穿刺或压缩法': 'Texture analyser (puncture / compression)', '流变仪法': 'Rheometry',
    '最小凝胶浓度法': 'Least gelation concentration', '滤纸法': 'Filter-paper press method', '蒸煮损失法': 'Cooking loss',
    '低场核磁法': 'Low-field NMR', '动态光散射（DLS）': 'Dynamic light scattering (DLS)', '激光衍射': 'Laser diffraction',
    '纳米颗粒跟踪分析（NTA）': 'Nanoparticle tracking analysis (NTA)', '显微图像分析': 'Microscopy image analysis',
    '电泳光散射': 'Electrophoretic light scattering', 'Ellman 法（DTNB）': "Ellman's assay (DTNB)",
    'Ellman 法加还原剂': "Ellman's assay with reducing agent", '由总巯基推算': 'Calculated from total SH',
    '拉曼光谱法': 'Raman spectroscopy', 'ANS 荧光探针法': 'ANS fluorescence probe',
    'PRODAN 荧光探针法': 'PRODAN fluorescence probe', 'CPA 荧光探针法': 'CPA fluorescence probe',
    '溴酚蓝结合法': 'Bromophenol blue binding', '疏水作用色谱法': 'Hydrophobic interaction chromatography',
    '吸光度法': 'Absorbance', '浊度计法': 'Turbidimeter', 'OPA 法': 'OPA method', 'TNBS 法': 'TNBS method',
    'pH-stat 法': 'pH-stat method', '甲醛滴定法': 'Formol titration', 'TCA 可溶氮法': 'TCA-soluble nitrogen',
    '荧光胺法': 'Fluorescamine method', '茚三酮法': 'Ninhydrin method', '氨基酸分析仪法': 'Amino acid analyser',
    '直接法': 'Direct method', '间接法': 'Indirect method', 'DPPH 自由基清除法': 'DPPH radical scavenging',
    'ABTS 自由基清除法': 'ABTS radical scavenging', 'FRAP 法': 'FRAP assay', 'ORAC 法': 'ORAC assay',
    '还原力法': 'Reducing power', '羟基自由基清除法': 'Hydroxyl radical scavenging',
    '金属离子螯合法': 'Metal ion chelating', '脂质氧化抑制法': 'Lipid oxidation inhibition',
    '超氧阴离子自由基清除法': 'Superoxide radical scavenging', '过氧化氢清除法': 'H2O2 scavenging',
}
bd_OTHER_METHOD = 'Other method'


def bd_method_en(name):
    """测试方法的标准名称（中文）→ 英文；标准名称表以外的（「其他：…」）一律 Other method，原文叫法在 method_raw。"""
    return bd_METHOD_EN.get(name or '', bd_OTHER_METHOD if name else '')


def bd_clean_text(s):
    """一段字：空白合成一个，^{–1} → ^–1。"""
    return re.sub(r'\^\{([^{}]*)\}', r'^\1', ' '.join(str(s or '').split()))


def bd_method_summary(m):
    """一种测试方法 → 英文概述：原文叫法（出处）. 参数: 值 单位; …. Instrument: …
    出处只是编号（(13)、[13, 16]）时写成「ref. 13, 16 of the paper」，单看编号不知道是哪篇。"""
    name = bd_clean_text(m.get('method_raw')) or bd_method_en(m.get('method'))
    ref = bd_clean_text(m.get('reference'))
    if ref and re.fullmatch(r'[\d\s,;()\[\]–-]+', ref):
        ref = 'ref. %s of the paper' % ', '.join(re.findall(r'\d+(?:\s*[–-]\s*\d+)?', ref))
    text = name + (' (%s)' % ref if ref and ref not in name else '')
    parts = []
    for p in m.get('params') or []:
        n = bd_clean_text(p.get('name'))
        v = ' '.join(x for x in (bd_clean_text(p.get('value')), bd_clean_text(p.get('unit'))) if x)
        if n[:1].islower() and not n[1:2].isupper():
            n = n[:1].upper() + n[1:]                 # 首字母大写；pH、mM 这种不动
        if n or v:
            parts.append('%s: %s' % (n, v) if n and v else n or v)
    text = text.rstrip('. ') + '.'
    if parts:
        text += ' ' + '; '.join(parts) + '.'
    inst = bd_clean_text(m.get('instrument')).rstrip('. ')
    if inst:
        text += ' Instrument: %s.' % inst
    return text


def bd_sample_types(trows):
    """样品各步处理的类型合起来（按先后、去重）。"""
    seen = []
    for t in trows:
        for x in t['treatment_type'].split(' | '):
            if x and x not in seen:
                seen.append(x)
    return ' | '.join(seen)


# ================================================================ 一篇 → 各表的行 ==
class Problem(Exception):
    pass
bd_Problem = Problem                    # 合并时改的名；类名不改（schema 和回答存档的指纹带类名）


def bd_shown_text(p):
    """md 样品表里这个数显示成什么（不带 *）：作者表格的格子不是单个数时显示原始单元格（同 ed.entry_text）。"""
    return p['数值'] if p['数值'] != '' else (p['原始单元格'] if p['来源'] == '作者表格' else '')


def bd_measure_row(p):
    mul = p.get('倍率') or ''
    num = ed_num_text(p['数值'])
    value_std, unit_std = bd_value_std(p['指标代号'], p['数值'], p['单位']) if mul in bd_NO_MUL else ('', '')
    table = p['来源'] == '作者表格'
    row = {'property': p['指标代号'], 'property_cn': p['指标'],
           'measure_name': p['测量名称'] or p['系列'] or p['指标'],
           'value': num if num is not None else '', 'value_text': bd_shown_text(p), 'sd': p.get('SD') or '',
           'err_low': p.get('误差下限') or '', 'err_high': p.get('误差上限') or '', 'unit': p.get('单位') or '',
           'multiplier': '' if mul in bd_NO_MUL else mul, 'significance': p.get('显著性') or '',
           'value_std': value_std, 'unit_std': unit_std,
           'conditions_all': p['测定条件'], 'source_type': p['来源'],
           'model_estimated': '是' if p['来源'] in ('图反读', '图片表格反读') else '否',
           'source_item': p['图表'],
           'source_panel': (p['面板编号'].split('.', 1)[1] if table and '.' in p['面板编号'] else p['子图或指标'])
           if p['来源'] != '正文' else '',
           'series': p['系列'], 'x': p.get('X') or '', 'x_unit': p.get('X单位') or '',
           'x_variable': p.get('X含义') or '', 'source_text': ' '.join((p.get('原始单元格') or '').split()),
           'check_note': p.get('提醒') or ''}
    row.update(bd_cond_fields(p.get('_conds')))
    return row


def bd_method_fields(pair):
    """(方法, 状态) → 数值行里的方法列；这篇还没提取方法（pair 为 None）时四列都空。"""
    if pair is None:
        return {'method_id': '', 'test_method': '', 'test_method_en': '', 'method_params': '', 'method_status': ''}
    m, st = pair
    return {'method_id': m['method_id'] if m else '', 'test_method': m['method'] if m else '',
            'test_method_en': bd_method_en(m['method']) if m else '',
            'method_params': ed_method_params_text(m) if m else '', 'method_status': st}


bd_SD_JOURNAL = re.compile(r'^## \[([^\]]+)\]\(/journal/')
# Elsevier API 抓的全文（elsevier_api.py）开头是「## Food Chemistry」，下一行「## Published by: …」或「# 题目」，期刊名不是链接
# （11-11 用户 Elsevier 建完库，5657 篇期刊名是空的，都是这种；扫过这 5657 篇，按这条规则每篇都读得到）。只认 Elsevier 系 DOI。
bd_ELSEVIER_PREFIXES = ('10.1016_', '10.3168_', '10.1263_', '10.4315_', '10.1205_')


def bd_journal_from_fulltext(root, article):
    """DOI 前缀认不出期刊的（Elsevier 等；用户 2026-10-21：建库里 Elsevier 文章的期刊名原来是空的）：读这篇 全文.md 开头
    ScienceDirect 页面上的期刊名「## [Food Chemistry](/journal/food-chemistry …)」。10-21 扫过 D:\\elsevier_papers 27745 篇，
    每篇都读得到、同一个期刊只有一种写法（61 种）。读不到留空。"""
    try:
        with open(os.path.join(ed_papers_dir(root), article, '全文.md'), encoding='utf-8', errors='replace') as fh:
            first = ''
            heads = []                                  # 开头两个非空行（Elsevier API 的写法）
            for i, line in enumerate(fh):
                if i > 40:
                    break
                first = first or line.strip()
                if line.strip() and len(heads) < 2:
                    heads.append(line.strip())
                m = bd_SD_JOURNAL.match(line) or bd_TF_JOURNAL.match(line.strip())
                if m:
                    return m.group(1).strip()
    except OSError:
        return ''
    if (article.startswith(bd_ELSEVIER_PREFIXES) and len(heads) == 2 and heads[0].startswith('## ')
            and not heads[0].startswith('## [') and (heads[1].startswith('## Published by') or heads[1].startswith('# '))):
        return heads[0][3:].strip()
    return bd_journal_new(root, article, first)


# 用户 2026-10-30 八家通用：Wiley、RSC、OUP 的页面标题（figure_markdown.md 第一行）是「题目 - 作者 - 年 - 期刊 - Wiley Online
# Library」「题目 | 期刊 | The Royal Society of Chemistry / Oxford Academic」；MDPI 的 全文.md 第一行是期刊链接（文字是期刊名
# 写两遍：「FoodsFoods」）。10-30 扫过这四家全部 17432 篇，每篇都读得到
# 11-11 补 Springer、T&F（10-30 时没样本，建完库这两家期刊名全空）：Springer 页面标题「题目 | 期刊 | Springer Nature Link」，
# Nature 子刊（10.1038，npj Science of Food）是「题目 | 期刊」；T&F 全文开头一行以期刊链接打头「[Food Biotechnology](/journals/lfbt20) Volume…」。
# 11-11 扫过这两家全部 4990 篇（建进库的），每篇都读得到：Springer 26 种、T&F 12 种期刊
bd_PAGE_JOURNAL = re.compile(r'^# .+ (?:\||-) (?P<j>[^|]+?) (?:\||-) '
                             r'(?:The Royal Society of Chemistry|Oxford Academic|Wiley Online Library|Springer Nature Link)\s*$')
bd_NATURE_JOURNAL = re.compile(r'^# .+ \| (?P<j>[^|]+?)\s*$')
bd_TF_JOURNAL = re.compile(r'^\[([^\]]+)\]\(/journals/[a-z0-9]+\)(?:\s|$)')
bd_MDPI_JOURNAL = re.compile(r'^\[(?:!\[[^\]]*\]\([^)]*\))?(?P<t>[^\[\]]+)\]\(/journal/[\w-]+\)\s*$')


def bd_journal_new(root, article, first_line):
    """其他几家的期刊名（读不到留空）：先看页面标题，再看 MDPI 全文第一行的期刊链接。"""
    try:
        with open(os.path.join(ed_papers_dir(root), article, 'figure', 'figure_markdown.md'), encoding='utf-8',
                  errors='replace') as fh:
            title = fh.readline().rstrip('\n')
        m = bd_PAGE_JOURNAL.match(title) or (bd_NATURE_JOURNAL.match(title) if article.startswith('10.1038_') else None)
        if m:
            return m.group('j').strip()
    except OSError:
        pass
    m = bd_MDPI_JOURNAL.match(first_line)
    if m:
        t = m.group('t').strip()
        h = len(t) // 2
        return t[:h] if len(t) % 2 == 0 and t[:h] == t[h:] else t
    return ''


def bd_paper_rows(article, root):
    """一篇 → ({表名: [行]}, 核对用的东西)。底稿缺了或和磁盘上的 md 对不上 → Problem。"""
    src_path = ed_merged_path(root, article)
    if not os.path.exists(src_path):
        raise bd_Problem('合并稿不在了：%s' % src_path)
    d = ed_parse_doc(src_path)
    cdir = os.path.join(ed_records_dir(root), ed_CACHE_DIR, ed_model_slug(ed_MODEL))
    c = ed_load_cache(cdir, d, ed_MODEL)
    if c is None:
        raise bd_Problem('没有有效的模型回答（缓存不在，或合并稿 / 提示词变了、指纹对不上）')
    pts, exc, srows, st = ed_build_paper(d, c['output'])
    disk = ed_read(os.path.join(ed_papers_dir(root), article, ed_DATAPOINT_NAME))
    if ed_render_md(d, c, pts, exc, st) != disk:
        raise bd_Problem('按底稿重新生成的 md 和磁盘上的 datapoint.md 不一样（datapoint 生成后底稿或程序变过）')

    doi = d['doi'] or article
    journal = next((j for pre, j in bd_JOURNALS if doi.startswith(pre)), '') or bd_journal_from_fulltext(root, article)
    samples = collections.OrderedDict((s['sample_id'], s) for s in c['output']['samples'])
    ok = [p for p in pts if p['对应状态'] == '已对应' and p['样品编号'] in samples]       # 同 ed.render_md
    shown = [sid for sid in samples if any(p['样品编号'] == sid for p in ok)]
    hidden = [p for p in ok if p['指标代号'] not in FUNCTIONAL]                         # md 表里没有这一行，不该有
    out = {name: [] for name, _ in bd_TABLES}
    # 测定方法（extract_method.py 提取过的文章才有）：和 datapoint.md 用同一个挂法（ed.point_methods）
    pm, asg = ed_point_methods(article, ok) if ok else (None, None)       # 同 ed.render_md：没有数值的文章不收方法
    pmeth = {}
    if pm is not None:
        mm = {m['method_id']: m for m in pm['methods']}
        pmeth = {id(p): (mm.get(mid), st) for p, (mid, st) in zip(ok, asg)}
        n_by = collections.Counter(mid for mid, _ in asg)
        out['methods'] = [{'doi': doi, 'method_id': m['method_id'], 'property': m['property'],
                           'property_cn': FUNCTIONAL.get(m['property'], ''), 'test_method': m['method'],
                           'test_method_en': bd_method_en(m['method']),
                           'method_raw': m.get('method_raw') or '', 'reference': m.get('reference') or '',
                           'instrument': m.get('instrument') or '', 'method_params': ed_method_params_text(m),
                           'method_summary': bd_method_summary(m),
                           'applies_to': ' | '.join(m.get('applies_to') or []), 'n_measurements': n_by.get(m['method_id'], 0),
                           'evidence_check': '%d / %d 条找到' % (sum(m.get('evidence_found') or []),
                                                               len(m.get('evidence') or []))}
                          for m in pm['methods']]
    for k, sid in enumerate(shown, 1):
        s = samples[sid]
        sample_id = '%s#%d' % (doi, k)
        info = ed_sample_info(s)
        steps = s.get('processing') or []
        srow = {'sample_id': sample_id, 'doi': doi, 'sample_no': k, 'sample_name': info['样品名称'],
                'description': info['样品说明'], 'protein_source': info['蛋白来源'],
                'protein_category': info['蛋白类别'], 'protein_form': info['蛋白形态'],
                'protein_source_std': bd_source_std(info['蛋白来源'], info['蛋白形态']),
                'protein_form_std': bd_form_std(info['蛋白形态']), 'protein_conc': info['蛋白浓度'],
                'ingredients_summary': info['复配物'], 'treatment_summary': info['样品处理方法'],
                'treatment_categories': info['样品处理类别'], 'treat_temperature': info['样品处理温度'],
                'treat_time': info['样品处理时间'], 'treat_ph': info['样品处理pH'], 'system': info['体系'],
                'evidence': ' ‖ '.join(' '.join(q.split()) for q in s.get('evidence') or [])}
        out['samples'].append(srow)
        out['ingredients'] += [{'sample_id': sample_id, 'doi': doi, 'ingredient_no': j, 'name': x.get('name', ''),
                                'category': x.get('category', ''), 'amount': x.get('amount') or ''}
                               for j, x in enumerate(s.get('ingredients') or [], 1)]
        trows = [bd_treatment_row(sample_id, doi, j, stp) for j, stp in enumerate(steps, 1)]
        srow['treatment_types'] = bd_sample_types(trows)
        out['treatments'] += trows
        out['treatment_params'] += [{'sample_id': sample_id, 'doi': doi, 'step_no': j, 'param_no': i,
                                     'name': p.get('name', ''), 'value': p.get('value', ''), 'unit': p.get('unit') or ''}
                                    for j, stp in enumerate(steps, 1) for i, p in enumerate(stp.get('params') or [], 1)]
        agg = {col: ' | '.join(v for v in (t[key] for t in trows) if v) for col, key in (
            ('treat_temperature_c', 'temperature_c'), ('treat_time_min', 'time_min'), ('treat_ph', 'ph'),
            ('treat_pressure_mpa', 'pressure_mpa'), ('treat_power_w', 'power_w'),
            ('treat_frequency_khz', 'frequency_khz'), ('treat_enzyme', 'enzyme'))}
        # 顺序同 md 样品表：17 项按 FUNCTIONAL 的顺序，同一格里按 作者表格 → 正文 → 读图
        mine = []
        for code in FUNCTIONAL:
            mine += sorted((p for p in ok if p['样品编号'] == sid and p['指标代号'] == code),
                           key=lambda p: ed_SRC_RANK.get(p['来源'], 9))
        for j, p in enumerate(mine, 1):
            mid = '%s-%d' % (sample_id, j)
            m = bd_measure_row(p)
            m.update({'measurement_id': mid, 'sample_id': sample_id, 'doi': doi, 'sample_no': k})
            m.update(bd_method_fields(pmeth.get(id(p))))
            out['measurements'].append(m)
            out['measurement_conditions'] += [{'measurement_id': mid, 'sample_id': sample_id, 'doi': doi, 'cond_no': i,
                                               'name': q.get('name', ''), 'value': q.get('value', ''),
                                               'unit': q.get('unit') or ''}
                                              for i, q in enumerate(p.get('_conds') or [], 1)]
            f = dict(m)
            f.update({kk: srow[kk] for kk in bd_FLAT_SAMPLE_KEYS})
            f.update(agg)
            f.update({'title': d['title'], 'journal': journal})
            out['flat_measurements'].append(f)
        srow['n_measurements'] = len(mine)
    if out['measurements']:
        n_src = collections.Counter(m['source_type'] for m in out['measurements'])
        out['papers'] = [{'doi': doi, 'article': article, 'title': d['title'], 'journal': journal,
                          'n_samples': len(out['samples']), 'n_measurements': len(out['measurements']),
                          'n_from_table': n_src['作者表格'], 'n_from_text': n_src['正文'],
                          'n_from_figure': n_src['图反读'] + n_src['图片表格反读'],
                          'extracted_by': c.get('model') or '', 'extracted_at': c.get('at') or ''}]
    return out, {'disk': disk, 'hidden': hidden, 'journal': journal}


# ================================================================ 核对：库里的列拼回 md 样品表 ==
bd_CELL_SPLIT = re.compile(r'(?<!\\)\|')


def bd_md_cells(line):
    return [x.strip().replace('\\|', '|') for x in bd_CELL_SPLIT.split(line.strip())[1:-1]]


def bd_parse_sample_table(md):
    """md 里「## 样品数据」那张表 → ({行名: [各列格子]}, 共同前处理, 共同后处理)。"""
    lines = md.split('\n')
    i = lines.index('## 样品数据')
    pre = post = ''
    rows = collections.OrderedDict()
    for line in lines[i + 1:]:
        if line.startswith('## '):
            break
        if line.startswith('- 所有样品共同的样品前处理：'):
            pre = line.split('：', 1)[1]
        elif line.startswith('- 所有样品共同的样品后处理：'):
            post = line.split('：', 1)[1]
        elif line.startswith('|') and not line.startswith('|---'):
            cells = bd_md_cells(line)
            rows[cells[0]] = cells[1:]
    return rows, pre, post


def bd_entry_from_row(m):
    """库里一行 → md 格子里那个数的写法（同 ed.entry_text，但只用库里的列）。"""
    text = '%s = %s%s' % (m['measure_name'], m['value_text'], '*' if m['model_estimated'] == '是' else '')
    if m['sd']:
        text += ' ± %s' % m['sd']
    if m['unit']:
        text += ' %s' % m['unit']
    if m['multiplier']:
        text += '（轴倍率 %s）' % m['multiplier']
    if m['err_low'] or m['err_high']:
        text += '（误差棒 %s–%s）' % (m['err_low'] or '?', m['err_high'] or '?')
    if m['significance']:
        text += ' %s' % m['significance']
    if m['conditions_all']:
        text += '｜' + m['conditions_all']
    if m['method_status']:                    # 同 ed.method_tag
        text += '｜测试方法 ' + ('%s %s' % (m['method_id'], m['test_method']) if m['method_id'] else
                           '原文未写明' if m['method_status'] == ed_NO_METHOD else '不确定')
    return ' '.join(text.split())


bd_SAMPLE_ROW_COL = (('样品名称', 'sample_name'), ('样品说明', 'description'), ('蛋白来源', 'protein_source'),
                  ('蛋白类别', 'protein_category'), ('蛋白形态', 'protein_form'), ('蛋白浓度', 'protein_conc'),
                  ('复配物', 'ingredients_summary'), ('样品处理类别', 'treatment_categories'),
                  ('样品处理温度', 'treat_temperature'), ('样品处理时间', 'treat_time'), ('样品处理pH', 'treat_ph'),
                  ('体系', 'system'))


def bd_check_against_md(article, out, md):
    """返回对不上的地方（空列表 = 全对上）。"""
    bad = []
    rows, pre, post = bd_parse_sample_table(md)
    n = len(out['samples'])
    head = rows.get('项目', [])
    if head != ['样品%d' % k for k in range(1, n + 1)]:
        return ['%s：样品列数对不上（md %d 列，库 %d 个样品）' % (article, len(head), n)]
    for s in out['samples']:
        k = s['sample_no'] - 1
        for label, col in bd_SAMPLE_ROW_COL:
            if rows[label][k] != ' '.join(str(s[col]).split()):
                bad.append('%s 样品%d %s：md「%s」库「%s」' % (article, k + 1, label, rows[label][k], s[col]))
        own = rows['样品处理方法'][k]
        # 两边一样合并空白：原文里的窄不换行空格（U+202F，「2 cm × 2 cm」）在共同处理那行没合并，11-11 Elsevier 一篇因此误报
        chain = ' '.join(' → '.join(x for x in (pre, '' if own == '（仅共同处理）' else own, post) if x).split())
        if chain != ' '.join(s['treatment_summary'].split()):
            bad.append('%s 样品%d 处理方法：md「%s」库「%s」' % (article, k + 1, chain, s['treatment_summary']))
        for code, cn in FUNCTIONAL.items():
            want = [x.strip() for x in rows[cn][k].split(ed_ENTRY_SEP)] if rows[cn][k] else []
            got = [bd_entry_from_row(m) for m in out['measurements']
                   if m['sample_id'] == s['sample_id'] and m['property'] == code]
            if want != got:
                bad.append('%s 样品%d %s：md %d 个数、库 %d 个数，写法不一致' % (article, k + 1, cn, len(want), len(got)))
    return bad


# ================================================================ 写文件 ==
# 离心力：全文里斜体 g 是 Markdown「10,000_g_」，模型抄参数时丢了后一个下划线，成了「10,000_g」「3000 _g」（用户 2026-11-02「改吧」）。
# 写库时改成「10,000 g」（库里多数就是「数字 g」的写法）；只认紧跟在数字后面的 _g，D_h、R_g、n_id_i 这类下标写法不动。
bd_ITALIC_G = re.compile(r'(?<=\d)\s*_g_?(?![A-Za-z0-9_])')


def bd_fix_g(v):
    if not isinstance(v, str) or '_g' not in v:
        return v
    if v.strip() in ('_g', '_g_'):                  # 单位一栏只写了「_g」
        return 'g'
    return bd_ITALIC_G.sub(' g', v)


def bd_write_csv(path, cols, rows):
    """UTF-8 带 BOM（Excel 直接打开不乱码）、LF 换行；先写临时文件再换上，写一半中断不会留下坏文件。"""
    fd, tmp = tempfile.mkstemp(prefix='.x-', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction='raise', lineterminator='\n')
            w.writeheader()
            for r in rows:
                missing = [k for k in cols if k not in r]
                if missing:                           # 列名写错会悄悄变成空列，宁可停下
                    raise KeyError('%s 缺列：%s' % (os.path.basename(path), ', '.join(missing)))
                w.writerow({k: bd_fix_g('' if r[k] is None else r[k]) for k in cols})
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


bd_README = """# 蛋白质功能特性数据库

由 `Desktop\\build_database\\build_database.py` 生成，数据来自 `papers\\<文章名>\\datapoint.md`（每篇一个）
（读的是生成它的底稿：模型回答 + 全文合并稿，不调模型）。**库里只有 datapoint.md「样品数据」表里的数**：
每个数恰好对应一个样品，样品都含蛋白质，只收 17 项性质（{props}）。

所有表都是 UTF-8 CSV（带 BOM，Excel 直接打开），**一行一个对象、每格一个值**，表之间用编号相连：

```
papers (doi)
 └─ samples (sample_id = doi#样品序号)
     ├─ ingredients          复配物，一行一个
     ├─ treatments           样品处理步骤，一行一步（按先后顺序）
     │   └─ treatment_params 每一步样品处理的全部参数，一行一个（名称、数值、单位照抄原文）
     └─ measurements         数值，一行一个（measurement_id = sample_id-序号）
         └─ measurement_conditions  每个数值的全部测定条件，一行一个
methods (doi + method_id)    每篇 17 项性质的测试方法（不是样品处理），一行一种（measurements 的 method_id 指向这里）
flat_measurements = measurements + 所属文章、样品、处理的信息平铺在同一行（做分析、建模直接用这张）
```

**测试方法**（2026-10-19 加，extract_method.py 从方法部分提取 17 项性质是怎么测的）：每个数值的 `method_id`、`test_method`、`method_params`、
`method_status` 和 datapoint.md 里「｜测试方法 M1 …」一致（test_method = 17 项性质的测试方法；样品处理方法在 treatments.treatment_method，两者不要混）；还没提取方法的文章这四列为空。

**编号和 datapoint.md 的对应**：`sample_id` 的 `#3` 就是那篇 datapoint.md 样品表里的「样品3」；`measurement_id` 的 `-5`
是这个样品的第 5 个数（顺序同 md 格子：17 项按表里的行序，同一格里 作者表格 → 正文 → 读图）。

## 约定
- **`model_estimated = 是`：数值是读图得到的（数据来源于模型推断）**，就是 datapoint.md 里数值后面带 `*` 的；
  `否` 是作者表格或正文里的原值
- 原值一律照抄原文（`value_text`、`unit`、`*_raw`、`treatment_params`、`measurement_conditions`）；另给纯数字和标准单位的列
  （`value`、`value_std`、`*_c`、`*_min`、`*_mpa`、`*_w`、`*_khz`），换不了的留空
- `value_std` / `unit_std` 按性质换成标准单位（{units}）；单位写法认不出、或基准不同（per g flour）的不换
- 规范化的列（2026-10-27 加，程序按规则从原文列推出来，不调模型）：`protein_source_std`（蛋白来源标准名称）、`protein_form_std`
  （形态类别）、`treatment_types` / `treatments.treatment_type`（处理类型）、`test_method_en`（测试方法英文名）、
  `methods.method_summary`（英文方法概述，可照着复现）
- `value` 是纯数字；作者表格的格子不是单个数（如「<0.1」「3.6–6.8」）时 `value` 留空，原样在 `value_text`
- 读图的数有纵轴倍率（`multiplier`，如 ×10^3）时，`value` 是刻度上的读数，没乘倍率
- 同一样品、同一指标、同一组测定条件只有一个数；同一个数在作者表格、正文、图里都出现时各留一行，用 `source_type` 区分
- 几个同类参数（如两步都有温度）在汇总列里用 ` | ` 隔开，这时标准单位列留空，详见 `treatments` / `treatment_params`

## 各表的列
{tables}
"""

bd_COL_DOC = {
    'doi': 'DOI', 'article': '文章名（DOI 里的 / 换成 _，papers 下这篇文章的文件夹名）', 'title': '论文题目',
    'journal': '期刊（ACS 按 DOI 前缀判断；Elsevier 取 ScienceDirect 页面上的期刊名）', 'n_samples': '样品数', 'n_measurements': '数值个数',
    'n_from_table': '其中来自作者表格', 'n_from_text': '其中来自正文', 'n_from_figure': '其中来自读图（模型推断）',
    'extracted_by': '解读样品和条件的模型', 'extracted_at': '模型解读的时间',
    'sample_id': '样品编号（doi#样品序号）', 'sample_no': '样品序号（= datapoint.md 里的「样品N」）',
    'sample_name': '文中用到的名称或缩写，/ 隔开', 'description': '一句话说明（原文措辞）',
    'protein_source': '蛋白来源', 'protein_category': '蛋白类别：植物蛋白 / 乳蛋白 / 蛋类蛋白 / 肉类或水产蛋白 / '
                                                       '其他动物蛋白 / 微生物蛋白 / 藻类蛋白 / 昆虫蛋白 / 多种来源 / 不明',
    'protein_form': '形态或组分（isolate、concentrate、hydrolysate、7S…）', 'protein_conc': '蛋白浓度或用量（原文写法）',
    'ingredients_summary': '复配物：名称（类别，用量）; …（详见 ingredients）',
    'treatment_summary': '完整样品处理：方法（参数, …）→ 下一步（详见 treatments）；没处理写「未处理」',
    'treatment_categories': '样品处理类别：物理法 / 化学法 / 生物法 / 复合法 / 其他，几类用 、 隔开',
    'treat_temperature': '样品处理温度（原文；几步都有时「方法: 值」用 | 隔开）', 'treat_time': '样品处理时间（同上）',
    'treat_ph': '样品处理 pH（同上）',
    'system': '测定时的体系：溶液或分散液 / 乳液 / 泡沫 / 凝胶 / 颗粒或纳米颗粒 / 复合物 / 膜 / 粉末或固体 / 其他 / 不明',
    'evidence': '组成和处理的原文依据（逐字摘录，‖ 隔开）',
    'ingredient_no': '序号', 'name': '名称（原文写法）', 'amount': '用量（原文写法）',
    'category': '类别（复配物：多糖 / 多酚 / 油脂 / 其他蛋白 / 肽 / 糖 / 盐或离子 / 表面活性剂或乳化剂 / 交联剂 / 活性物质 / 其他；'
                '样品处理：物理法 / 化学法 / 生物法 / 复合法 / 其他）',
    'step_no': '第几步', 'treatment_method': '样品处理方法（原文写法）', 'params': '这一步的全部参数（名称=数值 单位; …）',
    'temperature_raw': '温度（原文）', 'temperature_c': '温度（°C）', 'time_raw': '时间（原文）', 'time_min': '时间（min）',
    'ph': 'pH', 'pressure_raw': '压力（原文）', 'pressure_mpa': '压力（MPa）', 'power_raw': '功率（原文）',
    'power_w': '功率（W）', 'frequency_raw': '频率（原文）', 'frequency_khz': '频率（kHz）', 'enzyme': '酶',
    'enzyme_dosage': '加酶量（原文）', 'reagent': '试剂', 'reagent_conc': '试剂用量（原文）',
    'other_params': '其他参数（名称=数值 单位; …）', 'param_no': '序号', 'value': '数值（照抄原文）', 'unit': '单位（照抄原文）',
    'treat_temperature_c': '各步处理温度（°C），| 隔开', 'treat_time_min': '各步处理时间（min），| 隔开',
    'treat_pressure_mpa': '各步压力（MPa），| 隔开', 'treat_power_w': '各步功率（W），| 隔开',
    'treat_frequency_khz': '各步频率（kHz），| 隔开', 'treat_enzyme': '各步用的酶，| 隔开',
    'measurement_id': '数值编号（sample_id-序号）', 'property': '17 项代号', 'property_cn': '17 项中文名',
    'measure_name': '测量名称（原文说法，如 EAI、Solubility in 0.2% KOH）',
    'value_text': 'datapoint.md 里显示的数值（不带 *；作者表格的格子不是单个数时是原始写法）', 'sd': '标准差',
    'err_low': '误差棒下端（读图）', 'err_high': '误差棒上端（读图）',
    'multiplier': '纵轴倍率（读图，如 ×10^3；value 是刻度读数，没乘倍率）', 'significance': '显著性字母',
    'value_std': '标准单位的数值（按性质换：粒径 nm、ζ-电位 mV、溶解度 % 或 mg/mL、乳化性 m²/g、min 或 %、凝胶性 Pa 或 N、'
                 '持水持油 g/g、mL/g 或 %、巯基二硫键 µmol/g…，见 README；有纵轴倍率的不换，换不了留空）',
    'unit_std': '标准单位',
    'cond_ph': '测定 pH', 'cond_temperature_raw': '测定温度（原文）', 'cond_temperature_c': '测定温度（°C）',
    'cond_time_raw': '测定或储藏时间（名称=数值 单位）', 'cond_time_min': '测定或储藏时间（min）',
    'cond_ionic_strength': '离子强度、盐浓度（名称=数值 单位）', 'cond_concentration': '浓度类条件（名称=数值 单位）',
    'cond_other': '其他测定条件（名称=数值 单位）', 'conditions_all': '全部测定条件（名称=数值 单位; …），同 datapoint.md',
    'cond_no': '序号', 'source_type': '来源：作者表格 / 正文 / 图反读 / 图片表格反读',
    'model_estimated': '是 = 读图得到（数据来源于模型推断，md 里带 *）；否 = 作者原值',
    'source_item': '来源：Figure 3 / Table 2 / 正文', 'source_panel': '子图（A、b…），或作者表格的格子（T2.r3.c4 → r3.c4）',
    'series': '图的系列名，或作者表格里样品那一行（列）的表头', 'x': '图的 X 取值', 'x_unit': 'X 单位',
    'x_variable': 'X 的含义（pH、storage time…；X 是样品名时写「样品」）',
    'source_text': '作者表格的原始单元格，或正文数值的原句',
    'check_note': '程序核对时的提醒（例如读图结果里同一系列同一 X 有几个读数、同一根柱子读了几遍取了哪个）；空 = 没有',
    'method_id': '测定方法编号（M1、M2…，指向 methods 表里同一 doi 的那一行）；方法不确定或原文未写明时为空',
    'method_status': '方法对应状态：已对应 / 原文未写明方法 / 方法不确定（这一项用了几种方法、分不清这个数用的哪种）；'
                     '空 = 这篇还没提取方法',
    'method_params': '测定方法的关键参数（名称=数值 单位; …，如离心力、测定时蛋白浓度、波长、探针）',
    'method_raw': '原文对这个方法的叫法', 'reference': '原文写的方法出处（文献或标准号）', 'instrument': '仪器和型号',
    'applies_to': '这个方法对应的图表（| 隔开）',
}
bd_COL_DOC['test_method'] = '测试方法（标准名称，如 Bradford 法、动态光散射（DLS）、ANS 荧光探针法）'
bd_COL_DOC.update({                     # 用户 2026-10-27 加：规范化的列（程序按规则从原文列推出来，原文列照留）
    'protein_source_std': '蛋白来源的标准名称（英文，如 Soybean、Milk (bovine)、Egg (hen)；从 protein_source 和 protein_form 认，'
                          '几种来源 | 隔开；认不出来的留空）',
    'protein_form_std': '蛋白形态的标准类别（英文：Isolate、Concentrate、Hydrolysate、Peptide、Protein fraction…；'
                        '认不出写 Other，原文没写留空）',
    'treatment_types': '样品各步处理的类型合起来（英文，按先后、| 隔开；详见 treatments.treatment_type）',
    'treatment_type': '这一步样品处理的类型（英文：Heating、Ultrasound、Enzymatic hydrolysis、Glycation (Maillard)…；'
                      '几类 | 隔开；认不出写 Other）',
    'test_method_en': '测试方法的英文标准名称（标准名称表以外的写 Other method，原文叫法见 methods.method_raw）',
    'method_summary': '方法概述（英文，由原文叫法、出处、关键参数、仪器拼成，供复现实验；不含原文句子）',
})


def bd_readme_text():
    parts = []
    for name, cols in bd_TABLES:
        if name == 'flat_measurements':
            parts.append('### flat_measurements\nmeasurements 的全部列，加上 title、journal、样品的列（同 samples）、'
                         '各步处理的标准单位值（treat_*_c / _min / _mpa / _w / _khz、treat_ph、treat_enzyme，几步用 | 隔开）。')
            continue
        parts.append('### %s\n' % name + '\n'.join('- `%s`：%s' % (c, bd_COL_DOC.get(c, '')) for c in cols))
    units = '；'.join('%s %s' % (FUNCTIONAL[p], ' / '.join(f)) for p, f in bd_PROP_UNITS.items())
    return bd_README.format(props='、'.join(FUNCTIONAL.values()), tables='\n\n'.join(parts), units=units)


# ================================================================ 主程序 ==
# 用户 2026-10-21：「以 acs 已经有的库为基础，爱斯维尔的新数据点出来之后往数据库里更新，因为他们格式都是统一的」——
# ACS + Elsevier 合成一个库，放 D:\protein_database（D:\1.acs_papers_done\database 原样留着，当 ACS 的存档）。
# 每次只重算新的、输入变了的文章（datapoint.md、method.json、全文合并.md、数据点回答存档的大小和修改时间，记在库里的
# _建库清单.json），其余文章沿用上次库里核对过的行；数据点或建库这两部分代码改了就整库重算。行的顺序和整库重算一样（按文章名），
# 所以增量更新出来的库和整库重算的逐字节相同。编号都带 DOI，ACS 和 Elsevier 不会撞。
bd_DB_DIR = r'D:\protein_database'
# 用户 2026-10-27 把 ACS 总文件夹改名为 1.acs_papers_done；10-30 Elsevier 改名为 2.elsevier_papers，另外六家也进这个库
bd_DB_ROOTS = (ACS_ROOT,) + PAPER_ROOTS
bd_MANIFEST = '_建库清单.json'
bd_PAPER_FILES = (ed_DATAPOINT_NAME, ed_METHOD_NAME, ed_MERGED_NAME, '全文.md')     # 全文.md：期刊名从它读（Elsevier）


def bd_code_sig():
    """数据点、建库这两部分代码的指纹：改了就整库重算（行的写法可能跟着变了）。"""
    text = open(os.path.abspath(__file__), encoding='utf-8').read()
    a = text.index('# 数据点提取（原 extract_datapoint')
    b = text.index('# 测定方法提取（原')
    c = text.index('# 建库（原 build_database')
    d = text.rindex('# 命令行：一条命令跑全流程')
    return hashlib.sha256((text[a:b] + text[c:d]).encode('utf-8')).hexdigest()[:16]


def bd_paper_sig(root, article):
    """这篇的输入变没变：datapoint.md、method.json、全文合并.md、数据点回答存档的 [大小, 修改时间]（没有的写 null）。
    datapoint.md、method.json 内容没变就不重写（ed_write_if_changed），所以修改时间变了就是真变了。"""
    pdir = os.path.join(ed_papers_dir(root), article)
    files = [os.path.join(pdir, f) for f in bd_PAPER_FILES] + \
        [os.path.join(ed_records_dir(root), ed_CACHE_DIR, ed_model_slug(ed_MODEL), article + '.json')]
    out = []
    for f in files:
        try:
            st = os.stat(f)
            out.append([st.st_size, st.st_mtime_ns])
        except OSError:
            out.append(None)
    return out


def bd_csv_row(r):
    """写进 CSV 的样子（None → 空，数字 → 文字，和 csv 写出来的一样）：沿用的行是从 CSV 读回来的，两种拼在一起要一致。"""
    return {k: ('' if v is None else v if isinstance(v, str) else str(v)) for k, v in r.items()}


def bd_norm(p):
    return os.path.normcase(os.path.abspath(p))


def bd_main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    ap = argparse.ArgumentParser(description='每篇 datapoint.md 的数据 → 数据库（几张 CSV + 平铺总表）；默认 1–8 号总文件夹合成一个库 %s，'
                                             '只重算新的、输入变了的文章' % bd_DB_DIR)
    ap.add_argument('papers', nargs='*', help='只建这几篇（测试用，配 --out；整库重算、不记清单）')
    ap.add_argument('--root', action='append', default=None,
                    help='总文件夹，可以给几个；不给就是 %s，库写到 %s' % (' + '.join(bd_DB_ROOTS), bd_DB_DIR))
    ap.add_argument('--out', default=None, help='数据库目录；默认：没给 --root 时 %s，给了 --root 时 <第一个 root>\\%s'
                                                % (bd_DB_DIR, bd_DB_SUBDIR))
    ap.add_argument('--full', action='store_true', help='整库重算（默认只重算新的、输入变了的文章，其余沿用上次库里的行）')
    args = ap.parse_args(argv)
    roots = args.root or list(bd_DB_ROOTS)
    for r in roots:
        if not os.path.isdir(r):
            raise SystemExit('找不到总文件夹：%s' % r)
    args.out = args.out or (bd_DB_DIR if not args.root else os.path.join(roots[0], bd_DB_SUBDIR))
    if any(bd_norm(args.out) == bd_norm(ed_papers_dir(r)) for r in roots):
        raise SystemExit('--out 不能和文章文件夹相同（输入只读）')
    args.roots = roots
    global ed_PAPERS, ed_METHOD_DIR
    ed_METHOD_DIR = None                             # 测定方法读每篇文件夹里的 method.json
    t0 = time.time()
    # 文章：各总文件夹里有 datapoint.md 的；同名的只认排在前面的总文件夹
    where, dup = {}, []
    for r in roots:
        pdir = ed_papers_dir(r)
        for n in sorted(os.listdir(pdir)):
            if os.path.isfile(os.path.join(pdir, n, ed_DATAPOINT_NAME)):
                if n in where:
                    dup.append(n)
                else:
                    where[n] = r
    if dup:
        print('有 %d 篇在几个总文件夹里都有，只用前面那个：%s' % (len(dup), '、'.join(dup[:5])))
    if args.papers:
        missing = [n for n in args.papers if n not in where]
        if missing:
            raise SystemExit('这些文章没有 datapoint.md：%s' % '、'.join(missing[:10]))
        names = list(args.papers)
    else:
        names = sorted(where)
    sigs = {n: bd_paper_sig(where[n], n) for n in names}
    code = bd_code_sig()
    mpath = os.path.join(args.out, bd_MANIFEST)
    old, why_full = None, '--full' if args.full else '只建指定的几篇' if args.papers else '库里还没有清单（第一次建）'
    if not args.papers and not args.full and os.path.exists(mpath):
        try:
            old = json.loads(ed_read(mpath))
        except ValueError:
            old = None
            why_full = '清单读不出来'
        if old is not None:
            if old.get('code') != code:
                old, why_full = None, '数据点或建库的代码改了'
            elif old.get('roots') != [bd_norm(r) for r in roots]:
                old, why_full = None, '总文件夹和上次不一样'
            elif any(not os.path.exists(os.path.join(args.out, t + '.csv')) for t, _ in bd_TABLES):
                old, why_full = None, '库里缺 CSV'
    if old is not None:
        prev = old['papers']
        todo = [n for n in names if (prev.get(n) or {}).get('sig') != sigs[n] or (prev.get(n) or {}).get('root') != where[n]]
        removed = [n for n in prev if n not in where]
        if not todo and not removed:
            print('数据库 %s 已是最新：%d 篇 datapoint 的输入都没变，不用更新（%.0f 秒）' % (args.out, len(names), time.time() - t0))
            return 0
        mode = '增量更新：重算新的、变了的 %d 篇，去掉 %d 篇，其余 %d 篇沿用上次库里核对过的行' % (
            len(todo), len(removed), len(names) - len(todo))
    else:
        todo, removed, prev = names, [], {}
        mode = '整库重算（%s）：%d 篇' % (why_full, len(names))
    print(mode, flush=True)

    # 沿用的行：上次库里、这次没变的文章（各表按 doi 认是哪篇）
    keep = {}
    if old is not None:
        art_of = {v['doi']: n for n, v in prev.items() if v.get('doi')}
        redo = set(todo) | set(removed)
        for name, _ in bd_TABLES:
            with open(os.path.join(args.out, name + '.csv'), encoding='utf-8-sig', newline='') as fh:
                for r in csv.DictReader(fh):
                    a = art_of.get(r['doi'])
                    if a is None:
                        raise SystemExit('库里 %s.csv 有清单里没有的文章（doi %s），清单和库对不上；用 --full 整库重算' % (name, r['doi']))
                    if a not in redo:
                        keep.setdefault(a, {}).setdefault(name, []).append(r)

    # 重算
    fresh, info = {}, {}
    problems, mismatches, hidden, bad_names = [], [], [], set()
    for i, article in enumerate(todo, 1):
        ed_PAPERS = ed_papers_dir(where[article])
        try:
            out, aux = bd_paper_rows(article, where[article])
        except bd_Problem as e:
            problems.append('%s：%s' % (article, e))
            bad_names.add(article)
            continue
        mismatches += bd_check_against_md(article, out, aux['disk'])
        hidden += ['%s %s %s' % (article, p['指标代号'], p['测量名称']) for p in aux['hidden']]
        fresh[article] = {k: [bd_csv_row(r) for r in rows] for k, rows in out.items()}
        info[article] = next((rows[0]['doi'] for rows in out.values() if rows), None)
        if i % 500 == 0:
            print('  %d / %d 篇（%.0f 秒）' % (i, len(todo), time.time() - t0), flush=True)
    if problems and not args.papers:
        print('有 %d 篇底稿对不上，先不写库（库和清单都不动）：' % len(problems))
        for p in problems[:30]:
            print('  ' + p)
        return 1

    # 拼库：按文章名的顺序（同整库重算），新算的用新的，没变的用上次的
    db = {name: [] for name, _ in bd_TABLES}
    for a in names:
        src = fresh[a] if a in fresh else keep.get(a, {})
        for name, _ in bd_TABLES:
            db[name] += src.get(name, [])
    empty = sum(1 for a in names if a not in bad_names and not (fresh.get(a) or keep.get(a) or {}).get('measurements'))

    # 库内核对：编号不重复、挂得上（每次都对全库做）
    checks = []
    for name, key in (('papers', 'doi'), ('samples', 'sample_id'), ('measurements', 'measurement_id')):
        dupk = [k for k, v in collections.Counter(r[key] for r in db[name]).items() if v > 1]
        checks.append(('%s.%s 不重复' % (name, key), not dupk, '重复 %d 个' % len(dupk) if dupk else ''))
    sids, dois = {r['sample_id'] for r in db['samples']}, {r['doi'] for r in db['papers']}
    for name in ('ingredients', 'treatments', 'treatment_params', 'measurements', 'measurement_conditions',
                 'flat_measurements'):
        orphan = sum(1 for r in db[name] if r['sample_id'] not in sids)
        checks.append(('%s 的样品都在 samples 里' % name, not orphan, '挂不上 %d 行' % orphan if orphan else ''))
    orphan = sum(1 for r in db['samples'] if r['doi'] not in dois)
    checks.append(('samples 的文章都在 papers 里', not orphan, '挂不上 %d 行' % orphan if orphan else ''))
    mkeys = {(r['doi'], r['method_id']) for r in db['methods']}
    orphan = sum(1 for r in db['measurements'] if r['method_id'] and (r['doi'], r['method_id']) not in mkeys)
    checks.append(('数值的 method_id 都在 methods 里', not orphan, '挂不上 %d 行' % orphan if orphan else ''))
    no_data = sum(1 for r in db['samples'] if r['n_measurements'] in ('', '0'))
    checks.append(('每个样品至少一个数值', not no_data, '%d 个没有' % no_data if no_data else ''))
    checks.append(('flat_measurements 与 measurements 行数相同', len(db['flat_measurements']) == len(db['measurements']),
                   ''))
    scope = '' if old is None else '（这次重算的 %d 篇；其余沿用上次核对过的）' % len(todo)
    checks.append(('每篇按底稿重新生成的 md 与磁盘上的 datapoint.md 逐字相同' + scope, not problems,
                   '%d 篇不同或缺底稿' % len(problems) if problems else ''))
    checks.append(('库里的列拼回 md 样品表，逐格逐个数值相同' + scope, not mismatches,
                   '%d 处不同' % len(mismatches) if mismatches else ''))
    checks.append(('没有 md 表里显示不出来的数（指标不在 17 项）' + scope, not hidden, '%d 个' % len(hidden) if hidden else ''))

    os.makedirs(args.out, exist_ok=True)
    for name, cols in bd_TABLES:
        bd_write_csv(os.path.join(args.out, name + '.csv'), cols, db[name])
    ed_atomic_write(os.path.join(args.out, 'README.md'), bd_readme_text())
    bd_write_report(args, names, db, checks, problems, mismatches, hidden, empty, time.time() - t0, mode)
    if not args.papers:
        papers = {}
        for n in names:
            if n in bad_names:
                continue
            doi = info[n] if n in fresh else (prev.get(n) or {}).get('doi')
            papers[n] = {'root': where[n], 'sig': sigs[n], 'doi': doi}
        ed_atomic_write(mpath, json.dumps({'version': 1, 'code': code, 'roots': [bd_norm(r) for r in roots],
                                           'built_at': time.strftime('%Y-%m-%d %H:%M'), 'papers': papers},
                                          ensure_ascii=False, indent=0) + '\n')
    print('写出数据库 %s：文章 %d、样品 %d、数值 %d（%d 篇 datapoint 没有数值）；%s；核对 %s' % (
        args.out, len(db['papers']), len(db['samples']), len(db['measurements']), empty, mode,
        '全部通过' if all(ok for _, ok, _ in checks) else '有不通过的，见 ' + bd_REPORT_NAME))
    return 0 if all(ok for _, ok, _ in checks) else 1


def bd_write_report(args, names, db, checks, problems, mismatches, hidden, empty, seconds, mode=''):
    m = db['measurements']
    src = collections.Counter(r['source_type'] for r in m)
    prop = collections.Counter(r['property_cn'] for r in m)
    no_num = sum(1 for r in m if r['value'] == '')
    sizes = {name: os.path.getsize(os.path.join(args.out, name + '.csv')) for name, _ in bd_TABLES}
    by_root = collections.Counter()
    for r in db['papers']:
        by_root['ACS' if r['doi'].startswith('10.1021/') else 'Elsevier' if r['doi'].startswith('10.1016/') else '其他'] += 1
    lines = ['# 建库报告', '',
             '时间：%s；每篇的 datapoint.md（%s；底稿：%s 的模型回答 + 每篇的 全文合并.md）→ %s；用时 %.0f 秒。' % (
                 time.strftime('%Y-%m-%d %H:%M'), ' + '.join(ed_papers_dir(r) for r in args.roots), ed_MODEL, args.out,
                 seconds), '',
             '这次：%s。' % mode if mode else '', '',
             '## 数量', '',
             '- datapoint.md：%d 篇，其中有数值的 %d 篇（进 papers：%s），没有数值的 %d 篇' % (
                 len(names), len(db['papers']), '，'.join('%s %d' % kv for kv in by_root.most_common()), empty),
             '- 样品 %d，复配物 %d 行，处理步骤 %d 步（参数 %d 个）' % (
                 len(db['samples']), len(db['ingredients']), len(db['treatments']), len(db['treatment_params'])),
             '- 数值 %d（作者表格 %d、正文 %d、读图 %d），测定条件 %d 条；value 不是单个数的 %d 个（原样在 value_text）' % (
                 len(m), src['作者表格'], src['正文'], src['图反读'] + src['图片表格反读'],
                 len(db['measurement_conditions']), no_num),
             '- 各项：' + '，'.join('%s %d' % kv for kv in prop.most_common()), '',
             '## 核对', '']
    lines += ['- %s %s%s' % ('✓' if ok else '✗', what, '（%s）' % note if note else '') for what, ok, note in checks]
    for title, items in (('底稿对不上的文章', problems), ('和 md 样品表对不上的格子', mismatches),
                         ('md 表里显示不出来的数', hidden)):
        if items:
            lines += ['', '### %s（前 50 条）' % title, ''] + ['- ' + x for x in items[:50]]
    lines += ['', '## 文件', '', '| 表 | 行数 | 大小 |', '|---|---|---|']
    lines += ['| %s.csv | %d | %.1f MB |' % (name, len(db[name]), sizes[name] / 1e6) for name, _ in bd_TABLES]
    ed_atomic_write(os.path.join(args.out, bd_REPORT_NAME), '\n'.join(lines) + '\n')


# ====================================================================================================
# 命令行：一条命令跑全流程，或单跑某一步（用户 2026-10-21）
# ====================================================================================================
SITE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir))   # the website repository
MERGE_INPUTS = ('全文.md', MD_NAME, DB_NAME, os.path.join(FIGURE_DIR, 'figure_markdown.md'))


def needs_merge(root):
    """读完图的文章：还没有 全文合并.md，或 全文.md / 反读数据 / 图注比 全文合并.md 新。"""
    out = os.path.join(root, pc_MERGED_NAME)
    if not os.path.exists(out):
        return True
    t = os.path.getmtime(out)
    return any(os.path.exists(os.path.join(root, f)) and os.path.getmtime(os.path.join(root, f)) > t for f in MERGE_INPUTS)


# 用户 2026-10-21：「跑反读图、数据点提取以及方法提取这些需要调用模型的可以同时开五个甚至更多窗口，他们速度慢」
READ_WINDOWS = 5


def read_in_windows(roots, n, extra=()):
    """开 n 个读图窗口（同原来的 同时开5个*窗口.bat：每个带 --slot K/n，开始前先领取、互不重复；每隔 3 秒开一个），等它们都结束，
    返回各窗口的退出码。窗口里跑的是这个脚本的 read，参数和 bat 一样（默认模型、flex 路由、--log），key 用本进程的环境变量。
    roots：一个总文件夹，或几个（几个总文件夹的文章合在一起分给各窗口；用户 2026-10-30）。"""
    import subprocess
    roots = [roots] if isinstance(roots, str) else list(roots)
    procs = []
    for k in range(1, n + 1):
        cmd = [sys.executable, '-B', os.path.abspath(__file__), 'read'] + roots + ['--log', '--slot', '%d/%d' % (k, n)] + list(extra)
        procs.append(subprocess.Popen(cmd, creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)))
        if k < n:
            time.sleep(3)
    return [p.wait() for p in procs]


# 用户 2026-10-30：「2-8编号的文件夹 经过流水线脚本跑完 应该得到和D:\1.acs_papers_done 一样的结构和内容」
ORGANIZE_KEEP = (PAPERS_SUBDIR, pc_RECORDS_SUBDIR, bd_DB_SUBDIR)


def organize_root(top, dry_run=False):
    """总文件夹里直接放着的文章文件夹（有 全文.md 或 figure\\ 的）挪进 <top>\\papers\\，和 D:\\1.acs_papers_done 一样。
    同一个盘里改名，文件和修改时间都不变（回答存档按内容认、断点按文章名认，照样接着用）；papers、_records、database
    和不像文章的文件夹不动；papers 里已经有同名的不挪（列出来）。返回 (挪了的篇数, 同名没挪的)。dry_run 只数不挪。"""
    dest = os.path.join(top, PAPERS_SUBDIR)
    moved, clash = 0, []
    for name in sorted(os.listdir(top)):
        src = os.path.join(top, name)
        if name in ORGANIZE_KEEP or not os.path.isdir(src) or not (
                os.path.isfile(os.path.join(src, '全文.md')) or os.path.isdir(os.path.join(src, FIGURE_DIR))):
            continue
        if os.path.exists(os.path.join(dest, name)):
            clash.append(name)
            continue
        if not dry_run:
            os.makedirs(dest, exist_ok=True)
            os.rename(src, os.path.join(dest, name))
        moved += 1
    return moved, clash


def all_main(argv=None):
    """整条流程：读图 → 合并 → 数据点 → 测定方法 → 带方法的 datapoint.md → 建库。每一步都只做还没做的（读图跳过已完成的，
    合并只做新读完图的，数据点、测定方法有回答存档、输入没变的不重问），所以随时可以再跑一遍接着做。
    还没读完图（停在断点、或没开始）的文章后面几步先不做，免得用不完整的反读数据提取。
    调模型的三步默认并行（用户 2026-10-21）：读图开 --windows 个窗口（默认 5，同原来的 同时开5个*窗口.bat），都结束后还停在断点的
    再开一轮 --only-started 补一次；数据点、测定方法同时问模型的请求数 = 窗口数 × 每个窗口 4 个（默认 20）。
    用户 2026-10-30：不给 --root 就是 D 盘 2–8 号总文件夹（PAPER_ROOTS，SKIP_ROOTS 里的 Wiley 先跳过）一起做，和 Elsevier 一样处理：开头把直接放在总文件夹里的
    文章挪进 papers\\（organize_root）；按编号从小到大一个总文件夹一个总文件夹做（「处理顺序就按标号从小到大进行」）：读完图，
    后面几步另开一个进程做（读图常常要跑好几天，用的是那时候磁盘上的脚本，跑着的这几天里改过的规则也用上）；合并、数据点、
    测定方法按总文件夹分别做（报告和回答存档在各自的 _records）；建库更新 1–8 号合成的库 D:\\protein_database，再给这个
    总文件夹建它自己的 database\\（和 D:\\1.acs_papers_done 一样）。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog='pipeline.py all', description='整条流程：读图 → 合并 → 数据点 → 测定方法 → 建库')
    ap.add_argument('--root', action='append', default=None,
                    help='总文件夹，可以给几个；默认 D 盘 2–8 号（先跳过 %s）：%s' % ('、'.join(SKIP_ROOTS), '、'.join(DEFAULT_ROOTS)))
    ap.add_argument('--skip-read', action='store_true', help='不读图（读图另开 5 个窗口跑时用），其余照做')
    ap.add_argument('--remerge', action='store_true', help='读完图的文章全部重新合并（默认只合并还没合并的、或输入比合并稿新的）')
    ap.add_argument('--dry-run', action='store_true', help='只数每一步要做多少篇，不调模型、不写文件')
    ap.add_argument('--provider', default='auto', help='数据点、测定方法在 OpenRouter 上限定哪一家；auto = gemini 走 flex 档'
                                                       '（临时改标准档：--provider google-ai-studio）')
    ap.add_argument('--read-provider', default=None,
                    help='读图在 OpenRouter 上限定哪几家，默认同读图（%s，flex 档）；临时改标准档：openai,google-ai-studio'
                         % OPENROUTER_PROVIDER)
    ap.add_argument('--windows', type=int, default=READ_WINDOWS,
                    help='读图同时开几个窗口（默认 %d；1 = 就在这个窗口里读）' % READ_WINDOWS)
    ap.add_argument('--workers', type=int, default=None,
                    help='数据点、测定方法同时进行的请求数，默认 窗口数 × %d' % ed_WORKERS)
    args = ap.parse_args(argv)
    tops = list(dict.fromkeys(args.root or DEFAULT_ROOTS))
    for top in tops:
        if not os.path.isdir(top):
            raise SystemExit('找不到总文件夹：%s' % top)
    if args.windows < 1:
        raise SystemExit('--windows 至少是 1')
    args.workers = args.workers or ed_WORKERS * args.windows
    read_extra = ['--provider', args.read_provider] if args.read_provider else []
    t0 = time.time()
    for top in tops:
        moved, clash = organize_root(top, dry_run=args.dry_run)
        if moved or clash:
            print('%s：直接放在总文件夹里的文章 %d 篇%s挪进 papers\\%s' % (
                top, moved, '要' if args.dry_run else '已', '；papers 里已有同名、没挪的 %d 篇：%s' % (
                    len(clash), '、'.join(clash[:5])) if clash else ''), flush=True)
    papers = {top: find_papers([top]) for top in tops}
    unread = [r for top in tops for r in papers[top] if not is_done(r)]
    todo = set(unread)
    for top in tops:
        print('总文件夹 %s：文章 %d 篇，还没读完图的 %d 篇' % (top, len(papers[top]), sum(1 for r in papers[top] if r in todo)),
              flush=True)
    if args.dry_run:
        print('读图：%s %d 篇（调模型）' % ('跳过' if args.skip_read else '要读', len(unread)))
        for top in tops:
            done = [r for r in papers[top] if is_done(r)]
            merge = [r for r in done if args.remerge or needs_merge(r)]
            cdir = os.path.join(ed_records_dir(top), ed_CACHE_DIR, ed_model_slug(ed_MODEL))
            ask = 0
            for r in done:
                p = os.path.join(r, pc_MERGED_NAME)
                if r in merge or not os.path.exists(p) or ed_load_cache(cdir, ed_parse_doc(p), ed_MODEL) is None:
                    ask += 1
            print('—— %s' % top)
            print('合并：%d 篇（纯规则）' % len(merge))
            print('数据点：最多 %d 篇要问模型（合并稿新的、或还没有回答存档的；合并后文字没变的照用存档）' % ask)
        print('测定方法：数据点有进库数值、还没有回答存档的文章要问模型；建库：全部 datapoint.md 重新建（不调模型）')
        return 0
    rc = {}
    if not args.skip_read:
        # 用户 2026-10-30：「处理顺序就按标号从小到大进行」——一个总文件夹读完图、做完后面几步（到建库），再做下一个。
        # 读图常常跑好几天，这期间脚本可能改过：每个总文件夹读完图后，后面几步另开一个进程（同样的参数加 --skip-read），
        # 用的是那时候磁盘上的脚本
        import subprocess
        bad = []
        for top in tops:
            print('\n################ %s ################' % top, flush=True)
            print('\n######## 1 读图 ########', flush=True)
            unread = [r for r in find_papers([top]) if not is_done(r)]
            code = 0
            if unread and args.windows == 1:
                code = main([top, '--log'] + read_extra) or 0
            elif unread:
                n = min(args.windows, len(unread))
                print('开 %d 个读图窗口（每个窗口的屏幕输出也存在 %s）' % (n, LOG_DIR), flush=True)
                codes = read_in_windows([top], n, read_extra)
                left = [r for r in find_papers([top]) if not is_done(r) and os.path.isdir(work_dir(r))]
                if left:
                    n2 = min(args.windows, len(left))
                    print('%d 个窗口都结束了；还停在断点的 %d 篇，再开 %d 个窗口补一次（--only-started）' % (n, len(left), n2),
                          flush=True)
                    codes += read_in_windows([top], n2, ['--only-started'] + read_extra)
                code = max(codes) if codes else 0
                rest = [r for r in find_papers([top]) if not is_done(r)]
                print('读图结束：各窗口退出码 %s；还没读完的 %d 篇（停在断点的 %d 篇）' % (
                    codes, len(rest), sum(1 for r in rest if os.path.isdir(work_dir(r)))), flush=True)
            else:
                print('都读完了')
            if code:
                bad.append('%s 读图' % top)
            cmd = [sys.executable, '-B', os.path.abspath(__file__), 'all', '--skip-read', '--root', top] + \
                (['--remerge'] if args.remerge else []) + \
                ['--provider', args.provider, '--windows', str(args.windows), '--workers', str(args.workers)]
            print('\n读图之后的几步另开一个进程做（用现在磁盘上的脚本）：%s' % subprocess.list2cmdline(cmd[3:]), flush=True)
            if subprocess.call(cmd):
                bad.append('%s 读图之后的几步' % top)
        print('\n整条流程用时 %.0f 秒。%s' % (time.time() - t0, '有没做完或核对没过的：%s（原因见上面；同一条命令再跑一遍会接着做）'
                                             % '、'.join(bad) if bad else '每个总文件夹的每一步都完成了。'))
        return 1 if bad else 0
    print('\n######## 1 读图 ########', flush=True)
    print('跳过（--skip-read）')
    print('\n######## 2 全文合并 ########', flush=True)
    merged = []                                       # 有合并稿的总文件夹才做后面几步（空的总文件夹不建 _records）
    for top in tops:
        done = [r for r in find_papers([top]) if is_done(r)]
        merge = [r for r in done if args.remerge or needs_merge(r)]
        if merge:
            print('—— %s：合并 %d 篇' % (top, len(merge)), flush=True)
            rc['合并'] = pc_main(['--root', top] + merge) or rc.get('合并', 0)
        else:
            print('%s：读完图的 %d 篇都已经合并过，输入没变' % (top, len(done)))
        if any(os.path.exists(os.path.join(r, pc_MERGED_NAME)) for r in done):
            merged.append(top)
    print('\n######## 3–5 数据点 → 测定方法 → 带方法的 datapoint.md（同时 %d 个请求） ########' % args.workers, flush=True)
    for top in merged:
        print('—— %s' % top, flush=True)
        rc['数据点和测定方法'] = dw_main(['--root', top, '--provider', args.provider, '--workers', str(args.workers)]) \
            or rc.get('数据点和测定方法', 0)
    # 建库：1–8 号总文件夹的文章进合成的库 D:\protein_database（只重算新的、变了的文章）；别的总文件夹（测试用的）建在第一个下面。
    # 有数据点的总文件夹再各建一个自己的库 <总文件夹>\database（用户 2026-10-30：结构和内容同 D:\1.acs_papers_done）
    in_db = all(bd_norm(top) in {bd_norm(r) for r in bd_DB_ROOTS} for top in tops)
    print('\n######## 6 建库（%s） ########' % (bd_DB_DIR if in_db else os.path.join(tops[0], bd_DB_SUBDIR)), flush=True)
    rc['建库'] = bd_main([] if in_db else [x for top in tops for x in ('--root', top)]) or 0
    if in_db:
        for top in tops:
            if any(os.path.isfile(os.path.join(r, ed_DATAPOINT_NAME)) for r in find_papers([top])):
                print('\n—— %s 自己的库（%s）' % (top, os.path.join(top, bd_DB_SUBDIR)), flush=True)
                rc['建库'] = bd_main(['--root', top]) or rc['建库']
    bad = [k for k, v in rc.items() if v]
    print('\n整条流程用时 %.0f 秒。%s' % (time.time() - t0, '有没做完或核对没过的步骤：%s（原因见上面；同一条命令再跑一遍会接着做）'
                                         % '、'.join(bad) if bad else '每一步都完成了。'))
    return 1 if bad else 0


def site_main(argv=None):
    """建库 + 更新网站数据（原 build_database\\build_db_and_site.py，都不调模型）：建库核对不过就停，不更新网站。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog='pipeline.py site', description='建库 + 更新网站数据')
    ap.add_argument('--root', default=None, help='只用这个总文件夹的文章（库写到 <root>\\%s）；默认 1–8 号总文件夹合成的库 %s'
                                                 % (bd_DB_SUBDIR, bd_DB_DIR))
    ap.add_argument('--out', default=None, help='数据库目录')
    ap.add_argument('--site', default=SITE_DIR, help='网站目录，默认 %s' % SITE_DIR)
    args = ap.parse_args(argv)
    out = args.out or (os.path.join(args.root, bd_DB_SUBDIR) if args.root else bd_DB_DIR)
    print('==== 第 1 步：建库 ====', flush=True)
    rc = bd_main((['--root', args.root] if args.root else []) + ['--out', out])
    if rc:
        print('建库没有完成或核对没有全部通过（原因见上面；写了库的话明细在 %s），网站先不更新。' % os.path.join(out, bd_REPORT_NAME))
        return rc
    print('\n==== 第 2 步：更新网站数据 ====', flush=True)
    spec = importlib.util.spec_from_file_location('build_site_data', os.path.join(args.site, 'scripts', 'build_site_data.py'))
    site = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(site)
    site.main(['--db', out])
    print('\n完成：数据库 %s，网站数据 %s。网站要推送到 GitHub 才会上线。' % (out, os.path.join(args.site, 'data')))
    return 0


COMMANDS = {'all': all_main, 'read': main, 'merge': pc_main, 'datapoint': ed_main, 'method': em_main,
            'datapoint-with-method': dw_main, 'build-db': bd_main, 'site': site_main}


def cli(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0] in ('-h', '--help', 'help'):
        for stream in (sys.stdout,):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass
        print(__doc__)
        return 0
    if argv[0] not in COMMANDS:
        print('不认识的命令「%s」。可以用的：%s；python pipeline.py -h 看说明' % (argv[0], '、'.join(COMMANDS)))
        return 2
    return COMMANDS[argv[0]](argv[1:]) or 0


if __name__ == '__main__':
    sys.exit(cli())
