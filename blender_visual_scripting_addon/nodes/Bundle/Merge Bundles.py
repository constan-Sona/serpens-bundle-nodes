import bpy
from ..base_node import SN_ScriptingBaseNode
from ._bundle_common import resolve_struct, resolve_element_struct


# re-entrancy guard against feedback loops (same pattern as Combine/Separate)
_EVALUATING = set()


class SN_MergeBundlesNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_MergeBundlesNode"
    bl_label = "Merge Bundles"
    bl_width_default = 200
    node_color = (0.584, 0.294, 0.412)  # #954B69 (data, like Combine/Separate)

    def on_create(self, context):
        self._add_output("SN_BundleSocket", "Bundle")
        # dynamic object-bundle inputs; the LOWER input wins on key collisions
        self._add_input("SN_BundleSocket", "Bundle", dynamic=True)

    def value_inputs(self):
        return [inp for inp in self.inputs if not inp.dynamic]

    def struct_for_output(self, out):
        """Union of the input structs, later inputs override earlier keys."""
        merged = {}
        for inp in self.value_inputs():
            st = resolve_struct(inp)
            if st:
                for entry in st:
                    merged[entry[0]] = entry
        return list(merged.values()) if merged else None

    def evaluate(self, context):
        key = (self.node_tree.name, self.name)
        if key in _EVALUATING:
            return
        _EVALUATING.add(key)
        try:
            parts = [inp.python_value for inp in self.value_inputs() if inp.is_linked]
            if parts:
                args = ", ".join(parts)
                # dict-only merge: non-dict inputs are ignored, later wins
                self.outputs["Bundle"].python_value = (
                    "(lambda *sn_ds: {sn_k: sn_v for sn_d in sn_ds if isinstance(sn_d, dict) "
                    f"for sn_k, sn_v in sn_d.items()}})({args})"
                )
            else:
                self.outputs["Bundle"].python_value = "{}"
        finally:
            _EVALUATING.discard(key)

    def draw_node(self, context, layout):
        if len(self.value_inputs()) == 0:
            layout.label(text="Plug bundles with +", icon="INFO")
        else:
            layout.label(text="Lower input wins on collisions", icon="INFO")
        for inp in self.value_inputs():
            if inp.is_linked and resolve_element_struct(inp) and not resolve_struct(inp):
                row = layout.row()
                row.alert = True
                row.label(text="Array inputs are ignored", icon="ERROR")
                break
