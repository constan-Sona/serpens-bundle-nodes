import bpy
from ...base_node import SN_ScriptingBaseNode
from .._bundle_common import resolve_struct, resolve_element_struct


class SN_BundleToArrayNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_BundleToArrayNode"
    bl_label = "Bundle To Array"
    bl_width_default = 180
    node_color = (0.584, 0.294, 0.412)  # #954B69 (data, like Combine/Separate)

    def on_create(self, context):
        self._add_input("SN_BundleSocket", "Bundle")
        self._add_output("SN_BundleArraySocket", "Array")

    def element_struct_for_output(self, out):
        """Element shape of the produced array: {key, value} pairs for an object bundle,
        or the source element shape when an array is passed through."""
        if out.name != "Array":
            return None
        inp = self.inputs.get("Bundle")
        obj_struct = resolve_struct(inp)
        if obj_struct:
            return [("key", "SN_StringSocket", None, None, False),
                    ("value", "SN_DataSocket", None, None, False)]
        return resolve_element_struct(inp)  # array in -> passthrough

    def struct_for_output(self, out):
        return None  # the output is an array, not an object bundle

    def evaluate(self, context):
        binp = self.inputs["Bundle"]
        if binp.is_linked:
            pv = binp.python_value
            # object -> [{key, value}, ...]; array -> passthrough; anything else -> []
            self.outputs["Array"].python_value = (
                f'(lambda sn_d: [{{"key": sn_k, "value": sn_v}} for sn_k, sn_v in sn_d.items()] '
                f'if isinstance(sn_d, dict) else (sn_d or []))({pv})'
            )
        else:
            self.outputs["Array"].python_value = "[]"

    def draw_node(self, context, layout):
        inp = self.inputs.get("Bundle")
        if inp and inp.is_linked:
            if resolve_struct(inp):
                layout.label(text="Items: key + value", icon="INFO")
            elif resolve_element_struct(inp):
                layout.label(text="Already an array (passthrough)", icon="INFO")
