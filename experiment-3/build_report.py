#!/usr/bin/env python3
"""Build the Experiment 3 DOCX report from verified local evidence."""

import json
import re
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
EXP_DIR = ROOT / "experiment-3"
EVIDENCE_DIR = EXP_DIR / "evidence"
ASSET_DIR = EXP_DIR / "assets"
OUTPUT = ROOT / "实验三_接口契约测试智能Fuzzing与安全初探.docx"

sys.path.insert(0, str(ROOT / "experiment-1"))
import build_report as common  # noqa: E402


def read_json(name):
    return json.loads((EVIDENCE_DIR / name).read_text(encoding="utf-8-sig"))


def create_summary_chart(summary, live_results):
    common.configure_matplotlib()
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.35), gridspec_kw={"wspace": 0.34})

    labels = ["契约覆盖", "自动测试", "真实 Fuzzing"]
    values = [
        summary["contract"]["coveragePercent"],
        100.0 * summary["automatedTests"]["tests"]
        / max(summary["automatedTests"]["tests"], 1),
        100.0 * summary["liveHttpFuzzing"]["passed"]
        / max(summary["liveHttpFuzzing"]["cases"], 1),
    ]
    axes[0].bar(range(len(labels)), values, color="#666666", edgecolor="#000000", width=0.58)
    axes[0].set_xticks(range(len(labels)), labels)
    axes[0].set_ylim(0, 110)
    axes[0].set_ylabel("通过率（%）")
    axes[0].set_title("实验三验收结果", loc="left", fontweight="bold")
    axes[0].spines[["top", "right"]].set_visible(False)
    axes[0].grid(axis="y", color="#E6E6E6", linewidth=0.8)
    axes[0].set_axisbelow(True)
    for index, value in enumerate(values):
        axes[0].text(index, value + 2, f"{value:.0f}%", ha="center", fontsize=9)

    status_counts = Counter(str(item["httpStatus"]) for item in live_results)
    ordered = sorted(status_counts)
    axes[1].bar(
        range(len(ordered)),
        [status_counts[item] for item in ordered],
        color="#BDBDBD",
        edgecolor="#595959",
        width=0.58,
    )
    axes[1].set_xticks(range(len(ordered)), ordered)
    axes[1].set_ylabel("用例数量")
    axes[1].set_title("真实 HTTP 状态码分布", loc="left", fontweight="bold")
    axes[1].spines[["top", "right"]].set_visible(False)
    axes[1].grid(axis="y", color="#E6E6E6", linewidth=0.8)
    axes[1].set_axisbelow(True)
    for index, status in enumerate(ordered):
        axes[1].text(index, status_counts[status] + 0.18, str(status_counts[status]), ha="center", fontsize=9)

    fig.suptitle(
        "接口契约与语义 Fuzzing 结果",
        x=0.04,
        ha="left",
        fontsize=13,
        fontweight="bold",
        color="#000000",
    )
    path = ASSET_DIR / "contract-fuzz-summary.png"
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return path


def create_category_chart(live_results):
    common.configure_matplotlib()
    counts = Counter(item["category"] for item in live_results)
    labels = list(counts.keys())
    values = [counts[label] for label in labels]
    fig, ax = plt.subplots(figsize=(8.8, 3.0))
    ax.bar(range(len(labels)), values, color="#777777", edgecolor="#000000", width=0.58)
    ax.set_xticks(range(len(labels)), labels)
    ax.set_ylabel("用例数量")
    ax.set_title("真实 Fuzzing 类别分布", loc="left", fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#E6E6E6", linewidth=0.8)
    ax.set_axisbelow(True)
    for index, value in enumerate(values):
        ax.text(index, value + 0.1, str(value), ha="center", fontsize=9)
    path = ASSET_DIR / "fuzz-categories.png"
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
        ("OpenAPI", "控制器与\nSwagger 契约"),
        ("MockMvc", "32 个\n契约/Fuzz 测试"),
        ("Docker", "真实 HTTP\n与 JWT 鉴权"),
        ("分类审计", "状态码\n与 IDOR"),
        ("最小修复", "严格解析\n与错误分层"),
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
    path = ASSET_DIR / "contract-workflow.png"
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
    for line in commit_text.splitlines()[:25]:
        fill = "#000000" if line.startswith("commit ") or "experiment-3" in line else "#333333"
        draw.text((72, y), line[:96], font=body_font, fill=fill)
        y += 27
    path = ASSET_DIR / "git-commit-log.png"
    image.save(path)
    return path


def add_page_number_footer(section):
    footer = section.footer
    paragraph = footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    common.add_text(paragraph, "实验三  第 ", size=10.5, color=common.MUTED)
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
        "实验三  接口契约测试、智能 Fuzzing 与安全初探",
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
        "基于 litemall + MockMvc + Docker 的接口质量与安全报告",
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
        ("1  实验目的与核心指标", "契约覆盖、语义 Fuzzing 与安全验收"),
        ("2  实验原理与技术架构", "OpenAPI、MockMvc、JWT 与 Docker HTTP"),
        ("3  实验任务、Prompt 与实施步骤", "环境、契约矩阵、载荷矩阵与代码"),
        ("4  实验结果与量化分析", "32 个测试、16 个真实 HTTP 用例与 OpenAPI"),
        ("5  缺陷追踪与根因分析", "宽松类型解析、错误码分层与 IDOR"),
        ("6  AI 赋能反思与思考题", "LLM Fuzzing 的优势、短板与人工审计"),
        ("7  实验总结与工程心得", "工程结论、残余风险与后续计划"),
        ("附录 A—C", "Commit、AI 证据占位与过程文件"),
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


def build_document(summary, live_results, baseline, coverage, summary_chart, category_chart, workflow, commit_image):
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

    doc.core_properties.title = "软件质量与检测实验报告：实验三"
    doc.core_properties.subject = "litemall 接口契约测试、智能 Fuzzing 与安全初探"
    doc.core_properties.author = "Alisson668"
    doc.core_properties.keywords = "litemall, OpenAPI, MockMvc, Fuzzing, IDOR, SQL injection"

    add_classic_cover(doc)
    add_toc(doc)

    common.add_heading(doc, "1  实验目的与核心指标", 1)
    common.add_body(
        doc,
        "本实验聚焦 litemall 小程序订单接口 POST /wx/order/submit，并以 GET /wx/order/detail 的归属校验作为补充安全边界。实验将接口契约、语义 Fuzzing 和 JWT 身份链路放在同一条可复现流水线中验证。",
    )
    common.add_body(
        doc,
        "验收目标不是单纯获得 HTTP 200，而是确认方法、媒体类型、身份来源、JSON 类型、必填字段、值域、业务错误、响应结构和越权前置条件均有明确行为。真实 HTTP 用例还在 Docker 容器与 MySQL 环境中执行，确保测试结论不只停留在 MockMvc。",
    )
    common.add_table(
        doc,
        "表 1  实验三验收指标与最终结果",
        ["验收项", "目标", "最终结果", "证据"],
        [
            ("核心契约元素", "100%", "24 / 24", "contract-coverage.json"),
            ("自动契约/Fuzz 测试", "全部通过", "32 / 32", "Surefire"),
            ("真实 HTTP/IDOR 用例", "全部通过", "16 / 16", "live-final-results.json"),
            ("未捕获 5xx", "0", "0", "live-summary.json"),
            ("SQL 注入前置条件", "不进入数据库", "严格类型拒绝", "Mockito verify"),
            ("跨用户购物车", "拒绝", "errno 402", "真实 MySQL fixture"),
            ("OpenAPI 导出", "可获取", "84 paths", "wx-api-swagger.json"),
        ],
        [2500, 2400, 2500, 3060],
        source_text="数据来源：2026-11-13 本地 Java 8、Maven、MockMvc、Docker 29.5.2 与 MySQL 5.7 实测。",
    )

    common.add_heading(doc, "2  实验原理与技术架构", 1)
    common.add_heading(doc, "2.1  契约测试与语义 Fuzzing", 2)
    common.add_body(
        doc,
        "契约测试检查接口对调用者承诺的结构和行为，包括 HTTP 方法、Content-Type、请求体根节点、必填字段、整数类型、值域、JWT 身份来源、业务 errno、错误消息和响应格式。仅断言状态码或非空对象无法证明字段含义正确，也不能发现错误的类型强制转换。",
    )
    common.add_body(
        doc,
        "语义 Fuzzing 在语法变形之外加入业务含义：文本数字、布尔值、数组、对象、负数、零地址、32 位整数溢出、小数、SQL 注入文本、畸形 JSON、无效 UTF-8、64 KiB 消息以及请求体 userId 篡改。每条载荷都有明确期望错误和精确 JSONPath 断言。",
    )
    common.add_heading(doc, "2.2  工具链与工作流", 2)
    common.add_figure(doc, workflow, "图 1  OpenAPI、MockMvc、Docker HTTP、分类审计与最小修复工作流", width=6.8)
    common.add_table(
        doc,
        "表 2  实验三工具链",
        ["工具", "版本 / 入口", "用途"],
        [
            ("JDK / Maven", "OpenJDK 1.8.0_504 / 3.9.12", "Java 8 编译与测试"),
            ("Spring MVC MockMvc", "5.1.7.RELEASE", "控制器契约与异常处理"),
            ("JUnit 5", "5.10.3", "参数化 Fuzzing 与精确断言"),
            ("Mockito", "1.10.19", "服务交互、IDOR 与无 DB 验证"),
            ("Docker Engine", "29.5.2", "真实 HTTP 容器验证"),
            ("MySQL", "5.7", "跨用户购物车前置数据"),
            ("Swagger / OpenAPI", "/v2/api-docs?group=wx", "真实接口文档导出"),
        ],
        [2600, 3600, 4260],
        source_text="数据来源：litemall-wx-api/pom.xml、Docker Compose 与运行环境实测。",
    )

    common.add_heading(doc, "3  实验任务、Prompt 与实施步骤", 1)
    common.add_heading(doc, "3.1  Prompt 原文", 2)
    prompt = (EXP_DIR / "prompt.txt").read_text(encoding="utf-8")
    common.add_code_block(doc, "实验三 Prompt（原文记录）", prompt)
    common.add_callout(
        doc,
        "证据边界",
        "本报告记录用户提供的 Prompt 和本地真实工程结果，不伪造 SenseNova DeepSeek V4.1 Flash 的原始输出、截图或人工修正过程。AI 输出与截图须由学生后续在附录 B 补录。",
    )

    common.add_heading(doc, "3.2  环境配置", 2)
    common.add_numbered_step(doc, "确认 Docker Engine、litemall、MySQL、SonarQube、Prometheus 与 Grafana 容器运行。")
    common.add_numbered_step(doc, "使用 Java 8 编译并打包 litemall，复制可执行 JAR，重启 litemall 容器并等待 HTTP 健康检查通过。")
    common.add_numbered_step(doc, "从运行中的应用导出 /v2/api-docs?group=wx，确认 submit 只消费和生成 application/json。")
    common.add_numbered_step(doc, "执行 MockMvc 契约测试、参数化语义 Fuzzing、IDOR 和归属校验测试。")
    common.add_numbered_step(doc, "生成临时地址和跨用户购物车 fixture，执行真实 HTTP IDOR 测试，并在 finally 中自动清理。")
    common.add_numbered_step(doc, "汇总 HTTP 状态、errno、类别、OpenAPI 与 Surefire 报告，生成 Word 实验报告。")

    common.add_heading(doc, "3.3  核心契约矩阵", 2)
    common.add_table(
        doc,
        "表 3  POST /wx/order/submit 核心契约",
        ["编号", "契约元素", "约定", "验证"],
        [
            ("C01-C03", "方法与媒体类型", "POST；请求/响应 application/json", "MockMvc 200/405/415/406"),
            ("C04-C07", "JWT 身份链路", "token 提供 userId；缺失/伪造为匿名", "200 + errno 501"),
            ("C08-C09", "请求结构与必填项", "根节点为对象；cart/address/coupon 必填", "errno 401"),
            ("C10-C15", "类型与值域", "严格整数；cart≥0；address>0；coupon≥-1", "errno 402"),
            ("C16", "SQL 注入", "注入文本不得进入数据库查询", "verifyZeroInteractions(addressService)"),
            ("C17-C19", "异常编码与载荷", "畸形 JSON、无效 UTF-8、64 KiB 消息不崩溃", "无 5xx"),
            ("C20-C21", "IDOR", "购物车和订单必须按 JWT userId 查询", "Mockito 与 MySQL fixture"),
            ("C22-C24", "传输错误", "405 / 415 / 406", "标准 HTTP 状态"),
        ],
        [1300, 2800, 3500, 2860],
        font_size=9.5,
        source_text="数据来源：contract-coverage.json。完整矩阵共 24 项，全部 PASS。",
    )

    common.add_heading(doc, "3.4  真实 Fuzzing 载荷矩阵", 2)
    common.add_table(
        doc,
        "表 4  语义 Fuzzing 与安全用例",
        ["类别", "载荷 / 前置条件", "期望结果"],
        [
            ("正常", "合法 JSON，地址不存在", "HTTP 200，errno 401"),
            ("类型混淆", "cartId/addressId 为字符串、布尔、数组、对象", "HTTP 200，errno 402"),
            ("极值", "负地址、32 位整数溢出、64 KiB 消息", "业务错误，无 5xx"),
            ("SQL 注入", "addressId = 2 UNION SELECT 1", "errno 402，未调用地址查询"),
            ("编码异常", "畸形 JSON、数组根节点、text/plain", "402 或 415"),
            ("鉴权", "缺失 token、伪造 token", "errno 501"),
            ("IDOR", "请求体 userId=999；token userId=7", "只使用 7，忽略 999"),
            ("IDOR", "用户 7 地址 + 用户 999 购物车", "errno 402，临时数据已清理"),
            ("契约", "GET submit、Accept text/plain", "405、406"),
        ],
        [1700, 5600, 3160],
        source_text="数据来源：live-final-results.json 与 MockMvc 参数化 Fuzz 测试。",
    )

    common.add_heading(doc, "3.5  关键修复", 2)
    common.add_code_block(
        doc,
        "严格 JSON 整数解析",
        "JsonNode leaf = root.get(field);\n"
        "if (leaf == null || leaf.isNull()) return null;\n"
        "if (!leaf.isIntegralNumber() || !leaf.canConvertToInt()) {\n"
        "    throw new OrderValidationException(ResponseUtil.badArgumentValue());\n"
        "}\n"
        "return leaf.intValue();",
    )
    common.add_code_block(
        doc,
        "接口媒体类型契约",
        "@PostMapping(value = \"submit\",\n"
        "        consumes = MediaType.APPLICATION_JSON_VALUE,\n"
        "        produces = MediaType.APPLICATION_JSON_VALUE)\n"
        "public Object submit(@LoginUser Integer userId,\n"
        "                     @RequestBody String body) { ... }",
    )
    common.add_code_block(
        doc,
        "错误码分层",
        "if (!request.hasRequiredFields()) {\n"
        "    throw new OrderValidationException(ResponseUtil.badArgument());\n"
        "}\n"
        "if (!request.hasValidValues()) {\n"
        "    throw new OrderValidationException(ResponseUtil.badArgumentValue());\n"
        "}",
    )

    common.add_heading(doc, "3.6  一键复现", 2)
    common.add_code_block(
        doc,
        "实验三可复现命令",
        "powershell -ExecutionPolicy Bypass -File .\\scripts\\experiment3.ps1",
    )

    common.add_heading(doc, "4  实验结果与量化分析", 1)
    common.add_heading(doc, "4.1  自动测试与真实 HTTP", 2)
    common.add_table(
        doc,
        "表 5  测试结果汇总",
        ["测试层", "用例数", "通过", "失败", "错误"],
        [
            ("WxOrderSubmitContractTest", "7", "7", "0", "0"),
            ("WxOrderSubmitFuzzTest", "25", "25", "0", "0"),
            ("MockMvc 合计", "32", "32", "0", "0"),
            ("Docker 真实 HTTP/IDOR", "16", "16", "0", "0"),
        ],
        [4300, 1500, 1500, 1500, 1660],
        source_text="数据来源：Surefire 报告与 live-summary.json。",
    )
    common.add_table(
        doc,
        "表 6  真实 HTTP 状态分布",
        ["HTTP 状态", "数量", "含义"],
        [
            ("200", "13", "业务成功或业务错误（errno 区分）"),
            ("405", "1", "HTTP 方法不支持"),
            ("406", "1", "无法生成客户端可接受的响应"),
            ("415", "1", "请求媒体类型不支持"),
            ("5xx", "0", "无未捕获服务端崩溃"),
        ],
        [2300, 1600, 6560],
        source_text="数据来源：live-final-results.json。",
    )
    common.add_figure(doc, summary_chart, "图 2  契约覆盖、自动测试、真实 Fuzzing 与状态码分布", width=6.8)
    common.add_figure(doc, category_chart, "图 3  真实 Fuzzing 类别分布", width=6.5)

    common.add_heading(doc, "4.2  修复前后对比", 2)
    common.add_table(
        doc,
        "表 7  修复前后真实 HTTP 行为",
        ["载荷", "修复前", "修复后", "改进"],
        [
            ("文本整数", "200 / errno 401", "200 / errno 402", "拒绝类型混淆"),
            ("SQL 注入文本", "200 / errno 401", "200 / errno 402", "严格解析，不进 DB"),
            ("整数溢出", "200 / errno 401", "200 / errno 402", "拒绝越界"),
            ("畸形 JSON", "200 / errno 401", "200 / errno 402", "客户端错误明确"),
            ("数组根节点", "200 / errno 401", "200 / errno 402", "拒绝非对象"),
            ("text/plain", "200 / errno 401", "415 / errno 415", "媒体类型契约生效"),
            ("缺失/伪造 JWT", "errno 501", "errno 501", "行为保持"),
        ],
        [2600, 2500, 2500, 2860],
        source_text="数据来源：baseline-live-results.json 与 live-final-results.json。",
    )
    common.add_callout(
        doc,
        "结果解释",
        "修复前 JsonNode.asInt() 把大量非法输入强制转换后继续业务查询，接口也接受 text/plain。修复后先校验 JSON 节点类型、数值范围和业务值域，再把传输级错误交给 405/406/415 专用处理。真实 HTTP 用例未观察到 5xx。",
    )

    common.add_heading(doc, "4.3  OpenAPI 与证据质量", 2)
    common.add_table(
        doc,
        "表 8  OpenAPI 导出结果",
        ["项目", "结果"],
        [
            ("Swagger 版本", "2.0"),
            ("导出路径数", "84"),
            ("submit consumes", "application/json"),
            ("submit produces", "application/json"),
            ("detail 路由", "存在"),
            ("证据文件", "experiment-3/openapi/wx-api-swagger.json"),
        ],
        [3000, 7460],
        source_text="数据来源：运行中应用 http://localhost:8080/v2/api-docs?group=wx。",
    )

    common.add_heading(doc, "5  缺陷追踪与根因分析", 1)
    common.add_table(
        doc,
        "表 9  本次实验发现与修复",
        ["编号", "问题", "根因", "修复"],
        [
            ("D1", "文本、布尔、数组、对象被当成整数", "JsonNode.asInt() 宽松转换", "严格 integralNumber + canConvertToInt"),
            ("D2", "极值、负数和无效 coupon 未提前拒绝", "只检查非空，不检查值域", "补齐 cart/address/coupon/groupon 值域"),
            ("D3", "缺失字段与错误值都返回 401", "完整性和值域校验混在一起", "401 表示缺失，402 表示类型或值错误"),
            ("D4", "text/plain 被 submit 接受", "映射未声明 consumes", "固定 JSON 请求/响应媒体类型"),
            ("D5", "框架 405/406/415 可能落入通用 502", "仅配置 Exception 兜底", "增加专用状态处理"),
            ("D6", "请求体 userId 可能被误当作身份来源", "身份与业务载荷边界需验证", "断言只使用 JWT userId，忽略 body userId"),
            ("R1", "JWT 密钥硬编码，缺少轮换", "JwtHelper 使用固定 SECRET", "本次保留为残余风险，建议外部配置与轮换"),
        ],
        [800, 3000, 3000, 3660],
        font_size=9.5,
        source_text="数据来源：代码审计、MockMvc 测试和真实 HTTP 前后对比。",
    )

    common.add_heading(doc, "5.1  无法由当前单元/契约测试覆盖的路径", 2)
    common.add_table(
        doc,
        "表 10  残余风险与后续验证",
        ["路径", "当前缺口", "建议"],
        [
            ("Token 吊销与密钥轮换", "当前 JWT 无黑名单、无 kid", "引入密钥版本、短时 token 与吊销机制"),
            ("多实例限流与暴力尝试", "本地单实例无法验证分布式限流", "网关限流、审计日志与告警"),
            ("真实商品/优惠券组合成功路径", "示例库无完整购物车和地址", "使用 Testcontainers 构造全链路 fixture"),
            ("支付回调幂等与签名", "/wx/order/pay-notify 未在本接口范围", "微信签名、重复通知与任务幂等测试"),
            ("其他 84 个 OpenAPI 路径", "本次聚焦订单核心接口", "按风险继续生成契约测试"),
        ],
        [3300, 3700, 3460],
        font_size=9.5,
        source_text="数据来源：实验范围与安全审计的人工判断。",
    )

    common.add_heading(doc, "6  AI 赋能反思与深度思考题", 1)
    common.add_heading(doc, "6.1  LLM 在 Web API Fuzzing 中的优势与短板", 2)
    common.add_body(
        doc,
        "LLM 的优势在于理解字段语义并快速生成跨类别的对抗载荷，例如把 cartId 变成对象、把 addressId 变成 SQL 片段，或把身份放进请求体测试 IDOR。相比纯随机字节变异，语义载荷更容易命中业务边界，也更容易解释测试意图。",
    )
    common.add_body(
        doc,
        "短板是模型可能只生成“看起来危险”的载荷，却遗漏响应断言、身份链路和数据库副作用；也可能把 200 当作成功，忽略 errno 与 errmsg。因此 Prompt 必须要求契约矩阵、精确断言、真实 HTTP 执行和无法覆盖路径，人工还要检查测试是否真正触发了目标分支。",
    )
    common.add_heading(doc, "6.2  思考题：为什么不能只依赖随机 Fuzzing", 2)
    common.add_body(
        doc,
        "随机 Fuzzing 善于发现解析崩溃，但对业务不变量不敏感。比如一个随机字符串不一定能同时满足 JSON 可解析、进入订单提交、携带合法 token，并触发购物车归属查询。语义 Fuzzing 先理解接口字段和身份来源，再为每个业务决策构造可区分输入，因此更容易发现 IDOR、类型混淆和错误码混淆。",
    )
    common.add_heading(doc, "6.3  思考题：契约覆盖 100% 意味着什么", 2)
    common.add_body(
        doc,
        "本报告的 100% 是对明确列出的 24 个核心契约元素的覆盖，不代表覆盖全部 84 个 Swagger 路径，也不代表覆盖所有数据库状态。工程结论应说明范围、证据和残余风险，避免把局部接口的结论扩大成全系统安全证明。",
    )
    common.add_callout(
        doc,
        "AI 证据待补录",
        "Prompt 已记录。SenseNova DeepSeek V4.1 Flash 的原始输出、关键问题标注、学生发现与人工修正截图仍待补录，报告不伪造该模型的实际输出。",
    )

    common.add_heading(doc, "7  实验总结与工程心得", 1)
    common.add_body(
        doc,
        "本实验完成了从 OpenAPI 导出、MockMvc 契约测试、参数化语义 Fuzzing 到 Docker 真实 HTTP 与 MySQL IDOR fixture 的闭环。32 个自动测试与 16 个真实 HTTP/IDOR 用例全部通过，核心契约 24/24，覆盖 5xx 为 0。",
    )
    common.add_body(
        doc,
        "最重要的修复不是增加更多错误分支，而是把“能不能解析”和“值是否合法”分开：JSON 必须是对象，整数必须是整数类型且在 32 位范围内，必填字段缺失返回 401，类型或值错误返回 402，媒体类型错误返回 415。这样客户端能得到可诊断的反馈，服务端也不会把危险载荷带入数据库查询。",
    )
    common.add_body(
        doc,
        "安全测试仍需保持边界意识。JWT 密钥硬编码、分布式限流、支付回调和多实例一致性不在本次接口契约测试内，已作为残余风险明确列出，而不是用局部通过结果掩盖。",
    )

    doc.add_page_break()
    common.add_heading(doc, "附录 A  Git Commit Log", 1)
    common.add_body(
        doc,
        "实验三独立提交：1b1da370  test(experiment-3): harden order contract and add semantic fuzzing。截图由本地真实 git log --stat 输出生成。",
    )
    common.add_figure(doc, commit_image, "图 A-1  实验三 Git Commit Log 与文件变更统计", width=6.8)

    common.add_heading(doc, "附录 B  DeepSeek V4.1 Flash 关键对话", 1)
    common.add_callout(
        doc,
        "待学生补齐真实截图",
        "Prompt 已按原文记录。请补充 AI 输出中的弱断言、错误状态码、漏测 IDOR 或工具兼容问题，并展示学生发现、人工修正和复测证据。",
    )
    common.add_table(
        doc,
        "表 B-1  AI 对话核验清单",
        ["核验项", "要求", "状态"],
        [
            ("模型与端点", "SenseNova + DeepSeek V4.1 Flash", "待补录"),
            ("原始 Prompt", "使用 3.1 节完整原文", "已记录"),
            ("AI 输出问题点", "标注弱断言、漏测、错误 API 或安全盲区", "待补录"),
            ("人工修正", "展示代码、32 个测试与 16 个真实 HTTP 结果", "待补录"),
        ],
        [2200, 5900, 2360],
        source_text="数据来源：课程 AI 证据要求与本实验实际完成状态。",
    )

    common.add_heading(doc, "附录 C  过程证据与复现", 1)
    common.add_table(
        doc,
        "表 C-1  本地证据索引",
        ["文件", "内容"],
        [
            ("evidence/live-final-results.json", "16 个真实 HTTP/IDOR 用例"),
            ("evidence/live-summary.json", "16/16 通过、0 个 5xx"),
            ("evidence/contract-coverage.json", "24 个核心契约元素"),
            ("evidence/baseline-live-results.json", "修复前宽松解析行为"),
            ("evidence/test-summary.json", "环境、测试与结果汇总"),
            ("openapi/wx-api-swagger.json", "实际导出的 Swagger 2.0 文档"),
            ("prompt.txt", "实验三 Prompt 原文"),
        ],
        [4700, 5760],
        font_size=10.5,
        source_text="全部路径相对于 experiment-3/；一键复现命令见 3.6 节。",
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    return OUTPUT


def main():
    summary = read_json("test-summary.json")
    coverage = read_json("contract-coverage.json")
    baseline = read_json("baseline-live-results.json")
    live_results = read_json("live-final-results.json")
    summary_chart = create_summary_chart(summary, live_results)
    category_chart = create_category_chart(live_results)
    workflow = create_workflow_figure()
    commit_text = (EVIDENCE_DIR / "git-commit-experiment3.txt").read_text(
        encoding="utf-8"
    )
    commit_image = create_commit_image(commit_text)
    output = build_document(
        summary,
        live_results,
        baseline,
        coverage,
        summary_chart,
        category_chart,
        workflow,
        commit_image,
    )
    print(output)


if __name__ == "__main__":
    main()
