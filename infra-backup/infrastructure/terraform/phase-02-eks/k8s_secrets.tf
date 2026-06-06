# Kubernetes Namespace
resource "kubernetes_namespace_v1" "uniops" {
  metadata {
    name = "uniops"
  }
}
