from typing import Protocol

from doxa.core.models import Annotation, Event


class AnnotationService(Protocol):
    def record(self, annotation: Annotation, idempotency_key: str) -> Event: ...
