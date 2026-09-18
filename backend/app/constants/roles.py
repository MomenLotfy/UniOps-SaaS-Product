ROLES = {
    "super_admin":       "Super Administrator",
    "admin":             "Administrator",
    "security_engineer": "Security Engineer",
    "security_analyst":  "Security Analyst",
    "devops_engineer":   "DevOps Engineer",
    "compliance_manager":"Compliance Manager",
    "auditor":           "Auditor",
    "executive":         "Executive",
    "cost_analyst":      "Cost Analyst",
    "developer":         "Developer",
    "viewer":            "Viewer",
}

ROLE_HIERARCHY = [
    "super_admin", "admin",
    "security_engineer", "security_analyst",
    "devops_engineer", "compliance_manager",
    "auditor", "executive",
    "cost_analyst", "developer", "viewer",
]

SECURITY_ROLES = {
    "super_admin", "admin",
    "security_engineer", "security_analyst",
    "compliance_manager", "auditor",
}

WRITE_SECURITY_ROLES = {"super_admin", "admin", "security_engineer"}
COMPLIANCE_ROLES = {"super_admin", "admin", "security_engineer", "compliance_manager"}
AUDIT_READ_ROLES = {"super_admin", "admin", "security_engineer", "security_analyst", "compliance_manager", "auditor", "executive"}
EXECUTIVE_ROLES = {"super_admin", "admin", "executive"}


# ── Legacy role aliases (temporary migration/normalization layer) ────────────
# Older tenants have users/JWTs with pre-hardening role names.  These are
# accepted ONLY through normalize_role() — at JWT-parse time and at write
# time (invites, updates) so NEW rows/tokens are always canonical.
LEGACY_ROLE_ALIASES: dict[str, str] = {
    "devops":    "devops_engineer",
    "security":  "security_engineer",
    "finops":    "cost_analyst",
}

# The canonical product roles (subset used in product UI selectors)
CORE_ROLES = ("admin", "devops_engineer", "security_engineer", "cost_analyst", "viewer")


def normalize_role(role: str) -> str:
    """Map a (possibly legacy) role name to its canonical form."""
    return LEGACY_ROLE_ALIASES.get(role, role)


def normalize_roles(roles: list[str] | tuple[str, ...] | None) -> list[str]:
    """Normalize a role list to canonical names, dropping empties/dupes."""
    seen: list[str] = []
    for r in (roles or []):
        n = normalize_role(r)
        if n and n not in seen:
            seen.append(n)
    return seen


def is_valid_role(role: str) -> bool:
    return normalize_role(role) in ROLES
