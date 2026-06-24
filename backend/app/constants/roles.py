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
