import base64
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

class NationalIdApplicationController(http.Controller):
    @http.route('/id_application', type='http', auth='public', website=True)
    def id_application_form(self, **kwargs):
        return request.render('national_id_application.application_form_template', {})
        
    @http.route('/id_application/submit', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def id_application_submit(self, **post):
        photo_file = request.httprequest.files.get('photo')
        lc_letter_file = request.httprequest.files.get('lc_letter')
        
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
        
        if request.env.user.id != request.env.ref('base.public_user').id:
            vals['partner_id'] = request.env.user.partner_id.id
            
        application = request.env['national.id.application'].sudo().create(vals)
        
        return request.render('national_id_application.application_thank_you', {
            'application_ref': application.name
        })

class CustomerPortalIDApp(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'id_application_count' in counters:
            values['id_application_count'] = request.env['national.id.application'].search_count([
                ('partner_id', '=', request.env.user.partner_id.id)
            ])
        return values

    @http.route(['/my/id_applications', '/my/id_applications/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_id_applications(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        IdApplication = request.env['national.id.application']

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
        application = request.env['national.id.application'].search([('id', '=', application_id)])
        if not application:
            return request.redirect('/my')

        values = {
            'application': application,
            'page_name': 'id_application_detail',
        }
        return request.render("national_id_application.portal_id_application_page", values)
