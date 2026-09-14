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

resource "docker_image" "web" {
  name = "nginx:alpine"
}

resource "docker_container" "web" {
  name  = "terraform-learning-web"
  image = docker_image.web.image_id

  ports {
    internal = 80
    external = 8089
    ip       = "127.0.0.1"
  }
}