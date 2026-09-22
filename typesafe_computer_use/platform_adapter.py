"""Platform adapter dispatching to Windows or macOS backend."""

from __future__ import annotations

import os
import sys
import types

from . import macos, windows

_original_macos_attrs = dict(macos.__dict__)


class _PlatformAdapterModule(types.ModuleType):
    def __getattribute__(self, name: str):
        if not name.startswith("_"):
            # Honor test monkeypatching on the macos module
            if name in macos.__dict__ and macos.__dict__[name] is not _original_macos_attrs.get(name):
                return macos.__dict__[name]
            # Honor explicit attributes on the adapter module itself
            if name in self.__dict__:
                return self.__dict__[name]
            
            if os.environ.get("ARGUS_TARGET") == "android":
                from . import android
                return getattr(android, name)
            
            if sys.platform == "win32":
                return getattr(windows, name)
            return getattr(macos, name)
        return super().__getattribute__(name)

    def __dir__(self):
        if os.environ.get("ARGUS_TARGET") == "android":
            from . import android
            return sorted(set(dir(windows) + dir(macos) + dir(android)))
        if sys.platform == "win32":
            return sorted(set(dir(windows) + dir(macos)))
        return dir(macos)


sys.modules[__name__].__class__ = _PlatformAdapterModule
