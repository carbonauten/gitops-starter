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

  # Example S3 remote state backend (uncomment and configure)
  # backend "s3" {
  #   bucket = "<your-terraform-state-bucket>"
  #   key    = "gitops-starter/terraform.tfstate"
  #   region = "eu-central-1"
  # }
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

// Azure VPN Gateway (for connectivity to Alibaba and On-Prem)
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

resource "azurerm_vpn_gateway" "azure_vpn" {
  name                = "gitops-starter-vpn-gateway"
  resource_group_name = azurerm_resource_group.azure_rg.name
  location            = azurerm_resource_group.azure_rg.location

  type = "Vpn"

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
  name              = "gitops-starter-vpc"
  cidr_block        = var.alibaba_vpc_cidr
  enable_ipv6       = false
  enable_ipv4       = true
  resource_group_id = null
}

resource "alicloud_vpn_gateway" "alibaba_vpn" {
  name                 = "gitops-starter-vpn-gateway"
  vpc_id               = alicloud_vpc.alibaba_vpc.id
  bandwidth            = 5
  enable_ssl           = true
  enable_ipsec         = true
  instance_charge_type = "PostPaid"

  depends_on = [alicloud_vpc.alibaba_vpc]
}

// Alibaba ECS Security Group
resource "alicloud_security_group" "alibaba_sg" {
  name        = "gitops-starter-sg"
  description = "Security group for Alibaba ECS"
  vpc_id      = alicloud_vpc.alibaba_vpc.id
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
  value = azurerm_vpn_gateway.azure_vpn.id
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
