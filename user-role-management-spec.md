# User Role Management — Feature Specification

## Overview

Enable taxi fleet owners to invite and manage team members with different access levels (roles), giving them granular control over who can view data, log entries, manage fleet resources, and access financial reports.

---

## 1. Problem Statement

Currently, the system supports only two roles: **owner** and **manager**. Owners need finer-grained control over team access:

- An **accountant** should see financial reports but not modify taxi/driver data
- A **dispatcher** should manage taxi assignments and driver schedules but not view sensitive financials
- A **viewer** (e.g. investor, auditor) should have read-only dashboard access
- A **data clerk** should only log income/breakdowns, not access any management features

---

## 2. Proposed Roles

| Role | View Dashboard | Log Income | Log Breakdowns | Log Fuel | Manage Taxis | Manage Drivers | View Reports | Manage Users |
|---|---|---|---|---|---|---|---|---|
| **owner** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **manager** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **dispatcher** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **accountant** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **viewer** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

> **Note:** Owner remains the single superuser with full access. Only owners can invite/manage users.

---

## 3. Data Model Changes

### 3.1 User Table — Role & Status Columns

Currently, `role` is a free-form `String(10)`. Change to a constrained enum, and add a `status` field for soft-delete:

```python
class UserRole(str, Enum):
    OWNER = "owner"
    MANAGER = "manager"
    DISPATCHER = "dispatcher"
    ACCOUNTANT = "accountant"
    VIEWER = "viewer"

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
```

**Migration required:**
- Add `status TEXT NOT NULL DEFAULT 'active'` column to `users` table
- Validate role against enum at application layer (SQLite doesn't enforce CHECK on ALTER TABLE)

### 3.2 Invite Token — Store Role

Add `role` column to `invite_tokens` table so the invited user receives the correct role on acceptance:

| Column | Type | Notes |
|---|---|---|
| role | TEXT | NOT NULL, default 'manager'. One of: manager, dispatcher, accountant, viewer |

---

## 4. API Changes

### 4.1 Invite Endpoint — Accept Role Parameter

**Current:** `POST /api/auth/invite`
```json
{ "name": "John", "phone": "+27..." }
```

**Updated:** `POST /api/auth/invite`
```json
{ "name": "John", "phone": "+27...", "role": "dispatcher" }
```

- Only `owner` can invite (existing `require_owner` dependency)
- `role` must be one of: manager, dispatcher, accountant, viewer (owner cannot invite another owner)
- Store `role` in `invite_tokens` table

### 4.2 Accept Invite — Auto-Assign Role from Token

**Current:** `POST /api/auth/accept-invite` always assigns `role="manager"`

**Updated:** Read `role` from the `InviteToken` record and assign that role to the new user

### 4.3 User Management Endpoints (New)

| Endpoint | Method | Role | Description |
|---|---|---|---|
| `/api/users` | GET | owner | List all users in the organisation (excluding self) |
| `/api/users/{user_id}` | GET | owner | Get user details |
| `/api/users/{user_id}` | PATCH | owner | Update user role or status |
| `/api/users/{user_id}` | DELETE | owner | Soft-delete (set status='inactive') |
| `/api/users/me` | GET | any | Get current user's profile |

### 4.4 User List Response Schema

```python
class UserResponse(BaseModel):
    id: str
    name: str
    phone: str
    role: str
    status: str  # 'active' or 'inactive'
    created_at: datetime

class UserUpdateRequest(BaseModel):
    role: str | None = None  # validated against UserRole enum
    status: str | None = None  # 'active' or 'inactive'
```

---

## 5. Permission Enforcement

### 5.1 Dependency Pattern

Replace `require_owner` with a more flexible dependency:

```python
def require_role(allowed_roles: list[str]):
    """Return a dependency that checks if the user has one of the allowed roles."""
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency

# Usage:
require_owner = require_role(["owner"])
require_manager_or_above = require_role(["owner", "manager"])
require_dispatcher_or_above = require_role(["owner", "manager", "dispatcher"])
```

### 5.2 Route Protection Summary

| Route | Current | Updated |
|---|---|---|
| `POST /api/taxis` | owner | owner, dispatcher |
| `PATCH /api/taxis/{id}` | owner | owner, dispatcher |
| `POST /api/drivers` | owner | owner, dispatcher |
| `PATCH /api/drivers/{id}` | owner | owner, dispatcher |
| `POST /api/income` | owner, manager | owner, manager, dispatcher |
| `POST /api/breakdowns` | owner, manager | owner, manager, dispatcher |
| `POST /api/fuel` | owner, manager | owner, manager, dispatcher |
| `GET /api/reports/*` | owner | owner, accountant |
| `GET/POST/PATCH/DELETE /api/users/*` | — | owner only |

---

## 6. UI Changes

### 6.1 Sidebar Navigation — Role-Based Sections

Update sidebar in `base.html` to show/hide links based on role:

```jinja2
{% if user.role in ["owner", "dispatcher"] %}
  <!-- Fleet Management: Taxis, Drivers -->
{% endif %}

{% if user.role in ["owner", "accountant"] %}
  <!-- Reports -->
{% endif %}

{% if user.role == "owner" %}
  <!-- User Management -->
{% endif %}
```

### 6.2 New Page: User Management (`/users`)

Accessible only to owners. Displays:
- Table of all users in the organisation (name, phone, role, status, joined date)
- "Invite User" button → opens modal with name, phone, role dropdown
- Inline role dropdown to change role (owner cannot change own role)
- Deactivate/Reactivate toggle (soft delete — sets status to 'inactive'/'active')
- Inactive users shown in grey, with "Reactivate" button

### 6.3 Invite Modal

```
┌─────────────────────────────────────────┐
│  Invite Team Member                     │
├─────────────────────────────────────────┤
│  Name:     [________________]           │
│  Phone:    [________________]           │
│  Role:     [Dispatcher        ▼]        │
│                                         │
│  [Cancel]              [Send Invite]    │
└─────────────────────────────────────────┘
```

Role dropdown options: Manager, Dispatcher, Accountant, Viewer

### 6.4 Updated Login/Signup Flows

No changes needed — login already returns role in JWT, and signup always creates owner.

---

## 7. Migration Plan

### Step 1: Add `role` column to `invite_tokens`

```sql
ALTER TABLE invite_tokens ADD COLUMN role TEXT NOT NULL DEFAULT 'manager';
```

### Step 2: Create Alembic migration

```bash
alembic revision --autogenerate -m "add role to invite_tokens and constrain user roles"
```

### Step 3: Update existing invite tokens (optional)

Existing tokens without a role will default to 'manager' — acceptable since they were created under the old behaviour.

---

## 8. Testing Requirements

### 8.1 Multi-Tenant Isolation

Ensure user management endpoints are properly scoped:
- Owner of org A cannot list/modify users of org B
- Test: `GET /api/users` with org A's JWT returns only org A's users

### 8.2 Role Enforcement

- Test: manager cannot access `GET /api/users`
- Test: dispatcher can create taxis/drivers but cannot access reports
- Test: accountant can access reports but cannot log income

### 8.3 Invite Flow

- Test: invite with role="dispatcher" creates user with dispatcher role
- Test: expired/used invite tokens are rejected

---

## 9. Implementation Order

1. **Schema changes** — UserRole enum, update InviteToken model
2. **Migration** — Alembic migration for invite_tokens.role column
3. **API updates** — Modify invite/accept-invite endpoints, add user management endpoints
4. **Dependency refactoring** — Create `require_role()` factory, update route dependencies
5. **UI** — User management page, invite modal, sidebar role-based visibility
6. **Tests** — Multi-tenant isolation, role enforcement, invite flow

---

## 10. Definition of Done

- [ ] UserRole and UserStatus enums defined and enforced at schema level
- [ ] users table has `status` column with default 'active'
- [ ] invite_tokens table has role column with default 'manager'
- [ ] Accept-invite assigns role from token, not hardcoded 'manager'
- [ ] User management CRUD endpoints (list, get, update role/status, soft-delete) — owner only
- [ ] Owner can change a user's role via PATCH endpoint
- [ ] Owner can soft-delete (deactivate) and reactivate users
- [ ] require_role() dependency replaces hardcoded role checks
- [ ] Sidebar shows/hides links based on user role (dispatcher sees fleet mgmt, accountant sees reports, viewer sees dashboard only)
- [ ] User management page at `/users` with invite modal and role/status editing
- [ ] All existing tests pass
- [ ] New tests for role-based access control
- [ ] Multi-tenant isolation verified for user management endpoints
