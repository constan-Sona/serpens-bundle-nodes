import bpy
from ...base_node import SN_ScriptingBaseNode
from .._bundle_common import resolve_element_struct


class SN_BundleLoopNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_BundleLoopNode"
    bl_label = "Loop For Bundle (Execute)"
    bl_width_default = 200
    node_color = (0.431, 0.278, 0.341)  # #6E4757

    reverse: bpy.props.BoolProperty(
        name="Reverse",
        description="Reverse the order the loop runs through the items",
        default=False,
        update=SN_ScriptingBaseNode._evaluate,
    )

    def on_create(self, context):
        self.add_execute_input()
        self._add_input("SN_BundleArraySocket", "Bundle")
        self.add_execute_output("Repeat")
        self.add_execute_output("Continue")
        self._add_output("SN_BundleSocket", "Item")
        self.add_integer_output("Index")

    def struct_for_output(self, out):
        # the per-item bundle mirrors the element shape of the incoming array bundle
        if out.name == "Item":
            return resolve_element_struct(self.inputs.get("Bundle"))
        return None

    def evaluate(self, context):
        binp = self.inputs["Bundle"]
        if binp.is_linked:
            idx = f"sn_bidx_{self.static_uid}"
            item = f"sn_bitem_{self.static_uid}"
            self.outputs["Index"].python_value = idx
            self.outputs["Item"].python_value = item
            # the array bundle's value is the list itself
            seq = binp.python_value
            iterator = f"enumerate({seq})" if not self.reverse else f"enumerate(reversed(list({seq})))"
            self.code = f"""
                        for {idx}, {item} in {iterator}:
                            {self.indent(self.outputs['Repeat'].python_value, 7) if self.outputs['Repeat'].python_value.strip() else 'pass'}
                        {self.indent(self.outputs['Continue'].python_value, 6)}
                        """
        else:
            self.code = f'''print("No Bundle connected to {self.name}!")'''
            self.outputs["Index"].reset_value()
            self.outputs["Item"].reset_value()

    def draw_node(self, context, layout):
        layout.prop(self, "reverse")
        if self.inputs["Bundle"].is_linked and not resolve_element_struct(self.inputs.get("Bundle")):
            row = layout.row()
            row.alert = True
            row.label(text="Input is not an array bundle", icon="ERROR")
