"""Preparación explícita de tablas de ventas con columnas de origen variadas."""

from __future__ import annotations

import math
import re
import unicodedata

import pandas as pd

from nexo.analytics import REQUIRED_COLUMNS

FIELD_LABELS = {
    "fecha": "Fecha",
    "producto": "Producto",
    "cantidad": "Cantidad",
    "precio_unitario": "Precio unitario",
    "costo_unitario": "Costo unitario",
    "categoria": "Categoría",
}

_ALIASES = {
    "fecha": {"fecha", "date", "datetime", "dia", "fechaventa", "diaventa", "diadeventa", "fechadeventa"},
    "producto": {"producto", "product", "articulo", "item", "description", "descripcion", "sku"},
    "cantidad": {"cantidad", "quantity", "qty", "unidades", "units"},
    "precio_unitario": {"preciounitario", "precio", "unitprice", "price", "valorunitario"},
    "costo_unitario": {"costounitario", "costo", "cost", "unitcost", "costodeventa"},
    "categoria": {"categoria", "category", "linea", "rubro"},
}


def normalize_header(value: object) -> str:
    """Normaliza encabezados solo para sugerir una relación, nunca para renombrar."""
    decomposed = unicodedata.normalize("NFKD", str(value))
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", without_marks.lower())


def suggest_mapping(columns: list[object]) -> dict[str, object | None]:
    """Sugiere coincidencias exactas de alias normalizados, sin consumir columnas."""
    normalized = {column: normalize_header(column) for column in columns}
    result: dict[str, object | None] = {}
    for field, aliases in _ALIASES.items():
        matches = [column for column, name in normalized.items() if name in aliases]
        result[field] = matches[0] if len(matches) == 1 else None
    return result


def parse_number(value: object, decimal_style: str) -> float | None:
    """Convierte un número con la convención elegida explícitamente por la persona."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"(?i)\b(?:MXN|USD|MX\$|US\$)\b", "", text)
    text = text.replace("$", "").replace("€", "").replace("£", "").replace(" ", "")
    if decimal_style == "punto":
        text = text.replace(",", "")
    elif decimal_style == "coma":
        text = text.replace(".", "").replace(",", ".")
    else:
        raise ValueError("decimal_style debe ser 'punto' o 'coma'.")
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _parse_date(value: object, day_first: bool) -> pd.Timestamp | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce", dayfirst=day_first, format="mixed")
    except (TypeError, ValueError, OverflowError):
        return None
    return None if pd.isna(parsed) else pd.Timestamp(parsed)


def prepare_mapped_data(
    raw: pd.DataFrame,
    mapping: dict[str, object | None],
    *,
    day_first: bool,
    decimal_style: str,
) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    """Construye datos canónicos y devuelve un issue por celda obligatoria a corregir.

    Los índices de fila de ``issues`` son posicionales; ``source_row`` es el número
    visible en la hoja, suponiendo encabezados en la primera fila.
    """
    output_columns = list(REQUIRED_COLUMNS)
    if mapping.get("categoria") is not None:
        output_columns.append("categoria")
    prepared = pd.DataFrame(index=range(len(raw)), columns=output_columns)
    issues: list[dict[str, object]] = []

    for position in range(len(raw)):
        for field in output_columns:
            source_column = mapping.get(field)
            original = raw.iloc[position][source_column] if source_column is not None else None
            reason: str | None = None
            if field == "fecha":
                parsed = _parse_date(original, day_first)
                if parsed is None:
                    reason = "fecha vacía o no reconocida"
            elif field == "producto":
                parsed = None if original is None or pd.isna(original) else str(original).strip()
                if not parsed:
                    reason = "nombre vacío"
            elif field in {"cantidad", "precio_unitario", "costo_unitario"}:
                parsed = parse_number(original, decimal_style)
                if parsed is None:
                    reason = "valor vacío o no numérico"
                elif field == "cantidad" and parsed <= 0:
                    reason = "la cantidad debe ser mayor que cero"
                elif field != "cantidad" and parsed < 0:
                    reason = "el valor no puede ser negativo"
            else:
                parsed = None if original is None or pd.isna(original) else str(original).strip()
            prepared.iat[position, prepared.columns.get_loc(field)] = parsed
            if reason:
                issues.append({
                    "row_pos": position,
                    "source_row": position + 2,
                    "field": field,
                    "label": FIELD_LABELS[field],
                    "reason": reason,
                    "original": "(vacío)" if original is None or pd.isna(original) else str(original),
                })
    return prepared, issues


def parse_correction(field: str, value: str, *, day_first: bool, decimal_style: str) -> object | None:
    """Interpreta un valor que la persona ingresó para resolver un issue."""
    if field == "fecha":
        return _parse_date(value, day_first)
    if field == "producto":
        return value.strip() or None
    if field in {"cantidad", "precio_unitario", "costo_unitario"}:
        return parse_number(value, decimal_style)
    return value.strip() or None
