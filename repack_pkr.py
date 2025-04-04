#!/usr/bin/env python3

import sys
import os
import struct

# Assuming common.py is in the same directory or accessible via PYTHONPATH
try:
    from common import write8, write16, write32, write_string
except ImportError:
    print("Error: Could not import functions from common.py.")
    print("Ensure common.py is in the same directory or in your PYTHONPATH.")
    sys.exit(1)

def repack_pkr(input_dir, output_pkr_file):
    """
    Repacks a directory structure into a THPS2 PKR file.

    Args:
        input_dir (str): The path to the directory to repack.
        output_pkr_file (str): The path for the output .pkr file.
    """

    # --- 1. Collect files and directories ---
    dirs_to_pack = [] # List of tuples: (relative_dir_path, [file_name1, file_name2, ...])
    all_files_info = [] # List of tuples: (relative_dir_path, file_name, full_file_path, file_size)
    total_file_count = 0

    base_input_dir = os.path.abspath(input_dir)

    # First pass to get all directories including empty ones and collect files
    temp_dirs = {} # Use dict to store files per dir path
    for root, dirnames, filenames in os.walk(base_input_dir):
        relative_dir = os.path.relpath(root, base_input_dir).replace('\\', '/')
        pkr_dir_name = relative_dir if relative_dir != '.' else '/' # Use '/' for root
        if pkr_dir_name != '/' and not pkr_dir_name.endswith('/'):
             pkr_dir_name += '/' # Ensure trailing slash for subdirs

        # Store directory even if empty, using pkr_dir_name as key
        if pkr_dir_name not in temp_dirs:
            temp_dirs[pkr_dir_name] = []

        # Filter files (e.g., remove hidden)
        filenames = [f for f in filenames if not f.startswith('.')]
        dirnames[:] = [d for d in dirnames if not d.startswith('.')] # Modify in-place

        temp_dirs[pkr_dir_name].extend(filenames)

        for filename in filenames:
            full_path = os.path.join(root, filename)
            file_size = os.path.getsize(full_path)
            all_files_info.append((pkr_dir_name, filename, full_path, file_size))
            total_file_count += 1

    # Create dirs_to_pack list from temp_dirs, perhaps sorted?
    # THPS PKR might expect a specific order? Let's sort by name for consistency.
    sorted_dir_names = sorted(temp_dirs.keys())
    for pkr_dir_name in sorted_dir_names:
        dirs_to_pack.append((pkr_dir_name, sorted(temp_dirs[pkr_dir_name]))) # Sort files within dir too

    # Sort all_files_info consistently
    all_files_info.sort(key=lambda x: (x[0], x[1]))

    num_directories = len(dirs_to_pack)

    # --- 2. Calculate layout and offsets ---
    # Placeholder Magic and Version - Replace with actual known values if available
    PKR_MAGIC = 0x32524B50 # Updated from ALL.PKR
    PKR_VERSION = 0x00000001 # Updated from ALL.PKR

    header_size = 16 # magic, version, num_dir, num_file (4 bytes each)
    dir_entry_size = 32 + 4 + 4 # name (32), offset (4), count (4)
    dir_table_size = num_directories * dir_entry_size

    file_entry_size = 32 + 4 + 4 + 4 + 4 # name (32), unk1 (4), data_offset (4), size1 (4), size2 (4)
    total_file_tables_size = 0
    dir_offsets = {} # Store calculated offset for each directory's file table
    current_file_table_offset = header_size + dir_table_size
    for pkr_dir_name, filenames in dirs_to_pack:
        dir_offsets[pkr_dir_name] = current_file_table_offset
        file_table_size = len(filenames) * file_entry_size
        total_file_tables_size += file_table_size
        current_file_table_offset += file_table_size

    file_data_offsets = {}
    current_data_offset = header_size + dir_table_size + total_file_tables_size
    for pkr_dir_name, file_name, full_file_path, file_size in all_files_info:
        file_key = os.path.join(pkr_dir_name, file_name).replace('\\', '/')
        current_data_offset += file_size

    try:
        with open(output_pkr_file, "wb") as f:
            print(f"Writing header...")
            write32(f, PKR_MAGIC)
            write32(f, PKR_VERSION)
            write32(f, num_directories)
            write32(f, total_file_count)
            print(f"  Magic: 0x{PKR_MAGIC:08X}, Version: 0x{PKR_VERSION:08X}, Dirs: {num_directories}, Files: {total_file_count}")

            print(f"Writing directory table ({num_directories} entries)...")
            for pkr_dir_name, filenames in dirs_to_pack:
                file_count = len(filenames)
                offset = dir_offsets[pkr_dir_name]
                print(f"  Dir: '{pkr_dir_name}', Files: {file_count}, File Table Offset: 0x{offset:08X}")
                write_string(f, pkr_dir_name, 32) # Pad/truncate to 32 bytes
                write32(f, offset)
                write32(f, file_count)

            print(f"Writing file tables...")
            for pkr_dir_name, filenames in dirs_to_pack:
                offset = dir_offsets[pkr_dir_name]
                f.seek(offset)
                print(f"  Writing file table for '{pkr_dir_name}' at 0x{offset:08X}...")

                for file_name in filenames:
                    file_key = os.path.join(pkr_dir_name, file_name).replace('\\', '/')
                    file_info = next((info for info in all_files_info if os.path.join(info[0], info[1]).replace('\\', '/') == file_key), None)
                    if file_info:
                        _, _, _, file_size = file_info
                        data_offset = file_data_offsets[file_key]
                        print(f"    File: '{file_name}', Size: {file_size}, Data Offset: 0x{data_offset:08X}")
                        write_string(f, file_name, 32)
                        write32(f, 0xFFFFFFFE)  
                        write32(f, file_size)
                        write32(f, file_size)
                    else:
                         print(f"Error: Could not find file info for {file_key}")

            print(f"Writing file data...")
            f.seek(header_size + dir_table_size + total_file_tables_size)
            for pkr_dir_name, file_name, full_file_path, file_size in all_files_info:
                file_key = os.path.join(pkr_dir_name, file_name).replace('\\', '/')
                data_offset = file_data_offsets[file_key]
                if f.tell() != data_offset:
                     print(f"Warning: Current position 0x{f.tell():08X} does not match expected data offset 0x{data_offset:08X} for '{file_key}'. Seeking.")
                     f.seek(data_offset)

                print(f"  Writing {file_size} bytes for '{file_key}' at 0x{f.tell():08X}...")
                try:
                    with open(full_file_path, "rb") as infile:
                        data = infile.read()
                        if len(data) != file_size:
                            print(f"Warning: Actual size of {full_file_path} ({len(data)}) differs from calculated size ({file_size}). Using actual size.")
                        f.write(data)
                except IOError as e:
                    print(f"Error reading file {full_file_path}: {e}")
                    print(f"Writing {file_size} zero bytes instead.")
                    f.write(b'\0' * file_size)

        print(f"\nSuccessfully repacked '{input_dir}' into '{output_pkr_file}'")
        return True

    except IOError as e:
        print(f"Error writing output file {output_pkr_file}: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during repack: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python repack-pkr.py <input_directory> <output_pkr_file>")
        sys.exit(1)

    input_directory = sys.argv[1]
    output_file = sys.argv[2]

    if not os.path.isdir(input_directory):
        print(f"Error: Input directory '{input_directory}' not found or is not a directory.")
        sys.exit(1)

    repack_pkr(input_directory, output_file) 