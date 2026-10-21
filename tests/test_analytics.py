from io import BytesIO

import pandas as pd
import pytest

from nexo.analytics import DataValidationError, calculate_summary, load_sales_file, product_summary, validate_sales
from nexo.demo import demo_sales


def test_summary_uses_revenue_cost_and_gross_profit_separately():
    summary = calculate_summary(validate_sales(demo_sales()))
    assert summary["ingresos"] == pytest.approx(12902)
    assert summary["coste"] == pytest.approx(7077)
    assert summary["ganancia_bruta"] == pytest.approx(5825)
    assert summary["margen_bruto"] == pytest.approx(5825 / 12902)
    assert summary["unidades"] == 89
    assert summary["productos_distintos"] == 3


def test_product_margin_uses_aggregate_money_values():
    result = product_summary(validate_sales(demo_sales())).set_index("producto")
    assert result.loc["Café molido", "ingresos"] == 6380
    assert result.loc["Café molido", "ganancia_bruta"] == 2772
    assert result.loc["Café molido", "margen_bruto"] == pytest.approx(2772 / 6380)


def test_zero_revenue_has_undefined_margin():
    frame = pd.DataFrame([{"fecha": "2025-01-01", "producto": "Muestra", "cantidad": 1, "precio_unitario": 0, "costo_unitario": 0}])
    assert pd.isna(calculate_summary(validate_sales(frame))["margen_bruto"])
    assert pd.isna(product_summary(validate_sales(frame)).loc[0, "margen_bruto"])


@pytest.mark.parametrize("changes, message", [
    ({"precio_unitario": -1}, "no puede ser negativo"),
    ({"costo_unitario": -1}, "no puede ser negativo"),
    ({"cantidad": -1}, "mayor que cero"),
    ({"cantidad": "abc"}, "debe contener números"),
    ({"fecha": "fecha inválida"}, "Fechas inválidas"),
    ({"producto": None}, "valores faltantes"),
])
def test_invalid_values_are_reported(changes, message):
    frame = demo_sales().iloc[[0]].copy()
    for column, value in changes.items():
        frame[column] = frame[column].astype(object)
        frame.loc[frame.index[0], column] = value
    with pytest.raises(DataValidationError, match=message):
        validate_sales(frame)


def test_missing_required_column_is_reported():
    with pytest.raises(DataValidationError, match="Faltan columnas obligatorias.*costo_unitario"):
        validate_sales(demo_sales().drop(columns="costo_unitario"))


def test_validator_does_not_mutate_input():
    original = demo_sales()
    before = original.copy(deep=True)
    validate_sales(original)
    pd.testing.assert_frame_equal(original, before)


def test_loads_and_validates_csv_bytes():
    content = demo_sales().to_csv(index=False).encode("utf-8")
    loaded = load_sales_file("ventas.csv", content)
    assert len(loaded) == 10
    assert pd.api.types.is_datetime64_any_dtype(loaded["fecha"])
    assert calculate_summary(loaded)["ingresos"] == 12902


def test_loads_and_validates_first_excel_sheet():
    output = BytesIO()
    demo_sales().to_excel(output, index=False, engine="openpyxl")
    loaded = load_sales_file("ventas.xlsx", output.getvalue())
    assert len(loaded) == 10
    assert calculate_summary(loaded)["ganancia_bruta"] == 5825


def test_rejects_malformed_excel_with_actionable_error():
    with pytest.raises(DataValidationError, match="No se pudo abrir el libro Excel"):
        load_sales_file("ventas.xlsx", b"esto no es un libro Excel")


def test_rejects_values_that_overflow_calculated_amounts():
    frame = pd.DataFrame([{"fecha": "2025-01-01", "producto": "Grande", "cantidad": 1e308, "precio_unitario": 1e308, "costo_unitario": 0}])
    with pytest.raises(DataValidationError, match="importe no finito"):
        calculate_summary(validate_sales(frame))


def test_row_errors_use_file_position_even_with_custom_dataframe_index():
    frame = demo_sales().iloc[[0]].copy()
    frame.index = ["registro-abc"]
    frame["cantidad"] = -1
    with pytest.raises(DataValidationError, match="filas: 2"):
        validate_sales(frame)


def test_rejects_csv_that_is_not_utf8():
    with pytest.raises(DataValidationError, match="CSV debe estar codificado en UTF-8"):
        load_sales_file("ventas.csv", b"producto,precio\nCaf\xe9,100")
