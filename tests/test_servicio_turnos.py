"""Tests de ServicioTurnos."""

import pytest

from dominio.excepciones import EntidadNoEncontradaError, ReglaNegocioError, TurnoSuperpuestoError
from servicios import ServicioMascotas, ServicioTurnos


@pytest.fixture
def servicio(catalogo) -> ServicioTurnos:
    return ServicioTurnos()


@pytest.fixture
def mascota(catalogo):
    return ServicioMascotas().alta("Firulais", catalogo.perro.id_especie, "2024-01-01", catalogo.cliente.id_cliente)


def test_reservar_ok(servicio, catalogo, mascota) -> None:
    turno = servicio.reservar(catalogo.vet.id_veterinario, mascota.id_mascota, "2026-10-22 10:00", "2026-10-22 10:30")
    assert turno.id_turno is not None and turno.estado == "Reservado"
    assert [t.id_turno for t in servicio.turnos_del_dia("2026-10-22")] == [turno.id_turno]


@pytest.mark.parametrize(
    ("inicio", "fin"),
    [
        ("2026-10-22 10:15", "2026-10-22 10:45"),  # empieza durante el existente
        ("2026-10-22 09:45", "2026-10-22 10:15"),  # termina durante el existente
        ("2026-10-22 09:00", "2026-10-22 11:00"),  # lo contiene
        ("2026-10-22 10:05", "2026-10-22 10:20"),  # está contenido
        ("2026-10-22 10:00", "2026-10-22 10:30"),  # mismo horario
    ],
)
def test_reservar_superpuesto(servicio, catalogo, mascota, inicio, fin) -> None:
    vet = catalogo.vet.id_veterinario
    servicio.reservar(vet, mascota.id_mascota, "2026-10-22 10:00", "2026-10-22 10:30")
    with pytest.raises(TurnoSuperpuestoError, match="se superpone"):
        servicio.reservar(vet, mascota.id_mascota, inicio, fin)
    assert len(servicio.turnos_del_dia("2026-10-22")) == 1


@pytest.mark.parametrize(
    ("inicio", "fin"),
    [("2026-10-22 10:30", "2026-10-22 11:00"), ("2026-10-22 09:30", "2026-10-22 10:00")],
)
def test_reservar_turnos_contiguos_ok(servicio, catalogo, mascota, inicio, fin) -> None:
    vet = catalogo.vet.id_veterinario
    servicio.reservar(vet, mascota.id_mascota, "2026-10-22 10:00", "2026-10-22 10:30")
    servicio.reservar(vet, mascota.id_mascota, inicio, fin)
    assert len(servicio.turnos_del_dia("2026-10-22", vet)) == 2


def test_reservar_mismo_horario_otro_veterinario_ok(servicio, catalogo, mascota) -> None:
    servicio.reservar(catalogo.vet.id_veterinario, mascota.id_mascota, "2026-10-22 10:00", "2026-10-22 10:30")
    servicio.reservar(catalogo.vet2.id_veterinario, mascota.id_mascota, "2026-10-22 10:00", "2026-10-22 10:30")


def test_reservar_sobre_turno_cancelado_ok(servicio, catalogo, mascota) -> None:
    vet = catalogo.vet.id_veterinario
    turno = servicio.reservar(vet, mascota.id_mascota, "2026-10-22 10:00", "2026-10-22 10:30")
    servicio.cancelar(turno.id_turno)
    servicio.reservar(vet, mascota.id_mascota, "2026-10-22 10:00", "2026-10-22 10:30")


def test_reservar_validaciones(servicio, catalogo, mascota) -> None:
    with pytest.raises(ReglaNegocioError, match="dado/a de baja"):
        servicio.reservar(catalogo.vet_inactivo.id_veterinario, mascota.id_mascota,
                          "2026-10-22 10:00", "2026-10-22 10:30")
    with pytest.raises(EntidadNoEncontradaError, match="veterinario"):
        servicio.reservar(999, mascota.id_mascota, "2026-10-22 10:00", "2026-10-22 10:30")
    with pytest.raises(EntidadNoEncontradaError, match="mascota"):
        servicio.reservar(catalogo.vet.id_veterinario, 999, "2026-10-22 10:00", "2026-10-22 10:30")
    with pytest.raises(ValueError, match="posterior"):
        servicio.reservar(catalogo.vet.id_veterinario, mascota.id_mascota, "2026-10-22 10:30", "2026-10-22 10:00")


def test_reprogramar(servicio, catalogo, mascota) -> None:
    vet = catalogo.vet.id_veterinario
    t1 = servicio.reservar(vet, mascota.id_mascota, "2026-10-22 10:00", "2026-10-22 10:30")
    servicio.reservar(vet, mascota.id_mascota, "2026-10-22 11:00", "2026-10-22 11:30")

    # Correrlo dentro de su propio horario no choca consigo mismo.
    servicio.reprogramar(t1.id_turno, "2026-10-22 10:15", "2026-10-22 10:45")
    assert servicio.obtener(t1.id_turno).fecha_hora_inicio == "2026-10-22 10:15"
    with pytest.raises(TurnoSuperpuestoError):
        servicio.reprogramar(t1.id_turno, "2026-10-22 10:45", "2026-10-22 11:15")
    assert servicio.obtener(t1.id_turno).fecha_hora_inicio == "2026-10-22 10:15"


def test_cancelar_y_ausente_solo_desde_reservado(servicio, catalogo, mascota) -> None:
    vet = catalogo.vet.id_veterinario
    t1 = servicio.reservar(vet, mascota.id_mascota, "2026-10-22 10:00", "2026-10-22 10:30")
    t2 = servicio.reservar(vet, mascota.id_mascota, "2026-10-22 11:00", "2026-10-22 11:30")
    servicio.cancelar(t1.id_turno)
    servicio.marcar_ausente(t2.id_turno)
    assert servicio.obtener(t1.id_turno).estado == "Cancelado"
    assert servicio.obtener(t2.id_turno).estado == "Ausente"
    with pytest.raises(ReglaNegocioError, match="Cancelado"):
        servicio.cancelar(t1.id_turno)
    with pytest.raises(ReglaNegocioError, match="Ausente"):
        servicio.reprogramar(t2.id_turno, "2026-10-23 10:00", "2026-10-23 10:30")
    with pytest.raises(EntidadNoEncontradaError):
        servicio.cancelar(999)
