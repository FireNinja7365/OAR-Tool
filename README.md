# OAR-Tool (Fork)

## A Save File Editor For One Armed Robber

Forked to add support for new map additions without triggering altered save game error and without acquiring a .sav file that already has the map purchased.

**Added: Harbour Map**

## Included Features
- Easy Account Selection
- Map Unlocker
- Cosmetic Unlocker
- Custom Level & Max Skills
- Custom Amount Of Cash

---

## How New Maps Were Added

### Steps Taken

1. **Reverse engineered `Maps.sav`** to understand structure, required size, and count

2. **Discovered the GVAS structure:**
   - Position 1212: Array data size (4 bytes, little-endian)
   - Position 1240: Element count (4 bytes, little-endian)
   - Position 1244+: Map entries as `[4-byte length][path string + null terminator]`

3. **Extracted the format of map entries:**
   ```
   /Game/Maps/Menu/BP/Shop/Maps/ShopItem_Map_{map_name}.ShopItem_Map_{map_name}_C
   ```

4. **Used FModel to unpack the game `.pak` file** and get the map package paths:
   ```
   OAR/Content/Maps/Menu/BP/Shop/Maps/ShopItem_Map_base.uasset
   OAR/Content/Maps/Menu/BP/Shop/Maps/ShopItem_Map_BlackDiamondCasino.uasset
   OAR/Content/Maps/Menu/BP/Shop/Maps/ShopItem_Map_CarMansion.uasset
   OAR/Content/Maps/Menu/BP/Shop/Maps/ShopItem_Map_EscoBar.uasset
   OAR/Content/Maps/Menu/BP/Shop/Maps/ShopItem_Map_FIA.uasset
   OAR/Content/Maps/Menu/BP/Shop/Maps/ShopItem_Map_Harbour.uasset
   OAR/Content/Maps/Menu/BP/Shop/Maps/ShopItem_Map_JewelleryStore.uasset
   OAR/Content/Maps/Menu/BP/Shop/Maps/ShopItem_Map_Museum.uasset
   OAR/Content/Maps/Menu/BP/Shop/Maps/ShopItem_Map_OrbitalBank.uasset
   OAR/Content/Maps/Menu/BP/Shop/Maps/ShopItem_Map_Sciencelab.uasset
   OAR/Content/Maps/Menu/BP/Shop/Maps/ShopItem_Map_Small_Bank.uasset
   OAR/Content/Maps/Menu/BP/Shop/Maps/ShopItem_Map_Test.uasset
   OAR/Content/Maps/Menu/BP/Shop/Maps/ShopItem_Map_WineShop.uasset
   ```

5. **Implemented `patch_maps.py`** - A script that automatically adds any map using the map name acquired from the `.pak` file into `Maps.sav`, with regards to the GVAS structure and entry format. Automatically patches `Maps.sav` and keeps a backup of the unpatched version.

6. **Used the existing `OAR_tool.py`** to patch the account save files with the updated `Maps.sav`

**Result:** Game did not detect alteration and map unlocked successfully.

---

## Adding Future Maps

When new maps are added to the game:

```bash
python patch_maps.py              # List current maps
python patch_maps.py <MapName>    # Add a new map (e.g., CarMansion)
```

---

## Original Repository
🔗 [FireNinja7365/OAR-Tool](https://github.com/FireNinja7365/OAR-Tool)
