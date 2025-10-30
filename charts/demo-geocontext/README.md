# Helm chart for demo-geocontext

* Create target namespace :

```bash
kubectl create namespace geocontext
```

* Prepare helm values as `my-values.yaml` :

```yaml
modelName: "anthropic:claude-3-7-sonnet-latest"

extraEnv:
  - name: HTTP_PROXY
    value: 'http://proxy:3128'
  - name: HTTPS_PROXY
    value: 'http://proxy:3128'
  - name: NO_PROXY
    value: 'localhost,127.0.0.1'

extraEnvFrom:
   - secretRef:
       name: apikeys
```

* Create a secret with the corresponding credentials :

```bash
kubectl -n geocontext create secret generic apikeys --from-literal=ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
```

* Deploy with helm 

```bash
# TODO : adapt after chart publishing
helm -n geocontext upgrade --install demo-geocontext . -f my-values.yaml
```

## Debug

```bash
# generate YAML
helm template demo-geocontext . > debug.yaml

# deploy
helm -n geocontext upgrade --install demo-geocontext . 
```
