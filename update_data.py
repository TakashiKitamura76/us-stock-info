"""
update_data.py
-------------------

This script fetches the latest stock price and earnings surprise data for all
constituents of the S&P 500 index and generates a refreshed HTML page for the
GitHub Pages site.  It is designed to run within a GitHub Actions workflow.

Key steps:

1. **Load S&P 500 constituents**:  Instead of scraping Wikipedia, which often
   blocks automated requests, the script reads a published CSV dataset of the
   index constituents from GitHub.  Each row includes the ticker symbol and
   company name.

2. **Fetch quote and earnings data**:  Using the Finnhub API, the script
   requests the latest quote (`/quote`) and the most recent earnings surprise
   record (`/stock/earnings`) for each symbol.  A company is considered to have
   a "good earnings" result when both its actual EPS and actual revenue exceed
   the market estimates.

3. **Filter and build HTML**:  Only companies meeting the above criteria are
   retained.  The output HTML uses the same styling as the hand-crafted site
   and includes explanatory sections along with a table of the filtered
   companies.

Set the environment variable `FINNHUB_API_KEY` before running this script or
within the GitHub Actions workflow.
"""

import os
from datetime import datetime
from typing import List, Dict, Optional

import pandas as pd
import requests

API_BASE = "https://finnhub.io/api/v1"


def get_sp500_symbols() -> List[Dict[str, str]]:
    """Return a list of dicts with S&P 500 ticker symbols and company names.

    The constituent list is read from a CSV hosted on GitHub.  Using this CSV
    avoids hitting Wikipedia's HTML pages, which may rate‑limit or block
    automated scrapers.  Each entry in the returned list contains two keys:
    `symbol` (ticker) and `name` (company name).
    """
    csv_url = (
        "https://raw.githubusercontent.com/datasets/"
        "s-and-p-500-companies/main/data/constituents.csv"
    )
    try:
        df = pd.read_csv(csv_url)
    except Exception as e:
        print(f"Error fetching CSV from {csv_url}: {e}")
        return []
    symbols = df[["Symbol", "Security"]].rename(
        columns={"Symbol": "symbol", "Security": "name"}
    )
    return symbols.to_dict("records")


def fetch_quote(session: requests.Session, symbol: str, token: str) -> Optional[float]:
    """Fetch the latest stock price for a given ticker from Finnhub.

    Finnhub’s `/quote` endpoint returns fields including the current price (`c`).
    This function returns the current price as a float.  If the request fails,
    it returns `None`.
    """
    url = f"{API_BASE}/quote"
    params = {"symbol": symbol, "token": token}
    try:
        resp = session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("c"))
    except Exception:
        return None


def fetch_last_earnings(
    session: requests.Session, symbol: str, token: str
) -> Optional[Dict[str, float]]:
    """Return the most recent earnings surprise for a symbol.

    The Finnhub `/stock/earnings` endpoint returns a list of earnings surprises
    with fields such as `actual`, `estimate`, `revenueActual` and `revenueEstimate`.
    This function returns the first record (assumed to be the most recent
    quarter) with those four fields converted to floats.  If the response is
    empty or invalid, it returns `None`.
    """
    url = f"{API_BASE}/stock/earnings"
    params = {"symbol": symbol, "token": token}
    try:
        resp = session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        records = resp.json()
        if not records:
            return None
        rec = records[0]
        return {
            "actual_eps": float(rec.get("actual", 0)),
            "estimate_eps": float(rec.get("estimate", 0)),
            "actual_revenue": float(rec.get("revenueActual", 0)),
            "estimate_revenue": float(rec.get("revenueEstimate", 0)),
        }
    except Exception:
        return None


def is_good_earnings(record: Dict[str, float]) -> bool:
    """Determine whether a company meets the 'good earnings' criteria.

    A company is considered to have a good earnings result when its actual EPS
    and actual revenue both exceed the market estimates.  Guidance is not
    available via this API, so the comparison is limited to EPS and revenue.
    """
    return (
        record["actual_eps"] > record["estimate_eps"]
        and record["actual_revenue"] > record["estimate_revenue"]
    )


def build_html(entries: List[Dict[str, any]]) -> str:
    """Construct an HTML string for the main page from a list of entries.

    Each entry should have `name`, `symbol`, `price` and `good` fields.
    This function produces an HTML page mirroring the stylish design and
    populates the table rows using the provided entries.
    """
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang=\"ja\">",
        "<head>",
        "  <meta charset=\"UTF-8\">",
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
        "  <title>AI広瀬の米国株決算分析</title>",
        "  <style>",
        "    body { font-family: 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 0; background-color: #f7f9fc; color: #333; line-height: 1.6; }",
        "    header { background: linear-gradient(60deg, #007bff, #0d47a1); color: #fff; padding: 50px 20px; text-align: center; }",
        "    header h1 { margin: 0; font-size: 2.2rem; }",
        "    header .tagline { margin-top: 10px; font-size: 1.1rem; opacity: 0.85; }",
        "    main { max-width: 960px; margin: 0 auto; padding: 40px 20px; }",
        "    h2 { margin-top: 0; margin-bottom: 15px; color: #0d47a1; border-bottom: 2px solid #007bff; padding-bottom: 4px; font-size: 1.6rem; }",
        "    section { margin-bottom: 40px; }",
        "    p { margin-bottom: 20px; font-size: 0.98rem; }",
        "    ol { margin-left: 20px; margin-bottom: 20px; }",
        "    ol li { margin-bottom: 5px; }",
        "    table { width: 100%; border-collapse: collapse; background-color: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.05); font-size: 0.92rem; }",
        "    table th, table td { padding: 12px 15px; border-bottom: 1px solid #e0e6ed; vertical-align: middle; }",
        "    table th { background-color: #f3f6fa; text-align: left; font-weight: 600; }",
        "    table tbody tr:nth-child(even) { background-color: #fafbfc; }",
        "    table tbody tr:hover { background-color: #f1f5fa; }",
        "    .good { color: #27ae60; font-weight: 600; }",
        "    .no { color: #c0392b; font-weight: 600; }",
        "    .note { font-size: 0.8rem; color: #666; }",
        "    footer { text-align: center; padding: 25px 10px; background-color: #f3f6fa; color: #444; font-size: 0.85rem; }",
        "    footer a { color: #0d47a1; text-decoration: none; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <header>",
        "    <h1>AI広瀬の米国株決算分析</h1>",
        "    <p class=\"tagline\">個人投資家のための米国株情報サイト</p>",
        "  </header>",
        "  <main>",
        "    <section id=\"about\">",
        "      <h2>サイト概要</h2>",
        "      <p>当サイトは、S&P500 に含まれる米国株を対象に、決算情報と株価を自動収集し、<strong>良い決算</strong>を出した企業を一覧表示します。広瀬隆雄氏が提唱する『良い決算』の条件に基づいて、最新の EPS と売上高が市場予想を上回った銘柄だけを掲載しています。各行では企業名、ティッカー、現在株価、評価結果を確認できます。</p>",
        "    </section>",
        "    <section id=\"good-earnings\">",
        "      <h2>『良い決算』とは？</h2>",
        "      <p>広瀬隆雄氏によると、『良い決算』とは次の 3 つの指標がすべて市場予想（コンセンサス）を上回る決算を指します<sup><a href=\"#cite-hirosekessan\">[1]</a></sup>。</p>",
        "      <ol>",
        "        <li>EPS（1株当たり利益）</li>",
        "        <li>売上高</li>",
        "        <li>会社側ガイダンス（来期・今年度の見通し）</li>",
        "      </ol>",
        "      <p>本サイトではガイダンスデータが取得できないため、1 と 2 の条件を満たす企業を『良い決算』としています。</p>",
        "    </section>",
        "    <section id=\"table-section\">",
        "      <h2>良い決算を出した銘柄一覧</h2>",
        "      <table>",
        "        <thead>",
        "          <tr>",
        "            <th>企業名</th>",
        "            <th>ティッカー</th>",
        "            <th>株価（USD）</th>",
        "            <th>評価結果</th>",
        "          </tr>",
        "        </thead>",
        "        <tbody>",
    ]

    # Append table rows based on entries
    for entry in entries:
        cls = "good" if entry["good"] else "no"
        result_text = "良い決算" if entry["good"] else "該当なし"
        html_parts.append(
            f"          <tr><td>{entry['name']}</td><td>{entry['symbol']}</td><td>{entry['price']:.2f}</td><td class=\"{cls}\">{result_text}</td></tr>"
        )

    # Close out the table and add footnotes
    html_parts.extend([
        "        </tbody>",
        "      </table>",
        "      <p class=\"note\">表に表示されているデータは Finnhub API を使用して生成されています。API は RESTful な JSON 形式でレスポンスを返し、すべての GET リクエストで token パラメータが必要です。API キーの設定方法についてはリポジトリの README を参照してください。</p>",
        "    </section>",
        "    <section id=\"footnotes\">",
        "      <p id=\"cite-hirosekessan\" class=\"note\"><strong>[1]</strong> 良い決算の条件は EPS、売上高、会社ガイダンスが市場予想をすべて上回ることにあります。</p>",
        "    </section>",
        "  </main>",
        "  <footer>",
        "    <p>&copy; {year} AI広瀬の米国株決算分析. All rights reserved.</p>",
        "  </footer>",
        "</body>",
        "</html>",
    ])
    return "\n".join(html_parts).format(year=datetime.now().year)


def main() -> None:
    """Entry point for the update script."""
    token = os.getenv("FINNHUB_API_KEY")
    if not token:
        raise RuntimeError(
            "FINNHUB_API_KEY environment variable not set. Please supply your Finnhub API key."
        )

    session = requests.Session()
    sp500_list = get_sp500_symbols()
    if not sp500_list:
        raise RuntimeError("Could not retrieve S&P 500 symbols; aborting.")

    entries: List[Dict[str, any]] = []
    for item in sp500_list:
        symbol = item["symbol"]
        name = item["name"]
        price = fetch_quote(session, symbol, token)
        earnings = fetch_last_earnings(session, symbol, token)
        if price is None or earnings is None:
            continue
        good = is_good_earnings(earnings)
        if good:
            entries.append({"name": name, "symbol": symbol, "price": price, "good": good})

    # Sort entries alphabetically by symbol for consistency
    entries.sort(key=lambda e: e["symbol"])

    html = build_html(entries)
    # Write the generated HTML to index.html in the same directory as this script
    output_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Generated HTML for {len(entries)} companies with good earnings.")


if __name__ == "__main__":
    main()
