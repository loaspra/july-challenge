variable "node_count" {
  type        = number
  description = "Number of nodes in the default AKS node pool"
  default     = 2
}

variable "node_vm_size" {
  type        = string
  description = "Azure VM size for AKS agent nodes"
  default     = "Standard_DS2_v2"
}
