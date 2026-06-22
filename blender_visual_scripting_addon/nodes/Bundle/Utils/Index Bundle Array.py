import bpy
from ...base_node import SN_ScriptingBaseNode
from .._bundle_common import resolve_element_struct


class SN_IndexBundleArrayNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_IndexBundleArrayNode"
    bl_label = "Index Bundle Array"
    bl_width_default = 200
    node_color = (0.584, 0.294, 0.412)  # #954B69 (data, like Combine/Separate)

    def on_create(self, context):
        self._add_input("SN_BundleArraySocket", "Bundle")
        self.add_integer_input("Index")
        self._add_output("SN_BundleSocket", "Item")

    def update_mode(self, context):
        # swap the selector input between Integer (Index) and String (Name)
        sock = self.inputs[1]
        target = "SN_StringSocket" if self.mode == "Name" else "SN_IntegerSocket"
        if sock.bl_idname != target:
            new = self.convert_socket(sock, target)
            new.set_name_silent(self.mode)
        self._evaluate(context)

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="How to pick the item: by position (Index) or by its 'name' key (Name)",
        items=[("Index", "Index", "Pick by position", "DRIVER_TRANSFORM", 0),
               ("Name", "Name", "Pick by the item's 'name' key", "SYNTAX_OFF", 1)],
        default="Index",
        update=update_mode,
    )

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
        if binp.is_linked:
            seq = binp.python_value
            sel = self.inputs[1].python_value
            if self.mode == "Name":
                self.outputs["Item"].python_value = (
                    f'next((sn_x for sn_x in (({seq}) or []) if isinstance(sn_x, dict) '
                    f'and str(sn_x.get("name")) == str({sel})), {{}})'
                )
            else:
                # helper keeps any index (incl. negative / out of range) crash-proof
                self.code_imperative = f"""
                    def sn_bidx_get_{self.static_uid}(seq, idx):
                        try:
                            return seq[idx]
                        except Exception:
                            return {{}}
                    """
                self.outputs["Item"].python_value = f"sn_bidx_get_{self.static_uid}(({seq}) or [], {sel})"
        else:
            self.outputs["Item"].reset_value()

    def draw_node(self, context, layout):
        layout.prop(self, "mode", expand=True)
        if self.inputs["Bundle"].is_linked:
            if not resolve_element_struct(self.inputs.get("Bundle")):
                row = layout.row()
                row.alert = True
                row.label(text="Input is not an array bundle", icon="ERROR")
            elif self.mode == "Name" and not self._has_name_key():
                row = layout.row()
                row.alert = True
                row.label(text="Items have no 'name' key", icon="ERROR")
