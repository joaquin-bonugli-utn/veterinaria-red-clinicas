"""Test de integración: la carga de datos de prueba recorre todos los servicios sin violar reglas."""

from datetime import date

import pytest

from db.seed import cargar_datos
from dominio import Muestra
from persistencia.conexion import Conexion
from persistencia.repositorios import RepositorioDerivaciones, RepositorioEnvios

HOY = date(2026, 10, 23)


@pytest.fixture
def cargado(conexion: Conexion):
    return cargar_datos(HOY)


def test_cantidades_pedidas(conexion: Conexion, cargado) -> None:
    n = conexion.cantidades_por_tabla()
    assert (n["clinica"], n["laboratorio"], n["veterinario"], n["especie"]) == (3, 1, 6, 3)
    assert (n["cliente"], n["mascota"], n["historia_clinica"]) == (15, 25, 25)
    assert (n["orden_derivacion"], n["remito_biologico"], n["precinto_sanitario"]) == (10, 5, 5)
    assert n["tramo_envio"] >= 5
    for tabla in ("turno", "atencion", "aplicacion_vacuna", "resultado_analisis", "comprobante"):
        assert n[tabla] > 0, tabla


def test_casos_destacados(cargado) -> None:
    env, der = RepositorioEnvios(), RepositorioDerivaciones()
    roto = env.obtener_por_id(cargado.ids_destacados["remito_precinto_roto"])
    assert roto.estado == "Rechazado"
    assert env.obtener_precinto_por_remito(roto.id_remito).roto
    assert {m.estado_actual for m in der.listar_muestras_por_remito(roto.id_remito)} == {"Rechazada"}

    vencida = env.obtener_por_id(cargado.ids_destacados["remito_viabilidad_vencida"])
    muestras = der.listar_muestras_por_remito(vencida.id_remito)
    assert vencida.estado == "Recibido"
    assert any(m.estado_actual == "Rechazada" and "Viabilidad vencida" in m.ultimo_cambio.observacion
               for m in muestras)


def test_todas_las_muestras_tienen_historial_coherente(cargado) -> None:
    der = RepositorioDerivaciones()
    for muestra in der.listar(Muestra):
        historial = muestra.historial
        assert historial[0].estado == "Extraída"
        assert historial[-1].estado == muestra.estado_actual


def test_es_reproducible(conexion: Conexion) -> None:
    primera = (cargar_datos(HOY), conexion.cantidades_por_tabla())[1]
    Conexion.reiniciar_para_tests()
    segunda = (cargar_datos(HOY), Conexion.obtener().cantidades_por_tabla())[1]
    assert primera == segunda
