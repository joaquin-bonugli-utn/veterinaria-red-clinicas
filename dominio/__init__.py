"""Capa de dominio: entidades y reglas puras, sin SQL ni UI."""

from dominio.atencion import AplicacionVacuna, Atencion, TipoAtencion, Tratamiento, Turno, Vacuna
from dominio.clientes import Cliente, Especie, HistoriaClinica, Mascota
from dominio.derivacion import (
    CambioEstadoMuestra,
    Conservadora,
    Muestra,
    OrdenDerivacion,
    PrecintoSanitario,
    RemitoBiologico,
    TipoAnalisis,
)
from dominio.envio import Recepcion, ResultadoAnalisis, TramoEnvio, Transportista
from dominio.facturacion import Comprobante, DetalleComprobante
from dominio.red import Clinica, Laboratorio, Veterinario

__all__ = [
    "AplicacionVacuna", "Atencion", "CambioEstadoMuestra", "Cliente", "Clinica", "Comprobante",
    "Conservadora", "DetalleComprobante", "Especie", "HistoriaClinica", "Laboratorio", "Mascota",
    "Muestra", "OrdenDerivacion", "PrecintoSanitario", "Recepcion", "RemitoBiologico",
    "ResultadoAnalisis", "TipoAnalisis", "TipoAtencion", "TramoEnvio", "Transportista",
    "Tratamiento", "Turno", "Vacuna", "Veterinario",
]
