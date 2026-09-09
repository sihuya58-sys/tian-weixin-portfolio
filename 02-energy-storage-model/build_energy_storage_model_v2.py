#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
储能电站「谷充峰放」套利收益测算模型 v2.0
新增：IRR/NPV/动态回收期 + 龙卷风图 + 多情景分析
"""

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import LineChart, BarChart, Reference
from openpyxl.chart.series import SeriesLabel, DataPoint
from openpyxl.chart.label import DataLabelList
from openpyxl.utils import get_column_letter

# ============================================================
# 样式常量
# ============================================================
BLUE_FILL = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
LIGHT_BLUE_FILL = PatternFill(start_color="E9F0F8", end_color="E9F0F8", fill_type="solid")
GREEN_FILL = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
YELLOW_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
ORANGE_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
HEADER_FONT = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
TITLE_FONT = Font(name="微软雅黑", size=14, bold=True, color="1F4E79")
SECTION_FONT = Font(name="微软雅黑", size=10, bold=True, color="1F4E79")
PARAM_FONT = Font(name="微软雅黑", size=10)
BOLD_FONT = Font(name="微软雅黑", size=10, bold=True)
RESULT_FONT = Font(name="微软雅黑", size=10, bold=True, color="C00000")
GREEN_FONT = Font(name="微软雅黑", size=10, bold=True, color="375623")
NOTE_FONT = Font(name="微软雅黑", size=9, italic=True, color="808080")
SMALL_FONT = Font(name="微软雅黑", size=9)
THIN_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin")
)
BOTTOM_BORDER = Border(bottom=Side(style="medium"))
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
NUM_MONEY = '#,##0.00'
NUM_PCT = '0.00%'
NUM_INT = '#,##0'
NUM_WAN = '#,##0.00"万元"'


def ac(ws, row, col, value=None, font=PARAM_FONT, fill=None, alignment=CENTER,
       number_format=None, border=None):
    """apply_cell - 所有样式参数使用关键字传递，避免错位"""
    cell = ws.cell(row=row, column=col, value=value)
    if font is not None:
        cell.font = font
    if fill is not None:
        from openpyxl.styles.fills import Fill
        if not isinstance(fill, Fill):
            raise TypeError(f"fill应为Fill类型，实际{type(fill).__name__} at row={row},col={col}")
        cell.fill = fill
    if alignment is not None:
        cell.alignment = alignment
    if number_format is not None:
        cell.number_format = number_format
    if border is not None:
        cell.border = border
    return cell


def set_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def section_header(ws, row, text, ncols=9):
    """写入深蓝色section标题行"""
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    ac(ws, row, 1, text, font=HEADER_FONT, fill=HEADER_FILL, alignment=CENTER)
    for c in range(2, ncols + 1):
        ws.cell(row=row, column=c).fill = HEADER_FILL
        ws.cell(row=row, column=c).font = HEADER_FONT
    ws.row_dimensions[row].height = 24


def sub_header(ws, row, text):
    """写入小节标题"""
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    ac(ws, row, 1, text, font=SECTION_FONT, alignment=LEFT)


def param_row(ws, row, label, value, unit_note, is_pct=False, is_int=False):
    """写入一行输入参数（蓝色背景）"""
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    ac(ws, row, 1, label, font=PARAM_FONT, fill=BLUE_FILL, alignment=LEFT, border=THIN_BORDER)
    if value is not None:
        fmt = NUM_PCT if is_pct else (NUM_INT if is_int else NUM_MONEY)
        ac(ws, row, 3, value, font=PARAM_FONT, fill=BLUE_FILL, alignment=CENTER,
           number_format=fmt, border=THIN_BORDER)
    ac(ws, row, 5, unit_note, font=NOTE_FONT, alignment=LEFT)
    ws.merge_cells(start_row=row, start_column=5, end_row=row, end_column=7)


def param_formula(ws, row, label, formula, unit_note, fmt=NUM_MONEY):
    """写入一行公式参数（蓝色背景，值为公式）"""
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    ac(ws, row, 1, label, font=PARAM_FONT, fill=BLUE_FILL, alignment=LEFT, border=THIN_BORDER)
    ac(ws, row, 3, formula, font=PARAM_FONT, fill=BLUE_FILL, alignment=CENTER,
       number_format=fmt, border=THIN_BORDER)
    ac(ws, row, 5, unit_note, font=NOTE_FONT, alignment=LEFT)
    ws.merge_cells(start_row=row, start_column=5, end_row=row, end_column=7)


# ============================================================
# Python端NPV/IRR计算（用于龙卷风图预计算）
# ============================================================
def calc_financials(capacity_mwh, peak_price, valley_price, rte, cycles_per_year,
                    degradation, invest_per_wh, om_rate, discount_rate, years=10):
    """计算NPV和近似IRR"""
    cap_kwh = capacity_mwh * 1000
    eta_chg = rte ** 0.5
    eta_dis = rte ** 0.5
    investment = capacity_mwh * 1_000_000 * invest_per_wh / 10000  # 万元

    charge_cost_1 = valley_price * cap_kwh / eta_chg / 10000  # 万元/次
    discharge_rev_1 = peak_price * cap_kwh * eta_dis / 10000  # 万元/次
    profit_per_cycle_1 = discharge_rev_1 - charge_cost_1
    annual_gross_1 = profit_per_cycle_1 * cycles_per_year
    om_annual = investment * om_rate

    npv = -investment
    cap_factor = 1.0
    cashflows = [-investment]
    for yr in range(1, years + 1):
        cf = annual_gross_1 * cap_factor - om_annual
        npv += cf / ((1 + discount_rate) ** yr)
        cashflows.append(cf)
        cap_factor *= (1 - degradation)

    # 近似IRR
    irr_guess = 0.10
    for _ in range(100):
        npv_at_guess = sum(cf / ((1 + irr_guess) ** t) for t, cf in enumerate(cashflows))
        d_npv = sum(-t * cf / ((1 + irr_guess) ** (t + 1)) for t, cf in enumerate(cashflows))
        if abs(d_npv) < 1e-9:
            break
        irr_guess -= npv_at_guess / d_npv
        if abs(npv_at_guess) < 0.01:
            break

    # 动态回收期
    cum_dcf = -investment
    payback_yr = None
    for yr in range(1, years + 1):
        dcf = cashflows[yr] / ((1 + discount_rate) ** yr)
        cum_dcf += dcf
        if cum_dcf >= 0 and payback_yr is None:
            payback_yr = yr - 1 + (cum_dcf - dcf) / dcf if dcf != 0 else yr

    return {
        'npv': npv,
        'irr': irr_guess,
        'payback': payback_yr,
        'investment': investment,
        'annual_gross_1': annual_gross_1,
        'om_annual': om_annual,
    }


# ============================================================
# 基础参数
# ============================================================
BASE = {
    'peak': 1.20, 'valley': 0.30, 'capacity': 100, 'rte': 0.90,
    'cycles_per_year': 330, 'degradation': 0.02, 'invest_per_wh': 1.80,
    'om_rate': 0.02, 'discount_rate': 0.08, 'years': 10,
}

# 预计算基准财务指标
base_fin = calc_financials(capacity_mwh=BASE['capacity'], peak_price=BASE['peak'],
    valley_price=BASE['valley'], rte=BASE['rte'], cycles_per_year=BASE['cycles_per_year'],
    degradation=BASE['degradation'], invest_per_wh=BASE['invest_per_wh'],
    om_rate=BASE['om_rate'], discount_rate=BASE['discount_rate'])

# 龙卷风图数据：每个变量的低/高值对应的NPV
tornado_vars = []

# 1. 峰谷价差 ±20%
for pct in [-0.20, 0.20]:
    spread = BASE['peak'] - BASE['valley']
    new_spread = spread * (1 + pct)
    new_peak = BASE['valley'] + new_spread
    fin = calc_financials(capacity_mwh=BASE['capacity'], peak_price=new_peak,
                          valley_price=BASE['valley'], rte=BASE['rte'],
                          cycles_per_year=BASE['cycles_per_year'], degradation=BASE['degradation'],
                          invest_per_wh=BASE['invest_per_wh'], om_rate=BASE['om_rate'],
                          discount_rate=BASE['discount_rate'])
    tornado_vars.append(('峰谷价差', pct, new_spread, fin['npv'], fin['irr']))

# 2. 充放电效率 84%~96%
for rte in [0.84, 0.96]:
    fin = calc_financials(capacity_mwh=BASE['capacity'], peak_price=BASE['peak'],
                          valley_price=BASE['valley'], rte=rte,
                          cycles_per_year=BASE['cycles_per_year'], degradation=BASE['degradation'],
                          invest_per_wh=BASE['invest_per_wh'], om_rate=BASE['om_rate'],
                          discount_rate=BASE['discount_rate'])
    tornado_vars.append(('充放电效率', rte - BASE['rte'], rte, fin['npv'], fin['irr']))

# 3. 单位投资成本 ±15%
for pct in [-0.15, 0.15]:
    inv = BASE['invest_per_wh'] * (1 + pct)
    fin = calc_financials(capacity_mwh=BASE['capacity'], peak_price=BASE['peak'],
                          valley_price=BASE['valley'], rte=BASE['rte'],
                          cycles_per_year=BASE['cycles_per_year'], degradation=BASE['degradation'],
                          invest_per_wh=inv, om_rate=BASE['om_rate'],
                          discount_rate=BASE['discount_rate'])
    tornado_vars.append(('单位投资成本', pct, inv, fin['npv'], fin['irr']))

# 4. 折现率 5%~11%
for dr in [0.05, 0.11]:
    fin = calc_financials(capacity_mwh=BASE['capacity'], peak_price=BASE['peak'],
                          valley_price=BASE['valley'], rte=BASE['rte'],
                          cycles_per_year=BASE['cycles_per_year'], degradation=BASE['degradation'],
                          invest_per_wh=BASE['invest_per_wh'], om_rate=BASE['om_rate'],
                          discount_rate=dr)
    tornado_vars.append(('折现率', dr - BASE['discount_rate'], dr, fin['npv'], fin['irr']))

# 5. 年衰减率 1%~3%
for deg in [0.01, 0.03]:
    fin = calc_financials(capacity_mwh=BASE['capacity'], peak_price=BASE['peak'],
                          valley_price=BASE['valley'], rte=BASE['rte'],
                          cycles_per_year=BASE['cycles_per_year'], degradation=deg,
                          invest_per_wh=BASE['invest_per_wh'], om_rate=BASE['om_rate'],
                          discount_rate=BASE['discount_rate'])
    tornado_vars.append(('年衰减率', deg - BASE['degradation'], deg, fin['npv'], fin['irr']))

# 6. 年运营天数 ±10%
for pct in [-0.10, 0.10]:
    cyc = BASE['cycles_per_year'] * (1 + pct)
    fin = calc_financials(capacity_mwh=BASE['capacity'], peak_price=BASE['peak'],
                          valley_price=BASE['valley'], rte=BASE['rte'],
                          cycles_per_year=cyc, degradation=BASE['degradation'],
                          invest_per_wh=BASE['invest_per_wh'], om_rate=BASE['om_rate'],
                          discount_rate=BASE['discount_rate'])
    tornado_vars.append(('年运营天数', pct, cyc, fin['npv'], fin['irr']))

# 情景分析预计算
scenarios = {}
for name, adj in [
    ('乐观', {'peak': 1.32, 'valley': 0.27, 'rte': 0.93, 'invest_per_wh': 1.50, 'degradation': 0.015, 'cycles_per_year': 350, 'discount_rate': 0.06}),
    ('基准', {'peak': 1.20, 'valley': 0.30, 'rte': 0.90, 'invest_per_wh': 1.80, 'degradation': 0.02, 'cycles_per_year': 330, 'discount_rate': 0.08}),
    ('悲观', {'peak': 1.08, 'valley': 0.33, 'rte': 0.86, 'invest_per_wh': 2.10, 'degradation': 0.025, 'cycles_per_year': 300, 'discount_rate': 0.10}),
]:
    fin = calc_financials(
        capacity_mwh=BASE['capacity'], peak_price=adj['peak'], valley_price=adj['valley'],
        rte=adj['rte'], cycles_per_year=adj['cycles_per_year'],
        degradation=adj['degradation'], invest_per_wh=adj['invest_per_wh'],
        om_rate=BASE['om_rate'], discount_rate=adj['discount_rate'])
    scenarios[name] = {**adj, **fin}

print("Base NPV:", round(base_fin['npv'], 2))
print("Base IRR:", round(base_fin['irr'] * 100, 2), "%")
print("Scenarios:", {k: f"NPV={v['npv']:.0f}, IRR={v['irr']*100:.1f}%" for k, v in scenarios.items()})

# ============================================================
# 创建工作簿
# ============================================================
wb = openpyxl.Workbook()
wb.calculation.calcMode = 'auto'
wb.calculation.fullCalcOnLoad = True

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Sheet 1: 测算主页
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
ws1 = wb.active
ws1.title = "测算主页"
ws1.sheet_properties.tabColor = "1F4E79"
set_widths(ws1, [22, 18, 18, 22, 18, 18, 18, 18])

# 标题
ws1.merge_cells("A1:H1")
ac(ws1, 1, 1, "储能电站「谷充峰放」套利收益测算模型 v2.0", font=TITLE_FONT, alignment=CENTER)
ws1.row_dimensions[1].height = 30
ws1.merge_cells("A2:H2")
ac(ws1, 2, 1, "基于陕西省一般工商业分时电价  |  含IRR/NPV/多维度敏感性分析", font=NOTE_FONT, alignment=CENTER)

# === 输入参数区 ===
section_header(ws1, 4, "▎输入参数（修改蓝色区域数值，所有结果自动更新）", 8)

# -- 电价参数 --
r = 6
sub_header(ws1, r, "【电价参数】")
param_row(ws1, 8, "峰段电价（元/kWh）", 1.20, "陕西一般工商业峰段")
param_row(ws1, 9, "谷段电价（元/kWh）", 0.30, "陕西一般工商业谷段")
param_row(ws1, 10, "平时段电价（元/kWh）", 0.65, "参考值·平段不参与套利")
param_formula(ws1, 11, "峰谷价差（元/kWh）", "=B8-B9", "=峰段-谷段，自动计算")

# -- 储能系统参数 --
r = 13
sub_header(ws1, r, "【储能系统参数】")
param_row(ws1, 15, "额定容量（MWh）", 100, "交流侧可用容量", is_int=True)
param_row(ws1, 16, "充放电综合效率（RTE）", 0.90, "往返效率=放电量/充电量", is_pct=True)
param_formula(ws1, 17, "  其中：充电效率", "=SQRT(B16)", "=√RTE，自动计算", NUM_PCT)
param_formula(ws1, 18, "  其中：放电效率", "=SQRT(B16)", "=√RTE，自动计算", NUM_PCT)
param_row(ws1, 19, "放电深度（DoD）", 0.95, "实际可用容量比例", is_pct=True)
param_row(ws1, 20, "循环寿命（次）", 5000, "至容量衰减至80%", is_int=True)
param_row(ws1, 21, "年容量衰减率", 0.02, "日历+循环老化综合", is_pct=True)

# -- 运营参数 --
r = 23
sub_header(ws1, r, "【运营参数】")
param_row(ws1, 25, "每日循环次数", 1, "谷充峰放=1次完整循环", is_int=True)
param_row(ws1, 26, "年运营天数", 330, "扣除检修停机约35天", is_int=True)
param_formula(ws1, 27, "年循环次数", "=B25*B26", "=每日次数×年天数", NUM_INT)
param_row(ws1, 28, "项目运营年限", 10, "测算周期", is_int=True)

# -- 投资与财务参数 --
r = 30
sub_header(ws1, r, "【投资与财务参数】")
param_row(ws1, 32, "单位投资成本（元/Wh）", 1.80, "行业区间1.5-2.0元/Wh")
param_formula(ws1, 33, "初始总投资（万元）", "=B15*B32*100", "=容量MWh×投资元/Wh×100")
param_row(ws1, 34, "年运维费率", 0.02, "占初始投资比例", is_pct=True)
param_row(ws1, 35, "折现率（WACC）", 0.08, "加权平均资本成本", is_pct=True)
param_row(ws1, 36, "企业所得税率", 0.25, "用于净利润计算·可设为0忽略", is_pct=True)

# === 单次循环测算 ===
section_header(ws1, 38, "▎单次循环收益测算（第1年，无衰减，以100MWh容量为基准）", 8)

calc_rows = [
    ("有效可用容量（kWh）", "=B15*1000*B19", "额定容量×1000×DoD", NUM_INT, "kWh"),
    ("充电量·电网取电（kWh）", "=B40/B17", "有效容量÷充电效率（含损耗）", NUM_INT, "kWh"),
    ("充电成本（万元）", "=B41*B9/10000", "充电量×谷段电价÷10000", NUM_MONEY, "万元"),
    ("放电量·上网售电（kWh）", "=B40*B18", "有效容量×放电效率（含损耗）", NUM_INT, "kWh"),
    ("放电收入（万元）", "=B43*B8/10000", "放电量×峰段电价÷10000", NUM_MONEY, "万元"),
    ("单次循环毛利（万元）", "=B44-B42", "放电收入-充电成本", NUM_MONEY, "万元"),
    ("单次循环毛利率", "=B45/B44", "毛利÷收入", NUM_PCT, "%"),
]
for i, (label, formula, note, fmt, unit) in enumerate(calc_rows):
    row = 40 + i
    ws1.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    ac(ws1, row, 1, label, font=PARAM_FONT, fill=LIGHT_BLUE_FILL, alignment=LEFT, border=THIN_BORDER)
    ws1.merge_cells(start_row=row, start_column=3, end_row=row, end_column=4)
    ac(ws1, row, 3, formula, font=NOTE_FONT, alignment=LEFT, border=THIN_BORDER)
    is_result = any(kw in label for kw in ['成本', '收入', '毛利'])
    ac(ws1, row, 5, formula, font=RESULT_FONT if is_result else BOLD_FONT, alignment=CENTER,
       number_format=fmt, border=THIN_BORDER)
    ac(ws1, row, 6, unit, font=PARAM_FONT, alignment=CENTER, border=THIN_BORDER)
    ws1.merge_cells(start_row=row, start_column=7, end_row=row, end_column=8)
    ac(ws1, row, 7, note, font=NOTE_FONT, alignment=LEFT, border=THIN_BORDER)

# === 年度收益汇总 ===
section_header(ws1, 48, "▎年度收益汇总 & 核心财务指标（第1年为基准）", 8)

summary_rows = [
    ("年循环次数（次）", "=B27", "谷充峰放循环", NUM_INT, "次"),
    ("年充电总成本（万元）", "=B42*B49", "单次成本×循环次数", NUM_MONEY, "万元"),
    ("年放电总收入（万元）", "=B44*B49", "单次收入×循环次数", NUM_MONEY, "万元"),
    ("年毛利（万元）", "=B51-B50", "收入-成本", NUM_MONEY, "万元"),
    ("年运维费用（万元）", "=B33*B34", "投资×运维费率", NUM_MONEY, "万元"),
    ("年税前利润（万元）", "=B52-B53", "毛利-运维费", NUM_MONEY, "万元"),
    ("所得税（万元）", "=B54*B36", "税前利润×税率", NUM_MONEY, "万元"),
    ("年净利润（万元）", "=B54-B55", "税前利润-所得税", NUM_MONEY, "万元"),
]
for i, (label, formula, note, fmt, unit) in enumerate(summary_rows):
    row = 49 + i
    ws1.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    ac(ws1, row, 1, label, font=PARAM_FONT, fill=LIGHT_BLUE_FILL, alignment=LEFT, border=THIN_BORDER)
    ws1.merge_cells(start_row=row, start_column=3, end_row=row, end_column=4)
    ac(ws1, row, 3, formula, font=NOTE_FONT, alignment=LEFT, border=THIN_BORDER)
    ac(ws1, row, 5, formula, font=RESULT_FONT, alignment=CENTER, number_format=fmt, border=THIN_BORDER)
    ac(ws1, row, 6, unit, font=PARAM_FONT, alignment=CENTER, border=THIN_BORDER)
    ws1.merge_cells(start_row=row, start_column=7, end_row=row, end_column=8)
    ac(ws1, row, 7, note, font=NOTE_FONT, alignment=LEFT, border=THIN_BORDER)

# 核心财务指标（引用现金流sheet）
section_header(ws1, 59, "▎核心财务指标（详见「现金流与IRR」工作表）", 8)
kpi_rows = [
    ("10年累计净利润（万元）", "=现金流与IRR!F19", "净利润总和"),
    ("项目IRR（内部收益率）", "=现金流与IRR!F21", "使NPV=0的折现率"),
    ("NPV·净现值（万元）", "=现金流与IRR!F22", f"折现率={BASE['discount_rate']*100:.0f}%下的净现值"),
    ("静态投资回收期（年）", "=B33/(B52-B53)", "总投资÷年税前利润·粗略估算"),
    ("动态投资回收期（年）", "=现金流与IRR!F25", "考虑折现的回收期"),
]
for i, (label, formula, note) in enumerate(kpi_rows):
    row = 60 + i
    ws1.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    ac(ws1, row, 1, label, font=BOLD_FONT, fill=GREEN_FILL, alignment=LEFT, border=THIN_BORDER)
    ws1.merge_cells(start_row=row, start_column=3, end_row=row, end_column=4)
    ac(ws1, row, 3, formula, font=NOTE_FONT, alignment=LEFT, border=THIN_BORDER)
    fmt = NUM_PCT if 'IRR' in label else ('0.0' if '回收期' in label else NUM_MONEY)
    ac(ws1, row, 5, formula, font=RESULT_FONT, alignment=CENTER, number_format=fmt, border=THIN_BORDER)
    ws1.merge_cells(start_row=row, start_column=7, end_row=row, end_column=8)
    ac(ws1, row, 7, note, font=NOTE_FONT, alignment=LEFT, border=THIN_BORDER)

ws1.freeze_panes = "A4"

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Sheet 2: 逐年收益表
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
ws2 = wb.create_sheet("逐年收益表")
ws2.sheet_properties.tabColor = "2E75B6"
set_widths(ws2, [10, 16, 16, 16, 16, 16, 16, 16, 16])

ws2.merge_cells("A1:I1")
ac(ws2, 1, 1, "10年逐年收益测算明细", font=TITLE_FONT, alignment=CENTER)
ws2.row_dimensions[1].height = 28
ws2.merge_cells("A2:I2")
ac(ws2, 2, 1, "考虑容量衰减 + 充放电效率不变 + 电价不变", font=NOTE_FONT, alignment=CENTER)

headers = ["年份", "有效容量\n(MWh)", "有效容量\n(kWh)", "单次充电\n成本(万元)",
           "单次放电\n收入(万元)", "单次毛利\n(万元)", "年循环\n次数", "年度毛利\n(万元)", "累计毛利\n(万元)"]
r = 4
for ci, h in enumerate(headers, 1):
    ac(ws2, r, ci, h, font=HEADER_FONT, fill=HEADER_FILL, alignment=CENTER, border=THIN_BORDER)
ws2.row_dimensions[r].height = 40

for year in range(1, 11):
    row = 4 + year
    ac(ws2, row, 1, f"第{year}年", font=PARAM_FONT, alignment=CENTER, border=THIN_BORDER)

    # B: 有效容量 MWh = 额定×DoD×(1-衰减)^(n-1)
    if year == 1:
        ac(ws2, row, 2, "=测算主页!B15*测算主页!B19", font=BOLD_FONT, alignment=CENTER,
           number_format='#,##0.00', border=THIN_BORDER)
    else:
        ac(ws2, row, 2, f"=B{row-1}*(1-测算主页!B21)", font=BOLD_FONT, alignment=CENTER,
           number_format='#,##0.00', border=THIN_BORDER)

    # C: 有效容量 kWh = B×1000
    ac(ws2, row, 3, f"=B{row}*1000", font=BOLD_FONT, alignment=CENTER,
       number_format='#,##0', border=THIN_BORDER)

    # D: 单次充电成本 = 谷价 × 容量kWh / 充电效率 / 10000
    ac(ws2, row, 4, f"=测算主页!B9*C{row}/测算主页!B17/10000", font=PARAM_FONT, alignment=CENTER,
       number_format=NUM_MONEY, border=THIN_BORDER)

    # E: 单次放电收入 = 峰价 × 容量kWh × 放电效率 / 10000
    ac(ws2, row, 5, f"=测算主页!B8*C{row}*测算主页!B18/10000", font=PARAM_FONT, alignment=CENTER,
       number_format=NUM_MONEY, border=THIN_BORDER)

    # F: 单次毛利
    ac(ws2, row, 6, f"=E{row}-D{row}", font=BOLD_FONT, alignment=CENTER,
       number_format=NUM_MONEY, border=THIN_BORDER)

    # G: 年循环次数
    ac(ws2, row, 7, "=测算主页!B27", font=PARAM_FONT, alignment=CENTER,
       number_format=NUM_INT, border=THIN_BORDER)

    # H: 年度毛利
    ac(ws2, row, 8, f"=F{row}*G{row}", font=RESULT_FONT, alignment=CENTER,
       number_format=NUM_MONEY, border=THIN_BORDER)

    # I: 累计毛利
    if year == 1:
        ac(ws2, row, 9, f"=H{row}", font=RESULT_FONT, alignment=CENTER,
           number_format=NUM_MONEY, border=THIN_BORDER)
    else:
        ac(ws2, row, 9, f"=I{row-1}+H{row}", font=RESULT_FONT, alignment=CENTER,
           number_format=NUM_MONEY, border=THIN_BORDER)

# 合计行
sum_row = 15
ac(ws2, sum_row, 1, "10年合计", font=BOLD_FONT, fill=LIGHT_BLUE_FILL, alignment=CENTER, border=THIN_BORDER)
ac(ws2, sum_row, 8, "=SUM(H6:H15)", font=BOLD_FONT, fill=LIGHT_BLUE_FILL, alignment=CENTER,
   number_format=NUM_MONEY, border=THIN_BORDER)

# 图表：年度收益 + 累计收益
chart1 = BarChart()
chart1.type = "col"
chart1.style = 10
chart1.title = "逐年毛利与累计毛利"
chart1.y_axis.title = "万元"
chart1.width = 22
chart1.height = 14
data_bar = Reference(ws2, min_col=8, min_row=4, max_row=14, max_col=8)
cats = Reference(ws2, min_col=1, min_row=5, max_row=14)
chart1.add_data(data_bar, titles_from_data=True)
chart1.set_categories(cats)
chart1.series[0].title = SeriesLabel(v="年度毛利")
chart1.series[0].graphicalProperties.solidFill = "2E75B6"

chart1b = LineChart()
data_line = Reference(ws2, min_col=9, min_row=4, max_row=14, max_col=9)
chart1b.add_data(data_line, titles_from_data=True)
chart1b.series[0].title = SeriesLabel(v="累计毛利")
chart1b.series[0].graphicalProperties.line.solidFill = "C00000"
chart1b.y_axis.axId = 200
chart1 += chart1b
chart1.legend.position = 'b'
ws2.add_chart(chart1, "A18")

# 容量衰减曲线
chart2 = LineChart()
chart2.title = "有效容量衰减曲线（含DoD）"
chart2.y_axis.title = "MWh"
chart2.width = 22
chart2.height = 12
chart2.style = 10
data_cap = Reference(ws2, min_col=2, min_row=4, max_row=14, max_col=2)
chart2.add_data(data_cap, titles_from_data=True)
chart2.set_categories(cats)
chart2.series[0].graphicalProperties.line.solidFill = "548235"
chart2.legend.position = 'b'
ws2.add_chart(chart2, "A34")

ws2.freeze_panes = "A5"

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Sheet 3: 现金流与IRR
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
ws3 = wb.create_sheet("现金流与IRR")
ws3.sheet_properties.tabColor = "375623"
set_widths(ws3, [12, 18, 18, 18, 18, 18, 18, 18])

ws3.merge_cells("A1:H1")
ac(ws3, 1, 1, "全周期现金流分析：IRR / NPV / 投资回收期", font=TITLE_FONT, alignment=CENTER)
ws3.row_dimensions[1].height = 28
ws3.merge_cells("A2:H2")
ac(ws3, 2, 1, "自由现金流 = 毛利 - 运维费 - 所得税  |  折现率引用自测算主页", font=NOTE_FONT, alignment=CENTER)

# 现金流表
cf_headers = ["年份", "年度毛利\n(万元)", "运维费\n(万元)", "税前利润\n(万元)",
              "所得税\n(万元)", "自由现金流\n(万元)", "折现因子", "折现现金流\n(万元)"]
r = 4
for ci, h in enumerate(cf_headers, 1):
    ac(ws3, r, ci, h, font=HEADER_FONT, fill=HEADER_FILL, alignment=CENTER, border=THIN_BORDER)
ws3.row_dimensions[r].height = 36

# Year 0: 初始投资
ac(ws3, 5, 1, "第0年（投资）", font=BOLD_FONT, alignment=CENTER, border=THIN_BORDER)
ac(ws3, 5, 2, 0, font=PARAM_FONT, alignment=CENTER, number_format=NUM_MONEY, border=THIN_BORDER)
ac(ws3, 5, 3, 0, font=PARAM_FONT, alignment=CENTER, number_format=NUM_MONEY, border=THIN_BORDER)
ac(ws3, 5, 4, 0, font=PARAM_FONT, alignment=CENTER, number_format=NUM_MONEY, border=THIN_BORDER)
ac(ws3, 5, 5, 0, font=PARAM_FONT, alignment=CENTER, number_format=NUM_MONEY, border=THIN_BORDER)
ac(ws3, 5, 6, "=-测算主页!B33", font=RESULT_FONT, alignment=CENTER, number_format=NUM_MONEY, border=THIN_BORDER)
ac(ws3, 5, 7, 1.0, font=PARAM_FONT, alignment=CENTER, number_format='0.0000', border=THIN_BORDER)
ac(ws3, 5, 8, "=F5*G5", font=RESULT_FONT, alignment=CENTER, number_format=NUM_MONEY, border=THIN_BORDER)

# Years 1-10
for year in range(1, 11):
    row = 5 + year
    ac(ws3, row, 1, f"第{year}年", font=PARAM_FONT, alignment=CENTER, border=THIN_BORDER)

    # B: 年度毛利 from逐年收益表 (column H)
    ac(ws3, row, 2, f"=逐年收益表!H{4+year}", font=PARAM_FONT, alignment=CENTER,
       number_format=NUM_MONEY, border=THIN_BORDER)

    # C: 运维费
    ac(ws3, row, 3, "=测算主页!B33*测算主页!B34", font=PARAM_FONT, alignment=CENTER,
       number_format=NUM_MONEY, border=THIN_BORDER)

    # D: 税前利润
    ac(ws3, row, 4, f"=B{row}-C{row}", font=PARAM_FONT, alignment=CENTER,
       number_format=NUM_MONEY, border=THIN_BORDER)

    # E: 所得税
    ac(ws3, row, 5, f"=D{row}*测算主页!B36", font=PARAM_FONT, alignment=CENTER,
       number_format=NUM_MONEY, border=THIN_BORDER)

    # F: 自由现金流
    ac(ws3, row, 6, f"=D{row}-E{row}", font=RESULT_FONT, alignment=CENTER,
       number_format=NUM_MONEY, border=THIN_BORDER)

    # G: 折现因子 = 1/(1+r)^t
    ac(ws3, row, 7, f"=1/(1+测算主页!B35)^{year}", font=PARAM_FONT, alignment=CENTER,
       number_format='0.0000', border=THIN_BORDER)

    # H: 折现现金流
    ac(ws3, row, 8, f"=F{row}*G{row}", font=RESULT_FONT, alignment=CENTER,
       number_format=NUM_MONEY, border=THIN_BORDER)

# 合计
sr = 16
ac(ws3, sr, 1, "合计", font=BOLD_FONT, fill=LIGHT_BLUE_FILL, alignment=CENTER, border=THIN_BORDER)
for col in [2, 3, 4, 5, 6, 8]:
    col_letter = get_column_letter(col)
    ac(ws3, sr, col, f"=SUM({col_letter}6:{col_letter}15)", font=BOLD_FONT, fill=LIGHT_BLUE_FILL,
       alignment=CENTER, number_format=NUM_MONEY, border=THIN_BORDER)

# 财务指标
r = 18
ac(ws3, r, 1, "财务指标", font=HEADER_FONT, fill=HEADER_FILL, alignment=CENTER, border=THIN_BORDER)
ws3.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
ac(ws3, r, 3, "计算公式", font=HEADER_FONT, fill=HEADER_FILL, alignment=CENTER, border=THIN_BORDER)
ws3.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
ac(ws3, r, 6, "数值", font=HEADER_FONT, fill=HEADER_FILL, alignment=CENTER, border=THIN_BORDER)
ws3.merge_cells(start_row=r, start_column=6, end_row=r, end_column=8)

kpi_data = [
    ("累计自由现金流（万元）", "=SUM(F6:F15)", "Σ(年自由现金流)，不含初始投资"),
    ("初始总投资（万元）", "=测算主页!B33", "CAPEX"),
    ("IRR·内部收益率", "=IRR(F5:F15,0.1)", "使NPV=0的折现率，Excel IRR函数"),
    ("NPV·净现值（万元）", "=NPV(测算主页!B35,F6:F15)+F5", "折现现金流总和，含初始投资"),
    ("NPV不含投资（万元）", "=NPV(测算主页!B35,F6:F15)", "运营期折现现金流"),
    ("静态回收期（年）", "=测算主页!B33/AVERAGE(F6:F15)", "总投资÷平均年现金流"),
    ("动态回收期（年）", "=B23/(B25/B33)", "近似：投资÷年均折现现金流"),
]
for i, (label, formula, note) in enumerate(kpi_data):
    row = 19 + i
    ws3.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    ac(ws3, row, 1, label, font=BOLD_FONT, fill=GREEN_FILL if i >= 2 else LIGHT_BLUE_FILL,
       alignment=LEFT, border=THIN_BORDER)
    ws3.merge_cells(start_row=row, start_column=3, end_row=row, end_column=5)
    ac(ws3, row, 3, formula, font=NOTE_FONT, alignment=LEFT, border=THIN_BORDER)
    fmt = NUM_PCT if 'IRR' in label else ('0.0' if '回收期' in label else NUM_MONEY)
    fnt = RESULT_FONT if i >= 2 else BOLD_FONT
    ws3.merge_cells(start_row=row, start_column=6, end_row=row, end_column=8)
    ac(ws3, row, 6, formula, font=fnt, alignment=CENTER, number_format=fmt, border=THIN_BORDER)

# 折现现金流累计图
chart3 = LineChart()
chart3.title = "累计折现现金流曲线"
chart3.y_axis.title = "万元"
chart3.width = 22
chart3.height = 13
chart3.style = 10

# 构建累计折现现金流
ac(ws3, 28, 1, "累计DCF", font=NOTE_FONT)
ac(ws3, 5, 9, "累计DCF\n(万元)", font=HEADER_FONT, fill=HEADER_FILL, alignment=CENTER, border=THIN_BORDER)
for year in range(0, 11):
    row = 5 + year
    if year == 0:
        ac(ws3, row, 9, f"=H{row}", font=PARAM_FONT, alignment=CENTER,
           number_format=NUM_MONEY, border=THIN_BORDER)
    else:
        ac(ws3, row, 9, f"=I{row-1}+H{row}", font=RESULT_FONT, alignment=CENTER,
           number_format=NUM_MONEY, border=THIN_BORDER)

data_cf = Reference(ws3, min_col=9, min_row=4, max_row=15, max_col=9)
cats_cf = Reference(ws3, min_col=1, min_row=5, max_row=15)
chart3.add_data(data_cf, titles_from_data=True)
chart3.set_categories(cats_cf)
chart3.series[0].graphicalProperties.line.solidFill = "375623"
chart3.legend.position = 'b'
ws3.add_chart(chart3, "A29")

ws3.freeze_panes = "A5"

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Sheet 4: 敏感性分析
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
ws4 = wb.create_sheet("敏感性分析")
ws4.sheet_properties.tabColor = "C55A11"
set_widths(ws4, [20, 16, 16, 16, 16, 16, 14, 14, 16, 16])

ws4.merge_cells("A1:J1")
ac(ws4, 1, 1, "多维度敏感性分析：龙卷风图 + 价差×效率矩阵 + 蜘蛛图", font=TITLE_FONT, alignment=CENTER)
ws4.row_dimensions[1].height = 28

# === 龙卷风图 ===
section_header(ws4, 3, "▎龙卷风图：各变量对NPV的影响幅度（基于当前基准参数预计算）", 10)
ac(ws4, 4, 1, "说明：以下为Python端基于当前测算主页参数预计算的结果。修改基准参数后需重新运行脚本更新。",
   font=NOTE_FONT, alignment=LEFT)
ws4.merge_cells("A4:J4")

tornado_headers = ["变量", "低值", "高值", "NPV@低值\n(万元)", "NPV@高值\n(万元)",
                   "NPV变化\n(万元)", "NPV变化%", "IRR@低值", "IRR@高值", "IRR变化"]
r = 6
for ci, h in enumerate(tornado_headers, 1):
    ac(ws4, r, ci, h, font=HEADER_FONT, fill=HEADER_FILL, alignment=CENTER, border=THIN_BORDER)
ws4.row_dimensions[r].height = 36

# 整理龙卷风数据：每对(low, high) → 一个变量
tornado_pairs = []
for i in range(0, len(tornado_vars), 2):
    name = tornado_vars[i][0]
    low_val = tornado_vars[i][2]
    high_val = tornado_vars[i+1][2]
    npv_low = tornado_vars[i][3]
    npv_high = tornado_vars[i+1][3]
    irr_low = tornado_vars[i][4]
    irr_high = tornado_vars[i+1][4]
    tornado_pairs.append((name, low_val, high_val, npv_low, npv_high, irr_low, irr_high))

# 按NPV变化绝对值排序(从大到小)
tornado_pairs.sort(key=lambda x: abs(x[4] - x[3]), reverse=True)

for i, (name, low, high, npv_l, npv_h, irr_l, irr_h) in enumerate(tornado_pairs):
    row = 7 + i
    npv_change = npv_h - npv_l
    npv_change_pct = npv_change / base_fin['npv'] * 100 if base_fin['npv'] != 0 else 0
    irr_change = irr_h - irr_l

    ac(ws4, row, 1, name, font=BOLD_FONT, alignment=LEFT, border=THIN_BORDER)

    # 判断低值/高值的显示格式
    if '效率' in name:
        fmt = NUM_PCT
    elif '折现率' in name or '衰减' in name:
        fmt = NUM_PCT
    elif '天数' in name:
        fmt = '0'
    elif '价差' in name:
        fmt = NUM_MONEY
    elif '投资' in name:
        fmt = NUM_MONEY
    else:
        fmt = NUM_MONEY

    ac(ws4, row, 2, low, font=PARAM_FONT, alignment=CENTER, number_format=fmt, border=THIN_BORDER)
    ac(ws4, row, 3, high, font=PARAM_FONT, alignment=CENTER, number_format=fmt, border=THIN_BORDER)
    ac(ws4, row, 4, npv_l, font=PARAM_FONT, alignment=CENTER, number_format=NUM_MONEY, border=THIN_BORDER)
    ac(ws4, row, 5, npv_h, font=PARAM_FONT, alignment=CENTER, number_format=NUM_MONEY, border=THIN_BORDER)
    ac(ws4, row, 6, npv_change, font=RESULT_FONT, alignment=CENTER, number_format=NUM_MONEY, border=THIN_BORDER)
    ac(ws4, row, 7, npv_change_pct/100, font=RESULT_FONT, alignment=CENTER, number_format=NUM_PCT, border=THIN_BORDER)
    ac(ws4, row, 8, irr_l, font=PARAM_FONT, alignment=CENTER, number_format=NUM_PCT, border=THIN_BORDER)
    ac(ws4, row, 9, irr_h, font=PARAM_FONT, alignment=CENTER, number_format=NUM_PCT, border=THIN_BORDER)
    ac(ws4, row, 10, irr_change, font=RESULT_FONT, alignment=CENTER, number_format=NUM_PCT, border=THIN_BORDER)

ac(ws4, 13, 1, f"基准NPV = {base_fin['npv']:.0f}万元  |  基准IRR = {base_fin['irr']*100:.1f}%",
   font=NOTE_FONT, alignment=LEFT)
ws4.merge_cells("A13:J13")

# 龙卷风图（水平条形图）
chart4 = BarChart()
chart4.type = "bar"
chart4.style = 10
chart4.title = "龙卷风图：各变量对NPV的影响幅度"
chart4.x_axis.title = "NPV变化（万元）"
chart4.width = 24
chart4.height = 14

# 需要创建龙卷风图数据：低-NPV变化, 高-NPV变化
# 在辅助区域准备数据
tornado_plot_start = 15
ac(ws4, tornado_plot_start, 1, "变量", font=HEADER_FONT, fill=HEADER_FILL, alignment=CENTER)
ac(ws4, tornado_plot_start, 2, "NPV降低", font=HEADER_FONT, fill=HEADER_FILL, alignment=CENTER)
ac(ws4, tornado_plot_start, 3, "NPV增加", font=HEADER_FONT, fill=HEADER_FILL, alignment=CENTER)

for i, (name, low, high, npv_l, npv_h, irr_l, irr_h) in enumerate(tornado_pairs):
    row = tornado_plot_start + 1 + i
    base_npv = base_fin['npv']
    npv_down = npv_l - base_npv  # 负向变化
    npv_up = npv_h - base_npv    # 正向变化
    ac(ws4, row, 1, name, font=PARAM_FONT, alignment=LEFT, border=THIN_BORDER)
    ac(ws4, row, 2, npv_down, font=PARAM_FONT, alignment=CENTER, number_format=NUM_MONEY, border=THIN_BORDER)
    ac(ws4, row, 3, npv_up, font=PARAM_FONT, alignment=CENTER, number_format=NUM_MONEY, border=THIN_BORDER)

data_down = Reference(ws4, min_col=2, min_row=tornado_plot_start, max_row=tornado_plot_start+6, max_col=2)
data_up = Reference(ws4, min_col=3, min_row=tornado_plot_start, max_row=tornado_plot_start+6, max_col=3)
cats_t = Reference(ws4, min_col=1, min_row=tornado_plot_start+1, max_row=tornado_plot_start+6)

chart4.add_data(data_down, titles_from_data=True)
chart4.add_data(data_up, titles_from_data=True)
chart4.set_categories(cats_t)
chart4.series[0].graphicalProperties.solidFill = "5B9BD5"  # 蓝（低值）
chart4.series[1].graphicalProperties.solidFill = "ED7D31"  # 橙（高值）
chart4.legend.position = 'b'
ws4.add_chart(chart4, "A24")

# === 价差×效率二维矩阵 ===
matrix_start = 42
section_header(ws4, matrix_start, "▎价差×效率二维敏感性矩阵：第1年毛利（万元）— 公式动态计算", 10)

eff_list = [0.84, 0.86, 0.88, 0.90, 0.92, 0.94, 0.96]
spread_changes_2d = [-0.20, -0.15, -0.10, -0.05, 0, 0.05, 0.10, 0.15, 0.20]

mr = matrix_start + 2
ac(ws4, mr, 1, "价差变化 ↓ \\ 效率 →", font=BOLD_FONT, fill=LIGHT_BLUE_FILL, alignment=CENTER, border=THIN_BORDER)
for j, eff in enumerate(eff_list):
    ac(ws4, mr, j+2, eff, font=BOLD_FONT, fill=LIGHT_BLUE_FILL, alignment=CENTER, number_format=NUM_PCT, border=THIN_BORDER)

for i, sc in enumerate(spread_changes_2d):
    row = mr + 1 + i
    ac(ws4, row, 1, f"{sc:+.0%}", font=PARAM_FONT, fill=BLUE_FILL if sc == 0 else None,
       alignment=CENTER, border=THIN_BORDER)
    for j, eff in enumerate(eff_list):
        # 第1年毛利 = (新峰价×容量kWh×放电效率 - 谷价×容量kWh/充电效率) × 年循环次数 / 10000
        formula = (
            f"=((测算主页!B9+测算主页!B11*(1+A{row}))*测算主页!B15*1000*测算主页!B19*SQRT({eff})"
            f"-测算主页!B9*测算主页!B15*1000*测算主页!B19/SQRT({eff}))"
            f"*测算主页!B27/10000"
        )
        is_base = (abs(sc) < 1e-9 and abs(eff - 0.90) < 1e-9)
        ac(ws4, row, j+2, formula, font=RESULT_FONT if is_base else PARAM_FONT,
           fill=BLUE_FILL if is_base else None, alignment=CENTER,
           number_format=NUM_MONEY, border=THIN_BORDER)

# 识别最优/最差
best_row = mr + 1 + 8  # +20% spread
worst_row = mr + 1      # -20% spread
ac(ws4, best_row + 1, 1, "← 价差越大→毛利越高", font=NOTE_FONT, alignment=LEFT)
ac(ws4, worst_row, 1, "← 价差越小→毛利越低", font=NOTE_FONT, alignment=LEFT)
ac(ws4, mr + 1 + 4, len(eff_list) + 3, "基准组合", font=BOLD_FONT, fill=YELLOW_FILL, alignment=CENTER)

ws4.freeze_panes = "A2"

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Sheet 5: 情景分析
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
ws5 = wb.create_sheet("情景分析")
ws5.sheet_properties.tabColor = "7030A0"
set_widths(ws5, [20, 18, 18, 18, 18, 18])

ws5.merge_cells("A1:F1")
ac(ws5, 1, 1, "三情景对比分析：乐观 / 基准 / 悲观", font=TITLE_FONT, alignment=CENTER)
ws5.row_dimensions[1].height = 28
ws5.merge_cells("A2:F2")
ac(ws5, 2, 1, "多变量同时变化，评估不同市场环境下的项目收益弹性", font=NOTE_FONT, alignment=CENTER)

# 情景参数对比
r = 4
sc_headers = ["参数", "乐观情景", "基准情景", "悲观情景", "乐观vs基准", "悲观vs基准"]
for ci, h in enumerate(sc_headers, 1):
    ac(ws5, r, ci, h, font=HEADER_FONT, fill=HEADER_FILL, alignment=CENTER, border=THIN_BORDER)
ws5.row_dimensions[r].height = 30

sc_params = [
    ("峰段电价（元/kWh）", scenarios['乐观']['peak'], scenarios['基准']['peak'], scenarios['悲观']['peak'], NUM_MONEY),
    ("谷段电价（元/kWh）", scenarios['乐观']['valley'], scenarios['基准']['valley'], scenarios['悲观']['valley'], NUM_MONEY),
    ("峰谷价差（元/kWh）", scenarios['乐观']['peak']-scenarios['乐观']['valley'],
     scenarios['基准']['peak']-scenarios['基准']['valley'],
     scenarios['悲观']['peak']-scenarios['悲观']['valley'], NUM_MONEY),
    ("充放电效率", scenarios['乐观']['rte'], scenarios['基准']['rte'], scenarios['悲观']['rte'], NUM_PCT),
    ("单位投资（元/Wh）", scenarios['乐观']['invest_per_wh'], scenarios['基准']['invest_per_wh'],
     scenarios['悲观']['invest_per_wh'], NUM_MONEY),
    ("年衰减率", scenarios['乐观']['degradation'], scenarios['基准']['degradation'],
     scenarios['悲观']['degradation'], NUM_PCT),
    ("年运营天数", scenarios['乐观']['cycles_per_year'], scenarios['基准']['cycles_per_year'],
     scenarios['悲观']['cycles_per_year'], '0'),
    ("折现率", scenarios['乐观']['discount_rate'], scenarios['基准']['discount_rate'],
     scenarios['悲观']['discount_rate'], NUM_PCT),
]

for i, (label, opt, base, pes, fmt) in enumerate(sc_params):
    row = 5 + i
    ac(ws5, row, 1, label, font=BOLD_FONT, fill=LIGHT_BLUE_FILL, alignment=LEFT, border=THIN_BORDER)
    ac(ws5, row, 2, opt, font=PARAM_FONT, fill=GREEN_FILL, alignment=CENTER, number_format=fmt, border=THIN_BORDER)
    ac(ws5, row, 3, base, font=PARAM_FONT, fill=YELLOW_FILL, alignment=CENTER, number_format=fmt, border=THIN_BORDER)
    ac(ws5, row, 4, pes, font=PARAM_FONT, fill=ORANGE_FILL, alignment=CENTER, number_format=fmt, border=THIN_BORDER)
    # 变化
    if isinstance(opt, (int, float)) and isinstance(base, (int, float)) and base != 0:
        ac(ws5, row, 5, (opt-base)/base, font=PARAM_FONT, alignment=CENTER, number_format=NUM_PCT, border=THIN_BORDER)
        ac(ws5, row, 6, (pes-base)/base, font=PARAM_FONT, alignment=CENTER, number_format=NUM_PCT, border=THIN_BORDER)

# 情景财务指标对比
r = 14
ac(ws5, r, 1, "财务指标对比", font=HEADER_FONT, fill=HEADER_FILL, alignment=CENTER, border=THIN_BORDER)
ws5.merge_cells(start_row=r, start_column=1, end_row=r, end_column=1)
for ci, h in enumerate(["指标", "乐观情景", "基准情景", "悲观情景", "乐观vs基准", "悲观vs基准"], 1):
    ac(ws5, r+1, ci, h, font=BOLD_FONT, fill=LIGHT_BLUE_FILL, alignment=CENTER, border=THIN_BORDER)

sc_fin = [
    ("初始投资（万元）", 'investment'),
    ("第1年毛利（万元）", 'annual_gross_1'),
    ("年运维费（万元）", 'om_annual'),
    ("NPV（万元）", 'npv'),
    ("IRR", 'irr'),
    ("动态回收期（年）", 'payback'),
]

for i, (label, key) in enumerate(sc_fin):
    row = 16 + i
    opt_v = scenarios['乐观'][key]
    base_v = scenarios['基准'][key]
    pes_v = scenarios['悲观'][key]

    ac(ws5, row, 1, label, font=BOLD_FONT, fill=LIGHT_BLUE_FILL, alignment=LEFT, border=THIN_BORDER)

    if 'IRR' in label:
        fmt = NUM_PCT
        opt_d, base_d, pes_d = opt_v, base_v, pes_v
    elif '回收期' in label:
        fmt = '0.0'
        opt_d, base_d, pes_d = opt_v if opt_v else 10, base_v if base_v else 10, pes_v if pes_v else 10
    else:
        fmt = NUM_MONEY
        opt_d, base_d, pes_d = opt_v, base_v, pes_v

    ac(ws5, row, 2, opt_d, font=RESULT_FONT, fill=GREEN_FILL, alignment=CENTER, number_format=fmt, border=THIN_BORDER)
    ac(ws5, row, 3, base_d, font=RESULT_FONT, fill=YELLOW_FILL, alignment=CENTER, number_format=fmt, border=THIN_BORDER)
    ac(ws5, row, 4, pes_d, font=RESULT_FONT, fill=ORANGE_FILL, alignment=CENTER, number_format=fmt, border=THIN_BORDER)

    if 'IRR' in label:
        ac(ws5, row, 5, opt_v - base_v, font=PARAM_FONT, alignment=CENTER,
           number_format=NUM_PCT, border=THIN_BORDER)
        ac(ws5, row, 6, pes_v - base_v, font=PARAM_FONT, alignment=CENTER,
           number_format=NUM_PCT, border=THIN_BORDER)
    elif '回收期' in label:
        # 回收期可能为None（NPV未回正）
        if opt_v is not None and base_v is not None and base_v != 0:
            ac(ws5, row, 5, (opt_v - base_v) / base_v, font=PARAM_FONT, alignment=CENTER,
               number_format=NUM_PCT, border=THIN_BORDER)
        else:
            ac(ws5, row, 5, "N/A", font=NOTE_FONT, alignment=CENTER, border=THIN_BORDER)
        if pes_v is not None and base_v is not None and base_v != 0:
            ac(ws5, row, 6, (pes_v - base_v) / base_v, font=PARAM_FONT, alignment=CENTER,
               number_format=NUM_PCT, border=THIN_BORDER)
        else:
            ac(ws5, row, 6, "N/A", font=NOTE_FONT, alignment=CENTER, border=THIN_BORDER)
    elif base_v is not None and base_v != 0:
        ac(ws5, row, 5, (opt_v - base_v) / abs(base_v), font=PARAM_FONT, alignment=CENTER,
           number_format=NUM_PCT, border=THIN_BORDER)
        ac(ws5, row, 6, (pes_v - base_v) / abs(base_v), font=PARAM_FONT, alignment=CENTER,
           number_format=NUM_PCT, border=THIN_BORDER)

# 情景对比图表
chart5 = BarChart()
chart5.type = "col"
chart5.style = 10
chart5.title = "三情景 NPV 对比"
chart5.y_axis.title = "万元"
chart5.width = 22
chart5.height = 13

# NPV数据
ac(ws5, 24, 1, "NPV", font=NOTE_FONT)
ac(ws5, 24, 2, scenarios['乐观']['npv'], font=PARAM_FONT, number_format=NUM_MONEY)
ac(ws5, 24, 3, scenarios['基准']['npv'], font=PARAM_FONT, number_format=NUM_MONEY)
ac(ws5, 24, 4, scenarios['悲观']['npv'], font=PARAM_FONT, number_format=NUM_MONEY)
ac(ws5, 23, 2, "乐观", font=BOLD_FONT)
ac(ws5, 23, 3, "基准", font=BOLD_FONT)
ac(ws5, 23, 4, "悲观", font=BOLD_FONT)

data_sc = Reference(ws5, min_col=1, min_row=23, max_row=24, max_col=4)
chart5.add_data(data_sc, titles_from_data=True)
cats_sc = Reference(ws5, min_col=2, min_row=23, max_col=4)
chart5.set_categories(cats_sc)
chart5.series[0].graphicalProperties.solidFill = "70AD47"
chart5.legend.position = 'b'
ws5.add_chart(chart5, "A26")

# IRR 对比
chart6 = BarChart()
chart6.type = "col"
chart6.style = 10
chart6.title = "三情景 IRR 对比"
chart6.y_axis.title = "IRR"
chart6.y_axis.numFmt = '0%'
chart6.width = 22
chart6.height = 13

ac(ws5, 42, 1, "IRR", font=NOTE_FONT)
ac(ws5, 42, 2, scenarios['乐观']['irr'], font=PARAM_FONT, number_format=NUM_PCT)
ac(ws5, 42, 3, scenarios['基准']['irr'], font=PARAM_FONT, number_format=NUM_PCT)
ac(ws5, 42, 4, scenarios['悲观']['irr'], font=PARAM_FONT, number_format=NUM_PCT)
ac(ws5, 41, 2, "乐观", font=BOLD_FONT)
ac(ws5, 41, 3, "基准", font=BOLD_FONT)
ac(ws5, 41, 4, "悲观", font=BOLD_FONT)

data_sc2 = Reference(ws5, min_col=1, min_row=41, max_row=42, max_col=4)
chart6.add_data(data_sc2, titles_from_data=True)
chart6.set_categories(cats_sc)
chart6.series[0].graphicalProperties.solidFill = "ED7D31"
chart6.legend.position = 'b'
ws5.add_chart(chart6, "A44")

ws5.freeze_panes = "A3"

# ============================================================
# 保存前：确保所有跨表引用使用带引号的sheet名（兼容WPS/各版本Excel）
# ============================================================
sheet_names = wb.sheetnames
fixed = 0
for ws in wb.worksheets:
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column):
        for cell in row:
            if cell.value and isinstance(cell.value, str) and cell.value.startswith('='):
                for sn in sheet_names:
                    if sn in cell.value and f"'{sn}'" not in cell.value:
                        cell.value = cell.value.replace(sn, f"'{sn}'")
                        fixed += 1

# ============================================================
# 保存
# ============================================================
output_path = r"c:\Users\弹猫的吉他\Desktop\信息源\储能套利收益测算模型_v2.xlsx"
wb.save(output_path)
print(f"[OK] 模型已生成：{output_path}")
print(f"   - Sheet 1: 测算主页（输入参数 + 单次循环 + KPI仪表板）")
print(f"   - Sheet 2: 逐年收益表（10年明细 + 图表）")
print(f"   - Sheet 3: 现金流与IRR（IRR/NPV/回收期）")
print(f"   - Sheet 4: 敏感性分析（龙卷风图 + 二维矩阵）")
print(f"   - Sheet 5: 情景分析（乐观/基准/悲观三情景）")
