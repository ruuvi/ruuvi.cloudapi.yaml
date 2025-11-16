# ruuvi.cloudapi.yaml
Ruuvi Cloud API documentation in OpenAPI format

## Bundling API
```
npx -y @redocly/cli@latest bundle \
  userapi/openapi.yaml \
  -o userapi/bundle.yaml
```

## Publishing to GitBook
Run `Publish OpenAPI to GitBook` action manually in GitHub actions

## Publishing to Postman
Run `Publish API to Postman and run tests` action manually in GitHub actions

## Fuzzing API
### 1. Configure environments
Copy the template file and populate it with both your testing and production credentials:

```
cp .env.example .env
# edit .env
```

Each environment carries the `BASE_URL`, `USER_TOKEN`, and `SHAREE_ACCOUNT` variables that
Schemathesis will read when executed through the helper script.

### 2. Run Schemathesis for a specific environment
```
./scripts/run-schemathesis.sh test
# or
./scripts/run-schemathesis.sh production
```

The script loads the matching values from `.env` and executes:

```
uvx schemathesis run userapi/bundle.yaml \
  --url ${BASE_URL} \
  --header "Authorization: ${USER_TOKEN}" \
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