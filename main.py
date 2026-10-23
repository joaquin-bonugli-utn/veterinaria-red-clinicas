"""Punto de entrada: inicializa la base y abre la aplicación Flet.

Uso:  python main.py      (o: flet run main.py)
Para cargar datos de prueba antes:  python db/seed.py
"""

from __future__ import annotations

import flet as ft

from persistencia.conexion import Conexion
from ui.app import AplicacionVeterinaria


def main(page: ft.Page) -> None:
    AplicacionVeterinaria(page)


def inicializar_base() -> None:
    """Abre (o crea) veterinaria.db y aplica el esquema; es idempotente (IF NOT EXISTS)."""
    Conexion.obtener().inicializar_esquema()


if __name__ == "__main__":
    inicializar_base()
    ft.run(main)
