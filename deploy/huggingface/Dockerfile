# Hosted ERP demo on a Hugging Face Docker Space (deployed by .github/workflows/demo.yml).
# The workflow stages pyproject.toml, uv.lock, README.md, LICENSE, src/ and examples/erp/
# next to this file. Spaces run the container as uid 1000 and route traffic to port 7860.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

RUN useradd --create-home --uid 1000 demo
USER demo
WORKDIR /home/demo/app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/home/demo/app/.venv/bin:$PATH"

COPY --chown=demo pyproject.toml uv.lock README.md LICENSE ./
COPY --chown=demo src/ ./src/
COPY --chown=demo examples/ ./examples/

# The project plus its default dependency group (Faker, used to seed the demo data), and
# uvicorn, which the library leaves to the host app.
RUN uv sync --locked --no-editable && uv pip install "uvicorn>=0.30"

# Throwaway SQLite database: every restart (each deploy and the nightly reset) starts
# from freshly seeded data. HYPERADMIN_SECRET_KEY and HYPERADMIN_ADMIN_PASSWORD are
# Space secrets set by the deploy workflow.
ENV HYPERADMIN_DEMO=1 \
    DATABASE_URL=sqlite+aiosqlite:////tmp/erp-demo.db

EXPOSE 7860

CMD ["uvicorn", "examples.erp.main:app", "--host", "0.0.0.0", "--port", "7860", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
