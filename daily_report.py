# market-daily-report
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ------------------ 数据获取函数（带容错）------------------
def get_market_data():
    """获取所有需要的数据，返回字典"""
    data = {}
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 1. 融资余额（前一交易日）
    try:
       融 = ak.stock_market_activity_em(symbol="融资融券")  # 示例接口，可能需调整
        # 若接口变动，可用备用：ak.stock_finance_em() 等，但这里保持与最新akshare一致
        # 注意：akshare接口经常变，建议使用最新版，以下为参考写法
        # 实际我们用更稳定的方式：从东方财富获取融资融券历史
        # 采用稳妥写法：
        df_rz = ak.stock_finance_em(symbol="融资融券", date=today)  # 若出错则用前一日
        if df_rz.empty:
            # 尝试获取前一日
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            df_rz = ak.stock_finance_em(symbol="融资融券", date=yesterday)
        if not df_rz.empty:
            data['融资余额'] = df_rz.iloc[-1]['融资余额'] / 1e8  # 单位转亿
            data['融资净买入'] = df_rz.iloc[-1]['融资净买入'] / 1e8
    except Exception as e:
        data['融资余额'] = None
        data['融资净买入'] = None
        print(f"融资数据获取失败: {e}")
    
    # 2. 全市场成交额 & 涨跌家数
    try:
        df_quote = ak.stock_zh_a_spot_em()
        data['成交额(亿)'] = df_quote['成交额'].sum() / 1e8
        data['上涨家数'] = (df_quote['涨跌幅'] > 0).sum()
        data['下跌家数'] = (df_quote['涨跌幅'] < 0).sum()
    except Exception as e:
        data['成交额(亿)'] = None
        data['上涨家数'] = None
        data['下跌家数'] = None
        print(f"行情数据获取失败: {e}")
    
    # 3. 重点ETF份额变化（近5日）
    try:
        # 列举几只重点ETF代码，也可增加
        etf_codes = {
            '科创50': '588000',
            '半导体': '512480',
            '沪深300': '510300'
        }
        etf_data = {}
        for name, code in etf_codes.items():
            df_etf = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=(datetime.now()-timedelta(days=10)).strftime('%Y%m%d'))
            if not df_etf.empty:
                # 获取最近5日份额变化（假设有'份额'列，实际akshare可能返回'总份额'）
                # 注意：可能接口字段名不同，此处简化，实际需根据akshare版本调整
                # 若获取不到，可跳过
                df_etf['份额'] = df_etf['总份额']  # 假设列名
                latest = df_etf.iloc[-1]['份额']
                five_day_ago = df_etf.iloc[-5]['份额'] if len(df_etf)>=5 else latest
                etf_data[name] = (latest - five_day_ago) / 1e4  # 单位万份
            else:
                etf_data[name] = None
        data['ETF近5日净申赎(万份)'] = etf_data
    except Exception as e:
        data['ETF近5日净申赎(万份)'] = None
        print(f"ETF数据获取失败: {e}")
    
    # 4. 股指期货基差（主力合约）
    try:
        # 获取中金所期货数据，此处仅示例，实际可用ak.futures_main_sina()等
        # 简化：从新浪获取主力连续
        futures_list = [
            ('IH', '上证50'), ('IF', '沪深300'), ('IC', '中证500'), ('IM', '中证1000')
        ]
        basis = {}
        for symbol, name in futures_list:
            df_f = ak.futures_main_sina(symbol=symbol)  # 可能需指定symbol
            if not df_f.empty:
                # 获取最新价和现价，计算基差（需对应现货指数）
                # 这里简化，仅获取收盘价，基差需现货指数，我们直接从行情获取
                # 为简化，我们只取期货收盘价，基差留空，实际可用ak.stock_zh_index_spot获取现货
                basis[name] = df_f.iloc[-1]['收盘价']
            else:
                basis[name] = None
        data['期货收盘价'] = basis
        # 获取现货指数收盘
        index_codes = {'上证50': '000016', '沪深300': '000300', '中证500': '000905', '中证1000': '000852'}
        spot = {}
        for name, code in index_codes.items():
            df_idx = ak.stock_zh_index_spot_em(symbol=code)
            if not df_idx.empty:
                spot[name] = df_idx.iloc[-1]['最新价']
            else:
                spot[name] = None
        # 计算基差（期货-现货）
        basis_diff = {}
        for name in basis:
            if basis[name] and spot.get(name):
                basis_diff[name] = round((basis[name] - spot[name]) / spot[name] * 100, 2)  # 百分比
            else:
                basis_diff[name] = None
        data['基差(%)'] = basis_diff
    except Exception as e:
        data['基差(%)'] = None
        print(f"期货数据获取失败: {e}")
    
    # 5. 10年国债收益率
    try:
        df_bond = ak.bond_china_yield()  # 可能接口名
        if not df_bond.empty:
            data['10Y国债收益率'] = df_bond.iloc[-1]['收益率']
    except:
        data['10Y国债收益率'] = None
    
    return data

def generate_report(data):
    """生成诊断报告文本"""
    today = datetime.now().strftime('%Y-%m-%d')
    report = f"# 📊 市场诊断报告 {today}\n\n"
    
    # 杠杆温度
    rz = data.get('融资余额')
    rz_net = data.get('融资净买入')
    if rz is not None:
        report += f"## 🔥 杠杆资金\n- 融资余额：{rz:.2f} 亿\n"
        if rz_net is not None:
            report += f"- 当日净买入：{rz_net:+.2f} 亿\n"
            if rz_net < -50:
                report += "- ⚠️ 净卖出超过50亿，去化压力明显\n"
    else:
        report += "## 🔥 杠杆资金\n- 数据获取失败\n"
    
    # 成交与涨跌
    volume = data.get('成交额(亿)')
    up = data.get('上涨家数')
    down = data.get('下跌家数')
    if volume:
        report += f"\n## 📈 市场活跃度\n- 全A成交额：{volume:.0f} 亿\n"
        if up is not None and down is not None:
            total = up+down
            report += f"- 涨跌家数：{up}/{down}（上涨比例 {up/total*100:.1f}%）\n"
    else:
        report += "\n## 📈 市场活跃度\n- 数据获取失败\n"
    
    # ETF资金
    etf = data.get('ETF近5日净申赎(万份)')
    if etf and isinstance(etf, dict):
        report += "\n## 💰 重点ETF资金流向（近5日净申赎）\n"
        for name, val in etf.items():
            if val is not None:
                report += f"- {name}：{val:+.0f} 万份\n"
            else:
                report += f"- {name}：数据缺失\n"
    else:
        report += "\n## 💰 重点ETF资金流向\n- 数据获取失败\n"
    
    # 股指期货基差
    basis = data.get('基差(%)')
    if basis and isinstance(basis, dict):
        report += "\n## 📉 股指期货基差（现货为基准）\n"
        for name, val in basis.items():
            if val is not None:
                report += f"- {name}：{val:+.2f}%\n"
            else:
                report += f"- {name}：缺失\n"
    else:
        report += "\n## 📉 股指期货基差\n- 数据获取失败\n"
    
    # 国债收益率
    bond = data.get('10Y国债收益率')
    if bond:
        report += f"\n## 💹 宏观水位\n- 10Y国债收益率：{bond:.2f}%\n"
    
    # 综合诊断（简单规则）
    report += "\n## 🧭 综合视角\n"
    signals = []
    if rz is not None and rz > 25000:  # 假设高位阈值
        signals.append("融资余额高位运行")
    if volume and volume < 20000:
        signals.append("成交额偏低，市场缩量")
    # 可根据更多条件添加
    if signals:
        report += "- " + "；".join(signals) + "\n"
    else:
        report += "- 无明显极端信号，保持中性\n"
    
    report += "\n---\n*本报告由自动脚本生成，仅供参考。*"
    return report

if __name__ == "__main__":
    print("开始获取市场数据...")
    data = get_market_data()
    report_text = generate_report(data)
    # 保存文件，以日期命名
    filename = f"report_{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f"报告已生成：{filename}")
