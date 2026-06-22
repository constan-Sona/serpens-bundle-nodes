import bpy
from ...base_node import SN_ScriptingBaseNode
from .._bundle_common import resolve_element_struct


class SN_ArrayToBundleNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_ArrayToBundleNode"
    bl_label = "Array To Bundle"
    bl_width_default = 180
    node_color = (0.584, 0.294, 0.412)  # #954B69 (data, like Combine/Separate)

    def on_create(self, context):
        self._add_input("SN_BundleArraySocket", "Array")
        self._add_output("SN_BundleSocket", "Bundle")

    @property
    def _conv(self):
        return f"sn_arr2b_{self.static_uid}"

    def struct_for_output(self, out):
        # the object keys come from runtime VALUES (key/name fields), so the
        # structure can't be known at edit time -> read it with Get Key / Display
        return None

    def evaluate(self, context):
        # {key, value} pairs -> {key: value}  (inverse of Bundle To Array)
        # items with "name"  -> {name: item}
        # anything else      -> {"0": item, "1": item, ...}
        self.code_imperative = f"""
            def {self._conv}(sn_seq):
                sn_res = {{}}
                try:
                    for sn_i, sn_x in enumerate(sn_seq or []):
                        if isinstance(sn_x, dict) and "key" in sn_x and "value" in sn_x:
                            sn_res[str(sn_x["key"])] = sn_x["value"]
                        elif isinstance(sn_x, dict) and "name" in sn_x:
                            sn_res[str(sn_x["name"])] = sn_x
                        else:
                            sn_res[str(sn_i)] = sn_x
                except Exception:
                    pass
                return sn_res
            """
        binp = self.inputs["Array"]
        if binp.is_linked:
            self.outputs["Bundle"].python_value = f"{self._conv}({binp.python_value})"
        else:
            self.outputs["Bundle"].python_value = "{}"

    def draw_node(self, context, layout):
        binp = self.inputs["Array"]
        if binp.is_linked:
            st = resolve_element_struct(binp) or []
            names = [e[0] for e in st]
            if "key" in names and "value" in names:
                layout.label(text="{key, value} -> {key: value}", icon="INFO")
            elif "name" in names:
                layout.label(text="{name: item, ...}", icon="INFO")
            col = layout.column(align=True)
            col.scale_y = 0.8
            col.label(text="keys resolve at runtime:", icon="BLANK1")
            col.label(text="read with Get Key / Display", icon="BLANK1")