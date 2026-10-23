"""Tests de ServicioAtencion: registro de atenciones y control de vacunas (regla 6)."""

import pytest

from dominio.excepciones import EntidadNoEncontradaError, ReglaNegocioError
from servicios import (
    ServicioAtencion,
    ServicioMascotas,
    ServicioTurnos,
    TratamientoIndicado,
    VacunaAAplicar,
)


@pytest.fixture
def servicio(catalogo) -> ServicioAtencion:
    return ServicioAtencion()


@pytest.fixture
def perro(catalogo):
    """Nacido el 2026-01-01: el 2026-10-22 tiene 294 días."""
    return ServicioMascotas().alta("Firulais", catalogo.perro.id_especie, "2026-01-01", catalogo.cliente.id_cliente)


def contar(conexion, tabla: str) -> int:
    return conexion.cursor().execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


def registrar(servicio, catalogo, mascota, fecha_hora="2026-10-22 10:00", **extra):
    return servicio.registrar(mascota.id_mascota, catalogo.vet.id_veterinario, catalogo.consulta.id_tipo_atencion,
                              fecha_hora, "Control", **extra)


# =============================================================================
#  registrar(): casos OK
# =============================================================================

def test_registrar_sin_turno(servicio, catalogo, perro) -> None:
    resultado = registrar(servicio, catalogo, perro, diagnostico="Sano")
    atencion = resultado.atencion
    assert atencion.id_atencion is not None and atencion.id_turno is None
    assert atencion.id_clinica == catalogo.clinica.id_clinica  # por defecto, la del veterinario
    assert [a.id_atencion for a in servicio.atenciones_de_mascota(perro.id_mascota)] == [atencion.id_atencion]


def test_registrar_con_turno_lo_marca_atendido(servicio, catalogo, perro) -> None:
    turnos = ServicioTurnos()
    turno = turnos.reservar(catalogo.vet.id_veterinario, perro.id_mascota, "2026-10-22 10:00", "2026-10-22 10:30")
    resultado = registrar(servicio, catalogo, perro, id_turno=turno.id_turno)
    assert resultado.atencion.id_turno == turno.id_turno
    assert turnos.obtener(turno.id_turno).estado == "Atendido"


def test_registrar_tratamientos_y_vacunas(servicio, catalogo, perro) -> None:
    resultado = registrar(
        servicio, catalogo, perro,
        tratamientos=[TratamientoIndicado("Amoxicilina", "250 mg", "cada 12 h", fecha_fin="2026-10-29")],
        vacunas=[VacunaAAplicar(catalogo.antirrabica.id_vacuna, "L-RAB-1"),
                 VacunaAAplicar(catalogo.lepto.id_vacuna, "L-LEP-1")],
    )
    (tratamiento,) = resultado.tratamientos
    assert tratamiento.fecha_inicio == "2026-10-22"  # por defecto, el día de la atención

    por_vacuna = {a.id_vacuna: a for a in resultado.aplicaciones}
    assert por_vacuna[catalogo.antirrabica.id_vacuna].fecha_proxima_dosis == "2027-10-22"  # +365 días
    assert por_vacuna[catalogo.lepto.id_vacuna].fecha_proxima_dosis is None  # dosis única

    id_at = resultado.atencion.id_atencion
    assert len(servicio.tratamientos_de(id_at)) == 1
    assert len(servicio.vacunas_aplicadas_de(id_at)) == 2


def test_registrar_actualiza_peso_de_la_mascota(servicio, catalogo, perro) -> None:
    registrar(servicio, catalogo, perro, peso_kg=14.2)
    assert ServicioMascotas().obtener(perro.id_mascota).peso_kg == 14.2


def test_registrar_devuelve_vacunas_pendientes(servicio, catalogo, perro) -> None:
    resultado = registrar(servicio, catalogo, perro,
                          vacunas=[VacunaAAplicar(catalogo.antirrabica.id_vacuna, "L-1")])
    pendientes = {p.vacuna.nombre: p for p in resultado.vacunas_pendientes}
    # La recién aplicada ya no figura; la opcional (Giardia) nunca figura.
    assert set(pendientes) == {"Séxtuple", "Leptospirosis"}
    assert pendientes["Séxtuple"].situacion == "Pendiente"
    assert pendientes["Séxtuple"].fecha_limite == "2026-02-15"  # nacimiento + 45 días


# =============================================================================
#  registrar(): casos de error (todo se deshace)
# =============================================================================

def test_registrar_mascota_inexistente_o_inactiva(servicio, catalogo, perro) -> None:
    with pytest.raises(EntidadNoEncontradaError, match="mascota"):
        servicio.registrar(999, catalogo.vet.id_veterinario, catalogo.consulta.id_tipo_atencion,
                           "2026-10-22 10:00", "Control")
    ServicioMascotas().baja(perro.id_mascota)
    with pytest.raises(ReglaNegocioError, match="dado/a de baja"):
        registrar(servicio, catalogo, perro)


def test_registrar_veterinario_inactivo_y_tipo_inexistente(servicio, catalogo, perro) -> None:
    with pytest.raises(ReglaNegocioError, match="veterinario"):
        servicio.registrar(perro.id_mascota, catalogo.vet_inactivo.id_veterinario,
                           catalogo.consulta.id_tipo_atencion, "2026-10-22 10:00", "Control")
    with pytest.raises(EntidadNoEncontradaError, match="tipo de atención"):
        servicio.registrar(perro.id_mascota, catalogo.vet.id_veterinario, 999, "2026-10-22 10:00", "Control")


def test_registrar_turno_invalido(servicio, catalogo, perro) -> None:
    turnos = ServicioTurnos()
    otro = ServicioMascotas().alta("Toby", catalogo.perro.id_especie, "2025-01-01", catalogo.cliente.id_cliente)
    t_otra_mascota = turnos.reservar(catalogo.vet.id_veterinario, otro.id_mascota,
                                     "2026-10-22 09:00", "2026-10-22 09:30")
    t_otro_vet = turnos.reservar(catalogo.vet2.id_veterinario, perro.id_mascota,
                                 "2026-10-22 09:00", "2026-10-22 09:30")
    t_cancelado = turnos.reservar(catalogo.vet.id_veterinario, perro.id_mascota,
                                  "2026-10-22 11:00", "2026-10-22 11:30")
    turnos.cancelar(t_cancelado.id_turno)

    with pytest.raises(ReglaNegocioError, match="otra mascota"):
        registrar(servicio, catalogo, perro, id_turno=t_otra_mascota.id_turno)
    with pytest.raises(ReglaNegocioError, match="otro veterinario"):
        registrar(servicio, catalogo, perro, id_turno=t_otro_vet.id_turno)
    with pytest.raises(ReglaNegocioError, match="Cancelado"):
        registrar(servicio, catalogo, perro, id_turno=t_cancelado.id_turno)
    with pytest.raises(EntidadNoEncontradaError, match="turno"):
        registrar(servicio, catalogo, perro, id_turno=999)


def test_registrar_turno_ya_atendido(servicio, catalogo, perro) -> None:
    turno = ServicioTurnos().reservar(catalogo.vet.id_veterinario, perro.id_mascota,
                                      "2026-10-22 10:00", "2026-10-22 10:30")
    registrar(servicio, catalogo, perro, id_turno=turno.id_turno)
    with pytest.raises(ReglaNegocioError, match="Atendido"):
        registrar(servicio, catalogo, perro, id_turno=turno.id_turno)


def test_vacuna_de_otra_especie_deshace_todo(servicio, catalogo, perro, conexion) -> None:
    with pytest.raises(ReglaNegocioError, match="especie"):
        registrar(servicio, catalogo, perro,
                  tratamientos=[TratamientoIndicado("Amoxicilina", "250 mg")],
                  vacunas=[VacunaAAplicar(catalogo.triple_felina.id_vacuna, "L-1")])
    for tabla in ("atencion", "tratamiento", "aplicacion_vacuna"):
        assert contar(conexion, tabla) == 0


def test_turno_no_queda_atendido_si_falla(servicio, catalogo, perro) -> None:
    turnos = ServicioTurnos()
    turno = turnos.reservar(catalogo.vet.id_veterinario, perro.id_mascota, "2026-10-22 10:00", "2026-10-22 10:30")
    with pytest.raises(EntidadNoEncontradaError, match="vacuna"):
        registrar(servicio, catalogo, perro, id_turno=turno.id_turno, vacunas=[VacunaAAplicar(999, "L-1")])
    assert turnos.obtener(turno.id_turno).estado == "Reservado"


def test_vacuna_antes_de_la_edad_minima(servicio, catalogo) -> None:
    cachorro = ServicioMascotas().alta("Mini", catalogo.perro.id_especie, "2026-10-01", catalogo.cliente.id_cliente)
    with pytest.raises(ReglaNegocioError, match="90 días.*tiene 21"):
        registrar(servicio, catalogo, cachorro, vacunas=[VacunaAAplicar(catalogo.antirrabica.id_vacuna, "L-1")])


def test_vacuna_repetida_en_la_misma_atencion(servicio, catalogo, perro) -> None:
    vacuna = catalogo.antirrabica.id_vacuna
    with pytest.raises(ReglaNegocioError, match="dos veces"):
        registrar(servicio, catalogo, perro, vacunas=[VacunaAAplicar(vacuna, "L-1"), VacunaAAplicar(vacuna, "L-2")])


def test_vacuna_dosis_unica_ya_aplicada(servicio, catalogo, perro) -> None:
    registrar(servicio, catalogo, perro, vacunas=[VacunaAAplicar(catalogo.lepto.id_vacuna, "L-1")])
    with pytest.raises(ReglaNegocioError, match="dosis única"):
        registrar(servicio, catalogo, perro, "2026-11-22 10:00",
                  vacunas=[VacunaAAplicar(catalogo.lepto.id_vacuna, "L-2")])


def test_registrar_datos_invalidos(servicio, catalogo, perro, conexion) -> None:
    with pytest.raises(ValueError, match="HH:MM"):
        registrar(servicio, catalogo, perro, fecha_hora="22/10/2026")
    with pytest.raises(ValueError, match="motivo"):
        servicio.registrar(perro.id_mascota, catalogo.vet.id_veterinario, catalogo.consulta.id_tipo_atencion,
                           "2026-10-22 10:00", "  ")
    with pytest.raises(ValueError, match="dosis"):
        registrar(servicio, catalogo, perro, tratamientos=[TratamientoIndicado("Amoxicilina", "")])
    assert contar(conexion, "atencion") == 0


# =============================================================================
#  vacunas_pendientes()
# =============================================================================

def nombres(pendientes) -> dict[str, str]:
    return {p.vacuna.nombre: p.situacion for p in pendientes}


def test_pendientes_segun_edad(servicio, catalogo) -> None:
    cachorro = ServicioMascotas().alta("Mini", catalogo.perro.id_especie, "2026-08-01", catalogo.cliente.id_cliente)
    assert servicio.vacunas_pendientes(cachorro.id_mascota, "2026-09-01") == []  # 31 días: ninguna exigible
    assert nombres(servicio.vacunas_pendientes(cachorro.id_mascota, "2026-09-20")) == {"Séxtuple": "Pendiente"}
    assert nombres(servicio.vacunas_pendientes(cachorro.id_mascota, "2026-10-31")) == {
        "Séxtuple": "Pendiente", "Leptospirosis": "Pendiente", "Antirrábica": "Pendiente"
    }


def test_pendientes_con_refuerzo_vencido(servicio, catalogo, perro) -> None:
    registrar(servicio, catalogo, perro, "2026-04-01 10:00",
              vacunas=[VacunaAAplicar(catalogo.sextuple.id_vacuna, "L-1"),
                       VacunaAAplicar(catalogo.antirrabica.id_vacuna, "L-2"),
                       VacunaAAplicar(catalogo.lepto.id_vacuna, "L-3")])

    assert servicio.vacunas_pendientes(perro.id_mascota, "2027-03-31") == []  # todo al día
    vencidas = servicio.vacunas_pendientes(perro.id_mascota, "2027-04-01")
    assert nombres(vencidas) == {"Séxtuple": "Vencida", "Antirrábica": "Vencida"}  # lepto: dosis única
    assert vencidas[0].fecha_limite == "2027-04-01"
    assert vencidas[0].ultima_aplicacion == "2026-04-01"
    assert "refuerzo vencido" in str(vencidas[0])


def test_pendientes_ignora_aplicaciones_posteriores_a_la_fecha(servicio, catalogo, perro) -> None:
    registrar(servicio, catalogo, perro, "2026-10-22 10:00",
              vacunas=[VacunaAAplicar(catalogo.sextuple.id_vacuna, "L-1")])
    assert "Séxtuple" in nombres(servicio.vacunas_pendientes(perro.id_mascota, "2026-10-01"))
    assert "Séxtuple" not in nombres(servicio.vacunas_pendientes(perro.id_mascota, "2026-10-22"))


def test_pendientes_otra_especie_y_errores(servicio, catalogo) -> None:
    gato = ServicioMascotas().alta("Michi", catalogo.gato.id_especie, "2026-01-01", catalogo.cliente.id_cliente)
    assert nombres(servicio.vacunas_pendientes(gato.id_mascota, "2026-10-22")) == {"Triple felina": "Pendiente"}
    with pytest.raises(EntidadNoEncontradaError):
        servicio.vacunas_pendientes(999, "2026-10-22")
    with pytest.raises(ValueError, match="anterior al nacimiento"):
        servicio.vacunas_pendientes(gato.id_mascota, "2025-12-31")
