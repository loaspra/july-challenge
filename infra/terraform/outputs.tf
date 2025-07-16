output "resource_group_name" {
  description = "Name of the Azure resource group"
  value       = azurerm_resource_group.rg.name
}

output "aks_cluster_name" {
  description = "AKS cluster name"
  value       = azurerm_kubernetes_cluster.aks.name
}

output "aks_kube_config" {
  description = "Raw kubeconfig for the AKS cluster"
  sensitive   = true
  value       = azurerm_kubernetes_cluster.aks.kube_config_raw
}

output "acr_login_server" {
  description = "ACR login server (host)"
  value       = azurerm_container_registry.acr.login_server
}
