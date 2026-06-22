import bpy
from ...base_node import SN_ScriptingBaseNode
from .._bundle_common import resolve_element_struct


class SN_BundleForInterfaceNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_BundleForInterfaceNode"
    bl_label = "Loop For Bundle (Interface)"
    bl_width_default = 200
    node_color = (0.2, 0.129, 0.157)  # #332128

    reverse: bpy.props.BoolProperty(
        name="Reverse",
        description="Reverse the order the loop runs through the items",
        default=False,
        update=SN_ScriptingBaseNode._evaluate,
    )

    def on_create(self, context):
        self.add_interface_input()
        self._add_input("SN_BundleArraySocket", "Bundle")
        self.add_interface_output("Repeat").passthrough_layout_type = True
        self.add_dynamic_interface_output().passthrough_layout_type = True
        self._add_output("SN_BundleSocket", "Item")
        self.add_integer_output("Index")

    def struct_for_output(self, out):
        if out.name == "Item":
            return resolve_element_struct(self.inputs.get("Bundle"))
        return None

    def evaluate(self, context):
        binp = self.inputs["Bundle"]
        if binp.is_linked:
            idx = f"sn_bidx_{self.static_uid}"
            seq = binp.python_value
            self.outputs["Index"].python_value = idx
            self.outputs["Item"].python_value = f"({seq})[{idx}]"
            rng = f"range(len({seq}))" if not self.reverse else f"range(len({seq})-1,-1,-1)"
            self.code = f"""
                        for {idx} in {rng}:
                            {self.indent(self.outputs['Repeat'].python_value, 7) if self.outputs['Repeat'].python_value.strip() else 'pass'}
                        {self.indent([out.python_value if out.name == 'Interface' else '' for out in self.outputs], 6)}
                        """
        else:
            self.code = f"""
                        {self.active_layout}.label(text='No Bundle connected!', icon='ERROR')
                        {self.indent([out.python_value if out.name == 'Interface' else '' for out in self.outputs], 6)}
                        """
            self.outputs["Index"].reset_value()
            self.outputs["Item"].reset_value()

    def draw_node(self, context, layout):
        layout.prop(self, "reverse")
