import os

# Список папок, которые необходимо пропустить
EXCLUDED_DIRS = {'venv', '.venv', 'migrations', '__pycache__', 'static', 'uploads', 'templates',"media",'.git'}

def print_directory_tree(root_dir, prefix=""):
    # Сортируем папки и файлы для более организованного вывода
    items = sorted(os.listdir(root_dir))
    total_items = len(items)

    for index, item in enumerate(items):
        path = os.path.join(root_dir, item)
        
        # Пропускаем папки, указанные в EXCLUDED_DIRS
        if item in EXCLUDED_DIRS and os.path.isdir(path):
            continue

        connector = "└── " if index == total_items - 1 else "├── "
        
        # Печатаем текущую папку или файл
        print(prefix + connector + item)

        # Если это директория, рекурсивно выводим её содержимое
        if os.path.isdir(path):
            extension = "    " if index == total_items - 1 else "│   "
            print_directory_tree(path, prefix + extension)

if __name__ == "__main__":
    root_directory = "."  # Задаем начальную директорию
    print("Directory structure:")
    print_directory_tree(root_directory)
