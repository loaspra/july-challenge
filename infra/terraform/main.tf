############################################################
# Resource Group
############################################################
resource "azurerm_resource_group" "rg" {
  name     = "${var.project_name}-rg"
  location = var.location
}

############################################################
# Log Analytics (for AKS diagnostics)
############################################################
resource "azurerm_log_analytics_workspace" "log" {
  name                = "${var.project_name}-law"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

############################################################
# Azure Container Registry (optional but useful for images)
############################################################
resource "azurerm_container_registry" "acr" {
  name                     = replace("${var.project_name}acr", "-", "")
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  sku                      = "Basic"
  admin_enabled            = true
  georeplications          = []
}

############################################################
# AKS Cluster
############################################################
resource "azurerm_kubernetes_cluster" "aks" {
  name                = "${var.project_name}-aks"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  dns_prefix          = "${var.project_name}-dns"

  default_node_pool {
    name       = "default"
    node_count = var.node_count
    vm_size    = var.node_vm_size
  }

  identity {
    type = "SystemAssigned"
  }

  kubernetes_version = null # latest default

  lifecycle {
    ignore_changes = [kubernetes_version]
  }

  addon_profile {
    oms_agent {
      enabled                    = true
      log_analytics_workspace_id = azurerm_log_analytics_workspace.log.id
    }
  }

  # Attach ACR pull permissions
  role_based_access_control_enabled = true
}

############################################################
# Grant AKS cluster access to pull images from ACR
############################################################
resource "azurerm_role_assignment" "aks_acr_pull" {
  depends_on = [azurerm_kubernetes_cluster.aks]

  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.aks.identity[0].principal_id
}

############################################################
# Kubernetes provider (to interact with cluster after creation)
############################################################
provider "kubernetes" {
  host                   = azurerm_kubernetes_cluster.aks.kube_config[0].host
  client_certificate     = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].client_certificate)
  client_key             = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].client_key)
  cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].cluster_ca_certificate)
  token                  = azurerm_kubernetes_cluster.aks.kube_config[0].token
  load_config_file       = false
}

############################################################
# Helm provider to deploy charts later (e.g., ingress, prometheus)
############################################################
provider "helm" {
  kubernetes {
    host                   = azurerm_kubernetes_cluster.aks.kube_config[0].host
    client_certificate     = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].client_certificate)
    client_key             = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].client_key)
    cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].cluster_ca_certificate)
    token                  = azurerm_kubernetes_cluster.aks.kube_config[0].token
    load_config_file       = false
  }
}
