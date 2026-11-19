import pytest
from src.services.document.document_queue_service import estimate_total_seconds


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (None, 20),  # no upload summary counts as no lines
        (0, 20),
        (13, 20),
        (29, 22),
        (100, 40),
        (1000, 180),
        (10**6, 180),
    ],
)
def test_estimate(lines: int | None, expected: int) -> None:
    assert estimate_total_seconds(lines) == expected
