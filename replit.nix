{pkgs}: {
  deps = [
    pkgs.gitleaks
    pkgs.trivy
    pkgs.redis
  ];
}
