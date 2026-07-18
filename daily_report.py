# -*- coding: utf-8 -*-
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time
import warnings
import requests
import re
import json
warnings.filterwarnings('ignore')

# ------------------ 辅助函数：带重试的数据获取 ------------------
def fetch_with_retry(func, retries=3, delay=5):
    """通用重试函数，尝试多次获取数据"""
    for i in range(retries):
        try:
            result = func()
            # 检查结果是否有效
            if result is not None:
                if isinstance(result, dict) and len(result) == 0:
                    continue
                if isinstance(result, pd.DataFrame) and result.empty:
                    continue
                return result
        except Exception as e:
            print(f"  尝试 {i+1}/{retries} 失败: {type(e).__name__}: {e}")
            if i < retries - 1:
                time.sleep(delay)
    return None

# ------------------ 1. 融资余额（增强稳定性） ------------------
def get_rzrq():
    """获取融资融券概况，使用双重数据源"""
    # 方案1: 使用 akshare
    try:
        df = ak.stock_market_activity_em(symbol="融资融券")
        if df is not None and not df.empty:
            last = df.iloc[-1]
            return {
                '融资余额': float(last['融资余额']) / 1e8,
                '融资净买入': float(last['融资净买入']) / 1e8
            }
    except:
        pass
    
    # 方案2: 直接从东方财富数据接口获取
    try:
        url = "http://data.eastmoney.com/DataCenter_V3/zqrzrq.ashx"
        params = {
            'cb': 'jQuery',
            'pageSize': 1,
            'sortRule': -1,
            'sortType': 'RZRQHQ',
            'type': 'RZRQHQ',
            'token': '4f1862fc3b5e77c150a2b985b12db0fd'
        }
        resp = requests.get(url, params=params, timeout=15)
        text = resp.text
        json_str = re.search(r'\((.*)\)', text).group(1)
        data = json.loads(json_str)['data'][0]
        return {
            '融资余额': float(data['RZYL']) / 1e8,
            '融资净买入': float(data['RZJMR']) / 1e8
        }
    except:
        return None

# ------------------ 2. 市场活跃度 + 万得全A指数 ------------------
def get_market_overview():
    """获取全市场成交额、涨跌家数及万得全A指数"""
    result = {'成交额(亿)': None, '上涨家数': None, '下跌家数': None, '万得全A': None}
    
    # 获取A股实时行情
    try:
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            # 成交额和涨跌家数
            result['成交额(亿)'] = round(df['成交额'].sum() / 1e8, 0)
            result['上涨家数'] = int((df['涨跌幅'] > 0).sum())
            result['下跌家数'] = int((df['涨跌幅'] < 0).sum())
            
            # 尝试获取万得全A（代码881001）
            try:
                # 方法1：从akshare获取指数行情
                df_idx = ak.stock_zh_index_spot_em()
                if df_idx is not None and not df_idx.empty:
                    wind_row = df_idx[df_idx['代码'] == '881001']
                    if not wind_row.empty:
                        result['万得全A'] = float(wind_row.iloc[0]['最新价'])
            except:
                pass
            
            # 如果万得全A还未获取到，用备选方法
            if result['万得全A'] is None:
                try:
                    # 直接从新浪获取
                    url = "http://hq.sinajs.cn/list=sh000985"  # 万得全A新浪代码
                    resp = requests.get(url, timeout=10)
                    text = resp.text
                    if text and '=' in text:
                        parts = text.split(',')
                        if len(parts) > 1:
                            result['万得全A'] = float(parts[1])
                except:
                    pass
    except:
        pass
    
    return result

# ------------------ 3. 重点ETF净申赎（使用完整清单） ------------------
def get_etf_flow():
    """获取指定ETF近5日份额变化"""
    # 按用户提供的清单整理
    etf_list = {
        # ---- A股宽基 ----
        '沪深300': '510300',
        '上证50': '510050',
        '中证A500': '560500',
        '中证500': '510500',
        '中证1000': '159629',
        '中证2000': '159532',
        '科创50': '588000',
        '创业板': '159915',
        '双创50': '159782',
        '科创100': '588220',
        '中证红利': '515080',
        # ---- A股行业板块 ----
        '科创芯片': '588200',
        '通信': '515880',
        'AI算力': '560880',
        '软件': '159633',
        '新能源车': '159797',
        '光伏': '512410',
        '主要消费': '159928',
        '酒': '512690',
        '医疗': '512170',
        '创新药': '159992',
        '证券': '512880',
        '银行': '512700',
        '机器人': '562360',
        # ---- A股场内人民币港股ETF ----
        '恒生指数': '159920',
        '恒生H股': '510900',
        '恒生互联网': '513330',
    }
    
    result = {}
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=15)).strftime('%Y%m%d')
    
    for name, code in etf_list.items():
        try:
            df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                # 提取总份额列
                shares_col = None
                for col in ['总份额', '份额', '基金份额']:
                    if col in df.columns:
                        shares_col = col
                        break
                if shares_col is None:
                    result[name] = None
                    continue
                
                shares = df[shares_col]
                if len(shares) >= 6:  # 需要足够数据计算5日变化
                    change = shares.iloc[-1] - shares.iloc[-6]  # 从5个交易日前的数据到最新
                elif len(shares) > 1:
                    change = shares.iloc[-1] - shares.iloc[0]
                else:
                    change = 0
                # 转换为万份，保留整数
                result[name] = round(change / 10000, 0) if abs(change) < 1e12 else None
            else:
                result[name] = None
        except Exception as e:
            print(f"  ETF {name}({code}) 获取失败: {type(e).__name__}")
            result[name] = None
        # 加入短暂延迟，避免请求过快
        time.sleep(0.3)
    
    return result

# ------------------ 4. 股指期货基差（使用akshare） ------------------
def get_futures_basis():
    """获取四大股指期货基差（%）"""
    futures_symbols = {
        'IH': '000016',  # 上证50
        'IF': '000300',  # 沪深300
        'IC': '000905',  # 中证500
        'IM': '000852'   # 中证1000
    }
    basis = {}
    
    # 获取现货指数
    index_spot = {}
    try:
        df_index = ak.stock_zh_index_spot_em()
        if df_index is not None and not df_index.empty:
            for name, code in futures_symbols.items():
                row = df_index[df_index['代码'] == code]
                if not row.empty:
                    index_spot[name] = float(row.iloc[0]['最新价'])
    except:
        pass
    
    # 获取期货主力合约
    for sym in futures_symbols.keys():
        try:
            df_fut = ak.futures_main_sina(symbol=sym)
            if df_fut is not None and not df_fut.empty:
                last = df_fut.iloc[-1]
                fut_price = float(last['收盘价'])
                spot_price = index_spot.get(sym)
                if spot_price and spot_price > 0:
                    basis[sym] = round((fut_price - spot_price) / spot_price * 100, 2)
                else:
                    basis[sym] = None
            else:
                basis[sym] = None
        except Exception as e:
            print(f"  期货 {sym} 获取失败: {e}")
            basis[sym] = None
        time.sleep(0.3)
    
    return basis

# ------------------ 5. 10年期国债收益率 ------------------
def get_bond_yield():
    """获取10年国债收益率"""
    try:
        df = ak.bond_china_yield()
        if df is not None and not df.empty:
            if '10年' in df.columns:
                return float(df.iloc[-1]['10年'])
            elif '收益率' in df.columns:
                return float(df.iloc[-1]['收益率'])
    except:
        pass
    
    # 备用：从新浪
    try:
        url = "http://hq.sinajs.cn/list=bond_cn10"
        resp = requests.get(url, timeout=10)
        text = resp.text
        if text and '=' in text:
            parts = text.split(',')
            if len(parts) > 1:
                return float(parts[1])
    except:
        pass
    return None

# ------------------ 6. 生成最终报告 ------------------
def generate_report():
    """生成完整诊断报告"""
    today = datetime.now().strftime('%Y-%m-%d')
    report = f"# 📊 市场诊断报告 {today}\n\n"
    report += f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    # 1. 杠杆资金
    print("🔍 获取融资数据...")
    rz_data = fetch_with_retry(get_rzrq)
    if rz_data:
        report += f"## 🔥 杠杆资金\n"
        report += f"- **融资余额**：{rz_data['融资余额']:.2f} 亿\n"
        report += f"- **当日净买入**：{rz_data['融资净买入']:+.2f} 亿\n\n"
    else:
        report += "## 🔥 杠杆资金\n- ⚠️ 数据暂缺\n\n"
    
    # 2. 市场活跃度 + 万得全A
    print("🔍 获取市场概况...")
    mkt_data = fetch_with_retry(get_market_overview)
    if mkt_data:
        report += f"## 📈 市场活跃度\n"
        if mkt_data.get('成交额(亿)'):
            report += f"- **全A成交额**：{mkt_data['成交额(亿)']:.0f} 亿\n"
        if mkt_data.get('上涨家数') and mkt_data.get('下跌家数'):
            up = mkt_data['上涨家数']; down = mkt_data['下跌家数']
            total = up+down
            report += f"- **涨跌家数**：{up} / {down}（上涨比例 {up/total*100:.1f}%）\n"
        if mkt_data.get('万得全A'):
            report += f"- **万得全A指数**：{mkt_data['万得全A']:.2f}\n"
        report += "\n"
    else:
        report += "## 📈 市场活跃度\n- ⚠️ 数据暂缺\n\n"
    
    # 3. ETF资金流向（完整清单）
    print("🔍 获取ETF数据（可能需要1-2分钟）...")
    etf_flow = fetch_with_retry(get_etf_flow)
    if etf_flow and any(v is not None for v in etf_flow.values()):
        report += "## 💰 重点ETF净申赎（近5日，万份）\n\n"
        # 按类别分组显示（保持结构清晰）
        categories = {
            'A股宽基': ['沪深300', '上证50', '中证A500', '中证500', '中证1000', '中证2000', 
                       '科创50', '创业板', '双创50', '科创100', '中证红利'],
            '行业板块': ['科创芯片', '通信', 'AI算力', '软件', '新能源车', '光伏', 
                       '主要消费', '酒', '医疗', '创新药', '证券', '银行', '机器人'],
            '港股ETF': ['恒生指数', '恒生H股', '恒生互联网']
        }
        for cat, names in categories.items():
            report += f"### {cat}\n"
            for name in names:
                val = etf_flow.get(name)
                if val is not None:
                    report += f"- {name}：{val:+.0f}\n"
                else:
                    report += f"- {name}：⚠️ 数据缺失\n"
            report += "\n"
    else:
        report += "## 💰 重点ETF净申赎\n- ⚠️ 数据暂缺\n\n"
    
    # 4. 股指期货基差
    print("🔍 获取期货基差...")
    basis = fetch_with_retry(get_futures_basis)
    if basis and any(v is not None for v in basis.values()):
        report += "## 📉 股指期货基差（%）\n"
        for name, val in basis.items():
            if val is not None:
                report += f"- {name}：{val:+.2f}\n"
            else:
                report += f"- {name}：⚠️ 缺失\n"
        report += "\n"
    else:
        report += "## 📉 股指期货基差\n- ⚠️ 数据暂缺\n\n"
    
    # 5. 国债收益率
    print("🔍 获取债券收益率...")
    bond = fetch_with_retry(get_bond_yield)
    if bond:
        report += f"## 💹 宏观水位\n- **10Y国债收益率**：{bond:.2f}%\n\n"
    
    # 6. 综合诊断（简化）
    report += "## 🧭 综合视角\n"
    signals = []
    if rz_data and rz_data['融资余额'] > 25000:
        signals.append("融资余额高位（>2.5万亿）")
    if mkt_data and mkt_data.get('成交额(亿)') and mkt_data['成交额(亿)'] < 20000:
        signals.append("成交额偏低（<2万亿）")
    if mkt_data and mkt_data.get('上涨家数') and mkt_data.get('下跌家数'):
        if mkt_data['上涨家数'] / (mkt_data['上涨家数']+mkt_data['下跌家数']) < 0.3:
            signals.append("市场广度极差（上涨比例<30%）")
    
    if signals:
        report += "- ⚠️ " + "；".join(signals) + "\n"
    else:
        report += "- ✅ 未检测到极端信号，市场状态相对平稳\n"
    
    report += "\n---\n"
    report += "*本报告由自动脚本生成，数据来源于公开API，仅供参考，不构成投资建议。*"
    return report

# ------------------ 主程序入口 ------------------
if __name__ == "__main__":
    print("="*50)
    print(f"开始生成 {datetime.now().strftime('%Y-%m-%d')} 市场报告...")
    print("="*50)
    
    report_text = generate_report()
    
    filename = f"report_{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print("="*50)
    print(f"✅ 报告已生成：{filename}")
    print("="*50)
