import bpy
from ...base_node import SN_ScriptingBaseNode


class SN_DisplayBundleNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_DisplayBundleNode"
    bl_label = "Display Bundle"
    bl_width_default = 200
    node_color = (0.2, 0.129, 0.157)  # #332128 (interface family)

    max_depth: bpy.props.IntProperty(
        name="Depth",
        description="How deep nested objects/arrays are expanded (deeper levels are shown as text)",
        default=3, min=1, max=6,
        update=SN_ScriptingBaseNode._evaluate,
    )

    unwrap_pairs: bpy.props.BoolProperty(
        name="Unwrap Pairs",
        description="When the bundle is a {key, value} pair (e.g. a Bundle UI List item from "
                    "Bundle To Array), show only the value — the key is already visible in the list",
        default=True,
        update=SN_ScriptingBaseNode._evaluate,
    )

    def on_create(self, context):
        self.add_interface_input()
        self._add_input("SN_BundleSocket", "Bundle")
        self.add_dynamic_interface_output("Interface").passthrough_layout_type = True

    @property
    def _painter(self):
        return f"sn_draw_bundle_{self.static_uid}"

    def evaluate(self, context):
        binp = self.inputs["Bundle"]
        # runtime introspection: works for object bundles AND array bundles alike
        self.code_imperative = f"""
            def sn_unwrap_pair_{self.static_uid}(sn_data):
                # a top-level key/value pair shows only its value (the key is shown
                # by the UI List the item came from)
                if isinstance(sn_data, dict) and len(sn_data) == 2 and "key" in sn_data and "value" in sn_data:
                    return sn_data["value"]
                return sn_data

            def {self._painter}(sn_layout, sn_data, sn_depth):
                try:
                    if isinstance(sn_data, dict):
                        if not sn_data:
                            sn_layout.label(text="(empty)")
                        for sn_k, sn_v in sn_data.items():
                            if isinstance(sn_v, (dict, list)) and sn_depth > 1:
                                sn_box = sn_layout.box()
                                sn_box.label(text=str(sn_k), icon='PACKAGE' if isinstance(sn_v, dict) else 'MOD_ARRAY')
                                {self._painter}(sn_box, sn_v, sn_depth - 1)
                            else:
                                sn_layout.label(text=f"{{sn_k}}: {{sn_v}}")
                    elif isinstance(sn_data, list):
                        if not sn_data:
                            sn_layout.label(text="(empty list)")
                        for sn_i, sn_v in enumerate(sn_data):
                            if isinstance(sn_v, (dict, list)) and sn_depth > 1:
                                sn_box = sn_layout.box()
                                sn_box.label(text=f"[{{sn_i}}]", icon='PACKAGE' if isinstance(sn_v, dict) else 'MOD_ARRAY')
                                {self._painter}(sn_box, sn_v, sn_depth - 1)
                            else:
                                sn_layout.label(text=f"[{{sn_i}}] {{sn_v}}")
                    else:
                        sn_layout.label(text=str(sn_data))
                except Exception:
                    sn_layout.label(text="Display Bundle error", icon='ERROR')
            """
        if binp.is_linked:
            pv = binp.python_value
            if self.unwrap_pairs:
                pv = f"sn_unwrap_pair_{self.static_uid}({pv})"
            self.code = f"""
                {self._painter}({self.active_layout}, {pv}, {self.max_depth})
                {self.indent([out.python_value if out.name == 'Interface' else '' for out in self.outputs], 4)}
                """
        else:
            self.code = f"""
                {self.active_layout}.label(text='No Bundle connected!', icon='ERROR')
                {self.indent([out.python_value if out.name == 'Interface' else '' for out in self.outputs], 4)}
                """

    def draw_node(self, context, layout):
        layout.prop(self, "max_depth")
        layout.prop(self, "unwrap_pairs")
