# Nexo Intelligence — MVP de ventas

Aplicación local para preparar y analizar ventas desde CSV o Excel. Incluye una página **Constructor** separada para relacionar columnas de origen, elegir los formatos de fecha y número, completar cada dato obligatorio que falte o no se pueda leer, y descargar un CSV canónico o enviarlo directamente al análisis. La página **Análisis** presenta ingresos, costes, ganancia bruta, filtros, productos y gráficos. Si no se carga un archivo, muestra datos ficticios reproducibles claramente identificados.

## Requisitos y ejecución

Se recomienda Python 3.10 o superior. Desde la carpeta del proyecto:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Para ejecutar pruebas: `python -m pytest -p no:debugging -q`. En el entorno de desarrollo se desactiva el plugin de depuración de Pytest porque su importación provoca un cierre del intérprete; las pruebas normales siguen ejecutándose.

## Preparar un archivo con el Constructor

En la navegación de Streamlit, abre **Constructor** y carga un CSV o Excel. El Constructor sugiere relaciones por los encabezados, pero las puedes cambiar; luego pide escoger el orden de fecha y el separador decimal. Si una celda obligatoria está vacía o no se puede interpretar, aparece un input específico con su fila, campo y contenido original. Completa esos inputs y corrige también cantidades no positivas o precios/costes negativos. Al validar, puedes descargar `ventas_nexo.csv` o pasar el conjunto preparado a **Análisis**. El archivo original permanece intacto. La importación directa desde Análisis todavía requiere el formato canónico.

## Formato canónico de archivo

La primera fila debe contener exactamente `fecha`, `producto`, `cantidad`, `precio_unitario` y `costo_unitario`. `categoria` es opcional. Se admiten CSV UTF-8, `.xlsx` y `.xlsm`; Excel se lee desde la primera hoja. Las fechas deben ser reconocibles por Pandas. Los valores deben estar en una sola moneda y con formato numérico estándar (punto decimal, sin símbolos de moneda).

Las cantidades deben ser mayores que cero; precios y costes pueden ser cero, pero no negativos. Se reportan las filas con valores faltantes o inválidos. No se cambia el archivo cargado. Las celdas vacías de categoría se agrupan como “Sin categoría”.

## Supuestos financieros

- Ingresos = cantidad × precio unitario.
- Coste de ventas = cantidad × costo unitario.
- Ganancia bruta = ingresos − coste de ventas; puede ser negativa.
- Margen bruto = ganancia bruta agregada / ingresos agregados. Se muestra como no disponible cuando no hay ingresos.
- No se modelan IVA, descuentos, devoluciones, gastos operativos ni conversión de moneda. Los importes de origen se asumen homogéneos.
