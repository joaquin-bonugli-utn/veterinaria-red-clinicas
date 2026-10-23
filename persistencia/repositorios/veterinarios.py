"""Repositorio de veterinarios."""

from __future__ import annotations

from dominio import Veterinario
from persistencia.repositorios.base import RepositorioBase, Tabla


class RepositorioVeterinarios(RepositorioBase):
    TABLAS = (Tabla("veterinario", "id_veterinario", Veterinario),)
    PRINCIPAL = Veterinario

    def buscar_por_matricula(self, matricula: str) -> Veterinario | None:
        return self._buscar_uno(Veterinario, "matricula = ?", (matricula.strip(),))

    def listar_por_clinica(self, id_clinica: int, solo_activos: bool = True) -> list[Veterinario]:
        condicion = "id_clinica = ?" + (" AND activo = 1" if solo_activos else "")
        return self._buscar(Veterinario, condicion, (id_clinica,), orden="apellido, nombre")

    def buscar_por_apellido(self, texto: str, solo_activos: bool = True) -> list[Veterinario]:
        condicion = "apellido LIKE ?" + (" AND activo = 1" if solo_activos else "")
        return self._buscar(Veterinario, condicion, (f"{texto.strip()}%",), orden="apellido, nombre")
