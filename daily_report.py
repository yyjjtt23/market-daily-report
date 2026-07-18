# market-daily-report
import requests
import re
import json
from datetime import datetime, timedelta
import pandas as pd

# ------------------ 使用东方财富网公开API（较稳定）------------------
def get_rzrq():
    """获取融资融券概况（前一交易日）"""
    url = "http://data.eastmoney.com/DataCenter_V3/zqrzrq.ashx"
    params = {
        'cb': 'jQuery',
        'pageSize': 1,
        'sortRule': -1,
        'sortType': 'RZRQHQ',
        'type': 'RZRQHQ',
        'date': '',
        'token': '4f1862fc3b5e77c150a2b985b12db0fd'
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        text = resp.text
        # 解析JSONP
        json_str = re.search(r'\((.*)\)', text).group(1)
        data = json.loads(json_str)['data'][0]
        return {
            '融资余额': float(data['RZYL']) / 1e8,
            '融资净买入': float(data['RZJMR']) / 1e8
        }
    except:
        return None

def get_market_overview():
    """获取沪深两市总成交额及涨跌家数"""
    url = "http://push2.eastmoney.com/api/qt/stock/get"
    params = {
        'secid': '1.000001',  # 上证指数
        'fields': 'f57,f58,f60,f107,f168,f169,f170,f171'
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()['data']
        # 需要深证指数也获取，这里简化只取上证，或使用另一接口
        # 更稳妥：从股票列表汇总
        # 此处改用股票列表API
        url_list = "http://push2.eastmoney.com/api/qt/clist/get"
        params_list = {
            'pn': 1,
            'pz': 5000,
            'po': 1,
            'np': 1,
            'fltt': 2,
            'invt': 2,
            'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23',
            'fields': 'f43,f44'  # 涨跌幅
        }
        resp2 = requests.get(url_list, params=params_list, timeout=10)
        data2 = resp2.json()['data']['diff']
        up = sum(1 for item in data2 if float(item.get('f43',0)) > 0)
        down = sum(1 for item in data2 if float(item.get('f43',0)) < 0)
        # 总成交额从另一个接口获取
        url_vol = "http://push2.eastmoney.com/api/qt/stock/get"
        params_vol = {
            'secid': '1.000001',
            'fields': 'f57,f58,f60'
        }
        resp_vol = requests.get(url_vol, params=params_vol, timeout=10)
        vol = resp_vol.json()['data']['f57']  # 成交额单位万元？需验证
        # 实际东财成交额单位是元，除以1e8得到亿
        return {
            '成交额(亿)': float(vol) / 1e8 if vol else None,
            '上涨家数': up,
            '下跌家数': down
        }
    except:
        return None

def get_etf_flow(code, days=5):
    """获取单只ETF份额变化（近days日）"""
    # 使用天天基金接口
    url = f"http://fund.eastmoney.com/pingzhongdata/{code}.js"
    try:
        resp = requests.get(url, timeout=10)
        text = resp.text
        # 解析份额数据（示例，实际需从js中提取）
        # 因为天天基金接口返回的是js变量，需正则提取
        # 此处简化，暂返回None，我们可以用备选方案：从网页爬取
        # 为保持稳定，此功能可暂时放弃或使用手动更新方式
        return None
    except:
        return None

def get_bond_yield():
    """获取10年期国债收益率"""
    url = "http://www.chinabond.com.cn/portal/xg/queryYjxz"
    # 实际上这个接口较复杂，我们使用新浪财经
    url_sina = "http://hq.sinajs.cn/list=bond_cn10"
    try:
        resp = requests.get(url_sina, timeout=10)
        text = resp.text
        # 格式：var hq_str_bond_cn10="...,...";
        val = text.split('"')[1].split(',')[1]  # 第二个字段是收益率
        return float(val)
    except:
        return None

def get_futures_basis():
    """获取期指基差（简化）"""
    # 获取四个主力合约收盘价和现货指数
    symbols = {
        'IH': '000016',  # 上证50
        'IF': '000300',  # 沪深300
        'IC': '000905',  # 中证500
        'IM': '000852'   # 中证1000
    }
    basis = {}
    # 获取期货行情（用新浪）
    for sym in symbols:
        url_f = f"http://hq.sinajs.cn/list={sym}0"  # 主力连续
        try:
            resp = requests.get(url_f, timeout=10)
            txt = resp.text
            # 解析期货价格
            parts = txt.split(',')
            if len(parts) > 1:
                price = float(parts[1])  # 最新价
                # 获取现货指数
                url_s = f"http://hq.sinajs.cn/list=s_sh{symbols[sym]}"
                resp_s = requests.get(url_s, timeout=10)
                txt_s = resp_s.text
                spot = float(txt_s.split(',')[1]) if txt_s else None
                if spot:
                    basis[sym] = round((price - spot) / spot * 100, 2)
        except:
            pass
    return basis

def generate_report_simple(data_dict):
    """生成报告"""
    today = datetime.now().strftime('%Y-%m-%d')
    report = f"# 📊 市场诊断报告 {today}\n\n"
    
    if data_dict.get('融资余额'):
        report += f"## 🔥 杠杆资金\n- 融资余额：{data_dict['融资余额']:.2f} 亿\n"
        report += f"- 当日净买入：{data_dict.get('融资净买入',0):+.2f} 亿\n"
    else:
        report += "## 🔥 杠杆资金\n- 数据暂缺\n"
    
    if data_dict.get('成交额(亿)'):
        report += f"\n## 📈 市场活跃度\n- 全A成交额：{data_dict['成交额(亿)']:.0f} 亿\n"
        if '上涨家数' in data_dict:
            up = data_dict['上涨家数']; down = data_dict['下跌家数']
            report += f"- 涨跌家数：{up}/{down}（上涨比例 {up/(up+down)*100:.1f}%）\n"
    else:
        report += "\n## 📈 市场活跃度\n- 数据暂缺\n"
    
    if data_dict.get('基差'):
        report += "\n## 📉 股指期货基差（%）\n"
        for k,v in data_dict['基差'].items():
            report += f"- {k}：{v:+.2f}\n"
    else:
        report += "\n## 📉 股指期货基差\n- 数据暂缺\n"
    
    bond = data_dict.get('10Y国债收益率')
    if bond:
        report += f"\n## 💹 宏观水位\n- 10Y国债收益率：{bond:.2f}%\n"
    
    report += "\n---\n*本报告由自动脚本生成，仅供参考。*"
    return report

if __name__ == "__main__":
    print("开始获取数据...")
    data = {}
    data.update(get_rzrq() or {})
    data.update(get_market_overview() or {})
    data['基差'] = get_futures_basis()
    data['10Y国债收益率'] = get_bond_yield()
    report = generate_report_simple(data)
    filename = f"report_{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    print("完成")
