import bpy
from ...base_node import SN_ScriptingBaseNode
from .._bundle_common import resolve_element_struct


class SN_BundleRepeatExecuteNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_BundleRepeatExecuteNode"
    bl_label = "Loop Repeat Bundle (Execute)"
    bl_width_default = 200
    node_color = (0.431, 0.278, 0.341)  # #6E4757

    def on_create(self, context):
        self.add_execute_input()
        self._add_input("SN_BundleArraySocket", "Bundle")
        self.add_integer_input("Repetitions").default_value = 2
        self.add_execute_output("Repeat")
        self.add_execute_output("Continue")
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
            # the item at the current step, or an empty dict if the step is out of range
            self.outputs["Item"].python_value = f"(({seq})[{step}] if {step} < len({seq}) else {{}})"
        else:
            self.outputs["Item"].reset_value()
        self.code = f"""
                    for {step} in range({self.inputs['Repetitions'].python_value}):
                        {self.indent(self.outputs['Repeat'].python_value, 6) if self.outputs['Repeat'].python_value.strip() else 'pass'}
                    {self.indent(self.outputs['Continue'].python_value, 5)}
                    """
