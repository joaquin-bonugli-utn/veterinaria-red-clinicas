"""Repositorio de órdenes de derivación, muestras y su historial de estados.

El historial de estados es INMUTABLE: este repositorio solo hace INSERT en
historial_estado_muestra (además la base lo impide con triggers). Al agregar o
modificar una muestra se insertan los cambios de su historial que todavía no
estaban guardados, así ``estado_actual`` y el historial quedan en la misma
transacción que abra el servicio.
"""

from __future__ import annotations

from typing import Any

from dominio import CambioEstadoMuestra, Muestra, OrdenDerivacion
from persistencia.repositorios.base import RepositorioBase, Tabla


class RepositorioDerivaciones(RepositorioBase):
    TABLAS = (
        Tabla("orden_derivacion", "id_orden", OrdenDerivacion),
        Tabla("muestra", "id_muestra", Muestra),
    )
    PRINCIPAL = OrdenDerivacion

    # --- ABMC: la muestra arrastra su historial -------------------------------------

    def agregar(self, entidad: Any) -> int:
        id_ = super().agregar(entidad)
        if isinstance(entidad, Muestra):
            self._insertar_historial_pendiente(entidad)
        return id_

    def modificar(self, entidad: Any) -> None:
        super().modificar(entidad)
        if isinstance(entidad, Muestra):
            self._insertar_historial_pendiente(entidad)

    def _completar(self, entidad: Any) -> None:
        if isinstance(entidad, Muestra):
            for cambio in self.obtener_historial(entidad.id_muestra):
                entidad.agregar_al_historial(cambio)

    # --- Historial (solo INSERT) ------------------------------------------------------

    def _insertar_historial_pendiente(self, muestra: Muestra) -> None:
        for cambio in muestra.historial:
            if not cambio.persistido:
                self._insertar_cambio(muestra.id_muestra, cambio)

    def _insertar_cambio(self, id_muestra: int, cambio: CambioEstadoMuestra) -> None:
        cursor = self._ejecutar(
            "INSERT INTO historial_estado_muestra (id_muestra, estado, fecha_hora, responsable, observacion) "
            "VALUES (?, ?, ?, ?, ?)",
            (id_muestra, cambio.estado, cambio.fecha_hora, cambio.responsable, cambio.observacion),
        )
        cambio.marcar_persistido(cursor.lastrowid, id_muestra)

    def obtener_historial(self, id_muestra: int) -> list[CambioEstadoMuestra]:
        filas = self._todos(
            "SELECT * FROM historial_estado_muestra WHERE id_muestra = ? ORDER BY fecha_hora, id_historial",
            (id_muestra,),
        )
        return [CambioEstadoMuestra(**dict(fila)) for fila in filas]

    # --- Órdenes ----------------------------------------------------------------------

    def listar_ordenes_por_atencion(self, id_atencion: int) -> list[OrdenDerivacion]:
        return self._buscar(OrdenDerivacion, "id_atencion = ?", (id_atencion,), orden="fecha_emision, id_orden")

    def listar_ordenes_por_estado(self, estado: str) -> list[OrdenDerivacion]:
        return self._buscar(OrdenDerivacion, "estado = ?", (estado,), orden="fecha_emision, id_orden")

    # --- Muestras ---------------------------------------------------------------------

    def buscar_muestra_por_codigo(self, codigo: str) -> Muestra | None:
        return self._buscar_uno(Muestra, "codigo = ?", (codigo.strip(),))

    def listar_muestras_por_orden(self, id_orden: int) -> list[Muestra]:
        return self._buscar(Muestra, "id_orden = ?", (id_orden,))

    def listar_muestras_por_remito(self, id_remito: int) -> list[Muestra]:
        return self._buscar(Muestra, "id_remito = ?", (id_remito,))

    def listar_muestras_por_estado(self, estado: str) -> list[Muestra]:
        return self._buscar(Muestra, "estado_actual = ?", (estado,), orden="fecha_hora_extraccion")

    def listar_muestras_por_atencion(self, id_atencion: int) -> list[Muestra]:
        return self._buscar(
            Muestra,
            "id_orden IN (SELECT id_orden FROM orden_derivacion WHERE id_atencion = ?)",
            (id_atencion,),
        )
