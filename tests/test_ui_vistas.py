"""Tests de las vistas Flet (sin ventana) sobre los datos del seed: se completan los
controles y se invocan los manejadores como si el usuario hiciera clic."""

from datetime import date, timedelta

import flet as ft
import pytest

import reportes
from db.seed import cargar_datos
from servicios import (
    ServicioDerivacion,
    ServicioEnvios,
    ServicioFacturacion,
    ServicioLaboratorio,
    ServicioMascotas,
    ServicioTurnos,
)
from tests.pagina_falsa import PageFalsa
from ui.vista_atencion import VistaAtencion
from ui.vista_comprobantes import VistaComprobantes
from ui.vista_derivaciones import VistaDerivaciones
from ui.vista_envios import VistaEnvios
from ui.vista_laboratorio import VistaLaboratorio
from ui.vista_mascotas import VistaMascotas
from ui.vista_reportes import VistaReportes
from ui.vista_turnos import VistaTurnos

HOY = date.today()


@pytest.fixture
def seed(conexion):
    return cargar_datos(HOY)


@pytest.fixture
def page() -> PageFalsa:
    return PageFalsa()


def abrir(clase, page, **kwargs):
    vista = clase(page, **kwargs)
    _ = vista.control
    vista.al_mostrar()
    return vista


def textos(control) -> list[str]:
    """Todos los textos visibles dentro de un control (recorre el árbol)."""
    encontrados = []
    if isinstance(control, ft.Text) and control.value:
        encontrados.append(control.value)
    for atributo in ("content", "controls"):
        hijo = getattr(control, atributo, None)
        for h in (hijo if isinstance(hijo, list) else [hijo] if hijo is not None else []):
            if isinstance(h, ft.Control):
                encontrados += textos(h)
    return encontrados


def nueva_mascota(seed, nombre="Rayo", nacimiento=None):
    """Perro adulto sin vacunas: le corresponden Séxtuple y Antirrábica."""
    cliente = seed.mascotas[0].id_cliente
    return ServicioMascotas().alta(nombre, seed.especies["Perro"].id_especie,
                                   (nacimiento or HOY - timedelta(days=400)).isoformat(), cliente)


# =============================================================================
#  Mascotas
# =============================================================================

def test_mascotas_alta_y_responsable_obligatorio(seed, page) -> None:
    v = abrir(VistaMascotas, page)
    v.txt_nombre.value = "Rayo"
    v.dd_especie.value = str(seed.especies["Perro"].id_especie)
    v.fecha_nacimiento.valor = "2025-01-01"
    v._guardar()
    assert page.ultimo_fue_error and "cliente responsable" in page.ultimo_mensaje

    v.dd_cliente.value = str(seed.mascotas[0].id_cliente)
    v._guardar()
    assert not page.ultimo_fue_error and "Rayo registrada" in page.ultimo_mensaje
    assert "Rayo" in [f.cells[0].content.value for f in v.tabla.rows]


def test_mascotas_filtro_por_responsable_e_historia(seed, page) -> None:
    v = abrir(VistaMascotas, page)
    firulais = seed.mascotas[0]
    v.dd_filtro_cliente.value = str(firulais.id_cliente)
    v.cargar()
    assert {f.cells[0].content.value for f in v.tabla.rows} == {"Firulais", "Luna", "Michi"}

    v._historia(firulais)
    alergias = page.campos_dialogo()[0]
    alergias.value = "Polen"
    page.aceptar_dialogo()
    assert page.ultimo_mensaje == "Historia clínica actualizada."
    assert ServicioMascotas().obtener_historia(firulais.id_mascota).alergias == "Polen"


def test_mascotas_editar(seed, page) -> None:
    v = abrir(VistaMascotas, page)
    v._editar(ServicioMascotas().obtener(seed.mascotas[0].id_mascota))
    assert not v.fila_historia.visible and v.btn_cancelar.visible
    v.txt_peso.value = "19,5"
    v._guardar()
    assert page.ultimo_mensaje == "Cambios guardados."
    assert ServicioMascotas().obtener(seed.mascotas[0].id_mascota).peso_kg == 19.5


# =============================================================================
#  Turnos
# =============================================================================

def test_turnos_reservar_superposicion_y_estados(seed, page) -> None:
    v = abrir(VistaTurnos, page)
    dia = (HOY + timedelta(days=40)).isoformat()
    v.dd_vet.value = str(seed.veterinarios[0].id_veterinario)
    v.dd_mascota.value = str(seed.mascotas[0].id_mascota)
    v.fecha_turno.valor = dia
    v.txt_hora.value = "10:00"
    v._reservar()
    assert not page.ultimo_fue_error and "Turno reservado" in page.ultimo_mensaje
    assert v.fecha_agenda.valor == dia and len(v.tabla.rows) == 1

    v.txt_hora.value = "10:15"
    v._reservar()
    assert page.ultimo_fue_error and "se superpone" in page.ultimo_mensaje
    assert len(v.tabla.rows) == 1

    turno = ServicioTurnos().turnos_del_dia(dia)[0]
    v._reprogramar(turno)
    hora = page.campos_dialogo()[2]
    hora.value = "15:00"
    page.aceptar_dialogo()
    assert page.ultimo_mensaje == "Turno reprogramado."
    assert ServicioTurnos().obtener(turno.id_turno).fecha_hora_inicio == f"{dia} 15:00"

    v._cambiar(turno, "cancelar")
    page.aceptar_dialogo()
    assert ServicioTurnos().obtener(turno.id_turno).estado == "Cancelado"


def test_turnos_hora_invalida_y_navegacion(seed, page) -> None:
    v = abrir(VistaTurnos, page)
    v.dd_vet.value = str(seed.veterinarios[0].id_veterinario)
    v.dd_mascota.value = str(seed.mascotas[0].id_mascota)
    v.txt_hora.value = "diez"
    v._reservar()
    assert page.ultimo_fue_error and "HH:MM" in page.ultimo_mensaje
    v._mover_dia(1)
    assert v.fecha_agenda.valor == (HOY + timedelta(days=1)).isoformat()


# =============================================================================
#  Atención
# =============================================================================

def test_atencion_registrar_con_tratamiento_y_vacuna(seed, page) -> None:
    rayo = nueva_mascota(seed)
    v = abrir(VistaAtencion, page)
    v.dd_mascota.value = str(rayo.id_mascota)
    v._al_elegir_mascota()
    assert any("Séxtuple" in t for t in textos(v.panel_pendientes))

    v.dd_vet.value = str(seed.veterinarios[0].id_veterinario)
    v.dd_tipo.value = v._clave_tipo("Consulta")
    v.txt_hora.value = "10:00"
    v.txt_motivo.value = "Control"
    v.txt_medicamento.value, v.txt_dosis.value = "Meloxicam", "0,1 mg/kg"
    v._agregar_tratamiento()
    v.dd_vacuna.value = next(o.key for o in v.dd_vacuna.options if o.text.startswith("Séxtuple"))
    v.txt_lote.value = "L-77"
    v._agregar_vacuna()
    assert len(v.tabla_trat.rows) == 1 and len(v.tabla_vac.rows) == 1

    v._registrar()
    assert not page.ultimo_fue_error
    resumen = textos(page.dialogo_abierto.content)
    assert any("próxima dosis" in t for t in resumen)
    assert any("Antirrábica" in t for t in resumen)  # sigue pendiente (regla 6)
    assert len(v.tabla_historial.rows) == 1 and v.tabla_trat.rows == []


def test_atencion_con_turno_lo_marca_atendido(seed, page) -> None:
    rayo = nueva_mascota(seed)
    turno = ServicioTurnos().reservar(seed.veterinarios[1].id_veterinario, rayo.id_mascota,
                                      f"{HOY.isoformat()} 08:00", f"{HOY.isoformat()} 08:30")
    v = abrir(VistaAtencion, page)
    v.dd_mascota.value = str(rayo.id_mascota)
    v._al_elegir_mascota()
    v.dd_turno.value = str(turno.id_turno)
    v._al_elegir_turno()
    assert v.dd_vet.value == str(seed.veterinarios[1].id_veterinario) and v.txt_hora.value == "08:00"
    v.txt_motivo.value = "Consulta programada"
    v._registrar()
    assert not page.ultimo_fue_error
    assert ServicioTurnos().obtener(turno.id_turno).estado == "Atendido"


def test_atencion_validaciones(seed, page) -> None:
    v = abrir(VistaAtencion, page)
    v._registrar()
    assert page.ultimo_fue_error and "Elegí la mascota" in page.ultimo_mensaje
    v._agregar_tratamiento()
    assert "medicamento" in page.ultimo_mensaje


# =============================================================================
#  Derivaciones (línea de tiempo)
# =============================================================================

def hitos(linea: ft.Column) -> list[tuple[str, list[str]]]:
    """(estado, textos del detalle) de cada hito de la línea de tiempo."""
    return [(fila.controls[1].controls[0].value, textos(fila.controls[1])) for fila in linea.controls]


def test_derivaciones_emitir_orden_y_linea_de_tiempo(seed, page) -> None:
    v = abrir(VistaDerivaciones, page)
    v.dd_mascota.value = str(seed.mascotas[0].id_mascota)
    v._al_elegir_mascota()
    assert v.dd_atencion.value is not None
    v._emitir()
    assert page.ultimo_fue_error and "al menos una muestra" in page.ultimo_mensaje

    v.dd_tipo.value = str(seed.tipos_analisis["Hemograma completo"].id_tipo_analisis)
    v.txt_volumen.value = "3"
    v._agregar_muestra()
    v._emitir()
    assert not page.ultimo_fue_error and "emitida con 1 muestra" in page.ultimo_mensaje
    assert len(v.tabla_muestras.rows) == 1
    linea = hitos(v.panel_linea.content)
    assert [e for e, _ in linea] == ["Extraída", "Empaquetada", "En tránsito", "Recibida", "Analizada"]
    assert "Pendiente" in linea[1][1]  # lo que todavía no ocurrió se muestra atenuado


def test_derivaciones_linea_de_tiempo_con_precinto_roto(seed, page) -> None:
    v = abrir(VistaDerivaciones, page)
    muestra = ServicioEnvios().muestras_de_remito(seed.ids_destacados["remito_precinto_roto"])[0]
    v.seleccionar_orden(ServicioDerivacion().obtener_orden(muestra.id_orden))
    linea = hitos(v.panel_linea.content)
    assert [e for e, _ in linea] == ["Extraída", "Empaquetada", "En tránsito", "Rechazada"]
    assert any("Precinto roto" in t for t in linea[-1][1])

    v.dd_estado.value = "Finalizada"
    v.cargar()
    assert v.tabla_ordenes.rows and all(
        f.cells[5].content.content.value == "Finalizada" for f in v.tabla_ordenes.rows)


# =============================================================================
#  Envíos
# =============================================================================

def test_envios_empaquetar_y_primer_tramo(seed, page) -> None:
    v = abrir(VistaEnvios, page)
    v.dd_clinica.value = str(seed.clinicas[0].id_clinica)
    v._al_elegir_clinica()
    assert len(v._checks) == 2  # orden 10 (hemograma + urianálisis) de Sede Centro
    v._empaquetar()
    assert page.ultimo_fue_error and "Marcá al menos" in page.ultimo_mensaje

    for check in v._checks.values():
        check.value = True
    v.txt_precinto.value = "PS-UI-1"
    v.fecha_empaque.valor, v.hora_empaque.value = HOY.isoformat(), "23:00"
    v.txt_temp.value = "20"
    v._empaquetar()
    assert page.ultimo_fue_error and "fuera del rango" in page.ultimo_mensaje

    v.txt_temp.value = "4,5"
    v._empaquetar()
    assert not page.ultimo_fue_error and "generado con 2 muestra" in page.ultimo_mensaje
    remito = v._remito_sel
    assert v._checks == {}

    v.dd_transportista.value = str(seed.transportistas[0].id_transportista)
    v.txt_destino.value = "Laboratorio Central"
    v.fecha_salida.valor, v.hora_salida.value = HOY.isoformat(), "23:30"
    v._registrar_tramo(remito)
    assert page.ultimo_mensaje == "Tramo 1 registrado."
    assert ServicioEnvios().obtener_remito(remito.id_remito).estado == "En tránsito"


# =============================================================================
#  Laboratorio
# =============================================================================

def test_laboratorio_recepcion_con_precinto_roto(seed, page) -> None:
    v = abrir(VistaLaboratorio, page)
    remito = ServicioLaboratorio().remitos_en_transito()[0]
    assert len(v.tabla_remitos.rows) == 1
    v._recibir(remito)
    receptor, precinto, _temp, fecha, _boton, hora, _obs = page.campos_dialogo()
    formulario = page.dialogo_abierto
    receptor.value, precinto.value = "Lucía", False
    fecha.value, hora.value = HOY.isoformat(), "08:00"
    page.aceptar_dialogo()
    assert not formulario.open
    resumen = textos(page.dialogo_abierto.content)
    assert "Rechazado" in resumen and any("Precinto roto" in t for t in resumen)
    assert v.tabla_remitos.rows == []


def test_laboratorio_cargar_resultado(seed, page) -> None:
    v = abrir(VistaLaboratorio, page)
    muestra = ServicioLaboratorio().muestras_para_analizar()[0]
    v._resultado(muestra)
    bioq, valores, _concl, fecha, _boton, hora = page.campos_dialogo()
    bioq.value, fecha.value, hora.value = "Bioq. Méndez", HOY.isoformat(), "23:59"
    page.aceptar_dialogo()
    assert page.ultimo_fue_error and "valores" in page.ultimo_mensaje
    assert page.dialogo_abierto is not None  # el formulario queda abierto con lo cargado

    valores.value = "Hto 44 %"
    page.aceptar_dialogo()
    assert "pasó a Analizada" in page.ultimo_mensaje
    assert ServicioDerivacion().obtener_muestra(muestra.id_muestra).estado_actual == "Analizada"


# =============================================================================
#  Comprobantes
# =============================================================================

def test_comprobantes_facturar_pendiente(seed, page) -> None:
    v = abrir(VistaComprobantes, page)
    desde, hasta = v._rango()
    pendientes = ServicioFacturacion().atenciones_sin_facturar(desde, hasta)
    assert len(v.tabla_pendientes.rows) == len(pendientes) > 0
    atencion = pendientes[0]
    v._facturar(atencion)
    page.aceptar_dialogo()
    assert not page.ultimo_fue_error and "emitido por $" in page.ultimo_mensaje
    assert page.dialogo_abierto.title.value.startswith("Comprobante C-")
    assert ServicioFacturacion().esta_facturada(atencion.id_atencion)
    assert len(v.tabla_pendientes.rows) == len(pendientes) - 1
    assert "total $" in v.lbl_total.value


# =============================================================================
#  Reportes
# =============================================================================

def test_reportes_generar_y_abrir(seed, page, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(reportes, "CARPETA_SALIDA", tmp_path)
    abiertos = []
    v = abrir(VistaReportes, page, abrir=abiertos.append)
    v.generar("04_facturacion")
    assert not page.ultimo_fue_error
    assert abiertos == [tmp_path / "04_facturacion.pdf"] and abiertos[0].exists()

    v.dd_clinica.value = str(seed.clinicas[0].id_clinica)
    v.generar("01_atenciones_derivaciones")
    assert abiertos[-1].name == "01_atenciones_derivaciones_clinica1.pdf"

    v.hasta.valor = "2020-01-01"
    v.generar("02_rechazos_transporte")
    assert page.ultimo_fue_error and "anterior" in page.ultimo_mensaje


def test_reportes_generar_todos(seed, page, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(reportes, "CARPETA_SALIDA", tmp_path)
    abiertos = []
    v = abrir(VistaReportes, page, abrir=abiertos.append)
    v.generar_todos()
    assert len(list(tmp_path.glob("*.pdf"))) == 5
    assert abiertos == [tmp_path]  # abre la carpeta, no cada PDF
