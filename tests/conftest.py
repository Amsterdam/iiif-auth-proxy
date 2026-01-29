from functools import lru_cache
from pathlib import Path
from typing import Callable

import pytest


@pytest.fixture
def test_image_data_factory() -> Callable[[str], bytes]:
    @lru_cache(maxsize=128)
    def _get_image(filename: str) -> bytes:
        image_path = Path(__file__).parent / f"test-images/{filename}"
        return image_path.read_bytes()

    return _get_image
