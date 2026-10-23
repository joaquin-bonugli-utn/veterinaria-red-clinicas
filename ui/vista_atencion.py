"""Vista de Atención: registro de la atención con tratamientos y vacunas, y control de vacunas pendientes."""

from __future__ import annotations

from datetime import date, datetime

import flet as ft

from dominio import Clinica, Especie, TipoAtencion
from servicios import (
    ServicioAtencion,
    ServicioCatalogos,
    ServicioClientes,
    ServicioMascotas,
    ServicioTurnos,
    ServicioVeterinarios,
    TratamientoIndicado,
    VacunaAAplicar,
)
from ui.comun import (
    COLOR_ERROR,
    CampoFecha,
    campo_hora,
    celda,
    desplegable,
    dialogo_info,
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

SIN_TURNO = ""


class VistaAtencion(Vista):
    titulo = "Atención"
    subtitulo = ("Registrá la atención (con o sin turno), los tratamientos y las vacunas aplicadas. "
                 "Al guardar se informan las vacunas obligatorias pendientes o vencidas.")

    def __init__(self, page: ft.Page) -> None:
        super().__init__(page)
        self.servicio = ServicioAtencion()
        self.mascotas = ServicioMascotas()
        self.clientes = ServicioClientes()
        self.turnos = ServicioTurnos()
        self.veterinarios = ServicioVeterinarios()
        self.catalogos = ServicioCatalogos()
        self._tratamientos: list[TratamientoIndicado] = []
        self._vacunas: list[VacunaAAplicar] = []
        self._nombres_vacuna: dict[int, str] = {}
        self._mascotas: dict = {}
        self._turnos: dict = {}

    # --- Construcción -------------------------------------------------------------------

    def construir(self) -> ft.Control:
        self.dd_mascota = desplegable("Mascota *", width=320, filtro=True, on_select=self._al_elegir_mascota)
        self.dd_turno = desplegable("Turno", width=280, on_select=self._al_elegir_turno)
        self.dd_vet = desplegable("Veterinario *", width=260)
        self.dd_tipo = desplegable("Tipo de atención *", width=200)
        self.dd_clinica = desplegable("Clínica", width=240)
        self.fecha = CampoFecha(self.page, "Fecha *", date.today().isoformat())
        self.txt_hora = campo_hora("Hora *", datetime.now().strftime("%H:%M"))
        self.txt_motivo = ft.TextField(label="Motivo *", expand=True)
        self.txt_diagnostico = ft.TextField(label="Diagnóstico", expand=True)
        self.txt_peso = ft.TextField(label="Peso (kg)", width=120)
        self.panel_pendientes = ft.Column(spacing=6)

        # Tratamientos
        self.txt_medicamento = ft.TextField(label="Medicamento", width=220)
        self.txt_dosis = ft.TextField(label="Dosis", width=120)
        self.txt_frecuencia = ft.TextField(label="Frecuencia", width=140, hint_text="cada 12 h")
        self.fecha_fin_trat = CampoFecha(self.page, "Hasta", width=150)
        self.tabla_trat = tabla_datos(["Medicamento", "Dosis", "Frecuencia", "Hasta", ""])
        # Vacunas
        self.dd_vacuna = desplegable("Vacuna", width=260)
        self.txt_lote = ft.TextField(label="Lote", width=140)
        self.tabla_vac = tabla_datos(["Vacuna", "Lote", ""])

        datos = tarjeta(ft.Column([
            ft.Row([self.dd_mascota, self.dd_turno, self.dd_vet], wrap=True),
            ft.Row([self.dd_tipo, self.dd_clinica, self.fecha.control, self.txt_hora, self.txt_peso], wrap=True),
            ft.Row([self.txt_motivo]),
            ft.Row([self.txt_diagnostico]),
        ], spacing=10), "Datos de la atención")
        tratamientos = tarjeta(ft.Column([
            ft.Row([self.txt_medicamento, self.txt_dosis, self.txt_frecuencia, self.fecha_fin_trat.control,
                    ft.OutlinedButton("Agregar", icon=ft.Icons.MEDICATION, on_click=self._agregar_tratamiento)],
                   wrap=True),
            self.tabla_trat,
        ]), "Tratamientos")
        vacunas = tarjeta(ft.Column([
            self.panel_pendientes,
            ft.Row([self.dd_vacuna, self.txt_lote,
                    ft.OutlinedButton("Agregar", icon=ft.Icons.VACCINES, on_click=self._agregar_vacuna)], wrap=True),
            self.tabla_vac,
        ]), "Vacunas a aplicar")
        self.tabla_historial = tabla_datos(["Fecha", "Motivo", "Diagnóstico", "Tratamientos", "Vacunas"])

        return ft.Column([
            encabezado(self.titulo, self.subtitulo),
            datos, tratamientos, vacunas,
            ft.Row([ft.FilledButton("Registrar atención", icon=ft.Icons.SAVE, on_click=self._registrar),
                    ft.TextButton("Limpiar", icon=ft.Icons.CLEAR, on_click=lambda _e: self._limpiar(True))]),
            ft.Text("Atenciones anteriores de la mascota", weight=ft.FontWeight.BOLD, size=15),
            ft.Row([self.tabla_historial], scroll=ft.ScrollMode.AUTO),
        ], spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)

    # --- Datos --------------------------------------------------------------------------

    def al_mostrar(self) -> None:
        responsables = {c.id_cliente: c.nombre_completo for c in self.clientes.listar(solo_activos=False)}
        self._mascotas = {m.id_mascota: m for m in self.mascotas.buscar_por_nombre("")}
        self.dd_mascota.options = opciones_desplegable(sorted(
            ((m.id_mascota, f"{m.nombre} - {responsables.get(m.id_cliente, '')}") for m in self._mascotas.values()),
            key=lambda x: x[1]))
        self._vets = {v.id_veterinario: v for v in self.veterinarios.listar()}
        self.dd_vet.options = opciones_desplegable((v.id_veterinario, v.nombre_completo) for v in self._vets.values())
        self.dd_tipo.options = opciones_desplegable((t.id_tipo_atencion, t.nombre)
                                                    for t in self.catalogos.listar(TipoAtencion))
        self.dd_clinica.options = opciones_desplegable([("", "La del veterinario"),
                                                        *((c.id_clinica, c.nombre) for c in self.catalogos.listar(Clinica))])
        self.actualizar()

    def _al_elegir_mascota(self, _e=None) -> None:
        mascota = self._mascotas.get(entero(self.dd_mascota))
        self._vacunas.clear()
        self._refrescar_listas()
        if mascota is None:
            return
        # Turnos reservados de la mascota (de hoy en adelante y los pasados sin atender)
        self._turnos = {t.id_turno: t for t in self.turnos.turnos_de_mascota(mascota.id_mascota)
                        if t.estado == "Reservado"}
        self.dd_turno.options = opciones_desplegable([
            (SIN_TURNO, "Sin turno (urgencia)"),
            *((t.id_turno, f"{fecha_legible(t.fecha_hora_inicio)} - {self._nombre_vet(t.id_veterinario)}")
              for t in self._turnos.values()),
        ])
        self.dd_turno.value = SIN_TURNO
        # Vacunas de la especie y pendientes a hoy
        vacunas = self.catalogos.vacunas_de_especie(mascota.id_especie)
        self._nombres_vacuna = {v.id_vacuna: v.nombre for v in vacunas}
        self.dd_vacuna.options = opciones_desplegable(
            (v.id_vacuna, f"{v.nombre}{' (obligatoria)' if v.obligatoria else ''}") for v in vacunas)
        self._mostrar_pendientes(mascota.id_mascota)
        self._cargar_historial(mascota.id_mascota)
        self.actualizar()

    def _al_elegir_turno(self, _e=None) -> None:
        turno = self._turnos.get(entero(self.dd_turno))
        if turno:
            self.dd_vet.value = str(turno.id_veterinario)
            self.fecha.valor = turno.fecha_hora_inicio[:10]
            self.txt_hora.value = turno.fecha_hora_inicio[-5:]
            self.dd_tipo.value = self.dd_tipo.value or self._clave_tipo("Consulta")
        else:
            self.dd_tipo.value = self._clave_tipo("Urgencia")
        self.actualizar()

    def _nombre_vet(self, id_veterinario: int) -> str:
        vet = self._vets.get(id_veterinario)
        return vet.nombre_completo if vet else f"Vet. #{id_veterinario}"

    def _clave_tipo(self, nombre: str) -> str | None:
        return next((o.key for o in self.dd_tipo.options if o.text == nombre), None)

    def _mostrar_pendientes(self, id_mascota: int) -> None:
        pendientes = self.servicio.vacunas_pendientes(id_mascota, self.fecha.valor)
        especie = self.catalogos.obtener(self._mascotas[id_mascota].id_especie, Especie).nombre
        if not pendientes:
            self.panel_pendientes.controls = [ft.Text(f"Vacunación obligatoria al día ({especie}).",
                                                      color=ft.Colors.GREEN_700)]
        else:
            self.panel_pendientes.controls = [ft.Text("Vacunas obligatorias que corresponde aplicar:",
                                                      weight=ft.FontWeight.W_500)] + [
                ft.Row([etiqueta_estado(p.situacion), ft.Text(str(p))]) for p in pendientes]

    def _cargar_historial(self, id_mascota: int) -> None:
        filas = []
        for a in reversed(self.servicio.atenciones_de_mascota(id_mascota)):
            tratamientos = ", ".join(t.medicamento for t in self.servicio.tratamientos_de(a.id_atencion))
            vacunas = len(self.servicio.vacunas_aplicadas_de(a.id_atencion))
            filas.append(ft.DataRow(cells=[celda(fecha_legible(a.fecha_hora)), celda(a.motivo), celda(a.diagnostico),
                                           celda(tratamientos), celda(vacunas or None)]))
        self.tabla_historial.rows = filas

    # --- Listas de tratamientos y vacunas ---------------------------------------------------

    def _agregar_tratamiento(self, _e=None) -> None:
        if not texto(self.txt_medicamento) or not texto(self.txt_dosis):
            mostrar_mensaje(self.page, "Indicá al menos el medicamento y la dosis.", error=True)
            return
        self._tratamientos.append(TratamientoIndicado(texto(self.txt_medicamento), texto(self.txt_dosis),
                                                      texto(self.txt_frecuencia), self.fecha_fin_trat.valor))
        for campo in (self.txt_medicamento, self.txt_dosis, self.txt_frecuencia):
            campo.value = ""
        self.fecha_fin_trat.valor = None
        self._refrescar_listas()

    def _agregar_vacuna(self, _e=None) -> None:
        if entero(self.dd_vacuna) is None or not texto(self.txt_lote):
            mostrar_mensaje(self.page, "Elegí la vacuna e indicá el lote.", error=True)
            return
        self._vacunas.append(VacunaAAplicar(entero(self.dd_vacuna), texto(self.txt_lote)))
        self.txt_lote.value = ""
        self._refrescar_listas()

    def _refrescar_listas(self) -> None:
        def quitar(lista: list, indice: int) -> None:
            lista.pop(indice)
            self._refrescar_listas()

        self.tabla_trat.rows = [ft.DataRow(cells=[
            celda(t.medicamento), celda(t.dosis), celda(t.frecuencia), celda(fecha_legible(t.fecha_fin)),
            ft.DataCell(ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=COLOR_ERROR, tooltip="Quitar",
                                      on_click=lambda _e, i=i: quitar(self._tratamientos, i))),
        ]) for i, t in enumerate(self._tratamientos)]
        self.tabla_vac.rows = [ft.DataRow(cells=[
            celda(self._nombres_vacuna.get(v.id_vacuna)), celda(v.lote),
            ft.DataCell(ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=COLOR_ERROR, tooltip="Quitar",
                                      on_click=lambda _e, i=i: quitar(self._vacunas, i))),
        ]) for i, v in enumerate(self._vacunas)]
        self.actualizar()

    # --- Registrar ----------------------------------------------------------------------

    def _registrar(self, _e=None) -> None:
        resultado = {}

        def registrar():
            if entero(self.dd_mascota) is None or entero(self.dd_vet) is None or entero(self.dd_tipo) is None:
                raise ValueError("Elegí la mascota, el veterinario y el tipo de atención.")
            resultado["r"] = self.servicio.registrar(
                entero(self.dd_mascota), entero(self.dd_vet), entero(self.dd_tipo),
                fecha_hora(self.fecha, self.txt_hora), self.txt_motivo.value or "",
                id_clinica=entero(self.dd_clinica), id_turno=entero(self.dd_turno),
                diagnostico=texto(self.txt_diagnostico), peso_kg=numero(self.txt_peso, "peso"),
                tratamientos=list(self._tratamientos), vacunas=list(self._vacunas),
            )

        if not ejecutar(self.page, registrar, "Atención registrada."):
            self.actualizar()
            return
        r = resultado["r"]
        id_mascota = entero(self.dd_mascota)
        self._mostrar_resumen(r)
        self._limpiar(False)
        self._al_elegir_mascota()
        self.dd_mascota.value = str(id_mascota)
        self.actualizar()

    def _mostrar_resumen(self, r) -> None:
        lineas: list[ft.Control] = [
            ft.Text(f"Atención N° {r.atencion.id_atencion} - {fecha_legible(r.atencion.fecha_hora)}"),
            ft.Text(f"Tratamientos: {len(r.tratamientos)} · Vacunas aplicadas: {len(r.aplicaciones)}"),
        ]
        for a in r.aplicaciones:
            proxima = f" · próxima dosis {fecha_legible(a.fecha_proxima_dosis)}" if a.fecha_proxima_dosis else ""
            lineas.append(ft.Text(f"  {self._nombres_vacuna.get(a.id_vacuna)} (lote {a.lote}){proxima}"))
        lineas.append(ft.Divider())
        if r.vacunas_pendientes:
            lineas.append(ft.Text("Vacunas obligatorias pendientes o vencidas:", weight=ft.FontWeight.BOLD,
                                  color=ft.Colors.ORANGE_800))
            lineas += [ft.Row([etiqueta_estado(p.situacion), ft.Text(str(p))]) for p in r.vacunas_pendientes]
        else:
            lineas.append(ft.Text("La mascota tiene la vacunación obligatoria al día.", color=ft.Colors.GREEN_700))
        dialogo_info(self.page, "Atención registrada", ft.Column(lineas, tight=True, spacing=6), ancho=520)

    def _limpiar(self, todo: bool) -> None:
        for campo in (self.txt_motivo, self.txt_diagnostico, self.txt_peso, self.txt_medicamento, self.txt_dosis,
                      self.txt_frecuencia, self.txt_lote):
            campo.value = ""
        self._tratamientos.clear()
        self._vacunas.clear()
        self.dd_turno.value = SIN_TURNO
        if todo:
            for dd in (self.dd_mascota, self.dd_vet, self.dd_tipo, self.dd_turno):
                dd.value = None
            self.dd_turno.options = []
            self.panel_pendientes.controls = []
            self.tabla_historial.rows = []
        self._refrescar_listas()
