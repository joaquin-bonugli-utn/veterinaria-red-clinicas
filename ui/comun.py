"""Componentes y utilidades compartidas por las vistas Flet.

La UI solo llama a servicios: acá se centraliza cómo se ejecuta una acción y
cómo se muestran sus errores (ReglaNegocioError / ValueError → SnackBar rojo).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any

import flet as ft

from dominio.excepciones import ReglaNegocioError

COLOR_PRIMARIO = ft.Colors.BLUE_900
COLOR_OK = ft.Colors.GREEN_700
COLOR_ERROR = ft.Colors.RED_700
COLOR_FONDO_TARJETA = ft.Colors.BLUE_GREY_50

# Color de cada estado (turnos, muestras, remitos, órdenes) para las etiquetas.
COLORES_ESTADO = {
    "Reservado": ft.Colors.BLUE_700, "Atendido": ft.Colors.GREEN_700, "Cancelado": ft.Colors.GREY_600,
    "Ausente": ft.Colors.ORANGE_700,
    "Extraída": ft.Colors.BLUE_GREY_600, "Empaquetada": ft.Colors.INDIGO_500, "En tránsito": ft.Colors.AMBER_800,
    "Recibida": ft.Colors.TEAL_600, "Analizada": ft.Colors.GREEN_700, "Rechazada": ft.Colors.RED_700,
    "Emitido": ft.Colors.BLUE_GREY_600, "Recibido": ft.Colors.GREEN_700, "Rechazado": ft.Colors.RED_700,
    "Emitida": ft.Colors.BLUE_GREY_600, "En proceso": ft.Colors.AMBER_800, "Finalizada": ft.Colors.GREEN_700,
    "Anulada": ft.Colors.GREY_600, "Pendiente": ft.Colors.ORANGE_700, "Vencida": ft.Colors.RED_700,
    "Urgente": ft.Colors.RED_700, "Disponible": ft.Colors.GREEN_700, "En uso": ft.Colors.AMBER_800,
    "Colocado": ft.Colors.BLUE_GREY_600, "Intacto": ft.Colors.GREEN_700, "Roto": ft.Colors.RED_700,
}


# --- Mensajes ---------------------------------------------------------------------------

def mostrar_mensaje(page: ft.Page, texto: str, error: bool = False) -> None:
    """Muestra un SnackBar verde (éxito) o rojo (error)."""
    page.show_dialog(ft.SnackBar(
        ft.Text(texto, color=ft.Colors.WHITE),
        bgcolor=COLOR_ERROR if error else COLOR_OK,
        show_close_icon=True,
    ))


def ejecutar(
    page: ft.Page,
    accion: Callable[[], Any],
    exito: str | Callable[[Any], str] | None = None,
) -> bool:
    """Ejecuta una acción de servicio y muestra el resultado en un SnackBar.

    Devuelve True si la acción terminó bien. Los errores de negocio y de
    validación muestran su mensaje tal cual; cualquier otro error, un aviso genérico.
    """
    try:
        resultado = accion()
    except (ReglaNegocioError, ValueError) as error:
        mostrar_mensaje(page, str(error), error=True)
        return False
    except Exception as error:  # noqa: BLE001 - la UI nunca debe caerse por un error inesperado
        mostrar_mensaje(page, f"Error inesperado: {error}", error=True)
        return False
    if exito:
        mostrar_mensaje(page, exito(resultado) if callable(exito) else exito)
    return True


def cerrar_dialogo(page: ft.Page, dialogo: ft.DialogControl) -> None:
    """Cierra ESE diálogo. (page.pop_dialog() cerraría el último abierto, que puede ser un SnackBar.)"""
    dialogo.open = False
    page.update()


def confirmar(page: ft.Page, titulo: str, mensaje: str, al_confirmar: Callable[[], None],
              texto_boton: str = "Confirmar") -> None:
    """Diálogo modal de confirmación."""
    def aceptar(_e) -> None:
        cerrar_dialogo(page, dialogo)
        al_confirmar()

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text(titulo),
        content=ft.Text(mensaje),
        actions=[ft.TextButton("Cancelar", on_click=lambda _e: cerrar_dialogo(page, dialogo)),
                 ft.FilledButton(texto_boton, on_click=aceptar)],
    )
    page.show_dialog(dialogo)


# --- Controles reutilizables ----------------------------------------------------------------

def encabezado(titulo: str, subtitulo: str = "") -> ft.Control:
    controles: list[ft.Control] = [ft.Text(titulo, size=24, weight=ft.FontWeight.BOLD, color=COLOR_PRIMARIO)]
    if subtitulo:
        controles.append(ft.Text(subtitulo, size=13, color=ft.Colors.GREY_700))
    return ft.Column(controles, spacing=2)


def tarjeta(contenido: ft.Control, titulo: str | None = None) -> ft.Container:
    """Recuadro con fondo suave para agrupar un formulario."""
    if titulo:
        contenido = ft.Column([ft.Text(titulo, weight=ft.FontWeight.BOLD, size=15), contenido], spacing=10)
    return ft.Container(contenido, padding=16, border_radius=10, bgcolor=COLOR_FONDO_TARJETA)


def tabla_datos(columnas: list[str], numericas: tuple[int, ...] = ()) -> ft.DataTable:
    return ft.DataTable(
        columns=[ft.DataColumn(ft.Text(c, weight=ft.FontWeight.BOLD), numeric=i in numericas)
                 for i, c in enumerate(columnas)],
        heading_row_color=ft.Colors.BLUE_GREY_100,
        column_spacing=24,
        data_row_max_height=56,
    )


def celda(texto: Any, color: str | None = None, negrita: bool = False) -> ft.DataCell:
    return ft.DataCell(ft.Text("-" if texto in (None, "") else str(texto), color=color,
                               weight=ft.FontWeight.BOLD if negrita else None))


def texto(campo: ft.TextField) -> str | None:
    """Valor de un TextField sin espacios; None si quedó vacío."""
    valor = (campo.value or "").strip()
    return valor or None


def numero(campo: ft.TextField, nombre: str) -> float | None:
    """Valor numérico de un TextField (acepta coma decimal); None si está vacío."""
    valor = texto(campo)
    if valor is None:
        return None
    try:
        return float(valor.replace(",", "."))
    except ValueError:
        raise ValueError(f"El campo '{nombre}' debe ser numérico.") from None


def etiqueta_estado(estado: str, texto_: str | None = None) -> ft.Control:
    """Etiqueta redondeada con el color del estado (y opcionalmente otro texto)."""
    return ft.Container(ft.Text(texto_ or estado, color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.W_500),
                        bgcolor=COLORES_ESTADO.get(estado, ft.Colors.GREY_600),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=3), border_radius=12)


def desplegable(etiqueta: str, opciones: Iterable[tuple[Any, str]] = (), width: int | None = None,
                on_select: Callable | None = None, expand: bool | None = None,
                filtro: bool = False) -> ft.Dropdown:
    """Dropdown a partir de pares (clave, texto). Las claves se guardan como texto."""
    return ft.Dropdown(label=etiqueta, options=opciones_desplegable(opciones), width=width, expand=expand,
                       on_select=on_select, enable_filter=filtro, editable=filtro, menu_height=320)


def opciones_desplegable(opciones: Iterable[tuple[Any, str]]) -> list[ft.DropdownOption]:
    return [ft.DropdownOption(key=str(clave), text=texto_opcion) for clave, texto_opcion in opciones]


def entero(desplegable_: ft.Dropdown) -> int | None:
    """Clave seleccionada de un Dropdown como entero (None si no hay selección o es '')."""
    valor = desplegable_.value
    return int(valor) if valor not in (None, "") else None


def campo_hora(etiqueta: str = "Hora", valor: str = "", width: int = 110) -> ft.TextField:
    return ft.TextField(label=etiqueta, value=valor, width=width, hint_text="HH:MM", max_length=5,
                        counter=ft.Text(""))


def fecha_hora(campo_fecha: CampoFecha, campo_hora_: ft.TextField, nombre: str = "fecha y hora") -> str:
    """Combina un CampoFecha y un campo de hora en 'YYYY-MM-DD HH:MM'."""
    if not campo_fecha.valor:
        raise ValueError(f"Indicá la fecha ({nombre}).")
    hora = (campo_hora_.value or "").strip()
    if not re.fullmatch(r"\d{1,2}:\d{2}", hora):
        raise ValueError(f"La hora ({nombre}) debe tener formato HH:MM.")
    h, m = hora.split(":")
    return f"{campo_fecha.valor} {int(h):02d}:{m}"


def fecha_legible(fecha_iso: str | None) -> str:
    """'2026-08-15 10:30' → '15/08/2026 10:30'."""
    if not fecha_iso:
        return "-"
    d = fecha_iso[:10].split("-")
    return f"{d[2]}/{d[1]}/{d[0]}{fecha_iso[10:]}"


def moneda(valor: float) -> str:
    texto_ = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if valor < 0 else ''}$ {texto_}"


def dialogo_info(page: ft.Page, titulo: str, contenido: ft.Control, ancho: int = 640) -> None:
    """Diálogo de solo lectura con un botón Cerrar."""
    dialogo = ft.AlertDialog(
        title=ft.Text(titulo),
        content=ft.Container(contenido, width=ancho),
        actions=[ft.TextButton("Cerrar", on_click=lambda _e: cerrar_dialogo(page, dialogo))],
        scrollable=True,
    )
    page.show_dialog(dialogo)


def dialogo_formulario(page: ft.Page, titulo: str, campos: list[ft.Control], al_aceptar: Callable[[], bool],
                       texto_boton: str = "Guardar", ancho: int = 460) -> ft.AlertDialog:
    """Diálogo con un formulario; se cierra solo si `al_aceptar` devuelve True (si no, queda abierto
    con lo cargado y el error se ve en el SnackBar)."""
    def aceptar(_e) -> None:
        if al_aceptar():
            cerrar_dialogo(page, dialogo)
        page.update()

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text(titulo),
        content=ft.Container(ft.Column(campos, tight=True, spacing=12), width=ancho),
        actions=[ft.TextButton("Cancelar", on_click=lambda _e: cerrar_dialogo(page, dialogo)),
                 ft.FilledButton(texto_boton, on_click=aceptar)],
        scrollable=True,
    )
    page.show_dialog(dialogo)
    return dialogo


def abrir_archivo(ruta: Path | str) -> None:
    """Abre un archivo con la aplicación predeterminada del sistema (p. ej. el visor de PDF)."""
    ruta = str(ruta)
    if sys.platform.startswith("win"):
        os.startfile(ruta)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", ruta])  # noqa: S603, S607
    else:
        subprocess.Popen(["xdg-open", ruta])  # noqa: S603, S607


class CampoFecha:
    """TextField de solo lectura + botón que abre un DatePicker. Valor en ISO 'YYYY-MM-DD'."""

    def __init__(self, page: ft.Page, etiqueta: str, valor: str | None = None, width: int = 180) -> None:
        self.page = page
        self.campo = ft.TextField(label=etiqueta, value=valor or "", read_only=True, width=width,
                                  hint_text="AAAA-MM-DD")
        self.selector = ft.DatePicker(first_date=datetime(2000, 1, 1), last_date=datetime(2100, 12, 31),
                                      on_change=self._al_elegir)
        self.boton = ft.IconButton(ft.Icons.CALENDAR_MONTH, tooltip="Elegir fecha", on_click=self._abrir)
        self.control = ft.Row([self.campo, self.boton], spacing=0, tight=True)

    @property
    def valor(self) -> str | None:
        return self.campo.value or None

    @valor.setter
    def valor(self, nuevo: str | date | None) -> None:
        self.campo.value = nuevo.isoformat() if isinstance(nuevo, date) else (nuevo or "")

    def _abrir(self, _e) -> None:
        if self.valor:
            self.selector.value = datetime.fromisoformat(self.valor)
        self.page.show_dialog(self.selector)

    def _al_elegir(self, e) -> None:
        if e.control.value:
            self.valor = e.control.value.date()
            self.page.update()
