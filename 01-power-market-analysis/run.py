"""
run.py — 项目入口脚本
=====================
一键运行：python run.py
查看帮助：python run.py --help
仅校验数据：python run.py --validate-only
"""

import sys
import os
import io
import argparse
from datetime import datetime

# Windows GBK编码兼容
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 确保能找到同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def validate_data():
    """
    数据校验 —— 在分析前检查数据完整性
    返回 (is_valid, warnings, errors)
    """
    from data_collection import (
        wholesale_monthly, retail_monthly, spread_data,
        generation_cumulative
    )

    warnings = []
    errors = []

    # 检查1：核心数据表不能为空
    if wholesale_monthly.empty:
        errors.append('批发侧月度数据表为空！至少需要填入数据。')
    if generation_cumulative.empty:
        errors.append('发电侧数据表为空！')

    # 检查2：关键列不能有负数
    for col in ['批发结算电量_亿kWh', '批发结算均价_元每MWh']:
        if col in wholesale_monthly.columns:
            if (wholesale_monthly[col] < 0).any():
                errors.append(f'批发侧「{col}」存在负数，请检查数据。')

    # 检查3：估算数据占比提醒
    if '数据质量' in wholesale_monthly.columns:
        quality_counts = wholesale_monthly['数据质量'].value_counts()
        total = len(wholesale_monthly)
        estimated = quality_counts.get('估算', 0)
        missing = quality_counts.get('缺失', 0)
        if estimated + missing > total * 0.3:
            warnings.append(
                f'批发侧数据中估算+缺失占比 {(estimated+missing)/total*100:.0f}%（>{30}%），'
                '分析结论的可信度会降低。建议补充实际数据。'
            )

    # 检查4：零售侧数据点太少
    if len(retail_monthly) < 3:
        warnings.append(
            f'零售侧只有 {len(retail_monthly)} 个数据点，批零价差分析可能不够可靠。'
        )

    # 检查5：均价数值合理性（陕西电价正常范围200-500元/MWh）
    if '批发结算均价_元每MWh' in wholesale_monthly.columns:
        prices = wholesale_monthly['批发结算均价_元每MWh']
        if (prices < 100).any() or (prices > 800).any():
            errors.append('批发侧存在异常电价（<100或>800元/MWh），请核实数据来源。')

    return (len(errors) == 0, warnings, errors)


def run_analysis():
    """运行完整分析流程"""
    print('=' * 60)
    print('  陕西省电力市场月度电价趋势分析')
    print(f'  运行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

    # ---------- 步骤0：数据校验 ----------
    print('\n[步骤 0/4] 数据校验...')
    is_valid, warnings, errors = validate_data()

    if warnings:
        print('  [WARN] 警告：')
        for w in warnings:
            print(f'    - {w}')

    if errors:
        print('  [ERR] 错误：')
        for e in errors:
            print(f'    - {e}')
        print('\n  请修复以上错误后重新运行。')
        print('  提示：检查 data_collection.py 中的数据。')
        return False

    if not warnings:
        print('  [OK] 数据校验通过，未发现问题。')

    # ---------- 步骤1：生成图表 ----------
    print('\n[步骤 1/4] 生成图表...')
    try:
        from analysis import chart1_price_trend, chart2_market_structure, chart3_generation_analysis
        chart1_price_trend()
        chart2_market_structure()
        chart3_generation_analysis()
    except Exception as e:
        print(f'  [ERR] 图表生成失败: {e}')
        print('  常见原因：matplotlib字体问题。尝试安装中文字体。')
        return False

    # ---------- 步骤2：导出Excel ----------
    print('\n[步骤 2/4] 导出Excel...')
    try:
        from analysis import export_excel
        export_excel()
    except PermissionError:
        print(f'  [ERR] Excel导出失败: 文件被占用，请关闭 Excel 后重试。')
        return False
    except Exception as e:
        print(f'  [ERR] Excel导出失败: {e}')
        return False

    # ---------- 步骤3：生成报告 ----------
    print('\n[步骤 3/4] 生成分析报告...')
    try:
        from analysis import generate_report
        generate_report()
    except Exception as e:
        print(f'  [ERR] 报告生成失败: {e}')
        return False

    # ---------- 完成 ----------
    output_dir = os.path.dirname(os.path.abspath(__file__))
    print('\n' + '=' * 60)
    print('  [OK] 全部完成！')
    print(f'  输出目录: {output_dir}')
    print('=' * 60)
    return True


def main():
    parser = argparse.ArgumentParser(
        description='陕西省电力市场月度电价趋势分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python run.py                  # 运行完整分析
  python run.py --validate-only  # 仅校验数据，不生成输出
  python run.py --help           # 查看帮助
        """
    )
    parser.add_argument(
        '--validate-only', action='store_true',
        help='仅执行数据校验，不生成图表和报告'
    )
    parser.add_argument(
        '--version', action='version',
        version='陕西电力市场分析工具 v1.0 (2026-06)'
    )

    args = parser.parse_args()

    if args.validate_only:
        print('数据校验模式')
        print('=' * 40)
        is_valid, warnings, errors = validate_data()
        if warnings:
            print('\n[WARN] 警告：')
            for w in warnings:
                print(f'  - {w}')
        if errors:
            print('\n[ERR] 错误：')
            for e in errors:
                print(f'  - {e}')
        if not warnings and not errors:
            print('\n[OK] 数据校验全部通过！')
        return 0 if is_valid else 1

    success = run_analysis()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
