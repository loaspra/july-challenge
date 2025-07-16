# Input variables for Azure deployment

variable "project_name" {
  type        = string
  description = "Name prefix for all created resources"
  default     = "globant-challenge"
}

variable "location" {
  type        = string
  description = "Azure region"
  default     = "eastus"
}

variable "container_image" {
  type        = string
  description = "Fully qualified image name (e.g. ghcr.io/user/repo:tag)"
}

variable "api_key" {
  type        = string
  description = "API key passed to the container as env var"
  default     = "local-dev-key"
}
