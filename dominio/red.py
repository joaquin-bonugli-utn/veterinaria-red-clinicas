"""Entidades de la estructura de la red: clínicas, laboratorios y veterinarios."""

from __future__ import annotations

from dominio import validaciones as v


class Clinica:
    """Sede de la red de clínicas."""

    def __init__(
        self,
        nombre: str,
        direccion: str,
        telefono: str | None = None,
        id_clinica: int | None = None,
    ) -> None:
        self.id_clinica = v.id_opcional(id_clinica, "id_clinica")
        self.nombre = v.texto_obligatorio(nombre, "nombre")
        self.direccion = v.texto_obligatorio(direccion, "direccion")
        self.telefono = v.texto_opcional(telefono, "telefono")

    def __str__(self) -> str:
        return f"Clínica {self.nombre} ({self.direccion})"


class Laboratorio:
    """Laboratorio externo al que se derivan muestras."""

    def __init__(
        self,
        nombre: str,
        direccion: str,
        telefono: str | None = None,
        id_laboratorio: int | None = None,
    ) -> None:
        self.id_laboratorio = v.id_opcional(id_laboratorio, "id_laboratorio")
        self.nombre = v.texto_obligatorio(nombre, "nombre")
        self.direccion = v.texto_obligatorio(direccion, "direccion")
        self.telefono = v.texto_opcional(telefono, "telefono")

    def __str__(self) -> str:
        return f"Laboratorio {self.nombre} ({self.direccion})"


class Veterinario:
    """Profesional que trabaja en una clínica."""

    def __init__(
        self,
        matricula: str,
        nombre: str,
        apellido: str,
        id_clinica: int,
        especialidad: str | None = None,
        activo: bool = True,
        id_veterinario: int | None = None,
    ) -> None:
        self.id_veterinario = v.id_opcional(id_veterinario, "id_veterinario")
        self.matricula = v.texto_obligatorio(matricula, "matricula")
        self.nombre = v.texto_obligatorio(nombre, "nombre")
        self.apellido = v.texto_obligatorio(apellido, "apellido")
        self.id_clinica = v.id_obligatorio(id_clinica, "id_clinica")
        self.especialidad = v.texto_opcional(especialidad, "especialidad")
        self.activo = v.booleano(activo, "activo")

    @property
    def nombre_completo(self) -> str:
        return f"{self.apellido}, {self.nombre}"

    def __str__(self) -> str:
        return f"Dr/a. {self.nombre_completo} (MP {self.matricula})"
