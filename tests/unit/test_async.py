import asyncio

import pytest


@pytest.mark.anyio
async def test_dummy_async():
    await asyncio.sleep(0)
    assert True
