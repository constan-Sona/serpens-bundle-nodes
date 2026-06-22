# Serpens Bundle Nodes

Custom nodes for the [Serpens](https://blendermarket.com/products/serpens) addon (Blender Visual Scripting) that replicate Geometry Nodes' **Bundles**: group several values of different types into a single "Bundle" socket, unpack them with auto-mirroring, send them without wires through a portal, build them from a JSON file, iterate lists of objects, and pick items by index or name.

> Community add-on, not made by the Serpens dev. Use at your own risk. Feedback welcome!

---

## Nodes (Add → Bundle)

### Core

| Node | Description |
|------|-------------|
| **Combine Bundle** | Packs dynamic typed inputs into a bundle. Inputs can also be bundles themselves (object or array) — plug one in and the input converts automatically, so you can nest bundles inside bundles. Press `+` to add inputs, name them, pick their type. |
| **Separate Bundle** | Auto-mirrors a bundle source and unpacks it (Combine, JSON, Loop item, Index item, or another Separate's nested output). |
| **Bundle Portal** | Sends a bundle without a wire, matched by name. Toggle In / Out with the same name to carry the bundle across the node tree. |
| **Merge Bundles** | Merges two bundles into one. |
| **Print Bundle** | Prints all key/value pairs of a bundle in the Execute flow — on the node and in the console. Supports nested bundles. "Print On Node" toggle + clear button. |

### Utils

| Node | Description |
|------|-------------|
| **Bundle Length** | Number of items in an array bundle, or number of keys in an object bundle. |
| **Index Bundle Array** | Picks ONE item from an array bundle by position (Index mode) or by its `"name"` key (Name mode). Crash-proof: out-of-range / not-found → empty. |
| **Bundle Get Key** | Gets a single key's value from an object bundle. |
| **Bundle Keys** | Returns all keys of an object bundle as a list. |
| **Array To Bundle** | Converts a plain list to a bundle array. |
| **Bundle To Array** | Converts a bundle array to a plain list. |
| **Filter Bundle Array** | Filters items of an array bundle by a condition. |

### Interface (UI)

| Node | Description |
|------|-------------|
| **Bundle Search** | A searchable dropdown of the items' `"name"` key; outputs the matching Item (bundle) + the selected Name. |
| **Bundle UI List** | Displays a bundle array as a UI list. |
| **Display Bundle** | Displays a bundle's contents in the UI. |

### JSON

| Node | Description |
|------|-------------|
| **JSON Read** | Reads the `.json` file from its "Path" input and auto-generates a typed output per top-level key. Nested objects → Bundle; arrays of objects → Bundle (square); flat arrays → List. Refresh button re-reads the file. |
| **JSON Write** | Writes a bundle to a `.json` file. |
| **JSON Edit Key** | Edits a single key in a JSON file. |

### Loops

| Node | Description |
|------|-------------|
| **Loop For Bundle** (Execute) | Iterates an array bundle; each iteration provides an "Item" bundle + Index. Connect Item to a Separate Bundle to read each element's fields. For logic/execute flows. |
| **Loop For Bundle** (Interface) | Same as above, for UI drawing flows. |
| **Loop Repeat Bundle** (Execute) | Repeats a bundle-based loop a fixed number of times. For logic/execute flows. |
| **Loop Repeat Bundle** (Interface) | Same as above, for UI drawing flows. |

---

## Socket Types

The Bundle socket is **pink** (`#FF5AAD`).

- **Diamond** = a normal (object) bundle → feed a **Separate Bundle**
- **Square** = an array-of-objects bundle → feed a **Loop For Bundle** / **Index Bundle Array** / **Bundle Search** (their inputs are square too, showing they expect an array)

---

## Requirements

- Blender (tested on 4.2+)
- [Serpens](https://blendermarket.com/products/serpens) addon installed and enabled (`blender_visual_scripting_addon`)

---

## Installation

1. **Close Blender.**
2. Find the Serpens addon folder, usually at:
   ```
   %APPDATA%\Blender Foundation\Blender\<VERSION>\scripts\addons\blender_visual_scripting_addon
   ```
   *(on Windows, `<VERSION>` is e.g. `4.2`, `5.0`, `5.1` — use your Blender version)*
3. **Copy** the `blender_visual_scripting_addon` folder from this repo **into** the addon folder, keeping the subfolders. It only **adds** new files — it does not overwrite any existing Serpens file:
   ```
   blender_visual_scripting_addon\node_tree\sockets\bundle.py
   blender_visual_scripting_addon\nodes\Bundle\   (all .py files)
   ```
4. **Open Blender.** The nodes appear under **Add → Bundle**.

> **Note:** A simple addon reload (disable/enable) is **not** enough for new files. Restart Blender to load everything correctly.

---

## Quick Usage

### Bundles
1. **Combine Bundle** — press `+` to add inputs, name them, pick their type, connect values. Plugging a bundle (diamond or square) into a value input converts it automatically.
2. **Separate Bundle** — connect a Bundle to its input; its outputs mirror the source automatically.
3. **Bundle Portal** — create an **In** and an **Out** with the **same name** to carry a bundle without a wire.

### JSON
1. **JSON Read** — set the `.json` file in the "Path" input socket (type it, pick it with the folder icon, or wire it from e.g. Path Info). It builds a typed output per top-level key.
2. Drill into nested objects with **Separate Bundle**.
3. Iterate an array of objects (SQUARE socket) with **Loop For Bundle**, or pick a single item with **Index Bundle Array** (by Index or by Name) / **Bundle Search** (UI dropdown).
4. **Dynamic path** — wire the Path socket to switch files at runtime (e.g. one JSON per blend file). A reopened scene re-reads the file automatically.

---

## Notes & Limitations

- Bundle sockets only connect to other Bundle sockets.
- **Cycle-safe**: feeding a Separate output back into its bundle won't crash Blender (flags it, outputs `None`) — including through portals and multiple loops.
- JSON is for **stable schemas**. At runtime it's crash-proof: missing key/parent → `None`, extra keys ignored, bad index/name → empty item. The sockets reflect the file read at edit time.
- Feed the "Path" socket file-path strings (`FILE_PATH`); plain Strings with `\` can break — forward slashes always work. The runtime JSON loader caches per path.
- An **array of objects** is a Bundle holding the whole list (SQUARE socket) → use **Loop For Bundle** / **Index Bundle Array** / **Bundle Search** to read elements. A Separate on it shows "Empty or unknown bundle" on purpose. Flat arrays (strings/numbers) are a plain List socket.
- **Bundle Search** reads the array at the top level (JSON / portal / Separate chain); it can't read a bundle that only exists inside a loop iteration.
- Name mode (**Index Bundle Array** / **Bundle Search**) needs items to have a `"name"` key — the node warns if they don't.

---

## Changelog

### v1.1.0 — 2026-06-22
- **New node: Print Bundle** (Add → Bundle). Takes a Bundle input and an Execute flow; prints all key/value pairs on the node and in the console. Supports nested bundles. "Print On Node" toggle and clear button, same as the regular Print node.

### v1.0.0 — 2026-06-22
- Initial public release.
- Core nodes: Combine Bundle, Separate Bundle, Bundle Portal, Merge Bundles.
- Utils: Bundle Length, Index Bundle Array, Bundle Get Key, Bundle Keys, Array To Bundle, Bundle To Array, Filter Bundle Array.
- Interface nodes: Bundle Search, Bundle UI List, Display Bundle.
- JSON nodes: JSON Read, JSON Write, JSON Edit Key.
- Loop nodes: Loop For Bundle (Execute/Interface), Loop Repeat Bundle (Execute/Interface).
- Pink Bundle socket (`#FF5AAD`) with diamond (object) and square (array) variants.
- Cycle-safe Separate Bundle detection through portals and loops.
