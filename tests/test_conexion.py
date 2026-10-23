"""Tests del Singleton de conexión y del esquema."""

import threading

import pytest

from persistencia.conexion import Conexion

TABLAS_ESPERADAS = {
    "clinica", "laboratorio", "veterinario",
    "cliente", "especie", "mascota", "historia_clinica",
    "turno", "tipo_atencion", "atencion", "vacuna", "aplicacion_vacuna", "tratamiento",
    "tipo_analisis", "orden_derivacion", "conservadora", "remito_biologico",
    "precinto_sanitario", "muestra", "historial_estado_muestra",
    "transportista", "tramo_envio", "recepcion", "resultado_analisis",
    "comprobante", "detalle_comprobante",
}


def test_obtener_devuelve_siempre_la_misma_instancia(conexion: Conexion) -> None:
    assert Conexion.obtener() is Conexion.obtener()
    assert Conexion.obtener() is conexion


def test_no_se_puede_instanciar_directamente() -> None:
    with pytest.raises(TypeError, match="Singleton"):
        Conexion(":memory:")


def test_se_puede_usar_desde_otro_hilo(conexion: Conexion) -> None:
    """Flet ejecuta los manejadores de eventos en hilos de un ThreadPoolExecutor."""
    resultado = []

    def consultar() -> None:
        try:
            resultado.append(Conexion.obtener().cursor().execute("SELECT 1").fetchone()[0])
        except Exception as error:  # noqa: BLE001
            resultado.append(error)

    hilo = threading.Thread(target=consultar)
    hilo.start()
    hilo.join()
    assert resultado == [1]


def test_claves_foraneas_activas(conexion: Conexion) -> None:
    fila = conexion.cursor().execute("PRAGMA foreign_keys").fetchone()
    assert fila[0] == 1


def test_existen_las_26_tablas(conexion: Conexion) -> None:
    filas = conexion.cursor().execute(
        "SELECT name FROM sqlite_master WHERE type = ? AND name NOT LIKE ?",
        ("table", "sqlite_%"),
    ).fetchall()
    tablas = {fila["name"] for fila in filas}
    assert len(tablas) == 26
    assert tablas == TABLAS_ESPERADAS
