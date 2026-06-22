import bpy
from ..base_node import SN_ScriptingBaseNode


class SN_PrintBundleProperty(bpy.types.PropertyGroup):

    text: bpy.props.StringProperty()


class SN_OT_ClearBundlePrints(bpy.types.Operator):
    bl_idname = "sn.clear_bundle_prints"
    bl_label = "Clear Prints"
    bl_description = "Clear this print bundle node's messages"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    node_tree: bpy.props.StringProperty(options={"SKIP_SAVE", "HIDDEN"})
    node: bpy.props.StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        bpy.data.node_groups[self.node_tree].nodes[self.node].messages.clear()
        return {"FINISHED"}


class SN_PrintBundleNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_PrintBundleNode"
    bl_label = "Print Bundle"
    bl_width_default = 240
    node_color = "PROGRAM"

    messages: bpy.props.CollectionProperty(type=SN_PrintBundleProperty)

    print_on_node: bpy.props.BoolProperty(
        default=True,
        name="Print On Node",
        description="Show bundle contents on this node",
        update=SN_ScriptingBaseNode._evaluate,
    )

    def on_create(self, context):
        self.add_execute_input()
        self._add_input("SN_BundleSocket", "Bundle")
        self.add_execute_output()

    def evaluate(self, context):
        self.messages.clear()
        bundle_val = self.inputs[1].python_value
        self.code_imperative = f"""
        def sn_print_bundle(on_node, node, bundle):
            def _fmt(v, indent=0):
                pad = "  " * indent
                if isinstance(v, dict):
                    lines = []
                    for k, val in v.items():
                        child = _fmt(val, indent + 1)
                        if "\\n" in child:
                            lines.append(pad + str(k) + ":")
                            lines.append(child)
                        else:
                            lines.append(pad + str(k) + ": " + child)
                    return "\\n".join(lines) if lines else "(empty bundle)"
                if isinstance(v, (list, tuple)):
                    return "[" + str(len(v)) + " items]"
                return str(v)
            text = _fmt(bundle)
            print("Print Bundle [" + node.name + "]:")
            for line in text.splitlines():
                print("  " + line)
            if on_node:
                try:
                    node.messages.clear()
                    for line in text.splitlines():
                        msg = node.messages.add()
                        msg.text = line
                    for window in bpy.context.window_manager.windows:
                        for area in window.screen.areas:
                            area.tag_redraw()
                except Exception:
                    print("Can't show bundle on node when running in an interface flow!")
        """
        self.code = f"""
                    sn_print_bundle({self.print_on_node}, bpy.data.node_groups['{self.node_tree.name}'].nodes['{self.name}'], {bundle_val})
                    {self.indent(self.outputs[0].python_value, 5)}
                    """

    def draw_node(self, context, layout):
        layout.prop(self, "print_on_node", text="Print On Node")
        if self.print_on_node:
            if not self.messages:
                box = layout.box()
                box.label(text="Nothing printed!")
            else:
                row = layout.row()
                row.label(text="Bundle Contents:")
                op = row.operator("sn.clear_bundle_prints", text="", icon="TRASH", emboss=False)
                op.node_tree = self.node_tree.name
                op.node = self.name
                col = layout.column(align=True)
                col.scale_y = 0.9
                for msg in self.messages:
                    box = col.box()
                    box.label(text=msg.text)
