"""Repositorio de la cadena de envío: conservadoras, remitos, precintos, tramos y recepciones."""

from __future__ import annotations

from dominio import Conservadora, PrecintoSanitario, Recepcion, RemitoBiologico, TramoEnvio
from persistencia.repositorios.base import RepositorioBase, Tabla


class RepositorioEnvios(RepositorioBase):
    TABLAS = (
        Tabla("remito_biologico", "id_remito", RemitoBiologico),
        Tabla("conservadora", "id_conservadora", Conservadora),
        Tabla("precinto_sanitario", "id_precinto", PrecintoSanitario),
        Tabla("tramo_envio", "id_tramo", TramoEnvio),
        Tabla("recepcion", "id_recepcion", Recepcion),
    )
    PRINCIPAL = RemitoBiologico

    # --- Conservadoras ----------------------------------------------------------------

    def buscar_conservadora_por_codigo(self, codigo: str) -> Conservadora | None:
        return self._buscar_uno(Conservadora, "codigo = ?", (codigo.strip(),))

    def listar_conservadoras_disponibles(self, id_clinica: int | None = None) -> list[Conservadora]:
        condicion = "estado = 'Disponible'"
        parametros: list = []
        if id_clinica is not None:
            condicion += " AND id_clinica = ?"
            parametros.append(id_clinica)
        return self._buscar(Conservadora, condicion, parametros, orden="codigo")

    # --- Remitos ----------------------------------------------------------------------

    def buscar_remito_por_numero(self, numero: str) -> RemitoBiologico | None:
        return self._buscar_uno(RemitoBiologico, "numero = ?", (numero.strip(),))

    def listar_remitos_por_estado(self, estado: str) -> list[RemitoBiologico]:
        return self._buscar(RemitoBiologico, "estado = ?", (estado,), orden="fecha_emision, id_remito")

    def listar_remitos_por_rango(self, desde: str, hasta: str) -> list[RemitoBiologico]:
        return self._buscar(
            RemitoBiologico, "fecha_emision >= ? AND fecha_emision < ?", (desde, hasta),
            orden="fecha_emision, id_remito",
        )

    def ultimo_numero_remito(self, prefijo: str) -> str | None:
        """Mayor número de remito que empieza con `prefijo` (p. ej. 'REM-2026-')."""
        return self._escalar(
            "SELECT MAX(numero) FROM remito_biologico WHERE numero LIKE ?", (f"{prefijo}%",)
        )

    # --- Precinto, tramos y recepción (1 por remito, salvo tramos) ---------------------

    def obtener_precinto_por_remito(self, id_remito: int) -> PrecintoSanitario | None:
        return self._buscar_uno(PrecintoSanitario, "id_remito = ?", (id_remito,))

    def buscar_precinto_por_numero(self, numero: str) -> PrecintoSanitario | None:
        return self._buscar_uno(PrecintoSanitario, "numero = ?", (numero.strip(),))

    def listar_tramos_por_remito(self, id_remito: int) -> list[TramoEnvio]:
        return self._buscar(TramoEnvio, "id_remito = ?", (id_remito,), orden="nro_tramo")

    def obtener_recepcion_por_remito(self, id_remito: int) -> Recepcion | None:
        return self._buscar_uno(Recepcion, "id_remito = ?", (id_remito,))
