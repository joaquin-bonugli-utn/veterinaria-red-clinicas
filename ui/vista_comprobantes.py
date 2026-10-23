"""Vista de Comprobantes: facturación de atenciones (patrón Strategy de tarifas) y consulta de emitidos."""

from __future__ import annotations

from datetime import date, timedelta

import flet as ft

from dominio import Clinica, Comprobante, TipoAtencion
from servicios import ServicioAtencion, ServicioCatalogos, ServicioClientes, ServicioFacturacion
from ui.comun import (
    CampoFecha,
    celda,
    confirmar,
    desplegable,
    dialogo_info,
    ejecutar,
    encabezado,
    entero,
    fecha_legible,
    moneda,
    opciones_desplegable,
    tabla_datos,
)
from ui.vista_base import Vista


class VistaComprobantes(Vista):
    titulo = "Comprobantes"
    subtitulo = ("Cada atención se factura una sola vez, con su detalle de vacunas y análisis no rechazados. "
                 "La tarifa depende del tipo de atención: urgencia +30 %, control -20 %.")

    def __init__(self, page: ft.Page) -> None:
        super().__init__(page)
        self.servicio = ServicioFacturacion()
        self.atencion = ServicioAtencion()
        self.clientes = ServicioClientes()
        self.catalogos = ServicioCatalogos()
        self._clinicas: dict[int, str] = {}
        self._tipos: dict[int, str] = {}
        self._clientes: dict[int, str] = {}

    def construir(self) -> ft.Control:
        hoy = date.today()
        self.desde = CampoFecha(self.page, "Desde", (hoy - timedelta(days=30)).isoformat(), width=150)
        self.hasta = CampoFecha(self.page, "Hasta", hoy.isoformat(), width=150)
        self.dd_clinica = desplegable("Clínica", width=240)
        self.tabla_pendientes = tabla_datos(["Fecha", "Mascota", "Responsable", "Tipo", "Clínica", ""])
        self.tabla_emitidos = tabla_datos(["Número", "Emisión", "Cliente", "Clínica", "Total", ""], numericas=(4,))
        self.lbl_total = ft.Text(weight=ft.FontWeight.BOLD)
        filtros = ft.Row([self.desde.control, self.hasta.control, self.dd_clinica,
                          ft.FilledButton("Buscar", icon=ft.Icons.SEARCH, on_click=lambda _e: self.cargar())], wrap=True)
        seccion = lambda t: ft.Text(t, weight=ft.FontWeight.BOLD, size=15)  # noqa: E731
        return ft.Column([
            encabezado(self.titulo, self.subtitulo),
            filtros,
            seccion("Atenciones pendientes de facturar"),
            ft.Row([self.tabla_pendientes], scroll=ft.ScrollMode.AUTO),
            ft.Row([seccion("Comprobantes emitidos"), self.lbl_total]),
            ft.Row([self.tabla_emitidos], scroll=ft.ScrollMode.AUTO),
        ], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

    # --- Datos --------------------------------------------------------------------------

    def al_mostrar(self) -> None:
        self._clinicas = {c.id_clinica: c.nombre for c in self.catalogos.listar(Clinica)}
        self._tipos = {t.id_tipo_atencion: t.nombre for t in self.catalogos.listar(TipoAtencion)}
        self._clientes = {c.id_cliente: c.nombre_completo for c in self.clientes.listar(solo_activos=False)}
        self.dd_clinica.options = opciones_desplegable([("", "Todas"), *self._clinicas.items()])
        self.cargar()

    def _rango(self) -> tuple[str, str]:
        """Rango semiabierto [desde, hasta+1) a partir de las fechas inclusivas del filtro."""
        desde = self.desde.valor or "2000-01-01"
        hasta = date.fromisoformat(self.hasta.valor or date.today().isoformat()) + timedelta(days=1)
        return desde, hasta.isoformat()

    def cargar(self) -> None:
        desde, hasta = self._rango()
        id_clinica = entero(self.dd_clinica)
        filas = []
        for a in sorted(self.servicio.atenciones_sin_facturar(desde, hasta, id_clinica),
                        key=lambda x: x.fecha_hora, reverse=True):
            mascota = self.atencion.mascota_de_atencion(a.id_atencion)
            filas.append(ft.DataRow(cells=[
                celda(fecha_legible(a.fecha_hora)), celda(mascota.nombre, negrita=True),
                celda(self._clientes.get(mascota.id_cliente)), celda(self._tipos.get(a.id_tipo_atencion)),
                celda(self._clinicas.get(a.id_clinica)),
                ft.DataCell(ft.FilledButton("Facturar", icon=ft.Icons.RECEIPT,
                                            on_click=lambda _e, x=a: self._facturar(x))),
            ]))
        self.tabla_pendientes.rows = filas

        emitidos = sorted(self.servicio.comprobantes_por_rango(desde, hasta, id_clinica),
                          key=lambda c: c.numero, reverse=True)
        self.tabla_emitidos.rows = [ft.DataRow(cells=[
            celda(c.numero, negrita=True), celda(fecha_legible(c.fecha_emision)), celda(self._clientes.get(c.id_cliente)),
            celda(self._clinicas.get(c.id_clinica)), celda(moneda(c.total)),
            ft.DataCell(ft.IconButton(ft.Icons.VISIBILITY, tooltip="Ver detalle",
                                      on_click=lambda _e, x=c: self.ver_detalle(x))),
        ]) for c in emitidos]
        self.lbl_total.value = f"· {len(emitidos)} comprobante(s) · total {moneda(sum(c.total for c in emitidos))}"
        self.actualizar()

    # --- Acciones -----------------------------------------------------------------------

    def _facturar(self, atencion) -> None:
        tipo = self._tipos.get(atencion.id_tipo_atencion, "")

        def facturar() -> None:
            resultado: dict = {}
            if ejecutar(self.page, lambda: resultado.setdefault(
                    "c", self.servicio.emitir_comprobante(atencion.id_atencion, atencion.fecha_hora[:10])),
                    lambda c: f"Comprobante {c.numero} emitido por {moneda(c.total)}."):
                self.cargar()
                self.ver_detalle(resultado["c"])
            self.actualizar()

        confirmar(self.page, "Emitir comprobante",
                  f"¿Facturar la atención del {fecha_legible(atencion.fecha_hora)} ({tipo})? "
                  "No se podrá facturar dos veces.", facturar, "Emitir")

    def ver_detalle(self, comprobante: Comprobante) -> None:
        comprobante = self.servicio.obtener(comprobante.id_comprobante)
        tabla = tabla_datos(["Tipo", "Descripción", "Cant.", "P. unitario", "Subtotal"], numericas=(2, 3, 4))
        tabla.rows = [ft.DataRow(cells=[
            celda(d.tipo_item), celda(d.descripcion), celda(d.cantidad), celda(moneda(d.precio_unitario)),
            celda(moneda(d.subtotal), negrita=True)]) for d in comprobante.detalles]
        dialogo_info(self.page, f"Comprobante {comprobante.numero}", ft.Column([
            ft.Text(f"Cliente: {self._clientes.get(comprobante.id_cliente)} · "
                    f"Clínica: {self._clinicas.get(comprobante.id_clinica)} · "
                    f"Fecha: {fecha_legible(comprobante.fecha_emision)}"),
            ft.Row([tabla], scroll=ft.ScrollMode.AUTO),
            ft.Text(f"TOTAL {moneda(comprobante.total)}", size=18, weight=ft.FontWeight.BOLD),
        ], tight=True), ancho=820)
