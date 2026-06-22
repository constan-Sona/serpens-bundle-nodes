import bpy
from ...base_node import SN_ScriptingBaseNode
from .._bundle_common import resolve_element_struct


class SN_BundleUIListNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_BundleUIListNode"
    bl_label = "Bundle UI List"
    bl_width_default = 220
    node_color = (0.2, 0.129, 0.157)  # #332128 (interface family)

    def layout_type(self, _):
        return "layout"

    def on_create(self, context):
        self.add_interface_input()
        self._add_input("SN_BundleArraySocket", "Bundle")
        self.add_integer_input("Rows").default_value = 4
        self.add_dynamic_interface_output("Interface").passthrough_layout_type = True
        self._add_output("SN_BundleSocket", "Item")
        self.add_integer_output("Index")
        self.add_string_output("Name")

    def struct_for_output(self, out):
        # the active item mirrors the element shape of the incoming array bundle
        if out.name == "Item":
            return resolve_element_struct(self.inputs.get("Bundle"))
        return None

    @property
    def _uid(self):
        return self.static_uid

    def evaluate(self, context):
        binp = self.inputs["Bundle"]
        uid = self._uid
        ul = f"SNA_UL_sn_blist_{uid}"
        pg = f"SNA_PG_sn_blist_{uid}"
        coll = f"sn_blist_{uid}"
        idx = f"sn_blist_{uid}_index"
        seq = binp.python_value if binp.is_linked else "[]"

        self.code_imperative = f"""
            class {pg}(bpy.types.PropertyGroup):
                pass

            class {ul}(bpy.types.UIList):
                def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
                    layout.label(text=item.name)

            def sn_blist_names_{uid}(sn_data):
                sn_names = []
                try:
                    for sn_i, sn_x in enumerate(sn_data or []):
                        if isinstance(sn_x, dict) and "name" in sn_x:
                            sn_names.append(str(sn_x["name"]))
                        elif isinstance(sn_x, dict) and "key" in sn_x:
                            # key/value pairs (e.g. from Bundle To Array) -> show the key
                            sn_names.append(str(sn_x["key"]))
                        else:
                            sn_names.append(f"Item {{sn_i}}")
                except Exception:
                    pass
                return sn_names

            def sn_blist_sync_{uid}():
                try:
                    sn_wm = bpy.context.window_manager
                    sn_names = sn_blist_names_{uid}({seq})
                    sn_coll = sn_wm.{coll}
                    if [sn_c.name for sn_c in sn_coll] != sn_names:
                        sn_coll.clear()
                        for sn_n in sn_names:
                            sn_coll.add().name = sn_n
                except Exception as sn_e:
                    print("Bundle UI List sync error:", sn_e)
                return None

            def sn_blist_get_{uid}(sn_data, sn_i):
                try:
                    return sn_data[sn_i]
                except Exception:
                    return {{}}
            """
        self.code_register = f"""
            bpy.utils.register_class({pg})
            bpy.utils.register_class({ul})
            bpy.types.WindowManager.{coll} = bpy.props.CollectionProperty(type={pg})
            bpy.types.WindowManager.{idx} = bpy.props.IntProperty(name="Selected", default=0, min=0)
            """
        self.code_unregister = f"""
            try:
                del bpy.types.WindowManager.{coll}
                del bpy.types.WindowManager.{idx}
                bpy.utils.unregister_class({ul})
                bpy.utils.unregister_class({pg})
            except Exception:
                pass
            """

        if binp.is_linked:
            # draw can't write ID data, so the sync runs on a one-shot timer when needed
            self.code = f"""
                if [sn_c.name for sn_c in bpy.context.window_manager.{coll}] != sn_blist_names_{uid}({seq}):
                    if not bpy.app.timers.is_registered(sn_blist_sync_{uid}):
                        bpy.app.timers.register(sn_blist_sync_{uid}, first_interval=0.0)
                {self.active_layout}.template_list("{ul}", "", bpy.context.window_manager, "{coll}", bpy.context.window_manager, "{idx}", rows={self.inputs['Rows'].python_value})
                {self.indent([out.python_value if out.name == 'Interface' else '' for out in self.outputs], 4)}
                """
            self.outputs["Index"].python_value = f"bpy.context.window_manager.{idx}"
            self.outputs["Item"].python_value = f"sn_blist_get_{uid}(({seq}) or [], bpy.context.window_manager.{idx})"
            self.outputs["Name"].python_value = f"str(sn_blist_get_{uid}(sn_blist_names_{uid}(({seq}) or []), bpy.context.window_manager.{idx}) or '')"
        else:
            self.code = f"""
                {self.active_layout}.label(text='No Bundle connected!', icon='ERROR')
                {self.indent([out.python_value if out.name == 'Interface' else '' for out in self.outputs], 4)}
                """
            self.outputs["Index"].reset_value()
            self.outputs["Item"].reset_value()
            self.outputs["Name"].reset_value()

    def draw_node(self, context, layout):
        binp = self.inputs["Bundle"]
        if binp.is_linked and not resolve_element_struct(binp):
            row = layout.row()
            row.alert = True
            row.label(text="Input is not an array bundle", icon="ERROR")
