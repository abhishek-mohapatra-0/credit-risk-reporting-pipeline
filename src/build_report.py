"""Run the SQL layer over the clean data and publish the monthly risk pack.

Outputs
  reports/credit_risk_report_<YYYY-MM>.xlsx   Excel pack for stakeholders
  reports/extracts/*.csv                      flat files for Power BI / QuickSight
  docs/images/*.png                           charts used in the README
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

SQL = Path("sql")
CLEAN = Path("data/clean")
REPORTS = Path("reports")
IMG = Path("docs/images")

NAVY, LIGHT = "1F3864", "D9E1F2"
FONT = "Arial"
thin = Side(style="thin", color="BFBFBF")


def run_queries() -> dict[str, pd.DataFrame]:
    con = duckdb.connect()
    con.execute(f"CREATE VIEW loans AS SELECT * FROM '{CLEAN / 'loans.parquet'}'")
    con.execute(f"CREATE VIEW loan_performance AS SELECT * FROM '{CLEAN / 'loan_performance.parquet'}'")
    return {f.stem[3:]: con.execute(f.read_text()).df() for f in sorted(SQL.glob("*.sql"))}


def style_header(ws, row, ncol):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def write_table(ws, df: pd.DataFrame, start_row=1, formats: dict | None = None):
    formats = formats or {}
    for j, col in enumerate(df.columns, 1):
        ws.cell(row=start_row, column=j, value=col.replace("_", " ").title() if "_" in col else col)
    style_header(ws, start_row, len(df.columns))
    for i, rec in enumerate(df.itertuples(index=False), start_row + 1):
        for j, v in enumerate(rec, 1):
            if isinstance(v, pd.Timestamp):
                v = v.date()
            c = ws.cell(row=i, column=j, value=v)
            c.font = Font(name=FONT)
            c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
            fmt = formats.get(df.columns[j - 1])
            if fmt:
                c.number_format = fmt
    for j, col in enumerate(df.columns, 1):
        width = max(len(str(col)), *(len(str(x)) for x in df.iloc[:, j - 1].head(200))) + 3
        ws.column_dimensions[get_column_letter(j)].width = min(width, 28)
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)


def build_excel(q: dict[str, pd.DataFrame], dq: pd.DataFrame, month: str) -> Path:
    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"

    # Portfolio totals per month (one row per month) feed the summary formulas.
    trend = (q["portfolio_summary"].assign(arrears_cr=lambda d: d.exposure_cr * d.arrears_pct / 100,
                                           npa_cr=lambda d: d.exposure_cr * d.npa_pct / 100)
             .groupby("snapshot_month", as_index=False)[["active_accounts", "exposure_cr", "arrears_cr", "npa_cr"]].sum())
    ws = wb.create_sheet("Portfolio Trend")
    write_table(ws, trend, formats={"snapshot_month": "mmm-yy", "exposure_cr": "#,##0.00",
                                    "arrears_cr": "#,##0.00", "npa_cr": "#,##0.00", "active_accounts": "#,##0"})
    n = len(trend) + 1
    ws.cell(row=1, column=6, value="Arrears %"); ws.cell(row=1, column=7, value="NPA %")
    style_header(ws, 1, 7)
    for r in range(2, n + 1):
        ws.cell(row=r, column=6, value=f"=IFERROR(D{r}/C{r},0)").number_format = "0.00%"
        ws.cell(row=r, column=7, value=f"=IFERROR(E{r}/C{r},0)").number_format = "0.00%"
    ws.column_dimensions["F"].width = ws.column_dimensions["G"].width = 12
    ch = LineChart(); ch.title = "Arrears % and NPA % by month"; ch.height, ch.width = 8, 18
    ch.add_data(Reference(ws, min_col=6, max_col=7, min_row=1, max_row=n), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=n)); ch.y_axis.number_format = "0%"
    ws.add_chart(ch, "I2")

    by_product = q["portfolio_summary"]
    ws = wb.create_sheet("By Product")
    write_table(ws, by_product, formats={"snapshot_month": "mmm-yy", "exposure_cr": "#,##0.00"})

    dpd = q["delinquency_buckets"].pivot_table(index="grade", columns="dpd_bucket", values="exposure_cr", aggfunc="sum", fill_value=0)
    order = [c for c in ["Current", "1-30 DPD", "31-60 DPD", "61-90 DPD", "90+ DPD"] if c in dpd.columns]
    dpd = dpd[order].reset_index()
    ws = wb.create_sheet("DPD by Grade")
    write_table(ws, dpd, formats={c: "#,##0.00" for c in order})
    last = len(dpd) + 1; tc = len(order) + 2
    ws.cell(row=1, column=tc, value="Total"); ws.cell(row=1, column=tc + 1, value="Arrears %")
    style_header(ws, 1, tc + 1)
    for r in range(2, last + 1):
        ws.cell(row=r, column=tc, value=f"=SUM(B{r}:{get_column_letter(tc-1)}{r})").number_format = "#,##0.00"
        ws.cell(row=r, column=tc + 1, value=f"=IFERROR(1-B{r}/{get_column_letter(tc)}{r},0)").number_format = "0.00%"
    ws.cell(row=last + 2, column=1, value="Figures in INR crore, latest month.").font = Font(name=FONT, italic=True)
    bc = BarChart(); bc.type = "col"; bc.grouping = "stacked"; bc.overlap = 100
    bc.title = "Arrears exposure by grade (excl. Current)"; bc.height, bc.width = 8, 16
    bc.add_data(Reference(ws, min_col=3, max_col=len(order) + 1, min_row=1, max_row=last), titles_from_data=True)
    bc.set_categories(Reference(ws, min_col=1, min_row=2, max_row=last))
    ws.add_chart(bc, "J2")

    roll = q["roll_rates"].pivot_table(index="from_bucket", columns="to_bucket", values="roll_pct", fill_value=0)
    idx = [b for b in ["Current", "1-30 DPD", "31-60 DPD", "61-90 DPD", "90+ DPD"] if b in roll.index]
    roll = (roll.reindex(index=idx, columns=idx, fill_value=0) / 100).reset_index()
    ws = wb.create_sheet("Roll Rates")
    write_table(ws, roll, formats={c: "0.0%" for c in idx})
    ws.conditional_formatting.add(f"B2:{get_column_letter(len(idx)+1)}{len(idx)+1}",
                                  ColorScaleRule(start_type="num", start_value=0, start_color="FFFFFF",
                                                 end_type="num", end_value=1, end_color="F8696B"))
    ws.cell(row=len(idx) + 3, column=1, value="Share of opening balance moving between buckets, Jul-Dec 2025 average.").font = Font(name=FONT, italic=True)

    vint = q["vintage_default"].pivot_table(index="vintage", columns="grade", values="default_rate_pct", fill_value=0)
    vint = (vint / 100).reset_index()
    ws = wb.create_sheet("Vintage")
    write_table(ws, vint, formats={g: "0.00%" for g in vint.columns[1:]})
    ws.conditional_formatting.add(f"B2:{get_column_letter(len(vint.columns))}{len(vint)+1}",
                                  ColorScaleRule(start_type="min", start_color="FFFFFF", end_type="max", end_color="F8696B"))

    ws = wb.create_sheet("Concentration")
    write_table(ws, q["concentration"].assign(share_pct=lambda d: d.share_pct / 100), formats={"share_pct": "0.00%", "exposure_cr": "#,##0.00"})

    ws = wb.create_sheet("Data Quality")
    write_table(ws, dq[["table", "check", "severity", "failed_rows", "total_rows", "status"]], formats={"failed_rows": "#,##0", "total_rows": "#,##0"})
    for r in range(2, len(dq) + 2):
        s = ws.cell(row=r, column=6)
        s.fill = PatternFill("solid", fgColor={"PASS": "C6EFCE", "WARN": "FFEB9C", "FAIL": "FFC7CE"}[s.value])

    # Summary sheet: every KPI is a formula on the trend sheet, so it moves if the data does.
    t = "'Portfolio Trend'"
    summary["A1"] = f"Retail & SME Credit Risk Pack: {pd.Timestamp(month).strftime('%B %Y')}"
    summary["A1"].font = Font(name=FONT, bold=True, size=16, color=NAVY)
    summary["A2"] = "Synthetic portfolio. Amounts in INR crore."
    summary["A2"].font = Font(name=FONT, italic=True, color="595959")
    hdr = ["KPI", "This month", "Last month", "Change"]
    for j, h in enumerate(hdr, 1):
        summary.cell(row=4, column=j, value=h)
    style_header(summary, 4, 4)
    kpis = [("Active accounts", "B", "#,##0"), ("Exposure (cr)", "C", "#,##0.00"),
            ("Arrears %", "F", "0.00%"), ("NPA % (90+ DPD)", "G", "0.00%")]
    for i, (name, col, fmt) in enumerate(kpis, 5):
        summary.cell(row=i, column=1, value=name)
        summary.cell(row=i, column=2, value=f"={t}!{col}{n}").number_format = fmt
        summary.cell(row=i, column=3, value=f"={t}!{col}{n-1}").number_format = fmt
        ch = summary.cell(row=i, column=4, value=f"=B{i}-C{i}")
        ch.number_format = "+0.00%;-0.00%;0.00%" if "%" in fmt else "+#,##0.00;-#,##0.00;0"
        for c in range(1, 5):
            summary.cell(row=i, column=c).font = Font(name=FONT, bold=(c == 1))
            summary.cell(row=i, column=c).border = Border(top=thin, bottom=thin, left=thin, right=thin)
    summary.cell(row=10, column=1, value="Data-quality checks failed").font = Font(name=FONT, bold=True)
    summary.cell(row=10, column=2, value="=COUNTIF('Data Quality'!F:F,\"FAIL\")")
    summary.cell(row=11, column=1, value="Critical DQ failures (rows)").font = Font(name=FONT, bold=True)
    summary.cell(row=11, column=2, value="=SUMIFS('Data Quality'!D:D,'Data Quality'!C:C,\"critical\")").number_format = "#,##0"
    summary.column_dimensions["A"].width = 30
    for col in "BCD":
        summary.column_dimensions[col].width = 16

    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"credit_risk_report_{month[:7]}.xlsx"
    wb.save(out)
    return out


def build_charts(q: dict[str, pd.DataFrame]) -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})
    ps = q["portfolio_summary"]
    fig, ax = plt.subplots(figsize=(9, 4))
    for prod, g in ps.groupby("product"):
        ax.plot(pd.to_datetime(g.snapshot_month), g.npa_pct, label=prod, lw=2)
    ax.set_title("NPA % (90+ DPD) by product", loc="left", fontweight="bold")
    ax.set_ylabel("% of exposure"); ax.legend(frameon=False, ncol=4, fontsize=8)
    fig.tight_layout(); fig.savefig(IMG / "npa_trend.png", dpi=150); plt.close(fig)

    v = q["vintage_default"].pivot_table(index="vintage", columns="grade", values="default_rate_pct")
    fig, ax = plt.subplots(figsize=(9, 4))
    im = ax.imshow(v.T.values, cmap="Reds", aspect="auto")
    ax.set_xticks(range(len(v.index)), v.index, rotation=45, fontsize=8); ax.set_yticks(range(len(v.columns)), v.columns)
    ax.set_title("Ever-90+ default rate by vintage and grade (%)", loc="left", fontweight="bold")
    fig.colorbar(im, ax=ax, shrink=0.8); fig.tight_layout(); fig.savefig(IMG / "vintage_heatmap.png", dpi=150); plt.close(fig)

    r = q["roll_rates"].pivot_table(index="from_bucket", columns="to_bucket", values="roll_pct", fill_value=0)
    order = ["Current", "1-30 DPD", "31-60 DPD", "61-90 DPD", "90+ DPD"]
    r = r.reindex(index=order, columns=order, fill_value=0)
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.imshow(r.values, cmap="Blues", vmin=0, vmax=100)
    ax.set_xticks(range(5), order, rotation=30, fontsize=8); ax.set_yticks(range(5), order, fontsize=8)
    for i in range(5):
        for j in range(5):
            ax.text(j, i, f"{r.values[i, j]:.0f}%", ha="center", va="center", fontsize=8,
                    color="white" if r.values[i, j] > 60 else "black")
    ax.set_xlabel("To bucket"); ax.set_ylabel("From bucket")
    ax.set_title("Monthly roll-rate matrix (balance-weighted)", loc="left", fontweight="bold")
    fig.tight_layout(); fig.savefig(IMG / "roll_rates.png", dpi=150); plt.close(fig)


def main() -> None:
    q = run_queries()
    dq = pd.read_csv(CLEAN / "dq_summary.csv")
    month = str(pd.to_datetime(q["portfolio_summary"].snapshot_month).max().date())
    ext = REPORTS / "extracts"; ext.mkdir(parents=True, exist_ok=True)
    for name, df in q.items():
        df.to_csv(ext / f"{name}.csv", index=False)
    print("report:", build_excel(q, dq, month))
    build_charts(q)


if __name__ == "__main__":
    main()
