import bpy
from ...base_node import SN_ScriptingBaseNode


class SN_BundleGetKeyNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_BundleGetKeyNode"
    bl_label = "Bundle Get Key"
    bl_width_default = 200
    node_color = (0.584, 0.294, 0.412)  # #954B69 (data, like Combine/Separate)

    def on_create(self, context):
        self._add_input("SN_BundleSocket", "Bundle")
        self.add_string_input("Key")
        self.add_data_output("Value")
        self.add_boolean_output("Exists")

    @property
    def _getter(self):
        return f"sn_bget_{self.static_uid}"

    def evaluate(self, context):
        # dotted-path getter (objects + list indices), crash-proof: (value, exists)
        self.code_imperative = f"""
            def {self._getter}(sn_data, sn_key):
                try:
                    sn_t = sn_data
                    sn_parts = [p for p in str(sn_key).split(".") if p != ""]
                    if not sn_parts:
                        return (None, False)
                    for sn_p in sn_parts:
                        if isinstance(sn_t, list):
                            sn_t = sn_t[int(sn_p)]
                        elif isinstance(sn_t, dict):
                            if sn_p not in sn_t:
                                return (None, False)
                            sn_t = sn_t[sn_p]
                        else:
                            return (None, False)
                    return (sn_t, True)
                except Exception:
                    return (None, False)
            """
        binp = self.inputs["Bundle"]
        if binp.is_linked:
            call = f"{self._getter}({binp.python_value}, {self.inputs['Key'].python_value})"
            self.outputs["Value"].python_value = f"{call}[0]"
            self.outputs["Exists"].python_value = f"{call}[1]"
        else:
            self.outputs["Value"].reset_value()
            self.outputs["Exists"].reset_value()

    def draw_node(self, context, layout):
        col = layout.column(align=True)
        col.scale_y = 0.8
        col.label(text="item / item.subitem / item.0.subitem", icon="INFO")
