import bpy
from ...base_node import SN_ScriptingBaseNode


class SN_JsonWriteNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_JsonWriteNode"
    bl_label = "JSON Write"
    bl_width_default = 240
    node_color = (0.584, 0.443, 0.486)  # #95717C (JSON family)

    def on_create(self, context):
        self.add_execute_input()
        self._add_input("SN_BundleSocket", "Bundle")
        p = self._add_input("SN_StringSocket", "Path")
        try:
            p.subtype = "FILE_PATH"
        except Exception:
            pass
        self.add_execute_output()

    @property
    def _writer(self):
        return f"sn_json_write_{self.static_uid}"

    def evaluate(self, context):
        self.code_imperative = f"""
            def {self._writer}(path, data):
                try:
                    import os, json
                    sn_dir = os.path.dirname(path)
                    if sn_dir:
                        os.makedirs(sn_dir, exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                except Exception as sn_e:
                    print("JSON Write error:", sn_e)
            """
        self.code = f"""
                    {self._writer}({self.inputs['Path'].python_value}, {self.inputs['Bundle'].python_value})
                    {self.indent(self.outputs[0].python_value, 5)}
                    """

    def draw_node(self, context, layout):
        if not self.inputs["Bundle"].is_linked:
            layout.label(text="Connect a bundle to write", icon="INFO")
