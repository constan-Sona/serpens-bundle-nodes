import bpy
from ...base_node import SN_ScriptingBaseNode


class SN_BundleLengthNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_BundleLengthNode"
    bl_label = "Bundle Length"
    node_color = (0.10, 0.18, 0.22)

    def on_create(self, context):
        self._add_input("SN_BundleSocket", "Bundle")
        self.add_integer_output("Length")

    def evaluate(self, context):
        # number of items in an array bundle (or keys in an object bundle); crash-safe
        self.outputs[0].python_value = f"len(({self.inputs[0].python_value}) or [])"
