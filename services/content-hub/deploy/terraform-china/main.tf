terraform {
  required_version = ">= 1.5.0"

  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.220"
    }
  }
}

provider "alicloud" {
  region = var.region
}

variable "region" {
  description = "Alibaba Cloud region (e.g. cn-shanghai)"
  type        = string
  default     = "cn-shanghai"
}

variable "project_name" {
  description = "Resource name prefix"
  type        = string
  default     = "content-hub-cn"
}

variable "instance_type" {
  description = "ECS instance type"
  type        = string
  default     = "ecs.c6.large"
}

resource "alicloud_vpc" "main" {
  vpc_name   = "${var.project_name}-vpc"
  cidr_block = "10.20.0.0/16"
}

resource "alicloud_vswitch" "main" {
  vpc_id       = alicloud_vpc.main.id
  cidr_block   = "10.20.1.0/24"
  zone_id      = data.alicloud_zones.available.zones[0].id
  vswitch_name = "${var.project_name}-vswitch"
}

data "alicloud_zones" "available" {
  available_resource_creation = "VSwitch"
}

resource "alicloud_security_group" "app" {
  name   = "${var.project_name}-sg"
  vpc_id = alicloud_vpc.main.id

  ingress {
    ip_protocol = "tcp"
    port_range  = "80/80"
    cidr_ip     = "0.0.0.0/0"
  }

  ingress {
    ip_protocol = "tcp"
    port_range  = "443/443"
    cidr_ip     = "0.0.0.0/0"
  }

  ingress {
    ip_protocol = "tcp"
    port_range  = "22/22"
    cidr_ip     = "0.0.0.0/0"
  }

  egress {
    ip_protocol = "all"
    port_range  = "-1/-1"
    cidr_ip     = "0.0.0.0/0"
  }
}

resource "alicloud_oss_bucket" "uploads" {
  bucket = "${var.project_name}-uploads"
  acl    = "private"
}

resource "alicloud_instance" "app" {
  instance_name              = var.project_name
  security_groups            = [alicloud_security_group.app.id]
  instance_type              = var.instance_type
  system_disk_category       = "cloud_essd"
  image_id                   = data.alicloud_images.centos.images[0].id
  vswitch_id                 = alicloud_vswitch.main.id
  internet_max_bandwidth_out = 10

  user_data = <<-EOF
    #!/bin/bash
    yum install -y docker
    systemctl enable docker
    systemctl start docker
    mkdir -p /opt/content-hub
    echo "Deploy Content Hub container with DEPLOYMENT_REGION=cn and STORAGE_BACKEND=oss" > /opt/content-hub/README.txt
  EOF

  tags = {
    Name    = var.project_name
    Service = "content-hub"
    Region  = "cn"
  }
}

data "alicloud_images" "centos" {
  owners      = "system"
  name_regex  = "^centos_7"
  most_recent = true
}

output "ecs_public_ip" {
  value = alicloud_instance.app.public_ip
}

output "oss_bucket" {
  value = alicloud_oss_bucket.uploads.bucket
}

output "oss_endpoint_hint" {
  value = "oss-${var.region}.aliyuncs.com"
}
