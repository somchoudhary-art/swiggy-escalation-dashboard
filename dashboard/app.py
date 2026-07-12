"""
Swiggy Food vs Zomato — Customer Escalation Intelligence Dashboard
Run: streamlit run dashboard/app.py
"""

import json
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BASE_DIR  = Path(__file__).parent.parent
PROC_DIR  = BASE_DIR / "data" / "processed"
OUT_DIR   = BASE_DIR / "output"
ANALYTICS = OUT_DIR / "analytics.json"

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Swiggy vs Zomato | Escalation Intelligence Q2",
    page_icon="🍕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Brand colours ──────────────────────────────────────────────────────────────
SWIGGY_ORANGE = "#FC8019"
ZOMATO_RED    = "#E23744"
NEUTRAL_GREY  = "#9E9E9E"

BUCKET_COLORS = {
    "A. Cancellation":         "#EF5350",
    "B. AI/Bot Related":       "#AB47BC",
    "C. Customer Care":        "#FF7043",
    "D. Delay Related":        "#FFA726",
    "E. Food Quality":         "#26A69A",
    "F. Delivery Executive":   "#42A5F5",
    "G. Payment/Coupon":       "#66BB6A",
    "H. Price/Fee":            "#EC407A",
    "I. Other/Emerging":       "#BDBDBD",
}

MONTHS = ["April", "May", "June"]


@st.cache_data
def load_data():
    if not ANALYTICS.exists():
        st.error("analytics.json not found. Run `python src/run_pipeline.py` first.")
        st.stop()
    with open(ANALYTICS, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_df():
    path = PROC_DIR / "classified.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def fmt(n):
    return f"{int(n):,}"


# ── Sidebar ────────────────────────────────────────────────────────────────────
def sidebar():
    st.sidebar.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/Swiggy_logo.svg/320px-Swiggy_logo.svg.png",
        width=120,
    )
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Filters")
    brand_filter = st.sidebar.multiselect(
        "Brand", ["Swiggy", "Zomato"], default=["Swiggy", "Zomato"]
    )
    month_filter = st.sidebar.multiselect(
        "Month", MONTHS, default=MONTHS
    )
    platform_filter = st.sidebar.multiselect(
        "Platform", ["Twitter/X", "Reddit", "LinkedIn"],
        default=["Twitter/X", "Reddit", "LinkedIn"]
    )
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Period:** Apr – Jun 2025")
    st.sidebar.markdown("**Data Sources:** Twitter/X, Reddit, LinkedIn via Apify")
    return (
        [b.lower() for b in brand_filter],
        month_filter,
        platform_filter,
    )


# ── KPI cards ─────────────────────────────────────────────────────────────────
def kpi_cards(data: dict, df: pd.DataFrame):
    kpis = data["kpis"]
    sw   = kpis.get("swiggy", {})
    zm   = kpis.get("zomato", {})

    sw_total = sw.get("total_posts", 0)
    zm_total = zm.get("total_posts", 0)
    sw_comp  = sw.get("complaint_posts", 0)
    zm_comp  = zm.get("complaint_posts", 0)

    # Top bucket for Swiggy
    ba = data.get("bucket_analysis", {}).get("swiggy", {})
    top_bucket = max(ba, key=lambda k: ba[k]["count"]) if ba else "—"
    top_bucket_cnt = ba[top_bucket]["count"] if ba else 0

    # Fastest growing bucket Apr→Jun (Swiggy)
    mt = data.get("monthly_trend", {}).get("swiggy", {})
    fastest = data["monthly_trend"]["swiggy"].get("biggest_increase", "—")

    comp_growth = round((sw_comp - zm_comp) / max(zm_comp, 1) * 100, 1)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric("🍊 Swiggy Complaints", fmt(sw_comp),
                  delta=f"{sw.get('escalation_posts',0):,} escalations")
    with c2:
        st.metric("🔴 Zomato Complaints", fmt(zm_comp),
                  delta=f"{zm.get('escalation_posts',0):,} escalations")
    with c3:
        st.metric("📊 Total Posts (Swiggy)", fmt(sw_total))
    with c4:
        st.metric("📊 Total Posts (Zomato)", fmt(zm_total))
    with c5:
        st.metric("🔝 Top Bucket (Swiggy)", top_bucket.replace("A. ","").replace("B. ","")
                  .replace("C. ","").replace("D. ","").replace("E. ","")
                  .replace("F. ","").replace("G. ","").replace("H. ","").replace("I. ",""),
                  delta=f"{fmt(top_bucket_cnt)} posts")
    with c6:
        st.metric("🚀 Fastest Growing", fastest.split("(")[0].strip() if fastest else "—")


# ── Tab 1: Executive Summary ───────────────────────────────────────────────────
def tab_executive(data: dict, df: pd.DataFrame, brand_f, month_f, platform_f):
    st.markdown("## 📋 Executive Summary — Q2 2025")

    kpis = data["kpis"]
    sw   = kpis.get("swiggy", {})
    zm   = kpis.get("zomato", {})
    comp = data.get("competitive", {})
    emerging = data.get("emerging", [])
    mt   = data.get("monthly_trend", {})

    # Top issues
    ba_sw = data.get("bucket_analysis", {}).get("swiggy", {})
    sorted_buckets = sorted(ba_sw.items(), key=lambda x: x[1]["count"], reverse=True)
    top3 = [b[0] for b in sorted_buckets[:3]]

    higher_sw = comp.get("higher_swiggy", [])

    # Trend direction
    sw_apr = mt.get("swiggy", {}).get("by_month", {}).get("April", {}).get("total", 0)
    sw_jun = mt.get("swiggy", {}).get("by_month", {}).get("June",  {}).get("total", 0)
    trend_dir = "↑ increasing" if sw_jun > sw_apr else "↓ decreasing"

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"""
### 🔑 Key Findings

- **{fmt(sw.get('complaint_posts',0))} Swiggy Food complaints** collected across Twitter/X, Reddit, and LinkedIn (Apr–Jun 2025),
  vs **{fmt(zm.get('complaint_posts',0))} for Zomato** — a volume gap indicating higher CX friction for Swiggy.
- **Complaint trend is {trend_dir}** from April to June —
  {fmt(sw_apr)} posts in April growing to {fmt(sw_jun)} in June.
- **Top 3 escalation categories:** {", ".join(top3)}.
- **Swiggy disproportionately higher** in: {", ".join(higher_sw[:3]) if higher_sw else "comparable with Zomato"}.
- **{len(emerging)} emerging issues** detected via topic modelling — see Emerging Issues tab.

### ⚠️ Biggest Risks
1. **AI/Bot loop complaints** — customers unable to reach human agents is a reputational flashpoint.
2. **Cancellation surge** — auto-cancellations with delayed refunds driving Twitter escalations.
3. **Food quality & tampering** — hygiene complaints carry viral risk and regulatory exposure.

### 💡 Top Recommendations
| Priority | Action | Owner |
|---|---|---|
| P0 | Add human-agent escalation path after 2 bot loops | CX Product |
| P0 | Refund SLA enforcement — auto-credit in <24h | Finance + CX |
| P1 | Delivery Executive QA programme | Ops |
| P1 | Proactive delay comms at 20-min breach | Product |
| P2 | Platform fee transparency improvements | Product |
""")

    with col2:
        # Sentiment donut for Swiggy
        if not df.empty:
            sw_df = df[df["brand"] == "swiggy"]
            sent_counts = sw_df["sentiment"].value_counts().reset_index()
            sent_counts.columns = ["sentiment", "count"]
            fig = px.pie(
                sent_counts, values="count", names="sentiment",
                title="Swiggy Sentiment Split",
                color="sentiment",
                color_discrete_map={
                    "Negative": SWIGGY_ORANGE,
                    "Neutral":  NEUTRAL_GREY,
                    "Positive": "#66BB6A",
                },
                hole=0.45,
            )
            fig.update_layout(height=280, margin=dict(t=40, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)

        # Competitive position radar placeholder
        comp_by_bucket = comp.get("by_bucket", {})
        if comp_by_bucket:
            labels = list(comp_by_bucket.keys())
            sw_vals = [comp_by_bucket[k]["swiggy_share"] for k in labels]
            zm_vals = [comp_by_bucket[k]["zomato_share"] for k in labels]
            fig2 = go.Figure()
            fig2.add_trace(go.Scatterpolar(
                r=sw_vals + [sw_vals[0]], theta=labels + [labels[0]],
                fill="toself", name="Swiggy",
                line_color=SWIGGY_ORANGE,
            ))
            fig2.add_trace(go.Scatterpolar(
                r=zm_vals + [zm_vals[0]], theta=labels + [labels[0]],
                fill="toself", name="Zomato", opacity=0.6,
                line_color=ZOMATO_RED,
            ))
            fig2.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, max(sw_vals + zm_vals) + 5])),
                title="Complaint Share by Bucket (%)",
                height=300,
                margin=dict(t=50, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=-0.15),
            )
            st.plotly_chart(fig2, use_container_width=True)


# ── Tab 2: Monthly Trends ──────────────────────────────────────────────────────
def tab_monthly(data: dict, df: pd.DataFrame, brand_f, month_f):
    st.markdown("## 📅 Monthly Trends — Apr → May → Jun")

    mt = data.get("monthly_trend", {})

    col1, col2 = st.columns(2)
    for col, brand in zip([col1, col2], ["swiggy", "zomato"]):
        if brand not in [b.lower() for b in (brand_f or ["swiggy", "zomato"])]:
            continue
        brand_mt = mt.get(brand, {}).get("by_month", {})
        totals   = [brand_mt.get(m, {}).get("total", 0) for m in MONTHS]
        comps    = [brand_mt.get(m, {}).get("complaints", 0) for m in MONTHS]
        escs     = [brand_mt.get(m, {}).get("escalations", 0) for m in MONTHS]

        color = SWIGGY_ORANGE if brand == "swiggy" else ZOMATO_RED
        with col:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=MONTHS, y=totals,   name="Total Posts",  marker_color=color, opacity=0.4))
            fig.add_trace(go.Bar(x=MONTHS, y=comps,    name="Complaints",   marker_color=color, opacity=0.75))
            fig.add_trace(go.Bar(x=MONTHS, y=escs,     name="Escalations",  marker_color="#B71C1C"))
            fig.update_layout(
                title=f"{brand.title()} — Monthly Volume",
                barmode="group",
                height=350,
                legend=dict(orientation="h", yanchor="bottom", y=-0.25),
                margin=dict(t=50, b=60),
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("### Bucket Heatmap by Month")

    for brand in ["swiggy", "zomato"]:
        if brand not in (brand_f or ["swiggy", "zomato"]):
            continue
        brand_mt = mt.get(brand, {}).get("by_month", {})
        all_buckets = sorted(set(
            k for m in MONTHS for k in brand_mt.get(m, {}).get("bucket_counts", {}).keys()
        ))
        heat_data = []
        for bucket in all_buckets:
            row = [brand_mt.get(m, {}).get("bucket_counts", {}).get(bucket, 0) for m in MONTHS]
            heat_data.append(row)

        if heat_data:
            fig = px.imshow(
                heat_data,
                x=MONTHS,
                y=all_buckets,
                color_continuous_scale="Oranges" if brand == "swiggy" else "Reds",
                title=f"{brand.title()} — Complaint Heatmap (Absolute Count)",
                text_auto=True,
                aspect="auto",
            )
            fig.update_layout(height=350, margin=dict(t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)

    # MoM growth table
    st.markdown("### Month-over-Month Growth")
    rows = []
    for brand in ["swiggy", "zomato"]:
        brand_mt = mt.get(brand, {}).get("by_month", {})
        for m in ["May", "June"]:
            prev = "April" if m == "May" else "May"
            t_cur  = brand_mt.get(m, {}).get("total", 0)
            t_prev = brand_mt.get(prev, {}).get("total", 0)
            pct = f"+{round((t_cur-t_prev)/max(t_prev,1)*100,1)}%" if t_cur >= t_prev else f"{round((t_cur-t_prev)/max(t_prev,1)*100,1)}%"
            rows.append({"Brand": brand.title(), "Month": m, "Total": t_cur, "vs Prior Month": pct})
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ── Tab 3: Bucket Analysis ─────────────────────────────────────────────────────
def tab_buckets(data: dict, df: pd.DataFrame, brand_f):
    st.markdown("## 🪣 Bucket-Level Analysis")

    ba = data.get("bucket_analysis", {})

    col1, col2 = st.columns(2)
    for col, brand in zip([col1, col2], ["swiggy", "zomato"]):
        brand_ba = ba.get(brand, {})
        if not brand_ba:
            continue
        labels  = list(brand_ba.keys())
        counts  = [brand_ba[k]["count"] for k in labels]
        colors  = [BUCKET_COLORS.get(k, "#999") for k in labels]

        with col:
            fig = px.bar(
                x=counts, y=labels, orientation="h",
                title=f"{brand.title()} — Complaints by Bucket",
                color=labels,
                color_discrete_map=BUCKET_COLORS,
                text=counts,
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                showlegend=False, height=420,
                xaxis_title="Post Count", yaxis_title="",
                margin=dict(t=50, l=10, r=60),
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("### Stacked Bar: Bucket Trend Apr → Jun")

    for brand in ["swiggy", "zomato"]:
        if brand not in (brand_f or ["swiggy","zomato"]):
            continue
        brand_ba = ba.get(brand, {})
        if not brand_ba:
            continue

        fig = go.Figure()
        for bucket, bdata in brand_ba.items():
            trend = bdata.get("trend", {})
            fig.add_trace(go.Bar(
                name=bucket,
                x=MONTHS,
                y=[trend.get(m, 0) for m in MONTHS],
                marker_color=BUCKET_COLORS.get(bucket, "#999"),
            ))
        fig.update_layout(
            barmode="stack",
            title=f"{brand.title()} — Stacked Complaint Trend",
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=-0.35, font=dict(size=10)),
            margin=dict(t=50, b=100),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Detailed bucket table
    st.markdown("### Bucket Summary Table")
    rows = []
    for brand in ["swiggy", "zomato"]:
        brand_ba = ba.get(brand, {})
        for bucket, bdata in brand_ba.items():
            trend = bdata.get("trend", {})
            rows.append({
                "Brand":   brand.title(),
                "Bucket":  bucket,
                "Total":   bdata["count"],
                "Share %": f"{bdata['share']}%",
                "April":   trend.get("April", 0),
                "May":     trend.get("May",   0),
                "June":    trend.get("June",  0),
            })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ── Tab 4: Competitive ─────────────────────────────────────────────────────────
def tab_competitive(data: dict):
    st.markdown("## ⚔️ Swiggy vs Zomato — Competitive Analysis")

    comp = data.get("competitive", {})
    by_bucket = comp.get("by_bucket", {})

    if not by_bucket:
        st.info("No competitive data available.")
        return

    df_comp = pd.DataFrame([
        {
            "Bucket":         k,
            "Swiggy Count":   v["swiggy_count"],
            "Zomato Count":   v["zomato_count"],
            "Swiggy Share %": v["swiggy_share"],
            "Zomato Share %": v["zomato_share"],
            "Diff (pp)":      v["diff_share"],
        }
        for k, v in by_bucket.items()
    ])

    col1, col2 = st.columns(2)

    with col1:
        # Grouped bar: absolute counts
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Swiggy", x=df_comp["Bucket"],
            y=df_comp["Swiggy Count"], marker_color=SWIGGY_ORANGE,
        ))
        fig.add_trace(go.Bar(
            name="Zomato", x=df_comp["Bucket"],
            y=df_comp["Zomato Count"], marker_color=ZOMATO_RED,
        ))
        fig.update_layout(
            barmode="group", title="Absolute Count by Bucket",
            height=420, xaxis_tickangle=-35,
            legend=dict(orientation="h", y=-0.35),
            margin=dict(t=50, b=100),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Diff waterfall
        colors = [SWIGGY_ORANGE if v > 0 else ZOMATO_RED for v in df_comp["Diff (pp)"]]
        fig2 = go.Figure(go.Bar(
            x=df_comp["Bucket"], y=df_comp["Diff (pp)"],
            marker_color=colors,
            text=df_comp["Diff (pp)"].apply(lambda x: f"+{x}" if x > 0 else str(x)),
            textposition="outside",
        ))
        fig2.add_hline(y=0, line_dash="dash", line_color="grey")
        fig2.update_layout(
            title="Share Gap (Swiggy % − Zomato %) — positive = worse for Swiggy",
            height=420, xaxis_tickangle=-35,
            margin=dict(t=50, b=100),
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.markdown("### Platform Distribution")
    pc = data.get("platform_counts", {})
    platforms = ["Twitter/X", "Reddit", "LinkedIn"]
    fig3 = go.Figure()
    for brand, color in [("swiggy", SWIGGY_ORANGE), ("zomato", ZOMATO_RED)]:
        brand_pc = pc.get(brand, {})
        fig3.add_trace(go.Bar(
            name=brand.title(),
            x=platforms,
            y=[brand_pc.get(p, 0) for p in platforms],
            marker_color=color,
            text=[brand_pc.get(p, 0) for p in platforms],
            textposition="outside",
        ))
    fig3.update_layout(
        barmode="group", title="Platform Distribution (Absolute Post Counts)",
        height=360,
        legend=dict(orientation="h", y=-0.2),
        margin=dict(t=50, b=60),
    )
    st.plotly_chart(fig3, use_container_width=True)

    # Insight callouts
    higher_sw = comp.get("higher_swiggy", [])
    higher_zm = comp.get("higher_zomato", [])
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.error(f"**Swiggy disproportionately higher in:**\n\n" +
                 "\n".join(f"• {b}" for b in higher_sw) if higher_sw else "None identified")
    with c2:
        st.warning(f"**Zomato disproportionately higher in:**\n\n" +
                   "\n".join(f"• {b}" for b in higher_zm) if higher_zm else "None identified")


# ── Tab 5: Emerging Issues ─────────────────────────────────────────────────────
def tab_emerging(data: dict):
    st.markdown("## 🚨 Emerging & Trending Issues")

    emerging = data.get("emerging", [])
    if not emerging:
        st.info("No emerging issues detected. Run pipeline with more data.")
        return

    for i, issue in enumerate(emerging[:10], 1):
        growth = issue.get("growth_pct")
        growth_str = f"+{growth}% MoM" if growth and growth > 0 else (f"{growth}% MoM" if growth else "New")

        with st.expander(f"#{i} — {issue['issue']}  |  {growth_str}  |  {fmt(issue['total'])} posts", expanded=(i <= 3)):
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Posts", fmt(issue["total"]))
            c2.metric("April", fmt(issue.get("apr_count", 0)))
            c3.metric("June",  fmt(issue.get("jun_count", 0)), delta=growth_str)

            samples = issue.get("samples", [])
            if samples:
                st.markdown("**Sample Posts:**")
                for s in samples[:3]:
                    st.markdown(f"> *\"{s.get('text','')[:200]}...\"*  \n"
                                f"📌 {s.get('platform','?')} | 👍 {s.get('engagement',0)} | 📅 {str(s.get('date',''))[:10]}")


# ── Tab 6: Representative Posts ────────────────────────────────────────────────
def tab_posts(data: dict, df: pd.DataFrame):
    st.markdown("## 📝 Representative Customer Posts")

    rep = data.get("rep_posts", {})
    brand = st.selectbox("Select Brand", ["swiggy", "zomato"], format_func=str.title)
    bucket = st.selectbox("Select Bucket", list(rep.get(brand, {}).keys()))

    posts = rep.get(brand, {}).get(bucket, [])
    if not posts:
        st.info("No posts for this selection.")
        return

    for p in posts[:8]:
        text = p.get("text", "")
        platform = p.get("platform", "")
        date_str = str(p.get("date", ""))[:10]
        eng  = p.get("engagement", 0)
        sent = p.get("sentiment", "Neutral")
        url  = p.get("url", "")

        sent_icon = "🔴" if sent == "Negative" else ("🟢" if sent == "Positive" else "🟡")
        st.markdown(
            f"{sent_icon} **{platform}** | 📅 {date_str} | 👍 {eng}"
        )
        st.markdown(f"> {text[:300]}")
        if url:
            st.markdown(f"[View Post]({url})")
        st.markdown("---")


# ── Tab 7: Raw Data ────────────────────────────────────────────────────────────
def tab_rawdata(df: pd.DataFrame, brand_f, month_f, platform_f):
    st.markdown("## 📊 Full Dataset")

    if df.empty:
        st.info("No dataset loaded.")
        return

    filtered = df.copy()
    if brand_f:
        filtered = filtered[filtered["brand"].isin(brand_f)]
    if month_f:
        filtered = filtered[filtered["month"].isin(month_f)]
    if platform_f:
        filtered = filtered[filtered["platform"].isin(platform_f)]

    st.write(f"Showing **{len(filtered):,}** of {len(df):,} posts")

    display_cols = ["brand", "platform", "month", "date", "bucket_label",
                    "sentiment", "is_complaint", "is_escalation", "engagement", "text"]
    available = [c for c in display_cols if c in filtered.columns]
    st.dataframe(filtered[available].head(500), use_container_width=True, hide_index=True)

    csv = filtered.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "⬇️ Download CSV", data=csv,
        file_name="swiggy_zomato_escalations_q2.csv",
        mime="text/csv",
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    st.title("🍕 Swiggy Food vs Zomato — Customer Escalation Intelligence")
    st.markdown("**Q2 2025 (April – June) | Sources: Twitter/X, Reddit, LinkedIn**")
    st.markdown("---")

    brand_f, month_f, platform_f = sidebar()
    data = load_data()
    df   = load_df()

    kpi_cards(data, df)
    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📋 Executive Summary",
        "📅 Monthly Trends",
        "🪣 Bucket Analysis",
        "⚔️ Competitive",
        "🚨 Emerging Issues",
        "📝 Posts",
        "📊 Raw Data",
    ])

    with tab1:
        tab_executive(data, df, brand_f, month_f, platform_f)
    with tab2:
        tab_monthly(data, df, brand_f, month_f)
    with tab3:
        tab_buckets(data, df, brand_f)
    with tab4:
        tab_competitive(data)
    with tab5:
        tab_emerging(data)
    with tab6:
        tab_posts(data, df)
    with tab7:
        tab_rawdata(df, brand_f, month_f, platform_f)


if __name__ == "__main__":
    main()
