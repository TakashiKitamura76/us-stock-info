"""
update_data.py
----------------

This script fetches the latest stock price and recent earnings surprise data
for all constituents of the S&P 500 and updates the site's main HTML file.
The goal is to identify companies that satisfy Hirose Takao’s “good earnings”
criteria – EPS, revenue and guidance all beating market expectations – and
display those companies in the table on the website.

To keep the script simple and avoid relying on rate‑limited, unauthenticated
data sources, it uses the Finnhub API for both quotes and earnings
surprises.  Finnhub is a RESTful API that returns JSON‑encoded responses and
requires an API token for all requests【421114312369163†L139-L154】.  You must
provide a valid API key via the environment variable `FINNHUB_API_KEY`.

The script performs the following steps:

1.  **Load S&P 500 constituents**:  Pulls the list of ticker symbols and
    company names from the Wikipedia page for the S&P 500 index using
    `pandas.read_html`.  This keeps the list current without maintaining a
    local copy.
2.  **Fetch quote and earnings data**:  For each symbol, it requests the
    latest quote (`/quote`) and the most recent earnings surprise record
    (`/stock/earnings`) from Finnhub.  A company is considered to have a
    "good earnings" if the actual EPS and revenue both exceed the analysts’
    estimates.  Finnhub’s earnings endpoint returns a list of objects
    containing `actual`, `estimate` and `revenueActual`, `revenueEstimate`.
3.  **Filter for good earnings**:  Only companies meeting the criteria are
    retained.  This significantly reduces the size of the HTML table and
    makes it easier for investors to focus on strong performers.
4.  **Generate HTML**:  The updated data are used to build a new `index.html`
    file.  The design closely follows the hand‑crafted, stylish version of
    the site that exists in the repository – including a gradient header,
    crisp typography and colour‑coded evaluation results – but populates the
    table dynamically from the retrieved data.

The script is meant to be run automatically via a scheduled GitHub Action.
If run manually on your local machine you can test the logic and preview the
generated HTML before committing it to the repository.

Usage:

    FINNHUB_API_KEY=<your api key> python update_data.py

Note:  The script assumes it is executed from the repository root and
writes the generated HTML into the `site` directory as `index.html`.
"""

import json
import os
from datetime import datetime
from typing import List, Dict

import pandas as pd
import requests


API_BASE = "https://finnhub.io/api/v1"


def get_sp500_symbols() -> List[Dict[str, str]]:
    """Return a list of dicts with S&P 500 ticker symbols and company names.

    The list of constituents is scraped from the Wikipedia page for the S&P 500
    index.  It contains the most up‑to‑date membership because Wikipedia is
    community‑maintained and regularly updated when companies enter or leave
    the index.  Each entry in the returned list has two keys: `symbol` and
    `name`.
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    # Read the first table on the page; it contains the index constituents.
    tables = pd.read_html(url)
    sp500_table = tables[0]
    symbols = sp500_table[["Symbol", "Security"]].rename(
        columns={"Symbol": "symbol", "Security": "name"}
    )
    return symbols.to_dict("records")


def fetch_quote(session: requests.Session, symbol: str, token: str) -> float:
    """Fetch the latest stock price for a given ticker from Finnhub.

    Finnhub’s `/quote` endpoint returns fields including the current price
    (`c`), the previous close (`pc`) and others.  This function returns
    the current price as a float.  If the request fails, it returns `None`.
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


def fetch_last_earnings(session: requests.Session, symbol: str, token: str) -> Dict[str, float]:
    """Return the most recent earnings surprise for a symbol.

    The Finnhub `/stock/earnings` endpoint returns a list of earnings
    surprises with fields such as `actual`, `estimate`, `revenueActual` and
    `revenueEstimate`.  This function returns the first record in the list
    (assumed to be the most recent quarter) with those four fields converted
    to floats.  If the response is empty or invalid, `None` is returned.
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
    """Determine whether a company meets the "good earnings" criteria.

    A company is considered to have a good earnings result when its actual
    EPS and revenue both exceed the market estimates.  Guidance is not
    available via this API, so only the first two conditions are evaluated.
    """
    return (
        record["actual_eps"] > record["estimate_eps"]
        and record["actual_revenue"] > record["estimate_revenue"]
    )


def build_html(entries: List[Dict[str, any]]) -> str:
    """Construct an HTML string for the main page from a list of entries.

    Each entry should have `name`, `symbol`, `price` and `good` fields.  This
    function produces an HTML page mirroring the stylish design previously
    created, and populates the table rows using the provided entries.
    """
    # HTML header and CSS styling
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
        "        <tbody>"
    ]

    for entry in entries:
        # Determine class for the evaluation result
        cls = "good" if entry["good"] else "no"
        result_text = "良い決算" if entry["good"] else "該当なし"
        html_parts.append(
            f"          <tr><td>{entry['name']}</td><td>{entry['symbol']}</td><td>{entry['price']:.2f}</td><td class=\"{cls}\">{result_text}</td></tr>"
        )

    html_parts.extend([
        "        </tbody>",
        "      </table>",
        "      <p class=\"note\">表に表示されているデータは Finnhub API を使用して生成されています。API は RESTful な JSON 形式でレスポンスを返し、すべての GET リクエストで token パラメータが必要です【421114312369163†L139-L154】。API キーの設定方法についてはリポジトリの README を参照してください。</p>",
        "    </section>",
        "    <section id=\"footnotes\">",
        "      <p id=\"cite-hirosekessan\" class=\"note\"><strong>[1]</strong> 良い決算の条件は EPS、売上高、会社ガイダンスが市場予想をすべて上回ること【643053757984928†L296-L304】。</p>",
        "    </section>",
        "  </main>",
        "  <footer>",
        "    <p>&copy; {year} AI広瀬の米国株決算分析. All rights reserved.</p>",
        "  </footer>",
        "</body>",
        "</html>"
    ])
    return "\n".join(html_parts).format(year=datetime.now().year)


def main():
    token = os.getenv("FINNHUB_API_KEY")
    if not token:
        raise RuntimeError(
            "FINNHUB_API_KEY environment variable not set. Please supply your Finnhub API key."
        )

    session = requests.Session()

    sp500 = get_sp500_symbols()
    entries = []
    for item in sp500:
        symbol = item["symbol"]
        name = item["name"]
        quote = fetch_quote(session, symbol, token)
        earnings = fetch_last_earnings(session, symbol, token)
        if quote is None or earnings is None:
            continue
        good = is_good_earnings(earnings)
        if good:
            entries.append({"name": name, "symbol": symbol, "price": quote, "good": good})

    # Sort entries alphabetically for consistency
    entries.sort(key=lambda e: e["symbol"])

    html = build_html(entries)
    # Write to index.html in the site directory
    output_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated HTML for {len(entries)} companies with good earnings.")


if __name__ == "__main__":
    main()