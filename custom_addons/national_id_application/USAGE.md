# National ID Application — Usage Guide

This guide walks you through using and testing the **National ID Application**
module, end to end. The module lets members of the public submit an online
National ID application (with a photo and an LC reference letter) and lets
authorized officers process those applications through a two-stage approval
workflow, with full audit logging in the Odoo chatter and online status
tracking for applicants.

---

## 0. One-time setup — RESTART the Odoo service (important)

Several errors you may have seen (`404` on the form, `KeyError: 'website'`,
login prompts on public pages, `ir.module.module` access errors) all stem from
**one root cause**: the server is running with an old config that doesn't know
which database to serve. This has been fixed in the config file, but the
running service must be **restarted** to pick it up.

Run this once:

```bash
sudo systemctl restart odoo19
```

Then verify the server is up and serving the site:

```bash
systemctl is-active odoo19        # should print: active
curl -I http://localhost:8069/    # should return 200/30x, NOT 404
```

If `/` returns `200`, the database-binding fix is live and everything below
will work. If you ever see `404` again, repeat the restart.

> **Why:** your server hosts several databases. Without a `db_name` directive,
> Odoo refuses to bind a request to any single DB, so every website/portal
> route (including `/id_application`) returns `404` and the `website` model
> can't be found. The config now has `db_name = odoo` + `list_db = False`.

---

## 1. URLs at a glance

| What | URL | Who |
|------|-----|-----|
| **Homepage** (portal landing) | http://localhost:8069/ | Anyone (no login) |
| Public application form | http://localhost:8069/id_application | Anyone (no login) |
| Applicant portal (track status) | http://localhost:8069/my/id_applications | Logged-in users |
| Backend (process applications) | http://localhost:8069/web → *National ID* menu | Officers / Managers / Admin |
| Odoo login | http://localhost:8069/web/login | All staff |

The server is running at **http://localhost:8069** (system service `odoo19`).

> **Demo-friendly access note:** the module is configured for easy testing.
> Any logged-in **internal user (including the admin)** can see and process
> **all** applications — you do **not** strictly need to set up Officer/Manager
> users to test. The Officer/Manager groups only gate which *approval buttons*
> appear (see §4). Anonymous visitors can submit the form without logging in.

---

## 2. Access model (kept deliberately light for demo use)

The permission model is intentionally simple:

- **Public / anonymous visitors** — can open the homepage and submit the
  application form. They cannot see any saved records.
- **Portal users** (applicants who logged in) — see only **their own**
  applications in `/my/id_applications`.
- **Internal users** (admin and any staff user) — see **all** applications in
  the backend. This is what you'll use for most testing.
- **National ID → Officer** group — can also click **Review** / **Reject**.
- **National ID → Manager** group — inherits Officer rights and can click
  **Approve** (the second approval stage).

Because internal users already see everything, **you can test the full flow
using just your admin account**. Skip to §3.

### (Optional) Create dedicated Officer/Manager users

Only needed if you want to demonstrate role separation:

1. Log into the backend as administrator.
2. **Settings → Users → Users** → *New*.
3. Create the user, then under **Access Rights** set the *National ID
   Applications* group to **Officer** or **Manager** as desired.

---

## 3. Test the public application form

This simulates what a real applicant does.

1. Open http://localhost:8069/ — you'll see the new **portal homepage** with a
   hero banner and a "How It Works" section.
2. Click **Start Application** (or go straight to
   http://localhost:8069/id_application). No login is required.
3. Fill in the form. There are **8 fields**:
   - Full Name *(required)*
   - Date of Birth *(required)*
   - Gender *(required)*
   - Phone Number *(required)*
   - Email Address *(required)*
   - Physical Address *(required)*
   - **Applicant Photo** — passport-size image upload *(required)*
   - **LC Reference Letter** — scanned PDF/image of the LC recommendation
     letter *(required)*
4. Click **Submit Application**.
5. You'll see a confirmation page showing a unique **reference number** such as
   `NID/2026/0001`. Note this number — the applicant uses it to track their
   application.

> If you leave a required field blank, the form now re-displays with a clear
> list of what to fix (instead of crashing). Your typed values are preserved.

That's it for the applicant side. The application now exists in the backend
with status **Submitted**.

---

## 4. Process applications in the backend (officers/managers)

1. Log into the backend (http://localhost:8069/web) as admin — or an
   Officer/Manager user.
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

1. **Officer** (or admin) opens the *Submitted* application, reviews the photo
   & LC letter, clicks **Review** → status becomes *Under Review*. (Stage 1 ✅)
2. **Manager** opens the *Under Review* application, clicks **Approve** →
   status becomes *Approved*. (Stage 2 ✅)

If something is wrong, either role can click **Reject** instead.

> **Admin tip:** because the admin is an internal user, they see all records.
> But the **Approve** button only shows for users in the *Manager* group. To
> test the full two-stage flow as admin, either give yourself the *Manager*
> group (Settings → Users → [you] → Access Rights → National ID Applications =
> Manager), or log in as a Manager user.

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

If the applicant submitted the form while **logged in** (as any user, including
the admin testing), the application is linked to their partner and they can
track progress:

1. Log in at http://localhost:8069/web/login.
2. Go to **My Account** (the portal) at http://localhost:8069/my — a
   **National ID Applications** card shows the count of their applications.
3. Clicking it opens http://localhost:8069/my/id_applications — a list of
   their applications with reference number, date, and a status badge.
4. Clicking a reference opens a detail page showing the application info, the
   current status, and the communication history.

> **Note:** applications submitted from the **public** form (no login) are not
> linked to any user, so they only appear in the backend. To test portal
> tracking, submit the form while logged in, or set the **Portal User** field
> on the record in the backend.

---

## 6. Quick end-to-end test checklist

Run through this to confirm everything works:

- [ ] Restarted the service: `sudo systemctl restart odoo19`
- [ ] http://localhost:8069/ shows the new homepage (not a 404)
- [ ] Opened http://localhost:8069/id_application and submitted an application
      (got a reference number)
- [ ] Logged into the backend → **National ID → Applications** — the new
      application appears with status *Submitted*
- [ ] Opened it, clicked **Review** → status *Under Review*, chatter shows the
      action + user name
- [ ] (As a Manager user) clicked **Approve** → status *Approved*, chatter
      shows the action + manager name
- [ ] (Optional) Submitted an incomplete form → got a friendly error list,
      not a crash
- [ ] Logged in as the applicant → portal shows the application and its status

---

## 7. Troubleshooting

### Any page returns `404` / `KeyError: 'website'` / login prompt on public pages
These are all the **same** problem: the server hasn't bound a database.
Restart the service:

```bash
sudo systemctl restart odoo19
```

The config (already set) is:

```ini
# /home/benaiah/odoo19/config/odoo.conf
db_name = odoo
list_db = False
```

If you intentionally run multiple databases, remove those two lines and select
the DB via the database manager instead.

### `403: Forbidden` when opening the portal as an admin/internal user
This was a missing access rule and has been fixed in v1.1: internal users now
see all applications. Run the module upgrade + restart to apply:

```bash
# from the odoo-19.0 directory
/home/benaiah/odoo19/venv/bin/python odoo-bin -c /home/benaiah/odoo19/config/odoo.conf \
    -d odoo -u national_id_application --stop-after-init
sudo systemctl restart odoo19
```

### The approval buttons don't appear
The buttons are gated by role and state:
- **Review** only shows when status = *Submitted*.
- **Approve** only shows when status = *Under Review* **and** you are in the
  **Manager** group (give yourself that group under Settings → Users → Access
  Rights → National ID Applications).
- **Reject** only shows for *Submitted* / *Under Review* and requires the
  Officer group (Manager inherits this).

### Nothing shows in the portal for an applicant
The application's **Portal User** field must point to that user's partner.
Public (anonymous) submissions aren't tied to any account. Submit while logged
in, or set the field in the backend.

### Need to reset the reference sequence
Reference numbers come from the sequence `national.id.application`
(prefix `NID/%(year)s/`, 4-digit padding). Go to **Settings → Technical →
Sequences** (enable Developer Mode) and edit the *National ID Application
Sequence*.

---

## 8. Module file map (for reference)

```
custom_addons/national_id_application/
├── __manifest__.py              # module declaration & dependencies
├── models/
│   └── id_application.py        # model, sequence, state machine, audit logging
├── controllers/
│   └── main.py                  # homepage + public form + submit + portal routes
├── views/
│   ├── id_application_views.xml    # backend list/form views + menu
│   ├── website_form_templates.xml  # homepage + public form + thank-you page
│   └── portal_templates.xml        # applicant portal list/detail pages
├── security/
│   ├── security_groups.xml      # Officer/Manager groups + record rules
│   └── ir.model.access.csv      # per-group CRUD access rights
└── data/
    └── ir_sequence_data.xml     # NID/%(year)s/#### reference sequence
```
