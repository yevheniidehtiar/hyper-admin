"""Tests for auth domain models (A1).

TDD: These tests define the expected behavior for User, Group, Permission,
and junction table models before implementation.
"""

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select


@pytest.fixture
def engine(tmp_path):
    db_file = tmp_path / "test_auth.db"
    eng = create_engine(f"sqlite:///{db_file}")
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


class TestUserModel:
    def test_user_creation_with_new_fields(self, session: Session):
        from hyperadmin.auth.models import User

        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="fakehash",
            first_name="John",
            last_name="Doe",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        assert user.id is not None
        assert user.username == "testuser"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.is_active is True
        assert user.is_superuser is False
        assert user.created_at is not None
        assert user.updated_at is None

    def test_user_defaults(self, session: Session):
        from hyperadmin.auth.models import User

        user = User(
            username="defaults",
            email="defaults@example.com",
            password_hash="fakehash",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        assert user.is_active is True
        assert user.is_superuser is False
        assert user.first_name == ""
        assert user.last_name == ""

    def test_user_table_name(self):
        from hyperadmin.auth.models import User

        assert User.__tablename__ == "hyperadmin_users"

    def test_user_username_unique(self, session: Session):
        from sqlalchemy.exc import IntegrityError

        from hyperadmin.auth.models import User

        session.add(User(username="dup", email="a@a.com", password_hash="h"))
        session.commit()
        session.add(User(username="dup", email="b@b.com", password_hash="h"))
        with pytest.raises(IntegrityError):
            session.commit()


class TestGroupModel:
    def test_group_crud(self, session: Session):
        from hyperadmin.auth.models import Group

        group = Group(name="Editors", description="Can edit content")
        session.add(group)
        session.commit()
        session.refresh(group)

        assert group.id is not None
        assert group.name == "Editors"
        assert group.description == "Can edit content"
        assert group.is_active is True
        assert group.created_at is not None

    def test_group_table_name(self):
        from hyperadmin.auth.models import Group

        assert Group.__tablename__ == "hyperadmin_groups"

    def test_group_name_unique(self, session: Session):
        from sqlalchemy.exc import IntegrityError

        from hyperadmin.auth.models import Group

        session.add(Group(name="dup"))
        session.commit()
        session.add(Group(name="dup"))
        with pytest.raises(IntegrityError):
            session.commit()


class TestPermissionModel:
    def test_permission_creation(self, session: Session):
        from hyperadmin.auth.models import Permission

        perm = Permission(
            codename="view_user",
            name="Can view user",
            content_type="user",
        )
        session.add(perm)
        session.commit()
        session.refresh(perm)

        assert perm.id is not None
        assert perm.codename == "view_user"
        assert perm.name == "Can view user"
        assert perm.content_type == "user"

    def test_permission_table_name(self):
        from hyperadmin.auth.models import Permission

        assert Permission.__tablename__ == "hyperadmin_permissions"

    def test_permission_codename_unique(self, session: Session):
        from sqlalchemy.exc import IntegrityError

        from hyperadmin.auth.models import Permission

        session.add(Permission(codename="view_user", name="Can view user"))
        session.commit()
        session.add(Permission(codename="view_user", name="Can view user 2"))
        with pytest.raises(IntegrityError):
            session.commit()


class TestJunctionTables:
    def test_user_group_junction(self, session: Session):
        from hyperadmin.auth.models import Group, User, UserGroup

        user = User(username="jtest", email="j@t.com", password_hash="h")
        group = Group(name="TestGroup")
        session.add_all([user, group])
        session.commit()

        ug = UserGroup(user_id=user.id, group_id=group.id)
        session.add(ug)
        session.commit()
        session.refresh(ug)

        assert ug.id is not None
        assert ug.user_id == user.id
        assert ug.group_id == group.id

    def test_user_group_table_name(self):
        from hyperadmin.auth.models import UserGroup

        assert UserGroup.__tablename__ == "hyperadmin_user_groups"

    def test_user_permission_junction(self, session: Session):
        from hyperadmin.auth.models import Permission, User, UserPermission

        user = User(username="ptest", email="p@t.com", password_hash="h")
        perm = Permission(codename="view_user", name="Can view user")
        session.add_all([user, perm])
        session.commit()

        up = UserPermission(user_id=user.id, permission_id=perm.id)
        session.add(up)
        session.commit()
        session.refresh(up)

        assert up.id is not None
        assert up.user_id == user.id
        assert up.permission_id == perm.id

    def test_user_permission_table_name(self):
        from hyperadmin.auth.models import UserPermission

        assert UserPermission.__tablename__ == "hyperadmin_user_permissions"

    def test_group_permission_junction(self, session: Session):
        from hyperadmin.auth.models import Group, GroupPermission, Permission

        group = Group(name="GPTest")
        perm = Permission(codename="add_user", name="Can add user")
        session.add_all([group, perm])
        session.commit()

        gp = GroupPermission(group_id=group.id, permission_id=perm.id)
        session.add(gp)
        session.commit()
        session.refresh(gp)

        assert gp.id is not None
        assert gp.group_id == group.id
        assert gp.permission_id == perm.id

    def test_group_permission_table_name(self):
        from hyperadmin.auth.models import GroupPermission

        assert GroupPermission.__tablename__ == "hyperadmin_group_permissions"


class TestRelationshipTraversal:
    def test_group_to_permissions(self, session: Session):
        from hyperadmin.auth.models import Group, GroupPermission, Permission

        group = Group(name="Admins")
        p1 = Permission(codename="view_user", name="Can view user")
        p2 = Permission(codename="add_user", name="Can add user")
        session.add_all([group, p1, p2])
        session.commit()

        session.add_all(
            [
                GroupPermission(group_id=group.id, permission_id=p1.id),
                GroupPermission(group_id=group.id, permission_id=p2.id),
            ]
        )
        session.commit()

        # Refresh to load relationships
        session.expire_all()
        group = session.exec(select(Group).where(Group.name == "Admins")).one()
        perm_codenames = {gp.permission.codename for gp in group.group_permissions}
        assert perm_codenames == {"view_user", "add_user"}

    def test_user_to_direct_permissions(self, session: Session):
        from hyperadmin.auth.models import Permission, User, UserPermission

        user = User(username="directperm", email="dp@t.com", password_hash="h")
        perm = Permission(codename="delete_user", name="Can delete user")
        session.add_all([user, perm])
        session.commit()

        session.add(UserPermission(user_id=user.id, permission_id=perm.id))
        session.commit()

        session.expire_all()
        user = session.exec(select(User).where(User.username == "directperm")).one()
        perm_codenames = {up.permission.codename for up in user.user_permissions}
        assert perm_codenames == {"delete_user"}

    def test_user_to_group_to_permission_chain(self, session: Session):
        from hyperadmin.auth.models import (
            Group,
            GroupPermission,
            Permission,
            User,
            UserGroup,
        )

        user = User(username="chainuser", email="chain@t.com", password_hash="h")
        group = Group(name="ChainGroup")
        perm = Permission(codename="change_user", name="Can change user")
        session.add_all([user, group, perm])
        session.commit()

        session.add(UserGroup(user_id=user.id, group_id=group.id))
        session.add(GroupPermission(group_id=group.id, permission_id=perm.id))
        session.commit()

        session.expire_all()
        user = session.exec(select(User).where(User.username == "chainuser")).one()

        # Traverse: user -> user_groups -> group -> group_permissions -> permission
        inherited_perms: set[str] = set()
        for ug in user.user_groups:
            for gp in ug.group.group_permissions:
                inherited_perms.add(gp.permission.codename)

        assert inherited_perms == {"change_user"}


class TestExports:
    def test_imports_from_auth(self):
        from hyperadmin.auth import (
            Group,
            GroupPermission,
            Permission,
            User,
            UserGroup,
            UserPermission,
        )

        assert User is not None
        assert Group is not None
        assert Permission is not None
        assert UserGroup is not None
        assert UserPermission is not None
        assert GroupPermission is not None

    def test_no_core_views_adapters_imports(self):
        """auth/models.py must not import from core/, views/, or adapters/."""
        import ast
        from pathlib import Path

        source = Path("src/hyperadmin/auth/models.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("hyperadmin.core"), (
                    f"Forbidden import: {node.module}"
                )
                assert not node.module.startswith("hyperadmin.views"), (
                    f"Forbidden import: {node.module}"
                )
                assert not node.module.startswith("hyperadmin.adapters"), (
                    f"Forbidden import: {node.module}"
                )
