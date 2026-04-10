import os
import re

def rename_files_in_folder(folder_path):
    # Pattern: index_filename - date.ext
    # Example: 17_Revise Automotive ... - 20121212.pdf
    pattern = re.compile(r'^(\d+)_([^-\n]+?)\s*-\s*(\d{8})\.(.+)$')

    for filename in os.listdir(folder_path):
        match = pattern.match(filename)
        if match:
            index, title, date, ext = match.groups()

            # Clean title whitespace
            title = title.strip()

            # New filename format: date_title.ext
            new_filename = f"{date}_{title}.{ext}"

            old_path = os.path.join(folder_path, filename)
            new_path = os.path.join(folder_path, new_filename)

            print(f"Renaming:\n  {filename}\n→ {new_filename}")
            os.rename(old_path, new_path)

if __name__ == "__main__":
    folder = input("Enter folder path: ").strip()
    if os.path.isdir(folder):
        rename_files_in_folder(folder)
        print("Renaming complete!")
    else:
        print("Invalid folder path.")
