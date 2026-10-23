"""Vista de Clientes: ABMC con búsqueda, baja lógica y reactivación."""

from __future__ import annotations

import flet as ft

from dominio import Cliente
from servicios import ServicioClientes, ServicioMascotas
from ui.comun import (
    COLOR_ERROR,
    COLOR_OK,
    celda,
    confirmar,
    ejecutar,
    encabezado,
    tabla_datos,
    tarjeta,
    texto,
)
from ui.vista_base import Vista


class VistaClientes(Vista):
    titulo = "Clientes"
    subtitulo = "Alta, modificación, baja lógica y búsqueda de responsables de mascotas."

    def __init__(
        self,
        page: ft.Page,
        servicio: ServicioClientes | None = None,
        servicio_mascotas: ServicioMascotas | None = None,
    ) -> None:
        super().__init__(page)
        self.servicio = servicio or ServicioClientes()
        self.servicio_mascotas = servicio_mascotas or ServicioMascotas()
        self._editando: Cliente | None = None

    # --- Construcción -------------------------------------------------------------------

    def construir(self) -> ft.Control:
        self.txt_dni = ft.TextField(label="DNI *", width=160, input_filter=ft.NumbersOnlyInputFilter())
        self.txt_nombre = ft.TextField(label="Nombre *", expand=True)
        self.txt_apellido = ft.TextField(label="Apellido *", expand=True)
        self.txt_telefono = ft.TextField(label="Teléfono", width=180)
        self.txt_email = ft.TextField(label="Email", expand=True)
        self.txt_direccion = ft.TextField(label="Dirección", expand=True)
        self.lbl_formulario = ft.Text("Nuevo cliente", weight=ft.FontWeight.BOLD, size=15)
        self.btn_guardar = ft.FilledButton("Agregar", icon=ft.Icons.PERSON_ADD, on_click=self._guardar)
        self.btn_cancelar = ft.TextButton("Cancelar edición", icon=ft.Icons.CLEAR, on_click=self._cancelar,
                                          visible=False)

        self.txt_buscar = ft.TextField(label="Buscar por DNI, nombre o apellido", prefix_icon=ft.Icons.SEARCH,
                                       expand=True, on_change=lambda _e: self.cargar())
        self.chk_inactivos = ft.Checkbox(label="Mostrar dados de baja", on_change=lambda _e: self.cargar())
        self.lbl_cantidad = ft.Text(color=ft.Colors.GREY_700)
        self.tabla = tabla_datos(["DNI", "Apellido y nombre", "Teléfono", "Email", "Dirección", "Mascotas",
                                  "Estado", "Acciones"], numericas=(5,))

        formulario = tarjeta(ft.Column([
            self.lbl_formulario,
            ft.Row([self.txt_dni, self.txt_nombre, self.txt_apellido]),
            ft.Row([self.txt_telefono, self.txt_email, self.txt_direccion]),
            ft.Row([self.btn_guardar, self.btn_cancelar]),
        ], spacing=10))

        return ft.Column([
            encabezado(self.titulo, self.subtitulo),
            formulario,
            ft.Row([self.txt_buscar, self.chk_inactivos]),
            self.lbl_cantidad,
            ft.Column([ft.Row([self.tabla], scroll=ft.ScrollMode.AUTO)], scroll=ft.ScrollMode.AUTO, expand=True),
        ], spacing=14, expand=True)

    # --- Datos --------------------------------------------------------------------------

    def al_mostrar(self) -> None:
        self.cargar()

    def cargar(self) -> None:
        busqueda = texto(self.txt_buscar)
        solo_activos = not self.chk_inactivos.value
        clientes = (self.servicio.buscar(busqueda, solo_activos) if busqueda
                    else self.servicio.listar(solo_activos))
        self.tabla.rows = [self._fila(c) for c in clientes]
        self.lbl_cantidad.value = f"{len(clientes)} cliente(s)"
        self.actualizar()

    def _fila(self, cliente: Cliente) -> ft.DataRow:
        mascotas = self.servicio_mascotas.listar_por_cliente(cliente.id_cliente)
        if cliente.activo:
            accion_estado = ft.IconButton(ft.Icons.PERSON_OFF_OUTLINED, tooltip="Dar de baja",
                                          icon_color=COLOR_ERROR, on_click=lambda _e, c=cliente: self._baja(c))
        else:
            accion_estado = ft.IconButton(ft.Icons.RESTORE, tooltip="Reactivar", icon_color=COLOR_OK,
                                          on_click=lambda _e, c=cliente: self._reactivar(c))
        return ft.DataRow(cells=[
            celda(cliente.dni),
            celda(cliente.nombre_completo, negrita=True),
            celda(cliente.telefono),
            celda(cliente.email),
            celda(cliente.direccion),
            celda(", ".join(m.nombre for m in mascotas) if mascotas else "-"),
            celda("Activo" if cliente.activo else "Baja", color=COLOR_OK if cliente.activo else COLOR_ERROR),
            ft.DataCell(ft.Row([
                ft.IconButton(ft.Icons.EDIT_OUTLINED, tooltip="Editar",
                              on_click=lambda _e, c=cliente: self._editar(c)),
                accion_estado,
            ], spacing=0)),
        ])

    # --- Acciones -----------------------------------------------------------------------

    def _guardar(self, _e=None) -> None:
        datos = dict(dni=self.txt_dni.value or "", nombre=self.txt_nombre.value or "",
                     apellido=self.txt_apellido.value or "", telefono=texto(self.txt_telefono),
                     email=texto(self.txt_email), direccion=texto(self.txt_direccion))
        if self._editando is None:
            ok = ejecutar(self.page, lambda: self.servicio.alta(**datos),
                          lambda c: f"Cliente {c.nombre_completo} registrado.")
        else:
            editado = self._editando

            def modificar() -> None:
                self.servicio.modificar(Cliente(**datos, activo=editado.activo, id_cliente=editado.id_cliente))

            ok = ejecutar(self.page, modificar, "Cambios guardados.")
        if ok:
            self._limpiar_formulario()
            self.cargar()
        else:
            self.actualizar()

    def _editar(self, cliente: Cliente) -> None:
        self._editando = cliente
        self.txt_dni.value = cliente.dni
        self.txt_nombre.value = cliente.nombre
        self.txt_apellido.value = cliente.apellido
        self.txt_telefono.value = cliente.telefono or ""
        self.txt_email.value = cliente.email or ""
        self.txt_direccion.value = cliente.direccion or ""
        self.lbl_formulario.value = f"Editando a {cliente.nombre_completo}"
        self.btn_guardar.content = "Guardar cambios"
        self.btn_guardar.icon = ft.Icons.SAVE
        self.btn_cancelar.visible = True
        self.actualizar()

    def _cancelar(self, _e=None) -> None:
        self._limpiar_formulario()
        self.actualizar()

    def _baja(self, cliente: Cliente) -> None:
        def dar_de_baja() -> None:
            if ejecutar(self.page, lambda: self.servicio.baja(cliente.id_cliente),
                        f"{cliente.nombre_completo} fue dado/a de baja."):
                self.cargar()
            else:
                self.actualizar()

        confirmar(self.page, "Dar de baja",
                  f"¿Dar de baja a {cliente.nombre_completo} (DNI {cliente.dni})? Podrá reactivarse luego.",
                  dar_de_baja, "Dar de baja")

    def _reactivar(self, cliente: Cliente) -> None:
        if ejecutar(self.page, lambda: self.servicio.reactivar(cliente.id_cliente),
                    f"{cliente.nombre_completo} fue reactivado/a."):
            self.cargar()

    def _limpiar_formulario(self) -> None:
        self._editando = None
        for campo in (self.txt_dni, self.txt_nombre, self.txt_apellido, self.txt_telefono,
                      self.txt_email, self.txt_direccion):
            campo.value = ""
        self.lbl_formulario.value = "Nuevo cliente"
        self.btn_guardar.content = "Agregar"
        self.btn_guardar.icon = ft.Icons.PERSON_ADD
        self.btn_cancelar.visible = False
