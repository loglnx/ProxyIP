#!/usr/bin/env python3
"""
从 Top 1M 域名列表中筛选使用 Cloudflare 的站点
通过检测 HTTP 响应头中的 cf-ray 或 server: cloudflare 来判断
"""

import csv
import asyncio
import aiohttp
import json
from pathlib import Path

# 配置
INPUT_FILE = "top-1m.csv"
OUTPUT_FILE = "cf_domains.json"
MAX_DOMAINS = 10000  # 检测前 N 个域名（Top 1M 太多，先检测前 1 万）
CONCURRENT_LIMIT = 100  # 并发数
TIMEOUT = 5  # 请求超时（秒）

async def check_cloudflare(session: aiohttp.ClientSession, domain: str) -> tuple[str, bool]:
    """检查域名是否使用 Cloudflare"""
    try:
        async with session.head(
            f"https://{domain}",
            timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            allow_redirects=True,
            ssl=False  # 忽略 SSL 错误
        ) as resp:
            headers = resp.headers
            # Cloudflare 特征：cf-ray 头或 server: cloudflare
            if "cf-ray" in headers or headers.get("server", "").lower() == "cloudflare":
                return (domain, True)
    except Exception:
        pass
    return (domain, False)

async def main():
    # 读取域名列表
    domains = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i >= MAX_DOMAINS:
                break
            if len(row) >= 2:
                domains.append(row[1])  # CSV 格式: rank,domain
    
    print(f"📋 读取了 {len(domains)} 个域名")
    print(f"🔍 开始检测 Cloudflare 站点（并发数: {CONCURRENT_LIMIT}）...")
    
    cf_domains = []
    checked = 0
    
    # 创建信号量控制并发
    semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
    
    async def check_with_semaphore(session, domain):
        async with semaphore:
            return await check_cloudflare(session, domain)
    
    connector = aiohttp.TCPConnector(limit=CONCURRENT_LIMIT, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_with_semaphore(session, domain) for domain in domains]
        
        for coro in asyncio.as_completed(tasks):
            domain, is_cf = await coro
            checked += 1
            if is_cf:
                cf_domains.append(domain)
                print(f"✅ [{checked}/{len(domains)}] {domain} - Cloudflare")
            else:
                if checked % 100 == 0:
                    print(f"⏳ [{checked}/{len(domains)}] 已检测... (找到 {len(cf_domains)} 个 CF 站点)")
    
    # 保存结果
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cf_domains, f, indent=2, ensure_ascii=False)
    
    print(f"\n🎉 完成！")
    print(f"📊 检测了 {len(domains)} 个域名")
    print(f"✅ 找到 {len(cf_domains)} 个 Cloudflare 站点")
    print(f"💾 已保存到 {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
