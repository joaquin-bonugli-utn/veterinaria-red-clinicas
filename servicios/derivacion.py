"""Casos de uso de derivación: emisión de órdenes y extracción de muestras."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from dominio import CambioEstadoMuestra, Laboratorio, Muestra, OrdenDerivacion, TipoAnalisis
from dominio import validaciones as v
from dominio.excepciones import ReglaNegocioError
from persistencia.repositorios import (
    RepositorioAtenciones,
    RepositorioCatalogos,
    RepositorioDerivaciones,
    RepositorioVeterinarios,
)
from servicios.base import ServicioBase


@dataclass
class OrdenEmitida:
    orden: OrdenDerivacion
    muestras: list[Muestra] = field(default_factory=list)


class ServicioDerivacion(ServicioBase):
    def __init__(
        self,
        repo_derivaciones: RepositorioDerivaciones | None = None,
        repo_atenciones: RepositorioAtenciones | None = None,
        repo_catalogos: RepositorioCatalogos | None = None,
        repo_veterinarios: RepositorioVeterinarios | None = None,
    ) -> None:
        self.derivaciones = repo_derivaciones or RepositorioDerivaciones()
        self.atenciones = repo_atenciones or RepositorioAtenciones()
        self.catalogos = repo_catalogos or RepositorioCatalogos()
        self.veterinarios = repo_veterinarios or RepositorioVeterinarios()

    def emitir_orden(
        self,
        id_atencion: int,
        id_laboratorio: int,
        muestras: Sequence[tuple[int, float | None]],
        *,
        prioridad: str = "Normal",
        indicaciones: str | None = None,
        fecha_hora_extraccion: str | None = None,
        responsable: str | None = None,
    ) -> OrdenEmitida:
        """Crea la orden y sus muestras en estado Extraída, cada una con su primer
        registro en el historial, en una sola transacción.

        muestras: [(id_tipo_analisis, volumen_ml), ...]. Por defecto la extracción
        ocurre en la fecha y hora de la atención y el responsable es su veterinario.
        """
        if not muestras:
            raise ReglaNegocioError("La orden debe incluir al menos una muestra.")
        try:
            atencion = self._requerir(self.atenciones.obtener_por_id(id_atencion), "la atención")
            self._requerir(self.catalogos.obtener_por_id(id_laboratorio, Laboratorio), "el laboratorio")
            for id_tipo, _ in muestras:
                self._requerir(self.catalogos.obtener_por_id(id_tipo, TipoAnalisis),
                               f"el tipo de análisis {id_tipo}")

            extraccion = v.fecha_hora_iso(fecha_hora_extraccion or atencion.fecha_hora, "fecha_hora_extraccion")
            if extraccion < atencion.fecha_hora:
                raise ReglaNegocioError("La extracción no puede ser anterior a la atención.")
            if responsable is None:
                responsable = self.veterinarios.obtener_por_id(atencion.id_veterinario).nombre_completo

            orden = OrdenDerivacion(id_atencion, id_laboratorio, extraccion[:10], prioridad, indicaciones)
            self.derivaciones.agregar(orden)

            creadas = []
            for numero, (id_tipo, volumen) in enumerate(muestras, start=1):
                muestra = Muestra.nueva(f"M-{orden.id_orden:05d}-{numero}", orden.id_orden, id_tipo,
                                        extraccion, responsable, volumen)
                self.derivaciones.agregar(muestra)  # inserta también el registro "Extraída"
                creadas.append(muestra)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
        return OrdenEmitida(orden, creadas)

    # --- Consultas ---------------------------------------------------------------------

    def obtener_orden(self, id_orden: int) -> OrdenDerivacion:
        return self._requerir(self.derivaciones.obtener_por_id(id_orden), "la orden")

    def listar_ordenes(self, estado: str | None = None) -> list[OrdenDerivacion]:
        """Todas las órdenes (o las de un estado), de la más reciente a la más antigua."""
        ordenes = self.derivaciones.listar_ordenes_por_estado(estado) if estado else self.derivaciones.listar()
        return sorted(ordenes, key=lambda o: (o.fecha_emision, o.id_orden), reverse=True)

    def ordenes_de_atencion(self, id_atencion: int) -> list[OrdenDerivacion]:
        return self.derivaciones.listar_ordenes_por_atencion(id_atencion)

    def obtener_muestra(self, id_muestra: int) -> Muestra:
        return self._requerir(self.derivaciones.obtener_por_id(id_muestra, Muestra), "la muestra")

    def muestras_de_orden(self, id_orden: int) -> list[Muestra]:
        return self.derivaciones.listar_muestras_por_orden(id_orden)

    def muestras_por_estado(self, estado: str) -> list[Muestra]:
        return self.derivaciones.listar_muestras_por_estado(estado)

    def historial_de_muestra(self, id_muestra: int) -> list[CambioEstadoMuestra]:
        return self.derivaciones.obtener_historial(id_muestra)
