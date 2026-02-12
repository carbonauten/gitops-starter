Azure DevOps integration

This folder contains guidance for using Azure Pipelines with this repo.

Quick setup

1. Create an Azure Container Registry (ACR) or other container registry.
2. In Azure DevOps, create a Service Connection of type "Docker Registry" or "Azure Resource Manager" and note the name (e.g. `ACRServiceConnection`).
3. Set a pipeline variable `ACR_LOGIN_SERVER` to your registry host (e.g. `myregistry.azurecr.io`).
4. Create a pipeline from `azure-pipelines.yml` in this repo.

Pipeline behavior

- The `Build` stage builds `services/example-service` and pushes `:latest` and `:$(Build.SourceVersion)` tags to the configured registry.
- The optional `Deploy` stage updates the Kubernetes deployment image using `kubectl` (requires cluster access via an Azure service connection).

Customize

- Change `imageName` and `containerRegistry` variables in `azure-pipelines.yml` to match your naming.
- Replace `ACRServiceConnection` and `AzureServiceConnection` with your service connection names.
