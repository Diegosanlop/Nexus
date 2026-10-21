"""Asistente explícito para preparar archivos de ventas para Nexo."""

from hashlib import sha256
from pathlib import Path

import pandas as pd
import streamlit as st

from nexo.analytics import DataValidationError, read_tabular_file, validate_sales
from nexo.builder import FIELD_LABELS, parse_correction, prepare_mapped_data, suggest_mapping

st.set_page_config(page_title="Nexo · Constructor", page_icon="◈", layout="wide")
st.markdown(
    "<style>" + (Path(__file__).parent.parent / "nexo" / "theme.css").read_text() + "</style>",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero"><div><div class="eyebrow">Nexo Intelligence&nbsp;&nbsp; / &nbsp;&nbsp;Preparación</div>
    <h1>Constructor de archivos</h1>
    <p>Relaciona tus columnas, completa únicamente los datos obligatorios que falten y revisa el resultado.</p></div>
    <div class="hero-meta">El archivo de origen no se modifica</div></div>
    """,
    unsafe_allow_html=True,
)
st.info("Este es un paso separado del análisis. Al terminar, puedes descargar un CSV listo para Nexo o enviarlo directamente a Análisis.")

uploaded = st.file_uploader(
    "Archivo que quieres preparar", type=["csv", "xlsx", "xlsm"],
    help="El archivo puede tener encabezados y formatos distintos. Excel se lee desde la primera hoja.",
)
if uploaded is None:
    st.caption("Carga un CSV o Excel. Te pediremos una elección explícita para fechas y separadores numéricos.")
    st.stop()

content = uploaded.getvalue()
source_key = sha256(content).hexdigest()[:12]
try:
    raw = read_tabular_file(uploaded.name, content)
except DataValidationError as error:
    st.error(str(error))
    st.stop()

if raw.empty:
    st.error("El archivo no contiene filas de datos.")
    st.stop()
if raw.columns.duplicated().any():
    duplicates = raw.columns[raw.columns.duplicated()].astype(str).tolist()
    st.error("El archivo contiene encabezados duplicados y no se puede distinguir cuál columna usar: " + ", ".join(duplicates))
    st.stop()

columns = raw.columns.tolist()
st.markdown("### 1. Relaciona las columnas")
st.caption("Las sugerencias se basan solo en el nombre del encabezado. Confírmalas o cámbialas.")
suggestions = suggest_mapping(columns)
canonical_fields = ["fecha", "producto", "cantidad", "precio_unitario", "costo_unitario", "categoria"]
mapping: dict[str, object | None] = {}
column_options = ["— Sin asignar —", *columns]
for start in range(0, len(canonical_fields), 3):
    group = canonical_fields[start : start + 3]
    cols = st.columns(len(group), gap="medium")
    for col, field in zip(cols, group):
        with col:
            suggestion = suggestions[field]
            index = column_options.index(suggestion) if suggestion in column_options else 0
            selected = st.selectbox(
                f"{FIELD_LABELS[field]}{' (obligatorio)' if field != 'categoria' else ' (opcional)'}",
                column_options,
                index=index,
                key=f"map_{source_key}_{field}",
            )
        mapping[field] = None if selected == column_options[0] else selected

selected_sources = [source for source in mapping.values() if source is not None]
if len(selected_sources) != len(set(selected_sources)):
    st.error("Una columna de origen está asignada a más de un campo. Elige una columna diferente para cada campo.")
    st.stop()

st.markdown("### 2. Elige cómo interpretar los valores")
date_col, number_col = st.columns(2, gap="medium")
with date_col:
    date_style = st.selectbox(
        "Orden de fecha", ["Día primero (31/12/2025)", "Mes primero (12/31/2025)"],
        key=f"date_style_{source_key}",
    )
with number_col:
    number_style_label = st.selectbox(
        "Formato numérico", ["Punto decimal: 1,234.56", "Coma decimal: 1.234,56"],
        key=f"number_style_{source_key}",
    )
day_first = date_style.startswith("Día")
decimal_style = "punto" if number_style_label.startswith("Punto") else "coma"

mapped, issues = prepare_mapped_data(raw, mapping, day_first=day_first, decimal_style=decimal_style)
corrected = mapped.copy()
if issues:
    st.markdown("### 3. Completa los datos que faltan o no se pudieron interpretar")
    st.warning(f"Encontré {len(issues)} dato(s) obligatorio(s) por revisar. Cada pregunta identifica la fila y el campo.")
    for issue in issues:
        field = str(issue["field"])
        label = (
            f"Fila {issue['source_row']} · {issue['label']} — {issue['reason']} "
            f"(contenido original: {issue['original']}). Escribe el valor correcto"
        )
        answer = st.text_input(label, key=f"fix_{source_key}_{issue['row_pos']}_{field}")
        parsed = parse_correction(field, answer, day_first=day_first, decimal_style=decimal_style)
        corrected.iat[int(issue["row_pos"]), corrected.columns.get_loc(field)] = parsed

try:
    valid = validate_sales(corrected)
except DataValidationError as error:
    st.error(f"Aún hay datos por corregir: {error}")
    st.stop()

st.markdown("### 4. Revisa y usa el archivo preparado")
st.success(f"El archivo está listo: {len(valid):,} filas validadas. No se cambió el archivo original.")
st.dataframe(valid.head(20), use_container_width=True, hide_index=True)
csv_content = valid.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8-sig")
download_col, use_col = st.columns([1, 1], gap="medium")
with download_col:
    st.download_button(
        "Descargar CSV listo para Nexo", data=csv_content,
        file_name="ventas_nexo.csv", mime="text/csv", use_container_width=True,
    )
with use_col:
    if st.button("Usar este archivo en Análisis", type="primary", use_container_width=True):
        st.session_state["nexo_prepared_sales"] = valid
        st.session_state["nexo_prepared_name"] = uploaded.name
        st.session_state["nexo_prepared_key"] = source_key
        st.switch_page("app.py")
