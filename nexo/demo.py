"""Datos ficticios y reproducibles para probar la aplicación."""

import pandas as pd


def demo_sales() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("2025-01-03", "Café molido", "Bebidas", 12, 145.0, 82.0),
            ("2025-01-03", "Taza térmica", "Accesorios", 5, 230.0, 128.0),
            ("2025-01-10", "Café molido", "Bebidas", 8, 145.0, 82.0),
            ("2025-01-10", "Té verde", "Bebidas", 10, 98.0, 49.0),
            ("2025-01-18", "Taza térmica", "Accesorios", 7, 230.0, 128.0),
            ("2025-01-24", "Té verde", "Bebidas", 6, 98.0, 49.0),
            ("2025-02-02", "Café molido", "Bebidas", 15, 145.0, 82.0),
            ("2025-02-08", "Taza térmica", "Accesorios", 4, 230.0, 128.0),
            ("2025-02-15", "Té verde", "Bebidas", 13, 98.0, 49.0),
            ("2025-02-21", "Café molido", "Bebidas", 9, 145.0, 82.0),
        ],
        columns=["fecha", "producto", "categoria", "cantidad", "precio_unitario", "costo_unitario"],
    )
