# MISM Model Discovery Platform – Helm Chart

## Architecture Overview

The platform deploys five components plus a database migration Job:

| Component | Kind | Description |
|---|---|---|
| Discovery Gateway REST API | Deployment | FastAPI entry point — serves models, datasets, and full-text search |
| Search Service | Deployment | Downstream search microservice |
| Upload Service | Deployment | Handles dataset ingestion; delegates to Storage Interface |
| Storage Interface | Deployment | Adapter for iRODS or LakeFS backends |
| Metadata Store | StatefulSet | PostgreSQL — DAL read/write backend for the registry |
| Database Migration | Job (Helm hook) | Runs Alembic `upgrade head` on install/upgrade |

> ACL Server, OIDC (Keycloak), ACL DB, and Blob Storage (MinIO) are managed by
> separate charts and are **not** included here.

---

## Chart Structure

```
chart/
├── Chart.yaml
├── values.yaml
├── test-values.yaml                      # test overrides (feat branch, auth disabled)
└── templates/
    ├── _helpers.tpl                      # shared name/label helpers
    ├── configmap.yaml                    # shared environment config
    ├── secrets.yaml                      # dual-mode secret management (see below)
    ├── ingress.yaml                      # nginx Ingress for the gateway
    ├── services.yaml                     # ClusterIP Services (5 components)
    ├── networkpolicy.yaml                # per-receiver NetworkPolicies
    ├── hpa.yaml                          # HorizontalPodAutoscalers
    ├── job-migrate.yaml                  # Alembic migration Helm hook
    ├── NOTES.txt                         # post-install instructions
    ├── deployment-gateway.yaml
    ├── deployment-search-service.yaml
    ├── deployment-upload-service.yaml
    ├── deployment-storage-interface.yaml
    └── deployment-metadata-store.yaml    # StatefulSet (PostgreSQL)
```

---

## Key Design Decisions

### Database & Migrations

The Metadata Store is PostgreSQL 17. The gateway connects via `DATABASE_URL`,
which is assembled in the deployment template from the metadata-store values and
a secret password.

When `migration.enabled: true` (the default), a Helm hook Job runs Alembic
migrations (`post-install,post-upgrade`) using the same gateway image. An
init container waits for PostgreSQL readiness before migrating.

### Secret management (`templates/secrets.yaml`)

Two modes, toggled by `externalSecrets.enabled` in `values.yaml`:

| Mode | Renders | When to use |
|---|---|---|
| `false` (default) | Plain `Opaque Secret` from values | Local dev, CI |
| `true` | `ExternalSecret` CR (ESO v1beta1) | Production — pulls from Vault, AWS SM, GCP SM, Azure KV |

The generated Secret is always named `model-discovery-secrets` so all
deployment references stay the same regardless of mode.

### Network Policies (`templates/networkpolicy.yaml`)

A `default-deny-ingress` policy covers every pod in the namespace. Individual
allow policies then open only the required in-cluster communication paths:

```
Ingress controller  →  Gateway
Gateway             →  Search Service, Upload Service
Gateway             →  Metadata Store (PostgreSQL 5432)
Upload Service      →  Storage Interface
tusd                →  Gateway (/api/internal/tusd/hooks via ClusterIP)
```

Public ingress blocks `/api/internal` by default (`ingress.blockInternalApi: true`),
so tusd should call the gateway service directly inside the cluster, for example
`http://discovery-gateway:8000/api/internal/tusd/hooks`.

An optional `networkPolicy.restrictEgress: true` flag adds a matching egress
lockdown (DNS + intra-namespace + kube-apiserver only).

### HPA Autoscaling

Three HPAs for the stateless services (gateway, search, upload), each with
tuned CPU/memory thresholds and scale-up/down behaviors.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Kubernetes 1.25+ | NetworkPolicy and `autoscaling/v2` support |
| Helm 3.10+ | |
| metrics-server | Required for HPA CPU/memory metrics |
| nginx Ingress controller | Running in the `ingress-nginx` namespace (configurable) |
| External Secrets Operator | Only if `externalSecrets.enabled: true` |

---

## Installation

### Minimal (dev/local)

```bash
helm install mism ./chart -n <namespace> --create-namespace \
  --set secrets.databasePassword=<STRONG>
```

### With test values (feature branch)

```bash
helm install mism ./chart -n <namespace> --create-namespace \
  -f chart/test-values.yaml \
  --set secrets.databasePassword=<STRONG>
```

### Production with External Secrets Operator

```bash
helm install mism ./chart -n <namespace> --create-namespace \
  --set externalSecrets.enabled=true \
  --set externalSecrets.secretStoreName=vault-backend \
  --set externalSecrets.secretPath=prod/mism/discovery \
  --set ingress.host=model-discovery.your-domain.com \
  --set ingress.tls.enabled=true \
  --set networkPolicy.restrictEgress=true
```

### Useful commands after install

```bash
# Check pod status
kubectl -n <namespace> get pods

# Check migration Job
kubectl -n <namespace> get jobs -l app.kubernetes.io/component=migrate

# Watch HPA activity
kubectl -n <namespace> get hpa -w

# Tail gateway logs
kubectl -n <namespace> logs -l app.kubernetes.io/component=gateway -f

# Uninstall
helm uninstall mism -n <namespace>
```

---

## Storage

| Component | Default PVC size | Mount path |
|---|---|---|
| Metadata Store (PostgreSQL) | 20 Gi | `/var/lib/postgresql/data` |

Override via `metadataStore.persistence.size`. Set a custom `storageClass` per
component or globally via `global.storageClass`.
