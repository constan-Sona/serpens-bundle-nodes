import bpy
from ..base_node import SN_ScriptingBaseNode
from ...utils import get_python_name, unique_collection_name


# Node keys (tree, name) currently inside evaluate(); used to break cyclic
# re-evaluation (a feedback loop would otherwise grow the python_value forever
# and crash Blender). Module-level so it is cleared on reload, never persisted.
_EVALUATING = set()


class SN_CombineBundleNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_CombineBundleNode"
    bl_label = "Combine Bundle"
    bl_width_default = 200
    node_color = (0.584, 0.294, 0.412)  # #954B69

    # same as the base map plus the Bundle types, so a changeable input can become
    # a Bundle / Bundle Array (nested bundles inside a bundle)
    socket_names = {**SN_ScriptingBaseNode.socket_names,
                    "Bundle": "SN_BundleSocket",
                    "Bundle Array": "SN_BundleArraySocket"}

    def on_create(self, context):
        # the packed output
        self._add_output("SN_BundleSocket", "Bundle")
        # a single dynamic, renameable, type-changeable value input
        inp = self._add_input("SN_DataSocket", "Value", dynamic=True)
        inp.is_variable = True
        inp.changeable = True

    def value_inputs(self):
        """All real value sockets (everything except the trailing dynamic placeholder)."""
        return [inp for inp in self.inputs if not inp.dynamic]

    def _dup_names(self):
        """Names used by more than one value input (keys would collide in the dict)."""
        seen, dups = set(), set()
        for inp in self.value_inputs():
            if inp.name in seen:
                dups.add(inp.name)
            seen.add(inp.name)
        return dups

    def _deferred_dedupe_names(self):
        """Renames duplicated input names (socket names ARE the bundle/JSON keys, so
        duplicates would silently overwrite each other). Runs on a timer (topology-safe)."""
        self["_dedupe_pending"] = False
        try:
            seen = set()
            changed = False
            for inp in self.value_inputs():
                if inp.name in seen:
                    base = inp.name
                    i = 1
                    while f"{base}_{i:03d}" in seen:
                        i += 1
                    inp.set_name_silent(f"{base}_{i:03d}")
                    changed = True
                seen.add(inp.name)
            if changed:
                self.trigger_ref_update()
                self._evaluate(bpy.context)
        except Exception:
            pass
        return None  # one-shot

    def _unique_name(self, current_name):
        new_name = get_python_name(current_name, "Value", lower=False)
        return unique_collection_name(
            new_name, "Value", [inp.name for inp in self.inputs], "_", includes_name=True
        )

    def _deferred_fix_bundle_inputs(self):
        """Converts changeable value inputs to the Bundle type when a bundle is plugged
        in (the raw Bundle->Data link is invalid for Serpens, so on_link_insert never
        fires — we fix it from on_node_update instead), and mirrors the source shape
        (square = array bundle, diamond = object bundle)."""
        self["_fix_pending"] = False
        try:
            changed = False
            for i in range(len(self.inputs)):
                inp = self.inputs[i]
                if inp.dynamic or not inp.links:
                    continue
                fs = inp.links[0].from_socket
                if not fs or fs.bl_idname not in ("SN_BundleSocket", "SN_BundleArraySocket"):
                    continue
                if inp.bl_idname != fs.bl_idname and getattr(inp, "changeable", False):
                    self.convert_socket(inp, fs.bl_idname)
                    changed = True
            if changed:
                self.trigger_ref_update()
                self._evaluate(bpy.context)
        except Exception:
            pass
        return None  # one-shot

    def on_node_update(self):
        if not self.get("_fix_pending", False):
            self["_fix_pending"] = True
            bpy.app.timers.register(self._deferred_fix_bundle_inputs, first_interval=0.0)

    def on_dynamic_socket_add(self, socket):
        current_name = socket.name
        new_name = self._unique_name(current_name)
        if new_name != current_name:
            socket.set_name_silent(new_name)
        self.trigger_ref_update({"added": socket})
        self._evaluate(bpy.context)

    def on_dynamic_socket_remove(self, index, is_output):
        self.trigger_ref_update({"removed": index})
        self._evaluate(bpy.context)

    def on_socket_type_change(self, socket):
        self.trigger_ref_update({"changed": socket})
        self._evaluate(bpy.context)

    def on_socket_name_change(self, socket):
        # Prevent recursion (mirrors the pattern in Function Return)
        storage_key = f"_socket_updating_name_{id(socket)}"
        if self.get(storage_key, False):
            return
        name_storage_key = f"_socket_current_name_{id(socket)}"
        current_name = self.get(name_storage_key, socket.name)
        new_name = self._unique_name(current_name)
        if new_name != current_name:
            socket.set_name_silent(new_name)
        self.trigger_ref_update({"updated": socket, "new_name": new_name})
        self._evaluate(bpy.context)

    def evaluate(self, context):
        # Re-entrancy guard: if a feedback loop calls us while we're already
        # evaluating, bail out and keep the previous value so it can't grow forever.
        key = (self.node_tree.name, self.name)
        if key in _EVALUATING:
            return
        _EVALUATING.add(key)
        try:
            # Pack every named value into a python dict literal. The dict keys are the
            # socket names, which the Separate Bundle node mirrors exactly.
            pairs = []
            for inp in self.inputs:
                if inp.dynamic:
                    continue
                pairs.append(f'"{inp.name}": {inp.python_value}')
            self.outputs["Bundle"].python_value = "{" + ", ".join(pairs) + "}"

            # duplicated key names would overwrite each other in the dict -> fix them
            # on the next tick (renaming sockets inside evaluate is not safe)
            if self._dup_names() and not self.get("_dedupe_pending", False):
                self["_dedupe_pending"] = True
                bpy.app.timers.register(self._deferred_dedupe_names, first_interval=0.0)
        finally:
            _EVALUATING.discard(key)

    def draw_node(self, context, layout):
        if len(self.value_inputs()) == 0:
            layout.label(text="Add values with +", icon="INFO")
        dups = self._dup_names()
        if dups:
            row = layout.row()
            row.alert = True
            row.label(text=f"Duplicate key: {', '.join(sorted(dups))}", icon="ERROR")
