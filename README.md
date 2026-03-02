# GitOps Starter Repository

This starter repo contains a minimal GitOps setup: Terraform scaffold, ArgoCD Application manifest, a Helm chart for an example service, a simple Flask example service, and a CI workflow to build/push the container image.

Structure:

- `infra/terraform/` — Terraform scaffold (provider + backend examples)
- `platform/argocd/` — ArgoCD `Application` manifest(s)
- `gitops/charts/example-service/` — Helm chart for the example service
- `services/example-service/` — Example Flask service and `Dockerfile`
- `.github/workflows/ci.yml` — CI to build and push image to GitHub Container Registry (GHCR)

## Infrastructure Diagram

The high-level multi-cloud infrastructure for this starter looks like this:

```mermaid
flowchart TB
  subgraph cloud["☁️ Cloud Infrastructure"]
    subgraph azure["Azure (Europe)"]
      vpn_az["VPN Gateway"]
      k8s_az["AKS Kubernetes"]
    end

    subgraph alibaba["Alibaba Cloud (China)"]
      vpn_ali["VPN Gateway"]
      ecs_ali["Alibaba ECS"]
    end

    subgraph onprem["On-Premises Data Center"]
      vpn_onprem["VPN Gateway"]
      k8s_onprem["Kubernetes Cluster"]
      prom_onprem["Prometheus\n(Monitoring)"]
    end

    subgraph datalake["Data Lake"]
      adls["Azure Data Lake\nGen2 (ADLS)"]
      oss["Alibaba OSS\n(Object Storage)"]
    end

    kafka["Kafka + MirrorMaker 2\n(Message Broker)"]
    lb["Load Balancer\n(Traffic Router)"]
  end

  vpn_az --> kafka
  kafka --> vpn_ali
  vpn_az --> vpn_onprem
  vpn_ali --> vpn_onprem
  
  lb -->|routes| k8s_az
  lb -->|routes| ecs_ali
  lb -->|routes| k8s_onprem
  
  k8s_onprem --> prom_onprem
  
  k8s_az -->|reads/writes| adls
  ecs_ali -->|reads/writes| oss
  k8s_onprem -->|reads/writes| adls
  
  kafka -->|stream data| adls
  kafka -->|stream data| oss
    gha["GitHub Actions"]
    azp["Azure Pipelines"]
    terraform["Terraform (IaC)"]
  end

  gha -->|build & deploy| kafka
  azp -->|build & deploy| kafka
  terraform -->|provisions| cloud

  classDef cloudStyle fill:#e1f5ff,stroke:#01579b,stroke-width:2px;
  classDef onpremStyle fill:#fff3e0,stroke:#e65100,stroke-width:2px;
  class azure,alibaba cloudStyle;
  class onprem onpremStyle;
```

## Architecture Overview

For a more visual, component-level overview of the GitOps flow (developer → GitHub → CI → registry → Argo CD → Kubernetes → users), see:

![GitOps Starter architecture](docs/assets/gitops-starter-infrastructure.png)

Quick start (edit placeholders before use):

1. Customize `infra/terraform` provider and backend, then `terraform init`/`apply` (creates cloud infra as needed).
2. Push this repo to GitHub (e.g. `github.com/<org>/gitops-starter`).
3. Configure ArgoCD to track this repo and apply `platform/argocd/application.yaml`.
4. Configure CI secrets (GHCR or other registry) and run the workflow to build/push the image.

Notes:
- The Helm chart values use an `image.repository` placeholder — update to your registry (e.g. `ghcr.io/<org>/example-service`).
- The ArgoCD `Application` has `repoURL` placeholders; update to the actual repo URL.

If you want, I can:
- Create an AWS/Terraform example to provision EKS and RDS,
- Wire up a complete `ArgoCD` bootstrap, or
- Generate a PR in one of your repos with this starter.
