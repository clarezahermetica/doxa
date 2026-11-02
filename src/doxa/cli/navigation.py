"""Shared dialog cancellation. A child dismisses itself, preserving its parent screen."""

from typing import TypeVar

from textual.screen import ModalScreen

Result = TypeVar("Result")


class ClientModal(ModalScreen[Result]):
    BINDINGS = [("escape", "dismiss", "Back / cancel")]
