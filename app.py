"""基金月末购买回测网站 - Flask 后端"""
import json
import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify
from fund_api import fetch_fund_info, fetch_nav_data, fetch_dividends, preload_hot_funds
from backtest_engine import compute_backtest

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/search_fund")
def search_fund():
    code = request.args.get("code", "").strip()
    if not code or len(code) != 6:
        return jsonify({"success": False, "error": "请输入6位基金代码"})
    try:
        info = fetch_fund_info(code)
        return jsonify({"success": True, "fund": {"code": info["code"], "name": info["name"], "fullName": info["full_name"], "type": info["type"]}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/backtest")
def backtest():
    code = request.args.get("code", "").strip()
    if not code or len(code) != 6:
        return jsonify({"success": False, "error": "请输入6位基金代码"})
    
    try:
        info = fetch_fund_info(code)
        navs = fetch_nav_data(code)
        if not navs:
            return jsonify({"success": False, "error": "未获取到净值数据，请检查基金代码"})
        dividends = fetch_dividends(code)
        start_ym = navs[0]["date"][:7]
        end_ym = navs[-1]["date"][:7]
        result = compute_backtest(navs, dividends, start_ym=start_ym, end_ym=end_ym)
        
        return jsonify({
            "success": True,
            "fund": {"code": info["code"], "name": info["name"], "fullName": info["full_name"], "type": info["type"]},
            "navCount": len(navs),
            "dividendCount": len(dividends),
            "dataRange": {"from": navs[0]["date"], "to": navs[-1]["date"]},
            "endDate": result["endDate"],
            "endNAV": result["endNAV"],
            "summary": result["summary"],
            "results": result["results"],
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/refresh_cache")
def refresh_cache():
    """强制刷新某只基金的净值缓存"""
    code = request.args.get("code", "").strip()
    if not code or len(code) != 6:
        return jsonify({"success": False, "error": "请输入6位基金代码"})
    try:
        navs = fetch_nav_data(code, force_refresh=True)
        return jsonify({"success": True, "message": f"已刷新，共 {len(navs)} 条净值记录"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    print("=" * 50)
    print("  📊 公募基金收益回测网")
    print("  本地地址: http://localhost:5000")
    print("=" * 50)
    # 延迟5秒后后台预加载热门基金（等Flask完全启动）
    def _delayed_preload():
        import time as _t
        _t.sleep(5)
        try:
            preload_hot_funds()
        except Exception as e:
            print(f"[预加载] 异常: {e}")
    threading.Thread(target=_delayed_preload, daemon=True).start()
    app.run(debug=False, host="0.0.0.0", port=5000)
