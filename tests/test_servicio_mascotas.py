"""Tests de ServicioMascotas."""

from datetime import date

import pytest

from dominio import HistoriaClinica
from dominio.excepciones import EntidadNoEncontradaError, ReglaNegocioError
from servicios import ServicioMascotas


@pytest.fixture
def servicio(catalogo) -> ServicioMascotas:
    return ServicioMascotas()


def contar(conexion, tabla: str) -> int:
    return conexion.cursor().execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


def test_alta_crea_mascota_e_historia(servicio, catalogo, conexion) -> None:
    mascota = servicio.alta("Firulais", catalogo.perro.id_especie, "2024-01-01", catalogo.cliente.id_cliente,
                            raza="Mestizo", alergias="Penicilina")
    historia = servicio.obtener_historia(mascota.id_mascota)
    assert historia.id_mascota == mascota.id_mascota
    assert historia.alergias == "Penicilina"
    assert historia.fecha_apertura == date.today().isoformat()
    conexion.rollback()  # ya confirmado
    assert contar(conexion, "mascota") == contar(conexion, "historia_clinica") == 1


def test_alta_cliente_inexistente(servicio, catalogo, conexion) -> None:
    with pytest.raises(EntidadNoEncontradaError, match="cliente responsable"):
        servicio.alta("Firulais", catalogo.perro.id_especie, "2024-01-01", 999)
    assert contar(conexion, "mascota") == 0


def test_alta_cliente_inactivo(servicio, catalogo, conexion) -> None:
    with pytest.raises(ReglaNegocioError, match="dado/a de baja"):
        servicio.alta("Firulais", catalogo.perro.id_especie, "2024-01-01", catalogo.cliente_inactivo.id_cliente)
    assert contar(conexion, "mascota") == 0


def test_alta_sin_cliente(servicio, catalogo) -> None:
    with pytest.raises(ValueError, match="cliente responsable"):
        servicio.alta("Firulais", catalogo.perro.id_especie, "2024-01-01", None)


def test_alta_especie_inexistente(servicio, catalogo) -> None:
    with pytest.raises(EntidadNoEncontradaError, match="especie"):
        servicio.alta("Firulais", 999, "2024-01-01", catalogo.cliente.id_cliente)


def test_alta_es_atomica_si_falla_la_historia(servicio, catalogo, conexion, monkeypatch) -> None:
    """Si falla el INSERT de la historia, tampoco queda la mascota (rollback)."""
    agregar_original = servicio.mascotas.agregar

    def agregar_que_falla(entidad):
        if isinstance(entidad, HistoriaClinica):
            raise RuntimeError("falla simulada")
        return agregar_original(entidad)

    monkeypatch.setattr(servicio.mascotas, "agregar", agregar_que_falla)
    with pytest.raises(RuntimeError):
        servicio.alta("Firulais", catalogo.perro.id_especie, "2024-01-01", catalogo.cliente.id_cliente)
    assert contar(conexion, "mascota") == 0
    assert contar(conexion, "historia_clinica") == 0


def test_modificar_cambio_de_responsable(servicio, catalogo) -> None:
    mascota = servicio.alta("Firulais", catalogo.perro.id_especie, "2024-01-01", catalogo.cliente.id_cliente)
    mascota.id_cliente = catalogo.cliente_inactivo.id_cliente
    with pytest.raises(ReglaNegocioError):
        servicio.modificar(mascota)
    assert servicio.obtener(mascota.id_mascota).id_cliente == catalogo.cliente.id_cliente

    mascota.id_cliente = catalogo.cliente.id_cliente
    mascota.peso_kg = 12.5
    servicio.modificar(mascota)
    assert servicio.obtener(mascota.id_mascota).peso_kg == 12.5


def test_baja_y_listado(servicio, catalogo) -> None:
    m1 = servicio.alta("Firulais", catalogo.perro.id_especie, "2024-01-01", catalogo.cliente.id_cliente)
    servicio.alta("Toby", catalogo.perro.id_especie, "2023-01-01", catalogo.cliente.id_cliente)
    servicio.baja(m1.id_mascota)
    assert [m.nombre for m in servicio.listar_por_cliente(catalogo.cliente.id_cliente)] == ["Toby"]
    # La historia clínica se conserva.
    assert servicio.obtener_historia(m1.id_mascota) is not None
    with pytest.raises(ReglaNegocioError):
        servicio.baja(m1.id_mascota)


def test_actualizar_historia(servicio, catalogo) -> None:
    mascota = servicio.alta("Firulais", catalogo.perro.id_especie, "2024-01-01", catalogo.cliente.id_cliente)
    servicio.actualizar_historia(mascota.id_mascota, alergias="Ninguna", antecedentes="Displasia")
    assert servicio.obtener_historia(mascota.id_mascota).antecedentes == "Displasia"
    with pytest.raises(EntidadNoEncontradaError):
        servicio.actualizar_historia(999, alergias="x")
