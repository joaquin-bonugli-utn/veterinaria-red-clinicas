"""Entidades de clientes, mascotas e historias clínicas."""

from __future__ import annotations

from datetime import date

from dominio import validaciones as v


class Cliente:
    """Responsable de una o más mascotas."""

    def __init__(
        self,
        dni: str,
        nombre: str,
        apellido: str,
        telefono: str | None = None,
        email: str | None = None,
        direccion: str | None = None,
        activo: bool = True,
        id_cliente: int | None = None,
    ) -> None:
        self.id_cliente = v.id_opcional(id_cliente, "id_cliente")
        self.dni = v.texto_obligatorio(dni, "dni")
        if not self.dni.isdigit():
            raise ValueError("El DNI debe contener solo dígitos.")
        self.nombre = v.texto_obligatorio(nombre, "nombre")
        self.apellido = v.texto_obligatorio(apellido, "apellido")
        self.telefono = v.texto_opcional(telefono, "telefono")
        self.email = v.texto_opcional(email, "email")
        if self.email is not None and "@" not in self.email:
            raise ValueError(f"El email {self.email!r} no es válido.")
        self.direccion = v.texto_opcional(direccion, "direccion")
        self.activo = v.booleano(activo, "activo")

    @property
    def nombre_completo(self) -> str:
        return f"{self.apellido}, {self.nombre}"

    def __str__(self) -> str:
        return f"{self.nombre_completo} (DNI {self.dni})"


class Especie:
    """Especie animal (perro, gato...)."""

    def __init__(self, nombre: str, id_especie: int | None = None) -> None:
        self.id_especie = v.id_opcional(id_especie, "id_especie")
        self.nombre = v.texto_obligatorio(nombre, "nombre")

    def __str__(self) -> str:
        return self.nombre


class Mascota:
    """Paciente de la veterinaria. Siempre tiene un cliente responsable."""

    SEXOS = ("M", "H")

    def __init__(
        self,
        nombre: str,
        id_especie: int,
        fecha_nacimiento: str,
        id_cliente: int,
        raza: str | None = None,
        sexo: str | None = None,
        peso_kg: float | None = None,
        activo: bool = True,
        id_mascota: int | None = None,
    ) -> None:
        if id_cliente is None:
            raise ValueError("Toda mascota debe tener un cliente responsable.")
        self.id_mascota = v.id_opcional(id_mascota, "id_mascota")
        self.nombre = v.texto_obligatorio(nombre, "nombre")
        self.id_especie = v.id_obligatorio(id_especie, "id_especie")
        self.id_cliente = v.id_obligatorio(id_cliente, "id_cliente")
        self.fecha_nacimiento = v.fecha_iso(fecha_nacimiento, "fecha_nacimiento")
        if v.a_fecha(self.fecha_nacimiento) > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura.")
        self.raza = v.texto_opcional(raza, "raza")
        self.sexo = None if sexo is None else v.opcion(sexo, "sexo", self.SEXOS)
        self.peso_kg = v.numero_no_negativo_opcional(peso_kg, "peso_kg")
        self.activo = v.booleano(activo, "activo")

    def edad_en_dias(self, fecha: str | date | None = None) -> int:
        """Días transcurridos desde el nacimiento hasta `fecha` (hoy si se omite)."""
        referencia = date.today() if fecha is None else v.a_fecha(fecha)
        dias = (referencia - v.a_fecha(self.fecha_nacimiento)).days
        if dias < 0:
            raise ValueError("La fecha de referencia es anterior al nacimiento de la mascota.")
        return dias

    def __str__(self) -> str:
        detalle = f", {self.raza}" if self.raza else ""
        return f"{self.nombre}{detalle} (nac. {self.fecha_nacimiento})"


class HistoriaClinica:
    """Historia clínica única de una mascota."""

    def __init__(
        self,
        id_mascota: int,
        fecha_apertura: str,
        alergias: str | None = None,
        antecedentes: str | None = None,
        id_historia: int | None = None,
    ) -> None:
        self.id_historia = v.id_opcional(id_historia, "id_historia")
        self.id_mascota = v.id_obligatorio(id_mascota, "id_mascota")
        self.fecha_apertura = v.fecha_iso(fecha_apertura, "fecha_apertura")
        self.alergias = v.texto_opcional(alergias, "alergias")
        self.antecedentes = v.texto_opcional(antecedentes, "antecedentes")

    def __str__(self) -> str:
        numero = self.id_historia if self.id_historia is not None else "s/n"
        return f"Historia clínica N° {numero} de la mascota {self.id_mascota} (abierta {self.fecha_apertura})"
