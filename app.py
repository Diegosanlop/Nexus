"""Interfaz Streamlit para el análisis de ventas de Nexo Intelligence."""

from hashlib import sha256
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from nexo.analytics import (
    DataValidationError,
    calculate_summary,
    load_sales_file,
    product_summary,
    revenue_by_category,
    revenue_by_date,
    validate_sales,
)
from nexo.demo import demo_sales


st.set_page_config(page_title="Nexo Intelligence · Ventas", page_icon="◈", layout="wide")

st.markdown(
    "<style>" + (Path(__file__).parent / "nexo" / "theme.css").read_text() + "</style>",
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def _load_cached_file(filename: str, content: bytes) -> pd.DataFrame:
    return load_sales_file(filename, content)


def _section_header(title: str, detail: str) -> None:
    st.markdown(
        f'<div class="section-head"><h2>{title}</h2><span>{detail}</span></div>',
        unsafe_allow_html=True,
    )


with st.sidebar:
    st.markdown(
        """
        <div class="nexo-brand">
          <span class="nexo-mark">◈</span>
          <div><div class="nexo-brand-name">NEXO</div>
          <div class="nexo-brand-sub">INTELLIGENCE</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    prepared = st.session_state.get("nexo_prepared_sales")
    if isinstance(prepared, pd.DataFrame):
        source_choice = st.radio(
            "Origen de datos", ["Archivo construido", "Subir otro archivo"],
            key="analysis_source_choice",
        )
    else:
        source_choice = "Subir otro archivo"
    if source_choice == "Archivo construido":
        uploaded = None
    else:
        st.markdown('<div class="side-label">Origen de datos</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "Importa tus ventas", type=["csv", "xlsx", "xlsm"],
            help="Para formato flexible, usa primero la página Constructor.",
        )
        st.caption("Carga directa: CSV UTF-8 o Excel con encabezados canónicos. Excel usa la primera hoja.")

if source_choice == "Archivo construido":
    try:
        base_sales = validate_sales(prepared)
    except DataValidationError as error:
        st.error(f"El archivo preparado dejó de ser válido: {error}")
        st.stop()
    source_name = st.session_state.get("nexo_prepared_name", "Archivo construido")
    source_key = st.session_state.get("nexo_prepared_key", "prepared")
    source_class = "uploaded"
    source_message = f"Archivo preparado · {len(base_sales):,} registros · enviado desde el Constructor."
    is_demo = False
elif uploaded is None:
    try:
        base_sales = validate_sales(demo_sales())
    except DataValidationError as error:
        st.error(f"No se pudieron preparar los datos de demostración: {error}")
        st.stop()
    source_name = "Datos de demostración"
    source_key = "demo"
    source_class = ""
    source_message = "Explora el dashboard con ventas inventadas. Carga un archivo para analizar los datos de tu negocio."
    is_demo = True
else:
    file_bytes = uploaded.getvalue()
    source_key = sha256(file_bytes).hexdigest()[:12]
    try:
        with st.spinner("Leyendo y validando el archivo…"):
            base_sales = _load_cached_file(uploaded.name, file_bytes)
    except DataValidationError as error:
        st.markdown(
            """
            <div class="hero"><div><div class="eyebrow">Importación</div>
            <h1>Revisa tu archivo</h1>
            <p>Corregiremos el formato antes de calcular los resultados.</p>
            </div></div>
            """,
            unsafe_allow_html=True,
        )
        st.error(str(error))
        st.info(
            "Comprueba los nombres de las columnas, los valores de las filas indicadas "
            "y que los importes sean números sin símbolos de moneda."
        )
        st.stop()
    source_name = uploaded.name
    source_class = "uploaded"
    source_message = f"Archivo validado · {len(base_sales):,} registros · los resultados usan únicamente este archivo."
    is_demo = False

with st.sidebar:
    st.markdown('<div class="side-label">Filtros del análisis</div>', unsafe_allow_html=True)
    min_day = base_sales["fecha"].dt.date.min()
    max_day = base_sales["fecha"].dt.date.max()
    period = st.date_input(
        "Periodo de ventas", value=(min_day, max_day), min_value=min_day, max_value=max_day,
        key=f"period_{source_key}", help="El periodo inicial cubre todas las fechas presentes en los datos.",
    )
    if "categoria" in base_sales.columns:
        categories_available = sorted(base_sales["categoria"].dropna().astype(str).unique().tolist())
        selected_categories = st.multiselect(
            "Categorías", options=categories_available, default=categories_available,
            key=f"categories_{source_key}",
        )
    else:
        selected_categories = None
    product_query = st.text_input(
        "Buscar producto", placeholder="Todos los productos", key=f"product_query_{source_key}"
    )

st.markdown(
    """
    <div class="hero">
      <div><div class="eyebrow">Nexo Intelligence&nbsp;&nbsp; / &nbsp;&nbsp;Ventas</div>
      <h1>Ventas &amp; rentabilidad</h1>
      <p>Una lectura clara del ingreso, el coste y la contribución de cada producto.</p></div>
      <div class="hero-meta">Importes en moneda de origen · símbolo $ solo como formato</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    f"""
    <div class="source-banner {source_class}">
      <span class="source-pill">● &nbsp;{"DEMO · FICTICIO" if is_demo else "ARCHIVO VALIDADO"}</span>
      <span>{source_message}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

if isinstance(period, tuple):
    start_day, end_day = period
else:
    start_day = end_day = period
filtered = base_sales.loc[base_sales["fecha"].dt.date.between(start_day, end_day)].copy()
if selected_categories is not None:
    filtered = filtered.loc[filtered["categoria"].isin(selected_categories)]
if product_query.strip():
    filtered = filtered.loc[
        filtered["producto"].astype(str).str.contains(product_query.strip(), case=False, regex=False)
    ]

if filtered.empty:
    st.markdown(
        """
        <div class="empty-state"><strong>No hay ventas para esta selección.</strong><br>
        Amplía el periodo o ajusta las categorías y la búsqueda de producto.</div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

summary = calculate_summary(filtered)
margin = summary["margen_bruto"]
metric_specs = [
    ("Ingresos", f"${summary['ingresos']:,.2f}", "Venta antes de costes"),
    ("Coste de ventas", f"${summary['coste']:,.2f}", "Coste de los productos vendidos"),
    ("Ganancia bruta", f"${summary['ganancia_bruta']:,.2f}", "Ingresos menos coste de venta"),
    ("Margen bruto", "N/D" if pd.isna(margin) else f"{margin:.1%}", "Ganancia bruta / ingresos"),
    ("Unidades", f"{summary['unidades']:,.2f}", "Cantidad total vendida"),
    ("Productos", f"{summary['productos_distintos']:,}", "Productos con ventas"),
]
for row_start in (0, 3):
    metric_cols = st.columns(3, gap="small")
    for col, (label, value, help_text) in zip(metric_cols, metric_specs[row_start : row_start + 3]):
        with col:
            with st.container(border=True):
                st.metric(label, value, help=help_text)

_section_header(
    "Rendimiento de productos",
    f"{len(filtered):,} registros · {start_day:%d/%m/%Y} — {end_day:%d/%m/%Y}",
)
products = product_summary(filtered)
sort_options = {"Ingresos": "ingresos", "Ganancia bruta": "ganancia_bruta", "Margen bruto": "margen_bruto"}
sort_col, direction_col = st.columns([1, 1])
with sort_col:
    sort_label = st.selectbox("Ordenar por", list(sort_options), label_visibility="collapsed")
with direction_col:
    descending = (
        st.selectbox("Dirección", ["Mayor a menor", "Menor a mayor"], label_visibility="collapsed")
        == "Mayor a menor"
    )
sorted_products = products.sort_values(
    sort_options[sort_label], ascending=not descending, na_position="last", kind="stable"
)
display_products = sorted_products.rename(columns={
    "producto": "Producto", "unidades": "Unidades vendidas", "ingresos": "Ingresos ($)",
    "coste": "Coste ($)", "ganancia_bruta": "Ganancia bruta ($)", "margen_bruto": "Margen bruto",
})
st.dataframe(
    display_products,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Producto": st.column_config.TextColumn("Producto", help="Nombre como aparece en el archivo"),
        "Unidades vendidas": st.column_config.NumberColumn("Unidades vendidas", format="localized"),
        "Ingresos ($)": st.column_config.NumberColumn("Ingresos ($)", format="$ %.2f"),
        "Coste ($)": st.column_config.NumberColumn("Coste ($)", format="$ %.2f"),
        "Ganancia bruta ($)": st.column_config.NumberColumn("Ganancia bruta ($)", format="$ %.2f"),
        "Margen bruto": st.column_config.NumberColumn(
            "Margen bruto", format="percent", help="Ganancia bruta / ingresos del producto"
        ),
    },
)
st.markdown(
    '<div class="table-note">El margen se calcula sobre los importes totales de cada producto. '
    "Cuando los ingresos son cero, se muestra como no disponible.</div>",
    unsafe_allow_html=True,
)

_section_header(
    "Comportamiento de las ventas",
    "Las visualizaciones responden a los filtros seleccionados",
)
plotly_config = {"displayModeBar": False, "responsive": True}
chart_theme = {
    "template": "plotly_white",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {
        "family": "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
        "color": "#66756e",
        "size": 11,
    },
    "margin": {"l": 12, "r": 18, "t": 18, "b": 12},
    "hoverlabel": {"bgcolor": "#172722", "font": {"color": "#ffffff"}},
}
left, right = st.columns([1.45, 1], gap="medium")
timeline = revenue_by_date(filtered)
with left:
    with st.container(border=True):
        st.markdown("**Ingresos por fecha**")
        st.caption("Importe de venta por cada fecha registrada")
        trend = go.Figure(
            go.Scatter(
                x=timeline["fecha"], y=timeline["ingresos"], mode="lines+markers",
                line={"color": "#16805d", "width": 2.7},
                marker={"color": "#16805d", "size": 6, "line": {"color": "#ffffff", "width": 1.5}},
                fill="tozeroy", fillcolor="rgba(20,122,91,.09)",
                hovertemplate="%{x|%d/%m/%Y}<br>Ingresos: $%{y:,.2f}<extra></extra>",
            )
        )
        trend.update_layout(**chart_theme, height=310, showlegend=False)
        trend.update_xaxes(showgrid=False, zeroline=False, tickformat="%d/%m")
        trend.update_yaxes(showgrid=True, gridcolor="#edf0ed", zeroline=False, tickprefix="$", tickformat=",.0f")
        st.plotly_chart(trend, use_container_width=True, config=plotly_config)
with right:
    with st.container(border=True):
        st.markdown("**Ganancia bruta por producto**")
        st.caption("Ingresos menos coste de los productos vendidos")
        profit_rows = products.sort_values("ganancia_bruta", ascending=True, kind="stable").copy()
        bar_colors = ["#16805d" if value >= 0 else "#c45d4b" for value in profit_rows["ganancia_bruta"]]
        profit_chart = go.Figure(
            go.Bar(
                x=profit_rows["ganancia_bruta"], y=profit_rows["producto"], orientation="h",
                marker={"color": bar_colors, "cornerradius": 4},
                hovertemplate="%{y}<br>Ganancia bruta: $%{x:,.2f}<extra></extra>",
            )
        )
        profit_chart.update_layout(**chart_theme, height=max(310, len(profit_rows) * 48), showlegend=False, bargap=.36)
        profit_chart.update_xaxes(
            showgrid=True,
            gridcolor="#edf0ed",
            zeroline=True,
            zerolinecolor="#aebbb2",
            tickprefix="$",
            tickformat=",.0f",
        )
        profit_chart.update_yaxes(showgrid=False, automargin=True)
        st.plotly_chart(profit_chart, use_container_width=True, config=plotly_config)

if "categoria" in filtered.columns:
    category_rows = revenue_by_category(filtered)
    if not category_rows.empty:
        _section_header(
            "Ingresos por categoría", "Participación sobre las ventas filtradas"
        )
        category_col, _ = st.columns([1.1, 1.9])
        with category_col:
            with st.container(border=True):
                category_chart = go.Figure(
                    go.Pie(
                        labels=category_rows["categoria"], values=category_rows["ingresos"], hole=.72,
                        sort=False, textinfo="label+percent", textposition="outside",
                        marker={
                            "colors": ["#147a5b", "#96bd75", "#e6b266", "#8a9c93", "#5e8f7c", "#d17b60"],
                            "line": {"color": "#ffffff", "width": 3},
                        },
                        hovertemplate=(
                            "%{label}<br>Ingresos: $%{value:,.2f}"
                            "<br>Participación: %{percent}<extra></extra>"
                        ),
                    )
                )
                category_theme = {**chart_theme, "margin": {"l": 35, "r": 35, "t": 16, "b": 16}}
                annotations = [
                    {
                        "text": "INGRESOS",
                        "x": .5,
                        "y": .54,
                        "showarrow": False,
                        "font": {"size": 9, "color": "#748179", "family": "Inter, sans-serif"},
                    },
                    {
                        "text": f"${category_rows['ingresos'].sum():,.0f}",
                        "x": .5,
                        "y": .43,
                        "showarrow": False,
                        "font": {"size": 18, "color": "#15231f", "family": "Inter, sans-serif"},
                    },
                ]
                category_chart.update_layout(
                    **category_theme,
                    height=330,
                    showlegend=False,
                    annotations=annotations,
                )
                st.plotly_chart(category_chart, use_container_width=True, config=plotly_config)

with st.expander("Cómo leer las métricas y sus supuestos"):
    st.markdown(
        """
        <div class="footnote">
        <b>Ingresos</b> = cantidad × precio unitario. <b>Coste de ventas</b> = cantidad × costo unitario.
        <b>Ganancia bruta</b> = ingresos − coste de ventas. <b>Margen bruto</b> = ganancia bruta / ingresos;
        queda como N/D cuando los ingresos son cero. Los importes se asumen en una sola moneda y el símbolo
        $ solo sirve como formato visual: no hay conversión. No se incluyen impuestos, descuentos, devoluciones
        ni gastos operativos. Los filtros se aplican antes de agregar los importes.
        </div>
        """,
        unsafe_allow_html=True,
    )

if not is_demo:
    with st.expander("Vista previa de los datos importados"):
        st.caption(f"{source_name} · {len(base_sales):,} filas · columnas: {', '.join(map(str, base_sales.columns))}")
        st.dataframe(base_sales.head(8), use_container_width=True, hide_index=True)
