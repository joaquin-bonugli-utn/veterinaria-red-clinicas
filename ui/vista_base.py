"""Clase base de las vistas de la aplicación."""

from __future__ import annotations

from abc import ABC, abstractmethod

import flet as ft

from ui.comun import encabezado


class Vista(ABC):
    """Una sección de la app. Construye sus controles una sola vez (perezosamente)
    y refresca sus datos cada vez que se muestra (``al_mostrar``)."""

    titulo: str = ""
    subtitulo: str = ""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self._control: ft.Control | None = None

    @property
    def control(self) -> ft.Control:
        if self._control is None:
            self._control = self.construir()
        return self._control

    @abstractmethod
    def construir(self) -> ft.Control:
        """Arma y devuelve el árbol de controles de la vista."""

    def al_mostrar(self) -> None:
        """Se llama al entrar a la sección; por defecto no hace nada."""

    def actualizar(self) -> None:
        self.page.update()


class VistaEnConstruccion(Vista):
    """Marcador para las secciones que todavía no están implementadas."""

    def __init__(self, page: ft.Page, titulo: str) -> None:
        super().__init__(page)
        self.titulo = titulo

    def construir(self) -> ft.Control:
        return ft.Column([
            encabezado(self.titulo),
            ft.Container(height=40),
            ft.Row([ft.Icon(ft.Icons.CONSTRUCTION, size=48, color=ft.Colors.AMBER_700),
                    ft.Text("Sección en construcción.", size=16)], spacing=16),
        ])
