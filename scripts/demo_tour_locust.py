"""Locust users for the load-test scene of ``scripts/demo_tour_video.py``.

Runs against ``tests.e2e.apps.scalability`` seeded with 1.2 million rows. Two separate
measurements, one user class each (pass the class name on the command line):

* ``ReadUser``: list, detail and search on the 300,000 movements and 900,000 products.
* ``WriteUser``: create, update and delete of a movement. Each user only updates and
  deletes rows it created, and deletes what is left when it stops, so the table keeps its
  seeded size.

Logins and warm-up never reach the figures: every user logs in once in ``on_start``; once
all of them have, the run waits ``TOUR_WARMUP`` seconds, resets the statistics, measures for
``TOUR_SECONDS`` and writes the figures to ``TOUR_OUT`` (JSON) before it stops::

    TOUR_USERS=20 TOUR_SECONDS=30 TOUR_OUT=read.json LOADTEST_USER=alice \\
    LOADTEST_PASSWORD=secret123 locust -f scripts/demo_tour_locust.py --headless \\
        -u 20 -r 20 --host http://127.0.0.1:8000 ReadUser
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import gevent
from locust import HttpUser, between, events, task
from locust.stats import StatsEntry

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from examples.erp.loadtest.auth_mixin import HyperAdminAuthMixin

SCALE = int(os.environ.get("E2E_SCALABILITY_SCALE", "100"))
MOVEMENTS = 3_000 * SCALE
PRODUCTS = 9_000 * SCALE
USERS = int(os.environ.get("TOUR_USERS", "20"))
WARMUP = float(os.environ.get("TOUR_WARMUP", "5"))
SECONDS = float(os.environ.get("TOUR_SECONDS", "30"))
OUT = Path(os.environ.get("TOUR_OUT", "tour-locust.json"))
PERCENTILES = (0.5, 0.95, 0.99)
_DETAIL_ID = re.compile(r"/admin/movement/(\d+)")

_ready = 0  # users that finished logging in


class _TourUser(HyperAdminAuthMixin, HttpUser):
    abstract = True

    def on_start(self) -> None:
        global _ready  # noqa: PLW0603 - per-process counter shared by all users
        super().on_start()
        self.rng = random.Random()  # noqa: S311 - load shape, not security
        _ready += 1


class ReadUser(_TourUser):
    """Lists, opens and searches the two large tables."""

    wait_time = between(0.2, 0.6)

    @task(2)
    def list_view(self) -> None:
        if self.rng.random() < 0.5:
            self.client.get("/admin/movement", name="list")  # keyset pages
        else:
            # The first 100 pages, as people page through a list; deep offsets are what
            # pagination_mode="cursor" is for (the movement list above).
            page = self.rng.randint(1, 100)
            self.client.get(f"/admin/product?page={page}&page_size=10", name="list")

    @task(1)
    def detail_view(self) -> None:
        if self.rng.random() < 0.5:
            self.client.get(f"/admin/movement/{self.rng.randint(1, MOVEMENTS)}", name="detail")
        else:
            self.client.get(f"/admin/product/{self.rng.randint(1, PRODUCTS)}", name="detail")

    @task(1)
    def search_view(self) -> None:
        sku = f"SKU-{self.rng.randint(0, PRODUCTS - 1):07d}"
        self.client.get(f"/admin/product?search={sku}&page_size=10", name="search")


class WriteUser(_TourUser):
    """Creates a movement, updates it and deletes it again."""

    wait_time = between(0.2, 0.6)

    def on_start(self) -> None:
        super().on_start()
        self.mine: list[int] = []

    def _payload(self) -> dict[str, str]:
        return {
            "reference": f"LT-{uuid.uuid4().hex[:10]}",
            "quantity": str(self.rng.randint(1, 50)),
            "product_id": str(self.rng.randint(1, PRODUCTS)),
        }

    @task
    def create_update_delete(self) -> None:
        with self.client.post(
            "/admin/movement",
            data=self._payload(),
            name="create",
            allow_redirects=False,
            catch_response=True,
        ) as resp:
            match = _DETAIL_ID.search(resp.headers.get("location", ""))
            if resp.status_code != 303 or match is None:
                resp.failure(f"create answered {resp.status_code}")
                return
        item_id = int(match.group(1))
        self.mine.append(item_id)
        self.client.put(f"/admin/movement/{item_id}", data=self._payload(), name="update")
        self.client.delete(f"/admin/movement/{item_id}", name="delete")
        self.mine.remove(item_id)

    def on_stop(self) -> None:
        for item_id in self.mine:  # interrupted cycles: leave the table as seeded
            self.client.delete(f"/admin/movement/{item_id}", name="cleanup")


def _row(entry: Any, seconds: float) -> dict[str, Any]:
    return {
        "requests": entry.num_requests,
        "failures": entry.num_failures,
        "rps": entry.num_requests / seconds,
        **{f"p{round(p * 100)}": entry.get_response_time_percentile(p) for p in PERCENTILES},
    }


def _measure(environment: Any) -> None:
    while _ready < USERS:
        gevent.sleep(0.1)
    gevent.sleep(WARMUP)
    environment.runner.stats.reset_all()
    started = time.monotonic()
    gevent.sleep(SECONDS)
    seconds = time.monotonic() - started
    stats = environment.runner.stats
    endpoints = {
        name: entry
        for (name, _), entry in stats.entries.items()
        if entry.num_requests  # the logins were reset away with the warm-up
    }
    figures = {
        "users": USERS,
        "seconds": seconds,
        "total": _row(stats.total, seconds),
        "endpoints": {name: _row(entry, seconds) for name, entry in endpoints.items()},
    }
    if "search" in endpoints:
        # On SQLite the search is a table scan; list and detail without it, so the read
        # total is not read as the search's figure.
        browse = StatsEntry(stats, "list+detail", "")
        for name in ("list", "detail"):
            if name in endpoints:
                browse.extend(endpoints[name])
        figures["without_search"] = _row(browse, seconds)
    OUT.write_text(json.dumps(figures, indent=2))
    environment.runner.quit()


@events.test_start.add_listener
def _start_measuring(environment: Any, **_kwargs: Any) -> None:
    gevent.spawn(_measure, environment)
