import bpy
from ...base_node import SN_ScriptingBaseNode
from .._bundle_common import resolve_element_struct


class SN_BundleSearchNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_BundleSearchNode"
    bl_label = "Bundle Search"
    node_color = (0.2, 0.129, 0.157)  # #332128
    bl_width_default = 220

    def layout_type(self, _):
        return "layout"

    def on_create(self, context):
        self.add_interface_input()
        self._add_input("SN_BundleArraySocket", "Bundle")
        self.add_string_input("Label")
        self.add_dynamic_interface_output("Interface").passthrough_layout_type = True
        self._add_output("SN_BundleSocket", "Item")
        self.add_string_output("Name")

    def struct_for_output(self, out):
        # the picked item mirrors the element shape of the incoming array bundle
        if out.name == "Item":
            return resolve_element_struct(self.inputs.get("Bundle"))
        return None

    def _has_name_key(self):
        st = resolve_element_struct(self.inputs.get("Bundle")) or []
        return any(n == "name" for n, *_ in st)

    def evaluate(self, context):
        binp = self.inputs["Bundle"]
        prop = f"sn_search_{self.static_uid}"
        cb = f"sn_search_items_{self.static_uid}"
        if binp.is_linked:
            seq = binp.python_value
            label = self.inputs["Label"].python_value
            # runtime items callback: the item names from the bundle (kept in a global
            # to avoid Blender's enum-callback garbage-collection crash)
            self.code_imperative = f"""
                _{cb}_ref = [("", "<none>", "")]
                def {cb}(self, context):
                    global _{cb}_ref
                    sn_items = []
                    try:
                        for sn_x in ({seq}):
                            if isinstance(sn_x, dict) and "name" in sn_x:
                                sn_n = str(sn_x["name"])
                                sn_items.append((sn_n, sn_n, ""))
                    except Exception:
                        pass
                    _{cb}_ref = sn_items if sn_items else [("", "<none>", "")]
                    return _{cb}_ref
                """
            self.code_register = f"""
                bpy.types.WindowManager.{prop} = bpy.props.EnumProperty(name="Search", description="Pick an item by name", items={cb})
                """
            self.code_unregister = f"""
                try:
                    del bpy.types.WindowManager.{prop}
                except Exception:
                    pass
                """
            self.code = f"""
                {self.active_layout}.prop(bpy.context.window_manager, "{prop}", text={label})
                {self.indent([out.python_value if out.name == 'Interface' else '' for out in self.outputs], 4)}
                """
            sel = f"bpy.context.window_manager.{prop}"
            self.outputs["Name"].python_value = sel
            self.outputs["Item"].python_value = (
                f'next((sn_x for sn_x in ({seq}) if isinstance(sn_x, dict) '
                f'and str(sn_x.get("name")) == {sel}), {{}})'
            )
        else:
            self.code = f"{self.active_layout}.label(text='No Bundle connected!', icon='ERROR')"
            self.outputs["Item"].reset_value()
            self.outputs["Name"].reset_value()

    def draw_node(self, context, layout):
        if self.inputs["Bundle"].is_linked and not self._has_name_key():
            row = layout.row()
            row.alert = True
            row.label(text="Items have no 'name' key", icon="ERROR")
