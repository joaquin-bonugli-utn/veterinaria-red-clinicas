"""Consultas de solo lectura para los reportes PDF.

Devuelven listas de diccionarios (filas agregadas, no entidades de dominio).
Todos los métodos reciben un rango semiabierto [desde, hasta) en texto ISO y una
clínica opcional; el filtro de clínica usa el patrón ``(? IS NULL OR col = ?)``.
"""

from __future__ import annotations

from typing import Any

from persistencia.repositorios.base import RepositorioBase


class RepositorioReportes(RepositorioBase):
    """Repositorio de consultas agregadas (no tiene ABMC)."""

    def _filas(self, sql: str, parametros: tuple[Any, ...]) -> list[dict[str, Any]]:
        return [dict(fila) for fila in self._todos(sql, parametros)]

    # --- 1. Atenciones y derivaciones por clínica y mes -----------------------------

    def atenciones_por_clinica_y_mes(
        self, desde: str, hasta: str, id_clinica: int | None = None
    ) -> list[dict[str, Any]]:
        """Por clínica y mes: atenciones (total y por tipo), atenciones derivadas, órdenes y muestras."""
        return self._filas(
            """
            WITH base AS (
                SELECT a.id_atencion,
                       a.id_clinica,
                       substr(a.fecha_hora, 1, 7) AS mes,
                       t.nombre AS tipo,
                       (SELECT COUNT(*) FROM orden_derivacion o
                         WHERE o.id_atencion = a.id_atencion) AS ordenes,
                       (SELECT COUNT(*) FROM muestra m
                          JOIN orden_derivacion o ON o.id_orden = m.id_orden
                         WHERE o.id_atencion = a.id_atencion) AS muestras
                  FROM atencion a
                  JOIN tipo_atencion t ON t.id_tipo_atencion = a.id_tipo_atencion
                 WHERE a.fecha_hora >= ? AND a.fecha_hora < ?
                   AND (? IS NULL OR a.id_clinica = ?)
            )
            SELECT c.nombre AS clinica,
                   b.mes,
                   COUNT(*) AS atenciones,
                   SUM(b.tipo = 'Consulta') AS consultas,
                   SUM(b.tipo = 'Control') AS controles,
                   SUM(b.tipo = 'Urgencia') AS urgencias,
                   SUM(b.ordenes > 0) AS atenciones_derivadas,
                   SUM(b.ordenes) AS ordenes,
                   SUM(b.muestras) AS muestras
              FROM base b
              JOIN clinica c ON c.id_clinica = b.id_clinica
             GROUP BY c.nombre, b.mes
             ORDER BY b.mes, c.nombre
            """,
            (desde, hasta, id_clinica, id_clinica),
        )

    # --- 2. Muestras rechazadas por fallas en el transporte ------------------------

    def muestras_rechazadas_en_transporte(
        self, desde: str, hasta: str, id_clinica: int | None = None
    ) -> list[dict[str, Any]]:
        """Muestras rechazadas en la recepción (precinto roto, viabilidad vencida por
        demora o temperatura de llegada). Se atribuyen al transportista que entregó
        en el laboratorio (último tramo) y a la clínica de origen del remito."""
        return self._filas(
            """
            SELECT tr.nombre AS transportista,
                   c.nombre AS clinica,
                   r.numero AS remito,
                   m.codigo AS muestra,
                   ta.nombre AS analisis,
                   rc.fecha_hora AS fecha_recepcion,
                   rc.temperatura_llegada,
                   h.observacion AS motivo,
                   CASE
                       WHEN h.observacion LIKE 'Precinto roto%' THEN 'Precinto roto'
                       WHEN h.observacion LIKE 'Viabilidad vencida%' THEN 'Viabilidad vencida'
                       WHEN h.observacion LIKE 'Temperatura%' THEN 'Temperatura fuera de rango'
                       ELSE 'Otro'
                   END AS categoria
              FROM muestra m
              JOIN historial_estado_muestra h ON h.id_muestra = m.id_muestra AND h.estado = 'Rechazada'
              JOIN remito_biologico r ON r.id_remito = m.id_remito
              JOIN recepcion rc ON rc.id_remito = r.id_remito
              JOIN clinica c ON c.id_clinica = r.id_clinica
              JOIN tipo_analisis ta ON ta.id_tipo_analisis = m.id_tipo_analisis
              JOIN tramo_envio te ON te.id_remito = r.id_remito
                   AND te.nro_tramo = (SELECT MAX(t2.nro_tramo) FROM tramo_envio t2
                                        WHERE t2.id_remito = r.id_remito)
              JOIN transportista tr ON tr.id_transportista = te.id_transportista
             WHERE rc.fecha_hora >= ? AND rc.fecha_hora < ?
               AND (? IS NULL OR r.id_clinica = ?)
             ORDER BY tr.nombre, c.nombre, rc.fecha_hora, m.codigo
            """,
            (desde, hasta, id_clinica, id_clinica),
        )

    # --- 3. Tratamientos y vacunas por mascota -------------------------------------

    def mascotas_atendidas(self, desde: str, hasta: str, id_clinica: int | None = None) -> list[dict[str, Any]]:
        """Mascotas con al menos una atención en el período, con los datos del responsable."""
        return self._filas(
            """
            SELECT ma.id_mascota, ma.nombre AS mascota, e.nombre AS especie, ma.raza,
                   ma.fecha_nacimiento,
                   cl.apellido || ', ' || cl.nombre AS responsable, cl.dni, cl.telefono, cl.email,
                   COUNT(a.id_atencion) AS atenciones,
                   MAX(a.fecha_hora) AS ultima_atencion
              FROM mascota ma
              JOIN especie e ON e.id_especie = ma.id_especie
              JOIN cliente cl ON cl.id_cliente = ma.id_cliente
              JOIN historia_clinica hc ON hc.id_mascota = ma.id_mascota
              JOIN atencion a ON a.id_historia = hc.id_historia
             WHERE a.fecha_hora >= ? AND a.fecha_hora < ?
               AND (? IS NULL OR a.id_clinica = ?)
             GROUP BY ma.id_mascota
             ORDER BY cl.apellido, cl.nombre, ma.nombre
            """,
            (desde, hasta, id_clinica, id_clinica),
        )

    def tratamientos_aplicados(self, desde: str, hasta: str, id_clinica: int | None = None) -> list[dict[str, Any]]:
        """Tratamientos indicados en atenciones del período."""
        return self._filas(
            """
            SELECT hc.id_mascota, a.fecha_hora, c.nombre AS clinica,
                   v.apellido || ', ' || v.nombre AS veterinario,
                   t.medicamento, t.dosis, t.frecuencia, t.fecha_inicio, t.fecha_fin
              FROM tratamiento t
              JOIN atencion a ON a.id_atencion = t.id_atencion
              JOIN historia_clinica hc ON hc.id_historia = a.id_historia
              JOIN clinica c ON c.id_clinica = a.id_clinica
              JOIN veterinario v ON v.id_veterinario = a.id_veterinario
             WHERE a.fecha_hora >= ? AND a.fecha_hora < ?
               AND (? IS NULL OR a.id_clinica = ?)
             ORDER BY hc.id_mascota, a.fecha_hora
            """,
            (desde, hasta, id_clinica, id_clinica),
        )

    # --- 4. Facturación por clínica y tipo de servicio -----------------------------

    def facturacion_por_clinica_y_tipo(
        self, desde: str, hasta: str, id_clinica: int | None = None
    ) -> list[dict[str, Any]]:
        """Importe facturado por clínica y tipo de ítem, con el importe de lista
        (precio × cantidad) para ver el efecto de las tarifas."""
        return self._filas(
            """
            SELECT c.nombre AS clinica,
                   d.tipo_item,
                   COUNT(*) AS items,
                   COUNT(DISTINCT co.id_comprobante) AS comprobantes,
                   ROUND(SUM(d.precio_unitario * d.cantidad), 2) AS importe_lista,
                   ROUND(SUM(d.subtotal), 2) AS importe_facturado
              FROM detalle_comprobante d
              JOIN comprobante co ON co.id_comprobante = d.id_comprobante
              JOIN clinica c ON c.id_clinica = co.id_clinica
             WHERE co.fecha_emision >= ? AND co.fecha_emision < ?
               AND (? IS NULL OR co.id_clinica = ?)
             GROUP BY c.nombre, d.tipo_item
             ORDER BY c.nombre, d.tipo_item
            """,
            (desde, hasta, id_clinica, id_clinica),
        )

    def resumen_comprobantes(self, desde: str, hasta: str, id_clinica: int | None = None) -> dict[str, Any]:
        """Cantidad de comprobantes, total facturado y ticket promedio del período."""
        fila = self._uno(
            """
            SELECT COUNT(*) AS comprobantes,
                   COALESCE(ROUND(SUM(total), 2), 0) AS total,
                   COALESCE(ROUND(AVG(total), 2), 0) AS promedio
              FROM comprobante
             WHERE fecha_emision >= ? AND fecha_emision < ?
               AND (? IS NULL OR id_clinica = ?)
            """,
            (desde, hasta, id_clinica, id_clinica),
        )
        return dict(fila)

    # --- 5. Tiempos de tránsito y procesamiento ------------------------------------

    def tiempos_por_tipo_analisis(
        self, desde: str, hasta: str, id_clinica: int | None = None
    ) -> list[dict[str, Any]]:
        """Horas de tránsito (salida del primer tramo → recepción) y de procesamiento
        (recepción → resultado) por tipo de análisis, para remitos recibidos en el período.
        El tránsito incluye muestras rechazadas; el procesamiento, solo las analizadas."""
        return self._filas(
            """
            WITH tiempos AS (
                SELECT m.id_muestra, m.id_tipo_analisis,
                       (julianday(rc.fecha_hora) - julianday(te.fecha_hora_salida)) * 24 AS transito,
                       (julianday(ra.fecha_hora) - julianday(rc.fecha_hora)) * 24 AS procesamiento
                  FROM muestra m
                  JOIN remito_biologico r ON r.id_remito = m.id_remito
                  JOIN recepcion rc ON rc.id_remito = r.id_remito
                  JOIN tramo_envio te ON te.id_remito = r.id_remito AND te.nro_tramo = 1
                  LEFT JOIN resultado_analisis ra ON ra.id_muestra = m.id_muestra
                 WHERE rc.fecha_hora >= ? AND rc.fecha_hora < ?
                   AND (? IS NULL OR r.id_clinica = ?)
            )
            SELECT ta.nombre AS analisis,
                   ta.horas_viabilidad,
                   COUNT(*) AS muestras,
                   ROUND(AVG(t.transito), 2) AS transito_promedio,
                   ROUND(MIN(t.transito), 2) AS transito_minimo,
                   ROUND(MAX(t.transito), 2) AS transito_maximo,
                   COUNT(t.procesamiento) AS analizadas,
                   ROUND(AVG(t.procesamiento), 2) AS procesamiento_promedio
              FROM tiempos t
              JOIN tipo_analisis ta ON ta.id_tipo_analisis = t.id_tipo_analisis
             GROUP BY ta.id_tipo_analisis
             ORDER BY ta.nombre
            """,
            (desde, hasta, id_clinica, id_clinica),
        )

    # --- Auxiliares ----------------------------------------------------------------

    def nombre_clinica(self, id_clinica: int) -> str | None:
        return self._escalar("SELECT nombre FROM clinica WHERE id_clinica = ?", (id_clinica,))
