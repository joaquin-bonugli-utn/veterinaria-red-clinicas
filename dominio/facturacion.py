"""Entidades de facturación: comprobantes y sus detalles."""

from __future__ import annotations

from dominio import validaciones as v


class DetalleComprobante:
    """Línea de un comprobante: una atención, una vacuna o un análisis."""

    TIPOS_ITEM = ("Atención", "Vacuna", "Análisis")

    def __init__(
        self,
        tipo_item: str,
        descripcion: str,
        precio_unitario: float,
        cantidad: int = 1,
        id_atencion: int | None = None,
        id_muestra: int | None = None,
        subtotal: float | None = None,
        id_comprobante: int | None = None,
        id_detalle: int | None = None,
    ) -> None:
        self.id_detalle = v.id_opcional(id_detalle, "id_detalle")
        self.id_comprobante = v.id_opcional(id_comprobante, "id_comprobante")
        self.tipo_item = v.opcion(tipo_item, "tipo_item", self.TIPOS_ITEM)
        self.descripcion = v.texto_obligatorio(descripcion, "descripcion")
        self.precio_unitario = v.numero_no_negativo(precio_unitario, "precio_unitario")
        self.cantidad = v.entero_positivo(cantidad, "cantidad")
        self.id_atencion = v.id_opcional(id_atencion, "id_atencion")
        self.id_muestra = v.id_opcional(id_muestra, "id_muestra")
        if self.id_atencion is None and self.id_muestra is None:
            raise ValueError("El detalle debe referir a una atención o a una muestra.")
        # Si no se informa (p. ej. al aplicar una tarifa), se calcula cantidad × precio.
        self.subtotal = (
            round(self.cantidad * self.precio_unitario, 2)
            if subtotal is None
            else v.numero_no_negativo(subtotal, "subtotal")
        )

    def __str__(self) -> str:
        return f"{self.cantidad} x {self.descripcion} @ ${self.precio_unitario:,.2f} = ${self.subtotal:,.2f}"


class Comprobante:
    """Comprobante emitido a un cliente en una clínica."""

    def __init__(
        self,
        numero: str,
        id_cliente: int,
        id_clinica: int,
        fecha_emision: str,
        total: float = 0,
        id_comprobante: int | None = None,
    ) -> None:
        self.id_comprobante = v.id_opcional(id_comprobante, "id_comprobante")
        self.numero = v.texto_obligatorio(numero, "numero")
        self.id_cliente = v.id_obligatorio(id_cliente, "id_cliente")
        self.id_clinica = v.id_obligatorio(id_clinica, "id_clinica")
        self.fecha_emision = v.fecha_iso(fecha_emision, "fecha_emision")
        self.total = v.numero_no_negativo(total, "total")
        self.detalles: list[DetalleComprobante] = []

    def agregar_detalle(self, detalle: DetalleComprobante) -> None:
        """Agrega una línea y recalcula el total."""
        self.detalles.append(detalle)
        self.total = self.calcular_total()

    def calcular_total(self) -> float:
        return round(sum(d.subtotal for d in self.detalles), 2)

    def __str__(self) -> str:
        return f"Comprobante {self.numero} ({self.fecha_emision}) - total ${self.total:,.2f}"
