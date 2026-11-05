# gitops-starter-terraform

Standalone Terraform configuration extracted from the `gitops-starter` repository.

Contains multi-cloud infrastructure scaffolding for:

- Azure (`main.tf`): resource group, VNet, VPN gateway, Data Lake (ADLS Gen2), **Blob Storage** (standard account with containers `data` and `uploads`, versioning, private access)
- Azure (`content-hub.tf`, opt-in via `content_hub_enabled`): Container Apps hosting for the content-hub service, as an alternative to its usual Railway deployment
- Alibaba Cloud (`main.tf`): VPC, VPN gateway, security group, OSS-based data lake
- Hetzner Cloud (`mail_server.tf`): self-hosted Mailcow mail server VM for app.carbonauten.com's mailbox feature - see [infra/mailcow/README.md](../infra/mailcow/README.md) for the full setup (DNS records, Mailcow web setup, connecting it to the platform)
- Outputs that describe VPN gateways, VNet/VPC IDs, data lake endpoints, and the mail server's public IP.

To use:

```bash
cd gitops-starter-terraform
terraform init
terraform plan
terraform apply
```

Make sure to set/override the variables defined in `variables.tf` (e.g. subscription IDs, regions, CIDRs, and credentials) before applying.

CI on GitHub (see `.github/workflows/terraform-ci.yml`) automatically runs `terraform init -backend=false` and `terraform validate` on each push and pull request to `main`.

The **data pipeline consumer** (Kafka consumer) is deployed separately via [gitops-starter](https://github.com/carbonauten/gitops-starter) (Helm chart `gitops/charts/datapipeline-consumer` and Argo CD). This Terraform repo only provisions the underlying cloud and data lake resources.

