"""Repositorio de mascotas y sus historias clínicas."""

from __future__ import annotations

from dominio import HistoriaClinica, Mascota
from persistencia.repositorios.base import RepositorioBase, Tabla


class RepositorioMascotas(RepositorioBase):
    TABLAS = (
        Tabla("mascota", "id_mascota", Mascota),
        Tabla("historia_clinica", "id_historia", HistoriaClinica),
    )
    PRINCIPAL = Mascota

    def listar_por_cliente(self, id_cliente: int, solo_activas: bool = True) -> list[Mascota]:
        condicion = "id_cliente = ?" + (" AND activo = 1" if solo_activas else "")
        return self._buscar(Mascota, condicion, (id_cliente,), orden="nombre")

    def buscar_por_nombre(self, texto: str, solo_activas: bool = True) -> list[Mascota]:
        condicion = "nombre LIKE ?" + (" AND activo = 1" if solo_activas else "")
        return self._buscar(Mascota, condicion, (f"%{texto.strip()}%",), orden="nombre")

    def listar_por_especie(self, id_especie: int, solo_activas: bool = True) -> list[Mascota]:
        condicion = "id_especie = ?" + (" AND activo = 1" if solo_activas else "")
        return self._buscar(Mascota, condicion, (id_especie,), orden="nombre")

    # --- Historia clínica ---------------------------------------------------------

    def obtener_historia(self, id_mascota: int) -> HistoriaClinica | None:
        """Historia clínica de la mascota (relación 1 a 1)."""
        return self._buscar_uno(HistoriaClinica, "id_mascota = ?", (id_mascota,))
