"""Ventana principal: NavigationRail con las secciones y área de contenido."""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from ui.comun import COLOR_PRIMARIO
from ui.vista_atencion import VistaAtencion
from ui.vista_base import Vista, VistaEnConstruccion
from ui.vista_clientes import VistaClientes
from ui.vista_comprobantes import VistaComprobantes
from ui.vista_derivaciones import VistaDerivaciones
from ui.vista_envios import VistaEnvios
from ui.vista_laboratorio import VistaLaboratorio
from ui.vista_mascotas import VistaMascotas
from ui.vista_reportes import VistaReportes
from ui.vista_turnos import VistaTurnos

# (título, ícono, ícono seleccionado, fábrica de la vista o None si todavía no existe)
SECCIONES: list[tuple[str, str, str, Callable[[ft.Page], Vista] | None]] = [
    ("Clientes", ft.Icons.PEOPLE_OUTLINE, ft.Icons.PEOPLE, VistaClientes),
    ("Mascotas", ft.Icons.PETS_OUTLINED, ft.Icons.PETS, VistaMascotas),
    ("Turnos", ft.Icons.EVENT_OUTLINED, ft.Icons.EVENT, VistaTurnos),
    ("Atención", ft.Icons.MEDICAL_SERVICES_OUTLINED, ft.Icons.MEDICAL_SERVICES, VistaAtencion),
    ("Derivaciones", ft.Icons.BIOTECH_OUTLINED, ft.Icons.BIOTECH, VistaDerivaciones),
    ("Envíos", ft.Icons.LOCAL_SHIPPING_OUTLINED, ft.Icons.LOCAL_SHIPPING, VistaEnvios),
    ("Laboratorio", ft.Icons.SCIENCE_OUTLINED, ft.Icons.SCIENCE, VistaLaboratorio),
    ("Comprobantes", ft.Icons.RECEIPT_LONG_OUTLINED, ft.Icons.RECEIPT_LONG, VistaComprobantes),
    ("Reportes", ft.Icons.PICTURE_AS_PDF_OUTLINED, ft.Icons.PICTURE_AS_PDF, VistaReportes),
]


class AplicacionVeterinaria:
    """Arma la ventana y cambia de vista según la sección elegida en el NavigationRail."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self._vistas: dict[int, Vista] = {}

        page.title = "Red de Clínicas Veterinarias"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.theme = ft.Theme(color_scheme_seed=COLOR_PRIMARIO)
        page.padding = 0
        page.window.width = 1280
        page.window.height = 800
        page.window.min_width = 960
        page.window.min_height = 600

        self.rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=96,
            leading=ft.Container(ft.Icon(ft.Icons.LOCAL_HOSPITAL, size=36, color=COLOR_PRIMARIO),
                                 padding=ft.Padding.only(top=16, bottom=8)),
            destinations=[ft.NavigationRailDestination(icon=icono, selected_icon=seleccionado, label=titulo)
                          for titulo, icono, seleccionado, _ in SECCIONES],
            on_change=lambda e: self.mostrar(e.control.selected_index),
        )
        self.contenido = ft.Container(expand=True, padding=24)
        page.add(ft.Row([self.rail, ft.VerticalDivider(width=1), self.contenido], expand=True))
        self.mostrar(0)

    def vista(self, indice: int) -> Vista:
        if indice not in self._vistas:
            titulo, _, _, fabrica = SECCIONES[indice]
            self._vistas[indice] = fabrica(self.page) if fabrica else VistaEnConstruccion(self.page, titulo)
        return self._vistas[indice]

    def mostrar(self, indice: int) -> None:
        vista = self.vista(indice)
        self.rail.selected_index = indice
        self.contenido.content = vista.control
        vista.al_mostrar()
        self.page.update()
