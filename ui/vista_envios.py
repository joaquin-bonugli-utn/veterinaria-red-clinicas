"""Vista de Envíos: empaquetado en conservadora (remito + precinto) y tramos de la cadena de custodia."""

from __future__ import annotations

from datetime import date, datetime

import flet as ft

from dominio import Clinica, RemitoBiologico, TipoAnalisis, Transportista
from servicios import ServicioAtencion, ServicioCatalogos, ServicioDerivacion, ServicioEnvios
from ui.comun import (
    CampoFecha,
    campo_hora,
    celda,
    desplegable,
    dialogo_formulario,
    ejecutar,
    encabezado,
    entero,
    etiqueta_estado,
    fecha_hora,
    fecha_legible,
    mostrar_mensaje,
    numero,
    opciones_desplegable,
    tabla_datos,
    tarjeta,
    texto,
)
from ui.vista_base import Vista

ESTADOS_REMITO = ["Emitido", "En tránsito", "Recibido", "Rechazado"]


class VistaEnvios(Vista):
    titulo = "Envíos"
    subtitulo = ("Empaquetado de muestras en conservadoras con remito y precinto sanitario, "
                 "y registro de cada tramo hasta el laboratorio.")

    def __init__(self, page: ft.Page) -> None:
        super().__init__(page)
        self.servicio = ServicioEnvios()
        self.derivacion = ServicioDerivacion()
        self.atencion = ServicioAtencion()
        self.catalogos = ServicioCatalogos()
        self._clinicas: dict[int, str] = {}
        self._tipos: dict[int, str] = {}
        self._transportistas: dict[int, str] = {}
        self._checks: dict[int, ft.Checkbox] = {}
        self._remito_sel: RemitoBiologico | None = None

    # --- Construcción -------------------------------------------------------------------

    def construir(self) -> ft.Control:
        ahora = datetime.now()
        self.dd_clinica = desplegable("Clínica de origen *", width=260, on_select=self._al_elegir_clinica)
        self.dd_conservadora = desplegable("Conservadora *", width=300)
        self.txt_precinto = ft.TextField(label="N° de precinto *", width=170)
        self.txt_temp = ft.TextField(label="Temp. de cierre (°C) *", width=170)
        self.fecha_empaque = CampoFecha(self.page, "Fecha *", ahora.date().isoformat())
        self.hora_empaque = campo_hora("Hora *", ahora.strftime("%H:%M"))
        self.lista_muestras = ft.Column(spacing=0)
        empaquetar = tarjeta(ft.Column([
            ft.Row([self.dd_clinica, self.dd_conservadora], wrap=True),
            ft.Text("Muestras extraídas pendientes de envío (de la clínica elegida):", weight=ft.FontWeight.W_500),
            self.lista_muestras,
            ft.Row([self.txt_precinto, self.txt_temp, self.fecha_empaque.control, self.hora_empaque], wrap=True),
            ft.FilledButton("Empaquetar y generar remito", icon=ft.Icons.INVENTORY_2, on_click=self._empaquetar),
        ], spacing=10), "Empaquetar muestras")

        self.dd_estado = desplegable("Estado", [("", "Todos"), *((e, e) for e in ESTADOS_REMITO)], width=180,
                                     on_select=lambda _e: self.cargar())
        self.tabla_remitos = tabla_datos(["Remito", "Emisión", "Clínica", "Muestras", "Tramos", "Estado", ""])
        self.panel_detalle = ft.Column(spacing=10)
        return ft.Column([
            encabezado(self.titulo, self.subtitulo),
            empaquetar,
            ft.Row([ft.Text("Remitos", weight=ft.FontWeight.BOLD, size=15), self.dd_estado]),
            ft.Row([self.tabla_remitos], scroll=ft.ScrollMode.AUTO),
            self.panel_detalle,
        ], spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)

    # --- Datos --------------------------------------------------------------------------

    def al_mostrar(self) -> None:
        self._clinicas = {c.id_clinica: c.nombre for c in self.catalogos.listar(Clinica)}
        self._tipos = {t.id_tipo_analisis: t.nombre for t in self.catalogos.listar(TipoAnalisis)}
        self._transportistas = {t.id_transportista: t.nombre for t in self.catalogos.listar(Transportista)}
        self.dd_clinica.options = opciones_desplegable(self._clinicas.items())
        self._al_elegir_clinica()
        self.cargar()

    def _al_elegir_clinica(self, _e=None) -> None:
        id_clinica = entero(self.dd_clinica)
        conservadoras = self.servicio.conservadoras_disponibles(id_clinica) if id_clinica else []
        self.dd_conservadora.options = opciones_desplegable(
            (c.id_conservadora, f"{c.codigo} · cap. {c.capacidad} · {c.temp_min:g} a {c.temp_max:g} °C")
            for c in conservadoras)
        self.dd_conservadora.value = str(conservadoras[0].id_conservadora) if conservadoras else None
        self._checks = {}
        controles: list[ft.Control] = []
        for m in self.servicio.muestras_pendientes_de_envio(id_clinica):
            orden = self.derivacion.obtener_orden(m.id_orden)
            mascota = self.atencion.mascota_de_atencion(orden.id_atencion).nombre
            check = ft.Checkbox(label=f"{m.codigo} · {self._tipos.get(m.id_tipo_analisis)} · {mascota} · "
                                      f"extraída {fecha_legible(m.fecha_hora_extraccion)}")
            self._checks[m.id_muestra] = check
            controles.append(check)
        self.lista_muestras.controls = controles or [ft.Text("No hay muestras pendientes.", color=ft.Colors.GREY_600)]
        self.actualizar()

    def cargar(self) -> None:
        remitos = self.servicio.listar_remitos(self.dd_estado.value or None)
        self.tabla_remitos.rows = [ft.DataRow(cells=[
            celda(r.numero, negrita=True), celda(fecha_legible(r.fecha_emision)), celda(self._clinicas.get(r.id_clinica)),
            celda(len(self.servicio.muestras_de_remito(r.id_remito))), celda(len(self.servicio.tramos_de(r.id_remito))),
            ft.DataCell(etiqueta_estado(r.estado)),
            ft.DataCell(ft.IconButton(ft.Icons.VISIBILITY, tooltip="Ver detalle y tramos",
                                      on_click=lambda _e, x=r: self.seleccionar(x))),
        ]) for r in remitos]
        if self._remito_sel:
            self.seleccionar(self.servicio.obtener_remito(self._remito_sel.id_remito))
        self.actualizar()

    def seleccionar(self, remito: RemitoBiologico) -> None:
        self._remito_sel = remito
        precinto = self.servicio.obtener_precinto(remito.id_remito)
        tramos = self.servicio.tramos_de(remito.id_remito)
        muestras = self.servicio.muestras_de_remito(remito.id_remito)

        tabla_tramos = tabla_datos(["N°", "Origen", "Destino", "Transportista", "Salida", "Llegada", "Temp.", ""])
        tabla_tramos.rows = [ft.DataRow(cells=[
            celda(t.nro_tramo), celda(t.origen), celda(t.destino), celda(self._transportistas.get(t.id_transportista)),
            celda(fecha_legible(t.fecha_hora_salida)), celda(fecha_legible(t.fecha_hora_llegada)),
            celda(f"{t.temperatura:g} °C" if t.temperatura is not None else None),
            ft.DataCell(ft.TextButton("Registrar llegada", on_click=lambda _e, x=t: self._llegada(x))
                        if not t.finalizado else ft.Text("")),
        ]) for t in tramos]

        controles: list[ft.Control] = [
            ft.Divider(),
            ft.Row([ft.Text(f"Remito {remito.numero}", weight=ft.FontWeight.BOLD, size=16), etiqueta_estado(remito.estado)]),
            ft.Row([ft.Text(f"Precinto {precinto.numero} · cerrado a {precinto.temp_cierre:g} °C el "
                            f"{fecha_legible(precinto.fecha_colocacion)}" if precinto else "Sin precinto"),
                    etiqueta_estado(precinto.estado) if precinto else ft.Text("")]),
            ft.Row([ft.Text("Muestras:", weight=ft.FontWeight.W_500),
                    *(ft.Row([ft.Text(m.codigo), etiqueta_estado(m.estado_actual)], spacing=4) for m in muestras)],
                   wrap=True),
            ft.Text("Tramos", weight=ft.FontWeight.BOLD),
            ft.Row([tabla_tramos], scroll=ft.ScrollMode.AUTO) if tramos else ft.Text("Todavía sin tramos.",
                                                                                     color=ft.Colors.GREY_600),
        ]
        if remito.estado in ("Emitido", "En tránsito"):
            controles.append(self._formulario_tramo(remito, tramos))
        self.panel_detalle.controls = controles
        self.actualizar()

    def _formulario_tramo(self, remito: RemitoBiologico, tramos) -> ft.Control:
        origen_sugerido = tramos[-1].destino if tramos else self._clinicas.get(remito.id_clinica, "")
        self.dd_transportista = desplegable("Transportista *", self._transportistas.items(), width=220)
        self.txt_origen = ft.TextField(label="Origen *", value=origen_sugerido, width=220)
        self.txt_destino = ft.TextField(label="Destino *", width=220)
        self.fecha_salida = CampoFecha(self.page, "Salida *", date.today().isoformat(), width=150)
        self.hora_salida = campo_hora("Hora *", datetime.now().strftime("%H:%M"))
        self.fecha_llegada = CampoFecha(self.page, "Llegada", width=150)
        self.hora_llegada = campo_hora("Hora")
        self.txt_temp_tramo = ft.TextField(label="Temp. (°C)", width=110)
        nota = "El primer tramo pasa el remito y sus muestras a En tránsito." if not tramos else ""
        return tarjeta(ft.Column([
            ft.Row([self.dd_transportista, self.txt_origen, self.txt_destino], wrap=True),
            ft.Row([self.fecha_salida.control, self.hora_salida, self.fecha_llegada.control, self.hora_llegada,
                    self.txt_temp_tramo], wrap=True),
            ft.Row([ft.FilledButton("Registrar tramo", icon=ft.Icons.LOCAL_SHIPPING,
                                    on_click=lambda _e: self._registrar_tramo(remito)),
                    ft.Text(nota, size=12, color=ft.Colors.GREY_700)]),
        ], spacing=10), f"Nuevo tramo (N° {len(tramos) + 1})")

    # --- Acciones -----------------------------------------------------------------------

    def _empaquetar(self, _e=None) -> None:
        seleccionadas = [id_m for id_m, check in self._checks.items() if check.value]
        if not seleccionadas:
            mostrar_mensaje(self.page, "Marcá al menos una muestra para empaquetar.", error=True)
            return

        def empaquetar() -> RemitoBiologico:
            if entero(self.dd_conservadora) is None:
                raise ValueError("Elegí una conservadora disponible.")
            temp = numero(self.txt_temp, "temperatura de cierre")
            if temp is None:
                raise ValueError("Indicá la temperatura de cierre.")
            return self.servicio.empaquetar(seleccionadas, entero(self.dd_conservadora), self.txt_precinto.value or "",
                                            temp, fecha_hora=fecha_hora(self.fecha_empaque, self.hora_empaque))

        remito: dict = {}
        if ejecutar(self.page, lambda: remito.setdefault("r", empaquetar()),
                    lambda r: f"Remito {r.numero} generado con {len(seleccionadas)} muestra(s)."):
            self.txt_precinto.value = self.txt_temp.value = ""
            self._remito_sel = remito["r"]
            self._al_elegir_clinica()
            self.cargar()
        self.actualizar()

    def _registrar_tramo(self, remito: RemitoBiologico) -> None:
        def registrar():
            if entero(self.dd_transportista) is None:
                raise ValueError("Elegí el transportista.")
            llegada = (fecha_hora(self.fecha_llegada, self.hora_llegada, "llegada")
                       if self.fecha_llegada.valor else None)
            return self.servicio.registrar_tramo(
                remito.id_remito, entero(self.dd_transportista), texto(self.txt_origen) or "",
                texto(self.txt_destino) or "", fecha_hora(self.fecha_salida, self.hora_salida, "salida"),
                llegada, numero(self.txt_temp_tramo, "temperatura"))

        if ejecutar(self.page, registrar, lambda t: f"Tramo {t.nro_tramo} registrado."):
            self.cargar()
        self.actualizar()

    def _llegada(self, tramo) -> None:
        fecha = CampoFecha(self.page, "Fecha de llegada", date.today().isoformat())
        hora = campo_hora("Hora", datetime.now().strftime("%H:%M"))
        temp = ft.TextField(label="Temperatura (°C)", width=160)

        def guardar() -> bool:
            ok = ejecutar(self.page, lambda: self.servicio.registrar_llegada_tramo(
                tramo.id_tramo, fecha_hora(fecha, hora, "llegada"), numero(temp, "temperatura")),
                "Llegada registrada.")
            if ok:
                self.cargar()
            return ok

        dialogo_formulario(self.page, f"Llegada del tramo {tramo.nro_tramo} ({tramo.origen} a {tramo.destino})",
                           [fecha.control, ft.Row([hora, temp])], guardar)
