import click
from flask.cli import with_appcontext
from app.models.user_sqlalchemy import UserORM
from app.database import get_db_context
import logging

@click.group()
def db():
    """Database management commands."""
    pass

@db.command()
@with_appcontext
def init_users():
    """Initialize the users table."""
    try:
        # Tables are created via Alembic migrations
        # Run: alembic upgrade head
        click.echo('Users table should be created via Alembic migrations.')
        click.echo('Run: alembic upgrade head')
        click.echo('If table already exists, this is normal.')
    except Exception as e:
        click.echo(f'Error: {e}', err=True)

@db.command()
@click.option('--username', prompt=True, help='Username for the admin user')
@click.option('--email', prompt=True, help='Email for the admin user')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Password for the admin user')
@with_appcontext
def create_admin(username, email, password):
    """Create an admin user."""
    try:
        with get_db_context() as db:
            user = UserORM.create(username, email, password, is_admin=True, db=db)
            db.commit()
            if user:
                click.echo(f'Admin user {username} created successfully.')
            else:
                click.echo('Failed to create admin user.', err=True)
    except Exception as e:
        click.echo(f'Error creating admin user: {e}', err=True)

@db.command()
@click.option('--username', prompt=True, help='Username for the user')
@click.option('--email', prompt=True, help='Email for the user')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Password for the user')
@with_appcontext
def create_user(username, email, password):
    """Create a regular user."""
    try:
        with get_db_context() as db:
            user = UserORM.create(username, email, password, is_admin=False, db=db)
            db.commit()
            if user:
                click.echo(f'User {username} created successfully.')
            else:
                click.echo('Failed to create user.', err=True)
    except Exception as e:
        click.echo(f'Error creating user: {e}', err=True)

def init_app(app):
    """Register CLI commands with the app."""
    app.cli.add_command(db) 