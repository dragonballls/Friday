from core.registry import _register_functions_from_module


def test_generic_collection_annotations_map_to_json_schema(monkeypatch):
    def list_tool(items: list[str]):
        return items

    def dict_tool(options: dict[str, str]):
        return options

    class Module:
        __name__ = "test_registry_schema_module"

    list_tool.__module__ = Module.__name__
    dict_tool.__module__ = Module.__name__
    Module.list_tool = staticmethod(list_tool)
    Module.dict_tool = staticmethod(dict_tool)

    import core.registry as registry

    monkeypatch.setattr(registry, "_TOOL_MAP", {})
    monkeypatch.setattr(registry, "_TOOL_DEFINITIONS", [])

    _register_functions_from_module(Module)

    definitions = {d["function"]["name"]: d for d in registry.get_tool_definitions()}
    assert definitions["list_tool"]["function"]["parameters"]["properties"]["items"]["type"] == "array"
    assert definitions["dict_tool"]["function"]["parameters"]["properties"]["options"]["type"] == "object"
