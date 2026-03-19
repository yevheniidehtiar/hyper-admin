from __future__ import annotations

from typing import TYPE_CHECKING, Any

from starlette.responses import Response

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from starlette.requests import Request
    from starlette.templating import _TemplateResponse


class HtmxTemplateResponse:
    """Utility to render full template or a specific Jinja2 block for HTMX requests.

    - If the incoming request has the HX-Request header and a block name is provided,
      it will render only that block's HTML and return it as a Response.
    - Otherwise, it will return the full TemplateResponse.
    """

    def __init__(self, templates: Jinja2Templates) -> None:
        self.templates = templates

    def render(
        self,
        *,
        template_name: str,
        context: dict[str, Any],
        request: Request,
        block: str | None = None,
        status_code: int = 200,
    ) -> Response | _TemplateResponse:
        is_hx = request.headers.get("hx-request") is not None

        if is_hx and block:
            # Render only a specific block from the template
            template = self.templates.env.get_template(template_name)
            jinja_context = template.new_context(context)
            block_fn = template.blocks.get(block)

            if not block_fn:
                # Fallback to full template when block not found
                return self.templates.TemplateResponse(
                    template_name, context, status_code=status_code
                )

            html = "".join(block_fn(jinja_context))
            return Response(content=html, media_type="text/html", status_code=status_code)

        # Non-HTMX or no block specified: render full template
        return self.templates.TemplateResponse(template_name, context, status_code=status_code)
