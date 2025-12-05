import os

for root, dirs, files in os.walk("."):
    # Пропускаем директорию .venv
    if ".venv" in root:
        continue

    if "migrations" in dirs:
        migration_dir = os.path.join(root, "migrations")
        for file in os.listdir(migration_dir):
            if file != "__init__.py" and file.endswith(".py"):
                os.remove(os.path.join(migration_dir, file))
            if file.endswith(".pyc"):
                os.remove(os.path.join(migration_dir, file))
