import bpy
from ...base_node import SN_ScriptingBaseNode


class SN_BundleKeysNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_BundleKeysNode"
    bl_label = "Bundle Keys"
    node_color = (0.584, 0.294, 0.412)  # #954B69 (data, like Combine/Separate)

    def on_create(self, context):
        self._add_input("SN_BundleSocket", "Bundle")
        self.add_list_output("Keys")
        self.add_integer_output("Count")

    def evaluate(self, context):
        pv = self.inputs[0].python_value
        self.outputs["Keys"].python_value = f"list((({pv}) or {{}}).keys()) if isinstance({pv}, dict) else []"
        self.outputs["Count"].python_value = f"len(({pv}) or [])"
