#!/usr/bin/env python3
"""
Database initialization script.
Run this to create/update the database schema including the new TopicSection table.
"""

import os
from app import app, db

def init_database():
    with app.app_context():
        print("Creating all database tables...")
        db.create_all()
        print("✅ Database initialized successfully!")
        print("\nDatabase tables:")
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        for table_name in inspector.get_table_names():
            print(f"  - {table_name}")

if __name__ == '__main__':
    init_database()
