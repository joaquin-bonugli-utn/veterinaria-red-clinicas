"""Vista de Reportes: genera cada PDF con filtros de fechas y clínica y lo abre."""

from __future__ import annotations

from datetime import date, timedelta

import flet as ft

from dominio import Clinica
from servicios import ServicioCatalogos, ServicioReportes
from ui.comun import (
    COLOR_PRIMARIO,
    CampoFecha,
    abrir_archivo,
    desplegable,
    ejecutar,
    encabezado,
    entero,
    mostrar_mensaje,
    opciones_desplegable,
    tarjeta,
)
from ui.vista_base import Vista


class VistaReportes(Vista):
    titulo = "Reportes"
    subtitulo = "Reportes PDF con tablas y gráficos. Se guardan en la carpeta salida/ y se abren al generarlos."

    def __init__(self, page: ft.Page, abrir=abrir_archivo) -> None:
        super().__init__(page)
        self.servicio = ServicioReportes()
        self.catalogos = ServicioCatalogos()
        self._abrir = abrir  # inyectable para los tests
        self.generados: list = []

    def construir(self) -> ft.Control:
        hoy = date.today()
        self.desde = CampoFecha(self.page, "Desde", (hoy - timedelta(days=91)).isoformat(), width=150)
        self.hasta = CampoFecha(self.page, "Hasta", hoy.isoformat(), width=150)
        self.dd_clinica = desplegable("Clínica", width=260)
        self.lbl_estado = ft.Text(color=ft.Colors.GREY_700)
        tarjetas = [self._tarjeta(r) for r in self.servicio.disponibles()]
        return ft.Column([
            encabezado(self.titulo, self.subtitulo),
            tarjeta(ft.Row([self.desde.control, self.hasta.control, self.dd_clinica,
                            ft.OutlinedButton("Generar todos", icon=ft.Icons.DONE_ALL,
                                              on_click=lambda _e: self.generar_todos())], wrap=True), "Filtros"),
            *tarjetas,
            self.lbl_estado,
        ], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

    def _tarjeta(self, reporte) -> ft.Control:
        return ft.Container(ft.Row([
            ft.Icon(ft.Icons.PICTURE_AS_PDF, color=COLOR_PRIMARIO, size=36),
            ft.Column([ft.Text(reporte.titulo, weight=ft.FontWeight.BOLD, size=15),
                       ft.Text(reporte.descripcion, size=12, color=ft.Colors.GREY_700)], expand=True, spacing=2),
            ft.FilledButton("Generar y abrir", icon=ft.Icons.OPEN_IN_NEW,
                            on_click=lambda _e, clave=reporte.clave: self.generar(clave)),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=14, border_radius=10,
            border=ft.Border.all(1, ft.Colors.BLUE_GREY_100))

    def al_mostrar(self) -> None:
        self.dd_clinica.options = opciones_desplegable(
            [("", "Todas las clínicas"), *((c.id_clinica, c.nombre) for c in self.catalogos.listar(Clinica))])
        self.actualizar()

    def generar(self, clave: str, abrir: bool = True) -> None:
        resultado: dict = {}

        def generar():
            resultado["ruta"] = self.servicio.generar(clave, self.desde.valor or "", self.hasta.valor or "",
                                                      entero(self.dd_clinica))
            return resultado["ruta"]

        if ejecutar(self.page, generar, lambda ruta: f"Generado: {ruta.name}"):
            ruta = resultado["ruta"]
            self.generados.append(ruta)
            self.lbl_estado.value = f"Último reporte: {ruta}"
            if abrir:
                try:
                    self._abrir(ruta)
                except OSError as error:
                    mostrar_mensaje(self.page, f"Se generó {ruta.name} pero no se pudo abrir: {error}", error=True)
        self.actualizar()

    def generar_todos(self) -> None:
        cantidad = len(self.generados)
        for reporte in self.servicio.disponibles():
            self.generar(reporte.clave, abrir=False)
        nuevos = self.generados[cantidad:]
        if nuevos:
            mostrar_mensaje(self.page, f"Se generaron {len(nuevos)} reportes en {nuevos[0].parent}.")
            try:
                self._abrir(nuevos[0].parent)  # abre la carpeta salida/
            except OSError:
                pass
        self.actualizar()
