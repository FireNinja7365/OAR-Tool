"""
Script to add new maps to the Maps.sav file for OAR Tool.
This patches the GVAS save file to include additional map entries.
"""

import struct
import shutil
from pathlib import Path


def read_maps_sav(filepath: Path) -> tuple[bytes, int, int, int, list[str]]:
    """
    Read Maps.sav and extract structure info.
    Returns: (file_bytes, array_size_pos, count_pos, entries_start_pos, map_paths)
    """
    with open(filepath, 'rb') as f:
        data = bytearray(f.read())
    
    # Find "MapsSave" marker
    maps_save_pos = data.find(b'MapsSave\x00')
    if maps_save_pos == -1:
        raise ValueError("Could not find MapsSave marker")
    
    # Structure after MapsSave:
    # - 1 byte null terminator (already in search)
    # - 4 bytes: length of "ArrayProperty" string (14)
    # - 14 bytes: "ArrayProperty\x00"
    # - 4 bytes: array data size
    # - 4 bytes: padding (zeros)
    # - 4 bytes: length of inner type string (15)
    # - 15 bytes: "ObjectProperty\x00"
    # - 1 byte: null
    # - 4 bytes: element count
    # - entries...
    
    array_prop_pos = maps_save_pos + 9  # After "MapsSave\x00"
    array_size_pos = array_prop_pos + 4 + 14  # After length + "ArrayProperty\x00"
    count_pos = array_size_pos + 4 + 4 + 4 + 15 + 1  # After size, padding, inner type
    entries_start = count_pos + 4
    
    array_size = struct.unpack('<I', data[array_size_pos:array_size_pos+4])[0]
    count = struct.unpack('<I', data[count_pos:count_pos+4])[0]
    
    print(f"Array size position: {array_size_pos}")
    print(f"Array data size: {array_size} bytes")
    print(f"Count position: {count_pos}")
    print(f"Element count: {count}")
    print(f"Entries start: {entries_start}")
    
    # Read existing entries
    pos = entries_start
    map_paths = []
    for i in range(count):
        str_len = struct.unpack('<I', data[pos:pos+4])[0]
        path = data[pos+4:pos+4+str_len-1].decode('ascii')  # -1 to exclude null
        map_paths.append(path)
        pos += 4 + str_len
    
    return bytes(data), array_size_pos, count_pos, entries_start, map_paths


def add_map_entry(filepath: Path, new_map_name: str, output_path: Path = None):
    """
    Add a new map entry to Maps.sav
    new_map_name: Just the map name, e.g., "Harbour"
    """
    data, array_size_pos, count_pos, entries_start, existing_maps = read_maps_sav(filepath)
    data = bytearray(data)
    
    # Build the full path for the new map
    new_path = f"/Game/Maps/Menu/BP/Shop/Maps/ShopItem_Map_{new_map_name}.ShopItem_Map_{new_map_name}_C"
    
    # Check if already exists
    if new_path in existing_maps:
        print(f"Map '{new_map_name}' already exists in the save file!")
        return
    
    print(f"\nExisting maps:")
    for i, m in enumerate(existing_maps):
        print(f"  {i+1}. {m}")
    
    print(f"\nAdding: {new_path}")
    
    # Calculate positions
    # Find where the last entry ends (where we'll insert)
    pos = entries_start
    for path in existing_maps:
        str_len = len(path) + 1  # +1 for null terminator
        pos += 4 + str_len
    
    insert_pos = pos
    print(f"Insert position: {insert_pos}")
    
    # Create the new entry bytes
    new_path_bytes = new_path.encode('ascii') + b'\x00'
    new_entry = struct.pack('<I', len(new_path_bytes)) + new_path_bytes
    new_entry_size = len(new_entry)
    
    print(f"New entry size: {new_entry_size} bytes")
    
    # Update array data size
    old_array_size = struct.unpack('<I', data[array_size_pos:array_size_pos+4])[0]
    new_array_size = old_array_size + new_entry_size
    data[array_size_pos:array_size_pos+4] = struct.pack('<I', new_array_size)
    
    # Update element count
    old_count = struct.unpack('<I', data[count_pos:count_pos+4])[0]
    new_count = old_count + 1
    data[count_pos:count_pos+4] = struct.pack('<I', new_count)
    
    # Insert the new entry
    data = data[:insert_pos] + new_entry + data[insert_pos:]
    
    print(f"\nUpdated array size: {old_array_size} -> {new_array_size}")
    print(f"Updated count: {old_count} -> {new_count}")
    
    # Write output
    if output_path is None:
        output_path = filepath
    
    with open(output_path, 'wb') as f:
        f.write(data)
    
    print(f"\nSaved to: {output_path}")


def main():
    import sys
    
    script_files = Path(__file__).parent / "Script Files"
    maps_sav = script_files / "Maps.sav"
    
    # If command line arg provided, use it as map name
    if len(sys.argv) > 1:
        map_name = sys.argv[1]
    else:
        # Default: show current maps and prompt
        print("Current maps in Maps.sav:")
        _, _, _, _, maps = read_maps_sav(maps_sav)
        for i, m in enumerate(maps):
            short_name = m.split("ShopItem_Map_")[1].split(".")[0]
            print(f"  {i+1}. {short_name}")
        
        print("\nUsage: python patch_maps.py <MapName>")
        print("Example: python patch_maps.py Harbour")
        return
    
    # Backup original if not exists
    backup_path = script_files / "Maps.sav.backup"
    if not backup_path.exists():
        shutil.copy(maps_sav, backup_path)
        print(f"Backup created: {backup_path}")
    
    # Add the map
    add_map_entry(maps_sav, map_name)
    
    # Verify the result
    print("\n" + "="*50)
    print("Verification:")
    _, _, _, _, maps = read_maps_sav(maps_sav)
    print(f"\nAll maps in updated file:")
    for i, m in enumerate(maps):
        short_name = m.split("ShopItem_Map_")[1].split(".")[0]
        print(f"  {i+1}. {short_name}")


if __name__ == "__main__":
    main()
