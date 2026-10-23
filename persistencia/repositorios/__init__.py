"""Repositorios: ABMC y consultas por agregado. Devuelven objetos de dominio y no hacen commit."""

from persistencia.repositorios.atenciones import RepositorioAtenciones
from persistencia.repositorios.base import RegistroNoEncontradoError, RepositorioBase
from persistencia.repositorios.catalogos import RepositorioCatalogos
from persistencia.repositorios.clientes import RepositorioClientes
from persistencia.repositorios.comprobantes import RepositorioComprobantes
from persistencia.repositorios.derivaciones import RepositorioDerivaciones
from persistencia.repositorios.envios import RepositorioEnvios
from persistencia.repositorios.mascotas import RepositorioMascotas
from persistencia.repositorios.reportes import RepositorioReportes
from persistencia.repositorios.resultados import RepositorioResultados
from persistencia.repositorios.turnos import RepositorioTurnos
from persistencia.repositorios.veterinarios import RepositorioVeterinarios

__all__ = [
    "RegistroNoEncontradoError", "RepositorioAtenciones", "RepositorioBase", "RepositorioCatalogos",
    "RepositorioClientes", "RepositorioComprobantes", "RepositorioDerivaciones", "RepositorioEnvios",
    "RepositorioMascotas", "RepositorioReportes", "RepositorioResultados", "RepositorioTurnos", "RepositorioVeterinarios",
]
