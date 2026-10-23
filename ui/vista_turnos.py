"""Vista de Turnos: agenda diaria por veterinario, reserva sin superposición, reprogramación y estados."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import flet as ft

from dominio import Turno
from servicios import ServicioClientes, ServicioMascotas, ServicioTurnos, ServicioVeterinarios
from ui.comun import (
    COLOR_ERROR,
    CampoFecha,
    campo_hora,
    celda,
    confirmar,
    desplegable,
    dialogo_formulario,
    ejecutar,
    encabezado,
    entero,
    etiqueta_estado,
    fecha_hora,
    opciones_desplegable,
    tabla_datos,
    tarjeta,
)
from ui.vista_base import Vista

DURACIONES = [(15, "15 min"), (30, "30 min"), (45, "45 min"), (60, "1 hora")]


def calcular_fin(inicio: str, minutos: int) -> str:
    return (datetime.strptime(inicio, "%Y-%m-%d %H:%M") + timedelta(minutes=minutos)).strftime("%Y-%m-%d %H:%M")


class VistaTurnos(Vista):
    titulo = "Turnos"
    subtitulo = "Un veterinario no puede tener dos turnos superpuestos (los cancelados no cuentan)."

    def __init__(self, page: ft.Page) -> None:
        super().__init__(page)
        self.servicio = ServicioTurnos()
        self.veterinarios = ServicioVeterinarios()
        self.mascotas = ServicioMascotas()
        self.clientes = ServicioClientes()
        self._nombres_vet: dict[int, str] = {}
        self._nombres_mascota: dict[int, str] = {}

    # --- Construcción -------------------------------------------------------------------

    def construir(self) -> ft.Control:
        hoy = date.today().isoformat()
        # Formulario de reserva
        self.dd_vet = desplegable("Veterinario *", width=260)
        self.dd_mascota = desplegable("Mascota *", width=300, filtro=True)
        self.fecha_turno = CampoFecha(self.page, "Fecha *", hoy)
        self.txt_hora = campo_hora("Inicio *", "09:00")
        self.dd_duracion = desplegable("Duración", DURACIONES, width=130)
        self.dd_duracion.value = "30"
        formulario = tarjeta(ft.Column([
            ft.Row([self.dd_vet, self.dd_mascota], wrap=True),
            ft.Row([self.fecha_turno.control, self.txt_hora, self.dd_duracion,
                    ft.FilledButton("Reservar", icon=ft.Icons.EVENT, on_click=self._reservar)], wrap=True),
        ], spacing=10), "Reservar turno")

        # Agenda
        self.fecha_agenda = CampoFecha(self.page, "Día", hoy)
        self.fecha_agenda.selector.on_change = self._al_cambiar_dia
        self.dd_filtro_vet = desplegable("Veterinario", width=260, on_select=lambda _e: self.cargar())
        self.lbl_resumen = ft.Text(color=ft.Colors.GREY_700)
        self.tabla = tabla_datos(["Inicio", "Fin", "Veterinario", "Mascota", "Estado", "Acciones"])
        barra = ft.Row([
            ft.IconButton(ft.Icons.CHEVRON_LEFT, tooltip="Día anterior", on_click=lambda _e: self._mover_dia(-1)),
            self.fecha_agenda.control,
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Día siguiente", on_click=lambda _e: self._mover_dia(1)),
            ft.TextButton("Hoy", icon=ft.Icons.TODAY, on_click=lambda _e: self._ir_a(date.today())),
            self.dd_filtro_vet,
        ], wrap=True)

        return ft.Column([
            encabezado(self.titulo, self.subtitulo),
            formulario,
            ft.Text("Agenda del día", weight=ft.FontWeight.BOLD, size=15),
            barra,
            self.lbl_resumen,
            ft.Column([ft.Row([self.tabla], scroll=ft.ScrollMode.AUTO)], scroll=ft.ScrollMode.AUTO, expand=True),
        ], spacing=12, expand=True)

    # --- Datos --------------------------------------------------------------------------

    def al_mostrar(self) -> None:
        vets = self.veterinarios.listar()
        self._nombres_vet = {v.id_veterinario: v.nombre_completo for v in self.veterinarios.listar(False)}
        self.dd_vet.options = opciones_desplegable((v.id_veterinario, f"{v.nombre_completo} - {v.especialidad or ''}")
                                                   for v in vets)
        self.dd_filtro_vet.options = opciones_desplegable([("", "Todos"),
                                                           *((v.id_veterinario, v.nombre_completo) for v in vets)])
        responsables = {c.id_cliente: c.apellido for c in self.clientes.listar(solo_activos=False)}
        mascotas = self.mascotas.buscar_por_nombre("")
        self._nombres_mascota = {m.id_mascota: f"{m.nombre} ({responsables.get(m.id_cliente, '')})" for m in mascotas}
        self.dd_mascota.options = opciones_desplegable(sorted(self._nombres_mascota.items(), key=lambda x: x[1]))
        self.cargar()

    def cargar(self) -> None:
        turnos = self.servicio.turnos_del_dia(self.fecha_agenda.valor or date.today().isoformat(),
                                              entero(self.dd_filtro_vet))
        self.tabla.rows = [self._fila(t) for t in turnos]
        activos = sum(t.estado == "Reservado" for t in turnos)
        self.lbl_resumen.value = f"{len(turnos)} turno(s) · {activos} por atender"
        self.actualizar()

    def _fila(self, t: Turno) -> ft.DataRow:
        acciones: list[ft.Control] = []
        if t.estado == "Reservado":
            acciones = [
                ft.IconButton(ft.Icons.EDIT_CALENDAR, tooltip="Reprogramar", on_click=lambda _e, x=t: self._reprogramar(x)),
                ft.IconButton(ft.Icons.PERSON_OFF, tooltip="Marcar ausente", icon_color=ft.Colors.ORANGE_700,
                              on_click=lambda _e, x=t: self._cambiar(x, "ausente")),
                ft.IconButton(ft.Icons.EVENT_BUSY, tooltip="Cancelar", icon_color=COLOR_ERROR,
                              on_click=lambda _e, x=t: self._cambiar(x, "cancelar")),
            ]
        return ft.DataRow(cells=[
            celda(t.fecha_hora_inicio[-5:], negrita=True),
            celda(t.fecha_hora_fin[-5:]),
            celda(self._nombres_vet.get(t.id_veterinario)),
            celda(self._nombres_mascota.get(t.id_mascota, f"#{t.id_mascota}")),
            ft.DataCell(etiqueta_estado(t.estado)),
            ft.DataCell(ft.Row(acciones, spacing=0)),
        ])

    # --- Navegación por días -----------------------------------------------------------------

    def _ir_a(self, dia: date) -> None:
        self.fecha_agenda.valor = dia
        self.cargar()

    def _mover_dia(self, delta: int) -> None:
        actual = date.fromisoformat(self.fecha_agenda.valor or date.today().isoformat())
        self._ir_a(actual + timedelta(days=delta))

    def _al_cambiar_dia(self, e) -> None:
        if e.control.value:
            self._ir_a(e.control.value.date())

    # --- Acciones -----------------------------------------------------------------------

    def _reservar(self, _e=None) -> None:
        def reservar() -> Turno:
            if entero(self.dd_vet) is None or entero(self.dd_mascota) is None:
                raise ValueError("Elegí el veterinario y la mascota.")
            inicio = fecha_hora(self.fecha_turno, self.txt_hora, "inicio del turno")
            return self.servicio.reservar(entero(self.dd_vet), entero(self.dd_mascota), inicio,
                                          calcular_fin(inicio, entero(self.dd_duracion) or 30))

        if ejecutar(self.page, reservar, lambda t: f"Turno reservado: {t.fecha_hora_inicio} a {t.fecha_hora_fin[-5:]}."):
            self._ir_a(date.fromisoformat(self.fecha_turno.valor))
        else:
            self.actualizar()

    def _cambiar(self, t: Turno, accion: str) -> None:
        nombre = self._nombres_mascota.get(t.id_mascota, "la mascota")
        if accion == "cancelar":
            metodo, titulo, mensaje = self.servicio.cancelar, "Cancelar turno", "Turno cancelado."
        else:
            metodo, titulo, mensaje = self.servicio.marcar_ausente, "Marcar ausente", "Turno marcado como ausente."

        def aplicar() -> None:
            ejecutar(self.page, lambda: metodo(t.id_turno), mensaje)
            self.cargar()

        confirmar(self.page, titulo, f"{titulo}: {nombre}, {t.fecha_hora_inicio}?", aplicar, titulo)

    def _reprogramar(self, t: Turno) -> None:
        nueva_fecha = CampoFecha(self.page, "Nueva fecha", t.fecha_hora_inicio[:10])
        nueva_hora = campo_hora("Inicio", t.fecha_hora_inicio[-5:])
        minutos = int((datetime.strptime(t.fecha_hora_fin, "%Y-%m-%d %H:%M")
                       - datetime.strptime(t.fecha_hora_inicio, "%Y-%m-%d %H:%M")).total_seconds() // 60)
        duracion = desplegable("Duración", DURACIONES, width=130)
        duracion.value = str(minutos) if minutos in dict(DURACIONES) else "30"

        def guardar() -> bool:
            def reprogramar() -> Turno:
                inicio = fecha_hora(nueva_fecha, nueva_hora, "nuevo inicio")
                return self.servicio.reprogramar(t.id_turno, inicio, calcular_fin(inicio, entero(duracion) or 30))

            ok = ejecutar(self.page, reprogramar, "Turno reprogramado.")
            if ok:
                self.cargar()
            return ok

        dialogo_formulario(self.page, f"Reprogramar turno de {self._nombres_mascota.get(t.id_mascota, '')}",
                           [nueva_fecha.control, ft.Row([nueva_hora, duracion])], guardar, "Reprogramar")
