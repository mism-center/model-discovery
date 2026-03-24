# MISM Discovery Platform – Helm Chart

## Session Summary

This session translated the MISM Discovery architecture diagram
(`mism_discovery_architecture.png`) into a production-ready Helm chart located
at `Architecture-V2/mism-gateway-api/`.

---

## Architecture Overview

![MISM Discovery Architecture](./mism_discovery_architecture.png)

The platform is composed of nine components derived from the architecture diagram:

| Component | Kind | Description |
|---|---|---|
| Discovery Gateway REST API | Deployment | Single entry point for all client traffic |
| Search Service | Deployment | Queries the Metadata Store; consumes Croissant Data Specs |
| Upload Service | Deployment | Handles dataset ingestion; delegates to Storage Interface and ACL Server |
| ACL Server (AUTHo) | Deployment | Authorization layer; backed by ACL DB |
| OIDC Service (AUTHe) | Deployment | Authentication provider (Keycloak) |
| Storage Interface | Deployment | Adapter for iRODS or LakeFS backends |
| Metadata Store | StatefulSet | MongoDB; stores Croissant Data Spec records |
| ACL DB | StatefulSet | PostgreSQL; stores access-control rules |
| Blob Storage | StatefulSet | MinIO (S3-compatible); stores raw dataset files |

---

## Chart Structure

```
mism-gateway-api/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── _helpers.tpl                      # shared name/label helpers
    ├── configmap.yaml                    # shared environment config
    ├── secrets.yaml                      # dual-mode secret management (see below)
    ├── ingress.yaml                      # nginx Ingress for gateway + OIDC + MinIO console
    ├── services.yaml                     # ClusterIP Services for all nine components
    ├── networkpolicy.yaml                # per-receiver NetworkPolicies (see below)
    ├── hpa.yaml                          # HorizontalPodAutoscalers (see below)
    ├── NOTES.txt                         # post-install instructions
    ├── deployment-gateway.yaml
    ├── deployment-search-service.yaml
    ├── deployment-upload-service.yaml
    ├── deployment-acl-server.yaml
    ├── deployment-oidc.yaml
    ├── deployment-storage-interface.yaml
    ├── deployment-metadata-store.yaml    # StatefulSet
    ├── deployment-acl-db.yaml            # StatefulSet
    └── deployment-blob-storage.yaml      # StatefulSet
```

---

## Key Design Decisions

### Stateful vs Stateless workloads

MongoDB, PostgreSQL, and MinIO use `StatefulSet` with `volumeClaimTemplates`
so each pod gets a stable, persistent volume. All application services use
`Deployment` with configurable replica counts.

### Secret management (`templates/secrets.yaml`)

Two modes, toggled by `externalSecrets.enabled` in `values.yaml`:

| Mode | Renders | When to use |
|---|---|---|
| `false` (default) | Plain `Opaque Secret` from values | Local dev, CI |
| `true` | `ExternalSecret` CR (ESO v1beta1) | Production — pulls from Vault, AWS SM, GCP SM, Azure KV |

The generated Secret is always named `mism-gateway-api-secrets` so all Deployment
references stay the same regardless of mode. The plain Secret carries
`helm.sh/resource-policy: keep` to prevent accidental deletion on upgrade.

### Network Policies (`templates/networkpolicy.yaml`)

A `default-deny-ingress` policy covers every pod in the namespace. Individual
allow policies then open only the exact paths shown in the architecture diagram:

```
Ingress controller  →  Gateway
Gateway             →  Search Service, Upload Service, OIDC
Upload Service      →  Storage Interface, ACL Server
ACL Server          →  ACL DB (PostgreSQL 5432)
Search Service      →  Metadata Store (MongoDB 27017)
Storage Interface   →  Blob Storage (MinIO API 9000)
Ingress controller  →  OIDC (/auth), MinIO console (9001)
```

An optional `networkPolicy.restrictEgress: true` flag adds a matching egress
lockdown (DNS + intra-namespace + kube-apiserver only). It is off by default to
allow services to reach external iRODS or LakeFS endpoints.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Kubernetes 1.25+ | NetworkPolicy and `autoscaling/v2` support |
| Helm 3.10+ | |
| metrics-server | Required for HPA CPU/memory metrics |
| nginx Ingress controller | Running in the `ingress-nginx` namespace (configurable) |
| External Secrets Operator | Only if `externalSecrets.enabled: true` |
| Prometheus adapter or KEDA | Only if using `additionalMetrics` in HPA |

---

## Installation

All chart resources are created in the **Helm release namespace** (the `-n` /
`--namespace` you pass to `helm install` / `helm upgrade`). The chart does not
render a `Namespace` object, so whoever runs Helm must be able to deploy into
an existing namespace, or use `--create-namespace` when their RBAC allows
creating namespaces.

### Minimal (dev/local)

```bash
helm install mism . -n <namespace> --create-namespace \
  --set secrets.mongoRootPassword=<STRONG> \
  --set secrets.aclDbPassword=<STRONG> \
  --set secrets.minioRootPassword=<STRONG> \
  --set secrets.keycloakAdminPassword=<STRONG>
```

### Production with External Secrets Operator

```bash
helm install mism . -n <namespace> --create-namespace \
  --set externalSecrets.enabled=true \
  --set externalSecrets.secretStoreName=vault-backend \
  --set externalSecrets.secretPath=prod/mism/discovery \
  --set ingress.host=mism-gateway-api.your-domain.com \
  --set ingress.tls.enabled=true \
  --set networkPolicy.restrictEgress=true
```

### Useful commands after install

```bash
# Check pod status
kubectl -n <namespace> get pods

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
| Metadata Store (MongoDB) | 20 Gi | `/data/db` |
| ACL DB (PostgreSQL) | 10 Gi | `/var/lib/postgresql/data` |
| Blob Storage (MinIO) | 50 Gi | `/data` |

Override sizes via `metadataStore.persistence.size`, `aclDb.persistence.size`,
and `blobStorage.persistence.size`. Set a custom `storageClass` per component
or globally via `global.storageClass`.
