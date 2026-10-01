.PHONY: _custom-test-package-namespace
_custom-test-package-namespace:
	@"$(RUNTIME_VENV)/bin/python" -m pytest tests/unit/codegen/test_codegen_packaged_data_wheel_collision.py::TestsFlextInfraCodegenPackagedDataWheel::test_repository_namespace_keeps_its_import_path
