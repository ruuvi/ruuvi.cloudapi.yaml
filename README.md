# ruuvi.cloudapi.yaml
Ruuvi Cloud API documentation in OpenAPI format

## Bundling API
```
npx -y @redocly/cli@latest bundle \
  userapi/openapi.yaml \
  -o userapi/bundle.yaml
```

## Getting Postman identifiers:
- Workspaces
```
curl -X GET "https://api.getpostman.com/workspaces" \
  -H "X-Api-Key: ${POSTMAN_TOKEN}" \
  -H "Accept: application/vnd.api.v10+json"  
```
- APIs
```
curl -X GET "https://api.getpostman.com/apis?workspaceId=${WORKSPACE_ID}" \
  -H "X-Api-Key: ${POSTMAN_TOKEN}" \
  -H "Accept: application/vnd.api.v10+json"  
```

- Versions:
```
curl -X GET "https://api.getpostman.com/apis/${API_ID}/versions" \
  -H "X-Api-Key: ${POSTMAN_TOKEN}" \
  -H "Accept: application/vnd.api.v10+json"  
```

- Schemas:
```
curl -X GET "https://api.getpostman.com/apis/${API_ID}/versions/${VERSION_ID}" \     
  -H "X-Api-Key: ${POSTMAN_TOKEN}" \
  -H "Accept: application/vnd.api.v10+json"  
```

- Collections
```
curl -X GET \
  "https://api.getpostman.com/collections" \
  -H "X-Api-Key: ${POSTMAN_TOKEN}" \
  -H "Accept: application/vnd.api.v10+json" \
  -H "Content-Type: application/json"
```

- Files
```
curl -X GET \                                                                     
  "https://api.getpostman.com/apis/${API_ID}/schemas/${SCHEMA_ID}/files" \
  -H "X-Api-Key: ${POSTMAN_TOKEN}" \
  -H "Accept: application/vnd.api.v10+json" \
  -H "Content-Type: application/json"
```

## Fuzzing API
uvx schemathesis run userapi/bundle.yaml \
  --url ${BASE_URL} \
  --header "Authorization: ${RUUVI_CLOUD_TOKEN}"