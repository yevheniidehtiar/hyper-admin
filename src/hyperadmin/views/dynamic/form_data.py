"""Form-data extraction, file-upload splitting and inline formset building."""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import HTTPException, Request
from starlette.datastructures import UploadFile as StarletteUpload

from hyperadmin.uploads import FileValidationError, prepare_image_upload
from hyperadmin.views.dynamic.files import FileViewMixin
from hyperadmin.views.forms import (
    CheckboxInput,
    FileInputWidget,
    InlineFormset,
    MultiSelectWidget,
    PydanticForm,
    RelationMultiSelectWidget,
)
from hyperadmin.views.urls import admin_url_for

logger = logging.getLogger(__name__)


class FormDataMixin(FileViewMixin):
    """Form-data extraction, file-upload splitting and inline formset building."""

    def _build_inline_formsets(
        self,
        existing_data: dict[str, list[Any]] | None = None,
        request: Request | None = None,
    ) -> list[InlineFormset]:
        """Build ``InlineFormset`` instances for each configured inline spec.

        Args:
            existing_data: Mapping of inline prefix to list of existing related
                model instances (used in update views).
            request: The current HTTP request, used to resolve the ``add_row_url``
                for each inline via ``request.url_for``.
        """
        formsets: list[InlineFormset] = []
        existing = existing_data or {}
        for spec in getattr(self.options, "inlines", []):
            add_row_url = ""
            if request is not None:
                route_name = f"{self._model_name_lower}-inline-add-row"
                try:
                    add_row_url = str(
                        admin_url_for(request, route_name, inline_prefix=spec.model_name)
                    )
                except Exception:
                    add_row_url = ""
            formset = self._inline_formset(spec, add_row_url=add_row_url)
            instances = existing.get(formset.prefix, [])
            if instances:
                formset.populate_from_instances(instances)
            else:
                formset.build_empty_rows()
            formsets.append(formset)
        return formsets

    @staticmethod
    def _extract_form_data(
        form_data: Any,
        form: PydanticForm,
    ) -> dict[str, Any]:
        """Build a data dict from submitted form data, handling multi-value fields.

        For ``MultiSelectWidget`` and ``RelationMultiSelectWidget`` fields, uses
        ``getlist()`` to capture all submitted values.  Absent multiselect fields
        are set to an empty list (mirrors the checkbox-absent pattern).

        ``FileInputWidget`` fields are handled specially: ``UploadFile`` objects
        are kept as-is so that SQLAlchemy's ``FileType``/``ImageType``
        ``process_bind_param`` can write them to storage.  Empty file inputs
        (no file selected) are removed from the dict to avoid overwriting
        existing values.

        Keys that are not form fields are dropped: a hidden field (an auto-now
        timestamp, a field outside ``form_include``) is never user-writable.
        """
        allowed = {field.name for field in form.fields}
        data: dict[str, Any] = {k: v for k, v in dict(form_data).items() if k in allowed}
        for field in form.fields:
            is_multi = isinstance(field.widget, (MultiSelectWidget, RelationMultiSelectWidget))
            is_checkbox = isinstance(field.widget, CheckboxInput)
            is_file = isinstance(field.widget, FileInputWidget)
            if is_file:
                upload = form_data.get(field.name)
                if isinstance(upload, StarletteUpload) and upload.filename:
                    data[field.name] = upload
                else:
                    data.pop(field.name, None)
            elif is_multi:
                data[field.name] = form_data.getlist(field.name)
            elif is_checkbox and field.name not in data:
                data[field.name] = False
        return data

    def _pop_file_uploads(
        self,
        data: dict[str, Any],
        form: PydanticForm,
    ) -> dict[str, Any]:
        """Remove ``UploadFile`` values from *data* so Pydantic validation
        does not choke on non-string file objects.

        Each upload is renamed to a unique stored name first, so saving it
        through the column's ``FileType``/``ImageType`` never overwrites the
        file of another record that was uploaded under the same name.

        An image field's upload is auto-rotated to its EXIF orientation before
        the column writes it; an image above the decompression-bomb limit is
        refused with a 422 before any pixel is decoded.

        Returns a dict of ``{field_name: UploadFile}`` that must be merged
        back into the adapter data after validation succeeds.
        """
        uploads: dict[str, Any] = {}
        for field in form.fields:
            if isinstance(field.widget, FileInputWidget) and field.name in data:
                val = data.pop(field.name)
                if isinstance(val, StarletteUpload):
                    val.filename = self._new_upload_name(val.filename or "")
                    if field.widget.is_image:
                        self._prepare_image_upload(field.name, val)
                    uploads[field.name] = val
        return uploads

    @staticmethod
    def _prepare_image_upload(field_name: str, upload: StarletteUpload) -> None:
        """Run the image hook on ``upload``; map a refused image to a 422."""
        try:
            prepare_image_upload(upload)
        except FileValidationError as exc:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail={field_name: str(exc)},
            ) from exc

    def _validate_inline_formsets(
        self, form_data: Any
    ) -> tuple[list[InlineFormset], list[tuple[InlineFormset, list[dict]]], bool]:
        """Build each inline formset and validate its submitted rows.

        Returns the formsets, the (formset, valid rows) pairs to persist, and
        whether any row failed validation.
        """
        inline_formsets: list[InlineFormset] = []
        inline_valid_data: list[tuple[InlineFormset, list[dict]]] = []
        has_inline_errors = False
        for spec in getattr(self.options, "inlines", []):
            formset = self._inline_formset(spec)
            rows_data = formset.extract_submitted_data(form_data)
            valid_rows, row_errors = formset.validate_rows(rows_data)
            if row_errors:
                has_inline_errors = True
                formset.rebuild_from_submitted(form_data)
            inline_formsets.append(formset)
            inline_valid_data.append((formset, valid_rows))
        return inline_formsets, inline_valid_data, has_inline_errors
