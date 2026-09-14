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

resource "docker_image" "api" {
  name = "data-platform-api:terraform-lab"

  build {
    context = abspath("${path.module}/../..")
  }

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
    "DATABASE_URL=postgresql://platform_user:platform_pass@db:5432/platform_db"
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
