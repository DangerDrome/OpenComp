"""OpenComp Conform — EDL/AAF/XML ingest, media matching, .nk export."""

# Re-export submodules for convenient access
from . import ingest  # noqa: F401
from . import matcher  # noqa: F401
from . import handles  # noqa: F401
from . import structure  # noqa: F401
from . import nk_export  # noqa: F401

# vse_bridge and ui require bpy — imported on demand
