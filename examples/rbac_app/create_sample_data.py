from sqlmodel import Session, SQLModel
from sqlmodel.sql.expression import select

from .db import engine
from .models import Group, Permission, User, UserGroup, UserPermissions


# Database initialization
def create_tables():
    """Create database tables."""
    SQLModel.metadata.create_all(engine)


def create_sample_data():
    """Create sample data for demonstration."""

    with Session(bind=engine) as session:
        # Check if data already exists
        if session.exec(select(User)).first():
            return

        # Create sample permissions
        permissions = [
            Permission(name="Can add user", codename="add_user", content_type="user"),
            Permission(name="Can change user", codename="change_user", content_type="user"),
            Permission(name="Can delete user", codename="delete_user", content_type="user"),
            Permission(name="Can view user", codename="view_user", content_type="user"),
            Permission(name="Can add group", codename="add_group", content_type="group"),
            Permission(name="Can change group", codename="change_group", content_type="group"),
            Permission(name="Can delete group", codename="delete_group", content_type="group"),
            Permission(name="Can view group", codename="view_group", content_type="group"),
        ]

        for perm in permissions:
            session.add(perm)
        session.commit()

        # Create sample groups
        groups = [
            Group(
                name="Administrators",
                description="System administrators with full access",
            ),
            Group(name="Editors", description="Content editors with limited access"),
            Group(name="Viewers", description="Read-only access users"),
        ]

        for group in groups:
            session.add(group)
        session.commit()

        # Create sample users
        users = [
            User(
                username="admin",
                email="admin@example.com",
                first_name="Admin",
                last_name="User",
                is_superuser=True,
            ),
            User(
                username="editor",
                email="editor@example.com",
                first_name="Editor",
                last_name="User",
            ),
            User(
                username="viewer",
                email="viewer@example.com",
                first_name="Viewer",
                last_name="User",
            ),
        ]

        for user in users:
            session.add(user)
        session.commit()

        # Create user-group relationships
        admin_user = session.query(User).filter(User.username == "admin").first()
        editor_user = session.query(User).filter(User.username == "editor").first()
        viewer_user = session.query(User).filter(User.username == "viewer").first()

        admin_group = session.query(Group).filter(Group.name == "Administrators").first()
        editor_group = session.query(Group).filter(Group.name == "Editors").first()
        viewer_group = session.query(Group).filter(Group.name == "Viewers").first()

        user_groups = [
            UserGroup(user_id=admin_user.id, group_id=admin_group.id),
            UserGroup(user_id=editor_user.id, group_id=editor_group.id),
            UserGroup(user_id=viewer_user.id, group_id=viewer_group.id),
        ]

        for ug in user_groups:
            session.add(ug)
        session.commit()

        # Create user permissions
        admin_permissions = session.query(Permission).all()
        editor_permissions = (
            session.query(Permission)
            .filter(Permission.codename.in_(["view_user", "view_group", "change_user"]))
            .all()
        )
        viewer_permissions = (
            session.query(Permission)
            .filter(Permission.codename.in_(["view_user", "view_group"]))
            .all()
        )

        # Grant permissions to admin
        for perm in admin_permissions:
            session.add(UserPermissions(user_id=admin_user.id, permission_id=perm.id))

        # Grant permissions to editor
        for perm in editor_permissions:
            session.add(UserPermissions(user_id=editor_user.id, permission_id=perm.id))

        # Grant permissions to viewer
        for perm in viewer_permissions:
            session.add(UserPermissions(user_id=viewer_user.id, permission_id=perm.id))

        session.commit()
