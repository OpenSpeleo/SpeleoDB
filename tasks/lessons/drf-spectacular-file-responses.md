# DRF Spectacular File Responses

Every `GenericAPIView` exposed in the API schema needs a resolvable
`serializer_class`, even when the endpoint returns a file response instead of
serializer data.

For export/download endpoints:

- Set a concrete `serializer_class` for object lookup and schema introspection.
- Add `@extend_schema` on the file-returning method.
- Declare the real content type with `OpenApiTypes.BINARY`, for example
  `{(200, "application/gpx+xml"): OpenApiTypes.BINARY}`.
- Run `speleodb/users/tests/test_swagger.py::test_api_schema_no_warnings`
  before considering schema-facing API work done.
