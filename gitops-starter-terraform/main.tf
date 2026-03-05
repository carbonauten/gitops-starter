// Terraform scaffold for multi-cloud infrastructure
// Supports: Azure (Europe), Alibaba Cloud (China), On-Premises via VPN

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.0"
    }
    alicloud = {
      source  = "aliyun/alicloud"
      version = ">= 1.200"
    }
  }
}

// Azure Provider (Europe)
provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
}

// Alibaba Cloud Provider (China)
provider "alicloud" {
  region     = var.alibaba_region
  access_key = var.alibaba_access_key_id
  secret_key = var.alibaba_access_key_secret
}

// ============= Azure Resources (Europe) =============

resource "azurerm_resource_group" "azure_rg" {
  name     = "gitops-starter-rg"
  location = var.azure_region
}

// Azure Virtual Network Gateway (for connectivity to Alibaba and On-Prem)
resource "azurerm_virtual_network" "azure_vnet" {
  name                = "gitops-starter-vnet"
  resource_group_name = azurerm_resource_group.azure_rg.name
  location            = azurerm_resource_group.azure_rg.location
  address_space       = [var.azure_vnet_cidr]
}

resource "azurerm_subnet" "azure_vpn_subnet" {
  name                 = "GatewaySubnet"
  resource_group_name  = azurerm_resource_group.azure_rg.name
  virtual_network_name = azurerm_virtual_network.azure_vnet.name
  address_prefixes     = ["10.0.253.0/24"]
}

resource "azurerm_public_ip" "azure_vpn_ip" {
  name                = "gitops-starter-vpn-ip"
  resource_group_name = azurerm_resource_group.azure_rg.name
  location            = azurerm_resource_group.azure_rg.location
  allocation_method   = "Static"
  sku                 = "Standard"
}

resource "azurerm_virtual_network_gateway" "azure_vpn" {
  name                = "gitops-starter-vpn-gateway"
  resource_group_name = azurerm_resource_group.azure_rg.name
  location            = azurerm_resource_group.azure_rg.location

  type          = "Vpn"
  vpn_type      = "RouteBased"
  active_active = false
  bgp_enabled   = false
  sku           = "VpnGw1"

  ip_configuration {
    name                          = "vnetGatewayConfig"
    public_ip_address_id          = azurerm_public_ip.azure_vpn_ip.id
    private_ip_address_allocation = "Dynamic"
    subnet_id                     = azurerm_subnet.azure_vpn_subnet.id
  }
}

// ============= Alibaba Cloud Resources (China) =============

// Alibaba Cloud VPC and VPN Gateway
resource "alicloud_vpc" "alibaba_vpc" {
  vpc_name          = "gitops-starter-vpc"
  cidr_block        = var.alibaba_vpc_cidr
  enable_ipv6       = false
  resource_group_id = null
}

resource "alicloud_vpn_gateway" "alibaba_vpn" {
  vpn_gateway_name = "gitops-starter-vpn-gateway"
  vpc_id           = alicloud_vpc.alibaba_vpc.id
  bandwidth        = 5
  enable_ssl       = true
  enable_ipsec     = true
  payment_type     = "PayAsYouGo"

  depends_on = [alicloud_vpc.alibaba_vpc]
}

// Alibaba ECS Security Group
resource "alicloud_security_group" "alibaba_sg" {
  security_group_name = "gitops-starter-sg"
  description         = "Security group for Alibaba ECS"
  vpc_id              = alicloud_vpc.alibaba_vpc.id
}

// ============= Data Lake (ADLS Gen2 + Alibaba OSS) =============

// Azure Data Lake Storage Gen2
resource "azurerm_storage_account" "datalake" {
  name                = "gitopsdatalake${var.environment}"
  resource_group_name = azurerm_resource_group.azure_rg.name
  location            = azurerm_resource_group.azure_rg.location

  account_tier             = "Standard"
  account_replication_type = "GRS"
  is_hns_enabled           = true

  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
  }
}

resource "azurerm_storage_data_lake_gen2_filesystem" "data" {
  name               = "data"
  storage_account_id = azurerm_storage_account.datalake.id
}

resource "azurerm_storage_data_lake_gen2_filesystem" "raw" {
  name               = "raw"
  storage_account_id = azurerm_storage_account.datalake.id
}

// Azure Blob Storage (standard blob account + containers)
resource "azurerm_storage_account" "blob" {
  name                     = var.azure_blob_storage_account_name
  resource_group_name      = azurerm_resource_group.azure_rg.name
  location                 = azurerm_resource_group.azure_rg.location
  account_tier             = "Standard"
  account_replication_type = "GRS"
  account_kind             = "StorageV2"

  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
  }

  blob_properties {
    versioning_enabled = true
  }
}

resource "azurerm_storage_container" "blob_data" {
  name                  = "data"
  storage_account_id    = azurerm_storage_account.blob.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "blob_uploads" {
  name                  = "uploads"
  storage_account_id    = azurerm_storage_account.blob.id
  container_access_type = "private"
}

// Alibaba Cloud Object Storage Service (OSS)
resource "alicloud_oss_bucket" "datalake" {
  bucket = "gitops-starter-datalake-${var.environment}"
  server_side_encryption_rule {
    sse_algorithm = "AES256"
  }

  versioning {
    status = "Enabled"
  }
}

resource "alicloud_oss_bucket_acl" "datalake" {
  bucket = alicloud_oss_bucket.datalake.id
  acl    = "private"
}

// ============= Kafka + MirrorMaker 2 (Bridge) =============

// Note: Kafka deployment can be on either cloud or on-prem.
// This is a placeholder for multi-region kafka cluster.
// In practice, deploy Kafka using Docker/Kubernetes or managed service.
output "kafka_config" {
  value = "Deploy Kafka cluster with MirrorMaker 2 for bi-directional replication between clouds"
}

// ============= Outputs =============

output "azure_vpn_gateway_id" {
  value = azurerm_virtual_network_gateway.azure_vpn.id
}

output "alibaba_vpn_gateway_id" {
  value = alicloud_vpn_gateway.alibaba_vpn.id
}

output "azure_vnet_id" {
  value = azurerm_virtual_network.azure_vnet.id
}

output "alibaba_vpc_id" {
  value = alicloud_vpc.alibaba_vpc.id
}

output "azure_datalake_storage_account_id" {
  value = azurerm_storage_account.datalake.id
}

output "azure_datalake_primary_endpoints" {
  value = {
    dfs  = azurerm_storage_account.datalake.primary_dfs_endpoint
    blob = azurerm_storage_account.datalake.primary_blob_endpoint
  }
}

output "azure_blob_storage_account_id" {
  value       = azurerm_storage_account.blob.id
  description = "Azure Blob Storage account resource ID"
}

output "azure_blob_primary_endpoint" {
  value       = azurerm_storage_account.blob.primary_blob_endpoint
  description = "Azure Blob Storage primary blob endpoint"
}

output "azure_blob_container_names" {
  value       = [azurerm_storage_container.blob_data.name, azurerm_storage_container.blob_uploads.name]
  description = "Names of the blob containers (data, uploads)"
}

output "alibaba_oss_bucket_name" {
  value = alicloud_oss_bucket.datalake.id
}

output "alibaba_oss_bucket_endpoints" {
  value = {
    internal = alicloud_oss_bucket.datalake.intranet_endpoint
    public   = alicloud_oss_bucket.datalake.extranet_endpoint
  }
}
