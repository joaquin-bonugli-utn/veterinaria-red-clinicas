"""Tests de la UI sin abrir ventana: una Page falsa registra diálogos y SnackBars,
y los clics se simulan llamando a los manejadores de las vistas."""

import flet as ft
import pytest

from servicios import ServicioMascotas
from tests.pagina_falsa import PageFalsa
from ui.app import SECCIONES, AplicacionVeterinaria
from ui.vista_clientes import VistaClientes


@pytest.fixture
def page() -> PageFalsa:
    return PageFalsa()


@pytest.fixture
def vista(catalogo, page) -> VistaClientes:
    v = VistaClientes(page)
    _ = v.control  # construye los controles
    v.al_mostrar()
    return v


def completar(vista: VistaClientes, **valores) -> None:
    for nombre, valor in valores.items():
        getattr(vista, f"txt_{nombre}").value = valor


def dnis_en_tabla(vista: VistaClientes) -> list[str]:
    return [fila.cells[0].content.value for fila in vista.tabla.rows]


# --- Navegación -------------------------------------------------------------------------

def test_app_arma_las_nueve_secciones(catalogo, page) -> None:
    app = AplicacionVeterinaria(page)
    assert [d.label for d in app.rail.destinations] == [
        "Clientes", "Mascotas", "Turnos", "Atención", "Derivaciones", "Envíos", "Laboratorio",
        "Comprobantes", "Reportes",
    ]
    assert isinstance(app.vista(0), VistaClientes)
    assert app.contenido.content is app.vista(0).control
    for i in range(1, len(SECCIONES)):
        app.mostrar(i)
        assert app.rail.selected_index == i
        assert app.contenido.content is app.vista(i).control
        assert type(app.vista(i)).__name__ != "VistaEnConstruccion"
    app.mostrar(0)
    assert app.vista(0) is app.vista(0)  # las vistas se crean una sola vez


# --- Listado y búsqueda ------------------------------------------------------------------

def test_lista_solo_activos_y_permite_ver_bajas(vista, catalogo) -> None:
    assert dnis_en_tabla(vista) == [catalogo.cliente.dni]
    vista.chk_inactivos.value = True
    vista.cargar()
    assert set(dnis_en_tabla(vista)) == {catalogo.cliente.dni, catalogo.cliente_inactivo.dni}
    assert vista.lbl_cantidad.value == "2 cliente(s)"


def test_busqueda(vista) -> None:
    completar(vista, dni="40111222", nombre="Lucía", apellido="Ferreyra")
    vista._guardar()
    vista.txt_buscar.value = "ferr"
    vista.cargar()
    assert dnis_en_tabla(vista) == ["40111222"]


# --- Alta, edición, baja ----------------------------------------------------------------

def test_alta_ok_limpia_formulario(vista, page) -> None:
    completar(vista, dni="40111222", nombre="Lucía", apellido="Ferreyra", email="lu@mail.com")
    vista._guardar()
    assert not page.ultimo_fue_error
    assert "Ferreyra, Lucía registrado" in page.ultimo_mensaje
    assert "40111222" in dnis_en_tabla(vista)
    assert vista.txt_dni.value == "" and vista.txt_nombre.value == ""


@pytest.mark.parametrize(
    ("valores", "mensaje"),
    [
        ({"dni": "30111222", "nombre": "Otro", "apellido": "X"}, "Ya existe un cliente con DNI 30111222"),
        ({"dni": "", "nombre": "Lucía", "apellido": "Ferreyra"}, "obligatorio"),
        ({"dni": "40111222", "nombre": "Lucía", "apellido": "F", "email": "sin-arroba"}, "email"),
    ],
)
def test_errores_se_muestran_en_snackbar_rojo(vista, page, valores, mensaje) -> None:
    completar(vista, **valores)
    vista._guardar()
    assert page.ultimo_fue_error
    assert mensaje in page.ultimo_mensaje
    assert vista.txt_nombre.value == valores["nombre"]  # el formulario conserva lo cargado


def test_editar_y_guardar_cambios(vista, page, catalogo) -> None:
    cliente = vista.servicio.obtener(catalogo.cliente.id_cliente)
    vista._editar(cliente)
    assert vista.txt_dni.value == cliente.dni
    assert vista.btn_guardar.content == "Guardar cambios" and vista.btn_cancelar.visible
    vista.txt_telefono.value = "351-999"
    vista._guardar()
    assert page.ultimo_mensaje == "Cambios guardados."
    assert vista.servicio.obtener(cliente.id_cliente).telefono == "351-999"
    assert vista.btn_guardar.content == "Agregar" and not vista.btn_cancelar.visible


def test_cancelar_edicion(vista, catalogo) -> None:
    vista._editar(vista.servicio.obtener(catalogo.cliente.id_cliente))
    vista._cancelar()
    assert vista._editando is None and vista.txt_dni.value == ""


def test_baja_pide_confirmacion_y_reactivar(vista, page) -> None:
    completar(vista, dni="40111222", nombre="Lucía", apellido="Ferreyra")
    vista._guardar()
    cliente = vista.servicio.buscar_por_dni("40111222")

    vista._baja(cliente)
    assert isinstance(page.dialogo_abierto, ft.AlertDialog)
    page.aceptar_dialogo()  # "Dar de baja"
    assert page.dialogo_abierto is None
    assert "dado/a de baja" in page.ultimo_mensaje
    assert "40111222" not in dnis_en_tabla(vista)

    vista._reactivar(vista.servicio.obtener(cliente.id_cliente))
    assert "reactivado" in page.ultimo_mensaje
    assert "40111222" in dnis_en_tabla(vista)


def test_baja_con_mascotas_muestra_error(vista, page, catalogo) -> None:
    ServicioMascotas().alta("Firulais", catalogo.perro.id_especie, "2024-01-01", catalogo.cliente.id_cliente)
    vista.cargar()
    assert vista.tabla.rows[0].cells[5].content.value == "Firulais"
    vista._baja(vista.servicio.obtener(catalogo.cliente.id_cliente))
    page.aceptar_dialogo()
    assert page.ultimo_fue_error and "mascotas activas" in page.ultimo_mensaje
