# GitOps Starter Repository

This starter repo contains a minimal GitOps setup: Terraform scaffold, ArgoCD Application manifest, a Helm chart for an example service, a simple Flask example service, and a CI workflow to build/push the container image.

Structure:

- `infra/terraform/` — Terraform scaffold (provider + backend examples)
- `platform/argocd/` — ArgoCD `Application` manifest(s)
- `gitops/charts/example-service/` — Helm chart for the example service
- `services/example-service/` — Example Flask service and `Dockerfile`
- `.github/workflows/ci.yml` — CI to build and push image to GitHub Container Registry (GHCR)

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
