import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_html(name: str) -> str:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["html"]


@pytest.fixture
def sirotka_html() -> str:
    return fixture_html("sirotka")


@pytest.fixture
def chorny_html() -> str:
    return fixture_html("chyornyy-chelovek")


@pytest.fixture
def tanyusha_html() -> str:
    return fixture_html("tanyusha")
