import click
from flask.cli import with_appcontext
from app.models.user import User
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
        User.create_table()
        click.echo('Users table created successfully.')
    except Exception as e:
        click.echo(f'Error creating users table: {e}', err=True)

@db.command()
@click.option('--username', prompt=True, help='Username for the admin user')
@click.option('--email', prompt=True, help='Email for the admin user')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Password for the admin user')
@with_appcontext
def create_admin(username, email, password):
    """Create an admin user."""
    try:
        user = User.create_user(username, email, password, is_admin=True)
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
        user = User.create_user(username, email, password, is_admin=False)
        if user:
            click.echo(f'User {username} created successfully.')
        else:
            click.echo('Failed to create user.', err=True)
    except Exception as e:
        click.echo(f'Error creating user: {e}', err=True)

def init_app(app):
    """Register CLI commands with the app."""
    app.cli.add_command(db) 