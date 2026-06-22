SERPENS BUNDLE NODES
====================

Custom nodes for the Serpens addon (Visual Scripting / blender_visual_scripting_addon)
that replicate Geometry Nodes' Bundles: group several values of different types into a single
"Bundle" socket, unpack them with auto-mirroring, send them without wires through a portal,
build them from a JSON file, iterate lists of objects, and pick items by index or name.

Contents (all under  Add (Shift+A) -> Bundle):
- Combine Bundle            -> packs dynamic typed inputs into a bundle. Inputs can also be
                               bundles themselves (object or array) - plug one in and the input
                               converts automatically, so you can nest bundles inside bundles.
- Separate Bundle           -> auto-mirrors a bundle source and unpacks it (Combine, JSON,
                               Loop item, Index item, or another Separate's nested output).
- Bundle Portal             -> sends a bundle without a wire (matched by name). In / Out toggle.
- Bundle Length             -> number of items in an array bundle (or keys in an object bundle).
- Loop For Bundle (Execute)   \
- Loop For Bundle (Interface)  } iterate an array bundle; each iteration gives an "Item" bundle
- Loop Repeat Bundle (Execute) } (+ Index/Step). Connect Item to a Separate Bundle to read each
- Loop Repeat Bundle (Interface)/ element's fields. Execute = logic, Interface = UI drawing.
- Index Bundle Array        -> picks ONE item from an array bundle, by position (Index mode) or
                               by its "name" key (Name mode). Outputs the Item bundle. Crash-proof
                               (out-of-range / not-found -> empty). Like Index Collection Property,
                               but for bundles.
- Bundle Search             -> a searchable dropdown of the items' "name"; outputs the matching
                               Item (bundle) + the selected Name.
- JSON Read                 -> reads the .json file given in its "Path" input socket and
                               auto-generates a typed output per top-level key. Nested objects ->
                               Bundle; arrays of objects -> Bundle (square); flat arrays -> List.
                               Refresh button re-reads the file.

Socket shapes/colors: the Bundle socket is pink (#FF5AAD). DIAMOND = a normal (object) bundle ->
feed a Separate Bundle. SQUARE = an array-of-objects bundle -> feed a Loop For Bundle / Index
Bundle Array / Bundle Search (their inputs are square too, showing they expect an array).


REQUIREMENTS
------------
Requires the Serpens addon installed and enabled (module: blender_visual_scripting_addon).
These files are added INSIDE that addon's folder.


INSTALLATION (merge into the Serpens addon)
-------------------------------------------
1. Close Blender.
2. Find the Serpens addon folder. It's usually at:
     %APPDATA%\Blender Foundation\Blender\<VERSION>\scripts\addons\blender_visual_scripting_addon
   (on Windows, <VERSION> is e.g. 4.2, 5.0, 5.1 ...; use your Blender version)
3. Copy this zip's "blender_visual_scripting_addon" folder INTO the addon folder, keeping the
   subfolders. It only ADDS new files, it does not overwrite any existing one:
     blender_visual_scripting_addon\node_tree\sockets\bundle.py
     blender_visual_scripting_addon\nodes\Bundle\   (all the .py files)
4. Open Blender. The nodes appear under Add -> Bundle.

Note: if Blender is open, just restart it. A simple addon reload (disable/enable) is NOT enough
for NEW files; restarting Blender loads everything fresh and correctly.


QUICK USAGE
-----------
Bundles:
1. "Combine Bundle": press "+" to add inputs, name them, pick their type, connect values.
   Plugging a bundle (diamond or square) into a value input converts it automatically.
2. "Separate Bundle": connect a Bundle to its input; its outputs mirror the source automatically.
3. "Bundle Portal": In + Out with the SAME name carries a bundle without a wire.

JSON:
1. "JSON Read": set the .json file in the "Path" input socket (type it, pick it with the folder
   icon, or wire it from e.g. Path Info). It builds a typed output per top-level key.
2. Drill nested objects with a "Separate Bundle".
3. Iterate an array of objects (SQUARE socket) with a "Loop For Bundle", or pick a single item
   with "Index Bundle Array" (by Index or by Name) / "Bundle Search" (UI dropdown).
4. Dynamic path: wire the Path socket to switch files at RUNTIME (e.g. one JSON per blend file).
   A reopened scene re-reads the file automatically.


NOTES / LIMITATIONS
-------------------
- Bundle sockets only connect to other Bundle sockets.
- Cycle-safe: feeding a Separate output back into its bundle won't crash Blender (flags it, outputs
  None) - including through portals and multiple loops.
- JSON is for STABLE schemas. At runtime it's crash-proof: missing key/parent -> None, extra keys
  ignored, bad index/name -> empty item. The sockets reflect the file read at edit time.
- Feed the "Path" socket file-path strings (FILE_PATH); plain Strings with "\" can break - forward
  slashes always work. The runtime JSON loader caches per path.
- An array of objects is a Bundle holding the whole list (SQUARE socket) -> use Loop For Bundle /
  Index Bundle Array / Bundle Search to read elements (a Separate on it shows "Empty or unknown
  bundle" on purpose). Flat arrays (strings/numbers) are a plain List socket.
- Bundle Search reads the array at the top level (JSON / portal / Separate chain); it can't read a
  bundle that only exists inside a loop iteration (that value isn't defined outside the loop).
- Name mode (Index Bundle Array / Bundle Search) needs the items to have a "name" key - the node
  warns if they don't.

Community add-on, not made by the Serpens dev. Use at your own risk. Feedback welcome!
