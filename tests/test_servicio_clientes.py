"""Tests de ServicioClientes."""

import pytest

from dominio.excepciones import EntidadNoEncontradaError, ReglaNegocioError
from servicios import ServicioClientes, ServicioMascotas


@pytest.fixture
def servicio(catalogo) -> ServicioClientes:
    return ServicioClientes()


def test_alta_ok(servicio) -> None:
    cliente = servicio.alta("40111222", "Lucía", "Ferreyra", email="lu@mail.com")
    assert cliente.id_cliente is not None
    assert servicio.buscar_por_dni("40111222").nombre == "Lucía"


def test_alta_queda_confirmada(servicio, conexion) -> None:
    servicio.alta("40111222", "Lucía", "Ferreyra")
    conexion.rollback()  # un rollback posterior no la deshace: ya hubo commit
    assert servicio.buscar_por_dni("40111222") is not None


def test_alta_dni_repetido(servicio) -> None:
    with pytest.raises(ReglaNegocioError, match="Ya existe un cliente con DNI 30111222"):
        servicio.alta("30111222", "Otro", "Cliente")


def test_alta_dni_de_cliente_dado_de_baja_sugiere_reactivar(servicio) -> None:
    with pytest.raises(ReglaNegocioError, match="reactivalo"):
        servicio.alta("28999888", "Marta", "López")


def test_alta_datos_invalidos(servicio) -> None:
    with pytest.raises(ValueError, match="DNI"):
        servicio.alta("30.111.222", "Juan", "Gómez")
    with pytest.raises(ValueError, match="obligatorio"):
        servicio.alta("40111222", "", "Gómez")


def test_modificar_ok_y_dni_ajeno(servicio, catalogo) -> None:
    cliente = servicio.obtener(catalogo.cliente.id_cliente)
    cliente.telefono = "351-555"
    servicio.modificar(cliente)
    assert servicio.obtener(cliente.id_cliente).telefono == "351-555"

    otro = servicio.alta("40111222", "Lucía", "Ferreyra")
    otro.dni = "30111222"
    with pytest.raises(ReglaNegocioError, match="Ya existe"):
        servicio.modificar(otro)
    assert servicio.obtener(otro.id_cliente).dni == "40111222"


def test_baja_ok_y_reactivar(servicio) -> None:
    cliente = servicio.alta("40111222", "Lucía", "Ferreyra")
    servicio.baja(cliente.id_cliente)
    assert servicio.obtener(cliente.id_cliente).activo is False
    assert all(c.id_cliente != cliente.id_cliente for c in servicio.listar())
    servicio.reactivar(cliente.id_cliente)
    assert servicio.obtener(cliente.id_cliente).activo is True


def test_baja_con_mascotas_activas(servicio, catalogo) -> None:
    ServicioMascotas().alta("Firulais", catalogo.perro.id_especie, "2024-01-01", catalogo.cliente.id_cliente)
    with pytest.raises(ReglaNegocioError, match="Firulais"):
        servicio.baja(catalogo.cliente.id_cliente)
    assert servicio.obtener(catalogo.cliente.id_cliente).activo is True


def test_baja_inexistente_o_ya_dado_de_baja(servicio, catalogo) -> None:
    with pytest.raises(EntidadNoEncontradaError):
        servicio.baja(999)
    with pytest.raises(ReglaNegocioError, match="dado/a de baja"):
        servicio.baja(catalogo.cliente_inactivo.id_cliente)


def test_buscar(servicio) -> None:
    assert [c.dni for c in servicio.buscar("góm")] == ["30111222"]
    assert servicio.buscar("lópez") == []  # inactiva
    assert len(servicio.buscar("López", solo_activos=False)) == 1
