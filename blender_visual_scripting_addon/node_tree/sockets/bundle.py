import bpy
from .base_socket import ScriptingSocket


class SN_BundleSocket(bpy.types.NodeSocket, ScriptingSocket):

    bl_idname = "SN_BundleSocket"
    group = "DATA"
    bl_label = "Bundle"

    # A bundle is carried through the noodle as a python dict literal,
    # so its default value is an empty dict.
    default_python_value = "{}"
    default_prop_value = None

    # Diamond shape so it reads differently from regular value sockets.
    socket_shape = "DIAMOND"

    def get_python_repr(self):
        return "{}"

    def get_color(self, context, node):
        # pink (#FF5AAD), distinct from the interface/data socket colors
        return (1.0, 0.353, 0.678)

    def draw_socket(self, context, layout, node, text, minimal=False):
        layout.label(text=text)
