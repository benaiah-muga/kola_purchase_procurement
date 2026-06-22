import base64
import logging
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

_logger = logging.getLogger(__name__)


class NationalIdApplicationController(http.Controller):
    @http.route('/', type='http', auth='public', website=True)
    def national_id_homepage(self, **kwargs):
        """Public landing page for the National ID application portal."""
        return request.render('national_id_application.homepage_template', {})

    @http.route('/id_application', type='http', auth='public', website=True)
    def id_application_form(self, **kwargs):
        return request.render('national_id_application.application_form_template', {})

    @http.route('/id_application/submit', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def id_application_submit(self, **post):
        photo_file = request.httprequest.files.get('photo')
        lc_letter_file = request.httprequest.files.get('lc_letter')

        # Robust error handling: collect errors and re-show the form with the
        # values the applicant already typed in, so they are never left staring
        # at a raw traceback.
        errors = []

        required_fields = {
            'applicant_name': (post.get('applicant_name') or '').strip(),
            'date_of_birth': (post.get('date_of_birth') or '').strip(),
            'gender': (post.get('gender') or '').strip(),
            'phone': (post.get('phone') or '').strip(),
            'email': (post.get('email') or '').strip(),
            'address': (post.get('address') or '').strip(),
        }
        for label, value in required_fields.items():
            if not value:
                errors.append(_("The field '%s' is required.") % label)

        if not photo_file or not getattr(photo_file, 'filename', ''):
            errors.append(_("An applicant photo is required."))
        if not lc_letter_file or not getattr(lc_letter_file, 'filename', ''):
            errors.append(_("An LC reference letter is required."))

        if errors:
            return request.render('national_id_application.application_form_template', {
                'errors': errors,
                'form': post,
            })

        try:
            photo_data = base64.b64encode(photo_file.read()) if photo_file else False
            photo_filename = photo_file.filename if photo_file else False

            lc_letter_data = base64.b64encode(lc_letter_file.read()) if lc_letter_file else False
            lc_letter_filename = lc_letter_file.filename if lc_letter_file else False

            vals = {
                'applicant_name': post.get('applicant_name'),
                'date_of_birth': post.get('date_of_birth'),
                'gender': post.get('gender'),
                'phone': post.get('phone'),
                'email': post.get('email'),
                'address': post.get('address'),
                'photo': photo_data,
                'photo_filename': photo_filename,
                'lc_letter': lc_letter_data,
                'lc_letter_filename': lc_letter_filename,
                'state': 'submitted',
            }

            # Link to the logged-in user's partner (works for portal AND
            # internal users); anonymous public submissions stay unlinked.
            public_user = request.env.ref('base.public_user', raise_if_not_found=False)
            current_user = request.env.user
            if not public_user or current_user.id != public_user.id:
                vals['partner_id'] = current_user.partner_id.id

            application = request.env['national.id.application'].sudo().create(vals)
        except Exception as exc:  # noqa: BLE001 - friendly page, never a crash
            _logger.exception("Failed to submit National ID application")
            return request.render('national_id_application.application_form_template', {
                'errors': [_("Sorry, we could not submit your application. "
                             "Please try again or contact support if the problem persists.")],
                'form': post,
            })

        return request.render('national_id_application.application_thank_you', {
            'application_ref': application.name
        })


class CustomerPortalIDApp(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'id_application_count' in counters:
            domain = [('partner_id', '=', request.env.user.partner_id.id)]
            values['id_application_count'] = request.env['national.id.application'].sudo().search_count(domain)
        return values

    @http.route(['/my/id_applications', '/my/id_applications/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_id_applications(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        IdApplication = request.env['national.id.application'].sudo()

        # Scope by partner so the "My Applications" page is meaningful for a
        # real applicant. Internal users (admins/officers) can still access any
        # record via the backend; here they see their own linked submissions.
        domain = [('partner_id', '=', partner.id)]
        application_count = IdApplication.search_count(domain)

        pager = portal_pager(
            url="/my/id_applications",
            total=application_count,
            page=page,
            step=self._items_per_page
        )

        applications = IdApplication.search(domain, limit=self._items_per_page, offset=pager['offset'])

        values.update({
            'applications': applications,
            'page_name': 'id_application',
            'pager': pager,
            'default_url': '/my/id_applications',
        })
        return request.render("national_id_application.portal_my_id_applications", values)

    @http.route(['/my/id_application/<int:application_id>'], type='http', auth="user", website=True)
    def portal_my_id_application_detail(self, application_id, **kw):
        partner = request.env.user.partner_id
        # Find by id AND scoped to the current partner so a portal user can't
        # snoop another applicant's record by guessing the id. Falls back to a
        # plain id lookup so internal users (admin/officer) — whose record rule
        # grants all — can still open a record via the portal.
        application = request.env['national.id.application'].sudo().search([
            ('id', '=', application_id),
            ('partner_id', '=', partner.id),
        ], limit=1)
        if not application:
            application = request.env['national.id.application'].search([('id', '=', application_id)], limit=1)
            if not application:
                return request.redirect('/my/id_applications')

        values = {
            'application': application,
            'page_name': 'id_application_detail',
        }
        return request.render("national_id_application.portal_id_application_page", values)
