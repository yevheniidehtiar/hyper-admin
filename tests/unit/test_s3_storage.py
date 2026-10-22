"""S3-compatible storage backend configuration (epic #410, story #402).

Story: ``.meta/epics/epicuploads-advanced-file-uploads-v032/stories/
featuploads-add-s3-compatible-storage-backend-configuration.md``.

Every scenario runs against an in-memory stand-in for the boto3 S3 client:
nothing here opens a network connection.
"""

from __future__ import annotations

import io
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_storages import FileSystemStorage, S3Storage
from fastapi_storages.integrations.sqlalchemy import FileType
from pydantic import ValidationError
from sqlalchemy import Column, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.uploads import (
    S3StorageBackend,
    is_remote_storage,
    remote_file_name,
    remote_file_url,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


# ---------------------------------------------------------------------------
# Stubbed boto3 client
# ---------------------------------------------------------------------------


class _StubS3Client:
    """In-memory stand-in for a boto3 S3 client: records calls, never touches the network."""

    def __init__(self, endpoint_url: str = "https://s3.eu-central-1.amazonaws.com") -> None:
        self.meta = SimpleNamespace(endpoint_url=endpoint_url)
        self.objects: dict[tuple[str, str], bytes] = {}
        self.extra_args: dict[tuple[str, str], dict[str, Any]] = {}
        self.deleted: list[tuple[str, str]] = []

    def upload_fileobj(
        self,
        fileobj: Any,
        bucket: str,
        key: str,
        ExtraArgs: dict[str, Any] | None = None,  # noqa: N803 - boto3's parameter name
    ) -> None:
        self.objects[(bucket, key)] = fileobj.read()
        self.extra_args[(bucket, key)] = dict(ExtraArgs or {})

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, int]:  # noqa: N803
        return {"ContentLength": len(self.objects[(Bucket, Key)])}

    def delete_object(self, *, Bucket: str, Key: str) -> None:  # noqa: N803
        self.deleted.append((Bucket, Key))
        self.objects.pop((Bucket, Key), None)

    def generate_presigned_url(self, operation: str, Params: dict[str, str]) -> str:  # noqa: N803
        return f"{self.meta.endpoint_url}/{Params['Bucket']}/{Params['Key']}?X-Amz-Signature=stub"

    def reset(self) -> None:
        self.objects.clear()
        self.extra_args.clear()
        self.deleted.clear()


_BUCKET = "admin-files"
_stub = _StubS3Client("https://s3.example.test")
_s3 = S3StorageBackend(bucket_name=_BUCKET, endpoint_url="https://s3.example.test", client=_stub)


# ---------------------------------------------------------------------------
# Model, admin and app wiring
# ---------------------------------------------------------------------------


class S3Document(SQLModel, table=True):
    __tablename__ = "s3_document"

    id: int | None = Field(default=None, primary_key=True)
    title: str = ""
    doc: str | None = Field(default=None, sa_column=Column(FileType(storage=_s3)))


class S3DocumentAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    saved = dict(site._registry)
    site._registry = {}
    _stub.reset()
    yield
    site._registry = saved


async def _seed(engine: AsyncEngine, docs: dict[int, str | None]) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        for doc_id, name in docs.items():
            await conn.execute(
                text("INSERT INTO s3_document (id, title, doc) VALUES (:i, 't', :d)"),
                {"i": doc_id, "d": name},
            )


def _client(docs: dict[int, str | None], storage: Any = _s3) -> tuple[TestClient, AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    anyio.run(_seed, engine, docs)
    app = FastAPI()
    admin = Admin(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False),
        storage=storage,
    )
    site.register(S3Document, S3DocumentAdmin)
    admin.mount(path="/admin")
    return TestClient(app), engine


def _doc_names(engine: AsyncEngine) -> list[str | None]:
    async def _run() -> list[str | None]:
        async with engine.connect() as conn:
            rows = await conn.execute(text("SELECT doc FROM s3_document ORDER BY id"))
            return [r[0] for r in rows]

    return anyio.run(_run)


def _fake_boto3(monkeypatch: pytest.MonkeyPatch, stub: _StubS3Client) -> list[dict[str, Any]]:
    """Replace ``boto3.client`` with a recorder that hands back ``stub``."""
    calls: list[dict[str, Any]] = []

    def client(service: str, **kwargs: Any) -> _StubS3Client:
        calls.append({"service": service, **kwargs})
        return stub

    monkeypatch.setattr("boto3.client", client)
    return calls


# ---------------------------------------------------------------------------
# Story scenarios
# ---------------------------------------------------------------------------


def test_admin_accepts_an_s3_storage_instance() -> None:
    """
    Scenario: Admin accepts S3Storage instance
      Given an S3StorageBackend configured for an S3-compatible endpoint
      When  Admin(app, engine=engine, storage=s3_storage) is mounted
      Then  the upload route stores the file through the S3 client
    """
    # Given / When
    client, _ = _client({})

    # Then
    resp = client.post(
        "/admin/s3document/upload/doc", files={"file": ("notes.txt", b"hi", "text/plain")}
    )
    assert resp.status_code == 200
    name = resp.json()["filename"]
    assert name.endswith("-notes.txt")
    assert _stub.objects == {(_BUCKET, name): b"hi"}
    assert _stub.extra_args[(_BUCKET, name)] == {"ContentType": "text/plain"}


def test_s3_upload_stores_the_file_and_the_detail_view_links_a_download() -> None:
    """
    Scenario: S3 upload stores file and returns public URL
      Given S3StorageBackend with a configured bucket
      When  a file is uploaded via the admin create form
      Then  the object is stored in the bucket, the detail view links the
            per-record download route, and that route redirects to the object URL
    """
    # Given
    client, engine = _client({})

    # When
    created = client.post(
        "/admin/s3document",
        data={"title": "one"},
        files={"doc": ("report.pdf", b"%PDF", "application/pdf")},
        follow_redirects=False,
    )

    # Then
    assert created.status_code == 303
    (name,) = _doc_names(engine)
    assert name is not None and name.endswith("-report.pdf")
    assert _stub.objects == {(_BUCKET, name): b"%PDF"}

    detail = client.get("/admin/s3document/1")
    assert detail.status_code == 200
    assert 'href="http://testserver/admin/s3document/1/file/doc"' in detail.text
    assert ">report.pdf<" in detail.text

    download = client.get("/admin/s3document/1/file/doc", follow_redirects=False)
    assert download.status_code == 302
    assert download.headers["location"] == (
        f"https://s3.example.test/{_BUCKET}/{name}?X-Amz-Signature=stub"
    )
    assert download.headers["cache-control"] == "private, no-store"


def test_s3_file_deletion_removes_the_object_from_the_bucket() -> None:
    """
    Scenario: S3 file deletion removes object from bucket
      Given a record with a file stored in S3
      When  the file is deleted via the delete-file endpoint
      Then  the S3 object is removed and the field is cleared
    """
    # Given
    client, engine = _client({1: "abc-manual.pdf"})

    # When
    resp = client.delete("/admin/s3document/1/file/doc")

    # Then
    assert resp.status_code == 204
    assert _stub.deleted == [(_BUCKET, "abc-manual.pdf")]
    assert _doc_names(engine) == [None]


def test_record_deletion_removes_the_s3_object() -> None:
    """
    Scenario: S3 file deletion removes object from bucket (record deletion)
      Given a record with a file stored in S3
      When  the record is deleted via the admin
      Then  the S3 object is removed from the bucket
    """
    # Given
    client, engine = _client({1: "abc-manual.pdf", 2: None})

    # When
    resp = client.delete("/admin/s3document/1", follow_redirects=False)

    # Then
    assert resp.status_code in {200, 204, 303}
    assert _stub.deleted == [(_BUCKET, "abc-manual.pdf")]
    assert _doc_names(engine) == [None]


def test_environment_variables_configure_s3_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: environment variables configure S3 storage
      Given HYPERADMIN_STORAGE_BACKEND=s3, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
            AWS_S3_BUCKET_NAME are set
      When  Admin(app, engine=engine) is called without explicit storage
      Then  admin.storage is an S3Storage instance built from those variables
    """
    # Given
    monkeypatch.setenv("HYPERADMIN_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA-test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "shh")
    monkeypatch.setenv("AWS_S3_BUCKET_NAME", "env-bucket")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")
    calls = _fake_boto3(monkeypatch, _StubS3Client())

    # When
    admin = Admin(FastAPI(), engine=create_async_engine("sqlite+aiosqlite:///:memory:"))

    # Then
    assert isinstance(admin.storage, S3Storage)
    assert isinstance(admin.storage, S3StorageBackend)
    assert admin.storage.bucket_name == "env-bucket"
    assert calls == [
        {
            "service": "s3",
            "use_ssl": True,
            "region_name": "eu-central-1",
            "aws_access_key_id": "AKIA-test",
            "aws_secret_access_key": "shh",
        }
    ]


# ---------------------------------------------------------------------------
# Admin default storage selection
# ---------------------------------------------------------------------------


def test_local_backend_leaves_uploads_off_without_an_explicit_storage() -> None:
    """Scenario: storage_backend="local" (default) keeps admin.storage None."""
    admin = Admin(FastAPI(), engine=create_async_engine("sqlite+aiosqlite:///:memory:"))

    assert admin.settings.storage_backend == "local"
    assert admin.storage is None


def test_an_explicit_storage_wins_over_the_s3_setting(tmp_path: Path) -> None:
    """Scenario: storage= is kept as-is even when storage_backend="s3"."""
    local = FileSystemStorage(str(tmp_path))
    settings = HyperAdminSettings(storage_backend="s3", aws_s3_bucket_name="b")

    admin = Admin(FastAPI(), settings=settings, storage=local)

    assert admin.storage is local


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def test_s3_backend_requires_a_bucket_name() -> None:
    """Scenario: storage_backend="s3" without a bucket fails at settings validation."""
    with pytest.raises(ValidationError, match="aws_s3_bucket_name"):
        HyperAdminSettings(storage_backend="s3")


def test_prefixed_env_vars_take_precedence_over_plain_aws_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario: HYPERADMIN_AWS_* overrides AWS_* for the same setting."""
    monkeypatch.setenv("AWS_S3_BUCKET_NAME", "sdk-bucket")
    monkeypatch.setenv("HYPERADMIN_AWS_S3_BUCKET_NAME", "admin-bucket")
    monkeypatch.setenv("HYPERADMIN_AWS_S3_ENDPOINT_URL", "https://minio.local:9000")
    monkeypatch.setenv("AWS_QUERYSTRING_AUTH", "false")
    monkeypatch.setenv("AWS_DEFAULT_ACL", "public-read")
    monkeypatch.setenv("AWS_S3_CUSTOM_DOMAIN", "cdn.example.test")

    settings = HyperAdminSettings()

    assert settings.aws_s3_bucket_name == "admin-bucket"
    assert settings.aws_s3_endpoint_url == "https://minio.local:9000"
    assert settings.aws_s3_querystring_auth is False
    assert settings.aws_s3_default_acl == "public-read"
    assert settings.aws_s3_custom_domain == "cdn.example.test"


def test_the_secret_access_key_is_masked() -> None:
    """Scenario: the secret key never shows in repr or dumps."""
    settings = HyperAdminSettings(aws_secret_access_key="shh")

    assert settings.aws_secret_access_key is not None
    assert settings.aws_secret_access_key.get_secret_value() == "shh"
    assert "shh" not in repr(settings)


def test_aws_settings_default_to_none() -> None:
    """Scenario: no S3 configuration by default."""
    settings = HyperAdminSettings()

    assert settings.aws_access_key_id is None
    assert settings.aws_secret_access_key is None
    assert settings.aws_s3_bucket_name is None
    assert settings.aws_s3_region is None
    assert settings.aws_s3_endpoint_url is None
    assert settings.aws_s3_custom_domain is None
    assert settings.aws_s3_default_acl is None
    assert settings.aws_s3_querystring_auth is True


# ---------------------------------------------------------------------------
# S3StorageBackend
# ---------------------------------------------------------------------------


def test_from_settings_forwards_every_aws_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: from_settings builds the client from the aws_* settings."""
    stub = _StubS3Client()
    calls = _fake_boto3(monkeypatch, stub)
    settings = HyperAdminSettings(
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_s3_bucket_name="bucket",
        aws_s3_region="auto",
        aws_s3_endpoint_url="http://localhost:9000",
        aws_s3_custom_domain="files.example.test",
        aws_s3_querystring_auth=False,
        aws_s3_default_acl="public-read",
    )

    storage = S3StorageBackend.from_settings(settings)

    assert calls == [
        {
            "service": "s3",
            "use_ssl": False,
            "endpoint_url": "http://localhost:9000",
            "region_name": "auto",
            "aws_access_key_id": "id",
            "aws_secret_access_key": "secret",
        }
    ]
    assert storage._s3 is stub
    assert storage.bucket_name == "bucket"
    assert storage.region == "auto"
    assert storage._url == "http://localhost:9000"
    assert storage.custom_domain == "files.example.test"
    assert storage.querystring_auth is False
    assert storage.default_acl == "public-read"


def test_from_settings_without_a_bucket_is_an_error() -> None:
    """Scenario: from_settings needs aws_s3_bucket_name."""
    with pytest.raises(ValueError, match="AWS_S3_BUCKET_NAME"):
        S3StorageBackend.from_settings(HyperAdminSettings())


def test_without_credentials_boto3s_own_credential_chain_applies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario: no static credentials are passed when none are configured."""
    stub = _StubS3Client("https://s3.amazonaws.com")
    calls = _fake_boto3(monkeypatch, stub)

    storage = S3StorageBackend(bucket_name="b")

    assert calls == [{"service": "s3", "use_ssl": True}]
    assert storage._url == "https://s3.amazonaws.com"


def test_missing_boto3_names_the_extra_to_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario: building the backend without boto3 raises a helpful ImportError."""
    monkeypatch.setitem(sys.modules, "boto3", None)

    with pytest.raises(ImportError, match=r"pip install 'hyper-admin\[s3\]'"):
        S3StorageBackend(bucket_name="b")


@pytest.mark.parametrize(
    ("endpoint", "scheme", "host"),
    [
        ("https://minio.local:9000", "https", "minio.local:9000"),
        ("http://localhost:9000/", "http", "localhost:9000"),
        ("s3.eu-central-1.example.test", "https", "s3.eu-central-1.example.test"),
        ("https://gateway.example.test/s3/", "https", "gateway.example.test/s3"),
    ],
)
def test_endpoint_url_forms(endpoint: str, scheme: str, host: str) -> None:
    """Scenario: endpoint URLs with and without scheme, port, path and trailing slash."""
    storage = S3StorageBackend(bucket_name="b", endpoint_url=endpoint, client=_StubS3Client())

    assert storage._http_scheme == scheme
    assert storage._url == f"{scheme}://{host}"


@pytest.mark.parametrize("endpoint", ["ftp://files.example.test", "https://", "://x"])
def test_invalid_endpoint_url_is_rejected(endpoint: str) -> None:
    """Scenario: an endpoint without an http(s) host is a configuration error."""
    with pytest.raises(ValueError, match="Invalid S3 endpoint URL"):
        S3StorageBackend(bucket_name="b", endpoint_url=endpoint, client=_StubS3Client())


def test_an_empty_bucket_name_is_rejected() -> None:
    """Scenario: the bucket name is mandatory."""
    with pytest.raises(ValueError, match="bucket name"):
        S3StorageBackend(bucket_name="", client=_StubS3Client())


def test_object_urls_are_presigned_by_default() -> None:
    """Scenario: get_path signs URLs unless querystring_auth is off."""
    signed = S3StorageBackend(bucket_name="b", client=_StubS3Client("https://s3.example.test"))
    public = S3StorageBackend(
        bucket_name="b", client=_StubS3Client("https://s3.example.test"), querystring_auth=False
    )
    cdn = S3StorageBackend(
        bucket_name="b", client=_StubS3Client(), custom_domain="cdn.example.test"
    )

    assert signed.get_path("a.txt") == "https://s3.example.test/b/a.txt?X-Amz-Signature=stub"
    assert public.get_path("a.txt") == "https://s3.example.test/b/a.txt"
    assert cdn.get_path("a.txt") == "https://cdn.example.test/a.txt"


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("abc-report.pdf", "abc-report.pdf"),
        ("my report (final).pdf", "my_report_final.pdf"),
        ("2024/abc-report.pdf", "2024/abc-report.pdf"),
        ("2024\\abc-report.pdf", "2024/abc-report.pdf"),
        ("", ""),
    ],
)
def test_get_name_sanitises_the_basename_and_keeps_directories(name: str, key: str) -> None:
    """Scenario: object keys are the secure basename under the given prefix."""
    assert _s3.get_name(name) == key


def test_get_size_reads_the_object_head() -> None:
    """Scenario: get_size is one HeadObject call."""
    stub = _StubS3Client()
    storage = S3StorageBackend(bucket_name="b", client=stub)
    storage.write(io.BytesIO(b"12345"), "five.bin")

    assert storage.get_size("five.bin") == 5


def test_write_sends_an_acl_only_when_configured() -> None:
    """Scenario: write guesses the content type and omits ACL unless default_acl is set."""
    stub = _StubS3Client()
    private = S3StorageBackend(bucket_name="b", client=stub)
    public = S3StorageBackend(bucket_name="b", client=stub, default_acl="public-read")

    assert private.write(io.BytesIO(b"<svg/>"), "logo.svg") == "logo.svg"
    assert public.write(io.BytesIO(b"?"), "blob.unknownext") == "blob.unknownext"

    assert stub.objects == {("b", "logo.svg"): b"<svg/>", ("b", "blob.unknownext"): b"?"}
    assert stub.extra_args[("b", "logo.svg")] == {"ContentType": "image/svg+xml"}
    assert stub.extra_args[("b", "blob.unknownext")] == {
        "ContentType": "application/octet-stream",
        "ACL": "public-read",
    }


# ---------------------------------------------------------------------------
# Remote-storage helpers and containment
# ---------------------------------------------------------------------------


def test_is_remote_storage_only_for_s3(tmp_path: Path) -> None:
    """Scenario: FileSystemStorage and None are local; any S3Storage is remote."""
    assert is_remote_storage(_s3) is True
    assert is_remote_storage(FileSystemStorage(str(tmp_path))) is False
    assert is_remote_storage(None) is False


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("abc-report.pdf", "abc-report.pdf"),
        ("2024/abc-report.pdf", "2024/abc-report.pdf"),
        (SimpleNamespace(name="abc-report.pdf"), "abc-report.pdf"),
        ("../other-bucket/key", None),
        ("..\\..\\key", None),
        ("/absolute", None),
        ("a//b", None),
        ("./x", None),
    ],
)
def test_remote_file_name_refuses_traversal(value: Any, expected: str | None) -> None:
    """Scenario: names with empty, "." or ".." segments never reach the bucket URL."""
    assert remote_file_name(value) == expected


def test_remote_file_url_resolves_safe_names_only() -> None:
    """Scenario: remote_file_url returns the object URL for safe names and None otherwise."""
    assert remote_file_url(_s3, "abc-a.txt") == (
        f"https://s3.example.test/{_BUCKET}/abc-a.txt?X-Amz-Signature=stub"
    )
    assert remote_file_url(_s3, "../x") is None


def test_a_traversal_name_in_the_database_is_neither_served_nor_deleted() -> None:
    """
    Scenario: tampered stored name
      Given a record whose file column holds "../../other-bucket/key"
      When  its file is downloaded and then deleted via the admin
      Then  the download is 404 and no object is deleted from the bucket
    """
    # Given
    client, engine = _client({1: "../../other-bucket/key"})

    # When
    download = client.get("/admin/s3document/1/file/doc", follow_redirects=False)
    delete = client.delete("/admin/s3document/1/file/doc")

    # Then
    assert download.status_code == 404
    assert delete.status_code == 204
    assert _stub.deleted == []
    assert _doc_names(engine) == [None]


def test_download_of_an_empty_file_field_is_404() -> None:
    """Scenario: a record without a file has nothing to redirect to."""
    client, _ = _client({1: None})

    assert client.get("/admin/s3document/1/file/doc", follow_redirects=False).status_code == 404
