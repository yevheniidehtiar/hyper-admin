"""This module will contain the base HyperAdminModel class."""

import abc
import sys
from typing import TYPE_CHECKING, Any, Union

from hyperadmin.core.adapters import BaseAdapter

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from pydantic import BaseModel

if TYPE_CHECKING:
    import babel.support


class HyperAdminModel(BaseModel, abc.ABC):
    """A base class for creating administrative models in HyperAdmin.

    This class provides the core functionality for integrating Pydantic models
    with the HyperAdmin interface. It serves as a foundation for defining
    how models are displayed, validated, and managed in the admin panel.

    It includes abstract methods for CRUD operations and placeholder methods
    for lifecycle hooks, which should be implemented by subclasses.
    """

    class Meta:
        """Inner class for model-specific configuration.

        This class allows for the customization of the admin behavior for each
        model, such as specifying the list of fields to display or defining
        custom actions.
        """

    @classmethod
    @abc.abstractmethod
    async def create(cls, data: dict[str, Any]) -> Self:
        """Creates a new model instance."""
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    async def get(cls, pk: Any) -> Self | None:
        """Retrieves a model instance by its primary key."""
        raise NotImplementedError

    @abc.abstractmethod
    async def update(self, data: dict[str, Any]) -> None:
        """Updates the model instance."""
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self) -> None:
        """Deletes the model instance."""
        raise NotImplementedError

    async def before_save(self) -> None:
        """Lifecycle hook called before saving the model."""

    async def after_save(self) -> None:
        """Lifecycle hook called after saving the model."""

    async def before_delete(self) -> None:
        """Lifecycle hook called before deleting the model."""

    async def after_delete(self) -> None:
        """Lifecycle hook called after deleting the model."""


from hyperadmin.views.static import ModelView

#: Type alias for values accepted as verbose_name / verbose_name_plural.
#: Either a plain ``str`` or a ``babel.support.LazyProxy`` from
#: :func:`hyperadmin.i18n.gettext_lazy`.
VerboseNameType = Union[str, "babel.support.LazyProxy"]


class ModelAdmin:
    """Base class for registering a model with the HyperAdmin site.

    Subclass this and set class-level attributes to customise the admin
    behaviour for a model.

    Translatable labels
    -------------------
    ``verbose_name`` and ``verbose_name_plural`` accept either a plain string
    or a lazy proxy returned by :func:`hyperadmin.i18n.gettext_lazy`.  Lazy
    values are *not* pre-evaluated; they render in the active locale at
    template-render time.

    Example::

        from hyperadmin import gettext_lazy as _


        class UserAdmin(ModelAdmin):
            verbose_name = _("User")
            verbose_name_plural = _("Users")
    """

    view_class = ModelView
    adapter_class: type[BaseAdapter]

    #: Human-readable singular name for the model.
    #: Defaults to the model class name when ``None``.
    verbose_name: VerboseNameType | None = None

    #: Human-readable plural name for the model.
    #: Defaults to ``verbose_name + "s"`` when ``None``.
    verbose_name_plural: VerboseNameType | None = None

    def __init__(self, model: Any) -> None:
        self.model = model

    @classmethod
    def get_verbose_name(cls, model: Any) -> VerboseNameType:
        """Return the singular verbose name, lazily evaluated.

        Uses :attr:`verbose_name` when set; otherwise falls back to the
        model's ``__name__``.  The return value is *not* coerced to
        ``str`` so lazy proxies remain lazy.
        """
        if cls.verbose_name is not None:
            return cls.verbose_name
        return model.__name__

    @classmethod
    def get_verbose_name_plural(cls, model: Any) -> VerboseNameType:
        """Return the plural verbose name, lazily evaluated.

        Uses :attr:`verbose_name_plural` when set; otherwise appends
        ``"s"`` to :meth:`get_verbose_name`.  The return value is *not*
        coerced to ``str`` so lazy proxies remain lazy.
        """
        if cls.verbose_name_plural is not None:
            return cls.verbose_name_plural
        # Concatenation with a plain string keeps LazyProxy objects lazy
        # because babel.support.LazyProxy.__add__ returns another proxy.
        singular = cls.get_verbose_name(model)
        return singular + "s"  # type: ignore[operator]
