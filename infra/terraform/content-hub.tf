// Content Hub — Azure Container Apps scaffold (Sprint 1)
// Consumption plan: cost-effective hosting with scale-to-zero.

variable "content_hub_enabled" {
  description = "Provision Azure Container Apps resources for Content Hub"
  type        = bool
  default     = false
}

variable "content_hub_name" {
  description = "Base name for Content Hub resources"
  type        = string
  default     = "content-hub"
}

variable "content_hub_image" {
  description = "Container image for Content Hub (e.g. ghcr.io/org/content-hub:latest)"
  type        = string
  default     = "ghcr.io/carbonauten/content-hub:latest"
}

variable "content_hub_redirect_uri" {
  description = "Entra ID OAuth redirect URI for Content Hub"
  type        = string
  default     = "https://content-hub.example.com/api/auth/callback"
}

resource "azurerm_log_analytics_workspace" "content_hub" {
  count               = var.content_hub_enabled ? 1 : 0
  name                = "${var.content_hub_name}-logs"
  location            = azurerm_resource_group.azure_rg.location
  resource_group_name = azurerm_resource_group.azure_rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_container_app_environment" "content_hub" {
  count                       = var.content_hub_enabled ? 1 : 0
  name                        = "${var.content_hub_name}-env"
  location                    = azurerm_resource_group.azure_rg.location
  resource_group_name         = azurerm_resource_group.azure_rg.name
  log_analytics_workspace_id  = azurerm_log_analytics_workspace.content_hub[0].id
}

resource "azurerm_container_app" "content_hub" {
  count                        = var.content_hub_enabled ? 1 : 0
  name                         = var.content_hub_name
  container_app_environment_id = azurerm_container_app_environment.content_hub[0].id
  resource_group_name          = azurerm_resource_group.azure_rg.name
  revision_mode                = "Single"

  template {
    container {
      name   = "content-hub"
      image  = var.content_hub_image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "ENTRA_MOCK_AUTH"
        value = "false"
      }

      env {
        name  = "REDIRECT_URI"
        value = var.content_hub_redirect_uri
      }

      env {
        name        = "SESSION_SECRET"
        secret_name = "session-secret"
      }

      env {
        name        = "AZURE_TENANT_ID"
        secret_name = "azure-tenant-id"
      }

      env {
        name        = "AZURE_CLIENT_ID"
        secret_name = "azure-client-id"
      }

      env {
        name        = "AZURE_CLIENT_SECRET"
        secret_name = "azure-client-secret"
      }
    }

    min_replicas = 0
    max_replicas = 3
  }

  ingress {
    external_enabled = true
    target_port      = 8080
    transport        = "auto"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  secret {
    name  = "session-secret"
    value = "replace-me-in-key-vault-or-tfvars"
  }

  secret {
    name  = "azure-tenant-id"
    value = "replace-me"
  }

  secret {
    name  = "azure-client-id"
    value = "replace-me"
  }

  secret {
    name  = "azure-client-secret"
    value = "replace-me"
  }
}

output "content_hub_fqdn" {
  description = "Public FQDN for Content Hub (when enabled)"
  value       = var.content_hub_enabled ? azurerm_container_app.content_hub[0].ingress[0].fqdn : null
}
