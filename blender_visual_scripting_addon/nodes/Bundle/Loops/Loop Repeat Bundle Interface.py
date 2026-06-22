import bpy
from ...base_node import SN_ScriptingBaseNode
from .._bundle_common import resolve_element_struct


class SN_BundleRepeatInterfaceNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_BundleRepeatInterfaceNode"
    bl_label = "Loop Repeat Bundle (Interface)"
    bl_width_default = 200
    node_color = (0.2, 0.129, 0.157)  # #332128

    def on_create(self, context):
        self.add_interface_input()
        self._add_input("SN_BundleArraySocket", "Bundle")
        self.add_integer_input("Repetitions").default_value = 2
        self.add_interface_output("Repeat").passthrough_layout_type = True
        self.add_dynamic_interface_output().passthrough_layout_type = True
        self._add_output("SN_BundleSocket", "Item")
        self.add_integer_output("Step")

    def struct_for_output(self, out):
        if out.name == "Item":
            return resolve_element_struct(self.inputs.get("Bundle"))
        return None

    def evaluate(self, context):
        step = f"sn_bstep_{self.static_uid}"
        self.outputs["Step"].python_value = step
        binp = self.inputs["Bundle"]
        if binp.is_linked:
            seq = binp.python_value
            self.outputs["Item"].python_value = f"(({seq})[{step}] if {step} < len({seq}) else {{}})"
        else:
            self.outputs["Item"].reset_value()
        self.code = f"""
                    for {step} in range({self.inputs['Repetitions'].python_value}):
                        {self.indent(self.outputs['Repeat'].python_value, 6) if self.outputs['Repeat'].python_value.strip() else 'pass'}
                    {self.indent([out.python_value if out.name == 'Interface' else '' for out in self.outputs], 5)}
                    """
