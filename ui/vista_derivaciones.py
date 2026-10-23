"""Vista de Derivaciones: emisión de órdenes con muestras y línea de tiempo de estados de cada muestra."""

from __future__ import annotations

import flet as ft

from dominio import CambioEstadoMuestra, Laboratorio, Muestra, OrdenDerivacion, TipoAnalisis
from dominio.estados_muestra import SECUENCIA_NORMAL
from servicios import ServicioAtencion, ServicioCatalogos, ServicioDerivacion, ServicioMascotas
from ui.comun import (
    COLOR_ERROR,
    COLORES_ESTADO,
    celda,
    desplegable,
    ejecutar,
    encabezado,
    entero,
    etiqueta_estado,
    fecha_legible,
    mostrar_mensaje,
    numero,
    opciones_desplegable,
    tabla_datos,
    tarjeta,
    texto,
)
from ui.vista_base import Vista

ESTADOS_ORDEN = ["Emitida", "En proceso", "Finalizada", "Anulada"]
ICONOS_ESTADO = {
    "Extraída": ft.Icons.COLORIZE, "Empaquetada": ft.Icons.INVENTORY_2, "En tránsito": ft.Icons.LOCAL_SHIPPING,
    "Recibida": ft.Icons.MOVE_TO_INBOX, "Analizada": ft.Icons.CHECK_CIRCLE, "Rechazada": ft.Icons.CANCEL,
}


def linea_de_tiempo(historial: list[CambioEstadoMuestra]) -> ft.Control:
    """Línea de tiempo vertical: un hito por cambio de estado (inmutable) con fecha, responsable y observación.
    Los estados de la secuencia normal que todavía no ocurrieron se muestran atenuados."""
    ocurridos = [c.estado for c in historial]
    hitos: list[tuple[str, CambioEstadoMuestra | None]] = [(c.estado, c) for c in historial]
    if "Rechazada" not in ocurridos:
        hitos += [(e, None) for e in SECUENCIA_NORMAL if e not in ocurridos]

    filas: list[ft.Control] = []
    for i, (estado, cambio) in enumerate(hitos):
        color = COLORES_ESTADO.get(estado, ft.Colors.GREY_600) if cambio else ft.Colors.GREY_400
        ultimo = i == len(hitos) - 1
        marcador = ft.Column([
            ft.Container(ft.Icon(ICONOS_ESTADO.get(estado, ft.Icons.CIRCLE), color=ft.Colors.WHITE, size=16),
                         bgcolor=color, border_radius=16, width=32, height=32,
                         alignment=ft.Alignment.CENTER),
            ft.Container(width=2, height=0 if ultimo else 38, bgcolor=ft.Colors.GREY_300),
        ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        if cambio:
            detalle = [ft.Text(estado, weight=ft.FontWeight.BOLD, color=color),
                       ft.Text(f"{fecha_legible(cambio.fecha_hora)} · {cambio.responsable}", size=12)]
            if cambio.observacion:
                detalle.append(ft.Text(cambio.observacion, size=12, italic=True, color=ft.Colors.GREY_700))
        else:
            detalle = [ft.Text(estado, color=ft.Colors.GREY_500), ft.Text("Pendiente", size=12, color=ft.Colors.GREY_500)]
        filas.append(ft.Row([marcador, ft.Column(detalle, spacing=1, expand=True)],
                            vertical_alignment=ft.CrossAxisAlignment.START))
    return ft.Column(filas, spacing=0)


class VistaDerivaciones(Vista):
    titulo = "Derivaciones"
    subtitulo = "Órdenes de derivación a laboratorio y trazabilidad de cada muestra."

    def __init__(self, page: ft.Page) -> None:
        super().__init__(page)
        self.servicio = ServicioDerivacion()
        self.atencion = ServicioAtencion()
        self.mascotas = ServicioMascotas()
        self.catalogos = ServicioCatalogos()
        self._muestras_nuevas: list[tuple[int, float | None]] = []
        self._tipos: dict[int, str] = {}
        self._laboratorios: dict[int, str] = {}
        self._orden_sel: OrdenDerivacion | None = None

    # --- Construcción -------------------------------------------------------------------

    def construir(self) -> ft.Control:
        # Emitir orden
        self.dd_mascota = desplegable("Mascota *", width=260, filtro=True, on_select=self._al_elegir_mascota)
        self.dd_atencion = desplegable("Atención *", width=300)
        self.dd_laboratorio = desplegable("Laboratorio *", width=300)
        self.dd_prioridad = desplegable("Prioridad", [("Normal", "Normal"), ("Urgente", "Urgente")], width=140)
        self.dd_prioridad.value = "Normal"
        self.txt_indicaciones = ft.TextField(label="Indicaciones", expand=True)
        self.dd_tipo = desplegable("Tipo de análisis", width=260)
        self.txt_volumen = ft.TextField(label="Volumen (ml)", width=130)
        self.tabla_nuevas = tabla_datos(["Análisis", "Volumen", ""])
        emitir = tarjeta(ft.Column([
            ft.Row([self.dd_mascota, self.dd_atencion, self.dd_laboratorio], wrap=True),
            ft.Row([self.dd_prioridad, self.txt_indicaciones]),
            ft.Row([self.dd_tipo, self.txt_volumen,
                    ft.OutlinedButton("Agregar muestra", icon=ft.Icons.ADD, on_click=self._agregar_muestra)]),
            self.tabla_nuevas,
            ft.FilledButton("Emitir orden", icon=ft.Icons.ASSIGNMENT, on_click=self._emitir),
        ], spacing=10), "Emitir orden de derivación")

        # Órdenes y muestras
        self.dd_estado = desplegable("Estado", [("", "Todas"), *((e, e) for e in ESTADOS_ORDEN)], width=180,
                                     on_select=lambda _e: self.cargar())
        self.tabla_ordenes = tabla_datos(["N°", "Emisión", "Mascota", "Laboratorio", "Prioridad", "Estado", ""])
        self.lbl_orden = ft.Text("Elegí una orden para ver sus muestras.", color=ft.Colors.GREY_700)
        self.tabla_muestras = tabla_datos(["Código", "Análisis", "Extracción", "Estado", ""])
        self.titulo_linea = ft.Text("Línea de tiempo", weight=ft.FontWeight.BOLD, size=15)
        self.panel_linea = ft.Container(ft.Text("Elegí una muestra.", color=ft.Colors.GREY_700), padding=8)

        listado = ft.Column([
            ft.Row([ft.Text("Órdenes", weight=ft.FontWeight.BOLD, size=15), self.dd_estado]),
            ft.Row([self.tabla_ordenes], scroll=ft.ScrollMode.AUTO),
            self.lbl_orden,
            ft.Row([self.tabla_muestras], scroll=ft.ScrollMode.AUTO),
        ], expand=3)
        linea = ft.Container(ft.Column([self.titulo_linea, self.panel_linea], scroll=ft.ScrollMode.AUTO),
                             expand=2, padding=12, border_radius=10, bgcolor=ft.Colors.GREY_50)

        return ft.Column([
            encabezado(self.titulo, self.subtitulo),
            emitir,
            ft.Row([listado, linea], vertical_alignment=ft.CrossAxisAlignment.START),
        ], spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)

    # --- Datos --------------------------------------------------------------------------

    def al_mostrar(self) -> None:
        self._tipos = {t.id_tipo_analisis: t.nombre for t in self.catalogos.listar(TipoAnalisis)}
        self._laboratorios = {lab.id_laboratorio: lab.nombre for lab in self.catalogos.listar(Laboratorio)}
        self.dd_tipo.options = opciones_desplegable(self._tipos.items())
        self.dd_laboratorio.options = opciones_desplegable(self._laboratorios.items())
        if len(self._laboratorios) == 1:
            self.dd_laboratorio.value = str(next(iter(self._laboratorios)))
        self.dd_mascota.options = opciones_desplegable(sorted(
            ((m.id_mascota, m.nombre) for m in self.mascotas.buscar_por_nombre("")), key=lambda x: x[1]))
        self.cargar()

    def cargar(self) -> None:
        ordenes = self.servicio.listar_ordenes(self.dd_estado.value or None)
        self.tabla_ordenes.rows = [ft.DataRow(cells=[
            celda(o.id_orden, negrita=True), celda(fecha_legible(o.fecha_emision)),
            celda(self._mascota_de(o.id_atencion)), celda(self._laboratorios.get(o.id_laboratorio)),
            ft.DataCell(etiqueta_estado("Urgente") if o.prioridad == "Urgente" else ft.Text("Normal")),
            ft.DataCell(etiqueta_estado(o.estado)),
            ft.DataCell(ft.IconButton(ft.Icons.VISIBILITY, tooltip="Ver muestras",
                                      on_click=lambda _e, x=o: self.seleccionar_orden(x))),
        ], selected=self._orden_sel is not None and o.id_orden == self._orden_sel.id_orden) for o in ordenes]
        if self._orden_sel:
            self.seleccionar_orden(self.servicio.obtener_orden(self._orden_sel.id_orden))
        self.actualizar()

    def _mascota_de(self, id_atencion: int) -> str:
        return self.atencion.mascota_de_atencion(id_atencion).nombre

    def seleccionar_orden(self, orden: OrdenDerivacion) -> None:
        self._orden_sel = orden
        muestras = self.servicio.muestras_de_orden(orden.id_orden)
        self.lbl_orden.value = (f"Orden N° {orden.id_orden} - {self._mascota_de(orden.id_atencion)}"
                                f"{' · ' + orden.indicaciones if orden.indicaciones else ''}")
        self.lbl_orden.weight = ft.FontWeight.BOLD
        self.tabla_muestras.rows = [ft.DataRow(cells=[
            celda(m.codigo, negrita=True), celda(self._tipos.get(m.id_tipo_analisis)),
            celda(fecha_legible(m.fecha_hora_extraccion)), ft.DataCell(etiqueta_estado(m.estado_actual)),
            ft.DataCell(ft.IconButton(ft.Icons.TIMELINE, tooltip="Ver línea de tiempo",
                                      on_click=lambda _e, x=m: self.mostrar_linea(x))),
        ]) for m in muestras]
        if muestras:
            self.mostrar_linea(muestras[0])
        self.actualizar()

    def mostrar_linea(self, muestra: Muestra) -> None:
        self.titulo_linea.value = f"Línea de tiempo · {muestra.codigo} ({self._tipos.get(muestra.id_tipo_analisis)})"
        self.panel_linea.content = linea_de_tiempo(self.servicio.historial_de_muestra(muestra.id_muestra))
        self.actualizar()

    # --- Emitir orden ---------------------------------------------------------------------

    def _al_elegir_mascota(self, _e=None) -> None:
        id_mascota = entero(self.dd_mascota)
        atenciones = self.atencion.atenciones_de_mascota(id_mascota) if id_mascota else []
        self.dd_atencion.options = opciones_desplegable(
            (a.id_atencion, f"{fecha_legible(a.fecha_hora)} - {a.motivo}") for a in reversed(atenciones))
        self.dd_atencion.value = str(atenciones[-1].id_atencion) if atenciones else None
        self.actualizar()

    def _agregar_muestra(self, _e=None) -> None:
        def agregar() -> None:
            if entero(self.dd_tipo) is None:
                raise ValueError("Elegí el tipo de análisis.")
            self._muestras_nuevas.append((entero(self.dd_tipo), numero(self.txt_volumen, "volumen")))

        if ejecutar(self.page, agregar):
            self.txt_volumen.value = ""
            self._refrescar_nuevas()
        self.actualizar()

    def _refrescar_nuevas(self) -> None:
        def quitar(i: int) -> None:
            self._muestras_nuevas.pop(i)
            self._refrescar_nuevas()
            self.actualizar()

        self.tabla_nuevas.rows = [ft.DataRow(cells=[
            celda(self._tipos.get(id_tipo)), celda(f"{vol:g} ml" if vol else None),
            ft.DataCell(ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=COLOR_ERROR,
                                      on_click=lambda _e, i=i: quitar(i))),
        ]) for i, (id_tipo, vol) in enumerate(self._muestras_nuevas)]

    def _emitir(self, _e=None) -> None:
        if entero(self.dd_atencion) is None or entero(self.dd_laboratorio) is None:
            mostrar_mensaje(self.page, "Elegí la atención y el laboratorio.", error=True)
            return
        resultado = {}

        def emitir() -> None:
            resultado["o"] = self.servicio.emitir_orden(
                entero(self.dd_atencion), entero(self.dd_laboratorio), list(self._muestras_nuevas),
                prioridad=self.dd_prioridad.value or "Normal", indicaciones=texto(self.txt_indicaciones))

        if ejecutar(self.page, emitir, lambda _r: f"Orden N° {resultado['o'].orden.id_orden} emitida con "
                                                  f"{len(resultado['o'].muestras)} muestra(s)."):
            self._muestras_nuevas.clear()
            self.txt_indicaciones.value = ""
            self._refrescar_nuevas()
            self._orden_sel = resultado["o"].orden
            self.dd_estado.value = ""
            self.cargar()
        self.actualizar()
