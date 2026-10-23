"""Vista de Mascotas: ABMC, responsable obligatorio e historia clínica."""

from __future__ import annotations

from datetime import date

import flet as ft

from dominio import Especie, Mascota
from servicios import ServicioAtencion, ServicioCatalogos, ServicioClientes, ServicioMascotas
from ui.comun import (
    COLOR_ERROR,
    CampoFecha,
    celda,
    confirmar,
    desplegable,
    dialogo_formulario,
    ejecutar,
    encabezado,
    entero,
    etiqueta_estado,
    fecha_legible,
    numero,
    opciones_desplegable,
    tabla_datos,
    tarjeta,
    texto,
)
from ui.vista_base import Vista

SEXOS = [("M", "Macho"), ("H", "Hembra")]


def edad_legible(dias: int) -> str:
    if dias < 60:
        return f"{dias} días"
    if dias < 730:
        return f"{dias // 30} meses"
    return f"{dias // 365} años"


class VistaMascotas(Vista):
    titulo = "Mascotas"
    subtitulo = "Toda mascota tiene un cliente responsable. Cada alta abre su historia clínica."

    def __init__(self, page: ft.Page) -> None:
        super().__init__(page)
        self.servicio = ServicioMascotas()
        self.clientes = ServicioClientes()
        self.catalogos = ServicioCatalogos()
        self.atencion = ServicioAtencion()
        self._editando: Mascota | None = None
        self._especies: dict[int, str] = {}
        self._responsables: dict[int, str] = {}

    # --- Construcción -------------------------------------------------------------------

    def construir(self) -> ft.Control:
        self.txt_nombre = ft.TextField(label="Nombre *", width=200)
        self.dd_especie = desplegable("Especie *", width=160)
        self.txt_raza = ft.TextField(label="Raza", width=200)
        self.dd_sexo = desplegable("Sexo", SEXOS, width=130)
        self.fecha_nacimiento = CampoFecha(self.page, "Nacimiento *")
        self.txt_peso = ft.TextField(label="Peso (kg)", width=120)
        self.dd_cliente = desplegable("Responsable *", expand=True, filtro=True)
        self.txt_alergias = ft.TextField(label="Alergias", expand=True)
        self.txt_antecedentes = ft.TextField(label="Antecedentes", expand=True)
        self.fila_historia = ft.Row([self.txt_alergias, self.txt_antecedentes])
        self.lbl_formulario = ft.Text("Nueva mascota", weight=ft.FontWeight.BOLD, size=15)
        self.btn_guardar = ft.FilledButton("Agregar", icon=ft.Icons.PETS, on_click=self._guardar)
        self.btn_cancelar = ft.TextButton("Cancelar edición", icon=ft.Icons.CLEAR, visible=False,
                                          on_click=lambda _e: (self._limpiar(), self.actualizar()))

        self.txt_buscar = ft.TextField(label="Buscar por nombre", prefix_icon=ft.Icons.SEARCH, expand=True,
                                       on_change=lambda _e: self.cargar())
        self.dd_filtro_cliente = desplegable("Filtrar por responsable", width=320, filtro=True,
                                             on_select=lambda _e: self.cargar())
        self.lbl_cantidad = ft.Text(color=ft.Colors.GREY_700)
        self.tabla = tabla_datos(["Nombre", "Especie", "Raza", "Sexo", "Edad", "Peso", "Responsable",
                                  "Vacunas", "Acciones"])

        formulario = tarjeta(ft.Column([
            self.lbl_formulario,
            ft.Row([self.txt_nombre, self.dd_especie, self.txt_raza, self.dd_sexo], wrap=True),
            ft.Row([self.fecha_nacimiento.control, self.txt_peso, self.dd_cliente]),
            self.fila_historia,
            ft.Row([self.btn_guardar, self.btn_cancelar]),
        ], spacing=10))
        return ft.Column([
            encabezado(self.titulo, self.subtitulo),
            formulario,
            ft.Row([self.txt_buscar, self.dd_filtro_cliente]),
            self.lbl_cantidad,
            ft.Column([ft.Row([self.tabla], scroll=ft.ScrollMode.AUTO)], scroll=ft.ScrollMode.AUTO, expand=True),
        ], spacing=14, expand=True)

    # --- Datos --------------------------------------------------------------------------

    def al_mostrar(self) -> None:
        self._especies = {e.id_especie: e.nombre for e in self.catalogos.listar(Especie)}
        clientes = self.clientes.listar()
        self._responsables = {c.id_cliente: c.nombre_completo for c in self.clientes.listar(solo_activos=False)}
        self.dd_especie.options = opciones_desplegable(self._especies.items())
        opciones = [(c.id_cliente, f"{c.nombre_completo} (DNI {c.dni})") for c in clientes]
        self.dd_cliente.options = opciones_desplegable(opciones)
        self.dd_filtro_cliente.options = opciones_desplegable([("", "Todos los responsables"), *opciones])
        self.cargar()

    def cargar(self) -> None:
        id_cliente = entero(self.dd_filtro_cliente)
        if id_cliente:
            mascotas = self.servicio.listar_por_cliente(id_cliente)
            busqueda = (texto(self.txt_buscar) or "").lower()
            mascotas = [m for m in mascotas if busqueda in m.nombre.lower()]
        else:
            mascotas = self.servicio.buscar_por_nombre(texto(self.txt_buscar) or "")
        self.tabla.rows = [self._fila(m) for m in mascotas]
        self.lbl_cantidad.value = f"{len(mascotas)} mascota(s)"
        self.actualizar()

    def _fila(self, m: Mascota) -> ft.DataRow:
        pendientes = self.atencion.vacunas_pendientes(m.id_mascota)
        if not pendientes:
            vacunas: ft.Control = ft.Text("Al día", color=ft.Colors.GREEN_700)
        else:
            hay_vencidas = any(p.situacion == "Vencida" for p in pendientes)
            vacunas = etiqueta_estado("Vencida" if hay_vencidas else "Pendiente", f"{len(pendientes)} sin aplicar")
        return ft.DataRow(cells=[
            celda(m.nombre, negrita=True),
            celda(self._especies.get(m.id_especie)),
            celda(m.raza),
            celda(dict(SEXOS).get(m.sexo)),
            celda(edad_legible(m.edad_en_dias())),
            celda(f"{m.peso_kg:g} kg" if m.peso_kg else None),
            celda(self._responsables.get(m.id_cliente)),
            ft.DataCell(vacunas),
            ft.DataCell(ft.Row([
                ft.IconButton(ft.Icons.EDIT_OUTLINED, tooltip="Editar", on_click=lambda _e, x=m: self._editar(x)),
                ft.IconButton(ft.Icons.HISTORY, tooltip="Historia clínica",
                              on_click=lambda _e, x=m: self._historia(x)),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Dar de baja", icon_color=COLOR_ERROR,
                              on_click=lambda _e, x=m: self._baja(x)),
            ], spacing=0)),
        ])

    # --- Acciones -----------------------------------------------------------------------

    def _guardar(self, _e=None) -> None:
        def datos() -> dict:
            return dict(nombre=self.txt_nombre.value or "", id_especie=entero(self.dd_especie),
                        fecha_nacimiento=self.fecha_nacimiento.valor, id_cliente=entero(self.dd_cliente),
                        raza=texto(self.txt_raza), sexo=self.dd_sexo.value or None,
                        peso_kg=numero(self.txt_peso, "peso"))

        if self._editando is None:
            def alta():
                return self.servicio.alta(**datos(), alergias=texto(self.txt_alergias),
                                          antecedentes=texto(self.txt_antecedentes))
            ok = ejecutar(self.page, alta, lambda m: f"{m.nombre} registrada con su historia clínica.")
        else:
            id_mascota = self._editando.id_mascota
            ok = ejecutar(self.page, lambda: self.servicio.modificar(Mascota(**datos(), id_mascota=id_mascota)),
                          "Cambios guardados.")
        if ok:
            self._limpiar()
            self.cargar()
        else:
            self.actualizar()

    def _editar(self, m: Mascota) -> None:
        self._editando = m
        self.txt_nombre.value = m.nombre
        self.dd_especie.value = str(m.id_especie)
        self.txt_raza.value = m.raza or ""
        self.dd_sexo.value = m.sexo
        self.fecha_nacimiento.valor = m.fecha_nacimiento
        self.txt_peso.value = f"{m.peso_kg:g}" if m.peso_kg else ""
        self.dd_cliente.value = str(m.id_cliente)
        self.fila_historia.visible = False  # alergias/antecedentes se editan en la historia clínica
        self.lbl_formulario.value = f"Editando a {m.nombre}"
        self.btn_guardar.content = "Guardar cambios"
        self.btn_guardar.icon = ft.Icons.SAVE
        self.btn_cancelar.visible = True
        self.actualizar()

    def _limpiar(self) -> None:
        self._editando = None
        for campo in (self.txt_nombre, self.txt_raza, self.txt_peso, self.txt_alergias, self.txt_antecedentes):
            campo.value = ""
        for dd in (self.dd_especie, self.dd_sexo, self.dd_cliente):
            dd.value = None
        self.fecha_nacimiento.valor = None
        self.fila_historia.visible = True
        self.lbl_formulario.value = "Nueva mascota"
        self.btn_guardar.content = "Agregar"
        self.btn_guardar.icon = ft.Icons.PETS
        self.btn_cancelar.visible = False

    def _baja(self, m: Mascota) -> None:
        def dar_de_baja() -> None:
            if ejecutar(self.page, lambda: self.servicio.baja(m.id_mascota), f"{m.nombre} fue dada de baja."):
                self.cargar()
            self.actualizar()

        confirmar(self.page, "Dar de baja", f"¿Dar de baja a {m.nombre}? Su historia clínica se conserva.",
                  dar_de_baja, "Dar de baja")

    def _historia(self, m: Mascota) -> None:
        """Diálogo con la historia clínica: alergias/antecedentes editables, atenciones y vacunas."""
        historia = self.servicio.obtener_historia(m.id_mascota)
        txt_alergias = ft.TextField(label="Alergias", value=historia.alergias or "")
        txt_antecedentes = ft.TextField(label="Antecedentes", value=historia.antecedentes or "", multiline=True,
                                        min_lines=2)
        atenciones = tabla_datos(["Fecha", "Motivo", "Diagnóstico", "Peso"])
        atenciones.rows = [ft.DataRow(cells=[celda(fecha_legible(a.fecha_hora)), celda(a.motivo),
                                             celda(a.diagnostico), celda(f"{a.peso_kg:g} kg" if a.peso_kg else None)])
                           for a in reversed(self.atencion.atenciones_de_mascota(m.id_mascota))]
        pendientes = self.atencion.vacunas_pendientes(m.id_mascota)
        vacunas: list[ft.Control] = ([ft.Text("Vacunación obligatoria al día.", color=ft.Colors.GREEN_700)]
                                     if not pendientes else
                                     [ft.Row([etiqueta_estado(p.situacion), ft.Text(str(p))]) for p in pendientes])

        def guardar() -> bool:
            return ejecutar(self.page, lambda: self.servicio.actualizar_historia(
                m.id_mascota, texto(txt_alergias), texto(txt_antecedentes)), "Historia clínica actualizada.")

        dialogo_formulario(self.page, f"Historia clínica de {m.nombre} (abierta el "
                                      f"{fecha_legible(historia.fecha_apertura)})", [
            txt_alergias, txt_antecedentes,
            ft.Text(f"Vacunas obligatorias al {date.today().strftime('%d/%m/%Y')}", weight=ft.FontWeight.BOLD),
            *vacunas,
            ft.Text("Atenciones", weight=ft.FontWeight.BOLD),
            ft.Row([atenciones], scroll=ft.ScrollMode.AUTO) if atenciones.rows else ft.Text("Sin atenciones."),
        ], guardar, ancho=760)
