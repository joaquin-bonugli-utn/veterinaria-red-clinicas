"""Genera los 5 reportes PDF en la carpeta salida/.

Uso:
    python reportes/generar_todos.py                       # últimos 3 meses, todas las clínicas
    python reportes/generar_todos.py --desde 2026-08-01 --hasta 2026-10-31 --clinica 1
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:  # permite ejecutar "python reportes/generar_todos.py" desde la raíz
    sys.path.insert(0, str(RAIZ))

from persistencia.conexion import Conexion  # noqa: E402
from reportes import CARPETA_SALIDA, REPORTES, FiltrosReporte  # noqa: E402


def generar_todos(filtros: FiltrosReporte, carpeta: Path = CARPETA_SALIDA) -> list[Path]:
    return [clase().generar(filtros, carpeta) for clase in REPORTES]


def main() -> None:
    hoy = date.today()
    parser = argparse.ArgumentParser(description="Genera los reportes PDF de la red de clínicas.")
    parser.add_argument("--desde", default=(hoy - timedelta(days=91)).isoformat(), help="YYYY-MM-DD (inclusive)")
    parser.add_argument("--hasta", default=hoy.isoformat(), help="YYYY-MM-DD (inclusive)")
    parser.add_argument("--clinica", type=int, default=None, help="id de clínica (opcional)")
    args = parser.parse_args()

    filtros = FiltrosReporte(args.desde, args.hasta, args.clinica)
    Conexion.obtener()
    for ruta in generar_todos(filtros):
        print(f"  {ruta.relative_to(RAIZ)}  ({ruta.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
