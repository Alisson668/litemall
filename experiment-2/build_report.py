#!/usr/bin/env python3
"""Build the Experiment 2 DOCX report from verified local evidence."""

import csv
import json
import sys
from pathlib import Path
from xml.etree import ElementTree

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
EXP_DIR = ROOT / "experiment-2"
EVIDENCE_DIR = EXP_DIR / "evidence"
ASSET_DIR = EXP_DIR / "assets"
OUTPUT = ROOT / "实验二_白盒单元测试生成与变异测试强化.docx"

sys.path.insert(0, str(ROOT / "experiment-1"))
import build_report as common  # noqa: E402


EXPERIMENT_2_PROMPT = (
    "你是资深 Java 测试工程师。为目标类设计 JUnit 5 + Mockito 测试。\n"
    "要求：使用等价类和边界值；覆盖正常、异常、边界和并发前置条件；\n"
    "每条测试必须包含精确断言，禁止只用 assertNotNull 或只断言状态码。\n"
    "先输出测试路径矩阵，再输出测试代码，并列出无法覆盖的路径。"
)


def load_evidence():
    summary = json.loads((EVIDENCE_DIR / "test-summary.json").read_text(encoding="utf-8"))
    with (EVIDENCE_DIR / "jacoco.csv").open(encoding="utf-8", newline="") as handle:
        jacoco_rows = list(csv.DictReader(handle))
    summary["jacoco"]["lineCovered"] = sum(int(row["LINE_COVERED"]) for row in jacoco_rows)
    summary["jacoco"]["lineMissed"] = sum(int(row["LINE_MISSED"]) for row in jacoco_rows)
    summary["jacoco"]["branchCovered"] = sum(int(row["BRANCH_COVERED"]) for row in jacoco_rows)
    summary["jacoco"]["branchMissed"] = sum(int(row["BRANCH_MISSED"]) for row in jacoco_rows)
    line_total = summary["jacoco"]["lineCovered"] + summary["jacoco"]["lineMissed"]
    branch_total = summary["jacoco"]["branchCovered"] + summary["jacoco"]["branchMissed"]
    summary["jacoco"]["lineCoveragePercent"] = round(
        100 * summary["jacoco"]["lineCovered"] / line_total, 2
    )
    summary["jacoco"]["branchCoveragePercent"] = round(
        100 * summary["jacoco"]["branchCovered"] / branch_total, 2
    )

    tree = ElementTree.parse(EVIDENCE_DIR / "mutations.xml")
    mutations = list(tree.getroot())
    killed = sum(1 for item in mutations if item.get("status") == "KILLED")
    summary["pitest"]["generated"] = len(mutations)
    summary["pitest"]["killed"] = killed
    summary["pitest"]["survived"] = sum(
        1 for item in mutations if item.get("status") == "SURVIVED"
    )
    summary["pitest"]["noCoverage"] = sum(
        1 for item in mutations if item.get("status") == "NO_COVERAGE"
    )
    summary["pitest"]["runErrors"] = sum(
        1 for item in mutations if item.get("status") == "RUN_ERROR"
    )
    summary["pitest"]["mutationScorePercent"] = round(100 * killed / len(mutations), 2)
    summary["pitest"]["testStrengthPercent"] = round(100 * killed / len(mutations), 2)
    return summary


def create_summary_chart(summary):
    common.configure_matplotlib()
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.4), gridspec_kw={"wspace": 0.33})

    labels = ["行覆盖", "分支覆盖", "变异得分", "测试通过"]
    values = [
        summary["jacoco"]["lineCoveragePercent"],
        summary["jacoco"]["branchCoveragePercent"],
        summary["pitest"]["mutationScorePercent"],
        100.0 * (summary["tests"]["run"] - summary["tests"]["failures"] - summary["tests"]["errors"])
        / summary["tests"]["run"],
    ]
    axes[0].bar(range(len(labels)), values, color="#666666", edgecolor="#000000", width=0.58)
    axes[0].set_xticks(range(len(labels)), labels)
    axes[0].set_ylim(0, 110)
    axes[0].set_ylabel("百分比（%）")
    axes[0].set_title("覆盖率与测试有效性", loc="left", fontweight="bold")
    axes[0].spines[["top", "right"]].set_visible(False)
    axes[0].grid(axis="y", color="#E6E6E6", linewidth=0.8)
    axes[0].set_axisbelow(True)
    for index, value in enumerate(values):
        axes[0].text(index, value + 2, f"{value:.0f}%", ha="center", fontsize=9)

    operator_labels = ["边界", "TRUE", "NULL", "条件取反"]
    operator_values = [1, 1, 6, 5]
    axes[1].bar(
        range(len(operator_labels)),
        operator_values,
        color="#BDBDBD",
        edgecolor="#595959",
        width=0.58,
    )
    axes[1].set_xticks(range(len(operator_labels)), operator_labels)
    axes[1].set_ylabel("已杀死变异体数量")
    axes[1].set_title("PITest 变异算子分布", loc="left", fontweight="bold")
    axes[1].spines[["top", "right"]].set_visible(False)
    axes[1].grid(axis="y", color="#E6E6E6", linewidth=0.8)
    axes[1].set_axisbelow(True)
    for index, value in enumerate(operator_values):
        axes[1].text(index, value + 0.15, str(value), ha="center", fontsize=9)

    fig.suptitle(
        "OrderPriceCalculator 测试结果",
        x=0.04,
        ha="left",
        fontsize=13,
        fontweight="bold",
        color="#000000",
    )
    path = ASSET_DIR / "coverage-mutation-summary.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def create_workflow_figure():
    common.configure_matplotlib()
    fig, ax = plt.subplots(figsize=(9.2, 2.55))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 2.25)
    ax.axis("off")
    steps = [
        ("Prompt", "路径矩阵\n等价类 / 边界"),
        ("JUnit 5", "13 个测试\n精确断言"),
        ("JaCoCo", "行 / 分支\n覆盖率"),
        ("PITest", "13 个变异体\n逐项杀死"),
        ("人工审计", "弱断言与\n不可覆盖路径"),
    ]
    width = 1.62
    gap = 0.36
    for index, (title, detail) in enumerate(steps):
        left = 0.18 + index * (width + gap)
        fill = "#F2F2F2" if index % 2 == 0 else "#FFFFFF"
        ax.add_patch(
            plt.Rectangle(
                (left, 0.5),
                width,
                1.25,
                facecolor=fill,
                edgecolor="#7F7F7F",
                linewidth=1,
            )
        )
        ax.text(
            left + width / 2,
            1.4,
            title,
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            color="#000000",
        )
        ax.text(
            left + width / 2,
            0.94,
            detail,
            ha="center",
            va="center",
            fontsize=8,
            color="#404040",
            linespacing=1.4,
        )
        if index < len(steps) - 1:
            ax.annotate(
                "",
                xy=(left + width + gap - 0.03, 1.12),
                xytext=(left + width + 0.03, 1.12),
                arrowprops={"arrowstyle": "-|>", "color": "#595959", "lw": 1.2},
            )
    path = ASSET_DIR / "test-workflow.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def create_commit_image(commit_text):
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    width, height = 1600, 940
    image = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.truetype(r"C:\Windows\Fonts\consolab.ttf", 34)
    body_font = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 25)
    draw.rectangle((42, 42, width - 42, height - 42), outline="#7F7F7F", width=3)
    draw.text((70, 78), "Git Commit Log", font=title_font, fill="#000000")
    draw.text((70, 125), "$ git log -1 --pretty=fuller --stat", font=title_font, fill="#404040")
    y = 205
    for line in commit_text.splitlines()[:24]:
        fill = "#000000" if line.startswith("commit ") or "experiment-2" in line else "#333333"
        draw.text((72, y), line[:96], font=body_font, fill=fill)
        y += 28
    path = ASSET_DIR / "git-commit-log.png"
    image.save(path)
    return path


def add_page_number_footer(section):
    footer = section.footer
    paragraph = footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    common.add_text(paragraph, "实验二  第 ", size=10.5, color=common.MUTED)
    field = common.add_field(paragraph, " PAGE ")
    common.set_run_font(field, size=10.5, color=common.MUTED)
    common.add_text(paragraph, " 页", size=10.5, color=common.MUTED)


def add_classic_cover(doc):
    for _ in range(2):
        spacer = doc.add_paragraph()
        spacer.paragraph_format.space_after = Pt(18)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(10)
    common.add_text(
        title,
        "《软件质量与检测》实验",
        size=36,
        color=common.INK,
        bold=True,
        east_asia="宋体",
    )

    experiment = doc.add_paragraph()
    experiment.alignment = WD_ALIGN_PARAGRAPH.CENTER
    experiment.paragraph_format.space_before = Pt(4)
    experiment.paragraph_format.space_after = Pt(22)
    common.add_text(
        experiment,
        "实验二  白盒单元测试生成与变异测试强化",
        size=18,
        color=common.INK,
        bold=True,
        east_asia="黑体",
    )

    cover_lines = [
        "学院：信息工程        专业：网络工程",
        "地点：D508/D509",
        "班    级：________________",
        "学    号：________________        姓    名：________________",
        "开课时间：2026 至 2027 学年 第 1 学期",
        "成    绩：________________________________________________",
    ]
    for text in cover_lines:
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.line_spacing = 1.6
        paragraph.paragraph_format.space_after = Pt(2)
        common.add_text(paragraph, text, size=16, color=common.INK, bold=True, east_asia="宋体")

    topic = doc.add_paragraph()
    topic.alignment = WD_ALIGN_PARAGRAPH.CENTER
    topic.paragraph_format.space_before = Pt(34)
    common.add_text(
        topic,
        "基于 litemall + JUnit 5 + Mockito + JaCoCo + PITest 的实验报告",
        size=15,
        color=common.INK,
        bold=True,
        east_asia="黑体",
    )
    doc.add_page_break()


def add_toc(doc):
    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(12)
    common.add_text(title, "目录", size=18, color=common.INK, bold=True, east_asia="黑体")
    items = [
        ("1  实验目的与核心指标", "测试目标、质量指标与验收口径"),
        ("2  实验原理与技术架构", "CFG、等价类、边界值、Mockito 与变异测试"),
        ("3  实验任务、Prompt 与实施步骤", "配置、Prompt、测试路径矩阵与代码"),
        ("4  实验结果与量化分析", "JUnit、JaCoCo 与 PITest 实测数据"),
        ("5  缺陷追踪与根因分析", "依赖冲突、工具兼容与不可覆盖路径"),
        ("6  AI 赋能反思与思考题", "弱断言、变异测试与人工审计"),
        ("7  实验总结与工程心得", "可复用测试策略与后续计划"),
        ("附录 A—C", "Commit Log、AI 证据占位与本地证据索引"),
    ]
    table = doc.add_table(rows=1, cols=2)
    for index, text in enumerate(("章节", "主要内容")):
        cell = table.rows[0].cells[index]
        common.shade_cell(cell, common.LIGHT_GRAY)
        common.add_text(cell.paragraphs[0], text, size=12, color=common.INK, bold=True)
    for section, detail in items:
        cells = table.add_row().cells
        common.add_text(cells[0].paragraphs[0], section, size=12, color=common.INK, bold=True)
        common.add_text(cells[1].paragraphs[0], detail, size=12, color=common.MUTED)
    common.set_table_geometry(table, [3600, 6860])
    for row in table.rows:
        for cell in row.cells:
            common.set_cell_border(cell, bottom={"sz": 4, "color": common.MID_GRAY})
    common.add_body(doc, "本目录采用静态章节导航，页码由页脚字段显示。")
    doc.add_page_break()


def build_document(summary, summary_chart, workflow, commit_image):
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.268)
    section.page_height = Inches(11.693)
    section.top_margin = Inches(0.5)
    section.right_margin = Inches(0.5)
    section.bottom_margin = Inches(0.5)
    section.left_margin = Inches(0.5)
    section.header_distance = Inches(0.25)
    section.footer_distance = Inches(0.25)
    section.different_first_page_header_footer = True

    styles = doc.styles
    normal = styles["Normal"]
    common.set_style_font(normal, 12, common.INK, False, east_asia="宋体")
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.25

    body_text = styles["Body Text"]
    common.set_style_font(body_text, 12, common.INK, False, east_asia="宋体")
    body_text.paragraph_format.space_before = Pt(5)
    body_text.paragraph_format.space_after = Pt(5)
    body_text.paragraph_format.line_spacing = 1.25
    body_text.paragraph_format.first_line_indent = Pt(24)

    title_style = styles["Title"]
    common.set_style_font(title_style, 18, common.INK, False, east_asia="黑体")
    title_style.paragraph_format.space_before = Pt(5)
    title_style.paragraph_format.space_after = Pt(5)

    for name, size, before in (
        ("Heading 1", 16, 16),
        ("Heading 2", 15, 14),
        ("Heading 3", 15, 12),
    ):
        style = styles[name]
        common.set_style_font(style, size, common.INK, False, east_asia="黑体")
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(5)
        style.paragraph_format.line_spacing = 1.25
        style.paragraph_format.keep_with_next = True

    for list_name in ("List Bullet", "List Number"):
        style = styles[list_name]
        common.set_style_font(style, 12, common.INK, False, east_asia="宋体")
        style.paragraph_format.space_before = Pt(3)
        style.paragraph_format.space_after = Pt(3)
        style.paragraph_format.line_spacing = 1.25

    section.header.paragraphs[0].text = ""
    add_page_number_footer(section)
    section.first_page_header.paragraphs[0].text = ""
    section.first_page_footer.paragraphs[0].text = ""

    doc.core_properties.title = "软件质量与检测实验报告：实验二"
    doc.core_properties.subject = "litemall 白盒单元测试生成与变异测试强化"
    doc.core_properties.author = "Alisson668"
    doc.core_properties.keywords = "litemall, JUnit 5, Mockito, JaCoCo, PITest"

    add_classic_cover(doc)
    add_toc(doc)

    common.add_heading(doc, "1  实验目的与核心指标", 1)
    common.add_body(
        doc,
        "本实验以订单价格计算核心类 OrderPriceCalculator 为主要目标，并在 WxOrderService.submit 入口补充 Mockito 交互测试。目标是使用等价类、边界值和精确断言构建可审计的 JUnit 5 测试集，再以 JaCoCo 与 PITest 验证覆盖率和测试有效性。",
    )
    common.add_body(
        doc,
        "课程要求核心模块分支覆盖率与变异得分均不低于 85%。本实验不把“覆盖率 100%”直接等同于“测试有效”，因此同时报告测试数量、精确断言、变异体状态和无法单元测试的路径。",
    )
    common.add_table(
        doc,
        "表 1  实验二验收指标与最终结果",
        ["指标", "目标", "最终结果", "证据"],
        [
            ("JUnit 5 测试", "覆盖正常、异常与边界", "13 / 13 通过", "Surefire"),
            ("行覆盖率", "≥ 85%", "100% (29/29)", "JaCoCo"),
            ("分支覆盖率", "≥ 85%", "100% (12/12)", "JaCoCo"),
            ("变异得分", "≥ 85%", "100% (13/13)", "PITest"),
            ("测试强度", "≥ 85%", "100%", "PITest"),
            ("弱断言", "禁止仅 assertNotNull 或状态码", "0 处", "人工审计"),
        ],
        [2200, 3000, 2500, 2760],
        source_text="数据来源：2026-11-06 本地 Maven、JaCoCo 0.8.11 与 PITest 1.9.0 实测。",
    )

    common.add_heading(doc, "2  实验原理与技术架构", 1)
    common.add_heading(doc, "2.1  控制流、等价类与边界值", 2)
    common.add_body(
        doc,
        "OrderPriceCalculator 可分为两个核心决策区域：团购商品匹配与订单金额计算。团购匹配涉及规则为空、规则商品 ID 为空、购物车商品 ID 为空、商品匹配和商品不匹配；金额计算涉及运费门槛下方、等于门槛、高于门槛以及优惠券超过或恰好抵扣完商品金额。",
    )
    common.add_body(
        doc,
        "测试路径优先覆盖决策结果，而不是只追求执行行数。每个用例都给出可计算金额或可验证交互；对于并发库存、数据库原子更新和事务回滚等跨层路径，不伪造纯单元测试结论，而是列入“无法覆盖路径”。",
    )
    common.add_heading(doc, "2.2  工具链与工作流", 2)
    common.add_figure(doc, workflow, "图 1  Prompt、路径矩阵、JUnit 5、JaCoCo 与 PITest 工作流", width=6.8)
    common.add_table(
        doc,
        "表 2  实验二工具链",
        ["工具", "版本 / 配置", "用途"],
        [
            ("JDK", "OpenJDK 1.8.0_504", "保持项目 Java 8 兼容"),
            ("Maven", "3.9.12", "Reactor 构建与测试执行"),
            ("JUnit Jupiter", "5.10.3", "JUnit 5 测试 API、参数化与引擎"),
            ("JUnit Vintage", "5.10.3", "兼容仓库内 JUnit 4 测试"),
            ("Mockito", "1.10.19（父 POM 继承）", "服务交互与无交互校验"),
            ("JaCoCo", "0.8.11", "行覆盖率与分支覆盖率"),
            ("PITest", "1.9.0 + JUnit 5 插件 1.0.0", "变异测试与测试强度"),
        ],
        [2200, 3600, 4660],
        source_text="数据来源：litemall-wx-api/pom.xml 与实际 Maven 运行记录。",
    )

    common.add_heading(doc, "3  实验任务、Prompt 与实施步骤", 1)
    common.add_heading(doc, "3.1  Prompt 原文", 2)
    common.add_code_block(doc, "实验二 Prompt（原文记录）", EXPERIMENT_2_PROMPT)
    common.add_callout(
        doc,
        "证据边界",
        "本报告记录用户提供的 Prompt，不伪造 SenseNova DeepSeek V4.1 Flash 的原始输出、截图或人工修正过程。AI 输出与截图须由学生后续在附录 B 补录。",
    )

    common.add_heading(doc, "3.2  OrderPriceCalculator 测试路径矩阵", 2)
    common.add_table(
        doc,
        "表 3  单价计算与金额计算路径矩阵",
        ["编号", "路径 / 前置条件", "等价类或边界", "精确断言"],
        [
            ("T01", "团购商品匹配，混合普通商品", "正常等价类", "100×2 + 50 − 10 = 230.00"),
            ("T02", "团购规则指向其他商品", "不匹配等价类", "商品金额 = 100.00"),
            ("T03", "规则 goodsId 为 null", "空值异常边界", "商品金额 = 100.00"),
            ("T04", "购物车 goodsId 为 null", "空值异常边界", "商品金额 = 100.00"),
            ("T05", "无团购规则，多个商品", "正常等价类", "19.90×3 + 0.50×2 = 60.70"),
            ("T06", "购物车为空", "空集合边界", "商品金额 = 0.00"),
            ("T07", "商品金额 80，运费门槛 88", "下边界", "运费 8.00；订单 78.00"),
            ("T08", "商品金额恰好 88", "精确边界", "运费 0.00；订单 88.00"),
            ("T09", "商品金额 100，优惠券 20", "上边界", "运费 0.00；订单 80.00"),
            ("T10", "优惠券 30 大于可抵扣额", "超额边界", "订单金额 = 0.00"),
            ("T11", "商品 10 + 运费 8，优惠券 18", "恰好归零边界", "订单金额 = 0.00"),
        ],
        [700, 3650, 2400, 3710],
        font_size=9.5,
        source_text="数据来源：OrderPriceCalculatorTest 中 11 个 JUnit 5 @Test 方法。",
    )

    common.add_table(
        doc,
        "表 4  WxOrderService Mockito 交互矩阵",
        ["编号", "前置条件", "路径类型", "精确断言与 verify"],
        [
            (
                "T12",
                "userId 为 null",
                "未登录异常入口",
                "errno = 501；verifyZeroInteractions(addressService)",
            ),
            (
                "T13",
                "userId=7，addressId=22，地址不存在",
                "异常分支",
                "errno = 401；verify(addressService).query(7, 22)",
            ),
        ],
        [700, 3000, 2200, 4560],
        source_text="数据来源：WxOrderServiceMockitoTest 中 2 个 JUnit 5 + Mockito 测试。",
    )

    common.add_heading(doc, "3.3  精确断言样例", 2)
    common.add_code_block(
        doc,
        "边界值与精确交互断言",
        "@Test\n"
        "void removesFreightAtExactLimit() {\n"
        "    Amount amount = OrderPriceCalculator.calculateAmount(\n"
        "            new BigDecimal(\"88.00\"), ZERO,\n"
        "            new BigDecimal(\"88.00\"), new BigDecimal(\"8.00\"));\n"
        "    assertPrice(\"0.00\", amount.getFreightPrice());\n"
        "    assertPrice(\"88.00\", amount.getOrderPrice());\n"
        "}\n\n"
        "@Test\n"
        "void rejectsMissingAddress() {\n"
        "    when(addressService.query(7, 22)).thenReturn(null);\n"
        "    Map<String, Object> response = orderService.submit(7, body);\n"
        "    assertEquals(401, response.get(\"errno\"));\n"
        "    verify(addressService).query(7, 22);\n"
        "}",
    )

    common.add_heading(doc, "3.4  配置与执行步骤", 2)
    common.add_numbered_step(doc, "在 litemall-wx-api/pom.xml 引入 JUnit Jupiter 5.10.3、Vintage 兼容引擎、JaCoCo 0.8.11 与 PITest 1.9.0。")
    common.add_numbered_step(doc, "将原有 JUnit 4 价格测试迁移为 JUnit 5，并补齐 null IDs、空购物车、精确运费门槛和优惠券归零边界。")
    common.add_numbered_step(doc, "增加 WxOrderServiceMockitoTest，使用 @Mock、@InjectMocks 与 MockitoAnnotations.initMocks 兼容父 POM 的 Mockito 1.10.19。")
    common.add_numbered_step(doc, "以 JDK 8 执行目标测试，确认 13 个测试全部通过，并生成 JaCoCo 行/分支报告。")
    common.add_numbered_step(doc, "运行 PITest，仅变异 OrderPriceCalculator 及其内部 Amount 类，检查存活变异体和测试强度。")

    common.add_table(
        doc,
        "表 5  实际执行命令（摘要）",
        ["阶段", "命令摘要", "结果"],
        [
            (
                "JUnit 5",
                "mvn -pl litemall-wx-api -am -Dmaven.test.skip=false -Dtest=... test",
                "13 / 13 通过",
            ),
            (
                "JaCoCo",
                "显式传入 jacoco-agent argLine 后执行 test",
                "行 29/29；分支 12/12",
            ),
            (
                "PITest",
                "mvn -pl litemall-wx-api org.pitest:pitest-maven:1.9.0:mutationCoverage",
                "13 killed；0 survived",
            ),
        ],
        [1500, 6600, 2360],
        font_size=9.5,
        source_text="完整路径与依赖版本保存在 experiment-2/evidence 和 litemall-wx-api/pom.xml。",
    )

    common.add_heading(doc, "4  实验结果与量化分析", 1)
    common.add_heading(doc, "4.1  JUnit 5 与 JaCoCo", 2)
    common.add_table(
        doc,
        "表 6  测试与覆盖率实测",
        ["测试类", "用例数", "失败", "错误", "结果"],
        [
            ("OrderPriceCalculatorTest", "11", "0", "0", "PASS"),
            ("WxOrderServiceMockitoTest", "2", "0", "0", "PASS"),
            ("合计", "13", "0", "0", "PASS"),
        ],
        [4300, 1500, 1200, 1200, 2260],
        source_text="数据来源：experiment-2/evidence 中 Surefire TXT 与 XML 报告。",
    )
    common.add_table(
        doc,
        "表 7  JaCoCo 覆盖结果",
        ["范围", "行覆盖", "行覆盖率", "分支覆盖", "分支覆盖率"],
        [
            ("OrderPriceCalculator", "19 / 19", "100%", "12 / 12", "100%"),
            ("OrderPriceCalculator.Amount", "10 / 10", "100%", "无分支", "N/A"),
            ("目标合计", "29 / 29", "100%", "12 / 12", "100%"),
        ],
        [3700, 1500, 1500, 1500, 2260],
        source_text="数据来源：experiment-2/evidence/jacoco.csv。",
    )

    common.add_heading(doc, "4.2  PITest 变异测试", 2)
    common.add_figure(doc, summary_chart, "图 2  覆盖率与变异测试结果", width=6.8)
    common.add_table(
        doc,
        "表 8  变异算子结果",
        ["变异算子", "生成", "杀死", "存活", "无覆盖"],
        [
            ("条件边界", "1", "1", "0", "0"),
            ("布尔真值返回", "1", "1", "0", "0"),
            ("空值返回", "6", "6", "0", "0"),
            ("条件取反", "5", "5", "0", "0"),
            ("合计", "13", "13", "0", "0"),
        ],
        [3900, 1500, 1500, 1500, 2060],
        source_text="数据来源：experiment-2/evidence/mutations.xml 与 PITest 控制台汇总。",
    )
    common.add_callout(
        doc,
        "结果解释",
        "13 个变异体全部被杀死，说明现有断言能够区分正常逻辑与边界、空值和条件取反等逻辑变化。该结论只适用于 OrderPriceCalculator 及其内部 Amount 类，不外推到数据库事务、并发库存和微信支付回调。",
    )

    common.add_heading(doc, "5  缺陷追踪与根因分析", 1)
    common.add_table(
        doc,
        "表 9  实验二发现的问题与修正",
        ["编号", "现象", "根因", "修正与验证"],
        [
            (
                "D1",
                "Mockito 测试初始化失败：NoClassDefFoundError",
                "子模块 Mockito 4 与父 POM Mockito 1.10.19 同时进入测试类路径",
                "移除重复 Mockito 4 依赖，改用 MockitoAnnotations.initMocks 与 verifyZeroInteractions",
            ),
            (
                "D2",
                "PITest 覆盖率 Minion 异常退出：AbstractMethodError",
                "pitest-junit5-plugin 1.0.0 要求 PITest 1.9.0，而配置原为 1.7.4",
                "主插件对齐到 1.9.0，重新执行后 13/13 killed",
            ),
            (
                "D3",
                "旧测试只覆盖少数正常路径",
                "JUnit 4 用例未覆盖空 ID、空购物车和精确门槛",
                "迁移为 11 个 JUnit 5 价格测试，并补充精确金额断言",
            ),
            (
                "D4",
                "纯单元测试无法证明库存并发与事务回滚",
                "原子 UPDATE、DB 锁和 Spring 事务代理不在 OrderPriceCalculator 内",
                "列入无法覆盖路径，后续使用数据库集成测试验证",
            ),
        ],
        [800, 3200, 3200, 3260],
        font_size=9.5,
        source_text="数据来源：实际构建日志、POM 调整记录与测试报告。",
    )

    common.add_heading(doc, "5.1  无法覆盖的路径", 2)
    common.add_table(
        doc,
        "表 10  当前测试边界外路径",
        ["路径", "为什么无法由当前单元测试覆盖", "建议验证方式"],
        [
            (
                "同一商品并发扣库存",
                "需要真实数据库条件更新与并发事务",
                "Testcontainers + 两线程集成测试",
            ),
            (
                "库存扣减失败后订单事务回滚",
                "需要 Spring 代理和真实事务管理器",
                "@SpringBootTest 或事务模板集成测试",
            ),
            (
                "优惠券记录跨用户归属",
                "当前 Mockito 入口测试未覆盖 CouponUser 查询分支",
                "Mock couponUserService 返回其他 userId",
            ),
            (
                "团购活动满员、重复参团与自参团",
                "需要 LitemallGroupon 记录及关联查询状态",
                "构造 Mockito 服务交互测试",
            ),
            (
                "微信支付回调重复通知",
                "需要 XML 请求、支付服务与任务调度协作",
                "回调幂等集成测试",
            ),
        ],
        [3000, 4100, 3360],
        font_size=9.5,
        source_text="数据来源：WxOrderService 调用链与当前测试范围的人工审计。",
    )

    common.add_heading(doc, "6  AI 赋能反思与深度思考题", 1)
    common.add_heading(doc, "6.1  AI 生成测试的审计重点", 2)
    common.add_body(
        doc,
        "AI 往往能快速枚举常规路径，但容易停留在“调用成功”或“对象不为空”的弱断言。对于金额计算，模型必须写出确定金额；对于服务协作，模型必须 verify 具体参数与调用次数。否则测试即使提高覆盖率，也无法发现边界改变、条件取反或返回空值等变异。",
    )
    common.add_body(
        doc,
        "本实验没有把当前对话伪装为课程模型输出。用户提供的 Prompt 已完整记录，后续应由学生在 SenseNova DeepSeek V4.1 Flash 中执行，并保存 AI 初稿中的弱断言、遗漏空值和依赖版本冲突，再记录人工修正过程。",
    )
    common.add_heading(doc, "6.2  思考题：为什么变异测试比覆盖率更有力", 2)
    common.add_body(
        doc,
        "覆盖率只回答“代码是否被执行”，不回答“断言是否能识别错误”。例如把一个比较符从 < 改为 <=，原测试仍可能保持 100% 行覆盖，但断言没有区分边界，变异体就会存活。变异测试主动注入缺陷，只有断言足够精确、输入足够有区分度时，变异体才会被杀死。因此变异得分和测试强度更接近“测试能否发现真实回归”的证据。",
    )
    common.add_heading(doc, "6.3  思考题：如何设计可维护的测试矩阵", 2)
    common.add_body(
        doc,
        "可维护的矩阵应先按职责和决策点分层，再为每个等价类与边界选择最少但可区分的样例。表驱动测试可以减少重复，但不应把断言隐藏在模糊辅助方法中；金额、状态、异常和 Mockito 交互都应有明确期望。对无法由单元测试可靠证明的路径，应明确升级为集成测试，而不是用覆盖率数字掩盖。",
    )

    common.add_heading(doc, "7  实验总结与工程心得", 1)
    common.add_body(
        doc,
        "本实验将订单价格测试迁移到 JUnit 5，并补充了 11 个价格计算用例与 2 个 Mockito 交互用例。最终 13 个测试全部通过，OrderPriceCalculator 的行覆盖率和分支覆盖率均为 100%，PITest 生成并杀死 13 个变异体，变异得分与测试强度均为 100%。",
    )
    common.add_body(
        doc,
        "工程上更关键的收获是识别两类“表面通过”：一类是依赖版本冲突导致测试无法初始化，另一类是覆盖率很高但断言不够精确。通过查看异常链、对齐 PITest 与 JUnit 5 插件版本、审计每条金额断言，测试结果才具备可重复性和解释力。",
    )
    common.add_body(
        doc,
        "实验二也明确了测试边界：纯函数测试不能替代库存并发、事务回滚和支付回调幂等验证。后续可继续使用数据库集成测试与契约测试补充这些路径。",
    )

    doc.add_page_break()
    common.add_heading(doc, "附录 A  Git Commit Log", 1)
    common.add_body(
        doc,
        "实验二独立提交：9f92bb1e  test(experiment-2): add JUnit 5 coverage and mutation tests。截图由本地真实 git log --stat 输出生成，只包含实验二 POM 与测试文件。",
    )
    common.add_figure(doc, commit_image, "图 A-1  实验二 Git Commit Log 与文件变更统计", width=6.8)

    common.add_heading(doc, "附录 B  DeepSeek V4.1 Flash 关键对话", 1)
    common.add_callout(
        doc,
        "待学生补齐真实截图",
        "Prompt 已按原文记录。AI 原始输出、关键问题标注、学生发现与人工修正截图仍待补录。建议至少展示一次弱断言修正、一次空值/边界缺口修正和一次依赖或工具兼容问题。",
    )
    common.add_table(
        doc,
        "表 B-1  AI 对话核验清单",
        ["核验项", "要求", "状态"],
        [
            ("模型与端点", "SenseNova + DeepSeek V4.1 Flash", "待补录"),
            ("原始 Prompt", "使用 3.1 节目录中的完整原文", "已记录"),
            ("AI 输出问题点", "标注弱断言、漏测边界或错误 API", "待补录"),
            ("人工修正", "展示 JUnit 5 代码、JaCoCo 与 PITest 结果", "待补录"),
        ],
        [2200, 5900, 2360],
        source_text="数据来源：课程 AI 证据要求与本实验实际完成状态。",
    )

    common.add_heading(doc, "附录 C  过程证据文件", 1)
    common.add_table(
        doc,
        "表 C-1  本地证据索引",
        ["文件", "内容"],
        [
            ("evidence/jacoco.csv", "行覆盖 29/29、分支覆盖 12/12"),
            ("evidence/mutations.xml", "13 个变异体，全部 KILLED"),
            ("evidence/*OrderPriceCalculatorTest.txt", "11 个 JUnit 5 测试通过"),
            ("evidence/*WxOrderServiceMockitoTest.txt", "2 个 Mockito 交互测试通过"),
            ("evidence/test-summary.json", "环境、测试、覆盖率与变异结果汇总"),
            ("evidence/git-commit-experiment2.txt", "真实 Commit Log 文本"),
        ],
        [4500, 5960],
        font_size=10.5,
        source_text="全部文件位于 litemall/experiment-2/evidence。",
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    return OUTPUT


def main():
    summary = load_evidence()
    summary_chart = create_summary_chart(summary)
    workflow = create_workflow_figure()
    commit_text = (EVIDENCE_DIR / "git-commit-experiment2.txt").read_text(
        encoding="utf-8"
    )
    commit_image = create_commit_image(commit_text)
    output = build_document(summary, summary_chart, workflow, commit_image)
    print(output)


if __name__ == "__main__":
    main()
