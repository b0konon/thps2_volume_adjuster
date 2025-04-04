#!/usr/bin/env python3

import sys
import os
import struct

from common import *

def extract_pkr(pkr_file_path, output_base_dir):
    """Extracts the contents of a PKR file.

    Args:
        pkr_file_path (str): Path to the .pkr file.
        output_base_dir (str): The directory to extract files into.

    Returns:
        bool: True if extraction was successful, False otherwise.
    """
    print(f"Starting extraction of '{pkr_file_path}' to '{output_base_dir}'...")
    try:
        with open(pkr_file_path, "rb") as f:
            magic = read32(f)
            version = read32(f)
            num_dir = read32(f)
            num_file = read32(f)

            # Basic validation
            if magic != 0x32524B50 or version != 0x00000001:
                print(f"Warning: Unexpected Magic (0x{magic:08X}) or Version (0x{version:08X}) for {pkr_file_path}", file=sys.stderr)

            print(f"  PKR Header: Magic=0x{magic:08X}, Version=0x{version:08X}, Dirs={num_dir}, Files={num_file}")

            known_files = 0

            os.makedirs(output_base_dir, exist_ok=True)

            dir_entries = []
            for i in range(num_dir):
                name = read_string(f, 32)
                offset = read32(f)
                count = read32(f)
                dir_entries.append({'name': name, 'offset': offset, 'count': count})
                print(f"  Dir Entry {i}: Name='{name}', Offset=0x{offset:08X}, Count={count}")

            for i, entry in enumerate(dir_entries):
                name = entry['name']
                offset = entry['offset']
                count = entry['count']

                print(f"Processing Dir: '{name}' ({count} files at offset 0x{offset:08X})")

                path_parts = [part for part in name.split('/') if part]
                current_dir_export_path = os.path.join(output_base_dir, *path_parts)
                os.makedirs(current_dir_export_path, exist_ok=True)

                known_files += count

                cursor = f.tell()
                f.seek(offset)
                for j in range(count):
                    file_name = read_string(f, 32)
                    unk1 = read32(f)
                    if unk1 != 0xFFFFFFFE:
                         print(f"Warning: Unexpected unk1 value (0x{unk1:08X}) for file '{file_name}' in dir '{name}'. Expected 0xFFFFFFFE.", file=sys.stderr)
                    data_offset = read32(f)
                    size1 = read32(f)
                    size2 = read32(f)
                    if size1 != size2:
                         print(f"Warning: Size mismatch ({size1} != {size2}) for file '{file_name}' in dir '{name}'.", file=sys.stderr)

                    print(f"    File Entry {j}: Name='{file_name}', Data Offset=0x{data_offset:08X}, Size={size1}")

                    file_cursor = f.tell()
                    f.seek(data_offset)

                    file_export_path = os.path.join(current_dir_export_path, file_name)

                    try:
                        with open(file_export_path, "wb") as fo:
                            data = f.read(size1)
                            if len(data) != size1:
                                print(f"Warning: Read {len(data)} bytes, expected {size1} for file '{file_export_path}'", file=sys.stderr)
                            fo.write(data)
                    except IOError as e:
                        print(f"Error writing file {file_export_path}: {e}", file=sys.stderr)
                    f.seek(file_cursor)

                # Restore position after processing this directory's file table
                # Where should we be? If file tables are contiguous, we should be at offset + count * file_entry_size
                # If they are not contiguous, we need the original cursor after reading dir table.
                # Let's assume they might not be contiguous and restore the cursor position from after the *directory* table read
                # This seems wrong based on extract-pkr's original logic. It read file table then restored cursor to *after* dir table.
                # The original script used f.seek(cursor) where cursor was f.tell() *after* reading the dir table.
                # Let's rethink: The offset in the dir entry points to the *start* of that dir's file table.
                # We seek there, read the file table, extract data, seek back to file table pos.
                # After the inner loop finishes, where should the main loop continue? It should read the *next* dir entry.
                # Ah, the original script saved f.tell() *before* seeking to the file table offset, and restored it after processing *all* files in that directory.
                # Let's replicate that.

                # NO - Wait, the original script saved the position *before* the f.seek(offset) for the *directory*, not inside the loop.
                # Let's re-examine extract-pkr.py lines 27-57
                # Line 27: cursor = f.tell() (Position after reading dir entry N)
                # Line 28: f.seek(offset) (Go to file table for dir N)
                # Line 30-55: Loop through files in dir N, seeking to data_offset and back to file_cursor within loop.
                # Line 57: f.seek(cursor) (Return to position after reading dir entry N)
                # This seems correct. Let's add the cursor save/restore.

            # The outer loop already advanced the file pointer through the dir table.
            # The file reading seeks around. We don't need explicit seeks between dir processing if the file table reading logic is self-contained.
            # Let's remove the cursor save/restore around the inner loop for now, assuming file table reads correctly position for next entry.

        print(f"Extraction finished. {known_files} / {num_file} files processed.")
        return True

    except FileNotFoundError:
        print(f"Error: Input file not found: {pkr_file_path}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"An unexpected error occurred during extraction: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False

# Keep the command-line execution part for standalone use (optional)
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python extract-pkr.py <input_pkr_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = "out" # Default output directory

    if not os.path.isfile(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)

    if not extract_pkr(input_file, output_dir):
        print(f"Extraction failed for {input_file}")
        sys.exit(1)
    else:
        print(f"Extraction completed successfully into '{output_dir}' directory.")

