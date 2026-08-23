# Deploying to Azure

You have an Azure subscription — here are three paths, cheapest first. All keep the same containers as local dev.

## 0. Cost guardrail (do this first)

Azure Portal → **Cost Management → Budgets** → create a budget (e.g. ₹2,000/month) with an alert at 50%/90%.
Estimated running cost for this stack: **₹1,500–2,500/month** (two Container Apps consume-only + Postgres Burstable B1s). Stop/deallocate when not demoing to pay near zero.

## Path A — Azure Container Apps from compose (simplest)

```bash
az login
az containerapp up \
  --name sentinelpay-api \
  --environment sentinelpay-env \
  --compose-file docker-compose.yml \
  --resource-group sentinelpay-rg \
  --location centralindia
```

This builds both images and wires them up. Then set secrets explicitly:

```bash
az containerapp secret set -g sentinelpay-rg --name sentinelpay-api \
  --secrets sentinel-key=<YOUR_KEY> azure-openai-key=<KEY>
az containerapp update -g sentinelpay-rg --name sentinelpay-api \
  --set-env-vars SENTINELPAY_API_KEY=sentinel-key \
                 AZURE_OPENAI_ENDPOINT=https://<res>.openai.azure.com/ \
                 AZURE_OPENAI_API_KEY=azure-openai-key
```

Train the model once inside the running container (or bake artifacts into the image):

```bash
az containerapp exec -g sentinelpay-rg --name sentinelpay-api \
  --command bash
python -m scripts.generate_data && python -m app.ml.train
```

## Path B — Azure Developer CLI (`azd`)

`infra/azure.yaml` defines both services for `azd up` (Container Apps host):

```bash
cd infra
azd init
azd env set SENTINELPAY_API_KEY change-me-demo-key
azd up          # provisions + deploys both containers
```

## Path C — reference architecture (production-shaped)

Provision with Bicep (`infra/main.bicep`, adjust before use):

| Resource | Purpose |
|---|---|
| Container Apps Environment | hosts API + dashboard |
| Container App: api | FastAPI engine, autoscale on HTTP |
| Container App: dashboard | Next.js console |
| PostgreSQL Flexible (B1s) | replaces SQLite via `DATABASE_URL` |
| Key Vault | `SENTINELPAY_API_KEY`, OpenAI keys, DB connection string |
| Application Insights | request tracing, decision latency dashboards |

Wire-up:

```bash
az keyvault secret set --vault-name <kv> --name sentinel-key --value <key>
# container app identity + access policy, then:
--set-env-vars SENTINELPAY_API_KEY=keyvault-ref...
```

## Azure OpenAI specifically

1. Create an **Azure OpenAI resource**, deploy `gpt-4o-mini` (Deployments → new deployment, name it e.g. `gpt-4o-mini`).
2. Set on the API container:

```
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key-from-keys-endpoint>
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
```

The LLM layer auto-detects Azure vs plain OpenAI vs none (template fallback).

## Notes

- The dashboard needs `NEXT_PUBLIC_API_URL` at **build time** (it bakes into client JS) — pass it as a Docker build arg pointing at your API's public URL.
- SSE streaming works on Container Apps; no extra config needed.
- Keep `SENTINELPAY_API_KEY` non-default in any public deployment.
