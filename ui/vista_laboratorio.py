"""Vista de Laboratorio: recepción de remitos (control de precinto) y carga de resultados."""

from __future__ import annotations

from datetime import date, datetime

import flet as ft

from dominio import Clinica, Muestra, RemitoBiologico, TipoAnalisis
from servicios import ServicioCatalogos, ServicioEnvios, ServicioLaboratorio
from ui.comun import (
    CampoFecha,
    campo_hora,
    celda,
    dialogo_formulario,
    dialogo_info,
    ejecutar,
    encabezado,
    etiqueta_estado,
    fecha_hora,
    fecha_legible,
    numero,
    tabla_datos,
    texto,
)
from ui.vista_base import Vista


class VistaLaboratorio(Vista):
    titulo = "Laboratorio"
    subtitulo = ("Si el precinto llega roto se rechaza el remito completo. Con precinto intacto se rechazan "
                 "solo las muestras con viabilidad vencida o temperatura fuera de rango.")

    def __init__(self, page: ft.Page) -> None:
        super().__init__(page)
        self.servicio = ServicioLaboratorio()
        self.envios = ServicioEnvios()
        self.catalogos = ServicioCatalogos()
        self._tipos: dict[int, TipoAnalisis] = {}
        self._clinicas: dict[int, str] = {}

    def construir(self) -> ft.Control:
        self.tabla_remitos = tabla_datos(["Remito", "Clínica", "Muestras", "Último tramo", "Precinto", ""])
        self.tabla_muestras = tabla_datos(["Código", "Análisis", "Extracción", "Viabilidad", "Orden", ""])
        self.tabla_resultados = tabla_datos(["Código", "Análisis", "Fecha", "Bioquímico/a", "Valores", "Conclusión"])
        seccion = lambda t: ft.Text(t, weight=ft.FontWeight.BOLD, size=15)  # noqa: E731
        return ft.Column([
            encabezado(self.titulo, self.subtitulo),
            seccion("Remitos en tránsito"),
            ft.Row([self.tabla_remitos], scroll=ft.ScrollMode.AUTO),
            seccion("Muestras recibidas pendientes de resultado"),
            ft.Row([self.tabla_muestras], scroll=ft.ScrollMode.AUTO),
            seccion("Últimos resultados cargados"),
            ft.Row([self.tabla_resultados], scroll=ft.ScrollMode.AUTO),
        ], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

    # --- Datos --------------------------------------------------------------------------

    def al_mostrar(self) -> None:
        self._tipos = {t.id_tipo_analisis: t for t in self.catalogos.listar(TipoAnalisis)}
        self._clinicas = {c.id_clinica: c.nombre for c in self.catalogos.listar(Clinica)}
        self.cargar()

    def cargar(self) -> None:
        filas = []
        for r in self.servicio.remitos_en_transito():
            tramos = self.envios.tramos_de(r.id_remito)
            precinto = self.envios.obtener_precinto(r.id_remito)
            ultimo = tramos[-1] if tramos else None
            filas.append(ft.DataRow(cells=[
                celda(r.numero, negrita=True), celda(self._clinicas.get(r.id_clinica)),
                celda(len(self.envios.muestras_de_remito(r.id_remito))),
                celda(f"{ultimo.destino} ({fecha_legible(ultimo.fecha_hora_llegada) if ultimo.finalizado else 'en viaje'})"
                      if ultimo else None),
                celda(precinto.numero if precinto else None),
                ft.DataCell(ft.FilledButton("Recibir", icon=ft.Icons.MOVE_TO_INBOX,
                                            on_click=lambda _e, x=r: self._recibir(x))),
            ]))
        self.tabla_remitos.rows = filas

        self.tabla_muestras.rows = [ft.DataRow(cells=[
            celda(m.codigo, negrita=True), celda(self._tipos[m.id_tipo_analisis].nombre),
            celda(fecha_legible(m.fecha_hora_extraccion)), celda(f"{self._tipos[m.id_tipo_analisis].horas_viabilidad} h"),
            celda(m.id_orden),
            ft.DataCell(ft.FilledButton("Cargar resultado", icon=ft.Icons.SCIENCE,
                                        on_click=lambda _e, x=m: self._resultado(x))),
        ]) for m in self.servicio.muestras_para_analizar()]

        self.tabla_resultados.rows = [ft.DataRow(cells=[
            celda(m.codigo), celda(self._tipos[m.id_tipo_analisis].nombre), celda(fecha_legible(res.fecha_hora)),
            celda(res.bioquimico), celda(res.valores), celda(res.conclusion),
        ]) for m, res in self.servicio.resultados_recientes()]
        self.actualizar()

    # --- Acciones -----------------------------------------------------------------------

    def _recibir(self, remito: RemitoBiologico) -> None:
        txt_receptor = ft.TextField(label="Receptor/a *")
        sw_precinto = ft.Switch(label="Precinto intacto", value=True)
        txt_temp = ft.TextField(label="Temperatura de llegada (°C)", width=220)
        fecha = CampoFecha(self.page, "Fecha *", date.today().isoformat())
        hora = campo_hora("Hora *", datetime.now().strftime("%H:%M"))
        txt_obs = ft.TextField(label="Observaciones", multiline=True, min_lines=2)
        resultado: dict = {}

        def guardar() -> bool:
            def recibir():
                resultado["r"] = self.servicio.recibir(
                    remito.id_remito, txt_receptor.value or "", bool(sw_precinto.value), numero(txt_temp, "temperatura"),
                    fecha_hora=fecha_hora(fecha, hora, "recepción"), observaciones=texto(txt_obs))

            ok = ejecutar(self.page, recibir)
            if ok:
                self.cargar()
                self._mostrar_recepcion(remito, resultado["r"])
            return ok

        dialogo_formulario(self.page, f"Recibir remito {remito.numero}",
                           [txt_receptor, sw_precinto, txt_temp, ft.Row([fecha.control, hora]), txt_obs],
                           guardar, "Registrar recepción")

    def _mostrar_recepcion(self, remito: RemitoBiologico, r) -> None:
        roto = r.recepcion.estado_precinto == "Roto"
        lineas: list[ft.Control] = [
            ft.Row([ft.Text("Precinto:"), etiqueta_estado(r.recepcion.estado_precinto),
                    ft.Text("Remito:"), etiqueta_estado("Rechazado" if roto else "Recibido")]),
            ft.Text(f"Aceptadas: {len(r.aceptadas)} · Rechazadas: {len(r.rechazadas)}", weight=ft.FontWeight.BOLD),
        ]
        for m in r.aceptadas:
            lineas.append(ft.Row([etiqueta_estado("Recibida"), ft.Text(f"{m.codigo} · {self._tipos[m.id_tipo_analisis].nombre}")]))
        for m in r.rechazadas:
            lineas.append(ft.Row([etiqueta_estado("Rechazada"),
                                  ft.Text(f"{m.codigo} · {m.ultimo_cambio.observacion}", expand=True)]))
        dialogo_info(self.page, f"Recepción del remito {remito.numero}", ft.Column(lineas, tight=True), ancho=560)

    def _resultado(self, muestra: Muestra) -> None:
        tipo = self._tipos[muestra.id_tipo_analisis]
        txt_bioq = ft.TextField(label="Bioquímico/a *")
        txt_valores = ft.TextField(label="Valores *", multiline=True, min_lines=3)
        txt_conclusion = ft.TextField(label="Conclusión")
        fecha = CampoFecha(self.page, "Fecha *", date.today().isoformat())
        hora = campo_hora("Hora *", datetime.now().strftime("%H:%M"))

        def guardar() -> bool:
            ok = ejecutar(self.page, lambda: self.servicio.registrar_resultado(
                muestra.id_muestra, txt_bioq.value or "", txt_valores.value or "", texto(txt_conclusion),
                fecha_hora=fecha_hora(fecha, hora, "resultado")),
                f"Resultado de {muestra.codigo} cargado: la muestra pasó a Analizada.")
            if ok:
                self.cargar()
            return ok

        dialogo_formulario(self.page, f"Resultado de {muestra.codigo} · {tipo.nombre}",
                           [txt_bioq, txt_valores, txt_conclusion, ft.Row([fecha.control, hora])], guardar,
                           "Guardar resultado")
