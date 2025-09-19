import math
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.types import String
from sqlmodel import Session, SQLModel, func, or_, select

from hyperadmin.db import get_session

# The templates are now in src/hyperadmin/templates
template_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=template_dir)


class ModelView:
    """
    A view class for a SQLModel model. This is a base class that should be subclassed.
    The subclass should define the `model` attribute.
    """

    model: type[SQLModel]

    def __init__(self):
        if not hasattr(self, "model"):
            raise ValueError("ModelView subclass must define a 'model' attribute.")
        self.router = APIRouter()
        self.add_routes()

    def add_routes(self):
        """Adds the list, detail, and create view routes to the router."""
        self.router.add_api_route(
            f"/{self.model.__name__.lower()}",
            self.list_view,
            methods=["GET"],
            name=f"{self.model.__name__.lower()}-list",
        )
        self.router.add_api_route(
            f"/{self.model.__name__.lower()}/create",
            self.create_view,
            methods=["GET", "POST"],
            name=f"{self.model.__name__.lower()}-create",
        )
        self.router.add_api_route(
            f"/{self.model.__name__.lower()}/{{item_id}}",
            self.detail_view,
            methods=["GET"],
            name=f"{self.model.__name__.lower()}-detail",
        )
        self.router.add_api_route(
            f"/{self.model.__name__.lower()}/{{item_id}}/update",
            self.update_view,
            methods=["GET", "POST"],
            name=f"{self.model.__name__.lower()}-update",
        )
        self.router.add_api_route(
            f"/{self.model.__name__.lower()}/{{item_id}}/delete",
            self.delete_action,
            methods=["POST"],
            name=f"{self.model.__name__.lower()}-delete",
        )

    async def delete_action(self, item_id: int, session: Session = Depends(get_session)):
        """Deletes an item."""
        item = session.get(self.model, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        session.delete(item)
        session.commit()

        # HTMX will expect an empty response to remove the element
        return {}

    async def update_view(
        self, request: Request, item_id: int, session: Session = Depends(get_session)
    ):
        """Renders the update view and handles form submission for updating an item."""
        item = session.get(self.model, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        if request.method == "POST":
            form_data = await request.form()
            for key, value in form_data.items():
                setattr(item, key, value)
            session.add(item)
            session.commit()
            session.refresh(item)
            # For now, let's redirect to the list view. HTMX will be added later.
            return {"message": "Item updated successfully"}

        context = {
            "model_name": self.model.__name__,
            "item": item,
            "fields": list(self.model.model_fields.keys()),
        }
        return templates.TemplateResponse(request, "update.html", context)

    async def create_view(self, request: Request, session: Session = Depends(get_session)):
        """Renders the create view and handles form submission for creating a new item."""
        if request.method == "POST":
            form_data = await request.form()
            item = self.model(**form_data)
            session.add(item)
            session.commit()
            session.refresh(item)
            # For now, let's redirect to the list view. HTMX will be added later.
            return {"message": "Item created successfully"}  # This will be improved later

        context = {
            "model_name": self.model.__name__,
            "fields": list(self.model.model_fields.keys()),
        }
        return templates.TemplateResponse(request, "create.html", context)

    async def list_view(
        self,
        request: Request,
        session: Session = Depends(get_session),
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100),
        search: str = Query(""),
        sort_by: str = Query(None),
        sort_direction: str = Query("asc", pattern="^(asc|desc)$"),
    ):
        """Renders the list view for the model with pagination, sorting, and filtering."""
        query = select(self.model)

        # Filtering
        if search:
            search_clauses = []
            for column in self.model.__table__.columns:
                if isinstance(column.type, String):
                    search_clauses.append(column.ilike(f"%{search}%"))
            if search_clauses:
                query = query.where(or_(*search_clauses))

        # Count total items for pagination after filtering
        count_query = select(func.count()).select_from(query.subquery())
        total_items = session.exec(count_query).one()
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 0

        # Sorting
        sort_column = sort_by or list(self.model.model_fields.keys())[0]
        if hasattr(self.model, sort_column):
            column = getattr(self.model, sort_column)
            if sort_direction == "desc":
                query = query.order_by(column.desc())
            else:
                query = query.order_by(column.asc())

        # Pagination
        offset = (page - 1) * page_size
        if page_size > 0:
            query = query.offset(offset).limit(page_size)

        items = session.exec(query).all()

        context = {
            "request": request,
            "model_name": self.model.__name__,
            "fields": list(self.model.model_fields.keys()),
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "start_index": offset + 1,
                "end_index": min(offset + page_size, total_items),
            },
            "search_query": search,
            "sort_by": sort_column,
            "sort_direction": sort_direction,
        }

        template_name = (
            "components/table.html" if request.headers.get("hx-request") else "list.html"
        )
        return templates.TemplateResponse(template_name, context)

    async def detail_view(
        self, request: Request, item_id: int, session: Session = Depends(get_session)
    ):
        """
        Renders the detail view for a single item.
        Assumes the model has an 'id' field.
        """
        item = session.get(self.model, item_id)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        context = {
            "item_name": f"{self.model.__name__} #{getattr(item, 'id', 'N/A')}",
            "item": item.model_dump(),
        }
        return templates.TemplateResponse(request, "detail.html", context)
