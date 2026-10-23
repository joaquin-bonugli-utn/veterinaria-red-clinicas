"""Page de Flet simulada para testear las vistas sin abrir una ventana."""

from types import SimpleNamespace

import flet as ft


class PageFalsa:
    """Implementa lo mínimo de ft.Page que usan las vistas y registra los diálogos mostrados."""

    def __init__(self) -> None:
        self.dialogos: list = []
        self.controles: list = []
        self.window = SimpleNamespace()
        self.actualizaciones = 0

    def show_dialog(self, dialogo) -> None:
        dialogo.open = True
        self.dialogos.append(dialogo)

    def pop_dialog(self):
        abierto = next((d for d in reversed(self.dialogos) if d.open), None)
        if abierto:
            abierto.open = False
        return abierto

    def add(self, *controles) -> None:
        self.controles.extend(controles)

    def update(self, *_controles) -> None:
        self.actualizaciones += 1

    # --- Ayudas para los asserts ---------------------------------------------------------

    @property
    def ultimo_snackbar(self) -> ft.SnackBar:
        return next(d for d in reversed(self.dialogos) if isinstance(d, ft.SnackBar))

    @property
    def ultimo_mensaje(self) -> str:
        return self.ultimo_snackbar.content.value

    @property
    def ultimo_fue_error(self) -> bool:
        return self.ultimo_snackbar.bgcolor == ft.Colors.RED_700

    @property
    def dialogo_abierto(self) -> ft.AlertDialog | None:
        return next((d for d in reversed(self.dialogos) if isinstance(d, ft.AlertDialog) and d.open), None)

    def aceptar_dialogo(self) -> None:
        """Pulsa el botón principal (el último) del AlertDialog abierto."""
        self.dialogo_abierto.actions[-1].on_click(None)

    def campos_dialogo(self) -> list:
        """Controles del formulario del AlertDialog abierto (aplanando filas anidadas)."""
        def aplanar(controles):
            for c in controles:
                if isinstance(c, ft.Row):
                    yield from aplanar(c.controls)
                else:
                    yield c

        return list(aplanar(self.dialogo_abierto.content.content.controls))
