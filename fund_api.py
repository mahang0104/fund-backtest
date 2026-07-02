"""天天基金网 API - 拉取净值数据、分红记录、基金基本信息"""
import json
import urllib.request
import sys
import os
import time
import re
from collections import defaultdict

# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# 预加载的热门基金列表
HOT_FUNDS = [
    "519670", "000001", "110003", "110011", "161725", "005827",
    "320007", "163406", "001475", "000083", "260108", "161005",
    "003095", "001632", "160222", "501057", "001071", "519674",
    "001217", "012414",
]

def fetch_fund_info(fund_code):
    """获取基金基本信息（名称），通过天天基金实时估值接口"""
    url = f"http://fundgz.1234567.com.cn/js/{fund_code}.js"
    req = urllib.request.Request(url, headers={
        "Referer": "http://fund.eastmoney.com/",
        "User-Agent": "Mozilla/5.0"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode("utf-8")
        match = re.search(r'jsonpgz\((.*)\)', text, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            return {
                "code": fund_code,
                "name": data.get("name", ""),
                "full_name": data.get("name", ""),
                "type": "",
                "latestNAV": data.get("dwjz", ""),
                "latestDate": data.get("jzrq", ""),
            }
    except Exception as e:
        print(f"获取基金信息失败 [{fund_code}]: {e}")
    
    return {"code": fund_code, "name": "", "full_name": "", "type": ""}

def _cache_path(fund_code):
    return os.path.join(CACHE_DIR, f"{fund_code}.json")

def fetch_nav_data(fund_code, start_date="2010-01-01", end_date="2026-07-01", force_refresh=False):
    """拉取全部历史净值数据（分页），永久缓存直到手动刷新"""
    cache_file = _cache_path(fund_code)
    
    # 如果不是强制刷新，优先走缓存
    if not force_refresh and os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            navs = cached.get("navs", [])
            if navs:
                age_days = (time.time() - cached.get("timestamp", 0)) / 86400
                print(f"  [{fund_code}] 缓存命中 (age={age_days:.1f}d, {len(navs)} 条)")
                return navs
        except:
            pass
    
    # 从 API 拉取
    print(f"  [{fund_code}] 正在拉取净值数据...")
    all_data = []
    page = 1
    
    while True:
        url = f"http://api.fund.eastmoney.com/f10/lsjz?callback=&fundCode={fund_code}&pageIndex={page}&pageSize=20&startDate={start_date}&endDate={end_date}"
        req = urllib.request.Request(url, headers={
            "Referer": f"http://fundf10.eastmoney.com/jjjz_{fund_code}.html",
            "User-Agent": "Mozilla/5.0"
        })
        
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"  [{fund_code}] 第{page}页获取失败: {e}")
            break
        
        if data.get("ErrCode") != 0:
            print(f"  [{fund_code}] API错误: {data.get('ErrMsg')}")
            break
        
        items = data.get("Data", {}).get("LSJZList", [])
        if not items:
            break
        
        all_data.extend(items)
        
        total_count = data.get("TotalCount", 0)
        total_pages = (total_count + 19) // 20
        
        if page % 10 == 1 or page >= total_pages:
            print(f"  [{fund_code}] {page}/{total_pages} 页 ({len(all_data)} 条)")
        
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.02)
    
    all_data.sort(key=lambda x: x["FSRQ"])
    
    navs = []
    for item in all_data:
        navs.append({
            "date": item["FSRQ"],
            "dwjz": float(item["DWJZ"]),
            "ljjz": float(item["LJJZ"]),
            "growth": item.get("JZZZL", ""),
        })
    
    # 保存缓存
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({"fundCode": fund_code, "timestamp": time.time(), "navs": navs}, f, ensure_ascii=False)
        print(f"  [{fund_code}] 缓存已保存 ({len(navs)} 条)")
    except:
        pass
    
    return navs

def preload_hot_funds():
    """启动时后台预加载热门基金净值"""
    print(f"[预加载] 开始预加载 {len(HOT_FUNDS)} 只热门基金...")
    for code in HOT_FUNDS:
        try:
            if os.path.exists(_cache_path(code)):
                print(f"  [{code}] 已有缓存，跳过")
                continue
            print(f"  [{code}] 正在拉取...")
            fetch_nav_data(code)
        except Exception as e:
            print(f"  [{code}] 预加载失败: {e}")
    print("[预加载] 完成")

def fetch_dividends(fund_code):
    """获取基金分红记录 - 先从API获取，失败则用内置数据"""
    dividends = _fetch_dividends_api(fund_code)
    if dividends:
        return dividends
    
    dividends = _get_builtin_dividends(fund_code)
    if dividends:
        return dividends
    
    return []

def _fetch_dividends_api(fund_code):
    urls = [
        f"http://api.fund.eastmoney.com/f10/fhsp?callback=&fundCode={fund_code}&pageIndex=1&pageSize=100",
    ]
    
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={
                "Referer": f"http://fundf10.eastmoney.com/fhsp_{fund_code}.html",
                "User-Agent": "Mozilla/5.0"
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            
            if not data.get("Data"):
                continue
            
            items = data.get("Data", {}).get("list", [])
            if not items:
                continue
            
            dividends = []
            for item in items:
                ex_date = item.get("EXDIVIDEND", "")
                per_share = item.get("PERUNITVAL", "")
                if ex_date and per_share:
                    try:
                        dividends.append({"date": str(ex_date)[:10], "perShare": float(per_share)})
                    except (ValueError, TypeError):
                        continue
            
            if dividends:
                dividends.sort(key=lambda x: x["date"])
                return dividends
        except:
            continue
    
    return []

def _get_builtin_dividends(fund_code):
    BUILTIN = {
        "519670": [
            {"date": "2022-02-18", "perShare": 0.3920},
            {"date": "2021-01-12", "perShare": 0.5660},
            {"date": "2020-01-13", "perShare": 0.3300},
            {"date": "2016-01-19", "perShare": 0.8700},
            {"date": "2015-01-20", "perShare": 0.1550},
            {"date": "2014-02-20", "perShare": 0.1400},
            {"date": "2011-01-14", "perShare": 0.2100},
            {"date": "2010-01-20", "perShare": 0.1500},
        ],
    }
    return BUILTIN.get(fund_code, [])

def get_monthly_navs(navs):
    monthly = {}
    for item in navs:
        ym = item["date"][:7]
        monthly[ym] = item
    return monthly

if __name__ == "__main__":
    code = "519670"
    print(f"测试基金 {code}...")
    info = fetch_fund_info(code)
    print(f"基金名称: {info['name']}")
    navs = fetch_nav_data(code)
    print(f"净值记录: {len(navs)} 条")
    dividends = fetch_dividends(code)
    print(f"分红次数: {len(dividends)}")
