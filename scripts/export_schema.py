"""Export MySQL DDL from the same schema used by Python."""
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import mysql
from src.config import ROOT
from src.database import metadata

parts = ['-- Generated from src/database.py. MySQL 8.0+.\nCREATE DATABASE IF NOT EXISTS supply_chain CHARACTER SET utf8mb4;\nUSE supply_chain;']
for table in metadata.sorted_tables:
    parts.append(str(CreateTable(table, if_not_exists=True).compile(dialect=mysql.dialect()))+';')
    for index in table.indexes:
        parts.append(str(CreateIndex(index).compile(dialect=mysql.dialect()))+';')
(ROOT/'sql/01_schema.sql').write_text('\n\n'.join(parts), encoding='utf-8')
