# API-only learning lab. Compose owns the database and network used below.
terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "4.6.0"
    }
  }
}

provider "docker" {
  host = "npipe:////./pipe/dockerDesktopLinuxEngine"
}

variable "database_url" {
  description = "Connection to the local Compose database; provide through TF_VAR_database_url."
  type        = string
  sensitive   = true
}

resource "docker_image" "api" {
  name = "data-platform-api:terraform-lab"

  build {
    context = abspath("${path.module}/../..")
  }

  # Reevaluate hashes during plan/apply; source edits are not deployed automatically.
  # Add new application files here when they become part of the image's inputs.
  triggers = {
    dockerfile     = filesha256("${path.module}/../../Dockerfile")
    requirements   = filesha256("${path.module}/../../requirements.txt")
    main           = filesha256("${path.module}/../../app/main.py")
    query_executor = filesha256("${path.module}/../../app/query_executor.py")
    messaging      = filesha256("${path.module}/../../app/messaging.py")
    worker         = filesha256("${path.module}/../../app/worker.py")
    init           = filesha256("${path.module}/../../app/__init__.py")
    dockerignore   = filesha256("${path.module}/../../.dockerignore")
  }
}

resource "docker_container" "api" {
  name  = "terraform-learning-api"
  image = docker_image.api.image_id

  env = [
    "DATABASE_URL=${var.database_url}"
  ]

  networks_advanced {
    name = "data-platform-engineering_default"
  }

  ports {
    internal = 8000
    external = 8089
    ip       = "127.0.0.1"
  }
}
