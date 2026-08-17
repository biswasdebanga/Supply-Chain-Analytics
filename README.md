# Supply Chain & Inventory Analytics

SQL-driven analysis of a 120K+ record supply chain dataset, built to identify inventory
shortages, supplier delays, and high-demand products — plus a Power BI-style interactive
dashboard and an Excel KPI workbook for stakeholder reporting.

> **Stack:** SQL (SQLite) · Python (pandas) · Excel (openpyxl, live formulas + charts) ·
> Interactive HTML/JS dashboard (Chart.js) as a portable Power BI stand-in.

## What this project does

- Analyzes **120,000+ supply chain order records** using SQL to surface inventory
  shortages, supplier delays, and high-demand products.
- Evaluates **supplier and warehouse performance** using lead time, order fulfillment,
  stock levels, and delivery KPIs to identify operational bottlenecks.
- Produces an **interactive dashboard** to track inventory, supplier performance,
  stock-outs, and demand — plus a matching **Excel report** with live formulas and charts
  for anyone who prefers a workbook.

## Why it's structured this way

A real engagement like this normally runs on a live SQL Server + Power BI Service stack
tied to a company's ERP. To make the project fully self-contained, reproducible, and
reviewable by anyone who clones the repo (no database server, no Power BI license, no
company data required), it's rebuilt on an equivalent, fully open pipeline:

| Original | This repo |
|---|---|
| Company ERP / warehouse data | Synthetic, statistically realistic generator (`data/generate_data.py`) |
| SQL Server | SQLite (`sql/supply_chain.db`) — same SQL, zero setup |
| Power BI dashboard | `dashboard/index.html` — interactive, opens in any browser, no license needed |
| Excel reporting | `excel/Supply_Chain_KPI_Report.xlsx` — live formulas + native charts |

The SQL itself (`sql/analysis_queries.sql`) is standard ANSI-ish SQL and drops into
PostgreSQL or SQL Server with only minor type tweaks — see `sql/schema.sql`.

## Repo structure

```
supply-chain-analytics/
├── data/
│   ├── generate_data.py        # builds the synthetic 120K+ record dataset
│   └── raw/                    # generated CSVs (orders, suppliers, products, warehouses, inventory)
├── sql/
│   ├── schema.sql               # table definitions + indexes
│   ├── analysis_queries.sql     # 8 annotated analysis queries
│   └── supply_chain.db          # generated SQLite database
├── analysis/
│   ├── build_summary.py         # runs every query, writes CSVs + summary.json
│   ├── summary.json             # machine-readable results (feeds the dashboard)
│   └── *.csv                    # one CSV per analysis
├── dashboard/
│   ├── index.html               # interactive control-tower dashboard
│   └── data_embed.js            # summary.json embedded for offline/no-server viewing
├── excel/
│   ├── build_workbook.py        # builds the Excel report from analysis CSVs
│   └── Supply_Chain_KPI_Report.xlsx
├── requirements.txt
└── README.md
```

## The 8 analyses

1. **Inventory shortages** — product/warehouse lanes below reorder point, ranked by
   severity (stock-out / critical / reorder).
2. **Supplier delays** — on-time rate, % delayed, and average delay per supplier.
3. **High-demand products** — top SKUs by order volume, units, and revenue.
4. **Lead time analysis** — actual vs. promised lead time by supplier region.
5. **Order fulfillment rate** — units delivered ÷ units ordered, by warehouse.
6. **Stock-level trends** — monthly average stock vs. reorder point, with stock-out rate.
7. **Delivery KPI scorecard** — network-wide on-time / delayed / cancelled / backordered rates.
8. **Operational bottlenecks** — supplier × warehouse lanes with the worst combined
   delay + fulfillment shortfall.

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate the synthetic dataset (120K+ orders, loads into sql/supply_chain.db)
python data/generate_data.py --orders 120000 --seed 42

# 3. Run the SQL analyses and build summary.json + per-query CSVs
python analysis/build_summary.py

# 4. Open the dashboard (no server needed — it's a static file)
open dashboard/index.html        # macOS
# or just double-click dashboard/index.html

# 5. (Optional) Rebuild the Excel report from the fresh analysis CSVs
python excel/build_workbook.py
```

To explore the SQL directly:

```bash
sqlite3 sql/supply_chain.db
sqlite> .read sql/analysis_queries.sql
```

## Key findings (from the generated dataset)

- **65.3% on-time delivery** network-wide, with **29.8% of orders delayed**.
- A handful of suppliers (e.g. those with low `reliability_score`) account for a
  disproportionate share of delays — several run **75–80% delayed rates** despite
  each handling 1,900+ orders.
- Warehouses cluster around **88–92% fulfillment**, with the weakest warehouse
  meaningfully behind the network average — a clear target for root-cause review.
- Stock-out rate spikes seasonally, visible directly in the monthly stock-level trend.
- The worst supplier × warehouse "lanes" combine high delay rates with sub-80%
  fulfillment — these are the highest-leverage bottlenecks to fix first.

*(Because the dataset is synthetically generated with `--seed 42`, these exact figures
are reproducible — rerun the quickstart above and you'll get the same numbers.)*

## Notes on the synthetic dataset

`data/generate_data.py` builds a statistically realistic supply chain: supplier
reliability scores drive delay probability, product demand indexes follow a
Pareto-ish distribution (a few high-demand SKUs, a long tail), and weekly inventory
snapshots consume/replenish stock in a way that produces genuine stock-outs and
reorder-point breaches — so every analysis above surfaces real signal, not noise.
Swap in real ERP exports by matching the column names in `sql/schema.sql`.

## License

MIT — see `LICENSE`.
