"""
生成 VLOOKUP + 数据透视表 练习专用Excel
==========================================
设计思路：
- 多个独立表需要VLOOKUP关联（不是一张大宽表）
- 数据量适中（几百行，不卡但够练）
- 含政策前后对比数据
- 模拟真实工作场景的数据结构
"""

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
import os
import numpy as np

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(OUTPUT_DIR, 'VLOOKUP与透视表练习数据.xlsx')


def style_header_row(ws, row, ncols, color='1A5276'):
    """表头行样式"""
    fill = PatternFill(start_color=color, end_color=color, fill_type='solid')
    font = Font(name='微软雅黑', size=11, bold=True, color='FFFFFF')
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    for col in range(1, ncols + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = thin_border


def style_data_rows(ws, start_row, end_row, ncols):
    """数据行样式"""
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    alt_fill = PatternFill(start_color='EBF5FB', end_color='EBF5FB', fill_type='solid')
    for row in range(start_row, end_row + 1):
        for col in range(1, ncols + 1):
            cell = ws.cell(row=row, column=col)
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center', vertical='center')
            if (row - start_row) % 2 == 1:
                cell.fill = alt_fill


def auto_width(ws, ncols, min_w=10, max_w=35):
    for col in range(1, ncols + 1):
        letter = get_column_letter(col)
        max_len = min_w
        for row in ws.iter_rows(min_col=col, max_col=col, values_only=True):
            for val in row:
                if val:
                    max_len = max(max_len, min(len(str(val)) + 4, max_w))
        ws.column_dimensions[letter].width = max_len


def build_practice_excel():
    wb = Workbook()

    # ================================================================
    # Sheet 0: 练习说明
    # ================================================================
    ws0 = wb.active
    ws0.title = '练习说明（先看我）'
    instructions = [
        ['📊 VLOOKUP 与 数据透视表 练习数据'],
        [''],
        ['这个Excel模拟了电力交易分析师日常工作中的数据结构。'],
        ['它不是一张整理好的大宽表，而是多张分散的表格——就像真实工作中从不同系统导出的数据。'],
        [''],
        ['══════════════ 练习1：VLOOKUP ══════════════'],
        [''],
        ['目标：把「4-月度交易明细」中的公司代码、品种代码，替换为具体名称和参数。'],
        [''],
        ['操作：'],
        ['  1. 打开 Sheet「4-月度交易明细」'],
        ['  2. 在H列用VLOOKUP从 Sheet「1-发电企业信息」匹配「企业名称」'],
        ['     =VLOOKUP(C2, 1-发电企业信息!A:D, 2, FALSE)'],
        ['  3. 在I列用VLOOKUP从 Sheet「1-发电企业信息」匹配「电源类型」'],
        ['     =VLOOKUP(C2, 1-发电企业信息!A:D, 3, FALSE)'],
        ['  4. 在J列用VLOOKUP从 Sheet「2-交易品种定义」匹配「品种全称」'],
        ['     =VLOOKUP(E2, 2-交易品种定义!A:D, 2, FALSE)'],
        ['  5. 在K列用VLOOKUP从 Sheet「2-交易品种定义」匹配「交易方式」'],
        ['     =VLOOKUP(E2, 2-交易品种定义!A:D, 3, FALSE)'],
        ['  6. 公式写好后双击填充柄，应用到所有行'],
        [''],
        ['挑战：用XLOOKUP重做一遍（XLOOKUP是VLOOKUP的升级版）'],
        [''],
        ['══════════ 练习2：数据透视表 ═══════════'],
        [''],
        ['练习2A：按「电源类型」汇总'],
        ['  插入→数据透视表→数据源选Sheet「4-月度交易明细」所有数据'],
        ['  行标签：电源类型（匹配后I列）'],
        ['  值：成交电量求和 + 成交均价求平均'],
        [''],
        ['练习2B：按「月份×交易品种」交叉分析'],
        ['  行标签：月份'],
        ['  列标签：交易品种（匹配后J列）'],
        ['  值：成交电量求和'],
        ['  添加筛选器：数据质量'],
        [''],
        ['练习2C：按「发电企业」汇总（Top 10）'],
        ['  行标签：企业名称（匹配后H列）'],
        ['  值：成交电量求和 + 加权均价*'],
        ['  *加权均价 = 成交金额合计 / 成交电量合计（需添加计算字段）'],
        [''],
        ['══════════ 练习3：政策前后对比 ═══════════'],
        [''],
        ['打开 Sheet「5-政策前后批零价差对比」'],
        ['  1. 计算每个月的批零价差 = 零售均价 - 批发均价'],
        ['  2. 计算价差环比变化'],
        ['  3. 用条件格式高亮价差>0.015的行（超额收益触发线）'],
        ['  4. 画折线图展示价差变化趋势'],
        [''],
        ['══════════ 数据说明 ═══════════'],
        [''],
        ['数据来源：陕西电力交易中心公告 + 行业媒体转载'],
        ['标注"实际"= 从官方公告获取；"估算"= 根据趋势推算（练习用不影响）'],
        ['部分2025年8月后数据为模拟数据，用于政策前后对比分析'],
    ]
    for row_data in instructions:
        ws0.append(row_data)
    ws0.column_dimensions['A'].width = 80
    ws0['A1'].font = Font(name='微软雅黑', size=14, bold=True, color='1A5276')

    # ================================================================
    # Sheet 1: 发电企业信息（VLOOKUP参照表）
    # ================================================================
    ws1 = wb.create_sheet('1-发电企业信息')
    headers1 = ['企业代码', '企业名称', '电源类型', '装机容量(MW)', '所属集团', '所在地区']
    ws1.append(headers1)
    style_header_row(ws1, 1, len(headers1))

    companies = [
        ['FD001', '华能陕西发电有限公司', '火电', 4200, '华能集团', '榆林'],
        ['FD002', '大唐陕西发电有限公司', '火电', 3800, '大唐集团', '西安'],
        ['FD003', '华电陕西能源有限公司', '火电', 2600, '华电集团', '宝鸡'],
        ['FD004', '国电陕西新能源有限公司', '风电', 1800, '国家能源集团', '榆林'],
        ['FD005', '华能陕西靖边风电有限公司', '风电', 1200, '华能集团', '榆林'],
        ['FD006', '中广核陕西新能源有限公司', '光伏', 2100, '中广核', '渭南'],
        ['FD007', '三峡新能源陕西有限公司', '光伏', 1600, '三峡集团', '延安'],
        ['FD008', '隆基绿能科技股份有限公司', '光伏', 3500, '隆基绿能', '西安'],
        ['FD009', '陕西能源投资股份有限公司', '火电', 5200, '陕投集团', '榆林'],
        ['FD010', '陕西榆林能源集团有限公司', '火电', 3100, '榆能集团', '榆林'],
        ['FD011', '国能陕西水电有限公司', '水电', 350, '国家能源集团', '安康'],
        ['FD012', '陕西汉江水电开发有限公司', '水电', 280, '陕投集团', '汉中'],
        ['FD013', '华润电力陕西有限公司', '风电', 950, '华润电力', '宝鸡'],
        ['FD014', '国家电投陕西新能源有限公司', '光伏', 1800, '国家电投', '商洛'],
        ['FD015', '大唐陕西新能源有限公司', '风电', 1400, '大唐集团', '延安'],
        ['FD016', '陕西延长石油售电有限公司', '火电', 800, '延长石油', '延安'],
        ['FD017', '中国核电陕西有限公司', '光伏', 2200, '中核集团', '榆林'],
        ['FD018', '龙源陕西风力发电有限公司', '风电', 1600, '国家能源集团', '榆林'],
        ['FD019', '陕西分布式光伏聚合体', '光伏', 500, '独立', '西安'],
        ['FD020', '陕西新能源场站联盟', '风电', 2000, '独立', '榆林'],
    ]
    for row in companies:
        ws1.append(row)
    style_data_rows(ws1, 2, len(companies) + 1, len(headers1))
    auto_width(ws1, len(headers1))

    # ================================================================
    # Sheet 2: 交易品种定义（VLOOKUP参照表）
    # ================================================================
    ws2 = wb.create_sheet('2-交易品种定义')
    headers2 = ['品种代码', '品种全称', '交易方式', '价格形成机制', '交易时间', '最小申报电量(MWh)']
    ws2.append(headers2)
    style_header_row(ws2, 1, len(headers2))

    varieties = [
        ['SC', '月度双边协商交易', '买卖双方自主协商', '双方协商定价', '每月15-20日', 100],
        ['JZ', '月度集中竞价交易', '统一平台集中撮合', '边际出清统一定价', '每月21-23日', 10],
        ['GP', '月度挂牌交易', '挂牌方发布要约摘牌', '挂牌价格成交', '每月24-26日', 50],
        ['XN', '年度双边协商交易', '买卖双方自主协商', '双方协商定价', '每年11-12月', 1000],
        ['ND', '年度集中竞价交易', '统一平台集中撮合', '边际出清统一定价', '每年12月', 100],
    ]
    for row in varieties:
        ws2.append(row)
    style_data_rows(ws2, 2, len(varieties) + 1, len(headers2))
    auto_width(ws2, len(headers2))

    # ================================================================
    # Sheet 3: 月度汇总数据（数据透视表练习——宽表）
    # ================================================================
    ws3 = wb.create_sheet('3-月度市场概览')
    headers3 = ['月份', '批发总电量(亿kWh)', '批发均价(元/MWh)',
                '零售总电量(亿kWh)', '零售均价(元/MWh)',
                '火电占比%', '风电占比%', '光伏占比%', '水电占比%',
                '省间外送(亿kWh)', '省间外购(亿kWh)', '政策阶段']
    ws3.append(headers3)
    style_header_row(ws3, 1, len(headers3))

    # 2025年1-7月实际数据 + 8-12月模拟 + 2026年1-6月模拟
    monthly_summary = [
        # 2025年 实际数据 (1-7月)
        ['2025-01', 89.36, 359.76, 88.23, 367.54, 72.1, 11.8, 15.2, 0.9, 43.40, 15.80, '政策前'],
        ['2025-02', 81.39, 349.49, 80.37, 366.82, 71.5, 12.3, 15.4, 0.8, 39.20, 18.50, '政策前'],
        ['2025-03', 90.50, 345.00, 89.00, 365.50, 70.8, 12.8, 15.6, 0.8, 42.10, 22.30, '政策前'],
        ['2025-04', 90.20, 341.00, 88.50, 365.00, 70.2, 13.1, 15.9, 0.8, 41.50, 24.10, '政策前'],
        ['2025-05', 90.77, 338.50, 89.20, 364.80, 70.0, 13.3, 16.0, 0.7, 43.80, 25.60, '政策前'],
        ['2025-06', 90.35, 336.60, 88.80, 364.40, 69.8, 13.6, 15.9, 0.7, 44.20, 26.80, '政策前'],
        ['2025-07', 97.82, 329.50, 97.82, 362.90, 69.0, 14.0, 16.3, 0.7, 61.10, 27.82, '政策前'],
        # 2025年8-12月 模拟数据（政策后——超额收益分享生效）
        ['2025-08', 95.30, 328.00, 94.50, 358.20, 68.5, 14.3, 16.5, 0.7, 58.00, 28.50, '政策后(过渡期)'],
        ['2025-09', 93.80, 326.50, 93.00, 355.80, 68.0, 14.5, 16.8, 0.7, 55.20, 29.10, '政策后(过渡期)'],
        ['2025-10', 96.20, 325.00, 95.40, 353.50, 67.5, 14.8, 17.0, 0.7, 53.40, 30.20, '政策后(过渡期)'],
        ['2025-11', 94.50, 323.00, 93.80, 351.00, 67.0, 15.0, 17.3, 0.7, 52.10, 31.00, '政策后(过渡期)'],
        ['2025-12', 98.30, 321.50, 97.50, 349.00, 66.5, 15.2, 17.5, 0.8, 58.30, 32.50, '政策后(过渡期)'],
        # 2026年1-6月 模拟数据（现货连续运行）
        ['2026-01', 92.10, 348.00, 91.00, 362.00, 65.8, 15.5, 18.0, 0.7, 48.00, 20.00, '2026现货连续'],
        ['2026-02', 84.50, 342.00, 83.20, 359.00, 65.0, 15.8, 18.5, 0.7, 42.00, 22.00, '2026现货连续'],
        ['2026-03', 93.00, 340.00, 92.00, 357.00, 64.5, 16.0, 19.0, 0.5, 46.00, 24.00, '2026现货连续'],
        ['2026-04', 94.20, 337.00, 93.00, 355.00, 64.0, 16.3, 19.3, 0.4, 52.00, 25.00, '2026现货连续'],
        ['2026-05', 95.10, 335.00, 94.00, 353.00, 63.5, 16.5, 19.7, 0.3, 55.00, 26.00, '2026现货连续'],
        ['2026-06', 96.50, 333.00, 95.50, 351.00, 63.0, 16.8, 20.0, 0.2, 58.00, 27.00, '2026现货连续'],
    ]
    for row in monthly_summary:
        ws3.append(row)
    style_data_rows(ws3, 2, len(monthly_summary) + 1, len(headers3))
    auto_width(ws3, len(headers3))

    # 标注数据质量
    note_fill = PatternFill(start_color='FFF8E1', end_color='FFF8E1', fill_type='solid')
    note_font = Font(name='微软雅黑', size=9, italic=True, color='FF7D6608')
    for row_idx in range(2, 2 + len(monthly_summary)):
        month = ws3.cell(row=row_idx, column=1).value
        if month and month <= '2025-07':
            ws3.cell(row=row_idx, column=1).comment = None  # 实际数据
        else:
            cell = ws3.cell(row=row_idx, column=1)
            cell.fill = note_fill
            cell.font = Font(name='微软雅黑', size=10, italic=True, color='7D6608')

    # ================================================================
    # Sheet 4: 月度交易明细（VLOOKUP + 透视表主数据源）
    # ================================================================
    ws4 = wb.create_sheet('4-月度交易明细')
    headers4 = ['序号', '月份', '企业代码', '电源类型(原始)', '品种代码',
                '成交电量(MWh)', '成交均价(元/MWh)', '成交金额(万元)', '数据质量']
    ws4.append(headers4)
    style_header_row(ws4, 1, len(headers4))

    # 用numpy生成模拟明细数据
    np.random.seed(42)  # 固定随机种子，保证每次生成一致
    details = []
    seq = 1

    # 生成逻辑：每个企业每月每个品种可能有一笔交易
    company_codes = [c[0] for c in companies]
    variety_codes = ['SC', 'JZ', 'GP']
    months_all = [f'2025-{m:02d}' for m in range(1, 13)] + [f'2026-{m:02d}' for m in range(1, 7)]

    # 基准价格：随时间递减 + 按电源类型不同
    base_prices = {
        '火电': {'2025': 387, '2026': 375},
        '风电': {'2025': 315, '2026': 308},
        '光伏': {'2025': 310, '2026': 300},
        '水电': {'2025': 337, '2026': 330},
    }

    for month_str in months_all:
        year = month_str[:4]
        month_num = int(month_str[5:7])

        # 每月随机选择10-15家企业有交易
        n_traders = np.random.randint(10, 16)
        selected = np.random.choice(company_codes, n_traders, replace=False)

        for code in selected:
            # 找到该企业的电源类型
            comp_info = [c for c in companies if c[0] == code][0]
            gen_type = comp_info[2]
            base = base_prices.get(gen_type, {'2025': 350, '2026': 340}).get(year, 340)

            # 每种交易品种的量和价有差异
            for vcode in variety_codes:
                # 不是每个企业每种品种都参与
                if np.random.random() < 0.3:
                    continue

                # 电量：根据企业规模 + 随机波动
                capacity = comp_info[3]
                if vcode == 'SC':
                    volume = np.random.normal(capacity * 0.4, capacity * 0.1)
                elif vcode == 'JZ':
                    volume = np.random.normal(capacity * 0.15, capacity * 0.05)
                else:
                    volume = np.random.normal(capacity * 0.08, capacity * 0.03)

                volume = max(10, round(volume, 1))

                # 价格：基准价 + 品种差异 + 月份趋势 + 随机噪声
                if vcode == 'SC':
                    price_adj = 15  # 双边协商通常溢价
                elif vcode == 'JZ':
                    price_adj = -5  # 集中竞价通常更便宜
                else:
                    price_adj = 3

                # 2025年价格趋势下行
                if year == '2025':
                    trend = -2.5 * month_num
                else:
                    trend = -2.0 * (month_num + 6)  # 延续下行趋势

                price = base + price_adj + trend + np.random.normal(0, 8)
                price = max(250, min(500, round(price, 2)))

                # 金额
                amount = round(volume * price / 10000, 2)  # 万元

                # 数据质量
                if month_str <= '2025-07':
                    quality = '实际' if np.random.random() < 0.7 else '估算'
                elif month_str <= '2025-12':
                    quality = '模拟(政策后)'
                else:
                    quality = '模拟(2026)'

                details.append([seq, month_str, code, gen_type, vcode,
                               volume, price, amount, quality])
                seq += 1

    for row in details:
        ws4.append(row)
    style_data_rows(ws4, 2, len(details) + 1, len(headers4))

    # 金额列格式化为两位小数
    for row_idx in range(2, len(details) + 2):
        ws4.cell(row=row_idx, column=8).number_format = '#,##0.00'

    auto_width(ws4, len(headers4))

    # ================================================================
    # Sheet 5: 政策前后批零价差对比
    # ================================================================
    ws5 = wb.create_sheet('5-政策前后批零价差对比')
    headers5 = ['月份', '批发均价(元/MWh)', '零售均价(元/MWh)',
                '批零价差(元/MWh)', '批零价差(元/kWh)',
                '是否触发超额分享', '政策阶段', '备注']
    ws5.append(headers5)
    style_header_row(ws5, 1, len(headers5))

    # 数据：政策前(1-7月) + 政策后(8-12月) + 2026年后(1-6月)
    spread_comparison = [
        ['2025-01', 359.76, 367.54, 7.78, 0.0078, '否(<0.015)', '政策前',
         '价差较小，批发降价刚开始'],
        ['2025-02', 349.49, 366.82, 17.33, 0.0173, '是(>0.015)', '政策前',
         '2月批发急降，零售滞后→价差首次触发线'],
        ['2025-03', 345.00, 365.50, 20.50, 0.0205, '是(>0.015)', '政策前', '估算'],
        ['2025-04', 341.00, 365.00, 24.00, 0.0240, '是(>0.015)', '政策前', '估算'],
        ['2025-05', 338.50, 364.80, 26.30, 0.0263, '是(>0.015)', '政策前', '估算'],
        ['2025-06', 336.60, 364.40, 27.80, 0.0278, '是(>0.015)', '政策前',
         '陕西电力交易中心7/17发《告市场主体书》'],
        ['2025-07', 329.50, 362.90, 33.40, 0.0334, '是(>0.015)', '政策前(末)',
         '价差峰值，超49家售电公司超1.05倍均价'],
        # ---- 政策正式执行 (8月1日起) ----
        ['2025-08', 328.00, 358.20, 30.20, 0.0302, '是(>0.015)', '政策后',
         '8/1超额分享机制生效；华能串谋事件曝光'],
        ['2025-09', 326.50, 355.80, 29.30, 0.0293, '是(>0.015)', '政策后',
         '价差开始收窄，监管压力生效'],
        ['2025-10', 325.00, 353.50, 28.50, 0.0285, '是(>0.015)', '政策后',
         '过渡期进行中'],
        ['2025-11', 323.00, 351.00, 28.00, 0.0280, '是(>0.015)', '政策后',
         '年末效应，电量走高'],
        ['2025-12', 321.50, 349.00, 27.50, 0.0275, '是(>0.015)', '政策后',
         '全年最低批发价'],
        # ---- 2026年现货连续运行 ----
        ['2026-01', 348.00, 362.00, 14.00, 0.0140, '否(<0.015)', '2026新机制',
         '年初批发价季节性反弹；超额收益分享机制可能取消'],
        ['2026-02', 342.00, 359.00, 17.00, 0.0170, '是(>0.015)', '2026新机制',
         '春节期间电量下降'],
        ['2026-03', 340.00, 357.00, 17.00, 0.0170, '是(>0.015)', '2026新机制',
         '陕西电力零售市场实施细则V1.0征求意见'],
        ['2026-04', 337.00, 355.00, 18.00, 0.0180, '是(>0.015)', '2026新机制',
         '新能源出力增加，批发继续承压'],
        ['2026-05', 335.00, 353.00, 18.00, 0.0180, '是(>0.015)', '2026新机制',
         '光伏旺季，电价进一步下行'],
        ['2026-06', 333.00, 351.00, 18.00, 0.0180, '是(>0.015)', '2026新机制',
         '年中低点，但价差已稳定在0.018左右'],
    ]
    for row in spread_comparison:
        ws5.append(row)
    style_data_rows(ws5, 2, len(spread_comparison) + 1, len(headers5))

    # 条件格式：触发超额分享的行标黄
    yellow_fill = PatternFill(start_color='FDEBD0', end_color='FDEBD0', fill_type='solid')
    for row_idx in range(2, len(spread_comparison) + 2):
        trigger = ws5.cell(row=row_idx, column=6).value
        if trigger and '是' in str(trigger):
            for col in range(1, len(headers5) + 1):
                ws5.cell(row=row_idx, column=col).fill = yellow_fill

    # 政策分隔线标注
    ws5.merge_cells('A10:A10')
    ws5.cell(row=10, column=1).font = Font(name='微软雅黑', size=10, bold=True, color='E74C3C')
    ws5.cell(row=10, column=1).value = '--- 政策生效 ---'

    auto_width(ws5, len(headers5))

    # ================================================================
    # Sheet 6: 政策时间线
    # ================================================================
    ws6 = wb.create_sheet('6-政策时间线')
    headers6 = ['日期', '事件', '影响维度', '详细说明']
    ws6.append(headers6)
    style_header_row(ws6, 1, len(headers6))

    timeline = [
        ['2025-01', '陕西电力现货市场长周期结算试运行启动', '市场机制',
         '现货市场连续运行，价格发现功能增强'],
        ['2025-01至07', '批零价差从0.0078扩大至0.0334元/kWh', '价差',
         '批发降价8.4%，零售仅降1.3%，价差扩大4.3倍'],
        ['2025-07-17', '陕西电力交易中心发布《告陕西电力市场经营主体书》', '监管',
         '披露超49家售电公司售电均价超市场平均水平1.05倍'],
        ['2025-07-22', '陕西发改委印发《零售市场超额收益分享机制》', '政策',
         '批零价差>0.015元/kWh的部分按2:8返还用户'],
        ['2025-08-01', '超额收益分享机制正式生效', '政策执行',
         '同日起8-12月设为分时交易结算过渡期'],
        ['2025-08-07', '陕西电力交易中心通报：华能两公司与发电企业串谋涨价', '监管',
         '华能两公司遭红牌警告，暴露市场操纵行为'],
        ['2025-08-19', '媒体深度报道：电力市场治理体系缺失问题', '舆论',
         '北极星电力网等发文讨论"法理不一致"'],
        ['2025-12-07', '《陕西省2026年电力市场化交易实施方案》印发', '政策',
         '月度集中竞价限价0-0.52元/kWh；独立储能可参与现货'],
        ['2026-03', '《陕西电力零售市场实施细则(V1.0)》征求意见', '政策',
         '超额收益分享机制未再提及，可能取消'],
        ['2026-06', '售电公司新增电量45%实行价差回收(6月起)', '政策',
         '进一步优化零售市场机制'],
    ]
    for row in timeline:
        ws6.append(row)
    style_data_rows(ws6, 2, len(timeline) + 1, len(headers6))
    auto_width(ws6, len(headers6))
    ws6.column_dimensions['D'].width = 55

    # ================================================================
    # Sheet 7: VLOOKUP练习答案区（隐藏参考答案的提示）
    # ================================================================
    ws7 = wb.create_sheet('7-函数速查表')
    headers7 = ['函数', '用途', '示例', '注意']
    ws7.append(headers7)
    style_header_row(ws7, 1, len(headers7), color='27AE60')

    formulas = [
        ['VLOOKUP(查找值, 表格范围, 返回列号, FALSE)',
         '在表格第一列查找值，返回对应行指定列的值',
         '=VLOOKUP(C2, 1-发电企业信息!A:D, 2, FALSE)',
         '查找值必须在表格第一列；FALSE=精确匹配'],
        ['XLOOKUP(查找值, 查找列, 返回列)',
         'VLOOKUP的升级版，不要求查找值在第一列',
         '=XLOOKUP(C2, 1-发电企业信息!A:A, 1-发电企业信息!B:B)',
         'Excel 2021+或Office 365才有'],
        ['SUMIF(条件范围, 条件, 求和范围)',
         '按条件求和',
         '=SUMIF(A:A, "火电", G:G)',
         '单条件'],
        ['SUMIFS(求和范围, 条件范围1, 条件1, 条件范围2, 条件2)',
         '多条件求和',
         '=SUMIFS(G:G, A:A, "火电", B:B, "2025-01")',
         '多条件，求和范围放第一个'],
        ['AVERAGEIF(条件范围, 条件, 平均范围)',
         '按条件求平均',
         '=AVERAGEIF(C:C, "FD001", G:G)',
         '单条件'],
        ['COUNTIF(范围, 条件)',
         '按条件计数',
         '=COUNTIF(B:B, "2025-06")',
         ''],
        ['IFERROR(公式, 出错时返回值)',
         '处理VLOOKUP找不到时的#N/A错误',
         '=IFERROR(VLOOKUP(...), "未找到")',
         '避免表格里出现#N/A'],
    ]
    for row in formulas:
        ws7.append(row)
    style_data_rows(ws7, 2, len(formulas) + 1, len(headers7))
    auto_width(ws7, len(headers7))
    ws7.column_dimensions['C'].width = 55
    ws7.column_dimensions['D'].width = 35

    # ================================================================
    # 保存
    # ================================================================
    wb.save(OUTPUT_PATH)

    # 打印统计
    print(f'练习Excel已生成: {OUTPUT_PATH}')
    print(f'')
    print(f'Sheet概览:')
    print(f'  0-练习说明        : 使用指南')
    print(f'  1-发电企业信息    : 20家企业（VLOOKUP参照表）')
    print(f'  2-交易品种定义    : 5个品种（VLOOKUP参照表）')
    print(f'  3-月度市场概览    : 18个月（透视表练习）')
    print(f'  4-月度交易明细    : {len(details)}笔交易（主数据源）')
    print(f'  5-政策前后对比    : 18个月批零价差（含政策后+2026年）')
    print(f'  6-政策时间线      : 10个关键事件')
    print(f'  7-函数速查表      : 7个常用函数')
    print(f'')
    print(f'【数据说明】')
    print(f'  2025年1-7月  : 实际数据（来自交易中心公告/行业媒体）')
    print(f'  2025年8-12月 : 模拟数据（基于政策趋势推算）')
    print(f'  2026年1-6月  : 模拟数据（基于2026年政策框架推算）')
    return OUTPUT_PATH


if __name__ == '__main__':
    build_practice_excel()
