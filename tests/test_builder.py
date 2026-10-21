import pandas as pd
import pytest

from nexo.analytics import DataValidationError, validate_sales
from nexo.builder import parse_correction, parse_number, prepare_mapped_data, suggest_mapping


def test_suggests_common_spanish_and_english_headers():
    mapping = suggest_mapping(["Día de venta", "Artículo", "Qty", "Precio", "Costo", "Categoría"])
    assert mapping == {
        "fecha": "Día de venta",
        "producto": "Artículo",
        "cantidad": "Qty",
        "precio_unitario": "Precio",
        "costo_unitario": "Costo",
        "categoria": "Categoría",
    }


@pytest.mark.parametrize(
    "value, style, expected",
    [("1,234.56", "punto", 1234.56), ("1.234,56", "coma", 1234.56), ("$ 80,50", "coma", 80.5)],
)
def test_parse_number_uses_the_selected_separator_convention(value, style, expected):
    assert parse_number(value, style) == pytest.approx(expected)


def test_parse_number_does_not_guess_invalid_content():
    assert parse_number("aprox. 100", "punto") is None


def test_builder_reports_each_missing_or_invalid_required_cell():
    raw = pd.DataFrame(
        {
            "Fecha venta": ["31/12/2025", "no es fecha"],
            "Artículo": ["Taza", None],
            "Unidades": ["2", "abc"],
            "Precio": ["100,50", "200,00"],
            "Costo": ["60,00", "-1,00"],
        }
    )
    mapping = {
        "fecha": "Fecha venta",
        "producto": "Artículo",
        "cantidad": "Unidades",
        "precio_unitario": "Precio",
        "costo_unitario": "Costo",
        "categoria": None,
    }
    prepared, issues = prepare_mapped_data(raw, mapping, day_first=True, decimal_style="coma")
    assert [(issue["source_row"], issue["field"]) for issue in issues] == [
        (3, "fecha"), (3, "producto"), (3, "cantidad"), (3, "costo_unitario")
    ]
    assert prepared.loc[0, "precio_unitario"] == pytest.approx(100.5)


def test_missing_source_column_prompts_for_every_row_and_corrections_validate():
    raw = pd.DataFrame({"Artículo": ["Taza", "Té"], "Unidades": [1, 2], "Precio": [10, 20], "Costo": [4, 8]})
    mapping = {
        "fecha": None,
        "producto": "Artículo",
        "cantidad": "Unidades",
        "precio_unitario": "Precio",
        "costo_unitario": "Costo",
        "categoria": None,
    }
    prepared, issues = prepare_mapped_data(raw, mapping, day_first=True, decimal_style="punto")
    assert [issue["source_row"] for issue in issues] == [2, 3]
    for row_pos, date in enumerate(["2025-01-01", "2025-01-02"]):
        prepared.iat[row_pos, prepared.columns.get_loc("fecha")] = parse_correction(
            "fecha", date, day_first=True, decimal_style="punto"
        )
    assert len(validate_sales(prepared)) == 2


def test_corrections_still_pass_through_strict_validation():
    invalid = pd.DataFrame(
        [{"fecha": "2025-01-01", "producto": "Taza", "cantidad": 1, "precio_unitario": 10, "costo_unitario": -2}]
    )
    with pytest.raises(DataValidationError, match="no puede ser negativo"):
        validate_sales(invalid)
