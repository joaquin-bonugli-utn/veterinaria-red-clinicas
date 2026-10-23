"""Tests de los repositorios contra una base SQLite en memoria."""

import inspect
import re
import sqlite3
from types import SimpleNamespace

import pytest

from dominio import (
    AplicacionVacuna,
    Atencion,
    CambioEstadoMuestra,
    Cliente,
    Clinica,
    Comprobante,
    Conservadora,
    DetalleComprobante,
    Especie,
    HistoriaClinica,
    Laboratorio,
    Mascota,
    Muestra,
    OrdenDerivacion,
    PrecintoSanitario,
    Recepcion,
    RemitoBiologico,
    ResultadoAnalisis,
    TipoAnalisis,
    TipoAtencion,
    TramoEnvio,
    Transportista,
    Tratamiento,
    Turno,
    Vacuna,
    Veterinario,
)
from persistencia.conexion import Conexion
from persistencia.repositorios import (
    RegistroNoEncontradoError,
    RepositorioAtenciones,
    RepositorioCatalogos,
    RepositorioClientes,
    RepositorioComprobantes,
    RepositorioDerivaciones,
    RepositorioEnvios,
    RepositorioMascotas,
    RepositorioResultados,
    RepositorioTurnos,
    RepositorioVeterinarios,
)
from persistencia.repositorios import derivaciones as modulo_derivaciones


@pytest.fixture
def repos(conexion: Conexion) -> SimpleNamespace:
    return SimpleNamespace(
        clientes=RepositorioClientes(),
        mascotas=RepositorioMascotas(),
        veterinarios=RepositorioVeterinarios(),
        turnos=RepositorioTurnos(),
        atenciones=RepositorioAtenciones(),
        catalogos=RepositorioCatalogos(),
        derivaciones=RepositorioDerivaciones(),
        envios=RepositorioEnvios(),
        resultados=RepositorioResultados(),
        comprobantes=RepositorioComprobantes(),
    )


@pytest.fixture
def datos(repos: SimpleNamespace) -> SimpleNamespace:
    """Datos mínimos encadenados: clínica → veterinario, cliente → mascota → historia → atención."""
    cat = repos.catalogos
    d = SimpleNamespace()
    d.clinica = Clinica("Centro", "Av. Colón 100")
    d.laboratorio = Laboratorio("LabVet", "Bv. San Juan 50")
    d.perro = Especie("Perro")
    d.consulta = TipoAtencion("Consulta", 8000)
    d.hemograma = TipoAnalisis("Hemograma", "Sangre", 2, 8, 24, 5000)
    d.transportista = Transportista("20333444", "Carlos Ruiz")
    for entidad in (d.clinica, d.laboratorio, d.perro, d.consulta, d.hemograma, d.transportista):
        cat.agregar(entidad)
    d.rabia = Vacuna("Antirrábica", d.perro.id_especie, 6000, obligatoria=True, edad_minima_dias=90,
                     refuerzo_dias=365)
    cat.agregar(d.rabia)

    d.vet = Veterinario("MP-1", "Ana", "Pérez", d.clinica.id_clinica)
    repos.veterinarios.agregar(d.vet)
    d.cliente = Cliente("30111222", "Juan", "Gómez")
    repos.clientes.agregar(d.cliente)
    d.mascota = Mascota("Firulais", d.perro.id_especie, "2024-01-01", d.cliente.id_cliente)
    repos.mascotas.agregar(d.mascota)
    d.historia = HistoriaClinica(d.mascota.id_mascota, "2024-02-01")
    repos.mascotas.agregar(d.historia)
    d.atencion = Atencion(d.historia.id_historia, d.vet.id_veterinario, d.clinica.id_clinica,
                          d.consulta.id_tipo_atencion, "2026-10-22 10:05", "Control")
    repos.atenciones.agregar(d.atencion)
    d.orden = OrdenDerivacion(d.atencion.id_atencion, d.laboratorio.id_laboratorio, "2026-10-22")
    repos.derivaciones.agregar(d.orden)
    d.conservadora = Conservadora("CONS-01", d.clinica.id_clinica, 10, 2, 8)
    repos.envios.agregar(d.conservadora)
    d.remito = RemitoBiologico("REM-2026-00001", d.clinica.id_clinica, d.laboratorio.id_laboratorio,
                               d.conservadora.id_conservadora, "2026-10-22")
    repos.envios.agregar(d.remito)
    return d


def contar(conexion: Conexion, tabla: str) -> int:
    # Solo para tests: `tabla` es una constante del propio test.
    return conexion.cursor().execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


# =============================================================================
#  Comportamiento común (RepositorioBase)
# =============================================================================

def test_repositorios_no_hacen_commit(conexion: Conexion, repos) -> None:
    repos.catalogos.agregar(Especie("Gato"))
    assert contar(conexion, "especie") == 1
    conexion.rollback()
    assert contar(conexion, "especie") == 0


def test_agregar_asigna_id_y_rechaza_entidad_ya_guardada(repos) -> None:
    especie = Especie("Gato")
    id_ = repos.catalogos.agregar(especie)
    assert especie.id_especie == id_ > 0
    with pytest.raises(ValueError, match="modificar"):
        repos.catalogos.agregar(especie)


def test_modificar_sin_id_o_inexistente(repos) -> None:
    with pytest.raises(ValueError, match="agregar"):
        repos.clientes.modificar(Cliente("1", "A", "B"))
    with pytest.raises(RegistroNoEncontradoError):
        repos.clientes.modificar(Cliente("1", "A", "B", id_cliente=999))


def test_repositorio_rechaza_clases_ajenas(repos) -> None:
    with pytest.raises(TypeError, match="no maneja"):
        repos.clientes.agregar(Especie("Gato"))
    with pytest.raises(ValueError, match="indicá la clase"):
        repos.catalogos.listar()


def test_fk_activas_impiden_huerfanos(repos) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        repos.mascotas.agregar(Mascota("Michi", 99, "2024-01-01", 99))


def test_repo_sigue_al_singleton_tras_reiniciar(repos) -> None:
    repos.catalogos.agregar(Especie("Gato"))
    Conexion.reiniciar_para_tests()
    assert repos.catalogos.listar(Especie) == []


# =============================================================================
#  RepositorioClientes
# =============================================================================

def test_clientes_abmc_y_baja_logica(conexion: Conexion, repos) -> None:
    cliente = Cliente("30111222", "Juan", "Gómez", email="juan@mail.com")
    repos.clientes.agregar(cliente)

    leido = repos.clientes.obtener_por_id(cliente.id_cliente)
    assert isinstance(leido, Cliente)
    assert (leido.dni, leido.email, leido.activo) == ("30111222", "juan@mail.com", True)

    leido.telefono = "351-555"
    repos.clientes.modificar(leido)
    assert repos.clientes.obtener_por_id(cliente.id_cliente).telefono == "351-555"

    repos.clientes.baja(cliente.id_cliente)
    assert contar(conexion, "cliente") == 1  # sigue en la tabla
    assert repos.clientes.obtener_por_id(cliente.id_cliente).activo is False
    assert repos.clientes.listar() == []
    assert len(repos.clientes.listar(solo_activos=False)) == 1


def test_clientes_busquedas(repos) -> None:
    for dni, nombre, apellido in [("1", "Juan", "Gómez"), ("2", "Ana", "González"), ("3", "Luis", "Pérez")]:
        repos.clientes.agregar(Cliente(dni, nombre, apellido))
    assert repos.clientes.buscar_por_dni("2").apellido == "González"
    assert repos.clientes.buscar_por_dni("99") is None
    assert {c.apellido for c in repos.clientes.buscar_por_apellido("g")} == {"Gómez", "González"}
    assert [c.apellido for c in repos.clientes.buscar_por_apellido("GON")] == ["González"]
    assert [c.nombre for c in repos.clientes.buscar("lu")] == ["Luis"]


def test_clientes_baja_inexistente(repos) -> None:
    with pytest.raises(RegistroNoEncontradoError):
        repos.clientes.baja(999)


# =============================================================================
#  RepositorioMascotas (incluye historia clínica)
# =============================================================================

def test_mascotas_y_historia(repos, datos) -> None:
    mascota = repos.mascotas.obtener_por_id(datos.mascota.id_mascota)
    assert isinstance(mascota, Mascota) and mascota.nombre == "Firulais"
    historia = repos.mascotas.obtener_historia(datos.mascota.id_mascota)
    assert isinstance(historia, HistoriaClinica) and historia.id_historia == datos.historia.id_historia
    assert repos.mascotas.obtener_historia(999) is None

    historia.alergias = "Penicilina"
    repos.mascotas.modificar(historia)
    assert repos.mascotas.obtener_por_id(historia.id_historia, HistoriaClinica).alergias == "Penicilina"


def test_mascotas_busquedas_y_baja(repos, datos) -> None:
    otra = Mascota("Toby", datos.perro.id_especie, "2023-05-01", datos.cliente.id_cliente)
    repos.mascotas.agregar(otra)
    assert [m.nombre for m in repos.mascotas.listar_por_cliente(datos.cliente.id_cliente)] == ["Firulais", "Toby"]
    assert [m.nombre for m in repos.mascotas.buscar_por_nombre("tob")] == ["Toby"]
    assert len(repos.mascotas.listar_por_especie(datos.perro.id_especie)) == 2

    repos.mascotas.baja(otra.id_mascota)
    assert [m.nombre for m in repos.mascotas.listar_por_cliente(datos.cliente.id_cliente)] == ["Firulais"]
    assert len(repos.mascotas.listar_por_cliente(datos.cliente.id_cliente, solo_activas=False)) == 2


# =============================================================================
#  RepositorioVeterinarios
# =============================================================================

def test_veterinarios(repos, datos) -> None:
    repos.veterinarios.agregar(Veterinario("MP-2", "Luis", "Álvarez", datos.clinica.id_clinica))
    assert repos.veterinarios.buscar_por_matricula("MP-1").apellido == "Pérez"
    assert len(repos.veterinarios.listar_por_clinica(datos.clinica.id_clinica)) == 2
    assert [v.matricula for v in repos.veterinarios.buscar_por_apellido("Pé")] == ["MP-1"]

    repos.veterinarios.baja(datos.vet.id_veterinario)
    assert [v.matricula for v in repos.veterinarios.listar()] == ["MP-2"]
    assert repos.veterinarios.obtener_por_id(datos.vet.id_veterinario).activo is False


# =============================================================================
#  RepositorioTurnos
# =============================================================================

def test_turnos_por_veterinario_en_rango(repos, datos) -> None:
    vet, mascota = datos.vet.id_veterinario, datos.mascota.id_mascota
    for inicio, fin in [("2026-10-21 09:00", "2026-10-21 09:30"), ("2026-10-22 10:00", "2026-10-22 10:30"),
                        ("2026-10-22 18:00", "2026-10-22 18:30"), ("2026-10-23 08:00", "2026-10-23 08:30")]:
        repos.turnos.agregar(Turno(vet, mascota, inicio, fin))

    del_dia = repos.turnos.listar_por_veterinario(vet, "2026-10-22", "2026-10-23")
    assert [t.fecha_hora_inicio for t in del_dia] == ["2026-10-22 10:00", "2026-10-22 18:00"]
    assert len(repos.turnos.listar_por_rango("2026-10-21", "2026-10-24")) == 4
    assert len(repos.turnos.listar_por_mascota(mascota)) == 4


def test_turnos_superpuestos(repos, datos) -> None:
    vet, mascota = datos.vet.id_veterinario, datos.mascota.id_mascota
    turno = Turno(vet, mascota, "2026-10-22 10:00", "2026-10-22 10:30")
    repos.turnos.agregar(turno)
    cancelado = Turno(vet, mascota, "2026-10-22 11:00", "2026-10-22 11:30", estado="Cancelado")
    repos.turnos.agregar(cancelado)

    assert len(repos.turnos.buscar_superpuestos(vet, "2026-10-22 10:15", "2026-10-22 10:45")) == 1
    assert repos.turnos.buscar_superpuestos(vet, "2026-10-22 10:30", "2026-10-22 11:00") == []  # contiguo
    assert repos.turnos.buscar_superpuestos(vet, "2026-10-22 11:00", "2026-10-22 11:30") == []  # cancelado
    assert repos.turnos.buscar_superpuestos(vet, "2026-10-22 10:00", "2026-10-22 10:30",
                                            excluir_id=turno.id_turno) == []


def test_turnos_modificar_estado(repos, datos) -> None:
    turno = Turno(datos.vet.id_veterinario, datos.mascota.id_mascota, "2026-10-22 10:00", "2026-10-22 10:30")
    repos.turnos.agregar(turno)
    turno.estado = "Atendido"
    repos.turnos.modificar(turno)
    assert repos.turnos.obtener_por_id(turno.id_turno).estado == "Atendido"


# =============================================================================
#  RepositorioAtenciones (incluye tratamientos y aplicaciones de vacuna)
# =============================================================================

def test_atenciones_con_tratamientos_y_vacunas(repos, datos) -> None:
    rep = repos.atenciones
    id_at = datos.atencion.id_atencion
    rep.agregar(Tratamiento(id_at, "Amoxicilina", "250 mg", "2026-10-22"))
    rep.agregar(AplicacionVacuna(id_at, datos.rabia.id_vacuna, "2026-10-22", "L-1", "2027-10-22"))

    assert [t.medicamento for t in rep.listar_tratamientos(id_at)] == ["Amoxicilina"]
    assert [a.lote for a in rep.listar_aplicaciones(id_at)] == ["L-1"]
    assert [a.id_vacuna for a in rep.listar_aplicaciones_por_mascota(datos.mascota.id_mascota)] == [
        datos.rabia.id_vacuna
    ]
    assert [a.motivo for a in rep.listar_por_mascota(datos.mascota.id_mascota)] == ["Control"]
    assert len(rep.listar_por_historia(datos.historia.id_historia)) == 1
    assert len(rep.listar_por_rango("2026-10-22", "2026-10-23", id_clinica=datos.clinica.id_clinica)) == 1
    assert rep.listar_por_rango("2026-10-23", "2026-10-24") == []


def test_atencion_por_turno(repos, datos) -> None:
    turno = Turno(datos.vet.id_veterinario, datos.mascota.id_mascota, "2026-10-23 10:00", "2026-10-23 10:30")
    repos.turnos.agregar(turno)
    atencion = Atencion(datos.historia.id_historia, datos.vet.id_veterinario, datos.clinica.id_clinica,
                        datos.consulta.id_tipo_atencion, "2026-10-23 10:00", "Vómitos", id_turno=turno.id_turno)
    repos.atenciones.agregar(atencion)
    assert repos.atenciones.obtener_por_turno(turno.id_turno).motivo == "Vómitos"

    atencion.diagnostico = "Gastritis"
    repos.atenciones.modificar(atencion)
    assert repos.atenciones.obtener_por_id(atencion.id_atencion).diagnostico == "Gastritis"


# =============================================================================
#  RepositorioCatalogos
# =============================================================================

def test_catalogos_abmc(repos, datos) -> None:
    cat = repos.catalogos
    assert cat.obtener_por_id(datos.perro.id_especie, Especie).nombre == "Perro"
    assert cat.buscar_por_nombre(TipoAnalisis, "Hemograma").horas_viabilidad == 24
    assert cat.buscar_por_nombre(Clinica, "Inexistente") is None
    with pytest.raises(TypeError):
        cat.buscar_por_nombre(Vacuna, "Antirrábica")

    datos.consulta.precio = 9000
    cat.modificar(datos.consulta)
    assert cat.obtener_por_id(datos.consulta.id_tipo_atencion, TipoAtencion).precio == 9000

    cat.agregar(Especie("Gato"))
    assert [e.nombre for e in cat.listar_ordenado(Especie)] == ["Gato", "Perro"]
    gato = cat.buscar_por_nombre(Especie, "Gato")
    cat.baja(gato.id_especie, Especie)  # sin campo activo: baja física
    assert cat.obtener_por_id(gato.id_especie, Especie) is None


def test_catalogos_vacunas_y_transportistas(repos, datos) -> None:
    cat = repos.catalogos
    cat.agregar(Vacuna("Tos de las perreras", datos.perro.id_especie, 4000))
    assert len(cat.vacunas_por_especie(datos.perro.id_especie)) == 2
    obligatorias = cat.vacunas_por_especie(datos.perro.id_especie, solo_obligatorias=True)
    assert [v.nombre for v in obligatorias] == ["Antirrábica"]
    assert obligatorias[0].obligatoria is True and obligatorias[0].refuerzo_dias == 365
    assert cat.buscar_transportista_por_documento("20333444").nombre == "Carlos Ruiz"


def test_catalogos_baja_con_referencias_falla(repos, datos) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        repos.catalogos.baja(datos.perro.id_especie, Especie)


# =============================================================================
#  RepositorioDerivaciones (orden, muestra, historial)
# =============================================================================

def nueva_muestra(datos, codigo: str = "M-0001") -> Muestra:
    return Muestra.nueva(codigo, datos.orden.id_orden, datos.hemograma.id_tipo_analisis,
                         "2026-10-22 10:20", "Ana Pérez", volumen_ml=3)


def test_ordenes(repos, datos) -> None:
    rep = repos.derivaciones
    orden = rep.obtener_por_id(datos.orden.id_orden)
    assert isinstance(orden, OrdenDerivacion) and orden.estado == "Emitida"
    orden.estado = "En proceso"
    rep.modificar(orden)
    assert [o.id_orden for o in rep.listar_ordenes_por_estado("En proceso")] == [orden.id_orden]
    assert len(rep.listar_ordenes_por_atencion(datos.atencion.id_atencion)) == 1


def test_agregar_muestra_inserta_historial_inicial(conexion: Conexion, repos, datos) -> None:
    muestra = nueva_muestra(datos)
    repos.derivaciones.agregar(muestra)
    assert muestra.id_muestra is not None
    assert contar(conexion, "historial_estado_muestra") == 1
    assert muestra.historial[0].persistido and muestra.historial[0].id_muestra == muestra.id_muestra


def test_transicion_guarda_estado_e_historial(conexion: Conexion, repos, datos) -> None:
    rep = repos.derivaciones
    muestra = nueva_muestra(datos)
    rep.agregar(muestra)

    muestra.empaquetar(datos.remito.id_remito, "Ana Pérez", "2026-10-22 10:40")
    rep.modificar(muestra)
    rep.modificar(muestra)  # guardar dos veces no duplica el historial

    leida = rep.obtener_por_id(muestra.id_muestra, Muestra)
    assert leida.estado_actual == "Empaquetada"
    assert leida.id_remito == datos.remito.id_remito
    assert [c.estado for c in leida.historial] == ["Extraída", "Empaquetada"]
    assert all(c.persistido for c in leida.historial)
    assert contar(conexion, "historial_estado_muestra") == 2


def test_muestra_leida_puede_seguir_transicionando(repos, datos) -> None:
    rep = repos.derivaciones
    muestra = nueva_muestra(datos)
    rep.agregar(muestra)
    muestra.empaquetar(datos.remito.id_remito, "Ana", "2026-10-22 10:40")
    rep.modificar(muestra)

    leida = rep.obtener_por_id(muestra.id_muestra, Muestra)
    leida.despachar("Carlos", "2026-10-22 11:00")
    rep.modificar(leida)
    assert [c.estado for c in rep.obtener_historial(muestra.id_muestra)] == [
        "Extraída", "Empaquetada", "En tránsito"
    ]


def test_muestras_busquedas(repos, datos) -> None:
    rep = repos.derivaciones
    m1, m2 = nueva_muestra(datos, "M-1"), nueva_muestra(datos, "M-2")
    rep.agregar(m1)
    rep.agregar(m2)
    m1.empaquetar(datos.remito.id_remito, "Ana", "2026-10-22 10:40")
    rep.modificar(m1)

    assert rep.buscar_muestra_por_codigo("M-2").id_muestra == m2.id_muestra
    assert len(rep.listar_muestras_por_orden(datos.orden.id_orden)) == 2
    assert [m.codigo for m in rep.listar_muestras_por_remito(datos.remito.id_remito)] == ["M-1"]
    assert [m.codigo for m in rep.listar_muestras_por_estado("Extraída")] == ["M-2"]
    assert len(rep.listar_muestras_por_atencion(datos.atencion.id_atencion)) == 2


def test_historial_no_admite_update_ni_delete_en_la_base(conexion: Conexion, repos, datos) -> None:
    repos.derivaciones.agregar(nueva_muestra(datos))
    cur = conexion.cursor()
    with pytest.raises(sqlite3.DatabaseError, match="inmutable"):
        cur.execute("UPDATE historial_estado_muestra SET responsable = ?", ("Otro",))
    with pytest.raises(sqlite3.DatabaseError, match="inmutable"):
        cur.execute("DELETE FROM historial_estado_muestra")


def test_repositorio_no_maneja_historial_por_abmc(repos) -> None:
    cambio = CambioEstadoMuestra(1, "Extraída", "2026-10-22 10:00", "Ana")
    with pytest.raises(TypeError):
        repos.derivaciones.agregar(cambio)
    with pytest.raises(TypeError):
        repos.derivaciones.baja(1, CambioEstadoMuestra)


def test_repositorio_solo_inserta_en_historial() -> None:
    codigo = inspect.getsource(modulo_derivaciones)
    assert re.search(r"INSERT INTO historial_estado_muestra", codigo)
    assert not re.search(r"(UPDATE|DELETE FROM)\s+historial_estado_muestra", codigo, re.IGNORECASE)


# =============================================================================
#  RepositorioEnvios
# =============================================================================

def test_envios_remito_precinto_tramos_recepcion(repos, datos) -> None:
    rep = repos.envios
    id_rem = datos.remito.id_remito
    rep.agregar(PrecintoSanitario("P-1", id_rem, "2026-10-22 10:45", temp_cierre=4))
    rep.agregar(TramoEnvio(id_rem, datos.transportista.id_transportista, 2, "Centro logístico", "LabVet",
                           "2026-10-22 12:00"))
    rep.agregar(TramoEnvio(id_rem, datos.transportista.id_transportista, 1, "Centro", "Centro logístico",
                           "2026-10-22 11:00", "2026-10-22 11:40", 5.0))
    rep.agregar(Recepcion(id_rem, "2026-10-22 13:00", "Lucía", "Intacto", aceptada=True))

    assert rep.obtener_precinto_por_remito(id_rem).numero == "P-1"
    assert [t.nro_tramo for t in rep.listar_tramos_por_remito(id_rem)] == [1, 2]
    assert rep.obtener_recepcion_por_remito(id_rem).aceptada is True
    assert rep.obtener_recepcion_por_remito(999) is None


def test_envios_estado_del_remito_se_persiste(repos, datos) -> None:
    rep = repos.envios
    remito = rep.obtener_por_id(datos.remito.id_remito)
    remito.despachar()
    rep.modificar(remito)
    leido = rep.buscar_remito_por_numero("REM-2026-00001")
    assert leido.estado == "En tránsito"
    leido.recibir(precinto_intacto=False)
    rep.modificar(leido)
    assert [r.numero for r in rep.listar_remitos_por_estado("Rechazado")] == ["REM-2026-00001"]
    assert len(rep.listar_remitos_por_rango("2026-10-01", "2026-11-01")) == 1


def test_envios_conservadoras_y_numeracion(repos, datos) -> None:
    rep = repos.envios
    rep.agregar(Conservadora("CONS-02", datos.clinica.id_clinica, 5, -20, -10, estado="En uso"))
    assert [c.codigo for c in rep.listar_conservadoras_disponibles()] == ["CONS-01"]
    assert rep.listar_conservadoras_disponibles(id_clinica=999) == []
    assert rep.buscar_conservadora_por_codigo("CONS-02").temp_min == -20

    rep.agregar(RemitoBiologico("REM-2026-00007", datos.clinica.id_clinica, datos.laboratorio.id_laboratorio,
                                datos.conservadora.id_conservadora, "2026-10-22"))
    assert rep.ultimo_numero_remito("REM-2026-") == "REM-2026-00007"
    assert rep.ultimo_numero_remito("REM-2027-") is None


# =============================================================================
#  RepositorioResultados
# =============================================================================

def test_resultados(repos, datos) -> None:
    muestra = nueva_muestra(datos)
    repos.derivaciones.agregar(muestra)
    resultado = ResultadoAnalisis(muestra.id_muestra, "2026-10-23 09:00", "Bioq. Díaz", "Hto 45%")
    repos.resultados.agregar(resultado)

    assert repos.resultados.obtener_por_muestra(muestra.id_muestra).valores == "Hto 45%"
    assert len(repos.resultados.listar_por_orden(datos.orden.id_orden)) == 1
    assert len(repos.resultados.listar_por_rango("2026-10-23", "2026-10-24")) == 1

    resultado.conclusion = "Normal"
    repos.resultados.modificar(resultado)
    assert repos.resultados.obtener_por_id(resultado.id_resultado).conclusion == "Normal"
    with pytest.raises(sqlite3.IntegrityError):  # UNIQUE(id_muestra)
        repos.resultados.agregar(ResultadoAnalisis(muestra.id_muestra, "2026-10-23 10:00", "X", "Y"))


# =============================================================================
#  RepositorioComprobantes
# =============================================================================

def test_comprobante_con_detalles(conexion: Conexion, repos, datos) -> None:
    rep = repos.comprobantes
    comprobante = Comprobante("C-2026-00001", datos.cliente.id_cliente, datos.clinica.id_clinica, "2026-10-22")
    comprobante.agregar_detalle(DetalleComprobante("Atención", "Consulta", 8000, id_atencion=datos.atencion.id_atencion))
    rep.agregar(comprobante)

    leido = rep.buscar_por_numero("C-2026-00001")
    assert leido.total == 8000
    assert [d.descripcion for d in leido.detalles] == ["Consulta"]
    assert rep.existe_para_atencion(datos.atencion.id_atencion)
    assert not rep.existe_para_atencion(999)

    leido.agregar_detalle(DetalleComprobante("Vacuna", "Antirrábica", 6000, id_atencion=datos.atencion.id_atencion))
    rep.modificar(leido)
    rep.modificar(leido)  # no duplica detalles
    releido = rep.obtener_por_id(comprobante.id_comprobante)
    assert releido.total == 14000 and len(releido.detalles) == 2
    assert contar(conexion, "detalle_comprobante") == 2


def test_comprobantes_consultas_y_baja(conexion: Conexion, repos, datos) -> None:
    rep = repos.comprobantes
    for numero, fecha in [("C-2026-00001", "2026-10-01"), ("C-2026-00002", "2026-10-22")]:
        c = Comprobante(numero, datos.cliente.id_cliente, datos.clinica.id_clinica, fecha)
        c.agregar_detalle(DetalleComprobante("Atención", "Consulta", 8000, id_atencion=datos.atencion.id_atencion))
        rep.agregar(c)

    assert len(rep.listar_por_cliente(datos.cliente.id_cliente)) == 2
    assert [c.numero for c in rep.listar_por_rango("2026-10-15", "2026-11-01")] == ["C-2026-00002"]
    assert rep.ultimo_numero("C-2026-") == "C-2026-00002"

    primero = rep.buscar_por_numero("C-2026-00001")
    rep.baja(primero.id_comprobante)
    assert rep.obtener_por_id(primero.id_comprobante) is None
    assert contar(conexion, "detalle_comprobante") == 1
