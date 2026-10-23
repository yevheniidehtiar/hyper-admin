"""S3-compatible storage backend for upload fields (epic #410, story #402).

:class:`S3StorageBackend` is a ``fastapi_storages.S3Storage`` configured from
keyword arguments or :class:`~hyperadmin.core.settings.HyperAdminSettings`
instead of process-wide environment variables read at import time, and works
with any S3-compatible service: AWS S3, Cloudflare R2, MinIO, Hetzner Object
Storage, DigitalOcean Spaces.

It implements every storage operation itself over a boto3 S3 *client*, so it
behaves the same on every supported ``fastapi-storages`` release (0.1.0 still
builds a ``boto3.resource`` and has no ``delete``; later releases differ again).

Requires the optional extra: ``pip install 'hyper-admin[s3]'``. ``boto3`` is
imported lazily, so importing this module never fails; building a backend
without it raises an ``ImportError`` that names the extra to install.

Objects live behind a URL rather than on local disk, so the admin's file views
redirect downloads to :meth:`S3StorageBackend.get_path` (a presigned URL by
default) and delete objects through the client; see :func:`is_remote_storage`.
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from fastapi_storages.s3 import S3Storage
from fastapi_storages.utils import secure_filename

if TYPE_CHECKING:
    from typing import BinaryIO

    from hyperadmin.core.settings import HyperAdminSettings

logger = logging.getLogger(__name__)

_S3_EXTRA_HINT = (
    "S3StorageBackend requires the 'boto3' package. Install it with: pip install 'hyper-admin[s3]'"
)
_DEFAULT_CONTENT_TYPE = "application/octet-stream"

#: Object-name segments that would leave the bucket prefix on a path-style URL.
_UNSAFE_SEGMENTS = frozenset({"", ".", ".."})


def _s3_client(**kwargs: Any) -> Any:
    """Build a ``boto3`` S3 client, naming the extra to install when it is missing."""
    try:
        import boto3  # noqa: PLC0415 - optional extra, imported lazily
    except ImportError as exc:
        raise ImportError(_S3_EXTRA_HINT) from exc
    return boto3.client("s3", **kwargs)


def _split_endpoint(endpoint_url: str | None) -> tuple[str, str | None]:
    """Return ``(scheme, host)`` for an endpoint URL; ``("https", None)`` when unset.

    A bare ``host:port`` is taken as https. The host keeps any port and path
    (``https://minio.local:9000``, ``http://localhost:9000``), without the
    trailing slash.
    """
    if not endpoint_url:
        return "https", None
    raw = endpoint_url if "://" in endpoint_url else f"https://{endpoint_url}"
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        msg = f"Invalid S3 endpoint URL {endpoint_url!r}: expected http(s)://host[:port]"
        raise ValueError(msg)
    return parts.scheme, parts.netloc + parts.path.rstrip("/")


class S3StorageBackend(S3Storage):
    """``S3Storage`` configured per instance, for AWS S3 and S3-compatible services.

    ``fastapi_storages.S3Storage`` reads its configuration from ``AWS_*``
    environment variables when the module is imported. This subclass takes the
    same configuration as keyword arguments (or from settings via
    :meth:`from_settings`), so two backends can point at different buckets and
    nothing is read at import time.

    Args:
        bucket_name: The bucket objects are written to.
        access_key_id: Static credentials. When unset, boto3's own credential
            chain applies (profiles, instance and task roles, ``AWS_*`` env).
        secret_access_key: See ``access_key_id``.
        region: The region name (``"eu-central-1"``). Optional for services that
            ignore it (MinIO) but required by AWS without a profile default.
        endpoint_url: ``http(s)://host[:port]`` of an S3-compatible service
            (MinIO, R2, Hetzner, Spaces). Unset for AWS S3. ``http://`` turns SSL
            off for that endpoint.
        custom_domain: Serve object URLs from this host instead of the endpoint
            (a CDN or an R2 public bucket domain). URLs are then not signed.
        querystring_auth: Sign object URLs (presigned, time-limited; default).
            Set ``False`` only for a public-read bucket.
        default_acl: ACL set on every written object (``"public-read"``).
            Unset (default) keeps objects private and sends no ACL, which
            services without ACL support (R2) require.
        client: An existing boto3 S3 client to use instead of building one
            (tests, custom sessions). The other connection arguments are then
            only used to build URLs.
    """

    def __init__(  # noqa: PLR0913 - one keyword per S3 connection setting
        self,
        *,
        bucket_name: str,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
        custom_domain: str | None = None,
        querystring_auth: bool = True,
        default_acl: str | None = None,
        client: Any = None,
    ) -> None:
        if not bucket_name:
            msg = "S3StorageBackend requires a bucket name"
            raise ValueError(msg)
        scheme, host = _split_endpoint(endpoint_url)
        self.bucket_name = bucket_name
        self.region = region
        self.custom_domain = custom_domain
        self.querystring_auth = querystring_auth
        self.default_acl = default_acl
        self._http_scheme = scheme
        endpoint = f"{scheme}://{host}" if host else None
        if client is None:
            client = _s3_client(
                **_client_kwargs(
                    use_ssl=scheme == "https",
                    endpoint=endpoint,
                    region=region,
                    access_key_id=access_key_id,
                    secret_access_key=secret_access_key,
                )
            )
        self._s3 = client
        self._url = endpoint or str(client.meta.endpoint_url)

    @classmethod
    def from_settings(cls, settings: HyperAdminSettings, *, client: Any = None) -> S3StorageBackend:
        """Build a backend from the ``aws_*`` settings (``HYPERADMIN_AWS_*`` / ``AWS_*`` env).

        Raises:
            ValueError: ``aws_s3_bucket_name`` is unset.
        """
        if not settings.aws_s3_bucket_name:
            msg = (
                "S3 storage requires a bucket: set aws_s3_bucket_name "
                "(HYPERADMIN_AWS_S3_BUCKET_NAME or AWS_S3_BUCKET_NAME)"
            )
            raise ValueError(msg)
        secret = settings.aws_secret_access_key
        return cls(
            bucket_name=settings.aws_s3_bucket_name,
            access_key_id=settings.aws_access_key_id,
            secret_access_key=secret.get_secret_value() if secret is not None else None,
            region=settings.aws_s3_region,
            endpoint_url=settings.aws_s3_endpoint_url,
            custom_domain=settings.aws_s3_custom_domain,
            querystring_auth=settings.aws_s3_querystring_auth,
            default_acl=settings.aws_s3_default_acl,
            client=client,
        )

    def get_name(self, name: str) -> str:
        """Return the object key for ``name``: the basename sanitised, directories kept."""
        path = PurePosixPath(name.replace("\\", "/"))
        safe = secure_filename(path.name)
        return str(path.parent / safe) if safe else name

    def get_path(self, name: str) -> str:
        """Return the URL of the object ``name``.

        Served from ``custom_domain`` when set, otherwise presigned through the
        client when ``querystring_auth`` is on (default), otherwise the plain
        path-style URL under the endpoint.
        """
        key = self.get_name(name)
        if self.custom_domain:
            return f"{self._http_scheme}://{self.custom_domain}/{key}"
        if self.querystring_auth:
            params = {"Bucket": self.bucket_name, "Key": key}
            return str(self._s3.generate_presigned_url("get_object", Params=params))
        return f"{self._url}/{self.bucket_name}/{key}"

    def get_size(self, name: str) -> int:
        """Return the object size in bytes (one ``HeadObject`` call)."""
        response = self._s3.head_object(Bucket=self.bucket_name, Key=self.get_name(name))
        return int(response["ContentLength"])

    def write(self, file: BinaryIO, name: str) -> str:
        """Upload ``file`` as ``name`` and return the object key.

        No ``ACL`` parameter is sent when ``default_acl`` is unset: boto3
        rejects ``ACL=None``, and services such as R2 reject any ACL at all.
        """
        file.seek(0, 0)
        key = self.get_name(name)
        content_type, _ = mimetypes.guess_type(key)
        params: dict[str, Any] = {"ContentType": content_type or _DEFAULT_CONTENT_TYPE}
        if self.default_acl:
            params["ACL"] = self.default_acl
        self._s3.upload_fileobj(file, self.bucket_name, key, ExtraArgs=params)
        return key

    def delete(self, name: str) -> None:
        """Delete the object ``name`` from the bucket."""
        self._s3.delete_object(Bucket=self.bucket_name, Key=self.get_name(name))


def _client_kwargs(
    *,
    use_ssl: bool,
    endpoint: str | None,
    region: str | None,
    access_key_id: str | None,
    secret_access_key: str | None,
) -> dict[str, Any]:
    """Return the ``boto3.client("s3", ...)`` arguments; unset values are left to boto3."""
    kwargs: dict[str, Any] = {"use_ssl": use_ssl}
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    if region:
        kwargs["region_name"] = region
    if access_key_id:
        kwargs["aws_access_key_id"] = access_key_id
    if secret_access_key:
        kwargs["aws_secret_access_key"] = secret_access_key
    return kwargs


def is_remote_storage(storage: Any) -> bool:
    """Return ``True`` when ``storage`` keeps objects behind a URL rather than on disk.

    True for any ``fastapi_storages.S3Storage`` (``S3StorageBackend`` included).
    The admin then redirects downloads to the object URL and deletes through
    the storage instead of resolving paths inside a local root.
    """
    return isinstance(storage, S3Storage)


def remote_file_name(value: Any) -> str | None:
    """Return the object name a file column value holds, or ``None`` when unusable.

    A value written by a user into the database must never address an object
    outside the bucket: on a path-style URL a ``..`` segment would leave the
    bucket prefix, so names with empty, ``.`` or ``..`` segments are refused.
    """
    if not value:
        return None
    name = str(value.name if hasattr(value, "name") else value)
    if any(part in _UNSAFE_SEGMENTS for part in name.replace("\\", "/").split("/")):
        logger.warning("Refusing object name with empty or traversal segments: %r", name)
        return None
    return name


def remote_file_url(storage: Any, value: Any) -> str | None:
    """Return the URL ``storage`` serves the object held by ``value`` at, or ``None``."""
    name = remote_file_name(value)
    return None if name is None else str(storage.get_path(name))
