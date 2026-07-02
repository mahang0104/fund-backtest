"""基金回测计算引擎 - 月月末购买 + 分红再投资"""
from datetime import date
from collections import defaultdict

def compute_backtest(navs, dividends, start_ym="2010-12", end_ym="2026-06"):
    """
    计算每月月末买入的回测结果
    
    参数:
        navs: 净值列表 [{"date": "YYYY-MM-DD", "dwjz": 1.5, "ljjz": 2.0}, ...]
        dividends: 分红列表 [{"date": "YYYY-MM-DD", "perShare": 0.15}, ...]
        start_ym: 起始年月 "2010-12"
        end_ym: 结束年月 "2026-06"
    
    返回: {
        "results": [...],
        "summary": {...}
    }
    """
    # 1. 构建日期 -> 净值映射
    date_nav = {}
    all_dates = []
    for item in navs:
        d = item["date"]
        date_nav[d] = item["dwjz"]
        all_dates.append(d)
    all_dates.sort()
    
    # 2. 构建分红映射
    dividend_map = {}
    for d in dividends:
        div_date = d["date"]
        div_ps = d["perShare"]
        dividend_map[div_date] = div_ps
    
    # 3. 找到每月末净值
    monthly_navs = {}
    for d in all_dates:
        ym = d[:7]
        monthly_navs[ym] = {"date": d, "nav": date_nav[d]}
    
    # 3.5 推断基金成立月份（第一条净值记录所在月），成立当月买入净值设为1.0
    inception_ym = all_dates[0][:7] if all_dates else start_ym
    # 将成立月改为净值1.0，买入日期取该月最后一天或第一条记录日期
    inception_day = all_dates[0] if all_dates else inception_ym + "-01"
    monthly_navs[inception_ym] = {"date": inception_day, "nav": 1.0}
    # 对于成立月之前的月份（如果start_ym早于成立月），不生成回测点
    
    # 4. 确定截止净值
    end_dwjz = None
    for d in reversed(all_dates):
        if d[:7] <= end_ym:
            end_dwjz = date_nav[d]
            break
    
    if end_dwjz is None:
        raise ValueError(f"找不到 {end_ym} 或之前的净值数据")
    
    # 5. 对每个买入月份，计算最终收益
    results = []
    
    for ym in sorted(monthly_navs.keys()):
        if ym < inception_ym or ym < start_ym or ym > end_ym:
            continue
        
        buy_info = monthly_navs[ym]
        buy_date = buy_info["date"]
        buy_nav = buy_info["nav"]
        
        # 初始买入 1 份
        shares = 1.0
        
        # 统计分红次数（分红详情仅记录第一个月，避免数据过大）
        dividend_details = []
        div_count = 0
        is_first_month = (ym == sorted(monthly_navs.keys())[0])
        
        for div_date in sorted(dividend_map.keys()):
            div_per_share = dividend_map[div_date]
            
            if buy_date <= div_date <= all_dates[-1]:
                reinvest_nav = None
                for d in all_dates:
                    if d >= div_date:
                        reinvest_nav = date_nav[d]
                        break
                
                if reinvest_nav is None:
                    continue
                
                cash = shares * div_per_share
                new_shares = cash / reinvest_nav
                old_shares = shares
                shares += new_shares
                div_count += 1
                
                if is_first_month:
                    dividend_details.append({
                    "date": div_date,
                    "perShare": div_per_share,
                    "sharesBefore": round(old_shares, 6),
                    "cashDividend": round(cash, 4),
                    "reinvestNAV": round(reinvest_nav, 4),
                    "newShares": round(new_shares, 6),
                    "sharesAfter": round(shares, 6),
                })
        
        # 最终市值
        final_value = shares * end_dwjz
        original_investment = buy_nav  # 1份 × 买入净值
        
        # 累计收益率
        total_return_pct = ((final_value - original_investment) / original_investment) * 100
        
        # 持有年限
        buy_dt = date(int(buy_date[:4]), int(buy_date[5:7]), int(buy_date[8:10]))
        
        # 找到 end_ym 的实际日期
        end_actual_date = None
        for d in reversed(all_dates):
            if d[:7] <= end_ym:
                end_actual_date = d
                break
        
        end_dt = date(int(end_actual_date[:4]), int(end_actual_date[5:7]), int(end_actual_date[8:10]))
        years = max((end_dt - buy_dt).days / 365.25, 0.01)
        
        # 年化收益率 (CAGR)
        if years > 0 and final_value > 0:
            cagr = ((final_value / original_investment) ** (1 / years) - 1) * 100
        else:
            cagr = 0
        
        results.append({
            "yearMonth": ym,
            "buyDate": buy_date,
            "buyNAV": round(buy_nav, 4),
            "endNAV": round(end_dwjz, 4),
            "shares": round(shares, 6),
            "totalReturn": round(total_return_pct, 2),
            "cagr": round(cagr, 2),
            "years": round(years, 2),
            "isProfit": total_return_pct > 0,
            "dividendCount": len(dividend_details),
            "dividendDetails": dividend_details,
        })
    
    # 汇总统计
    profit_count = sum(1 for r in results if r["isProfit"])
    total_count = len(results)
    
    summary = {
        "totalMonths": total_count,
        "profitMonths": profit_count,
        "profitRatio": round(profit_count / max(total_count, 1) * 100, 1),
        "bestEntry": max(results, key=lambda r: r["totalReturn"]) if results else None,
        "worstEntry": min(results, key=lambda r: r["totalReturn"]) if results else None,
        "avgTotalReturn": round(sum(r["totalReturn"] for r in results) / max(total_count, 1), 2),
        "avgCAGR": round(sum(r["cagr"] for r in results) / max(total_count, 1), 2),
        "dividendCount": len(dividends),
    }
    
    return {
        "results": results,
        "summary": summary,
        "endDate": end_actual_date,
        "endNAV": end_dwjz,
    }

if __name__ == "__main__":
    import json
    from fund_api import fetch_nav_data, fetch_dividends
    
    code = "519670"
    navs = fetch_nav_data(code)
    dividends = fetch_dividends(code)
    
    result = compute_backtest(navs, dividends)
    
    summary = result["summary"]
    print(f"\n=== 回测汇总 ===")
    print(f"回测月份: {summary['totalMonths']}")
    print(f"盈利月份: {summary['profitMonths']} ({summary['profitRatio']}%)")
    print(f"平均累计收益: {summary['avgTotalReturn']}%")
    print(f"平均年化收益: {summary['avgCAGR']}%")
    
    if summary["bestEntry"]:
        b = summary["bestEntry"]
        print(f"最佳买入: {b['yearMonth']} 累计{b['totalReturn']}% 年化{b['cagr']}%")
    if summary["worstEntry"]:
        w = summary["worstEntry"]
        print(f"最差买入: {w['yearMonth']} 累计{w['totalReturn']}% 年化{w['cagr']}%")
