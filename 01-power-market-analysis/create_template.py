"""
生成「数据录入模板.xlsx」
用途：当你从交易中心官网下载到原始PDF/Excel公告后，
     把数据填进这个模板，然后更新 data_collection.py
"""

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
import os

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(OUTPUT_DIR, '数据录入模板.xlsx')


def style_header(ws, row, ncols, fill_color='1A5276'):
    """给表头行加样式"""
    header_fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type='solid')
    header_font = Font(name='微软雅黑', size=11, bold=True, color='FFFFFF')
    for col in range(1, ncols + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')


def auto_width(ws, ncols, min_width=10, max_width=30):
    """自动调整列宽"""
    for col in range(1, ncols + 1):
        letter = get_column_letter(col)
        max_len = min_width
        for row in ws.iter_rows(min_col=col, max_col=col, values_only=True):
            for cell_val in row:
                if cell_val:
                    max_len = max(max_len, min(len(str(cell_val)) + 2, max_width))
        ws.column_dimensions[letter].width = max_len


def create_template():
    wb = Workbook()

    # ========================
    # Sheet 1: 使用说明
    # ========================
    ws0 = wb.active
    ws0.title = '0-使用说明'
    instructions = [
        ['数据录入模板 — 使用说明', '', ''],
        ['', '', ''],
        ['用途', '从陕西电力交易中心官网下载原始公告后，把数据填进对应Sheet，然后更新 data_collection.py 中的对应数据', ''],
        ['数据来源', 'pmos.sn.sgcc.com.cn → 信息披露 → 市场运营 → 交易组织及出清 → 中长期交易 → 申报及成交情况', ''],
        ['', '', ''],
        ['填写规则', '', ''],
        ['1', '灰色底色的单元格 = 表头，不要修改', ''],
        ['2', '白色底色的单元格 = 需要你填写', ''],
        ['3', '黄色底色的单元格 = 选填（有就填，没有就留空）', ''],
        ['4', '"数据质量"列：下拉选择"实际"或"估算"', ''],
        ['5', '单位不要写进单元格（比如"359.76"而不是"359.76元/MWh"），单位在表头已标注', ''],
        ['', '', ''],
        ['填写完成后', '1. 打开 data_collection.py', ''],
        ['', '2. 把模板里的数据复制到对应的 DataFrame 变量中', ''],
        ['', '3. 运行 python analysis.py 重新生成所有输出', ''],
    ]
    for row in instructions:
        ws0.append(row)
    ws0.column_dimensions['A'].width = 18
    ws0.column_dimensions['B'].width = 70
    ws0.merge_cells('A1:C1')
    ws0['A1'].font = Font(name='微软雅黑', size=14, bold=True, color='1A5276')

    # ========================
    # Sheet 2: 批发侧月度数据
    # ========================
    ws1 = wb.create_sheet('1-批发侧月度数据')
    headers1 = ['月份', '批发结算电量(亿kWh)', '批发结算均价(元/MWh)', '数据质量', '备注']
    ws1.append(headers1)
    style_header(ws1, 1, len(headers1))

    # 预填示例数据
    sample_data = [
        ['2025-01', 89.36, 359.76, '实际', '来源：北极星电力网转载'],
        ['2025-02', 81.39, 349.49, '实际', ''],
        ['2025-03', None, None, '估算', '需从PDF核实'],
        ['2025-04', None, None, '估算', '需从PDF核实'],
        ['2025-05', None, None, '估算', '需从PDF核实'],
        ['2025-06', 90.35, 336.60, '实际', '来源：钢之家转载'],
        ['2025-07', 97.82, 329.50, '实际', ''],
        ['2025-08', None, None, None, '待获取'],
        ['2025-09', None, None, None, '待获取'],
        ['2025-10', None, None, None, '待获取'],
        ['2025-11', None, None, None, '待获取'],
        ['2025-12', None, None, None, '待获取'],
    ]
    for row in sample_data:
        ws1.append(row)

    # 数据验证：数据质量列下拉
    dv = DataValidation(type='list', formula1='"实际,估算,缺失"', allow_blank=True)
    dv.error = '请选择：实际、估算 或 缺失'
    ws1.add_data_validation(dv)
    for row in range(3, 15):
        dv.add(ws1.cell(row=row, column=4))

    auto_width(ws1, len(headers1))

    # ========================
    # Sheet 3: 零售侧月度数据
    # ========================
    ws2 = wb.create_sheet('2-零售侧月度数据')
    headers2 = ['月份', '零售结算电量(亿kWh)', '零售结算均价(元/MWh)', '数据质量', '备注']
    ws2.append(headers2)
    style_header(ws2, 1, len(headers2))

    retail_sample = [
        ['2025-01', 88.23, 367.54, '实际', ''],
        ['2025-02', 80.37, 366.82, '实际', ''],
        ['2025-03', None, None, '缺失', '需从PDF获取'],
        ['2025-04', None, None, '缺失', '需从PDF获取'],
        ['2025-05', None, None, '缺失', '需从PDF获取'],
        ['2025-06', None, None, '缺失', '需从PDF获取'],
        ['2025-07', 97.82, 362.90, '实际', ''],
    ]
    for row in retail_sample:
        ws2.append(row)

    dv2 = DataValidation(type='list', formula1='"实际,估算,缺失"', allow_blank=True)
    ws2.add_data_validation(dv2)
    for row in range(3, 10):
        dv2.add(ws2.cell(row=row, column=4))

    auto_width(ws2, len(headers2))

    # ========================
    # Sheet 4: 交易品种分解
    # ========================
    ws3 = wb.create_sheet('3-交易品种分解')
    headers3 = ['月份', '交易品种', '成交量(亿kWh)', '成交均价(元/MWh)', '数据质量', '来源']
    ws3.append(headers3)
    style_header(ws3, 1, len(headers3))

    varieties = ['双边协商', '集中竞价', '挂牌交易']
    for month in ['2025-06', '2025-07', '2025-08']:
        for var in varieties:
            ws3.append([month, var, None, None, '缺失', ''])

    dv3 = DataValidation(type='list', formula1='"实际,估算,缺失"', allow_blank=True)
    ws3.add_data_validation(dv3)
    for row in range(2, 12):
        dv3.add(ws3.cell(row=row, column=5))

    auto_width(ws3, len(headers3))

    # ========================
    # Sheet 5: 分时电价
    # ========================
    ws4 = wb.create_sheet('4-分时电价(选填)')
    headers4 = ['日期', '时段', '时段类型(峰/平/谷)', '电价(元/MWh)', '数据质量']
    ws4.append(headers4)
    style_header(ws4, 1, len(headers4))

    periods = ['00:00-08:00', '08:00-11:00', '11:00-17:00', '17:00-22:00', '22:00-24:00']
    types = ['谷', '平', '平', '峰', '平']
    for date in ['2025-07-01', '2025-07-15', '2025-07-31']:
        for per, tp in zip(periods, types):
            ws4.append([date, per, tp, None, '缺失'])

    dv4 = DataValidation(type='list', formula1='"实际,估算,缺失"', allow_blank=True)
    ws4.add_data_validation(dv4)
    for row in range(2, 18):
        dv4.add(ws4.cell(row=row, column=5))

    auto_width(ws4, len(headers4))

    # 用黄色标记选填Sheet
    light_yellow = PatternFill(start_color='FFF8E1', end_color='FFF8E1', fill_type='solid')
    for row in ws4.iter_rows(min_row=1, max_row=1):
        for cell in row:
            cell.fill = PatternFill(start_color='F39C12', end_color='F39C12', fill_type='solid')

    # 保存
    wb.save(OUTPUT_PATH)
    print(f'[OK] 数据录入模板已生成: {OUTPUT_PATH}')
    print(f'     包含5个Sheet: 使用说明 | 批发侧 | 零售侧 | 交易品种 | 分时电价')
    return OUTPUT_PATH


if __name__ == '__main__':
    create_template()
