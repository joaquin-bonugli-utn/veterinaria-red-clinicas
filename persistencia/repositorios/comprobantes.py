"""Repositorio de comprobantes y sus detalles.

Al agregar o modificar un comprobante se insertan los detalles que todavía no
tienen id. La baja borra primero los detalles y luego la cabecera (el servicio
debe envolverla en una transacción).
"""

from __future__ import annotations

from typing import Any

from dominio import Comprobante, DetalleComprobante
from persistencia.repositorios.base import RepositorioBase, Tabla


class RepositorioComprobantes(RepositorioBase):
    TABLAS = (
        Tabla("comprobante", "id_comprobante", Comprobante),
        Tabla("detalle_comprobante", "id_detalle", DetalleComprobante),
    )
    PRINCIPAL = Comprobante

    # --- ABMC: el comprobante arrastra sus detalles -----------------------------------

    def agregar(self, entidad: Any) -> int:
        id_ = super().agregar(entidad)
        if isinstance(entidad, Comprobante):
            self._insertar_detalles_pendientes(entidad)
        return id_

    def modificar(self, entidad: Any) -> None:
        super().modificar(entidad)
        if isinstance(entidad, Comprobante):
            self._insertar_detalles_pendientes(entidad)

    def baja(self, id_: int, clase: type | None = None) -> None:
        if clase in (None, Comprobante):
            self._ejecutar("DELETE FROM detalle_comprobante WHERE id_comprobante = ?", (id_,))
        super().baja(id_, clase)

    def _completar(self, entidad: Any) -> None:
        if isinstance(entidad, Comprobante):
            entidad.detalles.extend(self.listar_detalles(entidad.id_comprobante))

    def _insertar_detalles_pendientes(self, comprobante: Comprobante) -> None:
        for detalle in comprobante.detalles:
            if detalle.id_detalle is None:
                detalle.id_comprobante = comprobante.id_comprobante
                super().agregar(detalle)

    # --- Consultas --------------------------------------------------------------------

    def listar_detalles(self, id_comprobante: int) -> list[DetalleComprobante]:
        return self._buscar(DetalleComprobante, "id_comprobante = ?", (id_comprobante,))

    def buscar_por_numero(self, numero: str) -> Comprobante | None:
        return self._buscar_uno(Comprobante, "numero = ?", (numero.strip(),))

    def listar_por_cliente(self, id_cliente: int) -> list[Comprobante]:
        return self._buscar(Comprobante, "id_cliente = ?", (id_cliente,), orden="fecha_emision, id_comprobante")

    def listar_por_rango(self, desde: str, hasta: str, id_clinica: int | None = None) -> list[Comprobante]:
        condicion = "fecha_emision >= ? AND fecha_emision < ?"
        parametros: list = [desde, hasta]
        if id_clinica is not None:
            condicion += " AND id_clinica = ?"
            parametros.append(id_clinica)
        return self._buscar(Comprobante, condicion, parametros, orden="fecha_emision, id_comprobante")

    def existe_para_atencion(self, id_atencion: int) -> bool:
        """True si la atención ya fue facturada (para no facturarla dos veces)."""
        return self._escalar(
            "SELECT 1 FROM detalle_comprobante WHERE id_atencion = ? AND tipo_item = 'Atención' LIMIT 1",
            (id_atencion,),
        ) is not None

    def ultimo_numero(self, prefijo: str) -> str | None:
        """Mayor número de comprobante que empieza con `prefijo` (p. ej. 'C-2026-')."""
        return self._escalar("SELECT MAX(numero) FROM comprobante WHERE numero LIKE ?", (f"{prefijo}%",))
