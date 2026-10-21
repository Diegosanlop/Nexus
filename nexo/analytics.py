"""Carga, validación y análisis de ventas.

Supuestos: ingresos = cantidad * precio_unitario; coste vendido = cantidad *
costo_unitario; ganancia bruta = ingresos - coste vendido. El margen es
ganancia bruta / ingresos y queda indefinido cuando los ingresos son cero.
"""

from io import BytesIO, StringIO
import math
from pathlib import Path
from zipfile import BadZipFile

import pandas as pd

REQUIRED_COLUMNS = ("fecha", "producto", "cantidad", "precio_unitario", "costo_unitario")
OPTIONAL_COLUMNS = ("categoria",)


class DataValidationError(ValueError):
    """Error de formato o contenido que el usuario puede corregir."""


def read_tabular_file(filename: str, content: bytes) -> pd.DataFrame:
    """Lee sin validar un CSV o la primera hoja de un Excel, sin cambiar el origen."""
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".csv":
            frame = pd.read_csv(StringIO(content.decode("utf-8-sig")))
        elif suffix in {".xlsx", ".xlsm"}:
            frame = pd.read_excel(BytesIO(content), engine="openpyxl")
        else:
            raise DataValidationError("Formato no admitido. Sube un archivo CSV o Excel.")
    except DataValidationError:
        raise
    except UnicodeDecodeError as exc:
        raise DataValidationError("El CSV debe estar codificado en UTF-8. Guarda una copia como CSV UTF-8 y vuelve a cargarla.") from exc
    except pd.errors.EmptyDataError as exc:
        raise DataValidationError("El archivo está vacío o no contiene una fila de encabezados.") from exc
    except pd.errors.ParserError as exc:
        raise DataValidationError("No se pudo interpretar el CSV. Revisa que sus filas tengan el mismo número de columnas.") from exc
    except BadZipFile as exc:
        raise DataValidationError("No se pudo abrir el libro Excel. Comprueba que sea un archivo .xlsx o .xlsm válido y no esté dañado.") from exc
    except (ValueError, OSError) as exc:
        raise DataValidationError(f"No se pudo leer el archivo: {exc}") from exc
    return frame


def load_sales_file(filename: str, content: bytes) -> pd.DataFrame:
    """Lee y valida CSV o Excel en el formato canónico de Nexo."""
    return validate_sales(read_tabular_file(filename, content))


def validate_sales(data: pd.DataFrame) -> pd.DataFrame:
    """Valida un DataFrame y devuelve una copia normalizada para el análisis."""
    if not isinstance(data, pd.DataFrame):
        raise DataValidationError("Los datos deben tener formato tabular.")
    frame = data.copy()
    # Solo quitamos espacios de encabezados; no renombramos ni inferimos columnas.
    frame.columns = [str(column).strip() for column in frame.columns]
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise DataValidationError("Faltan columnas obligatorias: " + ", ".join(missing))
    duplicates = frame.columns[frame.columns.duplicated()].tolist()
    if duplicates:
        raise DataValidationError("Hay nombres de columna duplicados: " + ", ".join(duplicates))
    if frame.empty:
        raise DataValidationError("El archivo no contiene filas de ventas.")

    for column in REQUIRED_COLUMNS:
        missing_mask = frame[column].isna() | (frame[column].astype("string").str.strip() == "")
        if missing_mask.any():
            rows = _row_numbers(missing_mask)
            raise DataValidationError(f"Hay valores faltantes en '{column}' (filas: {_rows(rows)}).")

    parsed_dates = pd.to_datetime(frame["fecha"], errors="coerce")
    bad_dates = parsed_dates.isna()
    if bad_dates.any():
        raise DataValidationError(f"Fechas inválidas en filas: {_rows(_row_numbers(bad_dates))}.")
    frame["fecha"] = parsed_dates

    for column in ("cantidad", "precio_unitario", "costo_unitario"):
        original = frame[column]
        numeric = pd.to_numeric(original, errors="coerce")
        bad = numeric.isna()
        if bad.any():
            raise DataValidationError(
                f"'{column}' debe contener números; revisa las filas: {_rows(_row_numbers(bad))}."
            )
        nonfinite = ~numeric.map(_is_finite)
        if nonfinite.any():
            raise DataValidationError(
                f"'{column}' contiene valores no finitos en filas: {_rows(_row_numbers(nonfinite))}."
            )
        if column == "cantidad" and (numeric <= 0).any():
            rows = _row_numbers(numeric <= 0)
            raise DataValidationError(f"'cantidad' debe ser mayor que cero (filas: {_rows(rows)}).")
        if column != "cantidad" and (numeric < 0).any():
            rows = _row_numbers(numeric < 0)
            raise DataValidationError(f"'{column}' no puede ser negativo (filas: {_rows(rows)}).")
        frame[column] = numeric

    if frame["producto"].astype("string").str.strip().eq("").any():
        raise DataValidationError("'producto' no puede estar vacío.")
    if "categoria" in frame.columns:
        blank = frame["categoria"].isna() | frame["categoria"].astype("string").str.strip().eq("")
        frame.loc[blank, "categoria"] = "Sin categoría"
    return frame


def calculate_summary(data: pd.DataFrame) -> dict[str, float | int]:
    """Calcula indicadores globales. Exige datos previamente validados."""
    frame = _with_metrics(data)
    revenue = float(frame["ingresos"].sum())
    cost = float(frame["coste"].sum())
    if not math.isfinite(revenue) or not math.isfinite(cost):
        raise DataValidationError("Los totales exceden el rango numérico admitido; revisa cantidades, precios y costes.")
    profit = revenue - cost
    return {
        "ingresos": revenue,
        "coste": cost,
        "ganancia_bruta": profit,
        "margen_bruto": profit / revenue if revenue else float("nan"),
        "unidades": float(frame["cantidad"].sum()),
        "productos_distintos": int(frame["producto"].nunique()),
    }


def product_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Agrupa ventas por producto y calcula margen sobre importes agregados."""
    frame = _with_metrics(data)
    result = frame.groupby("producto", as_index=False).agg(
        unidades=("cantidad", "sum"), ingresos=("ingresos", "sum"), coste=("coste", "sum")
    )
    result["ganancia_bruta"] = result["ingresos"] - result["coste"]
    if not _all_finite(result, ("ingresos", "coste", "ganancia_bruta")):
        raise DataValidationError("Los totales por producto exceden el rango numérico admitido.")
    result["margen_bruto"] = result["ganancia_bruta"].div(result["ingresos"].where(result["ingresos"] != 0))
    return result.sort_values("ingresos", ascending=False, kind="stable").reset_index(drop=True)


def revenue_by_date(data: pd.DataFrame) -> pd.DataFrame:
    frame = _with_metrics(data)
    return frame.groupby("fecha", as_index=False)["ingresos"].sum().sort_values("fecha")


def revenue_by_category(data: pd.DataFrame) -> pd.DataFrame:
    if "categoria" not in data.columns:
        return pd.DataFrame(columns=["categoria", "ingresos"])
    frame = _with_metrics(data)
    return frame.groupby("categoria", as_index=False)["ingresos"].sum().sort_values("ingresos", ascending=False)


def _with_metrics(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    frame["ingresos"] = frame["cantidad"] * frame["precio_unitario"]
    frame["coste"] = frame["cantidad"] * frame["costo_unitario"]
    if not _all_finite(frame, ("ingresos", "coste")):
        raise DataValidationError("Una cantidad por precio o coste produjo un importe no finito; revisa los valores de origen.")
    return frame


def _all_finite(frame: pd.DataFrame, columns: tuple[str, ...]) -> bool:
    return all(frame[column].map(_is_finite).all() for column in columns)


def _is_finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _row_numbers(mask: pd.Series) -> list[int]:
    """Translate a bad-value mask to spreadsheet row numbers (header is row 1)."""
    return [position + 2 for position, is_bad in enumerate(mask.tolist()) if is_bad]


def _rows(rows: list[int]) -> str:
    return ", ".join(map(str, rows[:10])) + ("…" if len(rows) > 10 else "")
