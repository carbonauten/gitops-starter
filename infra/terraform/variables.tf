variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

// ===== Azure Variables =====
variable "azure_subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "azure_region" {
  description = "Azure region (Europe)"
  type        = string
  default     = "West Europe"
}

variable "azure_vnet_cidr" {
  description = "CIDR block for Azure VNet"
  type        = string
  default     = "10.0.0.0/16"
}

// ===== Alibaba Cloud Variables =====
variable "alibaba_region" {
  description = "Alibaba Cloud region (China)"
  type        = string
  default     = "cn-shanghai"
}

variable "alibaba_access_key_id" {
  description = "Alibaba Cloud Access Key ID"
  type        = string
  sensitive   = true
}

variable "alibaba_access_key_secret" {
  description = "Alibaba Cloud Access Key Secret"
  type        = string
  sensitive   = true
}

variable "alibaba_vpc_cidr" {
  description = "CIDR block for Alibaba VPC"
  type        = string
  default     = "172.16.0.0/16"
}

// ===== Kubernetes Variables (On-Premises) =====
variable "onprem_k8s_kubeconfig" {
  description = "Path to kubeconfig for on-premises Kubernetes cluster"
  type        = string
  default     = "~/.kube/config"
}

variable "cluster_name" {
  description = "Kubernetes cluster name"
  type        = string
  default     = "gitops-starter-cluster"
}

variable "cluster_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.27"
}

variable "node_instance_type" {
  description = "Compute instance type for worker nodes"
  type        = string
  default     = "t3.medium"
}

variable "node_desired_capacity" {
  type    = number
  default = 2
}

variable "node_min_capacity" {
  type    = number
  default = 1
}

variable "node_max_capacity" {
  type    = number
  default = 3
}

// ===== Data Lake Variables =====
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}
