// Self-hosted mail server (Mailcow) - dedicated VM so SMTP/IMAP traffic and
// mail storage are isolated from the other services in this repo. Reuses the
// Azure resource group/vnet already defined in main.tf.
//
// After `terraform apply` succeeds, there are still manual steps - see
// infra/mailcow/README.md: pointing DNS at the output IP, finishing the
// Mailcow web setup, and creating an API key to paste into the platform's
// Administration -> Mail server page.

variable "mail_server_fqdn" {
  description = "Public hostname for the mail server, e.g. mail.carbonauten.com. Must resolve to mail_server_public_ip's output once you add the DNS record."
  type        = string
}

variable "mail_server_allowed_ssh_cidr" {
  description = "CIDR allowed to SSH into the mail server (your office/VPN range - never leave this open to the internet). No default on purpose."
  type        = string
}

variable "mail_server_ssh_public_key" {
  description = "Public SSH key (contents of e.g. ~/.ssh/id_ed25519.pub) for the admin login."
  type        = string
}

variable "mail_server_admin_username" {
  description = "Linux admin username for SSH access."
  type        = string
  default     = "mailcowadmin"
}

variable "mail_server_vm_size" {
  description = "Azure VM size. B2s (2 vCPU/4GB) is enough for a handful of mailboxes; go larger for more volume/mailboxes."
  type        = string
  default     = "Standard_B2s"
}

variable "mail_server_disk_size_gb" {
  description = "OS + mail storage disk size in GB."
  type        = number
  default     = 64
}

resource "azurerm_subnet" "mail_server_subnet" {
  name                 = "mail-server-subnet"
  resource_group_name  = azurerm_resource_group.azure_rg.name
  virtual_network_name = azurerm_virtual_network.azure_vnet.name
  address_prefixes     = ["10.0.10.0/24"]
}

resource "azurerm_public_ip" "mail_server_ip" {
  name                = "mail-server-ip"
  resource_group_name = azurerm_resource_group.azure_rg.name
  location            = azurerm_resource_group.azure_rg.location
  allocation_method   = "Static"
  sku                 = "Standard"
  # Best-effort PTR record for mail reputation. Some providers only honor this
  # once the forward A record (mail_server_fqdn -> this IP) already resolves -
  # add the A record first, then re-apply if this doesn't take effect.
  reverse_fqdn = "${var.mail_server_fqdn}."
}

resource "azurerm_network_security_group" "mail_server_nsg" {
  name                = "mail-server-nsg"
  resource_group_name = azurerm_resource_group.azure_rg.name
  location            = azurerm_resource_group.azure_rg.location

  security_rule {
    name                       = "ssh-admin-only"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = var.mail_server_allowed_ssh_cidr
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "mail-and-web-public"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_ranges    = ["25", "80", "443", "465", "587", "993", "4190"]
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_interface" "mail_server_nic" {
  name                = "mail-server-nic"
  resource_group_name = azurerm_resource_group.azure_rg.name
  location            = azurerm_resource_group.azure_rg.location

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.mail_server_subnet.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.mail_server_ip.id
  }
}

resource "azurerm_network_interface_security_group_association" "mail_server_nic_nsg" {
  network_interface_id      = azurerm_network_interface.mail_server_nic.id
  network_security_group_id = azurerm_network_security_group.mail_server_nsg.id
}

resource "azurerm_linux_virtual_machine" "mail_server" {
  name                = "mail-server"
  resource_group_name = azurerm_resource_group.azure_rg.name
  location            = azurerm_resource_group.azure_rg.location
  size                = var.mail_server_vm_size
  admin_username      = var.mail_server_admin_username

  network_interface_ids = [azurerm_network_interface.mail_server_nic.id]

  admin_ssh_key {
    username   = var.mail_server_admin_username
    public_key = var.mail_server_ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    disk_size_gb         = var.mail_server_disk_size_gb
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  custom_data = base64encode(templatefile("${path.module}/templates/mailcow_cloud_init.yaml.tpl", {
    mail_server_fqdn = var.mail_server_fqdn
  }))
}

output "mail_server_public_ip" {
  description = "Point your DNS A record (mail_server_fqdn) at this IP, plus MX/SPF/DKIM/DMARC per infra/mailcow/README.md."
  value       = azurerm_public_ip.mail_server_ip.ip_address
}

output "mail_server_ssh_command" {
  value = "ssh ${var.mail_server_admin_username}@${azurerm_public_ip.mail_server_ip.ip_address}"
}
