import bpy
from ...base_node import SN_ScriptingBaseNode
from .._bundle_common import resolve_element_struct


class SN_BundleFilterNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_BundleFilterNode"
    bl_label = "Filter Bundle Array"
    bl_width_default = 220
    node_color = (0.584, 0.294, 0.412)  # #954B69 (data, like Combine/Separate)

    def update_mode(self, context):
        # the compare Value input only matters in Equals mode
        self.inputs["Value"].set_hide(self.mode != "Equals")
        self._evaluate(context)

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Keep items where the key's value is truthy, or equals the given Value",
        items=[("Truthy", "Truthy", "Keep items where the key's value is true / non-empty", "CHECKMARK", 0),
               ("Equals", "Equals", "Keep items where the key's value equals the Value input", "EVENT_RETURN", 1)],
        default="Truthy",
        update=update_mode,
    )

    invert: bpy.props.BoolProperty(
        name="Invert",
        description="Keep the items that do NOT match",
        default=False,
        update=SN_ScriptingBaseNode._evaluate,
    )

    def on_create(self, context):
        self._add_input("SN_BundleArraySocket", "Bundle")
        self.add_string_input("Key")
        v = self.add_data_input("Value")
        v.changeable = True
        v.set_hide(True)  # hidden until Equals mode
        self._add_output("SN_BundleArraySocket", "Filtered")
        self.add_integer_output("Count")

    def element_struct_for_output(self, out):
        # the filtered array keeps the source element shape
        if out.name == "Filtered":
            return resolve_element_struct(self.inputs.get("Bundle"))
        return None

    @property
    def _filter(self):
        return f"sn_bfilter_{self.static_uid}"

    def evaluate(self, context):
        self.code_imperative = f"""
            def {self._filter}(sn_seq, sn_key, sn_mode, sn_val, sn_invert):
                sn_res = []
                try:
                    for sn_x in (sn_seq or []):
                        if not isinstance(sn_x, dict):
                            continue
                        if sn_mode == "Equals":
                            sn_keep = sn_x.get(sn_key) == sn_val
                        else:
                            sn_keep = bool(sn_x.get(sn_key))
                        if sn_keep != sn_invert:
                            sn_res.append(sn_x)
                except Exception:
                    pass
                return sn_res
            """
        binp = self.inputs["Bundle"]
        if binp.is_linked:
            val = self.inputs["Value"].python_value if self.mode == "Equals" else "None"
            call = (f"{self._filter}({binp.python_value}, {self.inputs['Key'].python_value}, "
                    f"'{self.mode}', {val}, {self.invert})")
            self.outputs["Filtered"].python_value = call
            self.outputs["Count"].python_value = f"len({call})"
        else:
            self.outputs["Filtered"].python_value = "[]"
            self.outputs["Count"].python_value = "0"

    def draw_node(self, context, layout):
        layout.prop(self, "mode", expand=True)
        layout.prop(self, "invert")
        binp = self.inputs["Bundle"]
        if binp.is_linked and not resolve_element_struct(binp):
            row = layout.row()
            row.alert = True
            row.label(text="Input is not an array bundle", icon="ERROR")
