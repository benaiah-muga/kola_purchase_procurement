from odoo import api, fields, models, _
from odoo.exceptions import UserError
from markupsafe import Markup

class NationalIdApplication(models.Model):
    _name = 'national.id.application'
    _description = 'National ID Application'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    applicant_name = fields.Char(string='Applicant Name', required=True, tracking=True)
    date_of_birth = fields.Date(string='Date of Birth', required=True, tracking=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female')
    ], string='Gender', required=True, tracking=True)
    nin_number = fields.Char(string='NIN (Optional)', tracking=True)
    phone = fields.Char(string='Phone Number', tracking=True)
    email = fields.Char(string='Email Address', tracking=True)
    address = fields.Text(string='Physical Address', tracking=True)
    
    photo = fields.Binary(string='Applicant Photo', attachment=True)
    photo_filename = fields.Char(string='Photo Filename')
    
    lc_letter = fields.Binary(string='LC Reference Letter', attachment=True)
    lc_letter_filename = fields.Char(string='LC Letter Filename')
    
    partner_id = fields.Many2one('res.partner', string='Portal User', default=lambda self: self.env.user.partner_id)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', tracking=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('national.id.application') or _('New')
        return super().create(vals_list)

    def _log_state_change(self, action_label):
        """Post an audit message in the chatter naming the user who acted.

        mail.thread field tracking alone is unreliable for programmatic state
        changes (e.g. buttons calling action_* methods), so each action posts
        an explicit message to guarantee the approving user and action are
        recorded for audit.
        """
        user = self.env.user.name
        for app in self:
            app.message_post(
                body=Markup(
                    '<b>{action}</b> by <b>{user}</b>.<br/>'
                    'Application <b>{ref}</b> is now <b>{state}</b>.'
                ).format(
                    action=action_label,
                    user=user,
                    ref=app.name,
                    state=dict(self._fields['state'].selection).get(app.state, app.state),
                ),
            )

    def action_submit(self):
        self.write({'state': 'submitted'})
        self._log_state_change(_('Application Submitted'))

    def action_review(self):
        self.write({'state': 'under_review'})
        self._log_state_change(_('Moved to Review'))

    def action_approve(self):
        self.write({'state': 'approved'})
        self._log_state_change(_('Application Approved'))

    def action_reject(self):
        self.write({'state': 'rejected'})
        self._log_state_change(_('Application Rejected'))
