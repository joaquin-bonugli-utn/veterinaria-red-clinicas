"""Prueba de punta a punta de los 7 procesos del sistema, usando SOLO la capa de servicios
(como lo hace la UI), sobre una base vacía en memoria.

1. Alta de cliente y mascota (con historia clínica)   5. Recepción en laboratorio
2. Reserva de turno                                    6. Carga de resultados
3. Atención clínica con tratamiento y vacunas          7. Facturación
4. Derivación: orden, empaquetado y envío
Al final se generan los 5 reportes con los datos producidos.
"""

from datetime import date, timedelta

import pytest

from dominio import Clinica, Conservadora, Especie, Laboratorio, TipoAnalisis, TipoAtencion, Transportista, Vacuna
from dominio.excepciones import PrecintoRotoError, ReglaNegocioError, TurnoSuperpuestoError
from servicios import (
    ServicioAtencion,
    ServicioCatalogos,
    ServicioClientes,
    ServicioDerivacion,
    ServicioEnvios,
    ServicioFacturacion,
    ServicioLaboratorio,
    ServicioMascotas,
    ServicioReportes,
    ServicioTurnos,
    ServicioVeterinarios,
    TratamientoIndicado,
    VacunaAAplicar,
)

DIA = "2026-10-20"


@pytest.fixture
def red(conexion):
    """Catálogo mínimo dado de alta por servicios."""
    cat = ServicioCatalogos()
    clinica = cat.alta(Clinica("Sede Centro", "Av. Colón 1250"))
    laboratorio = cat.alta(Laboratorio("Lab Central", "Av. Vélez Sarsfield 2100"))
    perro = cat.alta(Especie("Perro"))
    antirrabica = cat.alta(Vacuna("Antirrábica", perro.id_especie, 7000, True, 90, 365))
    sextuple = cat.alta(Vacuna("Séxtuple", perro.id_especie, 9500, True, 45, 365))
    consulta = cat.alta(TipoAtencion("Consulta", 15000))
    hemograma = cat.alta(TipoAnalisis("Hemograma", "Sangre", 2, 8, 24, 18500))
    urianalisis = cat.alta(TipoAnalisis("Urianálisis", "Orina", 2, 8, 6, 12500))
    transportista = cat.alta(Transportista("20311222", "Carlos Ruiz"))
    conservadora = cat.alta(Conservadora("CONS-1", clinica.id_clinica, 4, 2, 8))
    vet = ServicioVeterinarios().alta("MP-1", "Ana", "Pérez", clinica.id_clinica)
    return locals()


def test_los_siete_procesos_de_punta_a_punta(red, tmp_path) -> None:
    # 1. Cliente y mascota (regla 1: responsable obligatorio; historia en la misma transacción)
    cliente = ServicioClientes().alta("30111222", "Juan", "Gómez")
    nacimiento = (date.fromisoformat(DIA) - timedelta(days=400)).isoformat()
    mascota = ServicioMascotas().alta("Firulais", red["perro"].id_especie, nacimiento, cliente.id_cliente)
    assert ServicioMascotas().obtener_historia(mascota.id_mascota) is not None

    # 2. Turno (regla 5: sin superposición)
    turnos = ServicioTurnos()
    turno = turnos.reservar(red["vet"].id_veterinario, mascota.id_mascota, f"{DIA} 08:00", f"{DIA} 08:30")
    with pytest.raises(TurnoSuperpuestoError):
        turnos.reservar(red["vet"].id_veterinario, mascota.id_mascota, f"{DIA} 08:15", f"{DIA} 08:45")

    # 3. Atención (regla 6: vacunas pendientes según especie y edad)
    resultado = ServicioAtencion().registrar(
        mascota.id_mascota, red["vet"].id_veterinario, red["consulta"].id_tipo_atencion, f"{DIA} 08:05",
        "Decaimiento", id_turno=turno.id_turno,
        tratamientos=[TratamientoIndicado("Meloxicam", "0,1 mg/kg", "cada 24 h")],
        vacunas=[VacunaAAplicar(red["antirrabica"].id_vacuna, "L-1")],
    )
    atencion = resultado.atencion
    assert turnos.obtener(turno.id_turno).estado == "Atendido"
    assert [p.vacuna.nombre for p in resultado.vacunas_pendientes] == ["Séxtuple"]

    # 4. Derivación: orden + muestras (State: Extraída), empaquetado (regla 7) y tramos (En tránsito)
    emitida = ServicioDerivacion().emitir_orden(
        atencion.id_atencion, red["laboratorio"].id_laboratorio,
        [(red["hemograma"].id_tipo_analisis, 3.0), (red["urianalisis"].id_tipo_analisis, 10.0)])
    envios = ServicioEnvios()
    remito = envios.empaquetar([m.id_muestra for m in emitida.muestras], red["conservadora"].id_conservadora,
                               "PS-1", 4.5, fecha_hora=f"{DIA} 09:00")
    assert remito.numero == "REM-2026-00001"
    envios.registrar_tramo(remito.id_remito, red["transportista"].id_transportista, "Sede Centro", "Lab Central",
                           f"{DIA} 09:30", f"{DIA} 10:30", 5.0)
    assert envios.obtener_remito(remito.id_remito).estado == "En tránsito"

    # 5. Recepción (precinto intacto): el urianálisis (6 h) llega con la viabilidad vencida
    recibido = ServicioLaboratorio().recibir(remito.id_remito, "Lucía", True, 5.0, fecha_hora=f"{DIA} 15:00")
    assert [m.codigo for m in recibido.aceptadas] == [emitida.muestras[0].codigo]
    assert "Viabilidad vencida" in recibido.rechazadas[0].ultimo_cambio.observacion

    # 6. Resultado: la orden se finaliza (una analizada, otra rechazada)
    ServicioLaboratorio().registrar_resultado(emitida.muestras[0].id_muestra, "Bioq. Díaz", "Hto 45 %",
                                              fecha_hora=f"{DIA} 18:00")
    assert ServicioDerivacion().obtener_orden(emitida.orden.id_orden).estado == "Finalizada"
    historial = ServicioDerivacion().historial_de_muestra(emitida.muestras[0].id_muestra)
    assert [c.estado for c in historial] == ["Extraída", "Empaquetada", "En tránsito", "Recibida", "Analizada"]

    # 7. Facturación (Strategy: tarifa normal; excluye la muestra rechazada; no se factura dos veces)
    facturacion = ServicioFacturacion()
    comprobante = facturacion.emitir_comprobante(atencion.id_atencion, DIA)
    assert {d.tipo_item for d in comprobante.detalles} == {"Atención", "Vacuna", "Análisis"}
    assert comprobante.total == 15000 + 7000 + 18500
    with pytest.raises(ReglaNegocioError, match="ya fue facturada"):
        facturacion.emitir_comprobante(atencion.id_atencion, DIA)

    # Reportes con lo producido
    servicio_reportes = ServicioReportes()
    rutas = [servicio_reportes.generar(r.clave, "2026-10-01", "2026-10-31", carpeta=tmp_path)
             for r in servicio_reportes.disponibles()]
    assert len(rutas) == 5 and all(r.read_bytes().startswith(b"%PDF") for r in rutas)


def test_precinto_roto_de_punta_a_punta(red) -> None:
    """Regla 2: remito Rechazado, todas las muestras Rechazada y sin carga de resultados."""
    cliente = ServicioClientes().alta("30111222", "Juan", "Gómez")
    mascota = ServicioMascotas().alta("Firulais", red["perro"].id_especie, "2024-01-01", cliente.id_cliente)
    atencion = ServicioAtencion().registrar(mascota.id_mascota, red["vet"].id_veterinario,
                                            red["consulta"].id_tipo_atencion, f"{DIA} 08:00", "Control").atencion
    emitida = ServicioDerivacion().emitir_orden(atencion.id_atencion, red["laboratorio"].id_laboratorio,
                                                [(red["hemograma"].id_tipo_analisis, 3.0)])
    envios = ServicioEnvios()
    remito = envios.empaquetar([emitida.muestras[0].id_muestra], red["conservadora"].id_conservadora, "PS-9", 4,
                               fecha_hora=f"{DIA} 08:30")
    envios.registrar_tramo(remito.id_remito, red["transportista"].id_transportista, "A", "B",
                           f"{DIA} 09:00", f"{DIA} 10:00")
    ServicioLaboratorio().recibir(remito.id_remito, "Lucía", False, 5.0, fecha_hora=f"{DIA} 10:30")

    assert envios.obtener_remito(remito.id_remito).estado == "Rechazado"
    assert envios.obtener_precinto(remito.id_remito).estado == "Roto"
    assert ServicioDerivacion().obtener_muestra(emitida.muestras[0].id_muestra).estado_actual == "Rechazada"
    assert envios.conservadoras_disponibles()[0].id_conservadora == red["conservadora"].id_conservadora
    with pytest.raises(PrecintoRotoError):
        ServicioLaboratorio().registrar_resultado(emitida.muestras[0].id_muestra, "Bioq.", "x")
