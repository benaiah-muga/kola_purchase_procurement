# National ID Application — Usage Guide

This guide walks you through using and testing the **National ID Application**
module, end to end. The module lets members of the public submit an online
National ID application (with a photo and an LC reference letter) and lets
authorized officers process those applications through a two-stage approval
workflow, with full audit logging in the Odoo chatter and online status
tracking for applicants.

> **Prerequisite (one-time):** the server config was updated to bind the Odoo
> server to a single database. You must **restart the Odoo service once** for
> that change to take effect (see *Troubleshooting* at the bottom if routes
> ever return `404`).
>
> ```bash
> sudo systemctl restart odoo19
> ```

---

## 1. URLs at a glance

| What | URL | Who |
|------|-----|-----|
| Public application form | http://localhost:8069/id_application | Anyone (no login) |
| Applicant portal (track status) | http://localhost:8069/my/id_applications | Logged-in applicants |
| Backend (process applications) | http://localhost:8069/web → *National ID* menu | Officers / Managers |
| Odoo login | http://localhost:8069/web/login | All staff |

The server is running at **http://localhost:8069** (system service `odoo19`).

---

## 2. Set up access (do this first)

Before testing the workflow you need at least two staff users with the right
permissions, because the approval workflow is split into two roles:

1. Log into the backend as **administrator** (http://localhost:8069/web/login).
2. Go to **Settings → Users → Users** and create two users (or reuse existing
   ones):
   - An **Officer** — e.g. `id.officer@example.com`
   - A **Manager** — e.g. `id.manager@example.com`
3. Open each user and under **Other → Access Rights** (or the *National ID
   Applications* group section) set:
   - Officer user → **Officer** (under *National ID Applications*)
   - Manager user → **Manager** (under *National ID Applications*)

The two permission groups provided by the module are:

- **National ID Applications → Officer** — can see all applications, move an
  application from *Submitted* to *Under Review*, and reject an application.
- **National ID Applications → Manager** — inherits Officer rights, and can
  additionally move an application from *Under Review* to *Approved*.

Public/portal users (applicants) can only ever see their own applications.

---

## 3. Test the public application form

This simulates what a real applicant does.

1. Open http://localhost:8069/id_application in a browser (incognito/private
   window works great — no login needed).
2. Fill in the form. There are **8 fields**:
   - Full Name *(required)*
   - Date of Birth *(required)*
   - Gender *(required)*
   - Phone Number *(required)*
   - Email Address *(required)*
   - Physical Address *(required)*
   - **Applicant Photo** — passport-size image upload *(required)*
   - **LC Reference Letter** — scanned PDF/image of the LC recommendation
     letter *(required)*
3. Click **Submit Application**.
4. You'll see a confirmation page showing a unique **reference number** such as
   `NID/2026/0001`. Note this number — the applicant uses it to track their
   application.

That's it for the applicant side. The application now exists in the backend
with status **Submitted**.

---

## 4. Process applications in the backend (officers/managers)

1. Log into the backend as the **Officer** user (or admin).
2. Open the **National ID → Applications** menu.
3. You'll see the **list view** of all applications with their current status
   shown as a colour-coded badge:
   - Submitted (blue) · Under Review (yellow) · Approved (green) ·
     Rejected (red)
4. Click into an application to open the **form view**. You'll see:
   - The header **status bar** (Draft → Submitted → Under Review → Approved /
     Rejected).
   - All applicant details and the uploaded **photo** and **LC letter**
     (downloadable).
   - A **chatter** pane (right side / bottom) that logs every action.

### The two-stage approval workflow

The buttons in the header guide the workflow. They only appear when relevant,
and only for the right role:

| Current status | Button shown | Who can click | Next status |
|----------------|--------------|---------------|-------------|
| Submitted      | **Review**   | Officer / Manager | Under Review |
| Under Review   | **Approve**  | Manager only      | Approved |
| Submitted or Under Review | **Reject** | Officer / Manager | Rejected |

So a typical approval goes:

1. **Officer** opens the *Submitted* application, reviews the photo & LC letter,
   clicks **Review** → status becomes *Under Review*. (Stage 1 ✅)
2. **Manager** opens the *Under Review* application, clicks **Approve** →
   status becomes *Approved*. (Stage 2 ✅)

If something is wrong, either role can click **Reject** instead.

### Audit trail (chatter)

Every one of these actions is automatically recorded in the chatter with the
**acting user's name** and a timestamp, for example:

> **Moved to Review** by **ID Officer**.
> Application **NID/2026/0001** is now **Under Review**.

> **Application Approved** by **ID Manager**.
> Application **NID/2026/0001** is now **Approved**.

You can also post free-form internal notes or message followers from the
chatter (the *Log Note* / *Send message* composers).

---

## 5. Track an application from the portal (applicant view)

If the applicant submitted the form while logged in (as a portal/contact
user), they can track progress themselves:

1. The applicant logs in at http://localhost:8069/web/login.
2. They go to **My Account** (the portal), where a **National ID Applications**
   card shows the count of their applications.
3. Clicking it opens http://localhost:8069/my/id_applications — a list of their
   applications with reference number, date, and a status badge.
4. Clicking a reference opens a detail page showing the application info, the
   current status, and the communication history.

> **Note:** applications submitted from the **public** form (no login) are not
> linked to a portal user, so they only appear in the backend. To test portal
> tracking, submit the form while logged in as a portal/contact user, or assign
> a `Portal User` (partner) on the record in the backend.

---

## 6. Quick end-to-end test checklist

Run through this to confirm everything works:

- [ ] Restarted the service: `sudo systemctl restart odoo19`
- [ ] Created an Officer user and a Manager user with the right groups
- [ ] Opened http://localhost:8069/id_application and submitted an application
      (got a reference number)
- [ ] Logged into the backend → **National ID → Applications** — the new
      application appears with status *Submitted*
- [ ] As **Officer**: opened it, clicked **Review** → status *Under Review*,
      chatter shows the action + officer name
- [ ] As **Manager**: opened it, clicked **Approve** → status *Approved*,
      chatter shows the action + manager name
- [ ] (Optional) As Officer: rejected a second test application → status
      *Rejected*, chatter logged
- [ ] Logged in as the applicant → portal shows the application and its status

---

## 7. Troubleshooting

### The form / portal URL returns `404`
This happens when the server has more than one database and can't tell which
one to serve. The fix already applied to the config is:

```ini
# /home/benaiah/odoo19/config/odoo.conf
db_name = odoo
list_db = False
```

After setting this, **restart the service**:

```bash
sudo systemctl restart odoo19
```

If you intentionally run multiple databases, remove those two lines and instead
access the site via the database manager / specify the DB in the URL.

### The approval buttons don't appear
The buttons are gated by role and state:
- **Review** only shows when status = *Submitted*.
- **Approve** only shows when status = *Under Review* **and** you are in the
  **Manager** group.
- **Reject** only shows for *Submitted* / *Under Review* and requires the
  Officer group.

Check that your user has the right *National ID Applications* group under
**Settings → Users → [user] → Access Rights**.

### Nothing shows in the portal for an applicant
The applicant must be a logged-in portal/contact user, and the application's
**Portal User** field must point to that user's partner. Public (anonymous)
submissions aren't tied to any portal account.

### Need to reset the reference sequence
Reference numbers come from the sequence `national.id.application`
(prefix `NID/%(year)s/`, 4-digit padding). To reset/adjust it, go to
**Settings → Technical → Sequences** (enable Developer Mode) and edit the
*National ID Application Sequence*.

---

## 8. Module file map (for reference)

```
custom_addons/national_id_application/
├── __manifest__.py              # module declaration & dependencies
├── models/
│   └── id_application.py        # model, sequence, state machine, audit logging
├── controllers/
│   └── main.py                  # public form + submit route + portal routes
├── views/
│   ├── id_application_views.xml # backend list/form views + menu
│   ├── website_form_templates.xml  # public application form + thank-you page
│   └── portal_templates.xml     # applicant portal list/detail pages
├── security/
│   ├── security_groups.xml      # Officer/Manager groups + record rules
│   └── ir.model.access.csv      # per-group CRUD access rights
└── data/
    └── ir_sequence_data.xml     # NID/%(year)s/#### reference sequence
```
