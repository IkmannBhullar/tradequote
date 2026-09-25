"""Database access.

The only layer that queries the database. Multi-tenancy is enforced here:
every query on a tenant-owned table filters by organization_id.
"""
