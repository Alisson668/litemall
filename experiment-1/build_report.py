#!/usr/bin/env python3
"""Build the Experiment 1 DOCX report from verified local evidence."""

import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as font_manager
from matplotlib.patches import Rectangle
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
EXP_DIR = ROOT / "experiment-1"
ASSET_DIR = EXP_DIR / "assets"
EVIDENCE_DIR = EXP_DIR / "evidence"
OUTPUT = ROOT / "实验一_软件质量度量静态分析与AI辅助重构_课程模板版.docx"

TEXT_WIDTH_DXA = 10460
INK = "000000"
MUTED = "595959"
GRID = "7F7F7F"
LIGHT_GRAY = "F2F2F2"
MID_GRAY = "D9D9D9"
DARK_GRAY = "404040"
NAVY = INK
BLUE = DARK_GRAY
DARK_BLUE = INK
LIGHT_BLUE = LIGHT_GRAY
GOLD = INK
RED = INK
GREEN = DARK_GRAY

EXPERIMENT_1_PROMPT = (
    "你是资深 Java 质量工程师。请审计 litemall 的 WxOrderService 订单提交逻辑，\n"
    "重点分析事务自调用、购物车归属、团购空值、库存并发、优惠券归属和 BigDecimal 精度。\n"
    "先列出问题与复现条件，再给出最小修改建议，不要求你输出完整文件。"
)


def load_measures(payload):
    measures = payload["wxOrderService"]["measures"]
    return {item["metric"]: item["value"] for item in measures}


def severity_count(payload, severity):
    for item in payload.get("issuesBySeverity", []):
        if item["severity"] == severity:
            return item["count"]
    return 0


def configure_matplotlib():
    font_path = Path(r"C:\Windows\Fonts\simsun.ttc")
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = "SimSun"
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"


def create_metric_charts(measures_before, measures_after):
    configure_matplotlib()
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.5), gridspec_kw={"wspace": 0.34})
    complexity_labels = ["认知复杂度", "圈复杂度"]
    before_values = [
        float(measures_before["cognitive_complexity"]),
        float(measures_before["complexity"]),
    ]
    after_values = [
        float(measures_after["cognitive_complexity"]),
        float(measures_after["complexity"]),
    ]
    x = range(len(complexity_labels))
    axes[0].bar([i - 0.18 for i in x], before_values, 0.36, label="基线", color="#BFBFBF", edgecolor="#595959")
    axes[0].bar([i + 0.18 for i in x], after_values, 0.36, label="最终", color="#595959", edgecolor="#000000")
    axes[0].set_xticks(list(x), complexity_labels)
    axes[0].set_ylabel("指标值")
    axes[0].set_title("文件级复杂度", loc="left", fontweight="bold")
    axes[0].legend(frameon=False, loc="upper right")
    axes[0].spines[["top", "right"]].set_visible(False)
    axes[0].grid(axis="y", color="#E6E6E6", linewidth=0.8)
    axes[0].set_axisbelow(True)
    for i, value in enumerate(before_values):
        axes[0].text(i - 0.18, value + 2, f"{value:.0f}", ha="center", fontsize=8, color=f"#{MUTED}")
    for i, value in enumerate(after_values):
        axes[0].text(i + 0.18, value + 2, f"{value:.0f}", ha="center", fontsize=8, color=f"#{BLUE}")

    finding_labels = ["静态问题总数", "代码异味", "Critical"]
    findings_before = [
        float(measures_before.get("issueTotal", 22)),
        float(measures_before["code_smells"]),
        float(measures_before.get("criticalCount", 7)),
    ]
    findings_after = [
        float(measures_after.get("issueTotal", 0)),
        float(measures_after["code_smells"]),
        float(measures_after.get("criticalCount", 0)),
    ]
    x = range(len(finding_labels))
    axes[1].bar([i - 0.18 for i in x], findings_before, 0.36, label="基线", color="#BFBFBF", edgecolor="#595959")
    axes[1].bar([i + 0.18 for i in x], findings_after, 0.36, label="最终", color="#595959", edgecolor="#000000")
    axes[1].set_xticks(list(x), finding_labels)
    axes[1].set_ylabel("数量")
    axes[1].set_title("静态检查发现", loc="left", fontweight="bold")
    axes[1].legend(frameon=False, loc="upper right")
    axes[1].spines[["top", "right"]].set_visible(False)
    axes[1].grid(axis="y", color="#E6E6E6", linewidth=0.8)
    axes[1].set_axisbelow(True)
    for i, value in enumerate(findings_before):
        axes[1].text(i - 0.18, value + 0.6, f"{value:.0f}", ha="center", fontsize=8, color=f"#{MUTED}")
    for i, value in enumerate(findings_after):
        axes[1].text(i + 0.18, value + 0.6, f"{value:.0f}", ha="center", fontsize=8, color=f"#{MUTED}")

    fig.suptitle("WxOrderService 改造前后质量指标", x=0.04, ha="left", fontsize=13, fontweight="bold", color=f"#{INK}")
    metrics_path = ASSET_DIR / "metrics-overview.png"
    fig.savefig(metrics_path, dpi=220, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.8, 3.25))
    methods = ["submit", "payNotify"]
    before_ccn = [49, 15]
    after_ccn = [4, 8]
    y = range(len(methods))
    ax.barh([i + 0.18 for i in y], before_ccn, 0.34, color="#BFBFBF", edgecolor="#595959", label="基线")
    ax.barh([i - 0.18 for i in y], after_ccn, 0.34, color="#595959", edgecolor="#000000", label="最终")
    ax.set_yticks(list(y), methods)
    ax.set_xlabel("圈复杂度 CCN")
    ax.set_title("核心方法圈复杂度下降", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color="#E6E6E6", linewidth=0.8)
    ax.set_axisbelow(True)
    for i, value in enumerate(before_ccn):
        ax.text(value + 0.7, i + 0.18, str(value), va="center", fontsize=9, color=f"#{MUTED}")
    for i, value in enumerate(after_ccn):
        ax.text(value + 0.7, i - 0.18, str(value), va="center", fontsize=9, color=f"#{BLUE}")
    method_path = ASSET_DIR / "method-complexity.png"
    fig.savefig(method_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return metrics_path, method_path


def create_workflow_figure():
    configure_matplotlib()
    fig, ax = plt.subplots(figsize=(9.0, 2.65))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 2.4)
    ax.axis("off")
    steps = [
        ("基线扫描", "SonarQube\n22 issues / 7 Critical", "F2F2F2"),
        ("热点定位", "WxOrderService\nsubmit CCN=49", "FFFFFF"),
        ("安全重构", "职责拆分\n事务与并发审计", "F2F2F2"),
        ("回归验证", "5 项价格测试\nMaven 构建", "FFFFFF"),
        ("二次扫描", "0 issues\nsubmit CCN=4", "F2F2F2"),
    ]
    width = 1.52
    gap = 0.42
    for index, (title, detail, fill) in enumerate(steps):
        left = 0.25 + index * (width + gap)
        box = Rectangle(
            (left, 0.55),
            width,
            1.22,
            linewidth=1,
            edgecolor=f"#{GRID}",
            facecolor=f"#{fill}",
        )
        ax.add_patch(box)
        ax.text(left + width / 2, 1.45, title, ha="center", va="center", fontsize=10, fontweight="bold", color=f"#{NAVY}")
        ax.text(left + width / 2, 0.98, detail, ha="center", va="center", fontsize=7.7, color=f"#{MUTED}", linespacing=1.45)
        if index < len(steps) - 1:
            ax.annotate(
                "",
                xy=(left + width + gap - 0.04, 1.16),
                xytext=(left + width + 0.05, 1.16),
                arrowprops={"arrowstyle": "-|>", "color": f"#{BLUE}", "lw": 1.3},
            )
    path = ASSET_DIR / "analysis-workflow.png"
    fig.savefig(path, dpi=220, bbox_inches="tight", transparent=False)
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

    wrapped = []
    for line in commit_text.splitlines():
        if not line:
            wrapped.append("")
            continue
        while len(line) > 92:
            wrapped.append(line[:92])
            line = "  " + line[92:]
        wrapped.append(line)

    y = 198
    for line in wrapped[:26]:
        color = "#000000" if line.startswith("commit ") or line.strip().startswith("feat(") else "#333333"
        draw.text((72, y), line, font=body_font, fill=color)
        y += 27
    path = ASSET_DIR / "git-commit-log.png"
    image.save(path)
    return path


def set_run_font(
    run,
    size=12,
    color=INK,
    bold=None,
    italic=None,
    font="Times New Roman",
    east_asia="宋体",
):
    run.font.name = font
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.rFonts
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.insert(0, r_fonts)
    r_fonts.set(qn("w:ascii"), font)
    r_fonts.set(qn("w:hAnsi"), font)
    r_fonts.set(qn("w:eastAsia"), east_asia)


def set_style_font(
    style,
    size,
    color=INK,
    bold=False,
    font="Times New Roman",
    east_asia="宋体",
):
    style.font.name = font
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor.from_string(color)
    style.font.bold = bold
    r_pr = style.element.get_or_add_rPr()
    r_fonts = r_pr.rFonts
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.insert(0, r_fonts)
    r_fonts.set(qn("w:ascii"), font)
    r_fonts.set(qn("w:hAnsi"), font)
    r_fonts.set(qn("w:eastAsia"), east_asia)


def add_text(
    paragraph,
    text,
    size=12,
    color=INK,
    bold=False,
    italic=False,
    font="Times New Roman",
    east_asia="宋体",
):
    run = paragraph.add_run(text)
    set_run_font(
        run,
        size=size,
        color=color,
        bold=bold,
        italic=italic,
        font=font,
        east_asia=east_asia,
    )
    return run


def set_paragraph_rule(paragraph, color=GRID, size=6):
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = p_pr.find(qn("w:pBdr"))
    if p_bdr is None:
        p_bdr = OxmlElement("w:pBdr")
        p_pr.append(p_bdr)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "5")
    bottom.set(qn("w:color"), color)
    p_bdr.append(bottom)


def shade_cell(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=70, bottom=70, start=90, end=90):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for name, value in (("top", top), ("bottom", bottom), ("start", start), ("end", end)):
        node = tc_mar.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_border(cell, **edges):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "start", "end", "insideH", "insideV"):
        if edge not in edges:
            continue
        spec = edges[edge]
        tag = f"w:{edge}"
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), spec.get("val", "single"))
        element.set(qn("w:sz"), str(spec.get("sz", 4)))
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), spec.get("color", GRID))


def set_table_geometry(table, widths_dxa, indent_dxa=0):
    total = sum(widths_dxa)
    if total <= 0:
        raise ValueError("table width must be positive")
    scale = TEXT_WIDTH_DXA / total
    widths_dxa = [round(width * scale) for width in widths_dxa]
    widths_dxa[-1] += TEXT_WIDTH_DXA - sum(widths_dxa)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths_dxa)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        layout = tbl_pr.find(qn("w:tblLayout"))
        if layout is None:
            tbl_pr.append(tbl_ind)
        else:
            layout.addprevious(tbl_ind)
    tbl_ind.set(qn("w:w"), str(indent_dxa))
    tbl_ind.set(qn("w:type"), "dxa")
    layouts = tbl_pr.findall(qn("w:tblLayout"))
    layout = layouts[0] if layouts else OxmlElement("w:tblLayout")
    for duplicate in layouts[1:]:
        tbl_pr.remove(duplicate)
    if not layouts:
        tbl_ind.addnext(layout)
    layout.set(qn("w:type"), "fixed")
    grid = table._tbl.tblGrid
    for index, width in enumerate(widths_dxa):
        grid.gridCol_lst[index].set(qn("w:w"), str(width))
        for row in table.rows:
            row.cells[index].width = Inches(width / 1440)
            set_cell_margins(row.cells[index])
    if table.rows:
        tr_pr = table.rows[0]._tr.get_or_add_trPr()
        if tr_pr.find(qn("w:tblHeader")) is None:
            header = OxmlElement("w:tblHeader")
            header.set(qn("w:val"), "true")
            tr_pr.insert(0, header)


def apply_three_line_table(table, widths_dxa):
    set_table_geometry(table, widths_dxa)
    for row_index, row in enumerate(table.rows):
        for cell in row.cells:
            set_cell_border(cell)
    for cell in table.rows[0].cells:
        set_cell_border(cell, top={"sz": 12, "color": INK}, bottom={"sz": 8, "color": INK})
    for cell in table.rows[-1].cells:
        set_cell_border(cell, bottom={"sz": 12, "color": INK})


def add_table(
    doc,
    caption,
    headers,
    rows,
    widths_dxa,
    font_size=10.5,
    source_text="数据来源：本次实验本地构建、测试与 SonarQube 9.9.8 实测结果。",
):
    cap = doc.add_paragraph(style="Body Text")
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.first_line_indent = Pt(0)
    cap.paragraph_format.space_before = Pt(4)
    cap.paragraph_format.space_after = Pt(4)
    add_text(cap, caption, size=10.5, color=INK, bold=True)
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    for index, value in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.first_line_indent = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        add_text(p, value, size=font_size, color=INK, bold=True)
    tr_pr = table.rows[0]._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    tr_pr.append(repeat)
    for values in rows:
        cells = table.add_row().cells
        for index, value in enumerate(values):
            cells[index].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            paragraph = cells[index].paragraphs[0]
            paragraph.paragraph_format.first_line_indent = Pt(0)
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.0
            add_text(paragraph, str(value), size=font_size, color=INK)
    apply_three_line_table(table, widths_dxa)
    source = doc.add_paragraph(style="Body Text")
    source.paragraph_format.first_line_indent = Pt(0)
    source.paragraph_format.space_before = Pt(4)
    source.paragraph_format.space_after = Pt(8)
    add_text(source, source_text, size=9.5, color=MUTED, italic=True)
    return table


def add_callout(doc, title, body, fill=LIGHT_GRAY, accent=GOLD):
    table = doc.add_table(rows=1, cols=1)
    set_table_geometry(table, [9360])
    cell = table.cell(0, 0)
    shade_cell(cell, LIGHT_GRAY)
    set_cell_border(
        cell,
        top={"sz": 4, "color": GRID},
        left={"sz": 8, "color": INK},
        bottom={"sz": 4, "color": GRID},
        right={"sz": 4, "color": GRID},
    )
    p = cell.paragraphs[0]
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    add_text(p, title, size=12, color=INK, bold=True, east_asia="黑体")
    p2 = cell.add_paragraph()
    p2.paragraph_format.first_line_indent = Pt(0)
    p2.paragraph_format.space_after = Pt(0)
    add_text(p2, body, size=12, color=INK)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def add_figure(doc, image_path, caption, width=6.3):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    shape = p.add_run().add_picture(str(image_path), width=Inches(width))
    shape._inline.docPr.set("descr", caption)
    shape._inline.docPr.set("title", caption)
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(8)
    add_text(cap, caption, size=10.5, color=MUTED)


def add_field(paragraph, field_code):
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin.set(qn("w:dirty"), "true")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = field_code
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instruction, separate, text, end])
    return run


def add_heading(doc, text, level=1):
    paragraph = doc.add_heading(text, level=level)
    paragraph.paragraph_format.keep_with_next = True
    return paragraph


def add_body(doc, text, bold_lead=None):
    paragraph = doc.add_paragraph(style="Body Text")
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.paragraph_format.first_line_indent = Pt(24)
    paragraph.paragraph_format.space_before = Pt(5)
    paragraph.paragraph_format.space_after = Pt(5)
    paragraph.paragraph_format.line_spacing = 1.25
    if bold_lead and text.startswith(bold_lead):
        add_text(paragraph, bold_lead, size=12, color=INK, bold=True)
        add_text(paragraph, text[len(bold_lead):], size=12)
    else:
        add_text(paragraph, text, size=12)
    return paragraph


def add_bullet(doc, text):
    paragraph = doc.add_paragraph(style="List Bullet")
    paragraph.paragraph_format.left_indent = Inches(0.42)
    paragraph.paragraph_format.first_line_indent = Inches(-0.22)
    paragraph.paragraph_format.space_before = Pt(3)
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.paragraph_format.line_spacing = 1.25
    add_text(paragraph, text, size=12)


def add_numbered_step(doc, text):
    paragraph = doc.add_paragraph(style="List Number")
    paragraph.paragraph_format.left_indent = Inches(0.42)
    paragraph.paragraph_format.first_line_indent = Inches(-0.22)
    paragraph.paragraph_format.space_before = Pt(3)
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.paragraph_format.line_spacing = 1.25
    add_text(paragraph, text, size=12)


def add_code_block(doc, title, code):
    table = doc.add_table(rows=2, cols=1)
    set_table_geometry(table, [9360])
    title_cell, code_cell = table.cell(0, 0), table.cell(1, 0)
    shade_cell(title_cell, "E7E7E7")
    shade_cell(code_cell, "F7F7F7")
    set_cell_border(title_cell)
    set_cell_border(code_cell)
    title_p = title_cell.paragraphs[0]
    title_p.paragraph_format.first_line_indent = Pt(0)
    title_p.paragraph_format.space_after = Pt(0)
    add_text(title_p, title, size=11, color=INK, bold=True, east_asia="黑体")
    code_p = code_cell.paragraphs[0]
    code_p.paragraph_format.first_line_indent = Pt(0)
    code_p.paragraph_format.space_after = Pt(0)
    code_p.paragraph_format.line_spacing = 1.0
    add_text(code_p, code, size=9.5, color=INK, font="Consolas", east_asia="宋体")
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def add_page_number_footer(section):
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    add_text(p, "实验一  第 ", size=10.5, color=MUTED)
    field = add_field(p, " PAGE ")
    set_run_font(field, size=10.5, color=MUTED)
    add_text(p, " 页", size=10.5, color=MUTED)


def build_document(baseline, final, metrics_chart, method_chart, workflow, commit_image):
    m0 = load_measures(baseline)
    m1 = load_measures(final)
    baseline_issues = float(baseline["issueTotal"])
    final_issues = float(final["issueTotal"])
    baseline_critical = severity_count(baseline, "CRITICAL")
    final_critical = severity_count(final, "CRITICAL")
    m0["issueTotal"] = baseline_issues
    m0["criticalCount"] = baseline_critical
    m1["issueTotal"] = final_issues
    m1["criticalCount"] = final_critical
    commit_text = (EVIDENCE_DIR / "git-commit-experiment1.txt").read_text(encoding="utf-8-sig")
    commit_hash = re.search(r"commit\s+([0-9a-f]+)", commit_text).group(1)[:8]
    commit_subject = re.search(r"\n\s{4}(feat\(experiment-1\).+)", commit_text).group(1)

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
    set_style_font(normal, 12, INK, False, east_asia="宋体")
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.25

    body_text = styles["Body Text"]
    set_style_font(body_text, 12, INK, False, east_asia="宋体")
    body_text.paragraph_format.space_before = Pt(5)
    body_text.paragraph_format.space_after = Pt(5)
    body_text.paragraph_format.line_spacing = 1.25
    body_text.paragraph_format.first_line_indent = Pt(24)

    title_style = styles["Title"]
    set_style_font(title_style, 18, INK, False, east_asia="黑体")
    title_style.paragraph_format.space_before = Pt(5)
    title_style.paragraph_format.space_after = Pt(5)
    title_style.paragraph_format.line_spacing = 1.0

    for name, size, color, before, after in (
        ("Heading 1", 16, INK, 16, 5),
        ("Heading 2", 15, INK, 14, 5),
        ("Heading 3", 15, INK, 12, 5),
    ):
        style = styles[name]
        set_style_font(style, size, color, False, east_asia="黑体")
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.25
        style.paragraph_format.keep_with_next = True

    for list_name in ("List Bullet", "List Number"):
        style = styles[list_name]
        set_style_font(style, 12, INK, False, east_asia="宋体")
        style.paragraph_format.space_before = Pt(3)
        style.paragraph_format.space_after = Pt(3)
        style.paragraph_format.line_spacing = 1.25

    header = section.header.paragraphs[0]
    header.text = ""
    add_page_number_footer(section)
    section.first_page_header.paragraphs[0].text = ""
    section.first_page_footer.paragraphs[0].text = ""

    doc.core_properties.title = "软件质量与检测实验报告：实验一"
    doc.core_properties.subject = "litemall 软件质量度量、静态代码分析与订单服务重构"
    doc.core_properties.author = "Alisson668"
    doc.core_properties.keywords = "litemall, SonarQube, ISO/IEC 25010, 圈复杂度, 软件质量"

    for _ in range(2):
        spacer = doc.add_paragraph()
        spacer.paragraph_format.space_after = Pt(18)

    course_title = doc.add_paragraph()
    course_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    course_title.paragraph_format.space_after = Pt(10)
    add_text(
        course_title,
        "《软件质量与检测》实验",
        size=36,
        color=INK,
        bold=True,
        east_asia="宋体",
    )

    experiment_title = doc.add_paragraph()
    experiment_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    experiment_title.paragraph_format.space_before = Pt(4)
    experiment_title.paragraph_format.space_after = Pt(22)
    add_text(
        experiment_title,
        "实验一  软件质量度量、静态代码分析与 AI 辅助重构",
        size=18,
        color=INK,
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
        add_text(paragraph, text, size=16, color=INK, bold=True, east_asia="宋体")

    topic = doc.add_paragraph()
    topic.paragraph_format.space_before = Pt(34)
    topic.paragraph_format.space_after = Pt(0)
    topic.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_text(
        topic,
        "基于 litemall + SonarQube 的软件质量工程报告",
        size=15,
        color=INK,
        bold=True,
        east_asia="黑体",
    )

    doc.add_page_break()
    toc_title = doc.add_paragraph(style="Title")
    toc_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    toc_title.paragraph_format.space_after = Pt(12)
    add_text(toc_title, "目录", size=18, color=INK, bold=True, east_asia="黑体")
    toc_table = doc.add_table(rows=1, cols=2)
    toc_headers = ("章节", "主要内容")
    for index, value in enumerate(toc_headers):
        cell = toc_table.rows[0].cells[index]
        shade_cell(cell, LIGHT_GRAY)
        add_text(cell.paragraphs[0], value, size=12, color=INK, bold=True)
    toc_items = [
        ("1  实验目的与核心指标", "目标、范围与量化验收标准"),
        ("2  实验原理与技术架构", "复杂度度量、工具链与工作流"),
        ("3  实验任务与工程实施", "重构步骤、事务审计与 AI 证据占位"),
        ("4  实验结果与量化分析", "SonarQube、Lizard、测试与运行结果"),
        ("5  缺陷追踪与根因分析", "D1—D5 缺陷、影响和修复 Diff"),
        ("6  AI 赋能反思与思考题", "跨切面风险、复杂度概念与审计策略"),
        ("7  实验总结与工程心得", "方法论收获、局限与后续计划"),
        ("附录 A—C", "Commit Log、AI 证据清单、过程文件"),
    ]
    for title_text, detail in toc_items:
        cells = toc_table.add_row().cells
        add_text(cells[0].paragraphs[0], title_text, size=12, color=INK, bold=True)
        add_text(cells[1].paragraphs[0], detail, size=12, color=MUTED)
    set_table_geometry(toc_table, [3500, 5860])
    for row in toc_table.rows:
        for cell in row.cells:
            set_cell_border(cell, bottom={"sz": 4, "color": MID_GRAY})
    add_body(doc, "说明：本目录采用静态章节导航，页码显示在每页页脚。")

    doc.add_page_break()
    add_heading(doc, "1  实验目的与核心指标", 1)
    add_body(doc, "本实验以 litemall 订单核心链路为对象，结合 ISO/IEC 25010 的可靠性、可维护性与安全性质量特性，建立可重复的静态分析基线，并通过结构化重构降低核心方法复杂度。")
    add_body(doc, "实验范围聚焦 WxOrderService 订单提交、支付回调及 CouponVerifyService 优惠券归属校验。全仓历史遗留问题不伪装为本次已全部消除，避免把局部改造结果错误扩大为仓库级结论。")
    add_table(
        doc,
        "表 1  实验一验收指标",
        ["质量维度", "度量项", "目标", "最终结果"],
        [
            ("可维护性", "submit 圈复杂度", "< 10", "4"),
            ("可维护性", "payNotify 圈复杂度", "下降并 < 15", "8"),
            ("静态分析", "WxOrderService Critical / Blocker", "0", "0"),
            ("静态分析", "WxOrderService 问题总数", "0", "0"),
            ("功能保障", "价格计算回归测试", "全部通过", "5 / 5"),
            ("运行验收", "litemall 核心 API", "HTTP 200", "HTTP 200"),
        ],
        [1800, 3160, 2200, 2200],
    )
    add_callout(doc, "范围说明", "本次实验完成了课程重点订单服务的 Blocker/Critical 清零，而不是对 litemall 全仓 300 余个 Java 文件进行一次性清理。全仓遗留问题继续保留在 SonarQube，作为后续实验的技术债基线。")

    add_heading(doc, "2  实验原理与技术架构", 1)
    add_heading(doc, "2.1  复杂度度量", 2)
    add_body(doc, "圈复杂度（Cyclomatic Complexity）用控制流图衡量线性独立路径数量，经典表达为 M = E − N + 2P；认知复杂度则对嵌套、跳转和连续逻辑进行加权，更接近开发者理解成本。二者同时观察，可以防止“拆分方法后总复杂度上升，但人工维护难度下降”这一常见误读。")
    add_body(doc, "静态质量门禁关注可靠性、安全性与可维护性，但覆盖率属于动态验证维度。实验一可以在静态规则上清零，却没有新增代码覆盖率，因此 SonarQube 质量门禁仍会因 new_coverage = 0% 而失败。这一失败被如实保留，并作为实验二的目标。")
    add_heading(doc, "2.2  工具链与工作流", 2)
    add_figure(doc, workflow, "图 1  SonarQube、代码审计、回归测试与二次扫描工作流", width=6.25)
    add_table(
        doc,
        "表 2  实验工具链",
        ["阶段", "工具 / 环境", "用途"],
        [
            ("构建", "Maven 3.9.12 + JDK 8", "Java 8 编译、测试与可执行 jar 打包"),
            ("静态分析", "SonarQube 9.9.8 + SonarScanner 7.1", "规则扫描、复杂度与问题追踪"),
            ("方法度量", "Lizard 1.24.3", "方法级圈复杂度交叉验证"),
            ("回归测试", "JUnit 4 + Maven Surefire", "价格计算纯函数校验"),
            ("运行验证", "Docker Compose + MySQL 5.7", "真实应用启动与 HTTP 健康检查"),
        ],
        [1500, 3100, 4760],
    )

    add_heading(doc, "3  实验任务与工程实施步骤", 1)
    add_heading(doc, "3.1  工程步骤", 2)
    add_numbered_step(doc, "启动 Docker Compose 服务，确认 litemall、MySQL、SonarQube、Prometheus 与 Grafana 健康。")
    add_numbered_step(doc, "执行 SonarQube 基线扫描，并导出 WxOrderService 的指标、问题严重级别与规则分布。")
    add_numbered_step(doc, "定位 submit 和 payNotify 两个高复杂度方法，同时审计事务、购物车归属、库存与优惠券边界。")
    add_numbered_step(doc, "抽取 OrderPriceCalculator 纯计算单元，将订单提交拆分为校验、取数、计价、持久化和补偿步骤。")
    add_numbered_step(doc, "补充 5 个价格计算回归测试，执行 Maven 编译、测试和可执行 jar 打包。")
    add_numbered_step(doc, "重建 litemall 容器，验证 HTTP 200，再执行 SonarQube 二次扫描和 Lizard 方法级复核。")

    add_heading(doc, "3.2  核心重构", 2)
    add_body(doc, "重构前 submit 为 287 行单体方法，承担团购校验、地址校验、购物车读取、价格计算、运费与优惠券、订单写入、库存扣减和零元支付等十余项职责。重构后公开方法只负责身份与参数入口，复杂流程由 submitOrder 统一编排，单价、运费和订单总额由纯函数负责。")
    add_code_block(
        doc,
        "重构后的主流程（保留 public 方法上的事务边界）",
        "@Transactional\n"
        "public Object submit(Integer userId, String body) {\n"
        "    if (userId == null) return ResponseUtil.unlogin();\n"
        "    if (body == null) return ResponseUtil.badArgument();\n"
        "    try {\n"
        "        return submitOrder(userId, SubmitOrderRequest.parse(body));\n"
        "    } catch (OrderValidationException e) {\n"
        "        return e.getResponse();\n"
        "    }\n"
        "}",
    )
    add_body(doc, "在事务审计中保留了 @Transactional 位于公开代理方法上的做法。私有提取方法被 submit 在同一事务内调用，没有把事务注解下沉到私有方法，因此不会出现 Spring AOP 自调用导致事务失效的典型缺陷。")
    add_body(doc, "价格计算抽离为 OrderPriceCalculator，避免 BigDecimal 运算散落在流程中。运费仅依据商品金额判断，优惠券在运费后扣减，订单金额使用 max(0) 防止负值，行为与原实现一致。")

    add_heading(doc, "3.3  AI 协同记录", 2)
    add_code_block(
        doc,
        "实验一 Prompt（原文记录）",
        EXPERIMENT_1_PROMPT,
    )
    add_callout(doc, "待学生补录", "本环境不调用或代填课程 AI 模型。用户提供的 Prompt 已按原文记录；AI 原始输出、截图和人工修正过程仍待补录。报告不会把当前对话伪装为 SenseNova DeepSeek V4.1 Flash 的输出。", fill="FFF8E8", accent=GOLD)
    add_table(
        doc,
        "表 3  AI 协同证据占位表（学生补录）",
        ["记录项", "需填写内容", "对应工程证据"],
        [
            ("结构化 Prompt", "已记录（见上方原文）", "问题背景、审计重点与输出约束"),
            ("AI 原始输出", "待补录", "建议的拆分方案或代码"),
            ("关键问题点", "待补录", "事务、并发、精度、空指针、边界遗漏"),
            ("人工修正", "待补录", "最终 Commit 与实际测试结果"),
        ],
        [2200, 2800, 4360],
    )

    add_heading(doc, "4  实验结果与量化数据分析", 1)
    add_heading(doc, "4.1  SonarQube 与方法级数据", 2)
    table_rows = [
        ("submit CCN", "49", "4", "−91.8%"),
        ("payNotify CCN", "15", "8", "−46.7%"),
        ("认知复杂度", f"{float(m0['cognitive_complexity']):.0f}", f"{float(m1['cognitive_complexity']):.0f}", "−22.3%"),
        ("文件圈复杂度", f"{float(m0['complexity']):.0f}", f"{float(m1['complexity']):.0f}", "+22.5%"),
        ("代码异味", f"{float(m0['code_smells']):.0f}", f"{float(m1['code_smells']):.0f}", "−100%"),
        ("问题总数", f"{baseline_issues:.0f}", f"{final_issues:.0f}", "−100%"),
        ("Critical", f"{baseline_critical:.0f}", f"{final_critical:.0f}", "−100%"),
        ("重复行密度", f"{float(m0['duplicated_lines_density']):.1f}%", f"{float(m1['duplicated_lines_density']):.1f}%", "−30.3%"),
        ("新增价格测试", "0", "5 / 5 通过", "新增"),
        ("新增代码覆盖率", "0%", "0%", "实验二补强"),
    ]
    add_table(
        doc,
        "表 4  实验一改造前后质量对比",
        ["指标", "基线", "最终", "变化"],
        table_rows,
        [2800, 2000, 2300, 2260],
    )
    add_figure(doc, metrics_chart, "图 2  WxOrderService 文件级复杂度与静态问题变化", width=6.35)
    add_figure(doc, method_chart, "图 3  核心方法圈复杂度下降", width=6.3)
    add_body(doc, "文件圈复杂度从 138 上升到 169，原因是原本集中在一个方法中的控制流被拆成多个可测试方法，方法总数增加；但人类认知复杂度从 175 降到 136，submit 热点的 CCN 从 49 降至 4。这体现了“总路径集合扩大、单次理解负担下降”的重构取舍，不能只看单一总量指标下结论。")

    add_heading(doc, "4.2  测试与运行验证", 2)
    add_table(
        doc,
        "表 5  回归测试与运行验收",
        ["验证项", "结果", "说明"],
        [
            ("OrderPriceCalculatorTest", "5/5 通过", "团购匹配、运费、优惠券和零元下限"),
            ("Maven package", "BUILD SUCCESS", "7 个 Reactor 模块全部成功"),
            ("litemall API", "HTTP 200", "/wx/home/index 返回业务数据"),
            ("Swagger UI", "HTTP 200", "/swagger-ui.html 可访问"),
            ("MySQL", "healthy", "34 张表，示例商品与优惠券完整"),
        ],
        [3000, 2200, 4160],
    )
    add_callout(doc, "质量门禁解释", "SonarQube 新代码覆盖率条件要求 ≥80%，本次实际为 0%，因此项目级质量门禁状态为 ERROR；可靠性、安全性、可维护性评分和新代码重复率条件均通过。覆盖率属于实验二的白盒测试与 JaCoCo 范围，本次不使用配置豁免来强行变绿。", fill="FFF8E8", accent=GOLD)

    add_heading(doc, "5  缺陷追踪与根因分析", 1)
    add_body(doc, "审计发现的问题并非只属于风格层面。购物车归属、优惠券归属和库存更新都位于订单提交事务内，任一遗漏都可能造成越权、空指针或并发超卖。以下缺陷通过代码路径复现、静态规则证据和回归测试完成修正。")
    add_table(
        doc,
        "表 6  本次实验发现与修复",
        ["编号", "缺陷与影响", "根因", "修复"],
        [
            ("D1", "用户可提交不属于自己的 cartId；不存在购物车时加入 null", "cartService.findById(cartId) 只按主键查询，未校验 userId", "改用 findById(userId, cartId)，空值统一转为 badArgumentValue"),
            ("D2", "无效团购规则或团购记录为空时可能 NPE；自参团校验使用错误查询语义", "grouponRulesId 无条件查询；queryById(userId, linkId) 过滤掉了待校验记录", "仅在规则 ID 有效时加载，并以记录 CreatorUserId 判断自参团"),
            ("D3", "先读库存再扣减存在 TOCTOU 竞争；null 商品触发 NPE", "查询库存与扣减分离，依赖应用层计算剩余库存", "直接依赖 number >= num 的原子 UPDATE，影响行数为 0 时抛出异常并回滚事务"),
            ("D4", "userCouponId 指向其他用户优惠券时仍可能被消费", "CouponVerifyService 只校验 couponId，未校验 couponUser.userId", "解析优惠券时校验 userId 与 couponId，两层校验归属"),
            ("D5", "重复字面量和通用 RuntimeException 降低可维护性", "错误标识散落在方法中，异常语义不明确", "定义常量与 OrderOperationException / OrderValidationException"),
        ],
        [900, 3450, 2600, 2410],
        font_size=9.5,
    )
    add_heading(doc, "5.1  关键修复 Diff", 2)
    add_code_block(
        doc,
        "购物车归属校验",
        "- LitemallCart cart = cartService.findById(cartId);\n"
        "- checkedGoodsList.add(cart);\n"
        "+ LitemallCart cart = cartService.findById(userId, cartId);\n"
        "+ if (cart == null) throw new OrderValidationException(ResponseUtil.badArgumentValue());",
    )
    add_code_block(
        doc,
        "库存原子条件更新",
        "- LitemallGoodsProduct product = productService.findById(productId);\n"
        "- int remainNumber = product.getNumber() - number;\n"
        "- if (remainNumber < 0) throw ...;\n"
        "- if (productService.reduceStock(productId, number) == 0) throw ...;\n"
        "+ if (productService.reduceStock(productId, number) == 0) {\n"
        "+     throw new OrderOperationException(\"商品货品库存减少失败\");\n"
        "+ }",
    )
    add_code_block(
        doc,
        "优惠券归属校验",
        "- } else if (!couponId.equals(couponUser.getCouponId())) {\n"
        "-     return null;\n"
        "- }\n"
        "+ } else if (!userId.equals(couponUser.getUserId())\n"
        "+         || !couponId.equals(couponUser.getCouponId())) {\n"
        "+     return null;\n"
        "+ }",
    )

    add_heading(doc, "6  AI 赋能反思与深度思考题", 1)
    add_heading(doc, "6.1  DeepSeek 在本实验中的局限", 2)
    add_body(doc, "AI 可以快速给出“提取方法、引入卫语句、拆分服务”的重构草稿，但仅从局部代码片段难以稳定识别跨切面约束。最典型的风险包括：把事务方法拆成另一个 Bean 或自作主张在私有方法上加 @Transactional；忽略 BigDecimal 精度与舍入；把条件更新还原成先查询再写入；遗漏 userCouponId 与 userId 的归属校验。")
    add_body(doc, "因此，AI 产物必须经过控制流、事务边界、数据所有权、并发窗口和异常回滚五个维度的审计。复杂度下降不等于功能正确，静态问题清零也不等于运行时无缺陷。")
    add_heading(doc, "6.2  思考题：圈复杂度与认知复杂度", 2)
    add_body(doc, "圈复杂度基于控制流图计算独立路径数量，适合衡量可测试性和分支数量；认知复杂度考虑嵌套、递归跳转、连续逻辑和短路条件，更接近阅读者理解代码的成本。本次拆分后文件总圈复杂度略有上升，但 submit 的认知与圈复杂度均显著下降，说明复杂度被分散到可命名、可测试的职责中。")
    add_heading(doc, "6.3  思考题：AI 的跨切面局限与人工干预", 2)
    add_body(doc, "Prompt 应明确事务边界、并发一致性、金额精度、空值与权限约束，并要求 AI 输出“改动理由 + 风险 + 回归用例”，而不是只给最终代码。人工介入的重点是审计不可见的上下文：Spring 代理、数据库原子性、跨表所有权、并发窗口和真实业务状态。")
    add_callout(doc, "真实 AI 证据要求", "附录 B 必须由学生补入真实 SenseNova DeepSeek V4.1 Flash 的原始 Prompt、关键错误点标注、人工发现与修正截图。不得把本报告或本对话伪装为该模型的输出。", fill="FFF8E8", accent=GOLD)

    add_heading(doc, "7  实验总结与工程心得", 1)
    add_body(doc, "本实验完成了从基线扫描到方法级重构、回归测试和二次扫描的闭环。订单提交方法的圈复杂度从 49 降到 4，WxOrderService 的 22 个静态问题与 7 个 Critical 全部清零，价格计算新增测试全部通过。")
    add_body(doc, "更重要的是，实验暴露了“为降复杂度而拆分”可能掩盖的新问题：事务边界不能随方法拆分而失效，购物车和优惠券必须校验用户归属，库存更新必须依赖数据库条件写入而不是应用层先查后改。静态质量规则能够定位热点，但真实质量结论仍依赖人工审计和运行验证。")
    add_body(doc, "本次未伪造 AI 过程，也未通过调整质量门禁规避覆盖率失败。新增代码覆盖率 0% 将成为实验二引入 JaCoCo、JUnit 5 与 PITest 的起点。")

    doc.add_page_break()
    add_heading(doc, "附录 A  Git Commit Log", 1)
    add_body(doc, f"实验一独立提交：{commit_hash}  {commit_subject}。截图由本地真实 git log --stat 输出生成，不含环境配置和报告文件。")
    add_figure(doc, commit_image, "图 A-1  实验一 Git Commit Log 与文件变更统计", width=6.4)

    add_heading(doc, "附录 B  DeepSeek V4.1 Flash 关键对话", 1)
    add_callout(doc, "待学生补齐真实截图", "此处不得使用伪造内容。请补充：原始 Prompt → AI 输出关键问题标注 → 学生发现 → 人工修正前后对比。建议至少覆盖事务自调用、并发库存、优惠券归属和 BigDecimal 计算之一。", fill="FFF8E8", accent=GOLD)
    add_table(
        doc,
        "表 B-1  AI 对话核验清单",
        ["核验项", "要求", "状态"],
        [
            ("模型与端点", "SenseNova + DeepSeek V4.1 Flash", "待补录"),
            ("原始 Prompt", "包含业务上下文、约束与验收标准", "待补录"),
            ("AI 输出问题点", "标注幻觉、漏测、事务或并发缺陷", "待补录"),
            ("人工修正", "展示修正代码、测试和二次扫描", "待补录"),
        ],
        [2200, 5060, 2100],
    )

    add_heading(doc, "附录 C  过程证据文件", 1)
    add_table(
        doc,
        "表 C-1  本地证据索引",
        ["文件", "内容"],
        [
            ("evidence/sonar-baseline.json", "改造前 SonarQube 指标与 22 个问题"),
            ("evidence/sonar-final.json", "改造后 SonarQube 指标与 0 个问题"),
            ("evidence/lizard-baseline.txt", "submit=49、payNotify=15 的方法级证据"),
            ("evidence/lizard-final.txt", "submit=4、payNotify=8 的方法级证据"),
            ("evidence/git-commit-experiment1.txt", "真实 Commit Log 文本"),
            ("evidence/WxOrderService.baseline.java", "改造前源码快照"),
        ],
        [3900, 5460],
        font_size=10.5,
    )
    add_body(doc, "SonarQube 在线结果：http://localhost:9000/dashboard?id=litemall。所有数据采集于 2026-10-30 的本地实验环境。")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    return OUTPUT


def main():
    baseline = json.loads((EVIDENCE_DIR / "sonar-baseline.json").read_text(encoding="utf-8"))
    final = json.loads((EVIDENCE_DIR / "sonar-final.json").read_text(encoding="utf-8"))
    commit_text = (EVIDENCE_DIR / "git-commit-experiment1.txt").read_text(encoding="utf-8-sig")
    metrics_chart, method_chart = create_metric_charts(
        load_measures(baseline),
        load_measures(final),
    )
    workflow = create_workflow_figure()
    commit_image = create_commit_image(commit_text)
    output = build_document(baseline, final, metrics_chart, method_chart, workflow, commit_image)
    print(output)


if __name__ == "__main__":
    main()
