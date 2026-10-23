"""Fixtures compartidos de pytest."""

from collections.abc import Iterator
from types import SimpleNamespace

import pytest

from dominio import (
    Cliente,
    Clinica,
    Conservadora,
    Especie,
    Laboratorio,
    TipoAnalisis,
    TipoAtencion,
    Transportista,
    Vacuna,
    Veterinario,
)
from persistencia.conexion import Conexion
from persistencia.repositorios import (
    RepositorioCatalogos,
    RepositorioClientes,
    RepositorioEnvios,
    RepositorioVeterinarios,
)
from servicios import ServicioAtencion, ServicioMascotas

# Fecha y hora de la atención del fixture `lab` (y de la extracción de sus muestras).
EXTRACCION = "2026-10-22 10:00"


@pytest.fixture
def conexion() -> Iterator[Conexion]:
    """Base en memoria con el esquema cargado; se descarta al terminar el test."""
    con = Conexion.reiniciar_para_tests(":memory:")
    yield con
    con.cerrar()


@pytest.fixture
def catalogo(conexion: Conexion) -> SimpleNamespace:
    """Datos de referencia confirmados (commit), para que los rollbacks de los servicios no los borren."""
    cat = RepositorioCatalogos()
    d = SimpleNamespace()
    d.clinica = Clinica("Centro", "Av. Colón 100")
    d.clinica2 = Clinica("Norte", "Av. Rafael Núñez 4000")
    d.perro = Especie("Perro")
    d.gato = Especie("Gato")
    d.consulta = TipoAtencion("Consulta", 8000)
    d.urgencia = TipoAtencion("Urgencia", 12000)
    d.control = TipoAtencion("Control", 6000)
    for entidad in (d.clinica, d.clinica2, d.perro, d.gato, d.consulta, d.urgencia, d.control):
        cat.agregar(entidad)

    perro = d.perro.id_especie
    d.sextuple = Vacuna("Séxtuple", perro, 7000, obligatoria=True, edad_minima_dias=45, refuerzo_dias=365)
    d.antirrabica = Vacuna("Antirrábica", perro, 6000, obligatoria=True, edad_minima_dias=90, refuerzo_dias=365)
    d.lepto = Vacuna("Leptospirosis", perro, 5000, obligatoria=True, edad_minima_dias=60)  # dosis única
    d.giardia = Vacuna("Giardia", perro, 4000, obligatoria=False, edad_minima_dias=60, refuerzo_dias=365)
    d.triple_felina = Vacuna("Triple felina", d.gato.id_especie, 6500, obligatoria=True, edad_minima_dias=60,
                             refuerzo_dias=365)
    for vacuna in (d.sextuple, d.antirrabica, d.lepto, d.giardia, d.triple_felina):
        cat.agregar(vacuna)

    d.vet = Veterinario("MP-1", "Ana", "Pérez", d.clinica.id_clinica)
    d.vet2 = Veterinario("MP-2", "Luis", "Álvarez", d.clinica2.id_clinica)
    d.vet_inactivo = Veterinario("MP-3", "Rosa", "Díaz", d.clinica.id_clinica, activo=False)
    for vet in (d.vet, d.vet2, d.vet_inactivo):
        RepositorioVeterinarios().agregar(vet)

    d.cliente = Cliente("30111222", "Juan", "Gómez")
    d.cliente_inactivo = Cliente("28999888", "Marta", "López", activo=False)
    for cliente in (d.cliente, d.cliente_inactivo):
        RepositorioClientes().agregar(cliente)

    conexion.commit()
    return d


@pytest.fixture
def lab(catalogo, conexion) -> SimpleNamespace:
    """Catálogo + laboratorio, tipos de análisis, conservadoras, transportista y una atención confirmados."""
    d =SimpleNamespace(**vars(catalogo))
    cat, env = RepositorioCatalogos(), RepositorioEnvios()
    d.laboratorio = Laboratorio("LabVet Central", "Bv. San Juan 50")
    d.laboratorio2 = Laboratorio("Lab Norte", "Av. Monseñor Pablo Cabrera 3000")
    d.hemograma = TipoAnalisis("Hemograma", "Sangre", 2, 8, 24, 5000)
    d.bioquimica = TipoAnalisis("Bioquímica", "Sangre", 2, 8, 48, 7000)
    d.urianalisis = TipoAnalisis("Urianálisis", "Orina", 2, 8, 4, 3000)
    d.transportista = Transportista("20333444", "Carlos Ruiz", vehiculo="Moto")
    for entidad in (d.laboratorio, d.laboratorio2, d.hemograma, d.bioquimica, d.urianalisis, d.transportista):
        cat.agregar(entidad)
    d.cons_a = Conservadora("CONS-A", d.clinica.id_clinica, capacidad=3, temp_min=0, temp_max=30)
    d.cons_b = Conservadora("CONS-B", d.clinica.id_clinica, capacidad=1, temp_min=2, temp_max=6)
    d.cons_fuera = Conservadora("CONS-C", d.clinica.id_clinica, 5, 2, 8, estado="Fuera de servicio")
    d.cons_norte = Conservadora("CONS-N", d.clinica2.id_clinica, 5, 2, 8)
    for cons in (d.cons_a, d.cons_b, d.cons_fuera, d.cons_norte):
        env.agregar(cons)
    conexion.commit()

    d.mascota = ServicioMascotas().alta("Firulais", d.perro.id_especie, "2024-01-01", d.cliente.id_cliente)
    d.atencion = ServicioAtencion().registrar(d.mascota.id_mascota, d.vet.id_veterinario,
                                              d.consulta.id_tipo_atencion, EXTRACCION, "Decaimiento").atencion
    return d
